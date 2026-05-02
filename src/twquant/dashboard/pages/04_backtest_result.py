"""Page 4：回測結果 - 資金曲線、績效指標、交易明細"""

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


def main():
    st.title("📊 回測結果")

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

    # ── 績效指標卡片 ──
    st.subheader("績效指標")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("累積報酬率", f"{report['total_return']:.2%}")
    c2.metric("最大回撤", f"{report['max_drawdown']:.2%}")
    c3.metric("夏普率", f"{report['sharpe_ratio']:.2f}")
    c4.metric("勝率", f"{report['win_rate']:.2%}")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("總交易次數", str(report["total_trades"]))
    c6.metric("年化報酬 (CAGR)", f"{report['cagr']:.2%}" if report['cagr'] == report['cagr'] else "N/A")
    c7.metric("Sortino Ratio", f"{report['sortino_ratio']:.2f}")
    c8.metric("盈虧比", f"{report['profit_factor']:.2f}")

    # ── 資金曲線 ──
    st.subheader("資金曲線")
    import plotly.graph_objects as go
    import pandas as pd
    equity = pd.Series(report["equity_curve"])
    equity.index = pd.to_datetime(equity.index)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=equity.index, y=equity.values, name="策略", line=dict(color="#007AFF")))
    fig.update_layout(height=350, margin=dict(l=40, r=20, t=30, b=20))
    st.plotly_chart(fig, use_container_width=True)


if __name__ == "__main__":
    main()
