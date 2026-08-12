# RGS — o'zgarishlar va yangi deploy tartibi

Bu versiyada **frontend va backend bitta `app` servisga birlashtirildi** (Railway usage kamayadi) va audit'da topilgan kamchiliklar tuzatildi (**tarjimaga tegilmadi — sizning talabingizga ko'ra**).

---

## 1. Nima o'zgardi (kod)

### Frontend → backend bilan bitta servis
- `frontend/` papkasi **o'chirildi**. Uning fayllari endi `backend/static/` ichida (index.html, app.js, style.css, i18n.js).
- `backend/app.py` oxirida `StaticFiles` mount qo'shildi — FastAPI ilovaning o'zi frontendni ham beradi.
- `backend/static/app.js`da `API_BASE = ""` (bir xil domen, nisbiy `/api/...`).
- Health endpoint `/` dan `/healthz` ga ko'chdi (chunki `/` endi index.html).

### Tuzatilgan kamchiliklar
| # | Kamchilik | Tuzatish | Fayl |
|---|---|---|---|
| R2 | Draft TTL 15 daqiqa — juda qisqa, rasm yo'qolardi | Standart **60 daqiqa**, `DRAFT_TTL_MINUTES` env orqali | `app.py` |
| R3 | Bot `/start`ga jim — javob bermasdi | Ruxsat bor → ilovani ochish ko'rsatmasi; ruxsat yo'q → "Ushbu bot ishlamaydi" | `bot_listener.py`, `telegram_utils.py` (`send_text_message`) |
| R4 | Rate-limit yo'q | Rasm yuklashga sirpanuvchi-oyna cheklovi (std 40/60s), env sozlanadi | `app.py` |
| R5 | Env yo'q bo'lsa noaniq crash | `BOT_TOKEN`/`GROUP_CHAT_ID`/`DATABASE_URL` uchun tushunarli xato | `db.py`, `telegram_utils.py` |
| R6 | `print()` bilan log | Standart `logging` (vaqt + daraja), `LOG_LEVEL` env | barcha fayllar |
| — | `__pycache__` repoda | O'chirildi + `.gitignore` qo'shildi | `.gitignore` |

### Railway usage optimizatsiyasi
- **Frontend servisi butunlay o'chadi** (eng katta tejash).
- DB connection pool `max_size` **25 → 10** (env: `DB_POOL_MAX`) — Railway Postgres xotira yuki kamayadi.
- Draft cleanup sikli **2 daqiqa → 5 daqiqa** (env: `DRAFT_CLEANUP_INTERVAL_SECONDS`) — bekorga uyg'onishlar (CPU) kamayadi.

**Tarjima (translate_utils.py) — o'zgarishsiz qoldirildi.**

---

## 2. Railway'da nima qilish kerak (bir martalik)

1. **Frontend servisini o'chiring** — u endi kerak emas (backend o'zi beradi).
2. **backend servisini `app` deb qoldiring**, Root Directory = `backend` (o'zgarishsiz). Start command o'zgarmaydi: `uvicorn app:app --host 0.0.0.0 --port $PORT` (`backend/railway.json`).
3. **BotFather** → Menu Button / mini app URL'ini endi **backend domeni**ga qarating (masalan `https://rgc.up.railway.app`) — chunki frontend ham shu domendan ochiladi.
4. (Ixtiyoriy) Railway → Settings → **Healthcheck Path** = `/healthz`. (`/` qoldirsangiz ham index.html 200 qaytaradi, ishlaydi.)

Environment variables **o'zgarmaydi**: `BOT_TOKEN`, `GROUP_CHAT_ID`, `DATABASE_URL`, `SUPERADMIN_IDS`.
Yangi ixtiyoriy sozlash o'zgaruvchilari (kerak bo'lsa): `DRAFT_TTL_MINUTES`, `DRAFT_CLEANUP_INTERVAL_SECONDS`, `DB_POOL_MAX`, `PHOTO_RATE_LIMIT_MAX`, `PHOTO_RATE_LIMIT_WINDOW`, `LOG_LEVEL`.

---

## 3. Tekshirildi
- Barcha Python fayllar sintaktik to'g'ri (AST parse).
- `app.py` import bo'ladi, StaticFiles mount eng oxirgi route (API'lar ustun).
- `GET /` → index.html (200), `/style.css` (200), `/app.js` → `API_BASE=""`, `/healthz` → `{"status":"ok"}`.
