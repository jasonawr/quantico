const statusEl = document.getElementById("xtStatus");
const quoteBody = document.getElementById("xtQuoteBody");
const heatmapEl = document.getElementById("xtHeatmap");
const alertBody = document.getElementById("xtAlertBody");
const notesBody = document.getElementById("xtNotesBody");
const bookBody = document.getElementById("xtBookBody");
const sentimentSummary = document.getElementById("xtSentimentSummary");
const palette = document.getElementById("cmdPalette");
const cmdInput = document.getElementById("cmdInput");

let boardTimer;
let boardRefreshInFlight = false;
const BOARD_REFRESH_MS = 15000;
const REQUEST_TIMEOUT_MS = 15000;
const LOOKBACK_BY_INTERVAL = {
  "1m": 260,
  "5m": 280,
  "15m": 300,
  "1h": 320,
  "4h": 280,
  "1d": 260,
};

function authHeaders(extra = {}) {
  const token = localStorage.getItem("jc_session_token") || "";
  const headers = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function hasSessionToken() {
  return Boolean(localStorage.getItem("jc_session_token"));
}

function symbolsFromInput() {
  return document
    .getElementById("xtSymbols")
    .value.split(",")
    .map((x) => x.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 40);
}

function boardLookback() {
  const interval = document.getElementById("xtInterval").value;
  return LOOKBACK_BY_INTERVAL[interval] || 320;
}

async function api(path, method = "GET", body = null, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  const options = { method, headers: authHeaders(body !== null ? { "Content-Type": "application/json" } : {}) };
  if (body !== null) options.body = JSON.stringify(body);
  options.signal = controller.signal;
  try {
    const res = await fetch(path, options);
    if (!res.ok) {
      let message = `HTTP ${res.status}`;
      try {
        const payload = await res.json();
        message = payload.detail || JSON.stringify(payload);
      } catch {
        message = await res.text();
      }
      throw new Error(message || `HTTP ${res.status}`);
    }
    return await res.json();
  } catch (err) {
    if (err && err.name === "AbortError") {
      throw new Error(`Request timed out for ${path}`);
    }
    throw err;
  } finally {
    clearTimeout(timeout);
  }
}

function pct(v) {
  return `${(100 * Number(v || 0)).toFixed(2)}%`;
}

function colorPct(v) {
  const n = Number(v || 0);
  if (n > 0) return "#34d399";
  if (n < 0) return "#ff6f61";
  return "#95aa94";
}

function renderQuoteBoard(items) {
  quoteBody.innerHTML = items
    .map(
      (x) => `
      <tr>
        <td>${x.symbol}</td>
        <td>${Number(x.price).toFixed(4)}</td>
        <td style="color:${colorPct(x.change_1)}">${pct(x.change_1)}</td>
        <td style="color:${colorPct(x.change_5)}">${pct(x.change_5)}</td>
        <td style="color:${colorPct(x.change_22)}">${pct(x.change_22)}</td>
        <td>${pct(x.volatility_ann)}</td>
        <td>${pct(x.trend_score)}</td>
        <td>${x.provider || "n/a"}</td>
      </tr>
    `,
    )
    .join("");
}

function buildHeatmapFromBoard(items) {
  if (!items.length) return [];
  const changes = items.map((x) => Number(x.change_1 || 0));
  const lo = Math.min(...changes);
  const hi = Math.max(...changes);
  const denom = hi - lo || 1;
  return items.map((row) => {
    const value = Number(row.change_1 || 0);
    const score = Math.max(0, Math.min(1, (value - lo) / denom));
    const hue = Math.round((1 - score) * 10 + score * 140);
    return {
      symbol: row.symbol,
      value,
      color: `hsl(${hue}, 70%, 45%)`,
      price: Number(row.price || 0),
    };
  });
}

function renderHeatmap(cells) {
  heatmapEl.innerHTML = cells
    .map(
      (c) =>
        `<div class="heat-cell" style="background:${c.color};"><div>${c.symbol}</div><div>${pct(c.value)}</div><div>${Number(c.price).toFixed(2)}</div></div>`,
    )
    .join("");
}

function renderBook(book) {
  const bids = book.bids || [];
  const asks = book.asks || [];
  const rows = Math.max(bids.length, asks.length);
  const html = [];
  for (let i = 0; i < rows; i++) {
    const b = bids[i] || { price: "", size: "" };
    const a = asks[i] || { price: "", size: "" };
    html.push(
      `<tr><td style="color:#34d399">${b.price === "" ? "" : Number(b.price).toFixed(4)}</td><td>${b.size === "" ? "" : Number(b.size).toFixed(2)}</td><td style="color:#ff6f61">${a.price === "" ? "" : Number(a.price).toFixed(4)}</td><td>${a.size === "" ? "" : Number(a.size).toFixed(2)}</td></tr>`,
    );
  }
  bookBody.innerHTML = html.join("");
}

function renderAlerts(items) {
  if (!items.length) {
    alertBody.innerHTML = `<tr><td colspan="4" style="color:#95aa94;">No alerts yet.</td></tr>`;
    return;
  }
  alertBody.innerHTML = items
    .map(
      (a) =>
        `<tr><td>${a.id}</td><td>${a.symbol} ${a.direction} ${a.threshold}</td><td>${a.enabled ? "ON" : "OFF"}</td><td><button data-alert-del="${a.id}">Delete</button> <button data-alert-toggle="${a.id}" data-enabled="${a.enabled ? 0 : 1}">${a.enabled ? "Disable" : "Enable"}</button></td></tr>`,
    )
    .join("");

  document.querySelectorAll("[data-alert-del]").forEach((el) =>
    el.addEventListener("click", async () => {
      try {
        await api(`/api/alerts/${el.getAttribute("data-alert-del")}`, "DELETE");
        await loadAlerts();
      } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
      }
    }),
  );
  document.querySelectorAll("[data-alert-toggle]").forEach((el) =>
    el.addEventListener("click", async () => {
      try {
        const alertId = Number(el.getAttribute("data-alert-toggle"));
        const enabled = Number(el.getAttribute("data-enabled")) === 1;
        await api(`/api/alerts/${alertId}/toggle`, "POST", { enabled });
        await loadAlerts();
      } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
      }
    }),
  );
}

function renderNotes(items) {
  if (!items.length) {
    notesBody.innerHTML = `<tr><td colspan="4" style="color:#95aa94;">No notes yet.</td></tr>`;
    return;
  }
  notesBody.innerHTML = items
    .map(
      (n) =>
        `<tr><td>${n.id}</td><td>${n.title}</td><td>${n.updated_at}</td><td><button data-note-del="${n.id}">Delete</button></td></tr>`,
    )
    .join("");
  document.querySelectorAll("[data-note-del]").forEach((el) =>
    el.addEventListener("click", async () => {
      try {
        await api(`/api/notes/${el.getAttribute("data-note-del")}`, "DELETE");
        await loadNotes();
      } catch (e) {
        statusEl.textContent = `Error: ${e.message}`;
      }
    }),
  );
}

async function refreshBoard({ force = false, quiet = false } = {}) {
  if (boardRefreshInFlight && !force) return;
  boardRefreshInFlight = true;
  const payload = {
    symbols: symbolsFromInput(),
    interval: document.getElementById("xtInterval").value,
    lookback: boardLookback(),
  };
  const startedAt = performance.now();
  try {
    const board = await api("/api/board/quotes", "POST", payload);
    const items = board.items || [];
    renderQuoteBoard(items);
    renderHeatmap(buildHeatmapFromBoard(items));
    const elapsed = ((performance.now() - startedAt) / 1000).toFixed(2);
    if (!quiet) {
      statusEl.textContent = `Board updated (${items.length} symbols) in ${elapsed}s`;
    }
  } finally {
    boardRefreshInFlight = false;
  }
}

async function loadOrderBook() {
  const symbol = document.getElementById("xtBookSymbol").value.toUpperCase();
  const book = await api(`/api/board/orderbook?symbol=${encodeURIComponent(symbol)}`);
  renderBook(book);
}

async function loadSentiment() {
  const query = document.getElementById("xtNewsQuery").value.trim() || "markets";
  const s = await api("/api/board/news-sentiment", "POST", { query, max_items: 24 });
  sentimentSummary.innerHTML = `<div><strong>Regime:</strong> ${s.regime}</div><div><strong>Avg sentiment:</strong> ${Number(s.avg_sentiment).toFixed(4)}</div><div><strong>Headlines:</strong> ${(s.items || []).length}</div>`;
}

async function loadAlerts() {
  if (!hasSessionToken()) {
    alertBody.innerHTML = `<tr><td colspan="4" style="color:#95aa94;">Sign in on Account page to use alerts.</td></tr>`;
    return;
  }
  const data = await api("/api/alerts");
  renderAlerts(data.items || []);
}

async function createAlert() {
  if (!hasSessionToken()) {
    statusEl.textContent = "Please sign in first to create alerts.";
    return;
  }
  const payload = {
    symbol: document.getElementById("xtAlertSymbol").value.toUpperCase(),
    direction: document.getElementById("xtAlertDirection").value,
    threshold: Number(document.getElementById("xtAlertThreshold").value),
    message: document.getElementById("xtAlertMessage").value,
  };
  await api("/api/alerts", "POST", payload);
  await loadAlerts();
  statusEl.textContent = "Alert created";
}

async function scanAlerts() {
  if (!hasSessionToken()) {
    statusEl.textContent = "Please sign in first to scan alerts.";
    return;
  }
  const data = await api("/api/alerts/scan", "POST", {});
  const hits = data.triggered || [];
  if (hits.length > 0) {
    statusEl.textContent = `Triggered: ${hits.map((h) => h.symbol).join(", ")}`;
  } else {
    statusEl.textContent = "No alerts triggered";
  }
}

async function loadNotes() {
  if (!hasSessionToken()) {
    notesBody.innerHTML = `<tr><td colspan="4" style="color:#95aa94;">Sign in on Account page to use research notes.</td></tr>`;
    return;
  }
  const data = await api("/api/notes?limit=100");
  renderNotes(data.items || []);
}

async function saveNote() {
  if (!hasSessionToken()) {
    statusEl.textContent = "Please sign in first to save notes.";
    return;
  }
  await api("/api/notes", "POST", {
    title: document.getElementById("xtNoteTitle").value,
    body: document.getElementById("xtNoteBody").value,
  });
  await loadNotes();
  statusEl.textContent = "Note saved";
}

function openPalette() {
  palette.classList.remove("hidden");
  cmdInput.value = "";
  cmdInput.focus();
}

function closePalette() {
  palette.classList.add("hidden");
}

async function executeCommand(raw) {
  const text = raw.trim();
  if (!text) return;
  const lower = text.toLowerCase();
  if (lower.startsWith("board ")) {
    const syms = text.slice(6).split(",").map((x) => x.trim().toUpperCase()).filter(Boolean);
    document.getElementById("xtSymbols").value = syms.join(",");
    await refreshBoard();
    return;
  }
  if (lower.startsWith("alert ")) {
    const parts = text.split(/\s+/);
    if (parts.length >= 4) {
      document.getElementById("xtAlertSymbol").value = parts[1].toUpperCase();
      document.getElementById("xtAlertDirection").value = parts[2].toLowerCase();
      document.getElementById("xtAlertThreshold").value = parts[3];
      await createAlert();
      return;
    }
  }
  if (lower.startsWith("note ")) {
    const body = text.slice(5);
    const split = body.split("|");
    document.getElementById("xtNoteTitle").value = (split[0] || "Desk Note").trim();
    document.getElementById("xtNoteBody").value = (split[1] || split[0] || "").trim();
    await saveNote();
    return;
  }
  if (lower.startsWith("news ")) {
    document.getElementById("xtNewsQuery").value = text.slice(5).trim();
    await loadSentiment();
    return;
  }
  statusEl.textContent = "Unknown command";
}

document.getElementById("xtRefreshBoardBtn").addEventListener("click", () => refreshBoard().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtScanAlertsBtn").addEventListener("click", () => scanAlerts().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtCreateAlertBtn").addEventListener("click", () => createAlert().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtSaveNoteBtn").addEventListener("click", () => saveNote().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtBookBtn").addEventListener("click", () => loadOrderBook().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtNewsBtn").addEventListener("click", () => loadSentiment().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("xtInterval").addEventListener("change", () => refreshBoard({ force: true }).catch((e) => (statusEl.textContent = `Error: ${e.message}`)));

window.addEventListener("keydown", (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openPalette();
  }
  if (e.key === "Escape") {
    closePalette();
  }
});

cmdInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const text = cmdInput.value;
    executeCommand(text)
      .then(() => closePalette())
      .catch((err) => {
        statusEl.textContent = `Error: ${err.message}`;
        closePalette();
      });
  }
});

(async () => {
  statusEl.textContent = "Loading board...";
  const initialJobs = await Promise.allSettled([refreshBoard({ force: true }), loadOrderBook()]);
  const failures = initialJobs.filter((j) => j.status === "rejected");
  if (failures.length > 0) {
    const reason = failures[0].reason?.message || String(failures[0].reason || "unknown error");
    statusEl.textContent = `Partial load: ${reason}`;
  }

  window.setTimeout(() => {
    loadSentiment().catch(() => {});
    if (hasSessionToken()) {
      loadAlerts().catch(() => {});
      loadNotes().catch(() => {});
    } else {
      renderAlerts([]);
      renderNotes([]);
    }
  }, 50);

  if (boardTimer) clearInterval(boardTimer);
  boardTimer = setInterval(() => refreshBoard({ quiet: true }).catch(() => {}), BOARD_REFRESH_MS);
})();
