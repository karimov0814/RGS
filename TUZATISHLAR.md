# RGS — muammolarning tuzatilishi (2026-08-31)

Uchta shikoyat bo'yicha ish: hisobot yuborilmay qolishi, zaxira nusxalarning
qolib ketishi, iPhone/Android farqi. Auditda topilgan 3 ta bloker ham
tuzatildi.

Har bir tuzatish haqiqiy PostgreSQL 16 va Telegram'ning **hujjatlashtirilgan
flood-limitlarini** taqlid qiluvchi soxta Bot API bilan o'lchandi.

---

## Natija (20 xodim × 8 bo'lim, bir vaqtda)

| | Oldin | Keyin |
|---|---|---|
| Muvaffaqiyatli hisobot | **0 / 10** | **20 / 20** |
| Xodim kutgan vaqt | 161 s (keyin xato) | **7,9 s** |
| Guruhga yetkazilgan xabar | 55 (chala) | **160 / 160** |
| O'chirilmay qolgan zaxira nusxa | 25 | **0** |
| Telegram 429 (flood) | 200 ta | **0 ta** |
| Bazada osilib qolgan qoralama | 25 | **0** |

---

## 1. "Hisobot yuborilmay qolyapti"

**Ildiz sabab.** Telegram bitta guruhga daqiqasiga ~20 ta xabar qabul qiladi.
Smena almashinuvida 10 xodim × 8 bo'lim = 80 xabar bir zumda urinardi.
Hammasi 429 (flood control) ga tushardi, va `telegram_utils.py` dagi
`min(retry_after, 10)` Telegram so'ragan muddatdan ancha erta qayta urinardi —
uchala urinish ham behuda ketardi. Frontend esa 40 soniyalik timeout'dan
keyin so'rovni yana 3 marta yuborib, yukni yanada oshirardi.

**Yechim — yetkazish navbati (outbox).**

- `POST /api/submit` endi Telegramga hech narsa yubormaydi: hisobotni
  `outbox` jadvaliga yozadi va ~0,2 soniyada javob qaytaradi.
- Fon worker'i (`_outbox_worker`) navbatni Telegram tezligida bo'shatadi,
  xatolarda eksponensial orqaga chekinish bilan qayta uradi.
- `telegram_utils.py` da markazlashgan cheklov: 18 xabar/60 s guruhga,
  25 so'rov/s global, 1 xabar/s har bir shaxsiy chatga. Cheklovga
  **oldindan** rioya qilinadi, shuning uchun 429 ga umuman urilmaydi.
- 429 baribir kelsa — `retry_after` **to'liq** kutiladi (endi cheklanmaydi).
- Yetkazish tugagach xodim botdan tasdiq xabarini oladi.

**Qo'shimcha kafolatlar:**

- Telegram butunlay ishlamay qolsa ham xodim xato ko'rmaydi; hisobot navbatda
  saqlanadi va **Telegram tiklangach avtomatik yetkaziladi** (sinovda
  tasdiqlangan).
- Server qayta ishga tushsa navbat bazada qoladi — hech narsa yo'qolmaydi.
- Bitta xodim uchun bir vaqtda faqat bitta yuborish (`SELECT ... FOR UPDATE`),
  ikkinchisi 409 oladi → **guruhga dublikat hisobot tushmaydi**.
- Frontend endi POST so'rovlarni 5xx javobda avtomatik qayta yubormaydi
  (dublikatlarning asosiy sababi shu edi) va "Yuborish" tugmasida ikki marta
  bosish himoyasi bor.

> **Eslatma.** Xabar formati o'zgarmadi (har bir bo'lim — alohida albom).
> Shuning uchun 20 ta hisobot guruhga to'liq tushishi ~9 daqiqa oladi —
> bu Telegram cheklovining fizikasi, xodimlar buni kutmaydi. Agar keyinchalik
> bir hisobotni bitta sarlavha + albomlarga birlashtirsangiz, bu vaqt ~4
> barobar qisqaradi.

---

## 2. "Zaxira nusxalar qolib ketyapti"

**Ildiz sabab — ikkita.**

1. O'chirish `asyncio.create_task(...)` bilan "yuborib yuborilardi", natijasi
   hech qayerda saqlanmasdi — Python bunday task'ni tugashidan oldin
   yig'ishtirib yuborishi mumkin.
2. `delete_message` `except Exception: pass` bilan **har qanday** xatoni
   jimgina yutardi. Band paytda Telegram 429 qaytarsa, o'chirish shunchaki
   yo'qolardi — logda ham, bazada ham iz qolmasdi.

Bundan tashqari, eskirgan qoralamalarni tozalash sikli avval xabarlar
ro'yxatini olib, keyin bazadan o'chirardi — oradagi har qanday xato "qaysi
xabarni o'chirish kerak" ma'lumotini butunlay yo'qotardi.

**Yechim.**

- Yangi `pending_deletions` jadvali: har bir o'chirish doimiy navbatda turadi
  va bajarilgunicha qayta uriniladi.
- `delete_message` endi cheklov orqali o'tadi, qayta uradi va natijani
  qaytaradi. "Xabar allaqachon yo'q" holati muvaffaqiyat deb hisoblanadi.
- Qoralama tozalash: xabarlar avval **bitta tranzaksiyada** navbatga
  ko'chiriladi, shundan keyingina qoralama o'chiriladi.

Sinov natijasi: 160 ta zaxira nusxadan **160 tasi** o'chirildi (avval 80 dan
55 tasi).

---

## 3. "iPhone va Android bir xil ishlamayapti"

**Ildiz sabab.** `compressImageForUpload` da "1 MB dan kichik bo'lsa
tegmaymiz" qoidasi bor edi. Android'da kadr `getUserMedia` dan olinadi va
odatda 1 MB dan kichik — ya'ni **umuman siqilmasdi**. iPhone'da tizim
kamerasi 12 MP / 3–5 MB rasm qaytaradi — ya'ni **har safar to'liq siqish
siklidan** o'tardi, u esa eng yomon holatda ~25 marta JPEG kodlash qilardi
va hammasi asosiy oqimda bajarilardi (interfeys qotib qolardi). HEIC
formatida `createImageBitmap` yiqilardi va `catch` bloki **asl faylni**
o'zgarishsiz yuborardi — Telegram esa uni rad etardi.

**Yechim — ikkala platformada bir xil quvur.**

| | Oldin | Keyin |
|---|---|---|
| Android | siqilmaydi (~0,5 MB, past sifat) | 1920 px, ~900 KB |
| iPhone | ~25 kodlash, interfeys qotadi | ~6 kodlash, Web Worker'da |
| HEIC | asl fayl yuboriladi → xato | `<img>` orqali dekodlanadi |
| Orientatsiya | portret rasm yonboshlaydi | `imageOrientation: from-image` |
| Siqib bo'lmasa | jimgina asl fayl ketardi | tushunarli xato ko'rsatiladi |

Siqish endi **Web Worker + OffscreenCanvas** da bajariladi — interfeys
qotmaydi; sifat binary search bilan topiladi (~6 kodlash, 25 emas);
`bitmap.close()` va `URL.revokeObjectURL()` chaqiriladi (xotira oqmaydi).

Kamera oqimi o'zgarmadi (iOS — tizim kamerasi, Android — getUserMedia),
sizning tanlovingizga ko'ra.

---

## 3.5. "Yuborish" tugmasi tushunarli bo'ldi

Qoida o'zgarmadi — har bir bo'limda kamida bitta rasm bo'lishi shart.
O'zgargani — xodim buni **ko'rib turadi**.

**Muammo edi.** Tugma to'lmaguncha butunlay yashirilardi (`hide()`), ya'ni
xodim kulrang, bosilmaydigan tugmani emas, umuman hech qanday tugmani
ko'rmasdi. Progress-bar "3 / 8" deb tursa ham, *qaysi* bo'lim qolgani
ko'rinmasdi va nega tugma yo'qligi hech qayerda yozilmasdi. Yangi xodim
buni "ilova buzuq" deb tushunardi.

Bundan tashqari, agar admin biror filial uchun barcha bo'limlarni
yashirgan bo'lsa (`total = 0`), ekran bo'm-bo'sh qolardi va tugma hech
qachon chiqmasdi — xodim boshi berk ko'chada qolardi.

**Endi:**

| | Oldin | Keyin |
|---|---|---|
| To'lmagan holat | tugma umuman yo'q | kulrang tugma: «Yana 12 ta bo'lim qoldi» |
| Qaysi bo'lim qolgani | ko'rinmaydi | amber chiziq + «KERAK» yorlig'i |
| To'lgach | tugma paydo bo'ladi | «✅ Yuborish» — yashil, faol |
| Bo'limi yo'q filial | bo'sh ekran, boshi berk | «Bu filial uchun bo'lim sozlanmagan…» |

Eski Telegram mijozlarida `is_active` qo'llab-quvvatlanmasligi mumkin,
shuning uchun tugma bosilganda to'liqlik **qayta tekshiriladi** va
to'lmagan bo'lsa «Yana N ta bo'lim qoldi» ogohlantirishi chiqadi.

Brauzerda 18 ta tekshiruv bilan tasdiqlangan (Playwright): tugma holati,
rangi, matni, «KERAK» yorliqlari, o'chiq tugmani bosish, bo'sh filial
holati va sahifada JS xatosi yo'qligi.

> **Eslatma.** Bu qoida hali ham faqat frontendda. Backend `submit`
> bo'limlar to'liqligini tekshirmaydi — qancha rasm bo'lsa, shuncha
> qabul qiladi. Hozir xavf yo'q (foydalanuvchilar whitelist'da), lekin
> qoida bitta joyda yashaydi.

---

## 4. Blokerlar (auditdan)

| # | Muammo | Tuzatish |
|---|---|---|
| BLK-01 | Toza bazada ilova umuman ishga tushmasdi (`ON CONFLICT (name)` mavjud bo'lmagan cheklovga tayanardi) | `INSERT ... WHERE NOT EXISTS` ga o'tkazildi. Endi bazani zaxiradan tiklash va staging muhiti yaratish mumkin. |
| BLK-02 | Bir xil nomli 2 ta bo'lim qo'shilsa, keyingi deployda ilova o'lardi | Har startupda yaratilib-o'chiriladigan UNIQUE indeks olib tashlandi; takroriy nom endi admin panelda 400 bilan rad etiladi. |
| BLK-03 | Fayl hajmi cheklanmagan → 4×100 MB = 958 MB RSS = OOM | 10 MB chegara, bo'lakli o'qish, magic-bytes tekshiruvi (413/400). |

---

## 5. Boshqa tuzatishlar

- `draft_photos.section_id` ga foreign key + smena turiga mosligi tekshiruvi —
  "zaharlangan qoralama" sikli yopildi (xodim endi hech qachon qamalib
  qolmaydi).
- Frontendda `esc()` funksiyasi — 13 ta `innerHTML` nuqtasi
  xavfsizlantirildi (filial/bo'lim nomi orqali XSS va `initData` o'g'irlash).
- Superadmin o'zini huquqdan mahrum qila olmaydi; oxirgi superadmin
  himoyalangan.
- `auth_date` buzuq bo'lsa 500 + ulanish uzilishi o'rniga 401.
- `initData` amal qilish muddati 24 soatdan **4 soatga** qisqartirildi.
- Takroriy filial nomi → 500 o'rniga tushunarli 400.
- Rate-limiter xotira oqmasi tuzatildi; `/api/submit` ga ham cheklov qo'shildi.
- Barcha `fetch` chaqiruvlariga timeout (ilgari 7 tasida yo'q edi — ilova
  "Yuklanmoqda" holatida abadiy qotib qolardi).
- Izohlar endi "Yuborish" bosilganda majburiy saqlanadi (`blur` native
  MainButton bilan ishlamasdi — izohlar jimgina yo'qolardi).
- Topic yaratish poygasi yopildi (guruhda "yetim" mavzular qolmaydi).
- Yetishmayotgan indekslar qo'shildi; N+1 so'rovlar bitta so'rovga
  birlashtirildi.
- `.gitignore` qo'shildi (`.env` tasodifan commit bo'lmasin).

---

## 6. Deploy

Kod o'zgarishi Railway'da odatdagidek: `git push` → avtomatik deploy.
Jadvallar (`outbox`, `pending_deletions`) va indekslar startupda **avtomatik**
yaratiladi, qo'lda SQL ishlatish shart emas.

**Mavjud environment variable'lar o'zgarmaydi.** Yangi, ixtiyoriy sozlamalar
(hammasining oqilona standart qiymati bor):

| O'zgaruvchi | Standart | Vazifasi |
|---|---|---|
| `TG_GROUP_RATE_LIMIT` | 18 | guruhga xabar / 60 s |
| `TG_GLOBAL_RATE_LIMIT` | 25 | Telegram so'rov / s |
| `TG_PRIVATE_MIN_INTERVAL` | 1.05 | shaxsiy chatga xabarlar orasidagi minimal vaqt |
| `MAX_PHOTO_BYTES` | 10485760 | maksimal rasm hajmi |
| `OUTBOX_MAX_ATTEMPTS` | 12 | yetkazishga urinishlar soni |
| `SUBMIT_RATE_LIMIT` | 10 | "Yuborish" / 60 s (bitta xodim) |
| `INIT_DATA_MAX_AGE_SECONDS` | 14400 | initData amal qilish muddati (4 soat) |

**Kuzatish uchun foydali so'rov** — navbat holatini ko'rish:

```sql
SELECT status, count(*) FROM outbox GROUP BY status;
SELECT count(*) FROM pending_deletions;
```

`status='failed'` yozuvlar paydo bo'lsa — `last_error` ustunida sabab yoziladi.
