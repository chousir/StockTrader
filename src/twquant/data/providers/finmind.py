import time
from threading import Lock

import pandas as pd
from FinMind.data import DataLoader
from loguru import logger

from .base import (
    BaseDataProvider,
    EmptyDataError,
    NetworkError,
    RateLimitError,
)

_DAILY_RENAME = {"Trading_Volume": "volume", "max": "high", "min": "low"}
_DAILY_COLS = ["date", "stock_id", "open", "high", "low", "close", "volume"]


class _RateLimiter:
    """滑動視窗速率限制器"""

    def __init__(self, max_calls: int, period: int = 3600):
        self._max = max_calls
        self._period = period
        self._calls: list[float] = []
        self._lock = Lock()

    def wait_if_needed(self) -> None:
        with self._lock:
            now = time.time()
            self._calls = [t for t in self._calls if now - t < self._period]
            if len(self._calls) >= self._max:
                wait = self._period - (now - self._calls[0]) + 0.1
                if wait > 0:
                    logger.info(f"速率限制：等待 {wait:.1f}s")
                    time.sleep(wait)
                self._calls = [t for t in self._calls if time.time() - t < self._period]
            self._calls.append(time.time())


class FinMindProvider(BaseDataProvider):
    """FinMind API 數據源適配器"""

    def __init__(self, token: str = ""):
        self._api = DataLoader()
        if token:
            self._api.login_by_token(api_token=token)
        # 登入後 600/hr，未登入 300/hr
        limit = 600 if token else 300
        self._limiter = _RateLimiter(max_calls=limit)

    # ─── 日K線 ────────────────────────────────────────────────────────────

    def fetch_daily(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self._limiter.wait_if_needed()
        try:
            raw = self._api.taiwan_stock_daily(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower() or "limit" in msg.lower():
                raise RateLimitError(f"FinMind API 超限 [{stock_id}]: {e}") from e
            raise NetworkError(f"FinMind API 網路錯誤 [{stock_id}]: {e}") from e

        if raw is None or raw.empty:
            raise EmptyDataError(
                f"FinMind 回傳空數據: stock={stock_id} {start_date}~{end_date}"
            )

        return self._normalize_daily(raw)

    def _normalize_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.rename(columns=_DAILY_RENAME)[_DAILY_COLS].copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df[["open", "high", "low", "close"]] = df[
            ["open", "high", "low", "close"]
        ].astype(float)
        df["volume"] = df["volume"].astype("int64")
        df = df.sort_values("date").reset_index(drop=True)
        from ..split_adjust import apply_split_adjust
        return apply_split_adjust(df)

    # ─── 三大法人 ─────────────────────────────────────────────────────────

    def fetch_institutional(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self._limiter.wait_if_needed()
        try:
            raw = self._api.taiwan_stock_institutional_investors(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                raise RateLimitError(f"FinMind API 超限 [{stock_id}]: {e}") from e
            raise NetworkError(f"FinMind API 網路錯誤 [{stock_id}]: {e}") from e

        if raw is None or raw.empty:
            raise EmptyDataError(
                f"FinMind 三大法人回傳空數據: stock={stock_id}"
            )

        # pivot: name 欄位轉為各法人的 buy/sell 欄位
        pivot_buy = raw.pivot_table(
            index=["date", "stock_id"], columns="name", values="buy", aggfunc="sum"
        ).add_suffix("_buy")
        pivot_sell = raw.pivot_table(
            index=["date", "stock_id"], columns="name", values="sell", aggfunc="sum"
        ).add_suffix("_sell")
        df = pd.concat([pivot_buy, pivot_sell], axis=1).reset_index()
        df.columns.name = None
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df.sort_values("date").reset_index(drop=True)

    # ─── 融資融券 ─────────────────────────────────────────────────────────

    def fetch_margin_short(
        self,
        stock_id: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        self._limiter.wait_if_needed()
        try:
            raw = self._api.taiwan_stock_margin_purchase_short_sale(
                stock_id=stock_id,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as e:
            msg = str(e)
            if "429" in msg or "rate" in msg.lower():
                raise RateLimitError(f"FinMind API 超限 [{stock_id}]: {e}") from e
            raise NetworkError(f"FinMind API 網路錯誤 [{stock_id}]: {e}") from e

        if raw is None or raw.empty:
            raise EmptyDataError(
                f"FinMind 融資融券回傳空數據: stock={stock_id}"
            )

        df = raw.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df.sort_values("date").reset_index(drop=True)

    # ─── 輔助 ─────────────────────────────────────────────────────────────

    def fetch_stock_list(self) -> list[str]:
        """取得全市場股票代碼清單"""
        raw = self._api.taiwan_stock_info()
        return raw["stock_id"].astype(str).tolist()
