"""Page 1：市場總覽 - 大盤行情 + 板塊輪動 + 法人 + 資料新鮮度"""

import sys
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="市場總覽", page_icon="🏛️", layout="wide")

DB_PATH = "data/twquant.db"

from twquant.dashboard.components.tradingview_widgets import render_tv_ticker_tape


@st.cache_data(ttl=1800)
def _load_latest(sids: tuple, days_back: int = 7):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    start = (today - pd.Timedelta(days=days_back * 2)).strftime("%Y-%m-%d")
    end   = today.strftime("%Y-%m-%d")
    out = {}
    for sid in sids:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            out[sid] = df.sort_values("date")
    return out


@st.cache_data(ttl=1800)
def _sector_performance(months: int = 3):
    import pandas as pd
    from twquant.data.universe import ANALYST_UNIVERSE
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    end   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - pd.DateOffset(months=months)).strftime("%Y-%m-%d")
    rows = []
    for sector, stocks in ANALYST_UNIVERSE.items():
        rets = []
        for sid, _ in stocks:
            df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
            if len(df) >= 10:
                cl = df["close"].astype(float)
                rets.append((cl.iloc[-1] / cl.iloc[0] - 1) * 100)
        if rets:
            rows.append({"板塊": sector,
                         f"{months}月報酬(%)": round(sum(rets)/len(rets), 2),
                         "樣本數": len(rets)})
    return sorted(rows, key=lambda r: -r[f"{months}月報酬(%)"])


def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.data.universe import ANALYST_UNIVERSE, get_name
    from twquant.data.storage import SQLiteStorage

    render_tv_ticker_tape()
    st.title("🏛️ 市場總覽")

    # ── 關鍵行情卡 ────────────────────────────────────────────────────────
    key_sids = ("0050", "2330", "2454", "2603", "2882", "0056")
    labels = {"0050": "大盤(0050)", "2330": "台積電", "2454": "聯發科",
              "2603": "長榮航", "2882": "國泰金", "0056": "高息(0056)"}
    latest_data = _load_latest(key_sids)

    st.subheader("📌 今日關鍵行情")
    cols = st.columns(len(key_sids))
    for i, sid in enumerate(key_sids):
        df = latest_data.get(sid)
        if df is None or len(df) < 2:
            cols[i].metric(labels.get(sid, sid), "載入中"); continue
        p  = float(df.iloc[-1]["close"])
        pp = float(df.iloc[-2]["close"])
        chg = p - pp; chg_p = chg / pp * 100
        cols[i].metric(labels.get(sid, sid), f"{p:.2f}",
                       f"{chg:+.2f} ({chg_p:+.2f}%)")

    st.divider()

    # ── 0050 走勢 + 板塊輪動雙欄 ─────────────────────────────────────────
    col_chart, col_sector = st.columns([3, 2])

    with col_chart:
        st.subheader("📈 市場走勢（0050 近1年，大盤代理）")
        storage = SQLiteStorage(DB_PATH)
        today = pd.Timestamp.today().normalize()
        df0050 = storage.load("daily_price/0050",
                              start_date=(today - pd.DateOffset(years=1)).strftime("%Y-%m-%d"),
                              end_date=today.strftime("%Y-%m-%d"))
        if not df0050.empty:
            df0050["date"] = pd.to_datetime(df0050["date"])
            cl = df0050["close"].astype(float)
            fig_m = go.Figure()
            fig_m.add_trace(go.Scatter(x=df0050["date"], y=cl, name="0050",
                line=dict(color="#3B82F6", width=2),
                fill="tozeroy", fillcolor="rgba(59,130,246,0.06)"))
            fig_m.add_trace(go.Scatter(x=df0050["date"], y=cl.rolling(20).mean(),
                name="MA20", line=dict(color="#F97316", width=1.2, dash="dash")))
            fig_m.update_layout(height=300, margin=dict(l=40,r=10,t=10,b=20),
                hovermode="x unified", legend=dict(orientation="h", y=1.05))
            st.plotly_chart(fig_m, use_container_width=True)
        else:
            st.info("0050 資料載入中...")

    with col_sector:
        st.subheader("🔄 板塊輪動（近3月平均報酬）")
        perf = _sector_performance(3)
        if perf:
            dfp = pd.DataFrame(perf)
            colors = ["#22C55E" if v >= 0 else "#EF4444" for v in dfp["3月報酬(%)"]]
            fig_s = go.Figure(go.Bar(
                x=dfp["3月報酬(%)"], y=dfp["板塊"], orientation="h",
                marker_color=colors,
                text=[f"{v:+.1f}%" for v in dfp["3月報酬(%)"]],
                textposition="outside",
            ))
            fig_s.update_layout(height=300, margin=dict(l=10,r=60,t=10,b=20),
                                 xaxis_title="報酬率（%）")
            st.plotly_chart(fig_s, use_container_width=True)

    st.divider()

    # ── 板塊個股漲跌排行 ─────────────────────────────────────────────────
    st.subheader("📊 個股今日行情（依板塊）")
    all_sids = list({sid for sec in ANALYST_UNIVERSE.values()
                     for sid, _ in sec})
    daily_data = _load_latest(tuple(all_sids), days_back=5)

    rows_today = []
    for sid in all_sids:
        df = daily_data.get(sid)
        if df is None or len(df) < 2: continue
        p  = float(df.iloc[-1]["close"]); pp = float(df.iloc[-2]["close"])
        chg_p = (p - pp) / pp * 100
        sector = next((s for s, stocks in ANALYST_UNIVERSE.items()
                       if any(x[0] == sid for x in stocks)), "其他")
        rows_today.append({"代號": sid, "名稱": get_name(sid), "板塊": sector,
                           "現價": p, "漲跌幅(%)": round(chg_p, 2),
                           "成交量(張)": int(df.iloc[-1]["volume"]) // 1000})

    if rows_today:
        df_today = pd.DataFrame(rows_today).sort_values("漲跌幅(%)", ascending=False)
        sectors_tab = ["全部"] + list(ANALYST_UNIVERSE.keys())
        tabs = st.tabs(sectors_tab)
        for i, tab in enumerate(tabs):
            with tab:
                dff = df_today if i == 0 else df_today[df_today["板塊"] == sectors_tab[i]]
                # 漲跌幅上色
                def color_chg(val):
                    c = "#EF4444" if val > 0 else ("#22C55E" if val < 0 else "#9CA3AF")
                    return f"color: {c}"
                styled = dff.copy()
                styled["漲跌幅(%)"] = styled["漲跌幅(%)"].apply(lambda v: f"{v:+.2f}%")
                st.dataframe(styled[["代號","名稱","板塊","現價","漲跌幅(%)","成交量(張)"]],
                             use_container_width=True, hide_index=True, height=320)

    st.divider()

    # ── TradingView 熱力圖 ───────────────────────────────────────────────
    from twquant.dashboard.components.tradingview_widgets import render_tv_heatmap
    with st.container(border=True):
        st.subheader("🌡️ TradingView 台股類股熱力圖")
        render_tv_heatmap(height=480)

    st.divider()

    # ── 資料庫狀態 ────────────────────────────────────────────────────────
    with st.expander("🔧 資料庫狀態（點開查看）"):
        storage2 = SQLiteStorage(DB_PATH)
        syms = storage2.list_symbols()
        today_d = pd.Timestamp.today().date()
        status_rows = []
        for sym in sorted(syms):
            hwm = storage2.get_hwm(sym)
            sid = sym.replace("daily_price/", "")
            lag = (today_d - hwm).days if hwm else 999
            status = "🟢" if lag <= 3 else ("🟡" if lag <= 7 else "🔴")
            status_rows.append({"代號": sid, "名稱": get_name(sid),
                                 "最新資料日": str(hwm) if hwm else "無",
                                 "落後天數": lag, "狀態": status})
        ok = sum(1 for r in status_rows if r["狀態"] == "🟢")
        st.caption(f"入庫 {len(status_rows)} 支 | 🟢 最新 {ok} 支")
        st.dataframe(pd.DataFrame(status_rows), use_container_width=True,
                     hide_index=True, height=300)


if __name__ == "__main__":
    main()
