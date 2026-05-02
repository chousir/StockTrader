"""全市場數據同步引擎：HWM 斷點續傳、指數退避重試、冪等寫入"""

import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from typing import AsyncGenerator

import pandas as pd
from loguru import logger

from .providers.base import NetworkError, RateLimitError


class SyncStatus(Enum):
    NEVER_SYNCED = "never_synced"
    PARTIAL = "partial"
    UP_TO_DATE = "up_to_date"
    STALE = "stale"


@dataclass
class SyncMetadata:
    stock_id: str
    dataset: str
    last_synced_date: date | None = None
    last_sync_attempt: datetime | None = None
    status: SyncStatus = SyncStatus.NEVER_SYNCED
    error_count: int = 0


class MarketDataSyncEngine:
    """全市場數據同步引擎"""

    def __init__(self, provider, storage, config: dict | None = None):
        self.provider = provider
        self.storage = storage
        self.config = config or {}
        self._meta: dict[tuple[str, str], SyncMetadata] = {}

    # ─── HWM metadata 管理 ────────────────────────────────────────────────

    def _get_metadata(self, stock_id: str, dataset: str) -> SyncMetadata:
        key = (stock_id, dataset)
        if key not in self._meta:
            hwm = self.storage.get_hwm(f"{dataset}/{stock_id}")
            status = SyncStatus.NEVER_SYNCED if hwm is None else SyncStatus.STALE
            self._meta[key] = SyncMetadata(stock_id, dataset, last_synced_date=hwm, status=status)
        return self._meta[key]

    def _update_hwm(self, stock_id: str, dataset: str, new_date: date) -> None:
        meta = self._get_metadata(stock_id, dataset)
        meta.last_synced_date = new_date
        meta.status = SyncStatus.UP_TO_DATE
        meta.error_count = 0

    def _record_failure(self, stock_id: str, dataset: str, error: Exception) -> None:
        meta = self._get_metadata(stock_id, dataset)
        meta.error_count += 1
        meta.last_sync_attempt = datetime.now()
        meta.status = SyncStatus.PARTIAL

    # ─── 全市場首次初始化 ──────────────────────────────────────────────────

    async def initial_full_sync(
        self,
        start_date: str = "2010-01-01",
    ) -> AsyncGenerator[tuple[int, int, str], None]:
        """
        首次全市場同步。yield (completed, total, current_stock_id) 供進度條使用。
        支援斷點續傳：已 UP_TO_DATE 的股票自動跳過。
        """
        stock_list = self.provider.fetch_stock_list()
        total = len(stock_list)

        for i, stock_id in enumerate(stock_list):
            meta = self._get_metadata(stock_id, "daily_price")
            if meta.status == SyncStatus.UP_TO_DATE:
                yield (i + 1, total, stock_id)
                continue

            hwm = meta.last_synced_date
            fetch_start = (hwm + timedelta(days=1)).isoformat() if hwm else start_date

            try:
                df = await self._fetch_with_retry(stock_id, fetch_start)
                if df is not None and len(df) > 0:
                    await self._write_idempotent(stock_id, "daily_price", df)
                    self._update_hwm(stock_id, "daily_price", df["date"].max())
                else:
                    self._record_failure(stock_id, "daily_price", Exception("empty or None"))
            except Exception as e:
                self._record_failure(stock_id, "daily_price", e)
                logger.warning(f"[{stock_id}] 同步失敗，將在下次重試: {e}")

            yield (i + 1, total, stock_id)

    # ─── 增量更新 ─────────────────────────────────────────────────────────

    async def incremental_sync(self) -> None:
        """增量更新：僅抓取 HWM 之後的新數據，關注清單股票優先"""
        today = date.today()
        stock_list = self.provider.fetch_stock_list()

        try:
            from .watchlist import Watchlist
            watchlist_ids = set(Watchlist().list_all())
        except Exception:
            watchlist_ids = set()

        stock_list = sorted(
            stock_list,
            key=lambda sid: (0 if sid in watchlist_ids else 1, sid),
        )

        for stock_id in stock_list:
            meta = self._get_metadata(stock_id, "daily_price")
            if meta.last_synced_date and meta.last_synced_date >= today:
                continue

            start = (
                (meta.last_synced_date + timedelta(days=1)).isoformat()
                if meta.last_synced_date
                else "2010-01-01"
            )
            df = await self._fetch_with_retry(stock_id, start)
            if df is not None and len(df) > 0:
                await self._write_idempotent(stock_id, "daily_price", df)
                self._update_hwm(stock_id, "daily_price", df["date"].max())

    # ─── 闕漏偵測與回補 ───────────────────────────────────────────────────

    async def detect_and_fill_gaps(self) -> None:
        """偵測資料庫中的日期空洞並自動回補"""
        from ..utils.tw_calendar import TWCalendar

        cal = TWCalendar()
        all_symbols = self.storage.list_symbols()
        today = date.today()

        for symbol in all_symbols:
            if not symbol.startswith("daily_price/"):
                continue
            stock_id = symbol.split("/", 1)[1]
            local_dates = set(self.storage.get_dates(symbol))

            first = min(local_dates) if local_dates else date(2010, 1, 1)
            expected = set(cal.trading_days_between(first, today))
            missing = sorted(expected - local_dates)

            if not missing:
                continue

            ranges = self._merge_date_ranges(missing)
            for start, end in ranges:
                df = await self._fetch_with_retry(
                    stock_id, start.isoformat(), end.isoformat()
                )
                if df is not None and len(df) > 0:
                    await self._write_idempotent(stock_id, "daily_price", df)
                    logger.info(f"[{stock_id}] 回補 {start} ~ {end}，{len(df)} 筆")

    # ─── 帶退避重試的 API 呼叫 ────────────────────────────────────────────

    async def _fetch_with_retry(
        self,
        stock_id: str,
        start_date: str,
        end_date: str | None = None,
        max_retries: int = 3,
    ) -> pd.DataFrame | None:
        end = end_date or date.today().isoformat()
        for attempt in range(max_retries):
            try:
                loop = asyncio.get_event_loop()
                df = await loop.run_in_executor(
                    None,
                    lambda: self.provider.fetch_daily(stock_id, start_date, end),
                )
                return df
            except RateLimitError:
                wait = 60
                logger.info(f"[{stock_id}] API 限流，等待 {wait}s...")
                await asyncio.sleep(wait)
            except NetworkError as e:
                wait = 2 ** (attempt + 1)
                logger.warning(f"[{stock_id}] 網路錯誤，第 {attempt+1} 次重試，等待 {wait}s: {e}")
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"[{stock_id}] 不可重試的錯誤: {e}")
                raise
        logger.error(f"[{stock_id}] 達到最大重試次數 {max_retries}")
        return None

    # ─── 冪等寫入 ─────────────────────────────────────────────────────────

    async def _write_idempotent(
        self, stock_id: str, dataset: str, df: pd.DataFrame
    ) -> None:
        if df is None or df.empty:
            return
        df = df.drop_duplicates(subset=["date", "stock_id"], keep="last")
        self.storage.upsert(f"{dataset}/{stock_id}", df, date_column="date")

    # ─── 工具方法 ─────────────────────────────────────────────────────────

    @staticmethod
    def _merge_date_ranges(dates: list[date]) -> list[tuple[date, date]]:
        """將缺失日期列表合併為連續區間，減少 API 呼叫次數"""
        if not dates:
            return []
        ranges: list[tuple[date, date]] = []
        start = dates[0]
        prev = dates[0]
        for d in dates[1:]:
            if (d - prev).days > 7:  # 超過 7 天視為新區間（含週末）
                ranges.append((start, prev))
                start = d
            prev = d
        ranges.append((start, prev))
        return ranges
