-- ============================================================
--  Filial Feedback Mini App — PostgreSQL sxemasi
-- ============================================================

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
--  Bo'limlarni FAQAT quyidagi ro'yxat bilan cheklash
--  (idempotent migratsiya — har ishga tushishda xavfsiz qayta bajariladi)
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

-- 3) Ro'yxatda YO'Q bo'lgan har qanday eski bo'lim (masalan avvalgi
--    namunaviy "Oshxona", "Zal" va h.k.) faolsizlantiriladi — o'chirilmaydi,
--    chunki unga bog'liq eski hisobotlar bo'lishi mumkin, lekin ilovada
--    endi ko'rinmaydi.
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

-- 4) Faqat kerakli 8 ta bo'lim mavjud va faol bo'lishini ta'minlaymiz
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

-- ============================================================
--  Filiallarni FAQAT quyidagi ro'yxat bilan cheklash
--  (idempotent migratsiya — har ishga tushishda xavfsiz qayta bajariladi)
-- ============================================================

-- Ro'yxatda YO'Q bo'lgan har qanday eski filial faolsizlantiriladi —
-- o'chirilmaydi, chunki unga bog'liq eski hisobotlar/thread_id bo'lishi
-- mumkin, lekin ilovada endi ko'rinmaydi.
UPDATE filials SET is_active = FALSE
WHERE name NOT IN (
    'Scopus Mall', 'City Mall', 'Alfraganus', 'Beruniy', 'Novza', 'Anhor',
    'Sergeli', 'Tuzel', 'Compass Mall', 'Navruz Mall', 'Samarqand Darvoza',
    'C1 Street', 'C1 Wok', 'Eco', 'Yunusabad Gallery', 'Glinka Wok', 'Chilonzor 20'
);

-- Kerakli filiallar mavjud, faol va bergan tartibingizda bo'lishini
-- ta'minlaymiz. `thread_id` ga tegilmaydi — mavjud filialning Telegram
-- topici saqlanib qoladi.
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
