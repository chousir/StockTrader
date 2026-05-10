"""M｜風險調整動能 RAM：ret₂₀/(σ₂₀×√20) > 0.7 + MA60 > MA120 進場"""

import math

import numpy as np
import pandas as pd

from ..base import BaseStrategy
from twquant.indicators.basic import compute_ma


class RiskAdjMomentum(BaseStrategy):
    """M｜RAM 風險調整動能 [全市場]"""

    name = "M｜RAM 風險調整動能"
    description = "[全市場] RAM=ret₂₀/(σ₂₀×√20)>0.7+Pt>MA60+MA60>MA120進場；RAM<0 OR Pt<MA60×0.97出場。超額+285%最高"

    def __init__(
        self,
        ret_window: int = 20,
        vol_window: int = 20,
        ram_entry: float = 0.7,
        ma_trend: int = 60,
        ma_long: int = 120,
        stop_buffer: float = 0.03,
    ):
        self.ret_window = ret_window
        self.vol_window = vol_window
        self.ram_entry = ram_entry
        self._ram_exit = 0.0  # 固定：動能歸零即出場
        self.ma_trend = ma_trend
        self.ma_long = ma_long
        self.stop_buffer = stop_buffer

    def get_parameters(self) -> dict:
        return {
            "ret_window": self.ret_window,
            "vol_window": self.vol_window,
            "ram_entry": self.ram_entry,
            "ma_trend": self.ma_trend,
            "ma_long": self.ma_long,
            "stop_buffer": self.stop_buffer,
        }

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].astype(float)
        ma60 = compute_ma(close, self.ma_trend)
        ma120 = compute_ma(close, self.ma_long)
        ret = close.pct_change(self.ret_window)
        vol = close.pct_change().rolling(self.vol_window).std().replace(0, float("nan"))
        ram = ret / (vol * math.sqrt(self.vol_window))

        entry_cond = (ram > self.ram_entry) & (close > ma60) & (ma60 > ma120)
        exit_cond = (ram < self._ram_exit) | (close < ma60 * (1 - self.stop_buffer))

        prev_e = entry_cond.shift(1, fill_value=False)
        prev_x = exit_cond.shift(1, fill_value=False)
        return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)