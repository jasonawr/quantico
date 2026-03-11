from dataclasses import dataclass


@dataclass(frozen=True)
class StrategySpec:
    key: str
    name: str
    description: str
    complexity: str


STRATEGIES = {
    "trend_following": StrategySpec(
        key="trend_following",
        name="Dual EMA Trend Following",
        description="Long/short based on fast/slow EMA crossover with volatility filter.",
        complexity="medium",
    ),
    "mean_reversion": StrategySpec(
        key="mean_reversion",
        name="Z-Score Mean Reversion",
        description="Fade extremes using rolling z-score and dynamic exit bands.",
        complexity="medium",
    ),
    "rsi_macd": StrategySpec(
        key="rsi_macd",
        name="RSI + MACD Regime",
        description="Regime-aware momentum/reversion hybrid based on RSI and MACD histograms.",
        complexity="medium",
    ),
    "volatility_breakout": StrategySpec(
        key="volatility_breakout",
        name="ATR Volatility Breakout",
        description="Enters trend continuation after volatility expansion and range breakout.",
        complexity="high",
    ),
    "pairs_stat_arb": StrategySpec(
        key="pairs_stat_arb",
        name="Synthetic Pairs Stat-Arb",
        description="Cointegration-inspired residual mean reversion using synthetic benchmark proxy.",
        complexity="high",
    ),
    "mesh_composite": StrategySpec(
        key="mesh_composite",
        name="MESH Composite Alpha",
        description="Composite of Momentum, Entropy, Sharpe, and Trend (MESH) with adaptive sizing.",
        complexity="very_high",
    ),
    "ml_adaptive": StrategySpec(
        key="ml_adaptive",
        name="Adaptive ML Classifier",
        description="Walk-forward logistic model on market features with confidence-gated long/short signals.",
        complexity="very_high",
    ),
}
