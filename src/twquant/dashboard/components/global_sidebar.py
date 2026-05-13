"""全域側邊欄元件：跨頁共用的股票/日期/快取控制"""

import streamlit as st
import pandas as pd


def render_global_sidebar(
    show_stock: bool = True,
    show_dates: bool = True,
    default_stock: str = "2330",
    default_years: int = 1,
) -> dict:
    """
    共用側邊欄：讀寫 g_current_stock / g_date_start / g_date_end。

    Returns {"stock_id": str, "start_date": date, "end_date": date}
    """
    today = pd.Timestamp.today().normalize()
    default_end = (today - pd.Timedelta(days=1)).date()
    default_start = (today - pd.DateOffset(years=default_years)).date()

    g_stock = st.session_state.get(
        "g_current_stock",
        st.session_state.get("current_stock", default_stock),
    )
    g_start = st.session_state.get("g_date_start", default_start)
    g_end = st.session_state.get("g_date_end", default_end)

    result: dict = {"stock_id": g_stock, "start_date": g_start, "end_date": g_end}

    with st.sidebar:
        if show_stock:
            new_stock = st.text_input(
                "股票代碼", value=g_stock, max_chars=6, key="g_stock_input"
            )
            sid = (new_stock or "").strip()
            if sid:
                st.session_state["g_current_stock"] = sid
                st.session_state["current_stock"] = sid
                result["stock_id"] = sid

        if show_dates:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("開始日期", value=g_start, key="g_start_date")
            with col2:
                end_date = st.date_input("結束日期", value=g_end, key="g_end_date")
            st.session_state["g_date_start"] = start_date
            st.session_state["g_date_end"] = end_date
            result["start_date"] = start_date
            result["end_date"] = end_date

        st.divider()
        if st.button(
            "🔄 清除快取",
            use_container_width=True,
            help="強制重新從資料庫載入所有快取資料",
            key="g_clear_cache",
        ):
            st.cache_data.clear()
            st.rerun()

        basket = list(st.session_state.get("g_basket", []))
        if basket:
            st.divider()
            with st.expander(f"🛒 交易籃（{len(basket)}）"):
                for sid in basket:
                    c1, c2 = st.columns([3, 1])
                    c1.caption(sid)
                    if c2.button("✗", key=f"bsk_rm_{sid}", use_container_width=True):
                        from twquant.data.basket import remove_from_basket
                        remove_from_basket(sid)
                        st.rerun()
                if st.button("🗑️ 清空籃子", use_container_width=True, key="bsk_clear"):
                    from twquant.data.basket import clear_basket
                    clear_basket()
                    st.rerun()
                if st.button("📊 跳頁 07 組合回測", type="primary",
                             use_container_width=True, key="bsk_goto07"):
                    st.switch_page("pages/07_portfolio.py")

        # ── 📡 全域同步狀態 widget（最底） ──
        st.divider()
        try:
            from twquant.data.sync_jobs import latest_running_job
            from twquant.data.auto_sync import last_sync_info
            job = latest_running_job("data/twquant.db")
            if job:
                pct = job["done"] / max(job["total"], 1)
                type_emoji = {"onboarding": "🎯", "manual": "🔄", "auto": "📡"}.get(
                    job["job_type"], "📡")
                st.caption(f"{type_emoji} 同步中：{job['done']}/{job['total']}")
                st.progress(pct, text=job.get("current_sid") or "初始化...")
            else:
                info = last_sync_info("data/twquant.db")
                mh_icon = "🟢" if info["thread_alive"] else "⚪"
                st.caption(f"{mh_icon} 同步：{info['up_to_date']}/{info['total']} 最新"
                           + ("（盤中）" if info["is_market_hours"] else ""))
        except Exception:
            pass

    return result
