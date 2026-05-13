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
    import sqlite3
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    end   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start = (today - pd.DateOffset(months=months)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    db_rows = conn.execute(
        "SELECT u.sector, u.stock_id FROM _universe u "
        "JOIN _symbols s ON s.name = 'daily_price/' || u.stock_id "
        "WHERE u.sector != ''"
    ).fetchall()
    conn.close()
    sector_stocks: dict[str, list[str]] = {}
    for sector, sid in db_rows:
        sector_stocks.setdefault(sector, []).append(sid)
    rows = []
    for sector, sids in sector_stocks.items():
        rets = []
        for sid in sids[:15]:
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
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    render_global_sidebar(show_stock=False, show_dates=False)

    render_tv_ticker_tape()
    st.title("🏛️ 市場總覽")

    # ── 市場狀態快報 ──────────────────────────────────────────────────────
    @st.cache_data(ttl=1800)
    def _market_regime():
        from twquant.data.storage import SQLiteStorage
        from twquant.indicators.basic import compute_rsi, compute_ma
        storage = SQLiteStorage(DB_PATH)
        df0 = storage.load("daily_price/0050")
        if df0.empty: return None
        cl = df0["close"].astype(float)
        ma60 = float(cl.rolling(60).mean().iloc[-1])
        price = float(cl.iloc[-1])
        rsi = float(compute_rsi(cl, 14).iloc[-1])
        bull = price > ma60

        all_sids = list({sid for sec in ANALYST_UNIVERSE.values() for sid, _ in sec})
        overbought, momentum, oversold = [], [], []
        for sid in all_sids:
            dfc = storage.load(f"daily_price/{sid}")
            if len(dfc) < 60: continue
            c = dfc["close"].astype(float)
            r = float(compute_rsi(c, 14).iloc[-1])
            m20 = float(compute_ma(c, 20).iloc[-1])
            m60 = float(compute_ma(c, 60).iloc[-1])
            p = float(c.iloc[-1])
            ret20 = (p/float(c.iloc[-21])-1)*100 if len(c)>=21 else 0
            if r > 80: overbought.append(f"{sid}({get_name(sid)}) RSI={r:.0f}")
            elif p > m20 > m60 and 45 <= r <= 72: momentum.append((sid, ret20))
            elif r < 35: oversold.append(f"{sid}({get_name(sid)}) RSI={r:.0f}")
        momentum.sort(key=lambda x: -x[1])
        return {"bull": bull, "price": price, "ma60": ma60, "rsi_0050": rsi,
                "overbought": overbought, "momentum": momentum[:5], "oversold": oversold}

    regime = _market_regime()
    if regime:
        bull = regime["bull"]
        regime_color = "#22C55E" if bull else "#EF4444"
        regime_text = "🐂 牛市" if bull else "🐻 熊市"
        st.markdown(
            f"<div style='background:{regime_color}22;border-left:4px solid {regime_color};"
            f"padding:10px 16px;border-radius:4px;margin-bottom:8px'>"
            f"<b style='color:{regime_color}'>{regime_text}</b> — "
            f"0050 = {regime['price']:.1f} / MA60 = {regime['ma60']:.1f} / RSI = {regime['rsi_0050']:.0f}"
            f"</div>",
            unsafe_allow_html=True,
        )
        col_mo, col_hot, col_cool = st.columns(3)
        with col_mo:
            st.caption("🚀 **動能前5（趨勢+RSI健康）**")
            for sid, ret in regime["momentum"]:
                st.markdown(f"- {sid} {get_name(sid)}　`{ret:+.1f}%`")
        with col_hot:
            if regime["overbought"]:
                st.caption(f"⚠️ **過熱警告（RSI>80）** {len(regime['overbought'])} 支")
                for s in regime["overbought"]: st.markdown(f"- {s}")
            else:
                st.caption("⚠️ 過熱警告：無")
        with col_cool:
            if regime["oversold"]:
                st.caption(f"👀 **超賣觀察（RSI<35）** {len(regime['oversold'])} 支")
                for s in regime["oversold"]: st.markdown(f"- {s}")
            else:
                st.caption("👀 超賣觀察：無（市場偏熱）")

    st.divider()

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
        st.subheader("🔄 板塊輪動 Treemap（近3月）")
        perf = _sector_performance(3)
        if perf:
            dfp = pd.DataFrame(perf)
            ret_col = "3月報酬(%)"
            fig_s = go.Figure(go.Treemap(
                labels=dfp["板塊"],
                values=dfp["樣本數"],
                parents=[""] * len(dfp),
                customdata=dfp[ret_col],
                texttemplate="%{label}<br>%{customdata:+.1f}%",
                marker=dict(
                    colors=dfp[ret_col],
                    colorscale=[[0,"#22C55E"],[0.5,"#1F2937"],[1,"#EF4444"]],
                    cmid=0,
                ),
                hovertemplate="<b>%{label}</b><br>報酬: %{customdata:+.1f}%<br>樣本: %{value}<extra></extra>",
            ))
            fig_s.update_layout(height=350, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_s, use_container_width=True)

    # ── ⚖️ 兩板塊強弱對比 ─────────────────────────────────────────────────
    with st.expander("⚖️ 兩板塊強弱對比"):
        from twquant.data.universe import list_sectors, list_by_sector_db
        all_sec = list_sectors()
        c1, c2 = st.columns(2)
        sec_a = c1.selectbox("板塊 A", all_sec, index=0, key="p01_sec_a")
        default_b = 1 if len(all_sec) > 1 else 0
        sec_b = c2.selectbox("板塊 B", all_sec, index=default_b, key="p01_sec_b")

        def _sec_perf(sec_name: str) -> dict:
            sids = [s for s, _ in list_by_sector_db(sec_name)]
            storage_local = SQLiteStorage(DB_PATH)
            r5, r20, r60 = [], [], []
            for sid in sids:
                df = storage_local.load(f"daily_price/{sid}")
                if df.empty or len(df) < 61:
                    continue
                cl = df["close"].astype(float)
                p = float(cl.iloc[-1])
                if len(cl) >= 6:  r5.append(p / float(cl.iloc[-6]) - 1)
                if len(cl) >= 21: r20.append(p / float(cl.iloc[-21]) - 1)
                if len(cl) >= 61: r60.append(p / float(cl.iloc[-61]) - 1)
            avg = lambda lst: sum(lst) / len(lst) * 100 if lst else 0
            return {"5d": avg(r5), "20d": avg(r20), "60d": avg(r60), "n": len(sids)}

        with st.spinner("計算中..."):
            pa = _sec_perf(sec_a)
            pb = _sec_perf(sec_b)
        cmp_fig = go.Figure(data=[
            go.Bar(name=sec_a, x=["近 5 日", "近 20 日", "近 60 日"],
                   y=[pa["5d"], pa["20d"], pa["60d"]],
                   marker_color="#3B82F6",
                   text=[f"{v:+.1f}%" for v in (pa["5d"], pa["20d"], pa["60d"])],
                   textposition="outside"),
            go.Bar(name=sec_b, x=["近 5 日", "近 20 日", "近 60 日"],
                   y=[pb["5d"], pb["20d"], pb["60d"]],
                   marker_color="#F97316",
                   text=[f"{v:+.1f}%" for v in (pb["5d"], pb["20d"], pb["60d"])],
                   textposition="outside"),
        ])
        cmp_fig.update_layout(height=300, barmode="group", yaxis_title="平均報酬 %",
                              hovermode="x unified",
                              legend=dict(orientation="h", y=1.1),
                              margin=dict(l=40, r=20, t=20, b=20))
        cmp_fig.add_hline(y=0, line_color="#4B5563", line_width=1)
        st.plotly_chart(cmp_fig, use_container_width=True)
        sl, sr = st.columns(2)
        sl.caption(f"**{sec_a}** 樣本：{pa['n']} 支")
        sr.caption(f"**{sec_b}** 樣本：{pb['n']} 支")

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
