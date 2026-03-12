const statusEl = document.getElementById("paperStatus");
const metricsEl = document.getElementById("paperMetrics");
const positionsBody = document.getElementById("paperPositionsBody");
const fillsBody = document.getElementById("paperFillsBody");

const theme = {
  paper_bgcolor: "#0f1420",
  plot_bgcolor: "#0f1420",
  font: { color: "#dce5ff", family: "Space Grotesk, sans-serif" },
  margin: { l: 45, r: 20, t: 35, b: 40 },
};

function renderMetrics(state) {
  const entries = [
    ["Cash", Number(state.cash || 0).toFixed(2)],
    ["Position Value", Number(state.position_value || 0).toFixed(2)],
    ["Equity", Number(state.equity || 0).toFixed(2)],
    ["Open Positions", Object.keys(state.positions || {}).length],
  ];
  metricsEl.innerHTML = entries.map(([k, v]) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
}

function renderTables(state) {
  const pos = state.positions || {};
  const px = state.last_prices || {};
  positionsBody.innerHTML = Object.keys(pos)
    .map((s) => `<tr><td>${s}</td><td>${Number(pos[s]).toFixed(6)}</td><td>${Number(px[s] || 0).toFixed(4)}</td></tr>`)
    .join("");

  fillsBody.innerHTML = (state.fills || [])
    .slice(-50)
    .reverse()
    .map((f) => `<tr><td>${new Date(f.time).toLocaleString()}</td><td>${f.symbol}</td><td>${Number(f.quantity).toFixed(6)}</td><td>${Number(f.price).toFixed(4)}</td></tr>`)
    .join("");
}

function renderCurve(state) {
  const eq = state.equity_curve || [];
  if (!eq.length) return Plotly.purge("paperEquityChart");
  Plotly.newPlot(
    "paperEquityChart",
    [{ x: eq.map((x) => x.time), y: eq.map((x) => x.equity), mode: "lines", type: "scatter", line: { color: "#1de9b6", width: 2.2 } }],
    { ...theme, title: "Paper Equity Curve", xaxis: { title: "Time" }, yaxis: { title: "Equity" } },
    { responsive: true },
  );
}

async function post(path, payload) {
  const res = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function getState() {
  const res = await fetch("/api/paper/state");
  if (!res.ok) throw new Error(await res.text());
  return await res.json();
}

async function refreshState() {
  const state = await getState();
  renderMetrics(state);
  renderTables(state);
  renderCurve(state);
  statusEl.textContent = "State updated";
}

async function resetPaper() {
  statusEl.textContent = "Resetting...";
  const cash = Number(document.getElementById("paperCash").value);
  const state = await post("/api/paper/reset", { cash });
  renderMetrics(state);
  renderTables(state);
  renderCurve(state);
  statusEl.textContent = "Portfolio reset";
}

async function placeOrder() {
  statusEl.textContent = "Submitting order...";
  const symbol = document.getElementById("paperSymbol").value.toUpperCase();
  const quantity = Number(document.getElementById("paperQty").value);
  const state = await post("/api/paper/order", { symbol, quantity });
  renderMetrics(state);
  renderTables(state);
  renderCurve(state);
  statusEl.textContent = "Order filled";
}

async function markPaper() {
  statusEl.textContent = "Marking to market...";
  const symbols = document
    .getElementById("paperMarks")
    .value.split(",")
    .map((x) => x.trim().toUpperCase())
    .filter(Boolean);
  const state = await post("/api/paper/mark", { symbols });
  renderMetrics(state);
  renderTables(state);
  renderCurve(state);
  statusEl.textContent = "Marked";
}

document.getElementById("paperResetBtn").addEventListener("click", () => resetPaper().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("paperOrderBtn").addEventListener("click", () => placeOrder().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("paperMarkBtn").addEventListener("click", () => markPaper().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));
document.getElementById("paperRefreshBtn").addEventListener("click", () => refreshState().catch((e) => (statusEl.textContent = `Error: ${e.message}`)));

(async () => {
  await refreshState();
})();
