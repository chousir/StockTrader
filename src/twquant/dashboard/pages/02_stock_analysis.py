"""Page 2：個股分析 - 三層佈局（搜尋列 / K線+指標 / 基本資料）"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="個股分析", page_icon="📈", layout="wide")


@st.cache_data(ttl=3600)
def _load_daily(stock_id: str, start_date: str, end_date: str):
    from twquant.data.providers.csv_local import CsvLocalProvider
    from twquant.data.providers.base import EmptyDataError

    try:
        return CsvLocalProvider("data/sample").fetch_daily(stock_id, start_date, end_date)
    except EmptyDataError:
        pass
    from twquant.data.providers.finmind import FinMindProvider
    return FinMindProvider().fetch_daily(stock_id, start_date, end_date)


def main():
    import pandas as pd
    from twquant.dashboard.components.kline_chart import create_tw_stock_chart
    from twquant.dashboard.components.smart_search import render_smart_search
    from twquant.dashboard.components.watchlist_ui import (
        render_watchlist_chips,
        render_watchlist_button,
    )

    # ── Layer 1：全局導覽（搜尋 + 關注清單快捷 + 狀態） ──
    col_search, col_chips, col_status = st.columns([4, 4, 1])
    with col_search:
        searched_id = render_smart_search(key="stock_analysis_search")
    with col_chips:
        render_watchlist_chips()
    with col_status:
        st.caption("🟢")

    # 決定最終股票代碼（搜尋 > session_state > 預設）
    stock_id = (
        searched_id
        or st.session_state.get("current_stock")
        or "2330"
    )

    st.divider()

    # ── 日期選擇（側邊欄） ──
    with st.sidebar:
        st.header("時間範圍")
        start_date = st.date_input("開始日期", value=pd.Timestamp("2024-01-01"))
        end_date = st.date_input("結束日期", value=pd.Timestamp("2024-12-31"))
        render_watchlist_button(stock_id)

    # ── 載入資料 ──
    try:
        df = _load_daily(stock_id, str(start_date), str(end_date))
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        return

    if df.empty:
        st.warning("無數據，請確認股票代碼與日期範圍。")
        return

    st.caption(f"{stock_id} | {len(df)} 個交易日 | {df['date'].min()} ~ {df['date'].max()}")

    # ── Layer 2：主力圖表（tabs） ──
    tab_kline, tab_indicators, tab_institutional = st.tabs(["📈 K 線圖", "📊 技術指標", "🏦 法人籌碼"])

    with tab_kline:
        ma_periods = st.multiselect("均線週期", [5, 10, 20, 60], default=[5, 20],
                                     key="ma_periods", label_visibility="collapsed")
        fig = create_tw_stock_chart(df, ma_periods=ma_periods)
        st.plotly_chart(fig, use_container_width=True)

    with tab_indicators:
        st.info("技術指標面板（Phase 8 整合）")

    with tab_institutional:
        st.info("法人籌碼面板（Phase 8 整合）")

    # ── Layer 3：輔助資訊 ──
    st.divider()
    col_left, col_right = st.columns(2)

    with col_left:
        with st.container(border=True):
            st.subheader("公司基本資料")
            st.caption(f"股票代碼：{stock_id}")
            st.caption("更多資訊整合中（Phase 8 實作）")

    with col_right:
        with st.container(border=True):
            st.subheader("關鍵財務指標")
            close = df["close"].iloc[-1]
            high = df["high"].max()
            low = df["low"].min()
            vol_avg = df["volume"].mean()
            c1, c2 = st.columns(2)
            c1.metric("最新收盤", f"{close:.1f}")
            c2.metric("區間最高", f"{high:.1f}")
            c1.metric("區間最低", f"{low:.1f}")
            c2.metric("均量", f"{vol_avg:,.0f}")


if __name__ == "__main__":
    main()
