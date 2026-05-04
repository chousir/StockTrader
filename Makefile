PYTHONPATH := src
PYTHON     := PYTHONPATH=$(PYTHONPATH) python
RUST_PATH  := $(HOME)/.cargo/bin

.PHONY: run build-rust test seed-data clean docker-build docker-up docker-down docker-logs

## 啟動 Streamlit dashboard
run:
	$(PYTHON) -m streamlit run src/twquant/dashboard/app.py

## 編譯 Rust 模組並安裝到當前 Python 環境
build-rust:
	PATH="$(RUST_PATH):$$PATH" maturin build --release \
		--manifest-path rust/twquant-core/Cargo.toml
	pip install rust/target/wheels/*.whl --force-reinstall

## 執行測試
test:
	$(PYTHON) -m pytest tests/python/ -v

## 下載種子數據（需設定 FINMIND_API_TOKEN 或在 data/user_config.json 填入 token）
seed-data:
	$(PYTHON) scripts/seed_data.py

## ── Docker ──

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f twquant-app

## 清理暫存
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	rm -rf rust/target/wheels
