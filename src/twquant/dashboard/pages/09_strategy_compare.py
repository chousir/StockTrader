"""Page 9：策略 A/B 並排比較器 — 同標的同時間軸對比兩組策略"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="A/B 策略比較", page_icon="🆚", layout="wide")

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

_COLOR_A  = "#3B82F6"
_COLOR_B  = "#F97316"
_COLOR_BH = "#94A3B8"


@st.cache_data(ttl=1800)
def _load(sid: str, start: str, end: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=1800)
def _run_one(stock_id: str, start: str, end: str, strat_key: str):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine
    from twquant.strategy.registry import get_strategy

    df = _load(stock_id, start, end)
    if df.empty or len(df) < 60:
        return None
    price = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))
    entries, exits = get_strategy(strat_key).generate_signals(df)
    if entries.sum() == 0:
        return None
    return TWSEBacktestEngine().run(price, entries, exits, init_cash=1_000_000)


@st.cache_data(ttl=1800)
def _run_bh(stock_id: str, start: str, end: str):
    import pandas as pd
    import numpy as np
    from twquant.backtest.engine import TWSEBacktestEngine

    df = _load(stock_id, start, end)
    if df.empty:
        return None
    price = pd.Series(df["close"].astype(float).values, index=pd.to_datetime(df["date"]))
    n = len(price)
    bh_e = np.zeros(n, dtype=bool); bh_e[0] = True
    bh_x = np.zeros(n, dtype=bool); bh_x[-1] = True
    return TWSEBacktestEngine().run(price, bh_e, bh_x, init_cash=1_000_000)


def _monthly_heatmap(equity_curve: dict, title: str, color: str):
    import pandas as pd
    import plotly.graph_objects as go

    equity = pd.Series(equity_curve)
    equity.index = pd.to_datetime(equity.index)
    monthly = equity.resample("ME").last().pct_change().dropna() * 100
    years  = sorted(monthly.index.year.unique())
    mnames = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    z = []
    for yr in years:
        row = []
        for mo in range(1, 13):
            vals = monthly[(monthly.index.year == yr) & (monthly.index.month == mo)]
            row.append(round(float(vals.iloc[0]), 2) if len(vals) > 0 else None)
        z.append(row)
    text = [[f"{v:.1f}%" if v is not None else "" for v in row] for row in z]
    fig = go.Figure(go.Heatmap(
        z=z, x=mnames, y=[str(y) for y in years],
        text=text, texttemplate="%{text}",
        colorscale=[[0, "#EF4444"], [0.5, "#1F2937"], [1, "#22C55E"]],
        zmid=0, hoverongaps=False,
    ))
    fig.update_layout(title=title, height=max(180, len(years)*40+80),
                      margin=dict(l=60, r=20, t=40, b=20))
    return fig


def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    register_twquant_dark_template()
    ctx = render_global_sidebar(show_stock=True, show_dates=True, default_years=3)
    stock_id = ctx["stock_id"]
    start    = ctx["start_date"]
    end      = ctx["end_date"]

    with st.sidebar:
        st.header("A/B 策略設定")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f"<span style='color:{_COLOR_A}'>**策略 A**</span>", unsafe_allow_html=True)
            strat_a = st.selectbox("A", _STRAT_KEYS, index=0, label_visibility="collapsed",
                                   format_func=lambda k: _STRAT_LABEL.get(k, k))
        with col_b:
            st.markdown(f"<span style='color:{_COLOR_B}'>**策略 B**</span>", unsafe_allow_html=True)
            strat_b = st.selectbox("B", _STRAT_KEYS, index=1, label_visibility="collapsed",
                                   format_func=lambda k: _STRAT_LABEL.get(k, k))
        run_btn = st.button("▶ 開始比較", type="primary", use_container_width=True)

    st.title("🆚 策略 A/B 並排比較器")
    st.caption(f"標的 **{stock_id}** ｜ {start} ~ {end} ｜ 初始資金 $1,000,000")

    if not run_btn:
        st.info("在左側選擇兩種策略，點擊「▶ 開始比較」即可並排比較績效。")
        st.markdown("""
| 策略 | 進場條件 |
|------|---------|
| F｜動能精選 ★ | ret₂₀>5% + Close>MA60 |
| H｜量價突破 | Close>20日高點 + 量比>1.5x + MA60 + RSI<76 |
| L｜三線扭轉 | MA5>MA20>MA60 剛成立第一天 + RSI<72 |
| M｜RAM動能 | RAM=ret₂₀/(σ₂₀×√20)>0.7 + MA60>MA120 |
| N｜唐奇安突破 | Close>DC_upper(20) + 量比>1.2x + MA60 + RSI<76 |
""")
        return

    with st.spinner("回測中..."):
        ma = _run_one(stock_id, str(start), str(end), strat_a)
        mb = _run_one(stock_id, str(start), str(end), strat_b)
        bh = _run_bh(stock_id, str(start), str(end))

    label_a = _STRAT_LABEL.get(strat_a, strat_a)
    label_b = _STRAT_LABEL.get(strat_b, strat_b)

    # ── 績效對比表 ──
    st.subheader("📊 績效對比")
    metrics_rows = []
    for label, m, color in [(label_a, ma, _COLOR_A), (label_b, mb, _COLOR_B), ("買入持有(基準)", bh, _COLOR_BH)]:
        if m is None:
            metrics_rows.append({"策略": label, "總報酬": "N/A", "最大回撤": "N/A",
                                  "Sharpe": "N/A", "Sortino": "N/A", "勝率": "N/A", "交易次數": "N/A"})
        else:
            metrics_rows.append({
                "策略": label,
                "總報酬": f"{m['total_return']:.1%}",
                "最大回撤": f"{m['max_drawdown']:.1%}",
                "Sharpe": f"{m['sharpe_ratio']:.2f}",
                "Sortino": f"{m['sortino_ratio']:.2f}",
                "勝率": f"{m['win_rate']:.1%}" if not pd.isna(m["win_rate"]) else "N/A",
                "交易次數": m["total_trades"],
            })
    st.dataframe(pd.DataFrame(metrics_rows), use_container_width=True, hide_index=True)

    # ── 資金曲線疊圖 ──
    st.divider()
    st.subheader("📈 資金曲線（同時間軸）")
    fig = go.Figure()
    for label, m, color, dash in [
        (label_a, ma, _COLOR_A, "solid"),
        (label_b, mb, _COLOR_B, "solid"),
        ("買入持有(基準)", bh, _COLOR_BH, "dash"),
    ]:
        if m is None:
            continue
        eq = pd.Series(m["equity_curve"])
        eq.index = pd.to_datetime(eq.index)
        fig.add_trace(go.Scatter(x=eq.index, y=eq.values, name=label,
                                 line=dict(color=color, width=2, dash=dash)))
    fig.update_layout(height=440, margin=dict(l=40, r=20, t=20, b=20),
                      hovermode="x unified", yaxis_title="資產淨值（元）",
                      legend=dict(orientation="h", y=-0.15))
    st.plotly_chart(fig, use_container_width=True)

    # ── 月報酬熱力圖並排 ──
    st.divider()
    st.subheader("📅 月度報酬熱力圖")
    col_ha, col_hb = st.columns(2)
    if ma:
        with col_ha:
            st.plotly_chart(_monthly_heatmap(ma["equity_curve"], label_a, _COLOR_A),
                            use_container_width=True)
    if mb:
        with col_hb:
            st.plotly_chart(_monthly_heatmap(mb["equity_curve"], label_b, _COLOR_B),
                            use_container_width=True)

    # ── 交易明細 ──
    if ma or mb:
        st.divider()
        st.subheader("📋 交易明細")
        tc_a, tc_b = st.columns(2)
        with tc_a:
            if ma and ma.get("trades"):
                st.markdown(f"<b style='color:{_COLOR_A}'>{label_a}</b>（最近 15 筆）", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(ma["trades"]).tail(15), use_container_width=True, hide_index=True)
        with tc_b:
            if mb and mb.get("trades"):
                st.markdown(f"<b style='color:{_COLOR_B}'>{label_b}</b>（最近 15 筆）", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(mb["trades"]).tail(15), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
