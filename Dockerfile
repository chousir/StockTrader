# ============================================================
# Stage 1: Rust 編譯階段
# ============================================================
FROM rust:1.80-bookworm AS rust-builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-dev python3-pip && \
    pip3 install maturin --break-system-packages && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /build

# 先複製 Cargo 設定，利用 cache 層加速依賴下載
COPY rust/Cargo.toml rust/Cargo.lock* ./rust/
COPY rust/twquant-core/Cargo.toml ./rust/twquant-core/
COPY rust/twquant-ml/Cargo.toml   ./rust/twquant-ml/

RUN mkdir -p rust/twquant-core/src rust/twquant-ml/src && \
    echo 'pub fn dummy(){}' > rust/twquant-core/src/lib.rs && \
    echo 'pub fn dummy(){}' > rust/twquant-ml/src/lib.rs && \
    cd rust && cargo build --release 2>/dev/null || true

# 複製完整 Rust 原始碼，正式編譯 wheel
COPY rust/ ./rust/
RUN cd rust/twquant-core && maturin build --release --out /build/wheels

# ============================================================
# Stage 2: Python 運行階段
# ============================================================
FROM python:3.11-slim-bookworm AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl cron && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安裝 Python 依賴（先複製 pyproject.toml 利用 cache）
COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    streamlit>=1.57.0 plotly>=6.7.0 pandas>=2.2 numpy>=2.4 \
    finmind>=1.9.9 aiohttp>=3.13 arcticdb>=6.14 vectorbt>=1.0 \
    loguru>=0.7.3 rapidfuzz>=3.14 streamlit-searchbox>=0.1.24

# 安裝 Rust 編譯的 wheel
COPY --from=rust-builder /build/wheels/*.whl /tmp/wheels/
RUN pip install --no-cache-dir /tmp/wheels/*.whl && rm -rf /tmp/wheels

# 複製應用原始碼與排程資源
COPY src/       src/
COPY scripts/   scripts/
COPY data/sample/ data/sample/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY docker/crontab       /etc/cron.d/twquant

RUN mkdir -p data/raw data/processed data/arcticdb && \
    chmod +x /usr/local/bin/entrypoint.sh && \
    chmod 644 /etc/cron.d/twquant && \
    touch /var/log/twquant-cron.log

ENV PYTHONPATH=/app/src
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
ENV AUTO_SEED=true
ENV ENABLE_CRON=true

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

EXPOSE 8501

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
