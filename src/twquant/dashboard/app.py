"""Streamlit 主入口：台股量化分析平台"""

import streamlit as st

st.set_page_config(
    page_title="twquant 台股量化",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _load_data(stock_id: str, start_date: str, end_date: str):
    """@st.cache_data 快取數據讀取（CSV 本地 → FinMind fallback）"""
    import sys

    sys.path.insert(0, "src")
    import pandas as pd

    from twquant.data.providers.csv_local import CsvLocalProvider
    from twquant.data.providers.base import EmptyDataError

    try:
        provider = CsvLocalProvider("data/sample")
        return provider.fetch_daily(stock_id, start_date, end_date)
    except EmptyDataError:
        pass

    try:
        from twquant.data.providers.finmind import FinMindProvider

        provider = FinMindProvider()
        return provider.fetch_daily(stock_id, start_date, end_date)
    except Exception as e:
        st.error(f"數據載入失敗：{e}")
        return pd.DataFrame()


load_data = st.cache_data(ttl=3600)(_load_data)


def main():
    import sys

    sys.path.insert(0, "src")
    import pandas as pd
    from twquant.dashboard.components.kline_chart import create_tw_stock_chart

    # ── 側邊欄 ──
    with st.sidebar:
        st.title("twquant 台股量化")
        stock_id = st.text_input("股票代碼", value="2330", max_chars=6)
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("開始日期", value=pd.Timestamp("2024-01-01"))
        with col2:
            end_date = st.date_input("結束日期", value=pd.Timestamp("2024-12-31"))
        ma_options = st.multiselect(
            "均線週期",
            options=[5, 10, 20, 60],
            default=[5, 20],
        )

    # ── 主頁面 ──
    st.header(f"📊 {stock_id} 日K線圖")

    df = load_data(stock_id, str(start_date), str(end_date))

    if df.empty:
        st.warning("無數據可顯示，請確認股票代碼與日期範圍。")
        return

    st.caption(f"共 {len(df)} 個交易日 | {df['date'].min()} ~ {df['date'].max()}")

    fig = create_tw_stock_chart(df, ma_periods=ma_options)
    st.plotly_chart(fig, use_container_width=True)

    # OHLCV 摘要
    with st.expander("數據摘要", expanded=False):
        st.dataframe(df.tail(20), use_container_width=True)


if __name__ == "__main__":
    main()
