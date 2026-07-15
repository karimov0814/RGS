// ============================================================
//  i18n — O'zbek / Rus / Ingliz tillari uchun tarjima tizimi
// ============================================================

const TRANSLATIONS = {
  uz: {
    blocked_title: "Ushbu bot ishlamaydi",
    blocked_subtitle: "Sizda ushbu ilovadan foydalanish uchun ruxsat yo'q",

    admin_title: "Admin panel",
    admin_subtitle: "Foydalanuvchilar va filiallarni boshqarish",

    tab_users: "Userlar",
    tab_filials: "Filiallar",
    tab_sections: "Bo'limlar",
    tab_report: "Hisobot rejimi",

    users_add_title: "Yangi foydalanuvchi qo'shish",
    users_id_placeholder: "Telegram user ID (masalan 123456789)",
    users_name_placeholder: "Ism (ixtiyoriy)",
    users_superadmin_checkbox: "Superadmin huquqi",
    btn_add: "Qo'shish",

    filials_add_title: "Yangi filial qo'shish",
    filials_name_placeholder: "Filial nomi",

    sections_subtitle: "Har bir chek-list turi uchun qaysi bo'lim (mavzu) so'ralishini shu yerdan sozlang. Tartibni o'zgartirish uchun ⠿ belgisidan ushlab suring.",
    sections_add_title: "Yangi bo'lim qo'shish",
    sections_add_hint: "Nomni joriy tanlangan tilda kiriting — tizim boshqa 2 tilga avtomatik tarjima qiladi.",
    sections_name_placeholder: "Bo'lim nomi (masalan: Fasad fotosi)",

    report_subtitle: "Superadmin sifatida ham oddiy hisobot yubora olasiz.",
    report_send_btn: "Hisobot yuborish",

    filial_screen_title: "Filialni tanlang",
    filial_screen_subtitle: "Hisobot qaysi filial uchun",
    admin_back_btn: "Admin panelga qaytish",

    checklist_subtitle: "Chek-list turini tanlang",
    checklist_back_btn: "Filialni o'zgartirish",
    checklist_none: "Hozircha chek-list turi sozlanmagan",

    sections_progress: "{done} / {total} bo'lim",
    add_photo_btn: "Rasm qo'shish",
    camera_permission_denied: "Kameraga ruxsat berilmadi yoki u mavjud emas. Fayl tanlash ekrani ochiladi.",
    photo_count: "{n} ta rasm",
    comment_placeholder: "Izoh (ixtiyoriy)",

    success_title: "Yuborildi!",
    success_subtitle: "Barcha rasmlar tegishli filial bo'limiga yetkazildi. Rahmat!",
    close_btn: "Yopish",

    modal_cancel: "Bekor qilish",
    modal_ok: "OK",
    modal_attention: "Diqqat",
    modal_understood: "Tushunarli",
    modal_confirm_title: "Tasdiqlang",
    modal_yes: "Ha",

    loading_default: "Yuklanmoqda...",
    loading_sending: "Yuborilmoqda...",
    loading_adding: "Qo'shilmoqda...",
    loading_saving: "Saqlanmoqda...",
    loading_deleting: "O'chirilmoqda...",
    loading_linking: "Bog'lanmoqda...",

    error_load_config: "Ma'lumotlarni yuklab bo'lmadi. Qayta urinib ko'ring.",
    error_load_sections: "Bo'limlarni yuklab bo'lmadi. Qayta urinib ko'ring.",
    error_submit: "Yuborishda xatolik yuz berdi. Qayta urinib ko'ring.",
    error_prefix: "Xatolik: ",
    error_generic: "Xatolik yuz berdi",
    load_error_prefix: "Yuklashda xatolik: ",

    mainbutton_submit: "✅ Yuborish",

    users_none: "Hozircha foydalanuvchi yo'q",
    users_no_name: "Ism kiritilmagan",
    users_id_label: "ID: {id}",
    users_group_superadmins: "Superadminlar",
    users_group_admins: "Adminlar",
    users_id_numeric_error: "Telegram user ID faqat raqamlardan iborat bo'lishi kerak",
    users_edit_title: "Foydalanuvchini tahrirlash",
    users_name_label: "Ism",
    users_delete_confirm: "{name} o'chirilsinmi?",
    users_delete_title: "Foydalanuvchini o'chirish",
    btn_delete: "O'chirish",

    filials_none: "Hozircha filial yo'q",
    filials_meta: "ID: {id} · Topic: {topic}",
    filials_topic_unlinked: "bog'lanmagan",
    toggle_deactivate_label: "Nofaol qilish",
    toggle_activate_label: "Faollashtirish",
    link_topic_title: "Mavjud topicga bog'lash",
    link_topic_tooltip: "Guruhdagi mavjud topic bilan bog'lash",
    edit_label: "Tahrirlash",
    delete_label: "O'chirish",
    filials_name_required: "Filial nomini kiriting",
    link_field_label: "Topic (thread) ID raqami",
    btn_link: "Bog'lash",
    link_id_error: "Topic ID musbat butun son bo'lishi kerak",
    filials_edit_title: "Filialni tahrirlash",
    filials_name_label: "Filial nomi",
    btn_save: "Saqlash",
    filials_toggle_off_confirm: "\"{name}\" filiali endi ro'yxatlarda ko'rinmaydi. Bazada saqlanib qoladi va istalgan vaqt qaytarish mumkin.",
    filials_toggle_on_confirm: "\"{name}\" filiali qaytadan faol qilinsinmi va ro'yxatlarda ko'rinadigan bo'lsinmi?",
    filials_toggle_off_title: "Filialni nofaol qilish",
    filials_toggle_on_title: "Filialni faollashtirish",
    filials_delete_confirm: "\"{name}\" filiali bazadan butunlay o'chiriladi. Bu amalni orqaga qaytarib bo'lmaydi. Filialni vaqtincha yashirish uchun o'rniga ko'z ikonkasidan foydalaning.",
    filials_delete_title: "Filialni butunlay o'chirish",
    btn_delete_permanent: "Butunlay o'chirish",
    inactive_badge: "nofaol",

    sections_types_none: "Chek-list turlari topilmadi",
    sections_none: "Hozircha bo'lim yo'q",
    sections_name_required: "Bo'lim nomini kiriting",
    sections_select_checklist_first: "Avval chek-list turini tanlang",
    sections_edit_title: "Bo'limni tahrirlash",
    sections_name_label: "Bo'lim nomi",
    sections_toggle_off_confirm: "\"{name}\" bo'limi endi bu chek-listda so'ralmaydi. Istalgan vaqt qaytarish mumkin.",
    sections_toggle_on_confirm: "\"{name}\" bo'limi qaytadan faol qilinsinmi?",
    sections_toggle_off_title: "Bo'limni nofaol qilish",
    sections_toggle_on_title: "Bo'limni faollashtirish",
    sections_delete_confirm: "\"{name}\" bo'limi bazadan butunlay o'chiriladi (unga bog'liq eski rasm hisobotlari bilan birga). Buning o'rniga ko'z ikonkasidan foydalanish tavsiya etiladi.",
    sections_delete_title: "Bo'limni butunlay o'chirish",
    sections_visibility_label: "Qaysi filiallarda ko'rinadi",
    sections_visibility_title: "\"{name}\" — qaysi filiallarda so'ralsin?",
    sections_visibility_hint: "Belgi olib tashlangan filialda bu bo'lim umuman ko'rinmaydi (masalan tashqi hududi yo'q filialda \"Tashqi hudud\" bo'limi).",
    sections_visibility_no_filials: "Hozircha faol filial yo'q",
    sections_drag_label: "Tartibini o'zgartirish uchun ushlab suring",
  },

  ru: {
    blocked_title: "Этот бот не работает",
    blocked_subtitle: "У вас нет доступа к этому приложению",

    admin_title: "Панель администратора",
    admin_subtitle: "Управление пользователями и филиалами",

    tab_users: "Пользователи",
    tab_filials: "Филиалы",
    tab_sections: "Разделы",
    tab_report: "Режим отчёта",

    users_add_title: "Добавить нового пользователя",
    users_id_placeholder: "Telegram ID пользователя (например 123456789)",
    users_name_placeholder: "Имя (необязательно)",
    users_superadmin_checkbox: "Права супер-администратора",
    btn_add: "Добавить",

    filials_add_title: "Добавить новый филиал",
    filials_name_placeholder: "Название филиала",

    sections_subtitle: "Здесь настройте, какие разделы (темы) запрашиваются для каждого типа чек-листа. Чтобы изменить порядок, удерживайте значок ⠿ и перетащите.",
    sections_add_title: "Добавить новый раздел",
    sections_add_hint: "Введите название на текущем выбранном языке — система автоматически переведёт на остальные 2 языка.",
    sections_name_placeholder: "Название раздела (например: Фото фасада)",

    report_subtitle: "Вы можете отправить обычный отчёт даже как супер-администратор.",
    report_send_btn: "Отправить отчёт",

    filial_screen_title: "Выберите филиал",
    filial_screen_subtitle: "Для какого филиала отчёт",
    admin_back_btn: "Вернуться в панель администратора",

    checklist_subtitle: "Выберите тип чек-листа",
    checklist_back_btn: "Изменить филиал",
    checklist_none: "Тип чек-листа пока не настроен",

    sections_progress: "{done} / {total} раздел",
    add_photo_btn: "Добавить фото",
    camera_permission_denied: "Доступ к камере не предоставлен или она недоступна. Откроется выбор файла.",
    photo_count: "{n} фото",
    comment_placeholder: "Комментарий (необязательно)",

    success_title: "Отправлено!",
    success_subtitle: "Все фото доставлены в соответствующий раздел филиала. Спасибо!",
    close_btn: "Закрыть",

    modal_cancel: "Отмена",
    modal_ok: "OK",
    modal_attention: "Внимание",
    modal_understood: "Понятно",
    modal_confirm_title: "Подтвердите",
    modal_yes: "Да",

    loading_default: "Загрузка...",
    loading_sending: "Отправка...",
    loading_adding: "Добавление...",
    loading_saving: "Сохранение...",
    loading_deleting: "Удаление...",
    loading_linking: "Связывание...",

    error_load_config: "Не удалось загрузить данные. Попробуйте снова.",
    error_load_sections: "Не удалось загрузить разделы. Попробуйте снова.",
    error_submit: "Ошибка при отправке. Попробуйте снова.",
    error_prefix: "Ошибка: ",
    error_generic: "Произошла ошибка",
    load_error_prefix: "Ошибка загрузки: ",

    mainbutton_submit: "✅ Отправить",

    users_none: "Пользователей пока нет",
    users_no_name: "Имя не указано",
    users_id_label: "ID: {id}",
    users_group_superadmins: "Суперадмины",
    users_group_admins: "Админы",
    users_id_numeric_error: "Telegram ID пользователя должен состоять только из цифр",
    users_edit_title: "Редактировать пользователя",
    users_name_label: "Имя",
    users_delete_confirm: "Удалить {name}?",
    users_delete_title: "Удаление пользователя",
    btn_delete: "Удалить",

    filials_none: "Филиалов пока нет",
    filials_meta: "ID: {id} · Тема: {topic}",
    filials_topic_unlinked: "не привязана",
    toggle_deactivate_label: "Деактивировать",
    toggle_activate_label: "Активировать",
    link_topic_title: "Привязать к существующей теме",
    link_topic_tooltip: "Привязать к существующей теме в группе",
    edit_label: "Редактировать",
    delete_label: "Удалить",
    filials_name_required: "Введите название филиала",
    link_field_label: "Номер ID темы (thread)",
    btn_link: "Привязать",
    link_id_error: "ID темы должен быть положительным целым числом",
    filials_edit_title: "Редактировать филиал",
    filials_name_label: "Название филиала",
    btn_save: "Сохранить",
    filials_toggle_off_confirm: "Филиал «{name}» больше не будет отображаться в списках. Он останется в базе данных, и его можно восстановить в любое время.",
    filials_toggle_on_confirm: "Снова активировать филиал «{name}» и показывать его в списках?",
    filials_toggle_off_title: "Деактивация филиала",
    filials_toggle_on_title: "Активация филиала",
    filials_delete_confirm: "Филиал «{name}» будет полностью удалён из базы данных. Это действие нельзя отменить. Чтобы временно скрыть филиал, используйте значок глаза.",
    filials_delete_title: "Полное удаление филиала",
    btn_delete_permanent: "Удалить полностью",
    inactive_badge: "неактивен",

    sections_types_none: "Типы чек-листов не найдены",
    sections_none: "Разделов пока нет",
    sections_name_required: "Введите название раздела",
    sections_select_checklist_first: "Сначала выберите тип чек-листа",
    sections_edit_title: "Редактировать раздел",
    sections_name_label: "Название раздела",
    sections_toggle_off_confirm: "Раздел «{name}» больше не будет запрашиваться в этом чек-листе. Его можно вернуть в любое время.",
    sections_toggle_on_confirm: "Снова активировать раздел «{name}»?",
    sections_toggle_off_title: "Деактивация раздела",
    sections_toggle_on_title: "Активация раздела",
    sections_delete_confirm: "Раздел «{name}» будет полностью удалён из базы данных (вместе со связанными старыми фотоотчётами). Рекомендуется вместо этого использовать значок глаза.",
    sections_delete_title: "Полное удаление раздела",
    sections_visibility_label: "В каких филиалах отображается",
    sections_visibility_title: "«{name}» — в каких филиалах запрашивать?",
    sections_visibility_hint: "Если снять галочку с филиала, этот раздел там вообще не будет показан (например, раздел «Внешняя территория» в филиале без неё).",
    sections_visibility_no_filials: "Пока нет активных филиалов",
    sections_drag_label: "Удерживайте, чтобы изменить порядок",
  },

  en: {
    blocked_title: "This bot doesn't work",
    blocked_subtitle: "You don't have permission to use this app",

    admin_title: "Admin panel",
    admin_subtitle: "Manage users and branches",

    tab_users: "Users",
    tab_filials: "Branches",
    tab_sections: "Sections",
    tab_report: "Report mode",

    users_add_title: "Add new user",
    users_id_placeholder: "Telegram user ID (e.g. 123456789)",
    users_name_placeholder: "Name (optional)",
    users_superadmin_checkbox: "Superadmin rights",
    btn_add: "Add",

    filials_add_title: "Add new branch",
    filials_name_placeholder: "Branch name",

    sections_subtitle: "Configure which sections (topics) are requested for each checklist type here. Drag the ⠿ handle to reorder.",
    sections_add_title: "Add new section",
    sections_add_hint: "Enter the name in the currently selected language — the system will automatically translate it into the other 2 languages.",
    sections_name_placeholder: "Section name (e.g. Facade photo)",

    report_subtitle: "As a superadmin, you can also submit a regular report.",
    report_send_btn: "Submit report",

    filial_screen_title: "Select a branch",
    filial_screen_subtitle: "Which branch is this report for",
    admin_back_btn: "Back to admin panel",

    checklist_subtitle: "Select checklist type",
    checklist_back_btn: "Change branch",
    checklist_none: "No checklist type configured yet",

    sections_progress: "{done} / {total} sections",
    add_photo_btn: "Add photo",
    camera_permission_denied: "Camera access was denied or is unavailable. Opening file picker instead.",
    photo_count: "{n} photo(s)",
    comment_placeholder: "Comment (optional)",

    success_title: "Sent!",
    success_subtitle: "All photos have been delivered to the branch section. Thank you!",
    close_btn: "Close",

    modal_cancel: "Cancel",
    modal_ok: "OK",
    modal_attention: "Attention",
    modal_understood: "Got it",
    modal_confirm_title: "Confirm",
    modal_yes: "Yes",

    loading_default: "Loading...",
    loading_sending: "Sending...",
    loading_adding: "Adding...",
    loading_saving: "Saving...",
    loading_deleting: "Deleting...",
    loading_linking: "Linking...",

    error_load_config: "Failed to load data. Please try again.",
    error_load_sections: "Failed to load sections. Please try again.",
    error_submit: "An error occurred while submitting. Please try again.",
    error_prefix: "Error: ",
    error_generic: "An error occurred",
    load_error_prefix: "Loading error: ",

    mainbutton_submit: "✅ Submit",

    users_none: "No users yet",
    users_no_name: "Name not entered",
    users_id_label: "ID: {id}",
    users_group_superadmins: "Superadmins",
    users_group_admins: "Admins",
    users_id_numeric_error: "Telegram user ID must contain only digits",
    users_edit_title: "Edit user",
    users_name_label: "Name",
    users_delete_confirm: "Delete {name}?",
    users_delete_title: "Delete user",
    btn_delete: "Delete",

    filials_none: "No branches yet",
    filials_meta: "ID: {id} · Topic: {topic}",
    filials_topic_unlinked: "not linked",
    toggle_deactivate_label: "Deactivate",
    toggle_activate_label: "Activate",
    link_topic_title: "Link to existing topic",
    link_topic_tooltip: "Link to an existing topic in the group",
    edit_label: "Edit",
    delete_label: "Delete",
    filials_name_required: "Enter branch name",
    link_field_label: "Topic (thread) ID number",
    btn_link: "Link",
    link_id_error: "Topic ID must be a positive integer",
    filials_edit_title: "Edit branch",
    filials_name_label: "Branch name",
    btn_save: "Save",
    filials_toggle_off_confirm: "The branch \"{name}\" will no longer appear in lists. It stays in the database and can be restored at any time.",
    filials_toggle_on_confirm: "Reactivate the branch \"{name}\" and show it in lists again?",
    filials_toggle_off_title: "Deactivate branch",
    filials_toggle_on_title: "Activate branch",
    filials_delete_confirm: "The branch \"{name}\" will be permanently deleted from the database. This action cannot be undone. To temporarily hide the branch, use the eye icon instead.",
    filials_delete_title: "Permanently delete branch",
    btn_delete_permanent: "Delete permanently",
    inactive_badge: "inactive",

    sections_types_none: "No checklist types found",
    sections_none: "No sections yet",
    sections_name_required: "Enter section name",
    sections_select_checklist_first: "Select checklist type first",
    sections_edit_title: "Edit section",
    sections_name_label: "Section name",
    sections_toggle_off_confirm: "The section \"{name}\" will no longer be requested in this checklist. It can be restored at any time.",
    sections_toggle_on_confirm: "Reactivate the section \"{name}\"?",
    sections_toggle_off_title: "Deactivate section",
    sections_toggle_on_title: "Activate section",
    sections_delete_confirm: "The section \"{name}\" will be permanently deleted from the database (along with related old photo reports). Using the eye icon instead is recommended.",
    sections_delete_title: "Permanently delete section",
    sections_visibility_label: "Which branches it's shown in",
    sections_visibility_title: "\"{name}\" — which branches should ask for it?",
    sections_visibility_hint: "Unchecking a branch hides this section there completely (e.g. the \"Exterior area\" section at a branch that has none).",
    sections_visibility_no_filials: "No active branches yet",
    sections_drag_label: "Hold to reorder",
  },
};

const SUPPORTED_LANGS = ["uz", "ru", "en"];
const LANG_STORAGE_KEY = "rgs_lang";

function detectInitialLang() {
  try {
    const saved = localStorage.getItem(LANG_STORAGE_KEY);
    if (saved && SUPPORTED_LANGS.includes(saved)) return saved;
  } catch (_) {}
  try {
    const tgLang = window.Telegram?.WebApp?.initDataUnsafe?.user?.language_code;
    if (tgLang && SUPPORTED_LANGS.includes(tgLang)) return tgLang;
  } catch (_) {}
  return "uz";
}

let currentLang = detectInitialLang();

function getLang() {
  return currentLang;
}

function setLang(lang) {
  if (!SUPPORTED_LANGS.includes(lang)) return;
  currentLang = lang;
  try {
    localStorage.setItem(LANG_STORAGE_KEY, lang);
  } catch (_) {}
  document.documentElement.lang = lang;
  applyStaticTranslations();
  updateLangSwitcherUI();
  if (typeof onLangChange === "function") onLangChange();
}

// t("key", {name: "..."}) -> tarjima matnini {placeholder}larni almashtirib qaytaradi
function t(key, vars) {
  const dict = TRANSLATIONS[currentLang] || TRANSLATIONS.uz;
  let str = dict[key] !== undefined ? dict[key] : (TRANSLATIONS.uz[key] !== undefined ? TRANSLATIONS.uz[key] : key);
  if (vars) {
    Object.keys(vars).forEach((k) => {
      str = str.replace(new RegExp(`\\{${k}\\}`, "g"), vars[k]);
    });
  }
  return str;
}

// Statik HTML ichidagi [data-i18n] va [data-i18n-placeholder] belgilangan
// joylarni joriy til bilan to'ldiradi.
function applyStaticTranslations() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
}

function updateLangSwitcherUI() {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.lang === currentLang);
  });
}

function initLangSwitcher() {
  document.querySelectorAll(".lang-btn").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.dataset.lang));
  });
  updateLangSwitcherUI();
}

// Bu skript body oxirida ulanadi, shu sabab DOM allaqachon tayyor —
// DOMContentLoaded kutmasdan darhol ishga tushiramiz.
document.documentElement.lang = currentLang;
applyStaticTranslations();
initLangSwitcher();
