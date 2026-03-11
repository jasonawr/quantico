from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd

from app.data.binance import fetch_klines
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


def _project_simplex(v: np.ndarray) -> np.ndarray:
    # Euclidean projection onto {w >= 0, sum(w)=1}
    if v.sum() == 1.0 and np.all(v >= 0):
        return v
    n = len(v)
    u = np.sort(v)[::-1]
    cssv = np.cumsum(u)
    rho = np.where(u * np.arange(1, n + 1) > (cssv - 1))[0][-1]
    theta = (cssv[rho] - 1) / (rho + 1.0)
    return np.maximum(v - theta, 0.0)


def _optimize_weights(mu: np.ndarray, cov: np.ndarray, risk_aversion: float, steps: int = 600, lr: float = 0.03) -> np.ndarray:
    n = len(mu)
    w = np.ones(n) / n
    for _ in range(steps):
        grad = -(mu - 2.0 * risk_aversion * (cov @ w))
        w = _project_simplex(w - lr * grad)
    return w


async def _load_symbol_returns(symbol: str, interval: str, lookback: int) -> dict[str, Any]:
    df = await fetch_klines(symbol, interval, lookback)
    r = df["returns"].replace([np.inf, -np.inf], np.nan).dropna()
    if len(r) < 150:
        raise ValueError("Insufficient history")

    probs, _ = walk_forward_probabilities(df)
    ml_prob = float(probs.dropna().iloc[-1]) if probs.dropna().shape[0] else 0.5
    ml_edge = (ml_prob - 0.5) * 2.0

    return {
        "symbol": symbol.upper(),
        "returns": r.tail(800).reset_index(drop=True),
        "ml_edge": ml_edge,
    }


async def optimize_portfolio(symbols: list[str], interval: str, lookback: int, risk_aversion: float) -> dict:
    uniq = [x.strip().upper() for x in symbols if x and x.strip()]
    uniq = list(dict.fromkeys(uniq))[:20]
    if len(uniq) < 2:
        raise ValueError("Provide at least two symbols for optimization.")

    semaphore = asyncio.Semaphore(6)
    errors: list[dict] = []

    async def wrapped(sym: str) -> dict[str, Any] | None:
        async with semaphore:
            try:
                return await _load_symbol_returns(sym, interval, lookback)
            except Exception as exc:  # noqa: BLE001
                errors.append({"symbol": sym, "error": str(exc)})
                return None

    rows = [x for x in await asyncio.gather(*[wrapped(s) for s in uniq]) if x is not None]
    if len(rows) < 2:
        raise ValueError("Not enough valid symbols to optimize.")

    min_len = min(len(x["returns"]) for x in rows)
    if min_len < 120:
        raise ValueError("Not enough overlapping history for optimization.")

    symbols_valid = [x["symbol"] for x in rows]
    ret_matrix = np.vstack([x["returns"].values[-min_len:] for x in rows]).T
    ret_df = pd.DataFrame(ret_matrix, columns=symbols_valid).dropna()
    ret_matrix = ret_df.values

    ann = _annualization_factor(interval)
    mu = ret_matrix.mean(axis=0) * ann
    cov = np.cov(ret_matrix.T) * ann + np.eye(ret_matrix.shape[1]) * 1e-8

    ml_edges = np.array([x["ml_edge"] for x in rows], dtype=float)
    mu_adj = mu + 0.08 * ml_edges

    w = _optimize_weights(mu_adj, cov, risk_aversion=risk_aversion)
    port_ret = float(mu_adj @ w)
    port_vol = float(np.sqrt(max(1e-12, w @ cov @ w)))
    sharpe = float(port_ret / max(1e-9, port_vol))

    allocations = [
        {"symbol": s, "weight": float(weight), "expected_return": float(mu_i), "ml_edge": float(edge)}
        for s, weight, mu_i, edge in zip(symbols_valid, w, mu_adj, ml_edges)
        if weight > 1e-4
    ]
    allocations.sort(key=lambda x: x["weight"], reverse=True)

    return {
        "interval": interval,
        "lookback": lookback,
        "risk_aversion": risk_aversion,
        "expected_return": port_ret,
        "expected_volatility": port_vol,
        "expected_sharpe": sharpe,
        "allocations": allocations,
        "errors": errors,
    }
