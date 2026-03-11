import numpy as np
import pandas as pd


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    gain = up.ewm(alpha=1 / period, adjust=False).mean()
    loss = down.ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def rolling_zscore(series: pd.Series, window: int = 50) -> pd.Series:
    mean = series.rolling(window).mean()
    std = series.rolling(window).std().replace(0, np.nan)
    return (series - mean) / std


def sharpe_like(returns: pd.Series, window: int = 60) -> pd.Series:
    mu = returns.rolling(window).mean()
    sigma = returns.rolling(window).std().replace(0, np.nan)
    return (mu / sigma).clip(-5, 5)


def entropy_like(returns: pd.Series, window: int = 80, bins: int = 20) -> pd.Series:
    vals = []
    arr = returns.fillna(0.0).values
    for i in range(len(arr)):
        if i < window:
            vals.append(np.nan)
            continue
        slice_arr = arr[i - window : i]
        hist, _ = np.histogram(slice_arr, bins=bins, density=True)
        hist = hist[hist > 0]
        ent = -np.sum(hist * np.log(hist))
        vals.append(ent)
    return pd.Series(vals, index=returns.index)
