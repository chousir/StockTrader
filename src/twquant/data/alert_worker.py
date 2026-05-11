"""告警掃描 Worker — 對所有啟用規則評估觸發條件，寫入 alert_logs"""

from __future__ import annotations
import os
import pandas as pd

from twquant.data.alerts import list_rules, log_trigger, init_schema
from twquant.data.notifiers.discord import DiscordNotifier

DB_PATH = "data/twquant.db"


def _load_stock(stock_id: str, db_path: str) -> pd.DataFrame:
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(db_path)
    today = pd.Timestamp.today().normalize()
    end_str   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start_str = (today - pd.DateOffset(days=300)).strftime("%Y-%m-%d")
    df = storage.load(f"daily_price/{stock_id}", start_date=start_str, end_date=end_str)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _eval_price_break(df: pd.DataFrame, params: dict) -> tuple[bool, str]:
    lookback  = int(params.get("lookback", 20))
    direction = params.get("direction", "high")
    close = df["close"].astype(float)
    if len(close) < lookback + 1:
        return False, ""
    last  = float(close.iloc[-1])
    ref   = float(close.iloc[-lookback:-1].max() if direction == "high" else close.iloc[-lookback:-1].min())
    if direction == "high" and last > ref:
        return True, f"收盤 {last:.2f} 突破 {lookback} 日高點 {ref:.2f}"
    if direction == "low" and last < ref:
        return True, f"收盤 {last:.2f} 跌破 {lookback} 日低點 {ref:.2f}"
    return False, ""


def _eval_rsi_threshold(df: pd.DataFrame, params: dict) -> tuple[bool, str]:
    from twquant.indicators.basic import compute_rsi
    level     = float(params.get("level", 70))
    direction = params.get("direction", "above")
    close = df["close"].astype(float)
    rsi   = compute_rsi(close, 14)
    if len(rsi) < 2:
        return False, ""
    curr = float(rsi.iloc[-1])
    prev = float(rsi.iloc[-2])
    if direction == "above" and curr >= level and prev < level:
        return True, f"RSI {curr:.1f} 上穿 {level}"
    if direction == "below" and curr <= level and prev > level:
        return True, f"RSI {curr:.1f} 下穿 {level}"
    return False, ""


def _eval_strategy_signal(df: pd.DataFrame, params: dict) -> tuple[bool, str]:
    from twquant.strategy.registry import get_strategy
    key = params.get("strategy_key", "momentum_concentrate")
    if len(df) < 120:
        return False, ""
    try:
        entries, _ = get_strategy(key).generate_signals(df)
        if len(entries) > 0 and bool(entries[-1]):
            return True, f"策略 {key} 發出進場訊號"
    except Exception:
        pass
    return False, ""


_EVAL_MAP = {
    "price_break":      _eval_price_break,
    "rsi_threshold":    _eval_rsi_threshold,
    "strategy_signal":  _eval_strategy_signal,
}


def evaluate_all_rules(db_path: str = DB_PATH) -> int:
    """
    評估所有啟用規則，觸發者寫入 alert_logs。
    回傳觸發筆數。
    """
    init_schema(db_path)
    rules = [r for r in list_rules(db_path) if r["enabled"]]
    triggered = 0
    notifier = DiscordNotifier(os.getenv("DISCORD_WEBHOOK_URL", ""))
    for rule in rules:
        sid = rule["stock_id"]
        if sid in ("WATCHLIST", "UNIVERSE"):
            continue
        df = _load_stock(sid, db_path)
        if df.empty:
            continue
        fn = _EVAL_MAP.get(rule["rule_type"])
        if fn is None:
            continue
        fired, msg = fn(df, rule["params"])
        if fired:
            log_trigger(rule["id"], sid, f"[{rule['name']}] {msg}", db_path)
            notifier.notify_alert(rule["name"], sid, msg)
            triggered += 1
    return triggered


_LAST_EVAL_TS: dict[str, pd.Timestamp] = {}


def auto_evaluate_on_dashboard_load(db_path: str = DB_PATH, interval_minutes: int = 30) -> int:
    """
    供首頁 @st.cache_resource 包裝，距上次掃描超過 interval_minutes 才重跑。
    回傳本次觸發筆數（0 代表未到期或無觸發）。
    """
    global _LAST_EVAL_TS
    now = pd.Timestamp.now()
    last = _LAST_EVAL_TS.get(db_path, pd.Timestamp("2000-01-01"))
    if (now - last).total_seconds() < interval_minutes * 60:
        return 0
    _LAST_EVAL_TS[db_path] = now
    try:
        return evaluate_all_rules(db_path)
    except Exception:
        return 0
