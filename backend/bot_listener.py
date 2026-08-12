"""
Fon rejimidagi "listener": Telegram guruhida yangi forum-topic
yaratilishini kuzatib boradi va uni mos filialga avtomatik bog'laydi.

Bot API'ning getUpdates (long polling) usulidan foydalanadi. Bu modul
alohida process sifatida EMAS, balki app.py ishga tushganda FastAPI
lifecycle'ining bir qismi sifatida fon vazifasida (background task)
avtomatik ishga tushadi (qarang: app.py dagi _startup/_shutdown).
Shuning uchun Railway'da alohida "worker" xizmati sozlashning hojati yo'q.

Nima uchun kerak:
    Guruhda filial nomi bilan forum-topic yaratilganda (botning o'zi
    createForumTopic orqali yaratganda ham, ADMIN GURUHDA QO'LDA
    yaratganda ham), Telegram avtomatik ravishda shu haqidagi xizmat
    xabarini (forum_topic_created) yuboradi. Shu xabarni ushlab, topic
    nomini filiallar ro'yxati bilan solishtirib, mos kelsa — filialga
    bog'lab qo'yamiz. Natijada, agar guruhda filial nomi bilan topic
    ALLAQACHON mavjud bo'lsa, mini-app uni qayta yaratmaydi — mavjud
    topicga yozadi.
"""
import asyncio
import logging
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

import db
import telegram_utils as tg

log = logging.getLogger("bot_listener")

try:
    BOT_TOKEN = os.environ["BOT_TOKEN"]
except KeyError as e:
    raise RuntimeError("BOT_TOKEN muhit o'zgaruvchisi o'rnatilmagan (@BotFather tokeni).") from e

TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Ruxsat etilmagan foydalanuvchi botga yozganda ko'radigan javob
# (app.py'dagi NOT_ALLOWED_MESSAGE bilan bir xil — bu yerda takrorlaymiz,
# aylanma import bo'lmasligi uchun).
NOT_ALLOWED_MESSAGE = "Ushbu bot ishlamaydi"
ALLOWED_HINT_MESSAGE = (
    "Assalomu alaykum! Hisobot yuborish uchun pastdagi menyu tugmasi "
    "orqali ilovani oching."
)


async def handle_forum_topic_created(message: dict):
    """Guruhda yangi forum-topic yaratilganda ishga tushadi. Agar topic nomi
    mini-app'dagi biror filial nomi bilan bir xil bo'lsa va o'sha filialda
    hali thread_id o'rnatilmagan bo'lsa — shu topicni filialga bog'lab
    qo'yadi."""
    topic_created = message.get("forum_topic_created")
    if not topic_created:
        return

    topic_name = (topic_created.get("name") or "").strip()
    thread_id = message.get("message_thread_id") or message.get("message_id")
    if not topic_name or not thread_id:
        return

    try:
        linked = await db.link_thread_id_by_name(topic_name, thread_id)
        if linked:
            log.info(
                "Topic avtomatik bog'landi: '%s' -> filial #%s (thread_id=%s)",
                topic_name, linked["id"], thread_id,
            )
    except Exception as e:  # noqa: BLE001
        log.warning("Topic bog'lashda xatolik: %r", e)


async def handle_private_message(message: dict):
    """Foydalanuvchi botga SHAXSIY chatda yozganda (masalan /start).

    Ilgari bu update'lar jimgina tashlab yuborilardi — foydalanuvchi
    hech qanday javob olmasdi (README va'da qilgan "Ushbu bot ishlamaydi"
    javobi ham chiqmasdi). Endi:
      - ruxsat etilgan (allowed_users) foydalanuvchi — ilovani menyudan
        ochish bo'yicha qisqa ko'rsatma oladi;
      - ruxsat etilmagan begona foydalanuvchi — "Ushbu bot ishlamaydi"
        javobini oladi.
    """
    from_user = message.get("from") or {}
    user_id = from_user.get("id")
    if not user_id or from_user.get("is_bot"):
        return
    try:
        allowed = await db.get_allowed_user(user_id)
    except Exception as e:  # noqa: BLE001
        log.warning("allowed tekshirishda xatolik: %r", e)
        return
    text = ALLOWED_HINT_MESSAGE if allowed else NOT_ALLOWED_MESSAGE
    await tg.send_text_message(user_id, text)


async def handle_update(client: httpx.AsyncClient, update: dict):
    message = update.get("message")
    if not message:
        return

    if message.get("forum_topic_created"):
        await handle_forum_topic_created(message)
        return

    # Shaxsiy chatdagi (guruh emas) oddiy xabar/buyruq — foydalanuvchiga
    # javob beramiz. Guruhdagi oddiy xabarlarni e'tiborsiz qoldiramiz.
    if (message.get("chat") or {}).get("type") == "private":
        await handle_private_message(message)


async def run_polling():
    """Cheksiz sikl: getUpdates orqali yangilanishlarni kutib turadi.
    app.py'ning startup hodisasida asyncio.create_task() bilan fon
    vazifasi sifatida ishga tushiriladi va shutdown'da bekor qilinadi."""
    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        log.info("fon vazifasi ishga tushdi (topic-bog'lash + /start javoblari)...")
        while True:
            try:
                resp = await client.get(
                    f"{TG_API}/getUpdates",
                    params={"offset": offset, "timeout": 30, "allowed_updates": ["message"]},
                )
                data = resp.json()
                for update in data.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        await handle_update(client, update)
                    except Exception as e:  # noqa: BLE001
                        log.warning("Update ishlashda xatolik: %r", e)
            except asyncio.CancelledError:
                log.info("to'xtatildi.")
                raise
            except Exception as e:  # noqa: BLE001
                # Tarmoq xatosi va hokazo — sikl davom etadi, lekin darhol
                # qayta-qayta urinib serverga zarba bermaslik uchun kutamiz
                log.warning("getUpdates xatolik: %r", e)
                await asyncio.sleep(3)


if __name__ == "__main__":
    # Lokal/mustaqil sinov uchun (app.py'siz alohida ishga tushirish)
    asyncio.run(run_polling())
