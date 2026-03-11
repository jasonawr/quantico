from __future__ import annotations

import numpy as np
import pandas as pd

from app.research.monte_carlo import simulate_paths
from app.strategies.signals import STRATEGY_FUNCS


def _max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    dd = equity / running_max - 1.0
    return float(dd.min())


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


def run_backtest(
    df: pd.DataFrame,
    strategy_key: str,
    interval: str,
    initial_capital: float,
    fee_bps: float,
) -> dict:
    if strategy_key not in STRATEGY_FUNCS:
        raise ValueError(f"Unknown strategy: {strategy_key}")

    signal_fn = STRATEGY_FUNCS[strategy_key]
    position = signal_fn(df).shift(1).fillna(0.0)

    turnover = (position - position.shift(1).fillna(0.0)).abs()
    fee = turnover * (fee_bps / 10000.0)
    strat_returns = position * df["returns"] - fee

    equity = initial_capital * (1 + strat_returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0

    ann = _annualization_factor(interval)
    ret_mu = strat_returns.mean()
    ret_std = strat_returns.std()
    sharpe = float((ret_mu / ret_std) * np.sqrt(ann)) if ret_std > 0 else 0.0

    wins = strat_returns[strat_returns > 0]
    losses = strat_returns[strat_returns < 0]

    metrics = {
        "total_return": float(equity.iloc[-1] / initial_capital - 1.0),
        "annualized_return": float(((1 + ret_mu) ** ann) - 1.0),
        "sharpe": sharpe,
        "sortino": float((ret_mu / losses.std()) * np.sqrt(ann)) if len(losses) > 3 and losses.std() > 0 else 0.0,
        "volatility": float(ret_std * np.sqrt(ann)) if ret_std > 0 else 0.0,
        "max_drawdown": _max_drawdown(equity),
        "win_rate": float(len(wins) / max(1, len(strat_returns))),
        "turnover": float(turnover.mean()),
        "trades_est": int((turnover > 0).sum()),
    }

    trades = []
    for idx in range(1, len(df)):
        if abs(position.iloc[idx] - position.iloc[idx - 1]) > 1e-9:
            trades.append(
                {
                    "time": str(df["open_time"].iloc[idx]),
                    "price": float(df["close"].iloc[idx]),
                    "position": float(position.iloc[idx]),
                }
            )

    return {
        "metrics": metrics,
        "equity_curve": [
            {"time": str(t), "equity": float(v)}
            for t, v in zip(df["open_time"], equity)
        ],
        "drawdown_curve": [
            {"time": str(t), "drawdown": float(v)}
            for t, v in zip(df["open_time"], drawdown)
        ],
        "trades": trades[-250:],
        "monte_carlo": simulate_paths(strat_returns, n_paths=300, horizon=220),
    }
