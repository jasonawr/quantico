from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd

from app.data.binance import fetch_klines, fetch_ticker
from app.research.ml import walk_forward_probabilities


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


def _zscore(values: np.ndarray) -> np.ndarray:
    std = values.std()
    if std == 0:
        return np.zeros_like(values)
    return (values - values.mean()) / std


async def _analyze_symbol(symbol: str, interval: str, lookback: int) -> dict[str, Any]:
    df = await fetch_klines(symbol, interval, lookback)
    returns = df["returns"].dropna()
    if len(returns) < 80:
        raise ValueError("Insufficient history")

    ann = _annualization_factor(interval)
    momentum = float(df["close"].pct_change(30).iloc[-1])
    vol = float(returns.tail(120).std() * np.sqrt(ann))
    sharpe = float((returns.tail(120).mean() / max(1e-9, returns.tail(120).std())) * np.sqrt(ann))

    probs, _ = walk_forward_probabilities(df)
    ml_prob = float(probs.dropna().iloc[-1]) if probs.dropna().shape[0] else 0.5

    try:
        tick = await fetch_ticker(symbol)
        price = float(tick.get("price", df["close"].iloc[-1]))
    except Exception:  # noqa: BLE001
        price = float(df["close"].iloc[-1])

    return {
        "symbol": symbol.upper(),
        "price": price,
        "momentum_30": momentum,
        "volatility_ann": vol,
        "sharpe_120": sharpe,
        "ml_prob_up": ml_prob,
    }


async def run_market_screener(symbols: list[str], interval: str, lookback: int) -> dict:
    uniq = [x.strip().upper() for x in symbols if x and x.strip()]
    uniq = list(dict.fromkeys(uniq))[:30]
    if len(uniq) < 2:
        raise ValueError("Provide at least two symbols for screener.")

    semaphore = asyncio.Semaphore(6)
    errors: list[dict] = []

    async def wrapped(sym: str) -> dict[str, Any] | None:
        async with semaphore:
            try:
                return await _analyze_symbol(sym, interval, lookback)
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": sym, "error": str(exc)})
                return None

    rows = [x for x in await asyncio.gather(*[wrapped(s) for s in uniq]) if x is not None]
    if len(rows) < 2:
        raise ValueError("Unable to compute screener rankings for the requested symbols.")

    frame = pd.DataFrame(rows)
    mom_z = _zscore(frame["momentum_30"].values.astype(float))
    sharpe_z = _zscore(frame["sharpe_120"].values.astype(float))
    vol_z = _zscore(frame["volatility_ann"].values.astype(float))
    ml_edge = (frame["ml_prob_up"].values.astype(float) - 0.5) * 2.0

    frame["score"] = 0.35 * mom_z + 0.25 * sharpe_z - 0.2 * vol_z + 0.2 * ml_edge
    frame = frame.sort_values("score", ascending=False).reset_index(drop=True)
    frame["rank"] = np.arange(1, len(frame) + 1)

    return {
        "interval": interval,
        "lookback": lookback,
        "count": int(len(frame)),
        "leaders": frame.head(3)["symbol"].tolist(),
        "items": frame[
            ["rank", "symbol", "price", "score", "momentum_30", "sharpe_120", "volatility_ann", "ml_prob_up"]
        ].to_dict(orient="records"),
        "errors": errors,
    }
