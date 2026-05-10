"""Page 3：策略建構器 - 所有策略 + 指標副圖 + 回測結果"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略建構器", page_icon="🔧", layout="wide")


@st.cache_data
def _get_data(stock_id: str, start_date: str, end_date: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage

    storage = SQLiteStorage("data/twquant.db")
    df = storage.load(f"daily_price/{stock_id}", start_date=start_date, end_date=end_date)
    if len(df) >= 60:
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)

    # DB 資料不足 → CSV 備援 → API 備援
    from twquant.data.providers.csv_local import CsvLocalProvider
    from twquant.data.providers.base import EmptyDataError
    try:
        return CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except EmptyDataError:
        from twquant.data.providers.finmind import FinMindProvider
        return FinMindProvider().fetch_daily(stock_id, start_date, end_date)


_PRODUCTION_STRATEGIES = {
    "momentum_concentrate", "volume_breakout", "triple_ma_twist",
    "risk_adj_momentum", "donchian_breakout",
}


def _build_signal_chart(df, entries, exits, strategy_key, strategy_obj):
    """K線+訊號標記 + 策略專屬指標副圖"""
    import numpy as np
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from twquant.dashboard.styles.theme import TWStockColors
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.indicators.basic import compute_macd, compute_rsi, compute_bollinger, compute_ma

    register_twquant_dark_template()

    close = df["close"]
    dates = df["date"].astype(str)

    # 副圖配置依策略調整
    if strategy_key == "macd_divergence":
        rows, row_heights = 3, [0.55, 0.20, 0.25]
        subplot_titles = ("K 線圖", "成交量（張）", "MACD")
    elif strategy_key in ("rsi_reversal", ) | _PRODUCTION_STRATEGIES:
        rows, row_heights = 3, [0.55, 0.20, 0.25]
        subplot_titles = ("K 線圖", "成交量（張）", "RSI(14)")
    elif strategy_key == "bollinger_breakout":
        rows, row_heights = 2, [0.70, 0.30]
        subplot_titles = ("K 線圖（布林帶）", "成交量（張）")
    else:
        rows, row_heights = 2, [0.70, 0.30]
        subplot_titles = ("K 線圖", "成交量（張）")

    fig = make_subplots(
        rows=rows, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=row_heights,
        subplot_titles=subplot_titles,
    )

    # ── K 線 ──
    fig.add_trace(go.Candlestick(
        x=dates, open=df["open"], high=df["high"],
        low=df["low"], close=close, name="K線",
        increasing_line_color=TWStockColors.CANDLE_UP_BORDER,
        increasing_fillcolor=TWStockColors.CANDLE_UP_FILL,
        decreasing_line_color=TWStockColors.CANDLE_DOWN_BORDER,
        decreasing_fillcolor=TWStockColors.CANDLE_DOWN_FILL,
    ), row=1, col=1)

    # MA 5/20（全策略）；MA60 加入生產策略
    for p, c in [(5, TWStockColors.MA_5), (20, TWStockColors.MA_20)]:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=dates, y=compute_ma(close, p), mode="lines",
                name=f"MA{p}", line=dict(color=c, width=1),
            ), row=1, col=1)
    if strategy_key in _PRODUCTION_STRATEGIES and len(df) >= 60:
        fig.add_trace(go.Scatter(
            x=dates, y=compute_ma(close, 60), mode="lines",
            name="MA60", line=dict(color=TWStockColors.MA_60, width=1.5),
        ), row=1, col=1)

    # 布林帶 overlay
    if strategy_key == "bollinger_breakout":
        upper, mid, lower = compute_bollinger(close)
        fig.add_trace(go.Scatter(
            x=dates, y=upper, mode="lines", name="BB上軌",
            line=dict(color="rgba(59,130,246,0.6)", width=1, dash="dot"),
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=dates, y=lower, mode="lines", name="BB下軌",
            line=dict(color="rgba(59,130,246,0.6)", width=1, dash="dot"),
            fill="tonexty", fillcolor="rgba(59,130,246,0.05)",
        ), row=1, col=1)

    # Kalman 平滑曲線
    if strategy_key == "rust_kalman":
        try:
            smoothed = strategy_obj.get_smoothed_prices(df)
            fig.add_trace(go.Scatter(
                x=dates, y=smoothed, mode="lines", name="Kalman 平滑",
                line=dict(color="#FF9500", width=2, dash="dash"),
            ), row=1, col=1)
        except Exception:
            pass

    # 進出場標記
    entry_mask = entries.astype(bool)
    exit_mask = exits.astype(bool)
    if entry_mask.any():
        fig.add_trace(go.Scatter(
            x=dates[entry_mask], y=df["close"].values[entry_mask] * 0.975,
            mode="markers", name="進場",
            marker=dict(symbol="triangle-up", size=12, color="#34C759"),
        ), row=1, col=1)
    if exit_mask.any():
        fig.add_trace(go.Scatter(
            x=dates[exit_mask], y=df["close"].values[exit_mask] * 1.025,
            mode="markers", name="出場",
            marker=dict(symbol="triangle-down", size=12, color="#FF3B30"),
        ), row=1, col=1)

    # ── 成交量（張） ──
    vol_row = 2
    is_up = df["close"] >= df["open"]
    bar_colors = [TWStockColors.VOLUME_UP if u else TWStockColors.VOLUME_DOWN for u in is_up]
    fig.add_trace(go.Bar(
        x=dates, y=df["volume"] / 1000,
        name="成交量(張)", marker_color=bar_colors, showlegend=False,
    ), row=vol_row, col=1)

    # ── 策略指標副圖 ──
    if rows == 3:
        if strategy_key == "macd_divergence":
            p = strategy_obj.get_parameters()
            macd, signal, hist = compute_macd(close, p.get("fast", 12), p.get("slow", 26), p.get("signal", 9))
            colors = ["#EF4444" if h >= 0 else "#22C55E" for h in hist.fillna(0)]
            fig.add_trace(go.Bar(x=dates, y=hist, name="MACD柱", marker_color=colors, showlegend=False), row=3, col=1)
            fig.add_trace(go.Scatter(x=dates, y=macd, mode="lines", name="MACD", line=dict(color="#3B82F6", width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=dates, y=signal, mode="lines", name="Signal", line=dict(color="#F97316", width=1)), row=3, col=1)
        elif strategy_key in ("rsi_reversal",) | _PRODUCTION_STRATEGIES:
            p = strategy_obj.get_parameters()
            rsi_period = p.get("period", 14)
            rsi = compute_rsi(close, rsi_period)
            fig.add_trace(go.Scatter(x=dates, y=rsi, mode="lines", name="RSI", line=dict(color="#A855F7", width=1.5)), row=3, col=1)
            # 依策略顯示對應的 RSI 閾值線
            rsi_ob = p.get("rsi_entry", p.get("rsi_cap", p.get("overbought", 70)))
            rsi_os = p.get("oversold", 30)
            for level, dash in [(rsi_ob, "dash"), (rsi_os, "dash"), (50, "dot")]:
                color = "#EF4444" if level == rsi_ob else ("#22C55E" if level == rsi_os else "#6B7280")
                fig.add_hline(y=level, line_dash=dash, line_color=color, line_width=1, row=3, col=1)

    fig.update_layout(
        height=620 if rows == 3 else 520,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02),
    )
    return fig


def main():
    import pandas as pd
    from twquant.strategy.registry import list_strategies, get_strategy
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.backtest.report import generate_report
    from twquant.dashboard.components.metrics_card import render_metrics_cards
    from twquant.dashboard.config import get_init_cash, get_broker_discount
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    # 全域 sidebar：股票 + 日期 + 快取清除
    ctx = render_global_sidebar(show_stock=True, show_dates=True, default_years=1)
    stock_id = ctx["stock_id"]
    start = ctx["start_date"]
    end = ctx["end_date"]

    strategy_info = list_strategies()
    strategy_map = {s["name"]: s["key"] for s in strategy_info}

    with st.sidebar:
        st.header("策略設定")
        strategy_label = st.selectbox("策略選擇", [s["name"] for s in strategy_info])
        strategy_key = strategy_map[strategy_label]
        selected_info = next(s for s in strategy_info if s["key"] == strategy_key)

        st.divider()
        st.caption("策略參數")
        params = {}
        for k, v in selected_info["parameters"].items():
            if isinstance(v, float):
                params[k] = st.slider(k, float(v * 0.1), float(v * 10), float(v), format="%.3f")
            elif isinstance(v, int):
                params[k] = st.slider(k, max(1, v // 3), v * 4, v)

        init_cash = st.number_input("初始資金（元）", value=get_init_cash(), step=100_000)
        broker_discount = st.select_slider("手續費折扣", options=[i / 10 for i in range(1, 11)], value=get_broker_discount(), format_func=lambda x: f"{x:.0%}")
        run_btn = st.button("執行回測", type="primary", use_container_width=True)

    st.title("🔧 策略建構器")
    st.caption(f"策略：{strategy_label}")

    try:
        df = _get_data(stock_id, str(start), str(end))
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        return

    if df.empty:
        st.warning("無數據，請確認股票代碼與日期範圍。")
        return

    # 建立策略實例並產生訊號
    try:
        strategy_obj = get_strategy(strategy_key, **params)
        entries, exits = strategy_obj.generate_signals(df)
    except Exception as e:
        st.error(f"訊號產生失敗：{e}")
        return

    col_info1, col_info2, col_info3 = st.columns(3)
    col_info1.metric("資料筆數", f"{len(df)} 個交易日")
    col_info2.metric("進場訊號", f"{int(entries.sum())} 次")
    col_info3.metric("出場訊號", f"{int(exits.sum())} 次")

    # K線+訊號+指標副圖
    fig = _build_signal_chart(df, entries, exits, strategy_key, strategy_obj)
    st.plotly_chart(fig, use_container_width=True)

    # 回測結果
    if run_btn:
        with st.spinner("回測執行中..."):
            try:
                df_idx = df.set_index("date")
                engine = TWSEBacktestEngine()
                metrics = engine.run(
                    pd.Series(df_idx["close"], dtype=float),
                    entries, exits,
                    init_cash=float(init_cash),
                    broker_discount=float(broker_discount),
                )
                report = generate_report(
                    metrics, strategy_label,
                    start_date=str(start), end_date=str(end),
                    init_cash=float(init_cash),
                )
            except Exception as e:
                st.error(f"回測失敗：{e}")
                return

        st.subheader("📊 績效指標")
        render_metrics_cards(report)

        # Markdown 報告下載
        from twquant.backtest.report import to_markdown
        st.download_button(
            "⬇ 下載績效報告 (Markdown)",
            data=to_markdown(report),
            file_name=f"backtest_{stock_id}_{strategy_key}.md",
            mime="text/markdown",
        )


if __name__ == "__main__":
    main()
