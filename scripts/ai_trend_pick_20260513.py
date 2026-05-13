"""
AI 趨勢產業選股分析 — 2026-05-13
基準日: 2026-05-12（DB 最新交易日）
分析師視角：完整 AI 8 大子產業 50 支候選 + 0050 基準
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import numpy as np
import pandas as pd
from twquant.data.storage import SQLiteStorage
from twquant.indicators import basic as ind
from twquant.strategy.registry import get_strategy

DB = "data/twquant.db"
ANCHOR_DATE = "2026-05-12"
RISK_BUDGET = 100_000

AI_UNIVERSE = {
    "晶圓代工": [("2330","台積電"),("2303","聯電"),("6770","力積電"),("5347","世界先進")],
    "IC設計/ASIC": [("2454","聯發科"),("3661","世芯-KY"),("3443","創意"),("3035","智原"),
                   ("5269","祥碩"),("5274","信驊"),("3034","聯詠"),("6533","晶心科")],
    "封裝測試":   [("3711","日月光投控"),("6147","頎邦"),("6515","穎崴")],
    "AI伺服器":   [("2317","鴻海"),("2382","廣達"),("2376","技嘉"),("2377","微星"),
                   ("2357","華碩"),("2356","英業達"),("3231","緯創"),("6669","緯穎"),("2353","宏碁")],
    "散熱機構":   [("3017","奇鋐"),("3324","雙鴻"),("3653","健策"),("6230","尼得科超眾"),("2059","川湖")],
    "HBM/記憶體": [("2408","南亞科"),("8299","群聯"),("3260","威剛"),("4967","十銓")],
    "光通訊":     [("4977","眾達-KY"),("4979","華星光"),("3406","玉晶光"),("3081","聯亞"),("3530","晶相光")],
    "網通/耗材":  [("2345","智邦"),("6285","啟碁"),("6488","環球晶"),("3680","家登"),("6803","崇越")],
    "電源/被動/PCB": [("2308","台達電"),("2327","國巨*"),("2492","華新科"),("2383","台光電"),("6213","聯茂")],
    "AI應用":     [("2395","研華")],
}

STRATS = ["momentum_concentrate", "volume_breakout", "triple_ma_twist",
          "risk_adj_momentum", "donchian_breakout"]
STRAT_LABEL = {
    "momentum_concentrate": "F動能", "volume_breakout": "H量價",
    "triple_ma_twist": "L三線", "risk_adj_momentum": "M-RAM",
    "donchian_breakout": "N唐奇安",
}

def load(sid: str) -> pd.DataFrame:
    s = SQLiteStorage(DB)
    df = s.load(f"daily_price/{sid}", start_date="2026-01-01")
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    for c in ["open","high","low","close","volume"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def compute_features(df: pd.DataFrame, bench: pd.DataFrame) -> dict:
    close = df["close"]
    high = df["high"]
    low = df["low"]
    vol = df["volume"]
    n = len(df)

    ma5  = close.rolling(5).mean().iloc[-1]
    ma20 = close.rolling(20).mean().iloc[-1]
    ma60 = close.rolling(60).mean().iloc[-1] if n >= 60 else np.nan
    rsi14 = ind.compute_rsi(close, 14).iloc[-1]
    macd_line, signal_line, _ = ind.compute_macd(close)
    macd_diff = (macd_line - signal_line).iloc[-1]
    atr14 = ind.compute_atr(high, low, close, 14).iloc[-1]

    vol5  = vol.rolling(5).mean().iloc[-1]
    vol20 = vol.rolling(20).mean().iloc[-1]
    vol_ratio = vol5 / vol20 if vol20 > 0 else np.nan

    chg_20d = (close.iloc[-1] / close.iloc[-21] - 1) if n >= 21 else np.nan
    chg_60d = (close.iloc[-1] / close.iloc[-61] - 1) if n >= 61 else np.nan

    # RS vs 0050（用 2026-01-01 起的相對表現）
    bench_aligned = bench.set_index("date").reindex(df["date"]).reset_index()
    s_norm = close / close.iloc[0]
    b_norm = bench_aligned["close"] / bench_aligned["close"].iloc[0]
    rs = s_norm / b_norm
    rs_now = rs.iloc[-1]
    rs_max = rs.max()
    rs_new_high = rs_now >= rs_max * 0.99  # 處於 RS 區間 99% 高位

    # Beta（與 0050 日報酬）
    s_r = close.pct_change().dropna()
    b_r = bench_aligned["close"].pct_change().dropna()
    common = s_r.index.intersection(b_r.index)
    if len(common) >= 30:
        sr = s_r.loc[common].values
        br = b_r.loc[common].values
        beta = float(np.cov(sr, br)[0,1] / np.var(br))
    else:
        beta = np.nan

    return {
        "close": float(close.iloc[-1]),
        "ma5": float(ma5) if pd.notna(ma5) else np.nan,
        "ma20": float(ma20) if pd.notna(ma20) else np.nan,
        "ma60": float(ma60) if pd.notna(ma60) else np.nan,
        "rsi14": float(rsi14) if pd.notna(rsi14) else np.nan,
        "macd_diff": float(macd_diff) if pd.notna(macd_diff) else np.nan,
        "atr14": float(atr14) if pd.notna(atr14) else np.nan,
        "vol_ratio": float(vol_ratio) if pd.notna(vol_ratio) else np.nan,
        "chg_20d": float(chg_20d) if pd.notna(chg_20d) else np.nan,
        "chg_60d": float(chg_60d) if pd.notna(chg_60d) else np.nan,
        "rs_now": float(rs_now) if pd.notna(rs_now) else np.nan,
        "rs_new_high": bool(rs_new_high),
        "beta": beta,
    }

def scan_strategies(df: pd.DataFrame) -> tuple[list[str], int]:
    """跑 5 策略，回傳近 5 日內觸發的策略 key 列表 + 共振分數"""
    fired = []
    for key in STRATS:
        try:
            entries, exits = get_strategy(key).generate_signals(df)
            if isinstance(entries, pd.Series):
                last5_entries = entries.iloc[-5:].any() if len(entries) >= 5 else entries.any()
            else:  # numpy array
                last5_entries = bool(entries[-5:].any()) if len(entries) >= 5 else bool(entries.any())
            if last5_entries:
                fired.append(key)
        except Exception:
            pass
    return fired, len(fired)

def position_calc(close: float, atr14: float, budget: float = RISK_BUDGET) -> dict:
    stop = close - 1.5 * atr14
    risk_per_share = max(close - stop, 0.01)
    lots = int(budget / (risk_per_share * 1000))
    r1 = close + 2 * (close - stop)
    r2 = close + 3 * (close - stop)
    return {"stop": stop, "r1": r1, "r2": r2, "lots": lots,
            "risk_per_share": risk_per_share}

def main():
    print(f"\n{'='*100}")
    print(f"AI 趨勢產業選股分析 — 基準日 {ANCHOR_DATE}（風險預算 ${RISK_BUDGET:,}）")
    print(f"{'='*100}\n")

    bench = load("0050")
    print(f"0050 基準：{bench['date'].min().date()} ~ {bench['date'].max().date()} ({len(bench)} 筆)")
    bench_chg_5d = float(bench['close'].iloc[-1] / bench['close'].iloc[-6] - 1) if len(bench) >= 6 else 0
    print(f"0050 近 5 日：{bench_chg_5d:+.2%}\n")

    rows = []
    for sector, stocks in AI_UNIVERSE.items():
        for sid, name in stocks:
            df = load(sid)
            if df.empty or len(df) < 30:
                continue
            f = compute_features(df, bench)
            fired, score = scan_strategies(df)
            pc = position_calc(f["close"], f["atr14"]) if pd.notna(f["atr14"]) else None
            rows.append({
                "sector": sector, "sid": sid, "name": name,
                **f,
                "fired_strats": fired,
                "score": score,
                **(pc or {}),
            })

    df_all = pd.DataFrame(rows)
    df_all["fired_label"] = df_all["fired_strats"].apply(
        lambda lst: "+".join(STRAT_LABEL[k] for k in lst) if lst else "-"
    )

    # ── Step 2 動能初篩：chg_20d > 0 + close > ma60 + rs_new_high (寬鬆) ──
    print("="*100)
    print("Step 2：動能初篩（漲幅+突破+量比+RS）")
    print("="*100)
    mom_pass = df_all[
        (df_all["chg_20d"] > 0)
        & (df_all["close"] > df_all["ma60"])
    ].copy()
    mom_pass["rs_pct"] = mom_pass["rs_now"].rank(pct=True)
    n1 = mom_pass[mom_pass["rs_pct"] >= 0.5]  # 前 50% RS
    print(f"通過動能初篩：{len(n1)} 支（共 {len(df_all)} 支）")

    # ── Step 3 多策略共振 ≥1 ──
    print("\n" + "="*100)
    print("Step 3：多策略共振")
    print("="*100)
    sigs = df_all[df_all["score"] >= 1].copy()
    print(f"5 策略中 ≥1 觸發：{len(sigs)} 支")
    print(f"≥2 共振：{len(sigs[sigs['score']>=2])} 支")
    print(f"≥3 共振：{len(sigs[sigs['score']>=3])} 支")

    # ── Step 4 健康度過濾 ──
    print("\n" + "="*100)
    print("Step 4：技術面健康度檢核")
    print("="*100)
    healthy = df_all[
        (df_all["close"] > df_all["ma20"])
        & (df_all["ma20"] > df_all["ma60"])
        & (df_all["rsi14"] >= 30) & (df_all["rsi14"] <= 80)
        & (df_all["macd_diff"] > 0)
        & (df_all["vol_ratio"] >= 0.8)
    ].copy()
    print(f"技術面健康：{len(healthy)} 支")

    # ── 兩級名單 ──
    healthy_sig = healthy[healthy["score"] >= 1].copy()
    main_picks = healthy_sig[
        (healthy_sig["score"] >= 2)
        & (healthy_sig["rsi14"] >= 50) & (healthy_sig["rsi14"] <= 75)
    ].sort_values(["score","chg_20d"], ascending=False)
    obs_picks = healthy_sig[~healthy_sig["sid"].isin(main_picks["sid"])].sort_values("score", ascending=False)

    print("\n" + "="*100)
    print("最終建議名單")
    print("="*100)

    def show(df, title):
        print(f"\n【{title}】({len(df)} 支)")
        if df.empty:
            print("  (空)")
            return
        cols = ["sid","name","sector","close","stop","r1","r2","lots",
                "rsi14","chg_20d","rs_now","fired_label","score"]
        sub = df[cols].copy()
        sub.columns = ["代號","名稱","子產業","收盤","停損","R1","R2","張數",
                       "RSI","20d漲","RS","共振策略","分"]
        for c in ["收盤","停損","R1","R2"]:
            sub[c] = sub[c].round(1)
        sub["RSI"] = sub["RSI"].round(1)
        sub["20d漲"] = (sub["20d漲"]*100).round(1).astype(str) + "%"
        sub["RS"] = sub["RS"].round(2)
        print(sub.to_string(index=False))

    show(main_picks, "⭐ 主推（2+ 策略共振 + 健康趨勢 + RSI 50-75）")
    show(obs_picks.head(8), "👀 觀察（1+ 策略共振 + 健康趨勢，動能偏弱）")

    # 候選池總覽（依共振分排序）
    print("\n" + "="*100)
    print("Full Pool 排序（依共振分數降序，前 20）")
    print("="*100)
    top = df_all.sort_values(["score","chg_20d"], ascending=False).head(20)
    cols = ["sid","name","sector","close","rsi14","chg_20d","rs_now","fired_label","score"]
    sub = top[cols].copy()
    sub.columns = ["代號","名稱","子產業","收盤","RSI","20d漲","RS","共振策略","分"]
    sub["收盤"] = sub["收盤"].round(1)
    sub["RSI"] = sub["RSI"].round(1)
    sub["20d漲"] = (sub["20d漲"]*100).round(1).astype(str) + "%"
    sub["RS"] = sub["RS"].round(2)
    print(sub.to_string(index=False))

    # 子產業強度榜
    print("\n" + "="*100)
    print("子產業強度榜（平均 20 日漲幅）")
    print("="*100)
    by_sec = df_all.groupby("sector").agg(
        股數=("sid","count"),
        平均20d漲=("chg_20d","mean"),
        平均60d漲=("chg_60d","mean"),
        平均RS=("rs_now","mean"),
        共振總分=("score","sum"),
    ).sort_values("平均20d漲", ascending=False)
    by_sec["平均20d漲"] = (by_sec["平均20d漲"]*100).round(1).astype(str) + "%"
    by_sec["平均60d漲"] = (by_sec["平均60d漲"]*100).round(1).astype(str) + "%"
    by_sec["平均RS"] = by_sec["平均RS"].round(2)
    print(by_sec.to_string())

    return main_picks, obs_picks, df_all

if __name__ == "__main__":
    main()
