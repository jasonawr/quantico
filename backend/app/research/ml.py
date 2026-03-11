from __future__ import annotations

import numpy as np
import pandas as pd

from app.research.indicators import rolling_zscore, rsi


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(z, -20, 20)))


def _fit_logistic(X: np.ndarray, y: np.ndarray, lr: float = 0.08, epochs: int = 240, l2: float = 1e-3) -> tuple[np.ndarray, float]:
    w = np.zeros(X.shape[1], dtype=float)
    b = 0.0
    n = max(1, X.shape[0])
    for _ in range(epochs):
        p = _sigmoid(X @ w + b)
        err = p - y
        grad_w = (X.T @ err) / n + l2 * w
        grad_b = float(np.mean(err))
        w -= lr * grad_w
        b -= lr * grad_b
    return w, b


def _feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    feat = pd.DataFrame(index=df.index)
    feat["ret1"] = df["close"].pct_change()
    feat["ret5"] = df["close"].pct_change(5)
    feat["mom20"] = df["close"].pct_change(20)
    feat["vol20"] = df["returns"].rolling(20).std()
    feat["rsi14"] = rsi(df["close"], 14) / 100.0
    feat["z40"] = rolling_zscore(df["close"], 40)
    feat = feat.replace([np.inf, -np.inf], np.nan).dropna().copy()
    return feat


def walk_forward_probabilities(df: pd.DataFrame, train_window: int = 250) -> tuple[pd.Series, pd.Series]:
    feat = _feature_frame(df)
    if len(feat) < train_window + 30:
        empty = pd.Series(index=df.index, data=np.nan, dtype=float)
        return empty, empty

    target = (df["returns"] > 0).astype(float).reindex(feat.index)
    probs = pd.Series(index=df.index, data=np.nan, dtype=float)

    X_all = feat.values.astype(float)
    y_all = target.values.astype(float)

    # Normalize each window independently to avoid leakage from future stats.
    for idx in range(train_window, len(feat)):
        start = idx - train_window
        X_train = X_all[start:idx]
        y_train = y_all[start:idx]
        mu = X_train.mean(axis=0)
        sigma = X_train.std(axis=0)
        sigma[sigma == 0] = 1.0

        X_train_n = (X_train - mu) / sigma
        w, b = _fit_logistic(X_train_n, y_train)

        x_live = (X_all[idx] - mu) / sigma
        p = float(_sigmoid(x_live @ w + b))
        probs.loc[feat.index[idx]] = p

    return probs, target.reindex(df.index)


def ml_adaptive_signal(df: pd.DataFrame) -> pd.Series:
    probs, _ = walk_forward_probabilities(df)
    signal = pd.Series(index=df.index, data=0.0, dtype=float)
    signal[probs > 0.56] = 1.0
    signal[probs < 0.44] = -1.0
    return signal.fillna(0.0)


def build_ml_report(df: pd.DataFrame) -> dict:
    probs, target = walk_forward_probabilities(df)
    valid = probs.notna() & target.notna()
    if valid.sum() < 40:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "observations": int(valid.sum()),
            "recent_probabilities": [],
        }

    y_true = target[valid].astype(int).values
    y_pred = (probs[valid].values >= 0.5).astype(int)

    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    accuracy = (tp + tn) / max(1, tp + tn + fp + fn)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = (2 * precision * recall) / max(1e-9, precision + recall)

    recent = probs[valid].tail(120)
    recent_series = [
        {"time": str(t), "prob_up": float(v)}
        for t, v in zip(recent.index, recent.values)
    ]

    return {
        "accuracy": float(accuracy),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "observations": int(valid.sum()),
        "recent_probabilities": recent_series,
    }
