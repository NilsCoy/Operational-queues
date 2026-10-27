// Keyword search over the schedule table shared by the user and admin pages.
// Matches are collected from the "big" and "small" operation cells only
// (td[data-col="big"], td[data-col="small"]), wrapped in <mark>, and the
// containing row is highlighted so the table stays readable while navigating.

const HIT_CLASS = "-hit";
const CURRENT_CLASS = "-hit-current";
const ROW_CLASS = "-row-hit";
const EMPTY = '<span class="cell-empty">\u2014</span>';

function normalize(value) {
  return String(value ?? "").toLocaleLowerCase("ru");
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function markHtml(text, query) {
  if (!query) return null;
  const haystack = normalize(text);
  const needle = normalize(query);
  if (!needle) return null;

  let index = haystack.indexOf(needle);
  if (index === -1) return null;

  const parts = [];
  let cursor = 0;
  while (index !== -1) {
    if (index > cursor) parts.push(escapeHtml(text.slice(cursor, index)));
    parts.push(`<mark class="${HIT_CLASS}">${escapeHtml(text.slice(index, index + needle.length))}</mark>`);
    cursor = index + needle.length;
    index = haystack.indexOf(needle, cursor);
  }
  if (cursor < text.length) parts.push(escapeHtml(text.slice(cursor)));
  return parts.join("");
}

function applyToCell(cell, query) {
  const original = cell.dataset.searchOriginal;
  if (original == null) return;
  if (!query) {
    cell.innerHTML = original;
    return;
  }
  const text = cell.textContent || "";
  const html = markHtml(text, query);
  cell.innerHTML = html == null ? original : html;
}

function parseOriginal(cell) {
  if (cell.dataset.searchOriginal != null) return;
  cell.dataset.searchOriginal = cell.innerHTML.trim() ? cell.innerHTML : EMPTY;
}

function clearRowHighlight(container) {
  container.querySelectorAll(`tr.${ROW_CLASS}`).forEach((row) => {
    row.classList.remove(ROW_CLASS);
  });
}

function setStatus(statusEl, matches, current, query) {
  if (!statusEl) return;
  if (!query.trim()) {
    statusEl.textContent = "";
    return;
  }
  if (!matches.length) {
    statusEl.textContent = "\u041d\u0438\u0447\u0435\u0433\u043e \u043d\u0435 \u043d\u0430\u0439\u0434\u0435\u043d\u043e";
    return;
  }
  statusEl.textContent = `${current + 1} \u0438\u0437 ${matches.length}`;
}

export function mount({ root, container, bar }) {
  if (!container) return null;
  const scope = bar || root || document;

  const input = scope.querySelector("[data-search-input]");
  const findBtn = scope.querySelector("[data-search-find]");
  const prevBtn = scope.querySelector("[data-search-prev]");
  const nextBtn = scope.querySelector("[data-search-next]");
  const clearBtn = scope.querySelector("[data-search-clear]");
  const statusEl = scope.querySelector("[data-search-status]");

  let query = "";
  let matches = [];
  let current = -1;

  function cells() {
    return Array.from(container.querySelectorAll('td[data-col="big"], td[data-col="small"]'));
  }

  function focusHit(index, { scroll = false } = {}) {
    if (!matches.length) return;
    const wrapped = ((index % matches.length) + matches.length) % matches.length;
    current = wrapped;

    matches.forEach((mark, i) => {
      mark.classList.toggle(CURRENT_CLASS, i === wrapped);
    });

    clearRowHighlight(container);
    const active = matches[wrapped];
    const row = active.closest("tr");
    if (row) row.classList.add(ROW_CLASS);

    if (scroll) {
      active.scrollIntoView({ behavior: "smooth", block: "center", inline: "nearest" });
    }
    setStatus(statusEl, matches, wrapped, query);
  }

  function collect() {
    matches = Array.from(container.querySelectorAll(`mark.${HIT_CLASS}`));
    if (matches.length) {
      current = 0;
      focusHit(0, { scroll: false });
    } else {
      current = -1;
      setStatus(statusEl, matches, -1, query);
    }
  }

  function clearHits() {
    clearRowHighlight(container);
    matches.forEach((mark) => mark.classList.remove(CURRENT_CLASS));
    cells().forEach((cell) => applyToCell(cell, ""));
    matches = [];
    current = -1;
  }

  function refresh() {
    clearHits();
    const needle = query.trim();
    if (!needle) {
      setStatus(statusEl, [], -1, "");
      return;
    }
    cells().forEach((cell) => {
      parseOriginal(cell);
      applyToCell(cell, needle);
    });
    collect();
  }

  function findNearest() {
    refresh();
    if (!matches.length) return;
    const anchor = window.innerHeight / 2;
    let nearest = 0;
    for (let i = 0; i < matches.length; i += 1) {
      const rect = matches[i].getBoundingClientRect();
      nearest = i;
      if (rect.top >= anchor) break;
    }
    focusHit(nearest, { scroll: true });
  }

  function next() {
    if (!matches.length) {
      findNearest();
      return;
    }
    focusHit(current + 1, { scroll: true });
  }

  function prev() {
    if (!matches.length) {
      findNearest();
      return;
    }
    focusHit(current - 1, { scroll: true });
  }

  function setQuery(value) {
    query = String(value ?? "");
    if (input) input.value = query;
    refresh();
  }

  function clear() {
    if (input) input.value = "";
    query = "";
    clearHits();
    setStatus(statusEl, [], -1, "");
  }

  if (input) {
    input.addEventListener("input", () => {
      query = input.value;
      refresh();
    });
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        findNearest();
      } else if (event.key === "Escape") {
        event.preventDefault();
        clear();
      }
    });
  }

  if (findBtn) findBtn.addEventListener("click", findNearest);
  if (nextBtn) nextBtn.addEventListener("click", next);
  if (prevBtn) prevBtn.addEventListener("click", prev);
  if (clearBtn) clearBtn.addEventListener("click", clear);

  return { refresh, findNearest, next, prev, clear, setQuery };
}
