# 系統架構說明

## 目錄

1. [系統總覽](#系統總覽)
2. [模組架構圖](#模組架構圖)
3. [Python 層](#python-層)
4. [Rust 層](#rust-層)
5. [跨語言橋接（PyO3）](#跨語言橋接)
6. [數據流](#數據流)
7. [儲存層](#儲存層)
8. [部署架構](#部署架構)

---

## 系統總覽

> 待填寫：台股量化平台整體架構描述

## 模組架構圖

> 待填寫：ASCII 或 Mermaid 架構圖

## Python 層

> 待填寫：各模組（data, strategy, backtest, dashboard）職責說明

## Rust 層

> 待填寫：twquant-core、twquant-ml crate 職責與 API 介面

## 跨語言橋接

> 待填寫：PyO3 + maturin 橋接機制、零拷貝傳輸設計

## 數據流

> 待填寫：從 FinMind API → ArcticDB → Strategy → VectorBT → Streamlit 的完整數據流

## 儲存層

> 待填寫：ArcticDB schema、SQLite 備選方案設計

## 部署架構

> 待填寫：Docker multi-stage build、Codespaces 開發環境
