"""每日選股訂閱與結果持久化 — 與 alerts.py 共用同一個 data/twquant.db"""

from __future__ import annotations
import sqlite3
from datetime import datetime
from typing import Iterable

import pandas as pd


DB_PATH = "data/twquant.db"


def _conn(db_path: str = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(db_path)


def init_schema(db_path: str = DB_PATH) -> None:
    with _conn(db_path) as con:
        con.executescript("""
CREATE TABLE IF NOT EXISTS scan_subscriptions (
    strategy_key TEXT PRIMARY KEY,
    enabled      INTEGER NOT NULL DEFAULT 1,
    updated_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_scans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_date    TEXT NOT NULL,
    strategy_key TEXT NOT NULL,
    stock_id     TEXT NOT NULL,
    close        REAL,
    ma60_dist    REAL,
    rsi          REAL,
    vol_ratio    REAL,
    created_at   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_daily_scans_date ON daily_scans(scan_date);
""")


def list_subscriptions(db_path: str = DB_PATH) -> list[dict]:
    init_schema(db_path)
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT strategy_key, enabled, updated_at FROM scan_subscriptions "
            "ORDER BY strategy_key"
        ).fetchall()
    return [{"strategy_key": r[0], "enabled": bool(r[1]), "updated_at": r[2]} for r in rows]


def set_subscription(strategy_key: str, enabled: bool, db_path: str = DB_PATH) -> None:
    init_schema(db_path)
    with _conn(db_path) as con:
        con.execute(
            "INSERT INTO scan_subscriptions (strategy_key, enabled, updated_at) "
            "VALUES (?, ?, ?) "
            "ON CONFLICT(strategy_key) DO UPDATE SET enabled=excluded.enabled, "
            "updated_at=excluded.updated_at",
            (strategy_key, 1 if enabled else 0, datetime.now().isoformat()),
        )


def set_subscriptions_bulk(
    enabled_keys: Iterable[str], all_keys: Iterable[str], db_path: str = DB_PATH
) -> None:
    """一次寫入：enabled_keys 設為 1，其餘 all_keys 設為 0。"""
    init_schema(db_path)
    enabled_set = set(enabled_keys)
    now = datetime.now().isoformat()
    with _conn(db_path) as con:
        for key in all_keys:
            con.execute(
                "INSERT INTO scan_subscriptions (strategy_key, enabled, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(strategy_key) DO UPDATE SET enabled=excluded.enabled, "
                "updated_at=excluded.updated_at",
                (key, 1 if key in enabled_set else 0, now),
            )


def save_scan_results(scan_date: str, df: pd.DataFrame, db_path: str = DB_PATH) -> int:
    """寫入掃描結果。同 scan_date+strategy_key 先 DELETE 再 INSERT（upsert）。

    df columns expected: 代號, 策略, 收盤價, 距MA60%, RSI, 量比
    """
    init_schema(db_path)
    if df is None or df.empty:
        return 0
    now = datetime.now().isoformat()
    strategies = df["策略"].unique().tolist()
    with _conn(db_path) as con:
        for key in strategies:
            con.execute(
                "DELETE FROM daily_scans WHERE scan_date=? AND strategy_key=?",
                (scan_date, key),
            )
        rows_inserted = 0
        for _, row in df.iterrows():
            con.execute(
                "INSERT INTO daily_scans "
                "(scan_date, strategy_key, stock_id, close, ma60_dist, rsi, vol_ratio, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    scan_date,
                    row["策略"],
                    row["代號"],
                    float(row["收盤價"]) if row["收盤價"] is not None else None,
                    float(row["距MA60%"]) if row["距MA60%"] is not None else None,
                    float(row["RSI"]) if row["RSI"] is not None else None,
                    float(row["量比"]) if row["量比"] is not None else None,
                    now,
                ),
            )
            rows_inserted += 1
    return rows_inserted


def get_scan(scan_date: str | None = None, db_path: str = DB_PATH) -> pd.DataFrame:
    """讀取指定日期的選股結果。scan_date=None 取最近一日。"""
    init_schema(db_path)
    with _conn(db_path) as con:
        if scan_date is None:
            row = con.execute(
                "SELECT MAX(scan_date) FROM daily_scans"
            ).fetchone()
            scan_date = row[0] if row and row[0] else None
        if scan_date is None:
            return pd.DataFrame(
                columns=["scan_date", "strategy_key", "stock_id",
                         "close", "ma60_dist", "rsi", "vol_ratio"]
            )
        rows = con.execute(
            "SELECT scan_date, strategy_key, stock_id, close, ma60_dist, rsi, vol_ratio "
            "FROM daily_scans WHERE scan_date=? ORDER BY strategy_key, stock_id",
            (scan_date,),
        ).fetchall()
    return pd.DataFrame(
        rows,
        columns=["scan_date", "strategy_key", "stock_id",
                 "close", "ma60_dist", "rsi", "vol_ratio"],
    )


def available_dates(limit: int = 30, db_path: str = DB_PATH) -> list[str]:
    init_schema(db_path)
    with _conn(db_path) as con:
        rows = con.execute(
            "SELECT DISTINCT scan_date FROM daily_scans "
            "ORDER BY scan_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r[0] for r in rows]
