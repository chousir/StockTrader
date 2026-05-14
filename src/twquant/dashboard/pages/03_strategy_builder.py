"""Page 3：兩階段選股漏斗 — 全市場 → 粗篩 → 5 策略精篩 → 候選清單"""

import sys
sys.path.insert(0, "src")

import math
import streamlit as st

st.set_page_config(page_title="兩階段選股漏斗", page_icon="🔻", layout="wide")

DB_PATH = "data/twquant.db"

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
_STRAT_SHORT = {
    "momentum_concentrate": "F", "volume_breakout": "H",
    "triple_ma_twist": "L", "risk_adj_momentum": "M",
    "donchian_breakout": "N",
}

# 一鍵模板：粗篩條件預設組合
_TEMPLATES = {
    "多頭趨勢（推薦）": dict(rsi_min=30, rsi_max=75, min_vol=1.0, min_ret20=0.0, max_dd=30.0),
    "保守":           dict(rsi_min=40, rsi_max=70, min_vol=1.2, min_ret20=0.0, max_dd=15.0),
    "激進動能":       dict(rsi_min=50, rsi_max=80, min_vol=1.5, min_ret20=10.0, max_dd=40.0),
}


@st.cache_data(ttl=900, show_spinner=False)
def _get_universe(source: str, sectors: tuple[str, ...],
                  exclude_etf: bool = True) -> list[str]:
    """依來源回傳股票代號清單；預設排除 ETF/ETN/權證，只留 4 碼純數字個股 (1xxx-9xxx)"""
    import re
    from twquant.data.storage import SQLiteStorage
    from twquant.data.universe import list_by_sector_db

    if source == "全市場":
        syms = SQLiteStorage(DB_PATH).list_symbols()
        sids = {s.replace("daily_price/", "") for s in syms if s.startswith("daily_price/")}
    elif source == "指定產業" and sectors:
        sids = set()
        for sec in sectors:
            for sid, _ in list_by_sector_db(sec):
                sids.add(sid)
    else:
        return []

    if exclude_etf:
        # 只留 4 碼純數字、首位 1-9 的個股（排除 ETF 00xx、ETN 02xx、權證 01xx 等）
        sids = {s for s in sids if re.match(r"^[1-9]\d{3}$", s)}
    return sorted(sids)


def _compute_features(df) -> dict:
    """單股技術特徵（重用 indicators/basic.py）"""
    import numpy as np
    import pandas as pd
    from twquant.indicators.basic import compute_ma, compute_rsi
    close = df["close"].astype(float)
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    volume = df["volume"].astype(float)
    n = len(df)
    if n < 60:
        return {}
    ma20 = compute_ma(close, 20).iloc[-1]
    ma60 = compute_ma(close, 60).iloc[-1]
    rsi14 = compute_rsi(close, 14).iloc[-1]
    vol5 = volume.iloc[-5:].mean()
    vol20 = volume.iloc[-20:].mean()
    vol_ratio = float(vol5 / vol20) if vol20 > 0 else 1.0
    ret20 = float(close.iloc[-1] / close.iloc[-21] - 1) if n >= 21 else 0.0
    high60 = close.iloc[-60:].max()
    dd_from_high = float(close.iloc[-1] / high60 - 1) if high60 > 0 else 0.0
    return {
        "close": float(close.iloc[-1]),
        "ma20": float(ma20) if pd.notna(ma20) else float("nan"),
        "ma60": float(ma60) if pd.notna(ma60) else float("nan"),
        "rsi14": float(rsi14) if pd.notna(rsi14) else float("nan"),
        "vol_ratio": vol_ratio,
        "ret20": ret20,
        "dd_from_high": dd_from_high,
    }


def _check_strategies(df, strat_keys: list[str], lookback_days: int = 5) -> list[str]:
    """回傳近 N 日內觸發進場的策略 key"""
    from twquant.strategy.registry import get_strategy
    if len(df) < 120:
        return []
    fired = []
    for key in strat_keys:
        try:
            entries, _ = get_strategy(key).generate_signals(df)
            tail = entries[-lookback_days:] if hasattr(entries, "__len__") and len(entries) >= lookback_days else entries
            if hasattr(tail, "any") and bool(tail.any()):
                fired.append(key)
            elif any(bool(x) for x in tail):
                fired.append(key)
        except Exception:
            pass
    return fired


@st.cache_data(ttl=900, show_spinner=False)
def _run_funnel(sids: tuple[str, ...], rsi_min: int, rsi_max: int,
                min_vol: float, min_ret20: float, max_dd: float,
                strat_keys: tuple[str, ...], lookback: int,
                skip_stage1: bool = False) -> tuple[list[dict], int]:
    """兩階段漏斗：粗篩 + 精篩，回傳 (通過清單, 粗篩通過數)

    skip_stage1=True → 純訊號雷達模式（略過粗篩，直接對來源股池跑 5 策略訊號）
    """
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    from twquant.data.universe import get_name, get_sector

    # 0050 基準
    storage = SQLiteStorage(DB_PATH)
    df_bench = storage.load("daily_price/0050")
    if not df_bench.empty:
        bench_close = df_bench["close"].astype(float)
        bench_first = bench_close.iloc[0]
        bench_last = bench_close.iloc[-1]
        bench_ret_total = bench_last / bench_first
    else:
        bench_ret_total = 1.0

    stage1_pass: list[dict] = []
    for sid in sids:
        df = storage.load(f"daily_price/{sid}")
        if df.empty or len(df) < 60:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        f = _compute_features(df)
        if not f or any(math.isnan(f.get(k, float("nan"))) for k in ("ma60", "rsi14")):
            continue
        # 粗篩條件（雷達模式跳過）
        if not skip_stage1:
            if not (
                f["close"] > f["ma60"]
                and f["vol_ratio"] >= min_vol
                and rsi_min <= f["rsi14"] <= rsi_max
                and f["ret20"] >= min_ret20 / 100
                and f["dd_from_high"] >= -max_dd / 100
            ):
                continue
        # RS vs 0050（自資料開始日起的累積比）
        if not df_bench.empty:
            stock_ret_total = float(df["close"].iloc[-1] / df["close"].iloc[0])
            rs = stock_ret_total / bench_ret_total
        else:
            rs = 1.0
        stage1_pass.append({"sid": sid, "df": df, "rs": rs, **f})

    n_stage1 = len(stage1_pass)
    if n_stage1 == 0:
        return [], 0

    # 階段 2：策略觸發
    stage2: list[dict] = []
    for s in stage1_pass:
        fired = _check_strategies(s["df"], list(strat_keys), lookback)
        if fired:
            stage2.append({
                "代號": s["sid"],
                "名稱": get_name(s["sid"]),
                "產業": get_sector(s["sid"]),
                "收盤": round(s["close"], 2),
                "RSI": round(s["rsi14"], 1),
                "量比": round(s["vol_ratio"], 2),
                "20d漲%": round(s["ret20"] * 100, 1),
                "距60d高%": round(s["dd_from_high"] * 100, 1),
                "RS": round(s["rs"], 2),
                "共振策略": "+".join(_STRAT_SHORT[k] for k in fired),
                "_fired_keys": fired,
                "分": len(fired),
            })
    return stage2, n_stage1


def main():
    import pandas as pd
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.components.global_sidebar import render_global_sidebar
    from twquant.data.universe import list_sectors

    register_twquant_dark_template()
    render_global_sidebar(show_stock=False, show_dates=False)

    with st.sidebar:
        # ── 📂 載入 preset（先處理，會 rerun） ──
        from twquant.data.funnel_presets import save_preset, list_presets, load_preset, delete_preset
        with st.expander("📂 載入條件 Preset", expanded=False):
            presets = list_presets()
            names = [p["name"] for p in presets]
            chosen = st.selectbox("選擇", ["(不載入)"] + names, key="p03_load_pick")
            if chosen != "(不載入)" and st.session_state.get("_p03_loaded") != chosen:
                loaded = load_preset(chosen)
                if loaded:
                    for k, v in loaded.items():
                        st.session_state[f"p03_pst_{k}"] = v
                    st.session_state["_p03_loaded"] = chosen
                    st.rerun()
            if chosen != "(不載入)" and st.button("🗑️ 刪除此 preset", use_container_width=True):
                delete_preset(chosen)
                st.session_state.pop("_p03_loaded", None)
                st.rerun()

        # 取出已載入的 preset 值（若有）
        _pst = {k.replace("p03_pst_", ""): v for k, v in st.session_state.items()
                if k.startswith("p03_pst_")}

        st.header("🎯 掃描模式")
        scan_mode = st.radio(
            "模式",
            ["🔻 精選候選股（先過濾再看訊號）", "📡 全部訊號（不過濾，看所有命中）"],
            index=0 if _pst.get("scan_mode", "漏斗") == "漏斗" else 1,
            label_visibility="collapsed",
            help="精選：粗篩 4 條件 → 5 策略；全部訊號：直接跑 5 策略，不過濾",
        )
        radar_mode = scan_mode.startswith("📡")

        st.divider()
        st.header("🔍 選股來源")
        source = st.radio("來源", ["全市場", "指定產業"], horizontal=True,
                          index=0 if _pst.get("source", "全市場") == "全市場" else 1)
        sectors = ()
        if source == "指定產業":
            sectors = tuple(st.multiselect("產業（可多選）", list_sectors(),
                                            default=_pst.get("sectors") or ["半導體業", "電子工業"]))
        exclude_etf = st.checkbox(
            "☑️ 只看個股（排除 ETF / ETN / 權證）",
            value=bool(_pst.get("exclude_etf", True)),
            help="預設只看 4 碼純數字個股（1xxx-9xxx）；取消則納入 ETF/ETN/權證",
        )

        # 粗篩條件區（雷達模式下隱藏）
        if not radar_mode:
            st.divider()
            st.header("📊 階段 1：粗篩條件")
            tmpl = st.selectbox("一鍵模板", list(_TEMPLATES.keys()))
            t = _TEMPLATES[tmpl]
            with st.expander("微調條件", expanded=False):
                rsi_range = st.slider("RSI(14) 區間", 0, 100,
                                      tuple(_pst.get("rsi_range") or (t["rsi_min"], t["rsi_max"])))
                min_vol = st.slider("最低量比（vol5/vol20）", 0.5, 3.0,
                                    float(_pst.get("min_vol", t["min_vol"])), 0.1)
                min_ret20 = st.slider("最低 20 日漲幅 %", -10.0, 30.0,
                                      float(_pst.get("min_ret20", t["min_ret20"])), 1.0)
                max_dd = st.slider("距 60 日高點最大跌幅 %", 0.0, 50.0,
                                   float(_pst.get("max_dd", t["max_dd"])), 1.0)
            st.caption("固定條件：Close > MA60（趨勢向上）")
        else:
            rsi_range = (0, 100)
            min_vol, min_ret20, max_dd = 0.0, -100.0, 100.0

        st.divider()
        st.header("🎯 階段 2：精篩策略" if not radar_mode else "🎯 策略訊號")
        strat_keys = st.multiselect(
            "策略（可多選）", _STRAT_KEYS,
            default=_pst.get("strat_keys") or _STRAT_KEYS,
            format_func=lambda k: _STRAT_LABEL.get(k, k),
        )
        lookback = st.slider("回看近 N 日內訊號觸發", 1, 10,
                             int(_pst.get("lookback", 5)))
        min_score = st.slider("最低共振分數（命中策略數）", 0, 5,
                              int(_pst.get("min_score", 1)))

        run_btn = st.button(
            "🚀 開始掃描",
            type="primary", use_container_width=True,
        )

        # ── 💾 儲存目前條件為 preset ──
        st.divider()
        with st.expander("💾 儲存目前條件"):
            save_name = st.text_input("preset 名稱", placeholder="如：每日多頭",
                                       key="p03_save_name")
            if st.button("💾 儲存", use_container_width=True,
                         key="p03_save_btn") and save_name:
                save_preset(save_name, {
                    "scan_mode": "雷達" if radar_mode else "漏斗",
                    "source": source, "sectors": list(sectors),
                    "exclude_etf": bool(exclude_etf),
                    "rsi_range": list(rsi_range), "min_vol": float(min_vol),
                    "min_ret20": float(min_ret20), "max_dd": float(max_dd),
                    "strat_keys": list(strat_keys), "lookback": int(lookback),
                    "min_score": int(min_score),
                })
                st.success(f"已儲存：{save_name}")

    # 主區標題
    if radar_mode:
        st.title("📡 全部訊號掃描")
        st.caption("直接掃描指定股池近 N 日的 5 策略訊號（不過濾），看所有命中｜快取 15 分鐘")
    else:
        st.title("🔻 精選候選股")
        st.caption("全市場 / 產業 → 粗篩（4 條件過濾）→ 5 策略精篩 → 候選清單｜快取 15 分鐘")

    if not run_btn:
        st.info("在左側設定條件後，點擊「🚀 開始掃描」")
        with st.expander("📖 兩種模式說明", expanded=True):
            st.markdown("""
**🔻 精選候選股（先過濾再看訊號）— 推薦**
- 第一步用 4 個技術門檻過濾掉爛標的：
  - Close > MA60（趨勢向上）
  - 量比 ≥ 設定值（量未萎縮）
  - RSI 在區間內（避超賣 / 超買陷阱）
  - 20 日漲幅 ≥ 設定值（動能存在）
  - 距 60 日高點跌幅 ≤ 設定值（不買破底股）
- 第二步對倖存股跑 5 策略，輸出命中標籤（如 F+H+L）

**📡 全部訊號（不過濾，看所有命中）**
- 跳過粗篩，直接對所有股票跑 5 策略
- 適合：想看「今天哪些股觸發訊號」全景，不在意品質
- 通常結果較雜，需自己挑

**策略：** F｜動能精選 / H｜量價突破 / L｜三線扭轉 / M｜RAM 動能 / N｜唐奇安突破
**共振分 ≥ 2 視為強訊號，≥ 3 視為高品質**
""")
        return

    if not strat_keys:
        st.warning("請至少選擇一個策略")
        return

    with st.spinner("掃描中…全市場約 30–60 秒、單一產業約 5–10 秒"):
        sids = _get_universe(source, sectors, exclude_etf=exclude_etf)
        if not sids:
            st.warning("無股票符合來源條件")
            return
        results, n_stage1 = _run_funnel(
            tuple(sids), rsi_range[0], rsi_range[1],
            float(min_vol), float(min_ret20), float(max_dd),
            tuple(strat_keys), int(lookback),
            skip_stage1=radar_mode,
        )

    # ── 漏斗統計 ──
    n_source = len(sids)
    n_stage2 = len(results)
    n_resonance = sum(1 for r in results if r["分"] >= 2)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("📥 來源", f"{n_source} 支")
    if radar_mode:
        c2.metric("📡 全部掃描", f"{n_stage1} 支", "不過濾", delta_color="off")
    else:
        c2.metric("📊 粗篩通過", f"{n_stage1} 支",
                  delta=f"{n_stage1-n_source}" if n_source else None,
                  delta_color="off")
    c3.metric("🎯 訊號觸發" if radar_mode else "🎯 精篩通過", f"{n_stage2} 支",
              delta=f"{n_stage2-n_stage1}" if n_stage1 else None,
              delta_color="off")
    c4.metric("⚡ 共振 ≥ 2", f"{n_resonance} 支")

    if not results:
        st.warning("無候選股。建議放寬條件或更換一鍵模板。")
        return

    # 過濾共振分
    df_res = pd.DataFrame(results)
    df_show = df_res[df_res["分"] >= min_score].copy().sort_values(
        ["分", "20d漲%"], ascending=[False, False]
    ).reset_index(drop=True)

    st.divider()
    st.subheader(f"📋 候選清單（{len(df_show)} 支，分數 ≥ {min_score}）")

    # ── 表格 + 行內操作 ──
    display_cols = ["代號", "名稱", "產業", "收盤", "RSI", "20d漲%", "距60d高%",
                    "量比", "RS", "共振策略", "分"]
    st.dataframe(df_show[display_cols], use_container_width=True, hide_index=True, height=480)

    # ── 一鍵動作：加籃 / 跳頁 02 / 跳頁 06 ──
    st.divider()
    st.subheader("⚡ 一鍵動作")
    col_act1, col_act2, col_act3 = st.columns([2, 2, 2])
    with col_act1:
        from twquant.data.basket import add_to_basket, get_basket
        top_n = st.slider("選前 N 支加入交易籃", 1, min(len(df_show), 20),
                          min(5, len(df_show)))
        if st.button("🛒 加入交易籃", use_container_width=True):
            already = set(get_basket())
            added = 0
            for sid in df_show["代號"].head(top_n).tolist():
                if sid not in already:
                    add_to_basket(sid)
                    added += 1
            st.success(f"已加入 {added} 支（籃內共 {len(get_basket())} 支）")

    with col_act2:
        selected_for_02 = st.selectbox("跳頁 02 個股分析", df_show["代號"].tolist(),
                                       format_func=lambda s: f"{s} {df_show.set_index('代號').loc[s, '名稱']}")
        if st.button("📈 跳頁 02", use_container_width=True):
            st.session_state["g_current_stock"] = selected_for_02
            st.session_state["current_stock"] = selected_for_02
            st.switch_page("pages/02_stock_analysis.py")

    with col_act3:
        selected_for_06 = st.selectbox("跳頁 06 五策略對照",
                                       df_show["代號"].tolist(),
                                       format_func=lambda s: f"{s} {df_show.set_index('代號').loc[s, '名稱']}",
                                       key="sel_06")
        if st.button("🆚 跳頁 06", use_container_width=True):
            row = df_show.set_index("代號").loc[selected_for_06]
            fired_keys = next((r["_fired_keys"] for r in results
                              if r["代號"] == selected_for_06), [])
            st.session_state["g_current_stock"] = selected_for_06
            st.session_state["current_stock"] = selected_for_06
            if fired_keys:
                st.session_state["g_selected_strategy"] = fired_keys[0]
            st.switch_page("pages/06_vs_benchmark.py")

    # ── CSV 下載 ──
    csv = df_show[display_cols].to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 下載候選 CSV", csv, "funnel_picks.csv", "text/csv")

    # ── 雷達模式專屬：訊號分布視覺化 ──
    if radar_mode and len(df_show) > 0:
        import plotly.graph_objects as go
        st.divider()
        with st.expander("📊 訊號分布視覺化", expanded=False):
            col_bar, col_sc = st.columns([1, 2])
            with col_bar:
                strat_counts: dict[str, int] = {}
                for r in results:
                    for k in r["_fired_keys"]:
                        strat_counts[_STRAT_LABEL[k]] = strat_counts.get(_STRAT_LABEL[k], 0) + 1
                if strat_counts:
                    fig_bar = go.Figure(go.Bar(
                        x=list(strat_counts.values()), y=list(strat_counts.keys()),
                        orientation="h", text=list(strat_counts.values()),
                        textposition="outside",
                    ))
                    fig_bar.update_layout(height=260, margin=dict(l=20, r=20, t=20, b=20),
                                          xaxis_title="觸發股數", yaxis_title="")
                    st.plotly_chart(fig_bar, use_container_width=True)
            with col_sc:
                fig_sc = go.Figure(go.Scatter(
                    x=df_show["距60d高%"], y=df_show["RSI"], mode="markers+text",
                    text=df_show["代號"], textposition="top center", textfont=dict(size=9),
                    marker=dict(size=df_show["分"] * 4 + 6,
                                color=df_show["20d漲%"], colorscale="RdYlGn",
                                cmid=0, line=dict(width=1, color="white")),
                ))
                fig_sc.add_hline(y=50, line_color="#4B5563", line_dash="dot", line_width=1)
                fig_sc.add_vline(x=-10, line_color="#4B5563", line_dash="dot", line_width=1)
                fig_sc.update_layout(
                    height=300, hovermode="closest",
                    xaxis_title="距 60 日高 %（負=遠離高點）",
                    yaxis_title="RSI(14)",
                    margin=dict(l=50, r=20, t=20, b=40),
                )
                st.plotly_chart(fig_sc, use_container_width=True)


if __name__ == "__main__":
    main()
