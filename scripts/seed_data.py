"""
種子數據下載腳本：從 FinMind 下載指定股票的歷史日K線並存入本地資料庫。
用途：首次建置本地數據庫，或在 Codespace 中快速初始化常用股票。

用法：
    python scripts/seed_data.py                      # 預設清單 + SQLite
    python scripts/seed_data.py --stocks 2330 0050   # 指定股票
    python scripts/seed_data.py --start 2020-01-01   # 指定起始日期
    python scripts/seed_data.py --storage arctic      # 使用 ArcticDB
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from twquant.data.providers.finmind import FinMindProvider
from twquant.data.sanity import TWSEDataSanityChecker
from twquant.data.storage import ArcticDBStorage, SQLiteStorage
from twquant.dashboard.config import get_finmind_token

DEFAULT_STOCKS = ["2330", "2317", "2454", "2412", "2882", "0050", "006208"]
DEFAULT_START = "2015-01-01"


def main():
    parser = argparse.ArgumentParser(description="台股種子數據下載")
    parser.add_argument("--stocks", nargs="+", default=DEFAULT_STOCKS)
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--storage", choices=["sqlite", "arctic"], default="sqlite")
    args = parser.parse_args()

    token = get_finmind_token()
    provider = FinMindProvider(token=token)
    checker = TWSEDataSanityChecker()

    if args.storage == "arctic":
        storage = ArcticDBStorage("lmdb://data/arcticdb")
    else:
        storage = SQLiteStorage("data/twquant.db")

    import datetime
    end = datetime.date.today().isoformat()

    logger.info(f"下載 {len(args.stocks)} 檔股票，{args.start} ~ {end}")

    for stock_id in args.stocks:
        try:
            df = provider.fetch_daily(stock_id, args.start, end)
            result = checker.run_all_checks(df, stock_id)
            storage.upsert(f"daily_price/{stock_id}", result.passed)
            logger.info(f"[{stock_id}] 完成，{len(result.passed)} 筆"
                        + (f"（隔離 {len(result.quarantined)} 筆）" if result.quarantined.shape[0] else ""))
        except Exception as e:
            logger.error(f"[{stock_id}] 失敗: {e}")

    logger.info("種子數據下載完成")


if __name__ == "__main__":
    main()
