from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import HTTPException

from app.data.binance import fetch_klines, fetch_ticker
from app.data.news import fetch_news
from app.research.backtest import run_backtest
from app.schemas.quant import BacktestRequest, BacktestResponse, StrategyInfo
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
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Ticker provider error: {exc}") from exc


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
