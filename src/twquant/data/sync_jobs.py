"""資料抓取任務表 CRUD — 統一管理 onboarding / manual / auto sync 任務狀態"""

import sqlite3
from datetime import datetime

DB_PATH = "data/twquant.db"


def _conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _sync_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_type TEXT NOT NULL,
            status TEXT NOT NULL,
            scope_desc TEXT,
            start_date TEXT,
            total INTEGER DEFAULT 0,
            done INTEGER DEFAULT 0,
            failed INTEGER DEFAULT 0,
            current_sid TEXT,
            started_at TEXT,
            finished_at TEXT,
            error_msg TEXT
        )
    """)
    conn.commit()
    return conn


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_job(job_type: str, scope_desc: str, start_date: str,
               total: int, db_path: str = DB_PATH) -> int:
    """建立任務並標記 running，回傳 job_id"""
    conn = _conn(db_path)
    cur = conn.execute(
        "INSERT INTO _sync_jobs (job_type, status, scope_desc, start_date, total, started_at) "
        "VALUES (?, 'running', ?, ?, ?, ?)",
        (job_type, scope_desc, start_date, int(total), _now()),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def update_progress(job_id: int, done: int | None = None,
                    failed: int | None = None, current_sid: str | None = None,
                    db_path: str = DB_PATH) -> None:
    conn = _conn(db_path)
    sets, vals = [], []
    if done is not None:
        sets.append("done = ?"); vals.append(int(done))
    if failed is not None:
        sets.append("failed = ?"); vals.append(int(failed))
    if current_sid is not None:
        sets.append("current_sid = ?"); vals.append(current_sid)
    if sets:
        vals.append(job_id)
        conn.execute(f"UPDATE _sync_jobs SET {', '.join(sets)} WHERE id = ?", vals)
        conn.commit()
    conn.close()


def finish_job(job_id: int, status: str = "done",
               error_msg: str | None = None, db_path: str = DB_PATH) -> None:
    conn = _conn(db_path)
    conn.execute(
        "UPDATE _sync_jobs SET status = ?, finished_at = ?, error_msg = ? WHERE id = ?",
        (status, _now(), error_msg, job_id),
    )
    conn.commit()
    conn.close()


def latest_running_job(db_path: str = DB_PATH) -> dict | None:
    """回傳目前 running 中的任務（若有），dict 形式"""
    conn = _conn(db_path)
    row = conn.execute(
        "SELECT id, job_type, status, scope_desc, start_date, total, done, failed, "
        "current_sid, started_at FROM _sync_jobs "
        "WHERE status = 'running' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    keys = ["id", "job_type", "status", "scope_desc", "start_date",
            "total", "done", "failed", "current_sid", "started_at"]
    return dict(zip(keys, row))


def recent_jobs(limit: int = 10, db_path: str = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT id, job_type, status, scope_desc, start_date, total, done, failed, "
        "started_at, finished_at, error_msg FROM _sync_jobs "
        "ORDER BY id DESC LIMIT ?", (int(limit),),
    ).fetchall()
    conn.close()
    keys = ["id", "job_type", "status", "scope_desc", "start_date",
            "total", "done", "failed", "started_at", "finished_at", "error_msg"]
    return [dict(zip(keys, r)) for r in rows]


def cancel_running_jobs(db_path: str = DB_PATH) -> int:
    """把所有 running 任務標為 cancelled，回傳影響筆數（由背景 thread 自行檢查並退出）"""
    conn = _conn(db_path)
    cur = conn.execute(
        "UPDATE _sync_jobs SET status = 'cancelled', finished_at = ? WHERE status = 'running'",
        (_now(),),
    )
    conn.commit()
    n = cur.rowcount
    conn.close()
    return n


def is_cancelled(job_id: int, db_path: str = DB_PATH) -> bool:
    """背景 thread 在每筆抓取前可呼叫此函式檢查是否被取消"""
    conn = _conn(db_path)
    row = conn.execute("SELECT status FROM _sync_jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()
    return bool(row and row[0] == "cancelled")
