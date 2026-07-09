"""
Filial Feedback Mini App — asosiy backend (FastAPI).

Ishga tushirish:
    uvicorn app:app --host 0.0.0.0 --port 8000

Muhit o'zgaruvchilari (.env):
    BOT_TOKEN, GROUP_CHAT_ID, DATABASE_URL
"""
import json
import os
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()  # faqat lokal ishlashda .env faylini o'qiydi; Railway'da shart emas
except ImportError:
    pass

from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional

import asyncio
import asyncpg

import db
import telegram_utils as tg
import bot_listener

app = FastAPI(title="Filial Feedback Mini App")

# Bootstrap uchun: ilk marta hech qanday superadmin bo'lmaganda shu yerdan
# ruxsat berish mumkin (.env dagi SUPERADMIN_IDS="123456789,987654321").
# Ilova ishga tushganda bu id'lar avtomatik allowed_users jadvaliga
# is_superadmin=TRUE qilib qo'shiladi.
SUPERADMIN_IDS = [
    int(x) for x in os.environ.get("SUPERADMIN_IDS", "").replace(" ", "").split(",") if x
]

NOT_ALLOWED_MESSAGE = "ushbu bot ishlamaydi"

# Mini app boshqa domenda joylashgan bo'lishi mumkin (masalan GitHub Pages / Railway static)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.on_event("shutdown")
async def _shutdown():
    task = getattr(app.state, "bot_listener_task", None)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    await db.close_pool()


@app.get("/")
async def health():
    # Railway health-check va domenni tekshirish uchun
    return {"status": "ok", "service": "filial-feedback-backend"}


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
async def get_config(init_data: str):
    user = await _check_auth(init_data)
    filials = await db.list_active_filials()
    checklist_types = await db.list_active_checklist_types()
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
async def get_sections(init_data: str, checklist_type_id: int):
    await _check_auth(init_data)
    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    sections = await db.list_active_sections(checklist_type_id)
    return {"sections": sections, "checklist_type": checklist_type}


# ---------------------------------------------------------------------------
# 2) Yakuniy yuborish: filial + har bir bo'lim uchun rasm(lar)
# ---------------------------------------------------------------------------
CHECKLIST_TYPE_EMOJI = {
    "opening": "🔓",
    "handover": "🔄",
    "closing": "🔒",
}


@app.post("/api/submit")
async def submit(
    init_data: str = Form(...),
    filial_id: int = Form(...),
    checklist_type_id: int = Form(...),
    items_meta: str = Form(...),  # JSON: [{"section_id": 1, "field": "photo_1", "comment": "..."}]
    files: List[UploadFile] = File(...),
):
    user = await _check_auth(init_data)

    filial = await db.get_filial(filial_id)
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")

    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")

    try:
        meta = json.loads(items_meta)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="items_meta JSON emas")

    if len(meta) != len(files):
        raise HTTPException(status_code=400, detail="Rasmlar soni mos emas")

    # Guruhda hali mavzu (topic) yo'q bo'lsa — avtomatik yaratamiz.
    # E'TIBOR: agar guruhda bu filial nomi bilan topic ALLAQACHON mavjud
    # bo'lsa (masalan admin qo'lda ochgan yoki bot_listener oldinroq
    # bog'lab qo'ygan bo'lsa), bazada thread_id allaqachon to'ldirilgan
    # bo'ladi va bu yerga umuman kirmaymiz — mavjud topicga yuboraveramiz.
    thread_id = filial["thread_id"]
    if not thread_id:
        # So'rov kelguncha oralab, boshqa parallel submit yoki
        # bot_listener allaqachon thread_id'ni bog'lagan bo'lishi mumkin —
        # shuning uchun yana bir bor bazadan yangilab tekshiramiz.
        fresh = await db.get_filial(filial_id)
        thread_id = fresh["thread_id"] if fresh else None

    if not thread_id:
        new_thread_id = await tg.create_forum_topic(filial["name"])
        # Atomik "claim": faqat thread_id hali NULL bo'lsagina o'rnatiladi.
        # Shu bilan bir vaqtda kelgan boshqa so'rov ikkinchi marta topic
        # yaratib yubormaydi.
        if await db.claim_filial_thread_id(filial_id, new_thread_id):
            thread_id = new_thread_id
        else:
            # Boshqa parallel so'rov bizdan oldin thread_id'ni o'rnatib
            # ulgurgan — o'sha mavjud thread_id'dan foydalanamiz.
            fresh = await db.get_filial(filial_id)
            thread_id = fresh["thread_id"]

    full_name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or user.get("username") or "Noma'lum"

    submission_id = await db.create_submission(
        filial_id=filial_id,
        filial_name=filial["name"],
        telegram_user_id=user["id"],
        full_name=full_name,
        checklist_type_id=checklist_type_id,
        checklist_type_name=checklist_type["name"],
    )

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    checklist_emoji = CHECKLIST_TYPE_EMOJI.get(checklist_type["key"], "📋")

    # Rasmlarni bo'lim (section_id) bo'yicha guruhlaymiz — shu tufayli bitta
    # bo'limga tegishli barcha rasmlar Telegramga BITTA albom (media group)
    # sifatida yuboriladi, har biri alohida xabar bo'lib ketmaydi.
    # dict Python 3.7+ da qo'shilish tartibini saqlaydi, shuning uchun
    # bo'limlar frontendda ko'rsatilgan tartibda yuboriladi.
    section_groups: dict[int, dict] = {}
    for item, upload in zip(meta, files):
        section_id = item["section_id"]
        group = section_groups.setdefault(section_id, {
            "section_name": item.get("section_name", ""),
            "items": [],
        })
        group["items"].append((item, upload))

    for section_id, group in section_groups.items():
        section_name = group["section_name"]
        items = group["items"]

        # Bo'lim uchun izoh — barcha rasmlar bitta umumiy izohni ishlatadi
        # (frontend shunday yuboradi), shuning uchun birinchisidan olamiz.
        comment = (items[0][0].get("comment") or "").strip()

        caption = (
            f"🏢 <b>{filial['name']}</b>\n"
            f"{checklist_emoji} <b>{checklist_type['name']}</b>\n"
            f"🕒 {now_str}\n👤 {full_name}"
        )
        if section_name:
            caption += f"\n📍 Bo'lim: {section_name}"
        if comment:
            caption += f"\n💬 {comment}"

        photo_payload = []
        for item, upload in items:
            photo_payload.append((await upload.read(), upload.filename or "photo.jpg"))

        if len(photo_payload) == 1:
            sent_list = [await tg.send_photo_to_topic(
                thread_id=thread_id,
                photo_bytes=photo_payload[0][0],
                filename=photo_payload[0][1],
                caption=caption,
            )]
        else:
            sent_list = await tg.send_media_group_to_topic(
                thread_id=thread_id,
                photos=photo_payload,
                caption=caption,
            )

        for (item, _upload), sent in zip(items, sent_list):
            item_comment = (item.get("comment") or "").strip()
            await db.add_submission_photo(
                submission_id=submission_id,
                section_id=section_id,
                file_id=sent["file_id"],
                comment=item_comment or None,
                sent_message_id=sent["message_id"],
            )

    return {"ok": True, "submission_id": submission_id}


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
    await _check_superadmin(init_data)
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
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas")
    filial = await db.create_filial(name)
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
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas")
    filial = await db.update_filial(filial_id, name, is_active)
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


# ---------- Chek-list turlari (o'qish uchun) ----------

@app.get("/api/admin/checklist-types")
async def admin_list_checklist_types(init_data: str):
    await _check_superadmin(init_data)
    return {"checklist_types": await db.list_all_checklist_types()}


# ---------- Bo'limlar (har bir chek-list turi uchun alohida) ----------

@app.get("/api/admin/sections")
async def admin_list_sections(init_data: str, checklist_type_id: int):
    await _check_superadmin(init_data)
    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    return {"sections": await db.list_all_sections(checklist_type_id)}


@app.post("/api/admin/sections")
async def admin_add_section(
    init_data: str = Form(...),
    checklist_type_id: int = Form(...),
    name: str = Form(...),
):
    await _check_superadmin(init_data)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bo'lim nomi bo'sh bo'lishi mumkin emas")
    checklist_type = await db.get_checklist_type(checklist_type_id)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")
    try:
        section = await db.create_section(checklist_type_id, name)
    except Exception:
        raise HTTPException(status_code=400, detail="Bu nomda bo'lim allaqachon mavjud")
    return {"ok": True, "section": section}


@app.put("/api/admin/sections/{section_id}")
async def admin_update_section(
    section_id: int,
    init_data: str = Form(...),
    name: str = Form(...),
    is_active: bool = Form(True),
):
    await _check_superadmin(init_data)
    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Bo'lim nomi bo'sh bo'lishi mumkin emas")
    try:
        section = await db.update_section(section_id, name, is_active)
    except Exception:
        raise HTTPException(status_code=400, detail="Bu nomda bo'lim allaqachon mavjud")
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
