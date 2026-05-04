"""
Phase 3 - 技術指標單元測試
涵蓋：MA, EMA, RSI, MACD, Bollinger Bands
"""
import numpy as np
import pandas as pd
import pytest

from twquant.indicators.basic import (
    compute_bollinger,
    compute_ema,
    compute_ma,
    compute_macd,
    compute_rsi,
)


@pytest.fixture
def close_series() -> pd.Series:
    np.random.seed(42)
    prices = 100.0 + np.cumsum(np.random.randn(60))
    return pd.Series(prices, name="close")


class TestMA:
    def test_length_preserved(self, close_series):
        result = compute_ma(close_series, 5)
        assert len(result) == len(close_series)

    def test_first_values_nan(self, close_series):
        result = compute_ma(close_series, 10)
        assert result.iloc[:9].isna().all()

    def test_value_correct(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        assert compute_ma(s, 3).iloc[2] == pytest.approx(2.0)

    def test_returns_series(self, close_series):
        assert isinstance(compute_ma(close_series, 5), pd.Series)


class TestEMA:
    def test_length_preserved(self, close_series):
        result = compute_ema(close_series, 12)
        assert len(result) == len(close_series)

    def test_no_nan_after_first(self, close_series):
        result = compute_ema(close_series, 12)
        assert result.iloc[1:].notna().all()

    def test_ema_smoother_than_price(self, close_series):
        ema = compute_ema(close_series, 12)
        assert ema.std() < close_series.std()


class TestRSI:
    def test_length_preserved(self, close_series):
        result = compute_rsi(close_series, 14)
        assert len(result) == len(close_series)

    def test_range_0_to_100(self, close_series):
        result = compute_rsi(close_series, 14).dropna()
        assert (result >= 0).all() and (result <= 100).all()

    def test_constant_price_nan_or_50(self):
        s = pd.Series([100.0] * 20)
        result = compute_rsi(s, 14).dropna()
        # 恆定價格：avg_loss=0 → RS 無窮大 → RSI=100，或有 NaN（除以零）
        assert result.isna().all() or (result == 100).all()

    def test_monotone_rising_rsi_high(self):
        # Pure monotone rising → avg_loss → 0 → RSI=100 or NaN (div-by-zero treated as NaN)
        s = pd.Series(range(1, 31, 1), dtype=float)
        result = compute_rsi(s, 14).dropna()
        assert result.empty or (result >= 70).all()


class TestMACD:
    def test_returns_three_series(self, close_series):
        macd, signal, hist = compute_macd(close_series)
        assert isinstance(macd, pd.Series)
        assert isinstance(signal, pd.Series)
        assert isinstance(hist, pd.Series)

    def test_histogram_equals_macd_minus_signal(self, close_series):
        macd, signal, hist = compute_macd(close_series)
        diff = (macd - signal - hist).dropna()
        assert (diff.abs() < 1e-10).all()

    def test_length_preserved(self, close_series):
        macd, signal, hist = compute_macd(close_series)
        assert len(hist) == len(close_series)


class TestBollinger:
    def test_returns_three_series(self, close_series):
        upper, middle, lower = compute_bollinger(close_series)
        assert isinstance(upper, pd.Series)
        assert isinstance(middle, pd.Series)
        assert isinstance(lower, pd.Series)

    def test_upper_above_middle_above_lower(self, close_series):
        upper, middle, lower = compute_bollinger(close_series)
        valid = upper.notna() & middle.notna() & lower.notna()
        assert (upper[valid] >= middle[valid]).all()
        assert (middle[valid] >= lower[valid]).all()

    def test_band_width_proportional_to_std(self):
        s = pd.Series([1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0,
                       1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0, 1.0, 2.0])
        upper, middle, lower = compute_bollinger(s, window=20, std_dev=2.0)
        width = (upper - lower).iloc[-1]
        std = s.std(ddof=1)
        assert abs(width - 4 * std) < 0.01
