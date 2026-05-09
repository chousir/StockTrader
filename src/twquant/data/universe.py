"""台股股票宇宙管理：產業分類、主要標的清單、DB 元資料儲存"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from loguru import logger

DB_PATH = "data/twquant.db"

# ── 分析師預設股票宇宙（依產業分類，涵蓋主要板塊） ───────────────────────
ANALYST_UNIVERSE: dict[str, list[tuple[str, str]]] = {
    "半導體": [
        ("2330", "台積電"), ("2454", "聯發科"), ("2303", "聯電"),
        ("2308", "台達電"), ("3034", "聯詠"), ("2379", "瑞昱"),
        ("3711", "日月光投控"), ("6239", "力成"), ("2449", "京元電子"), ("3006", "晶豪科"),
    ],
    "電子組件": [
        ("2317", "鴻海"), ("2382", "廣達"), ("2356", "英業達"),
        ("3231", "緯創"), ("6669", "緯穎"), ("2301", "光寶科"),
        ("2308", "台達電"), ("2327", "國巨"),
    ],
    "光電/精密": [
        ("3008", "大立光"), ("2448", "晶電"), ("3037", "欣興"),
    ],
    "金融保險": [
        ("2882", "國泰金"), ("2881", "富邦金"), ("2886", "兆豐金"),
        ("2891", "中信金"), ("2884", "玉山金"), ("2885", "元大金"),
        ("2892", "第一金"), ("5880", "合庫金"),
    ],
    "航運": [
        ("2603", "長榮"), ("2609", "陽明"), ("2615", "萬海"),
        ("2610", "華航"), ("2618", "長榮航"),
    ],
    "電信": [
        ("2412", "中華電"), ("3045", "台灣大"), ("4904", "遠傳"),
    ],
    "鋼鐵/材料": [
        ("2002", "中鋼"), ("2006", "東和鋼鐵"), ("1301", "台塑"),
        ("1303", "南亞"), ("1326", "台化"),
    ],
    "食品/消費": [
        ("1216", "統一"), ("2912", "統一超"), ("1101", "台泥"),
    ],
    "ETF": [
        ("0050", "元大台50"), ("0056", "元大高息"), ("00878", "國泰永續"),
        ("00929", "復華台灣科技優息"), ("006208", "富邦台50"),
    ],
}

# 扁平化 SID → (name, sector) mapping
_SID_META: dict[str, tuple[str, str]] = {}
for _sector, _stocks in ANALYST_UNIVERSE.items():
    for _sid, _name in _stocks:
        _SID_META[_sid] = (_name, _sector)

ALL_SIDS: list[str] = list(_SID_META.keys())


def get_name(sid: str) -> str:
    return _SID_META.get(sid, (sid, ""))[0]


def get_sector(sid: str) -> str:
    return _SID_META.get(sid, ("", "未分類"))[1]


def list_sectors() -> list[str]:
    return list(ANALYST_UNIVERSE.keys())


def list_by_sector(sector: str) -> list[tuple[str, str]]:
    return ANALYST_UNIVERSE.get(sector, [])


# ── DB 元資料表：儲存 FinMind 全市場股票名稱與產業 ─────────────────────────

def init_universe_table(db_path: str = DB_PATH) -> None:
    """建立 _universe 元資料表（已存在則 skip）"""
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _universe (
            stock_id   TEXT PRIMARY KEY,
            stock_name TEXT,
            sector     TEXT,
            market     TEXT
        )
    """)
    conn.commit()
    conn.close()


def upsert_universe(db_path: str = DB_PATH) -> int:
    """
    從 FinMind 拉取全市場股票資訊並寫入 _universe。
    回傳寫入筆數。
    """
    from FinMind.data import DataLoader
    init_universe_table(db_path)
    dl = DataLoader()
    raw = dl.taiwan_stock_info()
    if raw.empty:
        return 0

    records = []
    for _, row in raw.iterrows():
        records.append((
            str(row["stock_id"]).strip(),
            str(row.get("stock_name", "")).strip(),
            str(row.get("industry_category", "")).strip(),
            str(row.get("type", "")).strip(),
        ))

    conn = sqlite3.connect(db_path)
    conn.executemany(
        "INSERT OR REPLACE INTO _universe VALUES (?,?,?,?)",
        records,
    )
    conn.commit()
    conn.close()
    logger.info(f"[universe] 寫入 {len(records)} 支股票元資料")
    return len(records)


def search_universe(
    keyword: str = "",
    sector: str = "",
    db_path: str = DB_PATH,
) -> pd.DataFrame:
    """搜尋股票宇宙（名稱/代號關鍵字 + 產業篩選）"""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("SELECT 1 FROM _universe LIMIT 1")
    except sqlite3.OperationalError:
        conn.close()
        return pd.DataFrame(columns=["stock_id", "stock_name", "sector", "market"])

    conditions, params = [], []
    if keyword:
        conditions.append("(stock_id LIKE ? OR stock_name LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    if sector:
        conditions.append("sector = ?")
        params.append(sector)

    query = "SELECT stock_id, stock_name, sector, market FROM _universe"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY stock_id"

    df = pd.read_sql(query, conn, params=params)
    conn.close()
    return df


def get_all_sectors_from_db(db_path: str = DB_PATH) -> list[str]:
    """從 DB 取得所有產業分類（用於下拉選單）"""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT sector FROM _universe WHERE sector != '' ORDER BY sector"
        ).fetchall()
        return [r[0] for r in rows]
    except sqlite3.OperationalError:
        return list(ANALYST_UNIVERSE.keys())
    finally:
        conn.close()
