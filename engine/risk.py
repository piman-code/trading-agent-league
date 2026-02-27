from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class RiskConfig:
    max_position_pct: float = 1.0
    max_daily_drawdown_pct: float = 0.05
    min_trade_notional: float = 10.0


class RiskManager:
    """Position sizing, caps, and a daily max drawdown guard."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        if not (0 < self.config.max_position_pct <= 1.0):
            raise ValueError("max_position_pct must be in (0, 1]")
        if not (0 < self.config.max_daily_drawdown_pct < 1.0):
            raise ValueError("max_daily_drawdown_pct must be in (0, 1)")

        self._current_day: pd.Timestamp | None = None
        self._day_start_equity: float | None = None
        self.guard_triggered = False

    def register_equity(self, timestamp: pd.Timestamp, equity: float) -> None:
        bar_day = pd.Timestamp(timestamp).normalize()
        if self._current_day is None or bar_day != self._current_day:
            self._current_day = bar_day
            self._day_start_equity = max(equity, 1e-9)
            self.guard_triggered = False
            return

        if self._day_start_equity is None:
            self._day_start_equity = max(equity, 1e-9)
        day_return = (equity / self._day_start_equity) - 1.0
        if day_return <= -self.config.max_daily_drawdown_pct:
            self.guard_triggered = True

    def can_add_risk(self) -> bool:
        return not self.guard_triggered

    def size_buy_qty(
        self,
        requested_fraction: float,
        price: float,
        cash: float,
        equity: float,
        current_position_qty: float,
    ) -> float:
        if price <= 0 or cash <= 0 or equity <= 0:
            return 0.0
        requested_fraction = max(0.0, min(1.0, requested_fraction))
        if requested_fraction == 0:
            return 0.0

        max_position_notional = equity * self.config.max_position_pct
        current_notional = current_position_qty * price
        remaining_notional_capacity = max(0.0, max_position_notional - current_notional)
        requested_notional = equity * requested_fraction

        target_notional = min(requested_notional, remaining_notional_capacity, cash)
        if target_notional < self.config.min_trade_notional:
            return 0.0
        return target_notional / price

    def size_sell_qty(self, requested_fraction: float, current_position_qty: float) -> float:
        if current_position_qty <= 0:
            return 0.0
        requested_fraction = max(0.0, min(1.0, requested_fraction))
        if requested_fraction == 0:
            return 0.0
        return current_position_qty * requested_fraction

