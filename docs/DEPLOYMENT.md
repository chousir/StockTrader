# 部署與環境設定指南

## 目錄

1. [開發環境（Codespaces）](#開發環境)
2. [本地開發環境](#本地開發環境)
3. [Docker 部署](#docker-部署)
4. [環境變數](#環境變數)
5. [FinMind API Token 設定](#finmind-api-token)
6. [ArcticDB 初始化](#arcticdb-初始化)
7. [首次全市場數據同步](#首次全市場數據同步)

---

## 開發環境（Codespaces）

> 待填寫：Codespaces 啟動流程，devcontainer.json 說明

## 本地開發環境

```bash
# 安裝 Python 依賴
poetry install

# 安裝 Rust 工具鏈
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# 編譯 Rust 模組
pip install maturin
cd rust/twquant-core && maturin develop

# 啟動 Streamlit
poetry run streamlit run src/twquant/dashboard/app.py
```

## Docker 部署

> 待填寫：`docker compose up` 流程、各 service 說明

## 環境變數

| 變數名稱 | 必填 | 說明 | 預設值 |
|---------|------|------|--------|
| FINMIND_TOKEN | 是 | FinMind API token | - |
| ARCTICDB_URI | 否 | ArcticDB 連線字串 | `lmdb://data/arctic` |
| LOG_LEVEL | 否 | 日誌等級 | INFO |

## FinMind API Token

> 待填寫：申請 Token 步驟、`.env` 設定方式

## ArcticDB 初始化

> 待填寫：首次建立 Arctic library 的初始化程式碼

## 首次全市場數據同步

> 待填寫：預估時間（約 3-12 小時）、斷點續傳說明
