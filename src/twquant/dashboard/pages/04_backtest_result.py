"""Page 4：回測結果 — 5 大生產策略 + MA 雙線，三層佈局（策略摘要 / 資金曲線 / 指標+明細）"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="回測結果", page_icon="📊", layout="wide")

_STRAT_KEYS = [
    "momentum_concentrate", "volume_breakout", "triple_ma_twist",
    "risk_adj_momentum", "donchian_breakout", "ma_crossover",
]
_STRAT_LABEL = {
    "momentum_concentrate": "F｜動能精選 ★",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
    "ma_crossover":         "MA 黃金交叉",
}


@st.cache_data
def _run_backtest(stock_id: str, start_date: str, end_date: str,
                  strategy_key: str, short_w: int = 5, long_w: int = 20):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.backtest.report import generate_report
    from twquant.strategy.registry import get_strategy

    storage = SQLiteStorage("data/twquant.db")
    df = storage.load(f"daily_price/{stock_id}", start_date=start_date, end_date=end_date)
    if df.empty or len(df) < 60:
        try:
            from twquant.data.providers.csv_local import CsvLocalProvider
            df = CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
        except Exception:
            from twquant.data.providers.finmind import FinMindProvider
            df = FinMindProvider().fetch_daily(stock_id, start_date, end_date)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    kwargs = {"short_window": short_w, "long_window": long_w} if strategy_key == "ma_crossover" else {}
    strategy = get_strategy(strategy_key, **kwargs)
    entries, exits = strategy.generate_signals(df)
    price = pd.Series(df.set_index("date")["close"], dtype=float)
    metrics = TWSEBacktestEngine().run(price, entries, exits)
    label = _STRAT_LABEL.get(strategy_key, strategy_key)
    report = generate_report(metrics, label, "基準", start_date=start_date, end_date=end_date)
    return report, df


def _render_equity_curve(report: dict, start_date: str, end_date: str, height: int = 450):
    import plotly.graph_objects as go
    import pandas as pd
    from twquant.dashboard.styles.theme import TWStockColors

    equity = pd.Series(report["equity_curve"])
    equity.index = pd.to_datetime(equity.index)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        name="策略",
        line=dict(color=TWStockColors.EQUITY_CURVE, width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 212, 170, 0.1)",
    ))

    bench_equity = None
    try:
        from twquant.data.storage import SQLiteStorage
        storage = SQLiteStorage("data/twquant.db")
        df_bench = storage.load("daily_price/0050", start_date=start_date, end_date=end_date)
        if not df_bench.empty:
            init_cash = report.get("final_value", 1_000_000) / (1 + report.get("total_return", 0))
            bench_close = df_bench["close"].astype(float)
            bench_dates = pd.to_datetime(df_bench["date"])
            bench_equity = init_cash * bench_close / bench_close.iloc[0]
            fig.add_trace(go.Scatter(
                x=bench_dates, y=bench_equity.values,
                name="0050 持有（基準）",
                line=dict(color="#94A3B8", width=1.5, dash="dash"),
            ))
    except Exception:
        pass

    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=30, b=20),
        hovermode="x unified",
        xaxis_title="日期",
        yaxis_title="資產淨值",
        legend=dict(orientation="h", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

    if bench_equity is not None:
        bench_return = float(bench_equity.iloc[-1] / bench_equity.iloc[0] - 1)
        alpha = report.get("total_return", 0) - bench_return
        col1, col2, col3 = st.columns(3)
        col1.metric("策略報酬", f"{report.get('total_return', 0):.1%}")
        col2.metric("0050 基準", f"{bench_return:.1%}")
        col3.metric("超額報酬 α", f"{alpha:+.1%}", delta_color="normal")


def main():
    import pandas as pd
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    ctx = render_global_sidebar(show_stock=True, show_dates=True, default_years=1)
    stock_id = ctx["stock_id"]
    start = ctx["start_date"]
    end = ctx["end_date"]

    with st.sidebar:
        st.header("回測設定")
        default_key = st.session_state.get("g_selected_strategy", "ma_crossover")
        if default_key not in _STRAT_KEYS:
            default_key = "ma_crossover"
        strategy_key = st.selectbox(
            "策略",
            options=_STRAT_KEYS,
            index=_STRAT_KEYS.index(default_key),
            format_func=lambda k: _STRAT_LABEL.get(k, k),
        )
        short_w, long_w = 5, 20
        if strategy_key == "ma_crossover":
            short_w = st.slider("短均線", 3, 30, 5)
            long_w = st.slider("長均線", 10, 120, 20)
        run_btn = st.button("執行回測", type="primary")

    if not run_btn:
        st.info("請在左側設定參數後點擊「執行回測」")
        return

    with st.spinner("回測執行中..."):
        report, df = _run_backtest(
            stock_id, str(start), str(end), strategy_key, short_w, long_w
        )

    # ── Layer 1：策略摘要 ──
    st.markdown(f"### 回測結果：{_STRAT_LABEL.get(strategy_key, strategy_key)} | {stock_id}")
    st.caption(f"回測區間：{start} ~ {end} | 共 {len(df)} 個交易日")

    # ── Layer 2：資金曲線（視覺焦點） ──
    with st.container(border=True):
        st.subheader("📈 資金曲線（含 0050 基準）")
        _render_equity_curve(report, str(start), str(end), height=450)

    # ── Layer 3a：績效指標卡片群 ──
    st.subheader("📊 績效指標")
    from twquant.dashboard.components.metrics_card import render_metrics_cards
    render_metrics_cards(report)

    # ── Layer 3b：交易明細 + 月度報酬（雙欄） ──
    st.divider()
    col_trades, col_monthly = st.columns(2)

    with col_trades:
        with st.container(border=True):
            st.subheader("交易明細")
            if report.get("trades"):
                trades_df = pd.DataFrame(report["trades"])
                if "報酬率" in trades_df.columns:
                    st.dataframe(
                        trades_df.style.format({"報酬率": "{:.2%}"}),
                        use_container_width=True,
                    )
                else:
                    st.dataframe(trades_df, use_container_width=True)
            else:
                st.caption("無交易記錄")

    with col_monthly:
        with st.container(border=True):
            st.subheader("月度報酬熱力圖")
            try:
                import plotly.graph_objects as go
                equity_s = pd.Series(report["equity_curve"])
                equity_s.index = pd.to_datetime(equity_s.index)
                monthly = equity_s.resample("ME").last().pct_change().dropna() * 100
                years = sorted(monthly.index.year.unique())
                month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                z = []
                for yr in years:
                    row = []
                    for mo in range(1, 13):
                        vals = monthly[(monthly.index.year == yr) & (monthly.index.month == mo)]
                        row.append(round(float(vals.iloc[0]), 2) if len(vals) > 0 else None)
                    z.append(row)
                text = [[f"{v:.1f}%" if v is not None else "" for v in row] for row in z]
                fig_heat = go.Figure(go.Heatmap(
                    z=z, x=month_names, y=[str(y) for y in years],
                    text=text, texttemplate="%{text}",
                    colorscale=[[0,"#EF4444"],[0.5,"#1F2937"],[1,"#22C55E"]],
                    zmid=0, hoverongaps=False,
                    colorbar=dict(title="月報酬%"),
                ))
                fig_heat.update_layout(
                    height=max(160, len(years)*38+60),
                    margin=dict(l=50, r=10, t=10, b=10),
                )
                st.plotly_chart(fig_heat, use_container_width=True)
            except Exception as e:
                st.caption(f"熱力圖無法顯示: {e}")


if __name__ == "__main__":
    main()
