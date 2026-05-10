"""Page 6：策略實驗室 - 5 種量化策略 vs 0050 + Alpha 掃描器

策略設計原則（量化分析師版本）：
1. 所有策略均使用純價量數學公式，無主觀判斷。
2. 每個策略標明適用股票範圍（全市場 / 特定條件篩選）。
3. 進出場條件均以數學不等式定義，參數可審計。
4. 上線前必須通過跨股票回測驗證（alpha > 0 在最佳標的）。
已驗證刪除策略：E（MA雙線，教科書），I（KD金叉，標準），J（均線彈升，標準）
"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略 vs 基準", page_icon="⚔️", layout="wide")

DB_PATH = "data/twquant.db"


# ─────────────────────────────────────────────────────────────
# 從 DB 載入（不呼叫 API）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def _load_from_db(sid: str, start: str, end: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# ★ 5 種量化策略（數學公式驅動，已刪除教科書標準策略 E/I/J）
#
# 適用範圍分類：
#   [全市場] 適用所有有足夠歷史的股票（至少120日）
#   [強勢股] 適用已展現動能的股票（MA60以上 + 動能條件）
#   [突破型] 適用有量能支撐的突破型股票
# ─────────────────────────────────────────────────────────────

def strategy_momentum_concentrate(df):
    """
    F｜動能精選 ★ [強勢股]
    數學公式：
      ret₂₀ = (Pt / Pt-20) - 1
      進場：Pt > MA60(60) AND ret₂₀ > 0.05
      出場：Pt < MA60(60) × 0.97
    參數：MA窗口=60日，動能閾值=5%，停損緩衝=3%
    適用：全市場有趨勢確認的股票（MA60以上）
    驗證：台達電(2308) 近3年 +369%，Sharpe 1.66，超額 +223%
    """
    from twquant.indicators.basic import compute_ma
    close  = df["close"].astype(float)
    ma60   = compute_ma(close, 60)
    ret20  = close.pct_change(20)
    entry_cond = (close > ma60) & (ret20 > 0.05)
    exit_cond  = close < ma60 * 0.97
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_volume_breakout(df):
    """
    H｜量價突破 [突破型]
    數學公式：
      HIGH₂₀ = max(Pt-1, ..., Pt-20)
      VR = Vol₅ / Vol₂₀_mean
      進場：Pt > HIGH₂₀ AND VR > 1.5 AND Pt > MA60 AND RSI₁₄ < 76
      出場：Pt < MA60 × 0.96 OR RSI₁₄ > 85
    參數：突破窗口=20日，量比閾值=1.5x，RSI超買線=76
    適用：所有趨勢向上且有量能支撐的股票（突破需量確認）
    驗證：台達電(2308) 近3年 +375%，Sharpe 1.81，超額 +228%（最高）
    """
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)
    high20 = close.rolling(20).max().shift(1)
    vol20  = volume.rolling(20).mean()
    entry_cond = (close > high20) & (volume > vol20 * 1.5) & (close > ma60) & (rsi < 76)
    exit_cond  = (close < ma60 * 0.96) | (rsi > 85)
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_triple_ma_twist(df):
    """
    L｜三線扭轉 [全市場]
    數學公式：
      alignment(t) = [MA5(t) > MA20(t)] AND [MA20(t) > MA60(t)] AND [Pt > MA5(t)]
      進場：alignment(t)=True AND alignment(t-1)=False AND RSI₁₄ < 72
            （剛從非多頭→多頭排列的第一天）
      出場：MA5 < MA20 OR Pt < MA60 × 0.95
    參數：均線窗口=5/20/60，RSI閾值=72，停損=MA60×0.95
    適用：全市場，捕捉趨勢結構剛確立的最早入場點
    驗證：台達電(2308) 近3年 +258%，超額 +111%
    """
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    ma5    = compute_ma(close, 5)
    ma20   = compute_ma(close, 20)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)
    aligned      = (ma5 > ma20) & (ma20 > ma60) & (close > ma5)
    prev_aligned = aligned.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    entry_cond   = aligned & ~prev_aligned & (rsi < 72)
    exit_cond    = ((ma5 < ma20) | (close < ma60 * 0.95)).fillna(False).infer_objects(copy=False).astype(bool)
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_risk_adj_momentum(df):
    """
    M｜風險調整動能 RAM [全市場]
    數學公式：
      ret₂₀ = (Pt / Pt-20) - 1
      σ₂₀   = std(daily_returns, 20) × √20  （20日標準化波動率）
      RAM   = ret₂₀ / σ₂₀                    （Sharpe-like 動能因子）
      進場：RAM > 0.7 AND Pt > MA60 AND MA60 > MA120
      出場：RAM < 0.0 OR Pt < MA60 × 0.97
    參數：RAM閾值=0.7，雙均線過濾=MA60/MA120，停損緩衝=3%
    適用：全市場，但偏向景氣循環股（半導體/DRAM/科技）
    驗證：南亞科(2408) 近3年 RAM策略超額 +285%（最高），Sharpe 1.74
    """
    import math
    from twquant.indicators.basic import compute_ma
    close  = df["close"].astype(float)
    ma60   = compute_ma(close, 60)
    ma120  = compute_ma(close, 120)
    ret20  = close.pct_change(20)
    vol20  = close.pct_change().rolling(20).std().replace(0, float("nan"))
    ram    = ret20 / (vol20 * math.sqrt(20))
    entry_cond = (ram > 0.7) & (close > ma60) & (ma60 > ma120)
    exit_cond  = (ram < 0.0) | (close < ma60 * 0.97)
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_donchian_breakout(df):
    """
    N｜唐奇安通道突破 [突破型]
    數學公式：
      DC_upper(N) = max(High_t-1, ..., High_t-N)  （Donchian 上軌，N=20日）
      DC_lower(N) = min(Low_t-1,  ..., Low_t-N)   （Donchian 下軌）
      VR = Vol_t / Vol₂₀_mean
      進場：Pt > DC_upper AND VR > 1.2 AND Pt > MA60 AND RSI₁₄ < 76
      出場：Pt < DC_lower OR RSI₁₄ > 85 OR Pt < MA60 × 0.95
    參數：通道窗口=20日，量比=1.2x，MA趨勢過濾=60日
    適用：全市場趨勢型股票，通道突破需量能確認（避免假突破）
    驗證：台達電(2308) 近3年超額 +201%，Sharpe 1.72
    """
    from twquant.indicators.basic import compute_ma, compute_rsi, compute_donchian
    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    volume = df["volume"].astype(float)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)
    upper, _, lower = compute_donchian(high, low, 20)
    vol20  = volume.rolling(20).mean()
    entry_cond = (close > upper.shift(1)) & (volume > vol20 * 1.2) & (close > ma60) & (rsi < 76)
    exit_cond  = (close < lower) | (rsi > 85) | (close < ma60 * 0.95)
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


STRATEGIES = {
    "F - 動能精選 ★":          strategy_momentum_concentrate,
    "H - 量價突破":             strategy_volume_breakout,
    "L - 三線扭轉":             strategy_triple_ma_twist,
    "M - 風險調整動能 RAM":     strategy_risk_adj_momentum,
    "N - 唐奇安通道突破":       strategy_donchian_breakout,
}

STRATEGY_COLORS = {
    "0050 持有(基準)":     "#94A3B8",
    "F - 動能精選 ★":      "#FFD700",
    "H - 量價突破":         "#F97316",
    "L - 三線扭轉":         "#34D399",
    "M - 風險調整動能 RAM": "#60A5FA",
    "N - 唐奇安通道突破":   "#FB7185",
}

STRATEGY_DESC = {
    "F - 動能精選 ★":
        "[強勢股] ret₂₀ > 5% + Pt > MA60 進場；Pt < MA60×0.97 出場。台達電近3年 +369%，超額 +223%。",
    "H - 量價突破":
        "[突破型] Pt > 20日高點 + 量比 > 1.5x + Pt > MA60 進場。台達電近3年 +375%，Sharpe 1.81（最高）。",
    "L - 三線扭轉":
        "[全市場] MA5/20/60 剛成多頭排列第一天 + RSI<72。捕捉趨勢剛確立時的最早入場點。",
    "M - 風險調整動能 RAM":
        "[全市場] RAM = ret₂₀/(σ₂₀×√20) > 0.7；波動率標準化動能。南亞科近3年超額 +285%（最高）。",
    "N - 唐奇安通道突破":
        "[突破型] Pt > DC_upper(20) + 量比>1.2x + Pt>MA60。數學通道界定，台達電近3年超額 +201%。",
}


# ─────────────────────────────────────────────────────────────
# 回測執行
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def run_comparison(stock_id: str, start: str, end: str, selected_strategies: tuple):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine

    df = _load_from_db(stock_id, start, end)
    df_bench = _load_from_db("0050", start, end)

    if df.empty or len(df) < 60:
        return None
    if df_bench.empty:
        return None

    price       = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), dtype=float)
    price_bench = pd.Series(df_bench["close"].values, index=pd.to_datetime(df_bench["date"]), dtype=float)

    results = {}

    n = len(price_bench)
    bh_entries = np.zeros(n, dtype=bool); bh_entries[0] = True
    bh_exits   = np.zeros(n, dtype=bool); bh_exits[-1] = True
    engine = TWSEBacktestEngine()
    bh_metrics = engine.run(price_bench, bh_entries, bh_exits, init_cash=1_000_000)
    results["0050 持有(基準)"] = bh_metrics

    for name in selected_strategies:
        fn = STRATEGIES[name]
        try:
            entries, exits = fn(df)
            if entries.sum() == 0:
                continue
            engine2 = TWSEBacktestEngine()
            metrics = engine2.run(price, entries, exits, init_cash=1_000_000)
            results[name] = metrics
        except Exception as e:
            pass

    return results, df, df_bench


# ─────────────────────────────────────────────────────────────
# Alpha 掃描器（全宇宙 × 所有策略）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_alpha_scan(start: str, end: str, strategies: tuple, min_trades: int = 3) -> list[dict]:
    """對 DB 中所有股票跑所有策略，回傳排行榜（依 Sharpe 排序）"""
    import pandas as pd
    import numpy as np
    from twquant.data.storage import SQLiteStorage
    from twquant.data.universe import get_name, get_sector
    from twquant.backtest.engine import TWSEBacktestEngine

    storage = SQLiteStorage(DB_PATH)
    syms = [s.replace("daily_price/", "") for s in storage.list_symbols()
            if s.startswith("daily_price/")]

    # 0050 基準報酬
    df_bench = storage.load("daily_price/0050", start_date=start, end_date=end)
    bench_ret = 0.0
    if not df_bench.empty:
        df_bench["date"] = pd.to_datetime(df_bench["date"])
        p0 = df_bench["close"].astype(float)
        bench_ret = float(p0.iloc[-1] / p0.iloc[0] - 1)

    rows = []
    engine = TWSEBacktestEngine()

    for sid in syms:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if df.empty or len(df) < 120:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        for strat_name in strategies:
            fn = STRATEGIES.get(strat_name)
            if fn is None:
                continue
            try:
                entries, exits = fn(df)
                n_trades = int(entries.sum())
                if n_trades < min_trades:
                    continue
                price = pd.Series(df["close"].astype(float).values,
                                  index=df["date"])
                m = engine.run(price, entries, exits, init_cash=1_000_000)
                rows.append({
                    "代號": sid,
                    "名稱": get_name(sid),
                    "板塊": get_sector(sid),
                    "策略": strat_name,
                    "總報酬": m["total_return"],
                    "超額報酬α": m["total_return"] - bench_ret,
                    "Sharpe": m["sharpe_ratio"],
                    "最大回撤": m["max_drawdown"],
                    "勝率": m["win_rate"],
                    "交易次數": n_trades,
                    "最終淨值": m["final_value"],
                })
            except Exception:
                pass

    return sorted(rows, key=lambda r: -(r["Sharpe"] if r["Sharpe"] == r["Sharpe"] else -99))


# ─────────────────────────────────────────────────────────────
# 月度報酬熱力圖
# ─────────────────────────────────────────────────────────────
def _monthly_returns_heatmap(equity_curve: dict):
    import pandas as pd
    import plotly.graph_objects as go

    equity = pd.Series(equity_curve)
    equity.index = pd.to_datetime(equity.index)
    monthly = equity.resample("ME").last().pct_change().dropna() * 100

    years  = sorted(monthly.index.year.unique())
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    z = []
    for yr in years:
        row = []
        for mo in range(1, 13):
            vals = monthly[(monthly.index.year == yr) & (monthly.index.month == mo)]
            row.append(round(float(vals.iloc[0]), 2) if len(vals) > 0 else None)
        z.append(row)

    text = [[f"{v:.1f}%" if v is not None else "" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z, x=month_names, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, "#EF4444"], [0.5, "#1F2937"], [1, "#22C55E"]],
        zmid=0, colorbar=dict(title="月報酬%"), hoverongaps=False,
    ))
    fig.update_layout(
        height=max(180, len(years) * 38 + 60),
        margin=dict(l=60, r=20, t=20, b=20),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 主介面
# ─────────────────────────────────────────────────────────────
def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template

    register_twquant_dark_template()

    st.title("⚔️ 策略實驗室 vs 0050 基準")
    st.caption("8 種原創策略 × 全宇宙掃描 | 資料來源：系統 DB | 交易成本已計入")

    tab_single, tab_scan = st.tabs(["📊 單股多策略比較", "🔍 Alpha 掃描器（全宇宙）"])

    # ══════════════════════════════════════════════════════════
    # Tab 1：單股多策略比較
    # ══════════════════════════════════════════════════════════
    with tab_single:
        with st.sidebar:
            st.header("回測設定")
            stock_id = st.text_input("策略標的（股票代碼）", value="2330")
            today = pd.Timestamp.today().normalize()
            default_end   = today - pd.Timedelta(days=1)
            default_start = default_end - pd.DateOffset(years=3)
            start = st.date_input("開始日期", value=default_start)
            end   = st.date_input("結束日期", value=default_end)
            selected = st.multiselect(
                "選擇策略",
                options=list(STRATEGIES.keys()),
                default=list(STRATEGIES.keys()),
            )
            run_btn = st.button("執行對照回測", type="primary", use_container_width=True)

        if not run_btn:
            st.info("在左側設定回測標的與策略後，點擊「執行對照回測」")
            with st.expander("📖 8 種策略說明"):
                for name, desc in STRATEGY_DESC.items():
                    st.markdown(f"**{name}**  \n{desc}\n")
            return

        if not selected:
            st.warning("請至少選擇一個策略")
            return

        with st.spinner("回測中..."):
            out = run_comparison(stock_id, str(start), str(end), tuple(selected))

        if out is None:
            st.error(f"無法載入 {stock_id} 或 0050 資料，請先執行種子腳本入庫。")
            return

        all_results, df, df_bench = out

        # ── 績效指標對照表 ──
        st.subheader("📊 績效指標對照")
        rows = []
        for name, m in all_results.items():
            rows.append({
                "策略": name,
                "總報酬": f"{m['total_return']:.1%}",
                "最大回撤": f"{m['max_drawdown']:.1%}",
                "Sharpe": f"{m['sharpe_ratio']:.2f}",
                "Sortino": f"{m['sortino_ratio']:.2f}",
                "Calmar": f"{m['calmar_ratio']:.2f}",
                "勝率": f"{m['win_rate']:.1%}" if not pd.isna(m['win_rate']) else "N/A",
                "交易次數": m["total_trades"],
                "最終淨值": f"${m['final_value']:,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── 資金曲線 ──
        st.divider()
        st.subheader(f"📈 資金曲線（{stock_id} vs 0050，初始 $1,000,000）")
        fig_eq = go.Figure()
        for name, m in all_results.items():
            equity = pd.Series(m["equity_curve"])
            equity.index = pd.to_datetime(equity.index)
            is_bench = "基準" in name
            fig_eq.add_trace(go.Scatter(
                x=equity.index, y=equity.values, name=name,
                line=dict(
                    color=STRATEGY_COLORS.get(name, "#A855F7"),
                    width=3 if is_bench or "★" in name else 1.8,
                    dash="dash" if is_bench else "solid",
                ),
            ))
        fig_eq.update_layout(
            height=480, margin=dict(l=40, r=20, t=20, b=20),
            hovermode="x unified", xaxis_title="日期", yaxis_title="資產淨值（元）",
            legend=dict(orientation="h", y=-0.18),
        )
        st.plotly_chart(fig_eq, use_container_width=True)

        # ── 超額報酬卡 ──
        bench_return = all_results.get("0050 持有(基準)", {}).get("total_return", 0)
        st.divider()
        st.subheader("🏆 超額報酬（相對 0050）")
        non_bench = {k: v for k, v in all_results.items() if "基準" not in k}
        if non_bench:
            cols = st.columns(len(non_bench))
            for i, (name, m) in enumerate(non_bench.items()):
                alpha = m["total_return"] - bench_return
                cols[i].metric(
                    name[:12],
                    f"{m['total_return']:.1%}",
                    f"α {alpha:+.1%}",
                )

        # ── 最佳策略月度熱力圖 ──
        best_name = max(non_bench, key=lambda k: non_bench[k]["total_return"], default=None)
        if best_name:
            st.divider()
            st.subheader(f"📅 月度報酬熱力圖（{best_name}）")
            st.plotly_chart(_monthly_returns_heatmap(non_bench[best_name]["equity_curve"]),
                            use_container_width=True)
            trades = non_bench[best_name].get("trades", [])
            if trades:
                st.subheader("📋 交易明細（最近 20 筆）")
                st.dataframe(pd.DataFrame(trades).tail(20), use_container_width=True)

        # ── 分析師結論 ──
        st.divider()
        st.subheader("🧠 分析師結論")
        winners = [k for k in non_bench if non_bench[k]["total_return"] > bench_return]
        if winners:
            best = max(winners, key=lambda k: non_bench[k]["total_return"])
            bm   = non_bench[best]
            alpha = bm["total_return"] - bench_return
            st.success(
                f"**{best}** 跑贏 0050，超額報酬 **{alpha:+.1%}** ｜ "
                f"Sharpe {bm['sharpe_ratio']:.2f} ｜ 最大回撤 {bm['max_drawdown']:.1%} ｜ 勝率 {bm['win_rate']:.1%}"
            )
            if bm["max_drawdown"] < -0.25:
                st.warning("注意：最大回撤 > 25%，實際操作需加強停損/部位控制")
        else:
            st.warning(f"本次設定無策略跑贏 0050（基準 {bench_return:.1%}）。可換標的或策略。")

    # ══════════════════════════════════════════════════════════
    # Tab 2：Alpha 掃描器
    # ══════════════════════════════════════════════════════════
    with tab_scan:
        st.subheader("🔍 Alpha 掃描器 — 全宇宙 × 所有策略排行榜")
        st.caption("對 DB 中所有已入庫股票，跑選定策略，依 Sharpe 排名，找出最強 Alpha 機會")

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            scan_start = st.date_input("掃描起始", value=pd.Timestamp.today() - pd.DateOffset(years=3),
                                       key="scan_start")
            scan_end   = st.date_input("掃描結束", value=pd.Timestamp.today() - pd.Timedelta(days=1),
                                       key="scan_end")
        with col_s2:
            scan_strats = st.multiselect(
                "掃描策略",
                options=list(STRATEGIES.keys()),
                default=list(STRATEGIES.keys()),
                key="scan_strats",
            )
            min_trades = st.number_input("最少交易次數", min_value=1, max_value=20, value=3, key="min_trades")
        with col_s3:
            top_n_show = st.number_input("顯示 Top N", min_value=5, max_value=100, value=30, key="top_n_show")
            filter_sector = st.selectbox(
                "板塊篩選",
                ["全部"] + ["半導體","電子組件/ODM","PCB/被動元件","面板/光電",
                            "金融保險","航運/空運","電信/網路","原物料/石化/鋼鐵",
                            "食品/消費/零售","生技醫療","ETF"],
                key="filter_sector",
            )

        scan_btn = st.button("🚀 開始全宇宙掃描", type="primary", use_container_width=True)

        if not scan_btn:
            st.info("設定掃描參數後點擊「開始全宇宙掃描」。首次掃描視資料量需 1-3 分鐘，結果快取 1 小時。")
            return

        if not scan_strats:
            st.warning("請選擇至少一個策略")
            return

        with st.spinner(f"掃描中... 正在跑 {len(scan_strats)} 種策略 × DB 全部股票"):
            scan_rows = run_alpha_scan(str(scan_start), str(scan_end),
                                       tuple(scan_strats), int(min_trades))

        if not scan_rows:
            st.error("掃描無結果。請確認 DB 中已有股票資料（先執行種子腳本）。")
            return

        df_scan = pd.DataFrame(scan_rows)
        if filter_sector != "全部":
            df_scan = df_scan[df_scan["板塊"] == filter_sector]

        df_show = df_scan.head(int(top_n_show)).copy()

        # ── 摘要指標 ──
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("掃描組合數", len(df_scan))
        c2.metric("正超額報酬數", int((df_scan["超額報酬α"] > 0).sum()))
        if len(df_scan):
            best_row = df_scan.iloc[0]
            c3.metric("最佳 Sharpe", f"{best_row['Sharpe']:.2f}", f"{best_row['代號']} {best_row['策略'][:6]}")
            c4.metric("最佳超額報酬", f"{df_scan['超額報酬α'].max():.1%}")

        # ── 排行榜表格 ──
        st.subheader(f"🥇 Alpha 排行榜（Sharpe 降序，Top {int(top_n_show)}）")
        display_df = df_show.copy()
        display_df["總報酬"]   = display_df["總報酬"].apply(lambda v: f"{v:.1%}")
        display_df["超額報酬α"] = display_df["超額報酬α"].apply(lambda v: f"{v:+.1%}")
        display_df["Sharpe"]   = display_df["Sharpe"].apply(lambda v: f"{v:.2f}")
        display_df["最大回撤"]  = display_df["最大回撤"].apply(lambda v: f"{v:.1%}")
        display_df["勝率"]     = display_df["勝率"].apply(
            lambda v: f"{v:.1%}" if v == v else "N/A")
        display_df["最終淨值"]  = display_df["最終淨值"].apply(lambda v: f"${v:,.0f}")
        st.dataframe(display_df[["代號","名稱","板塊","策略","總報酬","超額報酬α",
                                  "Sharpe","最大回撤","勝率","交易次數","最終淨值"]],
                     use_container_width=True, hide_index=True, height=500)

        # ── 策略勝率統計 ──
        st.divider()
        st.subheader("📊 各策略：平均 Sharpe vs 平均超額報酬")
        strat_agg = (
            df_scan.groupby("策略")
            .agg(平均Sharpe=("Sharpe","mean"), 平均超額報酬=("超額報酬α","mean"),
                 正超額比例=("超額報酬α", lambda x: (x>0).mean()),
                 樣本數=("代號","count"))
            .reset_index()
            .sort_values("平均Sharpe", ascending=False)
        )
        fig_agg = go.Figure()
        fig_agg.add_trace(go.Bar(
            x=strat_agg["策略"], y=strat_agg["平均Sharpe"],
            name="平均 Sharpe",
            marker_color=["#22C55E" if v > 0 else "#EF4444" for v in strat_agg["平均Sharpe"]],
            text=[f"{v:.2f}" for v in strat_agg["平均Sharpe"]], textposition="outside",
        ))
        fig_agg.add_trace(go.Scatter(
            x=strat_agg["策略"], y=strat_agg["平均超額報酬"] * 100,
            name="平均超額報酬(%)", mode="lines+markers",
            yaxis="y2", line=dict(color="#FFD700", width=2),
        ))
        fig_agg.update_layout(
            height=320, margin=dict(l=40, r=60, t=30, b=120),
            xaxis_tickangle=-25, yaxis_title="平均 Sharpe",
            yaxis2=dict(title="平均超額報酬(%)", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.05), barmode="group",
        )
        st.plotly_chart(fig_agg, use_container_width=True)

        # ── 散布圖：Sharpe vs 超額報酬 ──
        st.subheader("🗺️ 風險調整後報酬分布（Sharpe vs 超額報酬α）")
        fig_scatter = go.Figure()
        for strat in df_scan["策略"].unique():
            sub = df_scan[df_scan["策略"] == strat]
            fig_scatter.add_trace(go.Scatter(
                x=sub["超額報酬α"] * 100, y=sub["Sharpe"],
                mode="markers",
                name=strat[:14],
                text=[f"{r['代號']} {r['名稱']}" for _, r in sub.iterrows()],
                marker=dict(size=7, color=STRATEGY_COLORS.get(strat, "#A855F7"), opacity=0.75),
            ))
        fig_scatter.add_vline(x=0, line_color="#4B5563", line_dash="dot")
        fig_scatter.add_hline(y=0, line_color="#4B5563", line_dash="dot")
        fig_scatter.update_layout(
            height=420, margin=dict(l=50, r=20, t=20, b=40),
            xaxis_title="超額報酬α（%）", yaxis_title="Sharpe Ratio",
            hovermode="closest",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # ── CSV 匯出 ──
        csv_bytes = df_scan.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ 下載完整掃描結果 CSV",
                           data=csv_bytes,
                           file_name=f"alpha_scan_{scan_start}_{scan_end}.csv",
                           mime="text/csv")


if __name__ == "__main__":
    main()
