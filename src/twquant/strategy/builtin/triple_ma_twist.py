"""L｜三線扭轉策略：MA5/20/60 多頭排列剛成立的第一天 + RSI<72 進場"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy
from twquant.indicators.basic import compute_ma, compute_rsi


class TripleMATwist(BaseStrategy):
    """L｜三線扭轉 [全市場]"""

    name = "L｜三線扭轉"
    description = "[全市場] MA5>MA20>MA60多頭排列剛成立第一天+RSI<72進場；MA5<MA20 OR Pt<MA60×0.95出場"

    def __init__(
        self,
        ma_short: int = 5,
        ma_mid: int = 20,
        ma_long: int = 60,
        rsi_cap: float = 72.0,
        stop_buffer: float = 0.05,
    ):
        self.ma_short = ma_short
        self.ma_mid = ma_mid
        self.ma_long = ma_long
        self.rsi_cap = rsi_cap
        self.stop_buffer = stop_buffer

    def get_parameters(self) -> dict:
        return {
            "ma_short": self.ma_short,
            "ma_mid": self.ma_mid,
            "ma_long": self.ma_long,
            "rsi_cap": self.rsi_cap,
            "stop_buffer": self.stop_buffer,
        }

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].astype(float)
        ma5 = compute_ma(close, self.ma_short)
        ma20 = compute_ma(close, self.ma_mid)
        ma60 = compute_ma(close, self.ma_long)
        rsi = compute_rsi(close, 14)

        aligned = (ma5 > ma20) & (ma20 > ma60) & (close > ma5)
        prev_aligned = aligned.shift(1, fill_value=False)
        entry_cond = aligned & ~prev_aligned & (rsi < self.rsi_cap)
        exit_cond = ((ma5 < ma20) | (close < ma60 * (1 - self.stop_buffer))).fillna(False).infer_objects(copy=False).astype(bool)

        prev_e = entry_cond.shift(1, fill_value=False)
        prev_x = exit_cond.shift(1, fill_value=False)
        return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)