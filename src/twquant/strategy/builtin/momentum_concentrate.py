"""F｜動能精選策略：20日動能 > 5% + 收盤 > MA60 進場，跌破 MA60×0.97 出場"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy
from twquant.indicators.basic import compute_ma


class MomentumConcentrate(BaseStrategy):
    """F｜動能精選 ★ [強勢股]"""

    name = "F｜動能精選 ★"
    description = "[強勢股] ret₂₀>5%+Pt>MA60進場；Pt<MA60×0.97停損。台達電+369%，Sharpe 1.66，超額+223%"

    def __init__(
        self,
        ma_window: int = 60,
        ret_window: int = 20,
        ret_threshold: float = 0.05,
        stop_buffer: float = 0.03,
    ):
        self.ma_window = ma_window
        self.ret_window = ret_window
        self.ret_threshold = ret_threshold
        self.stop_buffer = stop_buffer

    def get_parameters(self) -> dict:
        return {
            "ma_window": self.ma_window,
            "ret_window": self.ret_window,
            "ret_threshold": self.ret_threshold,
            "stop_buffer": self.stop_buffer,
        }

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].astype(float)
        ma = compute_ma(close, self.ma_window)
        ret = close.pct_change(self.ret_window)

        entry_cond = (close > ma) & (ret > self.ret_threshold)
        exit_cond = close < ma * (1 - self.stop_buffer)

        prev_e = entry_cond.shift(1, fill_value=False)
        prev_x = exit_cond.shift(1, fill_value=False)
        return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)