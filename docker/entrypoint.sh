#!/bin/bash
# twquant 容器啟動流程（lazy 模式）：
#   1. 同步 FINMIND_API_TOKEN → user_config.json
#   2. 啟動 cron daemon（ENABLE_CRON=true 預設）
#   3. 啟動 Streamlit（foreground）— 首次啟動由 dashboard onboarding 互動式抓取
#
# 不再自動 seed。資料抓取改由：
#   - Dashboard onboarding step 3（首次設定時）
#   - 頁 01「📡 資料中心」expander 手動補抓
#   - 背景 auto_sync（盤中 5min / 盤後 60min 自動擴展宇宙）

mkdir -p /app/data
echo "[entrypoint] twquant 啟動（lazy 模式）..."

# 1) 環境變數 dump 給 cron source
env | grep -E '^(FINMIND_API_TOKEN|DISCORD_WEBHOOK_URL|ARCTICDB_URI|TZ|PYTHONPATH)=' \
    > /app/.docker-env || true
chmod 600 /app/.docker-env

# 2) FINMIND_API_TOKEN env var → user_config.json
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

# 3) 啟動 cron daemon
# 預設停用（ENABLE_CRON=false）：資料同步改由 app 內部排程（頁 01 同步中心可設定時間）
# 若仍想用 14:30 cron，在 .env 加 ENABLE_CRON=true（與 app 排程二擇一，避免重複抓）
if [ "${ENABLE_CRON:-false}" = "true" ]; then
    echo "[entrypoint] 啟動 cron — 每個交易日 14:30 同步 + 掃描 + 告警"
    service cron start || cron
    touch /var/log/twquant-cron.log
else
    echo "[entrypoint] ENABLE_CRON=false — 資料同步由 app 排程（頁01同步中心）接管"
fi

# 4) 啟動 Streamlit
echo "[entrypoint] 🚀 Dashboard 將啟動於 http://localhost:8501"
echo "[entrypoint]    首次使用請開啟瀏覽器完成 onboarding（包含 token + 範圍 + 起始日）"
exec python -m streamlit run /app/src/twquant/dashboard/app.py
