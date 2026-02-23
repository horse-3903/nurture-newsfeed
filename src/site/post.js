const els = {
  loading: document.getElementById("postLoading"),
  error: document.getElementById("postError"),
  card: document.getElementById("postCard"),
  title: document.getElementById("postTitle"),
  body: document.getElementById("postBody"),
  date: document.getElementById("postDate"),
  author: document.getElementById("postAuthor"),
  sourceLink: document.getElementById("sourceLink"),
};

function getItemIdFromQuery() {
  const params = new URLSearchParams(window.location.search);
  return params.get("id");
}

function readCacheItems(payload) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload.items)) return payload.items;
  return [];
}

function formatDate(item) {
  if (item.pub_date_raw && item.pub_date) {
    const dt = new Date(item.pub_date);
    if (!Number.isNaN(dt.getTime())) {
      return `${item.pub_date_raw} (est. ${dt.toLocaleString()})`;
    }
    return item.pub_date_raw;
  }
  if (item.pub_date_raw) return item.pub_date_raw;
  if (item.pub_date) {
    const dt = new Date(item.pub_date);
    if (!Number.isNaN(dt.getTime())) return dt.toLocaleString();
    return item.pub_date;
  }
  return "Date unavailable";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function renderPost(item) {
  document.title = `${item.title || "Announcement"} | Nurture Announcements`;
  els.title.textContent = item.title || "Untitled announcement";
  els.body.innerHTML = item.description
    ? escapeHtml(item.description).replaceAll("\n", "<br>")
    : "<em>No content available in cache for this item yet.</em>";
  els.date.textContent = formatDate(item);

  if (item.author) {
    els.author.textContent = item.author;
    els.author.classList.remove("hidden");
  }

  if (item.link) {
    els.sourceLink.href = item.link;
  } else {
    els.sourceLink.classList.add("hidden");
  }

  els.loading.classList.add("hidden");
  els.card.classList.remove("hidden");
}

function showError(message) {
  els.loading.classList.add("hidden");
  els.error.textContent = message;
  els.error.classList.remove("hidden");
}

async function loadPost() {
  const id = getItemIdFromQuery();
  if (!id) {
    showError("Missing announcement id in URL.");
    return;
  }

  try {
    const resp = await fetch("./cache.json", { cache: "no-store" });
    if (!resp.ok) throw new Error(`Failed to load cache.json (${resp.status})`);
    const payload = await resp.json();
    const items = readCacheItems(payload);
    const item = items.find((entry) => entry.id === id);

    if (!item) {
      showError("Announcement not found in cache. It may have been pruned or not generated yet.");
      return;
    }

    renderPost(item);
  } catch (err) {
    showError(String(err && err.message ? err.message : err));
  }
}

loadPost();

