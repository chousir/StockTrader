"""Page 8：今日訊號掃描 - 全宇宙 × 5種已驗證策略的即時進場訊號偵測"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="訊號掃描", page_icon="📡", layout="wide")

DB_PATH = "data/twquant.db"

_STRATEGY_KEYS = [
    "momentum_concentrate",
    "volume_breakout",
    "triple_ma_twist",
    "risk_adj_momentum",
    "donchian_breakout",
]

_STRATEGY_LABEL = {
    "momentum_concentrate": "F｜動能精選 ★",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
}

_STRATEGY_COLORS = {
    "F｜動能精選 ★": "#FFD700",
    "H｜量價突破":   "#F97316",
    "L｜三線扭轉":   "#34D399",
    "M｜RAM動能":    "#60A5FA",
    "N｜唐奇安突破": "#FB7185",
}


# ─────────────────────────────────────────────────────────────
# 掃描邏輯
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800, show_spinner=False)
def scan_signals(strategy_keys: tuple) -> list[dict]:
    import pandas as pd
    from twquant.data.universe import get_name, get_sector
    from twquant.strategy.scanner import scan_universe

    df_raw = scan_universe(list(strategy_keys), db_path=DB_PATH)
    if df_raw.empty:
        return []
    results = []
    for _, row in df_raw.iterrows():
        sid = row["代號"]
        key = row["策略"]
        results.append({
            "代號":    sid,
            "名稱":    get_name(sid),
            "板塊":    get_sector(sid),
            "策略":    _STRATEGY_LABEL.get(key, key),
            "資料截止": row["資料截止"],
            "收盤價":  row["收盤價"],
            "距MA60%": row["距MA60%"],
            "RSI":     row["RSI"],
            "量比":    row["量比"],
        })
    return results


# ─────────────────────────────────────────────────────────────
# 主介面
# ─────────────────────────────────────────────────────────────
def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    register_twquant_dark_template()

    render_global_sidebar(show_stock=False, show_dates=False)

    st.title("📡 今日訊號掃描")
    st.caption("全宇宙 × 5 種已驗證策略 — 偵測最新 K 棒進場訊號 | 快取 30 分鐘")

    with st.sidebar:
        st.header("掃描設定")
        selected_strats = st.multiselect(
            "策略",
            options=_STRATEGY_KEYS,
            default=_STRATEGY_KEYS,
            format_func=lambda k: _STRATEGY_LABEL.get(k, k),
        )
        from twquant.data.universe import list_sectors
        filter_sector = st.selectbox("板塊篩選", ["全部"] + list_sectors())
        scan_btn = st.button("🔍 開始掃描", type="primary", use_container_width=True)

    if not scan_btn:
        st.info("點擊「開始掃描」偵測今日進場訊號。首次約 30-60 秒，結果快取 30 分鐘。")
        with st.expander("📖 各策略進場條件摘要"):
            st.markdown("""
| 策略 | 進場條件 | 驗證最佳標的 |
|------|---------|------------|
| F｜動能精選 ★ | ret₂₀ > 5% + Close > MA60 | 台達電 +369%, Sharpe 1.66 |
| H｜量價突破 | 收盤創20日高 + 量比>1.5x + Close>MA60 + RSI<76 | 台達電 Sharpe 1.81 最高 |
| L｜三線扭轉 | MA5>MA20>MA60 **剛成立第一天** + RSI<72 | 台達電 +258% |
| M｜RAM動能 | RAM=ret₂₀/(σ₂₀×√20) > 0.7 + MA60>MA120 | 南亞科 超額+285% 最高 |
| N｜唐奇安突破 | Close > DC_upper(20) + 量比>1.2x + Close>MA60 + RSI<76 | 台達電 Sharpe 1.72 |
""")
        return

    if not selected_strats:
        st.warning("請選擇至少一種策略")
        return

    with st.spinner("掃描中... 正在對全宇宙股票套用策略（約 30-60 秒）"):
        rows = scan_signals(tuple(selected_strats))

    if not rows:
        st.warning("目前無股票觸發任何進場訊號。可能原因：資料尚未更新、市場整體偏弱。")
        return

    df_res = pd.DataFrame(rows)
    if filter_sector != "全部":
        df_res = df_res[df_res["板塊"] == filter_sector]

    if df_res.empty:
        st.warning(f"板塊「{filter_sector}」中無訊號。")
        return

    # ── 摘要指標 ──
    total_stocks  = df_res["代號"].nunique()
    total_signals = len(df_res)
    strat_counts  = df_res["策略"].value_counts()
    top_strat     = strat_counts.index[0] if len(strat_counts) > 0 else "-"
    latest_date   = df_res["資料截止"].max()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("有訊號股票數",               total_stocks)
    c2.metric("訊號總數（含多策略重複）",   total_signals)
    c3.metric("最多訊號策略",               top_strat[:10])
    c4.metric("資料截止日",                latest_date)

    # 資料新鮮度警告
    today = pd.Timestamp.today().normalize()
    lag_days = (today - pd.to_datetime(latest_date)).days
    if lag_days > 3:
        st.warning(f"⚠️ 資料截止 {latest_date}，距今 {lag_days} 天。建議執行同步腳本更新資料後再掃描。")

    st.divider()

    # ── 策略訊號數長條圖 + 板塊圓餅圖 ──
    col_bar, col_pie = st.columns(2)
    with col_bar:
        st.subheader("各策略訊號數")
        sc = strat_counts.reset_index()
        sc.columns = ["策略", "訊號數"]
        fig_bar = go.Figure(go.Bar(
            x=sc["策略"], y=sc["訊號數"],
            marker_color=[_STRATEGY_COLORS.get(s, "#A855F7") for s in sc["策略"]],
            text=sc["訊號數"], textposition="outside",
        ))
        fig_bar.update_layout(
            height=260, margin=dict(l=20, r=20, t=20, b=60),
            xaxis_tickangle=-15, yaxis_title="訊號數",
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_pie:
        st.subheader("板塊分布")
        sec_cnt = df_res.groupby("板塊")["代號"].nunique().reset_index()
        sec_cnt.columns = ["板塊", "股票數"]
        fig_pie = go.Figure(go.Pie(
            labels=sec_cnt["板塊"], values=sec_cnt["股票數"],
            hole=0.4, textinfo="label+value",
        ))
        fig_pie.update_layout(height=260, margin=dict(l=10, r=10, t=20, b=10),
                              showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── 技術位置散布圖 ──
    st.subheader("📊 技術位置分布（距MA60% vs RSI）")
    df_plot = df_res.dropna(subset=["RSI", "距MA60%"]).copy()
    if not df_plot.empty:
        fig_sc = go.Figure()
        for strat in df_plot["策略"].unique():
            sub = df_plot[df_plot["策略"] == strat]
            fig_sc.add_trace(go.Scatter(
                x=sub["距MA60%"], y=sub["RSI"],
                mode="markers+text",
                name=strat[:10],
                text=sub["代號"] + " " + sub["名稱"],
                textposition="top center",
                textfont=dict(size=9),
                marker=dict(
                    size=10,
                    color=_STRATEGY_COLORS.get(strat, "#A855F7"),
                    opacity=0.85,
                    line=dict(width=1, color="white"),
                ),
            ))
        fig_sc.add_vline(x=0,  line_color="#4B5563", line_dash="dot", line_width=1)
        fig_sc.add_hline(y=50, line_color="#4B5563", line_dash="dot", line_width=1)
        fig_sc.update_layout(
            height=400, hovermode="closest",
            xaxis_title="距MA60（%，正值=站上MA60）",
            yaxis_title="RSI(14)",
            margin=dict(l=50, r=20, t=20, b=40),
            legend=dict(orientation="h", y=1.05),
        )
        st.plotly_chart(fig_sc, use_container_width=True)

    st.divider()

    # ── 訊號清單表格（一股多訊號合併顯示） ──
    st.subheader(f"📋 訊號清單（{df_res['代號'].nunique()} 支股票 / {len(df_res)} 筆訊號）")

    pivot = (
        df_res
        .groupby(["代號", "名稱", "板塊", "資料截止", "收盤價", "距MA60%", "RSI", "量比"])["策略"]
        .apply(lambda x: " / ".join(sorted(set(x))))
        .reset_index()
        .rename(columns={"策略": "觸發策略"})
    )
    pivot = pivot.sort_values("量比", ascending=False)

    display = pivot.copy()
    display["距MA60%"] = display["距MA60%"].apply(lambda v: f"{v:+.1f}%" if v is not None else "N/A")
    display["RSI"]     = display["RSI"].apply(lambda v: f"{v:.1f}" if v is not None else "N/A")
    display["量比"]    = display["量比"].apply(lambda v: f"{v:.2f}x")
    display["收盤價"]  = display["收盤價"].apply(lambda v: f"{v:.2f}")

    st.dataframe(
        display[["代號", "名稱", "板塊", "觸發策略", "收盤價", "距MA60%", "RSI", "量比", "資料截止"]],
        use_container_width=True, hide_index=True, height=520,
    )

    csv_bytes = pivot.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
    st.download_button(
        "⬇️ 下載訊號清單 CSV",
        data=csv_bytes,
        file_name=f"signals_{latest_date}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()