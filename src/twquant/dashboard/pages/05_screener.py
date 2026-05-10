"""Page 5：多因子選股工具 - 分析師用快速篩選（DB 優先，API 備援）"""

import sys, math, time, datetime, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="選股工具", page_icon="🔍", layout="wide")

DB_PATH = "data/twquant.db"

DEFAULT_LIST = [
    "2330:台積電", "2454:聯發科", "2303:聯電",   "2308:台達電",
    "2317:鴻海",   "3008:大立光", "2412:中華電",  "2002:中鋼",
    "2882:國泰金", "2881:富邦金", "2886:兆豐金",  "2891:中信金",
    "2603:長榮",   "2609:陽明",   "2615:萬海",
    "0050:元大台50", "0056:元大高息", "00878:國泰永續",
]
DEFAULT_SIDS = [s.split(":")[0] for s in DEFAULT_LIST]


# ─────────────────────────────────────────────────────────────
# 背景同步（cache_resource 確保 Streamlit 只啟動一次執行緒）
# ─────────────────────────────────────────────────────────────
@st.cache_resource
def _start_sync():
    from twquant.data.auto_sync import ensure_running
    ensure_running(DB_PATH, DEFAULT_SIDS)
    return True


# ─────────────────────────────────────────────────────────────
# 資料載入（DB 優先，缺失才呼叫 API）
# ─────────────────────────────────────────────────────────────
@st.cache_data(ttl=1800)
def _load_stock(sid: str, start: str, end: str):
    import pandas as pd
    from twquant.data.storage import SQLiteStorage

    storage = SQLiteStorage(DB_PATH)
    df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
    if len(df) >= 60:
        df["date"] = pd.to_datetime(df["date"])
        return df

    # DB 資料不足 → 備援 API
    try:
        from twquant.data.providers.finmind import FinMindProvider
        from twquant.dashboard.config import get_finmind_token
        provider = FinMindProvider(token=get_finmind_token() or "")
        df_api = provider.fetch_daily(sid, start, end)
        df_api["date"] = pd.to_datetime(df_api["date"])
        # 寫回 DB 供下次使用
        storage.upsert(f"daily_price/{sid}", df_api)
        return df_api
    except Exception:
        return pd.DataFrame()


# ─────────────────────────────────────────────────────────────
# 選股因子計算
# ─────────────────────────────────────────────────────────────
def compute_score(df):
    import numpy as np
    import pandas as pd
    from twquant.indicators.basic import (
        compute_rsi, compute_macd, compute_ma, compute_bollinger,
    )

    close  = df['close'].astype(float)
    high   = df['high'].astype(float)
    low    = df['low'].astype(float)
    volume = df['volume'].astype(float)
    price  = close.iloc[-1]
    n      = len(df)

    ma5   = compute_ma(close, 5).iloc[-1]
    ma20  = compute_ma(close, 20).iloc[-1]
    ma60  = compute_ma(close, 60).iloc[-1] if n >= 60 else float('nan')
    rsi   = compute_rsi(close, 14).iloc[-1]
    _, _, hist  = compute_macd(close)
    hist_v      = hist.iloc[-1]
    hist_prev   = hist.iloc[-2]
    upper_bb, _, lower_bb = compute_bollinger(close)
    bb_up  = upper_bb.iloc[-1]
    bb_lo  = lower_bb.iloc[-1]

    vol5   = volume.iloc[-5:].mean()
    vol20  = volume.iloc[-20:].mean()
    vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0

    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]

    ret5   = (price / close.iloc[-6]  - 1) if n >= 6  else float('nan')
    ret20  = (price / close.iloc[-21] - 1) if n >= 21 else float('nan')
    ret60  = (price / close.iloc[-61] - 1) if n >= 61 else float('nan')

    high60 = close.iloc[-60:].max() if n >= 60 else close.max()
    dd     = (price / high60 - 1)
    bb_pos = (price - bb_lo) / (bb_up - bb_lo) if (bb_up - bb_lo) > 0 else 0.5
    dr = close.pct_change().dropna()
    vol_20d = dr.iloc[-20:].std() * math.sqrt(252) * 100

    stop = max(price - 1.5 * atr14, ma20 * 0.99)
    risk = price - stop
    target = price + risk * 2

    score = 0; signals = []

    if not math.isnan(ma60):
        if price > ma20 > ma60:
            score += 3; signals.append("✅ 多頭排列")
        elif price > ma20:
            score += 2; signals.append("✅ 短線多頭")
        elif price > ma60:
            score += 1; signals.append("➕ 中線支撐")
        else:
            score -= 1; signals.append("⚠️ 跌破均線")
    if not math.isnan(rsi):
        if 45 <= rsi <= 65:
            score += 3; signals.append(f"✅ RSI健康({rsi:.0f})")
        elif 65 < rsi <= 72:
            score += 1; signals.append(f"➕ RSI偏強({rsi:.0f})")
        elif 35 <= rsi < 45:
            score += 1; signals.append(f"➕ RSI超賣({rsi:.0f})")
        elif rsi > 72:
            score -= 2; signals.append(f"🔴 RSI超買({rsi:.0f})")
        else:
            score -= 1; signals.append(f"⚠️ RSI弱({rsi:.0f})")
    if not math.isnan(hist_v):
        if hist_v > 0 and hist_prev <= 0:
            score += 3; signals.append("🚀 MACD金叉")
        elif hist_v > 0 and hist_prev > 0:
            score += 2; signals.append("✅ MACD正值")
        elif hist_v <= 0 and hist_prev > 0:
            score -= 2; signals.append("🔴 MACD死叉")
        else:
            score -= 1; signals.append("⚠️ MACD負值")
    if vol_ratio >= 1.3:
        score += 2; signals.append(f"✅ 量增({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.0:
        score += 1; signals.append(f"➕ 量平({vol_ratio:.1f}x)")
    else:
        score -= 1; signals.append(f"⚠️ 量縮({vol_ratio:.1f}x)")
    if 0.5 <= bb_pos <= 0.85:
        score += 2; signals.append(f"✅ 布林健康({bb_pos:.0%})")
    elif bb_pos > 0.85:
        score -= 1; signals.append(f"⚠️ 近布林上軌({bb_pos:.0%})")
    elif bb_pos < 0.2:
        score += 1; signals.append("➕ 超賣反彈機會")
    if dd < -0.20:
        score -= 2; signals.append(f"🔴 距高點{dd:.0%}")
    elif dd < -0.12:
        score -= 1; signals.append(f"⚠️ 距高點{dd:.0%}")
    elif dd >= -0.05:
        score += 1; signals.append(f"✅ 接近高點({dd:.0%})")
    if not math.isnan(ret5):
        if ret5 > 0.03:
            score += 1; signals.append(f"✅ 週漲{ret5:.1%}")
        elif ret5 < -0.05:
            score -= 1; signals.append(f"⚠️ 週跌{ret5:.1%}")
    if atr14 / price * 100 > 4.0:
        score -= 1; signals.append(f"⚠️ 高波動(ATR={atr14/price*100:.1f}%)")

    return {
        'price': price, 'ma5': ma5, 'ma20': ma20, 'ma60': ma60,
        'rsi': rsi, 'macd_hist': hist_v, 'vol_ratio': vol_ratio,
        'bb_pos': bb_pos, 'ret5': ret5, 'ret20': ret20, 'ret60': ret60,
        'dd_from_high': dd, 'atr_pct': atr14 / price * 100,
        'vol_20d': vol_20d, 'stop_loss': stop, 'stop_pct': (stop/price-1)*100,
        'target': target, 'rr_ratio': abs((target/price-1) / ((stop/price-1)+1e-9)),
        'score': score, 'signals': signals,
    }


def _check_strategies(df) -> list[str]:
    """檢查最新 K 棒是否觸發 5 種生產策略進場訊號，回傳觸發的標籤清單。"""
    from twquant.strategy.registry import get_strategy
    if len(df) < 120:
        return []
    triggered = []
    for key, label in [
        ("momentum_concentrate", "F"), ("volume_breakout", "H"),
        ("triple_ma_twist", "L"),      ("risk_adj_momentum", "M"),
        ("donchian_breakout", "N"),
    ]:
        try:
            entries, _ = get_strategy(key).generate_signals(df)
            if len(entries) > 0 and entries[-1]:
                triggered.append(label)
        except Exception:
            pass
    return triggered


@st.cache_data(ttl=1800)
def run_screener(stock_list: tuple, start: str, end: str) -> list[dict]:
    from twquant.data.universe import get_name
    results = []
    for item in stock_list:
        if ":" in item:
            sid, name = item.split(":", 1)
        else:
            sid = item.strip()
            name = get_name(sid)
        df = _load_stock(sid, start, end)
        if df is None or len(df) < 60:
            continue
        try:
            r = compute_score(df)
            r['sid'] = sid; r['name'] = name
            r['strategy_signals'] = _check_strategies(df)
            results.append(r)
        except Exception:
            pass
    return sorted(results, key=lambda x: -x['score'])


@st.cache_data(ttl=3600, show_spinner=False)
def _run_alpha_scan(stock_list: tuple, start: str, end: str,
                    strat_keys: tuple, min_trades: int = 3) -> list[dict]:
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
                    "策略": key, "總報酬": m["total_return"],
                    "超額報酬α": m["total_return"] - bench_ret,
                    "Sharpe": m["sharpe_ratio"], "最大回撤": m["max_drawdown"],
                    "勝率": m["win_rate"], "交易次數": int(entries.sum()),
                })
            except Exception:
                pass
    return sorted(rows, key=lambda r: -(r["Sharpe"] if r["Sharpe"] == r["Sharpe"] else -99))


# ─────────────────────────────────────────────────────────────
# 主介面
# ─────────────────────────────────────────────────────────────
def main():
    import pandas as pd
    import plotly.graph_objects as go
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.data.auto_sync import last_sync_info
    from twquant.dashboard.components.global_sidebar import render_global_sidebar

    register_twquant_dark_template()
    render_global_sidebar(show_stock=False, show_dates=False)
    _start_sync()

    page_mode = st.radio("模式", ["📊 多因子選股", "🎯 Alpha 全宇宙掃描"], horizontal=True, label_visibility="collapsed")
    st.divider()

    # ══ Alpha 掃描模式 ══
    if page_mode == "🎯 Alpha 全宇宙掃描":
        st.title("🎯 Alpha 全宇宙掃描")
        st.caption("對已選股票池 × 5 種策略跑完整回測，找出最高 Sharpe 機會 | 快取 1 小時")
        _ALPHA_KEYS = ["momentum_concentrate","volume_breakout","triple_ma_twist","risk_adj_momentum","donchian_breakout"]
        _ALPHA_LABEL = {"momentum_concentrate":"F動能精選","volume_breakout":"H量價突破",
                        "triple_ma_twist":"L三線扭轉","risk_adj_momentum":"M RAM動能","donchian_breakout":"N唐奇安"}
        with st.sidebar:
            st.header("掃描設定")
            today = pd.Timestamp.today().normalize()
            a_start = st.date_input("起始", value=today - pd.DateOffset(years=3), key="alpha_start")
            a_end   = st.date_input("結束", value=today - pd.Timedelta(days=1), key="alpha_end")
            a_strats = st.multiselect("策略", _ALPHA_KEYS, default=_ALPHA_KEYS,
                                      format_func=lambda k: _ALPHA_LABEL.get(k, k))
            a_min = st.number_input("最少交易次數", 1, 20, 3)
            mode = st.radio("股票來源", ["產業板塊", "全宇宙", "自訂清單"], horizontal=True)
            from twquant.data.universe import ANALYST_UNIVERSE, get_name, list_sectors
            if mode == "產業板塊":
                sector = st.selectbox("產業", list_sectors())
                stock_list = tuple(s for s, _ in ANALYST_UNIVERSE[sector])
            elif mode == "全宇宙":
                from twquant.data.storage import SQLiteStorage
                _syms = SQLiteStorage(DB_PATH).list_symbols()
                stock_list = tuple(s.replace("daily_price/", "") for s in _syms if s.startswith("daily_price/"))
                st.caption(f"全宇宙：{len(stock_list)} 支")
            else:
                raw = st.text_area("自訂清單", value="\n".join(DEFAULT_LIST), height=150)
                stock_list = tuple(s.strip() for s in raw.strip().split("\n") if s.strip())
            scan_btn = st.button("🚀 開始掃描", type="primary", use_container_width=True)
        if not scan_btn:
            st.info("設定左側參數後點擊「開始掃描」。首次可能需 1-3 分鐘，結果快取 1 小時。")
            return
        with st.spinner(f"掃描 {len(stock_list)} 支股票 × {len(a_strats)} 種策略..."):
            scan_rows = _run_alpha_scan(stock_list, str(a_start), str(a_end), tuple(a_strats), int(a_min))
        if not scan_rows:
            st.warning("掃描無結果，請確認 DB 中已有足夠資料（執行 seed_data.py）")
            return
        df_scan = pd.DataFrame(scan_rows)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("掃描組合數", len(df_scan))
        c2.metric("正超額報酬", int((df_scan["超額報酬α"] > 0).sum()))
        c3.metric("最佳 Sharpe", f"{df_scan['Sharpe'].max():.2f}")
        c4.metric("最佳超額", f"{df_scan['超額報酬α'].max():.1%}")
        display = df_scan.copy()
        for col in ["總報酬", "超額報酬α", "最大回撤"]:
            display[col] = display[col].apply(lambda v: f"{v:+.1%}")
        display["Sharpe"] = display["Sharpe"].apply(lambda v: f"{v:.2f}")
        display["勝率"] = display["勝率"].apply(lambda v: f"{v:.1%}" if v == v else "N/A")
        display["策略"] = display["策略"].apply(lambda k: _ALPHA_LABEL.get(k, k))
        st.dataframe(display[["代號","名稱","板塊","策略","總報酬","超額報酬α","Sharpe","最大回撤","勝率","交易次數"]],
                     use_container_width=True, hide_index=True, height=500)
        csv = df_scan.to_csv(index=False).encode("utf-8-sig")
        st.download_button("⬇️ 下載 CSV", csv, f"alpha_{a_start}_{a_end}.csv", "text/csv")
        return

    st.title("🔍 多因子選股工具")

    # ── 同步狀態列 ──
    info = last_sync_info(DB_PATH, DEFAULT_SIDS)
    sync_icon = "🟢" if info["up_to_date"] == info["total"] else "🟡"
    mh_txt = "盤中（30 分鐘同步）" if info["is_market_hours"] else "盤後（60 分鐘同步）"
    thread_txt = "背景同步執行中" if info["thread_alive"] else "同步執行緒未啟動"
    st.caption(
        f"{sync_icon} 資料庫：{info['up_to_date']}/{info['total']} 檔最新  |  "
        f"{mh_txt}  |  {thread_txt}  |  資料來源：系統 DB（FinMind 備援）"
    )

    from twquant.data.universe import ANALYST_UNIVERSE, get_name, list_sectors

    with st.sidebar:
        st.header("篩選設定")
        today = pd.Timestamp.today().normalize()
        end_date = (today - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (today - pd.DateOffset(months=18)).strftime('%Y-%m-%d')

        # ── 股票來源切換 ──
        mode = st.radio("股票來源", ["產業板塊", "全宇宙", "自訂清單"], horizontal=True)

        if mode == "產業板塊":
            sector = st.selectbox("選擇產業", list_sectors())
            sector_sids = [sid for sid, _ in ANALYST_UNIVERSE[sector]]
            selected_sids = st.multiselect(
                "股票（可移除）",
                options=sector_sids,
                default=sector_sids,
                format_func=lambda s: f"{s} {get_name(s)}",
            )
            stock_list = tuple(selected_sids)
        elif mode == "全宇宙":
            from twquant.data.storage import SQLiteStorage
            _db = SQLiteStorage(DB_PATH)
            _syms = _db.list_symbols()
            all_sids_dedup = [s.replace("daily_price/", "") for s in _syms if s.startswith("daily_price/")]
            st.caption(f"全宇宙：DB 中共 {len(all_sids_dedup)} 支已入庫股票")
            stock_list = tuple(all_sids_dedup)
        else:
            raw_input = st.text_area(
                "自訂清單（代碼:名稱 或純代碼，每行一個）",
                value="\n".join(DEFAULT_LIST),
                height=250,
            )
            stock_list = tuple(s.strip() for s in raw_input.strip().split("\n") if s.strip())

        st.divider()
        min_score = st.slider("最低得分篩選", -5, 14, 6)
        sort_by = st.selectbox("排序依據", ["得分", "週報酬", "月報酬", "RSI"])
        run_btn = st.button("🔍 開始選股", type="primary", use_container_width=True)
        st.caption(f"資料區間：{start_date} ~ {end_date}")
        st.caption("⏱ 快取 30 分鐘，資料來源：系統 DB")

    if not run_btn:
        st.info("設定左側選股條件後，點擊「開始選股」")
        with st.expander("📖 評分說明"):
            st.markdown("""
**多因子評分系統（滿分約 14 分）**

| 因子 | 正面訊號 | 負面訊號 |
|------|---------|---------|
| 趨勢排列 | MA多頭排列 +3 | 跌破均線 -1 |
| RSI動能 | 45-65健康 +3 | >72超買 -2 |
| MACD | 金叉 +3 / 正值 +2 | 死叉 -2 |
| 量能 | 量增1.3x +2 | 量縮 -1 |
| 布林位置 | 中軌以上(50-85%) +2 | 近上軌 -1 |
| 距高點 | 近高點 +1 | 回撤>20% -2 |
| 週動能 | 週漲>3% +1 | 週跌>5% -1 |
| 波動懲罰 | — | ATR>4% -1 |

> **推薦閾值**：≥8分積極關注，6-7分觀察，≤5分迴避
            """)
        return

    if not stock_list:
        st.error("請選擇至少一支股票")
        return

    with st.spinner(f"從系統資料庫分析 {len(stock_list)} 檔股票..."):
        results = run_screener(stock_list, start_date, end_date)

    if not results:
        st.error("無法取得分析結果，請確認資料庫是否已初始化")
        return

    # 排序
    sort_key_map = {
        "得分": lambda r: -r["score"],
        "週報酬": lambda r: -(r.get("ret5") or -99),
        "月報酬": lambda r: -(r.get("ret20") or -99),
        "RSI": lambda r: -(r.get("rsi") or 0),
    }
    results = sorted(results, key=sort_key_map.get(sort_by, lambda r: -r["score"]))

    strong = [r for r in results if r['score'] >= 8]
    watch  = [r for r in results if 5 < r['score'] < 8]
    avoid  = [r for r in results if r['score'] <= 5]

    c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1])
    c1.metric("分析標的", len(results))
    c2.metric("🟢 積極關注", len(strong))
    c3.metric("🟡 觀察中", len(watch))
    c4.metric("🔴 迴避", len(avoid))

    # CSV 匯出
    csv_rows = []
    for r in results:
        csv_rows.append({
            "代號": r["sid"], "名稱": r["name"], "得分": r["score"],
            "現價": r["price"], "RSI": f"{r['rsi']:.1f}",
            "MA5": f"{r['ma5']:.2f}", "MA20": f"{r['ma20']:.2f}",
            "週報酬": f"{r['ret5']:+.1%}" if r.get("ret5") and not math.isnan(r["ret5"]) else "N/A",
            "月報酬": f"{r['ret20']:+.1%}" if r.get("ret20") and not math.isnan(r["ret20"]) else "N/A",
            "季報酬": f"{r['ret60']:+.1%}" if r.get("ret60") and not math.isnan(r["ret60"]) else "N/A",
            "量比": f"{r['vol_ratio']:.2f}x",
            "ATR%": f"{r['atr_pct']:.1f}%",
            "年化波動": f"{r['vol_20d']:.1f}%",
            "停損": f"{r['stop_loss']:.2f}", "目標R1": f"{r['target']:.2f}",
            "觸發策略": " ".join(r.get("strategy_signals", [])),
            "訊號": " | ".join(r.get("signals", [])),
        })
    csv_str = pd.DataFrame(csv_rows).to_csv(index=False, encoding="utf-8-sig")
    c5.download_button(
        "⬇️ 匯出 CSV",
        data=csv_str.encode("utf-8-sig"),
        file_name=f"screener_{pd.Timestamp.today().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    st.divider()

    # ── 評分總覽圖 ──
    df_r = pd.DataFrame(results)
    colors = ['#22C55E' if s >= 8 else ('#FBBF24' if s >= 6 else '#EF4444') for s in df_r['score']]
    fig_score = go.Figure(go.Bar(
        x=df_r['name'] + ' (' + df_r['sid'] + ')',
        y=df_r['score'],
        marker_color=colors,
        text=df_r['score'],
        textposition='outside',
    ))
    fig_score.update_layout(
        title="多因子評分排行", height=320,
        margin=dict(l=20, r=20, t=40, b=60),
        yaxis_title="得分",
        xaxis_tickangle=-30,
    )
    st.plotly_chart(fig_score, use_container_width=True)

    # ── 積極關注清單 ──
    filtered = [r for r in results if r['score'] >= min_score]
    if strong:
        st.subheader("🟢 積極關注（得分 ≥ 8）")
        for r in filtered:
            if r['score'] < 8:
                continue
            with st.container(border=True):
                col_title, col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns([2, 1, 1, 1, 1, 1])
                ret5_s  = f"{r['ret5']:+.1%}"  if r['ret5']  and not math.isnan(r['ret5'])  else "N/A"
                ret20_s = f"{r['ret20']:+.1%}" if r['ret20'] and not math.isnan(r['ret20']) else "N/A"

                with col_title:
                    st.markdown(f"**{r['sid']} {r['name']}**")
                    score_color = '#22C55E' if r['score'] >= 8 else '#FBBF24'
                    st.markdown(f"<span style='color:{score_color};font-size:1.2rem;font-weight:bold'>得分：{r['score']}</span>",
                                unsafe_allow_html=True)
                    sigs = r.get("strategy_signals", [])
                    if sigs:
                        st.markdown(f"📡 **策略訊號：{'  '.join(sigs)}**")
                col_m1.metric("現價",  f"{r['price']:.2f}")
                col_m2.metric("RSI",   f"{r['rsi']:.1f}")
                col_m3.metric("週報酬", ret5_s)
                col_m4.metric("停損",  f"{r['stop_loss']:.2f} ({r['stop_pct']:+.1f}%)")
                col_m5.metric("目標R1", f"{r['target']:.2f} ({(r['target']/r['price']-1)*100:+.1f}%)")

                with st.expander("訊號詳情"):
                    sig_cols = st.columns(2)
                    for i, sig in enumerate(r['signals']):
                        sig_cols[i % 2].write(sig)
                    st.caption(f"月報酬: {ret20_s} | 量比: {r['vol_ratio']:.2f}x | ATR: {r['atr_pct']:.1f}% | 年化波動: {r['vol_20d']:.1f}%")

    # ── 觀察清單 ──
    watch_items = [r for r in results if 5 < r['score'] < 8]
    if watch_items:
        st.subheader("🟡 觀察中（得分 6-7）")
        rows = []
        for r in watch_items:
            rows.append({
                '代號': r['sid'], '名稱': r['name'],
                '現價': r['price'], 'RSI': f"{r['rsi']:.1f}",
                '週漲跌': f"{r['ret5']:+.1%}" if r['ret5'] and not math.isnan(r['ret5']) else "N/A",
                '量比': f"{r['vol_ratio']:.2f}x",
                '得分': r['score'],
                '觸發策略': ' '.join(r.get('strategy_signals', [])),
                '關鍵訊號': ' | '.join(r['signals'][:3]),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── 迴避清單 ──
    with st.expander("🔴 迴避標的"):
        avoid_items = [r for r in results if r['score'] <= 5]
        for r in avoid_items:
            ret5_s = f"{r['ret5']:+.1%}" if r['ret5'] and not math.isnan(r['ret5']) else "N/A"
            st.write(f"**{r['sid']} {r['name']}** 得分:{r['score']} 週:{ret5_s} RSI:{r['rsi']:.1f} "
                     + ' | '.join(s for s in r['signals'] if '🔴' in s or '⚠️' in s))

    # ── 風報比氣泡圖 ──
    st.divider()
    st.subheader("📊 風險 vs 報酬 分布（泡泡大小 = 評分）")
    df_plot = pd.DataFrame([r for r in results if not math.isnan(r.get('ret20', float('nan')))])
    if not df_plot.empty:
        fig_bubble = go.Figure(go.Scatter(
            x=df_plot['vol_20d'],
            y=df_plot['ret20'] * 100,
            mode='markers+text',
            text=df_plot['name'] + '(' + df_plot['sid'] + ')',
            textposition='top center',
            marker=dict(
                size=[max(s * 3, 8) for s in df_plot['score']],
                color=df_plot['score'],
                colorscale='RdYlGn',
                showscale=True,
                colorbar=dict(title="評分"),
                line=dict(width=1, color='white'),
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "年化波動: %{x:.1f}%<br>"
                "月報酬: %{y:.1f}%<br>"
                "<extra></extra>"
            ),
        ))
        fig_bubble.add_hline(y=0, line_color='#6B7280', line_dash='dot', line_width=1)
        fig_bubble.update_layout(
            height=420,
            xaxis_title="年化波動率（越低越穩定）",
            yaxis_title="近月報酬率（%）",
            margin=dict(l=40, r=20, t=20, b=40),
        )
        st.plotly_chart(fig_bubble, use_container_width=True)


if __name__ == "__main__":
    main()
