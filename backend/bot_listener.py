"""
Yengil "listener": Telegramdan kontakt (telefon raqami) xabarlarini kutib,
uni user_contacts jadvaliga yozadi. Bot API ning getUpdates (long polling)
usulidan foydalanadi — mavjud framework (aiogram/python-telegram-bot) bilan
to'qnashmaydi, chunki alohida oddiy HTTP so'rovlar orqali ishlaydi.

Agar loyihada allaqachon aiogram/PTB ishlatilayotgan bo'lsa, bu faylni
alohida ishga tushirmang — buning o'rniga shu logikani (contact handler)
mavjud botingizga qo'shing (pastda "INTEGRATSIYA" izohiga qarang).

Ishga tushirish:
    python bot_listener.py
"""
import asyncio
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import httpx

import db

BOT_TOKEN = os.environ["BOT_TOKEN"]
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

WELCOME_TEXT = (
    "Assalomu alaykum! Anketa (rasm hisobot) uchun avval telefon raqamingizni "
    "ulashing 👇"
)

NOT_ALLOWED_TEXT = "ushbu bot ishlamaydi"


async def send_contact_request(client: httpx.AsyncClient, chat_id: int):
    keyboard = {
        "keyboard": [[{"text": "📱 Raqamni ulashish", "request_contact": True}]],
        "resize_keyboard": True,
        "one_time_keyboard": True,
    }
    await client.post(
        f"{TG_API}/sendMessage",
        json={"chat_id": chat_id, "text": WELCOME_TEXT, "reply_markup": keyboard},
    )


async def handle_forum_topic_created(message: dict):
    """Guruhda YANGI forum-topic yaratilganda Telegram shu turdagi xizmat
    xabarini yuboradi (botning o'zi createForumTopic orqali yaratganda ham,
    ADMIN GURUHDA QO'LDA yaratganda ham). Agar topic nomi mini-app'dagi
    biror filial nomi bilan bir xil bo'lsa va o'sha filialda hali thread_id
    o'rnatilmagan bo'lsa — shu topicni filialga bog'lab qo'yamiz.

    Shu tufayli: agar guruhda filial nomi bilan topic ALLAQACHON mavjud
    bo'lsa (yoki admin uni qo'lda oldindan yaratib qo'ygan bo'lsa), mini-app
    xuddi shu nom bilan qaytadan topic yaratmaydi — chunki thread_id
    bazada allaqachon to'ldirilgan bo'ladi va submit() shunchaki mavjud
    topicga xabar yuboraveradi."""
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
            print(
                f"Topic avtomatik bog'landi: '{topic_name}' -> "
                f"filial #{linked['id']} (thread_id={thread_id})"
            )
    except Exception as e:  # noqa: BLE001
        print("Topic bog'lashda xatolik:", e)


async def handle_update(client: httpx.AsyncClient, update: dict):
    message = update.get("message")
    if not message:
        return

    # Guruh ichida yangi topic ochilishi haqidagi xizmat xabari — kontakt/
    # /start logikasidan oldin, alohida ishlov beramiz va chiqib ketamiz.
    if message.get("forum_topic_created"):
        await handle_forum_topic_created(message)
        return

    chat_id = message["chat"]["id"]
    from_user_id = message.get("from", {}).get("id")

    # Faqat ruxsat etilganlar (allowed_users) ro'yxatidagi foydalanuvchilar
    # botdan foydalana oladi. Boshqa har qanday begona foydalanuvchi uchun
    # /start bosganda "ushbu bot ishlamaydi" deb javob beramiz.
    allowed = await db.get_allowed_user(from_user_id) if from_user_id else None
    if not allowed:
        if message.get("text") == "/start":
            await client.post(
                f"{TG_API}/sendMessage",
                json={"chat_id": chat_id, "text": NOT_ALLOWED_TEXT},
            )
        return

    # /start bosilganda — agar telefon hali bazada bo'lmasa, so'raymiz
    if message.get("text") == "/start":
        existing = await db.get_contact(chat_id)
        if not existing:
            await send_contact_request(client, chat_id)
        return

    contact = message.get("contact")
    if contact:
        # Faqat foydalanuvchining o'z raqami qabul qilinadi (boshqa odam nomidan emas)
        if contact.get("user_id") == message["from"]["id"]:
            full_name = " ".join(
                filter(None, [contact.get("first_name"), contact.get("last_name")])
            )
            await db.upsert_contact(
                telegram_user_id=contact["user_id"],
                phone=contact["phone_number"],
                full_name=full_name or message["from"].get("first_name"),
            )
            await client.post(
                f"{TG_API}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "Rahmat! Endi mini-ilovadan foydalanishingiz mumkin.",
                    "reply_markup": {"remove_keyboard": True},
                },
            )


async def main():
    offset = 0
    async with httpx.AsyncClient(timeout=35) as client:
        print("bot_listener ishga tushdi...")
        while True:
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
                    print("Xatolik:", e)


if __name__ == "__main__":
    asyncio.run(main())

# ---------------------------------------------------------------------------
# INTEGRATSIYA: agar sizda allaqachon aiogram/python-telegram-bot ishlayotgan
# bo'lsa, shunchaki uning "contact" message handleriga quyidagini qo'shing:
#
#   await db.upsert_contact(
#       telegram_user_id=message.contact.user_id,
#       phone=message.contact.phone_number,
#       full_name=message.from_user.first_name,
#   )
# ---------------------------------------------------------------------------
