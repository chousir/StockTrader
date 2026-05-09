"""背景自動同步：盤中每 30 分鐘、盤後每小時更新一次 DB"""

import threading
import time
from datetime import datetime, timezone, timedelta

from loguru import logger

_thread: threading.Thread | None = None
_lock = threading.Lock()


def _is_market_hours() -> bool:
    """是否台灣盤中時間（週一到週五 09:00-13:30 TST）"""
    tst = datetime.now(timezone(timedelta(hours=8)))
    if tst.weekday() >= 5:
        return False
    h, m = tst.hour, tst.minute
    return (9, 0) <= (h, m) <= (13, 30)


def _sync_once(db_path: str, stock_ids: list[str]) -> None:
    """執行一次增量同步：從 DB HWM 到今日（自動同步 DB 中所有股票）"""
    from datetime import date
    from twquant.data.storage import SQLiteStorage
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.data.sanity import TWSEDataSanityChecker
    from twquant.dashboard.config import get_finmind_token

    storage = SQLiteStorage(db_path)
    # 從 DB 讀取所有已入庫股票，不受初始 stock_ids 限制
    all_syms = storage.list_symbols()
    all_sids = [s.replace("daily_price/", "") for s in all_syms if s.startswith("daily_price/")]
    # 合併傳入清單（seed 後首次 sync 時 DB 可能還空）
    merged = list(dict.fromkeys(all_sids + stock_ids))

    provider = FinMindProvider(token=get_finmind_token() or "")
    checker = TWSEDataSanityChecker()
    today = date.today().isoformat()
    updated = 0

    for sid in merged:
        symbol = f"daily_price/{sid}"
        hwm = storage.get_hwm(symbol)
        start = (
            (hwm + timedelta(days=1)).isoformat()
            if hwm and hwm.isoformat() < today
            else today
        )
        if start > today:
            continue
        try:
            df = provider.fetch_daily(sid, start, today)
            result = checker.run_all_checks(df, sid)
            if not result.passed.empty:
                storage.upsert(symbol, result.passed)
                updated += 1
        except Exception as e:
            logger.debug(f"[auto_sync] {sid} 跳過: {e}")
        time.sleep(0.2)

    logger.info(f"[auto_sync] 完成，更新 {updated}/{len(merged)} 檔")


def _worker(db_path: str, stock_ids: list[str]) -> None:
    while True:
        try:
            _sync_once(db_path, stock_ids)
        except Exception as e:
            logger.warning(f"[auto_sync] 同步異常: {e}")
        interval = 1800 if _is_market_hours() else 3600
        time.sleep(interval)


def ensure_running(db_path: str, stock_ids: list[str]) -> None:
    """確保背景同步執行緒已啟動（冪等，可多次呼叫）"""
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(
                target=_worker,
                args=(db_path, stock_ids),
                daemon=True,
                name="twquant-auto-sync",
            )
            _thread.start()
            logger.info(f"[auto_sync] 背景同步啟動，監控 {len(stock_ids)} 檔")


def last_sync_info(db_path: str, stock_ids: list[str] | None = None) -> dict:
    """回傳同步狀態摘要（供 UI 顯示），stock_ids 可省略，預設查詢 DB 全部"""
    from twquant.data.storage import SQLiteStorage
    from datetime import date

    storage = SQLiteStorage(db_path)
    all_syms = storage.list_symbols()
    all_sids = [s.replace("daily_price/", "") for s in all_syms if s.startswith("daily_price/")]
    merged = list(dict.fromkeys(all_sids + (stock_ids or [])))

    today = date.today()
    up_to_date = 0
    for sid in merged:
        hwm = storage.get_hwm(f"daily_price/{sid}")
        if hwm and (today - hwm).days <= 3:
            up_to_date += 1
    return {
        "total": len(merged),
        "up_to_date": up_to_date,
        "is_market_hours": _is_market_hours(),
        "thread_alive": _thread is not None and _thread.is_alive(),
    }
