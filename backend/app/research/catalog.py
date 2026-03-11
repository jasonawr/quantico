from __future__ import annotations


def research_catalog() -> dict:
    return {
        "note": "This catalog covers major strategy families used in systematic trading. It is extensive but not mathematically exhaustive.",
        "families": [
            {
                "name": "Trend / Momentum",
                "strategies": [
                    "trend_following",
                    "donchian_trend",
                    "multi_horizon_momentum",
                    "vol_target_trend",
                    "trend_strength_blend",
                ],
                "references": [
                    "Moskowitz, Ooi, Pedersen (2012) Time Series Momentum",
                    "Hurst, Ooi, Pedersen (2017) A Century of Evidence on Trend-Following",
                ],
            },
            {
                "name": "Mean Reversion",
                "strategies": [
                    "mean_reversion",
                    "bollinger_mean_reversion",
                    "intraday_reversal",
                    "pairs_stat_arb",
                ],
                "references": [
                    "Gatev, Goetzmann, Rouwenhorst (2006) Pairs Trading",
                    "Avellaneda, Lee (2010) Statistical Arbitrage in U.S. Equities",
                ],
            },
            {
                "name": "Volatility / Breakout",
                "strategies": [
                    "volatility_breakout",
                    "keltner_breakout",
                ],
                "references": [
                    "Original Turtle/Donchian breakout framework",
                    "ATR-based volatility breakout systems (practitioner literature)",
                ],
            },
            {
                "name": "Regime / Information-Theoretic",
                "strategies": [
                    "entropy_regime_switch",
                    "mesh_composite",
                ],
                "references": [
                    "Adaptive market regime models (broad literature)",
                    "Forecast combination literature (Timmermann, 2006 survey)",
                ],
            },
            {
                "name": "Machine Learning",
                "strategies": [
                    "ml_adaptive",
                ],
                "references": [
                    "Gu, Kelly, Xiu (2020) Empirical Asset Pricing via ML",
                    "Harvey, Liu, Zhu (2016) ... and the Cross-Section of Expected Returns",
                ],
            },
        ],
    }
