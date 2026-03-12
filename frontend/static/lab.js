const labStatus = document.getElementById("labStatus");
const symbolsEl = document.getElementById("labSymbols");
const intervalEl = document.getElementById("labInterval");
const lookbackEl = document.getElementById("labLookback");
const screenerBody = document.getElementById("labScreenerBody");
const resultsBody = document.getElementById("labResultsBody");

function authHeaders(extra = {}) {
  const token = localStorage.getItem("jc_session_token") || "";
  const headers = { ...extra };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

const theme = {
  paper_bgcolor: "#090d10",
  plot_bgcolor: "#090d10",
  font: { color: "#d9e5d4", family: "IBM Plex Mono, monospace" },
  margin: { l: 45, r: 20, t: 35, b: 40 },
};

function symbols() {
  return symbolsEl.value
    .split(",")
    .map((x) => x.trim().toUpperCase())
    .filter(Boolean)
    .slice(0, 20);
}

function renderScreener(items) {
  screenerBody.innerHTML = items
    .slice(0, 20)
    .map((x) => `<tr><td>${x.rank}</td><td>${x.symbol}</td><td>${Number(x.score).toFixed(3)}</td><td>${Number(x.sharpe_120).toFixed(2)}</td></tr>`)
    .join("");
}

function renderResults(items) {
  resultsBody.innerHTML = items
    .slice(0, 40)
    .map(
      (x) =>
        `<tr><td>${x.symbol}</td><td>${x.strategy}</td><td>${Number(x.score).toFixed(3)}</td><td>${Number(x.test_sharpe).toFixed(2)}</td><td>${(100 * Number(x.test_return)).toFixed(2)}%</td></tr>`,
    )
    .join("");
}

function renderAlloc(data) {
  const arr = data.allocations || [];
  if (!arr.length) return Plotly.purge("labAllocChart");
  Plotly.newPlot(
    "labAllocChart",
    [{ type: "pie", hole: 0.55, labels: arr.map((x) => x.symbol), values: arr.map((x) => x.weight) }],
    { ...theme, title: `Optimized Allocation (Sharpe ${Number(data.expected_sharpe || 0).toFixed(2)})` },
    { responsive: true },
  );
}

function renderRotate(data) {
  const eq = data.equity_curve || [];
  if (!eq.length) return Plotly.purge("labRotateChart");
  Plotly.newPlot(
    "labRotateChart",
    [{ x: eq.map((x) => x.time), y: eq.map((x) => x.equity), type: "scatter", mode: "lines", line: { color: "#34d399", width: 2 } }],
    { ...theme, title: `Rotation Equity (${data.symbol})` },
    { responsive: true },
  );
}

async function callApi(path, payload) {
  const res = await fetch(path, { method: "POST", headers: authHeaders({ "Content-Type": "application/json" }), body: JSON.stringify(payload) });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body);
  }
  return await res.json();
}

async function runScreener() {
  labStatus.textContent = "Running screener...";
  const data = await callApi("/api/screener", { symbols: symbols(), interval: intervalEl.value, lookback: Number(lookbackEl.value) });
  renderScreener(data.items || []);
  labStatus.textContent = `Screener done (${data.items?.length || 0})`;
}

async function runOptimize() {
  labStatus.textContent = "Optimizing...";
  const data = await callApi("/api/portfolio/optimize", {
    symbols: symbols(),
    interval: intervalEl.value,
    lookback: Number(lookbackEl.value),
    risk_aversion: 4.0,
  });
  renderAlloc(data);
  labStatus.textContent = "Optimization done";
}

async function runLab() {
  labStatus.textContent = "Running strategy lab...";
  const data = await callApi("/api/lab/run", {
    symbols: symbols(),
    interval: intervalEl.value,
    lookback: Number(lookbackEl.value),
    train_ratio: 0.7,
    top_n: 40,
  });
  renderResults(data.top_results || []);
  labStatus.textContent = `Lab done (${data.top_results?.length || 0})`;
}

async function runRotate() {
  labStatus.textContent = "Running rotation...";
  const data = await callApi("/api/lab/rotate", {
    symbol: symbols()[0] || "BTCUSDT",
    interval: intervalEl.value,
    lookback: Number(lookbackEl.value),
    rebalance_window: 120,
  });
  renderRotate(data);
  labStatus.textContent = "Rotation done";
}

document.getElementById("runScreenerBtn").addEventListener("click", () => runScreener().catch((e) => (labStatus.textContent = `Error: ${e.message}`)));
document.getElementById("runOptimizeBtn").addEventListener("click", () => runOptimize().catch((e) => (labStatus.textContent = `Error: ${e.message}`)));
document.getElementById("runLabBtn").addEventListener("click", () => runLab().catch((e) => (labStatus.textContent = `Error: ${e.message}`)));
document.getElementById("runRotateBtn").addEventListener("click", () => runRotate().catch((e) => (labStatus.textContent = `Error: ${e.message}`)));

(async () => {
  await runScreener();
  await runOptimize();
  await runLab();
  await runRotate();
})();
