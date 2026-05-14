"""關注清單 UI 元件：加入/移除按鈕、頂部管理面板、側邊欄清單"""

import streamlit as st


def _get_watchlist():
    import sys
    sys.path.insert(0, "src")
    from twquant.data.watchlist import Watchlist
    return Watchlist()


def render_watchlist_button(stock_id: str, stock_name: str = "") -> None:
    """個股頁面標題列的加入/移除自選切換按鈕"""
    wl = _get_watchlist()
    if wl.contains(stock_id):
        if st.button("✅ 已自選", key=f"wl_{stock_id}", type="secondary",
                     use_container_width=True,
                     help="已在長期追蹤清單中，點擊移除"):
            wl.remove(stock_id)
            st.rerun()
    else:
        if st.button("⭐ 加入自選", key=f"wl_{stock_id}", type="primary",
                     use_container_width=True,
                     help="加入長期追蹤清單，持久保存於 data/watchlist.json"):
            wl.add(stock_id, stock_name)
            st.rerun()


@st.cache_data(ttl=900)
def _load_wl_prices(sids: tuple) -> dict:
    """讀取自選股最新收盤價與漲跌%（{sid: (price, chg_pct)}）"""
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage("data/twquant.db")
    out: dict = {}
    for sid in sids:
        try:
            df = storage.load(f"daily_price/{sid}")
            if len(df) >= 2:
                df = df.sort_values("date")
                c = df["close"].astype(float)
                last, prev = float(c.iloc[-1]), float(c.iloc[-2])
                out[sid] = (last, (last / prev - 1) * 100 if prev else 0.0)
        except Exception:
            pass
    return out


def render_watchlist_panel() -> None:
    """頁 02 頂部自選股管理面板：看清單 / 勾選 / 帶去頁 06 / 移除"""
    import pandas as pd
    from twquant.data.universe import get_name

    wl = _get_watchlist()
    items = wl.list_with_details()

    with st.expander(f"⭐ 我的自選股 ({len(items)})", expanded=True):
        if not items:
            st.info("尚無自選股 — 用下方標題列的「⭐ 加入自選」加入第一檔")
            return

        sids = [it["stock_id"] for it in items]
        prices = _load_wl_prices(tuple(sids))
        rows = []
        for it in items:
            sid = it["stock_id"]
            price, chg = prices.get(sid, (None, None))
            rows.append({
                "選取": False,
                "代號": sid,
                "名稱": it.get("stock_name") or get_name(sid),
                "現價": price,
                "漲跌%": chg,
            })
        df = pd.DataFrame(rows)

        edited = st.data_editor(
            df,
            key="wl_panel_editor",
            hide_index=True,
            use_container_width=True,
            column_config={
                "選取": st.column_config.CheckboxColumn("選取", default=False),
                "代號": st.column_config.TextColumn("代號", disabled=True),
                "名稱": st.column_config.TextColumn("名稱", disabled=True),
                "現價": st.column_config.NumberColumn("現價", format="%.1f", disabled=True),
                "漲跌%": st.column_config.NumberColumn("漲跌%", format="%+.2f", disabled=True),
            },
        )
        selected = edited[edited["選取"]]["代號"].tolist()

        st.caption(f"已選 {len(selected)} 檔（勾選後選擇下方操作）")
        c1, c2, c3 = st.columns(3)
        if c1.button(f"🚀 帶 {len(selected)} 檔去頁 06 策略掃描",
                     disabled=not selected, use_container_width=True,
                     key="wl_to_p06"):
            st.session_state["g_scan_custom_list"] = selected
            st.switch_page("pages/06_vs_benchmark.py")
        if c2.button("📈 看 K 線", disabled=len(selected) != 1,
                     use_container_width=True, key="wl_view_kline",
                     help="勾選恰好 1 檔時可用"):
            st.session_state["g_current_stock"] = selected[0]
            st.session_state["current_stock"] = selected[0]
            st.rerun()
        if c3.button(f"🗑 從自選移除 {len(selected)} 檔",
                     disabled=not selected, use_container_width=True,
                     key="wl_remove_sel"):
            for sid in selected:
                wl.remove(sid)
            st.session_state.pop("wl_panel_editor", None)
            st.rerun()


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
