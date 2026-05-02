# 版本變更紀錄

所有重要變更依 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.0.0/) 格式記錄。

---

## [Unreleased]

### Added
- 專案骨架：目錄結構、CLAUDE.md、.gitignore
- Poetry 依賴管理（streamlit, vectorbt, arcticdb, finmind 等）
- Rust Cargo workspace（twquant-core, twquant-ml）
- GitHub Actions CI/CD（Python lint/test + Rust build/test）
- docs/ 文件骨架

---

## 版本說明

- **Phase 0**：專案骨架與環境建置
- **Phase 1**：PyO3 橋接與 Rust-Python 通訊
- **Phase 2**：台股數據管線與 Streamlit 基礎視覺化
- **Phase 3**：VectorBT 回測引擎整合
- **Phase 4**：Rust 策略模組整合
- **Phase 5**：壓力測試與記憶體 Profiling
