# 📈 TWQuant｜台股量化交易平台

> 端對端的台股量化交易回測與選股平台 — 以 **Python + Rust 混合架構** 打造，整合資料管線、9 種已驗證策略、VectorBT 回測、即時訊號掃描、告警與 Discord 推播。

![python](https://img.shields.io/badge/python-3.11%2B-blue)
![rust](https://img.shields.io/badge/rust-edition%202021-orange)
![streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![backtest](https://img.shields.io/badge/backtest-VectorBT-green)

---

## 🎯 平台是什麼？

TWQuant 是專為**台股**設計的量化交易研究與選股工作站。它一站式解決四件事：

1. **抓資料** — 從 FinMind API 取得 OHLCV、三大法人、融資融券；自動分割還原、除權息遮罩。
2. **驗策略** — 內建 9 種策略（5 種已實證超額報酬 > 0），整合台股真實交易成本（手續費 + 證交稅 + 滑價）。
3. **找訊號** — 全市場每日掃描，告警規則（價格突破 / RSI / 策略訊號）+ Discord 推播。
4. **看圖表** — 11 個 Streamlit 頁面組成的暗色系儀表板，從市場總覽、個股 K 線到 A/B 比較器一氣呵成。

效能熱點以 **Rust（PyO3）** 重寫：Kalman 降噪、滑動窗運算等，並透過零拷貝 NumPy 緩衝區傳遞。

---

## ✨ 主要功能

| 模組 | 說明 |
|---|---|
| 📊 **資料管線** | FinMind 適配器、HWM 斷點續傳、闕漏偵測、冪等寫入、分割還原、合理性檢查 |
| 🧠 **策略註冊表** | 9 種內建策略（動能、量價突破、三線扭轉、RAM、唐奇安等），可擴充 Rust 自訂策略 |
| 🔬 **VectorBT 回測** | 整合台股手續費（0.1425% × 折扣）、證交稅（股 0.3% / ETF 0.1% / 當沖 0.15%）、追蹤停損 |
| 🔍 **選股工具** | 多因子篩選器（價量、均線、RSI、季線）支援 DB 優先 / API 備援 |
| 📡 **訊號掃描器** | 全宇宙 × 多策略即時掃描，依板塊分組顯示 |
| 🔔 **告警系統** | 規則庫（突破 / RSI / 策略訊號）+ 手動 / 背景掃描 + 觸發紀錄 |
| 📅 **每日選股** | 策略訂閱 + 盤後自動掃描 + Discord 推播 + 30 日歷史檢索 |
| ⚔️ **策略比較** | 策略 vs 0050 基準、A/B 雙策略並排比較 |
| 🏗️ **產業組合回測** | 月度輪動、Top-N 持股、市場過濾器 |
| 🎓 **首次設定精靈** | 4 步驟 onboarding：手續費 / 資金 / Token / 同步模式 |

---

## 🏗️ 架構鳥瞰

```
┌─────────────────────────────────────────────────────────────────┐
│                    Streamlit Dashboard (11 頁)                  │
│   首頁 ── 市場 ── 個股 ── 策略 ── 回測 ── 篩選 ── 比較         │
│            └── 組合 ── 掃描 ── A/B ── 告警 ── 每日選股         │
└────────────────────────────┬────────────────────────────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│  Strategy    │    │   Backtest     │    │   Scanner    │
│  Registry    │───▶│   VectorBT     │    │  + Alerts    │
│  (9 策略)    │    │ + TW 成本模型  │    │  + Discord   │
└──────┬───────┘    └────────┬───────┘    └──────┬───────┘
       │                     │                   │
       └──────────┬──────────┴─────────┬─────────┘
                  ▼                    ▼
        ┌──────────────────┐   ┌──────────────────┐
        │  Indicators      │   │  Data Storage    │
        │  Python + Rust   │   │  SQLite/ArcticDB │
        └────────┬─────────┘   └────────┬─────────┘
                 │                      ▲
                 ▼                      │
        ┌──────────────────┐   ┌────────┴─────────┐
        │  Rust Core (PyO3)│   │  FinMind API     │
        │  Kalman / SIMD   │   │  + Auto Sync     │
        └──────────────────┘   └──────────────────┘
```

詳細互動式說明圖請開啟 [`docs/system_guide.html`](docs/system_guide.html)。

---

## 🚀 快速開始

### 1️⃣ 環境準備

```bash
# Python 依賴（Poetry）
poetry install

# Rust 工具鏈
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 編譯 Rust 模組並安裝為 wheel
make build-rust
```

### 2️⃣ 下載種子資料

```bash
# 49 支分析師宇宙（推薦首次）
poetry run python scripts/seed_data.py --universe

# 或全市場 (~3000 支，需 FINMIND_TOKEN，約 3-4 小時)
poetry run python scripts/seed_data.py --all
```

### 3️⃣ 啟動 Dashboard

```bash
make run
# 等同於：poetry run streamlit run src/twquant/dashboard/app.py
```

預設網址 [http://localhost:8501](http://localhost:8501)。首次啟動會自動進入 **Onboarding 精靈** 引導 4 步設定。

---

## 🐳 Docker 部署

```bash
# 一鍵啟動
make docker-up

# 即時 log
make docker-logs

# 關閉
make docker-down
```

`Dockerfile` 為兩階段建置：第一階段用 `rust:1.80-bookworm` 編譯 wheel，第二階段用 `python:3.12-slim-bookworm` 跑 Streamlit。

### 📦 資料持久化（Volume）

`docker-compose.yml` 使用具名 volume `twquant-data` 掛載容器內的 `/app/data`：

```yaml
volumes:
  - twquant-data:/app/data   # SQLite DB + ArcticDB 都存在這裡
```

- 容器更新 / 重啟後，資料庫**不會消失**。
- 查看 volume 實體路徑：`docker volume inspect twquant-data`
- 備份：`docker run --rm -v twquant-data:/data -v $(pwd):/backup alpine tar czf /backup/twquant-data.tar.gz /data`

### 🔑 環境變數設定

所有環境變數均為**選填**，未設定時平台仍可正常運行（僅對應功能停用）。

**方式一：`.env` 檔案（推薦）**

在專案根目錄建立 `.env`，`docker compose up` 會自動讀取：

```env
# FinMind API Token（無 Token 仍可用本地 DB；需即時拉取資料才必填）
FINMIND_API_TOKEN=your_token_here

# Discord Webhook URL（選填；未設定則每日選股只落地 DB，不推播）
# 建立方式：Discord 伺服器 → 頻道設定 → 整合 → Webhook → 複製 URL
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
```

**方式二：直接 export 再啟動**

```bash
export FINMIND_API_TOKEN=your_token_here
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
docker compose up -d
```

### ⏰ 每日自動掃描（排程）

每個交易日盤後 14:30，執行同步 → 策略掃描 → 告警評估 → Discord 推播：

```bash
# 在容器內（crontab -e 設定）
30 14 * * 1-5  docker exec twquant-app python scripts/scheduled_sync.py

# 或宿主機直接執行（需 Python 環境）
30 14 * * 1-5  cd /your/project && poetry run python scripts/scheduled_sync.py
```

僅同步資料、跳過掃描：`python scripts/scheduled_sync.py --no-scan`

---

## 📚 Dashboard 頁面導覽

| 頁面 | 用途 | 重點功能 |
|---|---|---|
| 🏠 **首頁** | 分析師桌面 | 多頭/空頭判定、自選股輪盤、今日訊號、系統健康 |
| 🏛️ **市場總覽** | 大盤行情 | 板塊輪動、法人籌碼、資料新鮮度 |
| 📈 **個股分析** | K 線深入 | 4 副圖（收盤+MA / RSI / MACD / KD），TradingView 整合 |
| 🔧 **策略建構器** | 訊號可視化 | 9 策略切換、進出場標記、策略專屬指標副圖 |
| 📊 **回測結果** | 報表 | 三層佈局（摘要 / 資金曲線 / 卡片+交易明細）|
| 🔍 **選股工具** | 多因子篩選 | 量比、價格區間、RSI、距均線、DB+API 雙線備援 |
| ⚔️ **策略 vs 基準** | 多策略比較 | 5 種已驗證策略對 0050 同期表現 |
| 🏗️ **組合回測** | 產業輪動 | 月度 Rebalance、Top-N、市場過濾器 |
| 📡 **訊號掃描** | 全市場掃描 | 多策略×全宇宙當日進場訊號表 |
| 🆚 **A/B 比較** | 雙策略對決 | 同標的同時間軸、並排績效卡 |
| 🔔 **告警中心** | 規則引擎 | 突破/RSI/策略訊號規則 + 觸發紀錄 + 已讀管理 |
| 📅 **每日選股** | 自動化 | 策略訂閱 + 盤後掃描 + Discord 推播 |

---

## 🧠 策略一覽

5 種**已驗證**生產策略（最佳標的超額報酬 > 0 @ vs 0050 同期）：

| Key | 名稱 | 類型 | 代表績效（2022-2026） |
|---|---|---|---|
| `momentum_concentrate` | F｜動能精選 ★ | 強勢股 | 台達電 +369%（超額 +223%）|
| `volume_breakout` | H｜量價突破 | 突破型 | 台達電 Sharpe 1.81（最高）|
| `triple_ma_twist` | L｜三線扭轉 | 全市場 | 台達電 +258%（超額 +111%）|
| `risk_adj_momentum` | M｜RAM 動能 | 景氣循環股 | 南亞科 超額 +285%（最高）|
| `donchian_breakout` | N｜唐奇安突破 | 突破型 | 台達電 超額 +201% |

另含 4 種**基礎教學**策略：`ma_crossover`, `macd_divergence`, `rsi_reversal`, `bollinger_breakout`。

每個策略的完整數學公式、進出場條件、回測結果請見 [`docs/STRATEGIES.md`](docs/STRATEGIES.md)。

---

## 🛠️ 常用指令

```bash
make run             # 啟動 Streamlit dashboard
make build-rust      # 編譯 Rust 模組
make test            # pytest tests/python/
make seed-data       # 下載種子資料（預設 7 支）
make docker-build    # 建置 Docker image
make clean           # 清理 __pycache__ / wheels
```

進階：

```bash
# 增量同步（從 HWM 接續）
poetry run python scripts/seed_data.py --incremental

# 排程同步
poetry run python scripts/scheduled_sync.py

# Rust benchmark
poetry run python scripts/benchmark_rust.py

# 記憶體 profiling
poetry run python scripts/profile_memory.py
```

---

## 📁 目錄結構

```
StockTrader/
├── src/twquant/
│   ├── dashboard/          # Streamlit UI（app.py + 11 pages）
│   │   ├── pages/          # 11 個頁面
│   │   ├── components/     # 共用 UI 元件（K線、搜尋、側欄）
│   │   └── styles/         # 暗色系 Plotly 主題
│   ├── data/               # 資料層
│   │   ├── providers/      # FinMind / CSV 適配器
│   │   ├── notifiers/      # Discord webhook
│   │   ├── storage.py      # SQLite / ArcticDB 抽象介面
│   │   ├── sync_engine.py  # HWM 斷點續傳、闕漏偵測
│   │   ├── alerts.py       # 告警規則庫
│   │   └── daily_scans.py  # 每日選股訂閱
│   ├── strategy/
│   │   ├── base.py         # BaseStrategy 抽象類
│   │   ├── registry.py     # 策略註冊表
│   │   ├── scanner.py      # 全宇宙掃描（無 streamlit 依賴）
│   │   └── builtin/        # 9 種內建策略
│   ├── backtest/
│   │   ├── engine.py       # VectorBT 封裝 + 追蹤停損
│   │   ├── cost_model.py   # 台股手續費 / 證交稅
│   │   └── portfolio.py    # 組合回測（月度輪動）
│   ├── indicators/basic.py # MA / RSI / MACD / KD / 布林 / ATR ...
│   ├── utils/rust_bridge.py # PyO3 安全呼叫包裝
│   └── constants.py        # TWSE 交易規則常數
├── rust/
│   ├── twquant-core/       # Kalman、移動窗、訊號引擎
│   └── twquant-ml/         # ML 擴充（保留）
├── scripts/                # 資料抓取與 benchmark
├── tests/python/           # pytest 測試
├── data/twquant.db         # SQLite 資料庫
├── docs/                   # 架構、API、策略、部署文件
│   ├── STRATEGIES.md       # 9 策略完整公式 ★
│   └── system_guide.html   # 互動式系統說明 ★
├── Makefile
├── pyproject.toml          # Poetry 依賴
├── Dockerfile              # 兩階段建置
└── CLAUDE.md               # AI 協作規範
```

---

## ⚖️ 台股交易規則內建

所有回測自動套用真實成本（`src/twquant/constants.py`）：

| 項目 | 數值 |
|---|---|
| 券商手續費 | 0.1425% × 折扣（最低 20 元 / 零股 1 元） |
| 股票證交稅 | 賣出 0.3% |
| ETF 證交稅 | 賣出 0.1% |
| 當沖證交稅 | 0.15%（優惠至 2027 年底） |
| 漲跌幅 | ±10% |
| 交易單位 | 1 張 = 1000 股，支援零股 |
| 交割 | T+2 |
| 預設滑價 | 0.1% |

---

## 🧪 測試

```bash
make test
# 涵蓋：indicators / backtest engine / cost model / sync engine /
#       sanity checker / ex-dividend / rust bridge 型別安全
```

---

## 🌐 環境變數

| 變數 | 必填 | 說明 |
|---|---|---|
| `FINMIND_TOKEN` | 建議 | FinMind API token（也可寫入 `data/user_config.json`）|
| `DISCORD_WEBHOOK_URL` | 否 | 每日選股推播 |
| `ARCTICDB_URI` | 否 | 預設 `lmdb://data/arcticdb` |
| `LOG_LEVEL` | 否 | 預設 `INFO` |

---

## 📖 文件索引

- [系統互動說明](docs/system_guide.html) — **互動式 HTML，建議用瀏覽器開啟** ★
- [策略總覽與數學公式](docs/STRATEGIES.md)
- [架構說明](docs/ARCHITECTURE.md)
- [API 參考](docs/API_REFERENCE.md)
- [部署指南](docs/DEPLOYMENT.md)
- [數據字典](docs/DATA_DICTIONARY.md)
- [測試策略](docs/TESTING_STRATEGY.md)
- [效能報告](docs/PERFORMANCE_REPORT.md)
- [版本紀錄](docs/CHANGELOG.md)

---

## 📝 開發規範

- Python 3.11+ ／ Rust edition 2021
- 跨語言禁止逐筆轉換，必須走 Apache Arrow / NumPy 零拷貝
- Streamlit 靜態資料一律 `@st.cache_data`
- VectorBT Portfolio 用完 `del + gc.collect()`
- 詳見 [`CLAUDE.md`](CLAUDE.md) 行為準則章節

---

## 📜 授權

本專案僅供研究與教學用途，不構成任何投資建議。實盤交易前請充分理解策略風險與限制。
