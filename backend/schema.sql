-- ============================================================
--  Filial Feedback Mini App — PostgreSQL sxemasi
-- ============================================================

-- ============================================================
--  Bir martalik migratsiyalarni kuzatish uchun jadval.
--  MUHIM: schema.sql backend har ishga tushganda (Railway restart/deploy)
--  to'liq qayta bajariladi. Agar quyidagi "bo'lim/filiallarni qattiq
--  ro'yxat bilan cheklash" migratsiyalari HAR safar ishlab tursa, u holda
--  admin panel orqali qilingan har qanday o'zgarish (yangi filial qo'shish,
--  filial o'chirish/tahrirlash) keyingi restart'da bekor qilinib qo'yardi.
--  Shu sabab bunday migratsiyalar shu jadval yordamida FAQAT BIR MARTA
--  ishlaydi.
-- ============================================================
CREATE TABLE IF NOT EXISTS schema_migrations (
    id          TEXT PRIMARY KEY,
    applied_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- ============================================================
--  Ruxsat etilgan foydalanuvchilar (whitelist)
--  Faqat shu jadvalda mavjud telegram_user_id lar mini app'dan
--  foydalana oladi. is_superadmin = TRUE bo'lganlar admin panelga
--  kira oladi (user/filial qo'shish, o'chirish, tahrirlash).
-- ============================================================
CREATE TABLE IF NOT EXISTS allowed_users (
    id                SERIAL PRIMARY KEY,
    telegram_user_id  BIGINT NOT NULL UNIQUE,
    full_name         TEXT,
    is_superadmin     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at        TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS filials (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,     -- "Chilonzor filiali"
    thread_id   INTEGER,                  -- Telegram guruhdagi forum-topic id (avtomatik to'ldiriladi)
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

-- Eski bazalarda `sort_order` ustuni bo'lmasligi mumkin (CREATE TABLE IF NOT
-- EXISTS mavjud jadvalni o'zgartirmaydi) — shu bilan xavfsiz qo'shamiz.
ALTER TABLE filials ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS sections (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,            -- "Oshxona", "Zal", "Ombor" ...
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS submissions (
    id                SERIAL PRIMARY KEY,
    filial_id         INTEGER NOT NULL REFERENCES filials(id),
    telegram_user_id  BIGINT NOT NULL,
    full_name         TEXT,
    created_at        TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS submission_photos (
    id                 SERIAL PRIMARY KEY,
    submission_id      INTEGER NOT NULL REFERENCES submissions(id) ON DELETE CASCADE,
    section_id         INTEGER NOT NULL REFERENCES sections(id),
    telegram_file_id   TEXT,
    comment            TEXT,
    sent_message_id    BIGINT,   -- guruhga yuborilgan xabar id (kuzatuv uchun)
    created_at         TIMESTAMP NOT NULL DEFAULT now()
);

-- ============================================================
--  Eski "rol" tizimidan qolgan ustun/jadvallarni tozalash
--  (CREATE TABLE IF NOT EXISTS mavjud jadvalni o'zgartirmaydi,
--   shuning uchun eski bazalarda role/phone hali ham qolgan bo'lishi
--   mumkin edi — shu DROP'lar uni xavfsiz olib tashlaydi)
-- ============================================================
ALTER TABLE submissions DROP COLUMN IF EXISTS role;
ALTER TABLE submissions DROP COLUMN IF EXISTS phone;
DROP TABLE IF EXISTS user_contacts;

-- ============================================================
--  Bo'limlar: takroriy nomlarni bir martalik tozalash + UNIQUE indeks
--  (bu qism har safar xavfsiz qayta ishlashi mumkin — faqat takrorlarni
--  birlashtiradi, mavjud is_active holatini o'zgartirmaydi)
-- ============================================================

-- 1) Avval `name` ustida UNIQUE cheklov bo'lmagani uchun, oldingi
--    deploylarda bir xil nomli takroriy qatorlar paydo bo'lgan bo'lishi
--    mumkin. Har bir nom uchun eng kichik id qoldiriladi, takroriy
--    qatorlarga bog'langan rasmlar (agar bo'lsa) shu idga ko'chiriladi.
WITH ranked AS (
    SELECT id, name,
           ROW_NUMBER() OVER (PARTITION BY name ORDER BY id) AS rn,
           FIRST_VALUE(id) OVER (PARTITION BY name ORDER BY id) AS keep_id
    FROM sections
),
to_merge AS (
    SELECT id, keep_id FROM ranked WHERE rn > 1
)
UPDATE submission_photos sp
SET section_id = tm.keep_id
FROM to_merge tm
WHERE sp.section_id = tm.id;

DELETE FROM sections s
USING (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY name ORDER BY id) AS rn
    FROM sections
) ranked
WHERE s.id = ranked.id AND ranked.rn > 1;

-- 2) Endi nomlar noyob bo'lishini doimiy ta'minlaymiz (kelajakda ham
--    takroriy qator qo'shilmasligi uchun)
CREATE UNIQUE INDEX IF NOT EXISTS sections_name_unique ON sections(name);

-- ============================================================
--  Bo'limlarni boshlang'ich 8 ta ro'yxat bilan to'ldirish
--  — FAQAT BIR MARTA ishlaydi (schema_migrations orqali qulflangan),
--  shunda keyinchalik bazada qilingan har qanday o'zgarish (masalan,
--  kelajakda bo'limlar uchun ham admin panel qo'shilsa) restart'da
--  bekor qilinmaydi.
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE id = 'seed_sections_v1') THEN
        UPDATE sections SET is_active = FALSE
        WHERE name NOT IN (
            'Фото внешней территории и фасада',
            'Фото зала и туалетов',
            'Фото прилавка',
            'Фото кухни (1. Станция пиццы, 2. Станция Вок, 3. Станция сборки бургеров и роллов, 4. Панировочная станция, 5. Станция фри, 6. Станция мойки и моповые зоны)',
            'Фото служебного помещения',
            'Фото доставочных помещений',
            'Фото сотрудников после пятиминутки и командной доски (только утром)',
            'Фото чек-листов: Чек-лист Чистоты, Чек-лист МС, КЛН, Бланк уборки ГСУ (11:00, 15:00, 18:00, 21:00, Закрытие смены)'
        );

        INSERT INTO sections (name, sort_order, is_active) VALUES
            ('Фото внешней территории и фасада', 1, TRUE),
            ('Фото зала и туалетов', 2, TRUE),
            ('Фото прилавка', 3, TRUE),
            ('Фото кухни (1. Станция пиццы, 2. Станция Вок, 3. Станция сборки бургеров и роллов, 4. Панировочная станция, 5. Станция фри, 6. Станция мойки и моповые зоны)', 4, TRUE),
            ('Фото служебного помещения', 5, TRUE),
            ('Фото доставочных помещений', 6, TRUE),
            ('Фото сотрудников после пятиминутки и командной доски (только утром)', 7, TRUE),
            ('Фото чек-листов: Чек-лист Чистоты, Чек-лист МС, КЛН, Бланк уборки ГСУ (11:00, 15:00, 18:00, 21:00, Закрытие смены)', 8, TRUE)
        ON CONFLICT (name) DO UPDATE SET sort_order = EXCLUDED.sort_order, is_active = TRUE;

        INSERT INTO schema_migrations (id) VALUES ('seed_sections_v1');
    END IF;
END $$;

-- ============================================================
--  Filiallarni boshlang'ich 17 ta ro'yxat bilan to'ldirish
--  — FAQAT BIR MARTA ishlaydi (schema_migrations orqali qulflangan).
--  Aynan shu joy avvalgi bug'ning manbai edi: bu bloklar himoyasiz
--  holda HAR safar ishga tushganda qayta bajarilardi va natijada
--  superadmin admin panel orqali o'chirgan (faolsizlantirgan) yoki
--  qo'shgan filiallar keyingi backend restart'ida avtomatik bekor
--  qilinib qo'yardi ("o'chirish to'liq ishlamayapti" muammosi shundan
--  edi). Endi bu migratsiya faqat bazada birinchi marta ishga
--  tushganda amalga oshadi, keyinchalik admin panel orqali qilingan
--  o'zgarishlarga tegilmaydi.
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE id = 'seed_filials_v1') THEN
        UPDATE filials SET is_active = FALSE
        WHERE name NOT IN (
            'Scopus Mall', 'City Mall', 'Alfraganus', 'Beruniy', 'Novza', 'Anhor',
            'Sergeli', 'Tuzel', 'Compass Mall', 'Navruz Mall', 'Samarqand Darvoza',
            'C1 Street', 'C1 Wok', 'Eco', 'Yunusabad Gallery', 'Glinka Wok', 'Chilonzor 20'
        );

        INSERT INTO filials (name, sort_order, is_active) VALUES
            ('Scopus Mall', 1, TRUE),
            ('City Mall', 2, TRUE),
            ('Alfraganus', 3, TRUE),
            ('Beruniy', 4, TRUE),
            ('Novza', 5, TRUE),
            ('Anhor', 6, TRUE),
            ('Sergeli', 7, TRUE),
            ('Tuzel', 8, TRUE),
            ('Compass Mall', 9, TRUE),
            ('Navruz Mall', 10, TRUE),
            ('Samarqand Darvoza', 11, TRUE),
            ('C1 Street', 12, TRUE),
            ('C1 Wok', 13, TRUE),
            ('Eco', 14, TRUE),
            ('Yunusabad Gallery', 15, TRUE),
            ('Glinka Wok', 16, TRUE),
            ('Chilonzor 20', 17, TRUE)
        ON CONFLICT (name) DO UPDATE SET sort_order = EXCLUDED.sort_order, is_active = TRUE;

        INSERT INTO schema_migrations (id) VALUES ('seed_filials_v1');
    END IF;
END $$;

-- ============================================================
--  Filialni SUPERADMIN "o'chirish" tugmasi orqali ENDI TO'LIQ
--  o'chirib tashlash mumkin (avval faqat is_active=FALSE qilib
--  "nofaol" holatda qolib ketardi). Buning uchun:
--    1) submissions.filial_id NOT NULL bo'lishi shart emas —
--       filial o'chirilganda eski hisobotlar saqlanib qoladi,
--       faqat filial_id NULL bo'lib qoladi (FK: ON DELETE SET NULL).
--    2) Filial nomi submissions.filial_name_snapshot ustunida
--       "suratga olingan holda" saqlanadi, shunda filial o'chirilgan
--       taqdirda ham eski hisobotlarda qaysi filialga tegishli
--       ekani ko'rinib turadi.
--  Bu bloklar xavfsiz tarzda har safar qayta ishlashi mumkin
--  (idempotent), shuning uchun schema_migrations orqali qulflanmagan.
-- ============================================================
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS filial_name_snapshot TEXT;

ALTER TABLE submissions ALTER COLUMN filial_id DROP NOT NULL;

ALTER TABLE submissions DROP CONSTRAINT IF EXISTS submissions_filial_id_fkey;
ALTER TABLE submissions
    ADD CONSTRAINT submissions_filial_id_fkey
    FOREIGN KEY (filial_id) REFERENCES filials(id) ON DELETE SET NULL;

-- Eski qatorlarda filial_name_snapshot bo'sh bo'lsa, hozirgi filial
-- nomidan bir martalik to'ldiramiz (faqat hali to'ldirilmagan joyda).
UPDATE submissions s
SET filial_name_snapshot = f.name
FROM filials f
WHERE s.filial_id = f.id AND s.filial_name_snapshot IS NULL;

-- ============================================================
--  CHEK-LIST TURLARI (Smena ochilishi / topshirilishi / yopilishi)
-- ============================================================
--  Filial tanlangandan keyin foydalanuvchi shu 3 turdan birini tanlaydi.
--  Har bir tur o'zining mustaqil bo'limlar (sections) ro'yxatiga ega —
--  admin panel orqali har bir tur uchun alohida boshqariladi. `key`
--  ustuni doimiy/o'zgarmas identifikator (kodda ishlatiladi), `name`
--  esa foydalanuvchiga ko'rinadigan sarlavha.
-- ============================================================
CREATE TABLE IF NOT EXISTS checklist_types (
    id          SERIAL PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,   -- 'opening' | 'handover' | 'closing'
    name        TEXT NOT NULL,          -- "Smena ochilishi" ...
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE id = 'seed_checklist_types_v1') THEN
        INSERT INTO checklist_types (key, name, sort_order, is_active) VALUES
            ('opening',  'Smena ochilishi',     1, TRUE),
            ('handover', 'Smena topshirilishi', 2, TRUE),
            ('closing',  'Smena yopilishi',     3, TRUE)
        ON CONFLICT (key) DO NOTHING;

        INSERT INTO schema_migrations (id) VALUES ('seed_checklist_types_v1');
    END IF;
END $$;

-- Bo'limlar (sections) endi har bir chek-list turiga tegishli bo'ladi.
ALTER TABLE sections ADD COLUMN IF NOT EXISTS checklist_type_id INTEGER
    REFERENCES checklist_types(id) ON DELETE CASCADE;

-- Eski global UNIQUE(name) endi kerak emas — bir xil nomdagi bo'lim
-- turli chek-list turlarida qayta-qayta bo'lishi mumkin bo'lishi kerak.
DROP INDEX IF EXISTS sections_name_unique;
CREATE UNIQUE INDEX IF NOT EXISTS sections_name_per_checklist_unique
    ON sections (checklist_type_id, name);

-- Mavjud (checklist_type_id hali NULL bo'lgan) 8 ta bo'lim — FAQAT BIR
-- MARTA — "Smena ochilishi" turiga biriktiriladi, so'ngra xuddi shu
-- bo'limlar "Smena topshirilishi" va "Smena yopilishi" turlari uchun
-- ham nusxalanadi (bu 3 tasi alohida-alohida, admin panel orqali
-- keyinchalik mustaqil tahrirlanadi).
DO $$
DECLARE
    opening_id  INTEGER;
    handover_id INTEGER;
    closing_id  INTEGER;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM schema_migrations WHERE id = 'assign_sections_checklist_type_v1') THEN
        SELECT id INTO opening_id  FROM checklist_types WHERE key = 'opening';
        SELECT id INTO handover_id FROM checklist_types WHERE key = 'handover';
        SELECT id INTO closing_id  FROM checklist_types WHERE key = 'closing';

        -- Eski (tur biriktirilmagan) bo'limlarni "Smena ochilishi"ga bog'laymiz.
        -- Bu orqali eski submission_photos yozuvlari (section_id) buzilmaydi.
        UPDATE sections SET checklist_type_id = opening_id
        WHERE checklist_type_id IS NULL;

        -- Xuddi shu bo'limlarni "Smena topshirilishi" va "Smena yopilishi"
        -- uchun nusxalab qo'yamiz (yangi id'lar bilan, mustaqil qatorlar).
        INSERT INTO sections (name, sort_order, is_active, checklist_type_id)
        SELECT name, sort_order, is_active, handover_id
        FROM sections WHERE checklist_type_id = opening_id
        ON CONFLICT (checklist_type_id, name) DO NOTHING;

        INSERT INTO sections (name, sort_order, is_active, checklist_type_id)
        SELECT name, sort_order, is_active, closing_id
        FROM sections WHERE checklist_type_id = opening_id
        ON CONFLICT (checklist_type_id, name) DO NOTHING;

        INSERT INTO schema_migrations (id) VALUES ('assign_sections_checklist_type_v1');
    END IF;
END $$;

-- Bundan buyon checklist_type_id har doim to'ldirilgan bo'lishi shart.
ALTER TABLE sections ALTER COLUMN checklist_type_id SET NOT NULL;

-- Submissionlar endi qaysi chek-list turi uchun yuborilganini ham
-- saqlaydi (filial kabi: tur o'chirilsa ham eski hisobot nomi
-- snapshot orqali saqlanib qoladi).
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS checklist_type_id INTEGER
    REFERENCES checklist_types(id) ON DELETE SET NULL;
ALTER TABLE submissions ADD COLUMN IF NOT EXISTS checklist_type_name_snapshot TEXT;

-- ============================================================
--  KO'P TILLI NOMLAR (uz / ru / en)
--  Muammo: foydalanuvchi ilovada Rus (yoki Ingliz) tilini tanlasa ham,
--  "Smena ochilishi/topshirilishi/yopilishi" va bo'limlar (sections)
--  nomlari bazada faqat BITTA tilda saqlangani uchun har doim o'sha bir
--  tilda ko'rinar edi — hattoki Telegram guruh-topic'ga yuborilgan
--  hisobot matnida ham. Yechim: har ikkala jadvalga name_uz/name_ru/
--  name_en ustunlari qo'shiladi, backend so'rov paytida foydalanuvchi
--  tanlagan tilga mos ustunni tanlab qaytaradi (fallback bilan), va bu
--  xuddi shu localized nom Telegram topic'iga yuboriladigan xabar
--  matnida ham ishlatiladi.
-- ============================================================
ALTER TABLE checklist_types ADD COLUMN IF NOT EXISTS name_uz TEXT;
ALTER TABLE checklist_types ADD COLUMN IF NOT EXISTS name_ru TEXT;
ALTER TABLE checklist_types ADD COLUMN IF NOT EXISTS name_en TEXT;

ALTER TABLE sections ADD COLUMN IF NOT EXISTS name_uz TEXT;
ALTER TABLE sections ADD COLUMN IF NOT EXISTS name_ru TEXT;
ALTER TABLE sections ADD COLUMN IF NOT EXISTS name_en TEXT;

-- checklist_types uchun 3 ta turdagi nom har doim ma'lum (key orqali
-- aniq belgilanadi), shuning uchun har safar xavfsiz to'ldirilishi
-- (faqat bo'sh joylarni) mumkin — schema_migrations bilan qulflanmagan.
UPDATE checklist_types SET name_uz = 'Smena ochilishi'      WHERE key = 'opening'  AND name_uz IS NULL;
UPDATE checklist_types SET name_ru = 'Открытие смены'        WHERE key = 'opening'  AND name_ru IS NULL;
UPDATE checklist_types SET name_en = 'Shift opening'         WHERE key = 'opening'  AND name_en IS NULL;

UPDATE checklist_types SET name_uz = 'Smena topshirilishi'   WHERE key = 'handover' AND name_uz IS NULL;
UPDATE checklist_types SET name_ru = 'Передача смены'        WHERE key = 'handover' AND name_ru IS NULL;
UPDATE checklist_types SET name_en = 'Shift handover'        WHERE key = 'handover' AND name_en IS NULL;

UPDATE checklist_types SET name_uz = 'Smena yopilishi'       WHERE key = 'closing'  AND name_uz IS NULL;
UPDATE checklist_types SET name_ru = 'Закрытие смены'        WHERE key = 'closing'  AND name_ru IS NULL;
UPDATE checklist_types SET name_en = 'Shift closing'         WHERE key = 'closing'  AND name_en IS NULL;

-- Boshlang'ich 8 ta bo'lim (avval faqat ruscha `name`da saqlangan) uchun
-- sifatli uch tilli tarjimalar. name_ru bo'sh bo'lgan joyda eski `name`
-- ustunidan ko'chiriladi (umumiy fallback), so'ng ma'lum matnlar uchun
-- aniq uz/en tarjimalari qo'yiladi.
UPDATE sections SET name_ru = name WHERE name_ru IS NULL;

UPDATE sections SET
    name_uz = 'Tashqi hudud va fasad fotosi',
    name_en = 'Photo of the exterior area and facade'
WHERE name_ru = 'Фото внешней территории и фасада' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Zal va hojatxonalar fotosi',
    name_en = 'Photo of the dining hall and restrooms'
WHERE name_ru = 'Фото зала и туалетов' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Peshtaxta (prilavka) fotosi',
    name_en = 'Photo of the counter'
WHERE name_ru = 'Фото прилавка' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Oshxona fotosi (1. Pitsa stansiyasi, 2. Vok stansiyasi, 3. Burger va rolls yig''ish stansiyasi, 4. Panirovka stansiyasi, 5. Fri stansiyasi, 6. Yuvish stansiyasi va mop zonalari)',
    name_en = 'Kitchen photo (1. Pizza station, 2. Wok station, 3. Burger & rolls assembly station, 4. Breading station, 5. Fries station, 6. Washing station and mop areas)'
WHERE name_ru = 'Фото кухни (1. Станция пиццы, 2. Станция Вок, 3. Станция сборки бургеров и роллов, 4. Панировочная станция, 5. Станция фри, 6. Станция мойки и моповые зоны)' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Xizmat xonasi fotosi',
    name_en = 'Photo of the staff/service room'
WHERE name_ru = 'Фото служебного помещения' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Yetkazib berish xonalari fotosi',
    name_en = 'Photo of the delivery rooms'
WHERE name_ru = 'Фото доставочных помещений' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Beshminutka va jamoa taxtasidan keyingi xodimlar fotosi (faqat ertalab)',
    name_en = 'Photo of staff after the 5-minute briefing and team board (morning only)'
WHERE name_ru = 'Фото сотрудников после пятиминутки и командной доски (только утром)' AND name_uz IS NULL;

UPDATE sections SET
    name_uz = 'Chek-listlar fotosi: Tozalik chek-listi, MS chek-listi, KLN, GSU tozalash blankasi (11:00, 15:00, 18:00, 21:00, Smena yopilishi)',
    name_en = 'Checklist photos: Cleanliness checklist, MS checklist, KLN, GSU cleaning form (11:00, 15:00, 18:00, 21:00, Shift closing)'
WHERE name_ru = 'Фото чек-листов: Чек-лист Чистоты, Чек-лист МС, КЛН, Бланк уборки ГСУ (11:00, 15:00, 18:00, 21:00, Закрытие смены)' AND name_uz IS NULL;

-- Yuqoridagi 8 tadan tashqarida qolgan har qanday eski bo'lim (masalan
-- admin panel orqali oldin qo'shilgan, faqat bitta tilda) uchun oxirgi
-- fallback: bo'sh qolgan uz/en ustunlarini eski `name` qiymati bilan
-- to'ldiramiz — shu bilan hech bir bo'lim nomsiz qolib ketmaydi (aks
-- holda o'sha til tanlanganda bo'lim nomi bo'sh ko'rinardi).
UPDATE sections SET name_uz = name WHERE name_uz IS NULL;
UPDATE sections SET name_en = name WHERE name_en IS NULL;
UPDATE checklist_types SET name_ru = name_uz WHERE name_ru IS NULL;
UPDATE checklist_types SET name_en = name_uz WHERE name_en IS NULL;

-- Bo'lim nomlari endi 3 ta alohida til ustunida saqlanadi, shuning uchun
-- eski global "bitta tildagi nom noyob bo'lishi kerak" cheklovi endi
-- ma'noni yo'qotdi (masalan bitta bo'lim uz/ru/en bo'yicha turlicha
-- uzunlikda bo'lishi mumkin, lekin ayni checklist ichida takrorlanmasligi
-- muhim emas — admin buni o'zi nazorat qiladi).
DROP INDEX IF EXISTS sections_name_per_checklist_unique;

-- ============================================================
--  BO'LIMNI FILIAL BO'YICHA YASHIRISH ("opt-out" model)
--  Muammo: ba'zi bo'limlar (masalan "Tashqi hudud va fasad fotosi")
--  barcha filiallarga tegishli emas — masalan foodcourt ichidagi
--  filialda tashqi hudud umuman yo'q.
--
--  Yechim: default holatda HAR BIR bo'lim BARCHA filiallarda ko'rinadi
--  (hech qanday sozlash talab qilinmaydi). Faqat ISTISNOLAR — "bu bo'lim
--  shu filialda YO'Q" — shu jadvalda alohida qayd etiladi. Bu bilan:
--    - Yangi filial qo'shilganda barcha mavjud bo'limlar avtomatik
--      unga ham tegishli bo'ladi (hech narsa qo'lda belgilash shart
--      emas).
--    - Yangi bo'lim qo'shilganda ham xuddi shunday — default barcha
--      filiallarda ko'rinadi, admin faqat kerak bo'lmagan filiallarni
--      "yashirish" ro'yxatiga qo'shadi.
-- ============================================================
CREATE TABLE IF NOT EXISTS filial_section_hidden (
    filial_id INTEGER NOT NULL REFERENCES filials(id) ON DELETE CASCADE,
    section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    PRIMARY KEY (filial_id, section_id)
);

-- ============================================================
--  BO'LIMLAR TARTIBINI TO'G'IRLASH (drag-and-drop uchun tayyorgarlik)
--  Ilgari yangi bo'lim qo'shilganda sort_order har doim 0 bilan
--  yaratilgan (`create_section` funksiyasida), shuning uchun ko'plab
--  bo'limlar bir xil tartib raqamiga ega bo'lib qolgan va ro'yxat
--  "tartibsiz" ko'rinardi. Bu yerda har bir chek-list turi ichida
--  mavjud bo'limlarga hozirgi tartibiga mos ketma-ket (0,1,2,...)
--  sort_order beriladi — bu superadmin keyinchalik drag-and-drop bilan
--  o'zgartira oladigan izchil boshlang'ich tartib bo'ladi. Idempotent —
--  qayta ishga tushirilganda (masalan admin allaqachon qo'lda
--  tartiblab bo'lgan bo'lsa) hech narsani buzmaydi.
-- ============================================================
WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY checklist_type_id ORDER BY sort_order, id) - 1 AS rn
    FROM sections
)
UPDATE sections s SET sort_order = ranked.rn
FROM ranked
WHERE s.id = ranked.id AND s.sort_order <> ranked.rn;
