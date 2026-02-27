from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List

import pandas as pd


@dataclass
class Trade:
    timestamp: pd.Timestamp
    side: str
    qty: float
    fill_price: float
    notional: float
    fee: float
    realized_pnl: float
    cash_after: float
    position_after: float


class OrderEngine:
    """Long-only order engine with slippage, fees, and portfolio tracking."""

    def __init__(self, initial_capital: float, slippage_bps: float = 2.0, fee_bps: float = 5.0) -> None:
        if initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.position_qty = 0.0
        self.position_cost_basis = 0.0
        self.slippage_bps = float(slippage_bps)
        self.fee_bps = float(fee_bps)
        self.trades: List[Trade] = []
        self.equity_points: List[Dict[str, float | pd.Timestamp]] = []

    @property
    def fee_rate(self) -> float:
        return self.fee_bps / 10_000.0

    @property
    def slippage_rate(self) -> float:
        return self.slippage_bps / 10_000.0

    def total_equity(self, mark_price: float) -> float:
        return self.cash + (self.position_qty * mark_price)

    def mark_to_market(self, timestamp: pd.Timestamp, close_price: float) -> float:
        equity = self.total_equity(close_price)
        self.equity_points.append(
            {
                "timestamp": timestamp,
                "equity": equity,
                "cash": self.cash,
                "position_qty": self.position_qty,
                "close": close_price,
            }
        )
        return equity

    def execute_order(self, timestamp: pd.Timestamp, side: str, qty: float, price: float) -> Trade | None:
        if qty <= 0:
            return None
        side = side.lower()
        if side not in {"buy", "sell"}:
            raise ValueError(f"Unsupported side: {side}")

        if side == "buy":
            fill_price = price * (1.0 + self.slippage_rate)
            affordable_qty = self.cash / (fill_price * (1.0 + self.fee_rate))
            trade_qty = min(qty, affordable_qty)
            if trade_qty <= 0:
                return None
            notional = trade_qty * fill_price
            fee = notional * self.fee_rate
            total_cost = notional + fee
            self.cash -= total_cost
            self.position_qty += trade_qty
            self.position_cost_basis += total_cost
            realized_pnl = 0.0
        else:
            trade_qty = min(qty, self.position_qty)
            if trade_qty <= 0:
                return None
            fill_price = price * (1.0 - self.slippage_rate)
            notional = trade_qty * fill_price
            fee = notional * self.fee_rate
            proceeds = notional - fee
            avg_cost = self.position_cost_basis / self.position_qty if self.position_qty > 0 else 0.0
            cost_released = avg_cost * trade_qty
            realized_pnl = proceeds - cost_released
            self.cash += proceeds
            self.position_qty -= trade_qty
            self.position_cost_basis -= cost_released
            if self.position_qty <= 1e-12:
                self.position_qty = 0.0
                self.position_cost_basis = 0.0

        trade = Trade(
            timestamp=timestamp,
            side=side,
            qty=trade_qty,
            fill_price=fill_price,
            notional=notional,
            fee=fee,
            realized_pnl=realized_pnl,
            cash_after=self.cash,
            position_after=self.position_qty,
        )
        self.trades.append(trade)
        return trade

    def trades_frame(self) -> pd.DataFrame:
        if not self.trades:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "side",
                    "qty",
                    "fill_price",
                    "notional",
                    "fee",
                    "realized_pnl",
                    "cash_after",
                    "position_after",
                ]
            )
        return pd.DataFrame([asdict(trade) for trade in self.trades])

    def equity_frame(self) -> pd.DataFrame:
        if not self.equity_points:
            return pd.DataFrame(columns=["timestamp", "equity", "cash", "position_qty", "close"])
        return pd.DataFrame(self.equity_points)

