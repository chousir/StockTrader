"""Page 3：策略建構器 - 選擇策略、調整參數、預覽訊號、執行回測"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略建構器", page_icon="🔧", layout="wide")


@st.cache_data
def _get_data(stock_id: str, start_date: str, end_date: str):
    from twquant.data.providers.csv_local import CsvLocalProvider
    from twquant.data.providers.base import EmptyDataError

    try:
        return CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except EmptyDataError:
        from twquant.data.providers.finmind import FinMindProvider
        return FinMindProvider().fetch_daily(stock_id, start_date, end_date)


def main():
    import numpy as np
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    from twquant.strategy.builtin.ma_crossover import MACrossover
    from twquant.strategy.builtin.rust_custom import RustCustomStrategy
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.backtest.report import generate_report
    from twquant.dashboard.components.kline_chart import create_tw_stock_chart

    STRATEGIES = {
        "雙均線交叉 (MA Crossover)": "ma",
        "Rust 自訂策略 (Kalman Denoise)": "rust",
    }

    with st.sidebar:
        st.header("策略設定")
        stock_id = st.text_input("股票代碼", value="2330")
        start = st.date_input("開始日期", value=pd.Timestamp("2024-01-01"))
        end = st.date_input("結束日期", value=pd.Timestamp("2024-12-31"))
        strategy_name = st.selectbox("策略選擇", list(STRATEGIES.keys()))

        st.divider()
        if STRATEGIES[strategy_name] == "ma":
            short_w = st.slider("短均線", 3, 30, 5)
            long_w = st.slider("長均線", 10, 120, 20)
        else:
            proc_noise = st.slider("Process Noise", 0.001, 0.1, 0.01, format="%.3f")
            meas_noise = st.slider("Measurement Noise", 0.1, 5.0, 1.0, format="%.1f")

        run_btn = st.button("執行回測", type="primary")

    st.title("🔧 策略建構器")

    df = _get_data(stock_id, str(start), str(end))

    # ── 產生訊號 ──
    if STRATEGIES[strategy_name] == "ma":
        strategy = MACrossover(short_window=short_w, long_window=long_w)
    else:
        strategy = RustCustomStrategy(process_noise=proc_noise, measurement_noise=meas_noise)

    entries, exits = strategy.generate_signals(df)

    st.caption(f"訊號：進場 {entries.sum()} 次 | 出場 {exits.sum()} 次")

    # ── K 線圖 + 訊號標記 ──
    fig = create_tw_stock_chart(df, ma_periods=[])

    # 進場標記（綠色三角）
    entry_dates = df["date"].astype(str).values[entries]
    entry_prices = df["close"].values[entries]
    if len(entry_dates) > 0:
        fig.add_trace(go.Scatter(
            x=entry_dates, y=entry_prices * 0.98,
            mode="markers", name="進場",
            marker=dict(symbol="triangle-up", size=10, color="#34C759"),
        ), row=1, col=1)

    # 出場標記（紅色三角）
    exit_dates = df["date"].astype(str).values[exits]
    exit_prices = df["close"].values[exits]
    if len(exit_dates) > 0:
        fig.add_trace(go.Scatter(
            x=exit_dates, y=exit_prices * 1.02,
            mode="markers", name="出場",
            marker=dict(symbol="triangle-down", size=10, color="#FF3B30"),
        ), row=1, col=1)

    # Rust 策略額外顯示 Kalman 平滑曲線
    if STRATEGIES[strategy_name] == "rust":
        smoothed = strategy.get_smoothed_prices(df)
        fig.add_trace(go.Scatter(
            x=df["date"].astype(str), y=smoothed,
            mode="lines", name="Kalman 平滑",
            line=dict(color="#FF9500", width=2, dash="dash"),
        ), row=1, col=1)

    st.plotly_chart(fig, use_container_width=True)

    # ── 回測結果 ──
    if run_btn:
        df_idx = df.set_index("date")
        engine = TWSEBacktestEngine()
        metrics = engine.run(pd.Series(df_idx["close"], dtype=float), entries, exits)
        report = generate_report(metrics, strategy_name, start_date=str(start), end_date=str(end))

        st.subheader("回測績效")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("累積報酬率", f"{report['total_return']:.2%}")
        c2.metric("最大回撤", f"{report['max_drawdown']:.2%}")
        c3.metric("夏普率", f"{report['sharpe_ratio']:.2f}")
        c4.metric("總交易次數", str(report["total_trades"]))


if __name__ == "__main__":
    main()
