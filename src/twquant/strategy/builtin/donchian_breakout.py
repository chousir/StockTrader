"""N｜唐奇安通道突破：Pt > DC_upper(20前日) + 量比>1.2x + MA60 + RSI<76 進場"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy
from twquant.indicators.basic import compute_ma, compute_rsi, compute_donchian


class DonchianBreakout(BaseStrategy):
    """N｜唐奇安通道突破 [突破型]"""

    name = "N｜唐奇安通道突破"
    description = "[突破型] Pt>DC_upper(20)+量比>1.2x+Pt>MA60+RSI<76進場；Pt<DC_lower OR RSI>85 OR Pt<MA60×0.95出場"

    def __init__(
        self,
        dc_window: int = 20,
        vol_ratio: float = 1.2,
        ma_filter: int = 60,
        rsi_entry: float = 76.0,
        rsi_exit: float = 85.0,
        stop_buffer: float = 0.05,
    ):
        self.dc_window = dc_window
        self.vol_ratio = vol_ratio
        self.ma_filter = ma_filter
        self.rsi_entry = rsi_entry
        self.rsi_exit = rsi_exit
        self.stop_buffer = stop_buffer

    def get_parameters(self) -> dict:
        return {
            "dc_window": self.dc_window,
            "vol_ratio": self.vol_ratio,
            "ma_filter": self.ma_filter,
            "rsi_entry": self.rsi_entry,
            "rsi_exit": self.rsi_exit,
            "stop_buffer": self.stop_buffer,
        }

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].astype(float)
        high = data["high"].astype(float)
        low = data["low"].astype(float)
        volume = data["volume"].astype(float)
        ma = compute_ma(close, self.ma_filter)
        rsi = compute_rsi(close, 14)
        upper, _, lower = compute_donchian(high, low, self.dc_window)
        vol_n = volume.rolling(self.dc_window).mean()

        entry_cond = (close > upper.shift(1)) & (volume > vol_n * self.vol_ratio) & (close > ma) & (rsi < self.rsi_entry)
        exit_cond = (close < lower) | (rsi > self.rsi_exit) | (close < ma * (1 - self.stop_buffer))

        prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
        prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
        return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)