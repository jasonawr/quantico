from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pandas as pd

from app.core.config import settings


def _to_ms(ts: datetime) -> int:
    return int(ts.replace(tzinfo=timezone.utc).timestamp() * 1000)


async def fetch_klines(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    url = f"{settings.binance_rest_url}/api/v3/klines"
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

    frame = pd.DataFrame(
        data,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )

    num_cols = ["open", "high", "low", "close", "volume", "quote_asset_volume"]
    for col in num_cols:
        frame[col] = frame[col].astype(float)

    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    frame["returns"] = frame["close"].pct_change().fillna(0.0)
    return frame


async def fetch_ticker(symbol: str) -> dict:
    url = f"{settings.binance_rest_url}/api/v3/ticker/price"
    params = {"symbol": symbol.upper()}
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    return {
        "symbol": payload["symbol"],
        "price": float(payload["price"]),
        "ts": int(datetime.now(tz=timezone.utc).timestamp() * 1000),
    }
