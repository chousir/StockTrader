"""Page 2：個股分析 - 三層佈局（搜尋列 / K線+指標 / 基本資料）"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="個股分析", page_icon="📈", layout="wide")

DB_PATH = "data/twquant.db"


@st.cache_data(ttl=1800)
def _load_daily(stock_id: str, start_date: str, end_date: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    df = storage.load(f"daily_price/{stock_id}", start_date=start_date, end_date=end_date)
    if not df.empty and len(df) >= 10:
        df["date"] = pd.to_datetime(df["date"])
        return df
    # 備援：嘗試 CSV 樣本
    try:
        from twquant.data.providers.csv_local import CsvLocalProvider
        from twquant.data.providers.base import EmptyDataError
        return CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except Exception:
        pass
    # 備援：FinMind API
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.dashboard.config import get_finmind_token
    df_api = FinMindProvider(token=get_finmind_token() or "").fetch_daily(stock_id, start_date, end_date)
    storage.upsert(f"daily_price/{stock_id}", df_api)
    return df_api


def _render_indicator_chart(df):
    """RSI + MACD 三合一指標圖"""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from twquant.indicators.basic import compute_rsi, compute_macd, compute_ma
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.styles.theme import TWStockColors

    register_twquant_dark_template()
    close = df["close"]
    dates = df["date"].astype(str)

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.45, 0.28, 0.27],
        subplot_titles=("收盤價 + 均線", "RSI (14)", "MACD (12,26,9)"),
    )

    # 收盤價 + MA
    fig.add_trace(go.Scatter(
        x=dates, y=close, mode="lines", name="收盤",
        line=dict(color="#E8EAED", width=1.5),
    ), row=1, col=1)
    for p, c in [(5, TWStockColors.MA_5), (20, TWStockColors.MA_20), (60, TWStockColors.MA_60)]:
        if len(df) >= p:
            fig.add_trace(go.Scatter(
                x=dates, y=compute_ma(close, p), mode="lines", name=f"MA{p}",
                line=dict(color=c, width=1),
            ), row=1, col=1)

    # RSI
    rsi = compute_rsi(close, 14)
    fig.add_trace(go.Scatter(
        x=dates, y=rsi, mode="lines", name="RSI",
        line=dict(color="#A855F7", width=1.5),
        hovertemplate="RSI: %{y:.1f}<extra></extra>",
    ), row=2, col=1)
    for level, color, dash in [(70, "#EF4444", "dash"), (30, "#22C55E", "dash"), (50, "#6B7280", "dot")]:
        fig.add_hline(y=level, line_color=color, line_dash=dash, line_width=1, row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)

    # MACD
    macd, signal, hist = compute_macd(close, 12, 26, 9)
    bar_colors = ["#EF4444" if h >= 0 else "#22C55E" for h in hist.fillna(0)]
    fig.add_trace(go.Bar(
        x=dates, y=hist, name="MACD柱", marker_color=bar_colors, showlegend=False,
        hovertemplate="MACD柱: %{y:.2f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=macd, mode="lines", name="MACD",
        line=dict(color="#3B82F6", width=1.2),
        hovertemplate="MACD: %{y:.2f}<extra></extra>",
    ), row=3, col=1)
    fig.add_trace(go.Scatter(
        x=dates, y=signal, mode="lines", name="Signal",
        line=dict(color="#F97316", width=1.2),
        hovertemplate="Signal: %{y:.2f}<extra></extra>",
    ), row=3, col=1)
    fig.add_hline(y=0, line_color="#6B7280", line_width=0.8, row=3, col=1)

    fig.update_layout(
        height=560,
        xaxis_rangeslider_visible=False,
        margin=dict(l=40, r=20, t=40, b=20),
        hovermode="x unified",
        legend=dict(orientation="h", y=1.02),
    )
    fig.update_yaxes(title_text="價格", row=1, col=1)
    fig.update_yaxes(title_text="RSI", row=2, col=1)
    fig.update_yaxes(title_text="MACD", row=3, col=1)
    return fig


def main():
    import pandas as pd
    from twquant.dashboard.components.kline_chart import create_tw_stock_chart
    from twquant.dashboard.components.smart_search import render_smart_search
    from twquant.dashboard.components.watchlist_ui import (
        render_watchlist_chips,
        render_watchlist_button,
    )
    from twquant.dashboard.components.tradingview_widgets import render_tv_technicals

    # ── Layer 1：全局導覽（搜尋 + 關注清單快捷 + 狀態） ──
    col_search, col_chips, col_status = st.columns([4, 4, 1])
    with col_search:
        searched_id = render_smart_search(key="stock_analysis_search")
    with col_chips:
        render_watchlist_chips()
    with col_status:
        st.caption("🟢 資料正常")

    stock_id = (
        searched_id
        or st.session_state.get("current_stock")
        or "2330"
    )

    st.divider()

    # ── 側邊欄：日期選擇（動態預設最近 1 年）──
    with st.sidebar:
        st.header("查詢條件")
        today = pd.Timestamp.today().normalize()
        default_end = today - pd.Timedelta(days=1)
        default_start = default_end - pd.DateOffset(years=1)
        start_date = st.date_input("開始日期", value=default_start)
        end_date = st.date_input("結束日期", value=default_end)
        st.divider()
        render_watchlist_button(stock_id)

    # ── 載入資料 ──
    try:
        df = _load_daily(stock_id, str(start_date), str(end_date))
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        return

    if df.empty:
        st.warning("查無資料，請確認股票代碼與日期範圍。樣本庫目前僅含 2330、0050、2317。")
        return

    # ── 標題列：最新行情摘要 ──
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    chg = latest["close"] - prev["close"]
    chg_pct = chg / prev["close"] * 100
    chg_color = "#EF4444" if chg > 0 else ("#22C55E" if chg < 0 else "#9CA3AF")
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")

    title_col, c1, c2, c3, c4 = st.columns([3, 1, 1, 1, 1])
    with title_col:
        st.markdown(
            f"### {stock_id} &nbsp; "
            f"<span style='font-size:1.5rem;color:{chg_color}'>{latest['close']:.1f}</span> &nbsp; "
            f"<span style='color:{chg_color};font-size:0.9rem'>{arrow} {abs(chg):.1f} ({chg_pct:+.2f}%)</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"最後更新：{latest['date']} | {len(df)} 個交易日")
    c1.metric("開盤", f"{latest['open']:.1f}")
    c2.metric("最高", f"{latest['high']:.1f}")
    c3.metric("最低", f"{latest['low']:.1f}")
    c4.metric("成交量", f"{latest['volume']/1000:,.0f} 張")

    # ── Layer 2：主力圖表（tabs） ──
    tab_kline, tab_indicators, tab_compare, tab_tv, tab_institutional = st.tabs([
        "📈 K 線圖", "📊 技術指標 (RSI/MACD)", "🔀 多股比較", "🔭 TradingView 技術分析", "🏦 法人籌碼"
    ])

    with tab_kline:
        ma_periods = st.multiselect(
            "均線週期", [5, 10, 20, 60], default=[5, 20],
            key="ma_periods_analysis", label_visibility="collapsed",
        )
        fig = create_tw_stock_chart(df, ma_periods=ma_periods)
        st.plotly_chart(fig, use_container_width=True)

    with tab_indicators:
        st.caption("以下指標由本系統即時計算，反映所選時間範圍內的數值。")
        ind_fig = _render_indicator_chart(df)
        st.plotly_chart(ind_fig, use_container_width=True)

        # 最新指標數值摘要
        from twquant.indicators.basic import compute_rsi, compute_macd
        rsi_val = compute_rsi(df["close"], 14).iloc[-1]
        macd_line, sig_line, hist_val = compute_macd(df["close"])
        m_v, s_v, h_v = macd_line.iloc[-1], sig_line.iloc[-1], hist_val.iloc[-1]

        ri_col, m1, m2, m3 = st.columns(4)
        rsi_state = "超買" if rsi_val > 70 else ("超賣" if rsi_val < 30 else "中性")
        ri_col.metric("RSI(14)", f"{rsi_val:.1f}", rsi_state)
        m1.metric("MACD", f"{m_v:.3f}")
        m2.metric("Signal", f"{s_v:.3f}")
        hist_delta = "多頭" if h_v > 0 else "空頭"
        m3.metric("MACD柱", f"{h_v:.3f}", hist_delta)

    with tab_compare:
        import plotly.graph_objects as go
        from twquant.data.universe import ANALYST_UNIVERSE, get_name

        st.caption("將多支股票的報酬率標準化（起始=100），疊加在同一圖上比較相對表現")
        all_compare_sids = sorted(set(
            sid for stocks in ANALYST_UNIVERSE.values() for sid, _ in stocks
        ))
        compare_sids = st.multiselect(
            "選擇比較標的（可多選）",
            options=all_compare_sids,
            default=[stock_id, "0050"],
            format_func=lambda s: f"{s} {get_name(s)}",
            key="compare_sids_select",
        )
        norm_mode = st.radio("基準化方式", ["起始=100（絕對報酬）", "各自起始=100（相對強弱）"],
                             horizontal=True)

        if compare_sids:
            from twquant.data.storage import SQLiteStorage
            storage_c = SQLiteStorage(DB_PATH)
            fig_cmp = go.Figure()
            color_palette = ["#FFD700","#3B82F6","#22C55E","#EF4444","#A855F7","#F97316","#94A3B8"]

            for i, cmp_sid in enumerate(compare_sids):
                df_c = storage_c.load(f"daily_price/{cmp_sid}",
                                      start_date=str(start_date), end_date=str(end_date))
                if df_c.empty:
                    st.caption(f"{cmp_sid}: 無資料（DB 未入庫）")
                    continue
                close_c = df_c["close"].astype(float)
                dates_c = pd.to_datetime(df_c["date"])
                base = float(close_c.iloc[0])
                normalized = close_c / base * 100
                color = color_palette[i % len(color_palette)]
                width = 2.5 if cmp_sid == stock_id else 1.5
                fig_cmp.add_trace(go.Scatter(
                    x=dates_c, y=normalized,
                    name=f"{cmp_sid} {get_name(cmp_sid)}",
                    line=dict(color=color, width=width),
                    hovertemplate=f"<b>{cmp_sid}</b>: %{{y:.1f}} (+%{{customdata:.1f}}%)<extra></extra>",
                    customdata=(normalized - 100).values,
                ))

            fig_cmp.add_hline(y=100, line_color="#4B5563", line_dash="dot", line_width=1)
            fig_cmp.update_layout(
                height=460,
                hovermode="x unified",
                xaxis_title="日期",
                yaxis_title="相對表現（起始=100）",
                legend=dict(orientation="h", y=1.05),
                margin=dict(l=40, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

            # 報酬率排行榜
            rows_cmp = []
            storage_c2 = SQLiteStorage(DB_PATH)
            for cmp_sid in compare_sids:
                df_c2 = storage_c2.load(f"daily_price/{cmp_sid}",
                                        start_date=str(start_date), end_date=str(end_date))
                if df_c2.empty:
                    continue
                cl2 = df_c2["close"].astype(float)
                ret = (cl2.iloc[-1] / cl2.iloc[0] - 1) * 100
                rows_cmp.append({"代號": cmp_sid, "名稱": get_name(cmp_sid),
                                  "期間報酬": f"{ret:+.1f}%",
                                  "現價": f"{cl2.iloc[-1]:.2f}"})
            if rows_cmp:
                rows_cmp_sorted = sorted(rows_cmp,
                    key=lambda r: float(r["期間報酬"].replace("%","").replace("+","")),
                    reverse=True)
                st.dataframe(pd.DataFrame(rows_cmp_sorted), use_container_width=True, hide_index=True)

    with tab_tv:
        render_tv_technicals(stock_id, height=420)

    with tab_institutional:
        st.info("法人籌碼資料需 FinMind API Token，請在設定精靈中填入後重新同步。")

    # ── Layer 3：區間統計 + 技術水位 ──
    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            st.subheader("📋 區間統計")
            period_high = df["high"].max()
            period_low = df["low"].min()
            period_return = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100
            avg_vol = df["volume"].mean() / 1000
            c1, c2 = st.columns(2)
            c1.metric("區間最高（元）", f"{period_high:.1f}")
            c2.metric("區間最低（元）", f"{period_low:.1f}")
            c1.metric("區間漲跌幅", f"{period_return:+.2f}%")
            c2.metric("日均成交量", f"{avg_vol:,.0f} 張")

    with col_right:
        with st.container(border=True):
            st.subheader("📐 技術水位")
            ma5 = df["close"].rolling(5).mean().iloc[-1]
            ma20 = df["close"].rolling(20).mean().iloc[-1]
            ma60 = df["close"].rolling(60).mean().iloc[-1] if len(df) >= 60 else float("nan")
            current = df["close"].iloc[-1]
            c1, c2 = st.columns(2)
            c1.metric("MA5", f"{ma5:.1f}", f"{'↑' if current > ma5 else '↓'} 股價{'上方' if current > ma5 else '下方'}")
            c2.metric("MA20", f"{ma20:.1f}", f"{'↑' if current > ma20 else '↓'} 股價{'上方' if current > ma20 else '下方'}")
            if not pd.isna(ma60):
                c1.metric("MA60", f"{ma60:.1f}", f"{'↑' if current > ma60 else '↓'} 股價{'上方' if current > ma60 else '下方'}")
            else:
                c1.caption("MA60：資料不足")
            # 布林帶
            from twquant.indicators.basic import compute_bollinger
            upper, mid, lower = compute_bollinger(df["close"])
            c2.metric("布林上軌", f"{upper.iloc[-1]:.1f}")


if __name__ == "__main__":
    main()
