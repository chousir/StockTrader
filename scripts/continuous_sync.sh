#!/usr/bin/env bash
# continuous_sync.sh：持續同步全市場股票資料
# 第一輪：完整下載（--all --skip-existing，跳過近3天已更新的）
# 後續輪：增量補齊（--all --incremental），確保資料最新
# 輸出 log 至 /tmp/twquant_sync.log

LOG="/tmp/twquant_sync.log"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

cd "$PROJECT_DIR" || exit 1

CYCLE=0

while true; do
    CYCLE=$((CYCLE + 1))
    log "=== 第 ${CYCLE} 輪同步開始 ==="

    if [ "$CYCLE" -eq 1 ]; then
        # 第一輪：完整下載全市場，已有近期資料的跳過
        log "模式：全市場首次完整下載 (--all --skip-existing)"
        python scripts/seed_data.py --all --start 2015-01-01 --skip-existing 2>&1 | tee -a "$LOG"
    else
        # 後續輪：從 HWM 增量補到今天
        log "模式：全市場增量補齊 (--all --incremental)"
        python scripts/seed_data.py --all --incremental 2>&1 | tee -a "$LOG"
    fi

    # 印出 DB 當前狀態
    python -c "
import sys; sys.path.insert(0,'src')
from twquant.data.storage import SQLiteStorage
import datetime
s = SQLiteStorage('data/twquant.db')
syms = s.list_symbols()
today = datetime.date.today()
fresh = sum(1 for sym in syms if (hwm := s.get_hwm(sym)) and (today - hwm).days <= 3)
print(f'[DB] 共 {len(syms)} 支 | 近3日新鮮: {fresh} 支 | 落後: {len(syms)-fresh} 支')
" 2>&1 | tee -a "$LOG"

    log "=== 第 ${CYCLE} 輪完成，等待 30 分鐘後繼續 ==="
    sleep 1800
done
