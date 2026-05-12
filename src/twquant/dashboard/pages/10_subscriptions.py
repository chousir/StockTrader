"""Page 10：訂閱中心 — 個股告警 + 每日策略選股 + 觸發紀錄"""

import sys
sys.path.insert(0, "src")

import os
import streamlit as st

st.set_page_config(page_title="訂閱中心", page_icon="🔔", layout="wide")

DB_PATH = "data/twquant.db"

_RULE_TYPES = {
    "price_break":     "📈 突破N日高/低點",
    "rsi_threshold":   "📊 RSI 閾值穿越",
    "strategy_signal": "📡 策略進場訊號",
}
_STRAT_KEYS = [
    "momentum_concentrate", "volume_breakout", "triple_ma_twist",
    "risk_adj_momentum", "donchian_breakout",
]
_STRAT_LABEL = {
    "momentum_concentrate": "F｜動能精選 ★",
    "volume_breakout":      "H｜量價突破",
    "triple_ma_twist":      "L｜三線扭轉",
    "risk_adj_momentum":    "M｜RAM動能",
    "donchian_breakout":    "N｜唐奇安突破",
}


def main():
    import pandas as pd
    from twquant.data.alerts import (
        init_schema as alert_init, add_rule, list_rules, delete_rule,
        toggle_rule, list_logs, ack_log, ack_all, unread_count,
    )
    from twquant.data.daily_scans import (
        init_schema as scan_init, list_subscriptions, set_subscriptions_bulk,
        get_scan, available_dates,
    )
    from twquant.data.universe import get_name, get_sector
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    render_global_sidebar(show_stock=False, show_dates=False)
    alert_init(DB_PATH)
    scan_init(DB_PATH)

    unread = unread_count(DB_PATH)
    st.title(f"🔔 訂閱中心{'  🔴 ' + str(unread) if unread else ''}")
    st.caption("個股告警規則 + 策略訂閱 → 每日自動掃描 + Discord 推播")

    tab_alert, tab_picks, tab_log = st.tabs(["🔔 個股告警", "📅 每日選股", "📡 觸發紀錄"])

    # ──────────────── 個股告警 ────────────────
    with tab_alert:
        col_scan, col_ack = st.columns([2, 1])
        with col_scan:
            if st.button("🔍 立即掃描規則", type="primary", use_container_width=True):
                from twquant.data.alert_worker import evaluate_all_rules
                with st.spinner("掃描中..."):
                    n = evaluate_all_rules(DB_PATH)
                st.success(f"觸發 {n} 條告警" if n > 0 else "本次無觸發")
                st.rerun()
        with col_ack:
            if st.button("✅ 全部已讀", use_container_width=True):
                ack_all(DB_PATH)
                st.rerun()

        col_rules, col_logs = st.columns(2)
        with col_rules:
            st.subheader("📋 告警規則")
            with st.expander("➕ 新增規則", expanded=False):
                with st.form("add_rule_form", clear_on_submit=True):
                    r_name  = st.text_input("規則名稱", placeholder="例：台積電 RSI 超買")
                    r_stock = st.text_input("股票代碼", value="2330")
                    r_type  = st.selectbox("類型", list(_RULE_TYPES.keys()),
                                           format_func=lambda k: _RULE_TYPES[k])
                    if r_type == "price_break":
                        pb_dir = st.radio("方向", ["high", "low"],
                                          format_func=lambda x: "突破N日高" if x == "high" else "跌破N日低",
                                          horizontal=True)
                        pb_lb  = st.number_input("回看天數", 5, 250, 20)
                        params = {"direction": pb_dir, "lookback": pb_lb}
                    elif r_type == "rsi_threshold":
                        rsi_lv = st.number_input("RSI 閾值", 10, 90, 70)
                        rsi_dr = st.radio("穿越方向", ["above", "below"],
                                          format_func=lambda x: "向上穿" if x == "above" else "向下穿",
                                          horizontal=True)
                        params = {"level": rsi_lv, "direction": rsi_dr}
                    else:
                        sk = st.selectbox("策略", _STRAT_KEYS,
                                          format_func=lambda k: _STRAT_LABEL.get(k, k))
                        params = {"strategy_key": sk}
                    if st.form_submit_button("✅ 新增", type="primary", use_container_width=True):
                        if r_name.strip() and r_stock.strip():
                            add_rule(r_name.strip(), r_stock.strip(), r_type, params, DB_PATH)
                            st.success("已新增")
                            st.rerun()
                        else:
                            st.error("名稱與代碼不可空白")

            for rule in list_rules(DB_PATH):
                icon = "🟢" if rule["enabled"] else "🔴"
                with st.container(border=True):
                    tc, tb1, tb2 = st.columns([4, 1, 1])
                    tc.markdown(f"{icon} **{rule['name']}** — {rule['stock_id']}  \n"
                                f"<small>{_RULE_TYPES.get(rule['rule_type'], rule['rule_type'])}</small>",
                                unsafe_allow_html=True)
                    if tb1.button("切換", key=f"tog_{rule['id']}", use_container_width=True):
                        toggle_rule(rule["id"], DB_PATH); st.rerun()
                    if tb2.button("刪除", key=f"del_{rule['id']}", use_container_width=True):
                        delete_rule(rule["id"], DB_PATH); st.rerun()

        with col_logs:
            st.subheader(f"📡 告警紀錄（未讀 {unread}）")
            for log in list_logs(limit=30, db_path=DB_PATH):
                icon = "⚪" if log["acknowledged"] else "🔴"
                with st.container(border=True):
                    lc, lb = st.columns([4, 1])
                    lc.markdown(f"{icon} **{log['stock_id']}** — {log['rule_name']}  \n"
                                f"{log['message']}  \n"
                                f"<small>{log['triggered_at'][:16]}</small>",
                                unsafe_allow_html=True)
                    if not log["acknowledged"]:
                        if lb.button("已讀", key=f"ack_{log['id']}", use_container_width=True):
                            ack_log(log["id"], DB_PATH); st.rerun()

    # ──────────────── 每日選股 ────────────────
    with tab_picks:
        webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
        col_ws, col_rr, col_dt = st.columns([3, 1, 2])
        with col_ws:
            if webhook:
                st.success("✅ Discord Webhook 已設定")
            else:
                st.caption("⚠️ Discord Webhook 未設定（DISCORD_WEBHOOK_URL）")
        with col_rr:
            if st.button("🔁 立即重跑", type="primary", use_container_width=True):
                from twquant.data.daily_scan_worker import run_daily_scan
                with st.spinner("掃描中（約 30-90 秒）..."):
                    stats = run_daily_scan(DB_PATH)
                st.success(
                    f"✅ {stats['scan_date']}：{stats['strategies']} 策略 / "
                    f"{stats['picks']} 筆" +
                    (" / Discord 已推播" if stats["notified"] else "")
                )
                st.rerun()

        dates = available_dates(30, DB_PATH)
        with col_dt:
            picked_date = st.selectbox("掃描日期", dates, index=0) if dates else None
            if not dates:
                st.caption("尚無掃描資料")

        st.divider()
        col_sub, col_res = st.columns([1, 3])
        with col_sub:
            st.subheader("📋 策略訂閱")
            subs = {s["strategy_key"]: s["enabled"] for s in list_subscriptions(DB_PATH)}
            with st.form("sub_form"):
                choices: list[str] = []
                for key in _STRAT_KEYS:
                    if st.checkbox(_STRAT_LABEL[key], value=subs.get(key, False), key=f"sub_{key}"):
                        choices.append(key)
                if st.form_submit_button("💾 儲存訂閱", type="primary", use_container_width=True):
                    set_subscriptions_bulk(choices, _STRAT_KEYS, DB_PATH)
                    st.success(f"已儲存 {len(choices)} 個"); st.rerun()
            st.caption(f"啟用：{sum(subs.values())} / {len(_STRAT_KEYS)}")

        with col_res:
            if picked_date is None:
                st.info("尚無掃描資料，請先訂閱策略 → 點「🔁 立即重跑」")
            else:
                df = get_scan(picked_date, DB_PATH)
                if df.empty:
                    st.info(f"{picked_date} 無資料")
                else:
                    st.subheader(f"📡 {picked_date} 選股結果（共 {len(df)} 筆）")
                    for key, group in df.groupby("strategy_key", sort=False):
                        label = _STRAT_LABEL.get(key, key)
                        with st.expander(f"{label} — {len(group)} 檔", expanded=True):
                            rows = []
                            for _, r in group.iterrows():
                                sid = r["stock_id"]
                                rows.append({
                                    "代號": sid, "名稱": get_name(sid),
                                    "板塊": get_sector(sid),
                                    "收盤": f"{r['close']:.1f}" if pd.notna(r["close"]) else "-",
                                    "距MA60%": f"{r['ma60_dist']:+.1f}" if pd.notna(r["ma60_dist"]) else "-",
                                    "RSI": f"{r['rsi']:.0f}" if pd.notna(r["rsi"]) else "-",
                                    "量比": f"{r['vol_ratio']:.1f}" if pd.notna(r["vol_ratio"]) else "-",
                                })
                            st.dataframe(pd.DataFrame(rows), use_container_width=True,
                                         hide_index=True, height=min(40+35*len(rows), 400))
                            n_jump = min(len(group), 8)
                            cols = st.columns(n_jump)
                            for i, (_, r) in enumerate(group.head(n_jump).iterrows()):
                                sid = r["stock_id"]
                                if cols[i].button(f"📊 {sid}", key=f"jump_{key}_{sid}",
                                                  use_container_width=True):
                                    st.session_state.update({"g_current_stock": sid, "current_stock": sid})
                                    st.switch_page("pages/02_stock_analysis.py")

    # ──────────────── 觸發紀錄 ────────────────
    with tab_log:
        st.subheader("📋 近期觸發紀錄（告警 + 選股）")
        logs = list_logs(limit=50, db_path=DB_PATH)
        dates_scan = available_dates(7, DB_PATH)
        col_a, col_b = st.columns(2)
        with col_a:
            st.caption("🔔 個股告警")
            if logs:
                rows = [{"時間": l["triggered_at"][:16], "代號": l["stock_id"],
                         "規則": l["rule_name"], "訊息": l["message"],
                         "已讀": "✓" if l["acknowledged"] else "●"} for l in logs]
                st.dataframe(pd.DataFrame(rows), use_container_width=True,
                             hide_index=True, height=350)
            else:
                st.caption("無告警紀錄")
        with col_b:
            st.caption("📡 每日選股")
            if dates_scan:
                df_scan = get_scan(dates_scan[0], DB_PATH)
                if not df_scan.empty:
                    st.dataframe(
                        df_scan[["strategy_key", "stock_id", "close", "rsi", "vol_ratio"]].rename(
                            columns={"strategy_key": "策略", "stock_id": "代號",
                                     "close": "收盤", "rsi": "RSI", "vol_ratio": "量比"}
                        ),
                        use_container_width=True, hide_index=True, height=350,
                    )
                else:
                    st.caption(f"{dates_scan[0]} 無選股資料")
            else:
                st.caption("無選股記錄")


if __name__ == "__main__":
    main()
