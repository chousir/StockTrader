"""Page 6：策略 vs 0050 基準 — 5 種已驗證策略單股多策略比較"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略 vs 基準", page_icon="⚔️", layout="wide")

DB_PATH = "data/twquant.db"

_STRAT_KEYS = [
    "momentum_concentrate",
    "volume_breakout",
    "triple_ma_twist",
    "risk_adj_momentum",
    "donchian_breakout",
]

_STRAT_LABEL = {
    "momentum_concentrate": "F｜動能精選 ★",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
}

_LABEL_TO_KEY = {v: k for k, v in _STRAT_LABEL.items()}

_STRAT_COLOR = {
    "0050 持有(基準)":   "#94A3B8",
    "F｜動能精選 ★":    "#FFD700",
    "H｜量價突破":       "#F97316",
    "L｜三線扭轉":       "#34D399",
    "M｜RAM動能":        "#60A5FA",
    "N｜唐奇安突破":     "#FB7185",
}

_STRAT_DESC = {
    "momentum_concentrate": "ret₂₀>5% + Close>MA60 進場；Close<MA60×0.97 出場。台達電近3年+369%，Sharpe 1.66。",
    "volume_breakout":      "Close>20日高點 + 量比>1.5x + Close>MA60 + RSI<76。台達電 Sharpe 1.81（最高）。",
    "triple_ma_twist":      "MA5/20/60 剛成多頭排列第一天 + RSI<72。台達電+258%，超額+111%。",
    "risk_adj_momentum":    "RAM=ret₂₀/(σ₂₀×√20)>0.7 + MA60>MA120。南亞科超額+285%（最高）。",
    "donchian_breakout":    "Close>DC_upper(20) + 量比>1.2x + Close>MA60 + RSI<76。台達電超額+201%。",
}


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


@st.cache_data(ttl=1800)
def run_comparison(stock_id: str, start: str, end: str, selected_keys: tuple):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.strategy.registry import get_strategy

    df = _load_from_db(stock_id, start, end)
    df_bench = _load_from_db("0050", start, end)
    if df.empty or len(df) < 60 or df_bench.empty:
        return None

    price       = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), dtype=float)
    price_bench = pd.Series(df_bench["close"].values, index=pd.to_datetime(df_bench["date"]), dtype=float)

    results = {}
    n = len(price_bench)
    bh_entries = np.zeros(n, dtype=bool); bh_entries[0] = True
    bh_exits   = np.zeros(n, dtype=bool); bh_exits[-1] = True
    results["0050 持有(基準)"] = TWSEBacktestEngine().run(price_bench, bh_entries, bh_exits, init_cash=1_000_000)

    for key in selected_keys:
        label = _STRAT_LABEL.get(key, key)
        try:
            entries, exits = get_strategy(key).generate_signals(df)
            if entries.sum() == 0:
                continue
            results[label] = TWSEBacktestEngine().run(price, entries, exits, init_cash=1_000_000)
        except Exception:
            pass

    return results, df, df_bench


def _monthly_heatmap(equity_curve: dict):
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
        zmid=0, hoverongaps=False,
    ))
    fig.update_layout(height=max(180, len(years)*38+60), margin=dict(l=60, r=20, t=20, b=20))
    return fig


def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    register_twquant_dark_template()
    ctx = render_global_sidebar(show_stock=True, show_dates=True, default_years=3)
    stock_id = ctx["stock_id"]
    start    = ctx["start_date"]
    end      = ctx["end_date"]

    with st.sidebar:
        st.header("回測設定")
        selected = st.multiselect(
            "選擇策略",
            options=_STRAT_KEYS,
            default=_STRAT_KEYS,
            format_func=lambda k: _STRAT_LABEL.get(k, k),
        )
        run_btn = st.button("▶ 執行對照回測", type="primary", use_container_width=True)

    st.title("⚔️ 策略 vs 0050 基準")
    st.caption("5 種已驗證策略 × 單股多策略並排 | 交易成本已計入 | 資料來源：系統 DB")

    if not run_btn:
        st.info("在左側選擇策略後，點擊「▶ 執行對照回測」")
        with st.expander("📖 各策略進場條件"):
            for k, desc in _STRAT_DESC.items():
                st.markdown(f"**{_STRAT_LABEL[k]}**  \n{desc}\n")
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
            line=dict(color=_STRAT_COLOR.get(name, "#A855F7"),
                      width=3 if is_bench or "★" in name else 1.8,
                      dash="dash" if is_bench else "solid"),
        ))
    fig_eq.update_layout(
        height=480, margin=dict(l=40, r=20, t=20, b=20),
        hovermode="x unified", xaxis_title="日期", yaxis_title="資產淨值（元）",
        legend=dict(orientation="h", y=-0.18),
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # ── 超額報酬 ──
    bench_return = all_results.get("0050 持有(基準)", {}).get("total_return", 0)
    non_bench = {k: v for k, v in all_results.items() if "基準" not in k}
    if non_bench:
        st.divider()
        st.subheader("🏆 超額報酬（相對 0050）")
        cols = st.columns(len(non_bench))
        for i, (name, m) in enumerate(non_bench.items()):
            cols[i].metric(name[:12], f"{m['total_return']:.1%}", f"α {m['total_return']-bench_return:+.1%}")

    # ── 最佳策略熱力圖 ──
    best_name = max(non_bench, key=lambda k: non_bench[k]["total_return"], default=None)
    if best_name:
        st.divider()
        st.subheader(f"📅 月度報酬熱力圖（{best_name}）")
        st.plotly_chart(_monthly_heatmap(non_bench[best_name]["equity_curve"]), use_container_width=True)
        trades = non_bench[best_name].get("trades", [])
        if trades:
            st.subheader("📋 交易明細（最近 20 筆）")
            t_df = pd.DataFrame(trades).tail(20)
            if "報酬率" in t_df.columns:
                st.dataframe(t_df.style.format({"報酬率": "{:.2%}"}), use_container_width=True)
            else:
                st.dataframe(t_df, use_container_width=True)

    # ── 分析師結論 ──
    st.divider()
    winners = [k for k in non_bench if non_bench[k]["total_return"] > bench_return]
    if winners:
        best = max(winners, key=lambda k: non_bench[k]["total_return"])
        bm = non_bench[best]
        alpha = bm["total_return"] - bench_return
        st.success(f"**{best}** 跑贏 0050，超額 **{alpha:+.1%}** ｜ Sharpe {bm['sharpe_ratio']:.2f} ｜ MDD {bm['max_drawdown']:.1%} ｜ 勝率 {bm['win_rate']:.1%}")
        if bm["max_drawdown"] < -0.25:
            st.warning("注意：最大回撤 > 25%，實際操作需加強停損/部位控制")
        if st.button(f"⚡ 用最佳策略跑單股回測（{best[:8]}）", use_container_width=True):
            st.session_state.update({
                "g_current_stock": stock_id, "current_stock": stock_id,
                "g_selected_strategy": _LABEL_TO_KEY.get(best_name, "momentum_concentrate"),
            })
            st.switch_page("pages/04_backtest_result.py")
    else:
        st.warning(f"本次設定無策略跑贏 0050（基準 {bench_return:.1%}）。可換標的或策略。")


if __name__ == "__main__":
    main()
