"""關注清單 UI 元件：加入/移除按鈕、快捷 chips、側邊欄清單"""

import streamlit as st


def _get_watchlist():
    import sys
    sys.path.insert(0, "src")
    from twquant.data.watchlist import Watchlist
    return Watchlist()


def render_watchlist_button(stock_id: str, stock_name: str = "") -> None:
    """個股頁面標題旁的加入/移除切換按鈕"""
    wl = _get_watchlist()
    if wl.contains(stock_id):
        if st.button("⭐ 已關注", key=f"wl_{stock_id}", type="secondary"):
            wl.remove(stock_id)
            st.rerun()
    else:
        if st.button("☆ 加入關注", key=f"wl_{stock_id}", type="primary"):
            wl.add(stock_id, stock_name)
            st.rerun()


def render_watchlist_chips() -> None:
    """頂部搜尋列旁的關注清單快捷 chips（最多顯示 8 檔）"""
    wl = _get_watchlist()
    stocks = wl.list_all()

    if not stocks:
        st.caption("尚未關注任何股票")
        return

    cols = st.columns(min(len(stocks), 8))
    for i, stock_id in enumerate(stocks[:8]):
        with cols[i]:
            if st.button(stock_id, key=f"chip_{stock_id}", use_container_width=True):
                st.session_state["current_stock"] = stock_id
                st.session_state["g_current_stock"] = stock_id
                st.rerun()

    if len(stocks) > 8:
        st.caption(f"...及其他 {len(stocks) - 8} 檔")


def render_watchlist_sidebar() -> None:
    """側邊欄完整關注清單"""
    wl = _get_watchlist()
    with st.sidebar:
        st.subheader("⭐ 關注清單")
        items = wl.list_with_details()
        if not items:
            st.caption("尚無關注股票")
            return
        for item in items:
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                if st.button(
                    item["stock_id"],
                    key=f"sidebar_wl_{item['stock_id']}",
                    use_container_width=True,
                ):
                    st.session_state["current_stock"] = item["stock_id"]
                    st.session_state["g_current_stock"] = item["stock_id"]
                    st.rerun()
            with col_btn:
                if st.button("✕", key=f"rm_wl_{item['stock_id']}"):
                    wl.remove(item["stock_id"])
                    st.rerun()
