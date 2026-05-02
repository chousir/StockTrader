# 後續規劃書 (Plan 2)：UX 強化與進階介面設計

> **版本**：v1.0 | **日期**：2026-05-02
> **定位**：Plan 1（核心引擎）完成後的介面體驗升級規劃
> **前置條件**：Plan 1 的 Phase 0-5 已全部完成
> **設計靈感來源**：OpenStock (Open-Dev-Society/OpenStock) 的 Dashboard 設計語言

---

## 0. 規劃總覽

本規劃書涵蓋 7 項 UX 強化功能，預計在 Plan 1 完成後分 3 個 Phase 交付。所有功能均基於現有 Streamlit + Plotly 技術棧實作，不引入 Next.js/React 等額外前端框架。

| Phase | 功能 | 預估時間 |
|-------|------|---------|
| Phase 6 | 深色主題 + Dashboard 佈局重構 + 卡片式績效摘要 | 3-4 小時 |
| Phase 7 | 台股智慧搜尋面板 + 關注清單 (Watchlist) | 4-5 小時 |
| Phase 8 | TradingView 輔助面板 + 首次設定精靈 | 3-4 小時 |

---

## 1. 深色主題為預設 (Dark Theme Default)

### 1.1 目標

長時間使用回測與盤中監控的使用者需要低眼壓的介面。系統預設深色主題，配色參考 OpenStock 的暗底風格，但加入台股慣用的紅漲綠跌色系。

### 1.2 實作規格

**Streamlit 主題配置：**

```toml
# .streamlit/config.toml

[theme]
base = "dark"

# 主色調：深藍灰底 + 青藍重點色（參考 OpenStock 風格）
primaryColor = "#00D4AA"           # 青綠色，用於按鈕、連結、重點元素
backgroundColor = "#0F1117"        # 深底色（近乎黑）
secondaryBackgroundColor = "#1A1D29" # 側邊欄、卡片背景
textColor = "#E8EAED"              # 主文字色（柔白）

[server]
headless = true

[browser]
gatherUsageStats = false
```

**台股專用色彩常數：**

```python
# src/twquant/dashboard/styles/theme.py

class TWStockColors:
    """台股慣用配色（深色主題版）"""
    
    # 漲跌色系（台股慣例：紅漲綠跌，與歐美相反）
    PRICE_UP = "#EF4444"           # 紅色（上漲）
    PRICE_DOWN = "#22C55E"         # 綠色（下跌）
    PRICE_FLAT = "#9CA3AF"         # 灰色（平盤）
    
    # 成交量柱狀圖配色
    VOLUME_UP = "rgba(239, 68, 68, 0.6)"    # 半透明紅
    VOLUME_DOWN = "rgba(34, 197, 94, 0.6)"  # 半透明綠
    
    # K 線圖配色
    CANDLE_UP_FILL = "#EF4444"
    CANDLE_UP_BORDER = "#DC2626"
    CANDLE_DOWN_FILL = "#22C55E"
    CANDLE_DOWN_BORDER = "#16A34A"
    
    # 均線色系（需在深底上清晰可辨）
    MA_5 = "#FBBF24"               # 黃色（5 日均線）
    MA_10 = "#F97316"              # 橙色（10 日均線）
    MA_20 = "#3B82F6"              # 藍色（20 日均線）
    MA_60 = "#A855F7"              # 紫色（60 日均線）
    
    # 回測專用
    EQUITY_CURVE = "#00D4AA"       # 策略資金曲線（青綠）
    BENCHMARK_CURVE = "#6B7280"    # 基準資金曲線（灰色）
    DRAWDOWN_FILL = "rgba(239, 68, 68, 0.2)"  # 回撤填充區
    
    # 法人籌碼面
    FOREIGN_BUY = "#3B82F6"        # 外資買超（藍）
    FOREIGN_SELL = "#EF4444"       # 外資賣超（紅）
    DEALER_COLOR = "#A855F7"       # 自營商（紫）
    TRUST_COLOR = "#F97316"        # 投信（橙）
    
    # 介面元素
    CARD_BG = "#1E2130"
    CARD_BORDER = "#2A2D3A"
    ACCENT = "#00D4AA"
    MUTED_TEXT = "#6B7280"
```

**Plotly 圖表全局深色模板：**

```python
# src/twquant/dashboard/styles/plotly_theme.py

import plotly.graph_objects as go
import plotly.io as pio

def register_twquant_dark_template():
    """註冊 TWQuant 深色 Plotly 模板，所有圖表自動套用"""
    
    pio.templates["twquant_dark"] = go.layout.Template(
        layout=go.Layout(
            paper_bgcolor="#0F1117",
            plot_bgcolor="#0F1117",
            font=dict(color="#E8EAED", family="Noto Sans TC, sans-serif"),
            xaxis=dict(
                gridcolor="#2A2D3A",
                zerolinecolor="#2A2D3A",
                linecolor="#2A2D3A",
            ),
            yaxis=dict(
                gridcolor="#2A2D3A",
                zerolinecolor="#2A2D3A",
                linecolor="#2A2D3A",
            ),
            colorway=[
                "#00D4AA", "#3B82F6", "#F97316", "#A855F7",
                "#FBBF24", "#EF4444", "#22C55E", "#EC4899",
            ],
            hoverlabel=dict(
                bgcolor="#1E2130",
                font_color="#E8EAED",
                bordercolor="#2A2D3A",
            ),
            legend=dict(
                bgcolor="rgba(0,0,0,0)",
                font=dict(color="#9CA3AF"),
            ),
        )
    )
    pio.templates.default = "twquant_dark"
```

### 1.3 Phase 6 步驟

```
步驟 6.1：建立主題配置
  → 執行：
    - 建立 .streamlit/config.toml（深色主題）
    - 建立 src/twquant/dashboard/styles/theme.py（色彩常數）
    - 建立 src/twquant/dashboard/styles/plotly_theme.py（Plotly 模板）
  → 驗證：
    - streamlit run 後預設為深色主題
    - K 線圖紅漲綠跌在深底上清晰可辨
    - 所有 Plotly 圖表自動套用深色模板
```

---

## 2. Dashboard 佈局重構 (Layout Restructure)

### 2.1 目標

將現有 Streamlit 頁面從「單欄流式佈局」重構為 OpenStock 風格的三層資訊架構，讓使用者一眼掌握全局、聚焦核心、按需展開細節。

### 2.2 三層資訊架構

```
┌─────────────────────────────────────────────────────────────┐
│  🔍 搜尋列 + 關注清單快捷 + 系統狀態指示燈                     │  ← Layer 1: 全局導覽
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                                                             │
│              主力圖表區 / 回測結果區                           │  ← Layer 2: 核心內容
│              （佔頁面 60-70% 高度）                           │     （佔最大面積）
│                                                             │
│                                                             │
├───────────────────────┬─────────────────────────────────────┤
│  績效指標卡片群        │  輔助資訊面板                         │  ← Layer 3: 輔助資訊
│  (Sharpe, MaxDD...)   │  (法人動態 / 新聞 / 基本面)           │
└───────────────────────┴─────────────────────────────────────┘
```

### 2.3 各頁面佈局實作

**個股分析頁 (02_stock_analysis.py)：**

```python
import streamlit as st

def render_stock_analysis_page():
    # ── Layer 1：全局導覽（固定在頂部） ──
    col_search, col_watchlist, col_status = st.columns([5, 3, 2])
    with col_search:
        selected_stock = render_smart_search()  # 見第 3 節
    with col_watchlist:
        render_watchlist_chips()                 # 見第 4 節
    with col_status:
        render_sync_status_indicator()           # 數據同步狀態燈
    
    st.divider()
    
    # ── Layer 2：主力圖表區 ──
    # 使用 tabs 切換不同圖表視角
    tab_kline, tab_indicators, tab_institutional = st.tabs([
        "📈 K 線圖", "📊 技術指標", "🏦 法人籌碼"
    ])
    
    with tab_kline:
        # 主 Plotly K 線圖（含均線、回測訊號標記）
        # 此區域佔頁面最大空間
        render_kline_chart(stock_id, height=500)
    
    with tab_indicators:
        render_indicator_panel(stock_id)
    
    with tab_institutional:
        render_institutional_chart(stock_id)
    
    # ── Layer 3：輔助資訊 ──
    col_left, col_right = st.columns([1, 1])
    
    with col_left:
        with st.container(border=True):
            st.subheader("公司基本資料")
            render_company_profile(stock_id)
    
    with col_right:
        with st.container(border=True):
            st.subheader("關鍵財務指標")
            render_financial_summary(stock_id)
```

**回測結果頁 (04_backtest_result.py)：**

```python
def render_backtest_result_page():
    # ── Layer 1：策略摘要 ──
    st.markdown(f"### 回測結果：{strategy_name} | {stock_id}")
    
    # ── Layer 2：資金曲線（主力區域） ──
    render_equity_curve_vs_benchmark(result, benchmark, height=450)
    
    # ── Layer 3：績效指標卡片群 + 交易明細 ──
    render_metrics_cards(result)  # 見第 5 節
    
    col_trades, col_monthly = st.columns([1, 1])
    with col_trades:
        with st.container(border=True):
            st.subheader("交易明細")
            render_trades_table(result)
    with col_monthly:
        with st.container(border=True):
            st.subheader("月度報酬")
            render_monthly_heatmap(result)
```

### 2.4 Phase 6 步驟

```
步驟 6.2：重構個股分析頁佈局
  → 執行：改寫 pages/02_stock_analysis.py
    - 頂部搜尋列（預留，第 3 節實作內容）
    - 中間 tabs 切換（K 線 / 指標 / 籌碼）
    - 底部雙欄輔助資訊
  → 驗證：三層結構清晰，主圖表佔最大面積

步驟 6.3：重構回測結果頁佈局
  → 執行：改寫 pages/04_backtest_result.py
    - 頂部策略摘要
    - 中間資金曲線
    - 底部卡片群 + 雙欄明細
  → 驗證：資金曲線為視覺焦點，績效指標一目了然

步驟 6.4：重構市場總覽頁佈局
  → 執行：改寫 pages/01_market_overview.py
    - 預留 TradingView Widget 嵌入區（第 6 節實作）
    - 外資買超排行 + 融資融券變化
  → 驗證：頁面資訊密度高但不擁擠
```

---

## 3. 台股智慧搜尋面板 (Smart Stock Search)

### 3.1 目標

實現類似 OpenStock Command+K 的即時搜尋體驗，但針對台股優化：支援股票代碼（2330）、中文名稱（台積電）、產業別（半導體）的模糊搜尋，idle 時顯示熱門個股或最近查看的股票。

### 3.2 實作規格

```python
# src/twquant/dashboard/components/smart_search.py

import streamlit as st
from streamlit_searchbox import st_searchbox
from rapidfuzz import fuzz, process
import pandas as pd

class TWStockSearchIndex:
    """
    台股搜尋索引
    
    資料來源：FinMind taiwan_stock_info()
    索引欄位：stock_id (代碼) + stock_name (名稱) + industry_category (產業別)
    搜尋演算法：RapidFuzz 模糊匹配（支援中文）
    """
    
    def __init__(self):
        self._index: pd.DataFrame = pd.DataFrame()
        self._search_corpus: list[str] = []
    
    @st.cache_data(ttl=86400)  # 每日更新一次股票清單
    def build_index(_self) -> None:
        """從本地資料庫或 FinMind 建立搜尋索引"""
        # 合併代碼+名稱+產業為搜尋字串
        # 例如："2330 台積電 半導體業"
        _self._index = load_stock_info()
        _self._search_corpus = [
            f"{row.stock_id} {row.stock_name} {row.industry_category}"
            for _, row in _self._index.iterrows()
        ]
    
    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        模糊搜尋台股
        
        支援的查詢方式：
        - 代碼精確匹配："2330" → 台積電
        - 名稱模糊匹配："台積" → 台積電、台積電ADR
        - 產業模糊匹配："半導" → 所有半導體業股票
        - 混合查詢："金融 兆豐" → 兆豐金
        """
        if not query or not query.strip():
            return self._get_popular_stocks()
        
        # 代碼精確匹配優先
        exact = self._index[self._index['stock_id'] == query.strip()]
        if not exact.empty:
            return self._format_results(exact)
        
        # RapidFuzz 模糊匹配
        matches = process.extract(
            query, self._search_corpus,
            scorer=fuzz.partial_ratio,
            limit=limit,
            score_cutoff=50
        )
        
        indices = [m[2] for m in matches]
        return self._format_results(self._index.iloc[indices])
    
    def _get_popular_stocks(self) -> list[dict]:
        """Idle 時顯示熱門台股"""
        popular_ids = [
            "2330", "2317", "2454", "2882", "2886",
            "2603", "0050", "0056", "00878", "3008",
        ]
        popular = self._index[self._index['stock_id'].isin(popular_ids)]
        return self._format_results(popular)
    
    def _get_recent_stocks(self) -> list[dict]:
        """顯示最近查看過的股票（從 session_state 讀取）"""
        recent_ids = st.session_state.get("recent_stocks", [])
        if not recent_ids:
            return self._get_popular_stocks()
        recent = self._index[self._index['stock_id'].isin(recent_ids[:10])]
        return self._format_results(recent)
    
    def _format_results(self, df: pd.DataFrame) -> list[dict]:
        return [
            {
                "stock_id": row.stock_id,
                "display": f"{row.stock_id} {row.stock_name}",
                "subtitle": row.industry_category,
            }
            for _, row in df.iterrows()
        ]


def render_smart_search() -> str | None:
    """
    渲染智慧搜尋元件
    
    行為：
    - 空白時顯示「熱門個股」或「最近查看」
    - 輸入時即時模糊搜尋
    - 選擇後更新全頁面的股票代碼
    - 自動記錄到最近查看清單
    """
    search_index = TWStockSearchIndex()
    search_index.build_index()
    
    def search_fn(query: str) -> list[str]:
        results = search_index.search(query)
        return [r["display"] for r in results]
    
    selected = st_searchbox(
        search_function=search_fn,
        placeholder="🔍 搜尋股票代碼或名稱（例如：2330、台積電、半導體）",
        key="stock_search",
        default=None,
        clearable=True,
    )
    
    if selected:
        stock_id = selected.split(" ")[0]  # 從 "2330 台積電" 提取代碼
        _record_recent(stock_id)
        return stock_id
    
    return None


def _record_recent(stock_id: str):
    """記錄最近查看的股票到 session_state"""
    if "recent_stocks" not in st.session_state:
        st.session_state.recent_stocks = []
    
    recent = st.session_state.recent_stocks
    if stock_id in recent:
        recent.remove(stock_id)
    recent.insert(0, stock_id)
    st.session_state.recent_stocks = recent[:20]  # 最多保留 20 筆
```

### 3.3 搜尋體驗設計

| 場景 | 使用者輸入 | 搜尋結果 |
|------|----------|---------|
| 空白（Idle） | （無） | 顯示熱門台股：台積電、鴻海、0050... |
| 代碼精確 | `2330` | 台積電（直接跳轉，不顯示下拉） |
| 名稱模糊 | `台積` | 台積電 (2330)、台積電ADR |
| 產業搜尋 | `航運` | 長榮 (2603)、萬海 (2615)、陽明 (2609)... |
| 混合查詢 | `金控 國泰` | 國泰金 (2882) |
| 代碼前綴 | `23` | 2330 台積電、2317 鴻海、2308 台達電... |

### 3.4 依賴套件

```toml
# pyproject.toml 新增
streamlit-searchbox = "^0.1"
rapidfuzz = "^3.6"         # 高速模糊匹配（C++ 實作，支援中文）
```

### 3.5 Phase 7 步驟

```
步驟 7.1：建立台股搜尋索引
  → 執行：src/twquant/dashboard/components/smart_search.py
    - TWStockSearchIndex 類別
    - 從 FinMind taiwan_stock_info() 建立索引
    - RapidFuzz 模糊匹配
  → 驗證：
    - search("台積") 回傳台積電
    - search("半導") 回傳所有半導體股
    - search("") 回傳熱門個股清單
    - 搜尋 2000+ 股票清單 < 50ms

步驟 7.2：整合至所有頁面頂部
  → 執行：在每個頁面的 Layer 1 嵌入 render_smart_search()
  → 驗證：
    - 搜尋後全頁面切換到所選股票
    - 最近查看清單正確記錄
```

---

## 4. 關注清單 (Watchlist)

### 4.1 目標

提供 per-user 的自選股清單，一鍵加入/移除。關注清單中的股票享有數據同步優先權，並直接出現在多標的回測的候選名單中。

### 4.2 實作規格

```python
# src/twquant/data/watchlist.py

import json
from pathlib import Path
from datetime import datetime

class Watchlist:
    """
    關注清單管理
    
    儲存方式：本地 JSON 檔案（單使用者場景）
    未來擴充：SQLite / ArcticDB metadata table（多使用者場景）
    
    與系統的整合點：
    1. 數據同步引擎：watchlist 中的股票優先同步
    2. 多標的回測：watchlist 作為預設股票池
    3. 市場總覽頁：watchlist 股票的即時行情卡片
    """
    
    WATCHLIST_PATH = Path("data/watchlist.json")
    
    def __init__(self):
        self._stocks: dict[str, dict] = {}
        self._load()
    
    def add(self, stock_id: str, stock_name: str = "") -> None:
        """加入關注清單"""
        if stock_id not in self._stocks:
            self._stocks[stock_id] = {
                "stock_name": stock_name,
                "added_at": datetime.now().isoformat(),
            }
            self._save()
    
    def remove(self, stock_id: str) -> None:
        """從關注清單移除"""
        self._stocks.pop(stock_id, None)
        self._save()
    
    def contains(self, stock_id: str) -> bool:
        return stock_id in self._stocks
    
    def list_all(self) -> list[str]:
        """回傳所有關注的股票代碼"""
        return list(self._stocks.keys())
    
    def list_with_details(self) -> list[dict]:
        """回傳含詳細資訊的關注清單"""
        return [
            {"stock_id": sid, **info}
            for sid, info in self._stocks.items()
        ]
    
    def _load(self):
        if self.WATCHLIST_PATH.exists():
            self._stocks = json.loads(self.WATCHLIST_PATH.read_text())
    
    def _save(self):
        self.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.WATCHLIST_PATH.write_text(
            json.dumps(self._stocks, ensure_ascii=False, indent=2)
        )
```

**Streamlit UI 元件：**

```python
# src/twquant/dashboard/components/watchlist_ui.py

import streamlit as st

def render_watchlist_button(stock_id: str, stock_name: str):
    """加入/移除關注清單的切換按鈕（顯示在個股頁面標題旁）"""
    wl = get_watchlist()
    
    if wl.contains(stock_id):
        if st.button("⭐ 已關注", key=f"wl_{stock_id}", type="secondary"):
            wl.remove(stock_id)
            st.rerun()
    else:
        if st.button("☆ 加入關注", key=f"wl_{stock_id}", type="primary"):
            wl.add(stock_id, stock_name)
            st.rerun()


def render_watchlist_chips():
    """在頂部搜尋列旁顯示關注清單的快捷 chips"""
    wl = get_watchlist()
    stocks = wl.list_all()
    
    if not stocks:
        st.caption("尚未關注任何股票")
        return
    
    cols = st.columns(min(len(stocks), 8))
    for i, stock_id in enumerate(stocks[:8]):
        with cols[i]:
            if st.button(stock_id, key=f"chip_{stock_id}", use_container_width=True):
                st.session_state.current_stock = stock_id
                st.rerun()
    
    if len(stocks) > 8:
        st.caption(f"...及其他 {len(stocks) - 8} 檔")


def render_watchlist_sidebar():
    """在側邊欄顯示完整關注清單"""
    wl = get_watchlist()
    
    with st.sidebar:
        st.subheader("⭐ 關注清單")
        
        for item in wl.list_with_details():
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                if st.button(
                    f"{item['stock_id']}",
                    key=f"sidebar_wl_{item['stock_id']}",
                    use_container_width=True,
                ):
                    st.session_state.current_stock = item['stock_id']
                    st.rerun()
            with col_btn:
                if st.button("✕", key=f"rm_wl_{item['stock_id']}"):
                    wl.remove(item['stock_id'])
                    st.rerun()
```

**與數據同步引擎的整合：**

```python
# sync_engine.py 中修改 incremental_sync 的排序邏輯

async def incremental_sync(self):
    all_stocks = await self._get_stale_stocks()
    watchlist_ids = set(Watchlist().list_all())
    
    # 關注清單中的股票排在最前面，優先同步
    prioritized = sorted(
        all_stocks,
        key=lambda sid: (0 if sid in watchlist_ids else 1, sid)
    )
    
    for stock_id in prioritized:
        await self._sync_single(stock_id)
```

### 4.3 Phase 7 步驟

```
步驟 7.3：實作關注清單核心邏輯
  → 執行：src/twquant/data/watchlist.py
  → 驗證：
    - add/remove/contains 正常運作
    - JSON 檔案正確持久化
    - 重啟後關注清單保留

步驟 7.4：實作關注清單 UI 元件
  → 執行：src/twquant/dashboard/components/watchlist_ui.py
    - 加入/移除按鈕
    - 頂部快捷 chips
    - 側邊欄完整清單
  → 驗證：
    - 點擊 chip 切換到該股票
    - 加入/移除後立即反映在 UI 上

步驟 7.5：整合至數據同步引擎
  → 執行：修改 sync_engine.py，watchlist 股票優先同步
  → 驗證：incremental_sync 時，watchlist 股票排在最前面

步驟 7.6：整合至多標的回測
  → 執行：回測頁面的股票池選擇器預設載入 watchlist
  → 驗證：進入多標的回測頁，watchlist 股票已勾選
```

---

## 5. 卡片式績效摘要 (Metric Cards)

### 5.1 目標

將回測績效指標從表格形式改為視覺化卡片群，類似 OpenStock 的 KPI 卡片設計。每張卡片包含指標名稱、數值、與基準的比較（↑↓），一目了然。

### 5.2 實作規格

```python
# src/twquant/dashboard/components/metrics_card.py

import streamlit as st

def render_metrics_cards(result: dict, benchmark_result: dict = None):
    """
    渲染卡片式績效摘要
    
    佈局：2 行 × 4 列 = 8 張卡片
    第一行：報酬相關（累積報酬、年化報酬、Alpha、勝率）
    第二行：風險相關（最大回撤、夏普率、Sortino、盈虧比）
    """
    
    # ── 第一行：報酬指標 ──
    row1 = st.columns(4)
    
    with row1[0]:
        _metric_card(
            label="累積報酬",
            value=f"{result['total_return']:.1%}",
            delta=_compare(result, benchmark_result, 'total_return'),
            is_good=result['total_return'] > 0,
        )
    
    with row1[1]:
        _metric_card(
            label="年化報酬 (CAGR)",
            value=f"{result.get('cagr', 0):.1%}",
            delta=None,
            is_good=result.get('cagr', 0) > 0,
        )
    
    with row1[2]:
        _metric_card(
            label="Alpha",
            value=f"{result.get('alpha', 0):.2%}",
            delta=None,
            is_good=result.get('alpha', 0) > 0,
        )
    
    with row1[3]:
        _metric_card(
            label="勝率",
            value=f"{result['win_rate']:.1%}",
            delta=None,
            is_good=result['win_rate'] > 0.5,
        )
    
    # ── 第二行：風險指標 ──
    row2 = st.columns(4)
    
    with row2[0]:
        _metric_card(
            label="最大回撤",
            value=f"{result['max_drawdown']:.1%}",
            delta=None,
            is_good=False,  # 回撤永遠是負面指標
            invert_color=True,
        )
    
    with row2[1]:
        _metric_card(
            label="夏普率",
            value=f"{result['sharpe_ratio']:.2f}",
            delta=None,
            is_good=result['sharpe_ratio'] > 1.0,
        )
    
    with row2[2]:
        _metric_card(
            label="Sortino",
            value=f"{result['sortino_ratio']:.2f}",
            delta=None,
            is_good=result['sortino_ratio'] > 1.0,
        )
    
    with row2[3]:
        _metric_card(
            label="盈虧比",
            value=f"{result['profit_factor']:.2f}",
            delta=None,
            is_good=result['profit_factor'] > 1.0,
        )
    
    # ── 第三行：台股特有 ──
    row3 = st.columns(4)
    
    with row3[0]:
        _metric_card(
            label="總交易次數",
            value=f"{result['total_trades']}",
            delta=None,
        )
    
    with row3[1]:
        _metric_card(
            label="平均持有天數",
            value=f"{result.get('avg_trade_duration', 0):.0f}",
            delta=None,
        )
    
    with row3[2]:
        _metric_card(
            label="手續費累計",
            value=f"${result.get('total_fees', 0):,.0f}",
            delta=None,
            is_good=False,
            invert_color=True,
        )
    
    with row3[3]:
        _metric_card(
            label="含稅淨報酬",
            value=f"{result.get('net_return_after_tax', 0):.1%}",
            delta=None,
            is_good=result.get('net_return_after_tax', 0) > 0,
        )


def _metric_card(label: str, value: str, delta: str = None,
                  is_good: bool = None, invert_color: bool = False):
    """
    渲染單張績效卡片
    
    使用 st.container(border=True) + 自訂 CSS 模擬卡片效果
    """
    with st.container(border=True):
        st.caption(label)
        
        if is_good is not None:
            if invert_color:
                color = "#22C55E" if not is_good else "#EF4444"
            else:
                color = "#22C55E" if is_good else "#EF4444"
            st.markdown(f"<h2 style='color:{color};margin:0'>{value}</h2>", 
                       unsafe_allow_html=True)
        else:
            st.markdown(f"<h2 style='margin:0'>{value}</h2>", 
                       unsafe_allow_html=True)
        
        if delta:
            st.caption(delta)


def _compare(result: dict, benchmark: dict, key: str) -> str | None:
    """與基準比較，產生 delta 文字"""
    if benchmark is None or key not in benchmark:
        return None
    diff = result[key] - benchmark[key]
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow} 較基準 {diff:+.1%}"
```

### 5.3 Phase 6 步驟

```
步驟 6.5：實作卡片式績效摘要元件
  → 執行：src/twquant/dashboard/components/metrics_card.py
  → 驗證：
    - 3 行 × 4 列 = 12 張卡片正確渲染
    - 正面指標顯示綠色、負面指標顯示紅色
    - 最大回撤等負面指標的顏色邏輯正確（值越大越紅）
    - 與基準比較的 delta 顯示正確

步驟 6.6：整合至回測結果頁
  → 執行：在 04_backtest_result.py 中替換原有的表格為卡片群
  → 驗證：回測完成後，績效指標以卡片形式顯示
```

---

## 6. TradingView 輔助面板嵌入 (TradingView Widgets)

### 6.1 目標

在「市場總覽」頁面嵌入 TradingView 的免費嵌入式 Widget，提供專業的市場全局視角。這些 Widget 作為 Plotly 自建圖表的補充，而非替代。

### 6.2 嵌入清單

| Widget 名稱 | 放置頁面 | 用途 | 台股適配 |
|------------|---------|------|---------|
| 市場熱力圖 (Heatmap) | 市場總覽 | 類股漲跌一覽 | 設定 exchange=TWSE |
| 技術分析摘要 (Technicals) | 個股分析（輔助面板） | 快速看技術面多空 | 設定 symbol=TWSE:2330 |
| 跑馬燈 (Ticker Tape) | 所有頁面頂部 | 即時行情滾動 | 自選台股標的 |

### 6.3 實作規格

```python
# src/twquant/dashboard/components/tradingview_widgets.py

import streamlit.components.v1 as components

def render_tv_heatmap(height: int = 500):
    """
    嵌入 TradingView 市場熱力圖
    
    注意事項：
    - TradingView 免費嵌入式 Widget 無需 API Key
    - 台股代碼格式：TWSE:2330（上市）、TPEX:6547（上櫃）
    - 數據可能有延遲（依 TradingView 免費版規則）
    - 此 Widget 僅作為市場總覽的補充，不用於回測
    """
    html = f"""
    <!-- TradingView Widget BEGIN -->
    <div class="tradingview-widget-container" style="height:{height}px;">
      <div class="tradingview-widget-container__widget" 
           style="height:100%;width:100%;">
      </div>
      <script type="text/javascript" 
              src="https://s3.tradingview.com/external-embedding/embed-widget-stock-heatmap.js" 
              async>
      {{
        "exchanges": ["TWSE", "TPEX"],
        "dataSource": "TWSE",
        "grouping": "sector",
        "blockSize": "market_cap_basic",
        "blockColor": "change",
        "locale": "zh_TW",
        "symbolUrl": "",
        "colorTheme": "dark",
        "hasTopBar": true,
        "isDataSetEnabled": true,
        "isZoomEnabled": true,
        "hasSymbolTooltip": true,
        "width": "100%",
        "height": "{height}"
      }}
      </script>
    </div>
    <!-- TradingView Widget END -->
    """
    components.html(html, height=height + 20)


def render_tv_technicals(stock_id: str, height: int = 400):
    """
    嵌入 TradingView 技術分析摘要
    
    顯示 RSI、MACD、MA 等指標的多空評級
    作為使用者自建指標的「第二意見」
    """
    symbol = f"TWSE:{stock_id}"
    
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" 
              src="https://s3.tradingview.com/external-embedding/embed-widget-technical-analysis.js" 
              async>
      {{
        "interval": "1D",
        "width": "100%",
        "isTransparent": true,
        "height": "{height}",
        "symbol": "{symbol}",
        "showIntervalTabs": true,
        "displayMode": "single",
        "locale": "zh_TW",
        "colorTheme": "dark"
      }}
      </script>
    </div>
    """
    components.html(html, height=height + 20)


def render_tv_ticker_tape(symbols: list[str] = None):
    """
    嵌入 TradingView 跑馬燈（頁面頂部）
    
    預設顯示台股權值股的即時行情
    """
    if symbols is None:
        symbols = [
            "TWSE:2330", "TWSE:2317", "TWSE:2454",
            "TWSE:2882", "TWSE:2886", "TWSE:2603",
            "TWSE:0050", "TWSE:0056",
        ]
    
    symbols_json = [{"proName": s, "title": s.split(":")[1]} for s in symbols]
    import json
    
    html = f"""
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" 
              src="https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js" 
              async>
      {{
        "symbols": {json.dumps(symbols_json)},
        "showSymbolLogo": false,
        "isTransparent": true,
        "displayMode": "adaptive",
        "colorTheme": "dark",
        "locale": "zh_TW"
      }}
      </script>
    </div>
    """
    components.html(html, height=46)
```

### 6.4 Phase 8 步驟

```
步驟 8.1：實作 TradingView Widget 元件
  → 執行：src/twquant/dashboard/components/tradingview_widgets.py
    - 市場熱力圖（TWSE + TPEX）
    - 技術分析摘要
    - 跑馬燈
  → 驗證：
    - 熱力圖顯示台股類股分佈
    - 技術分析摘要正確顯示指定台股的多空評級
    - 跑馬燈滾動顯示即時行情（可能有延遲）

步驟 8.2：嵌入至市場總覽頁
  → 執行：在 01_market_overview.py 中加入熱力圖 + 跑馬燈
  → 驗證：頁面載入後 Widget 正常渲染，不影響頁面其他元素

步驟 8.3：嵌入至個股分析頁（輔助面板）
  → 執行：在 02_stock_analysis.py 的 Layer 3 加入技術分析摘要
  → 驗證：切換股票後，Widget 更新為對應標的
```

---

## 7. 首次設定精靈 (Onboarding Wizard)

### 7.1 目標

新使用者首次啟動系統時，引導完成基本設定，避免面對空白的設定頁面不知所措。設定完成後系統即可開始運作。

### 7.2 設定精靈流程

```
Step 1/4：歡迎                    Step 2/4：交易設定
┌────────────────────────┐      ┌────────────────────────┐
│                        │      │                        │
│   🎯 歡迎使用 TWQuant   │      │  券商手續費折扣          │
│                        │      │  [========] 6 折        │
│   台股量化交易回測平台    │      │                        │
│                        │      │  初始回測資金             │
│   讓我們花 1 分鐘完成    │      │  [  1,000,000  ] 元     │
│   基本設定              │      │                        │
│                        │      │  基準指數               │
│        [開始設定 →]      │      │  ○ 加權指數 (TAIEX)     │
│                        │      │  ● 0050 ETF            │
└────────────────────────┘      │  ○ 006208 ETF          │
                                │                        │
                                │       [← 上一步] [下一步 →] │
                                └────────────────────────┘

Step 3/4：數據設定                Step 4/4：完成
┌────────────────────────┐      ┌────────────────────────┐
│                        │      │                        │
│  FinMind API Token     │      │   ✅ 設定完成！          │
│  [________________]    │      │                        │
│  (免費註冊取得)         │      │   你的設定：             │
│                        │      │   • 手續費六折            │
│  數據同步模式            │      │   • 初始資金 100 萬       │
│  ○ 僅同步關注清單        │      │   • 基準：0050          │
│  ● 全市場同步（建議）     │      │   • 全市場同步           │
│  ○ 暫不同步              │      │                        │
│                        │      │   [開始使用 TWQuant →]   │
│  歷史數據起始日           │      │                        │
│  [  2015-01-01  ]       │      │   預估首次同步：          │
│                        │      │   約 3-4 小時            │
│       [← 上一步] [下一步 →] │      │                        │
└────────────────────────┘      └────────────────────────┘
```

### 7.3 實作規格

```python
# src/twquant/dashboard/components/onboarding.py

import streamlit as st
from pathlib import Path
import json

ONBOARDING_COMPLETE_FLAG = Path("data/.onboarding_complete")

def should_show_onboarding() -> bool:
    """檢查是否需要顯示首次設定精靈"""
    return not ONBOARDING_COMPLETE_FLAG.exists()

def render_onboarding_wizard():
    """渲染首次設定精靈"""
    
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 1
    
    step = st.session_state.onboarding_step
    
    # 進度指示
    st.progress(step / 4, text=f"設定步驟 {step}/4")
    
    if step == 1:
        _render_step_welcome()
    elif step == 2:
        _render_step_trading()
    elif step == 3:
        _render_step_data()
    elif step == 4:
        _render_step_complete()


def _render_step_welcome():
    st.markdown("## 🎯 歡迎使用 TWQuant")
    st.markdown("台股量化交易回測平台")
    st.markdown("讓我們花 1 分鐘完成基本設定，之後你可以隨時在「設定」頁面修改。")
    
    if st.button("開始設定 →", type="primary", use_container_width=True):
        st.session_state.onboarding_step = 2
        st.rerun()


def _render_step_trading():
    st.markdown("## ⚙️ 交易設定")
    
    discount = st.slider(
        "券商手續費折扣",
        min_value=1, max_value=10, value=6,
        help="台股手續費公定價 0.1425%，多數券商提供 5-6 折優惠",
        format="%d 折",
    )
    st.session_state.onboarding_broker_discount = discount / 10
    
    init_cash = st.number_input(
        "初始回測資金（新台幣）",
        min_value=100_000, max_value=100_000_000,
        value=1_000_000, step=100_000,
        format="%d",
    )
    st.session_state.onboarding_init_cash = init_cash
    
    benchmark = st.radio(
        "預設基準指數",
        options=["0050", "TAIEX", "006208"],
        captions=[
            "元大台灣50 ETF（最常用）",
            "加權股價指數",
            "富邦台50 ETF（內扣費用較低）",
        ],
        index=0,
    )
    st.session_state.onboarding_benchmark = benchmark
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 上一步"):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col2:
        if st.button("下一步 →", type="primary"):
            st.session_state.onboarding_step = 3
            st.rerun()


def _render_step_data():
    st.markdown("## 📊 數據設定")
    
    api_token = st.text_input(
        "FinMind API Token",
        type="password",
        help="至 finmindtrade.com 免費註冊取得，可提高 API 上限至 600 次/小時",
    )
    st.session_state.onboarding_api_token = api_token
    
    sync_mode = st.radio(
        "數據同步模式",
        options=["full", "watchlist_only", "none"],
        captions=[
            "全市場同步（建議，約 2000 檔股票，首次約 3-4 小時）",
            "僅同步關注清單中的股票",
            "暫不同步（使用範例數據）",
        ],
        index=0,
    )
    st.session_state.onboarding_sync_mode = sync_mode
    
    start_date = st.date_input(
        "歷史數據起始日",
        value=pd.to_datetime("2015-01-01"),
        min_value=pd.to_datetime("2000-01-01"),
        max_value=pd.to_datetime("today"),
        help="建議至少 5 年以上的歷史數據，回測結果才有統計意義",
    )
    st.session_state.onboarding_start_date = start_date.isoformat()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 上一步"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col2:
        if st.button("下一步 →", type="primary"):
            st.session_state.onboarding_step = 4
            st.rerun()


def _render_step_complete():
    st.markdown("## ✅ 設定完成！")
    
    # 顯示設定摘要
    st.markdown("### 你的設定")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("手續費折扣", f"{st.session_state.get('onboarding_broker_discount', 0.6):.0%}")
        st.metric("基準指數", st.session_state.get('onboarding_benchmark', '0050'))
    with col2:
        st.metric("初始資金", f"${st.session_state.get('onboarding_init_cash', 1_000_000):,}")
        st.metric("同步模式", {
            "full": "全市場", "watchlist_only": "關注清單", "none": "暫不同步"
        }.get(st.session_state.get('onboarding_sync_mode', 'full')))
    
    sync_mode = st.session_state.get('onboarding_sync_mode', 'full')
    if sync_mode == "full":
        st.info("💡 首次全市場同步預計需要 3-4 小時，系統會在背景執行。你可以先用範例數據體驗功能。")
    
    if st.button("🚀 開始使用 TWQuant", type="primary", use_container_width=True):
        _save_onboarding_config()
        ONBOARDING_COMPLETE_FLAG.touch()
        st.session_state.onboarding_step = 1
        st.rerun()


def _save_onboarding_config():
    """將設定精靈的結果寫入 config 檔案"""
    config = {
        "broker_discount": st.session_state.get("onboarding_broker_discount", 0.6),
        "init_cash": st.session_state.get("onboarding_init_cash", 1_000_000),
        "benchmark": st.session_state.get("onboarding_benchmark", "0050"),
        "finmind_api_token": st.session_state.get("onboarding_api_token", ""),
        "sync_mode": st.session_state.get("onboarding_sync_mode", "full"),
        "history_start_date": st.session_state.get("onboarding_start_date", "2015-01-01"),
    }
    
    config_path = Path("data/user_config.json")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2))
```

**在主入口整合：**

```python
# src/twquant/dashboard/app.py

import streamlit as st
from components.onboarding import should_show_onboarding, render_onboarding_wizard

st.set_page_config(
    page_title="TWQuant 台股量化平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 首次啟動顯示設定精靈
if should_show_onboarding():
    render_onboarding_wizard()
    st.stop()  # 精靈完成前不顯示其他內容

# 正常頁面載入...
```

### 7.4 Phase 8 步驟

```
步驟 8.4：實作首次設定精靈
  → 執行：src/twquant/dashboard/components/onboarding.py
    - 4 步驟精靈流程
    - 設定持久化至 data/user_config.json
    - 完成旗標 data/.onboarding_complete
  → 驗證：
    - 首次啟動顯示精靈，設定完成後不再出現
    - 刪除 .onboarding_complete 後精靈重新出現
    - 所有設定值正確寫入 config 檔案

步驟 8.5：整合設定至系統各模組
  → 執行：
    - config.py 讀取 user_config.json
    - cost_model.py 使用 broker_discount 設定
    - benchmark.py 使用 benchmark 設定
    - sync_engine.py 使用 sync_mode 和 start_date 設定
  → 驗證：
    - 在精靈中設定手續費 5 折 → 回測結果反映 5 折手續費
    - 在精靈中選 TAIEX 基準 → 回測對比使用加權指數

步驟 8.6：提交全部 UX 強化
  → 執行：git add -A && git commit -m "feat: UX enhancements - dark theme, smart search, watchlist, TV widgets, onboarding" && git push
  → 驗證：CI 通過
```

---

## 8. 新增目錄與檔案總覽

以下是 Plan 2 新增的檔案（相對於 Plan 1 完成後的狀態）：

```
新增/修改的檔案：
├── .streamlit/
│   └── config.toml                          # 深色主題配置（新增）
│
├── src/twquant/dashboard/
│   ├── styles/
│   │   ├── theme.py                         # 台股色彩常數（新增）
│   │   └── plotly_theme.py                  # Plotly 深色模板（新增）
│   ├── components/
│   │   ├── smart_search.py                  # 台股智慧搜尋面板（新增）
│   │   ├── watchlist_ui.py                  # 關注清單 UI 元件（新增）
│   │   ├── metrics_card.py                  # 卡片式績效摘要（修改）
│   │   ├── tradingview_widgets.py           # TradingView 嵌入元件（新增）
│   │   └── onboarding.py                    # 首次設定精靈（新增）
│   ├── pages/
│   │   ├── 01_market_overview.py            # 修改：加入 TV 熱力圖
│   │   ├── 02_stock_analysis.py             # 修改：三層佈局重構
│   │   └── 04_backtest_result.py            # 修改：卡片式績效 + 佈局
│   └── app.py                               # 修改：加入 onboarding 攔截
│
├── src/twquant/data/
│   ├── watchlist.py                         # 關注清單核心邏輯（新增）
│   └── sync_engine.py                       # 修改：watchlist 優先同步
│
└── data/
    ├── watchlist.json                       # 關注清單持久化（運行時產生）
    └── user_config.json                     # 使用者設定（運行時產生）
```

### 新增依賴

```toml
# pyproject.toml 新增
streamlit-searchbox = "^0.1"
rapidfuzz = "^3.6"
```

---

## 9. 全局成功標準

Plan 2 全部完成後，系統應達到以下體驗標準：

1. **首次啟動體驗**：使用者啟動系統後，由設定精靈引導完成基本配置，全程不超過 2 分鐘
2. **股票搜尋**：從輸入到結果出現 < 100ms，支援代碼、中文名稱、產業別模糊搜尋
3. **視覺一致性**：所有頁面、所有圖表統一使用深色主題 + 台股紅漲綠跌配色
4. **資訊層次**：每個頁面遵循三層架構（導覽 → 核心 → 輔助），核心區域佔最大面積
5. **回測結果可讀性**：績效指標以卡片群呈現，正負面指標顏色直覺區分，3 秒內可掌握策略優劣
6. **關注清單整合**：watchlist 貫穿搜尋、同步、回測三個核心流程，減少重複操作
7. **TradingView 補充**：市場熱力圖提供全局視角，技術分析摘要作為自建指標的「第二意見」
