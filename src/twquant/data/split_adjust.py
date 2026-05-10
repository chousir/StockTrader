"""股票分割/減資自動偵測與向前還原（backward split adjustment）"""

import numpy as np
import pandas as pd


_ROUND_RATIOS = [2.0, 2.5, 3.0, 4.0, 4.5, 5.0, 6.0, 7.0, 8.0, 10.0]
_SPLIT_THRESHOLD = 0.35  # 單日跌幅超過 35% 且符合整數比才視為分割


def detect_splits(close: np.ndarray) -> list[tuple[int, float]]:
    """
    回傳 [(split_index, ratio), ...] 清單。
    split_index = 分割後第一個交易日的 index；ratio = 分割前/後比（>1 表示縮股）。
    """
    splits = []
    for i in range(1, len(close)):
        if close[i - 1] == 0 or close[i] == 0:
            continue
        change = (close[i] - close[i - 1]) / close[i - 1]
        if change < -_SPLIT_THRESHOLD:
            raw_ratio = close[i - 1] / close[i]
            # For large drops (>60%), use exact ratio if no round match found
            matched = False
            for n in _ROUND_RATIOS:
                if abs(raw_ratio - n) / n < 0.12:
                    splits.append((i, n))
                    matched = True
                    break
            if not matched and raw_ratio >= 3.0:
                # Non-standard split: use actual observed ratio
                splits.append((i, raw_ratio))
    return splits


def apply_split_adjust(df: pd.DataFrame) -> pd.DataFrame:
    """
    回傳**還原**後的 DataFrame（原始 df 不修改）。
    - OHLC 全部做向前除權調整（歷史價格 ÷ 分割比）
    - Volume 做向前乘以分割比
    """
    df = df.sort_values("date").copy().reset_index(drop=True)
    close = df["close"].astype(float).values
    splits = detect_splits(close)

    if not splits:
        return df

    price_cols = [c for c in ["open", "high", "low", "close"] if c in df.columns]
    vol_cols   = [c for c in ["volume"] if c in df.columns]

    # 從最晚到最早逐一套用（避免多次分割互相影響）
    for idx, ratio in reversed(splits):
        df.loc[: idx - 1, price_cols] = (
            df.loc[: idx - 1, price_cols].astype(float).values / ratio
        )
        if vol_cols:
            df.loc[: idx - 1, vol_cols] = (
                df.loc[: idx - 1, vol_cols].astype(float).values * ratio
            )

    return df
