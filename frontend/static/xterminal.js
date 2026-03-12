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

function authHeaders(extra = {}) {
  const token = localStorage.getItem("jc_session_token") || "";
  const headers = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function symbolsFromInput() {
  return document
    .getElementById("xtSymbols")
    .value.split(",")
    .map((x) => x.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 40);
}

async function api(path, method = "GET", body = null) {
  const options = { method, headers: authHeaders(body !== null ? { "Content-Type": "application/json" } : {}) };
  if (body !== null) options.body = JSON.stringify(body);
  const res = await fetch(path, options);
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
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

async function refreshBoard() {
  const payload = {
    symbols: symbolsFromInput(),
    interval: document.getElementById("xtInterval").value,
    lookback: 700,
  };
  const [board, heat] = await Promise.all([api("/api/board/quotes", "POST", payload), api("/api/board/heatmap", "POST", payload)]);
  renderQuoteBoard(board.items || []);
  renderHeatmap((heat.heatmap || {}).cells || []);
  statusEl.textContent = `Board updated (${(board.items || []).length} symbols)`;
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
  const data = await api("/api/alerts");
  renderAlerts(data.items || []);
}

async function createAlert() {
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
  const data = await api("/api/alerts/scan", "POST", {});
  const hits = data.triggered || [];
  if (hits.length > 0) {
    statusEl.textContent = `Triggered: ${hits.map((h) => h.symbol).join(", ")}`;
  } else {
    statusEl.textContent = "No alerts triggered";
  }
}

async function loadNotes() {
  const data = await api("/api/notes?limit=100");
  renderNotes(data.items || []);
}

async function saveNote() {
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
  try {
    await Promise.all([refreshBoard(), loadOrderBook(), loadSentiment(), loadAlerts(), loadNotes()]);
    if (boardTimer) clearInterval(boardTimer);
    boardTimer = setInterval(() => refreshBoard().catch(() => {}), 5000);
  } catch (e) {
    statusEl.textContent = `Error: ${e.message}`;
  }
})();
