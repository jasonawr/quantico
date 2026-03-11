const statusEl = document.getElementById("status");
const strategyEl = document.getElementById("strategy");
const metricsEl = document.getElementById("metrics");
const tradesBody = document.getElementById("tradesBody");
const liveTicker = document.getElementById("liveTicker");
const newsList = document.getElementById("newsList");
const symbolEl = document.getElementById("symbol");
const suggestionsEl = document.getElementById("symbolSuggestions");
const companyCard = document.getElementById("companyCard");
const mlStatsEl = document.getElementById("mlStats");

const plotTheme = {
  paper_bgcolor: "#0f1420",
  plot_bgcolor: "#0f1420",
  font: { color: "#dce5ff", family: "Space Grotesk, sans-serif" },
  margin: { l: 45, r: 20, t: 35, b: 40 },
};

async function loadStrategies() {
  const res = await fetch("/api/strategies");
  const data = await res.json();
  strategyEl.innerHTML = data
    .map((s) => `<option value="${s.key}">${s.name} (${s.complexity})</option>`)
    .join("");
}

function showCompanyCard(company) {
  const cap = company.market_cap ? Number(company.market_cap).toLocaleString() : "n/a";
  companyCard.innerHTML = [
    `<div style="font-weight:700; color:#dce5ff;">${company.name || company.symbol}</div>`,
    `<div>${company.symbol} | ${company.exchange || "Unknown exchange"}</div>`,
    `<div>Sector: ${company.sector || "n/a"} | Industry: ${company.industry || "n/a"}</div>`,
    `<div>Market Cap: ${cap} | FWD PE: ${company.forward_pe ?? "n/a"} | Beta: ${company.beta ?? "n/a"}</div>`,
  ].join("");
}

async function loadCompany(symbol) {
  try {
    const res = await fetch(`/api/company?symbol=${encodeURIComponent(symbol)}`);
    if (!res.ok) return;
    const company = await res.json();
    showCompanyCard(company);
  } catch {
    companyCard.textContent = "Company profile unavailable for this symbol.";
  }
}

let searchTimer;
async function updateSuggestions(query) {
  if (query.length < 2) {
    suggestionsEl.innerHTML = "";
    return;
  }
  const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
  if (!res.ok) return;
  const data = await res.json();
  suggestionsEl.innerHTML = data.items
    .map((x) => `<option value="${x.symbol}">${x.name} | ${x.exchange}</option>`)
    .join("");
}

async function loadNews(query) {
  const res = await fetch(`/api/news?query=${encodeURIComponent(query || "bitcoin")}`);
  if (!res.ok) {
    newsList.innerHTML = "<div style='color:#ff6b6b;'>News unavailable</div>";
    return;
  }
  const data = await res.json();
  newsList.innerHTML = data.items
    .map(
      (x) =>
        `<div class="news-item"><a href="${x.link}" target="_blank" rel="noopener noreferrer">${x.title}</a><div>${x.source || "News"} | ${x.pub_date || ""}</div></div>`,
    )
    .join("");
}

async function loadMlReport(symbol, interval, lookback) {
  try {
    const res = await fetch(
      `/api/ml/report?symbol=${encodeURIComponent(symbol)}&interval=${encodeURIComponent(interval)}&lookback=${encodeURIComponent(lookback)}`,
    );
    if (!res.ok) {
      mlStatsEl.textContent = "ML report unavailable";
      Plotly.purge("mlChart");
      return;
    }
    const payload = await res.json();
    const r = payload.report || {};
    mlStatsEl.textContent = `Accuracy ${(100 * (r.accuracy || 0)).toFixed(1)}% | Precision ${(100 * (r.precision || 0)).toFixed(1)}% | Recall ${(100 * (r.recall || 0)).toFixed(1)}% | F1 ${(r.f1 || 0).toFixed(3)} | N ${r.observations || 0}`;

    const recent = r.recent_probabilities || [];
    if (recent.length < 2) {
      Plotly.purge("mlChart");
      return;
    }
    Plotly.newPlot(
      "mlChart",
      [
        {
          x: recent.map((x) => x.time),
          y: recent.map((x) => x.prob_up),
          type: "scatter",
          mode: "lines",
          line: { color: "#ffd166", width: 2 },
          name: "P(up)",
        },
      ],
      {
        ...plotTheme,
        title: "ML Up-Probability",
        yaxis: { title: "Probability", range: [0, 1] },
        xaxis: { title: "Time" },
      },
      { responsive: true },
    );
  } catch {
    mlStatsEl.textContent = "ML report unavailable";
  }
}

function renderMetrics(metrics) {
  const entries = [
    ["Total Return", `${(metrics.total_return * 100).toFixed(2)}%`],
    ["Annualized", `${(metrics.annualized_return * 100).toFixed(2)}%`],
    ["Sharpe", metrics.sharpe.toFixed(2)],
    ["Sortino", metrics.sortino.toFixed(2)],
    ["Volatility", `${(metrics.volatility * 100).toFixed(2)}%`],
    ["Max Drawdown", `${(metrics.max_drawdown * 100).toFixed(2)}%`],
    ["Win Rate", `${(metrics.win_rate * 100).toFixed(2)}%`],
    ["Turnover", metrics.turnover.toFixed(3)],
    ["Trades", metrics.trades_est],
  ];
  metricsEl.innerHTML = entries
    .map(([k, v]) => `<div class="metric"><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
}

function renderTrades(trades) {
  tradesBody.innerHTML = trades
    .slice(-50)
    .reverse()
    .map(
      (t) => `<tr><td>${new Date(t.time).toLocaleString()}</td><td>${t.price.toFixed(2)}</td><td>${t.position.toFixed(3)}</td></tr>`,
    )
    .join("");
}

function renderCharts(payload) {
  const eqX = payload.equity_curve.map((x) => x.time);
  const eqY = payload.equity_curve.map((x) => x.equity);
  const ddY = payload.drawdown_curve.map((x) => x.drawdown * 100);

  Plotly.newPlot(
    "equityChart",
    [
      {
        x: eqX,
        y: eqY,
        type: "scatter",
        mode: "lines",
        line: { color: "#1de9b6", width: 2.2 },
        name: "Equity",
      },
    ],
    {
      ...plotTheme,
      title: "Equity Curve",
      yaxis: { title: "Portfolio Value" },
      xaxis: { title: "Time" },
    },
    { responsive: true },
  );

  Plotly.newPlot(
    "drawdownChart",
    [
      {
        x: eqX,
        y: ddY,
        type: "scatter",
        mode: "lines",
        line: { color: "#ff6b6b", width: 2 },
        fill: "tozeroy",
        fillcolor: "rgba(255,107,107,0.2)",
      },
    ],
    {
      ...plotTheme,
      title: "Drawdown",
      yaxis: { title: "%", ticksuffix: "%" },
      xaxis: { title: "Time" },
    },
    { responsive: true },
  );

  const mc = payload.monte_carlo;
  if (!mc || !mc.percentiles || !mc.percentiles.p50) {
    Plotly.purge("mcChart");
    return;
  }

  const x = mc.percentiles.p50.map((_, i) => i);
  Plotly.newPlot(
    "mcChart",
    [
      {
        x,
        y: mc.percentiles.p90,
        mode: "lines",
        line: { color: "rgba(79,195,247,0)" },
        showlegend: false,
        hoverinfo: "skip",
      },
      {
        x,
        y: mc.percentiles.p10,
        mode: "lines",
        line: { color: "rgba(79,195,247,0)" },
        fill: "tonexty",
        fillcolor: "rgba(79,195,247,0.25)",
        name: "10-90% Band",
      },
      {
        x,
        y: mc.percentiles.p50,
        mode: "lines",
        line: { color: "#4fc3f7", width: 2.2 },
        name: "Median Path",
      },
    ],
    {
      ...plotTheme,
      title: "Monte Carlo PnL Cone",
      yaxis: { title: "Growth of $1" },
      xaxis: { title: "Forward Steps" },
    },
    { responsive: true },
  );
}

async function runBacktest() {
  statusEl.textContent = "Running research/backtest...";
  const payload = {
    symbol: symbolEl.value.toUpperCase(),
    interval: document.getElementById("interval").value,
    lookback: Number(document.getElementById("lookback").value),
    strategy: document.getElementById("strategy").value,
    initial_capital: Number(document.getElementById("initialCapital").value),
    fee_bps: Number(document.getElementById("feeBps").value),
  };

  const res = await fetch("/api/backtest", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    let msg = "Unknown API error";
    try {
      const body = await res.json();
      msg = body.detail || JSON.stringify(body);
    } catch {
      msg = await res.text();
    }
    statusEl.textContent = `Error: ${msg}`;
    return;
  }

  const data = await res.json();
  renderMetrics(data.metrics);
  renderTrades(data.trades);
  renderCharts(data);
  statusEl.textContent = `Done: ${data.strategy} on ${data.symbol}`;
  connectTicker(payload.symbol);
  loadNews(payload.symbol);
  loadCompany(payload.symbol);
  loadMlReport(payload.symbol, payload.interval, payload.lookback);
}

let tickerTimer;
function connectTicker(symbol) {
  if (tickerTimer) clearInterval(tickerTimer);

  const update = async () => {
    try {
      const res = await fetch(`/api/ticker?symbol=${encodeURIComponent(symbol)}`);
      if (!res.ok) {
        liveTicker.textContent = "Live: unavailable";
        return;
      }
      const msg = await res.json();
      const provider = msg.provider ? ` [${msg.provider}]` : "";
      liveTicker.textContent = `Live ${msg.symbol}: ${Number(msg.price).toFixed(4)}${provider}`;
    } catch {
      liveTicker.textContent = "Live: unavailable";
    }
  };

  update();
  tickerTimer = setInterval(update, 2000);
}

document.getElementById("runBtn").addEventListener("click", runBacktest);
symbolEl.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => updateSuggestions(symbolEl.value.trim().toUpperCase()), 250);
});
symbolEl.addEventListener("change", () => loadCompany(symbolEl.value.trim().toUpperCase()));

(async () => {
  await loadStrategies();
  await loadNews("bitcoin");
  await loadCompany(symbolEl.value.trim().toUpperCase());
  await runBacktest();
})();
