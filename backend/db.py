"""
PostgreSQL bilan ishlash uchun yordamchi qatlam (asyncpg asosida).
"""
import os
import asyncpg
from typing import Optional

# Env yetishmasa — noaniq KeyError o'rniga tushunarli xato beramiz.
try:
    DATABASE_URL = os.environ["DATABASE_URL"]  # masalan: postgresql://user:pass@host:5432/db
except KeyError as e:
    raise RuntimeError(
        "DATABASE_URL muhit o'zgaruvchisi o'rnatilmagan. Railway'da Postgres "
        "servisidan `${{Postgres.DATABASE_URL}}` sifatida ulang."
    ) from e

# Pool o'lchami — ilgari max_size=25 qattiq yozilgan edi. Har bir ochiq
# ulanish Railway Postgres'da xotira band qiladi; 25 ta zaxira bu kichik
# ilova uchun ortiqcha. Standart 10 (env orqali sozlanadi) — 20+ xodim
# bir vaqtda ishlasa ham yetarli, lekin bazaga bekorga yuk solmaydi.
DB_POOL_MIN = int(os.environ.get("DB_POOL_MIN", "1"))
DB_POOL_MAX = int(os.environ.get("DB_POOL_MAX", "10"))

_pool: Optional[asyncpg.Pool] = None

# ---------- Ko'p tillilik (uz / ru / en) uchun umumiy yordamchi ----------
# Har bir til uchun "afzal ko'rilgan ustun -> zaxira ustunlar" tartibi.
# Masalan foydalanuvchi Rus tilini tanlagan bo'lsa, avval name_ru ga
# qaraladi; agar u to'ldirilmagan bo'lsa (masalan admin faqat o'zbekcha
# nom kiritgan bo'lsa), name_uz ga, so'ng name_en ga tushiladi — shu
# bilan bo'lim/chek-list turi hech qachon bo'sh nomsiz ko'rinmaydi.
_LANG_FALLBACK_ORDER = {
    "uz": ["name_uz", "name_ru", "name_en"],
    "ru": ["name_ru", "name_uz", "name_en"],
    "en": ["name_en", "name_ru", "name_uz"],
}


def _localized_name(row: dict, lang: str) -> str:
    for col in _LANG_FALLBACK_ORDER.get(lang, _LANG_FALLBACK_ORDER["uz"]):
        val = row.get(col)
        if val:
            return val
    return row.get("name") or ""


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        # O'lcham env orqali sozlanadi (DB_POOL_MIN/DB_POOL_MAX). Standart
        # 1..10 — 20+ xodim bir vaqtda ishlasa ham yetarli, lekin Railway
        # Postgres'ga ortiqcha ochiq ulanish bilan yuk solmaydi.
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=DB_POOL_MIN, max_size=DB_POOL_MAX)
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


# ---------- Ruxsat etilgan foydalanuvchilar (whitelist) ----------

async def get_allowed_user(telegram_user_id: int):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, telegram_user_id, full_name, is_superadmin FROM allowed_users "
        "WHERE telegram_user_id = $1",
        telegram_user_id,
    )
    return dict(row) if row else None


async def list_allowed_users():
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, telegram_user_id, full_name, is_superadmin, created_at "
        "FROM allowed_users ORDER BY created_at"
    )
    return [dict(r) for r in rows]


async def add_allowed_user(telegram_user_id: int, full_name: str | None, is_superadmin: bool) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO allowed_users (telegram_user_id, full_name, is_superadmin)
        VALUES ($1, $2, $3)
        ON CONFLICT (telegram_user_id)
        DO UPDATE SET full_name = EXCLUDED.full_name, is_superadmin = EXCLUDED.is_superadmin
        RETURNING id, telegram_user_id, full_name, is_superadmin
        """,
        telegram_user_id, full_name, is_superadmin,
    )
    return dict(row)


async def update_allowed_user(user_id: int, full_name: str | None, is_superadmin: bool) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE allowed_users SET full_name = $2, is_superadmin = $3
        WHERE id = $1
        RETURNING id, telegram_user_id, full_name, is_superadmin
        """,
        user_id, full_name, is_superadmin,
    )
    return dict(row) if row else None


async def delete_allowed_user(user_id: int) -> bool:
    pool = await get_pool()
    result = await pool.execute("DELETE FROM allowed_users WHERE id = $1", user_id)
    return result.endswith(" 1")


# ---------- Filiallar ----------

async def list_active_filials():
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, thread_id FROM filials WHERE is_active = TRUE ORDER BY sort_order, name"
    )
    return [dict(r) for r in rows]


async def list_all_filials():
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name, thread_id, sort_order, is_active FROM filials ORDER BY sort_order, name"
    )
    return [dict(r) for r in rows]


async def get_filial(filial_id: int):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, thread_id FROM filials WHERE id = $1", filial_id
    )
    return dict(row) if row else None


async def set_filial_thread_id(filial_id: int, thread_id: int):
    pool = await get_pool()
    await pool.execute(
        "UPDATE filials SET thread_id = $1 WHERE id = $2", thread_id, filial_id
    )


async def claim_filial_thread_id(filial_id: int, thread_id: int) -> bool:
    """Filialga thread_id'ni FAQAT hali thread_id o'rnatilmagan bo'lsagina
    biriktiradi (UPDATE ... WHERE thread_id IS NULL). Bu bir vaqtning o'zida
    kelgan bir nechta so'rov bir xil filial uchun ikkita alohida topic
    yaratib yubormasligini kafolatlaydi (race condition himoyasi).
    True qaytsa — shu chaqiruv thread_id'ni muvaffaqiyatli o'rnatdi degani."""
    pool = await get_pool()
    result = await pool.execute(
        "UPDATE filials SET thread_id = $1 WHERE id = $2 AND thread_id IS NULL",
        thread_id, filial_id,
    )
    return result.endswith(" 1")


async def link_thread_id_by_name(topic_name: str, thread_id: int) -> Optional[dict]:
    """Guruhda (botning o'zi orqali yoki ADMIN TOMONIDAN QO'LDA) yangi forum-topic
    yaratilganda chaqiriladi. Agar topic nomi mini-app'dagi biror filial nomi
    bilan mos kelsa (katta-kichik harf va bo'sh joylarga sezgir emas) va o'sha
    filialda hali thread_id o'rnatilmagan bo'lsa — shu topicni filialga bog'lab
    qo'yadi. Natijada keyingi safar shu filialga hisobot yuborilganda mini-app
    xuddi shu nom bilan YANGI topic yaratmaydi, balki mavjudiga yozadi."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE filials SET thread_id = $2
        WHERE lower(trim(name)) = lower(trim($1)) AND thread_id IS NULL
        RETURNING id, name, thread_id
        """,
        topic_name, thread_id,
    )
    return dict(row) if row else None


async def get_filial_by_name(name: str):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name, thread_id FROM filials WHERE lower(trim(name)) = lower(trim($1))",
        name,
    )
    return dict(row) if row else None


async def create_filial(name: str) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "INSERT INTO filials (name) VALUES ($1) RETURNING id, name, thread_id", name
    )
    return dict(row)


async def update_filial(filial_id: int, name: str, is_active: bool) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE filials SET name = $2, is_active = $3
        WHERE id = $1
        RETURNING id, name, thread_id, sort_order, is_active
        """,
        filial_id, name, is_active,
    )
    return dict(row) if row else None


async def delete_filial(filial_id: int) -> bool:
    """Filialni bazadan BUTUNLAY o'chirib tashlaydi. Bog'liq eski
    hisobotlar (submissions) saqlanib qoladi — ularning filial_id
    ustuni NULL bo'lib qoladi (FK: ON DELETE SET NULL), filial nomi esa
    submissions.filial_name_snapshot orqali tarixda saqlanib qoladi."""
    pool = await get_pool()
    result = await pool.execute("DELETE FROM filials WHERE id = $1", filial_id)
    return result.endswith(" 1")


async def set_filial_active(filial_id: int, is_active: bool) -> Optional[dict]:
    """Filialni faol/nofaol qilib qo'yadi (ko'z icon). Bazadan
    o'chirmaydi — faqat ro'yxatlarda ko'rinish/ko'rinmasligini
    boshqaradi, superadmin xohlagan payt qayta faollashtirishi mumkin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE filials SET is_active = $2
        WHERE id = $1
        RETURNING id, name, thread_id, sort_order, is_active
        """,
        filial_id, is_active,
    )
    return dict(row) if row else None


# ---------- Chek-list turlari (Ochilish / Topshirish / Yopilish) ----------

async def list_active_checklist_types(lang: str = "uz"):
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, key, name_uz, name_ru, name_en FROM checklist_types "
        "WHERE is_active = TRUE ORDER BY sort_order, id"
    )
    result = []
    for r in rows:
        d = dict(r)
        d["name"] = _localized_name(d, lang)
        result.append(d)
    return result


async def list_all_checklist_types():
    """Admin panel uchun — barcha 3 til qatorlari xom holda qaytariladi
    (tahrirlash uchun), 'name' maydoni hisoblanmaydi."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, key, name_uz, name_ru, name_en, sort_order, is_active "
        "FROM checklist_types ORDER BY sort_order, id"
    )
    return [dict(r) for r in rows]


async def get_checklist_type(checklist_type_id: int, lang: str = "uz"):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, key, name_uz, name_ru, name_en FROM checklist_types WHERE id = $1",
        checklist_type_id,
    )
    if not row:
        return None
    d = dict(row)
    d["name"] = _localized_name(d, lang)
    return d


async def update_checklist_type_name(checklist_type_id: int, name_uz: str, name_ru: str, name_en: str) -> Optional[dict]:
    """Superadmin smena nomini (masalan "Smena ochilishi") tahrirlaganda
    chaqiriladi — `key` (kodda ishlatiladigan doimiy identifikator)
    o'zgarmaydi, faqat foydalanuvchiga ko'rinadigan 3 tildagi nom."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE checklist_types SET name_uz = $2, name_ru = $3, name_en = $4
        WHERE id = $1
        RETURNING id, key, name_uz, name_ru, name_en, sort_order, is_active
        """,
        checklist_type_id, name_uz or None, name_ru or None, name_en or None,
    )
    return dict(row) if row else None


# ---------- Bo'limlar (har biri bitta chek-list turiga tegishli) ----------

async def list_active_sections(checklist_type_id: int, lang: str = "uz", filial_id: Optional[int] = None):
    pool = await get_pool()
    if filial_id is None:
        rows = await pool.fetch(
            """
            SELECT id, name_uz, name_ru, name_en FROM sections
            WHERE is_active = TRUE AND checklist_type_id = $1
            ORDER BY sort_order, id
            """,
            checklist_type_id,
        )
    else:
        # filial_id berilgan bo'lsa, shu filial uchun "yashirilgan" deb
        # belgilangan bo'limlar (filial_section_hidden) ro'yxatdan
        # chiqarib tashlanadi — masalan foodcourt filialida "Tashqi
        # hudud" bo'limi umuman ko'rinmasligi kerak bo'lsa, shu yerda
        # filtrlanadi.
        rows = await pool.fetch(
            """
            SELECT s.id, s.name_uz, s.name_ru, s.name_en FROM sections s
            WHERE s.is_active = TRUE AND s.checklist_type_id = $1
              AND NOT EXISTS (
                  SELECT 1 FROM filial_section_hidden h
                  WHERE h.section_id = s.id AND h.filial_id = $2
              )
            ORDER BY s.sort_order, s.id
            """,
            checklist_type_id, filial_id,
        )
    result = []
    for r in rows:
        d = dict(r)
        d["name"] = _localized_name(d, lang)
        result.append(d)
    return result


async def list_all_sections(checklist_type_id: int):
    """Admin panel uchun — barcha 3 til qatorlari xom holda qaytariladi."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT id, name_uz, name_ru, name_en, sort_order, is_active FROM sections
        WHERE checklist_type_id = $1
        ORDER BY sort_order, id
        """,
        checklist_type_id,
    )
    return [dict(r) for r in rows]


async def get_section(section_id: int, lang: str = "uz"):
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, name_uz, name_ru, name_en FROM sections WHERE id = $1", section_id
    )
    if not row:
        return None
    d = dict(row)
    d["name"] = _localized_name(d, lang)
    return d


async def create_section(checklist_type_id: int, name_uz: str, name_ru: str, name_en: str) -> dict:
    pool = await get_pool()
    # `name` ustuni eski jadval sxemasidan meros (hali NOT NULL) — birinchi
    # to'ldirilgan tildagi nom bilan to'ldiramiz, lekin logikada endi
    # ishlatilmaydi (uning o'rniga name_uz/ru/en ishlatiladi).
    legacy_name = name_uz or name_ru or name_en
    # Yangi bo'lim RO'YXAT OXIRIGA qo'shiladi (mavjud eng katta
    # sort_order'dan +1), doim 0 bilan boshlanmaydi — aks holda yangi
    # bo'lim eskilarning tepasiga tushib, tartibni buzib qo'yardi.
    row = await pool.fetchrow(
        """
        INSERT INTO sections (name, name_uz, name_ru, name_en, checklist_type_id, sort_order)
        VALUES (
            $1, $2, $3, $4, $5,
            COALESCE((SELECT MAX(sort_order) + 1 FROM sections WHERE checklist_type_id = $5), 0)
        )
        RETURNING id, name_uz, name_ru, name_en, sort_order, is_active
        """,
        legacy_name, name_uz or None, name_ru or None, name_en or None, checklist_type_id,
    )
    return dict(row)


async def update_section(section_id: int, name_uz: str, name_ru: str, name_en: str, is_active: bool) -> Optional[dict]:
    pool = await get_pool()
    legacy_name = name_uz or name_ru or name_en
    row = await pool.fetchrow(
        """
        UPDATE sections SET name = $2, name_uz = $3, name_ru = $4, name_en = $5, is_active = $6
        WHERE id = $1
        RETURNING id, name_uz, name_ru, name_en, sort_order, is_active
        """,
        section_id, legacy_name, name_uz or None, name_ru or None, name_en or None, is_active,
    )
    return dict(row) if row else None


async def delete_section(section_id: int) -> bool:
    """Bo'limni bazadan butunlay o'chiradi. submission_photos.section_id
    bu jadvalga FK bilan bog'langan (ON DELETE clause'siz — ya'ni RESTRICT),
    shuning uchun agar bu bo'limda allaqachon yuborilgan rasm(lar) bo'lsa,
    Postgres o'chirishni rad etadi (ForeignKeyViolationError). Bunday holda
    tarixiy hisobotlarni saqlab qolish uchun admin panelda ko'z
    (faol/nofaol) ikonkasidan foydalanish tavsiya etiladi."""
    pool = await get_pool()
    result = await pool.execute("DELETE FROM sections WHERE id = $1", section_id)
    return result.endswith(" 1")


async def set_section_active(section_id: int, is_active: bool) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE sections SET is_active = $2
        WHERE id = $1
        RETURNING id, name_uz, name_ru, name_en, sort_order, is_active
        """,
        section_id, is_active,
    )
    return dict(row) if row else None


# ---------- Bo'limni filial bo'yicha yashirish ("opt-out") ----------

async def get_hidden_filial_ids_for_section(section_id: int) -> list[int]:
    """Admin panelda "qaysi filiallarda ko'rinmasin" modalini ochish
    uchun — shu bo'lim hozircha qaysi filial(lar) uchun yashirilganini
    qaytaradi."""
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT filial_id FROM filial_section_hidden WHERE section_id = $1", section_id
    )
    return [r["filial_id"] for r in rows]


async def set_hidden_filials_for_section(section_id: int, hidden_filial_ids: list[int]) -> None:
    """Bo'lim uchun "yashirilgan filiallar" ro'yxatini TO'LIQ almashtiradi
    (avvalgi holatidan qat'iy nazar) — admin modalda belgilagan checkbox
    holatiga mos keladi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM filial_section_hidden WHERE section_id = $1", section_id
            )
            if hidden_filial_ids:
                await conn.executemany(
                    "INSERT INTO filial_section_hidden (filial_id, section_id) VALUES ($1, $2)",
                    [(fid, section_id) for fid in hidden_filial_ids],
                )


async def is_section_hidden_for_filial(section_id: int, filial_id: int) -> bool:
    """Hisobot yuborilayotganda (submit) serverda xavfsizlik uchun
    tekshiriladi — foydalanuvchi (masalan eskirgan/keshlangan sahifa
    orqali) shu filial uchun yashirilgan bo'limga rasm yubormasin."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT 1 FROM filial_section_hidden WHERE section_id = $1 AND filial_id = $2",
        section_id, filial_id,
    )
    return row is not None


async def reorder_sections(checklist_type_id: int, ordered_section_ids: list[int]) -> None:
    """Superadmin admin panelda drag-and-drop bilan belgilagan YANGI
    tartibni saqlaydi. `ordered_section_ids` ro'yxatidagi ketma-ketlik
    bo'yicha sort_order 0,1,2,... qilib qayta yoziladi — shu bilan
    barcha oddiy foydalanuvchilar tomonida ham bo'limlar aynan shu
    tartibda ko'rinadi (chunki list_active_sections ORDER BY sort_order
    ishlatadi). `checklist_type_id` bilan cheklash — boshqa chek-list
    turiga tegishli section_id tasodifan (yoki xato/zararli so'rov bilan)
    aralashib ketmasligi uchun xavfsizlik chorasi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            for index, section_id in enumerate(ordered_section_ids):
                await conn.execute(
                    "UPDATE sections SET sort_order = $2 WHERE id = $1 AND checklist_type_id = $3",
                    section_id, index, checklist_type_id,
                )


# ---------- Submissionlar ----------

async def create_submission(filial_id: int, filial_name: str, telegram_user_id: int, full_name: str,
                             checklist_type_id: int | None = None, checklist_type_name: str | None = None) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO submissions (filial_id, filial_name_snapshot, telegram_user_id, full_name,
                                  checklist_type_id, checklist_type_name_snapshot)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """,
        filial_id, filial_name, telegram_user_id, full_name, checklist_type_id, checklist_type_name,
    )
    return row["id"]


async def add_submission_photo(submission_id: int, section_id: int, file_id: str,
                                comment: str | None, sent_message_id: int | None):
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO submission_photos (submission_id, section_id, telegram_file_id, comment, sent_message_id)
        VALUES ($1, $2, $3, $4, $5)
        """,
        submission_id, section_id, file_id, comment, sent_message_id,
    )


# ---------- Qoralamalar (draft) ----------
# Har bir xodimning FAQAT o'ziga tegishli, hali yuborilmagan hisoboti —
# rasm olingan zahoti shu yerga saqlanadi, shuning uchun ilova yopilib
# ketsa yoki "Yuborish" muvaffaqiyatsiz tugasa ham ma'lumot yo'qolmaydi.

async def get_draft(telegram_user_id: int) -> Optional[dict]:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT id, telegram_user_id, filial_id, checklist_type_id, lang, updated_at "
        "FROM drafts WHERE telegram_user_id = $1",
        telegram_user_id,
    )
    return dict(row) if row else None


async def get_or_create_draft(telegram_user_id: int) -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO drafts (telegram_user_id)
        VALUES ($1)
        ON CONFLICT (telegram_user_id) DO UPDATE SET telegram_user_id = EXCLUDED.telegram_user_id
        RETURNING id, telegram_user_id, filial_id, checklist_type_id, lang, updated_at
        """,
        telegram_user_id,
    )
    return dict(row)


async def ensure_draft_meta(telegram_user_id: int, filial_id: Optional[int], checklist_type_id: Optional[int]) -> None:
    """`set_draft_meta`dan farqli o'laroq — bu funksiya HECH QACHON
    mavjud qiymatni bosib yozmaydi (faqat hali NULL bo'lgan joyni
    to'ldiradi, COALESCE orqali) va rasmlarni HECH QACHON tozalamaydi.
    Rasm yuklash so'rovidan "xavfsizlik to'ri" sifatida chaqiriladi —
    agar alohida saveDraftMeta so'rovi biror sababdan hali ulgurmagan/
    muvaffaqiyatsiz bo'lgan bo'lsa ham, qoralamaning filial/smena
    ma'lumoti bo'sh qolib ketmasin uchun."""
    pool = await get_pool()
    await get_or_create_draft(telegram_user_id)  # qator mavjudligini kafolatlaydi
    await pool.execute(
        """
        UPDATE drafts
        SET filial_id = COALESCE(filial_id, $2),
            checklist_type_id = COALESCE(checklist_type_id, $3),
            updated_at = now()
        WHERE telegram_user_id = $1
        """,
        telegram_user_id, filial_id, checklist_type_id,
    )


async def set_draft_meta(telegram_user_id: int, filial_id: Optional[int],
                          checklist_type_id: Optional[int], lang: str) -> dict:
    """Foydalanuvchi filial/chek-list turini tanlaganda chaqiriladi —
    shu tanlov saqlanadi, shunda ilova qayta ochilganda xuddi shu
    joydan (bo'limlar ekranidan) davom etadi. Agar filial yoki
    chek-list turi AVVALGISIDAN FARQLI bo'lsa, eski qoralamadagi
    rasmlar endi mos kelmay qoladi — shuning uchun bunday holatda
    avvalgi rasmlar tozalanadi (yangi hisobot boshlanganda eski
    filialning rasmlari aralashib ketmasin)."""
    pool = await get_pool()
    existing = await get_or_create_draft(telegram_user_id)
    changed = (existing["filial_id"] != filial_id) or (existing["checklist_type_id"] != checklist_type_id)
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """
                UPDATE drafts SET filial_id = $2, checklist_type_id = $3, lang = $4, updated_at = now()
                WHERE telegram_user_id = $1
                RETURNING id, telegram_user_id, filial_id, checklist_type_id, lang, updated_at
                """,
                telegram_user_id, filial_id, checklist_type_id, lang,
            )
            if changed:
                await conn.execute("DELETE FROM draft_photos WHERE draft_id = $1", row["id"])
    return dict(row)


async def add_draft_photo(telegram_user_id: int, section_id: int, comment: Optional[str],
                           filename: str, content_type: str, telegram_file_id: str,
                           telegram_message_id: Optional[int] = None) -> dict:
    """E'TIBOR: rasmning bayti (photo_data) endi bu yerga YOZILMAYDI —
    rasm allaqachon Telegramga (xodimning shaxsiy chatiga, zaxira sifatida)
    yuborilgan va uning `telegram_file_id`si shu yerda saqlanadi. Shu
    tufayli Postgres hech qachon rasm baytlari bilan to'lib qolmaydi.
    `telegram_message_id` esa shu xabarni keyinchalik (kerak bo'lmay
    qolganda) chatdan o'chirib tashlash uchun saqlanadi."""
    pool = await get_pool()
    draft = await get_or_create_draft(telegram_user_id)
    row = await pool.fetchrow(
        """
        INSERT INTO draft_photos (draft_id, section_id, comment, filename, content_type, telegram_file_id, telegram_message_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING id, draft_id, section_id, comment, filename, content_type, created_at
        """,
        draft["id"], section_id, comment, filename, content_type, telegram_file_id, telegram_message_id,
    )
    await pool.execute("UPDATE drafts SET updated_at = now() WHERE id = $1", draft["id"])
    return dict(row)


async def list_draft_photos(telegram_user_id: int) -> list[dict]:
    """Qoralamadagi rasmlar ro'yxati — rasm BAYTLARISIZ (faqat metadata),
    ilova ochilganda tez yuklash uchun. Rasmning o'zi kerak bo'lsa
    (masalan preview yoki yakuniy yuborish uchun) get_draft_photo
    ishlatiladi."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT dp.id, dp.section_id, dp.comment, dp.filename, dp.created_at
        FROM draft_photos dp
        JOIN drafts d ON d.id = dp.draft_id
        WHERE d.telegram_user_id = $1
        ORDER BY dp.id
        """,
        telegram_user_id,
    )
    return [dict(r) for r in rows]


async def get_draft_photo(photo_id: int, telegram_user_id: int) -> Optional[dict]:
    """Egalikni ham tekshiradi — boshqa xodim boshqasining rasmini
    (hatto id'sini bilib olsa ham) ko'ra/o'chira olmasligi uchun.

    `telegram_file_id` bo'lsa — rasm Telegramda saqlangan (yangi holat).
    `photo_data` bo'lsa — bu ESKI (migratsiyadan oldingi) qator, hali
    bazada baytlari bilan turibdi; orqaga moslik uchun ikkalasi ham
    qaytariladi, chaqiruvchi kerakligini tanlaydi."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT dp.id, dp.draft_id, dp.section_id, dp.comment, dp.filename, dp.content_type,
               dp.telegram_file_id, dp.telegram_message_id, dp.photo_data
        FROM draft_photos dp
        JOIN drafts d ON d.id = dp.draft_id
        WHERE dp.id = $1 AND d.telegram_user_id = $2
        """,
        photo_id, telegram_user_id,
    )
    return dict(row) if row else None


async def update_draft_photo_comment(photo_id: int, telegram_user_id: int, comment: Optional[str]) -> bool:
    pool = await get_pool()
    result = await pool.execute(
        """
        UPDATE draft_photos SET comment = $3
        WHERE id = $1 AND draft_id IN (SELECT id FROM drafts WHERE telegram_user_id = $2)
        """,
        photo_id, telegram_user_id, comment,
    )
    changed = result.endswith(" 1")
    if changed:
        # 15 daqiqalik TTL juda qisqa bo'lgani uchun, xodim faol ishlab
        # turgan bo'lsa (garchi yangi rasm qo'shmasa ham — masalan faqat
        # izohni tahrirlasa) qoralama vaqti hisobi qayta boshlanishi kerak.
        await pool.execute(
            "UPDATE drafts SET updated_at = now() WHERE telegram_user_id = $1", telegram_user_id
        )
    return changed


async def delete_draft_photo(photo_id: int, telegram_user_id: int) -> Optional[dict]:
    """O'chirilgan qator haqida ma'lumot (jumladan `telegram_user_id` va
    `telegram_message_id`) qaytaradi — shu tufayli chaqiruvchi (app.py)
    xodimning shaxsiy chatidagi mos zaxira xabarini ham o'chira oladi."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        DELETE FROM draft_photos
        WHERE id = $1 AND draft_id IN (SELECT id FROM drafts WHERE telegram_user_id = $2)
        RETURNING telegram_message_id
        """,
        photo_id, telegram_user_id,
    )
    if row:
        await pool.execute(
            "UPDATE drafts SET updated_at = now() WHERE telegram_user_id = $1", telegram_user_id
        )
        return {"telegram_user_id": telegram_user_id, "telegram_message_id": row["telegram_message_id"]}
    return None


async def clear_draft(telegram_user_id: int) -> None:
    """Qoralamani (va unga tegishli barcha rasmlarni, CASCADE orqali)
    butunlay o'chiradi — hisobot muvaffaqiyatli yuborilgandan keyin
    yoki xodim "boshidan boshlash"ni tanlaganda chaqiriladi."""
    pool = await get_pool()
    await pool.execute("DELETE FROM drafts WHERE telegram_user_id = $1", telegram_user_id)


async def get_stale_draft_photo_messages(max_age_minutes: int = 15) -> list[dict]:
    """cleanup_stale_drafts BOSHLANISHIDAN OLDIN chaqiriladi — o'chirilishi
    kutilayotgan qoralamalarning zaxira xabarlari ro'yxatini (kimga,
    qaysi message_id) qaytaradi, shunda ularni keyin Telegramdan ham
    (xodimning shaxsiy chatidan) o'chirish mumkin bo'ladi."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT dp.telegram_message_id, d.telegram_user_id
        FROM draft_photos dp
        JOIN drafts d ON d.id = dp.draft_id
        WHERE d.updated_at < now() - ($1 || ' minutes')::interval
          AND dp.telegram_message_id IS NOT NULL
        """,
        str(max_age_minutes),
    )
    return [dict(r) for r in rows]


async def stale_drafts_to_deletion_queue(max_age_minutes: int) -> int:
    """Eskirgan qoralamalarning zaxira nusxa xabarlarini O'CHIRISH NAVBATIGA
    ko'chiradi va qoralamalarni o'chiradi — ikkalasi ham BITTA tranzaksiyada.

    TUZATILDI: ilgari bu ikki qadam alohida edi — avval xabarlar ro'yxati
    olinardi, keyin qoralamalar bazadan o'chirilardi, so'ng xabarlar
    ketma-ket Telegramdan o'chirilardi. Agar shu oxirgi bosqichda xato
    bo'lsa (masalan flood-control), bazadagi yozuv allaqachon yo'q edi —
    ya'ni qaysi xabarni o'chirish kerakligi haqidagi ma'lumot butunlay
    yo'qolardi va zaxira nusxa xodimning chatida abadiy qolardi.
    Endi xabarlar avval doimiy navbatga yoziladi, shuning uchun hech
    qanday holatda yo'qolmaydi."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO pending_deletions (chat_id, message_id)
                SELECT d.telegram_user_id, dp.telegram_message_id
                FROM draft_photos dp
                JOIN drafts d ON d.id = dp.draft_id
                WHERE d.updated_at < now() - ($1 || ' minutes')::interval
                  AND dp.telegram_message_id IS NOT NULL
                ON CONFLICT (chat_id, message_id) DO NOTHING
                """,
                str(max_age_minutes),
            )
            rows = await conn.fetch(
                "DELETE FROM drafts WHERE updated_at < now() - ($1 || ' minutes')::interval RETURNING id",
                str(max_age_minutes),
            )
    return len(rows)


# ---------- Zaxira nusxalarni o'chirish navbati ----------

async def enqueue_deletion(chat_id: int, message_id: int) -> None:
    """Zaxira nusxa xabarini o'chirish navbatiga qo'yadi. Worker uni
    bajarilgunicha qayta uradi — shuning uchun 429/tarmoq xatosi tufayli
    hech qachon yo'qolmaydi."""
    if not chat_id or not message_id:
        return
    pool = await get_pool()
    await pool.execute(
        "INSERT INTO pending_deletions (chat_id, message_id) VALUES ($1, $2) "
        "ON CONFLICT (chat_id, message_id) DO NOTHING",
        chat_id, message_id,
    )


async def enqueue_deletions(items: list[tuple]) -> None:
    if not items:
        return
    pool = await get_pool()
    await pool.executemany(
        "INSERT INTO pending_deletions (chat_id, message_id) VALUES ($1, $2) "
        "ON CONFLICT (chat_id, message_id) DO NOTHING",
        [(c, m) for c, m in items if c and m],
    )


async def take_due_deletions(limit: int = 20) -> list[dict]:
    """Vaqti kelgan o'chirishlarni oladi va darhol keyingi urinish vaqtini
    surib qo'yadi — shu bilan bir necha worker bir xil yozuvni olmaydi."""
    pool = await get_pool()
    rows = await pool.fetch(
        """
        UPDATE pending_deletions SET
            attempts = attempts + 1,
            next_attempt_at = now() + (least(300, 15 * power(2, least(attempts, 5)))::int || ' seconds')::interval
        WHERE id IN (
            SELECT id FROM pending_deletions
            WHERE next_attempt_at <= now()
            ORDER BY next_attempt_at, id
            LIMIT $1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, chat_id, message_id, attempts
        """,
        limit,
    )
    return [dict(r) for r in rows]


async def finish_deletion(deletion_id: int) -> None:
    pool = await get_pool()
    await pool.execute("DELETE FROM pending_deletions WHERE id = $1", deletion_id)


async def drop_exhausted_deletions(max_attempts: int = 8) -> int:
    """Juda ko'p urinishdan keyin ham o'chirilmagan yozuvlarni tashlaymiz
    (masalan xodim botni bloklab qo'ygan) — navbat cheksiz o'smasin."""
    pool = await get_pool()
    rows = await pool.fetch(
        "DELETE FROM pending_deletions WHERE attempts >= $1 RETURNING id", max_attempts
    )
    return len(rows)


async def cleanup_stale_drafts(max_age_minutes: int = 15) -> int:
    """XODIM TASHLAB QO'YGAN (uzoq vaqt davomida hech narsa qo'shmagan/
    yangilamagan) qoralamalarni avtomatik o'chiradi — CASCADE orqali
    ularning draft_photos qatorlari (va, agar bo'lsa, eski bayt
    ma'lumotlari) ham birga o'chadi. Shu fon vazifasi bo'lmasa, hech
    qachon yuborilmagan/tugallanmagan qoralamalar bazada abadiy qolib,
    Postgres hajmini asta-sekin to'ldirib boraveradi.

    15 daqiqa — shu muddatdan ortiq "tegilmagan" (yangi rasm qo'shilmagan/
    yangilanmagan) qoralama avtomatik o'chiriladi."""
    pool = await get_pool()
    rows = await pool.fetch(
        "DELETE FROM drafts WHERE updated_at < now() - ($1 || ' minutes')::interval RETURNING id",
        str(max_age_minutes),
    )
    return len(rows)


# ============================================================
#  YETKAZISH NAVBATI (outbox)
#
#  "Yuborish" bosilganda hisobot Telegramga DARHOL emas, shu navbatga
#  yoziladi. Fon worker'i uni Telegram cheklovini hurmat qilgan holda
#  bo'shatadi. Shu tufayli:
#    - xodim kutmaydi (javob ~0.2 soniyada keladi);
#    - band paytda ham hech qanday xato ko'rmaydi;
#    - server qayta ishga tushsa ham navbat bazada saqlanib qoladi.
# ============================================================

async def enqueue_outbox(conn, submission_id: int, telegram_user_id: int, filial_id: Optional[int],
                          filial_name: str, section_id: int, seq: int, caption: str,
                          photos: list[dict]) -> None:
    import json as _json
    await conn.execute(
        """
        INSERT INTO outbox (submission_id, telegram_user_id, filial_id, filial_name,
                            section_id, seq, caption, photos)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
        """,
        submission_id, telegram_user_id, filial_id, filial_name,
        section_id, seq, caption, _json.dumps(photos),
    )


async def take_next_outbox() -> Optional[dict]:
    """Navbatdagi keyingi yozuvni oladi (eng eski birinchi) va uni
    boshqa worker olib qo'ymasligi uchun darhol band qiladi.
    FOR UPDATE SKIP LOCKED — bir nechta replika bo'lsa ham xavfsiz."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        UPDATE outbox SET attempts = attempts + 1
        WHERE id = (
            SELECT id FROM outbox
            WHERE status = 'pending' AND next_attempt_at <= now()
            ORDER BY next_attempt_at, id
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        )
        RETURNING id, submission_id, telegram_user_id, filial_id, filial_name,
                  section_id, seq, caption, photos, attempts
        """,
    )
    return dict(row) if row else None


async def mark_outbox_sent(outbox_id: int) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE outbox SET status = 'sent', sent_at = now(), last_error = NULL WHERE id = $1",
        outbox_id,
    )


async def reschedule_outbox(outbox_id: int, delay_seconds: float, error: str) -> None:
    """Vaqtinchalik xato — keyinroq qayta uriniladi (hisobot yo'qolmaydi)."""
    pool = await get_pool()
    await pool.execute(
        "UPDATE outbox SET next_attempt_at = now() + ($2 || ' seconds')::interval, "
        "last_error = $3 WHERE id = $1",
        outbox_id, str(int(max(1, delay_seconds))), (error or "")[:500],
    )


async def mark_outbox_failed(outbox_id: int, error: str) -> None:
    pool = await get_pool()
    await pool.execute(
        "UPDATE outbox SET status = 'failed', last_error = $2 WHERE id = $1",
        outbox_id, (error or "")[:500],
    )


async def submission_delivery_state(submission_id: int) -> dict:
    """Hisobotning barcha bo'limlari yetkazildimi — shuni aniqlaydi."""
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        SELECT count(*) FILTER (WHERE status = 'pending') AS pending,
               count(*) FILTER (WHERE status = 'failed')  AS failed,
               count(*) FILTER (WHERE status = 'sent')    AS sent,
               count(*) AS total
        FROM outbox WHERE submission_id = $1
        """,
        submission_id,
    )
    return dict(row) if row else {"pending": 0, "failed": 0, "sent": 0, "total": 0}


async def set_submission_delivery(submission_id: int, status: str) -> bool:
    """Holatni belgilaydi. True qaytsa — shu chaqiruv birinchi bo'lib
    o'zgartirdi (xodimga xabar faqat bir marta yuborilishi uchun)."""
    pool = await get_pool()
    row = await pool.fetchrow(
        "UPDATE submissions SET delivery_status = $2, notified_at = now() "
        "WHERE id = $1 AND delivery_status <> $2 RETURNING id",
        submission_id, status,
    )
    return row is not None


async def outbox_stats() -> dict:
    pool = await get_pool()
    row = await pool.fetchrow(
        "SELECT count(*) FILTER (WHERE status='pending') pending, "
        "       count(*) FILTER (WHERE status='failed') failed, "
        "       (SELECT count(*) FROM pending_deletions) deletions FROM outbox"
    )
    return dict(row)


async def purge_old_outbox(days: int = 7) -> int:
    pool = await get_pool()
    rows = await pool.fetch(
        "DELETE FROM outbox WHERE status = 'sent' AND sent_at < now() - ($1 || ' days')::interval "
        "RETURNING id", str(days),
    )
    return len(rows)


# ============================================================
#  VALIDATSIYA VA POYGA HIMOYASI
# ============================================================

async def section_belongs_to(section_id: int, checklist_type_id: Optional[int]) -> bool:
    """Bo'lim mavjudmi va (berilgan bo'lsa) shu smena turiga tegishlimi.

    Ilgari bu tekshiruv umuman yo'q edi: istalgan son `section_id`
    sifatida qabul qilinardi. Mavjud bo'lmagan ID "zaharlangan qoralama"
    hosil qilardi, boshqa smenaning ID'si esa hisobotda noto'g'ri bo'lim
    nomi chiqishiga olib kelardi."""
    pool = await get_pool()
    if checklist_type_id is None:
        row = await pool.fetchrow(
            "SELECT 1 FROM sections WHERE id = $1 AND is_active = TRUE", section_id)
    else:
        row = await pool.fetchrow(
            "SELECT 1 FROM sections WHERE id = $1 AND checklist_type_id = $2 AND is_active = TRUE",
            section_id, checklist_type_id)
    return row is not None


async def section_name_exists(checklist_type_id: int, name: str,
                               exclude_id: Optional[int] = None) -> bool:
    """Shu smena turida bir xil nomli bo'lim bormi.

    BLOKER himoyasi: ilgari takroriy nom bemalol qo'shilardi va KEYINGI
    restartda ilova butunlay ishga tushmay qolardi. Endi admin darhol
    tushunarli xato oladi."""
    pool = await get_pool()
    if exclude_id is None:
        row = await pool.fetchrow(
            "SELECT 1 FROM sections WHERE checklist_type_id = $1 "
            "AND lower(trim(name)) = lower(trim($2))",
            checklist_type_id, name)
    else:
        row = await pool.fetchrow(
            "SELECT 1 FROM sections WHERE checklist_type_id = $1 "
            "AND lower(trim(name)) = lower(trim($2)) AND id <> $3",
            checklist_type_id, name, exclude_id)
    return row is not None


async def get_section_checklist_type(section_id: int) -> Optional[int]:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT checklist_type_id FROM sections WHERE id = $1", section_id)
    return row["checklist_type_id"] if row else None


async def count_superadmins() -> int:
    pool = await get_pool()
    row = await pool.fetchrow("SELECT count(*) c FROM allowed_users WHERE is_superadmin = TRUE")
    return row["c"]


# ESLATMA: bu yerda ilgari `advisory_lock` kontekst-menejeri bor edi.
# U pool'dan ulanish olib, tranzaksiyani ochiq holda ushlab turardi —
# ichkarida esa yana pool'dan ulanish so'ralardi. 10 ta parallel yuborishda
# bu butun pool'ni qulflab, ilovani qotirib qo'yardi (o'lchov: 10 xodimdan
# 8 tasi ReadTimeout). Uning o'rniga `lock_draft_for_submit` /
# `claim_thread_slot` ishlatiladi — ular BITTA ulanishda `SELECT ... FOR
# UPDATE` bilan ishlaydi va qo'shimcha ulanish talab qilmaydi.


# ============================================================
#  BITTA ULANISHDA ISHLAYDIGAN VARIANTLAR (submit uchun)
#
#  MUHIM: `submit` butun kritik bo'limni BITTA ulanish va BITTA
#  tranzaksiyada bajaradi. Sabab — pool tugab qolishining oldini olish:
#  agar tranzaksiya ochiq turganda ichkarida pool'dan YANA ulanish
#  so'ralsa, 10 ta parallel yuborishda 10 ta ulanish qulfda ushlanib,
#  hech biri ikkinchisini ololmay, butun ilova qotib qoladi (deadlock).
#  Shuning uchun quyidagi funksiyalar tayyor `conn` ni qabul qiladi.
# ============================================================

async def lock_draft_for_submit(conn, telegram_user_id: int) -> Optional[dict]:
    """Qoralama qatorini SELECT ... FOR UPDATE bilan qulflaydi.

    Shu bilan bir vaqtda kelgan ikkinchi "Yuborish" so'rovi birinchisi
    tugagunicha kutadi va keyin qoralamani topa olmaydi (chunki u
    o'chirilgan bo'ladi) — natijada guruhga dublikat hisobot tushmaydi.
    Bu advisory lock'dan afzal: qo'shimcha ulanish talab qilmaydi va
    bir nechta replikada ham to'g'ri ishlaydi."""
    row = await conn.fetchrow(
        "SELECT id, telegram_user_id, filial_id, checklist_type_id, lang "
        "FROM drafts WHERE telegram_user_id = $1 FOR UPDATE",
        telegram_user_id,
    )
    return dict(row) if row else None


async def list_draft_photos_conn(conn, draft_id: int) -> list[dict]:
    rows = await conn.fetch(
        "SELECT id, section_id, comment, filename, telegram_file_id, telegram_message_id "
        "FROM draft_photos WHERE draft_id = $1 ORDER BY id",
        draft_id,
    )
    return [dict(r) for r in rows]


async def get_section_conn(conn, section_id: int, lang: str = "uz") -> Optional[dict]:
    row = await conn.fetchrow(
        "SELECT id, name_uz, name_ru, name_en FROM sections WHERE id = $1", section_id)
    if not row:
        return None
    d = dict(row)
    d["name"] = _localized_name(d, lang)
    return d


async def hidden_section_ids_conn(conn, filial_id: int, section_ids: list[int]) -> set:
    """Bitta so'rovda — ilgari har bir bo'lim uchun alohida so'rov ketardi (N+1)."""
    if not section_ids:
        return set()
    rows = await conn.fetch(
        "SELECT section_id FROM filial_section_hidden "
        "WHERE filial_id = $1 AND section_id = ANY($2::int[])",
        filial_id, section_ids,
    )
    return {r["section_id"] for r in rows}


async def create_submission_conn(conn, filial_id: int, filial_name: str, telegram_user_id: int,
                                  full_name: str, checklist_type_id, checklist_type_name) -> int:
    row = await conn.fetchrow(
        """
        INSERT INTO submissions (filial_id, filial_name_snapshot, telegram_user_id, full_name,
                                 checklist_type_id, checklist_type_name_snapshot)
        VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """,
        filial_id, filial_name, telegram_user_id, full_name, checklist_type_id, checklist_type_name,
    )
    return row["id"]


async def delete_draft_conn(conn, draft_id: int) -> None:
    await conn.execute("DELETE FROM drafts WHERE id = $1", draft_id)


async def get_filial_conn(conn, filial_id: int) -> Optional[dict]:
    row = await conn.fetchrow("SELECT id, name, thread_id FROM filials WHERE id = $1", filial_id)
    return dict(row) if row else None


async def claim_thread_slot(conn, filial_id: int) -> Optional[dict]:
    """Filial qatorini qulflab, joriy thread_id ni qaytaradi — topic
    yaratish poygasini to'xtatish uchun (bitta ulanishda)."""
    row = await conn.fetchrow(
        "SELECT id, name, thread_id FROM filials WHERE id = $1 FOR UPDATE", filial_id)
    return dict(row) if row else None


async def set_thread_id_conn(conn, filial_id: int, thread_id: int) -> None:
    await conn.execute("UPDATE filials SET thread_id = $1 WHERE id = $2", thread_id, filial_id)
