"""時間序列重採樣工具：日K → 週K / 月K"""

import pandas as pd


_OHLCV_AGG = {
    "open":   "first",
    "high":   "max",
    "low":    "min",
    "close":  "last",
    "volume": "sum",
}


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    將日K線重採樣為週K或月K。

    Parameters:
        df:   需含 date/open/high/low/close/volume 欄位，date 為 str 或 date
        freq: "W"（週K）或 "ME"（月K，Pandas 2.2+ 用 ME 取代 M）

    Returns:
        重採樣後的 DataFrame，date 欄位為該週期結尾日期
    """
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()

    agg_cols = {k: v for k, v in _OHLCV_AGG.items() if k in d.columns}

    resampled = d.resample(freq).agg(agg_cols).dropna(subset=["close"])
    resampled = resampled.reset_index()
    resampled["date"] = resampled["date"].dt.date

    if "stock_id" in df.columns:
        resampled.insert(1, "stock_id", df["stock_id"].iloc[0])

    return resampled


def to_weekly(df: pd.DataFrame) -> pd.DataFrame:
    return resample_ohlcv(df, "W")


def to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    return resample_ohlcv(df, "ME")
