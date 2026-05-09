"""
種子數據下載腳本：從 FinMind 下載歷史日K線並存入本地資料庫。
資料進管線時自動做分割還原（split_adjust）。

用法：
    python scripts/seed_data.py --universe          # 下載 ANALYST_UNIVERSE（49 支）
    python scripts/seed_data.py --all               # 下載全市場（TWSE+TPEX，~3000 支）
    python scripts/seed_data.py --all --type twse   # 只下載上市（~1800 支）
    python scripts/seed_data.py --stocks 2330 0050  # 指定股票
    python scripts/seed_data.py --start 2015-01-01  # 指定起始日期（預設 2015-01-01）
    python scripts/seed_data.py --incremental       # 只補缺漏（從 HWM 接續）
"""
import argparse
import datetime
import re
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


def get_all_market_sids(exchange_types: list[str]) -> list[str]:
    """從 FinMind 取得全市場股票清單（過濾掉權證/債券/期貨等）"""
    from FinMind.data import DataLoader
    api = DataLoader()
    token = get_finmind_token()
    if token:
        api.login_by_token(api_token=token)

    logger.info("從 FinMind 取得全市場股票清單...")
    info = api.taiwan_stock_info()

    # 只保留指定交易所
    info = info[info["type"].isin(exchange_types)].copy()

    # 一般股票：4碼純數字（1000-9999）
    stocks = info[info["stock_id"].astype(str).str.match(r"^[1-9]\d{3}$")]
    # ETF：0 開頭 4-6 碼數字
    etfs = info[info["stock_id"].astype(str).str.match(r"^0\d{3,5}$")]

    result = sorted(
        set(stocks["stock_id"].tolist()) | set(etfs["stock_id"].tolist())
    )
    logger.info(
        f"全市場股票: {len(stocks)} 支一般股票 + {len(etfs)} 支 ETF = 共 {len(result)} 支"
        f"（交易所: {exchange_types}）"
    )
    return result


def main():
    parser = argparse.ArgumentParser(description="台股種子數據下載（含分割自動還原）")
    parser.add_argument("--stocks", nargs="+", default=None, help="指定股票代碼")
    parser.add_argument("--universe", action="store_true", help="下載全 ANALYST_UNIVERSE")
    parser.add_argument("--all", dest="all_market", action="store_true",
                        help="下載全市場（TWSE+TPEX 所有一般股票+ETF）")
    parser.add_argument("--type", default="all", choices=["all", "twse", "tpex"],
                        help="交易所類型（預設 all）")
    parser.add_argument("--start", default=DEFAULT_START, help="起始日期")
    parser.add_argument("--incremental", action="store_true",
                        help="增量模式：從 DB HWM 接續下載")
    parser.add_argument("--skip-existing", action="store_true",
                        help="跳過 DB 中已有完整資料的股票（比 --incremental 更激進）")
    args = parser.parse_args()

    # 決定股票清單
    if args.all_market:
        exchange_map = {"all": ["twse", "tpex"], "twse": ["twse"], "tpex": ["tpex"]}
        stock_list = get_all_market_sids(exchange_map[args.type])
    elif args.universe:
        stock_list = get_universe_sids()
        logger.info(f"--universe 模式：{len(stock_list)} 支")
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

    logger.info(f"共 {total} 支，起始 {args.start} ~ {today}")
    logger.info(f"分割還原: ✓  增量模式: {args.incremental}  跳過已有: {args.skip_existing}")

    for i, stock_id in enumerate(stock_list, 1):
        start = args.start

        if args.skip_existing:
            hwm = storage.get_hwm(f"daily_price/{stock_id}")
            if hwm and (datetime.date.today() - hwm).days <= 3:
                logger.debug(f"[{i}/{total}] {stock_id}: 已最新，跳過")
                skip += 1
                continue

        if args.incremental:
            hwm = storage.get_hwm(f"daily_price/{stock_id}")
            if hwm:
                from_date = (hwm - datetime.timedelta(days=5)).isoformat()
                if from_date >= today:
                    skip += 1
                    continue
                start = from_date

        try:
            df = provider.fetch_daily(stock_id, start, today)
            result = checker.run_all_checks(df, stock_id)
            if result.passed.empty:
                logger.warning(f"[{i}/{total}] {stock_id}: 全部隔離，跳過")
                fail += 1
                continue
            storage.upsert(f"daily_price/{stock_id}", result.passed)
            q = len(result.quarantined)
            logger.info(f"[{i}/{total}] {stock_id}: ✓ {len(result.passed)} 筆"
                        + (f"（隔離 {q} 筆）" if q else ""))
            ok += 1
        except Exception as e:
            err = str(e)
            if "EmptyData" in err or "空數據" in err:
                logger.debug(f"[{i}/{total}] {stock_id}: 無資料（可能已下市）")
            else:
                logger.error(f"[{i}/{total}] {stock_id}: ✗ {e}")
            fail += 1

    logger.info(f"完成：成功 {ok}，跳過 {skip}，失敗 {fail}（共 {total} 支）")
    logger.info(f"DB 目前共 {len(storage.list_symbols())} 支")


if __name__ == "__main__":
    main()
