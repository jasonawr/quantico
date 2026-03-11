from typing import Literal

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT", description="Trading symbol")
    interval: str = Field(default="1m", description="Kline interval: 1m,5m,15m,1h,4h,1d")
    lookback: int = Field(default=1000, ge=200, le=5000)
    strategy: Literal[
        "trend_following",
        "mean_reversion",
        "rsi_macd",
        "volatility_breakout",
        "pairs_stat_arb",
        "mesh_composite",
        "ml_adaptive",
    ] = "mesh_composite"
    initial_capital: float = Field(default=10000.0, gt=0)
    fee_bps: float = Field(default=5.0, ge=0)


class BacktestResponse(BaseModel):
    strategy: str
    symbol: str
    metrics: dict
    equity_curve: list[dict]
    drawdown_curve: list[dict]
    trades: list[dict]
    monte_carlo: dict


class StrategyInfo(BaseModel):
    key: str
    name: str
    description: str
    complexity: str


class TickerMessage(BaseModel):
    symbol: str
    price: float
    ts: int
