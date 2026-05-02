# 系統開發規劃書：台股混合架構量化交易平台 (Python + Rust)

> **版本**：v1.1 | **日期**：2026-05-02
> **目標讀者**：Claude Code / AI 編程助手
> **開發環境**：GitHub Codespaces（完整 Linux 環境，可執行 git commit/push、安裝系統套件等所有操作）

---

## 0. 專案初始化：Claude Code 開發環境建置

在開始任何開發工作之前，必須先建立以下 Claude Code 所需的開發輔助文件。

### 0.1 建立 CLAUDE.md（專案行為準則）

在專案根目錄建立 `CLAUDE.md`，內容整合 Karpathy 準則與本專案約束：

```markdown
# CLAUDE.md

本專案為台股量化交易平台，採用 Python + Rust 混合架構。

## 行為準則（基於 Andrej Karpathy 觀察）

### 1. 先思考再寫碼
- 明確陳述你的假設。不確定就提問。
- 若有多種解讀方式，列出選項，不要擅自選擇。
- 若存在更簡單的方案，說出來。必要時提出反對意見。
- 若有不清楚之處，停下來。指出困惑之處並提問。

### 2. 簡單優先
- 只寫解決當前問題所需的最少程式碼。不寫推測性功能。
- 不為單次使用的程式碼建立抽象層。
- 不加入未被要求的「彈性」或「可配置性」。
- 不為不可能的情境添加錯誤處理。
- 如果你寫了 200 行而 50 行就能解決，重寫它。

### 3. 精確手術式修改
- 不「改善」鄰近的程式碼、註解或格式。
- 不重構沒有壞的東西。
- 匹配現有風格，即使你會用不同方式寫。
- 如果注意到無關的死碼，提及它但不要刪除。
- 移除你的修改所造成的無用 import/變數/函數。
- 測試標準：每一行修改都必須可追溯到使用者的請求。

### 4. 目標驅動執行
- 將任務轉化為可驗證的目標。
- 多步驟任務必須列出簡要計劃：
  ```
  1. [步驟] → 驗證：[檢查方式]
  2. [步驟] → 驗證：[檢查方式]
  ```
- 強的成功標準讓你能獨立循環執行。弱的標準需要反覆確認。

## 專案特定約束

### 技術棧鎖定
- Python 端：Poetry 管理依賴，Python 3.11+
- Rust 端：Cargo workspace，edition 2021
- 跨語言橋接：PyO3 + maturin
- 回測引擎：VectorBT
- 數據源：FinMind API（台股）、本地 CSV
- 儲存層：ArcticDB（首選）或 SQLite（備選）
- 前端：Streamlit + Plotly
- 數據處理：Polars（首選）、Pandas（VectorBT 相容層）

### 台股交易規則常數
- 券商手續費：成交金額 × 0.1425%（買賣各一次）
- 證券交易稅：賣出時 0.3%（股票）/ 0.1%（ETF）
- 當沖證交稅：0.15%（優惠至 2027 年底）
- 漲跌幅限制：±10%
- 交易單位：1000 股 = 1 張（整股），支援零股交易
- 交割制度：T+2
- 交易時間：09:00-13:30（盤中）、14:00-14:30（盤後零股）

### 記憶體與效能紅線
- Python ↔ Rust 之間禁止逐筆 (Row-by-Row) 資料轉換
- 必須使用 Apache Arrow 或 NumPy buffer 做零拷貝傳輸
- Streamlit 靜態數據必須用 @st.cache_data
- VectorBT Portfolio 物件用完必須 del + gc.collect()
- Rust 端取得 Python GIL 時，鎖定範圍最小化
```

### 0.2 建立 .cursorrules（若同時使用 Cursor）

```
# .cursorrules
與 CLAUDE.md 同步，參照根目錄 CLAUDE.md 中的行為準則與專案約束。
```

### 0.3 建立 docs/ 目錄結構

```
docs/
├── ARCHITECTURE.md          # 系統架構圖與模組關係說明
├── DATA_DICTIONARY.md       # 資料欄位定義與資料表結構
├── API_REFERENCE.md         # 內部模組 API 介面規格
├── DEPLOYMENT.md            # 部署與環境設定指南
├── TESTING_STRATEGY.md      # 測試策略與覆蓋率要求
└── CHANGELOG.md             # 版本變更紀錄
```

### 0.4 建立 .github/ CI/CD 配置

```
.github/
└── workflows/
    ├── ci.yml               # Python lint + test + Rust cargo test
    └── build-rust.yml       # maturin build 驗證
```

---

## 1. 系統總覽與定位

### 1.1 專案願景

開發一套專注於**台灣股市（TWSE/TPEx）**的高效能量化交易與回測系統。採用 Python + Rust 混合架構，Python 負責靈活的數據調度、開源回測引擎與前端視覺化；Rust 封裝非開源的核心商業邏輯與極限運算，確保策略隱私與執行效能。

### 1.2 系統邊界

**包含範圍（Scope In）**：
- 台灣上市（TWSE）、上櫃（TPEx）股票的歷史與即時行情
- 技術指標計算與視覺化
- 多策略回測與績效分析
- 與台灣大盤指數（加權指數、0050 ETF）的基準對比
- 三大法人籌碼數據整合
- 台股特有交易成本精確模擬（手續費 + 證交稅 + 漲跌幅限制）

**排除範圍（Scope Out，未來擴充）**：
- 實盤自動下單（Phase 5 之後）
- 期貨與選擇權
- 海外市場（美股、港股）
- 社群即時通知（LINE Bot/Telegram Bot）

### 1.3 參考的成熟專案

| 專案名稱 | 參考面向 | 連結 |
|---------|---------|------|
| VnPy | 事件驅動架構、模組化設計 | github.com/vnpy/vnpy |
| Hikyuu | C++/Python 混合架構、策略組件化 | github.com/fasiondog/hikyuu |
| FinMind | 台股數據 API 介面設計、50+ 資料集 | github.com/FinMind/FinMind |
| twstock | 台股即時報價與歷史數據爬取 | github.com/mlouielu/twstock |
| QuantConnect/Lean | 專業回測引擎架構、績效報告格式 | github.com/QuantConnect/Lean |
| Qbot | AI 量化策略整合、視覺化介面 | github.com/UFund-Me/Qbot |

---

## 2. 核心技術選型與架構

### 2.1 技術棧總覽

```
┌─────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard                   │
│          (Plotly / TradingView Lightweight Charts)       │
├──────────────────────┬──────────────────────────────────┤
│   Python 應用層      │      Rust 核心運算層              │
│                      │                                  │
│  ┌────────────────┐  │  ┌─────────────────────────────┐ │
│  │  VectorBT      │  │  │  私有策略模組 (.so/.pyd)     │ │
│  │  回測引擎       │◄─┼──│  透過 PyO3 暴露 Python API  │ │
│  └────────────────┘  │  └─────────────────────────────┘ │
│                      │                                  │
│  ┌────────────────┐  │  ┌─────────────────────────────┐ │
│  │  數據管線       │  │  │  高速指標計算引擎             │ │
│  │  (Asyncio +    │  │  │  (Arrow 零拷貝輸入/輸出)     │ │
│  │   FinMind API) │  │  └─────────────────────────────┘ │
│  └────────────────┘  │                                  │
├──────────────────────┴──────────────────────────────────┤
│                    數據儲存層                             │
│        ArcticDB (首選) / SQLite (輕量備選)                │
│        本地 CSV/Parquet 快取                              │
└─────────────────────────────────────────────────────────┘
```

### 2.2 各層技術細節

**前端框架：Streamlit**
- 版本：1.35+（需支援 `st.fragment` 局部更新）
- 視覺化：Plotly 5.x（`make_subplots` 多軸疊加）
- 選配：TradingView Lightweight Charts（透過 `streamlit-lightweight-charts` 套件）

**回測引擎：VectorBT**
- 版本：VectorBT Free 0.26+ 或 VectorBT PRO
- 用途：向量化多標的、多策略平行回測
- 關鍵 API：`Portfolio.from_signals()`、`IndicatorFactory`

**跨語言橋接：PyO3 + maturin**
- PyO3 版本：0.21+
- 建構工具：maturin（產出 `.so`/`.pyd`）
- 數據交換格式：Apache Arrow（透過 `arrow-rs` + `pyarrow`）或 NumPy buffer

**台股數據源：FinMind API**
- 提供 50+ 台股資料集（日 K 線、即時報價、三大法人、融資融券、財務報表等）
- Python SDK：`from FinMind.data import DataLoader`
- API 限制：未登入 300 次/小時，登入後 600 次/小時
- 備選數據源：twstock（即時報價）、證交所/櫃買中心 OpenData

**數據儲存：ArcticDB**
- 由量化基金 Man Group 開源
- 專為 Pandas DataFrame 設計，極高吞吐量
- 支援 S3 或本地 LMDB 後端
- 備選：SQLite（開發/測試階段用）

---

## 3. 目錄結構規劃

```
twquant/                          # 專案根目錄
├── CLAUDE.md                     # Claude Code 行為準則
├── README.md                     # 專案說明
├── pyproject.toml                # Poetry 配置 (Python 依賴管理)
├── poetry.lock
├── Makefile                      # 常用開發指令捷徑
├── Dockerfile                    # 正式版多階段建構
├── Dockerfile.dev                # 開發版（含 Rust 工具鏈）
├── docker-compose.yml            # 正式運行環境
├── docker-compose.dev.yml        # 開發環境覆蓋
├── .dockerignore
│
├── .devcontainer/                # Codespaces / VS Code 開發容器配置
│   └── devcontainer.json
│
├── docs/                         # 文件
│   ├── ARCHITECTURE.md
│   ├── DATA_DICTIONARY.md
│   ├── API_REFERENCE.md
│   ├── DEPLOYMENT.md
│   ├── TESTING_STRATEGY.md
│   └── CHANGELOG.md
│
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── build-rust.yml
│
├── src/                          # Python 原始碼
│   └── twquant/
│       ├── __init__.py
│       ├── config.py             # 全局配置（API keys, 交易常數）
│       ├── constants.py          # 台股交易規則常數
│       │
│       ├── data/                 # 數據管線模組
│       │   ├── __init__.py
│       │   ├── providers/        # 數據源適配器
│       │   │   ├── __init__.py
│       │   │   ├── base.py       # 抽象數據源介面
│       │   │   ├── finmind.py    # FinMind API 適配器
│       │   │   ├── twstock.py    # twstock 即時報價
│       │   │   └── csv_local.py  # 本地 CSV/Parquet 讀取
│       │   ├── storage.py        # ArcticDB / SQLite 儲存層（含 upsert）
│       │   ├── sync_engine.py    # 全市場數據同步引擎（HWM 斷點續傳）
│       │   ├── pipeline.py       # 非同步數據抓取與清洗管線
│       │   ├── sanity.py         # 數據合理性過濾器（OHLCV 檢查）
│       │   ├── ex_dividend_filter.py  # 除權息假跌破過濾器
│       │   └── resampler.py      # 時間序列重採樣工具
│       │
│       ├── indicators/           # 技術指標模組
│       │   ├── __init__.py
│       │   ├── basic.py          # MA, EMA, RSI, MACD, 布林通道
│       │   ├── volume.py         # 成交量相關指標
│       │   ├── custom.py         # 使用者自訂指標介面
│       │   └── tw_specific.py    # 台股特有指標（法人買超、融資融券比）
│       │
│       ├── strategy/             # 策略模組
│       │   ├── __init__.py
│       │   ├── base.py           # 策略抽象基底類別
│       │   ├── builtin/          # 內建策略
│       │   │   ├── __init__.py
│       │   │   ├── ma_crossover.py    # 雙均線交叉
│       │   │   ├── macd_divergence.py # MACD 背離
│       │   │   ├── rsi_reversal.py    # RSI 超買超賣
│       │   │   └── bollinger_breakout.py # 布林通道突破
│       │   └── registry.py       # 策略註冊表
│       │
│       ├── backtest/             # 回測模組
│       │   ├── __init__.py
│       │   ├── engine.py         # VectorBT 回測引擎封裝
│       │   ├── cost_model.py     # 台股交易成本模型
│       │   ├── benchmark.py      # 大盤基準對比
│       │   └── report.py         # 績效報告產出
│       │
│       ├── dashboard/            # Streamlit 前端模組
│       │   ├── __init__.py
│       │   ├── app.py            # Streamlit 主入口
│       │   ├── pages/
│       │   │   ├── 01_market_overview.py   # 市場總覽
│       │   │   ├── 02_stock_analysis.py    # 個股分析
│       │   │   ├── 03_strategy_builder.py  # 策略建構器
│       │   │   ├── 04_backtest_result.py   # 回測結果
│       │   │   └── 05_settings.py          # 系統設定
│       │   ├── components/       # 可複用 UI 元件
│       │   │   ├── __init__.py
│       │   │   ├── kline_chart.py     # K 線圖元件
│       │   │   ├── equity_curve.py    # 資金曲線元件
│       │   │   ├── metrics_card.py    # 績效指標卡片
│       │   │   ├── stock_selector.py  # 股票選擇器
│       │   │   └── progress_tracker.py # 非同步進度條元件
│       │   └── styles/           # CSS/主題樣式
│       │       └── theme.py
│       │
│       └── utils/                # 共用工具
│           ├── __init__.py
│           ├── memory.py         # 記憶體管理工具
│           ├── logging.py        # 日誌配置
│           ├── rust_bridge.py    # Rust 安全呼叫包裝層
│           └── tw_calendar.py    # 台股交易日曆
│
├── rust/                         # Rust 工作區
│   ├── Cargo.toml                # Workspace Cargo.toml
│   ├── twquant-core/             # 核心運算 crate
│   │   ├── Cargo.toml
│   │   └── src/
│   │       ├── lib.rs            # PyO3 模組入口
│   │       ├── errors.rs         # 錯誤型別定義（Rust → Python 映射）
│   │       ├── validation.rs     # 輸入驗證守衛
│   │       ├── indicators/       # 高速指標計算
│   │       │   ├── mod.rs
│   │       │   └── custom_denoise.rs  # 範例：自訂降噪演算法
│   │       ├── signals/          # 訊號產生器
│   │       │   ├── mod.rs
│   │       │   └── signal_engine.rs
│   │       └── arrow_bridge.rs   # Arrow 零拷貝橋接
│   │
│   └── twquant-ml/               # 機器學習推論 crate（未來）
│       ├── Cargo.toml
│       └── src/
│           └── lib.rs
│
├── tests/                        # 測試
│   ├── python/
│   │   ├── test_data_pipeline.py
│   │   ├── test_sync_engine.py       # 全市場同步、HWM、斷點續傳
│   │   ├── test_sanity_checker.py    # 資料合理性過濾
│   │   ├── test_ex_dividend.py       # 除權息假跌破過濾
│   │   ├── test_indicators.py
│   │   ├── test_backtest_engine.py
│   │   ├── test_cost_model.py
│   │   └── test_rust_bridge.py       # 含型別安全、NaN/Inf 防護測試
│   └── rust/
│       └── (Rust 測試內嵌於 src 中)
│
├── scripts/                      # 開發腳本
│   ├── seed_data.py              # 種子數據下載腳本
│   ├── scheduled_sync.py         # 排程同步腳本（供 Docker cron 使用）
│   ├── profile_memory.py         # 記憶體 Profiling 腳本
│   └── benchmark_rust.py         # Rust 模組效能基準測試
│
├── data/                         # 本地數據目錄 (gitignored)
│   ├── raw/                      # 原始下載數據
│   ├── processed/                # 處理後數據
│   └── sample/                   # 版控內的範例小數據集
│       └── twse_2330_sample.csv  # 台積電範例 K 線數據
│
└── .gitignore
```

---

## 4. 系統功能模組與實作規格

### 4.1 台股數據管線 (Data Pipeline)

#### 功能需求
- 透過 FinMind API 抓取台股日 K 線、即時報價、三大法人買賣超、融資融券等數據
- **全市場、全歷史數據同步**：首次啟動時自動下載全部上市/上櫃股票的完整歷史數據至本地資料庫
- **增量更新**：開盤期間持續更新當日數據；收盤後自動抓取當日完整數據
- **闕漏回補**：系統重啟後自動偵測資料庫中每檔股票的最後更新日期（高水位標記），僅回補缺失區間
- **斷線續抓與防重複**：API 中斷時自動重試，並透過冪等性（Idempotent）寫入機制防止重複儲存
- 數據清洗：處理除權息調整、停牌日缺值、時間戳對齊
- 儲存至 ArcticDB，支援版本化查詢

#### 4.1.1 全市場數據同步引擎 (Market Data Sync Engine)

本子模組是量化回測可靠性的基石。沒有「全市場、全歷史」的本地數據，任何回測結果都存在倖存者偏差。

**核心概念：高水位標記 (High-Water Mark, HWM)**

每檔股票在本地資料庫中維護一個 metadata 記錄，記載該股票各資料集的最後成功同步日期。每次同步只抓取 HWM 之後的數據，避免重複抓取。

```python
# src/twquant/data/sync_engine.py

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
import asyncio
from loguru import logger

class SyncStatus(Enum):
    NEVER_SYNCED = "never_synced"      # 從未同步過
    PARTIAL = "partial"                 # 部分同步（中途中斷）
    UP_TO_DATE = "up_to_date"          # 已是最新
    STALE = "stale"                     # 有闕漏需回補

@dataclass
class SyncMetadata:
    """每檔股票的同步狀態 metadata"""
    stock_id: str
    dataset: str                        # e.g., "daily_price", "institutional"
    last_synced_date: date | None       # 高水位標記（HWM）
    last_sync_attempt: datetime | None  # 最後一次嘗試同步的時間
    status: SyncStatus
    error_count: int = 0                # 連續失敗次數（用於退避策略）

class MarketDataSyncEngine:
    """全市場數據同步引擎"""
    
    def __init__(self, provider, storage, config):
        self.provider = provider       # FinMind 適配器
        self.storage = storage         # ArcticDB 儲存層
        self.config = config
        self._metadata_store = {}      # stock_id -> SyncMetadata
    
    # ─── 全市場首次初始化 ───
    async def initial_full_sync(self, start_date: str = "2010-01-01"):
        """
        首次啟動：下載全部上市/上櫃股票的完整歷史數據。
        
        流程：
        1. 從 FinMind 取得全部股票清單 (taiwan_stock_info)
        2. 依產業別分批，每批 20 檔，間隔休息以尊重 API 速率限制
        3. 每完成一檔就更新 HWM，即使中途中斷也能從上次斷點續傳
        4. 使用 Streamlit 進度條回報進度
        
        預估時間（全市場約 2000 檔，600 req/hr）：
        - 日K線：約 3-4 小時
        - 含法人+融資融券：約 10-12 小時
        """
        stock_list = await self.provider.fetch_stock_list()
        total = len(stock_list)
        
        for i, stock_id in enumerate(stock_list):
            meta = self._get_metadata(stock_id, "daily_price")
            
            if meta.status == SyncStatus.UP_TO_DATE:
                continue  # 已同步，跳過（支援斷點續傳）
            
            hwm = meta.last_synced_date or start_date
            try:
                df = await self._fetch_with_retry(stock_id, hwm)
                await self._write_idempotent(stock_id, "daily_price", df)
                self._update_hwm(stock_id, "daily_price", df['date'].max())
            except Exception as e:
                self._record_failure(stock_id, "daily_price", e)
                logger.warning(f"[{stock_id}] 同步失敗，將在下次重試: {e}")
            
            yield (i + 1, total, stock_id)  # 供進度條使用
    
    # ─── 增量更新（每日排程 / 開盤期間） ───
    async def incremental_sync(self):
        """
        增量更新：僅抓取每檔股票 HWM 之後的新數據。
        
        觸發時機：
        - 交易日收盤後自動執行（建議 14:00 後）
        - 使用者手動觸發「更新數據」按鈕
        """
        stock_list = await self._get_stale_stocks()
        today = date.today()
        
        for stock_id in stock_list:
            meta = self._get_metadata(stock_id, "daily_price")
            hwm = meta.last_synced_date
            
            if hwm and hwm >= today:
                continue  # 已是最新
            
            start = (hwm + timedelta(days=1)).isoformat() if hwm else "2010-01-01"
            df = await self._fetch_with_retry(stock_id, start)
            
            if df is not None and len(df) > 0:
                await self._write_idempotent(stock_id, "daily_price", df)
                self._update_hwm(stock_id, "daily_price", df['date'].max())
    
    # ─── 闕漏偵測與自動回補 ───
    async def detect_and_fill_gaps(self):
        """
        偵測資料庫中的日期空洞並自動回補。
        
        邏輯：
        1. 取得台股交易日曆
        2. 比對每檔股票在本地資料庫中的日期列表
        3. 找出缺失的交易日，逐段回補
        """
        trading_days = await self.provider.fetch_trading_calendar()
        all_stocks = self.storage.list_symbols()
        
        for stock_id in all_stocks:
            local_dates = set(self.storage.get_dates(stock_id))
            expected_dates = set(trading_days)
            missing = sorted(expected_dates - local_dates)
            
            if missing:
                # 將缺失日期合併為連續區間，減少 API 呼叫次數
                ranges = self._merge_date_ranges(missing)
                for start, end in ranges:
                    df = await self._fetch_with_retry(stock_id, start, end)
                    if df is not None and len(df) > 0:
                        await self._write_idempotent(stock_id, "daily_price", df)
    
    # ─── API 中斷重試機制 ───
    async def _fetch_with_retry(self, stock_id: str, start_date: str, 
                                 end_date: str = None, max_retries: int = 3) -> pd.DataFrame:
        """
        帶指數退避的重試機制。
        
        策略：
        - 第 1 次重試：等待 2 秒
        - 第 2 次重試：等待 4 秒
        - 第 3 次重試：等待 8 秒
        - 超過 max_retries：記錄失敗，留待下次同步
        
        HTTP 429 (Rate Limit)：額外等待 60 秒
        HTTP 5xx (Server Error)：執行標準退避
        其他錯誤：立即記錄，不重試
        """
        for attempt in range(max_retries):
            try:
                return await self.provider.fetch(stock_id, start_date, end_date)
            except RateLimitError:
                wait = 60  # API 限流，等待 1 分鐘
                logger.info(f"[{stock_id}] API 限流，等待 {wait}s...")
                await asyncio.sleep(wait)
            except ServerError:
                wait = 2 ** (attempt + 1)  # 指數退避
                logger.warning(f"[{stock_id}] 伺服器錯誤，第 {attempt+1} 次重試，等待 {wait}s")
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"[{stock_id}] 不可重試的錯誤: {e}")
                raise
        
        logger.error(f"[{stock_id}] 達到最大重試次數 {max_retries}，放棄本次同步")
        return None
    
    # ─── 冪等寫入（防止重複數據） ───
    async def _write_idempotent(self, stock_id: str, dataset: str, df: pd.DataFrame):
        """
        冪等性寫入：以 (stock_id, date) 為唯一鍵，
        若資料庫中已存在相同日期的記錄，則以新數據覆蓋（upsert 語義）。
        
        實作方式：
        - ArcticDB：使用 update() 而非 append()，按日期範圍覆蓋
        - SQLite：使用 INSERT OR REPLACE
        """
        if df is None or df.empty:
            return
        
        df = df.drop_duplicates(subset=['date', 'stock_id'], keep='last')
        self.storage.upsert(f"{dataset}/{stock_id}", df, date_column='date')
```

**同步排程配置：**

```python
# config.py 中的同步排程配置
SYNC_CONFIG = {
    "datasets_to_sync": [
        {"name": "daily_price", "method": "taiwan_stock_daily", "priority": 1},
        {"name": "institutional", "method": "taiwan_stock_institutional_investors", "priority": 2},
        {"name": "margin", "method": "taiwan_stock_margin_purchase_short_sale", "priority": 3},
        {"name": "revenue", "method": "taiwan_stock_month_revenue", "priority": 4},
    ],
    "batch_size": 20,                   # 每批處理股票數
    "inter_batch_delay_sec": 6,         # 批次間等待秒數（尊重 600/hr 限制）
    "max_concurrent_requests": 5,       # 最大並發數
    "full_sync_start_date": "2010-01-01",  # 全歷史起始日
    "auto_sync_after_close": True,      # 收盤後自動同步
    "auto_sync_time": "14:30",          # 自動同步觸發時間
}
```

**儲存層 upsert 介面：**

```python
# storage.py 需新增 upsert 方法
class DataStorage(ABC):
    @abstractmethod
    def upsert(self, symbol: str, df: pd.DataFrame, date_column: str):
        """冪等寫入：以 date_column 為鍵，存在則覆蓋，不存在則插入"""
        pass
    
    @abstractmethod
    def get_hwm(self, symbol: str) -> date | None:
        """取得該 symbol 的高水位標記（最後一筆資料日期）"""
        pass
    
    @abstractmethod
    def get_dates(self, symbol: str) -> list[date]:
        """取得該 symbol 在本地資料庫中的所有日期列表（用於闕漏偵測）"""
        pass
    
    @abstractmethod
    def list_symbols(self) -> list[str]:
        """列出資料庫中所有已儲存的 symbol"""
        pass
```

#### AI 實作指引

**台股數據源整合（FinMind）：**
```python
# 使用 FinMind SDK 取得台積電日K線
from FinMind.data import DataLoader
dl = DataLoader()
dl.login_by_token(api_token='YOUR_TOKEN')  # 提高 API 上限至 600/hr

# 日K線
df_price = dl.taiwan_stock_daily(
    stock_id='2330', start_date='2020-01-01', end_date='2026-04-30'
)

# 三大法人買賣超
df_inst = dl.taiwan_stock_institutional_investors(
    stock_id='2330', start_date='2020-01-01'
)

# 融資融券
df_margin = dl.taiwan_stock_margin_purchase_short_sale(
    stock_id='2330', start_date='2020-01-01'
)

# 月營收
df_revenue = dl.taiwan_stock_month_revenue(
    stock_id='2330', start_date='2020-01-01'
)
```

**FinMind 可用資料集清單（台股相關）：**

| 資料集名稱 | SDK 方法 | 說明 |
|-----------|---------|------|
| TaiwanStockPrice | `taiwan_stock_daily()` | 日 K 線（開高低收量） |
| TaiwanStockInfo | `taiwan_stock_info()` | 股票基本資料 |
| TaiwanStockInstitutionalInvestorsBuySell | `taiwan_stock_institutional_investors()` | 三大法人買賣超 |
| TaiwanStockMarginPurchaseShortSale | `taiwan_stock_margin_purchase_short_sale()` | 融資融券 |
| TaiwanStockHoldingSharesPer | `taiwan_stock_holding_shares_per()` | 股權分散表 |
| TaiwanStockFinancialStatements | `taiwan_stock_financial_statement()` | 綜合損益表 |
| TaiwanStockBalanceSheet | `taiwan_stock_balance_sheet()` | 資產負債表 |
| TaiwanStockCashFlowsStatement | `taiwan_stock_cash_flows_statement()` | 現金流量表 |
| TaiwanStockMonthRevenue | `taiwan_stock_month_revenue()` | 月營收 |
| TaiwanStockDividendResult | `taiwan_stock_dividend_result()` | 除權除息結果 |
| TaiwanStockPER | `taiwan_stock_per_pbr()` | PER / PBR |
| TaiwanStockTradingDate | — | 交易日曆 |

**非同步數據抓取：**
```python
# pipeline.py 設計要點
import asyncio
import aiohttp

class TWSEDataPipeline:
    """非同步台股數據管線"""
    
    def __init__(self, provider, storage):
        self.provider = provider  # FinMind 適配器
        self.storage = storage    # ArcticDB 儲存層
    
    async def fetch_batch(self, stock_ids: list[str], start_date: str, end_date: str):
        """批次抓取多檔股票，注意 FinMind API 速率限制 (600/hr)"""
        semaphore = asyncio.Semaphore(5)  # 並發限制
        # ... 實作細節
    
    def clean_and_align(self, df):
        """數據清洗：除權息還原、缺值填補、時間戳對齊"""
        # 使用 FinMind 提供的還原股價資料集 TaiwanStockPriceAdj
        # 處理停牌日：使用前一日收盤價 forward fill
        # 時間戳統一為 Asia/Taipei 時區
        pass
```

**Streamlit 即時更新整合：**
```python
# 使用 st.fragment 避免重繪整頁
@st.fragment(run_every=60)  # 每 60 秒更新
def live_price_widget(stock_id: str):
    price = fetch_latest_price(stock_id)
    st.metric("即時價格", f"${price:.2f}")
```

#### 4.1.2 資料合理性過濾 (Data Sanity Checks)

台股數據從 API 抓取後，**必須通過以下多層檢查才能寫入本地資料庫**。未通過的紀錄應標記為 `quarantine`（隔離），而非直接丟棄，以便人工檢視。

```python
# src/twquant/data/sanity.py

import pandas as pd
import numpy as np
from dataclasses import dataclass
from loguru import logger

@dataclass
class SanityResult:
    """合理性檢查結果"""
    passed: pd.DataFrame        # 通過檢查的乾淨數據
    quarantined: pd.DataFrame   # 被隔離的可疑數據
    report: list[str]           # 檢查報告（每條異常的說明）

class TWSEDataSanityChecker:
    """台股數據合理性檢查器"""
    
    def run_all_checks(self, df: pd.DataFrame, stock_id: str) -> SanityResult:
        """依序執行所有檢查，回傳乾淨數據與被隔離的可疑數據"""
        report = []
        mask_bad = pd.Series(False, index=df.index)
        
        # ── 檢查 1：OHLC 邏輯關係 ──
        # High 必須 >= Open, Close, Low；Low 必須 <= Open, Close, High
        ohlc_invalid = (
            (df['high'] < df['open']) | (df['high'] < df['close']) |
            (df['high'] < df['low']) | (df['low'] > df['open']) |
            (df['low'] > df['close'])
        )
        if ohlc_invalid.any():
            count = ohlc_invalid.sum()
            report.append(f"[{stock_id}] {count} 筆 OHLC 邏輯關係異常 (H < L 或 H < O/C)")
            mask_bad |= ohlc_invalid
        
        # ── 檢查 2：價格非正數 ──
        price_cols = ['open', 'high', 'low', 'close']
        non_positive = (df[price_cols] <= 0).any(axis=1)
        if non_positive.any():
            count = non_positive.sum()
            report.append(f"[{stock_id}] {count} 筆價格 <= 0")
            mask_bad |= non_positive
        
        # ── 檢查 3：成交量異常 ──
        # 成交量為負數或 NaN
        vol_invalid = (df['volume'] < 0) | df['volume'].isna()
        if vol_invalid.any():
            count = vol_invalid.sum()
            report.append(f"[{stock_id}] {count} 筆成交量異常 (負數或 NaN)")
            mask_bad |= vol_invalid
        
        # ── 檢查 4：日期重複 ──
        date_dup = df.duplicated(subset=['date'], keep='last')
        if date_dup.any():
            count = date_dup.sum()
            report.append(f"[{stock_id}] {count} 筆日期重複，保留最後一筆")
            mask_bad |= date_dup
        
        # ── 檢查 5：單日漲跌幅超過合理範圍 ──
        # 台股漲跌幅限制 ±10%，但除權息日可能超過此範圍
        # 此處先標記超過 ±11% 的（留 1% 容差給除權息日判斷）
        if len(df) > 1:
            pct_change = df['close'].pct_change()
            extreme_move = pct_change.abs() > 0.11
            if extreme_move.any():
                count = extreme_move.sum()
                report.append(f"[{stock_id}] {count} 筆單日漲跌幅超過 ±11%，需進一步確認是否為除權息")
                # 不直接隔離，留給除權息過濾器處理
        
        # ── 檢查 6：NaN / Inf 值 ──
        has_nan = df[price_cols + ['volume']].isna().any(axis=1)
        has_inf = np.isinf(df[price_cols].select_dtypes(include=[np.number])).any(axis=1)
        null_inf = has_nan | has_inf
        if null_inf.any():
            count = null_inf.sum()
            report.append(f"[{stock_id}] {count} 筆含有 NaN 或 Inf")
            mask_bad |= null_inf
        
        # ── 檢查 7：日期合理性 ──
        # 日期不在 1990-01-01 ~ 今天 之間的視為異常
        df_dates = pd.to_datetime(df['date'])
        date_out_of_range = (df_dates < '1990-01-01') | (df_dates > pd.Timestamp.now())
        if date_out_of_range.any():
            count = date_out_of_range.sum()
            report.append(f"[{stock_id}] {count} 筆日期超出合理範圍")
            mask_bad |= date_out_of_range
        
        passed = df[~mask_bad].copy()
        quarantined = df[mask_bad].copy()
        
        if report:
            for msg in report:
                logger.warning(msg)
        
        return SanityResult(passed=passed, quarantined=quarantined, report=report)
```

#### 4.1.3 除權息假跌破過濾 (Ex-Dividend False Signal Filter)

這是台股回測中**最容易被忽略、卻會嚴重扭曲回測結果的問題**。

台股除權息日（Ex-Dividend Date）當天，股價會因配息/配股而被交易所強制調降開盤參考價。例如某股票前一日收盤 100 元，配息 5 元，除息日開盤參考價為 95 元。若不處理，技術指標會將此視為「暴跌 5%」，產生假的賣出訊號。

```python
# src/twquant/data/ex_dividend_filter.py

import pandas as pd
import numpy as np
from loguru import logger

class ExDividendFilter:
    """
    除權息假跌破過濾器
    
    解決的問題：
    1. 除息日股價缺口被技術指標誤判為跌破支撐
    2. MA/MACD/RSI 等指標在除權息日產生假訊號
    3. 回測報酬率因未還原股價而失真
    
    處理策略（三選一，可配置）：
    A. 前復權 (Forward Adjust)：調整歷史價格，使除權息日無缺口（預設）
    B. 後復權 (Backward Adjust)：調整除權息後的價格
    C. 訊號遮罩 (Signal Mask)：在除權息日前後 N 日內抑制交易訊號
    """
    
    def __init__(self, provider):
        self.provider = provider  # 用於取得除權息資料
        self._dividend_cache = {}
    
    async def load_dividend_calendar(self, stock_id: str, start_date: str) -> pd.DataFrame:
        """
        取得除權息日曆
        使用 FinMind TaiwanStockDividendResult 資料集
        
        回傳 DataFrame 欄位：
        - date: 除權息交易日
        - stock_id: 股票代碼
        - cash_dividend: 現金股利（元/股）
        - stock_dividend: 股票股利（元/股，需換算為配股比例）
        """
        df = await self.provider.fetch_dividend_result(stock_id, start_date)
        self._dividend_cache[stock_id] = df
        return df
    
    def forward_adjust_prices(self, price_df: pd.DataFrame, 
                               dividend_df: pd.DataFrame) -> pd.DataFrame:
        """
        前復權處理（推薦用於回測）
        
        從最新日期往回調整，使得最新價格不變，歷史價格被調降。
        這樣回測結果更接近「如果當時持有到現在」的真實報酬。
        
        調整公式：
        - 除息：adjusted_price = price - cumulative_cash_dividend_after
        - 除權：adjusted_price = price / (1 + cumulative_stock_ratio_after)
        - 複合：adjusted_price = (price - cash) / (1 + stock_ratio)
        """
        df = price_df.copy()
        
        # 反向累積除權息因子（從最新到最舊）
        adj_factor = pd.Series(1.0, index=df.index)
        
        for _, div_row in dividend_df.iterrows():
            ex_date = div_row['date']
            cash = div_row.get('cash_dividend', 0) or 0
            stock_ratio = div_row.get('stock_dividend', 0) or 0
            stock_ratio = stock_ratio / 10  # 台股股票股利以「元」計，10元 = 1股
            
            # 除權息日之前的所有價格都需要調整
            mask_before = df['date'] < ex_date
            
            if cash > 0 or stock_ratio > 0:
                # 計算除權息參考價因子
                factor = (1 + stock_ratio)
                df.loc[mask_before, 'close'] = (df.loc[mask_before, 'close'] - cash) / factor
                df.loc[mask_before, 'open'] = (df.loc[mask_before, 'open'] - cash) / factor
                df.loc[mask_before, 'high'] = (df.loc[mask_before, 'high'] - cash) / factor
                df.loc[mask_before, 'low'] = (df.loc[mask_before, 'low'] - cash) / factor
                # 成交量反向調整（除權後股數增加）
                df.loc[mask_before, 'volume'] = df.loc[mask_before, 'volume'] * factor
        
        return df
    
    def generate_signal_mask(self, price_df: pd.DataFrame, 
                              dividend_df: pd.DataFrame,
                              suppress_days_before: int = 1,
                              suppress_days_after: int = 2) -> np.ndarray:
        """
        產生訊號遮罩：在除權息日前後抑制交易訊號
        
        用途：即使使用還原股價，除權息日附近的指標仍可能不穩定。
        此遮罩可直接 AND 到策略的 entries/exits 陣列上。
        
        Parameters:
            suppress_days_before: 除權息日前幾個交易日抑制訊號
            suppress_days_after: 除權息日後幾個交易日抑制訊號
        
        Returns:
            bool array，True = 允許交易，False = 抑制訊號
        """
        mask = np.ones(len(price_df), dtype=bool)  # 預設全部允許
        dates = pd.to_datetime(price_df['date'])
        
        for _, div_row in dividend_df.iterrows():
            ex_date = pd.to_datetime(div_row['date'])
            suppress_start = ex_date - pd.Timedelta(days=suppress_days_before * 2)  # 粗略估計，含非交易日
            suppress_end = ex_date + pd.Timedelta(days=suppress_days_after * 2)
            
            mask &= ~((dates >= suppress_start) & (dates <= suppress_end))
        
        return mask
    
    def detect_false_breakdowns(self, price_df: pd.DataFrame,
                                 dividend_df: pd.DataFrame) -> pd.DataFrame:
        """
        偵測並標記除權息造成的假跌破事件
        
        回傳 DataFrame 標註哪些日期的價格缺口是除權息造成的，
        而非真正的市場下跌。供策略開發者參考。
        """
        ex_dates = set(pd.to_datetime(dividend_df['date']).dt.date)
        
        events = []
        for i in range(1, len(price_df)):
            curr_date = pd.to_datetime(price_df.iloc[i]['date']).date()
            if curr_date in ex_dates:
                prev_close = price_df.iloc[i-1]['close']
                curr_open = price_df.iloc[i]['open']
                gap_pct = (curr_open - prev_close) / prev_close
                
                div_info = dividend_df[
                    pd.to_datetime(dividend_df['date']).dt.date == curr_date
                ].iloc[0]
                
                events.append({
                    'date': curr_date,
                    'prev_close': prev_close,
                    'ex_open': curr_open,
                    'gap_pct': gap_pct,
                    'cash_dividend': div_info.get('cash_dividend', 0),
                    'stock_dividend': div_info.get('stock_dividend', 0),
                    'is_false_breakdown': True,
                })
        
        return pd.DataFrame(events) if events else pd.DataFrame()
```

**在策略基底類別中整合除權息過濾：**

```python
# base.py 中 BaseStrategy 需新增的方法
class BaseStrategy(ABC):
    # ... 原有方法 ...
    
    def apply_ex_dividend_mask(self, entries: np.ndarray, exits: np.ndarray,
                                mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        將除權息遮罩套用到進出場訊號上。
        在除權息日前後抑制所有訊號，避免假跌破觸發錯誤交易。
        """
        return entries & mask, exits & mask
```

**回測引擎中的整合點：**

回測前必須選擇以下其一（在 Streamlit 設定頁面中暴露為選項）：
1. **前復權模式**（預設）：使用還原股價進行回測，報酬率最準確
2. **原始價格 + 訊號遮罩模式**：保留原始價格，但在除權息日前後抑制訊號
3. **原始價格模式**（不推薦）：不做任何處理，僅用於對比驗證

### 4.2 台股交易成本模型 (Cost Model)

此模組是本系統最重要的台股特化元件，確保回測結果貼近真實交易。

#### 台灣股市交易規則常數

```python
# constants.py
from dataclasses import dataclass
from decimal import Decimal

@dataclass(frozen=True)
class TWSEConstants:
    """台灣證券交易所交易規則常數"""
    
    # 手續費
    BROKER_FEE_RATE: Decimal = Decimal("0.001425")   # 0.1425%，買賣各一次
    BROKER_FEE_DISCOUNT: Decimal = Decimal("0.6")     # 預設六折（可調整）
    BROKER_FEE_MIN: int = 20                           # 整股最低 20 元
    BROKER_FEE_MIN_ODD_LOT: int = 1                    # 零股最低 1 元（部分券商）
    
    # 證券交易稅（僅賣出時課徵）
    STOCK_TAX_RATE: Decimal = Decimal("0.003")         # 股票 0.3%
    ETF_TAX_RATE: Decimal = Decimal("0.001")           # ETF 0.1%
    DAY_TRADE_TAX_RATE: Decimal = Decimal("0.0015")    # 當沖 0.15%（優惠至 2027 年底）
    BOND_ETF_TAX_RATE: Decimal = Decimal("0")          # 債券 ETF 免稅（至 2026 年底）
    
    # 漲跌幅限制
    PRICE_LIMIT_PCT: Decimal = Decimal("0.10")         # ±10%
    
    # 交易單位
    BOARD_LOT_SIZE: int = 1000                          # 1 張 = 1000 股
    
    # 交割
    SETTLEMENT_DAYS: int = 2                            # T+2 交割
    
    # 交易時間
    MARKET_OPEN: str = "09:00"
    MARKET_CLOSE: str = "13:30"
    ODD_LOT_START: str = "09:00"                        # 盤中零股
    ODD_LOT_MATCH_INTERVAL: int = 3                     # 每 3 分鐘撮合一次
    AFTER_HOUR_ODD_LOT: str = "14:00-14:30"            # 盤後零股

    # 台股特有的升降單位（Tick Size）
    TICK_SIZE_TABLE: dict = {
        (0, 10): Decimal("0.01"),
        (10, 50): Decimal("0.05"),
        (50, 100): Decimal("0.1"),
        (100, 500): Decimal("0.5"),
        (500, 1000): Decimal("1"),
        (1000, float('inf')): Decimal("5"),
    }
```

#### VectorBT 整合的交易成本函數

```python
# cost_model.py
import numpy as np

def tw_stock_fees(size: np.ndarray, price: np.ndarray, 
                  broker_discount: float = 0.6,
                  is_etf: bool = False) -> np.ndarray:
    """
    計算台股真實交易成本（供 VectorBT 使用）
    
    買入成本：成交金額 × 0.1425% × 折扣
    賣出成本：成交金額 × 0.1425% × 折扣 + 成交金額 × 證交稅率
    
    Parameters:
        size: 交易股數（正=買入，負=賣出）
        price: 成交價格
        broker_discount: 券商手續費折扣（預設六折）
        is_etf: 是否為 ETF（影響證交稅率）
    """
    trade_value = np.abs(size * price)
    broker_fee = trade_value * 0.001425 * broker_discount
    broker_fee = np.maximum(broker_fee, 20)  # 最低 20 元
    
    # 證交稅僅在賣出時收取
    tax_rate = 0.001 if is_etf else 0.003
    sell_tax = np.where(size < 0, trade_value * tax_rate, 0)
    
    return broker_fee + sell_tax
```

### 4.3 策略模組 (Strategy Builder)

#### 內建策略清單

| 策略名稱 | 類型 | 進場條件 | 出場條件 |
|---------|------|---------|---------|
| 雙均線交叉 (MA Crossover) | 趨勢追蹤 | 短均線上穿長均線 | 短均線下穿長均線 |
| MACD 背離 | 動量 | MACD 柱狀體由負轉正 | MACD 柱狀體由正轉負 |
| RSI 超買超賣 | 均值回歸 | RSI < 30 | RSI > 70 |
| 布林通道突破 | 波動率 | 價格突破下軌 | 價格觸及上軌 |
| 法人買超跟隨 | 台股籌碼面 | 外資連續買超 N 日 | 外資轉賣超 |
| 融資減碼 | 台股籌碼面 | 融資餘額連降 + 股價築底 | 融資餘額回升 |

#### 策略抽象介面設計

```python
# base.py
from abc import ABC, abstractmethod
import numpy as np
import pandas as pd

class BaseStrategy(ABC):
    """策略抽象基底類別"""
    
    name: str = "Unnamed Strategy"
    description: str = ""
    
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """
        產生進出場訊號
        
        Parameters:
            data: OHLCV DataFrame，需包含 open/high/low/close/volume 欄位
        
        Returns:
            (entries, exits): 布林陣列，True 表示該日進場/出場
        """
        pass
    
    def get_parameters(self) -> dict:
        """回傳策略可調參數及其預設值"""
        return {}
    
    def validate_data(self, data: pd.DataFrame) -> bool:
        """驗證輸入數據是否符合策略需求"""
        required_cols = {'open', 'high', 'low', 'close', 'volume'}
        return required_cols.issubset(set(data.columns))
```

#### Rust 端策略模組（閉源邏輯範例）

```rust
// rust/twquant-core/src/signals/signal_engine.rs
use numpy::ndarray::Array1;
use numpy::{IntoPyArray, PyArray1, PyReadonlyArray1};
use pyo3::prelude::*;

/// 接收 NumPy array，回傳買賣訊號
#[pyfunction]
fn compute_custom_signal<'py>(
    py: Python<'py>,
    close: PyReadonlyArray1<'py, f64>,
    volume: PyReadonlyArray1<'py, f64>,
    window: usize,
) -> PyResult<&'py PyArray1<f64>> {
    let close = close.as_array();
    let volume = volume.as_array();
    let n = close.len();
    
    // 私有策略邏輯：自訂降噪 + 量價背離偵測
    let mut signals = Array1::<f64>::zeros(n);
    
    // ... 核心運算邏輯（此處為閉源黑盒）
    
    Ok(signals.into_pyarray(py))
}

#[pymodule]
fn twquant_core(_py: Python, m: &PyModule) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(compute_custom_signal, m)?)?;
    Ok(())
}
```

### 4.4 回測引擎 (Backtesting Engine)

#### VectorBT 封裝

```python
# engine.py
import vectorbt as vbt
import pandas as pd
import numpy as np
import gc

class TWSEBacktestEngine:
    """台股回測引擎，封裝 VectorBT 並加入台股交易規則"""
    
    def __init__(self, config: dict):
        self.config = config
        self._portfolio = None
    
    def run(self, price: pd.Series, entries: np.ndarray, exits: np.ndarray,
            init_cash: float = 1_000_000,
            broker_discount: float = 0.6,
            slippage: float = 0.001) -> dict:
        """
        執行回測
        
        成功標準：
        1. 回傳包含所有績效指標的 dict
        2. Portfolio 物件使用完畢後被正確釋放
        3. 交易成本準確反映台股規則
        """
        # 台股交易成本
        fees = 0.001425 * broker_discount  # 單邊手續費
        
        self._portfolio = vbt.Portfolio.from_signals(
            close=price,
            entries=entries,
            exits=exits,
            init_cash=init_cash,
            fees=fees,              # VectorBT 內建手續費（單邊）
            slippage=slippage,
            freq='1D',
        )
        
        result = self._extract_metrics()
        self._cleanup()
        return result
    
    def _extract_metrics(self) -> dict:
        """擷取績效指標"""
        pf = self._portfolio
        return {
            "total_return": pf.total_return(),
            "max_drawdown": pf.max_drawdown(),
            "sharpe_ratio": pf.sharpe_ratio(),
            "sortino_ratio": pf.sortino_ratio(),
            "calmar_ratio": pf.calmar_ratio(),
            "win_rate": pf.trades.win_rate(),
            "profit_factor": pf.trades.profit_factor(),
            "total_trades": pf.trades.count(),
            "avg_trade_duration": pf.trades.duration.mean(),
            "equity_curve": pf.value().to_dict(),
        }
    
    def _cleanup(self):
        """顯式釋放記憶體"""
        if self._portfolio is not None:
            del self._portfolio
            self._portfolio = None
            gc.collect()
```

#### 基準對比 (Benchmark)

```python
# benchmark.py
# 台股常用基準指數
BENCHMARKS = {
    "TAIEX": {
        "name": "加權股價指數",
        "finmind_dataset": "TaiwanStockTotalReturnIndex",
        "description": "台灣加權股價報酬指數"
    },
    "0050": {
        "name": "元大台灣50 ETF",
        "stock_id": "0050",
        "description": "台灣市值前50大公司 ETF"
    },
    "006208": {
        "name": "富邦台50 ETF",
        "stock_id": "006208",
        "description": "台灣市值前50大公司 ETF（內扣費用較低）"
    }
}
```

#### 績效報告產出指標

| 指標類別 | 指標名稱 | 說明 |
|---------|---------|------|
| 報酬 | 累積報酬率 (Total Return) | 策略總報酬率 |
| 報酬 | 年化報酬率 (CAGR) | 幾何平均年化報酬 |
| 報酬 | Alpha | 相對於基準的超額報酬 |
| 風險 | 最大回撤 (Max Drawdown) | 最大資金縮水幅度 |
| 風險 | 波動率 (Volatility) | 年化標準差 |
| 風險 | Beta | 與基準的系統性風險 |
| 風險調整 | 夏普率 (Sharpe Ratio) | 風險調整後報酬（無風險利率使用台灣定存利率） |
| 風險調整 | Sortino Ratio | 僅計算下行風險的調整報酬 |
| 風險調整 | Calmar Ratio | 年化報酬 / 最大回撤 |
| 交易 | 勝率 (Win Rate) | 獲利交易 / 總交易次數 |
| 交易 | 盈虧比 (Profit Factor) | 總獲利 / 總虧損 |
| 交易 | 平均持有天數 | 每筆交易平均持有時間 |
| 台股特有 | 含稅報酬率 | 扣除證交稅後的淨報酬 |
| 台股特有 | 手續費累計 | 全期間手續費總額 |

### 4.5 視覺化儀表板 (Dashboard)

#### 頁面配置

**Page 1 - 市場總覽：**
- 加權指數走勢（日/週/月切換）
- 外資買超排行 Top 20
- 融資融券變化表
- 類股漲跌幅熱力圖

**Page 2 - 個股分析：**
- K 線圖（Candlestick）+ 均線疊加
- 副圖一：成交量柱狀圖
- 副圖二：MACD / RSI / KD（可切換）
- 副圖三：法人買賣超 / 融資融券（台股特有）
- 支援動態新增/移除指標圖層

**Page 3 - 策略建構器：**
- 策略選擇（下拉選單）
- 參數調整面板（滑桿 + 數值輸入）
- 即時預覽訊號標記於 K 線圖上

**Page 4 - 回測結果：**
- 資金曲線 (Equity Curve) vs 基準指數
- 績效指標卡片群
- 交易明細表（進出場價格、損益、持有天數）
- 月度報酬熱力圖
- 回撤圖 (Drawdown Chart)

**Page 5 - 系統設定：**
- API Token 管理（FinMind）
- 手續費折扣設定
- 資料庫路徑設定
- 記憶體使用量監控

#### K 線圖實作（Plotly make_subplots）

```python
# kline_chart.py
from plotly.subplots import make_subplots
import plotly.graph_objects as go

def create_tw_stock_chart(df, indicators=None, institutional=None):
    """
    建立台股分析圖表
    
    主圖：K 線 + 均線
    副圖1：成交量
    副圖2：技術指標（MACD/RSI/KD）
    副圖3：法人買賣超（台股特有）
    """
    rows = 3 if institutional is None else 4
    row_heights = [0.5, 0.15, 0.2] if rows == 3 else [0.4, 0.15, 0.2, 0.15]
    
    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=("K 線圖", "成交量", "技術指標", "法人動態")[:rows]
    )
    
    # 主圖：K 線
    fig.add_trace(go.Candlestick(
        x=df['date'], open=df['open'], high=df['high'],
        low=df['low'], close=df['close'], name='K線',
        increasing_line_color='red',    # 台股：紅漲綠跌
        decreasing_line_color='green',
    ), row=1, col=1)
    
    # 台股慣例：紅色代表上漲，綠色代表下跌
    # 這與歐美慣例相反，需特別注意
    
    return fig
```

---

## 5. 關鍵約束條件：記憶體管理與效能最佳化

### 5.1 零拷貝數據傳輸

**強制要求：** Python 與 Rust 之間的數據交換，**絕對禁止**使用低效的逐筆（Row-by-Row）轉換。

**合規實作方式：**

方式一：透過 NumPy Buffer（推薦於小型陣列）
```rust
use numpy::{PyReadonlyArray1, IntoPyArray};

#[pyfunction]
fn process_prices(py: Python, prices: PyReadonlyArray1<f64>) -> PyResult<...> {
    let arr = prices.as_array();  // 零拷貝讀取
    // ... 處理
}
```

方式二：透過 Apache Arrow（推薦於大型 DataFrame）
```rust
use arrow::array::Float64Array;
use arrow::ffi::{FFI_ArrowArray, FFI_ArrowSchema};

// 透過 Arrow C Data Interface 做零拷貝
```

**禁止的做法：**
```python
# ❌ 絕對禁止：逐筆轉換
for i in range(len(df)):
    rust_module.process_single_row(df.iloc[i].values)

# ❌ 禁止：轉換為 Python list 再傳入
rust_module.process(df['close'].tolist())
```

### 5.2 記憶體釋放與洩漏防護

**Rust 端：**
```rust
// ✅ GIL 鎖定範圍最小化
fn compute(data: &[f64]) -> Vec<f64> {
    // 純 Rust 運算，不持有 GIL
    data.iter().map(|x| x * 2.0).collect()
}

#[pyfunction]
fn py_compute(py: Python, arr: PyReadonlyArray1<f64>) -> PyResult<Py<PyArray1<f64>>> {
    let data = arr.as_slice()?;
    let result = compute(data);  // GIL 外運算
    Ok(result.into_pyarray(py).into())  // 最後才用 GIL
}
```

**Python/Streamlit 端：**
```python
# ✅ 靜態數據快取
@st.cache_data(ttl=3600, max_entries=50)
def load_historical_kline(stock_id: str, start_date: str) -> pd.DataFrame:
    """快取歷史 K 線數據，TTL=1小時"""
    return provider.fetch(stock_id, start_date)

# ✅ 限制 DataFrame 最大行數
MAX_ROWS = 500_000  # 約 2 年的分鐘線數據
def trim_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if len(df) > MAX_ROWS:
        df = df.tail(MAX_ROWS)
    return df

# ✅ 顯式記憶體釋放
def run_backtest_safely(strategy, data):
    try:
        result = engine.run(data, strategy.entries, strategy.exits)
        return result
    finally:
        del data
        gc.collect()
```

### 5.3 並發處理原則

| 任務類型 | 處理方式 | 執行位置 |
|---------|---------|---------|
| API 數據抓取 | asyncio + aiohttp | Python (I/O bound) |
| 技術指標計算 | VectorBT 內部向量化 或 Rust | VectorBT / Rust |
| 參數最佳化網格搜索 | VectorBT 內部並行 | VectorBT |
| 大型矩陣運算 | Rust 多執行緒 (rayon) | Rust |
| Streamlit 前端渲染 | st.fragment 局部更新 | Python (main thread) |

### 5.4 Rust-Python 橋接層防錯機制 (Bridge Safety)

Rust ↔ Python 的邊界是系統中最容易出現難以除錯的 segfault 或 panic 的位置。必須在此邊界建立嚴密的防護。

#### 5.4.1 錯誤型別映射 (Error Type Mapping)

Rust 的 `Result<T, E>` 必須在 PyO3 邊界被轉換為明確的 Python Exception，禁止讓 Rust panic 穿透到 Python 導致 segfault。

```rust
// rust/twquant-core/src/errors.rs

use pyo3::prelude::*;
use pyo3::exceptions;

/// 自訂錯誤型別，統一 Rust → Python 的錯誤映射
#[derive(Debug)]
pub enum TwQuantError {
    /// 輸入數據為空陣列
    EmptyInput { param_name: String },
    /// 陣列維度不匹配
    DimensionMismatch { expected: usize, got: usize, param_name: String },
    /// 數據包含 NaN 或 Inf
    InvalidFloat { position: usize, value: f64, param_name: String },
    /// 窗口大小超過數據長度
    WindowTooLarge { window: usize, data_len: usize },
    /// 內部運算錯誤
    ComputationError { message: String },
}

impl From<TwQuantError> for PyErr {
    fn from(err: TwQuantError) -> PyErr {
        match err {
            TwQuantError::EmptyInput { param_name } => {
                exceptions::PyValueError::new_err(
                    format!("輸入陣列 '{}' 不可為空", param_name)
                )
            }
            TwQuantError::DimensionMismatch { expected, got, param_name } => {
                exceptions::PyValueError::new_err(
                    format!("陣列 '{}' 維度不匹配：預期 {} 個元素，實際 {} 個", 
                            param_name, expected, got)
                )
            }
            TwQuantError::InvalidFloat { position, value, param_name } => {
                exceptions::PyValueError::new_err(
                    format!("陣列 '{}' 在位置 {} 包含無效浮點數：{}", 
                            param_name, position, value)
                )
            }
            TwQuantError::WindowTooLarge { window, data_len } => {
                exceptions::PyValueError::new_err(
                    format!("窗口大小 ({}) 超過數據長度 ({})", window, data_len)
                )
            }
            TwQuantError::ComputationError { message } => {
                exceptions::PyRuntimeError::new_err(
                    format!("Rust 運算錯誤：{}", message)
                )
            }
        }
    }
}
```

#### 5.4.2 輸入驗證守衛 (Input Validation Guards)

每個暴露給 Python 的 `#[pyfunction]` 都必須在函數入口處進行完整的輸入驗證，不信任任何來自 Python 的數據。

```rust
// rust/twquant-core/src/validation.rs

use numpy::PyReadonlyArray1;
use pyo3::prelude::*;

/// 輸入驗證守衛：在進入核心運算前，確保所有輸入合法
pub struct InputGuard;

impl InputGuard {
    /// 驗證 1D 陣列非空且不含 NaN/Inf
    pub fn validate_f64_array(
        arr: &PyReadonlyArray1<f64>, 
        param_name: &str
    ) -> Result<(), TwQuantError> {
        let slice = arr.as_array();
        
        // 檢查空陣列
        if slice.is_empty() {
            return Err(TwQuantError::EmptyInput {
                param_name: param_name.to_string(),
            });
        }
        
        // 檢查 NaN / Inf
        for (i, &val) in slice.iter().enumerate() {
            if val.is_nan() || val.is_infinite() {
                return Err(TwQuantError::InvalidFloat {
                    position: i,
                    value: val,
                    param_name: param_name.to_string(),
                });
            }
        }
        
        Ok(())
    }
    
    /// 驗證兩個陣列維度一致
    pub fn validate_same_length(
        a: &PyReadonlyArray1<f64>,
        b: &PyReadonlyArray1<f64>,
        name_a: &str,
        name_b: &str,
    ) -> Result<(), TwQuantError> {
        if a.len() != b.len() {
            return Err(TwQuantError::DimensionMismatch {
                expected: a.len(),
                got: b.len(),
                param_name: format!("{} vs {}", name_a, name_b),
            });
        }
        Ok(())
    }
    
    /// 驗證窗口參數合理
    pub fn validate_window(
        window: usize, 
        data_len: usize
    ) -> Result<(), TwQuantError> {
        if window == 0 || window > data_len {
            return Err(TwQuantError::WindowTooLarge { window, data_len });
        }
        Ok(())
    }
}
```

#### 5.4.3 安全的 PyO3 函數模板

所有暴露給 Python 的函數必須遵循此模板：

```rust
/// 安全的 PyO3 函數模板
/// 1. 入口驗證 → 2. 提取數據 → 3. 釋放 GIL 進行運算 → 4. 重新取得 GIL 回傳結果
#[pyfunction]
fn safe_compute_indicator(
    py: Python<'_>,
    close: PyReadonlyArray1<f64>,
    volume: PyReadonlyArray1<f64>,
    window: usize,
) -> PyResult<Py<PyArray1<f64>>> {
    // ── Step 1: 入口驗證（持有 GIL，但操作極輕量） ──
    InputGuard::validate_f64_array(&close, "close")?;
    InputGuard::validate_f64_array(&volume, "volume")?;
    InputGuard::validate_same_length(&close, &volume, "close", "volume")?;
    InputGuard::validate_window(window, close.len())?;
    
    // ── Step 2: 提取為純 Rust 數據（零拷貝） ──
    let close_slice = close.as_slice()
        .map_err(|e| TwQuantError::ComputationError { 
            message: format!("無法讀取 close 陣列: {}", e) 
        })?;
    let volume_slice = volume.as_slice()
        .map_err(|e| TwQuantError::ComputationError { 
            message: format!("無法讀取 volume 陣列: {}", e) 
        })?;
    
    // ── Step 3: 釋放 GIL，進行核心運算 ──
    // 這一步讓 Python 其他執行緒可以繼續工作
    let result = py.allow_threads(|| {
        core_computation(close_slice, volume_slice, window)
    }).map_err(|e| TwQuantError::ComputationError { message: e })?;
    
    // ── Step 4: 重新取得 GIL，轉換結果為 NumPy array ──
    Ok(result.into_pyarray(py).into())
}
```

#### 5.4.4 Panic 捕獲

在 `Cargo.toml` 中設定 panic = "abort" 以外的策略，並在 PyO3 邊界使用 `catch_unwind`：

```rust
use std::panic;

#[pyfunction]
fn safe_wrapper(py: Python<'_>, /* params */) -> PyResult</* return */> {
    let result = panic::catch_unwind(|| {
        // 可能 panic 的運算
        risky_computation()
    });
    
    match result {
        Ok(Ok(val)) => Ok(val.into_pyarray(py).into()),
        Ok(Err(e)) => Err(PyErr::from(e)),
        Err(_) => Err(exceptions::PyRuntimeError::new_err(
            "Rust 內部發生不可預期的錯誤 (panic)，請回報此問題"
        )),
    }
}
```

#### 5.4.5 Python 端的安全包裝層

Python 側也必須有一層防護，確保傳入 Rust 的數據格式正確：

```python
# src/twquant/utils/rust_bridge.py

import numpy as np
from loguru import logger

def safe_call_rust(func, *arrays, **kwargs):
    """
    安全呼叫 Rust 函數的包裝器
    
    職責：
    1. 確保所有陣列是 contiguous 的 float64 NumPy array
    2. 檢查 NaN/Inf
    3. 捕獲 Rust 拋出的異常並轉換為友善錯誤訊息
    """
    cleaned_arrays = []
    for i, arr in enumerate(arrays):
        if isinstance(arr, pd.Series):
            arr = arr.to_numpy()
        
        if not isinstance(arr, np.ndarray):
            raise TypeError(f"第 {i} 個參數必須是 NumPy array，實際為 {type(arr)}")
        
        # 強制轉換為 float64 + C-contiguous
        arr = np.ascontiguousarray(arr, dtype=np.float64)
        
        # Python 側也做一次 NaN 檢查（雙重保險）
        nan_count = np.isnan(arr).sum()
        if nan_count > 0:
            logger.warning(f"第 {i} 個參數含有 {nan_count} 個 NaN，Rust 端將拒絕處理")
        
        cleaned_arrays.append(arr)
    
    try:
        return func(*cleaned_arrays, **kwargs)
    except ValueError as e:
        logger.error(f"Rust 輸入驗證失敗: {e}")
        raise
    except RuntimeError as e:
        logger.error(f"Rust 運算錯誤: {e}")
        raise
```

### 5.5 非同步進度條 (Async Progress Bar)

當執行「全市場歷史數據回補」或「多標的平行回測」等耗時任務時，必須讓使用者看到即時進度，避免誤以為系統當機。

#### 5.5.1 Streamlit 進度條整合

```python
# src/twquant/dashboard/components/progress_tracker.py

import streamlit as st
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

class TaskType(Enum):
    FULL_SYNC = "全市場數據同步"
    INCREMENTAL_SYNC = "增量數據更新"
    GAP_FILL = "闕漏數據回補"
    MULTI_BACKTEST = "多標的平行回測"
    PARAM_OPTIMIZE = "參數最佳化搜索"

@dataclass
class ProgressState:
    """進度狀態物件，跨 Streamlit rerun 保持"""
    task_type: TaskType
    total: int
    completed: int = 0
    current_item: str = ""
    errors: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.now)
    
    @property
    def pct(self) -> float:
        return self.completed / self.total if self.total > 0 else 0
    
    @property
    def eta_seconds(self) -> float:
        if self.completed == 0:
            return float('inf')
        elapsed = (datetime.now() - self.start_time).total_seconds()
        rate = self.completed / elapsed
        remaining = self.total - self.completed
        return remaining / rate if rate > 0 else float('inf')


def render_progress_bar(state: ProgressState):
    """
    渲染 Streamlit 進度條 UI
    
    顯示內容：
    1. 進度條本體（百分比）
    2. 當前處理中的項目名稱
    3. 已完成 / 總數
    4. 預估剩餘時間 (ETA)
    5. 錯誤計數（若有）
    """
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.progress(state.pct, text=f"{state.task_type.value}：{state.current_item}")
    
    with col2:
        eta = state.eta_seconds
        if eta == float('inf'):
            eta_str = "計算中..."
        elif eta > 3600:
            eta_str = f"約 {eta/3600:.1f} 小時"
        elif eta > 60:
            eta_str = f"約 {eta/60:.0f} 分鐘"
        else:
            eta_str = f"約 {eta:.0f} 秒"
        
        st.caption(f"{state.completed}/{state.total} | ETA: {eta_str}")
    
    if state.errors:
        with st.expander(f"⚠️ {len(state.errors)} 個錯誤", expanded=False):
            for err in state.errors[-10:]:  # 最多顯示最近 10 個
                st.text(err)
```

#### 5.5.2 全市場同步的進度回報

```python
# 在 Streamlit 頁面中使用進度條
async def run_full_sync_with_progress():
    """帶進度條的全市場同步"""
    
    sync_engine = MarketDataSyncEngine(provider, storage, config)
    
    # 先取得股票清單以確定總數
    stock_list = await provider.fetch_stock_list()
    state = ProgressState(
        task_type=TaskType.FULL_SYNC,
        total=len(stock_list),
    )
    
    progress_placeholder = st.empty()
    
    async for completed, total, current_stock in sync_engine.initial_full_sync():
        state.completed = completed
        state.total = total
        state.current_item = f"{current_stock}"
        
        with progress_placeholder.container():
            render_progress_bar(state)
    
    st.success(f"✅ 同步完成！共處理 {state.total} 檔股票，{len(state.errors)} 個錯誤")
```

#### 5.5.3 多標的回測的進度回報

```python
# 在回測引擎中加入進度回調
class TWSEBacktestEngine:
    def run_multi_symbol(self, symbols: list[str], strategy, 
                          progress_callback=None) -> dict:
        """
        多標的平行回測，支援進度回調
        
        Parameters:
            progress_callback: 接收 (completed, total, symbol) 的函數
        """
        results = {}
        for i, symbol in enumerate(symbols):
            price = self.storage.load(symbol)
            entries, exits = strategy.generate_signals(price)
            results[symbol] = self.run(price['close'], entries, exits)
            
            if progress_callback:
                progress_callback(i + 1, len(symbols), symbol)
        
        return results

# Streamlit 中使用
def backtest_page():
    if st.button("開始多標的回測"):
        state = ProgressState(task_type=TaskType.MULTI_BACKTEST, total=len(selected_stocks))
        progress_placeholder = st.empty()
        
        def on_progress(completed, total, symbol):
            state.completed = completed
            state.current_item = symbol
            with progress_placeholder.container():
                render_progress_bar(state)
        
        results = engine.run_multi_symbol(selected_stocks, strategy, 
                                           progress_callback=on_progress)
```

---

## 6. 開發階段劃分 (Phased Execution)

### Phase 0：專案骨架與 Claude Code 環境（預計 1-2 小時）

**目標：** 建立完整的開發環境與 CI/CD 管線。

**步驟：**

```
步驟 0.1：初始化 Git 倉庫
  → 執行：git init && git remote add origin <repo_url>
  → 驗證：git status 顯示乾淨狀態

步驟 0.2：建立 CLAUDE.md
  → 執行：將第 0.1 節的內容寫入根目錄 CLAUDE.md
  → 驗證：cat CLAUDE.md 確認內容完整

步驟 0.3：建立目錄結構
  → 執行：mkdir -p 建立第 3 節定義的所有目錄
  → 驗證：tree 命令輸出與規劃一致

步驟 0.4：初始化 Poetry 專案
  → 執行：
    cd twquant
    poetry init --name twquant --python "^3.11"
    poetry add streamlit plotly pandas numpy vectorbt
    poetry add finmind aiohttp arcticdb
    poetry add --group dev pytest pytest-asyncio mypy ruff memray
  → 驗證：poetry install 成功，poetry run python -c "import streamlit" 無錯誤

步驟 0.5：初始化 Rust Cargo workspace
  → 執行：
    cd rust
    # 建立 workspace Cargo.toml
    cargo new twquant-core --lib
    # 在 twquant-core/Cargo.toml 加入 PyO3 + maturin 依賴
  → 驗證：cd rust && cargo build 成功

步驟 0.6：建立 CI/CD
  → 執行：寫入 .github/workflows/ci.yml
  → 驗證：YAML 語法正確（可用 yamllint）

步驟 0.7：建立 .gitignore
  → 執行：加入 Python, Rust, IDE, data/ 等忽略規則
  → 驗證：git status 不顯示應被忽略的檔案

步驟 0.8：建立文件骨架
  → 執行：在 docs/ 中建立所有 .md 檔案的標題與基本結構
  → 驗證：每個文件至少包含標題和目錄大綱

步驟 0.9：提交並推送
  → 執行：git add -A && git commit -m "feat: project scaffold" && git push
  → 驗證：GitHub 上可見完整目錄結構
```

**成功標準：**
- `poetry install` 無錯誤
- `cargo build` 無錯誤
- CI workflow 語法正確
- 目錄結構與第 3 節完全一致

---

### Phase 1：PyO3 橋接與基本連通（預計 2-3 小時）

**目標：** 完成 Rust ↔ Python 跨語言通訊的最小可行驗證。

**步驟：**

```
步驟 1.1：配置 maturin
  → 執行：
    pip install maturin
    cd rust/twquant-core
    # 在 Cargo.toml 中加入：
    # [lib]
    # crate-type = ["cdylib"]
    # [dependencies]
    # pyo3 = { version = "0.21", features = ["extension-module"] }
    # numpy = "0.21"
  → 驗證：maturin develop 可成功編譯

步驟 1.2：實作最基礎的 PyO3 函數
  → 執行：在 lib.rs 中實作一個接收 NumPy array 並回傳其總和的函數
    ```rust
    #[pyfunction]
    fn array_sum(arr: PyReadonlyArray1<f64>) -> f64 {
        arr.as_array().sum()
    }
    ```
  → 驗證：
    maturin develop
    python -c "import twquant_core; print(twquant_core.array_sum([1.0, 2.0, 3.0]))"
    # 預期輸出：6.0

步驟 1.3：實作 Rust 錯誤型別與輸入驗證守衛
  → 執行：
    - rust/twquant-core/src/errors.rs（參照第 5.4.1 節）
      定義 TwQuantError enum，實作 From<TwQuantError> for PyErr
    - rust/twquant-core/src/validation.rs（參照第 5.4.2 節）
      InputGuard::validate_f64_array()、validate_same_length()、validate_window()
  → 驗證：
    - 傳入空陣列 → Python 收到 ValueError，訊息清楚
    - 傳入含 NaN 的陣列 → Python 收到 ValueError，指出 NaN 位置
    - 傳入兩個長度不同的陣列 → Python 收到 ValueError

步驟 1.4：實作 Python 端安全呼叫包裝層
  → 執行：src/twquant/utils/rust_bridge.py（參照第 5.4.5 節）
    - safe_call_rust()：自動轉換 pd.Series → np.ndarray、強制 float64 + C-contiguous
    - 雙重 NaN 檢查（Python 側 + Rust 側）
  → 驗證：
    - 傳入 pd.Series → 自動轉換並成功呼叫 Rust
    - 傳入 Python list → 拋出 TypeError

步驟 1.5：驗證零拷貝傳輸
  → 執行：撰寫效能測試，比較 Rust vs pure Python 處理 100 萬筆 float64 的時間
  → 驗證：Rust 版本快於 Python 版本至少 5x

步驟 1.6：撰寫跨語言橋接測試（含型別安全）
  → 執行：tests/python/test_rust_bridge.py
    - 測試基本數值傳輸
    - 測試大型陣列（100 萬元素）傳輸
    - 測試空陣列 → 收到明確 ValueError
    - 測試全 NaN 陣列 → 收到 ValueError 並指出 NaN 位置
    - 測試 Inf 值 → 收到 ValueError
    - 測試維度不匹配 → 收到 ValueError
    - 測試 window > data_len → 收到 ValueError
    - 測試 Rust panic 被 catch_unwind 捕獲 → Python 收到 RuntimeError（而非 segfault）
    - 測試傳入非 float64 型別（int32, string）→ 收到 TypeError
  → 驗證：pytest tests/python/test_rust_bridge.py 全部通過

步驟 1.7：提交
  → 執行：git add -A && git commit -m "feat: PyO3 bridge with zero-copy, type safety, error mapping" && git push
  → 驗證：CI 通過
```

**成功標準：**
- `maturin develop` 無錯誤
- Python 可成功 `import twquant_core` 並呼叫 Rust 函數
- 100 萬元素的 NumPy array 可在 < 1ms 內跨語言傳輸
- 所有邊界輸入（空陣列、NaN、Inf、維度不匹配）都產生明確的 Python Exception 而非 segfault
- Rust panic 被安全捕獲為 Python RuntimeError
- 所有跨語言測試通過

---

### Phase 2：台股數據管線與基礎視覺化（預計 4-6 小時）

**目標：** 串接 FinMind API 取得台股數據，建立 Streamlit 基礎面板，畫出支援縮放的 K 線圖。

**步驟：**

```
步驟 2.1：實作台股交易規則常數模組
  → 執行：建立 src/twquant/constants.py（參照第 4.2 節）
  → 驗證：所有常數可被正確匯入，數值與台灣證交所規則一致

步驟 2.2：建立範例數據集
  → 執行：
    - 準備 data/sample/twse_2330_sample.csv（台積電近 2 年日K線）
    - 包含欄位：date, stock_id, open, high, low, close, volume
    - 首次開發時可從 FinMind 下載後存為 CSV
  → 驗證：pd.read_csv() 可正確載入，dtypes 正確

步驟 2.3：實作 FinMind 數據源適配器
  → 執行：src/twquant/data/providers/finmind.py
    - 封裝 FinMind DataLoader
    - 實作日K線、三大法人、融資融券的取得方法
    - 加入速率限制保護（600/hr）
    - 錯誤處理：API 超限、網路錯誤、資料為空
  → 驗證：
    provider = FinMindProvider(token="...")
    df = provider.fetch_daily("2330", "2024-01-01", "2024-12-31")
    assert len(df) > 200  # 約 240 個交易日
    assert set(df.columns) >= {"date", "open", "high", "low", "close", "volume"}

步驟 2.4：實作本地 CSV 適配器（備選數據源）
  → 執行：src/twquant/data/providers/csv_local.py
  → 驗證：可讀取 data/sample/ 中的範例數據

步驟 2.5：實作數據儲存層
  → 執行：src/twquant/data/storage.py
    - ArcticDB 適配器（首選）
    - SQLite 適配器（備選，供開發環境使用）
    - 統一介面：save(symbol, df) / load(symbol, start, end)
  → 驗證：存入再讀出的 DataFrame 與原始一致（dtypes, 數值）

步驟 2.6：實作台股交易日曆
  → 執行：src/twquant/utils/tw_calendar.py
    - 排除六日、國定假日（春節、清明、中秋等）
    - 可透過 FinMind TaiwanStockTradingDate 資料集取得
  → 驗證：is_trading_day("2026-01-01") == False（元旦非交易日）

步驟 2.7：實作全市場數據同步引擎
  → 執行：src/twquant/data/sync_engine.py（參照第 4.1.1 節）
    - HWM 高水位標記機制
    - initial_full_sync()：首次全市場同步（async generator 支援進度回報）
    - incremental_sync()：增量更新
    - detect_and_fill_gaps()：闕漏偵測與回補
    - _fetch_with_retry()：指數退避重試 + HTTP 429 處理
    - _write_idempotent()：冪等寫入（upsert 語義）
  → 驗證：
    - 同步 10 檔股票後中斷，重啟後只抓取未完成的部分
    - 模擬 API 限流 (429)，確認自動等待後重試
    - 故意插入重複數據，確認 upsert 不產生重複行

步驟 2.8：實作資料合理性過濾器
  → 執行：src/twquant/data/sanity.py（參照第 4.1.2 節）
    - 7 項 OHLCV 合理性檢查
    - 可疑數據隔離（quarantine）而非丟棄
  → 驗證：
    - 傳入 High < Low 的假數據 → 被隔離
    - 傳入含 NaN 的數據 → 被隔離
    - 正常數據 → 全部通過

步驟 2.9：實作除權息假跌破過濾器
  → 執行：src/twquant/data/ex_dividend_filter.py（參照第 4.1.3 節）
    - forward_adjust_prices()：前復權
    - generate_signal_mask()：除權息日訊號遮罩
    - detect_false_breakdowns()：假跌破偵測報告
  → 驗證：
    - 取得台積電 2024 年除權息資料
    - 前復權後，除息日無價格跳空
    - 訊號遮罩在除息日前後正確抑制

步驟 2.10：實作進度條元件
  → 執行：src/twquant/dashboard/components/progress_tracker.py（參照第 5.5 節）
    - ProgressState 狀態物件
    - render_progress_bar() Streamlit UI
    - 包含 ETA 估算與錯誤計數
  → 驗證：模擬長任務，進度條正確顯示百分比、ETA、錯誤數

步驟 2.11：建立 Streamlit 基礎面板
  → 執行：src/twquant/dashboard/app.py + pages/
    - 側邊欄：股票代碼輸入（預設 2330）、日期範圍選擇
    - 主頁面：K 線圖 + 成交量副圖
    - 設定頁面：「全市場同步」按鈕（帶進度條）
    - 使用 @st.cache_data 快取數據
  → 驗證：streamlit run src/twquant/dashboard/app.py 可正常顯示 K 線圖

步驟 2.12：實作 K 線圖元件（台股風格）
  → 執行：src/twquant/dashboard/components/kline_chart.py
    - Plotly make_subplots，支援縮放與平移
    - 台股配色：紅漲綠跌
    - 主圖：K 線 + 5/10/20/60 日均線（可切換）
    - 副圖：成交量（漲紅跌綠著色）
  → 驗證：圖表可正常互動（縮放、Hover 顯示 OHLCV）

步驟 2.13：提交
  → 執行：git add -A && git commit -m "feat: TWSE data pipeline with sync engine, sanity checks, ex-dividend filter" && git push
  → 驗證：CI 通過
```

**成功標準：**
- FinMind API 可正常取得台積電（2330）日 K 線數據
- 全市場同步引擎可斷點續傳，API 中斷後自動重試
- 冪等寫入確保無重複數據
- 資料合理性檢查攔截異常 OHLCV 數據
- 除權息前復權後無假跌破
- 進度條在全市場同步時正確顯示 ETA
- Streamlit 面板可正常啟動並顯示互動式 K 線圖
- K 線圖使用台股慣例配色（紅漲綠跌）
- 數據可存入/讀出 ArcticDB 或 SQLite
- `@st.cache_data` 正確快取，重新整理頁面不重複抓取 API

---

### Phase 3：VectorBT 回測引擎整合（預計 4-6 小時）

**目標：** 整合 VectorBT，實作雙均線策略，產出與台灣 0050 ETF 對比的績效報告。

**步驟：**

```
步驟 3.1：實作台股交易成本模型
  → 執行：src/twquant/backtest/cost_model.py（參照第 4.2 節）
    - tw_stock_fees() 函數
    - 支援整股/零股不同最低手續費
    - 支援股票/ETF 不同證交稅率
    - 支援券商折扣參數調整
  → 驗證：
    # 買入 1 張台積電（假設 $1000）的手續費
    fee = tw_stock_fees(size=1000, price=1000, broker_discount=0.6)
    # 預期：1000 × 1000 × 0.001425 × 0.6 = 855 元
    assert abs(fee - 855) < 1

步驟 3.2：實作策略基底類別
  → 執行：src/twquant/strategy/base.py（參照第 4.3 節）
  → 驗證：子類別可正確繼承並實作 generate_signals()

步驟 3.3：實作雙均線交叉策略
  → 執行：src/twquant/strategy/builtin/ma_crossover.py
    - 參數：short_window (預設 5), long_window (預設 20)
    - 使用 VectorBT IndicatorFactory 或純 Pandas 實作
  → 驗證：
    strategy = MACrossover(short_window=5, long_window=20)
    entries, exits = strategy.generate_signals(sample_data)
    assert entries.dtype == bool
    assert entries.sum() > 0  # 確保有產生訊號

步驟 3.4：實作 VectorBT 回測引擎封裝
  → 執行：src/twquant/backtest/engine.py（參照第 4.4 節）
    - 整合台股交易成本模型
    - 記憶體安全釋放
  → 驗證：
    engine = TWSEBacktestEngine(config)
    result = engine.run(price, entries, exits)
    assert "sharpe_ratio" in result
    assert "max_drawdown" in result

步驟 3.5：實作基準對比模組
  → 執行：src/twquant/backtest/benchmark.py
    - 取得 0050 ETF 同期數據
    - 計算 Alpha / Beta
    - 產出策略 vs 基準的資金曲線
  → 驗證：Alpha/Beta 數值合理（Beta 通常在 0.5-1.5 之間）

步驟 3.6：實作績效報告
  → 執行：src/twquant/backtest/report.py
    - 產出第 4.4 節定義的所有績效指標
    - 支援 dict 輸出（供 Streamlit 使用）
    - 支援 Markdown 格式輸出（供匯出用）
  → 驗證：所有指標欄位完整，數值在合理範圍內

步驟 3.7：整合回測結果至 Streamlit
  → 執行：src/twquant/dashboard/pages/04_backtest_result.py
    - 資金曲線圖（策略 vs 0050）
    - 績效指標卡片群（使用 st.metric）
    - 月度報酬熱力圖
    - 回撤圖
  → 驗證：Streamlit 頁面可完整顯示回測結果

步驟 3.8：撰寫回測引擎測試
  → 執行：tests/python/test_backtest_engine.py
    - 測試空訊號（無交易）
    - 測試全期持有（Buy & Hold）
    - 測試交易成本計算正確性
    - 測試記憶體釋放（前後比較）
  → 驗證：所有測試通過

步驟 3.9：提交
  → 執行：git add -A && git commit -m "feat: VectorBT backtest with TWSE cost model" && git push
  → 驗證：CI 通過
```

**成功標準：**
- 雙均線策略可在台積電 2 年日K線上成功執行回測
- 交易成本精確反映台股手續費（0.1425% × 折扣）與證交稅（0.3%）
- 資金曲線可與 0050 ETF 基準對比
- 所有績效指標（Sharpe、MaxDD、Alpha、Beta 等）正確計算
- Portfolio 物件使用後記憶體被正確釋放

---

### Phase 4：Rust 策略模組整合（預計 3-4 小時）

**目標：** 用 Rust 實作一個虛擬的「私有指標邏輯」，編譯為 Python 模組，成功整合至 Streamlit 畫面與 VectorBT 回測。

**步驟：**

```
步驟 4.1：實作 Rust 自訂指標
  → 執行：rust/twquant-core/src/indicators/custom_denoise.rs
    - 實作一個簡單的降噪移動平均（如 Kalman Filter 簡化版）
    - 接收 close prices NumPy array
    - 回傳平滑後的 price array
  → 驗證：maturin develop && python -c "import twquant_core; ..."

步驟 4.2：實作 Rust 訊號引擎
  → 執行：rust/twquant-core/src/signals/signal_engine.rs
    - 基於步驟 4.1 的降噪結果產生買賣訊號
    - 回傳兩個 bool array (entries, exits)
  → 驗證：回傳的 array 維度與輸入一致

步驟 4.3：建立 Python 包裝層
  → 執行：src/twquant/strategy/builtin/rust_custom.py
    - 繼承 BaseStrategy
    - 內部呼叫 twquant_core 的 Rust 函數
    - 將 Rust 回傳的訊號轉換為 VectorBT 可用格式
  → 驗證：
    strategy = RustCustomStrategy()
    entries, exits = strategy.generate_signals(sample_data)
    assert entries.dtype == bool

步驟 4.4：整合至 Streamlit
  → 執行：
    - 在策略選擇下拉選單中加入 "Rust 自訂策略"
    - 將 Rust 計算的平滑曲線疊加至 K 線圖上
    - 回測結果頁面支援此策略
  → 驗證：Streamlit 面板可選擇 Rust 策略並顯示回測結果

步驟 4.5：效能比較測試
  → 執行：scripts/benchmark_rust.py
    - 比較同一邏輯的 Python vs Rust 實作在 10 年日K線數據上的執行時間
    - 記錄記憶體使用量
  → 驗證：Rust 版本執行速度快於 Python 版本至少 10x

步驟 4.6：提交
  → 執行：git add -A && git commit -m "feat: Rust strategy module integration" && git push
  → 驗證：CI 通過
```

**成功標準：**
- Rust 自訂指標可被 Python 正確呼叫
- 計算結果可疊加顯示於 Streamlit K 線圖上
- 訊號可輸入 VectorBT 進行回測
- 零拷貝傳輸驗證通過（無不必要的記憶體複製）
- Rust 比 Python 至少快 10x

---

### Phase 5：壓力測試與記憶體 Profiling（預計 2-3 小時）

**目標：** 確保系統在極端數據量下穩定運作，無記憶體洩漏。

**步驟：**

```
步驟 5.1：準備極端數據集
  → 執行：
    - 下載 10 年期台積電日K線（約 2400 筆）
    - 合成 100 檔股票的模擬分鐘線數據（約 5000 萬筆）
  → 驗證：數據集可被正確載入

步驟 5.2：回測壓力測試
  → 執行：
    - 對 10 年期日K線執行所有內建策略
    - 對 50 檔股票執行多標的平行回測
    - 記錄每次回測的執行時間與峰值記憶體
  → 驗證：
    - 10 年日K線單策略回測 < 5 秒
    - 50 標的平行回測 < 30 秒
    - 峰值記憶體 < 2GB

步驟 5.3：記憶體洩漏檢測
  → 執行：scripts/profile_memory.py
    - 使用 memray 或 tracemalloc
    - 連續執行 100 次回測迴圈
    - 記錄每次迴圈後的記憶體使用量
  → 驗證：記憶體使用量不隨迴圈次數線性增長（允許 < 5% 波動）

步驟 5.4：Streamlit 長時間運行測試
  → 執行：
    - 模擬使用者操作：反覆切換股票代碼、調整策略參數、重新回測
    - 執行 30 分鐘以上
  → 驗證：
    - 頁面回應時間穩定
    - 記憶體使用量穩定（不持續增長）
    - 無 Python segfault 或 Rust panic

步驟 5.5：Rust 模組穩定性測試
  → 執行：
    - 傳入邊界數據：空陣列、全 NaN、極大值、極小值
    - 多執行緒並發呼叫 Rust 函數
  → 驗證：所有情況均正常處理（回傳合理結果或拋出明確錯誤），無 segfault

步驟 5.6：產出效能報告
  → 執行：將測試結果整理為 docs/PERFORMANCE_REPORT.md
  → 驗證：報告包含具體數據與結論

步驟 5.7：最終提交
  → 執行：git add -A && git commit -m "feat: stress test and memory profiling" && git push
  → 驗證：CI 通過，所有測試綠燈
```

**成功標準：**
- 10 年日K線回測 < 5 秒
- 連續 100 次回測迴圈無記憶體洩漏
- Streamlit 30 分鐘壓力測試無崩潰
- Rust 邊界輸入測試全部通過
- 效能報告完整產出

---

## 7. 依賴清單

### Python (pyproject.toml)

```toml
[tool.poetry.dependencies]
python = "^3.11"

# 核心框架
streamlit = "^1.35"
plotly = "^5.22"

# 回測引擎
vectorbt = "^0.26"

# 台股數據
finmind = "^1.9"

# 數據處理
pandas = "^2.2"
polars = "^0.20"
numpy = "^1.26"

# 數據儲存
arcticdb = "^4.5"

# 非同步
aiohttp = "^3.9"

# 工具
python-dotenv = "^1.0"
loguru = "^0.7"

[tool.poetry.group.dev.dependencies]
pytest = "^8.0"
pytest-asyncio = "^0.23"
mypy = "^1.8"
ruff = "^0.3"
memray = "^1.11"
maturin = "^1.5"
```

### Rust (Cargo.toml)

```toml
[workspace]
members = ["twquant-core", "twquant-ml"]

[workspace.dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
numpy = "0.21"
ndarray = "0.15"
arrow = "52"
rayon = "1.10"
```

---

## 8. Docker 容器化規劃

### 8.1 多階段建構 Dockerfile

由於本專案同時包含 Python 和 Rust，Dockerfile 採用多階段建構（multi-stage build），將 Rust 編譯環境與最終運行環境分離，大幅縮小產出 image 體積。

```dockerfile
# Dockerfile

# ============================================
# Stage 1: Rust 編譯階段
# ============================================
FROM rust:1.78-bookworm AS rust-builder

# 安裝 Python 開發標頭（maturin 需要）
RUN apt-get update && apt-get install -y python3-dev python3-pip && \
    pip3 install maturin --break-system-packages

WORKDIR /build/rust

# 先複製 Cargo 設定檔，利用 Docker cache 加速依賴下載
COPY rust/Cargo.toml rust/Cargo.lock* ./
COPY rust/twquant-core/Cargo.toml twquant-core/
COPY rust/twquant-ml/Cargo.toml twquant-ml/

# 建立空的 src 以觸發依賴預編譯
RUN mkdir -p twquant-core/src && echo "// placeholder" > twquant-core/src/lib.rs && \
    mkdir -p twquant-ml/src && echo "// placeholder" > twquant-ml/src/lib.rs && \
    cargo build --release 2>/dev/null || true

# 複製完整 Rust 原始碼並正式編譯
COPY rust/ .
RUN cd twquant-core && maturin build --release --out /build/wheels

# ============================================
# Stage 2: Python 運行階段
# ============================================
FROM python:3.11-slim-bookworm AS runtime

# 安裝系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Poetry
RUN pip install poetry==1.8.0 && \
    poetry config virtualenvs.create false

WORKDIR /app

# 先複製依賴定義，利用 Docker cache
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-dev --no-root

# 安裝 Rust 編譯產出的 wheel
COPY --from=rust-builder /build/wheels/*.whl /tmp/wheels/
RUN pip install /tmp/wheels/*.whl && rm -rf /tmp/wheels

# 複製 Python 原始碼
COPY src/ src/
COPY scripts/ scripts/
COPY data/sample/ data/sample/

# 建立數據目錄
RUN mkdir -p data/raw data/processed

# 環境變數
ENV PYTHONPATH=/app/src
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# 健康檢查
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

CMD ["streamlit", "run", "src/twquant/dashboard/app.py"]
```

### 8.2 Docker Compose（完整開發/運行環境）

```yaml
# docker-compose.yml

version: "3.9"

services:
  # ── 主應用 ──
  twquant-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: twquant-app
    ports:
      - "8501:8501"
    volumes:
      - twquant-data:/app/data          # 持久化數據
      - ./src:/app/src:ro               # 開發時掛載原始碼（hot reload）
    environment:
      - FINMIND_API_TOKEN=${FINMIND_API_TOKEN}
      - ARCTICDB_URI=lmdb:///app/data/arcticdb
      - TZ=Asia/Taipei
    restart: unless-stopped
    depends_on:
      - twquant-db
    networks:
      - twquant-net

  # ── ArcticDB 數據儲存（本地 LMDB 模式無需獨立服務） ──
  # 若未來切換為 S3 後端，可在此加入 MinIO 服務

  # ── SQLite 備選儲存（輕量開發模式） ──
  twquant-db:
    image: keinos/sqlite3:latest
    container_name: twquant-db
    volumes:
      - twquant-db-data:/data
    networks:
      - twquant-net

  # ── 數據同步排程（可選，用於全市場自動更新） ──
  twquant-sync:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: twquant-sync
    command: ["python", "scripts/scheduled_sync.py"]
    volumes:
      - twquant-data:/app/data
    environment:
      - FINMIND_API_TOKEN=${FINMIND_API_TOKEN}
      - SYNC_MODE=scheduled
      - SYNC_CRON=30 14 * * 1-5    # 週一至週五 14:30（收盤後）
      - TZ=Asia/Taipei
    restart: unless-stopped
    networks:
      - twquant-net

volumes:
  twquant-data:
    name: twquant-data
  twquant-db-data:
    name: twquant-db-data

networks:
  twquant-net:
    name: twquant-net
```

### 8.3 開發環境 Docker Compose（含 Rust 編譯）

```yaml
# docker-compose.dev.yml
# 用法：docker compose -f docker-compose.yml -f docker-compose.dev.yml up

version: "3.9"

services:
  twquant-app:
    build:
      context: .
      dockerfile: Dockerfile.dev       # 開發版 Dockerfile（含 Rust 工具鏈）
    volumes:
      - ./src:/app/src                  # 掛載原始碼（支援 hot reload）
      - ./rust:/app/rust                # 掛載 Rust 原始碼
      - ./tests:/app/tests
      - cargo-cache:/root/.cargo        # 快取 Cargo 下載
    command: >
      bash -c "cd rust/twquant-core && maturin develop &&
               streamlit run src/twquant/dashboard/app.py --server.runOnSave true"
    environment:
      - PYTHONDONTWRITEBYTECODE=1
      - RUST_BACKTRACE=1                # Rust panic 時顯示完整堆疊

volumes:
  cargo-cache:
    name: twquant-cargo-cache
```

### 8.4 .dockerignore

```
# .dockerignore
.git
.github
__pycache__
*.pyc
*.pyo
.mypy_cache
.pytest_cache
.ruff_cache
target/             # Rust build artifacts（在容器內重新編譯）
data/raw/           # 原始數據不打包入 image
data/processed/
*.egg-info
.env
.env.*
node_modules
```

### 8.5 Codespaces / devcontainer 整合

由於開發環境在 GitHub Codespaces，也提供 devcontainer 配置：

```json
// .devcontainer/devcontainer.json
{
  "name": "TWQuant Dev",
  "build": {
    "dockerfile": "../Dockerfile.dev"
  },
  "features": {
    "ghcr.io/devcontainers/features/rust:1": {
      "version": "1.78"
    },
    "ghcr.io/devcontainers/features/python:1": {
      "version": "3.11"
    }
  },
  "forwardPorts": [8501],
  "postCreateCommand": "poetry install && cd rust/twquant-core && maturin develop",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "rust-lang.rust-analyzer",
        "charliermarsh.ruff"
      ]
    }
  }
}
```

---

## 9. 風險與緩解措施

| 風險 | 影響 | 緩解措施 |
|------|------|---------|
| FinMind API 速率限制（600/hr） | 大量股票數據下載受限 | 實作本地快取層；批次下載後存入 ArcticDB |
| VectorBT Free 版功能限制 | 部分進階功能不可用 | 核心功能均在 Free 版內；必要時自行實作缺失功能 |
| PyO3 版本與 Python 版本相容性 | 編譯失敗 | 鎖定 PyO3 0.21 + Python 3.11；CI 中驗證 |
| Streamlit 記憶體洩漏 | 長時間運行後 OOM | 嚴格使用 cache_data；限制 DataFrame 大小；定期 gc |
| 台股交易規則變更 | 回測成本不準確 | 將所有規則常數集中於 constants.py；文件記錄資料來源 |
| ArcticDB 安裝困難 | 開發環境差異 | SQLite 作為備選；Docker 化開發環境 |

---

## 10. Makefile 常用指令

```makefile
.PHONY: install dev test lint build-rust run clean docker-build docker-up docker-down

install:
	poetry install
	cd rust && cargo build

dev:
	cd rust/twquant-core && maturin develop
	poetry run streamlit run src/twquant/dashboard/app.py

test:
	poetry run pytest tests/ -v
	cd rust && cargo test

lint:
	poetry run ruff check src/
	poetry run mypy src/twquant/
	cd rust && cargo clippy

build-rust:
	cd rust/twquant-core && maturin build --release

run:
	poetry run streamlit run src/twquant/dashboard/app.py --server.port 8501

seed-data:
	poetry run python scripts/seed_data.py

full-sync:
	poetry run python scripts/scheduled_sync.py --mode full

profile:
	poetry run python scripts/profile_memory.py

# ── Docker ──
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

docker-logs:
	docker compose logs -f twquant-app

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	cd rust && cargo clean
	rm -rf data/raw/*
```

---

## 11. 附錄

### A. 台股重要指數代碼

| 代碼 | 名稱 | 用途 |
|------|------|------|
| TAIEX | 加權股價指數 | 大盤基準 |
| 0050 | 元大台灣50 | ETF 基準 |
| 006208 | 富邦台50 | ETF 基準（低內扣） |
| 0056 | 元大高股息 | 高息策略基準 |
| 00878 | 國泰永續高股息 | ESG 高息基準 |

### B. 常見台股個股代碼（測試用）

| 代碼 | 名稱 | 產業 | 特性 |
|------|------|------|------|
| 2330 | 台積電 | 半導體 | 高成交量、權值王 |
| 2317 | 鴻海 | 電子代工 | 高成交量 |
| 2454 | 聯發科 | IC 設計 | 高波動 |
| 2882 | 國泰金 | 金融 | 金融股代表 |
| 2886 | 兆豐金 | 金融 | 高殖利率 |
| 2603 | 長榮 | 航運 | 景氣循環股 |
| 3008 | 大立光 | 光學 | 高價股 |

### C. 台股無風險利率參考

台灣央行定存利率（供 Sharpe Ratio 計算使用）：
- 2024 年：1.625%（一年期定存）
- 建議實作為可配置參數，預設 1.5%

### D. 資料來源與授權聲明

- FinMind：MIT License，資料僅供研究用途
- twstock：MIT License
- VectorBT Free：MIT License
- ArcticDB：Apache 2.0 License
- 台灣證交所公開資訊觀測站：公開資料

---

> **重要提醒：** 本系統產出的回測結果僅供研究與教育目的，不構成任何投資建議。過去績效不代表未來報酬。市場有風險，投資需謹慎。
