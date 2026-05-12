"""首頁排行榜 tabs — 策略訊號 + 漲幅/跌幅/量爆/突破"""
from __future__ import annotations
import streamlit as st


@st.cache_data(ttl=900, show_spinner=False)
def _get_rankings(db_path: str = "data/twquant.db"):
    from twquant.data.rankings import daily_rankings
    return daily_rankings(top_n=10, db_path=db_path)


def render_home_rankings(signals: list[dict], db_path: str = "data/twquant.db"):
    import pandas as pd

    tab_sig, tab_up, tab_dn, tab_vol, tab_brk = st.tabs(
        ["📡 訊號", "🚀 漲幅", "📉 跌幅", "⚡ 量爆", "💥 突破"]
    )

    with tab_sig:
        if signals:
            st.dataframe(pd.DataFrame(signals[:10]), use_container_width=True,
                         hide_index=True, height=210)
            st.caption(f"共 {len(signals)} 筆 — 完整掃描請到 📡 訊號掃描")
        else:
            st.caption("今日無訊號（自選 + 熱門）— 完整掃描請至 📡 訊號掃描")

    try:
        rnk = _get_rankings(db_path)
    except Exception:
        for tab in (tab_up, tab_dn, tab_vol, tab_brk):
            with tab:
                st.caption("排行榜暫無資料（DB 尚未入庫）")
        return

    for tab, key in [(tab_up, "gainers"), (tab_dn, "losers"),
                     (tab_vol, "vol_surge"), (tab_brk, "breakouts")]:
        with tab:
            df_r = rnk.get(key)
            if df_r is not None and not df_r.empty:
                st.dataframe(df_r, use_container_width=True, hide_index=True, height=210)
            else:
                st.caption("今日暫無資料")
