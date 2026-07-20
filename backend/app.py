"""
Filial Feedback Mini App — asosiy backend (FastAPI).

Ishga tushirish:
    uvicorn app:app --host 0.0.0.0 --port 8000

Muhit o'zgaruvchilari (.env):
    BOT_TOKEN, GROUP_CHAT_ID, DATABASE_URL
"""
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

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

from fastapi import FastAPI, Form, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
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

# Mini app boshqa domenda joylashgan bo'lishi mumkin (masalan GitHub Pages / Railway static)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
            # Avval o'chirilishi kutilayotgan qoralamalarning zaxira
            # xabarlari ro'yxatini olamiz (bazadan o'chgandan keyin bu
            # ma'lumot yo'qoladi), keyin bazadan o'chiramiz, so'ng har
            # bir xabarni xodimning shaxsiy chatidan ham tozalaymiz.
            pending_messages = await db.get_stale_draft_photo_messages(max_age_minutes=15)
            deleted = await db.cleanup_stale_drafts(max_age_minutes=15)
            for msg in pending_messages:
                await tg.delete_message(msg["telegram_user_id"], msg["telegram_message_id"])
            if deleted:
                print(f"[draft_cleanup] {deleted} ta eskirgan (15+ daqiqa tegilmagan) qoralama tozalandi")
        except Exception as e:  # noqa: BLE001
            print("[draft_cleanup] xatolik:", e)
        await asyncio.sleep(2 * 60)  # har 2 daqiqada bir marta tekshiradi


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


@app.on_event("shutdown")
async def _shutdown():
    for task_name in ("bot_listener_task", "draft_cleanup_task"):
        task = getattr(app.state, task_name, None)
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
    print(f"[unhandled] {request.method} {request.url.path}: {exc!r}")
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
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Bo'sh fayl")

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
    if result.get("telegram_message_id"):
        await tg.delete_message(result["telegram_user_id"], result["telegram_message_id"])
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
    """E'TIBOR: rasmlar bu so'rovda YUKLANMAYDI. Ular xodim rasm olgan
    zahoti /api/draft/photo orqali allaqachon serverga saqlangan bo'ladi
    — bu yerda faqat o'sha qoralamadagi rasmlarni Telegram guruhiga
    jo'natish sodir bo'ladi. Shu tufayli bu so'rov juda yengil (fayl
    yo'q, faqat bir nechta ID/matn) va sekin yoki beqaror internetda
    ham muvaffaqiyatli yetib borish ehtimoli ancha yuqori — avval
    xodim BARCHA rasmlarni bitta og'ir so'rovda qayta yuklashi kerak
    edi, shu sabab ko'p rasmli/sekin internetli holatlarda so'rov
    uzilib qolib, "xatolik" chiqib, faqat botni qayta ishga tushirgach
    ishlashi mumkin edi."""
    lang = _norm_lang(lang)
    user = await _check_auth(init_data)

    draft = await db.get_draft(user["id"])
    if not draft or draft["filial_id"] != filial_id or draft["checklist_type_id"] != checklist_type_id:
        raise HTTPException(
            status_code=400,
            detail="Qoralama topilmadi yoki eskirgan. Sahifani yangilab, qaytadan urinib ko'ring.",
        )

    draft_photos = await db.list_draft_photos(user["id"])
    if not draft_photos:
        raise HTTPException(status_code=400, detail="Hech qanday rasm topilmadi")

    filial = await db.get_filial(filial_id)
    if not filial:
        raise HTTPException(status_code=404, detail="Filial topilmadi")

    # E'TIBOR: checklist_type['name'] shu yerda TANLANGAN TILDA (lang)
    # olinadi — shunda Telegram topic'iga yuboriladigan xabar sarlavhasi
    # ham foydalanuvchi ilovada tanlagan til bilan bir xil bo'ladi, front-
    # enddan kelgan matnga ishonib o'tirilmaydi (xavfsizroq va izchil).
    checklist_type = await db.get_checklist_type(checklist_type_id, lang)
    if not checklist_type:
        raise HTTPException(status_code=404, detail="Chek-list turi topilmadi")

    # Xavfsizlik: agar foydalanuvchida ESKIRGAN/keshlangan bo'limlar
    # ro'yxati bo'lsa (masalan sahifani yangilamagan bo'lsa), shu filial
    # uchun keyinchalik "yashirilgan" deb belgilangan bo'limga rasm
    # yuborilmasin — bunday bo'lim topilsa so'rov butunlay rad etiladi.
    checked_section_ids = {p["section_id"] for p in draft_photos}
    for section_id in checked_section_ids:
        if await db.is_section_hidden_for_filial(section_id, filial_id):
            raise HTTPException(
                status_code=400,
                detail="Tanlangan bo'limlardan biri bu filial uchun endi mavjud emas. Sahifani yangilab, qayta urinib ko'ring.",
            )

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
        try:
            new_thread_id = await tg.create_forum_topic(filial["name"])
        except Exception as e:  # noqa: BLE001
            print(f"[submit] topic yaratishda xato (filial={filial_id}): {e}")
            raise HTTPException(
                status_code=502,
                detail=(
                    "Filial uchun Telegram mavzusini ochib bo'lmadi (aloqa "
                    "muammosi). Internetni tekshirib, qayta 'Yuborish'ni bosing."
                ),
            ) from e
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

    now_str = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y %H:%M")
    checklist_emoji = CHECKLIST_TYPE_EMOJI.get(checklist_type["key"], "📋")

    # Rasmlarni bo'lim (section_id) bo'yicha guruhlaymiz — shu tufayli bitta
    # bo'limga tegishli barcha rasmlar Telegramga BITTA albom (media group)
    # sifatida yuboriladi, har biri alohida xabar bo'lib ketmaydi.
    # dict Python 3.7+ da qo'shilish tartibini saqlaydi, shuning uchun
    # bo'limlar frontendda ko'rsatilgan tartibda yuboriladi (draft_photos
    # id bo'yicha, ya'ni olingan tartibda, saralangan).
    section_groups: dict[int, list] = {}
    for p in draft_photos:
        section_groups.setdefault(p["section_id"], []).append(p)

    # Bo'lim nomlarini FRONTENDDAN kelgan matnga ishonib emas, bazadan
    # TANLANGAN TILDA (lang) qayta o'qib olamiz — shunda Telegram
    # topic'iga yuboriladigan "📍 Bo'lim: ..." qatori ham har doim
    # foydalanuvchi ilovada tanlagan til bilan bir xil bo'ladi.
    section_names: dict[int, str] = {}
    for section_id in section_groups:
        sec = await db.get_section(section_id, lang)
        section_names[section_id] = sec["name"] if sec else ""

    for section_id, photos_meta in section_groups.items():
        section_name = section_names.get(section_id, "")

        # Bo'lim uchun izoh — barcha rasmlar bitta umumiy izohni ishlatadi
        # (frontend shunday yuboradi), shuning uchun birinchisidan olamiz.
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

        # Rasmlarni shu paytda (yuborish arafasida) bazadan o'qiymiz —
        # ular allaqachon /api/draft/photo orqali Telegramga (xodimning
        # shaxsiy chatiga) yuborilgan, shuning uchun odatda faqat
        # `telegram_file_id` (kichkina matn) bo'ladi — QAYTA yuklash
        # shart emas. Faqat migratsiyadan oldingi ESKI qatorlarda hali
        # xom baytlar (`photo_data`) bo'lishi mumkin — ular uchun ham
        # orqaga moslik saqlangan.
        photo_payload = []
        for p in photos_meta:
            full_photo = await db.get_draft_photo(p["id"], user["id"])
            if not full_photo:
                continue
            if full_photo.get("telegram_file_id"):
                photo_payload.append({"file_id": full_photo["telegram_file_id"]})
            elif full_photo.get("photo_data"):
                photo_payload.append({"data": full_photo["photo_data"], "filename": full_photo["filename"] or "photo.jpg"})

        if not photo_payload:
            continue

        # MUHIM TUZATISH: agar guruhdagi topic admin tomonidan qo'lda
        # o'chirib yuborilgan bo'lsa (yoki boshqa sababdan Telegramda
        # endi mavjud bo'lmasa), Telegram "message thread not found"
        # xatosini qaytaradi va OLDIN bu SHU YERDA (yoki oldingi
        # bo'limlarda) hisobotni BUTUNLAY to'xtatib qo'yardi — xodim
        # nechta marta "Yuborish"ni bossa ham hech qachon guruhga
        # yetib bormasdi, chunki bazadagi eskirgan thread_id hech qachon
        # tuzatilmasdi. Endi shu xato ushlanadi: yangi topic yaratiladi,
        # bazadagi thread_id yangilanadi va yuborish shu yangi topicga
        # BIR MARTA qayta uriniladi.
        try:
            sent_list = await tg.send_media_group_to_topic(
                thread_id=thread_id,
                items=photo_payload,
                caption=caption,
            )
        except TelegramTopicMissingError:
            new_thread_id = await tg.create_forum_topic(filial["name"])
            await db.set_filial_thread_id(filial_id, new_thread_id)
            thread_id = new_thread_id
            sent_list = await tg.send_media_group_to_topic(
                thread_id=thread_id,
                items=photo_payload,
                caption=caption,
            )
        except Exception as e:  # noqa: BLE001
            # Boshqa har qanday kutilmagan xato (tarmoq, Telegram
            # tomonidagi muammo va h.k.) — foydalanuvchiga TUSHUNARLI
            # xabar bilan qaytariladi (ilgari FastAPI buni umumiy "500
            # Internal Server Error" qilib ko'rsatardi, xodim sababini
            # bilolmasdi). Shu paytgacha muvaffaqiyatli yuborilgan
            # bo'limlar qoralamadan allaqachon o'chirilgan bo'lgani
            # uchun, xodim qayta "Yuborish"ni bossa faqat QOLGAN
            # bo'limlar qayta uriniladi — hech narsa ikki marta
            # yuborilmaydi.
            print(f"[submit] bo'lim {section_id} yuborishda xato: {e}")
            raise HTTPException(
                status_code=502,
                detail=(
                    "Guruhga yuborishda xatolik yuz berdi (Telegram bilan "
                    "aloqa muammosi). Internetni tekshirib, qayta 'Yuborish'ni "
                    "bosing — allaqachon yuborilgan rasmlar qayta yuborilmaydi."
                ),
            ) from e

        for p, sent in zip(photos_meta, sent_list):
            item_comment = (p.get("comment") or "").strip()
            await db.add_submission_photo(
                submission_id=submission_id,
                section_id=section_id,
                file_id=sent["file_id"],
                comment=item_comment or None,
                sent_message_id=sent["message_id"],
            )

        # Shu bo'lim MUVAFFAQIYATLI yuborilgach, uni qoralamadan darhol
        # o'chiramiz. Shu tufayli agar keyingi bo'limni yuborishda xatolik
        # yuz berib, xodim qayta "Yuborish"ni bosishga majbur bo'lsa —
        # allaqachon yuborilgan bo'limlar QAYTA yuborilmaydi (dublikat
        # bo'lmaydi), faqat qolganlari qayta urinilardi.
        #
        # MUHIM TUZATISH: xodimning shaxsiy chatidagi zaxira xabarini
        # o'chirish endi javobni KUTIB TURMAYDI (fon vazifasi sifatida
        # ishga tushiriladi). Bo'limlar ko'p bo'lgan hisobotlarda bu
        # tozalash (har bir rasm uchun alohida Telegram so'rovi) javobni
        # o'nlab soniyaga kechiktirib, "Yuborish" so'rovining o'zi
        # tarmoq darajasida uzilib qolishiga (mobil qurilmalarda "Load
        # failed" xatosi) sabab bo'lishi mumkin edi. Bu — shunchaki
        # "iloji bo'lsa tozalash" (xatoligi allaqachon e'tiborga
        # olinmaydi), shuning uchun uni orqa fonda, javobga to'sqinlik
        # qilmasdan bajarish butunlay xavfsiz.
        for p in photos_meta:
            deleted = await db.delete_draft_photo(p["id"], user["id"])
            if deleted and deleted.get("telegram_message_id"):
                asyncio.create_task(
                    tg.delete_message(deleted["telegram_user_id"], deleted["telegram_message_id"])
                )

    # Hammasi muvaffaqiyatli yuborilgach — qoralama endi kerak emas.
    await db.clear_draft(user["id"])

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
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas!")
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
        raise HTTPException(status_code=400, detail="Filial nomi bo'sh bo'lishi mumkin emas!")
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

    names = await translate_utils.translate_to_all_langs(name, lang)
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
