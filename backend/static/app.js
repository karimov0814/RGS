// ============================================================
//  Filial Feedback Mini App — frontend logikasi
// ============================================================

// Frontend endi backend bilan BITTA servis (bitta domen)dan beriladi —
// shuning uchun API_BASE bo'sh: barcha so'rovlar shu domenning o'ziga
// (nisbiy `/api/...`) ketadi. Alohida backend domenini yozish SHART EMAS.
const API_BASE = "";

const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData; // backendga validatsiya uchun yuboriladi

// ============================================================
//  Tarmoqdagi vaqtinchalik uzilishlarga chidamli fetch.
//
//  Avval: internet bir lahzaga uzilib qolsa (mobil tarmoqda odatiy hol)
//  yoki so'rov birinchi urinishda vaqt tugashi bilan tugasa, foydalanuvchi
//  darhol "xatolik" ko'rar va faqat botni qayta ishga tushirgach (ya'ni
//  ilova qaytadan yuklangach) qayta urinib ko'rish imkoni bo'lardi.
//  Endi shu darajadagi vaqtinchalik xatoliklar sezilmasdan avtomatik
//  qayta uriniladi.
// ============================================================
// MUHIM TUZATISH: ilgari `fetch()` hech qanday timeout'siz chaqirilardi.
// iPhone (WKWebView) va ba'zi Android tarmoqlarida ulanish "osilib qolishi"
// (na muvaffaqiyat, na xato — javob umuman kelmasligi) odatiy hol, ayniqsa
// mobil ilova fondan qaytganda yoki tarmoq turi (wifi<->mobil) almashganda.
// Bunday holatda foydalanuvchi "Yuborish" tugmasi cheksiz aylanib turgan
// holatda qolib ketardi va hech qanday xato ko'rsatilmasdi. Endi har bir
// urinish uchun aniq vaqt chegarasi (`timeoutMs`) qo'yiladi — shu vaqtda
// javob kelmasa, so'rov bekor qilinib (AbortController), qayta uriniladi.
// MUHIM TUZATISH — takroriy hisobotlar sababi shu funksiyada edi.
// Ilgari HAR QANDAY so'rov 5xx javobda VA timeout'da avtomatik qayta
// yuborilardi. Rasm yuklash va "Yuborish" — bu POST so'rovlar, ya'ni
// ular serverda O'ZGARISH qiladi. Sekin internetda server so'rovni
// bajarib bo'lgan, javob esa yetib bormagan holatda qayta yuborish
// guruhga bir xil hisobotning 2-4 nusxasi tushishiga olib kelardi.
// Endi `retryOnServerError` standart holatda O'CHIQ — POST so'rovlar
// faqat ULANISH umuman o'rnatilmagan holatda qayta uriniladi (bu
// xavfsiz, chunki server so'rovni ko'rmagan).
async function fetchWithRetry(url, options = {}, retries = 2, backoffMs = 900,
                              timeoutMs = 25000, retryOnServerError = false) {
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(url, { ...options, signal: controller.signal });
      clearTimeout(timer);
      if (retryOnServerError && res.status >= 500 && attempt < retries) {
        lastErr = new Error(`HTTP ${res.status}`);
        await new Promise((r) => setTimeout(r, backoffMs * (attempt + 1)));
        continue;
      }
      return res;
    } catch (err) {
      clearTimeout(timer);
      // Tarmoq xatosi yoki timeout (uzilib/osilib qolgan ulanish).
      lastErr = err && err.name === "AbortError"
        ? new Error("So'rov javob bermadi (internet aloqasi sekin yoki uzilgan)")
        : err;
      if (attempt < retries) {
        await new Promise((r) => setTimeout(r, backoffMs * (attempt + 1)));
        continue;
      }
    }
  }
  throw lastErr;
}

// HTML'ga qo'yiladigan har qanday matnni xavfsizlantiradi.
// Ilgari filial/bo'lim nomlari va xodim izohlari to'g'ridan-to'g'ri
// `innerHTML` ga qo'yilardi — nomida <img src=x onerror=...> bo'lgan
// filial har bir xodimning ilovasida skript ishga tushirardi va
// initData'ni (to'liq huquqli kredensial) o'g'irlashi mumkin edi.
function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ============================================================
//  Chiziqli (line) ikonkalar — minimalist dizayn uchun yagona
//  manba. Barcha ikonkalar bir xil stroke-width bilan chiziladi.
// ============================================================
const ICONS = {
  plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`,
  edit: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19 3 20l1-4Z"/></svg>`,
  trash: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16"/><path d="M9 7V4.8c0-.44.36-.8.8-.8h4.4c.44 0 .8.36.8.8V7"/><path d="M6 7l1 12.2c.05.98.86 1.8 1.85 1.8h6.3c.99 0 1.8-.82 1.85-1.8L18 7"/><path d="M10 11v6M14 11v6"/></svg>`,
  eye: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="2.6"/></svg>`,
  eyeOff: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l18 18"/><path d="M10.6 5.63A10.9 10.9 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a15.8 15.8 0 0 1-3.15 3.99M6.5 6.87C4.06 8.5 2.5 12 2.5 12s3.5 6.5 9.5 6.5c1.3 0 2.47-.31 3.5-.8"/><path d="M9.5 9.6a2.6 2.6 0 0 0 3.6 3.55"/></svg>`,
  chevron: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>`,
  check: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4.5 4.5L19 8"/></svg>`,
  close: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`,
  info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.6h.01"/></svg>`,
  camera: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8.2c0-.66.54-1.2 1.2-1.2h2.1l1-1.6c.2-.32.55-.5.92-.5h5.56c.37 0 .72.18.92.5l1 1.6h2.1c.66 0 1.2.54 1.2 1.2v10.6c0 .66-.54 1.2-1.2 1.2H5.2c-.66 0-1.2-.54-1.2-1.2Z"/><circle cx="12" cy="13" r="3.4"/></svg>`,
  settings: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2.8"/><path d="M19.4 13.5a1.8 1.8 0 0 0 .36 1.98l.06.06a2.16 2.16 0 1 1-3.06 3.06l-.06-.06a1.8 1.8 0 0 0-1.98-.36 1.8 1.8 0 0 0-1.1 1.65V20a2.16 2.16 0 1 1-4.32 0v-.1a1.8 1.8 0 0 0-1.18-1.65 1.8 1.8 0 0 0-1.98.36l-.06.06a2.16 2.16 0 1 1-3.06-3.06l.06-.06a1.8 1.8 0 0 0 .36-1.98 1.8 1.8 0 0 0-1.65-1.1H2a2.16 2.16 0 1 1 0-4.32h.1a1.8 1.8 0 0 0 1.65-1.18 1.8 1.8 0 0 0-.36-1.98l-.06-.06A2.16 2.16 0 1 1 6.4 3.15l.06.06a1.8 1.8 0 0 0 1.98.36h.09A1.8 1.8 0 0 0 9.63 1.9V1.8a2.16 2.16 0 1 1 4.32 0v.1a1.8 1.8 0 0 0 1.1 1.65 1.8 1.8 0 0 0 1.98-.36l.06-.06a2.16 2.16 0 1 1 3.06 3.06l-.06.06a1.8 1.8 0 0 0-.36 1.98v.09c.28.72.94 1.22 1.72 1.24h.1a2.16 2.16 0 1 1 0 4.32h-.1a1.8 1.8 0 0 0-1.65 1.1Z"/></svg>`,
  block: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6"><circle cx="12" cy="12" r="8.5"/><path d="M6.2 6.2l11.6 11.6" stroke-linecap="round"/></svg>`,
  crown: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8l3.2 3.2L12 6l4.8 5.2L20 8l-1.4 9.5H5.4Z"/><path d="M5.4 20h13.2"/></svg>`,
  building: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="10" height="18" rx="1"/><path d="M15 9h4v12H5"/><path d="M8 7h1M11 7h1M8 11h1M11 11h1M8 15h1M11 15h1"/></svg>`,
  drag: `<svg viewBox="0 0 24 24" fill="currentColor"><circle cx="9" cy="6" r="1.4"/><circle cx="15" cy="6" r="1.4"/><circle cx="9" cy="12" r="1.4"/><circle cx="15" cy="12" r="1.4"/><circle cx="9" cy="18" r="1.4"/><circle cx="15" cy="18" r="1.4"/></svg>`,
  link: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 15l6-6"/><path d="M10.5 7.5l1-1a3.5 3.5 0 0 1 5 5l-1 1"/><path d="M13.5 16.5l-1 1a3.5 3.5 0 0 1-5-5l1-1"/></svg>`,
};

function iconMarkup(name) {
  return `<span class="icon">${ICONS[name] || ""}</span>`;
}

// Admin panelda checklist_types/sections xom holda (name_uz/name_ru/
// name_en) keladi — shu yordamchi joriy tanlangan tilga mos nomni
// backenddagi bilan bir xil fallback tartibida tanlaydi (avval joriy
// til, keyin ru->uz->en tartibida zaxira).
const LANG_FALLBACK_ORDER = {
  uz: ["name_uz", "name_ru", "name_en"],
  ru: ["name_ru", "name_uz", "name_en"],
  en: ["name_en", "name_ru", "name_uz"],
};
function pickLocalized(obj) {
  const order = LANG_FALLBACK_ORDER[getLang()] || LANG_FALLBACK_ORDER.uz;
  for (const key of order) {
    if (obj[key]) return obj[key];
  }
  return obj.name || "";
}

// Statik HTML ichidagi [data-icon] belgilangan joylarni to'ldiramiz
function renderStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((el) => {
    el.innerHTML = ICONS[el.dataset.icon] || "";
  });
}
renderStaticIcons();

// ---------- Holat (state) ----------
const state = {
  filial: null,          // {id, name}
  checklistTypes: [],     // [{id, key, name}]
  checklistType: null,    // {id, key, name}
  sections: [],            // [{id, name}]
  // section_id -> [{id (draft_photos.id, serverda saqlangan bo'lsa),
  //                 file (mahalliy File, hali yuklanmagan bo'lsa),
  //                 previewUrl, comment, uploading (bool)}, ...]
  photos: {},
};

// ============================================================
//  QORALAMA (draft) — serverga darhol saqlash.
//
//  Avval: rasm/izoh/tanlovlar FAQAT shu JS state ob'ektida turardi.
//  Xodim botdan chiqib ketsa (yoki Telegram ilovani fonda "tozalab
//  qo'ysa") — bu ob'ekt butunlay yo'qolib, hamma narsani qaytadan
//  boshlashga to'g'ri kelardi.
//
//  Endi: har bir rasm OLINGAN ZAHOTI backendga yuboriladi va u yerda
//  saqlanadi (faqat shu xodimga tegishli). Ilova qayta ochilganda
//  saqlangan qoralama avtomatik tiklanadi (restoreDraftIfAny()).
// ============================================================
async function saveDraftMeta(filialId, checklistTypeId) {
  try {
    const fd = new FormData();
    fd.append("init_data", initData);
    if (filialId != null) fd.append("filial_id", filialId);
    if (checklistTypeId != null) fd.append("checklist_type_id", checklistTypeId);
    fd.append("lang", getLang());
    await fetchWithRetry(`${API_BASE}/api/draft/meta`, { method: "PUT", body: fd });
  } catch (_) {
    // Jim ichida muvaffaqiyatsiz bo'lsa ham ilova ishlashda davom etadi —
    // rasm yuklanganda draft baribir avtomatik yaratiladi.
  }
}

async function uploadDraftPhoto(sectionId, comment, file) {
  const fd = new FormData();
  fd.append("init_data", initData);
  fd.append("section_id", sectionId);
  fd.append("comment", comment || "");
  fd.append("file", file, file.name || "photo.jpg");
  // Filial/smena ID'sini HAR BIR rasm bilan birga ham yuboramiz — shunda
  // qoralamaning filial/smena ma'lumoti alohida saveDraftMeta() so'rovi
  // muvaffaqiyatli bo'lishiga bog'liq bo'lib qolmaydi (o'z-o'zini
  // tuzatadigan / "self-healing" qiladi).
  if (state.filial) fd.append("filial_id", state.filial.id);
  if (state.checklistType) fd.append("checklist_type_id", state.checklistType.id);
  const res = await fetchWithRetry(`${API_BASE}/api/draft/photo`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.photo; // {id, section_id, comment, image_url}
}

async function updateDraftPhotoComment(photoId, comment) {
  try {
    const fd = new FormData();
    fd.append("init_data", initData);
    fd.append("comment", comment || "");
    await fetchWithRetry(`${API_BASE}/api/draft/photo/${photoId}`, { method: "PUT", body: fd });
  } catch (_) {}
}

async function deleteDraftPhoto(photoId) {
  try {
    await fetchWithRetry(
      `${API_BASE}/api/draft/photo/${photoId}?init_data=${encodeURIComponent(initData)}`,
      { method: "DELETE" }
    );
  } catch (_) {}
}

// Ilova ochilganda avvalgi (hali yuborilmagan) qoralama bor-yo'qligini
// tekshiradi. Bo'lsa — filial/chek-list turi/bo'limlar/rasmlarni xuddi
// avvalgidek tiklab, to'g'ridan-to'g'ri bo'limlar ekraniga olib o'tadi.
// Faqat SHU xodimning o'z qoralamasi qaytariladi (backend telegram_user_id
// bo'yicha filtrlaydi) — boshqa hech kim buni ko'ra olmaydi.
async function restoreDraftIfAny() {
  try {
    const res = await fetchWithRetry(`${API_BASE}/api/draft?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`);
    if (!res.ok) return false;
    const data = await res.json();
    const draft = data.draft;
    if (!draft || !draft.filial_id || !draft.checklist_type_id) return false;

    const filial = (state.filials || []).find((f) => f.id === draft.filial_id);
    if (!filial) return false;

    showLoading(t("loading_default"));

    const secRes = await fetchWithRetry(
      `${API_BASE}/api/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${draft.checklist_type_id}&filial_id=${filial.id}&lang=${getLang()}`
    , {}, 2, 900, 20000, true);
    if (!secRes.ok) {
      hideLoading();
      return false;
    }
    const secData = await secRes.json();

    state.filial = filial;
    state.checklistType = secData.checklist_type;
    state.sections = secData.sections;
    state.photos = {};

    (data.photos || []).forEach((p) => {
      if (!state.photos[p.section_id]) state.photos[p.section_id] = [];
      state.photos[p.section_id].push({
        id: p.id,
        previewUrl: `${API_BASE}${p.image_url}`,
        comment: p.comment || "",
      });
    });

    document.getElementById("filial-name-title").textContent = state.filial.name;
    document.getElementById("checklist-name-subtitle").textContent =
      `${CHECKLIST_TYPE_EMOJI[state.checklistType.key] || "📋"} ${state.checklistType.name}`;

    hideLoading();
    renderSections();
    showScreen("screen-sections");
    return true;
  } catch (e) {
    console.error("[restoreDraftIfAny] tiklashda xatolik:", e);
    hideLoading();
    return false;
  }
}

// ---------- Ekranlarni almashtirish ----------
function showScreen(id) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function showLoading(text) {
  document.getElementById("loading-text").textContent = text || t("loading_default");
  document.getElementById("overlay-loading").classList.remove("hidden");
}
function hideLoading() {
  document.getElementById("overlay-loading").classList.add("hidden");
}

// ============================================================
//  Universal modal — Telegram Mini App WebView'larida
//  window.alert / confirm / prompt ko'p qurilmalarda (ayniqsa iOS)
//  bloklanadi yoki hech narsa ko'rsatmaydi, shu sabab tugma bosilganda
//  "hech narsa bo'lmayapti"day tuyulardi. Shu komponent ularning
//  o'rnini bosadi va har doim ishonchli ishlaydi.
// ============================================================
const modalOverlay = document.getElementById("modal-overlay");
const modalTitleEl = document.getElementById("modal-title");
const modalMessageEl = document.getElementById("modal-message");
const modalFieldsEl = document.getElementById("modal-fields");
const modalCancelBtn = document.getElementById("modal-cancel");
const modalConfirmBtn = document.getElementById("modal-confirm");

function closeModal() {
  modalOverlay.classList.add("hidden");
  modalFieldsEl.innerHTML = "";
}

/**
 * Umumiy modal ochuvchi. fields berilsa, forma sifatida ishlaydi va
 * confirm bosilganda field qiymatlari bilan resolve bo'ladi (yoki
 * bekor qilinsa null).
 */
function openModal({ title, message = "", fields = [], confirmText, cancelText, danger = false, showCancel = true }) {
  if (confirmText === undefined) confirmText = t("modal_ok");
  if (cancelText === undefined) cancelText = t("modal_cancel");
  return new Promise((resolve) => {
    modalTitleEl.textContent = title;
    modalMessageEl.textContent = message;
    modalFieldsEl.innerHTML = fields
      .map((f) => {
        if (f.type === "checkbox") {
          return `
            <label class="admin-checkbox">
              <input type="checkbox" id="modal-field-${f.id}" ${f.checked ? "checked" : ""} />
              ${esc(f.label)}
            </label>`;
        }
        return `
          <div>
            <label class="modal-field-label" for="modal-field-${f.id}">${esc(f.label)}</label>
            <input type="text" id="modal-field-${f.id}" class="admin-input" placeholder="${f.placeholder || ""}" value="${f.value ? String(f.value).replace(/"/g, "&quot;") : ""}" />
          </div>`;
      })
      .join("");

    modalConfirmBtn.textContent = confirmText;
    modalConfirmBtn.className = "primary-btn" + (danger ? " danger" : "");
    modalCancelBtn.style.display = showCancel ? "" : "none";
    modalCancelBtn.textContent = cancelText;

    modalOverlay.classList.remove("hidden");

    const firstInput = modalFieldsEl.querySelector('input[type="text"]');
    if (firstInput) setTimeout(() => firstInput.focus(), 50);

    function cleanup() {
      modalConfirmBtn.onclick = null;
      modalCancelBtn.onclick = null;
      closeModal();
    }

    modalConfirmBtn.onclick = () => {
      const result = {};
      fields.forEach((f) => {
        const el = document.getElementById(`modal-field-${f.id}`);
        result[f.id] = f.type === "checkbox" ? el.checked : el.value.trim();
      });
      cleanup();
      resolve(fields.length ? result : true);
    };
    modalCancelBtn.onclick = () => {
      cleanup();
      resolve(null);
    };
  });
}

function showAlert(message, title) {
  return openModal({ title: title || t("modal_attention"), message, confirmText: t("modal_understood"), showCancel: false });
}
function showConfirm(message, { title, confirmText, danger = false } = {}) {
  return openModal({
    title: title || t("modal_confirm_title"),
    message,
    confirmText: confirmText || t("modal_yes"),
    danger,
    showCancel: true,
  }).then((r) => r === true);
}
function showPrompt({ title, message = "", fields, confirmText }) {
  return openModal({ title, message, fields, confirmText: confirmText || t("btn_save"), showCancel: true });
}

// ---------- 0. Ruxsat tekshiruvi + 1. Filial tanlash (ilova ochilishi bilan) ----------
state.isSuperadmin = false;

function renderFilialList(filials) {
  state.filials = filials;
  const list = document.getElementById("filial-list");
  list.innerHTML = "";
  filials.forEach((f) => {
    const el = document.createElement("div");
    el.className = "filial-item";
    el.innerHTML = `<span>${esc(f.name)}</span><span class="arrow">${iconMarkup("chevron")}</span>`;
    el.addEventListener("click", () => selectFilial(f));
    list.appendChild(el);
  });
}

// Admin panelda yangi filial qo'shilgandan/o'chirilgandan/tahrirlangandan
// keyin "Hisobot yuborish" orqali filial tanlash ekraniga o'tilsa, ro'yxat
// ilova birinchi ochilgandagi ESKI holatda qolib ketmasin uchun — shu
// yerda bazadan QAYTA so'raladi.
async function refreshFilialList() {
  try {
    const res = await fetchWithRetry(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`, {}, 2, 900, 20000, true);
    if (!res.ok) return;
    const data = await res.json();
    state.checklistTypes = data.checklist_types;
    renderFilialList(data.filials);
  } catch (_) {
    // Jim ichida muvaffaqiyatsiz bo'lsa — eskirgan ro'yxat ko'rsatiladi,
    // lekin ilova ishlashda davom etadi.
  }
}

async function loadFilials() {
  showLoading(t("loading_default"));
  try {
    const res = await fetchWithRetry(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`, {}, 2, 900, 20000, true);

    if (res.status === 401 || res.status === 403) {
      // Ruxsat etilmagan (whitelist'da yo'q) yoki initData yaroqsiz foydalanuvchi
      hideLoading();
      showScreen("screen-blocked");
      return;
    }
    if (!res.ok) throw new Error(await res.text());

    const data = await res.json();
    state.checklistTypes = data.checklist_types;
    state.isSuperadmin = !!data.is_superadmin;

    renderFilialList(data.filials);

    hideLoading();

    if (state.isSuperadmin) {
      // Superadmin mini appni ochganda avval admin panel ochiladi
      document.getElementById("admin-back-bar").classList.remove("hidden");
      showScreen("screen-admin");
      loadAdminUsers();
      loadAdminFilials();
      initAdminSections();
    } else {
      // Xodimning yubormasdan qoldirgan qoralamasi bo'lsa — shu joydan
      // davom ettiramiz, bo'lmasa oddiy filial tanlash ekrani ko'rsatiladi.
      const resumed = await restoreDraftIfAny();
      if (!resumed) showScreen("screen-filial");
    }
  } catch (e) {
    hideLoading();
    await showAlert(t("error_load_config"));
  }
}

function selectFilial(filial) {
  state.filial = filial;
  state.checklistType = null;
  state.sections = [];
  state.photos = {};
  document.getElementById("checklist-filial-title").textContent = filial.name;
  renderChecklistTypes();
  showScreen("screen-checklist");
}

// ---------- 1.5. Chek-list turini tanlash ----------
const CHECKLIST_TYPE_EMOJI = { opening: "🔓", handover: "🔄", closing: "🔒" };

function renderChecklistTypes() {
  const list = document.getElementById("checklist-type-list");
  list.innerHTML = "";

  if (!state.checklistTypes.length) {
    list.innerHTML = `<p class="hint">${t("checklist_none")}</p>`;
    return;
  }

  state.checklistTypes.forEach((ct) => {
    const el = document.createElement("div");
    el.className = "filial-item";
    el.innerHTML = `<span>${CHECKLIST_TYPE_EMOJI[ct.key] || "📋"} ${esc(ct.name)}</span><span class="arrow">${iconMarkup("chevron")}</span>`;
    el.addEventListener("click", () => selectChecklistType(ct));
    list.appendChild(el);
  });
}

document.getElementById("btn-back-to-filial").addEventListener("click", async () => {
  showScreen("screen-filial");
  await refreshFilialList();
});

// Bo'limlar ekranidan orqaga — xodim adashib boshqa smena/filialni
// tanlab qo'ygan bo'lsa, shu tugma orqali qaytib, TO'G'RI filial/smenani
// tanlashi mumkin. Bu qadamning o'zi hech narsani o'chirmaydi — faqat
// selectChecklistType() ichida, HAQIQATAN HAM boshqa smena tanlansa,
// eski (yubormasdan qoldirgan) rasm/izohlar haqida ogohlantiriladi.
document.getElementById("btn-back-to-checklist").addEventListener("click", () => {
  if (!state.filial) {
    showScreen("screen-filial");
    return;
  }
  document.getElementById("checklist-filial-title").textContent = state.filial.name;
  renderChecklistTypes();
  showScreen("screen-checklist");
});

// Til almashtirilganda ekranda hozir ko'rinib turgan chek-list turlari /
// bo'limlar nomlarini yangi tilda bazadan qayta yuklaydi (bular bazada
// har bir til uchun alohida saqlanadi, shu sabab faqat statik matnlarni
// qayta chizish yetarli emas — backenddan yangi tilda qayta so'ralishi
// kerak).
async function refetchChecklistTypes() {
  try {
    const res = await fetchWithRetry(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`, {}, 2, 900, 20000, true);
    if (!res.ok) return;
    const data = await res.json();
    state.checklistTypes = data.checklist_types;
  } catch (_) {}
}

async function refetchSections() {
  if (!state.checklistType) return;
  try {
    const res = await fetchWithRetry(
      `${API_BASE}/api/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${state.checklistType.id}&filial_id=${state.filial.id}&lang=${getLang()}`
    , {}, 2, 900, 20000, true);
    if (!res.ok) return;
    const data = await res.json();
    // section.id lar o'zgarmaydi, faqat "name" yangi tilga almashadi —
    // shuning uchun state.photos (section_id bo'yicha kalitlangan) va
    // foydalanuvchi hozircha olgan rasmlar buzilmaydi.
    state.checklistType = data.checklist_type;
    state.sections = data.sections;
  } catch (_) {}
}

async function selectChecklistType(checklistType) {
  showLoading(t("loading_default"));
  try {
    // Serverdagi joriy qoralamani tekshiramiz — agar u BOSHQA
    // filial/smena uchun bo'lsa VA unda hali yubormasdan qolgan rasm(lar)
    // bo'lsa, xodimni ogohlantirmasdan turib eskisini o'chirib
    // yubormaymiz (chunki bu "yubormasdan botdan chiqib ketgan" holatdan
    // farqli — bu yerda xodim ONGLI ravishda boshqasini tanlamoqda).
    const draftRes = await fetchWithRetry(`${API_BASE}/api/draft?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`, {}, 2, 900, 20000, true);
    const draftData = draftRes.ok ? await draftRes.json() : { draft: null, photos: [] };
    const existingDraft = draftData.draft;
    const isSameSelection =
      existingDraft && existingDraft.filial_id === state.filial.id && existingDraft.checklist_type_id === checklistType.id;

    if (existingDraft && !isSameSelection && (draftData.photos || []).length > 0) {
      hideLoading();
      const proceed = await showConfirm(t("draft_discard_message"), {
        title: t("draft_discard_title"),
        confirmText: t("draft_discard_confirm"),
        danger: true,
      });
      if (!proceed) return;
      showLoading(t("loading_default"));
    }

    const res = await fetchWithRetry(
      `${API_BASE}/api/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${checklistType.id}&filial_id=${state.filial.id}&lang=${getLang()}`
    , {}, 2, 900, 20000, true);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    state.checklistType = checklistType;
    state.sections = data.sections;

    // Agar bu AYNAN o'sha qoralama bo'lsa (masalan xodim orqaga bosib,
    // qayta xuddi shu filial+smenani tanlasa) — avvalgi rasmlarni
    // yo'qotmasdan tiklaymiz. Aks holda (yangi tanlov) — bo'sh boshlanadi.
    state.photos = {};
    if (isSameSelection) {
      (draftData.photos || []).forEach((p) => {
        if (!state.photos[p.section_id]) state.photos[p.section_id] = [];
        state.photos[p.section_id].push({
          id: p.id,
          previewUrl: `${API_BASE}${p.image_url}`,
          comment: p.comment || "",
        });
      });
    }

    document.getElementById("filial-name-title").textContent = state.filial.name;
    document.getElementById("checklist-name-subtitle").textContent =
      `${CHECKLIST_TYPE_EMOJI[checklistType.key] || "📋"} ${checklistType.name}`;

    // Tanlov saqlanadi (KUTIB, ya'ni bo'limlar ekrani ko'rsatilishidan
    // OLDIN) — shu tufayli xodim bo'limlar ekraniga tushgan zahoti rasm
    // olishni boshlasa ham, qoralama filial/smenasi bazada ALLAQACHON
    // to'g'ri o'rnatilgan bo'ladi (poyga holati bo'lmaydi). Agar tanlov
    // haqiqatan ham o'zgargan bo'lsa, bu chaqiruv backendda eski (mos
    // kelmaydigan) qoralama rasmlarini ham tozalaydi.
    await saveDraftMeta(state.filial.id, checklistType.id);

    hideLoading();
    renderSections();
    showScreen("screen-sections");
  } catch (e) {
    hideLoading();
    await showAlert(t("error_load_sections"));
  }
}

// ---------- 2. Bo'limlar bo'yicha (bir nechta) rasm olish ----------
let activeSectionId = null;
const cameraInput = document.getElementById("camera-input");

// ============================================================
//  Platforma bo'yicha kamera strategiyasi.
//
//  iOS: native <input capture="environment"> WKWebView'da to'g'ridan-
//  to'g'ri to'liq ekranli kamera ilovasini ochadi va TO'LIQ SENSOR
//  o'lchamidagi, HDR/hisoblash-fotografiya bilan ishlangan rasm
//  qaytaradi — bu getUserMedia() orqali olinadigan video-freymdan
//  SIFAT jihatidan doim ustun bo'ladi (video oqimi hech qachon to'liq
//  fotosurat pipeline'iga teng bo'lmaydi). iOS'da bu ishonchli
//  ishlagani uchun ('Ishladi' — tasdiqlangan) native yo'l saqlanadi.
//
//  Android: Telegram Android WebView'ining onShowFileChooser()
//  implementatsiyasi "capture" atributini e'tiborsiz qoldiradi
//  (tasdiqlangan root cause), shuning uchun bu yerda getUserMedia()
//  asosidagi custom UI ishlatiladi — lekin endi IMKON QADAR YUQORI
//  sifat bilan: ImageCapture.takePhoto() (mavjud bo'lsa — bu videodan
//  emas, kameraning to'liq fotosurat quvuridan foydalanadi) yoki
//  yuqori-o'lchamli video-freym fallback orqali.
// ============================================================
function isIOSPlatform() {
  return tg.platform === "ios";
}

const cameraOverlay = document.getElementById("camera-overlay");
const cameraVideoEl = document.getElementById("camera-video");
const cameraCanvasEl = document.getElementById("camera-canvas");
const cameraCloseBtn = document.getElementById("camera-close-btn");
const cameraShutterBtn = document.getElementById("camera-shutter-btn");
const cameraSwitchBtn = document.getElementById("camera-switch-btn");

cameraCloseBtn.innerHTML = iconMarkup("close");
cameraSwitchBtn.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2.1 21 6l-4 3.9"/><path d="M3 11V9a4 4 0 0 1 4-4h14"/><path d="M7 21.9 3 18l4-3.9"/><path d="M21 13v2a4 4 0 0 1-4 4H3"/></svg>`;

let cameraStream = null;
let cameraImageCapture = null; // ImageCapture — mavjud bo'lsa yuqori sifat uchun
let cameraFacingMode = "environment"; // orqa kamera birinchi ustuvorlik

// Eng yuqori o'lchamdan boshlab, qurilma qo'llab-quvvatlamasa pastroqqa
// tushiladi (OverconstrainedError'dan qochish uchun).
const CAMERA_RESOLUTION_ATTEMPTS = [
  { width: { ideal: 4096 }, height: { ideal: 2160 } },
  { width: { ideal: 1920 }, height: { ideal: 1080 } },
  {}, // qurilma standart o'lchami — oxirgi zaxira
];

async function startCameraStream(facingMode) {
  // Avval eski oqimni to'xtatamiz — aks holda kamera band bo'lib qolishi mumkin.
  stopCameraStream();

  let lastErr = null;
  for (const resolution of CAMERA_RESOLUTION_ATTEMPTS) {
    try {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: facingMode }, ...resolution },
        audio: false,
      });
      break;
    } catch (err) {
      lastErr = err;
    }
  }
  if (!cameraStream) throw lastErr || new Error("getUserMedia failed");

  cameraVideoEl.srcObject = cameraStream;
  await cameraVideoEl.play();

  // ImageCapture — Chromium/Android WebView'da odatda qo'llab-quvvatlanadi
  // va videoning display-resolution'idan emas, kameraning haqiqiy
  // FOTOSURAT pipeline'idan (odatda ancha yuqori piksel) foydalanadi.
  cameraImageCapture = null;
  if ("ImageCapture" in window) {
    try {
      const track = cameraStream.getVideoTracks()[0];
      cameraImageCapture = new ImageCapture(track);
    } catch (_) {
      cameraImageCapture = null;
    }
  }
}

function stopCameraStream() {
  if (cameraStream) {
    cameraStream.getTracks().forEach((track) => track.stop());
    cameraStream = null;
  }
  cameraImageCapture = null;
  cameraVideoEl.srcObject = null;
}

async function openCameraCapture() {
  if (isIOSPlatform()) {
    // iOS: native kamera — eng yuqori sifat, allaqachon ishonchli ishlaydi.
    cameraInput.click();
    return;
  }

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    cameraInput.click(); // getUserMedia mavjud bo'lmagan eski brauzer uchun zaxira
    return;
  }
  try {
    await startCameraStream(cameraFacingMode);
    cameraOverlay.classList.remove("hidden");
  } catch (err) {
    // NotAllowedError (ruxsat berilmagan), NotFoundError (kamera yo'q)
    // va hokazo — foydalanuvchini bloklab qo'ymaslik uchun native
    // inputga qaytamiz.
    console.error("Camera error:", err);
    stopCameraStream();
    cameraOverlay.classList.add("hidden");
    await showAlert(t("camera_permission_denied"));
    cameraInput.click();
  }
}

function closeCameraCapture() {
  stopCameraStream();
  cameraOverlay.classList.add("hidden");
}

cameraCloseBtn.addEventListener("click", closeCameraCapture);

cameraSwitchBtn.addEventListener("click", async () => {
  cameraFacingMode = cameraFacingMode === "environment" ? "user" : "environment";
  try {
    await startCameraStream(cameraFacingMode);
  } catch (err) {
    console.error("Camera switch error:", err);
    // Almashtirish muvaffaqiyatsiz bo'lsa — oldingi kameraga qaytamiz.
    cameraFacingMode = cameraFacingMode === "environment" ? "user" : "environment";
    try {
      await startCameraStream(cameraFacingMode);
    } catch (_) {
      closeCameraCapture();
    }
  }
});

// Video elementining joriy freymini canvas orqali yuqori sifatli
// JPEG blob'ga aylantiradi — faqat ImageCapture mavjud bo'lmaganda
// ishlatiladigan zaxira yo'l.
function grabVideoFrameAsBlob() {
  return new Promise((resolve) => {
    const w = cameraVideoEl.videoWidth;
    const h = cameraVideoEl.videoHeight;
    if (!w || !h) return resolve(null);

    cameraCanvasEl.width = w;
    cameraCanvasEl.height = h;
    const ctx = cameraCanvasEl.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(cameraVideoEl, 0, 0, w, h);
    cameraCanvasEl.toBlob((blob) => resolve(blob), "image/jpeg", 0.95);
  });
}

cameraShutterBtn.addEventListener("click", async () => {
  if (!cameraStream || activeSectionId === null) return;
  cameraShutterBtn.disabled = true;
  try {
    let blob = null;

    // 1-ustuvorlik: ImageCapture.takePhoto() — to'liq fotosurat pipeline.
    if (cameraImageCapture && typeof cameraImageCapture.takePhoto === "function") {
      try {
        blob = await cameraImageCapture.takePhoto();
      } catch (err) {
        console.error("ImageCapture.takePhoto xatosi, canvas fallback:", err);
        blob = null;
      }
    }

    // 2-ustuvorlik: video-freymni canvas orqali yuqori sifatda olish.
    if (!blob) blob = await grabVideoFrameAsBlob();

    if (blob) {
      const file = new File([blob], `photo_${Date.now()}.jpg`, { type: blob.type || "image/jpeg" });
      handlePickedFiles([file]);
      closeCameraCapture();
    }
  } finally {
    cameraShutterBtn.disabled = false;
  }
});

// Ilova fonga o'tsa (Telegram'da boshqa oynaga o'tilsa) kamerani
// avtomatik o'chirib qo'yamiz — resurs va maxfiylik uchun muhim.
document.addEventListener("visibilitychange", () => {
  if (document.hidden && cameraStream) closeCameraCapture();
});

// Ikkala inputdan (galereya) va getUserMedia'dan (kamera) kelgan
// fayllarni bitta joyda qayta ishlash. Har bir rasm DARHOL serverga
// yuklanadi (draft sifatida saqlanadi) — shu tufayli xodim shu yerdan
// chiqib ketsa ham rasm yo'qolmaydi, va "Yuborish" bosilganda uni
// qayta yuklash shart bo'lmaydi.
// ============================================================
//  Rasmni yuklashdan OLDIN brauzerning o'zida siqish.
//
//  Muammo: Android'da kamera orqali olingan rasmlar odatda TO'LIQ
//  o'lchamda (ko'pincha 8-15 MB, ba'zan undan ham katta) qaytadi —
//  iPhone'da esa brauzer buni odatda avtomatik siqib yuboradi. Bunday
//  katta fayllar Telegram'ning rasm yuborish chegarasidan (10 MB)
//  oshib ketishi, yoki sekin mobil internetda so'rovni "uzilib
//  qolishga" yaqinlashtirishi mumkin edi — bu, ehtimol, "Yuborish"da
//  Android'ga xos xatolikning sababi edi.
//
//  Yechim: rasm serverga yuborilishidan oldin, shu yerning o'zida
//  (Canvas orqali) maksimal 1600px tomonga va sifatli, lekin ancha
//  yengilroq JPEG'ga siqiladi. Agar biror sabab bilan siqish
//  muvaffaqiyatsiz bo'lsa, asl fayl o'zgarishsiz yuboriladi (funksiya
//  hech qachon xato bermaydi).
// ============================================================
// ============================================================
//  Rasmni yuklashdan OLDIN brauzerning o'zida siqish — MAKSIMAL 1 MB.
//
//  Qoida: agar rasm allaqachon 1 MB'dan kichik bo'lsa — TEGILMAYDI
//  (asl sifatida qoladi). Agar 1 MB'dan katta bo'lsa — sifat va (kerak
//  bo'lsa) o'lchamni bosqichma-bosqich pasaytirib, natija 1 MB yoki
//  undan kichik bo'lguncha siqiladi.
//
//  Muammo: Android'da kamera orqali olingan rasmlar odatda TO'LIQ
//  o'lchamda (ko'pincha 8-15 MB) qaytadi — iPhone'da esa brauzer buni
//  odatda avtomatik siqib yuboradi. Bunday katta fayllar Telegram'ning
//  rasm yuborish chegarasidan (10 MB) oshib ketishi, yoki sekin mobil
//  internetda so'rovni "uzilib qolishga" yaqinlashtirishi mumkin edi.
// ============================================================
// ============================================================
//  RASMNI TAYYORLASH — iPhone va Android uchun BIR XIL natija.
//
//  MUAMMO EDI ("iPhone va Androidda bir xil rejimda va tezlikda
//  ishlamayapti"):
//    1. iOS tizim kamerasi 12 MP / 3-5 MB rasm qaytaradi; Androidda esa
//       kadr getUserMedia'dan olinadi va odatda 1 MB'dan kichik bo'ladi.
//       Eski kod "1 MB'dan kichik bo'lsa TEGMAYMIZ" qoidasi bilan
//       ishlagani uchun Android rasmlari umuman siqilmasdi, iPhone
//       rasmlari esa har safar to'liq siqish siklidan o'tardi —
//       natijada ikki telefonda ham hajm, ham tezlik butunlay boshqacha
//       edi.
//    2. Siqish sikli eng yomon holatda ~25 marta JPEG kodlash qilardi va
//       hammasi asosiy oqimda (main thread) bajarilardi — iPhone'da
//       interfeys bir necha soniyaga qotib qolardi.
//    3. HEIC (iPhone'ning standart formati) `createImageBitmap` da
//       yiqilardi va `catch` bloki ASL faylni o'zgarishsiz yuborardi —
//       Telegram esa uni rad etardi.
//    4. `bitmap.close()` chaqirilmasdi, EXIF orientatsiyasi hisobga
//       olinmasdi (portret rasmlar yonboshlab ketardi).
//
//  YECHIM: har ikkala platformada bir xil quvur (pipeline):
//    - har doim qayta kodlanadi (hajmidan qat'i nazar) → bir xil natija;
//    - maksimal tomon 1920px, maqsad hajm 900 KB;
//    - sifat BINARY SEARCH bilan topiladi (~6 kodlash, 25 emas);
//    - iloji bo'lsa Web Worker + OffscreenCanvas'da → interfeys qotmaydi;
//    - HEIC/dekodlanmaydigan format uchun <img> orqali zaxira yo'l;
//    - hech qanday yo'l ishlamasa va fayl chegaradan katta bo'lsa —
//      TUSHUNARLI XATO ko'rsatiladi (jimgina asl faylni yubormaydi).
// ============================================================
const TARGET_BYTES = 900 * 1024;        // maqsad: ~900 KB
const HARD_MAX_BYTES = 10 * 1024 * 1024; // server ham shu chegarani qo'llaydi
const MAX_DIMENSION = 1920;

// Worker kodi — alohida fayl sifatida joylashtirishning hojati yo'q,
// Blob URL orqali shu yerdan yaratiladi (bitta fayl bilan deploy).
const WORKER_SOURCE = `
self.onmessage = async (e) => {
  const { blob, maxDim, target, id } = e.data;
  try {
    const bmp = await createImageBitmap(blob, { imageOrientation: "from-image" });
    const scale = Math.min(1, maxDim / Math.max(bmp.width, bmp.height));
    const w = Math.max(1, Math.round(bmp.width * scale));
    const h = Math.max(1, Math.round(bmp.height * scale));
    const canvas = new OffscreenCanvas(w, h);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(bmp, 0, 0, w, h);
    bmp.close();
    // Sifatni binary search bilan topamiz — ~6 ta kodlash yetarli.
    let lo = 0.35, hi = 0.92, best = null;
    for (let i = 0; i < 6; i++) {
      const q = (lo + hi) / 2;
      const out = await canvas.convertToBlob({ type: "image/jpeg", quality: q });
      if (out.size <= target) { best = out; lo = q; } else { hi = q; }
      if (hi - lo < 0.04) break;
    }
    if (!best) best = await canvas.convertToBlob({ type: "image/jpeg", quality: 0.35 });
    self.postMessage({ id, ok: true, blob: best });
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err && err.message || err) });
  }
};
`;

let _worker = null;
let _workerJobId = 0;
const _workerJobs = new Map();

function getCompressWorker() {
  if (_worker === false) return null;          // qo'llab-quvvatlanmaydi
  if (_worker) return _worker;
  try {
    if (typeof Worker === "undefined" || typeof OffscreenCanvas === "undefined") {
      _worker = false;
      return null;
    }
    const url = URL.createObjectURL(new Blob([WORKER_SOURCE], { type: "text/javascript" }));
    _worker = new Worker(url);
    URL.revokeObjectURL(url);
    _worker.onmessage = (e) => {
      const job = _workerJobs.get(e.data.id);
      if (!job) return;
      _workerJobs.delete(e.data.id);
      e.data.ok ? job.resolve(e.data.blob) : job.reject(new Error(e.data.error));
    };
    _worker.onerror = () => {
      // Worker ishdan chiqsa — barcha kutayotgan ishlarni rad etamiz va
      // asosiy oqimdagi zaxira yo'lga o'tamiz.
      _workerJobs.forEach((j) => j.reject(new Error("worker error")));
      _workerJobs.clear();
      _worker = false;
    };
    return _worker;
  } catch (_) {
    _worker = false;
    return null;
  }
}

function compressInWorker(blob) {
  const worker = getCompressWorker();
  if (!worker) return Promise.reject(new Error("worker unavailable"));
  const id = ++_workerJobId;
  return new Promise((resolve, reject) => {
    _workerJobs.set(id, { resolve, reject });
    // 20 soniyada javob bo'lmasa — zaxira yo'lga o'tamiz.
    setTimeout(() => {
      if (_workerJobs.has(id)) {
        _workerJobs.delete(id);
        reject(new Error("worker timeout"));
      }
    }, 20000);
    worker.postMessage({ blob, maxDim: MAX_DIMENSION, target: TARGET_BYTES, id });
  });
}

// Faylni rasmga aylantirish. `createImageBitmap` HEIC'da yiqilishi
// mumkin — u holda <img> orqali dekodlaymiz (brauzer HEIC'ni ko'rsata
// olsa, canvas ham chiza oladi).
async function decodeImage(file) {
  try {
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch (_) {
    try {
      return await createImageBitmap(file);
    } catch (_) {
      return await new Promise((resolve, reject) => {
        const url = URL.createObjectURL(file);
        const img = new Image();
        img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
        img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("decode failed")); };
        img.src = url;
      });
    }
  }
}

async function compressOnMainThread(file) {
  const src = await decodeImage(file);
  const sw = src.width || src.naturalWidth;
  const sh = src.height || src.naturalHeight;
  const scale = Math.min(1, MAX_DIMENSION / Math.max(sw, sh));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(src, 0, 0, canvas.width, canvas.height);
  if (src.close) src.close();   // xotira oqmasin (ilgari chaqirilmasdi)

  const encode = (q) => new Promise((res) => canvas.toBlob(res, "image/jpeg", q));
  let lo = 0.35, hi = 0.92, best = null;
  for (let i = 0; i < 6; i++) {
    const q = (lo + hi) / 2;
    const out = await encode(q);
    if (!out) break;
    if (out.size <= TARGET_BYTES) { best = out; lo = q; } else { hi = q; }
    if (hi - lo < 0.04) break;
  }
  if (!best) best = await encode(0.35);
  canvas.width = canvas.height = 0;   // canvas xotirasini darhol bo'shatamiz
  return best;
}

class PhotoTooLargeError extends Error {}

async function compressImageForUpload(file) {
  if (!file) return file;

  let blob = null;
  try {
    blob = await compressInWorker(file);          // 1-yo'l: interfeysni bloklamaydi
  } catch (_) {
    try {
      blob = await compressOnMainThread(file);    // 2-yo'l: zaxira
    } catch (_) {
      blob = null;
    }
  }

  if (blob && blob.size > 0) {
    const base = (file.name || "photo").replace(/\.[^.]+$/, "");
    return new File([blob], base + ".jpg", { type: "image/jpeg" });
  }

  // Siqishning hech qanday yo'li ishlamadi. Ilgari bu holatda ASL fayl
  // jimgina yuborilardi — natijada 5 MB HEIC serverga ketib, Telegram
  // uni rad etardi va xodim tushunarsiz xato ko'rardi. Endi fayl
  // chegaradan kichik bo'lsa o'zini yuboramiz, katta bo'lsa aniq
  // xato beramiz.
  if (file.size <= HARD_MAX_BYTES) return file;
  throw new PhotoTooLargeError("photo_too_large");
}

async function handlePickedFiles(fileList) {
  const files = Array.from(fileList || []);
  if (!files.length || activeSectionId === null) return;

  const sectionId = activeSectionId;
  const existingComment = state.photos[sectionId][0]?.comment || "";

  for (const rawFile of files) {
    let file;
    try {
      file = await compressImageForUpload(rawFile);
    } catch (err) {
      // Rasmni qayta ishlab bo'lmadi (masalan juda katta HEIC) —
      // tushunarli xato ko'rsatamiz, jimgina yuborib qo'ymaymiz.
      await showAlert(t("error_photo_too_large"));
      continue;
    }
    // Foydalanuvchiga darhol (yuklanishi tugashini kutmasdan) lokal
    // preview ko'rsatamiz — ilova "qotib qolganday" tuyulmasin.
    const entry = {
      id: null,
      file,
      previewUrl: URL.createObjectURL(file),
      comment: existingComment,
      uploading: true,
    };
    state.photos[sectionId].push(entry);
    renderSectionCard(sectionId);
    updateProgress();
    attachMainButton();

    try {
      const photo = await uploadDraftPhoto(sectionId, existingComment, file);
      entry.id = photo.id;
      entry.uploading = false;
    } catch (err) {
      // Yuklash muvaffaqiyatsiz bo'lsa — shu rasmni ro'yxatdan olib
      // tashlaymiz va xodimga xabar beramiz (qayta urinib ko'rishi mumkin).
      console.error("[handlePickedFiles] rasm yuklashda xatolik:", err);
      const idx = state.photos[sectionId].indexOf(entry);
      if (idx !== -1) state.photos[sectionId].splice(idx, 1);
      // Xotira oqmasligi uchun preview blob'ini bo'shatamiz.
      if (entry.previewUrl) URL.revokeObjectURL(entry.previewUrl);
      // 429 (juda ko'p so'rov) va 413 (juda katta rasm) uchun alohida,
      // tushunarli xabar — ilgari hammasi umumiy "xatolik" edi.
      const msg = String(err && err.message || "");
      if (msg.includes("429")) await showAlert(t("error_too_many"));
      else if (msg.includes("413")) await showAlert(t("error_photo_too_large"));
      else await showAlert(t("error_submit"));
    }
    renderSectionCard(sectionId);
    updateProgress();
    attachMainButton();
  }
}

function renderSections() {
  const list = document.getElementById("section-list");
  list.innerHTML = "";

  // TUZATILDI — boshi berk ko'cha: agar admin bu filial uchun BARCHA
  // bo'limlarni yashirgan bo'lsa, ilgari ekran bo'm-bo'sh qolardi,
  // "Yuborish" tugmasi hech qachon chiqmasdi va hech qanday izoh
  // ko'rsatilmasdi — xodim nima qilishni bilmay qolardi.
  if (!state.sections.length) {
    const box = document.createElement("div");
    box.className = "sections-empty";
    box.innerHTML =
      `<span class="state-icon">${iconMarkup("info")}</span>` +
      `<h2>${esc(t("sections_empty_title"))}</h2>` +
      `<p>${esc(t("sections_empty_text"))}</p>`;
    list.appendChild(box);
    updateProgress();
    attachMainButton();
    return;
  }

  state.sections.forEach((sec) => {
    if (!state.photos[sec.id]) state.photos[sec.id] = [];

    const card = document.createElement("div");
    card.className = "section-card";
    card.id = `section-${sec.id}`;
    list.appendChild(card);

    renderSectionCard(sec.id);
  });

  updateProgress();
  attachMainButton();
}

function renderSectionCard(sectionId) {
  const sec = state.sections.find((s) => s.id === sectionId);
  const photos = state.photos[sectionId];
  const card = document.getElementById(`section-${sectionId}`);
  const isDone = photos.length > 0;

  card.classList.toggle("done", isDone);
  // To'ldirilmagan bo'limlar ko'zga tashlanib tursin — xodim qaysi
  // bo'lim qolganini ro'yxatdan darhol topadi (ilgari faqat "3 / 8"
  // degan umumiy raqam bor edi, qaysi biri ekani ko'rinmasdi).
  card.classList.toggle("pending", !isDone);

  const thumbsHtml = photos
    .map(
      (p, idx) => `
      <div class="photo-thumb-wrap${p.uploading ? " uploading" : ""}">
        <img class="photo-preview" src="${esc(p.previewUrl)}" />
        <button class="remove-photo-btn" data-section-id="${sectionId}" data-idx="${idx}" ${p.uploading ? "disabled" : ""}>${iconMarkup("close")}</button>
      </div>`
    )
    .join("");

  card.innerHTML = `
    <div class="section-top">
      <div class="section-title" data-required-label="${esc(t("section_required_badge"))}">
        <span class="section-status-icon">${isDone ? iconMarkup("check") : ""}</span>
        <span>${esc(sec.name)}</span>
      </div>
      <span class="photo-count">${photos.length > 0 ? esc(t("photo_count", { n: photos.length })) : ""}</span>
    </div>
    <div class="photos-row">
      ${thumbsHtml}
      <button class="add-photo-btn" data-section-id="${sectionId}">
        ${iconMarkup("plus")}<span>${esc(t("add_photo_btn"))}</span>
      </button>
    </div>
    ${isDone ? `<textarea class="comment-input" rows="2" placeholder="${esc(t("comment_placeholder"))}"></textarea>` : ""}
  `;

  // Izohni innerHTML orqali emas, `value` orqali qo'yamiz — matnda
  // </textarea> bo'lsa ham hech qanday HTML "sinmaydi".
  const commentBox = card.querySelector(".comment-input");
  if (commentBox) commentBox.value = photos[0].comment || "";

  card.querySelector(".add-photo-btn").addEventListener("click", () => {
    activeSectionId = sectionId;
    openCameraCapture();
  });

  card.querySelectorAll(".remove-photo-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      const [removed] = state.photos[sectionId].splice(idx, 1);
      if (removed && removed.id) deleteDraftPhoto(removed.id);
      // Xotira oqmasin — blob URL hech qachon bo'shatilmasdi.
      if (removed && removed.previewUrl) URL.revokeObjectURL(removed.previewUrl);
      renderSectionCard(sectionId);
      updateProgress();
      attachMainButton();
    });
  });

  const commentEl = card.querySelector(".comment-input");
  if (commentEl) {
    commentEl.addEventListener("input", (e) => {
      // Izoh butun bo'lim uchun umumiy (barcha rasmlarga bitta caption qo'shiladi)
      state.photos[sectionId].forEach((p) => (p.comment = e.target.value));
    });
    // Serverga esa faqat yozishni TUGATGANDA (blur) yuboramiz — har bir
    // harf uchun alohida so'rov yubormaslik uchun.
    commentEl.addEventListener("blur", (e) => {
      state.photos[sectionId]
        .filter((p) => p.id)
        .forEach((p) => updateDraftPhotoComment(p.id, e.target.value));
    });
  }
}

cameraInput.addEventListener("change", (e) => {
  // Bu faqat getUserMedia mavjud bo'lmagan/ruxsat berilmagan holatlar
  // uchun ZAXIRA yo'l — asosiy oqim custom kamera UI orqali ishlaydi.
  handlePickedFiles(e.target.files);
  cameraInput.value = ""; // qayta xuddi shu faylni tanlash imkonini saqlaydi
});

function updateProgress() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  document.getElementById("progress-fill").style.width = `${pct}%`;
  document.getElementById("progress-text").textContent = t("sections_progress", { done, total });
}

// ============================================================
//  YUBORISH TUGMASI
//
//  TUZATILDI: ilgari tugma barcha bo'limlar to'lmaguncha butunlay
//  YASHIRILARDI (`hide()`). Xodim kulrang, bosilmaydigan tugmani emas,
//  umuman hech qanday tugmani ko'rmasdi — va nega yo'qligi hech qayerda
//  yozilmasdi. Yangi xodim buni "ilova buzuq" deb tushunardi.
//
//  Endi tugma HAR DOIM ko'rinadi: to'lmaguncha o'chiq (kulrang) va
//  ustida nechta bo'lim qolgani yozilgan bo'ladi, to'lgach yashil
//  "✅ Yuborish" bo'lib faollashadi.
// ============================================================
const MB_DISABLED_BG = "#9AA3AC";
const MB_DISABLED_FG = "#F2F5F7";

function isReportComplete() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  return total > 0 && done === total;
}

function attachMainButton() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  const remaining = total - done;

  // Bu filial uchun bo'lim umuman sozlanmagan — yuboradigan narsa yo'q.
  // Tugma o'rniga ekranda tushunarli xabar ko'rsatiladi (renderSections).
  if (total === 0) {
    tg.MainButton.hide();
    return;
  }

  const themeBg = (tg.themeParams && tg.themeParams.button_color) || "#1F7A5C";
  const themeFg = (tg.themeParams && tg.themeParams.button_text_color) || "#FFFFFF";

  const params = remaining === 0
    ? { text: t("mainbutton_submit"), color: themeBg, text_color: themeFg,
        is_active: true, is_visible: true }
    : { text: t("mainbutton_remaining", { n: remaining }),
        color: MB_DISABLED_BG, text_color: MB_DISABLED_FG,
        is_active: false, is_visible: true };

  try {
    tg.MainButton.setParams(params);
  } catch (_) {
    // Eski Telegram mijozlarida setParams/is_active bo'lmasligi mumkin —
    // o'sha holatda eski usulga qaytamiz.
    tg.MainButton.setText(params.text);
    tg.MainButton.show();
    if (remaining === 0) tg.MainButton.enable();
    else if (tg.MainButton.disable) tg.MainButton.disable();
  }
}

// TUZATILDI: ilgari hech qanday "in-flight" himoyasi yo'q edi —
// MainButton'ni ikki marta bosish ikkita parallel yuborishni boshlardi.
let _submitting = false;
tg.MainButton.onClick(async () => {
  if (_submitting) return;
  // Himoya: `is_active: false` ni qo'llab-quvvatlamaydigan eski Telegram
  // mijozida bosish o'tib ketishi mumkin — shu yerda qayta tekshiramiz.
  if (!isReportComplete()) {
    const total = state.sections.length;
    const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
    await showAlert(t("alert_incomplete", { n: total - done }));
    return;
  }
  _submitting = true;
  try {
    await submitReport();
  } finally {
    _submitting = false;
  }
});

// ---------- 3. Yuborish ----------
// Ekrandagi barcha izohlarni serverga MAJBURIY saqlaydi.
// TUZATILDI: izoh serverga faqat `blur` hodisasida yuborilardi, lekin
// Telegram MainButton — WebView TASHQARISIDAGI native tugma, u bosilganda
// textarea fokusni yo'qotmaydi va `blur` umuman ishlamaydi. Natijada
// xodim izoh yozib darhol "Yuborish" bossa, izoh guruhga tushmasdi va
// xodim buni sezmasdi ham.
async function flushAllComments() {
  const jobs = [];
  document.querySelectorAll(".comment-input").forEach((el) => {
    const card = el.closest(".section-card");
    if (!card) return;
    const sectionId = parseInt(String(card.id).replace("section-", ""), 10);
    const photos = state.photos[sectionId] || [];
    photos.forEach((p) => {
      p.comment = el.value;
      if (p.id) jobs.push(updateDraftPhotoComment(p.id, el.value));
    });
  });
  if (jobs.length) await Promise.allSettled(jobs);
}

async function submitReport() {
  showLoading(t("loading_sending"));
  tg.MainButton.showProgress();

  try {
    await flushAllComments();
    // E'TIBOR: rasmlar bu yerda YUKLANMAYDI — ular xodim rasm olgan
    // zahoti /api/draft/photo orqali allaqachon serverga saqlangan.
    // Shu tufayli bu so'rov juda yengil (faqat matn) va sekin/beqaror
    // internetda ham muvaffaqiyatli yetib borish ehtimoli ancha yuqori.
    // Agar baribir uzilib qolsa (fetchWithRetry avtomatik 2 marta qayta
    // uradi) — qoralama serverda saqlanib qoladi, xodim shunchaki qayta
    // "Yuborish"ni bosishi kifoya, hech narsa qaytadan yuklanmaydi.
    const formData = new FormData();
    formData.append("init_data", initData);
    formData.append("filial_id", state.filial.id);
    formData.append("checklist_type_id", state.checklistType.id);
    formData.append("lang", getLang());

    // TUZATILDI: ilgari bu yerda `retries=3` va 5xx'da ham qayta urinish
    // yoqilgan edi — sekin internetda bu guruhga 2-4 nusxa hisobot
    // tushishiga olib kelardi. Endi so'rov juda yengil (server faqat
    // navbatga yozadi, ~0.2 s), shuning uchun bitta urinish yetarli;
    // ulanish umuman o'rnatilmasa bir marta qayta uriniladi.
    const res = await fetchWithRetry(`${API_BASE}/api/submit`,
      { method: "POST", body: formData }, 1, 1200, 30000, false);

    if (!res.ok) {
      const bodyText = await res.text();
      let detail = bodyText;
      try {
        detail = (JSON.parse(bodyText).detail) || bodyText;
      } catch (_) { /* JSON emas — xom matn ishlatiladi */ }

      // 409 = hisobot allaqachon qabul qilingan (masalan tugma ikki marta
      // bosilgan). Bu XATO EMAS — muvaffaqiyat deb ko'rsatamiz, aks holda
      // xodim allaqachon yuborilgan hisobotni qayta yuborishga urinadi.
      if (res.status === 409) {
        state.photos = {};
        hideLoading();
        tg.MainButton.hideProgress();
        tg.MainButton.hide();
        showScreen("screen-success");
        return;
      }
      throw new Error(detail || `HTTP ${res.status}`);
    }

    state.photos = {};

    hideLoading();
    tg.MainButton.hideProgress();
    tg.MainButton.hide();
    showScreen("screen-success");
    tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    console.error("[submitReport] yuborishda xatolik:", e);
    hideLoading();
    tg.MainButton.hideProgress();
    tg.HapticFeedback.notificationOccurred("error");
    // Rasmlar serverda xavfsiz saqlanib qolgani uchun, xodim shunchaki
    // "Yuborish"ni qayta bosishi mumkin — hech narsa qaytadan olinmaydi.
    // Xatoning ANIQ matnini ham ko'rsatamiz — shu bilan muammo takrorlansa,
    // xodim skrinshot orqali aniq sababni yuborishi mumkin bo'ladi
    // (umumiy "xatolik" deyishning o'rniga).
    await showAlert(`${t("error_submit")}\n\n${e.message || e}`);
  }
}

document.getElementById("btn-close").addEventListener("click", () => tg.close());

// ============================================================
//  ADMIN PANEL (faqat superadmin uchun)
// ============================================================

// ---------- Tablar ----------
document.querySelectorAll(".admin-tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".admin-tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".admin-tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(btn.dataset.tab).classList.add("active");
  });
});

// Admin panelga qaytish (hisobot rejimidan)
document.getElementById("btn-back-to-admin").addEventListener("click", () => {
  showScreen("screen-admin");
});
document.getElementById("btn-goto-report").addEventListener("click", async () => {
  showLoading(t("loading_default"));
  await refreshFilialList();
  hideLoading();
  showScreen("screen-filial");
});

function adminForm(extraFields) {
  const fd = new FormData();
  fd.append("init_data", initData);
  Object.entries(extraFields).forEach(([k, v]) => fd.append(k, v));
  return fd;
}

async function adminFetch(path, options = {}) {
  // TUZATILDI: timeout yo'q edi — ulanish osilsa admin panel abadiy
  // "Yuklanmoqda" holatida qolardi. GET uchun qayta urinish xavfsiz,
  // POST/PUT/DELETE uchun esa faqat ulanish o'rnatilmagan holatda.
  const isRead = !options.method || String(options.method).toUpperCase() === "GET";
  const res = await fetchWithRetry(`${API_BASE}${path}`, options, isRead ? 2 : 1, 900, 20000, isRead);
  if (!res.ok) {
    let detail = t("error_generic");
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

// ---------- Userlar ----------
async function loadAdminUsers() {
  const list = document.getElementById("users-list");
  list.innerHTML = `<p class="hint">${t("loading_default")}</p>`;
  try {
    const data = await adminFetch(`/api/admin/users?init_data=${encodeURIComponent(initData)}`);
    list.innerHTML = "";
    if (!data.users.length) {
      list.innerHTML = `<p class="hint">${t("users_none")}</p>`;
      return;
    }

    function renderUserRow(u) {
      const el = document.createElement("div");
      el.className = "admin-list-item" + (u.is_superadmin ? " is-superadmin" : "");
      el.innerHTML = `
        <div class="admin-list-main">
          <div class="admin-list-title">${esc(u.full_name || t("users_no_name"))} ${u.is_superadmin ? `<span class="badge">${iconMarkup("crown")}</span>` : ""}</div>
          <div class="admin-list-sub">${t("users_id_label", { id: u.telegram_user_id })}</div>
        </div>
        <div class="admin-list-actions">
          <button class="icon-btn" data-action="edit" aria-label="${t("edit_label")}">${iconMarkup("edit")}</button>
          <button class="icon-btn danger" data-action="delete" aria-label="${t("delete_label")}">${iconMarkup("trash")}</button>
        </div>
      `;
      el.querySelector('[data-action="edit"]').addEventListener("click", () => editUser(u));
      el.querySelector('[data-action="delete"]').addEventListener("click", () => deleteUser(u));
      return el;
    }

    // Superadminlar oddiy adminlardan DIZAYNDA aniq ajralib turishi
    // uchun ikkita alohida guruhga bo'lib ko'rsatiladi (backend/ma'lumot
    // tuzilishi o'zgarmaydi — faqat ko'rinish).
    const superadmins = data.users.filter((u) => u.is_superadmin);
    const regularAdmins = data.users.filter((u) => !u.is_superadmin);

    if (superadmins.length) {
      const title = document.createElement("div");
      title.className = "admin-list-group-title is-superadmin";
      title.textContent = `${t("users_group_superadmins")} · ${superadmins.length}`;
      list.appendChild(title);
      superadmins.forEach((u) => list.appendChild(renderUserRow(u)));
    }

    if (regularAdmins.length) {
      const title = document.createElement("div");
      title.className = "admin-list-group-title";
      title.textContent = `${t("users_group_admins")} · ${regularAdmins.length}`;
      list.appendChild(title);
      regularAdmins.forEach((u) => list.appendChild(renderUserRow(u)));
    }
  } catch (e) {
    list.innerHTML = `<p class="hint">${esc(t("load_error_prefix"))}${esc(e.message)}</p>`;
  }
}

document.getElementById("btn-add-user").addEventListener("click", async () => {
  const idInput = document.getElementById("new-user-id");
  const nameInput = document.getElementById("new-user-name");
  const saCheckbox = document.getElementById("new-user-superadmin");

  const telegramUserId = idInput.value.trim();
  if (!telegramUserId || !/^\d+$/.test(telegramUserId)) {
    await showAlert(t("users_id_numeric_error"));
    return;
  }

  showLoading(t("loading_adding"));
  try {
    await adminFetch("/api/admin/users", {
      method: "POST",
      body: adminForm({
        telegram_user_id: telegramUserId,
        full_name: nameInput.value.trim(),
        is_superadmin: saCheckbox.checked,
      }),
    });
    idInput.value = "";
    nameInput.value = "";
    saCheckbox.checked = false;
    await loadAdminUsers();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
});

async function editUser(u) {
  const result = await showPrompt({
    title: t("users_edit_title"),
    confirmText: t("btn_save"),
    fields: [
      { id: "full_name", label: t("users_name_label"), value: u.full_name || "" },
      { id: "is_superadmin", label: t("users_superadmin_checkbox"), type: "checkbox", checked: !!u.is_superadmin },
    ],
  });
  if (!result) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/users/${u.id}`, {
      method: "PUT",
      body: adminForm({ full_name: result.full_name, is_superadmin: result.is_superadmin }),
    });
    await loadAdminUsers();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

async function deleteUser(u) {
  const ok = await showConfirm(t("users_delete_confirm", { name: u.full_name || u.telegram_user_id }), {
    title: t("users_delete_title"),
    confirmText: t("btn_delete"),
    danger: true,
  });
  if (!ok) return;

  showLoading(t("loading_deleting"));
  try {
    await adminFetch(`/api/admin/users/${u.id}?init_data=${encodeURIComponent(initData)}`, {
      method: "DELETE",
    });
    await loadAdminUsers();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

// ---------- Filiallar ----------
async function loadAdminFilials() {
  const list = document.getElementById("filials-list");
  list.innerHTML = `<p class="hint">${t("loading_default")}</p>`;
  try {
    const data = await adminFetch(`/api/admin/filials?init_data=${encodeURIComponent(initData)}`);
    list.innerHTML = "";
    if (!data.filials.length) {
      list.innerHTML = `<p class="hint">${t("filials_none")}</p>`;
      return;
    }
    data.filials.forEach((f) => {
      const el = document.createElement("div");
      el.className = "admin-list-item" + (f.is_active ? "" : " is-inactive");
      el.innerHTML = `
        <div class="admin-list-main">
          <div class="admin-list-title">${esc(f.name)} ${f.is_active ? "" : `<span class="badge-text">${t("inactive_badge")}</span>`}</div>
          <div class="admin-list-sub">${t("filials_meta", { id: f.id, topic: f.thread_id ? `#${f.thread_id}` : t("filials_topic_unlinked") })}</div>
        </div>
        <div class="admin-list-actions">
          <button class="icon-btn active-toggle ${f.is_active ? "" : "is-off"}" data-action="toggle" aria-label="${f.is_active ? t("toggle_deactivate_label") : t("toggle_activate_label")}">${iconMarkup(f.is_active ? "eye" : "eyeOff")}</button>
          <button class="icon-btn" data-action="link" aria-label="${t("link_topic_title")}" title="${t("link_topic_tooltip")}">${iconMarkup("link")}</button>
          <button class="icon-btn" data-action="edit" aria-label="${t("edit_label")}">${iconMarkup("edit")}</button>
          <button class="icon-btn danger" data-action="delete" aria-label="${t("delete_label")}">${iconMarkup("trash")}</button>
        </div>
      `;
      el.querySelector('[data-action="toggle"]').addEventListener("click", () => toggleFilialActive(f));
      el.querySelector('[data-action="link"]').addEventListener("click", () => linkFilialThread(f));
      el.querySelector('[data-action="edit"]').addEventListener("click", () => editFilial(f));
      el.querySelector('[data-action="delete"]').addEventListener("click", () => deleteFilial(f));
      list.appendChild(el);
    });
  } catch (e) {
    list.innerHTML = `<p class="hint">${esc(t("load_error_prefix"))}${esc(e.message)}</p>`;
  }
}

document.getElementById("btn-add-filial").addEventListener("click", async () => {
  const nameInput = document.getElementById("new-filial-name");
  const name = nameInput.value.trim();
  if (!name) {
    await showAlert(t("filials_name_required"));
    return;
  }

  showLoading(t("loading_adding"));
  try {
    await adminFetch("/api/admin/filials", {
      method: "POST",
      body: adminForm({ name }),
    });
    nameInput.value = "";
    await loadAdminFilials();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
});

async function linkFilialThread(f) {
  const result = await showPrompt({
    title: t("link_topic_title"),
    confirmText: t("btn_link"),
    fields: [
      {
        id: "thread_id",
        label: t("link_field_label"),
        value: f.thread_id || "",
      },
    ],
  });
  if (!result || !result.thread_id) return;

  const threadId = parseInt(result.thread_id, 10);
  if (!Number.isInteger(threadId) || threadId <= 0) {
    await showAlert(t("link_id_error"));
    return;
  }

  showLoading(t("loading_linking"));
  try {
    await adminFetch(`/api/admin/filials/${f.id}/thread`, {
      method: "PUT",
      body: adminForm({ thread_id: threadId }),
    });
    await loadAdminFilials();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

async function editFilial(f) {
  const result = await showPrompt({
    title: t("filials_edit_title"),
    confirmText: t("btn_save"),
    fields: [{ id: "name", label: t("filials_name_label"), value: f.name }],
  });
  if (!result || !result.name) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/filials/${f.id}`, {
      method: "PUT",
      body: adminForm({ name: result.name, is_active: f.is_active }),
    });
    await loadAdminFilials();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

// Ko'z icon: filialni butunlay o'chirmasdan, faqat foydalanuvchilarga
// ko'rinish/ko'rinmasligini boshqaradi (superadmin xohlagan payt qayta
// faollashtirishi mumkin).
async function toggleFilialActive(f) {
  const makingInactive = f.is_active;
  const ok = await showConfirm(
    makingInactive
      ? t("filials_toggle_off_confirm", { name: f.name })
      : t("filials_toggle_on_confirm", { name: f.name }),
    {
      title: makingInactive ? t("filials_toggle_off_title") : t("filials_toggle_on_title"),
      confirmText: makingInactive ? t("toggle_deactivate_label") : t("toggle_activate_label"),
    }
  );
  if (!ok) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/filials/${f.id}/active`, {
      method: "PUT",
      body: adminForm({ is_active: !makingInactive }),
    });
    await loadAdminFilials();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

async function deleteFilial(f) {
  const ok = await showConfirm(
    t("filials_delete_confirm", { name: f.name }),
    { title: t("filials_delete_title"), confirmText: t("btn_delete_permanent"), danger: true }
  );
  if (!ok) return;

  showLoading(t("loading_deleting"));
  try {
    await adminFetch(`/api/admin/filials/${f.id}?init_data=${encodeURIComponent(initData)}`, {
      method: "DELETE",
    });
    await loadAdminFilials();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

// ---------- Bo'limlar (har bir chek-list turi uchun alohida) ----------
let adminSelectedChecklistTypeId = null;

async function initAdminSections() {
  const subtabsEl = document.getElementById("section-checklist-subtabs");
  subtabsEl.innerHTML = `<p class="hint">${t("loading_default")}</p>`;
  try {
    const data = await adminFetch(`/api/admin/checklist-types?init_data=${encodeURIComponent(initData)}`);
    const types = data.checklist_types;
    subtabsEl.innerHTML = "";
    if (!types.length) {
      subtabsEl.innerHTML = `<p class="hint">${t("sections_types_none")}</p>`;
      return;
    }
    if (adminSelectedChecklistTypeId === null || !types.some((ct) => ct.id === adminSelectedChecklistTypeId)) {
      adminSelectedChecklistTypeId = types[0].id;
    }
    types.forEach((ct) => {
      const wrap = document.createElement("div");
      wrap.className = "admin-checklist-tab-wrap";

      const btn = document.createElement("button");
      btn.className = "admin-tab-btn" + (ct.id === adminSelectedChecklistTypeId ? " active" : "");
      btn.textContent = `${CHECKLIST_TYPE_EMOJI[ct.key] || "📋"} ${pickLocalized(ct)}`;
      btn.addEventListener("click", () => {
        adminSelectedChecklistTypeId = ct.id;
        subtabsEl.querySelectorAll(".admin-tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        loadAdminSections();
      });

      const editBtn = document.createElement("button");
      editBtn.className = "icon-btn admin-checklist-tab-edit";
      editBtn.setAttribute("aria-label", t("edit_label"));
      editBtn.innerHTML = iconMarkup("edit");
      editBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        editChecklistType(ct);
      });

      wrap.appendChild(btn);
      wrap.appendChild(editBtn);
      subtabsEl.appendChild(wrap);
    });
    await loadAdminSections();
  } catch (e) {
    subtabsEl.innerHTML = `<p class="hint">${esc(t("load_error_prefix"))}${esc(e.message)}</p>`;
  }
}

async function loadAdminSections() {
  const list = document.getElementById("sections-list");
  if (adminSelectedChecklistTypeId === null) return;
  list.innerHTML = `<p class="hint">${t("loading_default")}</p>`;
  try {
    const data = await adminFetch(
      `/api/admin/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${adminSelectedChecklistTypeId}`
    );
    list.innerHTML = "";
    if (!data.sections.length) {
      list.innerHTML = `<p class="hint">${t("sections_none")}</p>`;
      destroySectionsSortable();
      return;
    }
    data.sections.forEach((s) => {
      const el = document.createElement("div");
      el.className = "admin-list-item section-list-item" + (s.is_active ? "" : " is-inactive");
      el.dataset.sectionId = s.id;
      el.innerHTML = `
        <span class="drag-handle" aria-label="${t("sections_drag_label")}">${iconMarkup("drag")}</span>
        <div class="admin-list-main">
          <div class="admin-list-title section-list-title">${esc(pickLocalized(s))} ${s.is_active ? "" : `<span class="badge-text">${t("inactive_badge")}</span>`}</div>
        </div>
        <div class="admin-list-actions">
          <button class="icon-btn" data-action="visibility" aria-label="${t("sections_visibility_label")}">${iconMarkup("building")}</button>
          <button class="icon-btn active-toggle ${s.is_active ? "" : "is-off"}" data-action="toggle" aria-label="${s.is_active ? t("toggle_deactivate_label") : t("toggle_activate_label")}">${iconMarkup(s.is_active ? "eye" : "eyeOff")}</button>
          <button class="icon-btn" data-action="edit" aria-label="${t("edit_label")}">${iconMarkup("edit")}</button>
          <button class="icon-btn danger" data-action="delete" aria-label="${t("delete_label")}">${iconMarkup("trash")}</button>
        </div>
      `;
      el.querySelector('[data-action="visibility"]').addEventListener("click", () => manageSectionVisibility(s));
      el.querySelector('[data-action="toggle"]').addEventListener("click", () => toggleSectionActive(s));
      el.querySelector('[data-action="edit"]').addEventListener("click", () => editSection(s));
      el.querySelector('[data-action="delete"]').addEventListener("click", () => deleteSection(s));
      list.appendChild(el);
    });
    initSectionsSortable(list);
  } catch (e) {
    list.innerHTML = `<p class="hint">${esc(t("load_error_prefix"))}${esc(e.message)}</p>`;
    destroySectionsSortable();
  }
}

// ---------- Bo'limlar tartibini drag-and-drop bilan o'zgartirish ----------
// Superadmin bu yerda bo'limlarni ushlab surishi bilan yangi tartib
// darhol backendga yuboriladi — shundan keyin BARCHA xodimlar
// (`/api/sections`) ham aynan shu tartibda ko'radi.
let sectionsSortableInstance = null;

function destroySectionsSortable() {
  if (sectionsSortableInstance) {
    sectionsSortableInstance.destroy();
    sectionsSortableInstance = null;
  }
}

function initSectionsSortable(list) {
  destroySectionsSortable();
  if (typeof Sortable === "undefined") return; // CDN yuklanmagan bo'lsa — jim tarzda o'tkazib yuboriladi
  sectionsSortableInstance = Sortable.create(list, {
    handle: ".drag-handle",
    animation: 150,
    ghostClass: "sortable-ghost",
    chosenClass: "sortable-chosen",
    onEnd: async () => {
      const orderedIds = Array.from(list.children)
        .map((el) => parseInt(el.dataset.sectionId, 10))
        .filter((id) => !Number.isNaN(id));
      try {
        await adminFetch("/api/admin/sections/reorder", {
          method: "PUT",
          body: adminForm({
            checklist_type_id: adminSelectedChecklistTypeId,
            ordered_section_ids: JSON.stringify(orderedIds),
          }),
        });
      } catch (e) {
        await showAlert(t("error_prefix") + e.message);
        await loadAdminSections(); // xatolik bo'lsa — serverdagi haqiqiy tartibga qaytaramiz
      }
    },
  });
}

// Bo'limni qaysi filial(lar)da YASHIRISH kerakligini boshqarish modali —
// masalan "Tashqi hudud va fasad fotosi" bo'limi barcha filiallarda
// default ko'rinadi, lekin foodcourt ichidagi filialda tashqi hudud
// umuman yo'q bo'lgani uchun shu yerdan o'sha filial uchun o'chirib
// qo'yish mumkin. Checkbox BELGILANGAN = shu filialda ko'rinadi.
async function manageSectionVisibility(s) {
  showLoading(t("loading_default"));
  let filials, hiddenIds;
  try {
    const [filialsData, hiddenData] = await Promise.all([
      adminFetch(`/api/admin/filials?init_data=${encodeURIComponent(initData)}`),
      adminFetch(`/api/admin/sections/${s.id}/hidden-filials?init_data=${encodeURIComponent(initData)}`),
    ]);
    filials = filialsData.filials.filter((f) => f.is_active);
    hiddenIds = new Set(hiddenData.hidden_filial_ids);
  } catch (e) {
    hideLoading();
    await showAlert(t("error_prefix") + e.message);
    return;
  }
  hideLoading();

  if (!filials.length) {
    await showAlert(t("sections_visibility_no_filials"));
    return;
  }

  const fields = filials.map((f) => ({
    id: `filial_${f.id}`,
    label: f.name,
    type: "checkbox",
    checked: !hiddenIds.has(f.id),
  }));

  const result = await showPrompt({
    title: t("sections_visibility_title", { name: pickLocalized(s) }),
    message: t("sections_visibility_hint"),
    fields,
  });
  if (!result) return;

  const newHiddenIds = filials.filter((f) => !result[`filial_${f.id}`]).map((f) => f.id);

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/sections/${s.id}/hidden-filials`, {
      method: "PUT",
      body: adminForm({ hidden_filial_ids: JSON.stringify(newHiddenIds) }),
    });
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

document.getElementById("btn-add-section").addEventListener("click", async () => {
  const nameInput = document.getElementById("new-section-name");
  const name = nameInput.value.trim();
  if (!name) {
    await showAlert(t("sections_name_required"));
    return;
  }
  if (adminSelectedChecklistTypeId === null) {
    await showAlert(t("sections_select_checklist_first"));
    return;
  }

  showLoading(t("loading_adding"));
  try {
    await adminFetch("/api/admin/sections", {
      method: "POST",
      body: adminForm({
        name,
        lang: getLang(),
        checklist_type_id: adminSelectedChecklistTypeId,
      }),
    });
    nameInput.value = "";
    await loadAdminSections();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
});

async function editSection(s) {
  const result = await showPrompt({
    title: t("sections_edit_title"),
    confirmText: t("btn_save"),
    fields: [{ id: "name", label: t("sections_name_label"), value: pickLocalized(s) }],
  });
  if (!result || !result.name) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/sections/${s.id}`, {
      method: "PUT",
      body: adminForm({ name: result.name, lang: getLang(), is_active: s.is_active }),
    });
    await loadAdminSections();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

// Superadmin smena nomini (masalan "Smena ochilishi") tahrirlaydi —
// bo'lim nomini tahrirlash bilan bir xil naqsh: faqat joriy tilda
// kiritiladi, qolgan ikki til avtomatik tarjima qilinadi. `key`
// (opening/handover/closing) o'zgarmaydi.
async function editChecklistType(ct) {
  const result = await showPrompt({
    title: t("checklist_type_edit_title"),
    confirmText: t("btn_save"),
    fields: [{ id: "name", label: t("checklist_type_name_label"), value: pickLocalized(ct) }],
  });
  if (!result || !result.name) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/checklist-types/${ct.id}`, {
      method: "PUT",
      body: adminForm({ name: result.name, lang: getLang() }),
    });
    await initAdminSections();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

async function toggleSectionActive(s) {
  const makingInactive = s.is_active;
  const ok = await showConfirm(
    makingInactive
      ? t("sections_toggle_off_confirm", { name: pickLocalized(s) })
      : t("sections_toggle_on_confirm", { name: pickLocalized(s) }),
    {
      title: makingInactive ? t("sections_toggle_off_title") : t("sections_toggle_on_title"),
      confirmText: makingInactive ? t("toggle_deactivate_label") : t("toggle_activate_label"),
    }
  );
  if (!ok) return;

  showLoading(t("loading_saving"));
  try {
    await adminFetch(`/api/admin/sections/${s.id}/active`, {
      method: "PUT",
      body: adminForm({ is_active: !makingInactive }),
    });
    await loadAdminSections();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

async function deleteSection(s) {
  const ok = await showConfirm(
    t("sections_delete_confirm", { name: pickLocalized(s) }),
    { title: t("sections_delete_title"), confirmText: t("btn_delete_permanent"), danger: true }
  );
  if (!ok) return;

  showLoading(t("loading_deleting"));
  try {
    await adminFetch(`/api/admin/sections/${s.id}?init_data=${encodeURIComponent(initData)}`, {
      method: "DELETE",
    });
    await loadAdminSections();
  } catch (e) {
    await showAlert(t("error_prefix") + e.message);
  } finally {
    hideLoading();
  }
}

// ============================================================
//  Til o'zgarganda joriy ekrandagi dinamik matnlarni yangilash
//  (statik matnlar i18n.js tomonidan avtomatik yangilanadi)
// ============================================================
async function onLangChange() {
  const activeScreen = document.querySelector(".screen.active");
  const activeId = activeScreen ? activeScreen.id : null;

  if (activeId === "screen-checklist") {
    await refetchChecklistTypes();
    renderChecklistTypes();
  } else if (activeId === "screen-sections") {
    await refetchSections();
    if (state.checklistType) {
      document.getElementById("checklist-name-subtitle").textContent =
        `${CHECKLIST_TYPE_EMOJI[state.checklistType.key] || "📋"} ${state.checklistType.name}`;
    }
    renderSections();
  } else if (activeId === "screen-admin") {
    loadAdminUsers();
    loadAdminFilials();
    initAdminSections();
  } else if (activeId === "screen-filial") {
    // Chek-list turlari keshini fonda yangilab qo'yamiz, shunda
    // foydalanuvchi filialni tanlaganda keyingi ekran to'g'ri tilda
    // ochiladi.
    refetchChecklistTypes();
  }

  // MainButton matnini yangilash (agar hozir ko'rsatilayotgan bo'lsa)
  if (state.sections && state.sections.length) {
    attachMainButton();
  }
}

// ---------- Ishga tushirish ----------
loadFilials();
