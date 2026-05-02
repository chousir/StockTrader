# 數據字典

## 目錄

1. [OHLCV 日K線](#ohlcv-日k線)
2. [三大法人](#三大法人)
3. [融資融券](#融資融券)
4. [月營收](#月營收)
5. [ArcticDB Symbol 命名規則](#arcticdb-symbol-命名規則)
6. [欄位型別規範](#欄位型別規範)

---

## OHLCV 日K線

| 欄位 | 型別 | 說明 | 範例 |
|------|------|------|------|
| date | date | 交易日期 | 2024-01-02 |
| stock_id | str | 股票代碼 | 2330 |
| open | float64 | 開盤價（元） | 580.0 |
| high | float64 | 最高價（元） | 595.0 |
| low | float64 | 最低價（元） | 578.0 |
| close | float64 | 收盤價（元） | 590.0 |
| volume | int64 | 成交量（股） | 30000000 |

## 三大法人

> 待填寫：institutional_investors 資料集欄位定義

## 融資融券

> 待填寫：margin_purchase_short_sale 資料集欄位定義

## 月營收

> 待填寫：month_revenue 資料集欄位定義

## ArcticDB Symbol 命名規則

> 待填寫：`{dataset}/{stock_id}` 格式說明，例如 `daily_price/2330`

## 欄位型別規範

> 待填寫：統一的 dtype 規範，避免 float32/float64 混用問題
