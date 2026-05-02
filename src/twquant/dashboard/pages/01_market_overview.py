"""Page 1：市場總覽 - 大盤指數 + 法人動態 + TradingView 熱力圖預留區"""

import sys

sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="市場總覽", page_icon="🏛️", layout="wide")


def main():
    st.title("🏛️ 市場總覽")

    # ── 大盤摘要卡片 ──
    st.subheader("大盤指標")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("台灣加權指數", "—", help="即時數據 Phase 8 整合")
    c2.metric("成交量 (億)", "—", help="即時數據 Phase 8 整合")
    c3.metric("外資買賣超", "—", help="即時數據 Phase 8 整合")
    c4.metric("融資餘額變化", "—", help="即時數據 Phase 8 整合")

    st.divider()

    # ── TradingView 熱力圖預留區（Phase 8.1-8.2 實作）──
    with st.container(border=True):
        st.subheader("📊 台股類股熱力圖")
        st.info("TradingView 市場熱力圖將於 Phase 8 嵌入（TWSE + TPEX 類股漲跌一覽）")
        st.caption("預計嵌入：TWSE 電子 / 金融 / 傳產類股市值加權熱力圖，grouping=sector")

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
