from __future__ import annotations

import numpy as np
import pandas as pd

from app.research.indicators import atr, ema, entropy_like, rolling_zscore, rsi, sharpe_like


def _clip_position(pos: pd.Series, max_abs: float = 1.0) -> pd.Series:
    return pos.fillna(0.0).clip(-max_abs, max_abs)


def trend_following(df: pd.DataFrame) -> pd.Series:
    fast = ema(df["close"], 21)
    slow = ema(df["close"], 84)
    vol = df["returns"].rolling(50).std()
    vol_filter = (vol > vol.rolling(200).median()).astype(float)
    raw = np.sign(fast - slow) * vol_filter
    return _clip_position(pd.Series(raw, index=df.index))


def mean_reversion(df: pd.DataFrame) -> pd.Series:
    z = rolling_zscore(df["close"], 60)
    long_sig = (z < -1.7).astype(float)
    short_sig = (z > 1.7).astype(float)
    exit_zone = (z.abs() < 0.4).astype(float)
    pos = long_sig - short_sig
    pos = pd.Series(pos, index=df.index)
    pos = pos.where(exit_zone == 0, 0)
    return _clip_position(pos)


def rsi_macd(df: pd.DataFrame) -> pd.Series:
    r = rsi(df["close"], 14)
    macd = ema(df["close"], 12) - ema(df["close"], 26)
    signal = ema(macd, 9)
    hist = macd - signal
    long_sig = ((r < 35) & (hist > 0)).astype(float)
    short_sig = ((r > 65) & (hist < 0)).astype(float)
    pos = long_sig - short_sig
    return _clip_position(pd.Series(pos, index=df.index))


def volatility_breakout(df: pd.DataFrame) -> pd.Series:
    a = atr(df["high"], df["low"], df["close"], 20)
    high_break = df["close"] > (df["close"].rolling(20).max().shift(1) + 0.2 * a)
    low_break = df["close"] < (df["close"].rolling(20).min().shift(1) - 0.2 * a)
    pos = high_break.astype(float) - low_break.astype(float)
    return _clip_position(pd.Series(pos, index=df.index))


def pairs_stat_arb(df: pd.DataFrame) -> pd.Series:
    proxy = ema(df["close"], 10) / ema(df["close"], 120)
    spread = np.log(df["close"]) - np.log(proxy.replace(0, np.nan))
    z = rolling_zscore(spread.replace([np.inf, -np.inf], np.nan).fillna(method="bfill"), 80)
    pos = (z < -1.2).astype(float) - (z > 1.2).astype(float)
    return _clip_position(pd.Series(pos, index=df.index), max_abs=0.8)


def mesh_composite(df: pd.DataFrame) -> pd.Series:
    # MESH = Momentum + Entropy + Sharpe + Trend with adaptive confidence weighting.
    mom = (df["close"].pct_change(20)).clip(-0.2, 0.2)
    ent = entropy_like(df["returns"], 80)
    ent_norm = (ent - ent.rolling(200).mean()) / ent.rolling(200).std().replace(0, np.nan)
    sh = sharpe_like(df["returns"], 60)
    trend = np.sign(ema(df["close"], 34) - ema(df["close"], 144))

    comp = 0.45 * mom + 0.2 * sh + 0.25 * trend - 0.1 * ent_norm
    regime = (df["returns"].rolling(120).std() / df["returns"].rolling(360).std()).clip(0.5, 2.0)
    confidence = (comp.abs().rolling(20).mean()).clip(0, 1)
    sized = np.tanh(4 * comp.fillna(0.0)) * confidence.fillna(0.0) / regime.fillna(1.0)
    return _clip_position(pd.Series(sized, index=df.index))


STRATEGY_FUNCS = {
    "trend_following": trend_following,
    "mean_reversion": mean_reversion,
    "rsi_macd": rsi_macd,
    "volatility_breakout": volatility_breakout,
    "pairs_stat_arb": pairs_stat_arb,
    "mesh_composite": mesh_composite,
}
