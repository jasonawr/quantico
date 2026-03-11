# Quant Forge

Dark-mode full-stack quant research and backtesting app with live market data.

## Features
- Real-time ticker stream (WebSocket)
- Real-time finance headlines (Google News RSS query API)
- Multi-strategy research/backtest engine
- Complex MESH composite strategy
- Performance/risk metrics
- Monte Carlo PnL cone chart
- Dark UI with interactive charts

## Stack
- Backend: FastAPI + pandas/numpy/scipy/statsmodels
- Frontend: HTML/CSS/JS + Plotly
- Live data: Binance Spot public API

## Quick Start
1. `python -m pip install -r backend/requirements.txt`
2. `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend`
3. Open `http://localhost:8000`

## API
- `GET /api/health`
- `GET /api/strategies`
- `GET /api/news?query=bitcoin`
- `POST /api/backtest`
- `WS /api/ws/ticker?symbol=BTCUSDT`

## Notes
- This is research software, not financial advice.
- Add broker/exchange execution adapters only after paper-trading validation.
