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
        "bollinger_mean_reversion",
        "donchian_trend",
        "keltner_breakout",
        "intraday_reversal",
        "multi_horizon_momentum",
        "vol_target_trend",
        "entropy_regime_switch",
        "trend_strength_blend",
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


class ScreenerRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA"])
    interval: str = Field(default="1h")
    lookback: int = Field(default=900, ge=300, le=5000)


class PortfolioOptimizeRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA"])
    interval: str = Field(default="1h")
    lookback: int = Field(default=900, ge=300, le=5000)
    risk_aversion: float = Field(default=4.0, ge=0.1, le=20.0)


class StrategyLabRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA"])
    interval: str = Field(default="1h")
    lookback: int = Field(default=1200, ge=400, le=5000)
    train_ratio: float = Field(default=0.7, gt=0.5, lt=0.9)
    top_n: int = Field(default=20, ge=5, le=200)


class RotationRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    interval: str = Field(default="1h")
    lookback: int = Field(default=1500, ge=500, le=5000)
    rebalance_window: int = Field(default=120, ge=40, le=400)


class PaperResetRequest(BaseModel):
    cash: float = Field(default=100000.0, gt=1000)


class PaperOrderRequest(BaseModel):
    symbol: str = Field(default="BTCUSDT")
    quantity: float = Field(description="Positive for buy, negative for sell.")


class PaperMarkRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "AAPL", "MSFT"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str = "Trader"


class LoginRequest(BaseModel):
    email: str
    password: str


class WatchlistUpsertRequest(BaseModel):
    name: str
    symbols: list[str]


class LabRunSaveRequest(BaseModel):
    run_type: str
    name: str
    params: dict
    result: dict


class QuoteBoardRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT", "AAPL", "MSFT", "NVDA", "TSLA"])
    interval: str = Field(default="1h")
    lookback: int = Field(default=700, ge=200, le=5000)


class NewsSentimentRequest(BaseModel):
    query: str = "markets"
    max_items: int = Field(default=20, ge=5, le=100)


class AlertCreateRequest(BaseModel):
    symbol: str
    direction: Literal["above", "below"]
    threshold: float = Field(gt=0)
    message: str = ""


class AlertToggleRequest(BaseModel):
    enabled: bool


class DashboardLayoutRequest(BaseModel):
    layout: dict


class NoteCreateRequest(BaseModel):
    title: str = "Untitled Note"
    body: str = ""
