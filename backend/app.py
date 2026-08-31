"""
Filial Feedback Mini App — asosiy backend (FastAPI).

Ishga tushirish:
    uvicorn app:app --host 0.0.0.0 --port 8000

Muhit o'zgaruvchilari (.env):
    BOT_TOKEN, GROUP_CHAT_ID, DATABASE_URL
"""
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

# ============================================================
#  Logging — ilgari hamma joyda oddiy print() ishlatilardi. print()
#  buferlanishi va Railway loglarida vaqt belgisisiz/darajasiz chiqishi
#  mumkin. Endi standart `logging` moduli: har xabar vaqt + daraja
#  (INFO/WARNING/ERROR) bilan chiqadi, kerak bo'lsa LOG_LEVEL env orqali
#  sozlanadi.
# ============================================================
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("app")

# ---------- Sozlamalar (env orqali o'zgartirsa bo'ladi) ----------
# Qoralama (draft) yashash muddati. Ilgari 15 daqiqa qattiq yozilgan edi
# — bu juda qisqa: sekin internetli yoki ko'p bo'limli hisobot ustida
# ishlayotgan xodim shuncha vaqt chiqib tursa, olingan rasmlarini
# yo'qotardi. Endi standart 60 daqiqa, va DRAFT_TTL_MINUTES env orqali
# o'zgartirsa bo'ladi.
DRAFT_TTL_MINUTES = int(os.environ.get("DRAFT_TTL_MINUTES", "60"))
# Tozalash sikli qancha tez-tez ishlashi. Ilgari har 2 daqiqada edi —
# 5 daqiqa ham yetarli va Railway'da bekorga uyg'onishlarni (CPU) kamaytiradi.
DRAFT_CLEANUP_INTERVAL_SECONDS = int(os.environ.get("DRAFT_CLEANUP_INTERVAL_SECONDS", "300"))

# Server (Railway) UTC bo'yicha ishlaydi, lekin filiallar O'zbekiston
# vaqti (UTC+5, Asia/Tashkent) bo'yicha ishlaydi. Shu sababli xabarlardagi
# vaqt shu offset bilan hisoblanadi, aks holda Telegram guruhida vaqt
# 5 soat orqada ko'rsatilardi.
TASHKENT_TZ = timezone(timedelta(hours=5))

try:
    from dotenv import load_dotenv
    load_dotenv()  # faqat lokal ishlashda .env faylini o'qiydi; Railway'da shart emas
except ImportError:
    pass

from fastapi import FastAPI, Form, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from typing import Optional

import asyncio
import asyncpg

import db
import telegram_utils as tg
from telegram_utils import TelegramTopicMissingError
import bot_listener
import translate_utils

app = FastAPI(title="Street77 & Wok System App")

# Bootstrap uchun: ilk marta hech qanday superadmin bo'lmaganda shu yerdan
# ruxsat berish mumkin (.env dagi SUPERADMIN_IDS="123456789,987654321").
# Ilova ishga tushganda bu id'lar avtomatik allowed_users jadvaliga
# is_superadmin=TRUE qilib qo'shiladi.
SUPERADMIN_IDS = [
    int(x) for x in os.environ.get("SUPERADMIN_IDS", "").replace(" ", "").split(",") if x
]

NOT_ALLOWED_MESSAGE = "Ushbu bot ishlamaydi"

# Frontenddagi i18n.js bilan bir xil ro'yxat — foydalanuvchi tanlagan til
# har doim shu 3 tadan biriga tushishini kafolatlaydi (aks holda "uz"ga
# tushiladi).
SUPPORTED_LANGS = {"uz", "ru", "en"}


def _norm_lang(lang: Optional[str]) -> str:
    return lang if lang in SUPPORTED_LANGS else "uz"


# ============================================================
#  Oddiy, xotira ichidagi rate-limiter (rasm yuklash uchun).
#  Faqat whitelist'dagi foydalanuvchilar yuklaydi, shuning uchun xavf
#  past — lekin bitta foydalanuvchi (yoki o'g'irlangan initData) juda
#  ko'p rasmni ketma-ket yuborib, botni Telegram flood-limitiga urib
#  qo'yishining oldini olish uchun sirpanuvchi-oyna (sliding window)
#  cheklovi qo'yamiz. Yagona servis (bitta process) bo'lgani uchun
#  oddiy dict yetarli; qiymatlar RATE_LIMIT_WINDOW ichida o'z-o'zidan
#  eskiradi. Chegaralar env orqali sozlanadi.
# ============================================================
RATE_LIMIT_MAX = int(os.environ.get("PHOTO_RATE_LIMIT_MAX", "60"))       # oynadagi maksimal yuklash
RATE_LIMIT_WINDOW = int(os.environ.get("PHOTO_RATE_LIMIT_WINDOW", "60"))  # oyna (soniya)
# Yuborish endi juda yengil (faqat bazaga yozadi), lekin baribir cheklaymiz —
# ilgari bu endpointda cheklov umuman yo'q edi.
SUBMIT_RATE_LIMIT = int(os.environ.get("SUBMIT_RATE_LIMIT", "10"))
_rate_hits: dict[int, list[float]] = {}
_rate_last_sweep = 0.0


def _check_rate_limit(user_id: int, limit: int | None = None) -> None:
    """user_id uchun sirpanuvchi-oyna cheklovini tekshiradi. Chegaradan
    oshsa 429 (Too Many Requests) ko'taradi.

    TUZATILDI: tozalash mantig'i ilgari amalda ishlamasdi — u faqat
    `len(_rate_hits) > 5000` bo'lganda va faqat BO'SH ro'yxatli kalitlarni
    o'chirardi; ro'yxat esa faqat o'sha foydalanuvchi QAYTA so'rov
    yuborganda tozalanardi. Ya'ni bir marta kirgan foydalanuvchi kaliti
    abadiy qolib, xotira asta-sekin oqardi. Endi tozalash VAQT bo'yicha:
    har daqiqada oynadan tashqarida qolgan barcha kalitlar o'chiriladi."""
    global _rate_last_sweep
    limit = limit or RATE_LIMIT_MAX
    now = time.monotonic()
    cutoff = now - RATE_LIMIT_WINDOW

    if now - _rate_last_sweep > 60:
        _rate_last_sweep = now
        for uid in [uid for uid, ts in _rate_hits.items() if not ts or ts[-1] <= cutoff]:
            _rate_hits.pop(uid, None)

    hits = _rate_hits.setdefault(user_id, [])
    hits[:] = [t for t in hits if t > cutoff]
    if len(hits) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Juda ko'p so'rov yuborildi. Bir oz kutib, qayta urinib ko'ring.",
        )
    hits.append(now)


# ============================================================
#  FAYL HAJMI CHEGARASI (BLOKER tuzatildi)
#
#  Ilgari `await file.read()` faylni to'liq RAM'ga o'qirdi va hech qanday
#  chegara yo'q edi. O'lchov: 4 ta parallel 100 MB yuklash server
#  xotirasini 66 MB dan 958 MB ga ko'tardi — Railway'ning 512 MB
#  konteynerida bu OOM-kill demak, ya'ni bitta xodim xizmatni to'xtatib
#  qo'yishi mumkin edi.
#
#  Endi fayl 64 KB'lik bo'laklar bilan o'qiladi va chegaradan oshgan
#  zahoti uziladi — server hech qachon chegaradan ko'p xotira
#  band qilmaydi. Telegram'ning o'z chegarasi 10 MB, shuning uchun
#  undan kattasini qabul qilishning ma'nosi ham yo'q.
# ============================================================
MAX_PHOTO_BYTES = int(os.environ.get("MAX_PHOTO_BYTES", str(10 * 1024 * 1024)))
_CHUNK = 64 * 1024

# Rasm formatlarining "magic bytes"lari — Telegram faqat rasmni qabul
# qiladi, shuning uchun boshqa fayl turlarini shu yerda rad etamiz.
_IMAGE_SIGNATURES = (
    b"\xff\xd8\xff",                 # JPEG
    b"\x89PNG\r\n\x1a\n",            # PNG
    b"GIF87a", b"GIF89a",            # GIF
    b"BM",                           # BMP
)


def _looks_like_image(head: bytes) -> bool:
    if any(head.startswith(sig) for sig in _IMAGE_SIGNATURES):
        return True
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":       # WEBP
        return True
    if head[4:8] == b"ftyp" and head[8:12] in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
        return True                                          # HEIC (iPhone)
    return False


async def _read_upload_limited(file: UploadFile) -> bytes:
    """Yuklanayotgan faylni chegara bilan o'qiydi. Chegaradan oshsa
    o'qishni DARHOL to'xtatadi va 413 qaytaradi."""
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(f"Rasm juda katta (maksimal {MAX_PHOTO_BYTES // (1024*1024)} MB). "
                        "Qaytadan suratga oling yoki sifatini pasaytiring."),
            )
    if not buf:
        raise HTTPException(status_code=400, detail="Bo'sh fayl")
    if not _looks_like_image(bytes(buf[:16])):
        raise HTTPException(
            status_code=400,
            detail="Faqat rasm yuborish mumkin (JPEG, PNG, HEIC).",
        )
    return bytes(buf)

# Mini app boshqa domenda joylashgan bo'lishi mumkin (masalan GitHub Pages / Railway static)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  1) YETKAZISH WORKER'I — navbatni (outbox) Telegramga bo'shatadi.
#
#  Bu "hisobot yuborilmay qolyapti" muammosining asosiy yechimi.
#  Ilgari "Yuborish" bosilganda barcha rasmlar SHU SO'ROV ichida
#  Telegramga yuborilardi. Telegram bitta guruhga daqiqasiga ~20 ta
#  xabar qabul qiladi, smena almashinuvida esa 10 xodim × 8 bo'lim = 80
#  xabar bir zumda urinardi — hammasi flood-control'ga tushib, hisobot
#  xatolik bilan tugardi (o'lchov: 10 xodimdan 0 tasi yubora oldi).
#
#  Endi so'rov faqat navbatga yozadi va darhol qaytadi. Shu worker esa
#  navbatni Telegram tezligida, xatolarni qayta urinish bilan bo'shatadi.
#  Xodim kutmaydi, xato ko'rmaydi, va hech narsa yo'qolmaydi.
# ============================================================
OUTBOX_MAX_ATTEMPTS = int(os.environ.get("OUTBOX_MAX_ATTEMPTS", "12"))
OUTBOX_IDLE_SLEEP = float(os.environ.get("OUTBOX_IDLE_SLEEP", "1.0"))


async def _resolve_thread_id(filial_id: int, filial_name: str) -> int:
    """Filialning forum-topic'ini topadi, kerak bo'lsa yaratadi.

    TUZATILDI: ilgari topic YARATISH atomik "claim"dan OLDIN bajarilardi,
    shuning uchun bir vaqtda kelgan 3 ta so'rov Telegramda 3 ta topic
    yaratardi va bazaga faqat bittasi yozilardi — guruhda "yetim" bo'sh
    mavzular qolib ketardi. Endi butun blok advisory lock ichida: bir
    vaqtning o'zida faqat bitta jarayon topic yaratadi."""
    filial = await db.get_filial(filial_id)
    if filial and filial.get("thread_id"):
        return filial["thread_id"]

    # Filial qatorini qulflab, ikkinchi marta tekshiramiz va faqat
    # shundan keyin topic yaratamiz — shu bilan guruhda "yetim" bo'sh
    # mavzular paydo bo'lmaydi. Butun blok BITTA ulanishda (ichkarida
    # pool'dan qo'shimcha ulanish so'ralmaydi).
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await db.claim_thread_slot(conn, filial_id)
            if row and row.get("thread_id"):
                return row["thread_id"]
            new_thread_id = await tg.create_forum_topic(filial_name)
            await db.set_thread_id_conn(conn, filial_id, new_thread_id)
            log.info("filial #%s uchun yangi topic yaratildi: %s", filial_id, new_thread_id)
            return new_thread_id


async def _deliver_outbox_item(item: dict) -> None:
    """Navbatdagi bitta yozuvni (bitta bo'lim = bitta albom) yetkazadi."""
    photos = item["photos"]
    if isinstance(photos, str):
        photos = json.loads(photos)
    payload = [{"file_id": p["file_id"]} for p in photos if p.get("file_id")]
    if not payload:
        await db.mark_outbox_sent(item["id"])
        return

    thread_id = await _resolve_thread_id(item["filial_id"], item["filial_name"])

    try:
        sent_list = await tg.send_media_group_to_topic(
            thread_id=thread_id, items=payload, caption=item["caption"])
    except TelegramTopicMissingError:
        # Topic guruhda o'chirib yuborilgan — yangisini yaratib, BIR
        # marta qayta uramiz. TUZATILDI: ilgari bu ikkinchi urinishning
        # xatosi hech qayerda ushlanmasdi va 500 bilan tugardi.
        log.warning("outbox #%s: topic topilmadi, qayta yaratilmoqda", item["id"])
        new_thread_id = await tg.create_forum_topic(item["filial_name"])
        await db.set_filial_thread_id(item["filial_id"], new_thread_id)
        sent_list = await tg.send_media_group_to_topic(
            thread_id=new_thread_id, items=payload, caption=item["caption"])

    # Bazaga yozamiz. TUZATILDI: ilgari `zip(photos_meta, sent_list)`
    # ishlatilardi va ro'yxatlar uzunligi mos kelmasa izohlar noto'g'ri
    # rasmga biriktirilardi. Endi indeks bo'yicha xavfsiz moslashtiramiz.
    for idx, sent in enumerate(sent_list):
        meta = photos[idx] if idx < len(photos) else {}
        try:
            await db.add_submission_photo(
                submission_id=item["submission_id"],
                section_id=item["section_id"],
                file_id=sent["file_id"],
                comment=(meta.get("comment") or None),
                sent_message_id=sent["message_id"],
            )
        except asyncpg.ForeignKeyViolationError:
            # Bo'lim oradan o'chirilgan — rasm guruhga yetib bordi,
            # shuning uchun buni xato deb hisoblamaymiz.
            log.warning("outbox #%s: section %s endi mavjud emas, yozuv o'tkazib yuborildi",
                        item["id"], item["section_id"])

    await db.mark_outbox_sent(item["id"])

    # Zaxira nusxalarni o'chirish NAVBATIGA qo'yamiz (fire-and-forget emas).
    await db.enqueue_deletions(
        [(item["telegram_user_id"], p["backup_message_id"])
         for p in photos if p.get("backup_message_id")])


async def _notify_if_complete(submission_id: int, telegram_user_id: int) -> None:
    """Hisobotning barcha bo'limlari yetkazilganda xodimga bir marta
    xabar beramiz. Xodim "Yuborish"dan keyin darhol muvaffaqiyat
    ekranini ko'radi, bu esa yetkazish HAQIQATAN tugaganini tasdiqlaydi."""
    state = await db.submission_delivery_state(submission_id)
    if state["pending"]:
        return
    if state["failed"]:
        if await db.set_submission_delivery(submission_id, "failed"):
            await tg.send_text_message(
                telegram_user_id,
                "⚠️ Hisobotingizning bir qismini guruhga yuborib bo'lmadi. "
                "Iltimos, administratorga xabar bering.")
    else:
        if await db.set_submission_delivery(submission_id, "delivered"):
            await tg.send_text_message(
                telegram_user_id, "✅ Hisobotingiz guruhga muvaffaqiyatli yuborildi.")


async def _outbox_worker():
    log.info("outbox worker ishga tushdi")
    while True:
        try:
            item = await db.take_next_outbox()
            if item is None:
                await asyncio.sleep(OUTBOX_IDLE_SLEEP)
                continue
            try:
                await _deliver_outbox_item(item)
                await _notify_if_complete(item["submission_id"], item["telegram_user_id"])
            except tg.TelegramFloodError as e:
                # Vaqtinchalik — Telegram so'ragan muddatdan keyin qayta uramiz.
                await db.reschedule_outbox(item["id"], e.retry_after + 2, str(e))
            except Exception as e:  # noqa: BLE001
                if item["attempts"] >= OUTBOX_MAX_ATTEMPTS:
                    log.error("outbox #%s: %d urinishdan keyin ham yetkazilmadi: %r",
                              item["id"], item["attempts"], e)
                    await db.mark_outbox_failed(item["id"], repr(e))
                    await _notify_if_complete(item["submission_id"], item["telegram_user_id"])
                else:
                    delay = min(300, 5 * (2 ** min(item["attempts"], 6)))
                    log.warning("outbox #%s xato (urinish %d), %ss dan keyin qayta: %r",
                                item["id"], item["attempts"], delay, e)
                    await db.reschedule_outbox(item["id"], delay, repr(e))
        except asyncio.CancelledError:
            log.info("outbox worker to'xtatildi")
            raise
        except Exception as e:  # noqa: BLE001
            log.error("outbox worker kutilmagan xato: %r", e)
            await asyncio.sleep(3)


# ============================================================
#  2) ZAXIRA NUSXALARNI O'CHIRISH WORKER'I
#
#  "Yuborilgan hisobotlarning bir nechtasi zaxira nusxa bo'lib qolib
#  ketyapti" muammosining yechimi. Ilgari o'chirish
#  `asyncio.create_task(...)` bilan yuborilardi (natija saqlanmasdi —
#  Python bunday task'ni tugashidan oldin yig'ishtirib yuborishi mumkin)
#  va `delete_message` har qanday xatoni jimgina yutardi. Band paytda
#  Telegram 429 qaytarsa, o'chirish shunchaki yo'qolardi.
#  O'lchov: 80 ta zaxira nusxadan 25 tasi o'chirilmay qoldi.
#
#  Endi har bir o'chirish bazadagi navbatda turadi va bajarilgunicha
#  qayta uriniladi.
# ============================================================
async def _deletion_worker():
    log.info("zaxira-nusxa tozalash worker'i ishga tushdi")
    while True:
        try:
            items = await db.take_due_deletions(limit=10)
            if not items:
                await db.drop_exhausted_deletions()
                await asyncio.sleep(3)
                continue
            for it in items:
                ok = await tg.delete_message(it["chat_id"], it["message_id"])
                if ok:
                    await db.finish_deletion(it["id"])
        except asyncio.CancelledError:
            log.info("tozalash worker'i to'xtatildi")
            raise
        except Exception as e:  # noqa: BLE001
            log.error("tozalash worker'i xatosi: %r", e)
            await asyncio.sleep(5)


async def _draft_cleanup_loop():
    """Xodim tashlab qo'ygan (15 daqiqadan ortiq yangilanmagan)
    qoralamalarni davriy ravishda avtomatik o'chirib turadi. Bu
    bo'lmasa, hech qachon yuborilmagan qoralamalar bazada abadiy qolib,
    Postgres hajmini (Railway volume) asta-sekin to'ldirib boraveradi.

    DIQQAT: 15 daqiqa juda qisqa muddat — agar xodim shuncha vaqtdan
    ortiq ilovadan chiqib tursa, hozirgacha olingan rasmlari o'chib
    ketadi va qaytadan boshlashga to'g'ri keladi."""
    while True:
        try:
            # TUZATILDI: zaxira xabarlari endi BITTA TRANZAKSIYADA doimiy
            # o'chirish navbatiga ko'chiriladi va shundan keyingina
            # qoralama bazadan o'chiriladi. Ilgari bu ikki qadam alohida
            # edi va oradagi har qanday xato "qaysi xabarni o'chirish
            # kerak" ma'lumotini butunlay yo'qotardi. Telegramga
            # o'chirish so'rovlarini bu sikl endi umuman yubormaydi —
            # buni alohida worker cheklovga rioya qilib bajaradi.
            deleted = await db.stale_drafts_to_deletion_queue(max_age_minutes=DRAFT_TTL_MINUTES)
            if deleted:
                log.info("draft_cleanup: %d ta eskirgan (%d+ daqiqa tegilmagan) qoralama tozalandi",
                         deleted, DRAFT_TTL_MINUTES)
            await db.purge_old_outbox(days=7)
        except Exception as e:  # noqa: BLE001
            log.warning("draft_cleanup xatolik: %r", e)
        await asyncio.sleep(DRAFT_CLEANUP_INTERVAL_SECONDS)


@app.on_event("startup")
async def _startup():
    """Railway'da har deployda jadvallar mavjudligini avtomatik ta'minlaydi
    (schema.sql barcha CREATE TABLE larda IF NOT EXISTS ishlatadi — xavfsiz)."""
    pool = await db.get_pool()
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    with open(schema_path, encoding="utf-8") as f:
        schema_sql = f.read()
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)

    # .env dagi SUPERADMIN_IDS ro'yxatidagi har bir id ni superadmin
    # sifatida ruxsat etilganlar jadvaliga qo'shamiz (bootstrap).
    for sa_id in SUPERADMIN_IDS:
        existing = await db.get_allowed_user(sa_id)
        await db.add_allowed_user(
            telegram_user_id=sa_id,
            full_name=existing["full_name"] if existing else None,
            is_superadmin=True,
        )

    # Guruhda yaratilgan (qo'lda yoki avtomatik) forum-topic'larni filiallar
    # bilan nom bo'yicha bog'lab turadigan fon vazifasini ishga tushiramiz.
    # Shu tufayli alohida "worker" process/Railway-service kerak bo'lmaydi —
    # bitta web-service ichida ishlab turadi.
    app.state.bot_listener_task = asyncio.create_task(bot_listener.run_polling())
    app.state.draft_cleanup_task = asyncio.create_task(_draft_cleanup_loop())
    app.state.outbox_task = asyncio.create_task(_outbox_worker())
    app.state.deletion_task = asyncio.create_task(_deletion_worker())

    stats = await db.outbox_stats()
    log.info(
        "startup tayyor: draft TTL=%d daq, cleanup=%ds, rate-limit=%d/%ds, "
        "maks rasm=%d MB | navbatda: %d ta yetkazish, %d ta tozalash",
        DRAFT_TTL_MINUTES, DRAFT_CLEANUP_INTERVAL_SECONDS, RATE_LIMIT_MAX, RATE_LIMIT_WINDOW,
        MAX_PHOTO_BYTES // (1024 * 1024), stats["pending"], stats["deletions"],
    )


@app.on_event("shutdown")
async def _shutdown():
    for task_name in ("bot_listener_task", "draft_cleanup_task", "outbox_task", "deletion_task"):
        task = getattr(app.state, task_name, None)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    await tg.close_client()
    await db.close_pool()


@app.get("/healthz")
async def health():
    # Railway health-check uchun. Ilgari "/" edi, endi "/" ni frontend
    # (index.html) egallaydi (fayl oxiridagi StaticFiles mount), shuning
    # uchun health tekshiruvi shu yerga ko'chdi. Railway'da Settings →
    # Healthcheck Path ni "/healthz" qilib qo'ying (yoki "/" qoldirsangiz
    # ham index.html 200 qaytaradi, bu ham ishlaydi).
    return {"status": "ok", "service": "filial-feedback-app"}


# ============================================================
#  MUHIM TUZATISH: kutilmagan (kod ichida try/except bilan ushlanmagan)
#  har qanday xato ilgari FastAPI'ning standart "500 Internal Server
#  Error" javobini (bo'sh yoki oddiy matn, JSON EMAS) qaytarardi.
#  Frontend esa javobni HAR DOIM JSON deb kutib, uni ochib bo'lmagach
#  xom (foydalanuvchiga tushunarsiz) matnni ko'rsatardi — natijada
#  "Yuborish" xatolik bilan tugagach XODIM SABABINI umuman bilolmasdi.
#  Endi har qanday kutilmagan xato ham izchil JSON ko'rinishida
#  ({"detail": "..."}), tushunarli matn bilan qaytariladi.
# ============================================================
@app.exception_handler(Exception)
async def _unhandled_exception_handler(request, exc: Exception):
    from fastapi.responses import JSONResponse
    log.error("unhandled %s %s: %r", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Kutilmagan xatolik yuz berdi. Qayta urinib ko'ring."},
    )


def _check_init_data(init_data: str) -> dict:
    """initData ning haqiqiy Telegram tomonidan yuborilganini tekshiradi
    (imzo/vaqt), lekin ruxsat etilgan foydalanuvchi ekanini TEKSHIRMAYDI."""
    user = tg.validate_init_data(init_data)
    if not user or not user.get("id"):
        raise HTTPException(status_code=401, detail="initData yaroqsiz")
    return user


async def _check_auth(init_data: str) -> dict:
    """initData'ni tekshiradi VA foydalanuvchi ruxsat etilganlar
    (allowed_users) ro'yxatida borligini tasdiqlaydi. Ro'yxatda yo'q har
    qanday begona foydalanuvchi uchun 403 qaytaradi — frontend buni
    "ushbu bot ishlamaydi" ekranini ko'rsatish uchun ishlatadi."""
    user = _check_init_data(init_data)
    allowed = await db.get_allowed_user(user["id"])
    if not allowed:
        raise HTTPException(status_code=403, detail=NOT_ALLOWED_MESSAGE)
    user["is_superadmin"] = allowed["is_superadmin"]
    return user


async def _check_superadmin(init_data: str) -> dict:
    """Faqat superadmin uchun ruxsat beradi (admin panel funksiyalari)."""
    user = await _check_auth(init_data)
    if not user.get("is_superadmin"):
        raise HTTPException(status_code=403, detail="Faqat superadmin uchun")
    return user


# ---------------------------------------------------------------------------
# 1) Mini app ochilganda kerakli konfiguratsiya: filiallar + chek-list turlari
#    (bo'limlar endi tanlangan chek-list turiga qarab alohida so'raladi —
#    quyidagi /api/sections ga qarang)
# ---------------------------------------------------------------------------
@app.get("/api/config")
async def get_config(init_data: str, lang: str = "uz"):
    lang = _norm_lang(lang)
    user = await _check_auth(init_data)
    filials = await db.list_active_filials()
    checklist_types = await db.list_active_checklist_types(lang)
    return {
        "filials": filials,
        "checklist_types": checklist_types,
        "is_superadmin": user["is_superadmin"],
    }


# ---------------------------------------------------------------------------
# 1.1) Filial VA chek-list turi tanlangandan keyin — o'sha turga tegishli
#      bo'limlar (sections) ro'yxati
# ---------------------------------------------------------------------------
@app.get("/api/sections")
async def get_sections(init_data: str, checklist_type_id: int, filial_id: int, lang: str = "uz"):
    lang = _norm_lang(lang)
    await _check_auth(init_data)
    checklist_type = await db.get_checklist_type(checklist_type_id, lang)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    # filial_id beriladi — shu filialda "yashirilgan" deb belgilangan
    # bo'limlar (masalan foodcourt filialida "Tashqi hudud") ro'yxatdan
    # chiqarib tashlanadi (filial_section_hidden jadvali orqali).
    sections = await db.list_active_sections(checklist_type_id, lang, filial_id=filial_id)
    return {"sections": sections, "checklist_type": checklist_type}


# ---------------------------------------------------------------------------
# 1.5) QORALAMA (draft) — hali yuborilmagan, jarayondagi hisobot.
#
# Nega kerak: oldin rasm/izoh faqat mini app'ning JS xotirasida turardi —
# xodim botdan chiqib ketsa yoki ilova fonga o'tib qayta yuklansa hammasi
# yo'qolardi. Endi HAR BIR rasm olingan zahoti shu yerga (bazaga) darhol
# saqlanadi. Shu tufayli:
#   - Xodim chiqib ketsa/ilova yopilsa — rasmlar, izohlar va tanlangan
#     filial/chek-list turi saqlanib qoladi, keyin qaytib kirganda xuddi
#     shu joyidan davom etadi.
#   - "Yuborish" bosilganda endi barcha rasmlarni qayta yuklash shart
#     emas (ular allaqachon serverda) — shuning uchun sekin internetda
#     ham yuborish tezroq va ishonchliroq ishlaydi.
#   - Qoralama FAQAT shu xodimning o'ziga tegishli — telegram_user_id
#     orqali bog'langan, boshqa hech kim ko'ra olmaydi.
# ---------------------------------------------------------------------------

@app.get("/api/draft")
async def get_draft(init_data: str, lang: str = "uz"):
    lang = _norm_lang(lang)
    user = await _check_auth(init_data)
    draft = await db.get_draft(user["id"])
    if not draft:
        return {"draft": None, "photos": []}

    photos = await db.list_draft_photos(user["id"])
    photos_out = [
        {
            "id": p["id"],
            "section_id": p["section_id"],
            "comment": p["comment"] or "",
            "image_url": f"/api/draft/photo/{p['id']}/image?init_data={quote(init_data, safe='')}",
        }
        for p in photos
    ]
    return {
        "draft": {
            "filial_id": draft["filial_id"],
            "checklist_type_id": draft["checklist_type_id"],
            "lang": draft["lang"],
        },
        "photos": photos_out,
    }


@app.put("/api/draft/meta")
async def put_draft_meta(
    init_data: str = Form(...),
    filial_id: Optional[int] = Form(None),
    checklist_type_id: Optional[int] = Form(None),
    lang: str = Form("uz"),
):
    """Xodim filial va/yoki chek-list turini tanlaganda chaqiriladi —
    shu tanlov saqlanadi, shunda ilova qayta ochilganda aynan shu
    joydan davom etadi."""
    lang = _norm_lang(lang)
    user = await _check_auth(init_data)
    draft = await db.set_draft_meta(user["id"], filial_id, checklist_type_id, lang)
    return {"ok": True, "draft": draft}


@app.post("/api/draft/photo")
async def post_draft_photo(
    init_data: str = Form(...),
    section_id: int = Form(...),
    comment: str = Form(""),
    file: UploadFile = File(...),
    filial_id: Optional[int] = Form(None),
    checklist_type_id: Optional[int] = Form(None),
):
    """Rasm olingan ZAHOTI (foydalanuvchi "Yuborish"ni bosishidan ancha
    oldin) darhol Telegramga (xodimning botga shaxsiy chatiga, zaxira
    sifatida) yuboriladi va qaytgan file_id bazaga yoziladi — shu tufayli
    ilova favqulodda yopilib qolsa ham rasm yo'qolmaydi, VA bazada
    rasmning og'ir baytlari saqlanmaydi (Postgres hajmi to'lib qolmaydi).

    MUHIM TUZATISH: `filial_id`/`checklist_type_id` endi shu so'rov bilan
    HAM yuboriladi (frontend filial/smenani tanlaganda alohida saqlash
    so'rovi bilan bir qatorda). Agar o'sha alohida so'rov biror sababdan
    (tarmoq, poyga holati) hali ulgurmagan/muvaffaqiyatsiz bo'lgan bo'lsa,
    shu yerda ham qoralamaning filial/smena ma'lumoti "o'zi tuzatiladi"
    (faqat hali bo'sh bo'lsa to'ldiriladi, hech qachon mavjud to'g'ri
    qiymatni bosib yozmaydi) — aks holda "Yuborish" bosilganda backend
    bazadagi (bo'sh qolib ketgan) filial/smena bilan solishtirib mos
    kelmadi deb rad etardi, garchi foydalanuvchi ekranda hammasini
    to'g'ri tanlagan bo'lsa ham."""
    user = await _check_auth(init_data)
    _check_rate_limit(user["id"])

    # TUZATILDI: bo'lim mavjudligi va tanlangan smenaga tegishliligi endi
    # SHU YERDA tekshiriladi. Ilgari hech qanday tekshiruv yo'q edi va
    # yaroqsiz section_id "zaharlangan qoralama" hosil qilardi: rasm
    # guruhga yuborilardi, keyin bazaga yozishda FK xatosi chiqib 500
    # qaytarardi, qoralama esa o'chirilmasdi — xodim har "Yuborish"
    # bosganda guruhga yana bitta ortiqcha rasm tushardi va u hech qachon
    # hisobotni yakunlay olmasdi.
    draft_now = await db.get_draft(user["id"])
    expected_type = checklist_type_id or (draft_now or {}).get("checklist_type_id")
    if not await db.section_belongs_to(section_id, expected_type):
        raise HTTPException(
            status_code=400,
            detail="Bo'lim topilmadi yoki bu smenaga tegishli emas. Sahifani yangilab ko'ring.",
        )

    data = await _read_upload_limited(file)

    if filial_id is not None or checklist_type_id is not None:
        await db.ensure_draft_meta(user["id"], filial_id, checklist_type_id)

    sent = await tg.send_draft_photo_to_owner(user["id"], data, file.filename or "photo.jpg")

    photo = await db.add_draft_photo(
        telegram_user_id=user["id"],
        section_id=section_id,
        comment=comment.strip() or None,
        filename=file.filename or "photo.jpg",
        content_type=file.content_type or "image/jpeg",
        telegram_file_id=sent["file_id"],
        telegram_message_id=sent["message_id"],
    )
    return {
        "ok": True,
        "photo": {
            "id": photo["id"],
            "section_id": photo["section_id"],
            "comment": photo["comment"] or "",
            "image_url": f"/api/draft/photo/{photo['id']}/image?init_data={quote(init_data, safe='')}",
        },
    }


@app.get("/api/draft/photo/{photo_id}/image")
async def get_draft_photo_image(photo_id: int, init_data: str):
    """Qoralamadagi rasmni ko'rsatish uchun (masalan ilova qayta
    ochilganda avvalgi rasmlar preview'ini tiklash). Faqat rasmning
    egasi (o'sha telegram_user_id) ko'ra oladi.

    Rasm bazada emas, Telegramda saqlangani uchun, shu yerda Telegramdan
    qayta yuklab olinadi va to'g'ridan-to'g'ri brauzerga uzatiladi
    (hech qayerda saqlanmaydi) — eski (migratsiyadan oldingi) qatorlar
    uchun esa hali bazadagi baytlar bilan ishlayveradi."""
    user = await _check_auth(init_data)
    photo = await db.get_draft_photo(photo_id, user["id"])
    if not photo:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")

    if photo.get("telegram_file_id"):
        image_bytes = await tg.download_file_bytes(photo["telegram_file_id"])
    elif photo.get("photo_data"):
        image_bytes = photo["photo_data"]
    else:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")

    return Response(content=image_bytes, media_type=photo["content_type"] or "image/jpeg")


@app.put("/api/draft/photo/{photo_id}")
async def put_draft_photo(
    photo_id: int,
    init_data: str = Form(...),
    comment: str = Form(""),
):
    user = await _check_auth(init_data)
    ok = await db.update_draft_photo_comment(photo_id, user["id"], comment.strip() or None)
    if not ok:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    return {"ok": True}


@app.delete("/api/draft/photo/{photo_id}")
async def delete_draft_photo(photo_id: int, init_data: str):
    user = await _check_auth(init_data)
    result = await db.delete_draft_photo(photo_id, user["id"])
    if not result:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")
    # Zaxira nusxani o'chirishni NAVBATGA qo'yamiz — javobni kutib
    # turmaydi, lekin bajarilgunicha qayta uriniladi (ilgari bu yerda
    # javob kutilardi va xato jimgina yutilardi).
    if result.get("telegram_message_id"):
        await db.enqueue_deletion(result["telegram_user_id"], result["telegram_message_id"])
    return {"ok": True}


@app.delete("/api/draft")
async def delete_draft(init_data: str):
    """Xodim "boshidan boshlash" ni tanlaganda — butun qoralamani
    (barcha rasmlari bilan) o'chiradi."""
    user = await _check_auth(init_data)
    await db.clear_draft(user["id"])
    return {"ok": True}


# ---------------------------------------------------------------------------
# 2) Yakuniy yuborish: filial + har bir bo'lim uchun oldindan (draft
#    sifatida) saqlangan rasm(lar)ni Telegram guruhiga jo'natish.
#
# E'TIBOR: rasmlar bu so'rovda YUKLANMAYDI — ular allaqachon
# /api/draft/photo orqali serverda saqlangan. Shu tufayli bu so'rov
# yengil (faqat matn) va sekin/beqaror internetda ham muvaffaqiyatli
# yetib borish ehtimoli ancha yuqori. Agar baribir uzilib qolsa —
# qoralama saqlanib qoladi va xodim shunchaki qayta "Yuborish"ni
# bosishi kifoya (rasmlarni qayta yuklashi shart emas).
# ---------------------------------------------------------------------------
CHECKLIST_TYPE_EMOJI = {
    "opening": "🔓",
    "handover": "🔄",
    "closing": "🔒",
}


def _html_escape(text: str) -> str:
    """Telegramga `parse_mode: HTML` bilan yuboriladigan caption'lar ichiga
    qo'yiladigan HAR QANDAY dinamik matnni (filial nomi, bo'lim nomi,
    xodimning izohi, ismi va h.k.) xavfsizlantiradi.

    MUHIM BUG TUZATILDI: agar bunday matnlarda `<`, `>` yoki `&` belgisi
    bo'lsa (masalan xodim izohga "5<10" yoki "narx & sifat" deb yozsa),
    Telegram buni yaroqsiz HTML deb hisoblab, BUTUN XABARNI rad etar edi
    — natijada "Yuborish" xatolik bilan tugar edi. Bu hech qanday
    qurilmaga (Android/iPhone) bog'liq emas edi, faqat izoh/nom matniga
    bog'liq edi — shu sabab ba'zan bitta qurilmada, ba'zan ikkalasida
    ham chiqib turardi."""
    if not text:
        return text
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


@app.post("/api/submit")
async def submit(
    init_data: str = Form(...),
    filial_id: int = Form(...),
    checklist_type_id: int = Form(...),
    lang: str = Form("uz"),
):
    """Hisobotni YETKAZISH NAVBATIGA qo'yadi va darhol qaytadi.

    ============================================================
    ASOSIY O'ZGARISH — "hisobot yuborilmay qolyapti" muammosining yechimi
    ============================================================
    Ilgari bu funksiya barcha rasmlarni SHU SO'ROV ichida, bo'lim-bo'lim
    Telegram guruhiga yuborardi. Telegram bitta guruhga daqiqasiga ~20 ta
    xabar qabul qiladi; smena almashinuvida 10 xodim × 8 bo'lim = 80
    xabar bir zumda urinardi. Natijada:
      - Telegram 429 (flood control) qaytarardi;
      - eski kod `retry_after` ni 10 soniyaga cheklab, erta qayta urinardi
        va yana 429 olardi;
      - so'rov 40 soniyadan oshib ketardi, frontend uni bekor qilib
        avtomatik 3 marta QAYTA yuborardi — bu esa yukni yanada oshirardi;
      - oxir-oqibat xodim "Telegram bilan aloqa muammosi" xatosini
        ko'rardi, hisobot esa guruhga umuman yetib bormasdi.
    O'lchov (10 xodim, 8 bo'lim): 10 tadan 0 tasi muvaffaqiyatli, 161
    soniya kutish, 25 ta zaxira nusxa osilib qolgan.

    Endi bu so'rov faqat bazaga yozadi (~0.2 soniya) va "qabul qilindi"
    deb javob beradi. Rasmlarni guruhga fon worker'i (`_outbox_worker`)
    Telegram cheklovini hurmat qilgan holda, xatolarda qayta urinib
    yetkazadi. Xodim kutmaydi, xato ko'rmaydi; server qayta ishga tushsa
    ham navbat bazada saqlanib qoladi. Yetkazish tugagach xodim botdan
    "✅ Hisobotingiz guruhga muvaffaqiyatli yuborildi" xabarini oladi.
    """
    lang = _norm_lang(lang)
    user = await _check_auth(init_data)
    _check_rate_limit(user["id"], limit=SUBMIT_RATE_LIMIT)

    filial = await db.get_filial(filial_id)
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")

    checklist_type = await db.get_checklist_type(checklist_type_id, lang)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")

    # ------------------------------------------------------------------
    # TUZATILDI: bitta xodim uchun bir vaqtda faqat BITTA yuborish.
    # Ilgari hech qanday qulf yo'q edi: frontend timeout'dan keyin
    # avtomatik qayta yuborardi va parallel so'rovlarning HAMMASI bir xil
    # qoralamani o'qib, guruhga bir xil hisobotni bir necha marta
    # yuborardi (o'lchov: 3 parallel so'rov = guruhda 3 ta nusxa).
    #
    # Butun kritik bo'lim BITTA ulanish va BITTA tranzaksiyada bajariladi,
    # qoralama qatori esa `SELECT ... FOR UPDATE` bilan qulflanadi.
    # Ikkinchi parallel so'rov birinchisi tugagunicha kutadi, so'ng
    # qoralamani topa olmay 409 oladi. Bu advisory lock'dan afzal:
    # tranzaksiya ichida qo'shimcha ulanish SO'RALMAYDI, shuning uchun
    # pool (standart 10 ta ulanish) hech qachon o'zini-o'zi qulflab
    # qo'ymaydi.
    # ------------------------------------------------------------------
    now_str = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M")
    checklist_emoji = CHECKLIST_TYPE_EMOJI.get(checklist_type["key"], "📋")
    full_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) \
        or user.get("username") or "Noma'lum"

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            draft = await db.lock_draft_for_submit(conn, user["id"])
            if not draft or draft["filial_id"] != filial_id \
                    or draft["checklist_type_id"] != checklist_type_id:
                raise HTTPException(
                    status_code=409,
                    detail="Bu hisobot allaqachon yuborilgan yoki qoralama eskirgan. "
                           "Sahifani yangilab, qaytadan urinib ko'ring.",
                )

            draft_photos = await db.list_draft_photos_conn(conn, draft["id"])
            if not draft_photos:
                raise HTTPException(status_code=400, detail="Hech qanday rasm topilmadi")

            # Rasmlarni bo'lim bo'yicha guruhlaymiz — har bir bo'lim guruhga
            # bitta albom bo'lib tushadi (xabar ko'rinishi o'zgarmadi).
            section_groups: dict[int, list] = {}
            for p in draft_photos:
                section_groups.setdefault(p["section_id"], []).append(p)

            # Eskirgan/keshlangan sahifadan shu filial uchun yashirilgan
            # bo'limga rasm yuborilmasin (bitta so'rovda — ilgari har bir
            # bo'lim uchun alohida so'rov ketardi).
            hidden = await db.hidden_section_ids_conn(conn, filial_id, list(section_groups))
            if hidden:
                raise HTTPException(
                    status_code=400,
                    detail="Tanlangan bo'limlardan biri bu filial uchun endi mavjud emas. "
                           "Sahifani yangilab, qayta urinib ko'ring.",
                )

            submission_id = await db.create_submission_conn(
                conn,
                filial_id=filial_id,
                filial_name=filial["name"],
                telegram_user_id=user["id"],
                full_name=full_name,
                checklist_type_id=checklist_type_id,
                checklist_type_name=checklist_type["name"],
            )

            queued_sections = 0
            for seq, (section_id, photos_meta) in enumerate(section_groups.items()):
                sec = await db.get_section_conn(conn, section_id, lang)
                section_name = sec["name"] if sec else ""
                comment = (photos_meta[0].get("comment") or "").strip()

                caption = (
                    f"🏢 <b>{_html_escape(filial['name'])}</b>\n"
                    f"{checklist_emoji} <b>{_html_escape(checklist_type['name'])}</b>\n"
                    f"🕒 {now_str}\n👤 {_html_escape(full_name)}"
                )
                if section_name:
                    caption += f"\n📍 Bo'lim: {_html_escape(section_name)}"
                if comment:
                    caption += f"\n💬 {_html_escape(comment)}"

                photos_payload = [
                    {
                        "file_id": p["telegram_file_id"],
                        "comment": (p.get("comment") or "").strip() or None,
                        "backup_message_id": p.get("telegram_message_id"),
                    }
                    for p in photos_meta if p.get("telegram_file_id")
                ]
                if not photos_payload:
                    continue

                await db.enqueue_outbox(
                    conn,
                    submission_id=submission_id,
                    telegram_user_id=user["id"],
                    filial_id=filial_id,
                    filial_name=filial["name"],
                    section_id=section_id,
                    seq=seq,
                    caption=caption,
                    photos=photos_payload,
                )
                queued_sections += 1

            if not queued_sections:
                raise HTTPException(status_code=400, detail="Hech qanday rasm topilmadi")

            # Qoralama endi kerak emas — barcha ma'lumot navbatda saqlangan.
            # Zaxira nusxa xabarlari navbat YETKAZGANDAN KEYIN o'chiriladi,
            # shuning uchun bu yerda ularga tegmaymiz (yetkazish
            # muvaffaqiyatsiz bo'lsa, zaxira nusxa xodimda qolib turadi).
            await db.delete_draft_conn(conn, draft["id"])

    log.info("submit: hisobot #%s navbatga qo'yildi (%d ta bo'lim, xodim %s)",
             submission_id, queued_sections, user["id"])
    return {"ok": True, "submission_id": submission_id, "queued": True}


# ---------------------------------------------------------------------------
# ADMIN PANEL — faqat is_superadmin=TRUE bo'lgan foydalanuvchilar uchun.
# Har bir endpoint init_data orqali superadmin ekanini tekshiradi.
# ---------------------------------------------------------------------------

# ---------- Foydalanuvchilar (ruxsat etilganlar ro'yxati) ----------

@app.get("/api/admin/users")
async def admin_list_users(init_data: str):
    await _check_superadmin(init_data)
    return {"users": await db.list_allowed_users()}


@app.post("/api/admin/users")
async def admin_add_user(
    init_data: str = Form(...),
    telegram_user_id: int = Form(...),
    full_name: Optional[str] = Form(None),
    is_superadmin: bool = Form(False),
):
    await _check_superadmin(init_data)
    user = await db.add_allowed_user(telegram_user_id, full_name, is_superadmin)
    return {"ok": True, "user": user}


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(
    user_id: int,
    init_data: str = Form(...),
    full_name: Optional[str] = Form(None),
    is_superadmin: bool = Form(False),
):
    requester = await _check_superadmin(init_data)

    # TUZATILDI: superadmin o'zini huquqdan mahrum qilib, tizimga kira
    # olmay qolardi. O'chirishda ("O'zingizni o'chira olmaysiz") himoya
    # bor edi, tahrirlashda esa yo'q edi — admin panelda "Ism" va
    # "Superadmin huquqi" bitta modalda bo'lgani uchun, ismni tuzatayotib
    # checkbox'ni beixtiyor bosish yetarli edi. Tiklash faqat env
    # o'zgaruvchisi + redeploy orqali mumkin edi.
    users = await db.list_allowed_users()
    target = next((u for u in users if u["id"] == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if target["telegram_user_id"] == requester["id"] and not is_superadmin:
        raise HTTPException(
            status_code=400,
            detail="O'zingizni superadmin huquqidan mahrum qila olmaysiz.",
        )
    # Oxirgi superadmin qolmasin (aks holda admin panelga kirish yo'qoladi).
    if target["is_superadmin"] and not is_superadmin and await db.count_superadmins() <= 1:
        raise HTTPException(
            status_code=400,
            detail="Bu yagona superadmin — huquqni olib tashlash mumkin emas.",
        )

    user = await db.update_allowed_user(user_id, full_name, is_superadmin)
    if not user:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return {"ok": True, "user": user}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, init_data: str):
    requester = await _check_superadmin(init_data)

    users = await db.list_allowed_users()
    target = next((u for u in users if u["id"] == user_id), None)
    if not target:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    if target["telegram_user_id"] == requester["id"]:
        raise HTTPException(status_code=400, detail="O'zingizni o'chira olmaysiz")

    ok = await db.delete_allowed_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Foydalanuvchi topilmadi")
    return {"ok": True}


# ---------- Filiallar ----------

@app.get("/api/admin/filials")
async def admin_list_filials(init_data: str):
    await _check_superadmin(init_data)
    return {"filials": await db.list_all_filials()}


@app.post("/api/admin/filials")
async def admin_add_filial(
    init_data: str = Form(...),
    name: str = Form(...),
):
    await _check_superadmin(init_data)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas!")
    # TUZATILDI: takroriy nom ilgari ushlanmagan UniqueViolationError
    # ko'tarib, adminga "Kutilmagan xatolik yuz berdi" deb ko'rsatardi.
    try:
        filial = await db.create_filial(name)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Bunday nomli filial allaqachon mavjud.")
    return {"ok": True, "filial": filial}


@app.put("/api/admin/filials/{filial_id}")
async def admin_update_filial(
    filial_id: int,
    init_data: str = Form(...),
    name: str = Form(...),
    is_active: bool = Form(True),
):
    await _check_superadmin(init_data)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas!")
    try:
        filial = await db.update_filial(filial_id, name, is_active)
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=400, detail="Bunday nomli filial allaqachon mavjud.")
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")
    return {"ok": True, "filial": filial}


@app.delete("/api/admin/filials/{filial_id}")
async def admin_delete_filial(filial_id: int, init_data: str):
    """Filialni bazadan BUTUNLAY o'chiradi (nofaol bo'lib qolib ketmaydi).
    Bog'liq eski hisobotlar saqlanib qoladi (filial_id NULL bo'ladi,
    filial nomi esa snapshot sifatida saqlanadi)."""
    await _check_superadmin(init_data)
    ok = await db.delete_filial(filial_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Filial topilmadi")
    return {"ok": True}


@app.put("/api/admin/filials/{filial_id}/thread")
async def admin_link_filial_thread(
    filial_id: int,
    init_data: str = Form(...),
    thread_id: int = Form(...),
):
    """Filialni guruhdagi MAVJUD topic (message_thread_id) bilan qo'lda
    bog'laydi. Ayniqsa, bot_listener ishga tushirilishidan OLDIN guruhda
    filial nomi bilan topic allaqachon yaratib qo'yilgan bo'lsa foydali —
    shu endpoint orqali admin uni bir marta bog'lab qo'ysa, mini-app
    keyingi safar shu filial uchun YANGI topic yaratmay, mavjudiga
    yozadi. thread_id ni topic ustidagi xabarni forward qilib yoki
    guruh havolasidagi /ID qismidan olish mumkin."""
    await _check_superadmin(init_data)
    filial = await db.get_filial(filial_id)
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")
    await db.set_filial_thread_id(filial_id, thread_id)
    updated = await db.get_filial(filial_id)
    return {"ok": True, "filial": updated}


# ---------- Chek-list turlari ----------

@app.get("/api/admin/checklist-types")
async def admin_list_checklist_types(init_data: str):
    await _check_superadmin(init_data)
    return {"checklist_types": await db.list_all_checklist_types()}


@app.put("/api/admin/checklist-types/{checklist_type_id}")
async def admin_update_checklist_type(
    checklist_type_id: int,
    init_data: str = Form(...),
    name: str = Form(...),
    lang: str = Form("uz"),
):
    """Superadmin smena nomini (masalan "Smena ochilishi" -> "Ochilish
    smenasi") FAQAT o'zi tanlagan interfeys tilida (`lang`) kiritadi —
    qolgan ikkita til uchun nom bo'lim nomlari kabi avtomatik tarjima
    qilinadi. `key` (opening/handover/closing) o'zgarmaydi — u faqat
    kod ichida ishlatiladigan doimiy identifikator."""
    await _check_superadmin(init_data)
    lang = _norm_lang(lang)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Smena nomini kiriting")

    names = await translate_utils.translate_to_all_langs(name, lang)
    checklist_type = await db.update_checklist_type_name(checklist_type_id, names["uz"], names["ru"], names["en"])
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    return {"ok": True, "checklist_type": checklist_type}


# ---------- Bo'limlar (har bir chek-list turi uchun alohida) ----------

@app.get("/api/admin/sections")
async def admin_list_sections(init_data: str, checklist_type_id: int):
    await _check_superadmin(init_data)
    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    return {"sections": await db.list_all_sections(checklist_type_id)}


# E'TIBOR: bu endpoint /api/admin/sections/{section_id} dan OLDIN
# e'lon qilingan bo'lishi SHART — aks holda FastAPI "reorder" so'zini
# {section_id}:int sifatida parslashga urinib, 422 xato bilan
# to'xtaydi va bu yerga hech qachon yetib kelmaydi (path-matching
# yuqoridan pastga qarab, birinchi mos kelgan marshrutda to'xtaydi).
@app.put("/api/admin/sections/reorder")
async def admin_reorder_sections(
    init_data: str = Form(...),
    checklist_type_id: int = Form(...),
    ordered_section_ids: str = Form(...),  # JSON: [3, 1, 2, ...] — yangi tartib
):
    """Superadmin bo'limlar ro'yxatini drag-and-drop bilan surishtirganda
    chaqiriladi — yangi tartib bazaga yoziladi va shundan keyin BARCHA
    foydalanuvchilar (`/api/sections`) xuddi shu tartibni ko'radi."""
    await _check_superadmin(init_data)
    try:
        ids = json.loads(ordered_section_ids)
        if not isinstance(ids, list):
            raise ValueError
        ids = [int(x) for x in ids]
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="ordered_section_ids noto'g'ri formatda")

    await db.reorder_sections(checklist_type_id, ids)
    return {"ok": True}


@app.post("/api/admin/sections")
async def admin_add_section(
    init_data: str = Form(...),
    checklist_type_id: int = Form(...),
    name: str = Form(...),
    lang: str = Form("uz"),
):
    """Superadmin bo'lim nomini FAQAT o'zi tanlagan interfeys tilida
    (`lang`) kiritadi — qolgan ikkita til uchun nom avtomatik tarjima
    qilinadi, alohida-alohida kiritish shart emas."""
    await _check_superadmin(init_data)
    lang = _norm_lang(lang)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bo'lim nomini kiriting")
    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")

    # ------------------------------------------------------------------
    # BLOKER himoyasi: ilgari bir xil nomli ikkita bo'lim bemalol
    # qo'shilardi (HTTP 200), lekin KEYINGI restart/deployda schema.sql
    # dagi UNIQUE indeks yaratilmay, ilova butunlay ishga tushmay
    # qolardi ("Application startup failed. Exiting."). Sabab bilan
    # oqibat orasida kunlar bo'lishi mumkin edi. Endi admin darhol
    # tushunarli xato oladi.
    # ------------------------------------------------------------------
    names = await translate_utils.translate_to_all_langs(name, lang)
    legacy_name = names["uz"] or names["ru"] or names["en"]
    if await db.section_name_exists(checklist_type_id, legacy_name):
        raise HTTPException(
            status_code=400,
            detail="Bu smenada shunday nomli bo'lim allaqachon mavjud. Boshqa nom kiriting.",
        )
    section = await db.create_section(checklist_type_id, names["uz"], names["ru"], names["en"])
    return {"ok": True, "section": section}


@app.put("/api/admin/sections/{section_id}")
async def admin_update_section(
    section_id: int,
    init_data: str = Form(...),
    name: str = Form(...),
    lang: str = Form("uz"),
    is_active: bool = Form(True),
):
    """Bo'lim nomi tahrirlanganda ham xuddi shunday — admin faqat bitta
    tilda (`lang`) yangi nomni kiritadi, qolgan ikkita til shu nomdan
    qayta tarjima qilinib yangilanadi."""
    await _check_superadmin(init_data)
    lang = _norm_lang(lang)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bo'lim nomini kiriting")

    names = await translate_utils.translate_to_all_langs(name, lang)
    legacy_name = names["uz"] or names["ru"] or names["en"]
    ct_id = await db.get_section_checklist_type(section_id)
    if ct_id is None:
        raise HTTPException(status_code=404, detail="Bo'lim topilmadi")
    if await db.section_name_exists(ct_id, legacy_name, exclude_id=section_id):
        raise HTTPException(
            status_code=400,
            detail="Bu smenada shunday nomli bo'lim allaqachon mavjud. Boshqa nom kiriting.",
        )
    section = await db.update_section(section_id, names["uz"], names["ru"], names["en"], is_active)
    if not section:
        raise HTTPException(status_code=404, detail="Bo'lim topilmadi")
    return {"ok": True, "section": section}


@app.put("/api/admin/sections/{section_id}/active")
async def admin_set_section_active(
    section_id: int,
    init_data: str = Form(...),
    is_active: bool = Form(...),
):
    await _check_superadmin(init_data)
    section = await db.set_section_active(section_id, is_active)
    if not section:
        raise HTTPException(status_code=404, detail="Bo'lim topilmadi")
    return {"ok": True, "section": section}


@app.delete("/api/admin/sections/{section_id}")
async def admin_delete_section(section_id: int, init_data: str):
    """Bo'limni bazadan butunlay o'chiradi. Agar bu bo'limga bog'langan
    eski rasm hisobotlari bo'lsa, Postgres o'chirishga yo'l qo'ymaydi
    (tarixni buzmaslik uchun) — bunday holatda 400 qaytariladi va
    frontend buning o'rniga ko'z (faol/nofaol) ikonkasini tavsiya qiladi."""
    await _check_superadmin(init_data)
    try:
        ok = await db.delete_section(section_id)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(
            status_code=400,
            detail="Bu bo'limda allaqachon yuborilgan rasm hisobotlari bor, shuning uchun butunlay o'chirib bo'lmaydi. Buning o'rniga ko'z ikonkasi bilan nofaol qiling.",
        )
    if not ok:
        raise HTTPException(status_code=404, detail="Bo'lim topilmadi")
    return {"ok": True}


# ---------- Bo'limni filial bo'yicha yashirish ("opt-out") ----------
# Masalan "Tashqi hudud va fasad fotosi" bo'limi barcha filiallarda
# default ko'rinadi, lekin foodcourt ichidagi filialda tashqi hudud
# umuman yo'q bo'lgani uchun admin shu bo'limni faqat o'sha filial(lar)
# uchun yashirib qo'yishi mumkin.

@app.get("/api/admin/sections/{section_id}/hidden-filials")
async def admin_get_section_hidden_filials(section_id: int, init_data: str):
    await _check_superadmin(init_data)
    hidden_filial_ids = await db.get_hidden_filial_ids_for_section(section_id)
    return {"hidden_filial_ids": hidden_filial_ids}


@app.put("/api/admin/sections/{section_id}/hidden-filials")
async def admin_set_section_hidden_filials(
    section_id: int,
    init_data: str = Form(...),
    hidden_filial_ids: str = Form("[]"),  # JSON: [1, 5, 7]
):
    await _check_superadmin(init_data)
    try:
        ids = json.loads(hidden_filial_ids)
        if not isinstance(ids, list):
            raise ValueError
        ids = [int(x) for x in ids]
    except (json.JSONDecodeError, ValueError):
        raise HTTPException(status_code=400, detail="hidden_filial_ids noto'g'ri formatda")

    await db.set_hidden_filials_for_section(section_id, ids)
    return {"ok": True, "hidden_filial_ids": ids}


@app.put("/api/admin/filials/{filial_id}/active")
async def admin_set_filial_active(
    filial_id: int,
    init_data: str = Form(...),
    is_active: bool = Form(...),
):
    """Superadmin filialni ko'z icon orqali faol/nofaol qilib qo'yadi —
    filial bazada qoladi, faqat oddiy foydalanuvchilarga ko'rinmay
    qoladi (filialni butunlay o'chirmaydi)."""
    await _check_superadmin(init_data)
    filial = await db.set_filial_active(filial_id, is_active)
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")
    return {"ok": True, "filial": filial}


# ============================================================
#  FRONTEND (statik fayllar) — endi backend bilan BITTA servis.
#
#  Ilgari frontend alohida Railway servisida `npx serve` bilan 24/7
#  ishlab turardi (qo'shimcha konteyner = qo'shimcha Railway usage).
#  Endi shu FastAPI ilovasining o'zi `backend/static/` papkasidagi
#  index.html/app.js/style.css/i18n.js fayllarini ham beradi — alohida
#  frontend servis KERAK EMAS (uni Railway'da o'chirib tashlang).
#
#  MUHIM: bu mount fayl ENG OXIRIDA turishi shart — shunda barcha
#  `/api/...` va `/healthz` marshrutlari avval ro'yxatga olinadi va
#  StaticFiles faqat qolgan (mos kelmagan) yo'llarni, jumladan "/" ni
#  (html=True → index.html) ushlaydi.
# ============================================================
_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_STATIC_DIR):
    app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
else:
    log.warning("static papka topilmadi (%s) — frontend berilmaydi", _STATIC_DIR)
