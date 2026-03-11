from __future__ import annotations

import numpy as np
import pandas as pd


def simulate_paths(returns: pd.Series, n_paths: int = 250, horizon: int = 180) -> dict:
    clean = returns.dropna().values
    if len(clean) < 30:
        return {"paths": [], "percentiles": []}

    mu = np.mean(clean)
    sigma = np.std(clean)
    last = 1.0

    paths = []
    for _ in range(n_paths):
        shocks = np.random.normal(mu, sigma, size=horizon)
        path = [last]
        for shock in shocks:
            path.append(path[-1] * (1 + shock))
        paths.append(path)

    arr = np.array(paths)
    p10 = np.percentile(arr, 10, axis=0)
    p50 = np.percentile(arr, 50, axis=0)
    p90 = np.percentile(arr, 90, axis=0)

    return {
        "paths": arr[:, ::6].round(6).tolist(),
        "percentiles": {
            "p10": p10.round(6).tolist(),
            "p50": p50.round(6).tolist(),
            "p90": p90.round(6).tolist(),
        },
        "horizon": horizon,
    }
