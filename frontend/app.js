// ============================================================
//  Filial Feedback Mini App — frontend logikasi
// ============================================================

const API_BASE = "https://rgc.up.railway.app";// <-- backend manzilini shu yerga qo'ying

const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData; // backendga validatsiya uchun yuboriladi

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
  photos: {},               // section_id -> [{file, previewUrl, comment}, ...]
};

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
              ${f.label}
            </label>`;
        }
        return `
          <div>
            <label class="modal-field-label" for="modal-field-${f.id}">${f.label}</label>
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
    el.innerHTML = `<span>${f.name}</span><span class="arrow">${iconMarkup("chevron")}</span>`;
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
    const res = await fetch(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`);
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
    const res = await fetch(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`);

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
      showScreen("screen-filial");
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
    el.innerHTML = `<span>${CHECKLIST_TYPE_EMOJI[ct.key] || "📋"} ${ct.name}</span><span class="arrow">${iconMarkup("chevron")}</span>`;
    el.addEventListener("click", () => selectChecklistType(ct));
    list.appendChild(el);
  });
}

document.getElementById("btn-back-to-filial").addEventListener("click", async () => {
  showScreen("screen-filial");
  await refreshFilialList();
});

// Til almashtirilganda ekranda hozir ko'rinib turgan chek-list turlari /
// bo'limlar nomlarini yangi tilda bazadan qayta yuklaydi (bular bazada
// har bir til uchun alohida saqlanadi, shu sabab faqat statik matnlarni
// qayta chizish yetarli emas — backenddan yangi tilda qayta so'ralishi
// kerak).
async function refetchChecklistTypes() {
  try {
    const res = await fetch(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}&lang=${getLang()}`);
    if (!res.ok) return;
    const data = await res.json();
    state.checklistTypes = data.checklist_types;
  } catch (_) {}
}

async function refetchSections() {
  if (!state.checklistType) return;
  try {
    const res = await fetch(
      `${API_BASE}/api/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${state.checklistType.id}&filial_id=${state.filial.id}&lang=${getLang()}`
    );
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
    const res = await fetch(
      `${API_BASE}/api/sections?init_data=${encodeURIComponent(initData)}&checklist_type_id=${checklistType.id}&filial_id=${state.filial.id}&lang=${getLang()}`
    );
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    state.checklistType = checklistType;
    state.sections = data.sections;
    state.photos = {};

    document.getElementById("filial-name-title").textContent = state.filial.name;
    document.getElementById("checklist-name-subtitle").textContent =
      `${CHECKLIST_TYPE_EMOJI[checklistType.key] || "📋"} ${checklistType.name}`;

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

function renderSections() {
  const list = document.getElementById("section-list");
  list.innerHTML = "";

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

  const thumbsHtml = photos
    .map(
      (p, idx) => `
      <div class="photo-thumb-wrap">
        <img class="photo-preview" src="${p.previewUrl}" />
        <button class="remove-photo-btn" data-section-id="${sectionId}" data-idx="${idx}">${iconMarkup("close")}</button>
      </div>`
    )
    .join("");

  card.innerHTML = `
    <div class="section-top">
      <div class="section-title">
        <span class="section-status-icon">${isDone ? iconMarkup("check") : ""}</span>
        <span>${sec.name}</span>
      </div>
      <span class="photo-count">${photos.length > 0 ? t("photo_count", { n: photos.length }) : ""}</span>
    </div>
    <div class="photos-row">
      ${thumbsHtml}
      <button class="add-photo-btn" data-section-id="${sectionId}">
        ${iconMarkup("plus")}<span>${t("add_photo_btn")}</span>
      </button>
    </div>
    ${isDone ? `<textarea class="comment-input" rows="2" placeholder="${t("comment_placeholder")}">${photos[0].comment || ""}</textarea>` : ""}
  `;

  card.querySelector(".add-photo-btn").addEventListener("click", () => {
    activeSectionId = sectionId;
    cameraInput.click();
  });

  card.querySelectorAll(".remove-photo-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = parseInt(btn.dataset.idx, 10);
      state.photos[sectionId].splice(idx, 1);
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
  }
}

cameraInput.addEventListener("change", (e) => {
  const files = Array.from(e.target.files || []);
  if (!files.length || activeSectionId === null) return;

  const existingComment = state.photos[activeSectionId][0]?.comment || "";
  files.forEach((file) => {
    state.photos[activeSectionId].push({
      file,
      previewUrl: URL.createObjectURL(file),
      comment: existingComment,
    });
  });

  renderSectionCard(activeSectionId);
  updateProgress();
  attachMainButton();

  cameraInput.value = ""; // qayta xuddi shu faylni tanlash imkonini saqlaydi
});

function updateProgress() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  document.getElementById("progress-fill").style.width = `${pct}%`;
  document.getElementById("progress-text").textContent = t("sections_progress", { done, total });
}

function attachMainButton() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  const allDone = total > 0 && done === total;

  tg.MainButton.setText(t("mainbutton_submit"));
  if (allDone) {
    tg.MainButton.show();
    tg.MainButton.enable();
  } else {
    tg.MainButton.hide();
  }
}

tg.MainButton.onClick(async () => {
  await submitReport();
});

// ---------- 3. Yuborish ----------
async function submitReport() {
  showLoading(t("loading_sending"));
  tg.MainButton.showProgress();

  try {
    const formData = new FormData();
    formData.append("init_data", initData);
    formData.append("filial_id", state.filial.id);
    formData.append("checklist_type_id", state.checklistType.id);
    formData.append("lang", getLang());

    const meta = [];
    state.sections.forEach((sec) => {
      const photos = state.photos[sec.id] || [];
      photos.forEach((p) => {
        meta.push({ section_id: sec.id, section_name: sec.name, comment: p.comment });
        formData.append("files", p.file, `section_${sec.id}_${Date.now()}_${Math.random().toString(36).slice(2)}.jpg`);
      });
    });
    formData.append("items_meta", JSON.stringify(meta));

    const res = await fetch(`${API_BASE}/api/submit`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(await res.text());

    hideLoading();
    tg.MainButton.hideProgress();
    tg.MainButton.hide();
    showScreen("screen-success");
    tg.HapticFeedback.notificationOccurred("success");
  } catch (e) {
    hideLoading();
    tg.MainButton.hideProgress();
    tg.HapticFeedback.notificationOccurred("error");
    await showAlert(t("error_submit"));
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
  const res = await fetch(`${API_BASE}${path}`, options);
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
          <div class="admin-list-title">${u.full_name || t("users_no_name")} ${u.is_superadmin ? `<span class="badge">${iconMarkup("crown")}</span>` : ""}</div>
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
    list.innerHTML = `<p class="hint">${t("load_error_prefix")}${e.message}</p>`;
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
          <div class="admin-list-title">${f.name} ${f.is_active ? "" : `<span class="badge-text">${t("inactive_badge")}</span>`}</div>
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
    list.innerHTML = `<p class="hint">${t("load_error_prefix")}${e.message}</p>`;
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
      const btn = document.createElement("button");
      btn.className = "admin-tab-btn" + (ct.id === adminSelectedChecklistTypeId ? " active" : "");
      btn.textContent = `${CHECKLIST_TYPE_EMOJI[ct.key] || "📋"} ${pickLocalized(ct)}`;
      btn.addEventListener("click", () => {
        adminSelectedChecklistTypeId = ct.id;
        subtabsEl.querySelectorAll(".admin-tab-btn").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        loadAdminSections();
      });
      subtabsEl.appendChild(btn);
    });
    await loadAdminSections();
  } catch (e) {
    subtabsEl.innerHTML = `<p class="hint">${t("load_error_prefix")}${e.message}</p>`;
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
          <div class="admin-list-title section-list-title">${pickLocalized(s)} ${s.is_active ? "" : `<span class="badge-text">${t("inactive_badge")}</span>`}</div>
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
    list.innerHTML = `<p class="hint">${t("load_error_prefix")}${e.message}</p>`;
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
