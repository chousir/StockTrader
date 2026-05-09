"""基礎技術指標：MA, EMA, RSI, MACD, Bollinger Bands, KD, BIAS, ATR"""

import pandas as pd


def compute_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window).mean()


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def compute_macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (macd_line, signal_line, histogram)."""
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger(
    series: pd.Series,
    window: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (upper, middle, lower)."""
    middle = compute_ma(series, window)
    std = series.rolling(window=window).std()
    upper = middle + std_dev * std
    lower = middle - std_dev * std
    return upper, middle, lower


def compute_kd(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 9,
    smooth_k: int = 3,
    smooth_d: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """
    KD 隨機指標（Stochastic Oscillator）。
    Returns (K, D)，範圍 0~100。
    台股慣用：period=9, smooth=3。
    """
    lowest_low   = low.rolling(period).min()
    highest_high = high.rolling(period).max()
    denom = (highest_high - lowest_low).replace(0, float("nan"))
    rsv = (close - lowest_low) / denom * 100
    k = rsv.ewm(com=smooth_k - 1, adjust=False).mean()
    d = k.ewm(com=smooth_d - 1, adjust=False).mean()
    return k, d


def compute_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Average True Range（平均真實波幅）"""
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def compute_bias(series: pd.Series, window: int = 20) -> pd.Series:
    """乖離率 BIAS = (收盤 - MAn) / MAn × 100"""
    ma = compute_ma(series, window)
    return (series - ma) / ma * 100
