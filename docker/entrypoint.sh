#!/bin/bash
# twquant 容器啟動流程：
#   1. 同步 FINMIND_API_TOKEN → user_config.json（讓 dashboard 看見）
#   2. 第一次啟動偵測空 DB → 自動 seed --universe（AUTO_SEED=true 預設）
#   3. 啟動 cron daemon（ENABLE_CRON=true 預設）
#   4. 啟動 Streamlit（foreground）

DB_PATH=/app/data/twquant.db
mkdir -p /app/data

echo "[entrypoint] twquant 啟動..."

# 1) 把容器內環境變數 dump 到 .docker-env，供 cron 任務 source
env | grep -E '^(FINMIND_API_TOKEN|DISCORD_WEBHOOK_URL|ARCTICDB_URI|TZ|PYTHONPATH)=' \
    > /app/.docker-env || true
chmod 600 /app/.docker-env

# 2) FINMIND_API_TOKEN env var → user_config.json（env 優先；dashboard 讀 config）
if [ -n "$FINMIND_API_TOKEN" ]; then
    python - <<'PY'
import json, os
from pathlib import Path
p = Path('/app/data/user_config.json')
cfg = json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
cfg['finmind_api_token'] = os.environ.get('FINMIND_API_TOKEN', '')
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding='utf-8')
print('[entrypoint] FINMIND_API_TOKEN 已同步至 user_config.json')
PY
fi

# 3) 自動 seed（僅當 DB 不存在或無 daily_price 表）
db_empty() {
    python - <<PY
import sqlite3, sys, os
db = "$DB_PATH"
if not os.path.exists(db):
    sys.exit(0)
con = sqlite3.connect(db)
n = con.execute(
    "SELECT COUNT(*) FROM sqlite_master "
    "WHERE type='table' AND name LIKE 'data_daily_price_%'"
).fetchone()[0]
sys.exit(0 if n == 0 else 1)
PY
}

if [ "${AUTO_SEED:-true}" = "true" ] && db_empty; then
    if [ -n "$FINMIND_API_TOKEN" ]; then
        echo "[entrypoint] 偵測空 DB → 自動 seed_data.py --universe（約 5-10 分鐘，可從 docker logs 看進度）..."
        python /app/scripts/seed_data.py --universe \
            || echo "[entrypoint] ⚠️ seed 失敗，可手動重試：docker exec twquant-app python scripts/seed_data.py --universe"
    else
        echo "[entrypoint] ℹ️ 空 DB 但未設 FINMIND_API_TOKEN — 跳過自動 seed"
        echo "[entrypoint]    啟動後請在 dashboard onboarding 設定 token，或手動 seed："
        echo "[entrypoint]    docker exec twquant-app python scripts/seed_data.py --universe"
    fi
else
    echo "[entrypoint] DB 已存在資料（或 AUTO_SEED=false）— 跳過 seed"
fi

# 4) 啟動 cron daemon
if [ "${ENABLE_CRON:-true}" = "true" ]; then
    echo "[entrypoint] 啟動 cron — 每個交易日 14:30 自動同步 + 策略掃描 + 告警評估"
    service cron start || cron
    touch /var/log/twquant-cron.log
else
    echo "[entrypoint] ENABLE_CRON=false — 跳過 cron"
fi

# 5) 啟動 Streamlit（foreground）
echo "[entrypoint] 🚀 啟動 Streamlit dashboard (port 8501)..."
exec python -m streamlit run /app/src/twquant/dashboard/app.py
