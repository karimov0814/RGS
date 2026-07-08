// ============================================================
//  Filial Feedback Mini App — frontend logikasi
// ============================================================

const API_BASE = "https://rgc.up.railway.app";// <-- backend manzilini shu yerga qo'ying

const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const initData = tg.initData; // backendga validatsiya uchun yuboriladi

// Rol tanlash ekrani olib tashlandi — hozircha barcha yuborishlar "employee"
// sifatida belgilanadi. Kelajakda mehmon oqimi kerak bo'lsa, shu qiymatni
// dinamik qilish kifoya.
const ROLE = "employee";

// ---------- Holat (state) ----------
const state = {
  filial: null,     // {id, name}
  sections: [],      // [{id, name}]
  photos: {},         // section_id -> [{file, previewUrl, comment}, ...]
};

// ---------- Ekranlarni almashtirish ----------
function showScreen(id) {
  document.querySelectorAll(".screen").forEach((el) => el.classList.remove("active"));
  document.getElementById(id).classList.add("active");
}

function showLoading(text) {
  document.getElementById("loading-text").textContent = text || "Yuklanmoqda...";
  document.getElementById("overlay-loading").classList.remove("hidden");
}
function hideLoading() {
  document.getElementById("overlay-loading").classList.add("hidden");
}

// ---------- 1. Filial tanlash (ilova ochilishi bilan) ----------
async function loadFilials() {
  showLoading("Yuklanmoqda...");
  try {
    const res = await fetch(`${API_BASE}/api/config?init_data=${encodeURIComponent(initData)}`);
    const data = await res.json();
    state.sections = data.sections;

    const list = document.getElementById("filial-list");
    list.innerHTML = "";
    data.filials.forEach((f) => {
      const el = document.createElement("div");
      el.className = "filial-item";
      el.innerHTML = `<span>${f.name}</span><span class="arrow">›</span>`;
      el.addEventListener("click", () => selectFilial(f));
      list.appendChild(el);
    });

    hideLoading();
    showScreen("screen-filial");
  } catch (e) {
    hideLoading();
    alert("Ma'lumotlarni yuklab bo'lmadi. Qayta urinib ko'ring.");
  }
}

function selectFilial(filial) {
  state.filial = filial;
  state.photos = {};
  document.getElementById("filial-name-title").textContent = filial.name;
  renderSections();
  showScreen("screen-sections");
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
        <button class="remove-photo-btn" data-section-id="${sectionId}" data-idx="${idx}">×</button>
      </div>`
    )
    .join("");

  card.innerHTML = `
    <div class="section-top">
      <div class="section-title">
        <span class="section-status-icon">${isDone ? "✅" : "⬜"}</span>
        <span>${sec.name}</span>
      </div>
      <span class="photo-count">${photos.length > 0 ? photos.length + " ta rasm" : ""}</span>
    </div>
    <div class="photos-row">
      ${thumbsHtml}
      <button class="add-photo-btn" data-section-id="${sectionId}">
        <span>➕</span><span>Rasm qo'shish</span>
      </button>
    </div>
    ${isDone ? `<textarea class="comment-input" rows="2" placeholder="Izoh (ixtiyoriy)">${photos[0].comment || ""}</textarea>` : ""}
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
  document.getElementById("progress-text").textContent = `${done} / ${total} bo'lim`;
}

function attachMainButton() {
  const total = state.sections.length;
  const done = state.sections.filter((s) => state.photos[s.id]?.length > 0).length;
  const allDone = total > 0 && done === total;

  tg.MainButton.setText("✅ Yuborish");
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
  showLoading("Yuborilmoqda...");
  tg.MainButton.showProgress();

  try {
    const formData = new FormData();
    formData.append("init_data", initData);
    formData.append("filial_id", state.filial.id);
    formData.append("role", ROLE);

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
    alert("Yuborishda xatolik yuz berdi. Qayta urinib ko'ring.");
  }
}

document.getElementById("btn-close").addEventListener("click", () => tg.close());

// ---------- Ishga tushirish ----------
loadFilials();
