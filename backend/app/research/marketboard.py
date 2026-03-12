from __future__ import annotations

import asyncio
import copy
import math
import random
import time
from typing import Any

import numpy as np

from app.data.binance import fetch_klines, fetch_ticker
from app.data.news import fetch_news

_BOARD_CACHE_TTL_SECONDS = 12.0
_BOARD_CACHE_MAX_ENTRIES = 64
_BOARD_CACHE: dict[tuple[tuple[str, ...], str, int], tuple[float, dict[str, Any]]] = {}


def _annualization_factor(interval: str) -> float:
    mapping = {
        "1m": 365 * 24 * 60,
        "5m": 365 * 24 * 12,
        "15m": 365 * 24 * 4,
        "1h": 365 * 24,
        "4h": 365 * 6,
        "1d": 365,
    }
    return float(mapping.get(interval, 365))


def _safe(v: float, fallback: float = 0.0) -> float:
    if v is None or math.isnan(v) or math.isinf(v):
        return fallback
    return float(v)


async def _quote_row(symbol: str, interval: str, lookback: int) -> dict[str, Any]:
    symbol_n = symbol.strip().upper()
    kline_task = asyncio.create_task(fetch_klines(symbol_n, interval, max(lookback, 260)))
    tick_task = asyncio.create_task(fetch_ticker(symbol_n))
    df = await kline_task
    tick = await tick_task

    close = df["close"]
    ret = df["returns"].replace([np.inf, -np.inf], np.nan).dropna()

    last = _safe(float(tick.get("price", close.iloc[-1])))
    day_change = _safe(close.pct_change().iloc[-1])
    week_change = _safe(close.pct_change(24 * 7 if interval == "1h" else 5).iloc[-1])
    month_change = _safe(close.pct_change(22 if interval in {"1d", "4h"} else 24 * 22).iloc[-1])
    vol_ann = _safe(ret.tail(180).std() * np.sqrt(_annualization_factor(interval)))
    atr_like = _safe((df["high"] - df["low"]).tail(60).mean() / max(1e-9, close.tail(60).mean()))
    trend = _safe((close.tail(80).mean() / max(1e-9, close.tail(240).mean())) - 1.0)
    liquidity = _safe((df["quote_asset_volume"].tail(120).mean() if "quote_asset_volume" in df else (close * df["volume"]).tail(120).mean()))

    return {
        "symbol": symbol_n,
        "price": last,
        "provider": tick.get("provider", ""),
        "change_1": day_change,
        "change_5": week_change,
        "change_22": month_change,
        "volatility_ann": vol_ann,
        "atr_like": atr_like,
        "trend_score": trend,
        "liquidity": liquidity,
    }


def _normalize_symbols(symbols: list[str]) -> list[str]:
    uniq = [x.strip().upper() for x in symbols if x and x.strip()]
    return list(dict.fromkeys(uniq))[:40]


def _board_cache_key(symbols: list[str], interval: str, lookback: int) -> tuple[tuple[str, ...], str, int]:
    return (tuple(symbols), str(interval), int(lookback))


def _cache_get(key: tuple[tuple[str, ...], str, int]) -> dict[str, Any] | None:
    cached = _BOARD_CACHE.get(key)
    if not cached:
        return None
    ts, value = cached
    if (time.monotonic() - ts) > _BOARD_CACHE_TTL_SECONDS:
        _BOARD_CACHE.pop(key, None)
        return None
    return copy.deepcopy(value)


def _cache_set(key: tuple[tuple[str, ...], str, int], value: dict[str, Any]) -> None:
    _BOARD_CACHE[key] = (time.monotonic(), copy.deepcopy(value))
    if len(_BOARD_CACHE) <= _BOARD_CACHE_MAX_ENTRIES:
        return
    stale = sorted(_BOARD_CACHE.items(), key=lambda item: item[1][0])[: max(1, len(_BOARD_CACHE) // 3)]
    for cache_key, _ in stale:
        _BOARD_CACHE.pop(cache_key, None)


async def quote_board(symbols: list[str], interval: str = "1h", lookback: int = 320) -> dict:
    uniq = _normalize_symbols(symbols)
    if not uniq:
        raise ValueError("No symbols provided.")
    lookback_n = int(max(120, min(5000, int(lookback))))

    cache_key = _board_cache_key(uniq, interval, lookback_n)
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    semaphore = asyncio.Semaphore(6)
    errors: list[dict] = []

    async def wrapped(sym: str) -> dict | None:
        async with semaphore:
            try:
                return await asyncio.wait_for(_quote_row(sym, interval, lookback_n), timeout=12.0)
            except asyncio.TimeoutError:
                errors.append({"symbol": sym, "error": "Timed out while loading market data."})
                return None
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": sym, "error": str(exc)})
                return None

    rows = [x for x in await asyncio.gather(*[wrapped(s) for s in uniq]) if x is not None]
    if not rows:
        raise ValueError("No symbols available from providers.")

    rows = sorted(rows, key=lambda x: x["liquidity"], reverse=True)
    result = {"items": rows, "errors": errors, "interval": interval, "lookback": lookback_n}
    _cache_set(cache_key, result)
    return copy.deepcopy(result)


def _bucket_score(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.5
    return max(0.0, min(1.0, (value - lo) / (hi - lo)))


def build_heatmap(quote_items: list[dict]) -> dict:
    if not quote_items:
        return {"cells": []}
    vals = [float(x.get("change_1", 0.0)) for x in quote_items]
    lo, hi = min(vals), max(vals)
    cells = []
    for row in quote_items:
        ch = float(row.get("change_1", 0.0))
        score = _bucket_score(ch, lo, hi)
        hue = int((1.0 - score) * 10 + score * 140)
        color = f"hsl({hue}, 70%, 45%)"
        cells.append({"symbol": row["symbol"], "value": ch, "color": color, "price": row["price"]})
    return {"cells": cells}


def _headline_sentiment(title: str) -> float:
    pos_words = {"beats", "surge", "rally", "up", "strong", "growth", "record", "gain", "bullish", "outperform"}
    neg_words = {"miss", "drop", "down", "weak", "loss", "lawsuit", "bearish", "cut", "downgrade", "risk"}
    tokens = [t.strip(".,:;!?()[]{}\"'").lower() for t in title.split()]
    score = 0.0
    for tok in tokens:
        if tok in pos_words:
            score += 1.0
        elif tok in neg_words:
            score -= 1.0
    if not tokens:
        return 0.0
    return score / max(1.0, len(tokens) / 8.0)


async def market_news_sentiment(query: str = "markets", max_items: int = 20) -> dict:
    news = await fetch_news(query=query, max_items=max_items)
    items = []
    total = 0.0
    for n in news:
        score = _headline_sentiment(n.get("title", ""))
        total += score
        items.append(
            {
                "title": n.get("title"),
                "source": n.get("source"),
                "pub_date": n.get("pub_date"),
                "link": n.get("link"),
                "sentiment": float(score),
            }
        )
    avg = total / max(1, len(items))
    regime = "neutral"
    if avg > 0.12:
        regime = "risk_on"
    elif avg < -0.12:
        regime = "risk_off"
    return {"query": query, "avg_sentiment": float(avg), "regime": regime, "items": items}


def synthetic_order_book(last_price: float, levels: int = 12) -> dict:
    # Public free APIs do not provide full cross-venue depth in a normalized way here,
    # so this creates a consistent visualizable synthetic book from volatility-scaled bands.
    px = max(1e-9, float(last_price))
    bids = []
    asks = []
    for i in range(1, levels + 1):
        spread = px * 0.0004 * i
        bid_px = px - spread
        ask_px = px + spread
        size_scale = max(0.1, 1.0 - i / (levels + 2))
        bid_size = round(2500 * size_scale * (0.5 + random.random()), 4)
        ask_size = round(2500 * size_scale * (0.5 + random.random()), 4)
        bids.append({"price": bid_px, "size": bid_size})
        asks.append({"price": ask_px, "size": ask_size})
    return {"last_price": px, "bids": bids, "asks": asks}
