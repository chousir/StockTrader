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
    try:
        from twquant.data.providers.csv_local import CsvLocalProvider
        return CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except Exception:
        pass
    from twquant.data.providers.finmind import FinMindProvider
    from twquant.dashboard.config import get_finmind_token
    df_api = FinMindProvider(token=get_finmind_token() or "").fetch_daily(stock_id, start_date, end_date)
    storage.upsert(f"daily_price/{stock_id}", df_api)
    return df_api


def _render_indicator_chart(df):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from twquant.indicators.basic import compute_rsi, compute_macd, compute_ma, compute_kd
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.styles.theme import TWStockColors

    register_twquant_dark_template()
    close = df["close"]
    dates = df["date"].astype(str)
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                        row_heights=[0.38, 0.20, 0.22, 0.20],
                        subplot_titles=("收盤價 + 均線", "RSI (14)", "MACD (12,26,9)", "KD (9,3,3)"))
    fig.add_trace(go.Scatter(x=dates, y=close, mode="lines", name="收盤",
                             line=dict(color="#E8EAED", width=1.5)), row=1, col=1)
    for p, c in [(5, TWStockColors.MA_5), (20, TWStockColors.MA_20), (60, TWStockColors.MA_60)]:
        if len(df) >= p:
            fig.add_trace(go.Scatter(x=dates, y=compute_ma(close, p), mode="lines",
                                     name=f"MA{p}", line=dict(color=c, width=1)), row=1, col=1)
    rsi = compute_rsi(close, 14)
    fig.add_trace(go.Scatter(x=dates, y=rsi, mode="lines", name="RSI",
                             line=dict(color="#A855F7", width=1.5)), row=2, col=1)
    for level, color, dash in [(70, "#EF4444", "dash"), (30, "#22C55E", "dash"), (50, "#6B7280", "dot")]:
        fig.add_hline(y=level, line_color=color, line_dash=dash, line_width=1, row=2, col=1)
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    macd, signal, hist = compute_macd(close, 12, 26, 9)
    bar_colors = ["#EF4444" if h >= 0 else "#22C55E" for h in hist.fillna(0)]
    fig.add_trace(go.Bar(x=dates, y=hist, name="MACD柱", marker_color=bar_colors, showlegend=False), row=3, col=1)
    fig.add_trace(go.Scatter(x=dates, y=macd, mode="lines", name="MACD",
                             line=dict(color="#3B82F6", width=1.2)), row=3, col=1)
    fig.add_trace(go.Scatter(x=dates, y=signal, mode="lines", name="Signal",
                             line=dict(color="#F97316", width=1.2)), row=3, col=1)
    fig.add_hline(y=0, line_color="#6B7280", line_width=0.8, row=3, col=1)
    k, d = compute_kd(df["high"], df["low"], df["close"])
    fig.add_trace(go.Scatter(x=dates, y=k, mode="lines", name="K",
                             line=dict(color="#22C55E", width=1.5)), row=4, col=1)
    fig.add_trace(go.Scatter(x=dates, y=d, mode="lines", name="D",
                             line=dict(color="#EF4444", width=1.5)), row=4, col=1)
    for level, color in [(80, "#EF4444"), (20, "#22C55E"), (50, "#6B7280")]:
        fig.add_hline(y=level, line_color=color, line_dash="dash", line_width=1, row=4, col=1)
    fig.update_yaxes(range=[0, 100], row=4, col=1)
    fig.update_layout(height=680, xaxis_rangeslider_visible=False,
                      margin=dict(l=40, r=20, t=40, b=20), hovermode="x unified",
                      legend=dict(orientation="h", y=1.02))
    return fig


@st.cache_data(ttl=3600)
def _load_institutional(stock_id: str, start_date: str, end_date: str):
    try:
        from twquant.data.providers.finmind import FinMindProvider
        from twquant.dashboard.config import get_finmind_token
        api = FinMindProvider(token=get_finmind_token() or "")
        return api.fetch_institutional(stock_id, start_date, end_date)
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _load_monthly_revenue(stock_id: str, start_date: str):
    import pandas as pd
    try:
        from twquant.data.providers.finmind import FinMindProvider
        from twquant.dashboard.config import get_finmind_token
        api = FinMindProvider(token=get_finmind_token() or "")
        api._limiter.wait_if_needed()
        raw = api._api.taiwan_stock_month_revenue(stock_id=stock_id, start_date=start_date)
        if raw is None or raw.empty:
            return None
        raw["date"] = pd.to_datetime(raw["date"])
        raw = raw.sort_values("date").reset_index(drop=True)
        return raw
    except Exception:
        return None


@st.cache_data(ttl=3600)
def _load_per_pbr(stock_id: str, start_date: str):
    import pandas as pd
    try:
        from twquant.data.providers.finmind import FinMindProvider
        from twquant.dashboard.config import get_finmind_token
        api = FinMindProvider(token=get_finmind_token() or "")
        api._limiter.wait_if_needed()
        raw = api._api.taiwan_stock_per_pbr(stock_id=stock_id, start_date=start_date)
        if raw is None or raw.empty:
            return None
        raw["date"] = pd.to_datetime(raw["date"])
        raw = raw.sort_values("date").reset_index(drop=True)
        return raw
    except Exception:
        return None


def main():
    import pandas as pd
    from twquant.dashboard.components.kline_chart import create_tw_stock_chart
    from twquant.dashboard.components.smart_search import render_smart_search
    from twquant.dashboard.components.watchlist_ui import (
        render_watchlist_chips,
        render_watchlist_button,
    )
    from twquant.dashboard.components.tradingview_widgets import render_tv_technicals
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    # 全域 sidebar：日期 + 快取清除（股票由 smart_search 控制）
    ctx = render_global_sidebar(show_stock=False, show_dates=True)
    start_date = ctx["start_date"]
    end_date = ctx["end_date"]

    with st.sidebar:
        st.divider()
        st.caption("📌 關注清單")

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
        or st.session_state.get("g_current_stock")
        or st.session_state.get("current_stock")
        or "2330"
    )

    with st.sidebar:
        render_watchlist_button(stock_id)

    st.divider()

    # ── 載入資料 ──
    try:
        df = _load_daily(stock_id, str(start_date), str(end_date))
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        return

    if df.empty:
        st.warning("查無資料，請確認股票代碼與日期範圍。樣本庫目前僅含 2330、0050、2317。")
        return

    # ── 標題列：精簡版（今日詳情放 expander）──
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) >= 2 else latest
    chg = latest["close"] - prev["close"]
    chg_pct = chg / prev["close"] * 100
    chg_color = "#EF4444" if chg > 0 else ("#22C55E" if chg < 0 else "#9CA3AF")
    arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "─")

    title_col, btn_col = st.columns([5, 1])
    with title_col:
        st.markdown(
            f"### {stock_id} &nbsp; "
            f"<span style='font-size:1.5rem;color:{chg_color}'>{latest['close']:.1f}</span> &nbsp; "
            f"<span style='color:{chg_color};font-size:0.9rem'>{arrow}{abs(chg):.1f}（{chg_pct:+.2f}%）</span>",
            unsafe_allow_html=True,
        )
        st.caption(f"最後更新：{latest['date']} | {len(df)} 個交易日")
    with btn_col:
        if st.button("⚡ 快速回測", use_container_width=True, type="primary",
                     help="帶入當前股票跳到策略建構器"):
            st.session_state.update({"g_current_stock": stock_id, "current_stock": stock_id})
            st.switch_page("pages/03_strategy_builder.py")

    with st.expander("📋 今日詳情"):
        e1, e2, e3, e4 = st.columns(4)
        e1.metric("開盤", f"{latest['open']:.1f}")
        e2.metric("最高", f"{latest['high']:.1f}")
        e3.metric("最低", f"{latest['low']:.1f}")
        e4.metric("成交量", f"{latest['volume']/1000:,.0f} 張")

    # ── 3 Tabs（技術 / 籌碼 / 基本面） ──
    tab_tech, tab_institutional, tab_fundamental = st.tabs([
        "📈 技術", "🏦 籌碼", "💰 基本面"
    ])

    with tab_tech:
        ma_periods = st.multiselect(
            "均線週期", [5, 10, 20, 60], default=[5, 20],
            key="ma_periods_analysis", label_visibility="collapsed",
        )
        fig = create_tw_stock_chart(df, ma_periods=ma_periods)
        st.plotly_chart(fig, use_container_width=True)

        # 技術指標（可展開）
        with st.expander("📊 技術指標（RSI / MACD / KD）"):
            ind_fig = _render_indicator_chart(df)
            st.plotly_chart(ind_fig, use_container_width=True)

        # 技術水位 + 區間統計（可展開）
        with st.expander("📐 技術水位 + 區間統計"):
            from twquant.indicators.basic import compute_bollinger
            close = df["close"].astype(float)
            ma5   = float(close.rolling(5).mean().iloc[-1])
            ma20  = float(close.rolling(20).mean().iloc[-1])
            ma60  = float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else float("nan")
            upper_bb, _, _ = compute_bollinger(close)
            curr  = float(close.iloc[-1])
            w1, w2, w3, w4 = st.columns(4)
            w1.metric("MA5",  f"{ma5:.1f}",  f"{'↑' if curr>ma5 else '↓'}")
            w2.metric("MA20", f"{ma20:.1f}", f"{'↑' if curr>ma20 else '↓'}")
            if not pd.isna(ma60):
                w3.metric("MA60", f"{ma60:.1f}", f"{'↑' if curr>ma60 else '↓'}")
            w4.metric("布林上軌", f"{upper_bb.iloc[-1]:.1f}")
            st.divider()
            period_ret = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("區間最高", f"{df['high'].max():.1f}")
            s2.metric("區間最低", f"{df['low'].min():.1f}")
            s3.metric("區間漲跌幅", f"{period_ret:+.2f}%")
            s4.metric("日均成交量", f"{df['volume'].mean()/1000:,.0f} 張")

        # TradingView 外部技術評分（可展開）
        with st.expander("🔭 外部技術評分（TradingView）"):
            render_tv_technicals(stock_id, height=320)

    with tab_institutional:
        import plotly.graph_objects as go
        st.caption("外資、投信、自營商每日買賣超（來源：FinMind）")
        inst_start = (pd.Timestamp.today() - pd.DateOffset(months=6)).strftime("%Y-%m-%d")
        df_inst = _load_institutional(stock_id, inst_start, str(end_date))
        if df_inst is None or df_inst.empty:
            st.info("⚠️ 無法取得法人資料，請確認 FinMind Token 已設定（設定精靈 → API Token）")
        else:
            # 找出外資/投信/自營商 net 欄位
            cols_buy = [c for c in df_inst.columns if c.endswith("_buy")]
            cols_sell = [c for c in df_inst.columns if c.endswith("_sell")]
            INST_NAME_MAP = {
                "Foreign_Investor": "外資",
                "Investment_Trust": "投信",
                "Dealer_self": "自營商(自行)",
                "Dealer": "自營商",
            }
            inst_colors = {"外資": "#3B82F6", "投信": "#F97316", "自營商": "#A855F7", "自營商(自行)": "#A855F7"}

            # 累計淨買超（近60日）
            df_inst["date"] = pd.to_datetime(df_inst["date"])
            df_inst = df_inst.tail(60)

            fig_inst = go.Figure()
            for buy_col in cols_buy:
                name_key = buy_col.replace("_buy", "")
                sell_col = name_key + "_sell"
                label = INST_NAME_MAP.get(name_key, name_key)
                if sell_col not in df_inst.columns:
                    continue
                net = df_inst[buy_col].fillna(0) - df_inst[sell_col].fillna(0)
                color = inst_colors.get(label, "#94A3B8")
                bar_colors = [color if v >= 0 else "#EF4444" for v in net]
                fig_inst.add_trace(go.Bar(
                    x=df_inst["date"], y=net / 1000,
                    name=label,
                    marker_color=bar_colors,
                    hovertemplate=f"<b>{label}</b>: %{{y:+,.0f}} 張<extra></extra>",
                ))

            fig_inst.update_layout(
                height=360, barmode="group",
                xaxis_title="日期", yaxis_title="淨買超（千股）",
                hovermode="x unified",
                legend=dict(orientation="h", y=1.05),
                margin=dict(l=40, r=20, t=20, b=20),
            )
            st.plotly_chart(fig_inst, use_container_width=True)

        st.divider()
        st.caption("📋 月營收 MoM（月增率）/ YoY（年增率），來源：FinMind")
        rev_start = (pd.Timestamp.today() - pd.DateOffset(years=2)).strftime("%Y-%m-%d")
        df_rev = _load_monthly_revenue(stock_id, rev_start)
        if df_rev is None or df_rev.empty:
            st.info("⚠️ 無法取得月營收資料，請確認 FinMind Token 已設定")
        else:
            rev_col = next((c for c in ["revenue", "Revenue", "revenue_month"] if c in df_rev.columns), None)
            if rev_col is None:
                st.warning(f"欄位名稱異常：{list(df_rev.columns)}")
            else:
                df_rev["revenue_val"] = pd.to_numeric(df_rev[rev_col], errors="coerce")
                df_rev = df_rev.dropna(subset=["revenue_val"])
                df_rev["mom"] = df_rev["revenue_val"].pct_change(1) * 100
                df_rev["yoy"] = df_rev["revenue_val"].pct_change(12) * 100
                mom_colors = ["#22C55E" if v >= 0 else "#EF4444" for v in df_rev["mom"].fillna(0)]
                fig_rev = go.Figure()
                fig_rev.add_trace(go.Bar(x=df_rev["date"], y=df_rev["mom"], name="MoM%",
                                         marker_color=mom_colors))
                fig_rev.add_trace(go.Scatter(x=df_rev["date"], y=df_rev["yoy"], name="YoY%",
                                             mode="lines+markers", line=dict(color="#F97316", width=2)))
                fig_rev.add_hline(y=0, line_color="#4B5563", line_width=1)
                fig_rev.update_layout(height=280, hovermode="x unified", yaxis_title="%",
                                      legend=dict(orientation="h", y=1.05),
                                      margin=dict(l=40, r=20, t=20, b=20))
                st.plotly_chart(fig_rev, use_container_width=True)

    with tab_fundamental:
        from plotly.subplots import make_subplots as _msp2
        st.caption("本益比(PER) / 股價淨值比(PBR) / 殖利率，來源：FinMind")
        fund_start = (pd.Timestamp.today() - pd.DateOffset(years=3)).strftime("%Y-%m-%d")
        df_fund = _load_per_pbr(stock_id, fund_start)
        if df_fund is None or df_fund.empty:
            st.info("⚠️ 無法取得本益比/殖利率資料，請確認 FinMind Token 已設定")
        else:
            per_col = next((c for c in ["PER", "per", "price_earnings_ratio"] if c in df_fund.columns), None)
            pbr_col = next((c for c in ["PBR", "pbr", "price_book_ratio"] if c in df_fund.columns), None)
            div_col = next((c for c in ["dividend_yield", "DividendYield", "yield"] if c in df_fund.columns), None)
            if per_col is None and pbr_col is None:
                st.warning(f"欄位名稱異常：{list(df_fund.columns)}")
            else:
                latest_fund = df_fund.iloc[-1]
                f1, f2, f3 = st.columns(3)
                f1.metric("最新 PER", f"{float(latest_fund[per_col]):.1f}x"
                          if per_col and pd.notna(latest_fund.get(per_col)) else "N/A")
                f2.metric("最新 PBR", f"{float(latest_fund[pbr_col]):.2f}x"
                          if pbr_col and pd.notna(latest_fund.get(pbr_col)) else "N/A")
                f3.metric("最新殖利率", f"{float(latest_fund[div_col]):.2f}%"
                          if div_col and pd.notna(latest_fund.get(div_col)) else "N/A")
                fig_fund = _msp2(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                                  subplot_titles=("本益比 (PER)", "殖利率 (%)"))
                if per_col:
                    df_fund[per_col] = pd.to_numeric(df_fund[per_col], errors="coerce")
                    fig_fund.add_trace(go.Scatter(x=df_fund["date"], y=df_fund[per_col],
                                                  name="PER", line=dict(color="#3B82F6", width=2)), row=1, col=1)
                if div_col:
                    df_fund[div_col] = pd.to_numeric(df_fund[div_col], errors="coerce")
                    fig_fund.add_trace(go.Scatter(x=df_fund["date"], y=df_fund[div_col],
                                                  name="殖利率", line=dict(color="#22C55E", width=2)), row=2, col=1)
                fig_fund.update_layout(height=380, hovermode="x unified", showlegend=False,
                                       margin=dict(l=40, r=20, t=40, b=20))
                st.plotly_chart(fig_fund, use_container_width=True)



if __name__ == "__main__":
    main()
