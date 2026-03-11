from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
from typing import Any

import httpx
import pandas as pd

from app.core.config import settings

COMMON_SYMBOLS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "AMZN", "name": "Amazon.com, Inc.", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "GOOGL", "name": "Alphabet Inc.", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "TSLA", "name": "Tesla, Inc.", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "META", "name": "Meta Platforms, Inc.", "exchange": "NASDAQ", "type": "EQUITY"},
    {"symbol": "SPY", "name": "SPDR S&P 500 ETF Trust", "exchange": "NYSEARCA", "type": "ETF"},
    {"symbol": "QQQ", "name": "Invesco QQQ Trust", "exchange": "NASDAQ", "type": "ETF"},
    {"symbol": "BTCUSDT", "name": "Bitcoin / Tether", "exchange": "CRYPTO", "type": "CRYPTO"},
    {"symbol": "ETHUSDT", "name": "Ethereum / Tether", "exchange": "CRYPTO", "type": "CRYPTO"},
]


def _now_ms() -> int:
    return int(datetime.now(tz=timezone.utc).timestamp() * 1000)


def _is_crypto_symbol(symbol: str) -> bool:
    sym = symbol.upper().strip()
    if "-" in sym and sym.endswith("USD"):
        return True
    quote_assets = ("USDT", "USDC", "USD", "BUSD", "BTC", "ETH")
    return any(sym.endswith(q) for q in quote_assets) and len(sym) > 5


def _to_coinbase_product(symbol: str) -> str:
    sym = symbol.upper().strip()
    if "-" in sym:
        return sym
    for q in ("USDT", "USDC", "USD", "BTC", "ETH"):
        if sym.endswith(q):
            base = sym[: -len(q)]
            q_norm = "USD" if q in ("USDT", "USDC") else q
            return f"{base}-{q_norm}"
    return sym


def _to_yahoo_symbol(symbol: str) -> str:
    sym = symbol.upper().strip()
    if _is_crypto_symbol(sym):
        product = _to_coinbase_product(sym)
        return product if product.endswith("-USD") else f"{product}-USD"
    return sym


def _to_stooq_symbol(symbol: str) -> str:
    sym = symbol.upper().strip()
    if _is_crypto_symbol(sym):
        product = _to_coinbase_product(sym).replace("-", "")
        return f"{product.lower()}.v"
    if "." in sym:
        return sym.lower()
    return f"{sym.lower()}.us"


def _range_for_interval(interval: str) -> str:
    mapping = {
        "1m": "7d",
        "5m": "1mo",
        "15m": "2mo",
        "1h": "6mo",
        "4h": "1y",
        "1d": "5y",
    }
    return mapping.get(interval, "1mo")


def _coinbase_granularity(interval: str) -> int:
    mapping = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
    return mapping.get(interval, 60)


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _finalize_frame(frame: pd.DataFrame, limit: int) -> pd.DataFrame:
    frame = frame.sort_values("open_time").tail(limit).copy()
    frame["returns"] = frame["close"].pct_change().fillna(0.0)
    return frame.reset_index(drop=True)


async def _fetch_klines_binance(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    out: list[list[Any]] = []
    end_ms = _now_ms()
    remaining = limit

    async with httpx.AsyncClient(timeout=20.0) as client:
        while remaining > 0:
            batch = min(1000, remaining)
            response = await client.get(
                f"{settings.binance_rest_url}/api/v3/klines",
                params={"symbol": symbol.upper(), "interval": interval, "limit": batch, "endTime": end_ms},
            )
            response.raise_for_status()
            rows = response.json()
            if not rows:
                break
            out = rows + out
            remaining -= len(rows)
            oldest_open = int(rows[0][0])
            end_ms = oldest_open - 1
            if len(rows) < batch:
                break

    frame = pd.DataFrame(
        out,
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
    if frame.empty:
        raise ValueError("No kline data returned from Binance.")

    for col in ("open", "high", "low", "close", "volume", "quote_asset_volume"):
        frame[col] = frame[col].astype(float)
    frame["open_time"] = pd.to_datetime(frame["open_time"], unit="ms", utc=True)
    frame["close_time"] = pd.to_datetime(frame["close_time"], unit="ms", utc=True)
    return _finalize_frame(frame[["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume"]], limit)


async def _fetch_klines_coinbase(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    product = _to_coinbase_product(symbol)
    granularity = _coinbase_granularity(interval)
    end = datetime.now(tz=timezone.utc)
    out: list[list[Any]] = []
    loops = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        while len(out) < limit and loops < 30:
            start = end - timedelta(seconds=granularity * 300)
            response = await client.get(
                f"https://api.exchange.coinbase.com/products/{product}/candles",
                params={
                    "granularity": granularity,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )
            response.raise_for_status()
            rows = response.json()
            if not rows:
                break
            out.extend(rows)
            end = start
            loops += 1

    if not out:
        raise ValueError("No candle data returned from Coinbase.")

    frame = pd.DataFrame(out, columns=["ts", "low", "high", "open", "close", "volume"]).drop_duplicates(subset=["ts"])
    frame["open_time"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
    frame["close_time"] = frame["open_time"] + pd.to_timedelta(granularity, unit="s")
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = frame[col].astype(float)
    frame["quote_asset_volume"] = frame["close"] * frame["volume"]
    return _finalize_frame(frame[["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume"]], limit)


async def _fetch_klines_yahoo(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    yahoo_symbol = _to_yahoo_symbol(symbol)
    yahoo_interval = "1h" if interval == "4h" else interval
    response_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_symbol}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            response_url,
            params={"interval": yahoo_interval, "range": _range_for_interval(interval)},
        )
        response.raise_for_status()
        payload = response.json()

    result = payload.get("chart", {}).get("result", [])
    if not result:
        raise ValueError("No chart data returned from Yahoo Finance.")

    node = result[0]
    ts = node.get("timestamp", [])
    quote = node.get("indicators", {}).get("quote", [{}])[0]
    frame = pd.DataFrame(
        {
            "open_time": pd.to_datetime(ts, unit="s", utc=True),
            "open": quote.get("open", []),
            "high": quote.get("high", []),
            "low": quote.get("low", []),
            "close": quote.get("close", []),
            "volume": quote.get("volume", []),
        }
    ).dropna()
    if frame.empty:
        raise ValueError("Yahoo chart data is empty.")

    if interval == "4h":
        frame = frame.set_index("open_time").resample("4h").agg(
            {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        )
        frame = frame.dropna().reset_index()

    frame["close_time"] = frame["open_time"] + (frame["open_time"].diff().median() or pd.Timedelta(hours=1))
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = frame[col].astype(float)
    frame["quote_asset_volume"] = frame["close"] * frame["volume"]
    return _finalize_frame(frame[["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume"]], limit)


async def _fetch_klines_stooq(symbol: str, interval: str, limit: int) -> pd.DataFrame:
    if interval not in ("1d", "4h", "1h"):
        raise ValueError("Stooq fallback supports daily data only.")
    stooq_symbol = _to_stooq_symbol(symbol)
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get("https://stooq.com/q/d/l/", params={"s": stooq_symbol, "i": "d"})
        response.raise_for_status()
        csv_text = response.text
    frame = pd.read_csv(io.StringIO(csv_text))
    if frame.empty or "Date" not in frame.columns:
        raise ValueError("No historical data returned from Stooq.")
    frame = frame.rename(columns={"Date": "open_time", "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"})
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True)
    for col in ("open", "high", "low", "close", "volume"):
        frame[col] = frame[col].astype(float)
    frame["close_time"] = frame["open_time"] + pd.Timedelta(days=1)
    frame["quote_asset_volume"] = frame["close"] * frame["volume"]
    return _finalize_frame(frame[["open_time", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume"]], limit)


async def fetch_klines(symbol: str, interval: str, limit: int = 1000) -> pd.DataFrame:
    errors: list[str] = []
    providers = [
        ("binance", _fetch_klines_binance),
        ("coinbase", _fetch_klines_coinbase),
        ("yahoo", _fetch_klines_yahoo),
        ("stooq", _fetch_klines_stooq),
    ]
    for name, fn in providers:
        try:
            return await fn(symbol, interval, limit)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")
    raise ValueError(f"All market data providers failed for {symbol}. " + " | ".join(errors))


async def fetch_ticker(symbol: str) -> dict:
    sym = symbol.upper()
    now_ms = _now_ms()
    errors: list[str] = []

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.binance_rest_url}/api/v3/ticker/price", params={"symbol": sym})
            response.raise_for_status()
            payload = response.json()
        return {"symbol": payload["symbol"], "price": float(payload["price"]), "ts": now_ms, "provider": "binance"}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"binance: {exc}")

    try:
        product = _to_coinbase_product(sym)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"https://api.exchange.coinbase.com/products/{product}/ticker")
            response.raise_for_status()
            payload = response.json()
        return {"symbol": product, "price": _safe_float(payload.get("price")), "ts": now_ms, "provider": "coinbase"}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"coinbase: {exc}")

    try:
        yahoo_symbol = _to_yahoo_symbol(sym)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://query1.finance.yahoo.com/v7/finance/quote",
                params={"symbols": yahoo_symbol},
            )
            response.raise_for_status()
            quote = response.json().get("quoteResponse", {}).get("result", [])[0]
        return {"symbol": yahoo_symbol, "price": _safe_float(quote.get("regularMarketPrice")), "ts": now_ms, "provider": "yahoo"}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"yahoo: {exc}")

    try:
        stooq_symbol = _to_stooq_symbol(sym)
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://stooq.com/q/l/", params={"s": stooq_symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"})
            response.raise_for_status()
        lines = response.text.strip().splitlines()
        if len(lines) >= 2:
            row = lines[1].split(",")
            return {"symbol": sym, "price": _safe_float(row[6]), "ts": now_ms, "provider": "stooq"}
    except Exception as exc:  # noqa: BLE001
        errors.append(f"stooq: {exc}")

    raise ValueError("All ticker providers failed. " + " | ".join(errors))


async def fetch_symbol_search(query: str, limit: int = 12) -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=12.0) as client:
            response = await client.get(
                "https://query1.finance.yahoo.com/v1/finance/search",
                params={"q": query, "quotesCount": limit, "newsCount": 0},
            )
            response.raise_for_status()
            data = response.json()
        quotes = data.get("quotes", [])
        out = []
        for item in quotes[:limit]:
            out.append(
                {
                    "symbol": item.get("symbol"),
                    "name": item.get("shortname") or item.get("longname") or "",
                    "exchange": item.get("exchange") or "",
                    "type": item.get("quoteType") or "",
                }
            )
        return out
    except Exception:  # noqa: BLE001
        needle = query.upper().strip()
        return [x for x in COMMON_SYMBOLS if needle in x["symbol"] or needle in x["name"].upper()][:limit]


async def fetch_company_profile(symbol: str) -> dict:
    sym = _to_yahoo_symbol(symbol)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            quote_response = await client.get("https://query1.finance.yahoo.com/v7/finance/quote", params={"symbols": sym})
            quote_response.raise_for_status()
            quote_list = quote_response.json().get("quoteResponse", {}).get("result", [])
            if not quote_list:
                raise ValueError(f"No quote data for {sym}")
            quote = quote_list[0]

            summary_result: dict[str, Any] = {}
            summary_response = await client.get(
                f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{sym}",
                params={"modules": "summaryProfile,financialData,defaultKeyStatistics"},
            )
            if summary_response.status_code < 400:
                summary_result = summary_response.json().get("quoteSummary", {}).get("result", [{}])[0]

        profile = summary_result.get("summaryProfile", {}) or {}
        financial = summary_result.get("financialData", {}) or {}
        stats = summary_result.get("defaultKeyStatistics", {}) or {}
        return {
            "symbol": sym,
            "name": quote.get("longName") or quote.get("shortName") or sym,
            "exchange": quote.get("fullExchangeName") or quote.get("exchange") or "",
            "market_cap": quote.get("marketCap"),
            "sector": profile.get("sector"),
            "industry": profile.get("industry"),
            "country": profile.get("country"),
            "website": profile.get("website"),
            "summary": profile.get("longBusinessSummary"),
            "target_mean_price": (financial.get("targetMeanPrice") or {}).get("raw"),
            "forward_pe": (stats.get("forwardPE") or {}).get("raw"),
            "beta": (stats.get("beta") or {}).get("raw"),
        }
    except Exception:  # noqa: BLE001
        for item in COMMON_SYMBOLS:
            if item["symbol"] == symbol.upper().strip():
                return {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "exchange": item["exchange"],
                    "market_cap": None,
                    "sector": None,
                    "industry": None,
                    "country": None,
                    "website": None,
                    "summary": "Fallback profile (network-restricted provider mode).",
                    "target_mean_price": None,
                    "forward_pe": None,
                    "beta": None,
                }
        return {
            "symbol": symbol.upper().strip(),
            "name": symbol.upper().strip(),
            "exchange": "Unknown",
            "market_cap": None,
            "sector": None,
            "industry": None,
            "country": None,
            "website": None,
            "summary": "Profile unavailable from upstream data vendors in current network region.",
            "target_mean_price": None,
            "forward_pe": None,
            "beta": None,
        }
