"""告警規則資料層 — 使用同一個 data/twquant.db"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime


DB_PATH = "data/twquant.db"


def _conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_schema(db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.executescript("""
CREATE TABLE IF NOT EXISTS alert_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    stock_id TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    params_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alert_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_id INTEGER NOT NULL,
    stock_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    message TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (rule_id) REFERENCES alert_rules(id)
);
""")


def add_rule(name: str, stock_id: str, rule_type: str, params: dict,
             db_path: str = DB_PATH) -> int:
    init_schema(db_path)
    with _conn(db_path) as con:
        cur = con.execute(
            "INSERT INTO alert_rules (name, stock_id, rule_type, params_json, enabled, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (name, stock_id, rule_type, json.dumps(params), datetime.now().isoformat()),
        )
        return cur.lastrowid


def list_rules(db_path: str = DB_PATH) -> list[dict]:
    init_schema(db_path)
    with _conn(db_path) as con:
        rows = con.execute("SELECT id, name, stock_id, rule_type, params_json, enabled, created_at "
                           "FROM alert_rules ORDER BY created_at DESC").fetchall()
    return [
        {"id": r[0], "name": r[1], "stock_id": r[2], "rule_type": r[3],
         "params": json.loads(r[4]), "enabled": bool(r[5]), "created_at": r[6]}
        for r in rows
    ]


def delete_rule(rule_id: int, db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("DELETE FROM alert_rules WHERE id=?", (rule_id,))
        con.execute("DELETE FROM alert_logs WHERE rule_id=?", (rule_id,))


def toggle_rule(rule_id: int, db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("UPDATE alert_rules SET enabled = 1 - enabled WHERE id=?", (rule_id,))


def log_trigger(rule_id: int, stock_id: str, message: str, db_path: str = DB_PATH) -> None:
    init_schema(db_path)
    with _conn(db_path) as con:
        con.execute(
            "INSERT INTO alert_logs (rule_id, stock_id, triggered_at, message, acknowledged) "
            "VALUES (?, ?, ?, ?, 0)",
            (rule_id, stock_id, datetime.now().isoformat(), message),
        )


def list_logs(limit: int = 50, db_path: str = DB_PATH) -> list[dict]:
    init_schema(db_path)
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT l.id, l.rule_id, r.name, l.stock_id, l.triggered_at, l.message, l.acknowledged "
            "FROM alert_logs l JOIN alert_rules r ON l.rule_id=r.id "
            "ORDER BY l.triggered_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [
        {"id": r[0], "rule_id": r[1], "rule_name": r[2], "stock_id": r[3],
         "triggered_at": r[4], "message": r[5], "acknowledged": bool(r[6])}
        for r in rows
    ]


def ack_log(log_id: int, db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("UPDATE alert_logs SET acknowledged=1 WHERE id=?", (log_id,))


def ack_all(db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.execute("UPDATE alert_logs SET acknowledged=1 WHERE acknowledged=0")


def unread_count(db_path: str = DB_PATH) -> int:
    init_schema(db_path)
    with _conn(db_path) as con:
        row = con.execute("SELECT COUNT(*) FROM alert_logs WHERE acknowledged=0").fetchone()
    return row[0] if row else 0
