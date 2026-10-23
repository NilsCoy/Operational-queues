// Shared HTTP layer for the schedule app.
// Talks to the FastAPI backend under /api and keeps the session token.

const TOKEN_KEY = "oq_token";
const ROLE_KEY = "oq_role";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function getRole() {
  return localStorage.getItem(ROLE_KEY) || "";
}

export function setSession(token, role) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ROLE_KEY, role);
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ROLE_KEY);
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`/api${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const error = new Error((data && data.detail) || `HTTP ${response.status}`);
    error.status = response.status;
    if (response.status === 401) clearSession();
    throw error;
  }
  return data;
}

function weekQuery(weekOf) {
  return weekOf ? `?week_of=${encodeURIComponent(weekOf)}` : "";
}

export const api = {
  health: () => request("GET", "/health"),
  bootstrapStatus: () => request("GET", "/bootstrap"),
  bootstrapAdmin: (password) => request("POST", "/bootstrap/admin", { password }),

  login: (password) => request("POST", "/login", { password }),
  logout: () => request("POST", "/logout"),
  me: () => request("GET", "/me"),

  schedule: (weekOf) => request("GET", `/schedule${weekQuery(weekOf)}`),

  adminRecords: (weekOf) => request("GET", `/admin/records${weekQuery(weekOf)}`),
  createRecord: (payload) => request("POST", "/admin/records", payload),
  updateRecord: (id, payload) => request("PUT", `/admin/records/${id}`, payload),
  deleteRecord: (id) => request("DELETE", `/admin/records/${id}`),

  pins: () => request("GET", "/admin/pins"),
  createPin: (payload) => request("POST", "/admin/pins", payload),
  deletePin: (index) => request("DELETE", `/admin/pins/${index}`),
};
