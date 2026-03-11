from __future__ import annotations

import numpy as np
import pandas as pd

from app.research.indicators import atr, ema, entropy_like, rolling_zscore, rsi, sharpe_like
from app.research.ml import ml_adaptive_signal


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
    z = rolling_zscore(spread.replace([np.inf, -np.inf], np.nan).bfill(), 80)
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


def bollinger_mean_reversion(df: pd.DataFrame) -> pd.Series:
    ma = df["close"].rolling(30).mean()
    sd = df["close"].rolling(30).std()
    upper = ma + 2.0 * sd
    lower = ma - 2.0 * sd
    long_sig = (df["close"] < lower).astype(float)
    short_sig = (df["close"] > upper).astype(float)
    neutral = ((df["close"] - ma).abs() < 0.25 * sd).astype(float)
    pos = long_sig - short_sig
    pos = pd.Series(pos, index=df.index)
    pos = pos.where(neutral == 0, 0.0)
    return _clip_position(pos)


def donchian_trend(df: pd.DataFrame) -> pd.Series:
    hi = df["high"].rolling(55).max().shift(1)
    lo = df["low"].rolling(55).min().shift(1)
    long_sig = (df["close"] > hi).astype(float)
    short_sig = (df["close"] < lo).astype(float)
    return _clip_position(pd.Series(long_sig - short_sig, index=df.index))


def keltner_breakout(df: pd.DataFrame) -> pd.Series:
    mid = ema(df["close"], 20)
    rng = atr(df["high"], df["low"], df["close"], 20)
    upper = mid + 1.6 * rng
    lower = mid - 1.6 * rng
    long_sig = (df["close"] > upper).astype(float)
    short_sig = (df["close"] < lower).astype(float)
    return _clip_position(pd.Series(long_sig - short_sig, index=df.index))


def intraday_reversal(df: pd.DataFrame) -> pd.Series:
    lag = df["returns"].rolling(3).sum()
    vol = df["returns"].rolling(30).std().replace(0, np.nan)
    score = -(lag / vol).clip(-2.0, 2.0)
    return _clip_position(pd.Series(np.tanh(score), index=df.index), max_abs=0.75)


def multi_horizon_momentum(df: pd.DataFrame) -> pd.Series:
    m1 = df["close"].pct_change(10)
    m2 = df["close"].pct_change(30)
    m3 = df["close"].pct_change(90)
    comp = 0.5 * m1 + 0.35 * m2 + 0.15 * m3
    vol = df["returns"].rolling(60).std().replace(0, np.nan)
    score = comp / vol
    return _clip_position(pd.Series(np.tanh(2.5 * score), index=df.index))


def vol_target_trend(df: pd.DataFrame) -> pd.Series:
    trend = np.sign(ema(df["close"], 25) - ema(df["close"], 120))
    vol = df["returns"].rolling(50).std().replace(0, np.nan)
    target = 0.18
    scaling = (target / (vol * np.sqrt(365))).clip(0, 1.8)
    pos = trend * scaling
    return _clip_position(pd.Series(pos, index=df.index))


def entropy_regime_switch(df: pd.DataFrame) -> pd.Series:
    ent = entropy_like(df["returns"], 90)
    ent_z = (ent - ent.rolling(180).mean()) / ent.rolling(180).std().replace(0, np.nan)
    trend = np.sign(ema(df["close"], 20) - ema(df["close"], 80))
    mr = -np.sign(rolling_zscore(df["close"], 40))
    regime = (ent_z > 0).astype(float)
    pos = regime * trend + (1 - regime) * mr
    return _clip_position(pd.Series(pos, index=df.index), max_abs=0.9)


def trend_strength_blend(df: pd.DataFrame) -> pd.Series:
    fast = ema(df["close"], 12)
    slow = ema(df["close"], 48)
    slope = (slow / slow.shift(12) - 1.0).clip(-0.2, 0.2)
    spread = (fast - slow) / slow.replace(0, np.nan)
    strength = 3.0 * spread + 2.0 * slope
    noise_penalty = df["returns"].rolling(20).std() / df["returns"].rolling(120).std().replace(0, np.nan)
    score = strength / noise_penalty.clip(0.6, 2.0)
    return _clip_position(pd.Series(np.tanh(score), index=df.index))


STRATEGY_FUNCS = {
    "trend_following": trend_following,
    "mean_reversion": mean_reversion,
    "rsi_macd": rsi_macd,
    "volatility_breakout": volatility_breakout,
    "pairs_stat_arb": pairs_stat_arb,
    "mesh_composite": mesh_composite,
    "ml_adaptive": ml_adaptive_signal,
    "bollinger_mean_reversion": bollinger_mean_reversion,
    "donchian_trend": donchian_trend,
    "keltner_breakout": keltner_breakout,
    "intraday_reversal": intraday_reversal,
    "multi_horizon_momentum": multi_horizon_momentum,
    "vol_target_trend": vol_target_trend,
    "entropy_regime_switch": entropy_regime_switch,
    "trend_strength_blend": trend_strength_blend,
}
