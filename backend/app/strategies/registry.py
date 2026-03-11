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
    "bollinger_mean_reversion": StrategySpec(
        key="bollinger_mean_reversion",
        name="Bollinger Mean Reversion",
        description="Contrarian entries at Bollinger extremes with mean reversion exits.",
        complexity="medium",
    ),
    "donchian_trend": StrategySpec(
        key="donchian_trend",
        name="Donchian Breakout Trend",
        description="Classic channel breakout trend-following system.",
        complexity="medium",
    ),
    "keltner_breakout": StrategySpec(
        key="keltner_breakout",
        name="Keltner Channel Breakout",
        description="Volatility channel breakout using EMA + ATR envelopes.",
        complexity="high",
    ),
    "intraday_reversal": StrategySpec(
        key="intraday_reversal",
        name="Short-Term Reversal",
        description="Fades short-run return shocks using volatility-normalized position sizing.",
        complexity="high",
    ),
    "multi_horizon_momentum": StrategySpec(
        key="multi_horizon_momentum",
        name="Multi-Horizon Momentum",
        description="Combines 10/30/90-bar momentum horizons with volatility scaling.",
        complexity="high",
    ),
    "vol_target_trend": StrategySpec(
        key="vol_target_trend",
        name="Vol Target Trend",
        description="Trend signal with dynamic volatility targeting and leverage caps.",
        complexity="very_high",
    ),
    "entropy_regime_switch": StrategySpec(
        key="entropy_regime_switch",
        name="Entropy Regime Switch",
        description="Switches between trend and mean reversion by entropy regime.",
        complexity="very_high",
    ),
    "trend_strength_blend": StrategySpec(
        key="trend_strength_blend",
        name="Trend Strength Blend",
        description="Composite of EMA spread and slope with noise penalty control.",
        complexity="high",
    ),
}
