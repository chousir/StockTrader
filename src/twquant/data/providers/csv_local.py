from pathlib import Path

import pandas as pd

from .base import BaseDataProvider, EmptyDataError

_DAILY_COLS = ["date", "stock_id", "open", "high", "low", "close", "volume"]


class CsvLocalProvider(BaseDataProvider):
    """本地 CSV 數據源（開發/測試備選）"""

    def __init__(self, data_dir: str = "data/sample"):
        self._dir = Path(data_dir)

    def fetch_daily(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        path = self._dir / f"twse_{stock_id}_sample.csv"
        if not path.exists():
            raise EmptyDataError(f"找不到本地 CSV 檔案: {path}")

        df = pd.read_csv(path, parse_dates=["date"])
        df["date"] = df["date"].dt.date
        df[["open", "high", "low", "close"]] = df[
            ["open", "high", "low", "close"]
        ].astype(float)
        df["volume"] = df["volume"].astype("int64")

        start = pd.to_datetime(start_date).date()
        end = pd.to_datetime(end_date).date()
        df = df[(df["date"] >= start) & (df["date"] <= end)].reset_index(drop=True)

        if df.empty:
            raise EmptyDataError(
                f"本地 CSV 無 {start_date}~{end_date} 的 {stock_id} 數據"
            )

        return df[_DAILY_COLS]

    def fetch_institutional(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        raise NotImplementedError("CsvLocalProvider 不支援三大法人數據")

    def fetch_margin_short(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        raise NotImplementedError("CsvLocalProvider 不支援融資融券數據")
