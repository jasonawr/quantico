from __future__ import annotations

import numpy as np
import pandas as pd

from app.data.binance import fetch_klines
from app.strategies.signals import STRATEGY_FUNCS


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


def _rolling_sharpe(returns: pd.Series, window: int, ann: float) -> pd.Series:
    mu = returns.rolling(window).mean()
    sd = returns.rolling(window).std().replace(0, np.nan)
    return (mu / sd) * np.sqrt(ann)


def _max_drawdown(equity: pd.Series) -> float:
    dd = equity / equity.cummax() - 1.0
    return float(dd.min())


async def simulate_strategy_rotation(symbol: str, interval: str, lookback: int, rebalance_window: int) -> dict:
    df = await fetch_klines(symbol, interval, lookback)
    returns = df["returns"].fillna(0.0)
    ann = _annualization_factor(interval)

    strategy_returns: dict[str, pd.Series] = {}
    for name, signal_fn in STRATEGY_FUNCS.items():
        signal = signal_fn(df)
        if name != "ml_adaptive":
            signal = signal.shift(1)
        signal = signal.fillna(0.0).clip(-1.0, 1.0)
        trade_cost = (signal - signal.shift(1).fillna(0.0)).abs() * 0.0005
        strategy_returns[name] = signal * returns - trade_cost

    ret_df = pd.DataFrame(strategy_returns).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    sharpe_df = pd.DataFrame({name: _rolling_sharpe(ret_df[name], rebalance_window, ann) for name in ret_df.columns})

    chosen = []
    rotated_ret = []
    for i in range(len(ret_df)):
        if i < rebalance_window:
            name = "mesh_composite"
        else:
            row = sharpe_df.iloc[i - 1].dropna()
            if row.empty:
                name = "mesh_composite"
            else:
                name = row.sort_values(ascending=False).index[0]
        chosen.append(name)
        rotated_ret.append(float(ret_df.iloc[i][name]))

    rotated_series = pd.Series(rotated_ret, index=df.index)
    equity = 10000.0 * (1.0 + rotated_series).cumprod()
    drawdown = equity / equity.cummax() - 1.0

    mu = rotated_series.mean()
    sd = rotated_series.std()
    sharpe = float((mu / sd) * np.sqrt(ann)) if sd > 0 else 0.0
    total_return = float(equity.iloc[-1] / 10000.0 - 1.0)

    usage = pd.Series(chosen).value_counts().to_dict()
    selection = [{"time": str(t), "strategy": s} for t, s in zip(df["open_time"], chosen)]

    return {
        "symbol": symbol.upper(),
        "interval": interval,
        "rebalance_window": rebalance_window,
        "metrics": {
            "total_return": total_return,
            "sharpe": sharpe,
            "max_drawdown": _max_drawdown(equity),
            "annualized_volatility": float(sd * np.sqrt(ann)) if sd > 0 else 0.0,
        },
        "selection_usage": usage,
        "selection_path": selection[-500:],
        "equity_curve": [{"time": str(t), "equity": float(v)} for t, v in zip(df["open_time"], equity)],
        "drawdown_curve": [{"time": str(t), "drawdown": float(v)} for t, v in zip(df["open_time"], drawdown)],
    }
