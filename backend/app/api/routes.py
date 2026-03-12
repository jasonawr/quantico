from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi import HTTPException

from app.data.binance import fetch_company_profile, fetch_klines, fetch_symbol_search, fetch_ticker
from app.data.news import fetch_news
from app.research.backtest import run_backtest
from app.research.catalog import research_catalog
from app.research.lab import run_strategy_lab
from app.research.ml import build_ml_report
from app.research.paper import mark_to_market, place_order, reset_paper, state as paper_state
from app.research.portfolio import optimize_portfolio
from app.research.rotation import simulate_strategy_rotation
from app.research.screener import run_market_screener
from app.core.db import (
    create_session,
    create_user,
    delete_session,
    delete_watchlist,
    get_paper_account,
    get_user_by_email,
    get_user_by_session,
    list_lab_runs,
    list_watchlists,
    save_lab_run,
    set_paper_account,
    upsert_watchlist,
    verify_password,
)
from app.schemas.quant import (
    BacktestRequest,
    BacktestResponse,
    LabRunSaveRequest,
    LoginRequest,
    PortfolioOptimizeRequest,
    PaperMarkRequest,
    PaperOrderRequest,
    PaperResetRequest,
    RegisterRequest,
    RotationRequest,
    ScreenerRequest,
    StrategyLabRequest,
    StrategyInfo,
    WatchlistUpsertRequest,
)
from app.strategies.registry import STRATEGIES

router = APIRouter()


def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    return request.headers.get("X-Session-Token", "").strip()


def _require_user(request: Request) -> dict:
    token = _extract_token(request)
    user = get_user_by_session(token)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/strategies", response_model=list[StrategyInfo])
def get_strategies() -> list[StrategyInfo]:
    return [
        StrategyInfo(
            key=s.key,
            name=s.name,
            description=s.description,
            complexity=s.complexity,
        )
        for s in STRATEGIES.values()
    ]


@router.get("/strategies/catalog")
def strategies_catalog() -> dict:
    return research_catalog()


@router.post("/auth/register")
async def auth_register(payload: RegisterRequest) -> dict:
    user = create_user(payload.email, payload.password, payload.display_name)
    token = create_session(int(user["id"]))
    return {"token": token, "user": user}


@router.post("/auth/login")
async def auth_login(payload: LoginRequest) -> dict:
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token = create_session(int(user["id"]))
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    return {"token": token, "user": safe_user}


@router.post("/auth/logout")
async def auth_logout(request: Request) -> dict:
    token = _extract_token(request)
    if token:
        delete_session(token)
    return {"ok": True}


@router.get("/auth/me")
async def auth_me(request: Request) -> dict:
    user = _require_user(request)
    return {"user": user}


@router.get("/watchlists")
async def watchlists_list(request: Request) -> dict:
    user = _require_user(request)
    return {"items": list_watchlists(int(user["id"]))}


@router.post("/watchlists")
async def watchlists_upsert(request: Request, payload: WatchlistUpsertRequest) -> dict:
    user = _require_user(request)
    try:
        item = upsert_watchlist(int(user["id"]), payload.name, payload.symbols)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item


@router.delete("/watchlists/{watchlist_id}")
async def watchlists_delete(request: Request, watchlist_id: int) -> dict:
    user = _require_user(request)
    delete_watchlist(int(user["id"]), watchlist_id)
    return {"ok": True}


@router.get("/news")
async def news(query: str = "bitcoin") -> dict:
    try:
        items = await fetch_news(query=query, max_items=12)
        return {"query": query, "items": items}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"News provider error: {exc}") from exc


@router.get("/ticker")
async def ticker(symbol: str = "BTCUSDT") -> dict:
    try:
        return await fetch_ticker(symbol)
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Ticker provider error: {exc}") from exc


@router.get("/search")
async def search(q: str) -> dict:
    if len(q.strip()) < 2:
        return {"items": []}
    try:
        return {"items": await fetch_symbol_search(q, limit=12)}
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Search provider error: {exc}") from exc


@router.get("/company")
async def company(symbol: str) -> dict:
    try:
        return await fetch_company_profile(symbol)
    except (httpx.HTTPError, ValueError, IndexError) as exc:
        raise HTTPException(status_code=502, detail=f"Company provider error: {exc}") from exc


@router.post("/backtest", response_model=BacktestResponse)
async def backtest(payload: BacktestRequest) -> BacktestResponse:
    try:
        df = await fetch_klines(payload.symbol, payload.interval, payload.lookback)
        result = run_backtest(
            df=df,
            strategy_key=payload.strategy,
            interval=payload.interval,
            initial_capital=payload.initial_capital,
            fee_bps=payload.fee_bps,
        )
        return BacktestResponse(
            strategy=payload.strategy,
            symbol=payload.symbol,
            metrics=result["metrics"],
            equity_curve=result["equity_curve"],
            drawdown_curve=result["drawdown_curve"],
            trades=result["trades"],
            monte_carlo=result["monte_carlo"],
        )
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Market data provider error: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ml/report")
async def ml_report(symbol: str = "BTCUSDT", interval: str = "1h", lookback: int = 1200) -> dict:
    try:
        df = await fetch_klines(symbol, interval, lookback)
        report = build_ml_report(df)
        return {"symbol": symbol.upper(), "interval": interval, "report": report}
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"ML report error: {exc}") from exc


@router.post("/screener")
async def screener(payload: ScreenerRequest) -> dict:
    try:
        return await run_market_screener(payload.symbols, payload.interval, payload.lookback)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio/optimize")
async def portfolio_optimize(payload: PortfolioOptimizeRequest) -> dict:
    try:
        return await optimize_portfolio(payload.symbols, payload.interval, payload.lookback, payload.risk_aversion)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lab/run")
async def lab_run(payload: StrategyLabRequest) -> dict:
    try:
        return await run_strategy_lab(
            symbols=payload.symbols,
            interval=payload.interval,
            lookback=payload.lookback,
            train_ratio=payload.train_ratio,
            top_n=payload.top_n,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lab/rotate")
async def lab_rotate(payload: RotationRequest) -> dict:
    try:
        return await simulate_strategy_rotation(
            symbol=payload.symbol,
            interval=payload.interval,
            lookback=payload.lookback,
            rebalance_window=payload.rebalance_window,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/lab/runs/save")
async def lab_runs_save(request: Request, payload: LabRunSaveRequest) -> dict:
    user = _require_user(request)
    return save_lab_run(int(user["id"]), payload.run_type, payload.name, payload.params, payload.result)


@router.get("/lab/runs")
async def lab_runs_list(request: Request, limit: int = 30) -> dict:
    user = _require_user(request)
    limit_n = min(max(1, limit), 200)
    return {"items": list_lab_runs(int(user["id"]), limit_n)}


@router.post("/paper/reset")
async def paper_reset(payload: PaperResetRequest, request: Request) -> dict:
    user = get_user_by_session(_extract_token(request))
    if not user:
        return reset_paper(payload.cash)
    account = {
        "cash": payload.cash,
        "positions": {},
        "last_prices": {},
        "fills": [],
        "equity_curve": [],
    }
    return set_paper_account(int(user["id"]), account)


@router.post("/paper/order")
async def paper_order(payload: PaperOrderRequest, request: Request) -> dict:
    user = get_user_by_session(_extract_token(request))
    if user:
        try:
            account = get_paper_account(int(user["id"]))
            tick = await fetch_ticker(payload.symbol.strip().upper())
            px = float(tick.get("price", 0.0))
            if px <= 0:
                raise ValueError("Invalid market price.")
            qty = float(payload.quantity)
            if abs(qty) < 1e-12:
                raise ValueError("Quantity cannot be zero.")
            notional = qty * px
            fee = abs(notional) * 0.0005
            new_cash = float(account["cash"]) - notional - fee
            if new_cash < -1e-9:
                raise ValueError("Insufficient cash for this order.")
            positions = dict(account["positions"])
            prices = dict(account["last_prices"])
            fills = list(account["fills"])
            curve = list(account["equity_curve"])
            sym = payload.symbol.strip().upper()
            positions[sym] = float(positions.get(sym, 0.0)) + qty
            prices[sym] = px
            fills.append(
                {
                    "time": datetime.now(timezone.utc).isoformat(),
                    "symbol": sym,
                    "quantity": qty,
                    "price": px,
                    "notional": notional,
                    "fee": fee,
                }
            )
            account = {
                "cash": new_cash,
                "positions": positions,
                "last_prices": prices,
                "fills": fills[-500:],
                "equity_curve": curve[-2000:],
            }
            return set_paper_account(int(user["id"]), account)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return await place_order(payload.symbol, payload.quantity)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/paper/mark")
async def paper_mark(payload: PaperMarkRequest, request: Request) -> dict:
    user = get_user_by_session(_extract_token(request))
    if user:
        account = get_paper_account(int(user["id"]))
        prices = dict(account["last_prices"])
        for sym in payload.symbols:
            try:
                tick = await fetch_ticker(sym)
                prices[sym.strip().upper()] = float(tick.get("price", 0.0))
            except Exception:  # noqa: BLE001
                continue
        positions = dict(account["positions"])
        cash = float(account["cash"])
        position_value = sum(float(positions.get(s, 0.0)) * float(prices.get(s, 0.0)) for s in positions.keys())
        equity = cash + position_value
        curve = list(account["equity_curve"])
        curve.append(
            {
                "time": datetime.now(timezone.utc).isoformat(),
                "equity": equity,
                "cash": cash,
            }
        )
        updated = {
            "cash": cash,
            "positions": positions,
            "last_prices": prices,
            "fills": list(account["fills"]),
            "equity_curve": curve[-2000:],
        }
        return set_paper_account(int(user["id"]), updated)
    return await mark_to_market(payload.symbols)


@router.get("/paper/state")
async def paper_state_view(request: Request) -> dict:
    user = get_user_by_session(_extract_token(request))
    if user:
        account = get_paper_account(int(user["id"]))
        positions = account["positions"]
        prices = account["last_prices"]
        cash = float(account["cash"])
        position_value = sum(float(positions.get(s, 0.0)) * float(prices.get(s, 0.0)) for s in positions.keys())
        return {
            "cash": cash,
            "positions": positions,
            "last_prices": prices,
            "position_value": position_value,
            "equity": cash + position_value,
            "fills": account["fills"][-300:],
            "equity_curve": account["equity_curve"][-1000:],
        }
    return paper_state.snapshot()


@router.websocket("/ws/ticker")
async def ws_ticker(websocket: WebSocket, symbol: str = "BTCUSDT") -> None:
    await websocket.accept()
    try:
        while True:
            tick = await fetch_ticker(symbol)
            await websocket.send_json(tick)
            await asyncio.sleep(1.0)
    except (WebSocketDisconnect, RuntimeError, httpx.HTTPError):
        return
