// Admin page: create/read/update/delete records grouped by week, and manage access passwords.
import { api, getRole, setSession, clearSession } from "../shared/api.js";
import { formatWeekRange, startOfWeek, addWeeks, toIsoDate, parseIsoDate } from "../shared/dates.js";
import { renderWeeks, escapeHtml } from "../shared/schedule.js";
import { mount as create } from "../shared/search.js";

const setupSection = document.getElementById("setup");
const setupForm = document.getElementById("setup-form");
const setupPassword = document.getElementById("setup-password");
const setupPassword2 = document.getElementById("setup-password-2");
const setupError = document.getElementById("setup-error");

const loginAuthSection = document.getElementById("login-auth");
const loginForm = document.getElementById("login-form");
const loginPassword = document.getElementById("login-password");
const loginError = document.getElementById("login-error");

const loginModal = document.getElementById("login-modal");
const appSection = document.getElementById("app");
const logoutBtn = document.getElementById("logout");

const weekLabel = document.getElementById("week-label");
const prevWeek = document.getElementById("prev-week");
const nextWeek = document.getElementById("next-week");
const jumpDay = document.getElementById("jump-day");
const jumpGo = document.getElementById("jump-go");
const jumpToday = document.getElementById("jump-today");
const scheduleEl = document.getElementById("schedule");
const tableTitle = document.getElementById("table-title");
const searchBar = document.querySelector("[data-search-bar]");

const recordForm = document.getElementById("record-form");
const recordFormTitle = document.getElementById("record-form-title");
const recordId = document.getElementById("record-id");
const recordDay = document.getElementById("record-day");
const recordBig = document.getElementById("record-big");
const recordSmall = document.getElementById("record-small");
const recordSubmit = document.getElementById("record-submit");
const recordCancel = document.getElementById("record-cancel");
const recordError = document.getElementById("record-error");

const pinsModal = document.getElementById("pins-modal");
const pinsOpen = document.getElementById("pins-open");
const pinsClose = document.getElementById("pins-close");
const pinForm = document.getElementById("pin-form");
const pinValue = document.getElementById("pin-value");
const pinLabel = document.getElementById("pin-label");
const pinRole = document.getElementById("pin-role");
const pinList = document.getElementById("pin-list");
const pinCreated = document.getElementById("pin-created");
const pinError = document.getElementById("pin-error");

let currentWeek = startOfWeek(new Date());
let hasAdmin = false;
let weekRecords = [];
let search = null;
let searchActive = false;

function showError(el, message) {
  el.textContent = message || "";
  el.hidden = !message;
}

// setup-form is shown only while no admin exists; login-auth only once it does.
function applyAuthMode() {
  const mode = hasAdmin ? "login" : "setup";
  setupSection.hidden = mode !== "setup";
  loginAuthSection.hidden = mode !== "login";
  if (setupForm) setupForm.hidden = hasAdmin;
  return mode;
}

function openAuthModal() {
  const mode = applyAuthMode();
  loginModal.hidden = false;
  if (mode === "setup") {
    setupPassword.value = "";
    setupPassword2.value = "";
    showError(setupError, "");
  } else {
    loginPassword.value = "";
    showError(loginError, "");
  }
  const focusInput = mode === "setup" ? setupPassword : loginPassword;
  requestAnimationFrame(() => focusInput.focus());
}

function closeAuthModal() {
  loginModal.hidden = true;
}

function openPinsModal() {
  if (getRole() !== "admin") return;
  showError(pinError, "");
  pinCreated.hidden = true;
  pinsModal.hidden = false;
  loadPins();
  requestAnimationFrame(() => pinValue.focus());
}

function closePinsModal() {
  pinsModal.hidden = true;
}

// Logged out: the whole inner content is hidden and the auth modal cannot be closed.
// Only an authorized admin sees the main admin content and its buttons.
function renderSessionUi() {
  const role = getRole();
  const loggedIn = Boolean(role);
  const isAdmin = role === "admin";
  appSection.hidden = !isAdmin;
  pinsOpen.hidden = !isAdmin;
  logoutBtn.hidden = !loggedIn;
  document.body.classList.toggle("is-admin", isAdmin);
  document.body.classList.toggle("is-guest", !loggedIn);
  if (!isAdmin) closePinsModal();
  if (!loggedIn) {
    openAuthModal();
  } else {
    closeAuthModal();
  }
}

function refreshWeekUi() {
  weekLabel.textContent = formatWeekRange(toIsoDate(currentWeek));
  if (jumpDay) jumpDay.value = toIsoDate(currentWeek);
  if (tableTitle) {
    tableTitle.textContent = searchActive ? "Результаты поиска (все даты)" : "Расписание";
  }
}

function renderCurrent(data) {
  weekRecords = Array.isArray(data) ? data : data.records || [];
  renderWeeks(scheduleEl, weekRecords, toIsoDate(currentWeek), {
    editable: true,
    allDates: searchActive,
  });
}

async function loadWeek() {
  searchActive = false;
  if (search) search.clear();
  refreshWeekUi();
  try {
    const data = await api.adminRecords(toIsoDate(currentWeek));
    renderCurrent(data);
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    scheduleEl.innerHTML = `<p class="schedule-empty">Не удалось загрузить расписание: ${escapeHtml(err.message)}</p>`;
  }
}

// Searches across all dates with records, then jumps to the nearest hit.
async function run(query) {
  const needle = String(query || "").trim();
  if (!needle) {
    if (search) search.clear();
    await loadWeek();
    return;
  }
  searchActive = true;
  refreshWeekUi();
  try {
    const data = await api.adminRecords(null, needle);
    renderCurrent(data);
    if (search) {
      search.setQuery(needle);
      search.findNearest();
    }
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    scheduleEl.innerHTML = `<p class="schedule-empty">Ошибка поиска: ${escapeHtml(err.message)}</p>`;
  }
}

function goToDay(iso) {
  if (!iso) return;
  currentWeek = startOfWeek(parseIsoDate(iso));
  loadWeek();
}

async function loadPins() {
  pinList.innerHTML = '<tr><td colspan="4" class="pin-empty">Загрузка…</td></tr>';
  try {
    const data = await api.pins();
    renderPins(data.pins);
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    pinList.innerHTML = `<tr><td colspan="4" class="pin-empty">Ошибка: ${escapeHtml(err.message)}</td></tr>`;
  }
}

function renderPins(pins) {
  if (!pins || !pins.length) {
    pinList.innerHTML = '<tr><td colspan="4" class="pin-empty">Паролей нет</td></tr>';
    return;
  }
  pinList.innerHTML = pins
    .map(
      (p, index) => `<tr>
        <td><span class="pin-role-badge pin-role-${escapeHtml(p.role)}">${p.role === "admin" ? "Администратор" : "Пользователь"}</span></td>
        <td>${escapeHtml(p.label || "—")}</td>
        <td class="pin-hash">${escapeHtml(p.hash_prefix)}…</td>
        <td><button type="button" class="btn btn-sm btn-ghost pin-delete" data-delete-index="${index}">Удалить</button></td>
      </tr>`,
    )
    .join("");
}

// ---- search wiring ----

function mountBar() {
  if (!scheduleEl || !searchBar) return;
  search = create({ container: scheduleEl, bar: searchBar });
  if (search) search.onFind(run);
}

// ---- record form: add / edit mode ----

function resetRecordForm() {
  recordId.value = "";
  recordBig.value = "";
  recordSmall.value = "";
  recordFormTitle.textContent = "Добавить запись";
  recordSubmit.textContent = "Добавить";
  recordCancel.hidden = true;
  showError(recordError, "");
}

function startEditRecord(record) {
  recordId.value = record.id;
  recordDay.value = record.day;
  recordBig.value = record.big_operations || "";
  recordSmall.value = record.small_operations || "";
  recordFormTitle.textContent = "Изменить запись";
  recordSubmit.textContent = "Сохранить";
  recordCancel.hidden = false;
  showError(recordError, "");
  recordForm.scrollIntoView({ behavior: "smooth", block: "start" });
  requestAnimationFrame(() => recordBig.focus());
}

function enterApp() {
  closeAuthModal();
  renderSessionUi();
  recordDay.value = toIsoDate(currentWeek);
  mountBar();
  loadWeek();
}

function onUnauthorized() {
  clearSession();
  renderSessionUi();
}

async function boot() {
  if (getRole() === "admin") {
    enterApp();
    return;
  }
  try {
    const { has_admin } = await api.bootstrapStatus();
    hasAdmin = Boolean(has_admin);
  } catch {
    hasAdmin = true;
  }
  renderSessionUi();
}

setupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError(setupError, "");
  const password = setupPassword.value;
  if (password.length < 4) {
    showError(setupError, "Пароль: минимум 4 символа");
    return;
  }
  if (password !== setupPassword2.value) {
    showError(setupError, "Пароли не совпадают");
    return;
  }
  try {
    await api.bootstrapAdmin(password);
    hasAdmin = true;
    applyAuthMode();
    loginPassword.value = "";
    showError(loginError, "Администратор создан — войдите");
    requestAnimationFrame(() => loginPassword.focus());
  } catch (err) {
    if (err.status === 409) {
      hasAdmin = true;
      applyAuthMode();
      showError(loginError, "Администратор уже создан — войдите");
      requestAnimationFrame(() => loginPassword.focus());
      return;
    }
    showError(setupError, err.message);
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError(loginError, "");
  const password = loginPassword.value;
  if (!password) {
    showError(loginError, "Введите пароль");
    return;
  }
  try {
    const { token, role } = await api.login(password);
    if (role !== "admin") {
      clearSession();
      showError(loginError, "Этот пароль не администраторский");
      return;
    }
    setSession(token, role);
    loginPassword.value = "";
    enterApp();
  } catch (err) {
    showError(loginError, err.status === 401 ? "Неверный пароль" : err.message);
  }
});

pinsOpen.addEventListener("click", openPinsModal);
pinsClose.addEventListener("click", closePinsModal);
pinsModal.addEventListener("click", (event) => {
  if (event.target === pinsModal) closePinsModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !pinsModal.hidden) closePinsModal();
});

prevWeek.addEventListener("click", () => {
  currentWeek = addWeeks(currentWeek, -1);
  loadWeek();
});
nextWeek.addEventListener("click", () => {
  currentWeek = addWeeks(currentWeek, 1);
  loadWeek();
});
if (jumpGo) jumpGo.addEventListener("click", () => goToDay(jumpDay.value));
if (jumpDay) {
  jumpDay.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      goToDay(jumpDay.value);
    }
  });
}
if (jumpToday) jumpToday.addEventListener("click", () => goToDay(toIsoDate(new Date())));

recordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError(recordError, "");
  if (!recordDay.value) {
    showError(recordError, "Укажите дату");
    return;
  }
  const payload = {
    day: recordDay.value,
    big_operations: recordBig.value,
    small_operations: recordSmall.value,
  };
  try {
    if (recordId.value) {
      await api.updateRecord(recordId.value, payload);
    } else {
      // POST always appends: a second record for the same day is allowed.
      await api.createRecord(payload);
    }
    resetRecordForm();
    goToDay(payload.day);
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    showError(recordError, err.message);
  }
});

recordCancel.addEventListener("click", () => {
  resetRecordForm();
  recordDay.value = toIsoDate(currentWeek);
});

scheduleEl.addEventListener("click", async (event) => {
  const editBtn = event.target.closest("[data-edit-record]");
  if (editBtn) {
    const record = weekRecords.find((r) => String(r.id) === editBtn.dataset.editRecord);
    if (record) startEditRecord(record);
    return;
  }

  const deleteBtn = event.target.closest("[data-delete-record]");
  if (!deleteBtn) return;
  if (recordId.value === deleteBtn.dataset.deleteRecord) resetRecordForm();
  if (!window.confirm("Удалить эту запись?")) return;
  try {
    await api.deleteRecord(deleteBtn.dataset.deleteRecord);
    await loadWeek();
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    showError(recordError, err.message);
  }
});

pinForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showError(pinError, "");
  pinCreated.hidden = true;
  const password = pinValue.value;
  if (password.length < 4) {
    showError(pinError, "Пароль: минимум 4 символа");
    return;
  }
  try {
    await api.createPin({
      password,
      role: pinRole.value,
      label: pinLabel.value.trim(),
    });
    pinCreated.textContent = `Пароль создан: ${password} — передайте его владельцу, он больше не покажется.`;
    pinCreated.hidden = false;
    pinValue.value = "";
    pinLabel.value = "";
    await loadPins();
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    showError(pinError, err.message);
  }
});

pinList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-index]");
  if (!button) return;
  showError(pinError, "");
  if (!window.confirm("Удалить этот пароль?")) return;
  try {
    await api.deletePin(Number(button.dataset.deleteIndex));
    await loadPins();
  } catch (err) {
    if (err.status === 401) return onUnauthorized();
    showError(pinError, err.message);
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api.logout();
  } catch {
    // token may already be invalid
  }
  clearSession();
  renderSessionUi();
});

boot();
