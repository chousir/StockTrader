"""首次設定精靈：4 步驟引導 + step 3 觸發資料抓取"""

import json
from pathlib import Path

import streamlit as st

ONBOARDING_COMPLETE_FLAG = Path("data/.onboarding_complete")
CONFIG_PATH = Path("data/user_config.json")
DB_PATH = "data/twquant.db"


def should_show_onboarding() -> bool:
    return not ONBOARDING_COMPLETE_FLAG.exists()


def render_onboarding_wizard() -> None:
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 1

    step = st.session_state.onboarding_step
    st.progress(step / 4, text=f"設定步驟 {step}/4")

    if step == 1:   _render_step_welcome()
    elif step == 2: _render_step_trading()
    elif step == 3: _render_step_data()
    elif step == 4: _render_step_complete()


def _render_step_welcome() -> None:
    st.markdown("## 🎯 歡迎使用 TWQuant")
    st.markdown("台股量化交易回測平台")
    st.markdown("讓我們花 1 分鐘完成基本設定，之後可隨時在「設定」頁面修改。")
    if st.button("開始設定 →", type="primary", use_container_width=True):
        st.session_state.onboarding_step = 2
        st.rerun()


def _render_step_trading() -> None:
    st.markdown("## ⚙️ 交易設定")

    discount = st.slider("券商手續費折扣", 1, 10, 6,
                         help="台股手續費公定價 0.1425%，多數券商提供 5-6 折優惠",
                         format="%d 折")
    st.session_state.onboarding_broker_discount = discount / 10

    init_cash = st.number_input("初始回測資金（新台幣）",
                                min_value=100_000, max_value=100_000_000,
                                value=1_000_000, step=100_000)
    st.session_state.onboarding_init_cash = int(init_cash)

    benchmark = st.radio("預設基準指數",
                         options=["0050", "TAIEX", "006208"],
                         captions=["元大台灣50 ETF（最常用）", "加權股價指數",
                                   "富邦台50 ETF（內扣費用較低）"],
                         index=0)
    st.session_state.onboarding_benchmark = benchmark

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 上一步"):
            st.session_state.onboarding_step = 1
            st.rerun()
    with col2:
        if st.button("下一步 →", type="primary"):
            st.session_state.onboarding_step = 3
            st.rerun()


def validate_finmind_token(token: str) -> tuple[bool, str]:
    """打 FinMind 一次小量請求驗證 token；空 token 也可呼叫（測試匿名額度）"""
    try:
        from twquant.data.providers.finmind import FinMindProvider
        p = FinMindProvider(token=token or "")
        df = p.fetch_daily("0050", "2024-01-01", "2024-01-31")
        if df is None or df.empty:
            return False, "回傳空資料 — token 可能無效"
        return True, f"OK，0050 測試取得 {len(df)} 筆"
    except Exception as e:
        return False, str(e)[:200]


def _compute_target_sids(mode: str, custom_sectors: list[str],
                         custom_codes: str) -> tuple[list[str], str]:
    """依範圍模式回傳 (sids, scope_desc)"""
    import sqlite3
    if mode == "⚡ 快速入門":
        from twquant.data.universe import ANALYST_UNIVERSE
        seen, sids = set(), []
        for stocks in ANALYST_UNIVERSE.values():
            for sid, _ in stocks:
                if sid not in seen:
                    seen.add(sid); sids.append(sid)
        return sids, f"快速入門：分析師宇宙 {len(sids)} 支"
    if mode == "🌐 完整":
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT stock_id FROM _universe WHERE stock_id GLOB '[0-9]*'"
            ).fetchall()
            conn.close()
            sids = sorted({r[0] for r in rows})
            return sids, f"完整全市場 {len(sids)} 支"
        except Exception:
            return [], "完整：_universe 表為空"
    # ⚙️ 自訂
    from twquant.data.universe import list_by_sector_db
    seen, sids = set(), []
    for sec in custom_sectors:
        for sid, _ in list_by_sector_db(sec):
            if sid not in seen:
                seen.add(sid); sids.append(sid)
    for line in (custom_codes or "").splitlines():
        c = line.strip()
        if c and c not in seen:
            seen.add(c); sids.append(c)
    sec_desc = "+".join(custom_sectors[:3]) + ("..." if len(custom_sectors) > 3 else "")
    return sids, f"自訂：{sec_desc} ({len(sids)} 支)"


def _render_step_data() -> None:
    import pandas as pd
    from twquant.data.universe import list_sectors

    st.markdown("## 📊 資料抓取設定")

    # ── 🔑 Token ──
    st.subheader("🔑 FinMind API Token")
    col_tok, col_val = st.columns([3, 1])
    api_token = col_tok.text_input(
        "Token（finmindtrade.com 免費註冊）", type="password",
        value=st.session_state.get("onboarding_api_token", ""),
        label_visibility="collapsed",
        placeholder="不填則用匿名（額度較低）",
    )
    if col_val.button("🔍 驗證", use_container_width=True):
        ok, msg = validate_finmind_token(api_token)
        st.session_state["_onboarding_token_valid"] = ok
        st.session_state["_onboarding_token_msg"] = msg
    if "_onboarding_token_valid" in st.session_state:
        if st.session_state["_onboarding_token_valid"]:
            st.success(f"✅ {st.session_state['_onboarding_token_msg']}")
        else:
            st.warning(f"⚠️ {st.session_state['_onboarding_token_msg']}（仍可用匿名模式繼續）")
    st.session_state.onboarding_api_token = api_token

    # ── 📦 範圍 ──
    st.subheader("📦 抓取範圍")
    mode = st.radio(
        "範圍",
        options=["⚡ 快速入門", "🌐 完整", "⚙️ 自訂"],
        captions=[
            "49 支精選宇宙 — 約 1-2 分鐘（推薦首次體驗）",
            "全市場 3000+ 支 — 約 1.5-2 小時",
            "多選板塊 + 自選代號 — 視範圍而定",
        ],
        index=0,
        label_visibility="collapsed",
    )

    custom_sectors: list[str] = []
    custom_codes = ""
    if mode == "⚙️ 自訂":
        custom_sectors = st.multiselect(
            "產業（多選）", list_sectors(),
            default=st.session_state.get("onboarding_custom_sectors",
                                         ["半導體業", "電子工業"]),
        )
        st.session_state.onboarding_custom_sectors = custom_sectors
        custom_codes = st.text_area(
            "或直接貼代號（每行一支）",
            placeholder="2330\n2317\n0050",
            value=st.session_state.get("onboarding_custom_codes", ""),
            height=100,
        )
        st.session_state.onboarding_custom_codes = custom_codes

    # ── 📅 起始日 ──
    start_date = st.date_input(
        "📅 歷史資料起始日",
        value=pd.Timestamp(st.session_state.get("onboarding_start_date", "2023-01-01")),
        min_value=pd.Timestamp("2000-01-01"),
        help="建議至少 3 年以上，回測才有統計意義；範圍越大抓取時間越長",
    )
    st.session_state.onboarding_start_date = str(start_date)

    # 預覽
    target_sids, scope_desc = _compute_target_sids(mode, custom_sectors, custom_codes)
    st.caption(f"📋 預計抓取：**{len(target_sids)} 支**｜範圍：{scope_desc}")

    # ── 動作按鈕 ──
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("← 上一步"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with c2:
        if st.button("💾 跳過抓取", help="進入空 DB，之後可在頁 01 手動補抓"):
            _save_onboarding_config()
            st.session_state["onboarding_job_id"] = None
            ONBOARDING_COMPLETE_FLAG.parent.mkdir(parents=True, exist_ok=True)
            ONBOARDING_COMPLETE_FLAG.touch()
            st.session_state.onboarding_step = 4
            st.rerun()
    with c3:
        if st.button("🚀 開始抓取", type="primary"):
            if not target_sids:
                st.error("目標股票清單為空，請選範圍或填代號")
            else:
                _save_onboarding_config()
                # 同步 token 至 user_config（讓 FinMindProvider 讀到）
                if api_token:
                    _persist_token(api_token)
                # 啟動背景 job
                from twquant.data.auto_sync import run_manual_job
                job_id = run_manual_job(
                    DB_PATH, target_sids, str(start_date),
                    scope_desc=scope_desc, job_type="onboarding",
                )
                st.session_state["onboarding_job_id"] = job_id
                ONBOARDING_COMPLETE_FLAG.parent.mkdir(parents=True, exist_ok=True)
                ONBOARDING_COMPLETE_FLAG.touch()
                st.session_state.onboarding_step = 4
                st.rerun()


def _render_step_complete() -> None:
    job_id = st.session_state.get("onboarding_job_id")
    st.markdown("## ✅ 設定完成！")

    col1, col2 = st.columns(2)
    with col1:
        discount = st.session_state.get("onboarding_broker_discount", 0.6)
        st.metric("手續費折扣", f"{discount:.0%}")
        st.metric("基準指數", st.session_state.get("onboarding_benchmark", "0050"))
    with col2:
        init_cash = st.session_state.get("onboarding_init_cash", 1_000_000)
        st.metric("初始資金", f"${init_cash:,}")
        st.metric("起始資料日", st.session_state.get("onboarding_start_date", "2023-01-01"))

    if job_id:
        st.divider()
        st.info(f"📡 資料抓取任務 #{job_id} 已在背景啟動 — 你可以進入 dashboard，"
                f"sidebar 底部會持續顯示進度。盤中每 5 分鐘、盤後每 60 分鐘自動增量補齊。")
        # 顯示目前進度（不阻擋）
        try:
            from twquant.data.sync_jobs import latest_running_job
            j = latest_running_job(DB_PATH)
            if j:
                pct = j["done"] / max(j["total"], 1)
                st.progress(pct, text=f"{j['done']}/{j['total']}（{j.get('current_sid') or '初始化中'}）")
        except Exception:
            pass
    else:
        st.divider()
        st.warning("ℹ️ 已跳過資料抓取。可在「頁 01 市場總覽」頂部資料中心手動補抓。")

    if st.button("🚀 進入 dashboard", type="primary", use_container_width=True):
        st.session_state.onboarding_step = 1
        st.rerun()


def _persist_token(token: str) -> None:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8")) if CONFIG_PATH.exists() else {}
    cfg["finmind_api_token"] = token
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_onboarding_config() -> None:
    config = {
        "broker_discount": st.session_state.get("onboarding_broker_discount", 0.6),
        "init_cash": st.session_state.get("onboarding_init_cash", 1_000_000),
        "benchmark": st.session_state.get("onboarding_benchmark", "0050"),
        "finmind_api_token": st.session_state.get("onboarding_api_token", ""),
        "history_start_date": st.session_state.get("onboarding_start_date", "2023-01-01"),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
