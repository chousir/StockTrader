"""背景同步排程：每個交易日晚上自動增量同步 + 每日掃描

架構：
  - 一個長駐執行緒每分鐘檢查是否到達 nightly_time，到了就執行 _run_nightly()
  - _run_nightly()：增量同步已入庫股票 → 每日選股 → 告警評估（全同步阻塞，不重疊）
  - run_manual_job()：UI 觸發（onboarding / 手動補抓），回傳 job_id 供進度條用
  - run_catchup_job()：補齊全部 _universe 股票到今日（長時間離線後使用）
  - _JOB_LOCK 確保同一時間只有一個同步 job 在跑

移除：盤中抓取（FinMind 日K盤中無當天資料，徒耗 API 額度）
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
_JOB_LOCK = threading.Lock()

_SLEEP_PER_REQ = 0.3  # FinMind 限速保護（provider 本身有 600/hr limiter，此為額外緩衝）


# ─── 工具 ──────────────────────────────────────────────────────────────────

def _is_trading_day() -> bool:
    """週一至週五視為交易日（不排除台灣國定假日）"""
    return datetime.now(timezone(timedelta(hours=8))).weekday() < 5


def _list_in_db_sids(db_path: str) -> list[str]:
    from twquant.data.storage import SQLiteStorage
    syms = SQLiteStorage(db_path).list_symbols()
    return [s.replace("daily_price/", "") for s in syms if s.startswith("daily_price/")]


def _list_universe_sids(db_path: str) -> list[str]:
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


def _ensure_universe(db_path: str) -> None:
    """懶載 _universe 表（7 天刷新一次，失敗不影響啟動）"""
    from twquant.data import sync_config
    if not sync_config.universe_needs_refresh():
        return
    try:
        from twquant.data.universe import upsert_universe
        n = upsert_universe(db_path)
        if n > 0:
            sync_config.mark_universe_updated()
            logger.info(f"[auto_sync] _universe 已更新 {n} 筆")
    except Exception as e:
        logger.debug(f"[auto_sync] _universe 更新失敗（非致命）: {e}")


def _sync_one(sid: str, storage, provider, checker, start: str, end: str) -> bool:
    try:
        df = provider.fetch_daily(sid, start, end)
        result = checker.run_all_checks(df, sid)
        if not result.passed.empty:
            storage.upsert(f"daily_price/{sid}", result.passed)
            return True
    except Exception as e:
        logger.debug(f"[auto_sync] {sid} 失敗: {e}")
    return False


# ─── 夜間排程任務（阻塞，在獨立 thread 執行） ─────────────────────────────

def _run_nightly(db_path: str) -> None:
    from twquant.data.storage import SQLiteStorage
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.data.sanity import TWSEDataSanityChecker
    from twquant.dashboard.config import get_finmind_token
    from twquant.data import sync_config

    in_db = _list_in_db_sids(db_path)
    if not in_db:
        logger.info("[auto_sync] DB 無資料，略過夜間同步")
        return

    history_start = sync_config.get_history_start()
    today = date.today().isoformat()
    scope = f"夜間增量 {len(in_db)} 支"
    job_id = create_job("nightly", scope, history_start, len(in_db), db_path)

    if not _JOB_LOCK.acquire(blocking=True, timeout=30):
        finish_job(job_id, "failed", error_msg="另一個同步任務佔用鎖", db_path=db_path)
        return

    storage = SQLiteStorage(db_path)
    provider = FinMindProvider(token=get_finmind_token() or "")
    checker = TWSEDataSanityChecker()
    done = failed = 0
    try:
        logger.info(f"[auto_sync] 夜間增量同步開始：{len(in_db)} 支")
        for sid in in_db:
            if is_cancelled(job_id, db_path):
                break
            hwm = storage.get_hwm(f"daily_price/{sid}")
            if hwm and (date.today() - hwm).days <= 3:
                done += 1
                update_progress(job_id, done=done, failed=failed,
                                current_sid=sid, db_path=db_path)
                continue
            update_progress(job_id, done=done, failed=failed,
                            current_sid=sid, db_path=db_path)
            start = history_start
            if hwm:
                hwm_next = (hwm + timedelta(days=1)).isoformat()
                if hwm_next > start:
                    start = hwm_next
            if start > today:
                done += 1
                continue
            ok = _sync_one(sid, storage, provider, checker, start, today)
            if ok:
                done += 1
            else:
                failed += 1
            time.sleep(_SLEEP_PER_REQ)

        finish_job(job_id, "done", db_path=db_path)
        logger.info(f"[auto_sync] 夜間同步完成 {done}/{len(in_db)}（失敗 {failed}）")
    except Exception as e:
        finish_job(job_id, "failed", error_msg=str(e)[:500], db_path=db_path)
        logger.error(f"[auto_sync] 夜間同步異常: {e}")
    finally:
        _JOB_LOCK.release()

    # 掃描 + 告警（sync 完後接著跑）
    cfg = sync_config.load()
    if not cfg.get("run_scan_after_sync", True):
        return
    try:
        from twquant.data.daily_scan_worker import run_daily_scan
        from twquant.data.alert_worker import evaluate_all_rules
        stats = run_daily_scan()
        logger.info(f"[auto_sync] 每日選股完成 {stats}")
        n = evaluate_all_rules()
        logger.info(f"[auto_sync] 告警評估完成 觸發 {n} 筆")
    except Exception as e:
        logger.warning(f"[auto_sync] 掃描/告警失敗（非致命）: {e}")


# ─── UI 觸發任務（fire-and-forget，回傳 job_id） ───────────────────────────

def run_manual_job(
    db_path: str,
    target_sids: list[str],
    start_date: str,
    scope_desc: str = "manual",
    job_type: str = "manual",
) -> int:
    """背景啟動指定範圍抓取，回傳 job_id 供進度條追蹤"""
    from twquant.data.storage import SQLiteStorage
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.data.sanity import TWSEDataSanityChecker
    from twquant.dashboard.config import get_finmind_token
    from twquant.data.sync_config import get_history_start

    storage = SQLiteStorage(db_path)
    provider = FinMindProvider(token=get_finmind_token() or "")
    checker = TWSEDataSanityChecker()
    history_start = get_history_start()
    today = date.today().isoformat()
    job_id = create_job(job_type, scope_desc, start_date, len(target_sids), db_path)

    def _runner():
        if not _JOB_LOCK.acquire(blocking=True, timeout=10):
            finish_job(job_id, "failed", error_msg="另一個同步任務正在執行，請稍後再試",
                       db_path=db_path)
            return
        done = failed = 0
        try:
            for sid in target_sids:
                if is_cancelled(job_id, db_path):
                    return
                hwm = storage.get_hwm(f"daily_price/{sid}")
                if hwm and (date.today() - hwm).days <= 3:
                    done += 1
                    update_progress(job_id, done=done, failed=failed,
                                    current_sid=sid, db_path=db_path)
                    continue
                update_progress(job_id, done=done, failed=failed,
                                current_sid=sid, db_path=db_path)
                # 起始日：取 max(history_start, start_date, hwm+1)
                effective_start = max(history_start, start_date)
                if hwm:
                    hwm_next = (hwm + timedelta(days=1)).isoformat()
                    if hwm_next > effective_start:
                        effective_start = hwm_next
                if effective_start > today:
                    done += 1
                    continue
                ok = _sync_one(sid, storage, provider, checker, effective_start, today)
                if ok:
                    done += 1
                else:
                    failed += 1
                time.sleep(_SLEEP_PER_REQ)
            update_progress(job_id, done=done, failed=failed,
                            current_sid=None, db_path=db_path)
            finish_job(job_id, "done", db_path=db_path)
        except Exception as e:
            finish_job(job_id, "failed", error_msg=str(e)[:500], db_path=db_path)
        finally:
            _JOB_LOCK.release()

    threading.Thread(target=_runner, daemon=True,
                     name=f"twquant-job-{job_id}").start()
    return job_id


def run_catchup_job(db_path: str) -> int:
    """補齊全部到今日：_universe 所有股票從 HWM 補到今天（長時間離線後使用）"""
    from twquant.data.sync_config import get_history_start
    sids = _list_universe_sids(db_path) or _list_in_db_sids(db_path)
    if not sids:
        sids = []
    history_start = get_history_start()
    return run_manual_job(
        db_path, sids, history_start,
        scope_desc=f"補齊全部 {len(sids)} 支",
        job_type="catchup",
    )


# ─── 排程執行緒 ────────────────────────────────────────────────────────────

def _worker(db_path: str) -> None:
    """每分鐘檢查是否到達 nightly_time；到了且是交易日就啟動夜間任務"""
    from twquant.data import sync_config
    last_run_date: date | None = None
    while True:
        try:
            now = datetime.now(timezone(timedelta(hours=8)))
            target_h, target_m = sync_config.get_nightly_time()
            if (
                sync_config.is_enabled()
                and _is_trading_day()
                and now.hour == target_h
                and now.minute == target_m
                and (last_run_date is None or last_run_date < now.date())
            ):
                last_run_date = now.date()
                threading.Thread(
                    target=_run_nightly, args=(db_path,),
                    daemon=True, name="twquant-nightly",
                ).start()
        except Exception as e:
            logger.warning(f"[auto_sync] 排程輪外異常: {e}")
        time.sleep(60)


def ensure_running(db_path: str, default_universe: list[str] | None = None) -> None:
    """確保背景排程執行緒已啟動（冪等）。default_universe 保留供相容，不再使用。"""
    global _thread
    with _lock:
        if _thread is None or not _thread.is_alive():
            _ensure_universe(db_path)
            _thread = threading.Thread(
                target=_worker, args=(db_path,),
                daemon=True, name="twquant-nightly-scheduler",
            )
            _thread.start()
            logger.info("[auto_sync] 夜間排程啟動（每交易日 nightly_time 自動增量同步）")


# ─── UI 狀態查詢 ───────────────────────────────────────────────────────────

def last_sync_info(db_path: str, stock_ids: list[str] | None = None) -> dict:
    """同步狀態摘要（sidebar widget 與頁 01 使用）"""
    from twquant.data.storage import SQLiteStorage
    from twquant.data import sync_config
    storage = SQLiteStorage(db_path)
    in_db = [s.replace("daily_price/", "") for s in storage.list_symbols()
             if s.startswith("daily_price/")]
    today = date.today()
    up_to_date = sum(
        1 for sid in in_db
        if (hwm := storage.get_hwm(f"daily_price/{sid}")) and (today - hwm).days <= 3
    )
    h, m = sync_config.get_nightly_time()
    return {
        "total": len(in_db),
        "up_to_date": up_to_date,
        "auto_sync_enabled": sync_config.is_enabled(),
        "nightly_time": f"{h:02d}:{m:02d}",
        "thread_alive": _thread is not None and _thread.is_alive(),
    }
