"""Page 7：產業組合回測 - 月度輪動策略 vs 0050"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="組合回測", page_icon="🏗️", layout="wide")

DB_PATH = "data/twquant.db"


@st.cache_data(ttl=3600)
def _load_universe_sectors():
    from twquant.data.universe import ANALYST_UNIVERSE
    return {k: [(sid, name) for sid, name in v] for k, v in ANALYST_UNIVERSE.items()}


@st.cache_data(ttl=1800)
def _load_price_data(sids: tuple, start: str, end: str) -> dict:
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    out = {}
    for sid in sids:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if not df.empty and len(df) >= 60:
            df["date"] = pd.to_datetime(df["date"])
            out[sid] = df
    return out


@st.cache_data(ttl=1800)
def _run_portfolio(sids: tuple, start: str, end: str, top_n: int):
    import pandas as pd
    import numpy as np
    from twquant.backtest.portfolio import run_portfolio_backtest
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.data.storage import SQLiteStorage

    price_data = _load_price_data(sids, start, end)
    if not price_data:
        return None, None

    result = run_portfolio_backtest(price_data, start, end, top_n=top_n)

    # 0050 benchmark
    storage = SQLiteStorage(DB_PATH)
    df0 = storage.load("daily_price/0050", start_date=start, end_date=end)
    if df0.empty:
        return result, None
    df0["date"] = pd.to_datetime(df0["date"])
    p0 = pd.Series(df0["close"].astype(float).values, index=df0["date"])
    n = len(p0)
    bh_e = np.zeros(n, bool); bh_e[0] = True
    bh_x = np.zeros(n, bool); bh_x[-1] = True
    bm = TWSEBacktestEngine().run(p0, bh_e, bh_x, init_cash=1_000_000)
    return result, bm


def _monthly_heatmap(monthly_returns: dict):
    import pandas as pd
    import plotly.graph_objects as go

    mr = pd.Series(monthly_returns)
    mr.index = pd.to_datetime(mr.index)
    mr = mr * 100

    years = sorted(mr.index.year.unique())
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    z, text = [], []
    for yr in years:
        row, txt_row = [], []
        for mo in range(1, 13):
            vals = mr[(mr.index.year == yr) & (mr.index.month == mo)]
            v = round(float(vals.iloc[0]), 2) if len(vals) > 0 else None
            row.append(v)
            txt_row.append(f"{v:.1f}%" if v is not None else "")
        z.append(row); text.append(txt_row)

    fig = go.Figure(go.Heatmap(
        z=z, x=month_names, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, "#EF4444"], [0.5, "#1F2937"], [1, "#22C55E"]],
        zmid=0, hoverongaps=False,
        colorbar=dict(title="月報酬%"),
    ))
    fig.update_layout(
        height=max(180, len(years) * 38 + 60),
        margin=dict(l=50, r=10, t=10, b=10),
    )
    return fig


def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.data.universe import get_name, ANALYST_UNIVERSE

    st.title("🏗️ 產業組合回測")
    st.caption("月度輪動策略：每月評分 → 選 Top-N → 等權重配置 vs 0050 買進持有")

    universe = _load_universe_sectors()

    # ── 側邊欄 ──
    with st.sidebar:
        st.header("回測設定")

        mode = st.radio("股票來源", ["依產業選擇", "自訂清單"], horizontal=True)

        if mode == "依產業選擇":
            sector = st.selectbox("產業板塊", list(universe.keys()))
            sector_stocks = universe[sector]
            selected_sids = st.multiselect(
                "選擇股票",
                options=[s for s, _ in sector_stocks],
                default=[s for s, _ in sector_stocks],
                format_func=lambda s: f"{s} {get_name(s)}",
            )
        else:
            custom_input = st.text_area(
                "自訂股票代碼（每行一個）",
                value="2330\n2454\n2303\n2308\n3034",
                height=150,
            )
            selected_sids = [s.strip() for s in custom_input.strip().split("\n") if s.strip()]

        st.divider()
        today = pd.Timestamp.today().normalize()
        default_end   = today - pd.Timedelta(days=1)
        default_start = default_end - pd.DateOffset(years=3)
        start = st.date_input("開始日期", value=default_start)
        end   = st.date_input("結束日期", value=default_end)
        top_n = st.slider("每期持有支數 (Top-N)", 1, 10, 5)
        run_btn = st.button("執行組合回測", type="primary", use_container_width=True)

    if not run_btn:
        st.info("在左側選擇產業板塊或自訂清單，設定參數後點擊「執行組合回測」")
        with st.expander("📖 策略說明"):
            st.markdown("""
**月度輪動策略（月度動態再平衡）**

1. **每月月底** 對所有股票進行多因子評分
2. 選出得分最高的 **Top-N 支**，等權重配置（100% / N）
3. 下個月月底再次評分換倉

**評分因子（共 8 維）**：
| 因子 | 說明 |
|------|------|
| 趨勢排列 | 收盤 > MA20 > MA60（多頭排列）|
| RSI 動能 | 45-65 為健康動能區間 |
| MACD 金叉 | 柱狀體由負轉正 +3 分 |
| 20日動能 | 近月報酬率 > 8% 加分 |
| 量能比 | 近5日均量 / 近20日均量 |

**交易成本**：手續費 0.1425%×0.6 折 + 證交稅 0.3%（買賣各計）

**基準**：0050（元大台灣50）買進持有

> 策略優勢：自動追蹤板塊內的強勢輪動；不依賴固定股票，每月動態調整
            """)

        # 顯示當前宇宙中各板塊股票數
        st.subheader("📊 分析師股票宇宙（含入庫股票數）")
        from twquant.data.storage import SQLiteStorage
        storage = SQLiteStorage(DB_PATH)
        db_sids = set(s.replace("daily_price/", "") for s in storage.list_symbols())
        rows = []
        for sec, stocks in ANALYST_UNIVERSE.items():
            in_db = sum(1 for s, _ in stocks if s in db_sids)
            rows.append({"產業": sec, "股票數": len(stocks), "已入庫": in_db,
                          "入庫率": f"{in_db/max(len(stocks),1):.0%}"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        return

    if not selected_sids:
        st.warning("請選擇至少一支股票")
        return

    with st.spinner(f"回測 {len(selected_sids)} 支股票，月度輪動 Top-{top_n}..."):
        result, bm = _run_portfolio(tuple(selected_sids), str(start), str(end), top_n)

    if result is None:
        st.error("無法載入資料，請確認股票已入庫（可先執行種子腳本）")
        return

    bench_ret = bm["total_return"] if bm else 0
    alpha = result["total_return"] - bench_ret

    # ── 摘要指標卡 ──
    st.subheader(f"📊 回測結果摘要（{len(selected_sids)}支 → 每期持有Top-{top_n}）")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("組合總報酬", f"{result['total_return']:.1%}")
    c2.metric("0050 基準", f"{bench_ret:.1%}")
    clr = "normal" if alpha >= 0 else "inverse"
    c3.metric("超額報酬 α", f"{alpha:+.1%}")
    c4.metric("Sharpe Ratio", f"{result['sharpe_ratio']:.2f}")
    c5.metric("最大回撤", f"{result['max_drawdown']:.1%}")
    c6.metric("平均月換手", f"{result['turnover_avg']:.0%}")

    if alpha >= 0:
        st.success(f"✅ 策略跑贏 0050！超額報酬 {alpha:+.1%}，Sharpe {result['sharpe_ratio']:.2f}")
    else:
        st.warning(f"⚠️ 本次設定未跑贏 0050（差距 {alpha:.1%}）。可嘗試調整 Top-N 或更換板塊。")

    st.divider()

    # ── 資金曲線 ──
    st.subheader("📈 資金曲線：組合 vs 0050")
    fig_eq = go.Figure()
    equity = pd.Series(result["equity_curve"])
    equity.index = pd.to_datetime(equity.index)
    fig_eq.add_trace(go.Scatter(
        x=equity.index, y=equity.values,
        name=f"輪動組合 Top-{top_n}",
        line=dict(color="#FFD700", width=2.5),
        fill="tozeroy", fillcolor="rgba(255,215,0,0.05)",
    ))
    if bm:
        bench_eq = pd.Series(bm["equity_curve"])
        bench_eq.index = pd.to_datetime(bench_eq.index)
        fig_eq.add_trace(go.Scatter(
            x=bench_eq.index, y=bench_eq.values,
            name="0050 買進持有",
            line=dict(color="#94A3B8", width=2, dash="dash"),
        ))
    fig_eq.update_layout(
        height=460, hovermode="x unified",
        xaxis_title="日期", yaxis_title="資產淨值（元）",
        legend=dict(orientation="h", y=1.02),
        margin=dict(l=40, r=20, t=20, b=20),
    )
    st.plotly_chart(fig_eq, use_container_width=True)

    # ── 月度熱力圖 ──
    st.divider()
    col_heat, col_hold = st.columns([3, 2])

    with col_heat:
        st.subheader("📅 月度報酬熱力圖")
        if result["monthly_returns"]:
            st.plotly_chart(_monthly_heatmap(result["monthly_returns"]),
                            use_container_width=True)

    with col_hold:
        st.subheader("📋 近期持股記錄（最後 6 期）")
        logs = result.get("holdings_log", [])[-6:]
        for log in reversed(logs):
            sids_held = [h["sid"] for h in log["holdings"]]
            names = [f"{s} {get_name(s)}" for s in sids_held]
            scores = [h["score"] for h in log["holdings"]]
            st.markdown(f"**{log['date']}** 換手 {log['turnover']:.0%}")
            df_hold = pd.DataFrame({"代號": sids_held, "名稱": [get_name(s) for s in sids_held], "評分": scores})
            st.dataframe(df_hold, use_container_width=True, hide_index=True, height=160)

    # ── 報酬分布 ──
    st.divider()
    st.subheader("📊 年度績效對照")
    mr = pd.Series(result["monthly_returns"])
    mr.index = pd.to_datetime(mr.index)
    annual = (1 + mr).groupby(mr.index.year).prod() - 1
    bm_annual = None
    if bm:
        bm_mr = pd.Series(bm["equity_curve"])
        bm_mr.index = pd.to_datetime(bm_mr.index)
        bm_mr = bm_mr.resample("ME").last().pct_change().dropna()
        bm_annual = (1 + bm_mr).groupby(bm_mr.index.year).prod() - 1

    fig_annual = go.Figure()
    fig_annual.add_trace(go.Bar(
        x=[str(y) for y in annual.index],
        y=annual.values * 100,
        name=f"輪動組合",
        marker_color=["#22C55E" if v > 0 else "#EF4444" for v in annual.values],
        text=[f"{v:.1%}" for v in annual.values],
        textposition="outside",
    ))
    if bm_annual is not None:
        fig_annual.add_trace(go.Scatter(
            x=[str(y) for y in bm_annual.index],
            y=bm_annual.values * 100,
            name="0050 基準",
            mode="lines+markers",
            line=dict(color="#94A3B8", width=2, dash="dash"),
        ))
    fig_annual.add_hline(y=0, line_color="#4B5563", line_width=1)
    fig_annual.update_layout(
        height=300, margin=dict(l=40, r=20, t=20, b=20),
        yaxis_title="年報酬（%）",
        legend=dict(orientation="h", y=1.05),
        barmode="group",
    )
    st.plotly_chart(fig_annual, use_container_width=True)


if __name__ == "__main__":
    main()
