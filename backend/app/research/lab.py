from __future__ import annotations

import asyncio
from typing import Any

import numpy as np
import pandas as pd

from app.data.binance import fetch_klines
from app.research.backtest import run_backtest
from app.strategies.signals import STRATEGY_FUNCS


def _split_frame(df: pd.DataFrame, train_ratio: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    cut = int(len(df) * train_ratio)
    if cut < 250 or len(df) - cut < 120:
        raise ValueError("Not enough history to split train/test safely.")
    train = df.iloc[:cut].copy()
    test = df.iloc[cut:].copy()
    return train, test


def _safe_metric(metrics: dict, key: str) -> float:
    value = metrics.get(key, 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stability_score(train_metrics: dict, test_metrics: dict) -> float:
    train_sharpe = _safe_metric(train_metrics, "sharpe")
    test_sharpe = _safe_metric(test_metrics, "sharpe")
    train_dd = abs(_safe_metric(train_metrics, "max_drawdown"))
    test_dd = abs(_safe_metric(test_metrics, "max_drawdown"))
    train_turnover = _safe_metric(train_metrics, "turnover")
    test_turnover = _safe_metric(test_metrics, "turnover")

    consistency_penalty = abs(train_sharpe - test_sharpe)
    dd_penalty = 2.5 * test_dd
    turnover_penalty = 0.6 * max(train_turnover, test_turnover)

    return test_sharpe - consistency_penalty - dd_penalty - turnover_penalty


def _pack_record(symbol: str, strategy: str, train_result: dict, test_result: dict) -> dict[str, Any]:
    train_metrics = train_result["metrics"]
    test_metrics = test_result["metrics"]

    return {
        "symbol": symbol,
        "strategy": strategy,
        "score": float(_stability_score(train_metrics, test_metrics)),
        "train_sharpe": _safe_metric(train_metrics, "sharpe"),
        "test_sharpe": _safe_metric(test_metrics, "sharpe"),
        "train_return": _safe_metric(train_metrics, "total_return"),
        "test_return": _safe_metric(test_metrics, "total_return"),
        "test_drawdown": _safe_metric(test_metrics, "max_drawdown"),
        "test_volatility": _safe_metric(test_metrics, "volatility"),
        "test_win_rate": _safe_metric(test_metrics, "win_rate"),
        "test_turnover": _safe_metric(test_metrics, "turnover"),
        "trades_est": int(test_metrics.get("trades_est", 0)),
    }


def _summary(records: list[dict]) -> dict:
    if not records:
        return {
            "best": None,
            "avg_test_sharpe": 0.0,
            "avg_test_return": 0.0,
            "avg_drawdown": 0.0,
            "strategy_count": 0,
        }
    frame = pd.DataFrame(records)
    best = frame.sort_values("score", ascending=False).iloc[0].to_dict()
    return {
        "best": best,
        "avg_test_sharpe": float(frame["test_sharpe"].mean()),
        "avg_test_return": float(frame["test_return"].mean()),
        "avg_drawdown": float(frame["test_drawdown"].mean()),
        "strategy_count": int(frame["strategy"].nunique()),
    }


async def _process_symbol(symbol: str, interval: str, lookback: int, train_ratio: float) -> tuple[list[dict], dict | None]:
    try:
        df = await fetch_klines(symbol, interval, lookback)
        train_df, test_df = _split_frame(df, train_ratio)
    except Exception as exc:  # noqa: BLE001
        return [], {"symbol": symbol, "error": f"data_error: {exc}"}

    records: list[dict] = []
    for strategy in STRATEGY_FUNCS.keys():
        try:
            train_result = run_backtest(
                df=train_df,
                strategy_key=strategy,
                interval=interval,
                initial_capital=10000.0,
                fee_bps=5.0,
            )
            test_result = run_backtest(
                df=test_df,
                strategy_key=strategy,
                interval=interval,
                initial_capital=10000.0,
                fee_bps=5.0,
            )
            records.append(_pack_record(symbol.upper(), strategy, train_result, test_result))
        except Exception as exc:  # noqa: BLE001
            records.append(
                {
                    "symbol": symbol.upper(),
                    "strategy": strategy,
                    "score": -999.0,
                    "train_sharpe": 0.0,
                    "test_sharpe": 0.0,
                    "train_return": 0.0,
                    "test_return": 0.0,
                    "test_drawdown": 0.0,
                    "test_volatility": 0.0,
                    "test_win_rate": 0.0,
                    "test_turnover": 0.0,
                    "trades_est": 0,
                    "error": str(exc),
                }
            )
    return records, None


async def run_strategy_lab(
    symbols: list[str],
    interval: str,
    lookback: int,
    train_ratio: float,
    top_n: int,
) -> dict:
    uniq = [x.strip().upper() for x in symbols if x and x.strip()]
    uniq = list(dict.fromkeys(uniq))[:25]
    if not uniq:
        raise ValueError("No symbols provided.")

    semaphore = asyncio.Semaphore(5)
    errors: list[dict] = []

    async def wrapped(sym: str) -> list[dict]:
        async with semaphore:
            rows, err = await _process_symbol(sym, interval, lookback, train_ratio)
            if err is not None:
                errors.append(err)
            return rows

    nested = await asyncio.gather(*[wrapped(s) for s in uniq])
    records = [row for group in nested for row in group]
    if not records:
        raise ValueError("Strategy lab produced no results.")

    ranked = sorted(records, key=lambda x: x.get("score", -999), reverse=True)
    top = ranked[:top_n]

    by_symbol: dict[str, list[dict]] = {}
    for row in top:
        by_symbol.setdefault(row["symbol"], []).append(row)
    symbol_leaders = []
    for sym, rows in by_symbol.items():
        best = sorted(rows, key=lambda x: x["score"], reverse=True)[0]
        symbol_leaders.append({"symbol": sym, "best_strategy": best["strategy"], "score": float(best["score"])})

    return {
        "interval": interval,
        "lookback": lookback,
        "train_ratio": train_ratio,
        "tested_symbols": uniq,
        "tested_strategies": list(STRATEGY_FUNCS.keys()),
        "summary": _summary(top),
        "top_results": top,
        "symbol_leaders": sorted(symbol_leaders, key=lambda x: x["score"], reverse=True),
        "errors": errors,
    }
