"""
種子數據下載腳本：從 FinMind 下載歷史日K線並存入本地資料庫。
資料進管線時自動做分割還原（split_adjust）。

用法：
    python scripts/seed_data.py --universe          # 下載全 ANALYST_UNIVERSE（49 支）
    python scripts/seed_data.py --stocks 2330 0050  # 指定股票
    python scripts/seed_data.py --start 2015-01-01  # 指定起始日期（預設 2015-01-01）
    python scripts/seed_data.py --incremental       # 只補缺漏（從 HWM 接續）
"""
import argparse
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from loguru import logger

from twquant.data.providers.finmind import FinMindProvider
from twquant.data.sanity import TWSEDataSanityChecker
from twquant.data.storage import SQLiteStorage
from twquant.dashboard.config import get_finmind_token

DEFAULT_STOCKS = ["2330", "2317", "2454", "2412", "2882", "0050", "006208"]
DEFAULT_START = "2015-01-01"
DB_PATH = "data/twquant.db"


def get_universe_sids() -> list[str]:
    from twquant.data.universe import ANALYST_UNIVERSE
    seen: set[str] = set()
    result = []
    for stocks in ANALYST_UNIVERSE.values():
        for sid, _ in stocks:
            if sid not in seen:
                seen.add(sid)
                result.append(sid)
    return result


def main():
    parser = argparse.ArgumentParser(description="台股種子數據下載（含分割自動還原）")
    parser.add_argument("--stocks", nargs="+", default=None)
    parser.add_argument("--universe", action="store_true", help="下載全 ANALYST_UNIVERSE")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：從 DB 最後一筆日期接續，跳過已有完整資料的股票")
    args = parser.parse_args()

    # 決定股票清單
    if args.universe:
        stock_list = get_universe_sids()
        logger.info(f"--universe 模式：載入 {len(stock_list)} 支 ANALYST_UNIVERSE 股票")
    elif args.stocks:
        stock_list = args.stocks
    else:
        stock_list = DEFAULT_STOCKS

    token = get_finmind_token()
    provider = FinMindProvider(token=token)
    checker = TWSEDataSanityChecker()
    storage = SQLiteStorage(DB_PATH)

    today = datetime.date.today().isoformat()
    total = len(stock_list)
    ok = skip = fail = 0

    logger.info(f"共 {total} 支，起始 {args.start} ~ {today}，增量={args.incremental}")
    logger.info("資料進管線時自動執行分割還原（split_adjust）")

    for i, stock_id in enumerate(stock_list, 1):
        start = args.start

        if args.incremental:
            hwm = storage.get_hwm(f"daily_price/{stock_id}")
            if hwm:
                # 從 HWM 前一天接續，確保不漏
                from_date = (hwm - datetime.timedelta(days=5)).isoformat()
                if from_date >= today:
                    logger.info(f"[{i}/{total}] {stock_id}: 已最新，跳過")
                    skip += 1
                    continue
                start = from_date

        try:
            df = provider.fetch_daily(stock_id, start, today)
            result = checker.run_all_checks(df, stock_id)
            storage.upsert(f"daily_price/{stock_id}", result.passed)
            q = len(result.quarantined)
            logger.info(f"[{i}/{total}] {stock_id}: ✓ {len(result.passed)} 筆"
                        + (f"（隔離 {q} 筆）" if q else ""))
            ok += 1
        except Exception as e:
            logger.error(f"[{i}/{total}] {stock_id}: ✗ {e}")
            fail += 1

    logger.info(f"完成：成功 {ok}，跳過 {skip}，失敗 {fail}（共 {total} 支）")


if __name__ == "__main__":
    main()
