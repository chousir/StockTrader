"""Page 11：每日選股 — 訂閱策略 + 持久化掃描結果 + Discord 推播設定"""

import sys
sys.path.insert(0, "src")

import os
import streamlit as st

st.set_page_config(page_title="每日選股", page_icon="📅", layout="wide")

DB_PATH = "data/twquant.db"

_STRAT_KEYS = [
    "momentum_concentrate",
    "volume_breakout",
    "triple_ma_twist",
    "risk_adj_momentum",
    "donchian_breakout",
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
    from twquant.dashboard.components.global_sidebar import render_global_sidebar
    from twquant.data.daily_scans import (
        init_schema, list_subscriptions, set_subscriptions_bulk,
        get_scan, available_dates,
    )
    from twquant.data.universe import get_name, get_sector

    render_global_sidebar(show_stock=False, show_dates=False)
    init_schema(DB_PATH)

    st.title("📅 每日選股")
    st.caption("訂閱策略 → 每日盤後自動掃描 → 結果落地 + Discord 推播")

    # ── 頂部狀態列：webhook + 重跑 + 日期 ──
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    col_status, col_rerun, col_date = st.columns([3, 1, 2])

    with col_status:
        if webhook:
            st.success("✅ Discord Webhook 已設定（DISCORD_WEBHOOK_URL）")
        else:
            with st.expander("⚠️ Discord Webhook 未設定 — 點此查看設定方式", expanded=False):
                st.code(
                    "# 1. Discord 伺服器 → 頻道設定 → 整合 → 建立 Webhook → 複製 URL\n"
                    "# 2. 設環境變數後重啟 dashboard：\n"
                    "export DISCORD_WEBHOOK_URL='https://discord.com/api/webhooks/...'",
                    language="bash",
                )

    with col_rerun:
        if st.button("🔁 立即重跑", type="primary", use_container_width=True):
            from twquant.data.daily_scan_worker import run_daily_scan
            with st.spinner("掃描中（約 30-90 秒）..."):
                stats = run_daily_scan(DB_PATH)
            st.success(
                f"✅ {stats['scan_date']}：{stats['strategies']} 策略 / "
                f"{stats['picks']} 筆訊號" +
                (" / Discord 已推播" if stats["notified"] else "")
            )
            st.rerun()

    dates = available_dates(30, DB_PATH)
    with col_date:
        if dates:
            picked_date = st.selectbox("掃描日期", dates, index=0)
        else:
            picked_date = None
            st.caption("尚無掃描資料")

    st.divider()

    # ── 主體：左側訂閱 | 右側結果 ──
    col_sub, col_results = st.columns([1, 3])

    # 訂閱面板
    with col_sub:
        st.subheader("📋 策略訂閱")
        subs = {s["strategy_key"]: s["enabled"] for s in list_subscriptions(DB_PATH)}
        with st.form("sub_form"):
            choices: list[str] = []
            for key in _STRAT_KEYS:
                checked = st.checkbox(
                    _STRAT_LABEL[key],
                    value=subs.get(key, False),
                    key=f"sub_{key}",
                )
                if checked:
                    choices.append(key)
            saved = st.form_submit_button("💾 儲存訂閱", type="primary", use_container_width=True)
            if saved:
                set_subscriptions_bulk(choices, _STRAT_KEYS, DB_PATH)
                st.success(f"已儲存 {len(choices)} 個訂閱")
                st.rerun()
        st.caption(f"目前啟用：{len([k for k in subs if subs[k]])} / {len(_STRAT_KEYS)}")

    # 結果區
    with col_results:
        if picked_date is None:
            st.info("尚無掃描資料。請先在左側勾選策略 → 點頂部「🔁 立即重跑」。")
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
                                "代號":   sid,
                                "名稱":   get_name(sid),
                                "板塊":   get_sector(sid),
                                "收盤":   f"{r['close']:.1f}" if pd.notna(r["close"]) else "-",
                                "距MA60%": f"{r['ma60_dist']:+.1f}" if pd.notna(r["ma60_dist"]) else "-",
                                "RSI":    f"{r['rsi']:.0f}" if pd.notna(r["rsi"]) else "-",
                                "量比":   f"{r['vol_ratio']:.1f}" if pd.notna(r["vol_ratio"]) else "-",
                            })
                        st.dataframe(
                            pd.DataFrame(rows), use_container_width=True,
                            hide_index=True, height=min(40 + 35 * len(rows), 400),
                        )
                        # 跳轉按鈕（取前 8 檔）
                        n_jump = min(len(group), 8)
                        cols = st.columns(n_jump)
                        for i, (_, r) in enumerate(group.head(n_jump).iterrows()):
                            sid = r["stock_id"]
                            with cols[i]:
                                if st.button(f"📊 {sid}", key=f"jump_{key}_{sid}",
                                             use_container_width=True):
                                    st.session_state.update({
                                        "g_current_stock": sid, "current_stock": sid,
                                    })
                                    st.switch_page("pages/02_stock_analysis.py")


if __name__ == "__main__":
    main()
