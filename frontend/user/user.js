// Read-only schedule page. Content is hidden until the user logs in with a password.
import { api, getRole, setSession, clearSession } from "../shared/api.js";
import { renderWeeks } from "../shared/schedule.js";
import {
  formatWeekRange,
  startOfWeek,
  addWeeks,
  toIsoDate,
  parseIsoDate,
} from "../shared/dates.js";

const appSection = document.getElementById("app");
const scheduleEl = document.getElementById("schedule");
const weekLabel = document.getElementById("week-label");
const prevWeek = document.getElementById("prev-week");
const nextWeek = document.getElementById("next-week");
const jumpDay = document.getElementById("jump-day");
const jumpGo = document.getElementById("jump-go");
const jumpToday = document.getElementById("jump-today");

const loginModal = document.getElementById("login-modal");
const loginForm = document.getElementById("login-form");
const loginPassword = document.getElementById("login-password");
const loginError = document.getElementById("login-error");
const logoutBtn = document.getElementById("logout");
const adminLink = document.getElementById("admin-link");

let currentWeek = startOfWeek(new Date());
let loadSeq = 0;

function showError(el, message) {
  if (!el) return;
  el.textContent = message || "";
  el.hidden = !message;
}

// Logged out: the whole inner content is hidden and the login modal is shown.
// The admin panel link is visible only for the admin role, never for a plain user.
function refreshSessionUi() {
  const role = getRole();
  const loggedIn = Boolean(role);
  appSection.hidden = !loggedIn;
  logoutBtn.hidden = !loggedIn;
  adminLink.hidden = role !== "admin";
  loginModal.hidden = loggedIn;
  document.body.classList.toggle("is-guest", !loggedIn);
  if (!loggedIn) requestAnimationFrame(() => loginPassword.focus());
}

function refreshWeekUi() {
  weekLabel.textContent = formatWeekRange(toIsoDate(currentWeek));
  if (jumpDay) jumpDay.value = toIsoDate(currentWeek);
}

async function loadWeek() {
  refreshWeekUi();
  const seq = ++loadSeq;
  try {
    const data = await api.schedule(toIsoDate(currentWeek));
    if (seq !== loadSeq) return; // a newer week request already started
    renderWeeks(scheduleEl, data, toIsoDate(currentWeek));
  } catch (err) {
    if (seq !== loadSeq) return;
    if (err.status === 401) return onUnauthorized();
    scheduleEl.innerHTML = '<p class="empty">Не удалось загрузить расписание</p>';
  }
}

function goToDay(iso) {
  if (!iso) return;
  currentWeek = startOfWeek(parseIsoDate(iso));
  loadWeek();
}

function onUnauthorized() {
  clearSession();
  refreshSessionUi();
}

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
    setSession(token, role);
    loginPassword.value = "";
    refreshSessionUi();
    loadWeek();
    if (role === "admin") {
      window.location.href = "/admin";
    }
  } catch (err) {
    showError(loginError, err.status === 401 ? "Неверный пароль" : err.message);
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await api.logout();
  } catch {
    // token may already be invalid
  }
  clearSession();
  refreshSessionUi();
});

refreshSessionUi();
if (getRole()) loadWeek();
