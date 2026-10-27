// Renders weekly schedule tables shared by the user and admin pages.
// Each record occupies its own row; a day with several records keeps the
// date cell merged (rowspan) so the week stays compact and readable.
import { formatDay, weekdayLabel, startOfWeek, addDays, toIsoDate } from "./dates.js";

export function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// Multi-line values keep their line breaks inside the cell.
function cellHtml(value) {
  const text = value == null ? "" : String(value);
  if (!text.trim()) return '<span class="cell-empty">—</span>';
  return `<div class="cell-multiline">${escapeHtml(text)}</div>`;
}

// The backend returns { weeks: [...], records: [...] }. Either shape is accepted
// here so a single-record object or a bare array never breaks rendering.
function normalizeRecords(data) {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== "object") return [];
  if (Array.isArray(data.records)) return data.records;
  const out = [];
  for (const week of data.weeks || []) {
    for (const record of week.records || []) out.push(record);
  }
  return out;
}

function recordDay(record) {
  return record.day || record.date || "";
}

function groupByDay(records) {
  const groups = new Map();
  for (const record of records || []) {
    const key = recordDay(record);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(record);
  }
  return groups;
}

function recordActions(record, options) {
  if (!options.editable) return "";
  return `<td class="row-actions">
      <button type="button" class="btn btn-sm btn-ghost" data-edit-record="${escapeHtml(record.id)}" title="Изменить" aria-label="Изменить">✎</button>
      <button type="button" class="btn btn-sm btn-danger" data-delete-record="${escapeHtml(record.id)}" title="Удалить" aria-label="Удалить">✕</button>
    </td>`;
}

export function renderWeeks(container, data, weekStartIso, options = {}) {
  if (!container) return 0;
  const editable = Boolean(options.editable);
  const weekStart = startOfWeek(weekStartIso);
  const groups = groupByDay(normalizeRecords(data));

  const headCells = ["День", "Большие операции", "Малые операции"];
  if (editable) headCells.push("Действия");
  const colCount = headCells.length;

  const rows = [];
  for (let i = 0; i < 7; i += 1) {
    const day = addDays(weekStart, i);
    const iso = toIsoDate(day);
    const dayRecords = groups.get(iso) || [];

    const dayLabel = `<div class="day-label">
        <span class="day-weekday">${escapeHtml(weekdayLabel(day))}</span>
        <span class="day-date">${escapeHtml(formatDay(day))}</span>
      </div>`;

    if (!dayRecords.length) {
      const emptyCells = `<td><span class="cell-empty">—</span></td><td><span class="cell-empty">—</span></td>`;
      const actionCell = editable ? '<td class="row-actions"></td>' : "";
      rows.push(`<tr class="day-row day-empty">
        <td class="day-cell">${dayLabel}</td>${emptyCells}${actionCell}
      </tr>`);
      continue;
    }

    dayRecords.forEach((record, index) => {
      const cells = [];
      if (index === 0) {
        cells.push(
          `<td class="day-cell" rowspan="${dayRecords.length}">${dayLabel}</td>`,
        );
      }
      cells.push(`<td>${cellHtml(record.big_operations)}</td>`);
      cells.push(`<td>${cellHtml(record.small_operations)}</td>`);
      cells.push(recordActions(record, { editable }));
      const firstClass = index === 0 ? " day-row day-first" : " day-row";
      rows.push(`<tr class="${firstClass.trim()}" data-day="${escapeHtml(iso)}">${cells.join("")}</tr>`);
    });
  }

  container.innerHTML = `<table class="schedule-table">
    <thead><tr>${headCells.map((h) => `<th>${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.join("")}</tbody>
  </table>`;
  return colCount;
}
