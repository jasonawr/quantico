# Quant Research Notes (Implemented)

## Core Return Model
- Log return: g_t = ln(P_t / P_{t-1})
- Strategy return: r^s_t = w_{t-1} * r_t - fee_t
- Equity: E_t = E_0 * prod(1 + r^s_i)

## Implemented Strategies
1. Trend Following (Dual EMA + volatility filter)
2. Z-Score Mean Reversion
3. RSI + MACD Hybrid
4. ATR Volatility Breakout
5. Synthetic Pairs Stat-Arb (residual z-score)
6. MESH Composite:
   - M = Momentum over medium horizon
   - E = Entropy-like uncertainty penalty
   - S = Rolling Sharpe-like score
   - T = Trend score via multi-horizon EMA
   - Adaptive position sizing with tanh(confidence/regime)

## Risk Metrics
- Annualized return and volatility
- Sharpe and Sortino
- Max drawdown
- Win rate
- Turnover and trade count proxy

## Monte Carlo
- Returns are sampled with Gaussian shocks from empirical mean/std.
- Generates scenario fan with p10/p50/p90 cone.
- Used as stress/sensitivity overlay, not production VaR certification.

## Data Source
- Binance Spot public market endpoints for klines and ticker.
- No Polymarket dependency.
