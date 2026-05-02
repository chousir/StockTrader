"""Rust 自訂策略：Kalman 降噪訊號引擎（閉源邏輯包裝層）"""

import numpy as np
import pandas as pd

from ..base import BaseStrategy


class RustCustomStrategy(BaseStrategy):
    """
    基於 Rust Kalman 濾波降噪的自訂策略。
    內部呼叫 twquant_core 的 Rust 函數，零拷貝傳輸。
    """

    name = "Rust 自訂策略 (Kalman Denoise)"
    description = "Kalman 濾波平滑曲線斜率反轉訊號，閉源 Rust 實作"

    def __init__(
        self,
        process_noise: float = 0.01,
        measurement_noise: float = 1.0,
    ):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise

    def get_parameters(self) -> dict:
        return {
            "process_noise": self.process_noise,
            "measurement_noise": self.measurement_noise,
        }

    def generate_signals(
        self, data: pd.DataFrame
    ) -> tuple[np.ndarray, np.ndarray]:
        from ...utils.rust_bridge import safe_call_rust
        import twquant_core

        close = data["close"].to_numpy()
        close_f64 = np.ascontiguousarray(close, dtype=np.float64)

        entries_raw, exits_raw = safe_call_rust(
            lambda arr: twquant_core.compute_kalman_signals(
                arr, self.process_noise, self.measurement_noise
            ),
            close_f64,
        )
        return np.asarray(entries_raw, dtype=bool), np.asarray(exits_raw, dtype=bool)

    def get_smoothed_prices(self, data: pd.DataFrame) -> np.ndarray:
        """取得 Kalman 平滑後的價格曲線（供 Streamlit 疊加顯示）"""
        from ...utils.rust_bridge import safe_call_rust
        import twquant_core

        close = data["close"].to_numpy()
        close_f64 = np.ascontiguousarray(close, dtype=np.float64)
        return np.asarray(
            safe_call_rust(
                lambda arr: twquant_core.denoise_prices(
                    arr, self.process_noise, self.measurement_noise
                ),
                close_f64,
            )
        )
