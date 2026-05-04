"""
Phase 2.9 - ExDividendFilter 測試
涵蓋：前復權調整、訊號遮罩、假跌破偵測
"""
import numpy as np
import pandas as pd
import pytest

from twquant.data.ex_dividend_filter import ExDividendFilter


def _price_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date":     ["2024-07-15", "2024-07-16", "2024-07-17", "2024-07-18", "2024-07-19"],
        "stock_id": ["2330"] * 5,
        "open":  [900.0, 905.0, 867.0, 870.0, 875.0],
        "high":  [910.0, 910.0, 875.0, 878.0, 880.0],
        "low":   [895.0, 900.0, 860.0, 865.0, 868.0],
        "close": [904.0, 867.0, 870.0, 875.0, 878.0],
        "volume": [25000000, 30000000, 28000000, 22000000, 20000000],
    })


def _cash_div(date_str: str, amount: float) -> pd.DataFrame:
    return pd.DataFrame({
        "date": [date_str],
        "cash_dividend": [amount],
        "stock_dividend": [0.0],
    })


@pytest.fixture
def filt():
    return ExDividendFilter()


# ─── 前復權 ───────────────────────────────────────────────────────────────────

class TestForwardAdjust:
    def test_prices_before_ex_date_adjusted(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        adj = filt.forward_adjust_prices(prices, divs)

        # 除息日前（index 0,1）的收盤價應減 3.5
        assert abs(adj.iloc[0]["close"] - (904.0 - 3.5)) < 0.01
        assert abs(adj.iloc[1]["close"] - (867.0 - 3.5)) < 0.01

    def test_prices_on_and_after_ex_date_unchanged(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        adj = filt.forward_adjust_prices(prices, divs)

        # 除息日當天及之後（index 2,3,4）不變
        assert abs(adj.iloc[2]["close"] - 870.0) < 0.01
        assert abs(adj.iloc[4]["close"] - 878.0) < 0.01

    def test_no_dividend_no_change(self, filt):
        prices = _price_df()
        divs = pd.DataFrame(columns=["date", "cash_dividend", "stock_dividend"])
        adj = filt.forward_adjust_prices(prices, divs)

        assert abs(adj.iloc[0]["close"] - 904.0) < 0.01

    def test_stock_dividend_adjusts_volume(self, filt):
        prices = _price_df()
        # 股票股利 10 元 = 1 股 → stock_ratio = 10/10 = 1 → volume *= 2
        divs = pd.DataFrame({
            "date": ["2024-07-17"],
            "cash_dividend": [0.0],
            "stock_dividend": [10.0],
        })
        adj = filt.forward_adjust_prices(prices, divs)
        # 除息日前的成交量應放大 2 倍
        assert adj.iloc[0]["volume"] == pytest.approx(prices.iloc[0]["volume"] * 2)

    def test_multiple_ex_dates_cumulative(self, filt):
        prices = _price_df()
        divs = pd.DataFrame({
            "date": ["2024-07-16", "2024-07-17"],
            "cash_dividend": [1.0, 2.0],
            "stock_dividend": [0.0, 0.0],
        })
        adj = filt.forward_adjust_prices(prices, divs)
        # row 0 應被兩次除息調整：- 1.0（for 07-16） - 2.0（for 07-17）
        expected = 904.0 - 1.0 - 2.0
        assert abs(adj.iloc[0]["close"] - expected) < 0.01


# ─── 訊號遮罩 ─────────────────────────────────────────────────────────────────

class TestSignalMask:
    def test_mask_is_bool_array(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        mask = filt.generate_signal_mask(prices, divs)
        assert mask.dtype == bool
        assert len(mask) == len(prices)

    def test_ex_date_window_suppressed(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        mask = filt.generate_signal_mask(prices, divs, suppress_days_before=1, suppress_days_after=1)
        # 除息日（index 2）應被抑制
        assert mask[2] == False

    def test_no_dividend_all_true(self, filt):
        prices = _price_df()
        divs = pd.DataFrame(columns=["date", "cash_dividend", "stock_dividend"])
        mask = filt.generate_signal_mask(prices, divs)
        assert mask.all()


# ─── 假跌破偵測 ───────────────────────────────────────────────────────────────

class TestFalseBreakdowns:
    def test_detects_ex_date_gap(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        report = filt.detect_false_breakdowns(prices, divs)

        assert len(report) == 1
        assert report.iloc[0]["is_false_breakdown"] == True
        assert report.iloc[0]["cash_dividend"] == pytest.approx(3.5)

    def test_no_dividend_no_events(self, filt):
        prices = _price_df()
        divs = pd.DataFrame(columns=["date", "cash_dividend", "stock_dividend"])
        report = filt.detect_false_breakdowns(prices, divs)
        assert len(report) == 0

    def test_gap_pct_calculated(self, filt):
        prices = _price_df()
        divs = _cash_div("2024-07-17", 3.5)
        report = filt.detect_false_breakdowns(prices, divs)

        expected_gap = (prices.iloc[2]["open"] - prices.iloc[1]["close"]) / prices.iloc[1]["close"]
        assert abs(report.iloc[0]["gap_pct"] - expected_gap) < 1e-6
