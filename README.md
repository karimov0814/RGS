# Filial Feedback Mini App — MVP

Telegram mini app orqali filial tanlanadi → har bir bo'lim uchun rasm olinadi →
"Yuborish" bosilganda rasmlar **shu filialga tegishli forum-topicga** (guruh
mavzusiga) filial nomi, vaqti va izoh bilan avtomatik tushadi.

## Arxitektura

```
mini app (index.html/app.js)  --(HTTPS, multipart/form-data)-->  FastAPI backend
                                                                        |
                                                                        v
                                                        PostgreSQL  +  Telegram Bot API
                                                                        |
                                                                        v
                                                        Guruh (forum topics yoqilgan)
```

- **Frontend** (`frontend/`) — sof HTML/JS, Telegram WebApp SDK orqali ishlaydi.
- **Backend** (`backend/app.py`) — FastAPI, `initData`ni tekshiradi, rasmlarni
  qabul qilib, tegishli filial mavzusiga (`message_thread_id`) yuboradi.

## O'rnatish

### 1. Guruhni tayyorlash
1. Telegram guruhingizda **Settings → Topics** ni yoqing (faqat supergroup).
2. Botni guruhga admin qilib qo'shing, **"Manage Topics"** huquqini bering.
3. `GROUP_CHAT_ID` ni oling (masalan `@userinfobot` yoki `getUpdates` orqali).

> Filiallar uchun topic'larni qo'lda ochish shart emas — birinchi marta
> shu filialdan rasm yuborilganda backend avtomatik `createForumTopic`
> chaqirib, mavzu ochadi va `thread_id`ni bazaga yozadi.

### 2. Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # BOT_TOKEN, GROUP_CHAT_ID, DATABASE_URL ni to'ldiring

psql "$DATABASE_URL" -f schema.sql   # jadvallarni yaratish

uvicorn app:app --host 0.0.0.0 --port 8000
```

Productionda backendni HTTPS ortida joylashtiring (nginx + Let's Encrypt yoki
Railway/Render kabi xizmat) — Telegram WebApp faqat HTTPS bilan ishlaydi.

### 3. Frontend
1. `frontend/app.js` ichidagi `API_BASE` ni backend domeningizga o'zgartiring.
2. `frontend/` papkasini istalgan statik hosting'ga joylashtiring (GitHub
   Pages, Netlify, Vercel, yoki backend bilan bir joyda `StaticFiles`).
3. BotFather'da: `/mybots → Bot Settings → Menu Button` yoki `/newapp` orqali
   shu URL'ni mini app sifatida bog'lang.

### 4. Bo'limlarni sozlash
`schema.sql` dagi `sections` jadvaliga real bo'lim nomlaringizni kiriting
(masalan: "Oshxona", "Zal", "Hojatxona"...). Filiallar esa birinchi submit
paytida avtomatik yaratiladi, yoki oldindan:
```sql
INSERT INTO filials (name) VALUES ('Chilonzor filiali'), ('Yunusobod filiali');
```

## Oqim (user flow)

1. **Filial tanlash** — ro'yxatdan bosiladi
2. **Bo'limlar** — har biri uchun kamera orqali rasm + ixtiyoriy izoh;
   progress-bar nechta bo'lim to'ldirilganini ko'rsatadi
3. Hammasi to'lganda pastda Telegram **MainButton "✅ Yuborish"** chiqadi
4. Bosilganda barcha rasmlar bitta so'rovda backendga yuboriladi →
   backend har birini tegishli filial-topicga jo'natadi, izoh + filial nomi +
   vaqt + yuborgan foydalanuvchining F.I.Sh. caption sifatida qo'shiladi
5. Muvaffaqiyat ekrani ko'rsatiladi

## Mavjud loyihangizga integratsiya bo'yicha eslatma

Sizda allaqachon `feedback-bot-main` (bot.py, PostgreSQL, Google Sheets)
mavjud ekan. Bu MVP'ni ikki xil integratsiya qilish mumkin:

- **A variant (tavsiya etiladi):** shu backend'ni alohida mikroservis sifatida
  ishga tushirasiz, faqat `BOT_TOKEN` va `DATABASE_URL`ni umumiy qilasiz.
- **B variant:** `app.py`dagi funksiyalarni (`telegram_utils.py`,
  `db.py`) to'g'ridan-to'g'ri `bot.py` loyihangiz ichiga ko'chirib,
  Google Sheets yozuvini ham `submit_photo` funksiyasiga qo'shib yuborasiz.

## GitHub + Railway orqali deploy qilish

### 1-qadam — GitHub'ga yuklash

```bash
cd mvp
git init
git add .
git commit -m "Filial feedback mini app MVP"
git branch -M main
git remote add origin https://github.com/USERNAME/filial-feedback-mvp.git
git push -u origin main
```

> `.env` fayli `.gitignore`da — u hech qachon GitHub'ga tushmaydi. `BOT_TOKEN`
> kabi maxfiy qiymatlarni faqat Railway paneliga kiritasiz (pastda).

### 2-qadam — Railway'da PostgreSQL yaratish

1. [railway.app](https://railway.app) → **New Project** → **Provision PostgreSQL**.
2. Yaratilgach, Postgres servisi ichida **Variables** bo'limidan `DATABASE_URL`
   qiymatini ko'rasiz (buni qo'lda ko'chirish shart emas — 3-qadamda referens
   orqali ulaymiz).

### 3-qadam — Backend servisini yaratish

1. Shu loyihada **+ New → GitHub Repo** → repongizni tanlang.
2. Servis sozlamalarida **Settings → Root Directory** ni `backend` deb belgilang
   (chunki repo ichida `backend/` va `frontend/` alohida joylashgan).
3. **Variables** bo'limiga quyidagilarni qo'shing:
   | Nomi | Qiymati |
   |---|---|
   | `BOT_TOKEN` | BotFather bergan token |
   | `GROUP_CHAT_ID` | guruhingiz id'si (masalan `-1001234567890`) |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — Railway'da shu yozuvni kiritsangiz, avtomatik Postgres servisidan referens oladi |
4. Railway `Procfile`/`railway.json` orqali avtomatik
   `uvicorn app:app --host 0.0.0.0 --port $PORT` bilan ishga tushadi.
5. Deploy tugagach, **Settings → Networking → Generate Domain** bosing —
   sizga `https://xxxx.up.railway.app` ko'rinishidagi backend manzili beriladi.
6. Jadvallar birinchi ishga tushishda **avtomatik** yaratiladi (`app.py`dagi
   `startup` hodisasi `schema.sql`ni ishga tushiradi) — qo'lda `psql` ishlatish
   shart emas.

### 4-qadam — Frontend servisini yaratish

1. Frontend'ni ham backend bilan bitta domenda joylashtirish shart emas —
   shu repo, boshqa **root directory: `frontend`** bilan yangi Railway servisi
   yarating (**+ New → GitHub Repo**, xuddi shu repo, lekin Root Directory =
   `frontend`).
2. `frontend/app.js` ichidagi:
   ```js
   const API_BASE = "https://YOUR_BACKEND_DOMAIN";
   ```
   qatorini 3-qadamdagi backend domeningizga o'zgartirib, commit + push qiling
   (Railway avtomatik qayta deploy qiladi).
3. Frontend servisi `frontend/package.json`dagi `serve` orqali statik fayllarni
   xizmat qiladi. Shu yerda ham **Generate Domain** bosing —
   `https://yyyy.up.railway.app` frontend manzilingiz bo'ladi.

> Muqobil variant: frontend juda oddiy statik fayl bo'lgani uchun uni
> Railway o'rniga bepul **GitHub Pages**ga ham joylashtirish mumkin — u holda
> faqat `frontend/` papkasini alohida branch (`gh-pages`) yoki repo qilib
> yuklaysiz.

### 5-qadam — BotFather'da mini appni ulash

`@BotFather` → botingiz → **Bot Settings → Menu Button** (yoki `/newapp`) →
4-qadamdagi frontend domenini (`https://yyyy.up.railway.app`) kiriting.

### Yangilanish oqimi

Kodga o'zgartirish kiritib, shunchaki:
```bash
git add .
git commit -m "yangilanish"
git push
```
— Railway GitHub repoga ulangani uchun har ikkala servisni (backend, frontend)
avtomatik qayta deploy qiladi.

## Xavfsizlik eslatmasi

`telegram_utils.validate_init_data()` har bir so'rovda **majburiy** chaqiriladi
— bu orqali faqat haqiqiy Telegram mini app orqali kelgan so'rovlar qabul
qilinadi (soxta so'rovlarning oldini oladi).
