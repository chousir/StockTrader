"""台股智慧搜尋元件：支援代碼、中文名稱、產業別的模糊搜尋"""

import streamlit as st
import pandas as pd
from rapidfuzz import fuzz, process

_POPULAR_IDS = [
    "2330", "2317", "2454", "2882", "2886",
    "2603", "0050", "0056", "00878", "3008",
]

_BUILTIN_STOCKS = [
    {"stock_id": "2330", "stock_name": "台積電", "industry_category": "半導體業"},
    {"stock_id": "2317", "stock_name": "鴻海", "industry_category": "電子零組件業"},
    {"stock_id": "2454", "stock_name": "聯發科", "industry_category": "半導體業"},
    {"stock_id": "2882", "stock_name": "國泰金", "industry_category": "金融保險業"},
    {"stock_id": "2886", "stock_name": "兆豐金", "industry_category": "金融保險業"},
    {"stock_id": "2603", "stock_name": "長榮", "industry_category": "航運業"},
    {"stock_id": "2609", "stock_name": "陽明", "industry_category": "航運業"},
    {"stock_id": "2615", "stock_name": "萬海", "industry_category": "航運業"},
    {"stock_id": "0050", "stock_name": "元大台灣50", "industry_category": "ETF"},
    {"stock_id": "0056", "stock_name": "元大高股息", "industry_category": "ETF"},
    {"stock_id": "00878", "stock_name": "國泰永續高股息", "industry_category": "ETF"},
    {"stock_id": "3008", "stock_name": "大立光", "industry_category": "光學器材業"},
    {"stock_id": "2308", "stock_name": "台達電", "industry_category": "電子零組件業"},
    {"stock_id": "2303", "stock_name": "聯電", "industry_category": "半導體業"},
    {"stock_id": "2002", "stock_name": "中鋼", "industry_category": "鋼鐵工業"},
    {"stock_id": "1303", "stock_name": "南亞", "industry_category": "塑膠工業"},
    {"stock_id": "1301", "stock_name": "台塑", "industry_category": "塑膠工業"},
    {"stock_id": "2412", "stock_name": "中華電", "industry_category": "電信業"},
    {"stock_id": "2891", "stock_name": "中信金", "industry_category": "金融保險業"},
    {"stock_id": "2881", "stock_name": "富邦金", "industry_category": "金融保險業"},
]


class TWStockSearchIndex:
    """台股搜尋索引，支援代碼/名稱/產業模糊搜尋"""

    def __init__(self):
        self._index: pd.DataFrame = pd.DataFrame(_BUILTIN_STOCKS)
        self._corpus: list[str] = [
            f"{r['stock_id']} {r['stock_name']} {r['industry_category']}"
            for r in _BUILTIN_STOCKS
        ]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not query or not query.strip():
            return self._popular()

        exact = self._index[self._index["stock_id"] == query.strip()]
        if not exact.empty:
            return self._fmt(exact)

        matches = process.extract(
            query, self._corpus,
            scorer=fuzz.partial_ratio,
            limit=limit,
            score_cutoff=40,
        )
        if not matches:
            return self._popular()
        indices = [m[2] for m in matches]
        return self._fmt(self._index.iloc[indices])

    def _popular(self) -> list[dict]:
        rows = self._index[self._index["stock_id"].isin(_POPULAR_IDS)]
        return self._fmt(rows)

    def _fmt(self, df: pd.DataFrame) -> list[dict]:
        return [
            {
                "stock_id": row["stock_id"],
                "display": f"{row['stock_id']} {row['stock_name']}",
                "subtitle": row["industry_category"],
            }
            for _, row in df.iterrows()
        ]


@st.cache_resource
def _get_search_index() -> TWStockSearchIndex:
    return TWStockSearchIndex()


def render_smart_search(key: str = "stock_search") -> str | None:
    """
    渲染台股搜尋框（text_input 實作，不依賴 streamlit-searchbox）

    回傳選定的股票代碼，未選擇時回傳 None。
    """
    idx = _get_search_index()
    query = st.text_input(
        "搜尋股票",
        placeholder="輸入代碼或名稱（例如：2330、台積電、半導體）",
        key=key,
        label_visibility="collapsed",
    )

    results = idx.search(query or "")

    if not query:
        st.caption("熱門：" + "  ".join(r["display"] for r in results[:5]))
        return st.session_state.get("current_stock")

    if len(results) == 1:
        stock_id = results[0]["stock_id"]
        _record_recent(stock_id)
        st.session_state["current_stock"] = stock_id
        st.session_state["g_current_stock"] = stock_id
        return stock_id

    if results:
        options = [r["display"] for r in results]
        chosen = st.selectbox("選擇股票", options, key=f"{key}_select",
                               label_visibility="collapsed")
        if chosen:
            stock_id = chosen.split(" ")[0]
            _record_recent(stock_id)
            st.session_state["current_stock"] = stock_id
            st.session_state["g_current_stock"] = stock_id
            return stock_id

    return None


def _record_recent(stock_id: str) -> None:
    if "recent_stocks" not in st.session_state:
        st.session_state.recent_stocks = []
    recent: list = st.session_state.recent_stocks
    if stock_id in recent:
        recent.remove(stock_id)
    recent.insert(0, stock_id)
    st.session_state.recent_stocks = recent[:20]
