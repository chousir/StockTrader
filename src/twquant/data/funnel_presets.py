"""頁 03 兩階段選股漏斗條件 preset CRUD（SQLite 後端）"""

import json
import sqlite3
from datetime import datetime

DB_PATH = "data/twquant.db"


def _conn(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _funnel_presets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            conditions_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_preset(name: str, conditions: dict, db_path: str = DB_PATH) -> None:
    """儲存或更新 preset（同名覆蓋）"""
    conn = _conn(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO _funnel_presets (name, conditions_json, created_at) VALUES (?, ?, ?)",
        (name, json.dumps(conditions, ensure_ascii=False), datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()


def list_presets(db_path: str = DB_PATH) -> list[dict]:
    conn = _conn(db_path)
    rows = conn.execute(
        "SELECT name, conditions_json, created_at FROM _funnel_presets ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    return [{"name": r[0], "conditions": json.loads(r[1]), "created_at": r[2]} for r in rows]


def load_preset(name: str, db_path: str = DB_PATH) -> dict | None:
    conn = _conn(db_path)
    row = conn.execute(
        "SELECT conditions_json FROM _funnel_presets WHERE name = ?", (name,)
    ).fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def delete_preset(name: str, db_path: str = DB_PATH) -> None:
    conn = _conn(db_path)
    conn.execute("DELETE FROM _funnel_presets WHERE name = ?", (name,))
    conn.commit()
    conn.close()
