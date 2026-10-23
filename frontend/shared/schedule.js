// Renders weekly schedule tables. Records come from /api/schedule.
import { formatDay, weekdayLabel, startOfWeek, addDays, toIsoDate } from "./dates.js";

export function escapeHtml(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Backend returns { weeks: [{week_start, week_end, records: [...]}], records: [...] }.
// Accept a payload, a plain array or a single week and always return a flat array.
function flattenRecords(source) {
  if (!source) return [];
  if (Array.isArray(source)) return source;
  if (Array.isArray(source.records)) return source.records;
  if (Array.isArray(source.weeks)) {
    return source.weeks.flatMap((w) => (Array.isArray(w.records) ? w.records : []));
  }
  if (source.day) return [source];
  return [];
}

function recordsForWeek(records, weekStart) {
  const startIso = toIsoDate(weekStart);
  const endIso = toIsoDate(addDays(weekStart, 6));
  return records
    .filter((r) => r && r.day && r.day >= startIso && r.day <= endIso)
    .sort((a, b) => (a.day < b.day ? -1 : a.day > b.day ? 1 : 0));
}

function rowFor(record, iso) {
  const big = escapeHtml(record ? record.big_operations : "");
  const small = escapeHtml(record ? record.small_operations : "");
  const day = formatDay(iso);
  const label = weekdayLabel(iso);
  const today = iso === toIsoDate(new Date()) ? ' class="is-today"' : "";
  return `<tr${today}>
    <td class="weekday"><span class="weekday-name">${label}</span> ${day}</td>
    <td>${big}</td>
    <td>${small}</td>
  </tr>`;
}

// Builds the table HTML for one week starting on weekStart.
export function renderWeekTable(source, weekStart) {
  const start = startOfWeek(weekStart || new Date());
  const byDay = new Map();
  for (const r of recordsForWeek(flattenRecords(source), start)) byDay.set(r.day, r);

  let rows = "";
  for (let i = 0; i < 7; i += 1) {
    const iso = toIsoDate(addDays(start, i));
    rows += rowFor(byDay.get(iso), iso);
  }

  return `<div class="week-block">
    <table class="schedule-table">
      <thead>
        <tr><th>Дата</th><th>Большие операции</th><th>Малые операции</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  </div>`;
}

// Supports renderWeeks(container, data, week) and renderWeeks(data, week).
export function renderWeeks(containerOrData, dataOrWeek, weekArg) {
  let container = null;
  let data = null;
  let week = null;

  const looksLikeContainer =
    containerOrData &&
    typeof containerOrData === "object" &&
    "innerHTML" in containerOrData &&
    typeof containerOrData.innerHTML === "string";

  if (looksLikeContainer) {
    container = containerOrData;
    data = dataOrWeek;
    week = weekArg;
  } else {
    container = document.getElementById("schedule");
    data = containerOrData;
    week = dataOrWeek;
  }

  if (!container) return;
  // Guard against a DOM element accidentally passed as the week start.
  if (!(week instanceof Date) && typeof week !== "string") week = null;
  container.innerHTML = renderWeekTable(data, week || new Date());
}
