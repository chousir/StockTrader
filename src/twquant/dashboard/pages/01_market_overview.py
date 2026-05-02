"""Page 1：市場總覽 - 跑馬燈 + 大盤摘要 + TradingView 熱力圖"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="市場總覽", page_icon="🏛️", layout="wide")

from twquant.dashboard.components.tradingview_widgets import (
    render_tv_heatmap,
    render_tv_ticker_tape,
)


def main():
    # ── 跑馬燈（頁面頂部即時行情）──
    render_tv_ticker_tape()

    st.title("🏛️ 市場總覽")

    # ── 大盤摘要卡片 ──
    st.subheader("大盤指標")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("台灣加權指數", "—", help="即時數據整合中")
    c2.metric("成交量 (億)", "—", help="即時數據整合中")
    c3.metric("外資買賣超", "—", help="即時數據整合中")
    c4.metric("融資餘額變化", "—", help="即時數據整合中")

    st.divider()

    # ── TradingView 台股熱力圖 ──
    with st.container(border=True):
        st.subheader("📊 台股類股熱力圖")
        render_tv_heatmap(height=500)

    st.divider()

    # ── 雙欄：外資排行 + 融資融券 ──
    col_foreign, col_margin = st.columns(2)

    with col_foreign:
        with st.container(border=True):
            st.subheader("🏦 外資買超排行（近 5 日）")
            st.info("法人資料整合中（Phase 7 實作）")

    with col_margin:
        with st.container(border=True):
            st.subheader("📉 融資融券變化")
            st.info("融資融券資料整合中（Phase 7 實作）")


if __name__ == "__main__":
    main()
