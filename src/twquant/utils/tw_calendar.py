"""台股交易日曆工具：判斷交易日 / 取得交易日列表"""

from datetime import date, timedelta
from functools import lru_cache

import pandas as pd


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5  # 5=Sat, 6=Sun


@lru_cache(maxsize=4)
def _fetch_trading_dates(year_from: int, year_to: int) -> frozenset[date]:
    """從 FinMind 取得 TWSE 交易日（帶快取，同參數只取一次）"""
    from FinMind.data import DataLoader

    dl = DataLoader()
    raw = dl.taiwan_stock_info()
    # FinMind 沒有獨立的 trading date API，改用已知上市股票的日期集合代替
    # 用 0050 的日K線取得有效交易日曆（僅需呼叫一次）
    price = dl.taiwan_stock_daily(
        stock_id="0050",
        start_date=f"{year_from}-01-01",
        end_date=f"{year_to}-12-31",
    )
    return frozenset(pd.to_datetime(price["date"]).dt.date)


class TWCalendar:
    """台股交易日曆"""

    def __init__(self, use_api: bool = False):
        self._api_dates: frozenset[date] | None = None
        self._use_api = use_api

    def load_from_api(self, year_from: int = 2010, year_to: int | None = None) -> None:
        if year_to is None:
            year_to = date.today().year
        self._api_dates = _fetch_trading_dates(year_from, year_to)

    def is_trading_day(self, d: date | str) -> bool:
        """判斷是否為台股交易日"""
        if isinstance(d, str):
            d = pd.to_datetime(d).date()
        if is_weekend(d):
            return False
        if self._api_dates is not None:
            return d in self._api_dates
        return d not in _NATIONAL_HOLIDAYS

    def trading_days_between(self, start: date | str, end: date | str) -> list[date]:
        """回傳 [start, end] 之間的所有交易日列表"""
        if isinstance(start, str):
            start = pd.to_datetime(start).date()
        if isinstance(end, str):
            end = pd.to_datetime(end).date()

        days = []
        cur = start
        while cur <= end:
            if self.is_trading_day(cur):
                days.append(cur)
            cur += timedelta(days=1)
        return days

    def next_trading_day(self, d: date | str) -> date:
        """取得下一個交易日"""
        if isinstance(d, str):
            d = pd.to_datetime(d).date()
        cur = d + timedelta(days=1)
        while not self.is_trading_day(cur):
            cur += timedelta(days=1)
        return cur


_NATIONAL_HOLIDAYS = {
    # 以下為 2026 年主要國定假日（固定日期者；春節等浮動假日需由 API 取得）
    date(2026, 1, 1),   # 元旦
    date(2026, 2, 28),  # 和平紀念日
    date(2026, 4, 4),   # 兒童節
    date(2026, 5, 1),   # 勞動節
    date(2026, 10, 10), # 國慶日
}


def is_trading_day(d: date | str) -> bool:
    """簡易版：不需 API，僅排除六日與已知國定假日。適用於快速驗證。"""
    if isinstance(d, str):
        d = pd.to_datetime(d).date()
    return not is_weekend(d) and d not in _NATIONAL_HOLIDAYS
