"""Page 6：策略 vs 基準對照 - 多策略回測比較 + Alpha 掃描器"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="策略 vs 基準", page_icon="⚔️", layout="wide")

DB_PATH = "data/twquant.db"


# ─────────────────────────────────────────────────────────────
# 從 DB 載入（不呼叫 API）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def _load_from_db(sid: str, start: str, end: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


# ─────────────────────────────────────────────────────────────
# ★ 8 種原創策略定義（E, F 原有；G-L 新增）
# ─────────────────────────────────────────────────────────────

def strategy_ma60_trend(df):
    """E: MA60 主趨勢跟蹤（少量進出，長線持有）"""
    from twquant.indicators.basic import compute_ma
    close = df["close"].astype(float)
    ma60  = compute_ma(close, 60)
    ma120 = compute_ma(close, 120)
    uptrend = (ma60 > ma120) & (close > ma60)
    prev = uptrend.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    entries = (uptrend & ~prev).to_numpy().astype(bool)
    exits   = (~uptrend & ~(~uptrend).shift(1).fillna(False).infer_objects(copy=False).astype(bool)).to_numpy().astype(bool)
    return entries, exits


def strategy_momentum_concentrate(df):
    """F: 動能精選（20 日動能 > 5% + 站穩 MA60，破 MA60×0.97 才出）★ 推薦 ★"""
    from twquant.indicators.basic import compute_ma
    close = df["close"].astype(float)
    ma60  = compute_ma(close, 60)
    ret20 = close.pct_change(20)
    entry_cond = (close > ma60) & (ret20 > 0.05)
    exit_cond  = close < ma60 * 0.97
    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    entries = (entry_cond & ~prev_e).to_numpy().astype(bool)
    exits   = (exit_cond & ~prev_x).to_numpy().astype(bool)
    return entries, exits


def strategy_rsi_dip(df):
    """G: RSI 拉回買進 ─ 趨勢中低量回調、RSI 回健康區進場"""
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ma20   = compute_ma(close, 20)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)
    vol20  = volume.rolling(20).mean()

    uptrend    = (close > ma60) & (ma20 > ma60)
    rsi_dip    = (rsi >= 42) & (rsi <= 58)
    # 近10日RSI曾高於60：確認是回調，不是下跌趨勢
    rsi_recent_strong = rsi.shift(1).rolling(10).max() > 60
    low_vol    = volume < (vol20 * 0.92)       # 量縮回調 = 洗盤特徵

    entry_cond = uptrend & rsi_dip & rsi_recent_strong & low_vol
    exit_cond  = (close < ma20 * 0.985) | (rsi > 82)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_volume_breakout(df):
    """H: 量價突破新高 ─ 成交量放大 1.5x 確認 20 日高點突破"""
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)

    high20 = close.rolling(20).max().shift(1)  # 前20日最高（不含今日，避免偏差）
    vol20  = volume.rolling(20).mean()

    entry_cond = (
        (close > high20) &          # 突破 20 日新高
        (volume > vol20 * 1.5) &    # 量能放大 1.5 倍
        (close > ma60) &            # 長線趨勢向上
        (rsi < 76)                  # 非極度超買
    )
    exit_cond = (close < ma60 * 0.96) | (rsi > 85)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_kd_cross_trend(df):
    """I: KD 低檔金叉 + 趨勢過濾 ─ K 從低位穿越 D，且收盤不破 MA60"""
    from twquant.indicators.basic import compute_ma, compute_kd
    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    ma60   = compute_ma(close, 60)
    k, d   = compute_kd(high, low, close)

    # 金叉：K 由下穿越 D，且仍在低檔區（K < 55 避免高位金叉）
    kd_cross_up = (k > d) & (k.shift(1) <= d.shift(1)) & (k < 55)
    in_trend    = close > ma60 * 0.97  # 允許3%緩衝，不要求嚴格貼合

    entry_cond  = kd_cross_up & in_trend

    # 死叉出場：K 由高位穿越 D（K > 70 的高位死叉）或跌破趨勢
    kd_cross_dn = (k < d) & (k.shift(1) >= d.shift(1)) & (k > 70)
    exit_cond   = kd_cross_dn | (close < ma60 * 0.93)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_ma_bounce(df):
    """J: 均線彈升 ─ 量縮回測 MA20 的低波動拉回買點"""
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    volume = df["volume"].astype(float)
    ma20   = compute_ma(close, 20)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)
    vol20  = volume.rolling(20).mean()

    near_ma20   = (close / ma20 - 1).abs() < 0.025   # 收盤在 MA20 ±2.5% 內
    trend_ok    = ma20 > ma60                          # MA 多頭排列
    low_vol     = volume < vol20 * 0.90               # 量縮（非出貨）
    rsi_neutral = (rsi >= 38) & (rsi <= 60)           # RSI 中性（不超買不超賣）

    entry_cond = near_ma20 & trend_ok & low_vol & rsi_neutral
    exit_cond  = (close < ma60 * 0.96) | (rsi > 78)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_atr_squeeze(df):
    """K: 波動壓縮突破 ─ 低 ATR 蓄勢後向上放量突破（類似 Bollinger Squeeze 變形）"""
    from twquant.indicators.basic import compute_ma, compute_atr
    close  = df["close"].astype(float)
    high   = df["high"].astype(float)
    low    = df["low"].astype(float)
    ma20   = compute_ma(close, 20)
    ma60   = compute_ma(close, 60)
    atr14  = compute_atr(high, low, close, 14)
    atr_pct = atr14 / close * 100

    # 前10天處於低波動壓縮狀態（ATR% 最高值 < 2.5%）
    squeeze       = atr_pct.rolling(10).max() < 2.5
    # 今日突破：ATR 放大 + 方向向上
    expansion_up  = (atr_pct > atr_pct.shift(1) * 1.2) & (close > ma20)
    in_trend      = close > ma60 * 0.97

    entry_cond = squeeze.shift(1).fillna(False) & expansion_up & in_trend
    exit_cond  = (close < ma20 * 0.97) | (close < ma60 * 0.93)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


def strategy_triple_ma_twist(df):
    """L: 三線扭轉 ─ MA5/20/60 從非多頭→多頭排列的扭轉點進場"""
    from twquant.indicators.basic import compute_ma, compute_rsi
    close  = df["close"].astype(float)
    ma5    = compute_ma(close, 5)
    ma20   = compute_ma(close, 20)
    ma60   = compute_ma(close, 60)
    rsi    = compute_rsi(close, 14)

    aligned      = (ma5 > ma20) & (ma20 > ma60) & (close > ma5)
    prev_aligned = aligned.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    just_twisted = aligned & ~prev_aligned          # 剛從非多頭→多頭排列

    entry_cond = just_twisted & (rsi < 72)          # RSI 未極度超買才進場
    exit_cond  = (ma5 < ma20) | (close < ma60 * 0.95)
    exit_cond  = exit_cond.fillna(False).infer_objects(copy=False).astype(bool)

    prev_e = entry_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    prev_x = exit_cond.shift(1).fillna(False).infer_objects(copy=False).astype(bool)
    return (entry_cond & ~prev_e).to_numpy().astype(bool), (exit_cond & ~prev_x).to_numpy().astype(bool)


STRATEGIES = {
    "E - MA60 主趨勢跟蹤":          strategy_ma60_trend,
    "F - 動能精選 ★":              strategy_momentum_concentrate,
    "G - RSI 拉回買進":             strategy_rsi_dip,
    "H - 量價突破新高":             strategy_volume_breakout,
    "I - KD 低檔金叉":              strategy_kd_cross_trend,
    "J - 均線彈升（低量回調）":      strategy_ma_bounce,
    "K - 波動壓縮突破（ATR Squeeze）": strategy_atr_squeeze,
    "L - 三線扭轉進場":             strategy_triple_ma_twist,
}

STRATEGY_COLORS = {
    "0050 持有(基準)":                  "#94A3B8",
    "E - MA60 主趨勢跟蹤":             "#22C55E",
    "F - 動能精選 ★":                  "#FFD700",
    "G - RSI 拉回買進":                "#60A5FA",
    "H - 量價突破新高":                "#F97316",
    "I - KD 低檔金叉":                 "#A78BFA",
    "J - 均線彈升（低量回調）":         "#34D399",
    "K - 波動壓縮突破（ATR Squeeze）":  "#FB7185",
    "L - 三線扭轉進場":                "#FBBF24",
}

STRATEGY_DESC = {
    "E - MA60 主趨勢跟蹤":
        "MA60 > MA120 且收盤 > MA60。長線趨勢確立才進場，違背即出。交易次數少，適合長線。",
    "F - 動能精選 ★":
        "收盤 > MA60 且 20 日動能 > 5%。動能強勢確認才進，跌破 MA60×0.97 才出。最強歷史表現。",
    "G - RSI 拉回買進":
        "趨勢中（MA20>MA60、收盤>MA60），RSI 回到 42-58 健康區，且為低量回調。買健康回調，不買強跌。",
    "H - 量價突破新高":
        "收盤突破 20 日高點，且量能為 20 日均量 1.5 倍以上。量大確認突破真實性，非假突破。",
    "I - KD 低檔金叉":
        "K 從低檔區（K<55）向上穿越 D（金叉），且收盤不破 MA60。低檔反彈確認，高檔死叉出場。",
    "J - 均線彈升（低量回調）":
        "收盤在 MA20 ±2.5% 附近，MA20>MA60，量縮至 0.9 倍以下，RSI 中性（38-60）。低量回測支撐。",
    "K - 波動壓縮突破（ATR Squeeze）":
        "前 10 日 ATR% 均低於 2.5%（蓄勢），今日 ATR 放大 1.2 倍且收盤突破 MA20。壓縮後方向選擇。",
    "L - 三線扭轉進場":
        "MA5/20/60 剛從非多頭→多頭排列（扭轉點），且 RSI < 72。抓住趨勢確立的最早入場點。",
}


# ─────────────────────────────────────────────────────────────
# 回測執行
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def run_comparison(stock_id: str, start: str, end: str, selected_strategies: tuple):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine

    df = _load_from_db(stock_id, start, end)
    df_bench = _load_from_db("0050", start, end)

    if df.empty or len(df) < 60:
        return None
    if df_bench.empty:
        return None

    price       = pd.Series(df["close"].values, index=pd.to_datetime(df["date"]), dtype=float)
    price_bench = pd.Series(df_bench["close"].values, index=pd.to_datetime(df_bench["date"]), dtype=float)

    results = {}

    n = len(price_bench)
    bh_entries = np.zeros(n, dtype=bool); bh_entries[0] = True
    bh_exits   = np.zeros(n, dtype=bool); bh_exits[-1] = True
    engine = TWSEBacktestEngine()
    bh_metrics = engine.run(price_bench, bh_entries, bh_exits, init_cash=1_000_000)
    results["0050 持有(基準)"] = bh_metrics

    for name in selected_strategies:
        fn = STRATEGIES[name]
        try:
            entries, exits = fn(df)
            if entries.sum() == 0:
                continue
            engine2 = TWSEBacktestEngine()
            metrics = engine2.run(price, entries, exits, init_cash=1_000_000)
            results[name] = metrics
        except Exception as e:
            pass

    return results, df, df_bench


# ─────────────────────────────────────────────────────────────
# Alpha 掃描器（全宇宙 × 所有策略）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_alpha_scan(start: str, end: str, strategies: tuple, min_trades: int = 3) -> list[dict]:
    """對 DB 中所有股票跑所有策略，回傳排行榜（依 Sharpe 排序）"""
    import pandas as pd
    import numpy as np
    from twquant.data.storage import SQLiteStorage
    from twquant.data.universe import get_name, get_sector
    from twquant.backtest.engine import TWSEBacktestEngine

    storage = SQLiteStorage(DB_PATH)
    syms = [s.replace("daily_price/", "") for s in storage.list_symbols()
            if s.startswith("daily_price/")]

    # 0050 基準報酬
    df_bench = storage.load("daily_price/0050", start_date=start, end_date=end)
    bench_ret = 0.0
    if not df_bench.empty:
        df_bench["date"] = pd.to_datetime(df_bench["date"])
        p0 = df_bench["close"].astype(float)
        bench_ret = float(p0.iloc[-1] / p0.iloc[0] - 1)

    rows = []
    engine = TWSEBacktestEngine()

    for sid in syms:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if df.empty or len(df) < 120:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        for strat_name in strategies:
            fn = STRATEGIES.get(strat_name)
            if fn is None:
                continue
            try:
                entries, exits = fn(df)
                n_trades = int(entries.sum())
                if n_trades < min_trades:
                    continue
                price = pd.Series(df["close"].astype(float).values,
                                  index=df["date"])
                m = engine.run(price, entries, exits, init_cash=1_000_000)
                rows.append({
                    "代號": sid,
                    "名稱": get_name(sid),
                    "板塊": get_sector(sid),
                    "策略": strat_name,
                    "總報酬": m["total_return"],
                    "超額報酬α": m["total_return"] - bench_ret,
                    "Sharpe": m["sharpe_ratio"],
                    "最大回撤": m["max_drawdown"],
                    "勝率": m["win_rate"],
                    "交易次數": n_trades,
                    "最終淨值": m["final_value"],
                })
            except Exception:
                pass

    return sorted(rows, key=lambda r: -(r["Sharpe"] if r["Sharpe"] == r["Sharpe"] else -99))


# ─────────────────────────────────────────────────────────────
# 月度報酬熱力圖
# ─────────────────────────────────────────────────────────────
def _monthly_returns_heatmap(equity_curve: dict):
    import pandas as pd
    import plotly.graph_objects as go

    equity = pd.Series(equity_curve)
    equity.index = pd.to_datetime(equity.index)
    monthly = equity.resample("ME").last().pct_change().dropna() * 100

    years  = sorted(monthly.index.year.unique())
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
        zmid=0, colorbar=dict(title="月報酬%"), hoverongaps=False,
    ))
    fig.update_layout(
        height=max(180, len(years) * 38 + 60),
        margin=dict(l=60, r=20, t=20, b=20),
    )
    return fig


# ─────────────────────────────────────────────────────────────
# 主介面
# ─────────────────────────────────────────────────────────────
def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template

    register_twquant_dark_template()

    st.title("⚔️ 策略實驗室 vs 0050 基準")
    st.caption("8 種原創策略 × 全宇宙掃描 | 資料來源：系統 DB | 交易成本已計入")

    tab_single, tab_scan = st.tabs(["📊 單股多策略比較", "🔍 Alpha 掃描器（全宇宙）"])

    # ══════════════════════════════════════════════════════════
    # Tab 1：單股多策略比較
    # ══════════════════════════════════════════════════════════
    with tab_single:
        with st.sidebar:
            st.header("回測設定")
            stock_id = st.text_input("策略標的（股票代碼）", value="2330")
            today = pd.Timestamp.today().normalize()
            default_end   = today - pd.Timedelta(days=1)
            default_start = default_end - pd.DateOffset(years=3)
            start = st.date_input("開始日期", value=default_start)
            end   = st.date_input("結束日期", value=default_end)
            selected = st.multiselect(
                "選擇策略",
                options=list(STRATEGIES.keys()),
                default=list(STRATEGIES.keys()),
            )
            run_btn = st.button("執行對照回測", type="primary", use_container_width=True)

        if not run_btn:
            st.info("在左側設定回測標的與策略後，點擊「執行對照回測」")
            with st.expander("📖 8 種策略說明"):
                for name, desc in STRATEGY_DESC.items():
                    st.markdown(f"**{name}**  \n{desc}\n")
            return

        if not selected:
            st.warning("請至少選擇一個策略")
            return

        with st.spinner("回測中..."):
            out = run_comparison(stock_id, str(start), str(end), tuple(selected))

        if out is None:
            st.error(f"無法載入 {stock_id} 或 0050 資料，請先執行種子腳本入庫。")
            return

        all_results, df, df_bench = out

        # ── 績效指標對照表 ──
        st.subheader("📊 績效指標對照")
        rows = []
        for name, m in all_results.items():
            rows.append({
                "策略": name,
                "總報酬": f"{m['total_return']:.1%}",
                "最大回撤": f"{m['max_drawdown']:.1%}",
                "Sharpe": f"{m['sharpe_ratio']:.2f}",
                "Sortino": f"{m['sortino_ratio']:.2f}",
                "Calmar": f"{m['calmar_ratio']:.2f}",
                "勝率": f"{m['win_rate']:.1%}" if not pd.isna(m['win_rate']) else "N/A",
                "交易次數": m["total_trades"],
                "最終淨值": f"${m['final_value']:,.0f}",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        # ── 資金曲線 ──
        st.divider()
        st.subheader(f"📈 資金曲線（{stock_id} vs 0050，初始 $1,000,000）")
        fig_eq = go.Figure()
        for name, m in all_results.items():
            equity = pd.Series(m["equity_curve"])
            equity.index = pd.to_datetime(equity.index)
            is_bench = "基準" in name
            fig_eq.add_trace(go.Scatter(
                x=equity.index, y=equity.values, name=name,
                line=dict(
                    color=STRATEGY_COLORS.get(name, "#A855F7"),
                    width=3 if is_bench or "★" in name else 1.8,
                    dash="dash" if is_bench else "solid",
                ),
            ))
        fig_eq.update_layout(
            height=480, margin=dict(l=40, r=20, t=20, b=20),
            hovermode="x unified", xaxis_title="日期", yaxis_title="資產淨值（元）",
            legend=dict(orientation="h", y=-0.18),
        )
        st.plotly_chart(fig_eq, use_container_width=True)

        # ── 超額報酬卡 ──
        bench_return = all_results.get("0050 持有(基準)", {}).get("total_return", 0)
        st.divider()
        st.subheader("🏆 超額報酬（相對 0050）")
        non_bench = {k: v for k, v in all_results.items() if "基準" not in k}
        if non_bench:
            cols = st.columns(len(non_bench))
            for i, (name, m) in enumerate(non_bench.items()):
                alpha = m["total_return"] - bench_return
                cols[i].metric(
                    name[:12],
                    f"{m['total_return']:.1%}",
                    f"α {alpha:+.1%}",
                )

        # ── 最佳策略月度熱力圖 ──
        best_name = max(non_bench, key=lambda k: non_bench[k]["total_return"], default=None)
        if best_name:
            st.divider()
            st.subheader(f"📅 月度報酬熱力圖（{best_name}）")
            st.plotly_chart(_monthly_returns_heatmap(non_bench[best_name]["equity_curve"]),
                            use_container_width=True)
            trades = non_bench[best_name].get("trades", [])
            if trades:
                st.subheader("📋 交易明細（最近 20 筆）")
                st.dataframe(pd.DataFrame(trades).tail(20), use_container_width=True)

        # ── 分析師結論 ──
        st.divider()
        st.subheader("🧠 分析師結論")
        winners = [k for k in non_bench if non_bench[k]["total_return"] > bench_return]
        if winners:
            best = max(winners, key=lambda k: non_bench[k]["total_return"])
            bm   = non_bench[best]
            alpha = bm["total_return"] - bench_return
            st.success(
                f"**{best}** 跑贏 0050，超額報酬 **{alpha:+.1%}** ｜ "
                f"Sharpe {bm['sharpe_ratio']:.2f} ｜ 最大回撤 {bm['max_drawdown']:.1%} ｜ 勝率 {bm['win_rate']:.1%}"
            )
            if bm["max_drawdown"] < -0.25:
                st.warning("注意：最大回撤 > 25%，實際操作需加強停損/部位控制")
        else:
            st.warning(f"本次設定無策略跑贏 0050（基準 {bench_return:.1%}）。可換標的或策略。")

    # ══════════════════════════════════════════════════════════
    # Tab 2：Alpha 掃描器
    # ══════════════════════════════════════════════════════════
    with tab_scan:
        st.subheader("🔍 Alpha 掃描器 — 全宇宙 × 所有策略排行榜")
        st.caption("對 DB 中所有已入庫股票，跑選定策略，依 Sharpe 排名，找出最強 Alpha 機會")

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            scan_start = st.date_input("掃描起始", value=pd.Timestamp.today() - pd.DateOffset(years=3),
                                       key="scan_start")
            scan_end   = st.date_input("掃描結束", value=pd.Timestamp.today() - pd.Timedelta(days=1),
                                       key="scan_end")
        with col_s2:
            scan_strats = st.multiselect(
                "掃描策略",
                options=list(STRATEGIES.keys()),
                default=list(STRATEGIES.keys()),
                key="scan_strats",
            )
            min_trades = st.number_input("最少交易次數", min_value=1, max_value=20, value=3, key="min_trades")
        with col_s3:
            top_n_show = st.number_input("顯示 Top N", min_value=5, max_value=100, value=30, key="top_n_show")
            filter_sector = st.selectbox(
                "板塊篩選",
                ["全部"] + ["半導體","電子組件/ODM","PCB/被動元件","面板/光電",
                            "金融保險","航運/空運","電信/網路","原物料/石化/鋼鐵",
                            "食品/消費/零售","生技醫療","ETF"],
                key="filter_sector",
            )

        scan_btn = st.button("🚀 開始全宇宙掃描", type="primary", use_container_width=True)

        if not scan_btn:
            st.info("設定掃描參數後點擊「開始全宇宙掃描」。首次掃描視資料量需 1-3 分鐘，結果快取 1 小時。")
            return

        if not scan_strats:
            st.warning("請選擇至少一個策略")
            return

        with st.spinner(f"掃描中... 正在跑 {len(scan_strats)} 種策略 × DB 全部股票"):
            scan_rows = run_alpha_scan(str(scan_start), str(scan_end),
                                       tuple(scan_strats), int(min_trades))

        if not scan_rows:
            st.error("掃描無結果。請確認 DB 中已有股票資料（先執行種子腳本）。")
            return

        df_scan = pd.DataFrame(scan_rows)
        if filter_sector != "全部":
            df_scan = df_scan[df_scan["板塊"] == filter_sector]

        df_show = df_scan.head(int(top_n_show)).copy()

        # ── 摘要指標 ──
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("掃描組合數", len(df_scan))
        c2.metric("正超額報酬數", int((df_scan["超額報酬α"] > 0).sum()))
        if len(df_scan):
            best_row = df_scan.iloc[0]
            c3.metric("最佳 Sharpe", f"{best_row['Sharpe']:.2f}", f"{best_row['代號']} {best_row['策略'][:6]}")
            c4.metric("最佳超額報酬", f"{df_scan['超額報酬α'].max():.1%}")

        # ── 排行榜表格 ──
        st.subheader(f"🥇 Alpha 排行榜（Sharpe 降序，Top {int(top_n_show)}）")
        display_df = df_show.copy()
        display_df["總報酬"]   = display_df["總報酬"].apply(lambda v: f"{v:.1%}")
        display_df["超額報酬α"] = display_df["超額報酬α"].apply(lambda v: f"{v:+.1%}")
        display_df["Sharpe"]   = display_df["Sharpe"].apply(lambda v: f"{v:.2f}")
        display_df["最大回撤"]  = display_df["最大回撤"].apply(lambda v: f"{v:.1%}")
        display_df["勝率"]     = display_df["勝率"].apply(
            lambda v: f"{v:.1%}" if v == v else "N/A")
        display_df["最終淨值"]  = display_df["最終淨值"].apply(lambda v: f"${v:,.0f}")
        st.dataframe(display_df[["代號","名稱","板塊","策略","總報酬","超額報酬α",
                                  "Sharpe","最大回撤","勝率","交易次數","最終淨值"]],
                     use_container_width=True, hide_index=True, height=500)

        # ── 策略勝率統計 ──
        st.divider()
        st.subheader("📊 各策略：平均 Sharpe vs 平均超額報酬")
        strat_agg = (
            df_scan.groupby("策略")
            .agg(平均Sharpe=("Sharpe","mean"), 平均超額報酬=("超額報酬α","mean"),
                 正超額比例=("超額報酬α", lambda x: (x>0).mean()),
                 樣本數=("代號","count"))
            .reset_index()
            .sort_values("平均Sharpe", ascending=False)
        )
        fig_agg = go.Figure()
        fig_agg.add_trace(go.Bar(
            x=strat_agg["策略"], y=strat_agg["平均Sharpe"],
            name="平均 Sharpe",
            marker_color=["#22C55E" if v > 0 else "#EF4444" for v in strat_agg["平均Sharpe"]],
            text=[f"{v:.2f}" for v in strat_agg["平均Sharpe"]], textposition="outside",
        ))
        fig_agg.add_trace(go.Scatter(
            x=strat_agg["策略"], y=strat_agg["平均超額報酬"] * 100,
            name="平均超額報酬(%)", mode="lines+markers",
            yaxis="y2", line=dict(color="#FFD700", width=2),
        ))
        fig_agg.update_layout(
            height=320, margin=dict(l=40, r=60, t=30, b=120),
            xaxis_tickangle=-25, yaxis_title="平均 Sharpe",
            yaxis2=dict(title="平均超額報酬(%)", overlaying="y", side="right"),
            legend=dict(orientation="h", y=1.05), barmode="group",
        )
        st.plotly_chart(fig_agg, use_container_width=True)

        # ── 散布圖：Sharpe vs 超額報酬 ──
        st.subheader("🗺️ 風險調整後報酬分布（Sharpe vs 超額報酬α）")
        fig_scatter = go.Figure()
        for strat in df_scan["策略"].unique():
            sub = df_scan[df_scan["策略"] == strat]
            fig_scatter.add_trace(go.Scatter(
                x=sub["超額報酬α"] * 100, y=sub["Sharpe"],
                mode="markers",
                name=strat[:14],
                text=[f"{r['代號']} {r['名稱']}" for _, r in sub.iterrows()],
                marker=dict(size=7, color=STRATEGY_COLORS.get(strat, "#A855F7"), opacity=0.75),
            ))
        fig_scatter.add_vline(x=0, line_color="#4B5563", line_dash="dot")
        fig_scatter.add_hline(y=0, line_color="#4B5563", line_dash="dot")
        fig_scatter.update_layout(
            height=420, margin=dict(l=50, r=20, t=20, b=40),
            xaxis_title="超額報酬α（%）", yaxis_title="Sharpe Ratio",
            hovermode="closest",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

        # ── CSV 匯出 ──
        csv_bytes = df_scan.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ 下載完整掃描結果 CSV",
                           data=csv_bytes,
                           file_name=f"alpha_scan_{scan_start}_{scan_end}.csv",
                           mime="text/csv")


if __name__ == "__main__":
    main()
