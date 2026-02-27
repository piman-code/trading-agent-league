from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class Signal:
    action: str = "hold"
    size: float = 0.0


HOLD_SIGNAL = Signal(action="hold", size=0.0)


class BaseAgent:
    name = "base"

    def __init__(self) -> None:
        self.data: pd.DataFrame | None = None

    def reset(self) -> None:
        """Reset internal state before each backtest run."""

    def prepare(self, data: pd.DataFrame) -> None:
        """Pre-compute indicators using full history when needed."""
        self.data = data

    def on_bar(self, index: int, row: pd.Series, position_qty: float) -> Signal:
        raise NotImplementedError


class BuyAndHoldAgent(BaseAgent):
    name = "buy_hold"

    def __init__(self) -> None:
        super().__init__()
        self.entered = False

    def reset(self) -> None:
        self.entered = False

    def on_bar(self, index: int, row: pd.Series, position_qty: float) -> Signal:
        if not self.entered and position_qty <= 0:
            self.entered = True
            return Signal(action="buy", size=1.0)
        return HOLD_SIGNAL


class SMACrossoverAgent(BaseAgent):
    name = "sma_crossover"

    def __init__(self, short_window: int = 20, long_window: int = 50) -> None:
        super().__init__()
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window")
        self.short_window = short_window
        self.long_window = long_window
        self.sma_short: pd.Series | None = None
        self.sma_long: pd.Series | None = None

    def reset(self) -> None:
        return None

    def prepare(self, data: pd.DataFrame) -> None:
        super().prepare(data)
        close = data["close"]
        self.sma_short = close.rolling(self.short_window).mean()
        self.sma_long = close.rolling(self.long_window).mean()

    def on_bar(self, index: int, row: pd.Series, position_qty: float) -> Signal:
        if self.sma_short is None or self.sma_long is None:
            return HOLD_SIGNAL
        fast = self.sma_short.iloc[index]
        slow = self.sma_long.iloc[index]
        if np.isnan(fast) or np.isnan(slow):
            return HOLD_SIGNAL
        if fast > slow and position_qty <= 0:
            return Signal(action="buy", size=1.0)
        if fast < slow and position_qty > 0:
            return Signal(action="sell", size=1.0)
        return HOLD_SIGNAL


class RSIMeanReversionAgent(BaseAgent):
    name = "rsi_mean_reversion"

    def __init__(
        self,
        period: int = 14,
        lower: float = 30.0,
        upper: float = 70.0,
        buy_size: float = 0.5,
    ) -> None:
        super().__init__()
        if lower >= upper:
            raise ValueError("lower RSI threshold must be less than upper")
        self.period = period
        self.lower = lower
        self.upper = upper
        self.buy_size = buy_size
        self.rsi: pd.Series | None = None

    def reset(self) -> None:
        return None

    def prepare(self, data: pd.DataFrame) -> None:
        super().prepare(data)
        close = data["close"]
        delta = close.diff()
        gains = delta.clip(lower=0.0)
        losses = -delta.clip(upper=0.0)
        avg_gain = gains.ewm(alpha=1 / self.period, adjust=False, min_periods=self.period).mean()
        avg_loss = losses.ewm(alpha=1 / self.period, adjust=False, min_periods=self.period).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        self.rsi = rsi.fillna(50.0)

    def on_bar(self, index: int, row: pd.Series, position_qty: float) -> Signal:
        if self.rsi is None:
            return HOLD_SIGNAL
        rsi_value = self.rsi.iloc[index]
        if np.isnan(rsi_value):
            return HOLD_SIGNAL
        if rsi_value < self.lower and position_qty <= 0:
            return Signal(action="buy", size=self.buy_size)
        if rsi_value > self.upper and position_qty > 0:
            return Signal(action="sell", size=1.0)
        return HOLD_SIGNAL


def get_baseline_agents() -> Dict[str, BaseAgent]:
    return {
        BuyAndHoldAgent.name: BuyAndHoldAgent(),
        SMACrossoverAgent.name: SMACrossoverAgent(),
        RSIMeanReversionAgent.name: RSIMeanReversionAgent(),
    }

