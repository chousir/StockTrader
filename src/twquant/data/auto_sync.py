"""智能背景自動同步：盤中 5 分鐘 / 盤後 60 分鐘

每輪兩階段：
  Phase A（補新）：DB 內已入庫股票，從 HWM 增量補到 today
  Phase B（擴宇宙）：宇宙中尚未入庫的股票，每輪挑 N 支補抓 2015-01-01 起

進度寫入 _sync_jobs 表，UI 可即時讀取。
"""

import threading
import time
from datetime import datetime, timezone, timedelta, date

from loguru import logger

from twquant.data.sync_jobs import (
    create_job, update_progress, finish_job, is_cancelled,
)

_thread: threading.Thread | None = None
_lock = threading.Lock()

# 速率參數（盤中 batch=10，每秒約 3 req → 1 小時 1080 req，FinMind 限 600/h 故 sleep 拉到 0.3s）
_BATCH_MARKET_HOURS = 10
_BATCH_OFF_HOURS = 50
_INTERVAL_MARKET = 300
_INTERVAL_OFF = 3600
_SLEEP_PER_REQ = 0.3


def _is_market_hours() -> bool:
    tst = datetime.now(timezone(timedelta(hours=8)))
    if tst.weekday() >= 5:
        return False
    h, m = tst.hour, tst.minute
    return (9, 0) <= (h, m) <= (13, 30)


def _list_in_db_sids(db_path: str) -> list[str]:
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(db_path)
    syms = storage.list_symbols()
    return [s.replace("daily_price/", "") for s in syms if s.startswith("daily_price/")]


def _list_universe_sids(db_path: str) -> list[str]:
    """從 _universe 表撈所有股票（含 ETF），按代號排序"""
    import sqlite3
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT stock_id FROM _universe WHERE stock_id GLOB '[0-9]*' ORDER BY stock_id"
        ).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def _sync_one(sid: str, storage, provider, checker, start: str, end: str) -> bool:
    """抓一支股票 [start, end]，回傳成功與否"""
    try:
        df = provider.fetch_daily(sid, start, end)
        result = checker.run_all_checks(df, sid)
        if not result.passed.empty:
            storage.upsert(f"daily_price/{sid}", result.passed)
            return True
    except Exception as e:
        logger.debug(f"[auto_sync] {sid} 失敗: {e}")
    return False


def _sync_once(db_path: str, default_universe: list[str]) -> None:
    """執行一輪 Phase A + Phase B"""
    from twquant.data.storage import SQLiteStorage
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.data.sanity import TWSEDataSanityChecker
    from twquant.dashboard.config import get_finmind_token

    storage = SQLiteStorage(db_path)
    provider = FinMindProvider(token=get_finmind_token() or "")
    checker = TWSEDataSanityChecker()
    today = date.today().isoformat()

    in_market = _is_market_hours()
    batch = _BATCH_MARKET_HOURS if in_market else _BATCH_OFF_HOURS

    in_db = _list_in_db_sids(db_path)
    universe = _list_universe_sids(db_path) or default_universe
    missing = [s for s in universe if s not in set(in_db)]

    # 預估本輪總量
    phase_a_targets = []
    for sid in in_db:
        hwm = storage.get_hwm(f"daily_price/{sid}")
        if hwm and hwm.isoformat() < today:
            phase_a_targets.append(sid)
    phase_a_batch = phase_a_targets[:batch]
    phase_b_batch = missing[:batch]
    total = len(phase_a_batch) + len(phase_b_batch)

    if total == 0:
        return

    scope = f"自動 (盤{'中' if in_market else '後'} batch={batch}): A={len(phase_a_batch)} B={len(phase_b_batch)}"
    job_id = create_job("auto", scope, "varies", total, db_path)

    done = failed = 0
    try:
        for sid in phase_a_batch:
            if is_cancelled(job_id, db_path):
                break
            hwm = storage.get_hwm(f"daily_price/{sid}")
            start = (hwm + timedelta(days=1)).isoformat() if hwm else "2015-01-01"
            update_progress(job_id, done=done, failed=failed, current_sid=sid, db_path=db_path)
            ok = _sync_one(sid, storage, provider, checker, start, today)
            if ok: done += 1
            else: failed += 1
            time.sleep(_SLEEP_PER_REQ)

        for sid in phase_b_batch:
            if is_cancelled(job_id, db_path):
                break
            update_progress(job_id, done=done, failed=failed, current_sid=sid, db_path=db_path)
            ok = _sync_one(sid, storage, provider, checker, "2015-01-01", today)
            if ok: done += 1
            else: failed += 1
            time.sleep(_SLEEP_PER_REQ)

        update_progress(job_id, done=done, failed=failed, current_sid=None, db_path=db_path)
        finish_job(job_id, "done", db_path=db_path)
        logger.info(f"[auto_sync] 完成輪：{done}/{total}（失敗 {failed}）")
    except Exception as e:
        finish_job(job_id, "failed", error_msg=str(e)[:500], db_path=db_path)
        logger.warning(f"[auto_sync] 輪異常: {e}")


def run_manual_job(db_path: str, target_sids: list[str], start_date: str,
                   scope_desc: str = "manual", job_type: str = "manual") -> int:
    """背景啟動指定範圍抓取，回傳 job_id（可用於 UI 追蹤）

    用於 onboarding 啟動與頁 01「手動補抓」按鈕。
    """
    from twquant.data.storage import SQLiteStorage
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.data.sanity import TWSEDataSanityChecker
    from twquant.dashboard.config import get_finmind_token

    storage = SQLiteStorage(db_path)
    provider = FinMindProvider(token=get_finmind_token() or "")
    checker = TWSEDataSanityChecker()
    today = date.today().isoformat()
    total = len(target_sids)
    job_id = create_job(job_type, scope_desc, start_date, total, db_path)

    def _runner():
        done = failed = 0
        try:
            for sid in target_sids:
                if is_cancelled(job_id, db_path):
                    return  # 已被取消
                hwm = storage.get_hwm(f"daily_price/{sid}")
                # 已近 3 天內 → 跳過
                if hwm and (date.today() - hwm).days <= 3:
                    done += 1
                    update_progress(job_id, done=done, failed=failed,
                                    current_sid=sid, db_path=db_path)
                    continue
                update_progress(job_id, done=done, failed=failed,
                                current_sid=sid, db_path=db_path)
                start = start_date
                if hwm:
                    s2 = (hwm + timedelta(days=1)).isoformat()
                    if s2 > start_date:
                        start = s2
                ok = _sync_one(sid, storage, provider, checker, start, today)
                if ok: done += 1
                else: failed += 1
                time.sleep(_SLEEP_PER_REQ)
            update_progress(job_id, done=done, failed=failed,
                            current_sid=None, db_path=db_path)
            finish_job(job_id, "done", db_path=db_path)
        except Exception as e:
            finish_job(job_id, "failed", error_msg=str(e)[:500], db_path=db_path)

    threading.Thread(target=_runner, daemon=True, name=f"twquant-job-{job_id}").start()
    return job_id


def _worker(db_path: str, default_universe: list[str]) -> None:
    while True:
        try:
            _sync_once(db_path, default_universe)
        except Exception as e:
            logger.warning(f"[auto_sync] 輪外異常: {e}")
        interval = _INTERVAL_MARKET if _is_market_hours() else _INTERVAL_OFF
        time.sleep(interval)


def ensure_running(db_path: str, default_universe: list[str]) -> None:
    """確保背景同步執行緒已啟動（冪等）"""
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _thread = threading.Thread(
                target=_worker, args=(db_path, default_universe),
                daemon=True, name="twquant-auto-sync",
            )
            _thread.start()
            logger.info("[auto_sync] 智能背景同步啟動（盤中 5min / 盤後 60min）")


def last_sync_info(db_path: str, stock_ids: list[str] | None = None) -> dict:
    """同步狀態摘要（給 sidebar widget 用）"""
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(db_path)
    all_syms = storage.list_symbols()
    in_db = [s.replace("daily_price/", "") for s in all_syms if s.startswith("daily_price/")]
    today = date.today()
    up_to_date = 0
    for sid in in_db:
        hwm = storage.get_hwm(f"daily_price/{sid}")
        if hwm and (today - hwm).days <= 3:
            up_to_date += 1
    return {
        "total": len(in_db),
        "up_to_date": up_to_date,
        "is_market_hours": _is_market_hours(),
        "thread_alive": _thread is not None and _thread.is_alive(),
    }
