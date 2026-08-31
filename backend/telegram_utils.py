"""
- Telegram WebApp initData ni tekshirish (xavfsizlik uchun majburiy)
- Bot API orqali rasm yuborish / forum-topic yaratish
"""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
from collections import deque
from urllib.parse import parse_qsl

import httpx

# Env yetishmasa — import paytidagi noaniq KeyError/ValueError o'rniga
# tushunarli xato beramiz (Railway loglarida sababi darhol ko'rinadi).
try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as e:
    raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan (@BotFather tokeni).") from e

try:
    GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])  # masalan: -1001234567890
except KeyError as e:
    raise RuntimeError("GROUP_CHAT_ID muhit o'zgaruvchisi o'rnatilmagan.") from e
except ValueError as e:
    raise RuntimeError("GROUP_CHAT_ID butun son bo'lishi kerak (masalan -1001234567890).") from e

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# initData amal qilish muddati. Ilgari 24 soat edi — o'g'irlangan initData
# (u query-string orqali loglarga tushadi) bir kun davomida to'liq huquq
# berardi. 4 soat — smena davomida ishlash uchun yetarli, lekin xavf oynasi
# olti barobar qisqaradi. INIT_DATA_MAX_AGE_SECONDS env orqali sozlanadi.
INIT_DATA_MAX_AGE = int(os.environ.get("INIT_DATA_MAX_AGE_SECONDS", str(4 * 60 * 60)))

log = logging.getLogger("telegram_utils")


class TelegramTopicMissingError(RuntimeError):
    """Filialga bog'langan forum-topic guruhda endi mavjud emas (masalan
    admin uni qo'lda o'chirib yuborgan). Bunday holatda oddiy qayta
    urinish yordam bermaydi — topic'ni QAYTADAN yaratish kerak. app.py
    shu xatoni ushlab, yangi topic yaratib, qayta urinadi."""


class TelegramFloodError(RuntimeError):
    """Telegram flood-control tufayli so'rovni hozir bajarib bo'lmadi.
    Bu VAQTINCHALIK xato — navbat (outbox) worker'i uni keyinroq qayta
    uradi. `retry_after` — Telegram tavsiya qilgan kutish muddati."""

    def __init__(self, description: str, retry_after: int):
        super().__init__(description)
        self.retry_after = retry_after


# ============================================================
#  MARKAZLASHGAN CHEKLOV (rate limiter) — eng muhim tuzatish.
#
#  ILDIZ SABAB: Telegram bitta guruhga DAQIQASIGA taxminan 20 ta xabar
#  qabul qiladi (hujjatlashtirilgan cheklov), umumiy tezlik esa 30
#  so'rov/soniya. Ilgari kod bu cheklovlarni umuman hisobga olmasdi:
#  smena almashinuvida 10 xodim bir vaqtda hisobot yuborsa, bitta guruhga
#  bir zumda 80 ta xabar urinardi. Telegram 429 qaytarardi, va eski kod
#  `min(retry_after, 10)` bilan Telegram so'ragan muddatdan ANCHA erta
#  qayta urinib, yana 429 olardi — natijada 3 ta urinish ham behuda
#  sarflanib, butun hisobot "Telegram bilan aloqa muammosi" xatosi bilan
#  tugardi. O'lchov: 10 xodimdan 0 tasi hisobotni yubora oldi.
#
#  Yechim: barcha Telegram so'rovlari shu yerdan o'tadi va cheklovga
#  OLDINDAN rioya qiladi — ya'ni 429 ga umuman urilmaydi. 429 baribir
#  kelsa, `retry_after` TO'LIQ hurmat qilinadi (cheklab qo'yilmaydi).
# ============================================================
GROUP_RATE_LIMIT = int(os.environ.get("TG_GROUP_RATE_LIMIT", "18"))      # xabar / 60s (20 dan xavfsiz pastroq)
GROUP_RATE_WINDOW = float(os.environ.get("TG_GROUP_RATE_WINDOW", "60"))
GLOBAL_RATE_LIMIT = int(os.environ.get("TG_GLOBAL_RATE_LIMIT", "25"))    # so'rov / soniya (30 dan pastroq)
PRIVATE_MIN_INTERVAL = float(os.environ.get("TG_PRIVATE_MIN_INTERVAL", "1.05"))  # bitta shaxsiy chatga


class _RateLimiter:
    """Telegram cheklovlariga oldindan rioya qiluvchi darvoza.

    Uch qatlam:
      1) global   — 25 so'rov / soniya (barcha chatlar bo'yicha)
      2) guruh    — 18 xabar / 60 soniya (GROUP_CHAT_ID uchun)
      3) shaxsiy  — har bir foydalanuvchi chatiga 1 soniyada 1 xabar
    """

    def __init__(self):
        self._lock = asyncio.Lock()
        self._global_hits: deque[float] = deque()
        self._group_hits: deque[float] = deque()
        self._private_last: dict[int, float] = {}

    @staticmethod
    def _prune(dq: deque, window: float, now: float) -> None:
        while dq and dq[0] <= now - window:
            dq.popleft()

    async def acquire(self, chat_id, is_group: bool) -> None:
        """Ruxsat berilgunga qadar kutadi. Hech qachon xato ko'tarmaydi."""
        while True:
            async with self._lock:
                now = time.monotonic()
                wait = 0.0

                self._prune(self._global_hits, 1.0, now)
                if len(self._global_hits) >= GLOBAL_RATE_LIMIT:
                    wait = max(wait, self._global_hits[0] + 1.0 - now)

                if is_group:
                    self._prune(self._group_hits, GROUP_RATE_WINDOW, now)
                    if len(self._group_hits) >= GROUP_RATE_LIMIT:
                        wait = max(wait, self._group_hits[0] + GROUP_RATE_WINDOW - now)
                else:
                    last = self._private_last.get(chat_id)
                    if last is not None and now - last < PRIVATE_MIN_INTERVAL:
                        wait = max(wait, last + PRIVATE_MIN_INTERVAL - now)
                    # Xotira cheksiz o'smasligi uchun: 10 daqiqadan eski
                    # yozuvlarni tozalab turamiz (audit topgan oqmaning
                    # oldini oladi — bu yerda tozalash VAQT bo'yicha,
                    # kalit soniga bog'liq emas).
                    if len(self._private_last) > 500:
                        cutoff = now - 600
                        for k in [k for k, v in self._private_last.items() if v < cutoff]:
                            self._private_last.pop(k, None)

                if wait <= 0:
                    self._global_hits.append(now)
                    if is_group:
                        self._group_hits.append(now)
                    else:
                        self._private_last[chat_id] = now
                    return

            # Qulfni bo'shatib kutamiz — boshqa so'rovlar bloklanmaydi.
            await asyncio.sleep(min(wait, 5.0) + 0.02)

    def penalise_group(self, seconds: float) -> None:
        """Telegram baribir 429 qaytarsa — guruh oynasini sun'iy ravishda
        to'ldirib qo'yamiz, shunda keyingi so'rovlar o'z-o'zidan kutadi."""
        now = time.monotonic()
        self._group_hits.clear()
        for _ in range(GROUP_RATE_LIMIT):
            self._group_hits.append(now + seconds - GROUP_RATE_WINDOW)


_limiter = _RateLimiter()


# ============================================================
#  Umumiy HTTP client — ilgari HAR BIR Telegram chaqiruvi uchun yangi
#  `httpx.AsyncClient` ochilardi (yangi TCP+TLS qo'l berishuvi). Hisobot
#  yuborishda bu o'nlab ortiqcha ulanish demak edi. Endi bitta umumiy
#  client ulanishlarni qayta ishlatadi — sezilarli darajada tezroq.
# ============================================================
_client: "httpx.AsyncClient | None" = None
_client_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        async with _client_lock:
            if _client is None or _client.is_closed:
                _client = httpx.AsyncClient(
                    timeout=httpx.Timeout(connect=10.0, read=90.0, write=90.0, pool=10.0),
                    limits=httpx.Limits(max_connections=30, max_keepalive_connections=10),
                )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


# ============================================================
#  Tarmoq/Telegram darajasidagi vaqtinchalik xatoliklarga chidamli
#  so'rov yuboruvchi umumiy funksiya.
#
#  MUHIM TUZATISH: ilgari har bir Telegram API chaqiruvi (sendPhoto,
#  sendMediaGroup va h.k.) FAQAT BITTA marta urinilardi. Amalda esa:
#    - mobil internetda (ayniqsa iPhone/Android'da ilova fonga o'tib,
#      qayta faollashganda) so'rov davomida ulanish bir lahzaga uzilib
#      qolishi odatiy hol (httpx.TransportError / TimeoutException);
#    - Telegram vaqti-vaqti bilan 429 (Too many requests) yoki 502/503
#      qaytarishi mumkin (flood-control yoki serverning vaqtinchalik band
#      bo'lishi).
#  Bularning BIRI yuz berishi bilan butun "Yuborish" so'rovi xatolik
#  bilan tugab, guruhga HECH NARSA yetib bormas edi — garchi muammo
#  shunchaki bir lahzalik bo'lsa ham. Endi shu turdagi xatoliklarda
#  avtomatik (eksponensial orqaga chekinish bilan) qayta uriniladi,
#  shundan keyingina foydalanuvchiga xatolik ko'rsatiladi.
# ============================================================
async def _tg_request(method: str, url: str, chat_id=None, max_retries: int = 3,
                       client: httpx.AsyncClient | None = None, **kwargs) -> dict:
    """Har qanday Telegram chaqiruvi shu yerdan o'tadi.

    TUZATILDI (1): `chat_id` bo'yicha cheklovga OLDINDAN rioya qilinadi —
    so'rov yuborilishidan oldin navbat kutiladi, shuning uchun 429 ga
    deyarli hech qachon urilmaydi.

    TUZATILDI (2): 429 baribir kelsa, Telegram so'ragan `retry_after`
    TO'LIQ kutiladi. Ilgari `min(retry_after, 10)` bilan cheklangan edi —
    Telegram 45 soniya so'rasa ham 10 soniyada qayta urinilardi, bu esa
    yana 429 bilan tugardi va uchala urinish ham behuda ketardi.

    TUZATILDI (3): urinishlar tugagach endi umumiy `RuntimeError` emas,
    `TelegramFloodError` ko'tariladi — navbat worker'i buni VAQTINCHALIK
    xato deb tushunadi va keyinroq qayta uradi (hisobot yo'qolmaydi).
    """
    is_group = chat_id is not None and str(chat_id) == str(GROUP_CHAT_ID)
    cl = client or await get_client()
    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        if chat_id is not None:
            await _limiter.acquire(chat_id, is_group)

        try:
            resp = await cl.request(method, url, **kwargs)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(0.8 * (2 ** attempt))
                continue
            raise RuntimeError(f"Telegram API bilan aloqa o'rnatib bo'lmadi: {e}") from e

        # 429 — flood control.
        if resp.status_code == 429:
            try:
                retry_after = int(resp.json().get("parameters", {}).get("retry_after", 5))
            except Exception:  # noqa: BLE001
                retry_after = 5
            if is_group:
                _limiter.penalise_group(retry_after)
            log.warning("Telegram 429 (%s): retry_after=%ss, urinish %d/%d",
                        url.rsplit("/", 1)[-1], retry_after, attempt + 1, max_retries + 1)
            if attempt < max_retries:
                await asyncio.sleep(retry_after + 0.5)   # TO'LIQ kutamiz
                continue
            raise TelegramFloodError(
                f"Telegram flood-control: {retry_after}s kutish kerak", retry_after)

        if resp.status_code >= 500 and attempt < max_retries:
            last_exc = RuntimeError(f"HTTP {resp.status_code}")
            await asyncio.sleep(0.8 * (2 ** attempt))
            continue

        try:
            result = resp.json()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"Telegram javobini o'qib bo'lmadi (HTTP {resp.status_code}): {e}") from e

        if not result.get("ok"):
            description = str(result.get("description", ""))
            if "thread not found" in description.lower() or "TOPIC_DELETED" in description:
                raise TelegramTopicMissingError(description)
            raise RuntimeError(f"Telegram xato ({method} {url}): {result}")

        return result

    raise RuntimeError(f"Telegram API bilan aloqa o'rnatib bo'lmadi: {last_exc}")


# Telegram caption (rasm tagidagi matn) uchun qat'iy chegara — 1024 UTF-16
# birlik. Undan uzun caption yuborilsa Telegram BUTUN so'rovni
# "MESSAGE_CAPTION_TOO_LONG" deb rad etardi va hisobot guruhga umuman
# yetib bormas edi (ayniqsa uzun izoh yozilganda). Endi shunday holatda
# caption avtomatik xavfsiz uzunlikkacha qisqartiriladi.
CAPTION_LIMIT = 1024


def safe_caption(text: str) -> str:
    if len(text) <= CAPTION_LIMIT:
        return text
    return text[: CAPTION_LIMIT - 1].rstrip() + "…"


def validate_init_data(init_data: str) -> dict | None:
    """
    Telegram hujjatiga muvofiq WebApp.initData ni tekshiradi.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    Muvaffaqiyatli bo'lsa foydalanuvchi ma'lumotlarini qaytaradi, aks holda None.
    """
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None

    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # auth_date muddati o'tganini tekshirish.
    # TUZATILDI: ilgari `int(...)` to'g'ridan-to'g'ri chaqirilardi va
    # `auth_date=abc` kabi buzuq qiymat ValueError ko'tarib, ilova
    # AUTENTIFIKATSIYASIZ 500 xato qaytarardi hamda ulanishni uzardi.
    # Endi har qanday buzuq initData oddiygina 401 bo'ladi.
    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except (TypeError, ValueError):
        return None
    if time.time() - auth_date > INIT_DATA_MAX_AGE:
        return None

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(parsed.items())
    )
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    # `user` maydoni ham buzuq JSON bo'lishi mumkin — 500 o'rniga 401.
    try:
        user = json.loads(parsed.get("user", "{}"))
    except (TypeError, ValueError):
        return None
    if not isinstance(user, dict):
        return None
    return {
        "id": user.get("id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "username": user.get("username"),
    }


async def send_text_message(chat_id: int, text: str) -> None:
    """Oddiy matnli xabar yuboradi (masalan foydalanuvchi botga /start
    bosganda javob berish uchun, yoki hisobot yetkazilgani/yetkazilmagani
    haqida xabar berish uchun). Ataylab xatolikni KO'TARMAYDI — javob
    berolmasa (masalan foydalanuvchi botni bloklagan bo'lsa) asosiy
    oqimga to'sqinlik qilmaydi."""
    try:
        await _tg_request("POST", f"{TG_API}/sendMessage", chat_id=chat_id, max_retries=1,
                          json={"chat_id": chat_id, "text": text, "disable_notification": True})
    except Exception:  # noqa: BLE001
        pass


async def create_forum_topic(name: str) -> int:
    """Guruhda filial nomi bilan yangi mavzu (topic) ochadi, thread_id qaytaradi."""
    data = await _tg_request("POST", f"{TG_API}/createForumTopic", chat_id=GROUP_CHAT_ID,
                             json={"chat_id": GROUP_CHAT_ID, "name": name})
    return data["result"]["message_thread_id"]


# Telegram "xabarni o'chirib bo'lmaydi" deydigan holatlar — bularda qayta
# urinishning ma'nosi yo'q (xabar allaqachon yo'q yoki 48 soatdan eski).
_DELETE_PERMANENT = (
    "message to delete not found",
    "message can't be deleted",
    "message identifier is not specified",
    "chat not found",
    "bot was blocked",
)


async def delete_message(chat_id: int, message_id: int) -> bool:
    """Xodimning shaxsiy chatidagi zaxira nusxa xabarini o'chiradi.

    TUZATILDI — "zaxira nusxalar qolib ketyapti" muammosining ILDIZ
    SABABI shu funksiyada edi. Ilgari u:
      - `_tg_request`dan foydalanmasdi (ya'ni na cheklov, na qayta
        urinish bor edi), va
      - `except Exception: pass` bilan HAR QANDAY xatoni jimgina yutardi.
    Natijada band paytda Telegram 429 qaytarsa, o'chirish so'rovi
    shunchaki yo'qolardi — logda ham, bazada ham iz qolmasdi, va zaxira
    nusxa xodimning chatida abadiy qolib ketardi.

    Endi: cheklov orqali o'tadi, qayta urinadi, va MUVAFFAQIYATSIZ
    bo'lsa False qaytaradi — chaqiruvchi (app.py'dagi o'chirish navbati)
    uni keyinroq qayta uradi. Xabar allaqachon yo'q bo'lsa — bu ham
    "bajarildi" hisoblanadi (True)."""
    try:
        await _tg_request("POST", f"{TG_API}/deleteMessage", chat_id=chat_id, max_retries=2,
                          data={"chat_id": chat_id, "message_id": message_id})
        return True
    except TelegramFloodError:
        return False
    except RuntimeError as e:
        text = str(e).lower()
        if any(marker in text for marker in _DELETE_PERMANENT):
            return True   # o'chirishning hojati qolmagan
        log.warning("delete_message muvaffaqiyatsiz (chat=%s msg=%s): %s", chat_id, message_id, e)
        return False
    except Exception as e:  # noqa: BLE001
        log.warning("delete_message kutilmagan xato: %r", e)
        return False


async def send_photo_to_topic(thread_id: int, photo_bytes: bytes, filename: str,
                               caption: str) -> dict:
    """Rasmni tegishli filial mavzusiga (topic) yuboradi. {file_id, message_id} qaytaradi."""
    files = {"photo": (filename, photo_bytes, "image/jpeg")}
    data = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": thread_id,
        "caption": safe_caption(caption),
        "parse_mode": "HTML",
    }
    result = await _tg_request("POST", f"{TG_API}/sendPhoto", chat_id=GROUP_CHAT_ID,
                               data=data, files=files)
    msg = result["result"]
    largest_photo = msg["photo"][-1]
    return {"file_id": largest_photo["file_id"], "message_id": msg["message_id"]}


async def send_photo_to_topic_by_file_id(thread_id: int, file_id: str, caption: str) -> dict:
    """send_photo_to_topic bilan bir xil, lekin fayl BAYTLARINI qayta
    yuklamasdan — Telegramda allaqachon mavjud rasmni uning file_id'si
    orqali to'g'ridan-to'g'ri jo'natadi (masalan qoralamada saqlangan
    rasmni yakuniy yuborishda). Tezroq va serverga yuk solmaydi."""
    data = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": thread_id,
        "photo": file_id,
        "caption": safe_caption(caption),
        "parse_mode": "HTML",
    }
    result = await _tg_request("POST", f"{TG_API}/sendPhoto", chat_id=GROUP_CHAT_ID, data=data)
    msg = result["result"]
    largest_photo = msg["photo"][-1]
    return {"file_id": largest_photo["file_id"], "message_id": msg["message_id"]}


async def send_draft_photo_to_owner(user_id: int, photo_bytes: bytes, filename: str) -> dict:
    """QORALAMA rasmini bazaga EMAS, Telegramning o'ziga — xodimning
    botga shaxsiy chatiga ("zaxira nusxa" sifatida, ovozsiz) yuboradi.
    Qaytgan `file_id` (kichkina matn) bazada saqlanadi, rasmning o'zi
    esa Telegram serverlarida qoladi — shu tufayli Postgres hech qachon
    rasm baytlari bilan to'lib qolmaydi.

    Bu xodim uchun kutilmagan emas: u allaqachon shu bot bilan
    suhbatni boshlagan (mini app aynan shu bot orqali ochilgan), shuning
    uchun bot unga xabar yuborishga ruxsatga ega."""
    files = {"photo": (filename, photo_bytes, "image/jpeg")}
    data = {
        "chat_id": user_id,
        "caption": "🗂 Avtomatik zaxira nusxa — hisobot hali yuborilmagan",
        "disable_notification": True,
    }
    result = await _tg_request("POST", f"{TG_API}/sendPhoto", chat_id=user_id, data=data, files=files)
    msg = result["result"]
    largest_photo = msg["photo"][-1]
    return {"file_id": largest_photo["file_id"], "message_id": msg["message_id"]}


async def download_file_bytes(file_id: str) -> bytes:
    """Telegramda (file_id orqali) saqlangan faylni qaytadan yuklab oladi —
    masalan qoralama preview'ini mini appda ko'rsatish uchun. Bu baytlar
    hech qayerda saqlanmaydi, faqat shu so'rov davomida brauzerga
    o'tkaziladi (proxy qilinadi)."""
    client = await get_client()
    result = await _tg_request("GET", f"{TG_API}/getFile", params={"file_id": file_id})
    file_path = result["result"]["file_path"]
    file_resp = await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}")
    file_resp.raise_for_status()
    return file_resp.content


# Telegram sendMediaGroup bitta so'rovda ko'pi bilan 10 ta media qabul qiladi.
MEDIA_GROUP_CHUNK_SIZE = 10


async def send_media_group_to_topic(thread_id: int, items: list[dict], caption: str) -> list[dict]:
    """Bir nechta rasmni BITTA albom (media group) sifatida filial mavzusiga
    yuboradi — Telegramda barchasi bitta xabar/albom bo'lib ko'rinadi.
    Caption faqat albomning birinchi rasmiga qo'yiladi.

    Har bir `items` elementi ikki turdan biri bo'lishi mumkin (ARALASH
    holda ham ishlaydi, bitta albom ichida ham):
      - {"file_id": "..."}              — Telegramda ALLAQACHON mavjud rasm
                                           (qoralamadan, qayta yuklanmaydi)
      - {"data": b"...", "filename": ".."} — hali Telegramga tushmagan
                                           xom baytlar (eski/legacy holat)

    Agar 10 tadan ko'p rasm bo'lsa, 10 talik bo'laklarga bo'linib ketma-ket
    albomlar sifatida yuboriladi; caption faqat birinchi bo'lakka qo'yiladi.
    """
    caption = safe_caption(caption)
    out: list[dict] = []
    for chunk_start in range(0, len(items), MEDIA_GROUP_CHUNK_SIZE):
        chunk = items[chunk_start:chunk_start + MEDIA_GROUP_CHUNK_SIZE]

        if len(chunk) == 1:
            # sendMediaGroup kamida 2 ta media talab qiladi — yagona
            # rasm qolsa oddiy sendPhoto bilan yuboramiz.
            item = chunk[0]
            item_caption = caption if chunk_start == 0 else ""
            if "file_id" in item:
                sent = await send_photo_to_topic_by_file_id(thread_id, item["file_id"], item_caption)
            else:
                sent = await send_photo_to_topic(thread_id, item["data"], item["filename"], item_caption)
            out.append(sent)
            continue

        media = []
        files = {}
        for idx, item in enumerate(chunk):
            media_item = {"type": "photo"}
            if "file_id" in item:
                media_item["media"] = item["file_id"]
            else:
                attach_name = f"photo{chunk_start + idx}"
                files[attach_name] = (item["filename"], item["data"], "image/jpeg")
                media_item["media"] = f"attach://{attach_name}"
            if idx == 0 and chunk_start == 0:
                media_item["caption"] = caption
                media_item["parse_mode"] = "HTML"
            media.append(media_item)

        data = {
            "chat_id": GROUP_CHAT_ID,
            "message_thread_id": thread_id,
            "media": json.dumps(media),
        }
        result = await _tg_request("POST", f"{TG_API}/sendMediaGroup", chat_id=GROUP_CHAT_ID,
                                   data=data, files=files)
        for msg in result["result"]:
            largest_photo = msg["photo"][-1]
            out.append({"file_id": largest_photo["file_id"], "message_id": msg["message_id"]})

    return out
