"""共用訊號掃描模組 — 無 streamlit 依賴，供頁 08 / 首頁 / 告警 worker 共用"""

from __future__ import annotations
import pandas as pd


def scan_universe(
    strategy_keys: list[str],
    universe: list[str] | None = None,
    as_of: pd.Timestamp | None = None,
    db_path: str = "data/twquant.db",
    lookback_days: int = 300,
    min_bars: int = 120,
) -> pd.DataFrame:
    """
    對 universe 中的每支股票，套用 strategy_keys 中的每個策略，
    回傳最新 K 棒有進場訊號的股票清單。

    Parameters
    ----------
    strategy_keys : list[str]  策略 key（registry 中的 key）
    universe      : list[str]  股票代碼清單；None 代表取 DB 全部已入庫股票
    as_of         : pd.Timestamp  基準日（不含）；None 代表今日
    db_path       : str
    lookback_days : int  往前取幾天資料
    min_bars      : int  最少需要幾根 K 棒才跑策略

    Returns
    -------
    pd.DataFrame  columns: 代號, 策略, 資料截止, 收盤價, 距MA60%, RSI, 量比
    """
    import math
    from twquant.data.storage import SQLiteStorage
    from twquant.strategy.registry import get_strategy
    from twquant.indicators.basic import compute_ma, compute_rsi

    storage = SQLiteStorage(db_path)

    if universe is None:
        universe = [
            s.replace("daily_price/", "")
            for s in storage.list_symbols()
            if s.startswith("daily_price/")
        ]

    if as_of is None:
        as_of = pd.Timestamp.today().normalize()

    end_str   = (as_of - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start_str = (as_of - pd.DateOffset(days=lookback_days)).strftime("%Y-%m-%d")

    rows: list[dict] = []

    for sid in universe:
        df = storage.load(f"daily_price/{sid}", start_date=start_str, end_date=end_str)
        if df.empty or len(df) < min_bars:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        close    = df["close"].astype(float)
        last_dt  = df["date"].iloc[-1]
        last_px  = float(close.iloc[-1])
        ma60_val = float(compute_ma(close, 60).iloc[-1])
        rsi_val  = float(compute_rsi(close, 14).iloc[-1])
        vol5     = df["volume"].astype(float).iloc[-5:].mean()
        vol20    = df["volume"].astype(float).iloc[-20:].mean()
        vol_ratio = round(vol5 / vol20, 2) if vol20 > 0 else 1.0
        ma60_dist = (
            round((last_px / ma60_val - 1) * 100, 1)
            if not math.isnan(ma60_val) and ma60_val > 0
            else None
        )

        for key in strategy_keys:
            try:
                entries, _ = get_strategy(key).generate_signals(df)
                if len(entries) > 0 and bool(entries[-1]):
                    rows.append({
                        "代號":    sid,
                        "策略":    key,
                        "資料截止": last_dt.strftime("%Y-%m-%d"),
                        "收盤價":  last_px,
                        "距MA60%": ma60_dist,
                        "RSI":     round(rsi_val, 1) if not math.isnan(rsi_val) else None,
                        "量比":    vol_ratio,
                    })
            except Exception:
                pass

    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["代號", "策略", "資料截止", "收盤價", "距MA60%", "RSI", "量比"]
    )
