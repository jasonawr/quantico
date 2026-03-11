from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import HTTPException

from app.data.binance import fetch_company_profile, fetch_klines, fetch_symbol_search, fetch_ticker
from app.data.news import fetch_news
from app.research.backtest import run_backtest
from app.research.catalog import research_catalog
from app.research.ml import build_ml_report
from app.research.portfolio import optimize_portfolio
from app.research.screener import run_market_screener
from app.schemas.quant import (
    BacktestRequest,
    BacktestResponse,
    PortfolioOptimizeRequest,
    ScreenerRequest,
    StrategyInfo,
)
from app.strategies.registry import STRATEGIES

router = APIRouter()


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
