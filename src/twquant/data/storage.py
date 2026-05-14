"""數據儲存層：ArcticDB（首選）和 SQLite（備選）統一介面"""

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

import pandas as pd


class DataStorage(ABC):
    """儲存層統一抽象介面"""

    @abstractmethod
    def upsert(self, symbol: str, df: pd.DataFrame, date_column: str = "date") -> None:
        """冪等寫入：以 date_column 為鍵，存在則覆蓋，不存在則插入"""

    @abstractmethod
    def load(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        """讀取數據，支援日期範圍篩選。回傳空 DataFrame 若 symbol 不存在"""

    @abstractmethod
    def get_hwm(self, symbol: str) -> date | None:
        """取得 symbol 最後一筆資料的日期（高水位標記）"""

    @abstractmethod
    def get_dates(self, symbol: str) -> list[date]:
        """取得 symbol 在資料庫中的所有日期列表（用於闕漏偵測）"""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """列出資料庫中所有已儲存的 symbol"""


class ArcticDBStorage(DataStorage):
    """ArcticDB 儲存適配器（正式環境首選）"""

    def __init__(self, uri: str = "lmdb://data/arcticdb"):
        import arcticdb as adb

        self._ac = adb.Arctic(uri)
        self._lib = self._ac.get_library("twquant", create_if_missing=True)

    def upsert(self, symbol: str, df: pd.DataFrame, date_column: str = "date") -> None:
        df = df.copy()
        df[date_column] = pd.to_datetime(df[date_column])
        df = df.set_index(date_column).sort_index()
        if self._lib.has_symbol(symbol):
            self._lib.update(symbol, df, upsert=True)
        else:
            self._lib.write(symbol, df)

    def load(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        if not self._lib.has_symbol(symbol):
            return pd.DataFrame()
        date_range = None
        if start_date or end_date:
            import arcticdb as adb

            _s = pd.Timestamp(start_date) if start_date else None
            _e = pd.Timestamp(end_date) if end_date else None
            date_range = adb.QueryBuilder().date_range(_s, _e) if False else None
            # ArcticDB QueryBuilder 使用 read with date_range 參數
            _s = pd.Timestamp(start_date) if start_date else pd.Timestamp("1970-01-01")
            _e = pd.Timestamp(end_date) if end_date else pd.Timestamp("2099-12-31")
            df = self._lib.read(symbol, date_range=(_s, _e)).data
        else:
            df = self._lib.read(symbol).data
        df = df.reset_index()
        df["date"] = pd.to_datetime(df["date"]).dt.date
        return df

    def get_hwm(self, symbol: str) -> date | None:
        if not self._lib.has_symbol(symbol):
            return None
        df = self._lib.read(symbol).data
        if df.empty:
            return None
        return df.index.max().date()

    def get_dates(self, symbol: str) -> list[date]:
        if not self._lib.has_symbol(symbol):
            return []
        df = self._lib.read(symbol).data
        return [ts.date() for ts in df.index]

    def list_symbols(self) -> list[str]:
        return self._lib.list_symbols()


class SQLiteStorage(DataStorage):
    """SQLite 儲存適配器（開發/測試備選）"""

    def __init__(self, db_path: str = "data/twquant.db"):
        import sqlite3

        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS _symbols (name TEXT PRIMARY KEY)"
        )
        self._conn.commit()

    def _table(self, symbol: str) -> str:
        return f"data_{symbol.replace('/', '_').replace('-', '_')}"

    def upsert(self, symbol: str, df: pd.DataFrame, date_column: str = "date") -> None:
        if df is None or df.empty:
            return
        df = df.copy()
        df[date_column] = df[date_column].astype(str)
        table = self._table(symbol)
        min_date = df[date_column].min()
        max_date = df[date_column].max()
        try:
            # 刪除重疊日期範圍後 append，保留範圍外的歷史資料
            self._conn.execute(
                f"DELETE FROM {table} WHERE {date_column} >= ? AND {date_column} <= ?",
                (min_date, max_date),
            )
            df.to_sql(table, self._conn, if_exists="append", index=False)
        except Exception:
            # 表不存在 → 直接建立
            df.to_sql(table, self._conn, if_exists="replace", index=False)
        self._conn.execute(
            "INSERT OR IGNORE INTO _symbols VALUES (?)", (symbol,)
        )
        self._conn.commit()

    def load(
        self,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> pd.DataFrame:
        table = self._table(symbol)
        try:
            query = f"SELECT * FROM {table}"
            params: list = []
            clauses = []
            if start_date:
                clauses.append("date >= ?")
                params.append(start_date)
            if end_date:
                clauses.append("date <= ?")
                params.append(end_date)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            df = pd.read_sql(query, self._conn, params=params)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"]).dt.date
            return df
        except Exception:
            return pd.DataFrame()

    def get_hwm(self, symbol: str) -> date | None:
        table = self._table(symbol)
        try:
            row = self._conn.execute(
                f"SELECT MAX(date) FROM {table}"
            ).fetchone()
            if row and row[0]:
                return pd.to_datetime(row[0]).date()
        except Exception:
            pass
        return None

    def get_dates(self, symbol: str) -> list[date]:
        table = self._table(symbol)
        try:
            rows = self._conn.execute(
                f"SELECT DISTINCT date FROM {table} ORDER BY date"
            ).fetchall()
            return [pd.to_datetime(r[0]).date() for r in rows]
        except Exception:
            return []

    def list_symbols(self) -> list[str]:
        rows = self._conn.execute("SELECT name FROM _symbols").fetchall()
        return [r[0] for r in rows]

    def close(self) -> None:
        self._conn.close()
