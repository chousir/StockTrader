"""每日選股 orchestrator — 跑訂閱策略 → 寫入 daily_scans → 推播 Discord"""

from __future__ import annotations
import os

import pandas as pd
from loguru import logger

from twquant.data.daily_scans import (
    DB_PATH,
    init_schema,
    list_subscriptions,
    save_scan_results,
)
from twquant.data.notifiers.discord import DiscordNotifier
from twquant.strategy.scanner import scan_universe


def run_daily_scan(db_path: str = DB_PATH, notify: bool = True) -> dict:
    """執行每日策略掃描，寫入結果並可選擇推播。

    Returns
    -------
    dict  {"strategies": int, "picks": int, "notified": bool, "scan_date": str}
    """
    init_schema(db_path)
    subs = [s for s in list_subscriptions(db_path) if s["enabled"]]
    scan_date = (pd.Timestamp.today().normalize() - pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    if not subs:
        logger.info("沒有啟用的策略訂閱，跳過每日掃描")
        return {"strategies": 0, "picks": 0, "notified": False, "scan_date": scan_date}

    keys = [s["strategy_key"] for s in subs]
    logger.info(f"開始每日策略掃描：{keys}")
    df = scan_universe(strategy_keys=keys, db_path=db_path)
    n_picks = save_scan_results(scan_date, df, db_path)
    logger.info(f"每日策略掃描完成，{n_picks} 筆訊號寫入 {scan_date}")

    notified = False
    if notify:
        webhook = os.getenv("DISCORD_WEBHOOK_URL", "")
        notifier = DiscordNotifier(webhook)
        if notifier.enabled:
            notified = notifier.notify_daily_picks(scan_date, df)
            if notified:
                logger.info("Discord 推播成功")
            else:
                logger.warning("Discord 推播未發送或失敗")
        else:
            logger.info("DISCORD_WEBHOOK_URL 未設定，略過推播")

    return {"strategies": len(keys), "picks": n_picks, "notified": notified, "scan_date": scan_date}
