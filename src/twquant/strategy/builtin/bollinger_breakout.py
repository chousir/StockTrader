"""布林帶突破策略：跌破下軌進場，觸及上軌出場"""

import numpy as np
import pandas as pd

from twquant.indicators.basic import compute_bollinger
from twquant.strategy.base import BaseStrategy


class BollingerBreakout(BaseStrategy):
    name = "Bollinger Breakout"
    description = "收盤跌破下軌進場，觸及上軌出場"

    def __init__(self, window: int = 20, std_dev: float = 2.0):
        self.window = window
        self.std_dev = std_dev

    def get_parameters(self) -> dict:
        return {"window": self.window, "std_dev": self.std_dev}

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        upper, _, lower = compute_bollinger(data["close"], self.window, self.std_dev)
        entries = (data["close"] < lower).to_numpy()
        exits = (data["close"] >= upper).to_numpy()
        return entries, exits
