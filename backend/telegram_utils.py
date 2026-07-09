"""
- Telegram WebApp initData ni tekshirish (xavfsizlik uchun majburiy)
- Bot API orqali rasm yuborish / forum-topic yaratish
"""
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

import httpx

BOT_TOKEN = os.environ["BOT_TOKEN"]
GROUP_CHAT_ID = int(os.environ["GROUP_CHAT_ID"])  # masalan: -1001234567890
TG_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

INIT_DATA_MAX_AGE = 24 * 60 * 60  # 24 soat


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
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{TG_API}/createForumTopic",
            json={"chat_id": GROUP_CHAT_ID, "name": name},
        )
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"createForumTopic xato: {data}")
        return data["result"]["message_thread_id"]


async def send_photo_to_topic(thread_id: int, photo_bytes: bytes, filename: str,
                               caption: str) -> dict:
    """Rasmni tegishli filial mavzusiga (topic) yuboradi. {file_id, message_id} qaytaradi."""
    files = {"photo": (filename, photo_bytes, "image/jpeg")}
    data = {
        "chat_id": GROUP_CHAT_ID,
        "message_thread_id": thread_id,
        "caption": caption,
        "parse_mode": "HTML",
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{TG_API}/sendPhoto", data=data, files=files)
        resp.raise_for_status()
        result = resp.json()
        if not result.get("ok"):
            raise RuntimeError(f"sendPhoto xato: {result}")
        msg = result["result"]
        largest_photo = msg["photo"][-1]
        return {"file_id": largest_photo["file_id"], "message_id": msg["message_id"]}


# Telegram sendMediaGroup bitta so'rovda ko'pi bilan 10 ta media qabul qiladi.
MEDIA_GROUP_CHUNK_SIZE = 10


async def send_media_group_to_topic(thread_id: int, photos: list[tuple[bytes, str]],
                                     caption: str) -> list[dict]:
    """Bir nechta rasmni BITTA albom (media group) sifatida filial mavzusiga
    yuboradi — Telegramda barchasi bitta xabar/albom bo'lib ko'rinadi.
    Caption faqat albomning birinchi rasmiga qo'yiladi (Telegram shuni albom
    izohi sifatida ko'rsatadi). photos yuborilgan tartibda {file_id,
    message_id} ro'yxatini qaytaradi.

    Agar 10 tadan ko'p rasm bo'lsa, Telegram cheklovi tufayli 10 talik
    bo'laklarga (chunk) bo'linib ketma-ket albomlar sifatida yuboriladi;
    caption faqat birinchi bo'lakning birinchi rasmiga qo'yiladi.
    """
    out: list[dict] = []
    async with httpx.AsyncClient(timeout=60) as client:
        for chunk_start in range(0, len(photos), MEDIA_GROUP_CHUNK_SIZE):
            chunk = photos[chunk_start:chunk_start + MEDIA_GROUP_CHUNK_SIZE]

            if len(chunk) == 1:
                # sendMediaGroup kamida 2 ta media talab qiladi — yagona
                # rasm qolsa oddiy sendPhoto bilan yuboramiz.
                photo_bytes, filename = chunk[0]
                item_caption = caption if chunk_start == 0 else ""
                sent = await send_photo_to_topic(thread_id, photo_bytes, filename, item_caption)
                out.append(sent)
                continue

            media = []
            files = {}
            for idx, (photo_bytes, filename) in enumerate(chunk):
                attach_name = f"photo{chunk_start + idx}"
                files[attach_name] = (filename, photo_bytes, "image/jpeg")
                item = {"type": "photo", "media": f"attach://{attach_name}"}
                if idx == 0 and chunk_start == 0:
                    item["caption"] = caption
                    item["parse_mode"] = "HTML"
                media.append(item)

            data = {
                "chat_id": GROUP_CHAT_ID,
                "message_thread_id": thread_id,
                "media": json.dumps(media),
            }
            resp = await client.post(f"{TG_API}/sendMediaGroup", data=data, files=files)
            resp.raise_for_status()
            result = resp.json()
            if not result.get("ok"):
                raise RuntimeError(f"sendMediaGroup xato: {result}")
            for msg in result["result"]:
                largest_photo = msg["photo"][-1]
                out.append({"file_id": largest_photo["file_id"], "message_id": msg["message_id"]})

    return out
