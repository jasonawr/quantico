const statusEl = document.getElementById("workspaceStatus");
const watchBody = document.getElementById("watchlistBody");
const labRunsBody = document.getElementById("labRunsBody");

function token() {
  return localStorage.getItem("jc_session_token") || "";
}

async function api(path, method = "GET", body = null) {
  const headers = {};
  if (token()) headers["Authorization"] = `Bearer ${token()}`;
  if (body !== null) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: body !== null ? JSON.stringify(body) : undefined });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

function renderWatchlists(items) {
  watchBody.innerHTML = items
    .map((x) => `<tr><td>${x.id}</td><td>${x.name}</td><td>${(x.symbols || []).join(", ")}</td></tr>`)
    .join("");
}

function renderLabRuns(items) {
  labRunsBody.innerHTML = items
    .map((x) => `<tr><td>${x.id}</td><td>${x.run_type}</td><td>${x.name}</td><td>${x.created_at}</td></tr>`)
    .join("");
}

async function refreshWatchlists() {
  const data = await api("/api/watchlists");
  renderWatchlists(data.items || []);
}

async function refreshLabRuns() {
  const data = await api("/api/lab/runs?limit=50");
  renderLabRuns(data.items || []);
}

async function saveWatchlist() {
  const name = document.getElementById("wlName").value.trim();
  const symbols = document
    .getElementById("wlSymbols")
    .value.split(",")
    .map((x) => x.trim().toUpperCase())
    .filter(Boolean);
  await api("/api/watchlists", "POST", { name, symbols });
  await refreshWatchlists();
}

async function saveLabSnapshot() {
  const name = document.getElementById("labSaveName").value.trim();
  const payload = {
    run_type: "manual_snapshot",
    name,
    params: { note: "Saved from workspace page" },
    result: { sample_metric: Math.random(), timestamp: new Date().toISOString() },
  };
  await api("/api/lab/runs/save", "POST", payload);
  await refreshLabRuns();
}

function requireAuth() {
  if (!token()) {
    statusEl.textContent = "Login required (open Account page)";
    return false;
  }
  return true;
}

document.getElementById("saveWlBtn").addEventListener("click", () => {
  if (!requireAuth()) return;
  saveWatchlist().then(() => (statusEl.textContent = "Watchlist saved")).catch((e) => (statusEl.textContent = `Error: ${e.message}`));
});
document.getElementById("refreshWlBtn").addEventListener("click", () => {
  if (!requireAuth()) return;
  refreshWatchlists().then(() => (statusEl.textContent = "Watchlists loaded")).catch((e) => (statusEl.textContent = `Error: ${e.message}`));
});
document.getElementById("saveLabBtn").addEventListener("click", () => {
  if (!requireAuth()) return;
  saveLabSnapshot().then(() => (statusEl.textContent = "Lab run saved")).catch((e) => (statusEl.textContent = `Error: ${e.message}`));
});
document.getElementById("refreshLabBtn").addEventListener("click", () => {
  if (!requireAuth()) return;
  refreshLabRuns().then(() => (statusEl.textContent = "Lab runs loaded")).catch((e) => (statusEl.textContent = `Error: ${e.message}`));
});

(async () => {
  if (!requireAuth()) return;
  await refreshWatchlists();
  await refreshLabRuns();
})();
