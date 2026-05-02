"""首次設定精靈：4 步驟引導完成基本設定"""

import json
from pathlib import Path

import streamlit as st

ONBOARDING_COMPLETE_FLAG = Path("data/.onboarding_complete")
CONFIG_PATH = Path("data/user_config.json")


def should_show_onboarding() -> bool:
    return not ONBOARDING_COMPLETE_FLAG.exists()


def render_onboarding_wizard() -> None:
    if "onboarding_step" not in st.session_state:
        st.session_state.onboarding_step = 1

    step = st.session_state.onboarding_step
    st.progress(step / 4, text=f"設定步驟 {step}/4")

    if step == 1:
        _render_step_welcome()
    elif step == 2:
        _render_step_trading()
    elif step == 3:
        _render_step_data()
    elif step == 4:
        _render_step_complete()


def _render_step_welcome() -> None:
    st.markdown("## 🎯 歡迎使用 TWQuant")
    st.markdown("台股量化交易回測平台")
    st.markdown("讓我們花 1 分鐘完成基本設定，之後可隨時在「設定」頁面修改。")
    if st.button("開始設定 →", type="primary", use_container_width=True):
        st.session_state.onboarding_step = 2
        st.rerun()


def _render_step_trading() -> None:
    st.markdown("## ⚙️ 交易設定")

    discount = st.slider(
        "券商手續費折扣",
        min_value=1, max_value=10, value=6,
        help="台股手續費公定價 0.1425%，多數券商提供 5-6 折優惠",
        format="%d 折",
    )
    st.session_state.onboarding_broker_discount = discount / 10

    init_cash = st.number_input(
        "初始回測資金（新台幣）",
        min_value=100_000, max_value=100_000_000,
        value=1_000_000, step=100_000,
    )
    st.session_state.onboarding_init_cash = int(init_cash)

    benchmark = st.radio(
        "預設基準指數",
        options=["0050", "TAIEX", "006208"],
        captions=[
            "元大台灣50 ETF（最常用）",
            "加權股價指數",
            "富邦台50 ETF（內扣費用較低）",
        ],
        index=0,
    )
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


def _render_step_data() -> None:
    import pandas as pd

    st.markdown("## 📊 數據設定")

    api_token = st.text_input(
        "FinMind API Token",
        type="password",
        help="至 finmindtrade.com 免費註冊取得，可提高 API 上限至 600 次/小時",
    )
    st.session_state.onboarding_api_token = api_token

    sync_mode = st.radio(
        "數據同步模式",
        options=["full", "watchlist_only", "none"],
        captions=[
            "全市場同步（建議，約 2000 檔股票，首次約 3-4 小時）",
            "僅同步關注清單中的股票",
            "暫不同步（使用範例數據）",
        ],
        index=0,
    )
    st.session_state.onboarding_sync_mode = sync_mode

    start_date = st.date_input(
        "歷史數據起始日",
        value=pd.Timestamp("2015-01-01"),
        min_value=pd.Timestamp("2000-01-01"),
        help="建議至少 5 年以上的歷史數據，回測結果才有統計意義",
    )
    st.session_state.onboarding_start_date = str(start_date)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← 上一步"):
            st.session_state.onboarding_step = 2
            st.rerun()
    with col2:
        if st.button("下一步 →", type="primary"):
            st.session_state.onboarding_step = 4
            st.rerun()


def _render_step_complete() -> None:
    st.markdown("## ✅ 設定完成！")
    st.markdown("### 你的設定")

    col1, col2 = st.columns(2)
    with col1:
        discount = st.session_state.get("onboarding_broker_discount", 0.6)
        st.metric("手續費折扣", f"{discount:.0%}")
        st.metric("基準指數", st.session_state.get("onboarding_benchmark", "0050"))
    with col2:
        init_cash = st.session_state.get("onboarding_init_cash", 1_000_000)
        st.metric("初始資金", f"${init_cash:,}")
        mode_label = {
            "full": "全市場",
            "watchlist_only": "關注清單",
            "none": "暫不同步",
        }.get(st.session_state.get("onboarding_sync_mode", "full"), "全市場")
        st.metric("同步模式", mode_label)

    if st.session_state.get("onboarding_sync_mode", "full") == "full":
        st.info("💡 首次全市場同步預計需要 3-4 小時，系統會在背景執行。你可以先用範例數據體驗功能。")

    if st.button("🚀 開始使用 TWQuant", type="primary", use_container_width=True):
        _save_onboarding_config()
        ONBOARDING_COMPLETE_FLAG.parent.mkdir(parents=True, exist_ok=True)
        ONBOARDING_COMPLETE_FLAG.touch()
        st.session_state.onboarding_step = 1
        st.rerun()


def _save_onboarding_config() -> None:
    config = {
        "broker_discount": st.session_state.get("onboarding_broker_discount", 0.6),
        "init_cash": st.session_state.get("onboarding_init_cash", 1_000_000),
        "benchmark": st.session_state.get("onboarding_benchmark", "0050"),
        "finmind_api_token": st.session_state.get("onboarding_api_token", ""),
        "sync_mode": st.session_state.get("onboarding_sync_mode", "full"),
        "history_start_date": st.session_state.get("onboarding_start_date", "2015-01-01"),
    }
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
