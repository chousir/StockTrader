# 📈 TWQuant｜台股量化交易平台

> 端對端的台股量化交易回測與選股平台 — 以 **Python + Rust 混合架構** 打造，整合資料管線、5 種已驗證策略、VectorBT 回測、即時訊號掃描、告警與 Discord 推播。

![python](https://img.shields.io/badge/python-3.11%2B-blue)
![rust](https://img.shields.io/badge/rust-edition%202021-orange)
![streamlit](https://img.shields.io/badge/UI-Streamlit-red)
![backtest](https://img.shields.io/badge/backtest-VectorBT-green)

---

## 🎯 平台是什麼？

TWQuant 是專為**台股**設計的量化交易研究與選股工作站。它一站式解決四件事：

1. **抓資料** — 從 FinMind API 取得 OHLCV、三大法人、融資融券；自動分割還原、除權息遮罩。
2. **驗策略** — 內建 5 種已驗證生產策略（超額報酬 > 0 @ 最佳標的），整合台股真實交易成本（手續費 + 證交稅 + 滑價）。
3. **找訊號** — 全市場每日掃描 + 兩階段選股漏斗（粗篩 → 5 策略精篩），告警規則 + Discord 推播。
4. **看圖表** — 6 個 Streamlit 頁面組成的暗色系儀表板（含首頁），從市場總覽、個股 K 線到策略對照一氣呵成。

效能熱點以 **Rust（PyO3）** 重寫：Kalman 降噪、滑動窗運算等，並透過零拷貝 NumPy 緩衝區傳遞。

---

## ✨ 主要功能

| 模組 | 說明 |
|---|---|
| 📊 **資料管線** | FinMind 適配器、HWM 斷點續傳、DB-first 籌碼/月營收/PER、`--include` 旗標、還原權息 |
| 🧠 **策略註冊表** | 5 種已驗證生產策略（動能、量價突破、三線扭轉、RAM、唐奇安），可擴充 Rust 自訂策略 |
| 🔬 **VectorBT 回測** | 整合台股手續費（0.1425% × 折扣）、證交稅（股 0.3% / ETF 0.1% / 當沖 0.15%）、追蹤停損 |
| 🔍 **選股工具** | 多因子篩選器（價量、均線、RSI、季線）、55 板塊 DB 動態分類 |
| 📡 **訊號掃描器** | 全宇宙 × 5 策略即時掃描，漲幅/跌幅/量爆/突破 排行榜 tabs |
| 🔔 **訂閱中心** | 個股告警（突破/RSI/策略）+ 每日選股訂閱 + 觸發紀錄，一頁統一管理 |
| 📈 **個股分析** | RS 相對強弱、Beta、ATR 建倉計算器、DB-first 法人/基本面 |
| ⚔️ **策略比較** | 5 大生產策略 vs 0050 基準，還原權息開關，跳頁帶入最佳策略 |
| 🛒 **交易籃** | 跨頁 session 暫存，側邊欄一鍵跳頁 07 組合回測 |
| 🏗️ **產業組合回測** | 月度輪動、Top-N 持股、市場過濾器 |
| 🎓 **首次設定精靈** | 4 步驟 onboarding：手續費 / 資金 / Token / 同步模式 |

---

## 🎯 分析師日常流程（5 分鐘上手）

```
① 首頁排行榜  ──▶  ② 頁 03 兩階段漏斗  ──▶  ③ 頁 02 個股深度  ──▶  ④ 頁 07 組合回測
  (掌握強勢族群)      (粗篩 + 5 策略精篩)        (停損 / 目標計算)        (組合 3 年回測)
```

| 步驟 | 頁面 | 目的 | 約耗時 |
|:---:|:---|:---|:---:|
| ① 晨會 | 首頁 | 看漲幅 / 量爆 / 突破排行榜，掌握當日強勢族群 | 30 秒 |
| ② 選股漏斗 | 🔻 **頁 03 兩階段漏斗** | 全市場 → 粗篩（4 條件）→ 精篩（5 策略共振）→ 候選 5-10 支 | 1 分鐘 |
| ③ 個股深度 | 📈 頁 02 個股分析 | 看 K 線 + RS + Beta + 建倉計算器，算停損 / 目標價 / 建議張數 | 1 分鐘 / 支 |
| ④ 組合 | 🏗️ 頁 07 組合回測 | 把交易籃內候選跑組合回測，看 3 年表現 | 30 秒 |

**核心心法**：頁 03 的「**粗篩 → 精篩**」漏斗是分析的入口。粗篩過濾掉 90% 不健康的股票，精篩用 5 策略找出多策略共振的「強訊號」，每股能看到命中哪些策略（如「F+H+L」）。

> 🧪 **實戰案例**：[scripts/ai_trend_pick_20260513.py](scripts/ai_trend_pick_20260513.py) — AI 趨勢產業選股，50 支候選 → 7 主推 + 3 觀察。

---

## 🏗️ 架構鳥瞰

```
┌─────────────────────────────────────────────────────────────────┐
│              Streamlit Dashboard (6 頁 + 首頁)                  │
│   首頁 ── 市場總覽 ── 個股分析 ── 選股入口（漏斗/雷達）         │
│         ── 策略覆驗中心（並排/單策略/全宇宙）── 組合 ── 訂閱     │
└────────────────────────────┬────────────────────────────────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       ▼                     ▼                     ▼
┌──────────────┐    ┌────────────────┐    ┌──────────────┐
│  Strategy    │    │   Backtest     │    │   Scanner    │
│  Registry    │───▶│   VectorBT     │    │  + Alerts    │
│  (5 策略)    │    │ + TW 成本模型  │    │  + Discord   │
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
# Build image
make docker-build

# 一鍵啟動
make docker-up

# 即時 log
make docker-logs

# 關閉（資料不會消失）
make docker-down
```

`Dockerfile` 為兩階段建置：第一階段用 `rust:1.80-bookworm` 編譯 wheel，第二階段用 `python:3.11-slim-bookworm` 跑 Streamlit。容器內建 cron daemon。**Lazy 啟動模式**：不再自動 seed，由 dashboard onboarding 互動式抓取，**首次體驗 30 秒上線**。

### 🚦 啟動行為一覽（Lazy 模式）

| 場景 | 行為 |
|------|------|
| **首次啟動（空 volume）** | 容器只啟動 Streamlit + cron，不抓資料 → 開啟 http://localhost:8501 → onboarding 4 步驟（含 token 驗證 + 範圍選擇 + 起始日）→ 點「🚀 開始抓取」啟動背景任務 |
| **重啟容器** | Volume 保留 → 直接啟動，sidebar 同步 widget 顯示 DB 狀態 |
| **背景自動補齊** | `auto_sync.py` 每 5 分鐘（盤中）/ 60 分鐘（盤後）跑 Phase A（補 HWM）+ Phase B（擴宇宙），漸進把全市場 3000+ 支補滿 |
| **手動補抓** | 開「頁 01 市場總覽」→ 「📡 資料中心」expander → 選範圍 + 起始日 → 「▶ 開始補抓」（背景執行，不擋手） |
| **每日盤後** | 容器內 cron 14:30 跑 `scheduled_sync.py`（策略掃描 + 告警 + Discord 推播） |
| **看抓取進度** | 全頁 sidebar 底部 widget；頁 01 頂部詳細面板（含進度條 + 取消按鈕 + 最近 10 次任務） |

### 📦 資料持久化（Volume）

`docker-compose.yml` 使用具名 volume `twquant-data` 掛載容器內的 `/app/data`：

```yaml
volumes:
  - twquant-data:/app/data   # SQLite DB + ArcticDB + user_config.json
```

- 容器更新 / 重啟後，資料庫**不會消失**。
- 查看 volume 實體路徑：`docker volume inspect twquant-data`
- 備份：`docker run --rm -v twquant-data:/data -v $(pwd):/backup alpine tar czf /backup/twquant-data.tar.gz /data`
- 重置（清空所有資料重來）：`docker compose down && docker volume rm twquant-data && docker compose up -d`

### 🔑 環境變數設定

**所有環境變數均為選填**，未設定時平台仍可運行（僅對應功能停用）。

**方式一：`.env` 檔案（推薦）**

在專案根目錄建立 `.env`，`docker compose up` 會自動讀取：

```env
# FinMind API Token（不填 → 無法拉取新資料，但本地 DB 既有資料仍可讀；
#                   設定後 entrypoint 會自動同步到 user_config.json 供 dashboard 使用）
FINMIND_API_TOKEN=your_token_here

# Discord Webhook URL（不填 → 每日選股仍會落地 DB，但不推播）
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# 行為旗標（保留預設即可）
ENABLE_CRON=true     # 啟動 cron daemon（每交易日 14:30 自動同步+掃描+推播）
```

**方式二：直接 export 再啟動**

```bash
export FINMIND_API_TOKEN=your_token_here
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy
docker compose up -d
```

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `FINMIND_API_TOKEN` | 空 | FinMind API Token；空值仍可用匿名額度（較低，建議註冊） |
| `DISCORD_WEBHOOK_URL` | 空 | Discord Webhook；空值不推播 |
| `ENABLE_CRON` | `true` | 容器內建 cron 排程。不想用設為 `false`，改自己用宿主機 cron |
| `ARCTICDB_URI` | `lmdb:///app/data/arcticdb` | ArcticDB 連線字串 |
| `TZ` | `Asia/Taipei` | 時區（影響 cron 觸發時間） |

### ⏰ 每日自動同步（容器內建 cron）

`Dockerfile` 安裝了 `cron` 套件，`entrypoint.sh` 啟動時會啟動 cron daemon。預設排程：

```cron
30 14 * * 1-5  python scripts/scheduled_sync.py >> /var/log/twquant-cron.log 2>&1
```

每個交易日（週一至週五）14:30（盤後 1 小時）執行：
1. **增量同步**：從 HWM 接續抓取新資料
2. **每日策略掃描**：對訂閱的策略跑全宇宙掃描，結果寫入 `daily_scans` 表
3. **告警評估**：所有啟用規則跑一次
4. **Discord 推播**：選股清單 + 告警觸發訊息

**查看 cron 執行紀錄**：

```bash
docker exec twquant-app tail -f /var/log/twquant-cron.log
```

**自訂排程時間**：編輯 [`docker/crontab`](docker/crontab) 後 `docker compose up --build`。

**手動立即執行**：

```bash
docker exec twquant-app python scripts/scheduled_sync.py             # 同步 + 掃描 + 推播
docker exec twquant-app python scripts/scheduled_sync.py --no-scan   # 僅同步資料
```

### 🌱 手動 seed（首次未自動跑或要重建時）

```bash
docker exec twquant-app python scripts/seed_data.py --universe       # 49 支精選宇宙（推薦）
docker exec twquant-app python scripts/seed_data.py --all            # 全市場 ~3000 支（3-4 小時）
docker exec twquant-app python scripts/seed_data.py --stocks 2330 0050  # 指定股票
```

---

## 📚 Dashboard 頁面導覽

| 頁面 | 用途 | 重點功能 |
|---|---|---|
| 🏠 **首頁** | 分析師桌面 | 多頭/空頭判定、自選股輪盤、漲幅/量爆/突破 tabs、系統健康 |
| 🏛️ **頁 01 市場總覽** | 大盤行情 | 0050 走勢、板塊輪動 treemap、⚖️ 兩板塊強弱對比、TradingView 熱力圖 |
| 📈 **頁 02 個股分析** | K 線深入 | 一頁滑完：K 線 + RSI/MACD/KD + RS + Beta + ATR 建倉計算器 + 🚀 快速回測（5 策略 vs 0050）|
| 🔻 **頁 03 選股入口** | 漏斗 + 雷達 | 🔻 兩階段漏斗（粗篩+精篩）或 📡 純訊號雷達；條件 preset 儲存/載入；命中策略標籤 F+H+L |
| ⚔️ **頁 06 策略覆驗中心** | 三合一覆驗 | 5 策略並排 / 🎯 單策略快測 / 🌐 全宇宙 Alpha 掃描，含 0050 基準 |
| 🏗️ **頁 07 組合回測** | 產業輪動 | 月度 Rebalance、Top-N、市場過濾器、支援交易籃 |
| 🔔 **頁 10 訂閱中心** | 告警 + 選股 | 個股告警規則 + 每日策略訂閱 + 觸發紀錄 + Discord，一頁統一管理 |

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

每個策略的完整數學公式、進出場條件、回測結果請見 [`docs/STRATEGIES.md`](docs/STRATEGIES.md)。

> 註：早期版本另含 4 個未驗證的教學策略（MA 黃金交叉、MACD 背離、RSI 反轉、Bollinger 突破），已從 dashboard 軟刪以精簡操作；檔案保留於 `src/twquant/strategy/builtin/` 以便未來研究使用。

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
│   │   └── builtin/        # 5 種已驗證策略（+ 4 軟刪教學）
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
│   ├── STRATEGIES.md       # 策略完整公式 ★
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
