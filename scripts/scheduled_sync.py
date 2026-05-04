"""
排程同步腳本：供 Docker cron 使用，每日收盤後自動增量更新數據。

用法：
    python scripts/scheduled_sync.py              # 執行一次增量同步
    python scripts/scheduled_sync.py --mode full  # 執行全量同步（首次使用）

環境變數：
    FINMIND_API_TOKEN   FinMind API Token
    ARCTICDB_URI        ArcticDB 連線字串（預設 lmdb://data/arcticdb）
    SYNC_MODE           full / incremental（預設 incremental）
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from twquant.data.providers.finmind import FinMindProvider
from twquant.data.storage import ArcticDBStorage, SQLiteStorage
from twquant.data.sync_engine import MarketDataSyncEngine


def _build_storage():
    uri = os.getenv("ARCTICDB_URI", "")
    if uri:
        return ArcticDBStorage(uri)
    return SQLiteStorage("data/twquant.db")


async def run_sync(mode: str):
    token = os.getenv("FINMIND_API_TOKEN", "")
    provider = FinMindProvider(token=token)
    storage = _build_storage()
    engine = MarketDataSyncEngine(provider, storage)

    if mode == "full":
        logger.info("全市場全量同步開始")
        total = 0
        async for completed, total_count, stock_id in engine.initial_full_sync():
            if completed % 50 == 0:
                logger.info(f"進度 {completed}/{total_count}（目前: {stock_id}）")
            total = total_count
        logger.info(f"全量同步完成，共 {total} 檔")
    else:
        logger.info("增量同步開始")
        await engine.incremental_sync()
        logger.info("增量同步完成")


def main():
    parser = argparse.ArgumentParser(description="台股數據排程同步")
    default_mode = os.getenv("SYNC_MODE", "incremental")
    parser.add_argument("--mode", choices=["full", "incremental"], default=default_mode)
    args = parser.parse_args()

    asyncio.run(run_sync(args.mode))


if __name__ == "__main__":
    main()
