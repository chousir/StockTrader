"""H｜量價突破策略：收盤創20日高 + 量比>1.5x + MA60趨勢 + RSI<76 進場"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy
from twquant.indicators.basic import compute_ma, compute_rsi


class VolumeBreakout(BaseStrategy):
    """H｜量價突破 [突破型]"""

    name = "H｜量價突破"
    description = "[突破型] Pt>20日高+量比>1.5x+Pt>MA60+RSI<76進場；Pt<MA60×0.96 OR RSI>85出場。Sharpe 1.81最高"

    def __init__(
        self,
        high_window: int = 20,
        vol_ratio: float = 1.5,
        ma_window: int = 60,
        rsi_entry: float = 76.0,
        rsi_exit: float = 85.0,
        stop_buffer: float = 0.04,
    ):
        self.high_window = high_window
        self.vol_ratio = vol_ratio
        self.ma_window = ma_window
        self.rsi_entry = rsi_entry
        self.rsi_exit = rsi_exit
        self.stop_buffer = stop_buffer

    def get_parameters(self) -> dict:
        return {
            "high_window": self.high_window,
            "vol_ratio": self.vol_ratio,
            "ma_window": self.ma_window,
            "rsi_entry": self.rsi_entry,
            "rsi_exit": self.rsi_exit,
            "stop_buffer": self.stop_buffer,
        }

    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        close = data["close"].astype(float)
        volume = data["volume"].astype(float)
        ma = compute_ma(close, self.ma_window)
        rsi = compute_rsi(close, 14)
        high_n = close.rolling(self.high_window).max().shift(1)
        vol_n = volume.rolling(self.high_window).mean()

        entry_cond = (close > high_n) & (volume > vol_n * self.vol_ratio) & (close > ma) & (rsi < self.rsi_entry)
        exit_cond = (close < ma * (1 - self.stop_buffer)) | (rsi > self.rsi_exit)

        prev_e = entry_cond.shift(1, fill_value=False)
        prev_x = exit_cond.shift(1, fill_value=False)
        return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)