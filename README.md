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

## Vercel Deploy
1. Push this repo to GitHub.
2. In Vercel, import the repo and deploy with default settings.
3. Vercel uses `vercel.json`:
- Static frontend served from `frontend/static`
- Python serverless API from `api/index.py`
4. Open your Vercel URL and run backtests from the dashboard.

## Docker Start
1. `docker compose up --build`
2. Open `http://localhost:8000`

## Environment
- Copy `.env.example` to `.env` if you want to override defaults.
- All backend settings are loaded from env vars via pydantic settings.

## API
- `GET /api/health`
- `GET /api/strategies`
- `GET /api/news?query=bitcoin`
- `GET /api/ticker?symbol=BTCUSDT`
- `POST /api/backtest`
- `WS /api/ws/ticker?symbol=BTCUSDT`

## Notes
- This is research software, not financial advice.
- Vercel serverless does not support long-lived websocket sessions in this setup; the UI uses HTTP polling for live ticker updates.
- Add broker/exchange execution adapters only after paper-trading validation.
