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
from urllib.parse import parse_qsl

import httpx

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])  # masalan: -1001234567890
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

INIT_DATA_MAX_AGE = 24 * 60 * 60  # 24 soat

log = logging.getLogger("telegram_utils")


class TelegramTopicMissingError(RuntimeError):
    """Filialga bog'langan forum-topic guruhda endi mavjud emas (masalan
    admin uni qo'lda o'chirib yuborgan). Bunday holatda oddiy qayta
    urinish yordam bermaydi — topic'ni QAYTADAN yaratish kerak. app.py
    shu xatoni ushlab, yangi topic yaratib, qayta urinadi."""


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
async def _tg_request(client: httpx.AsyncClient, method: str, url: str,
                       max_retries: int = 3, **kwargs) -> dict:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = await client.request(method, url, **kwargs)
        except (httpx.TransportError, httpx.TimeoutException) as e:
            # Ulanish darajasidagi xato (uzilish, timeout) — qayta urinamiz.
            last_exc = e
            if attempt < max_retries:
                await asyncio.sleep(0.8 * (2 ** attempt))
                continue
            raise RuntimeError(f"Telegram API bilan aloqa o'rnatib bo'lmadi: {e}") from e

        # 429 — flood control: Telegram ko'rsatgan `retry_after` muddatida kutamiz.
        if resp.status_code == 429:
            try:
                retry_after = resp.json().get("parameters", {}).get("retry_after", 2)
            except Exception:  # noqa: BLE001
                retry_after = 2
            if attempt < max_retries:
                await asyncio.sleep(min(retry_after, 10) + 0.5)
                continue

        # 5xx — Telegram tomonidagi vaqtinchalik muammo, qayta urinamiz.
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
            # Topic o'chirib yuborilgan / mavjud emas bo'lsa, oddiy qayta
            # urinish foyda bermaydi — buni alohida xato turi bilan
            # belgilaymiz, shunda chaqiruvchi (app.py) yangi topic yaratib
            # qayta urinishi mumkin.
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

    # auth_date muddati o'tganini tekshirish
    auth_date = int(parsed.get("auth_date", "0"))
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

    user = json.loads(parsed.get("user", "{}"))
    return {
        "id": user.get("id"),
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "username": user.get("username"),
    }


async def create_forum_topic(name: str) -> int:
    """Guruhda filial nomi bilan yangi mavzu (topic) ochadi, thread_id qaytaradi."""
    async with httpx.AsyncClient(timeout=20) as client:
        data = await _tg_request(
            client, "POST", f"{TG_API}/createForumTopic",
            json={"chat_id": GROUP_CHAT_ID, "name": name},
        )
        return data["result"]["message_thread_id"]


async def delete_message(chat_id: int, message_id: int) -> None:
    """Xabarni chatdan o'chiradi — masalan xodimning shaxsiy chatiga
    zaxira sifatida yuborilgan qoralama rasmi endi kerak bo'lmay
    qolganda (hisobot yuborilgach, rasm o'chirilganda, yoki qoralama
    eskirib avtomatik tozalanganda). Ataylab XATOLIKNI KO'TARMAYDI —
    bu "iloji bo'lsa tozalash", muvaffaqiyatsiz bo'lsa ham (masalan
    xabar allaqachon qo'lda o'chirilgan bo'lsa) asosiy oqimga
    to'sqinlik qilmasligi kerak."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.post(f"{TG_API}/deleteMessage", data={"chat_id": chat_id, "message_id": message_id})
    except Exception:  # noqa: BLE001
        pass


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
    async with httpx.AsyncClient(timeout=60) as client:
        result = await _tg_request(client, "POST", f"{TG_API}/sendPhoto", data=data, files=files)
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
    async with httpx.AsyncClient(timeout=30) as client:
        result = await _tg_request(client, "POST", f"{TG_API}/sendPhoto", data=data)
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
    async with httpx.AsyncClient(timeout=60) as client:
        result = await _tg_request(client, "POST", f"{TG_API}/sendPhoto", data=data, files=files)
        msg = result["result"]
        largest_photo = msg["photo"][-1]
        return {"file_id": largest_photo["file_id"], "message_id": msg["message_id"]}


async def download_file_bytes(file_id: str) -> bytes:
    """Telegramda (file_id orqali) saqlangan faylni qaytadan yuklab oladi —
    masalan qoralama preview'ini mini appda ko'rsatish uchun. Bu baytlar
    hech qayerda saqlanmaydi, faqat shu so'rov davomida brauzerga
    o'tkaziladi (proxy qilinadi)."""
    async with httpx.AsyncClient(timeout=30) as client:
        result = await _tg_request(client, "GET", f"{TG_API}/getFile", params={"file_id": file_id})
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
    async with httpx.AsyncClient(timeout=90) as client:
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
            result = await _tg_request(client, "POST", f"{TG_API}/sendMediaGroup", data=data, files=files)
            for msg in result["result"]:
                largest_photo = msg["photo"][-1]
                out.append({"file_id": largest_photo["file_id"], "message_id": msg["message_id"]})

    return out
