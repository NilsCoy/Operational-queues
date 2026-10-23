// Date helpers for the weekly schedule. Weeks run Monday..Sunday, dates are dd.mm.yyyy.

export function toIsoDate(date) {
  const d = date instanceof Date ? date : new Date(date);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function parseIsoDate(iso) {
  const [y, m, d] = String(iso).split("-").map(Number);
  return new Date(y, (m || 1) - 1, d || 1);
}

export function startOfWeek(date) {
  const d = date instanceof Date ? new Date(date) : parseIsoDate(date);
  d.setHours(0, 0, 0, 0);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day; // Monday is the first day
  d.setDate(d.getDate() + diff);
  return d;
}

export function addDays(date, amount) {
  const d = date instanceof Date ? new Date(date) : parseIsoDate(date);
  d.setDate(d.getDate() + amount);
  return d;
}

export function addWeeks(date, amount) {
  return addDays(startOfWeek(date), amount * 7);
}

export function formatDay(date) {
  const d = date instanceof Date ? date : parseIsoDate(date);
  const day = String(d.getDate()).padStart(2, "0");
  const m = String(d.getMonth() + 1).padStart(2, "0");
  return `${day}.${m}.${d.getFullYear()}`;
}

export function weekdayLabel(date) {
  const names = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"];
  const d = date instanceof Date ? date : parseIsoDate(date);
  return names[d.getDay()];
}

export function formatWeekRange(weekStart) {
  const start = startOfWeek(weekStart);
  const end = addDays(start, 6);
  return `${formatDay(start)} — ${formatDay(end)}`;
}
