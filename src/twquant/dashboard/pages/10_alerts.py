"""Page 10：告警中心 — 規則管理 + 觸發紀錄 + 手動掃描"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="告警中心", page_icon="🔔", layout="wide")

DB_PATH = "data/twquant.db"

_RULE_TYPES = {
    "price_break":     "📈 突破N日高/低點",
    "rsi_threshold":   "📊 RSI 閾值穿越",
    "strategy_signal": "📡 策略進場訊號",
}

_STRAT_KEYS = [
    "momentum_concentrate",
    "volume_breakout",
    "triple_ma_twist",
    "risk_adj_momentum",
    "donchian_breakout",
]
_STRAT_LABEL = {
    "momentum_concentrate": "F｜動能精選",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
}


def main():
    import pandas as pd
    from twquant.data.alerts import (
        init_schema, add_rule, list_rules, delete_rule, toggle_rule,
        list_logs, ack_log, ack_all, unread_count,
    )
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    render_global_sidebar(show_stock=False, show_dates=False)
    init_schema(DB_PATH)

    unread = unread_count(DB_PATH)
    st.title(f"🔔 告警中心{'  🔴 ' + str(unread) if unread else ''}")
    st.caption("設定價格/RSI/策略訊號規則 → 手動掃描或等候首頁自動評估")

    # ── 手動掃描按鈕（頂部） ──
    col_scan, col_ack = st.columns([2, 1])
    with col_scan:
        if st.button("🔍 立即掃描全部規則", type="primary", use_container_width=True):
            from twquant.data.alert_worker import evaluate_all_rules
            with st.spinner("掃描中..."):
                n = evaluate_all_rules(DB_PATH)
            if n > 0:
                st.success(f"✅ 觸發 {n} 條告警，請查看下方紀錄")
                st.rerun()
            else:
                st.info("本次掃描無觸發。")
    with col_ack:
        if st.button("✅ 全部標為已讀", use_container_width=True):
            ack_all(DB_PATH)
            st.rerun()

    st.divider()

    # ── 主體：規則管理 | 觸發紀錄 ──
    col_rules, col_logs = st.columns([1, 1])

    # ── 左側：規則管理 ──
    with col_rules:
        st.subheader("📋 告警規則")

        with st.expander("➕ 新增規則", expanded=False):
            with st.form("add_rule_form", clear_on_submit=True):
                r_name    = st.text_input("規則名稱", placeholder="例：台積電 RSI 超買")
                r_stock   = st.text_input("股票代碼", value="2330")
                r_type    = st.selectbox("規則類型", list(_RULE_TYPES.keys()),
                                         format_func=lambda k: _RULE_TYPES[k])

                if r_type == "price_break":
                    pb_dir      = st.radio("方向", ["high", "low"], format_func=lambda x: "突破N日高點" if x == "high" else "跌破N日低點", horizontal=True)
                    pb_lookback = st.number_input("回看天數 N", 5, 250, 20)
                    params = {"direction": pb_dir, "lookback": pb_lookback}
                elif r_type == "rsi_threshold":
                    rsi_level = st.number_input("RSI 閾值", 10, 90, 70)
                    rsi_dir   = st.radio("穿越方向", ["above", "below"], format_func=lambda x: "向上穿越" if x == "above" else "向下穿越", horizontal=True)
                    params = {"level": rsi_level, "direction": rsi_dir}
                else:
                    strat_key = st.selectbox("策略", _STRAT_KEYS, format_func=lambda k: _STRAT_LABEL.get(k, k))
                    params = {"strategy_key": strat_key}

                submitted = st.form_submit_button("✅ 新增", type="primary", use_container_width=True)
                if submitted:
                    if not r_name.strip() or not r_stock.strip():
                        st.error("規則名稱與股票代碼不可空白")
                    else:
                        add_rule(r_name.strip(), r_stock.strip(), r_type, params, DB_PATH)
                        st.success("規則已新增！")
                        st.rerun()

        rules = list_rules(DB_PATH)
        if not rules:
            st.info("尚無規則，點擊「➕ 新增規則」建立第一條。")
        else:
            for rule in rules:
                status_icon = "🟢" if rule["enabled"] else "🔴"
                with st.container(border=True):
                    tc, tb1, tb2 = st.columns([4, 1, 1])
                    with tc:
                        st.markdown(f"{status_icon} **{rule['name']}** — {rule['stock_id']}  \n"
                                    f"<small>{_RULE_TYPES.get(rule['rule_type'], rule['rule_type'])} | {rule['created_at'][:10]}</small>",
                                    unsafe_allow_html=True)
                    with tb1:
                        if st.button("切換", key=f"tog_{rule['id']}", use_container_width=True):
                            toggle_rule(rule["id"], DB_PATH)
                            st.rerun()
                    with tb2:
                        if st.button("刪除", key=f"del_{rule['id']}", use_container_width=True):
                            delete_rule(rule["id"], DB_PATH)
                            st.rerun()

    # ── 右側：觸發紀錄 ──
    with col_logs:
        st.subheader(f"📡 觸發紀錄（未讀 {unread} 筆）")
        logs = list_logs(limit=50, db_path=DB_PATH)
        if not logs:
            st.info("尚無觸發紀錄。執行掃描後，觸發的告警會顯示在這裡。")
        else:
            for log in logs:
                read_icon = "⚪" if log["acknowledged"] else "🔴"
                with st.container(border=True):
                    lc, lb = st.columns([4, 1])
                    with lc:
                        st.markdown(
                            f"{read_icon} **{log['stock_id']}** — {log['rule_name']}  \n"
                            f"{log['message']}  \n"
                            f"<small>{log['triggered_at'][:16]}</small>",
                            unsafe_allow_html=True,
                        )
                    with lb:
                        if not log["acknowledged"]:
                            if st.button("已讀", key=f"ack_{log['id']}", use_container_width=True):
                                ack_log(log["id"], DB_PATH)
                                st.rerun()


if __name__ == "__main__":
    main()
