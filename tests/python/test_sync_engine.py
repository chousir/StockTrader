"""
Phase 2.7 - MarketDataSyncEngine 測試
涵蓋：HWM 斷點續傳、增量更新、冪等寫入、merge_date_ranges
"""
import asyncio
from datetime import date, timedelta

import pandas as pd
import pytest

from twquant.data.providers.csv_local import CsvLocalProvider
from twquant.data.storage import SQLiteStorage
from twquant.data.sync_engine import MarketDataSyncEngine, SyncStatus


def _make_storage(tmp_path) -> SQLiteStorage:
    return SQLiteStorage(str(tmp_path / "test.db"))


def _make_provider():
    provider = CsvLocalProvider("data/sample")
    provider.fetch_stock_list = lambda: ["2330"]
    return provider


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── HWM 斷點續傳 ─────────────────────────────────────────────────────────────

class TestHWMResume:
    def test_first_sync_populates_data(self, tmp_path):
        storage = _make_storage(tmp_path)
        engine = MarketDataSyncEngine(_make_provider(), storage)

        results = _run(_collect(engine.initial_full_sync("2024-01-01")))
        assert len(results) == 1
        assert results[0][2] == "2330"

        loaded = storage.load("daily_price/2330")
        assert len(loaded) > 0

    def test_second_sync_skips_uptodate(self, tmp_path):
        storage = _make_storage(tmp_path)
        engine = MarketDataSyncEngine(_make_provider(), storage)

        _run(_collect(engine.initial_full_sync("2024-01-01")))
        hwm_after_first = storage.get_hwm("daily_price/2330")

        # 第二次同步：引擎應跳過已 UP_TO_DATE 的股票
        _run(_collect(engine.initial_full_sync("2024-01-01")))
        hwm_after_second = storage.get_hwm("daily_price/2330")

        assert hwm_after_first == hwm_after_second

    def test_hwm_reflects_latest_date(self, tmp_path):
        storage = _make_storage(tmp_path)
        engine = MarketDataSyncEngine(_make_provider(), storage)

        _run(_collect(engine.initial_full_sync("2024-01-01")))
        hwm = storage.get_hwm("daily_price/2330")

        loaded = storage.load("daily_price/2330")
        max_date = pd.to_datetime(loaded["date"]).dt.date.max()
        assert hwm == max_date


# ─── 冪等寫入 ─────────────────────────────────────────────────────────────────

class TestIdempotentWrite:
    def test_double_sync_no_duplicate_rows(self, tmp_path):
        storage = _make_storage(tmp_path)
        provider = CsvLocalProvider("data/sample")
        provider.fetch_stock_list = lambda: ["2330"]
        engine = MarketDataSyncEngine(provider, storage)

        # 手動 upsert 兩次相同數據
        df = pd.read_csv("data/sample/twse_2330_sample.csv")
        _run(engine._write_idempotent("2330", "daily_price", df))
        _run(engine._write_idempotent("2330", "daily_price", df))

        loaded = storage.load("daily_price/2330")
        # 不能比原始數據多
        assert len(loaded) <= len(df)

    def test_write_with_duplicate_dates_keeps_last(self, tmp_path):
        storage = _make_storage(tmp_path)
        provider = CsvLocalProvider("data/sample")
        engine = MarketDataSyncEngine(provider, storage)

        df = pd.DataFrame({
            "date": ["2024-01-02", "2024-01-02"],
            "stock_id": ["2330", "2330"],
            "open": [590.0, 591.0],
            "high": [593.0, 594.0],
            "low": [589.0, 590.0],
            "close": [593.0, 592.0],
            "volume": [10000000, 11000000],
        })
        _run(engine._write_idempotent("2330", "daily_price", df))
        loaded = storage.load("daily_price/2330")
        # 重複日期應只保留一筆
        assert len(loaded[pd.to_datetime(loaded["date"]).dt.date == date(2024, 1, 2)]) == 1


# ─── merge_date_ranges 工具 ───────────────────────────────────────────────────

class TestMergeDateRanges:
    def test_empty(self):
        assert MarketDataSyncEngine._merge_date_ranges([]) == []

    def test_single(self):
        d = date(2024, 1, 2)
        result = MarketDataSyncEngine._merge_date_ranges([d])
        assert result == [(d, d)]

    def test_consecutive_merged(self):
        dates = [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]
        result = MarketDataSyncEngine._merge_date_ranges(dates)
        assert len(result) == 1
        assert result[0] == (date(2024, 1, 2), date(2024, 1, 4))

    def test_large_gap_splits(self):
        dates = [date(2024, 1, 2), date(2024, 3, 1)]
        result = MarketDataSyncEngine._merge_date_ranges(dates)
        assert len(result) == 2


# ─── 輔助 ─────────────────────────────────────────────────────────────────────

async def _collect(gen):
    results = []
    async for item in gen:
        results.append(item)
    return results
