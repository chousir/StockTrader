"""分析師排行榜 — 漲幅/跌幅/量爆/突破/超賣，供首頁 tabs 使用"""
from __future__ import annotations
import pandas as pd

DB_PATH = "data/twquant.db"


def daily_rankings(top_n: int = 20, db_path: str = DB_PATH) -> dict[str, pd.DataFrame]:
    """
    回傳 {
        'gainers':   漲幅榜（chg_pct desc）,
        'losers':    跌幅榜,
        'vol_surge': 量爆榜（vol5/vol20 desc, 收盤紅）,
        'breakouts': 突破榜（創 20 日新高 + 量比 > 1.5）,
        'oversold':  超賣榜（RSI < 30 + Close > MA60）,
    }
    """
    from twquant.data.storage import SQLiteStorage
    from twquant.indicators.basic import compute_rsi, compute_ma

    storage = SQLiteStorage(db_path)
    universe = [
        s.replace("daily_price/", "")
        for s in storage.list_symbols()
        if s.startswith("daily_price/")
    ]

    today = pd.Timestamp.today().normalize()
    end_str   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start_str = (today - pd.DateOffset(days=60)).strftime("%Y-%m-%d")

    rows: list[dict] = []
    for sid in universe:
        df = storage.load(f"daily_price/{sid}", start_date=start_str, end_date=end_str)
        if df.empty or len(df) < 22:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        vol   = df["volume"].astype(float)

        last_close = float(close.iloc[-1])
        prev_close = float(close.iloc[-2])
        chg_pct    = (last_close / prev_close - 1) * 100

        vol5  = float(vol.iloc[-5:].mean())  if len(vol) >= 5  else float(vol.mean())
        vol20 = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())
        vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0

        ma60  = float(compute_ma(close, 60).iloc[-1]) if len(close) >= 60 else None
        rsi14 = float(compute_rsi(close, 14).iloc[-1]) if len(close) >= 15 else None

        is_breakout = False
        if len(close) >= 21:
            high20 = float(close.iloc[-21:-1].max())
            is_breakout = last_close > high20 and vol_ratio > 1.5

        rows.append({
            "代號":   sid,
            "現價":   round(last_close, 2),
            "漲跌%":  round(chg_pct, 2),
            "量比":   round(vol_ratio, 2),
            "RSI":    round(rsi14, 1) if rsi14 is not None else float("nan"),
            "_ma60":  float(ma60) if ma60 is not None else float("nan"),
            "_is_up": last_close >= prev_close,
            "_brk":   is_breakout,
        })

    _COLS = ["代號", "現價", "漲跌%", "量比", "RSI"]

    if not rows:
        empty = pd.DataFrame(columns=_COLS)
        return {k: empty for k in ("gainers", "losers", "vol_surge", "breakouts", "oversold")}

    df_all = pd.DataFrame(rows)

    oversold_mask = (
        df_all["RSI"].notna() & (df_all["RSI"] < 30) &
        df_all["_ma60"].notna() & (df_all["現價"] > df_all["_ma60"])
    )
    return {
        "gainers":   df_all.nlargest(top_n, "漲跌%")[_COLS].reset_index(drop=True),
        "losers":    df_all.nsmallest(top_n, "漲跌%")[_COLS].reset_index(drop=True),
        "vol_surge": df_all[df_all["_is_up"]].nlargest(top_n, "量比")[_COLS].reset_index(drop=True),
        "breakouts": df_all[df_all["_brk"]].nlargest(top_n, "量比")[_COLS].reset_index(drop=True),
        "oversold":  df_all[oversold_mask].nsmallest(top_n, "RSI")[_COLS].reset_index(drop=True),
    }
