"""
Phase 2.8 - TWSEDataSanityChecker 測試
涵蓋：7 項 OHLCV 合理性檢查、可疑數據隔離、正常數據全通過
"""
import numpy as np
import pandas as pd
import pytest

from twquant.data.sanity import TWSEDataSanityChecker


def _base_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03", "2024-01-04"],
        "stock_id": ["2330"] * 3,
        "open":  [590.0, 584.0, 580.0],
        "high":  [593.0, 585.0, 583.0],
        "low":   [589.0, 576.0, 578.0],
        "close": [593.0, 578.0, 582.0],
        "volume": [27000000, 40000000, 25000000],
    })


@pytest.fixture
def checker():
    return TWSEDataSanityChecker()


# ─── 正常數據 ─────────────────────────────────────────────────────────────────

class TestNormalData:
    def test_clean_data_all_pass(self, checker):
        result = checker.run_all_checks(_base_df(), "2330")
        assert len(result.passed) == 3
        assert len(result.quarantined) == 0
        assert result.report == []


# ─── 檢查 1：OHLC 邏輯關係 ───────────────────────────────────────────────────

class TestOHLCLogic:
    def test_high_less_than_low_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "high"] = 585.0
        df.loc[0, "low"] = 591.0  # low > high
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1
        assert any("OHLC" in r for r in result.report)

    def test_high_less_than_open_quarantined(self, checker):
        df = _base_df()
        df.loc[1, "high"] = 580.0  # high < open(584)
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1

    def test_low_greater_than_close_quarantined(self, checker):
        df = _base_df()
        df.loc[2, "low"] = 590.0  # low > close(582)
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1


# ─── 檢查 2：價格非正數 ───────────────────────────────────────────────────────

class TestNonPositivePrice:
    def test_zero_price_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "open"] = 0.0
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1
        assert any("<= 0" in r for r in result.report)

    def test_negative_price_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "close"] = -10.0
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1


# ─── 檢查 3：成交量異常 ───────────────────────────────────────────────────────

class TestVolumeCheck:
    def test_negative_volume_quarantined(self, checker):
        df = _base_df()
        df.loc[1, "volume"] = -1
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1
        assert any("成交量" in r for r in result.report)

    def test_nan_volume_quarantined(self, checker):
        df = _base_df()
        df = df.astype({"volume": float})
        df.loc[2, "volume"] = float("nan")
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) == 1


# ─── 檢查 4：日期重複 ─────────────────────────────────────────────────────────

class TestDuplicateDate:
    def test_duplicate_date_quarantined(self, checker):
        df = _base_df()
        df.loc[1, "date"] = "2024-01-02"  # 與 row 0 重複
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) >= 1
        assert any("重複" in r for r in result.report)


# ─── 檢查 6：NaN / Inf ────────────────────────────────────────────────────────

class TestNaNInf:
    def test_nan_in_close_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "close"] = float("nan")
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) >= 1
        assert any("NaN" in r or "Inf" in r for r in result.report)

    def test_inf_in_high_quarantined(self, checker):
        df = _base_df()
        df.loc[1, "high"] = float("inf")
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) >= 1


# ─── 檢查 7：日期合理性 ───────────────────────────────────────────────────────

class TestDateRange:
    def test_date_before_1990_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "date"] = "1985-01-01"
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) >= 1
        assert any("日期" in r for r in result.report)

    def test_future_date_quarantined(self, checker):
        df = _base_df()
        df.loc[0, "date"] = "2099-12-31"
        result = checker.run_all_checks(df, "2330")
        assert len(result.quarantined) >= 1
