// Read-only schedule page. Content is hidden until the user logs in with a password.
import { api, getRole, setSession, clearSession } from "../shared/api.js";
import { renderWeeks } from "../shared/schedule.js";
import { mount } from "../shared/search.js";
import {
  formatWeekRange,
  startOfWeek,
  addWeeks,
  toIsoDate,
  parseIsoDate,
} from "../shared/dates.js";

const appSection = document.querySelector("#app");
const scheduleEl = document.querySelector("#schedule");
const weekLabel = document.querySelector("#week-label");
const searchBar = document.querySelector("[data-search-bar]");
const prevWeekBtn = document.querySelector("#prev-week");
const nextWeekBtn = document.querySelector("#next-week");
const todayBtn = document.querySelector("#jump-today");
const jumpDay = document.querySelector("#jump-day");
const loginModal = document.querySelector("#login-modal");
const loginPassword = document.querySelector("#login-password");
const loginError = document.querySelector("#login-error");
const loginForm = document.querySelector("#login-form");
const logoutBtn = document.querySelector("#logout");
const adminLink = document.querySelector("#admin-link");

let currentWeek = startOfWeek(new Date());
let loadSeq = 0;
let search = null;
let searchActive = false;

function showLoginError(message) {
  loginError.textContent = message || "";
  loginError.hidden = !message;
}

function onUnauthorized() {
  clearSession();
  refreshSessionUi();
}

function refreshSessionUi() {
  const role = getRole();
  const loggedIn = Boolean(role);
  const isAdmin = role === "admin";

  loginModal.hidden = loggedIn;
  appSection.hidden = !loggedIn;
  logoutBtn.hidden = !loggedIn;
  if (adminLink) adminLink.hidden = !isAdmin;

  document.body.classList.toggle("is-guest", !loggedIn);
  if (!loggedIn) {
    showLoginError("");
    requestAnimationFrame(() => loginPassword.focus());
  }
}

function refreshWeekUi() {
  weekLabel.textContent = formatWeekRange(toIsoDate(currentWeek));
  if (jumpDay) jumpDay.value = toIsoDate(currentWeek);
}

async function loadWeek() {
  searchActive = false;
  refreshWeekUi();
  const seq = ++loadSeq;
  try {
    const data = await api.schedule(toIsoDate(currentWeek));
    if (seq !== loadSeq) return;
    renderWeeks(scheduleEl, data, toIsoDate(currentWeek));
    if (search) {
      search.clear();
      search.refresh();
    }
  } catch (err) {
    if (seq !== loadSeq) return;
    if (err.status === 401) return onUnauthorized();
    scheduleEl.innerHTML = '<p class="empty">Не удалось загрузить расписание</p>';
  }
}

// Search across all dates that have records; the backend filters by `q`.
async function run(query) {
  const needle = String(query || "").trim();
  if (!needle) {
    if (search) search.clear();
    await loadWeek();
    return;
  }
  searchActive = true;
  const seq = ++loadSeq;
  try {
    const data = await api.schedule(null, needle);
    if (seq !== loadSeq) return;
    renderWeeks(scheduleEl, data, toIsoDate(currentWeek), { allDates: true });
    if (search) {
      search.setQuery(needle);
      search.findNearest();
    }
  } catch (err) {
    if (seq !== loadSeq) return;
    if (err.status === 401) return onUnauthorized();
    scheduleEl.innerHTML = '<p class="empty">Ошибка поиска</p>';
  }
}

function mountBar() {
  if (!scheduleEl || !searchBar) return;
  search = mount({ container: scheduleEl, bar: searchBar });
  if (search) search.onFind(run);
}

prevWeekBtn.addEventListener("click", () => {
  currentWeek = addWeeks(currentWeek, -1);
  loadWeek();
});
nextWeekBtn.addEventListener("click", () => {
  currentWeek = addWeeks(currentWeek, 1);
  loadWeek();
});
todayBtn.addEventListener("click", () => {
  currentWeek = startOfWeek(parseIsoDate(todayIso()));
  loadWeek();
});
if (jumpDay) {
  jumpDay.addEventListener("change", () => {
    const picked = parseIsoDate(jumpDay.value);
    if (!picked) return;
    currentWeek = startOfWeek(picked);
    loadWeek();
  });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  showLoginError("");
  try {
    const data = await api.login(loginPassword.value);
    setSession(data.token, data.role || "user");
    loginPassword.value = "";
    refreshSessionUi();
    loadWeek();
  } catch (err) {
    showLoginError(err.message || "Неверный пароль");
  }
});

logoutBtn.addEventListener("click", () => {
  clearSession();
  refreshSessionUi();
});

mountBar();
refreshSessionUi();
refreshWeekUi();
if (getRole()) loadWeek();