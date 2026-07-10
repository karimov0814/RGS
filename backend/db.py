"""
PostgreSQL bilan ishlash uchun yordamchi qatlam (asyncpg asosida).
"""
import os
import asyncpg
from typing import Optional

DATABASE_URL = os.environ["DATABASE_URL"]  # masalan: postgresql://user:pass@localhost:5432/feedback

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
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
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
