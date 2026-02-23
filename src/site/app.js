const els = {
  loading: document.getElementById("loadingBox"),
  error: document.getElementById("errorBox"),
  empty: document.getElementById("emptyState"),
  grid: document.getElementById("cardsGrid"),
  count: document.getElementById("countPill"),
  updated: document.getElementById("updatedPill"),
  search: document.getElementById("searchInput"),
  template: document.getElementById("cardTemplate"),
  themeToggle: document.getElementById("themeToggle"),
};

let allItems = [];
const THEME_KEY = "nurture-feed-theme";

function getPreferredTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  if (els.themeToggle) {
    const isDark = theme === "dark";
    els.themeToggle.textContent = isDark ? "Light mode" : "Dark mode";
    els.themeToggle.setAttribute("aria-pressed", String(isDark));
  }
}

function toggleTheme() {
  const next = document.body.dataset.theme === "dark" ? "light" : "dark";
  localStorage.setItem(THEME_KEY, next);
  applyTheme(next);
}

function readCacheItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

function formatDisplayDate(item) {
  if (item.pub_date_raw) return item.pub_date_raw;
  if (item.pub_date) {
    const d = new Date(item.pub_date);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleString([], {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "numeric",
        minute: "2-digit",
      });
    }
  }
  return "Date unavailable";
}

function sortItems(items) {
  return [...items].sort((a, b) => {
    const aTime = a.pub_date ? Date.parse(a.pub_date) : NaN;
    const bTime = b.pub_date ? Date.parse(b.pub_date) : NaN;
    if (!Number.isNaN(aTime) && !Number.isNaN(bTime)) return bTime - aTime;
    if (!Number.isNaN(aTime)) return -1;
    if (!Number.isNaN(bTime)) return 1;
    return 0;
  });
}

function truncate(text, maxLen = 180) {
  if (!text) return "No preview available.";
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen - 1).trimEnd()}…`;
}

function renderCards(items) {
  els.grid.innerHTML = "";
  const fragment = document.createDocumentFragment();

  for (const item of items) {
    const node = els.template.content.firstElementChild.cloneNode(true);
    const link = node.querySelector(".card__link");
    const dateEl = node.querySelector(".card__date");
    const authorEl = node.querySelector(".card__author");
    const titleEl = node.querySelector(".card__title");
    const descEl = node.querySelector(".card__desc");

    link.href = item.link || "#";
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.setAttribute(
      "aria-label",
      `Open announcement on Nurture: ${item.title || "Untitled"}`
    );

    dateEl.textContent = formatDisplayDate(item);
    if (item.author) {
      authorEl.textContent = item.author;
      authorEl.classList.remove("hidden");
    } else {
      authorEl.classList.add("hidden");
    }

    titleEl.textContent = item.title || "Untitled announcement";
    descEl.textContent = truncate(item.description);
    fragment.appendChild(node);
  }

  els.grid.appendChild(fragment);
  els.count.textContent = `${items.length} announcement${items.length === 1 ? "" : "s"}`;
  els.grid.classList.toggle("hidden", items.length === 0);
  els.empty.classList.toggle("hidden", items.length !== 0);
}

function applySearch() {
  const term = els.search.value.trim().toLowerCase();
  if (!term) {
    renderCards(allItems);
    return;
  }
  const filtered = allItems.filter((item) => {
    const haystack = [item.title, item.description, item.author, item.pub_date_raw]
      .filter(Boolean)
      .join("\n")
      .toLowerCase();
    return haystack.includes(term);
  });
  renderCards(filtered);
}

async function loadAnnouncements() {
  try {
    const resp = await fetch("./cache.json", { cache: "no-store" });
    if (!resp.ok) {
      throw new Error(`Failed to load cache.json (${resp.status})`);
    }
    const payload = await resp.json();
    const items = readCacheItems(payload);
    allItems = sortItems(items);

    if (payload && payload.updated_at_utc) {
      const dt = new Date(payload.updated_at_utc);
      if (!Number.isNaN(dt.getTime())) {
        els.updated.textContent = `Updated ${dt.toLocaleString()}`;
      }
    } else {
      els.updated.textContent = "";
    }

    renderCards(allItems);
    els.loading.classList.add("hidden");
    els.search.addEventListener("input", applySearch);
  } catch (err) {
    els.loading.classList.add("hidden");
    els.error.textContent = String(err && err.message ? err.message : err);
    els.error.classList.remove("hidden");
    els.count.textContent = "Load failed";
  }
}

applyTheme(getPreferredTheme());
if (els.themeToggle) {
  els.themeToggle.addEventListener("click", toggleTheme);
}
loadAnnouncements();
