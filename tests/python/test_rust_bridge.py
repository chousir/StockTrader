"""
Phase 1.5 / 1.6 - PyO3 跨語言橋接完整測試
涵蓋：基本傳輸、大型陣列、輸入驗證、型別安全、Panic 捕獲、零拷貝效能
"""
import time

import numpy as np
import pandas as pd
import pytest

import twquant_core
from twquant.utils.rust_bridge import safe_call_rust

N = 1_000_000


# ─── 基本數值傳輸 ────────────────────────────────────────────────────────────

class TestBasicTransfer:
    def test_array_sum_small(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert twquant_core.array_sum(arr) == pytest.approx(15.0)

    def test_dot_product_correct(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([4.0, 5.0, 6.0])
        # 1*4 + 2*5 + 3*6 = 32
        assert twquant_core.dot_product(a, b) == pytest.approx(32.0)

    def test_moving_sum_correct(self):
        arr = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = twquant_core.moving_sum(arr, window=3)
        # [1+2+3, 2+3+4, 3+4+5] = [6, 9, 12]
        assert result == pytest.approx([6.0, 9.0, 12.0])

    def test_large_array_transfer(self):
        """步驟 1.6：大型陣列（100 萬元素）傳輸"""
        arr = np.ones(N, dtype=np.float64)
        result = twquant_core.array_sum(arr)
        assert result == pytest.approx(float(N), rel=1e-6)


# ─── 輸入驗證（Rust 端） ──────────────────────────────────────────────────────

class TestRustValidation:
    def test_empty_array_raises_value_error(self):
        """步驟 1.6：空陣列 → 明確 ValueError"""
        with pytest.raises(ValueError, match="不可為空"):
            twquant_core.array_sum(np.array([], dtype=np.float64))

    def test_full_nan_array_raises_value_error_with_position(self):
        """步驟 1.6：全 NaN 陣列 → ValueError 並指出位置"""
        arr = np.array([float("nan"), float("nan"), float("nan")])
        with pytest.raises(ValueError, match="位置 0"):
            twquant_core.array_sum(arr)

    def test_nan_in_middle_points_to_correct_position(self):
        arr = np.array([1.0, 2.0, float("nan"), 4.0])
        with pytest.raises(ValueError, match="位置 2"):
            twquant_core.array_sum(arr)

    def test_inf_raises_value_error(self):
        """步驟 1.6：Inf 值 → ValueError"""
        arr = np.array([1.0, float("inf"), 3.0])
        with pytest.raises(ValueError, match="位置 1"):
            twquant_core.array_sum(arr)

    def test_neg_inf_raises_value_error(self):
        arr = np.array([1.0, float("-inf"), 3.0])
        with pytest.raises(ValueError, match="位置 1"):
            twquant_core.array_sum(arr)

    def test_dimension_mismatch_raises_value_error(self):
        """步驟 1.6：維度不匹配 → ValueError"""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([1.0, 2.0])
        with pytest.raises(ValueError, match="維度不匹配"):
            twquant_core.dot_product(a, b)

    def test_window_too_large_raises_value_error(self):
        """步驟 1.6：window > data_len → ValueError"""
        arr = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="窗口大小"):
            twquant_core.moving_sum(arr, window=10)

    def test_zero_window_raises_value_error(self):
        arr = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="窗口大小"):
            twquant_core.moving_sum(arr, window=0)


# ─── Panic 安全捕獲 ───────────────────────────────────────────────────────────

class TestPanicSafety:
    def test_rust_panic_becomes_runtime_error_not_segfault(self):
        """步驟 1.6：Rust panic 被 catch_unwind 捕獲 → Python RuntimeError"""
        with pytest.raises(RuntimeError):
            twquant_core.trigger_panic()


# ─── 型別安全（直接呼叫 Rust，不經 safe_call_rust） ──────────────────────────

class TestDirectTypeRejection:
    def test_int32_array_raises_type_error(self):
        """步驟 1.6：int32 陣列直接傳 Rust → TypeError（PyO3 型別嚴格）"""
        arr = np.array([1, 2, 3], dtype=np.int32)
        with pytest.raises(TypeError):
            twquant_core.array_sum(arr)

    def test_string_raises_type_error(self):
        """步驟 1.6：string 直接傳 Rust → TypeError"""
        with pytest.raises(TypeError):
            twquant_core.array_sum("hello")


# ─── Python 端 safe_call_rust 包裝層 ─────────────────────────────────────────

class TestSafeCallRust:
    def test_series_auto_convert(self):
        """步驟 1.4 驗證：pd.Series → 自動轉換並成功呼叫"""
        s = pd.Series([1.0, 2.0, 3.0])
        assert safe_call_rust(twquant_core.array_sum, s) == pytest.approx(6.0)

    def test_int32_auto_cast_to_float64(self):
        """int32 → safe_call_rust 自動升型 float64 後成功"""
        arr = np.array([10, 20, 30], dtype=np.int32)
        assert safe_call_rust(twquant_core.array_sum, arr) == pytest.approx(60.0)

    def test_list_raises_type_error(self):
        """步驟 1.4 驗證：Python list → TypeError"""
        with pytest.raises(TypeError):
            safe_call_rust(twquant_core.array_sum, [1.0, 2.0, 3.0])

    def test_string_raises_type_error(self):
        with pytest.raises(TypeError):
            safe_call_rust(twquant_core.array_sum, "not_an_array")


# ─── 零拷貝效能（步驟 1.5） ──────────────────────────────────────────────────

class TestZeroCopyPerformance:
    def test_rust_faster_than_pure_python_5x(self):
        """步驟 1.5：Rust 處理 100 萬筆 float64 快於 pure Python 至少 5x"""
        arr = np.ones(N, dtype=np.float64)
        py_list = arr.tolist()

        REPS = 5

        # Rust
        t0 = time.perf_counter()
        for _ in range(REPS):
            twquant_core.array_sum(arr)
        rust_sec = (time.perf_counter() - t0) / REPS

        # Pure Python for loop（Python 位元組碼，無 C/NumPy 加速）
        t0 = time.perf_counter()
        for _ in range(REPS):
            total = 0.0
            for x in py_list:
                total += x
        py_sec = (time.perf_counter() - t0) / REPS

        speedup = py_sec / rust_sec
        print(
            f"\n[效能] Rust={rust_sec*1000:.2f}ms  "
            f"PurePython={py_sec*1000:.2f}ms  "
            f"speedup={speedup:.1f}x"
        )
        assert speedup >= 5.0, (
            f"Rust 應快於 pure Python 至少 5x，實際 {speedup:.1f}x"
        )
