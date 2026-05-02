# 測試策略與覆蓋率要求

## 目錄

1. [測試分層架構](#測試分層架構)
2. [Python 測試規範](#python-測試規範)
3. [Rust 測試規範](#rust-測試規範)
4. [跨語言橋接測試](#跨語言橋接測試)
5. [覆蓋率目標](#覆蓋率目標)
6. [CI 測試門檻](#ci-測試門檻)

---

## 測試分層架構

```
tests/
├── python/
│   ├── test_data_pipeline.py      # 數據管線單元測試
│   ├── test_sync_engine.py        # HWM、斷點續傳、冪等寫入
│   ├── test_sanity_checker.py     # OHLCV 合理性過濾
│   ├── test_ex_dividend.py        # 除權息假跌破過濾
│   ├── test_indicators.py         # 技術指標計算正確性
│   ├── test_backtest_engine.py    # 回測引擎整合測試
│   ├── test_cost_model.py         # 台股手續費計算
│   └── test_rust_bridge.py        # PyO3 橋接型別安全測試
└── rust/
    └── (內嵌於各 src/*.rs 的 #[cfg(test)] 模組)
```

## Python 測試規範

> 待填寫：pytest fixture 設計、async test 規範、mock 使用原則（禁止 mock DB）

## Rust 測試規範

> 待填寫：`#[test]`、`#[cfg(test)]` 模組規範、`proptest` 屬性測試建議

## 跨語言橋接測試

關鍵測試案例（Phase 1 完成後實作）：

- 空陣列 → Python 收到 `ValueError`
- 含 NaN 的陣列 → `ValueError` 並指出位置
- 含 Inf 的陣列 → `ValueError`
- 維度不匹配 → `ValueError`
- Rust panic → Python 收到 `RuntimeError`（非 segfault）
- 非 float64 輸入（int32, str）→ `TypeError`

## 覆蓋率目標

| 模組 | 目標覆蓋率 |
|------|-----------|
| data/ | ≥ 80% |
| strategy/ | ≥ 85% |
| backtest/ | ≥ 90% |
| utils/rust_bridge.py | 100% |

## CI 測試門檻

> 待填寫：PR merge 前必須通過的 gate 條件
