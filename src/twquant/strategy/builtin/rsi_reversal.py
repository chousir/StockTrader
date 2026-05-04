"""RSI 超賣/超買反轉策略：RSI < 30 進場，RSI > 70 出場"""

import numpy as np
import pandas as pd

from twquant.indicators.basic import compute_rsi
from twquant.strategy.base import BaseStrategy


class RSIReversal(BaseStrategy):
    name = "RSI Reversal"
    description = "RSI < oversold 進場，RSI > overbought 出場"

    def __init__(self, period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought

    def get_parameters(self) -> dict:
        return {"period": self.period, "oversold": self.oversold, "overbought": self.overbought}

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        rsi = compute_rsi(data["close"], self.period)
        entries = (rsi < self.oversold).to_numpy()
        exits = (rsi > self.overbought).to_numpy()
        return entries, exits
