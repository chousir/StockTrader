"""Page 6：策略覆驗中心 — 5 策略並排 / 單策略快測 / 全宇宙 Alpha 掃描 三合一"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略覆驗中心", page_icon="⚔️", layout="wide")

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
_LABEL_TO_KEY = {v: k for k, v in _STRAT_LABEL.items()}
_STRAT_COLOR = {
    "0050 持有(基準)": "#94A3B8",
    "F｜動能精選 ★":  "#FFD700",
    "H｜量價突破":     "#F97316",
    "L｜三線扭轉":     "#34D399",
    "M｜RAM動能":      "#60A5FA",
    "N｜唐奇安突破":   "#FB7185",
}
_STRAT_DESC = {
    "momentum_concentrate": "ret₂₀>5% + Close>MA60 進場；Close<MA60×0.97 出場。台達電近3年+369%，Sharpe 1.66。",
    "volume_breakout":      "Close>20日高點 + 量比>1.5x + Close>MA60 + RSI<76。台達電 Sharpe 1.81（最高）。",
    "triple_ma_twist":      "MA5/20/60 剛成多頭排列第一天 + RSI<72。台達電+258%，超額+111%。",
    "risk_adj_momentum":    "RAM=ret₂₀/(σ₂₀×√20)>0.7 + MA60>MA120。南亞科超額+285%（最高）。",
    "donchian_breakout":    "Close>DC_upper(20) + 量比>1.2x + Close>MA60 + RSI<76。台達電超額+201%。",
}


# ─── 共用：載入價量 ─────────────────────────────────
@st.cache_data(ttl=1800)
def _load_from_db(sid: str, start: str, end: str, use_adj: bool = False):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    ns = f"daily_adj/{sid}" if use_adj else f"daily_price/{sid}"
    df = storage.load(ns, start_date=start, end_date=end)
    if df.empty and use_adj:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def _monthly_heatmap(equity_curve: dict):
    import pandas as pd
    import plotly.graph_objects as go
    equity = pd.Series(equity_curve)
    equity.index = pd.to_datetime(equity.index)
    monthly = equity.resample("ME").last().pct_change().dropna() * 100
    years = sorted(monthly.index.year.unique())
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    z = []
    for yr in years:
        row = []
        for mo in range(1, 13):
            vals = monthly[(monthly.index.year == yr) & (monthly.index.month == mo)]
            row.append(round(float(vals.iloc[0]), 2) if len(vals) > 0 else None)
        z.append(row)
    text = [[f"{v:.1f}%" if v is not None else "" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=month_names, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, "#EF4444"], [0.5, "#1F2937"], [1, "#22C55E"]],
        zmid=0, hoverongaps=False,
    ))
    fig.update_layout(height=max(180, len(years)*38+60), margin=dict(l=60, r=20, t=20, b=20))
    return fig


# ─── 模式 1：5 策略並排對照 ─────────────────────────
@st.cache_data(ttl=1800)
def run_comparison(stock_id: str, start: str, end: str, selected_keys: tuple,
                   use_adj: bool = False):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.strategy.registry import get_strategy

    df = _load_from_db(stock_id, start, end, use_adj)
    df_bench = _load_from_db("0050", start, end)
    if df.empty or len(df) < 60 or df_bench.empty:
        return None
    price = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), dtype=float)
    price_bench = pd.Series(df_bench["close"].values, index=pd.to_datetime(df_bench["date"]), dtype=float)
    results = {}
    n = len(price_bench)
    bh_entries = np.zeros(n, dtype=bool); bh_entries[0] = True
    bh_exits = np.zeros(n, dtype=bool); bh_exits[-1] = True
    results["0050 持有(基準)"] = TWSEBacktestEngine().run(price_bench, bh_entries, bh_exits, init_cash=1_000_000)
    for key in selected_keys:
        label = _STRAT_LABEL.get(key, key)
        try:
            entries, exits = get_strategy(key).generate_signals(df)
            if entries.sum() == 0:
                continue
            results[label] = TWSEBacktestEngine().run(price, entries, exits, init_cash=1_000_000)
        except Exception:
            pass
    return results, df, df_bench


# ─── 模式 2：單策略快測（含 0050 + 月度熱力圖） ─────
@st.cache_data(ttl=1800)
def run_single(stock_id: str, start: str, end: str, strategy_key: str,
               use_adj: bool = False):
    import pandas as pd
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.backtest.report import generate_report
    from twquant.strategy.registry import get_strategy

    df = _load_from_db(stock_id, start, end, use_adj)
    if df.empty or len(df) < 60:
        return None
    strategy = get_strategy(strategy_key)
    entries, exits = strategy.generate_signals(df)
    price = pd.Series(df.set_index("date")["close"], dtype=float)
    metrics = TWSEBacktestEngine().run(price, entries, exits)
    return generate_report(metrics, _STRAT_LABEL.get(strategy_key, strategy_key),
                           "基準", start_date=start, end_date=end), df


# ─── 模式 3：全宇宙 Alpha 掃描 ─────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_alpha_scan(stock_list: tuple, start: str, end: str,
                   strat_keys: tuple, min_trades: int = 3):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.strategy.registry import get_strategy
    from twquant.data.universe import get_name, get_sector

    storage = SQLiteStorage(DB_PATH)
    df_bench = storage.load("daily_price/0050", start_date=start, end_date=end)
    bench_ret = 0.0
    if not df_bench.empty:
        p0 = df_bench["close"].astype(float)
        bench_ret = float(p0.iloc[-1] / p0.iloc[0] - 1)

    rows = []
    for sid in stock_list:
        sid = sid.split(":")[0] if ":" in sid else sid
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if df.empty or len(df) < 120:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        price_s = pd.Series(df["close"].astype(float).values, index=df["date"])
        for key in strat_keys:
            try:
                entries, exits = get_strategy(key).generate_signals(df)
                if int(entries.sum()) < min_trades:
                    continue
                m = TWSEBacktestEngine().run(price_s, entries, exits, init_cash=1_000_000)
                rows.append({
                    "代號": sid, "名稱": get_name(sid), "板塊": get_sector(sid),
                    "策略": _STRAT_LABEL.get(key, key),
                    "總報酬": m["total_return"], "超額α": m["total_return"] - bench_ret,
                    "Sharpe": m["sharpe_ratio"], "最大回撤": m["max_drawdown"],
                    "勝率": m["win_rate"], "交易次數": int(entries.sum()),
                })
            except Exception:
                pass
    return sorted(rows, key=lambda r: -(r["Sharpe"] if r["Sharpe"] == r["Sharpe"] else -99))


# ─── UI 渲染 ───────────────────────────────────────
def _render_compare(stock_id, start, end, selected, use_adj):
    import pandas as pd
    import plotly.graph_objects as go

    with st.spinner("回測中..."):
        out = run_comparison(stock_id, str(start), str(end), tuple(selected), use_adj)
    if out is None:
        st.error(f"無法載入 {stock_id} 或 0050 資料，請先執行種子腳本入庫。")
        return
    all_results, df, df_bench = out

    st.subheader("📊 績效指標對照")
    rows = []
    for name, m in all_results.items():
        rows.append({
            "策略": name, "總報酬": f"{m['total_return']:.1%}",
            "最大回撤": f"{m['max_drawdown']:.1%}",
            "Sharpe": f"{m['sharpe_ratio']:.2f}",
            "Sortino": f"{m['sortino_ratio']:.2f}",
            "Calmar": f"{m['calmar_ratio']:.2f}",
            "勝率": f"{m['win_rate']:.1%}" if not pd.isna(m['win_rate']) else "N/A",
            "交易次數": m["total_trades"],
            "最終淨值": f"${m['final_value']:,.0f}",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader(f"📈 資金曲線（{stock_id} vs 0050，初始 $1,000,000）")
    fig_eq = go.Figure()
    for name, m in all_results.items():
        equity = pd.Series(m["equity_curve"])
        equity.index = pd.to_datetime(equity.index)
        is_bench = "基準" in name
        fig_eq.add_trace(go.Scatter(
            x=equity.index, y=equity.values, name=name,
            line=dict(color=_STRAT_COLOR.get(name, "#A855F7"),
                      width=3 if is_bench or "★" in name else 1.8,
                      dash="dash" if is_bench else "solid"),
        ))
    fig_eq.update_layout(height=480, margin=dict(l=40, r=20, t=20, b=20),
                         hovermode="x unified", xaxis_title="日期", yaxis_title="資產淨值（元）",
                         legend=dict(orientation="h", y=-0.18))
    st.plotly_chart(fig_eq, use_container_width=True)

    bench_return = all_results.get("0050 持有(基準)", {}).get("total_return", 0)
    non_bench = {k: v for k, v in all_results.items() if "基準" not in k}
    if non_bench:
        st.divider()
        st.subheader("🏆 超額報酬（相對 0050）")
        cols = st.columns(len(non_bench))
        for i, (name, m) in enumerate(non_bench.items()):
            cols[i].metric(name[:12], f"{m['total_return']:.1%}",
                           f"α {m['total_return']-bench_return:+.1%}")

    best_name = max(non_bench, key=lambda k: non_bench[k]["total_return"], default=None)
    if best_name:
        st.divider()
        st.subheader(f"📅 月度報酬熱力圖（{best_name}）")
        st.plotly_chart(_monthly_heatmap(non_bench[best_name]["equity_curve"]),
                        use_container_width=True)
        trades = non_bench[best_name].get("trades", [])
        if trades:
            st.subheader("📋 交易明細（最近 20 筆）")
            t_df = pd.DataFrame(trades).tail(20)
            if "報酬率" in t_df.columns:
                st.dataframe(t_df.style.format({"報酬率": "{:.2%}"}), use_container_width=True)
            else:
                st.dataframe(t_df, use_container_width=True)


def _render_single(stock_id, start, end, strat_key, use_adj):
    import pandas as pd
    import plotly.graph_objects as go
    with st.spinner("回測執行中..."):
        out = run_single(stock_id, str(start), str(end), strat_key, use_adj)
    if out is None:
        st.error(f"無法載入 {stock_id} 資料")
        return
    report, df = out

    st.markdown(f"### {_STRAT_LABEL.get(strat_key, strat_key)} | {stock_id}")
    st.caption(f"回測區間：{start} ~ {end} | 共 {len(df)} 個交易日")

    # 資金曲線 + 0050 基準
    with st.container(border=True):
        st.subheader("📈 資金曲線（含 0050 基準）")
        from twquant.dashboard.styles.theme import TWStockColors
        equity = pd.Series(report["equity_curve"])
        equity.index = pd.to_datetime(equity.index)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=equity.index, y=equity.values, name="策略",
                                 line=dict(color=TWStockColors.EQUITY_CURVE, width=2),
                                 fill="tozeroy", fillcolor="rgba(0,212,170,0.1)"))
        try:
            df_bench = _load_from_db("0050", str(start), str(end))
            if not df_bench.empty:
                init_cash = report.get("final_value", 1_000_000) / (1 + report.get("total_return", 0))
                bench_close = df_bench["close"].astype(float)
                bench_eq = init_cash * bench_close / bench_close.iloc[0]
                fig.add_trace(go.Scatter(x=df_bench["date"], y=bench_eq.values,
                                         name="0050 持有", line=dict(color="#94A3B8", width=1.5, dash="dash")))
                bench_ret = float(bench_eq.iloc[-1] / bench_eq.iloc[0] - 1)
                alpha = report.get("total_return", 0) - bench_ret
                fig.update_layout(height=450, hovermode="x unified",
                                  margin=dict(l=40, r=20, t=30, b=20))
                st.plotly_chart(fig, use_container_width=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("策略報酬", f"{report.get('total_return', 0):.1%}")
                c2.metric("0050 基準", f"{bench_ret:.1%}")
                c3.metric("超額 α", f"{alpha:+.1%}")
            else:
                st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.plotly_chart(fig, use_container_width=True)

    st.subheader("📊 績效指標")
    from twquant.dashboard.components.metrics_card import render_metrics_cards
    render_metrics_cards(report)

    st.divider()
    col_t, col_m = st.columns(2)
    with col_t:
        with st.container(border=True):
            st.subheader("交易明細")
            if report.get("trades"):
                t_df = pd.DataFrame(report["trades"])
                if "報酬率" in t_df.columns:
                    st.dataframe(t_df.style.format({"報酬率": "{:.2%}"}), use_container_width=True)
                else:
                    st.dataframe(t_df, use_container_width=True)
            else:
                st.caption("無交易記錄")
    with col_m:
        with st.container(border=True):
            st.subheader("月度報酬熱力圖")
            st.plotly_chart(_monthly_heatmap(report["equity_curve"]), use_container_width=True)


def _render_alpha(start, end, source, sectors, strats, min_trades, custom_list):
    import pandas as pd
    from twquant.data.universe import list_by_sector_db
    from twquant.data.storage import SQLiteStorage

    if source == "產業板塊":
        stock_list = tuple(sid for sec in sectors for sid, _ in list_by_sector_db(sec))
    elif source == "全宇宙":
        syms = SQLiteStorage(DB_PATH).list_symbols()
        stock_list = tuple(s.replace("daily_price/", "") for s in syms if s.startswith("daily_price/"))
    else:
        stock_list = tuple(s.strip() for s in custom_list.strip().split("\n") if s.strip())

    st.caption(f"掃描範圍：{len(stock_list)} 支 × {len(strats)} 種策略")

    with st.spinner(f"掃描中（首次約 1-3 分鐘）..."):
        scan_rows = run_alpha_scan(stock_list, str(start), str(end),
                                   tuple(strats), int(min_trades))

    if not scan_rows:
        st.warning("掃描無結果，請確認 DB 中已有足夠資料（執行 seed_data.py）")
        return

    df_scan = pd.DataFrame(scan_rows)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("掃描組合數", len(df_scan))
    c2.metric("正超額報酬", int((df_scan["超額α"] > 0).sum()))
    c3.metric("最佳 Sharpe", f"{df_scan['Sharpe'].max():.2f}")
    c4.metric("最佳超額", f"{df_scan['超額α'].max():.1%}")

    display = df_scan.copy()
    for col in ["總報酬", "超額α", "最大回撤"]:
        display[col] = display[col].apply(lambda v: f"{v:+.1%}")
    display["Sharpe"] = display["Sharpe"].apply(lambda v: f"{v:.2f}")
    display["勝率"] = display["勝率"].apply(lambda v: f"{v:.1%}" if v == v else "N/A")
    st.dataframe(display, use_container_width=True, hide_index=True, height=500)

    csv = df_scan.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ 下載 CSV", csv, f"alpha_{start}_{end}.csv", "text/csv")


# ─── 主介面 ────────────────────────────────────────
def main():
    import pandas as pd
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.components.global_sidebar import render_global_sidebar
    from twquant.data.universe import list_sectors, list_by_sector_db

    register_twquant_dark_template()

    # ── 模式選擇（最頂） ──
    g_sel_strat = st.session_state.get("g_selected_strategy")
    default_mode_idx = 1 if g_sel_strat in _STRAT_KEYS else 0
    with st.sidebar:
        st.header("🎯 模式")
        mode = st.radio(
            "選擇模式",
            ["5 策略並排對照", "🎯 單策略快測", "🌐 全宇宙策略掃描"],
            index=default_mode_idx,
            label_visibility="collapsed",
        )

    needs_stock = mode != "🌐 全宇宙策略掃描"
    ctx = render_global_sidebar(show_stock=needs_stock, show_dates=True, default_years=3)
    stock_id = ctx["stock_id"]
    start = ctx["start_date"]
    end = ctx["end_date"]

    # ── 模式特定 sidebar ──
    with st.sidebar:
        if mode != "🌐 全宇宙策略掃描":
            with st.expander("📂 依產業選股"):
                sec = st.selectbox("產業", list_sectors(), key="p06_sec_pick")
                options = [(s, n) for s, n in list_by_sector_db(sec)]
                if options:
                    idx = st.selectbox("股票", range(len(options)),
                                       format_func=lambda i: f"{options[i][0]} {options[i][1]}",
                                       key="p06_sec_stock")
                    if st.button("套用此股票", use_container_width=True, key="p06_apply_sec"):
                        st.session_state["g_current_stock"] = options[idx][0]
                        st.session_state["current_stock"] = options[idx][0]
                        st.rerun()

        st.header("回測設定")
        if mode == "5 策略並排對照":
            selected = st.multiselect("選擇策略", _STRAT_KEYS, default=_STRAT_KEYS,
                                      format_func=lambda k: _STRAT_LABEL.get(k, k))
            use_adj = st.checkbox("✅ 使用還原權息", value=False,
                                  help="需先執行 seed_data.py --include adj")
            run_btn = st.button("▶ 執行對照回測", type="primary", use_container_width=True)
        elif mode == "🎯 單策略快測":
            default_strat = g_sel_strat if g_sel_strat in _STRAT_KEYS else "momentum_concentrate"
            strat_key = st.selectbox("策略", _STRAT_KEYS,
                                     index=_STRAT_KEYS.index(default_strat),
                                     format_func=lambda k: _STRAT_LABEL.get(k, k))
            use_adj = st.checkbox("✅ 使用還原權息", value=False)
            run_btn = st.button("▶ 執行單策略回測", type="primary", use_container_width=True)
        else:  # 全宇宙
            source = st.radio("股票來源", ["產業板塊", "全宇宙", "自訂清單"], horizontal=True)
            sectors = ()
            custom_list = ""
            if source == "產業板塊":
                sectors = tuple(st.multiselect("產業（可多選）", list_sectors(),
                                                default=["半導體業", "電子工業"]))
            elif source == "自訂清單":
                custom_list = st.text_area("代號清單", value="2330\n2317\n2454\n0050", height=120)
            strats = st.multiselect("策略", _STRAT_KEYS, default=_STRAT_KEYS,
                                    format_func=lambda k: _STRAT_LABEL.get(k, k))
            min_trades = st.number_input("最少交易次數", 1, 20, 3)
            run_btn = st.button("🚀 開始全宇宙掃描", type="primary", use_container_width=True)

    # ── 主區 ──
    st.title("⚔️ 策略覆驗中心")
    st.caption("5 策略並排 / 單策略快測 / 全宇宙 Alpha 掃描 三模式合一 | 含 0050 基準")

    if not run_btn:
        st.info(f"當前模式：**{mode}**。在左側設定後點擊執行按鈕。")
        with st.expander("📖 各策略進場條件"):
            for k, desc in _STRAT_DESC.items():
                st.markdown(f"**{_STRAT_LABEL[k]}**  \n{desc}\n")
        return

    if mode == "5 策略並排對照":
        if not selected:
            st.warning("請至少選擇一個策略")
            return
        _render_compare(stock_id, start, end, selected, use_adj)
        # 用最佳策略跳「單策略快測」模式（同頁切換）
        st.divider()
        if st.button("💡 提示：可切換到「🎯 單策略快測」深入看單一策略表現",
                     use_container_width=True):
            pass
    elif mode == "🎯 單策略快測":
        _render_single(stock_id, start, end, strat_key, use_adj)
    else:
        if not strats:
            st.warning("請至少選擇一個策略")
            return
        _render_alpha(start, end, source, sectors, strats, min_trades, custom_list)


if __name__ == "__main__":
    main()
