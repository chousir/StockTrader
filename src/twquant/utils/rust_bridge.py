import numpy as np
import pandas as pd
from loguru import logger


def safe_call_rust(func, *arrays, **kwargs):
    """
    安全呼叫 Rust 函數的包裝器。

    職責：
    1. pd.Series → np.ndarray 自動轉換
    2. 拒絕非 array 型別（list、tuple 等）
    3. 強制 float64 + C-contiguous
    4. Python 側 NaN 預檢查（雙重保險）
    5. 捕獲 Rust ValueError / RuntimeError 並記錄
    """
    cleaned = []
    for i, arr in enumerate(arrays):
        if isinstance(arr, pd.Series):
            arr = arr.to_numpy()

        if not isinstance(arr, np.ndarray):
            raise TypeError(
                f"第 {i} 個參數必須是 np.ndarray 或 pd.Series，"
                f"實際為 {type(arr).__name__}"
            )

        arr = np.ascontiguousarray(arr, dtype=np.float64)

        nan_count = int(np.isnan(arr).sum())
        if nan_count > 0:
            logger.warning(
                f"第 {i} 個參數含有 {nan_count} 個 NaN，Rust 端將拒絕處理"
            )

        cleaned.append(arr)

    try:
        return func(*cleaned, **kwargs)
    except ValueError as e:
        logger.error(f"Rust 輸入驗證失敗: {e}")
        raise
    except RuntimeError as e:
        logger.error(f"Rust 運算錯誤: {e}")
        raise
