from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.data.binance import fetch_ticker


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


@dataclass
class PaperState:
    cash: float = 100000.0
    positions: dict[str, float] = field(default_factory=dict)
    last_prices: dict[str, float] = field(default_factory=dict)
    fills: list[dict] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)

    def snapshot(self) -> dict:
        position_value = sum(self.positions.get(sym, 0.0) * self.last_prices.get(sym, 0.0) for sym in self.positions)
        equity = self.cash + position_value
        return {
            "cash": float(self.cash),
            "positions": {k: float(v) for k, v in self.positions.items() if abs(v) > 1e-12},
            "last_prices": {k: float(v) for k, v in self.last_prices.items()},
            "position_value": float(position_value),
            "equity": float(equity),
            "fills": self.fills[-300:],
            "equity_curve": self.equity_curve[-1000:],
        }


state = PaperState()


def reset_paper(cash: float) -> dict:
    state.cash = cash
    state.positions = {}
    state.last_prices = {}
    state.fills = []
    state.equity_curve = []
    return state.snapshot()


async def mark_to_market(symbols: list[str]) -> dict:
    uniq = [x.strip().upper() for x in symbols if x and x.strip()]
    for sym in uniq:
        try:
            tick = await fetch_ticker(sym)
            state.last_prices[sym] = float(tick.get("price", 0.0))
        except Exception:  # noqa: BLE001
            continue
    snap = state.snapshot()
    snap_point = {"time": _now_iso(), "equity": snap["equity"], "cash": snap["cash"]}
    state.equity_curve.append(snap_point)
    return state.snapshot()


async def place_order(symbol: str, quantity: float) -> dict:
    sym = symbol.strip().upper()
    if abs(quantity) < 1e-12:
        raise ValueError("Quantity cannot be zero.")

    tick = await fetch_ticker(sym)
    px = float(tick.get("price", 0.0))
    if px <= 0:
        raise ValueError("Invalid market price.")

    notional = quantity * px
    fee = abs(notional) * 0.0005
    new_cash = state.cash - notional - fee
    if new_cash < -1e-9:
        raise ValueError("Insufficient cash for this order.")

    state.cash = new_cash
    state.positions[sym] = state.positions.get(sym, 0.0) + quantity
    state.last_prices[sym] = px

    fill = {
        "time": _now_iso(),
        "symbol": sym,
        "quantity": float(quantity),
        "price": float(px),
        "notional": float(notional),
        "fee": float(fee),
    }
    state.fills.append(fill)
    return state.snapshot()
