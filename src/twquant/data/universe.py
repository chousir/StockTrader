"""台股股票宇宙管理：產業分類、主要標的清單、DB 元資料儲存"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
from loguru import logger

DB_PATH = "data/twquant.db"

# ── 分析師預設股票宇宙（依產業分類，涵蓋主要板塊） ───────────────────────
# 目標：~120 支，覆蓋台股主要產業，兼顧流動性與代表性
ANALYST_UNIVERSE: dict[str, list[tuple[str, str]]] = {
    "半導體": [
        ("2330", "台積電"), ("2454", "聯發科"), ("2303", "聯電"),
        ("3034", "聯詠"), ("2379", "瑞昱"), ("3711", "日月光投控"),
        ("6239", "力成"), ("2449", "京元電子"), ("3006", "晶豪科"),
        ("2344", "華邦電"), ("2408", "南亞科"), ("3443", "創意電子"),
        ("5274", "信驊科技"), ("8299", "群聯電子"), ("3035", "智原"),
        ("3450", "聯鈞"), ("2337", "旺宏"),
    ],
    "電子組件/ODM": [
        ("2317", "鴻海"), ("2382", "廣達"), ("2356", "英業達"),
        ("3231", "緯創"), ("6669", "緯穎"), ("2301", "光寶科"),
        ("2327", "國巨"), ("2357", "華碩"), ("2353", "宏碁"),
        ("2376", "技嘉"), ("2377", "微星"), ("4938", "和碩"),
        ("2395", "研華科技"), ("2385", "群光電子"), ("2308", "台達電"),
        ("3005", "神基科技"), ("2360", "致茂電子"),
    ],
    "PCB/被動元件": [
        ("3037", "欣興"), ("2367", "燿華"), ("3008", "大立光"),
        ("6271", "同欣電"), ("2049", "上銀"), ("3533", "嘉澤"),
        ("2474", "可成"), ("6415", "矽力-KY"), ("3034", "聯詠"),
    ],
    "面板/光電": [
        ("2409", "友達"), ("3481", "群創"), ("2385", "群光電子"),
        ("3673", "TPK"), ("6244", "茂迪"),
    ],
    "金融保險": [
        ("2882", "國泰金"), ("2881", "富邦金"), ("2886", "兆豐金"),
        ("2891", "中信金"), ("2884", "玉山金"), ("2885", "元大金"),
        ("2892", "第一金"), ("5880", "合庫金"), ("2880", "華南金"),
        ("2887", "台新金"), ("5876", "上海商銀"), ("2883", "開發金"),
        ("2823", "中壽"), ("2812", "台中銀"),
    ],
    "航運/空運": [
        ("2603", "長榮"), ("2609", "陽明"), ("2615", "萬海"),
        ("2610", "華航"), ("2618", "長榮航"), ("2634", "漢翔"),
        ("5608", "四維航"), ("2612", "中航"),
    ],
    "電信/網路": [
        ("2412", "中華電"), ("3045", "台灣大"), ("4904", "遠傳"),
        ("3702", "大聯大"),
    ],
    "原物料/石化/鋼鐵": [
        ("2002", "中鋼"), ("2006", "東和鋼鐵"), ("1301", "台塑"),
        ("1303", "南亞"), ("1326", "台化"), ("1102", "亞泥"),
        ("1101", "台泥"), ("6505", "台塑化"), ("2015", "豐興"),
        ("1603", "華電"), ("1605", "華新"), ("2104", "中橡"),
    ],
    "食品/消費/零售": [
        ("1216", "統一"), ("2912", "統一超"), ("1215", "卜蜂"),
        ("1210", "大成"), ("2727", "王品"), ("5904", "寶雅"),
        ("9917", "中保科"), ("2723", "美廉社"),
        ("1201", "味全"), ("6191", "精成科"),
    ],
    "生技醫療": [
        ("4106", "雃博"), ("4114", "健喬信元"), ("1737", "台鹽"),
        ("4538", "葡萄王"), ("4150", "玄天"), ("4107", "邦特"),
        ("4126", "太醫"), ("4174", "浩鼎"), ("1762", "中化合成"),
    ],
    "ETF": [
        ("0050", "元大台50"), ("0056", "元大高息"), ("00878", "國泰永續"),
        ("00929", "復華台灣科技優息"), ("006208", "富邦台50"),
        ("00900", "富邦特選高股息"), ("00692", "富邦公司治理"),
        ("00713", "元大台灣高息低波"), ("0052", "富邦科技"),
        ("00733", "富邦台灣中小"),
    ],
}

# 去重：若同一 sid 出現在多個板塊，以第一次出現的板塊為準
_seen: set[str] = set()
_deduped: dict[str, list[tuple[str, str]]] = {}
for _sector, _stocks in ANALYST_UNIVERSE.items():
    _deduped[_sector] = []
    for _sid, _name in _stocks:
        if _sid not in _seen:
            _seen.add(_sid)
            _deduped[_sector].append((_sid, _name))
ANALYST_UNIVERSE = _deduped

# 扁平化 SID → (name, sector) mapping
_SID_META: dict[str, tuple[str, str]] = {}
for _sector, _stocks in ANALYST_UNIVERSE.items():
    for _sid, _name in _stocks:
        _SID_META[_sid] = (_name, _sector)

ALL_SIDS: list[str] = list(_SID_META.keys())

# ── DB-backed lookup cache (loaded once on first use) ───────────────────────
_DB_META: dict[str, tuple[str, str]] | None = None  # sid → (name, sector)


def _load_db_meta(db_path: str = DB_PATH) -> dict[str, tuple[str, str]]:
    global _DB_META
    if _DB_META is not None:
        return _DB_META
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT stock_id, stock_name, sector FROM _universe").fetchall()
        conn.close()
        _DB_META = {r[0]: (r[1] or r[0], r[2] or "未分類") for r in rows}
    except Exception:
        _DB_META = {}
    return _DB_META


def get_name(sid: str, db_path: str = DB_PATH) -> str:
    meta = _load_db_meta(db_path)
    if sid in meta:
        return meta[sid][0]
    return _SID_META.get(sid, (sid, ""))[0]


def get_sector(sid: str, db_path: str = DB_PATH) -> str:
    meta = _load_db_meta(db_path)
    if sid in meta:
        return meta[sid][1]
    return _SID_META.get(sid, ("", "未分類"))[1]


def list_sectors(db_path: str = DB_PATH) -> list[str]:
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT sector, COUNT(*) cnt FROM _universe WHERE sector != '' "
            "GROUP BY sector ORDER BY cnt DESC"
        ).fetchall()
        conn.close()
        if rows:
            return [r[0] for r in rows]
    except Exception:
        pass
    return list(ANALYST_UNIVERSE.keys())


def list_by_sector(sector: str) -> list[tuple[str, str]]:
    return ANALYST_UNIVERSE.get(sector, [])


def list_by_sector_db(sector: str, db_path: str = DB_PATH) -> list[tuple[str, str]]:
    """Return (sid, name) pairs for a sector, limited to stocks with daily_price in DB."""
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT u.stock_id, u.stock_name FROM _universe u "
            "JOIN _symbols s ON s.name = 'daily_price/' || u.stock_id "
            "WHERE u.sector = ? ORDER BY u.stock_id",
            (sector,),
        ).fetchall()
        conn.close()
        if rows:
            return [(r[0], r[1] or r[0]) for r in rows]
    except Exception:
        pass
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
