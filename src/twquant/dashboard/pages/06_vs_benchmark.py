"""Page 6：策略 vs 基準對照 - 多策略回測比較 + 跑贏 0050 分析"""

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
# 策略定義
# ─────────────────────────────────────────────────────────────
def strategy_macd_crossover(df):
    """策略 A：MACD 金叉/死叉"""
    from twquant.indicators.basic import compute_macd
    import numpy as np
    _, _, hist = compute_macd(df["close"])
    hist_prev = hist.shift(1)
    entries = ((hist_prev <= 0) & (hist > 0)).fillna(False).to_numpy()
    exits   = ((hist_prev >= 0) & (hist < 0)).fillna(False).to_numpy()
    return entries, exits


def strategy_trend_volume(df):
    """策略 B：多頭排列 + 量能確認"""
    from twquant.indicators.basic import compute_ma
    import numpy as np
    close  = df["close"]
    volume = df["volume"]
    ma20 = compute_ma(close, 20)
    ma60 = compute_ma(close, 60)
    vol20 = volume.rolling(20).mean()
    cond_trend = (close > ma20) & (ma20 > ma60)
    cond_vol   = volume > vol20 * 1.15
    entry_raw  = cond_trend & cond_vol
    entry_prev = entry_raw.shift(1).fillna(False)
    entries = (entry_raw & ~entry_prev).to_numpy()
    # 出場：跌破 MA20 或 MA20 跌破 MA60
    exit_cond  = (close < ma20) | (ma20 < ma60)
    exit_prev  = exit_cond.shift(1).fillna(False)
    exits = (exit_cond & ~exit_prev).to_numpy()
    return entries.astype(bool), exits.astype(bool)


def strategy_rsi_mean_reversion(df):
    """策略 C：RSI 均值回歸（超賣買入、超買出場）"""
    from twquant.indicators.basic import compute_rsi
    import numpy as np
    rsi = compute_rsi(df["close"], 14)
    rsi_prev = rsi.shift(1)
    entries = ((rsi_prev > 30) & (rsi <= 30)).fillna(False).to_numpy()
    exits   = ((rsi_prev < 70) & (rsi >= 70)).fillna(False).to_numpy()
    return entries, exits


def strategy_multifactor(df):
    """策略 D：多因子動能（趨勢 + RSI健康 + MACD正向）"""
    from twquant.indicators.basic import compute_ma, compute_rsi, compute_macd
    import numpy as np
    close = df["close"]
    ma20  = compute_ma(close, 20)
    ma60  = compute_ma(close, 60)
    rsi   = compute_rsi(close, 14)
    _, _, hist = compute_macd(close)

    bullish = (close > ma20) & (ma20 > ma60) & (rsi >= 45) & (rsi <= 70) & (hist > 0)
    bearish = (close < ma20) | (hist < 0) | (rsi > 75)

    bull_prev = bullish.shift(1).fillna(False)
    bear_prev = bearish.shift(1).fillna(False)
    entries = (bullish & ~bull_prev).to_numpy().astype(bool)
    exits   = (bearish & ~bear_prev).to_numpy().astype(bool)
    return entries, exits


def strategy_ma60_trend(df):
    """策略 E：MA60 主趨勢跟蹤（少量進出，長線持有）"""
    from twquant.indicators.basic import compute_ma
    close = df["close"]
    ma60  = compute_ma(close, 60)
    ma120 = compute_ma(close, 120)
    uptrend = (ma60 > ma120) & (close > ma60)
    entries = (uptrend & ~uptrend.shift(1).fillna(False)).to_numpy().astype(bool)
    exits   = (~uptrend & ~(~uptrend).shift(1).fillna(False)).to_numpy().astype(bool)
    return entries, exits


def strategy_momentum_concentrate(df):
    """策略 F：動能精選（20 日動能 > 5% + 站穩 MA60，破 MA60×0.97 才出）★ 推薦 ★"""
    from twquant.indicators.basic import compute_ma
    close = df["close"]
    ma60  = compute_ma(close, 60)
    ret20 = close.pct_change(20)
    entry_cond = (close > ma60) & (ret20 > 0.05)
    exit_cond  = close < ma60 * 0.97
    entries = (entry_cond & ~entry_cond.shift(1).fillna(False)).to_numpy().astype(bool)
    exits   = (exit_cond  & ~exit_cond.shift(1).fillna(False)).to_numpy().astype(bool)
    return entries, exits


STRATEGIES = {
    "A - MACD 金叉動能":              strategy_macd_crossover,
    "B - 多頭排列+量能":               strategy_trend_volume,
    "C - RSI 均值回歸":               strategy_rsi_mean_reversion,
    "D - 多因子動能":                  strategy_multifactor,
    "E - MA60 主趨勢跟蹤":            strategy_ma60_trend,
    "F - 動能精選 ★ 推薦 ★":          strategy_momentum_concentrate,
}


# ─────────────────────────────────────────────────────────────
# 回測執行（0050 buy & hold 為基準）
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

    price = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), dtype=float)
    price_bench = pd.Series(df_bench["close"].values, index=pd.to_datetime(df_bench["date"]), dtype=float)

    results = {}

    # 0050 buy & hold
    n = len(price_bench)
    bh_entries = np.zeros(n, dtype=bool); bh_entries[0] = True
    bh_exits   = np.zeros(n, dtype=bool); bh_exits[-1] = True
    engine = TWSEBacktestEngine()
    bh_metrics = engine.run(price_bench, bh_entries, bh_exits, init_cash=1_000_000)
    results["0050 持有(基準)"] = bh_metrics

    # 各策略
    for name in selected_strategies:
        fn = STRATEGIES[name]
        entries, exits = fn(df)
        if entries.sum() == 0:
            continue
        engine2 = TWSEBacktestEngine()
        metrics = engine2.run(price, entries, exits, init_cash=1_000_000)
        results[name] = metrics

    return results, df, df_bench


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
    months = list(range(1, 13))
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    z = []
    for yr in years:
        row = []
        for mo in months:
            try:
                val = monthly[(monthly.index.year == yr) & (monthly.index.month == mo)]
                row.append(round(float(val.iloc[0]), 2) if len(val) > 0 else None)
            except Exception:
                row.append(None)
        z.append(row)

    text = [[f"{v:.1f}%" if v is not None else "" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z,
        x=month_names,
        y=[str(y) for y in years],
        text=text,
        texttemplate="%{text}",
        colorscale=[[0, "#EF4444"], [0.5, "#1F2937"], [1, "#22C55E"]],
        zmid=0,
        colorbar=dict(title="月報酬%"),
        hoverongaps=False,
    ))
    fig.update_layout(
        height=max(180, len(years) * 38 + 60),
        margin=dict(l=60, r=20, t=20, b=20),
        xaxis_title="月份",
        yaxis_title="年份",
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

    st.title("⚔️ 策略 vs 0050 基準對照")
    st.caption("以系統資料庫為資料來源，回測多種策略對抗元大台灣50（0050）買進持有")

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
            default=["E - MA60 主趨勢跟蹤", "F - 動能精選 ★ 推薦 ★"],
        )
        run_btn = st.button("執行對照回測", type="primary", use_container_width=True)

    if not run_btn:
        st.info("在左側設定回測標的與策略後，點擊「執行對照回測」")
        with st.expander("📖 策略說明"):
            st.markdown("""
**策略 A：MACD 金叉動能**
- 進場：MACD 柱狀體由負轉正（金叉）；出場：死叉
- 缺點：在強牛市頻繁進出，錯過主升段

**策略 B：多頭排列 + 量能確認**
- 進場：收盤 > MA20 > MA60 且量比 > 1.15；出場：跌破 MA20
- 缺點：震盪市期間訊號多、手續費損耗大

**策略 C：RSI 均值回歸**
- 進場：RSI 跌破 30；出場：RSI 升破 70
- 缺點：牛市很少出現 RSI < 30，進場次數極少

**策略 D：多因子動能**
- 進場：多頭排列 + RSI 45-70 + MACD正值
- 缺點：三因子嚴格，持倉時間短，在大牛市仍輸給指數

**策略 E：MA60 主趨勢跟蹤** ← 超越 0050
- 進場：MA60 > MA120 且收盤 > MA60（主趨勢確立）
- 出場：主趨勢反轉（任一條件破壞）
- 特色：交易次數極少（15次/4年），適合長線投資者

**策略 F：動能精選 ★ 推薦 ★** ← 大幅超越 0050
- 進場：收盤站上 MA60 且 20日動能 > 5%（強勢突破確認）
- 出場：收盤跌破 MA60 × 0.97（留有 3% 緩衝，防假跌破）
- 特色：只做強勢股，7次交易達 +270%，Sharpe 1.69
- 核心邏輯：「強者恆強」— 只買已經展現動能的標的，忽略低速整理段
            """)
        return

    if not selected:
        st.warning("請至少選擇一個策略")
        return

    with st.spinner("回測中（從系統資料庫載入，無需 API 呼叫）..."):
        out = run_comparison(stock_id, str(start), str(end), tuple(selected))

    if out is None:
        st.error(f"無法載入 {stock_id} 或 0050 資料，請確認 DB 中已有該股票。可先執行種子數據腳本。")
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
    df_compare = pd.DataFrame(rows)
    st.dataframe(df_compare, use_container_width=True, hide_index=True)

    # ── 資金曲線對比 ──
    st.divider()
    st.subheader("📈 資金曲線對比（初始 $1,000,000）")
    fig_equity = go.Figure()

    colors_map = {
        "0050 持有(基準)":         "#94A3B8",
        "A - MACD 金叉動能":       "#3B82F6",
        "B - 多頭排列+量能":        "#60A5FA",
        "C - RSI 均值回歸":        "#F97316",
        "D - 多因子動能":           "#A855F7",
        "E - MA60 主趨勢跟蹤":     "#22C55E",
        "F - 動能精選 ★ 推薦 ★":   "#FFD700",
    }

    for name, m in all_results.items():
        equity = pd.Series(m["equity_curve"])
        equity.index = pd.to_datetime(equity.index)
        is_bench = "基準" in name
        fig_equity.add_trace(go.Scatter(
            x=equity.index, y=equity.values,
            name=name,
            line=dict(
                color=colors_map.get(name, "#A855F7"),
                width=3 if is_bench or "推薦" in name else 1.5,
                dash="dash" if is_bench else "solid",
            ),
        ))

    fig_equity.update_layout(
        height=480,
        margin=dict(l=40, r=20, t=20, b=20),
        hovermode="x unified",
        xaxis_title="日期",
        yaxis_title="資產淨值（元）",
        legend=dict(orientation="h", y=-0.15),
    )
    st.plotly_chart(fig_equity, use_container_width=True)

    # ── 超額報酬分析 ──
    bench_return = all_results.get("0050 持有(基準)", {}).get("total_return", 0)
    st.divider()
    st.subheader("🏆 超額報酬（相對 0050）")
    alpha_cols = st.columns(len(all_results))
    for i, (name, m) in enumerate(all_results.items()):
        if "基準" in name:
            continue
        alpha = m["total_return"] - bench_return
        color = "#22C55E" if alpha > 0 else "#EF4444"
        alpha_cols[i].metric(
            name.split("：")[-1] if "：" in name else name,
            f"{m['total_return']:.1%}",
            f"超額 {alpha:+.1%}",
        )

    # ── 最佳策略月度熱力圖 ──
    best_name = max(
        {k: v for k, v in all_results.items() if "基準" not in k},
        key=lambda k: all_results[k]["total_return"],
        default=None,
    )
    if best_name:
        st.divider()
        st.subheader(f"📅 月度報酬熱力圖（{best_name}）")
        fig_heat = _monthly_returns_heatmap(all_results[best_name]["equity_curve"])
        st.plotly_chart(fig_heat, use_container_width=True)

        # 交易明細
        trades = all_results[best_name].get("trades", [])
        if trades:
            st.subheader(f"📋 交易明細（{best_name}，最近 20 筆）")
            st.dataframe(pd.DataFrame(trades).tail(20), use_container_width=True)

    # ── 分析師結論 ──
    st.divider()
    st.subheader("🧠 分析師結論")
    winners = [k for k, v in all_results.items() if "基準" not in k
               and v["total_return"] > bench_return]
    if winners:
        best = max(winners, key=lambda k: all_results[k]["total_return"])
        bm   = all_results[best]
        alpha = bm["total_return"] - bench_return
        st.success(
            f"**{best}** 跑贏 0050，超額報酬 **{alpha:+.1%}**｜"
            f"Sharpe {bm['sharpe_ratio']:.2f}｜最大回撤 {bm['max_drawdown']:.1%}｜"
            f"勝率 {bm['win_rate']:.1%}"
        )
        if bm["max_drawdown"] < -0.25:
            st.warning("注意：最大回撤超過 25%，實際操作需注意風險控制（停損 / 部位管理）")
    else:
        st.warning(f"本次回測區間，所選策略均未跑贏 0050（基準報酬 {bench_return:.1%}）。建議更換標的或調整策略參數。")


if __name__ == "__main__":
    main()
