"""雙均線交叉策略：短均線上穿長均線進場，下穿出場"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy


class MACrossover(BaseStrategy):
    """雙均線交叉策略"""

    name = "雙均線交叉 (MA Crossover)"
    description = "短均線上穿長均線時進場，下穿時出場"

    def __init__(self, short_window: int = 5, long_window: int = 20):
        self.short_window = short_window
        self.long_window = long_window

    def get_parameters(self) -> dict:
        return {
            "short_window": self.short_window,
            "long_window": self.long_window,
        }

    def generate_signals(
        self, data: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].values.astype(float)
        n = len(close)

        short_ma = pd.Series(close).rolling(self.short_window).mean().values
        long_ma = pd.Series(close).rolling(self.long_window).mean().values

        # 短均線在長均線上方時為多頭
        above = short_ma > long_ma
        # 交叉：前一根不在上方，當根在上方 → 進場
        entries = np.zeros(n, dtype=bool)
        exits = np.zeros(n, dtype=bool)

        for i in range(1, n):
            if np.isnan(short_ma[i]) or np.isnan(long_ma[i]):
                continue
            if not above[i - 1] and above[i]:
                entries[i] = True
            elif above[i - 1] and not above[i]:
                exits[i] = True

        return entries, exits
