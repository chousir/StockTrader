"""策略抽象基底類別"""

from abc import ABC, abstractmethod

import numpy as np
import pandas as pd


class BaseStrategy(ABC):
    """策略抽象基底類別"""

    name: str = "Unnamed Strategy"
    description: str = ""

    @abstractmethod
    def generate_signals(
        self, data: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray]:
        """
        產生進出場訊號。

        Parameters:
            data: OHLCV DataFrame，需含 open/high/low/close/volume 欄位

        Returns:
            (entries, exits): bool 陣列，True 表示該日進場/出場
        """

    def get_parameters(self) -> dict:
        """回傳策略可調參數及預設值"""
        return {}

    def validate_data(self, data: pd.DataFrame) -> bool:
        required_cols = {"open", "high", "low", "close", "volume"}
        return required_cols.issubset(set(data.columns))

    def apply_ex_dividend_mask(
        self,
        entries: np.ndarray,
        exits: np.ndarray,
        mask: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """將除權息遮罩套用到進出場訊號上"""
        return entries & mask, exits & mask
