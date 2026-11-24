// Change-password modal shared by the schedule page (/user) and the admin page (/admin).
// Opened by the button, or forced when the password has expired (every 3 months):
// a forced modal cannot be closed until the password is changed.
import { api, getRole, clearSession } from "./api.js";

const PASSWORD_HINT =
  "Минимум 12 символов, хотя бы одна заглавная буква и хотя бы один специальный символ. Пробелы разрешены.";

const EXPIRED_NOTE =
  "Срок действия пароля истёк (пароль меняется раз в 3 месяца). Смените пароль, чтобы продолжить.";

let controller = null;

// Mirrors backend/app/auth.py password_policy_error: 12+ chars, one uppercase, one special char.
export function passwordPolicyError(password) {
  const value = String(password || "");
  if (value.length < 12) return "Пароль: минимум 12 символов";
  if (!/[A-ZА-ЯЁ]/u.test(value)) return "Пароль: нужна хотя бы одна заглавная буква";
  if (!/[^\p{L}\p{N}\s]/u.test(value)) return "Пароль: нужен хотя бы один специальный символ";
  return null;
}

function escapeAttr(value) {
  return String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

// Builds the modal once, appends it to <body> and wires it to `openButton`.
// `onUnauthorized` is called when the session has expired.
export function mountChangePassword({ openButton, onUnauthorized }) {
  const modal = document.createElement("div");
  modal.className = "modal";
  modal.id = "change-password-modal";
  modal.hidden = true;
  modal.innerHTML = `
    <div class="modal-card">
      <h2>Смена пароля</h2>
      <p class="modal-hint" data-cp-expired hidden>${escapeAttr(EXPIRED_NOTE)}</p>
      <p class="modal-hint">${escapeAttr(PASSWORD_HINT)}</p>
      <form id="change-password-form" class="form-column">
        <label>Текущий пароль<input type="password" name="current" autocomplete="current-password" required></label>
        <label>Новый пароль<input type="password" name="next" autocomplete="new-password" required></label>
        <label>Повторите новый пароль<input type="password" name="repeat" autocomplete="new-password" required></label>
        <button type="submit" class="btn">Сменить пароль</button>
      </form>
      <p class="form-success" data-cp-success hidden></p>
      <p class="form-error" data-cp-error hidden></p>
      <button type="button" class="btn btn-ghost" data-cp-close>Закрыть</button>
    </div>`;
  document.body.appendChild(modal);

  const form = modal.querySelector("#change-password-form");
  const currentInput = form.elements.current;
  const nextInput = form.elements.next;
  const repeatInput = form.elements.repeat;
  const closeBtn = modal.querySelector("[data-cp-close]");
  const expiredNote = modal.querySelector("[data-cp-expired]");
  const errorEl = modal.querySelector("[data-cp-error]");
  const successEl = modal.querySelector("[data-cp-success]");
  let forced = false;

  function showError(message) {
    errorEl.textContent = message || "";
    errorEl.hidden = !message;
  }

  function showSuccess(message) {
    successEl.textContent = message || "";
    successEl.hidden = !message;
  }

  function setForced(value) {
    forced = value;
    closeBtn.hidden = value;
    expiredNote.hidden = !value;
  }

  function hide() {
    setForced(false);
    modal.hidden = true;
  }

  function open({ forced: isForced = false } = {}) {
    if (!getRole()) return;
    form.reset();
    showError("");
    showSuccess("");
    setForced(isForced);
    modal.hidden = false;
    requestAnimationFrame(() => currentInput.focus());
  }

  function close() {
    if (forced) return;
    hide();
  }

  if (openButton) openButton.addEventListener("click", () => open());
  closeBtn.addEventListener("click", close);
  modal.addEventListener("click", (event) => {
    if (event.target === modal) close();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modal.hidden) close();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    showError("");
    showSuccess("");
    const policyError = passwordPolicyError(nextInput.value);
    if (policyError) {
      showError(policyError);
      return;
    }
    if (nextInput.value !== repeatInput.value) {
      showError("Новые пароли не совпадают");
      return;
    }
    try {
      await api.changePassword(currentInput.value, nextInput.value);
      form.reset();
      if (forced) {
        hide();
      } else {
        showSuccess("Пароль изменён");
      }
    } catch (err) {
      if (err.status === 401) {
        hide();
        clearSession();
        if (onUnauthorized) onUnauthorized();
        return;
      }
      showError(err.message);
    }
  });

  controller = { open };
  return controller;
}

// Asks the backend whether the current password is older than 3 months.
// If so, opens the change-password modal in forced mode.
export async function enforcePasswordExpiry() {
  if (!getRole() || !controller) return;
  try {
    const me = await api.me();
    if (me.password_expired) controller.open({ forced: true });
  } catch {
    // session problems are handled by the page's own 401 handling
  }
}
