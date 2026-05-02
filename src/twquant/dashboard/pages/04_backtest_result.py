"""Page 4：回測結果 - 三層佈局（策略摘要 / 資金曲線 / 卡片指標+交易明細）"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="回測結果", page_icon="📊", layout="wide")


@st.cache_data
def _run_backtest(stock_id: str, start_date: str, end_date: str,
                  short_w: int, long_w: int):
    import pandas as pd
    from twquant.data.providers.csv_local import CsvLocalProvider
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.backtest.report import generate_report
    from twquant.strategy.builtin.ma_crossover import MACrossover

    try:
        df = CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except Exception:
        from twquant.data.providers.finmind import FinMindProvider
        df = FinMindProvider().fetch_daily(stock_id, start_date, end_date)

    df_idx = df.set_index("date")
    strategy = MACrossover(short_window=short_w, long_window=long_w)
    entries, exits = strategy.generate_signals(df)
    engine = TWSEBacktestEngine()
    metrics = engine.run(pd.Series(df_idx["close"], dtype=float), entries, exits)
    report = generate_report(metrics, f"MA{short_w}/{long_w}", "基準",
                             start_date=start_date, end_date=end_date)
    return report, df


def _render_equity_curve(report: dict, height: int = 450):
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
    fig.update_layout(
        height=height,
        margin=dict(l=40, r=20, t=30, b=20),
        hovermode="x unified",
        xaxis_title="日期",
        yaxis_title="資產淨值",
    )
    st.plotly_chart(fig, use_container_width=True)


def main():
    with st.sidebar:
        st.header("回測設定")
        stock_id = st.text_input("股票代碼", value="2330")
        import pandas as pd
        start = st.date_input("開始日期", value=pd.Timestamp("2024-01-01"))
        end = st.date_input("結束日期", value=pd.Timestamp("2024-12-31"))
        short_w = st.slider("短均線", 3, 30, 5)
        long_w = st.slider("長均線", 10, 120, 20)
        run_btn = st.button("執行回測", type="primary")

    if not run_btn:
        st.info("請在左側設定參數後點擊「執行回測」")
        return

    with st.spinner("回測執行中..."):
        report, df = _run_backtest(
            stock_id, str(start), str(end), short_w, long_w
        )

    # ── Layer 1：策略摘要 ──
    strategy_name = f"MA{short_w}/{long_w}"
    st.markdown(f"### 回測結果：{strategy_name} | {stock_id}")
    st.caption(f"回測區間：{start} ~ {end} | 共 {len(df)} 個交易日")

    # ── Layer 2：資金曲線（視覺焦點） ──
    with st.container(border=True):
        st.subheader("📈 資金曲線")
        _render_equity_curve(report, height=450)

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
                import pandas as pd
                trades_df = pd.DataFrame(report["trades"])
                st.dataframe(trades_df, use_container_width=True)
            else:
                st.caption("無交易記錄")

    with col_monthly:
        with st.container(border=True):
            st.subheader("月度報酬")
            st.info("月度熱力圖（Phase 7 實作）")


if __name__ == "__main__":
    main()
