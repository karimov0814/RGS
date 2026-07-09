"""
PostgreSQL bilan ishlash uchun yordamchi qatlam (asyncpg asosida).
"""
import os
import asyncpg
from typing import Optional

DATABASE_URL = os.environ["DATABASE_URL"]  # masalan: postgresql://user:pass@localhost:5432/feedback

_pool: Optional[asyncpg.Pool] = None


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


# ---------- Bo'limlar ----------

async def list_active_sections():
    pool = await get_pool()
    rows = await pool.fetch(
        "SELECT id, name FROM sections WHERE is_active = TRUE ORDER BY sort_order, id"
    )
    return [dict(r) for r in rows]


# ---------- Submissionlar ----------

async def create_submission(filial_id: int, filial_name: str, telegram_user_id: int, full_name: str) -> int:
    pool = await get_pool()
    row = await pool.fetchrow(
        """
        INSERT INTO submissions (filial_id, filial_name_snapshot, telegram_user_id, full_name)
        VALUES ($1, $2, $3, $4) RETURNING id
        """,
        filial_id, filial_name, telegram_user_id, full_name,
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
