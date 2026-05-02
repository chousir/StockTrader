# 內部模組 API 參考

## 目錄

1. [數據層 (twquant.data)](#數據層)
2. [策略層 (twquant.strategy)](#策略層)
3. [回測層 (twquant.backtest)](#回測層)
4. [Rust 橋接 (twquant_core)](#rust-橋接)
5. [工具層 (twquant.utils)](#工具層)

---

## 數據層

### FinMindProvider

> 待填寫：`fetch_daily()`、`fetch_institutional()`、`fetch_stock_list()` 方法簽名與範例

### DataStorage

> 待填寫：`save()`、`load()`、`upsert()`、`get_hwm()` 抽象介面說明

### MarketDataSyncEngine

> 待填寫：`initial_full_sync()`、`incremental_sync()`、`detect_and_fill_gaps()` 說明

## 策略層

### BaseStrategy

> 待填寫：`generate_signals(df) -> (entries, exits)` 抽象方法規格

### MACrossover

> 待填寫：參數、`generate_signals()` 回傳格式

## 回測層

### TWSEBacktestEngine

> 待填寫：`run(price, entries, exits) -> BacktestResult` 方法說明

### tw_stock_fees()

> 待填寫：手續費計算函數簽名與範例

## Rust 橋接

### twquant_core（Python 可見 API）

> 待填寫：Phase 1 完成後補充 `array_sum()`、`validate_f64_array()` 等函數說明

## 工具層

### safe_call_rust()

> 待填寫：`rust_bridge.py` 安全呼叫包裝層說明
