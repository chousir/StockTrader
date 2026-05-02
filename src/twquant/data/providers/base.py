from abc import ABC, abstractmethod

import pandas as pd


class DataProviderError(Exception):
    """數據源基礎異常"""


class RateLimitError(DataProviderError):
    """API 速率超限"""


class NetworkError(DataProviderError):
    """網路連線錯誤"""


class EmptyDataError(DataProviderError):
    """API 回傳空數據"""


class BaseDataProvider(ABC):
    """數據源適配器抽象基底類別"""

    @abstractmethod
    def fetch_daily(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """取得日K線數據。返回欄位：date, stock_id, open, high, low, close, volume"""
        ...

    @abstractmethod
    def fetch_institutional(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """取得三大法人買賣超數據"""
        ...

    @abstractmethod
    def fetch_margin_short(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """取得融資融券數據"""
        ...
