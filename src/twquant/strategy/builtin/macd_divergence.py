"""MACD 柱狀圖轉向策略：histogram 由負轉正進場，由正轉負出場"""

import numpy as np
import pandas as pd

from twquant.indicators.basic import compute_macd
from twquant.strategy.base import BaseStrategy


class MACDDivergence(BaseStrategy):
    name = "MACD Divergence"
    description = "MACD histogram 由負轉正進場，由正轉負出場"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal

    def get_parameters(self) -> dict:
        return {"fast": self.fast, "slow": self.slow, "signal": self.signal}

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        _, _, hist = compute_macd(data["close"], self.fast, self.slow, self.signal)
        hist_prev = hist.shift(1)
        entries = ((hist_prev < 0) & (hist >= 0)).to_numpy()
        exits = ((hist_prev > 0) & (hist <= 0)).to_numpy()
        return entries, exits
