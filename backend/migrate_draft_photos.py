"""
BIR MARTALIK migratsiya skripti.

Vazifasi: `draft_photos` jadvalidagi ESKI qatorlarda (yangi
`telegram_file_id` ustuni qo'shilishidan OLDIN yaratilgan, hali xom
bayt — `photo_data` — saqlab turgan yozuvlarda) rasmlarni Telegramga
(egasining botga shaxsiy chatiga, zaxira sifatida) yuboradi, qaytgan
`telegram_file_id`ni bazaga yozadi, so'ng `photo_data`ni NULL qiladi —
shu tufayli Postgres hajmi (Railway volume) bo'shaydi.

Ishlatish (Railway CLI orqali, backend papkasida):
    railway run python migrate_draft_photos.py

Yoki lokal/serverda to'g'ridan-to'g'ri:
    python migrate_draft_photos.py

Xavfsiz: faqat `photo_data IS NOT NULL AND telegram_file_id IS NULL`
bo'lgan qatorlarni qayta ishlaydi, xodimning joriy (tugallanmagan)
ishiga tegmaydi — aksincha, uni yo'qotmasdan, faqat saqlash usulini
o'zgartiradi. Bir necha marta ishga tushirilsa ham xavfsiz (idempotent):
allaqachon ko'chirilgan qatorlarni qayta ko'rmaydi.

Oxirida, haqiqatan ham disk joyi bo'shashi uchun (Postgres NULL qilish
o'zi darhol faylni "siqmaydi"), quyidagini BIR MARTA psql'da ishga
tushirish tavsiya etiladi:
    VACUUM FULL draft_photos;
(Diqqat: VACUUM FULL jadvalni vaqtincha qulflaydi — shu sabab kam
yuklama vaqtida, masalan tunda, bajarish tavsiya etiladi.)
"""
import asyncio
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import db
import telegram_utils as tg


async def main():
    pool = await db.get_pool()

    rows = await pool.fetch(
        """
        SELECT dp.id, dp.filename, dp.photo_data, d.telegram_user_id
        FROM draft_photos dp
        JOIN drafts d ON d.id = dp.draft_id
        WHERE dp.photo_data IS NOT NULL AND dp.telegram_file_id IS NULL
        ORDER BY dp.id
        """
    )

    print(f"Ko'chirilishi kerak bo'lgan eski qatorlar: {len(rows)} ta")

    ok, failed = 0, 0
    for row in rows:
        try:
            sent = await tg.send_draft_photo_to_owner(
                row["telegram_user_id"], row["photo_data"], row["filename"] or "photo.jpg"
            )
            await pool.execute(
                "UPDATE draft_photos SET telegram_file_id = $2, telegram_message_id = $3, photo_data = NULL WHERE id = $1",
                row["id"], sent["file_id"], sent["message_id"],
            )
            ok += 1
            print(f"  #{row['id']} -> OK (file_id saqlandi, bayt tozalandi)")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  #{row['id']} -> XATOLIK: {e}")

    print(f"\nTugadi. Muvaffaqiyatli: {ok}, xatolik: {failed}")
    if ok:
        print(
            "\nEslatma: bazadagi haqiqiy disk joyini bo'shatish uchun "
            "psql'da BIR MARTA quyidagini ishga tushiring (kam yuklama "
            "vaqtida):\n    VACUUM FULL draft_photos;"
        )

    await db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
