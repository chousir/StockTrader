"""Page 5：多因子選股工具 - 分析師用快速篩選"""

import sys, math, time, datetime, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, "src")

import streamlit as st

st.set_page_config(page_title="選股工具", page_icon="🔍", layout="wide")


# ─────────────────────────────────────────────────────────────
# 選股因子計算
# ─────────────────────────────────────────────────────────────
def compute_score(df):
    """多因子評分，回傳 dict"""
    import numpy as np
    import pandas as pd
    from twquant.indicators.basic import (
        compute_rsi, compute_macd, compute_ma, compute_bollinger, compute_ema,
    )

    close  = df['close']
    high   = df['high']
    low    = df['low']
    volume = df['volume']
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

    # 停損/目標
    stop = max(price - 1.5 * atr14, ma20 * 0.99)
    risk = price - stop
    target = price + risk * 2

    score = 0; signals = []

    # 趨勢
    if not math.isnan(ma60):
        if price > ma20 > ma60:
            score += 3; signals.append("✅ 多頭排列")
        elif price > ma20:
            score += 2; signals.append("✅ 短線多頭")
        elif price > ma60:
            score += 1; signals.append("➕ 中線支撐")
        else:
            score -= 1; signals.append("⚠️ 跌破均線")
    # RSI
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
    # MACD
    if not math.isnan(hist_v):
        if hist_v > 0 and hist_prev <= 0:
            score += 3; signals.append("🚀 MACD金叉")
        elif hist_v > 0 and hist_prev > 0:
            score += 2; signals.append("✅ MACD正值")
        elif hist_v <= 0 and hist_prev > 0:
            score -= 2; signals.append("🔴 MACD死叉")
        else:
            score -= 1; signals.append("⚠️ MACD負值")
    # 量能
    if vol_ratio >= 1.3:
        score += 2; signals.append(f"✅ 量增({vol_ratio:.1f}x)")
    elif vol_ratio >= 1.0:
        score += 1; signals.append(f"➕ 量平({vol_ratio:.1f}x)")
    else:
        score -= 1; signals.append(f"⚠️ 量縮({vol_ratio:.1f}x)")
    # 布林
    if 0.5 <= bb_pos <= 0.85:
        score += 2; signals.append(f"✅ 布林健康({bb_pos:.0%})")
    elif bb_pos > 0.85:
        score -= 1; signals.append(f"⚠️ 近布林上軌({bb_pos:.0%})")
    elif bb_pos < 0.2:
        score += 1; signals.append("➕ 超賣反彈機會")
    # 回撤
    if dd < -0.20:
        score -= 2; signals.append(f"🔴 距高點{dd:.0%}")
    elif dd < -0.12:
        score -= 1; signals.append(f"⚠️ 距高點{dd:.0%}")
    elif dd >= -0.05:
        score += 1; signals.append(f"✅ 接近高點({dd:.0%})")
    # 週動能
    if not math.isnan(ret5):
        if ret5 > 0.03:
            score += 1; signals.append(f"✅ 週漲{ret5:.1%}")
        elif ret5 < -0.05:
            score -= 1; signals.append(f"⚠️ 週跌{ret5:.1%}")
    # 波動懲罰
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


@st.cache_data(ttl=3600)
def run_screener(stock_list: list[str], start: str, end: str) -> list[dict]:
    from twquant.data.providers.finmind import FinMindProvider
    provider = FinMindProvider(token="")
    results = []
    for sid_name in stock_list:
        sid, name = sid_name.split(":")
        try:
            df = provider.fetch_daily(sid, start, end)
            if len(df) < 60:
                continue
            r = compute_score(df)
            r['sid'] = sid
            r['name'] = name
            results.append(r)
            time.sleep(0.3)
        except Exception as e:
            st.warning(f"{sid} {name}: {e}")
    return sorted(results, key=lambda x: -x['score'])


# ─────────────────────────────────────────────────────────────
# 主介面
# ─────────────────────────────────────────────────────────────
def main():
    import pandas as pd
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    from twquant.dashboard.styles.plotly_theme import register_twquant_dark_template
    from twquant.dashboard.styles.theme import TWStockColors

    register_twquant_dark_template()

    st.title("🔍 多因子選股工具")

    DEFAULT_LIST = [
        "2330:台積電", "2454:聯發科", "2303:聯電",   "2308:台達電",
        "2317:鴻海",   "3008:大立光", "2412:中華電",  "2002:中鋼",
        "2882:國泰金", "2881:富邦金", "2886:兆豐金",  "2891:中信金",
        "2603:長榮",   "2609:陽明",   "2615:萬海",
        "0050:元大台50", "0056:元大高息", "00878:國泰永續",
    ]

    with st.sidebar:
        st.header("篩選設定")
        today = pd.Timestamp.today().normalize()
        end_date = (today - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
        start_date = (today - pd.DateOffset(months=18)).strftime('%Y-%m-%d')

        stock_input = st.text_area(
            "股票清單（格式：代碼:名稱，每行一個）",
            value="\n".join(DEFAULT_LIST),
            height=300,
        )
        min_score = st.slider("最低得分篩選", 0, 14, 6)
        run_btn = st.button("🔍 開始選股", type="primary", use_container_width=True)
        st.caption(f"資料區間：{start_date} ~ {end_date}")
        st.caption("⏱ 首次約 10-15 秒，快取 1 小時")

    if not run_btn:
        st.info("設定左側股票清單後，點擊「開始選股」")
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

    stock_list = [s.strip() for s in stock_input.strip().split('\n') if ':' in s.strip()]
    if not stock_list:
        st.error("請確認股票清單格式（代碼:名稱）")
        return

    with st.spinner(f"分析 {len(stock_list)} 檔股票中..."):
        results = run_screener(stock_list, start_date, end_date)

    if not results:
        st.error("無法取得分析結果")
        return

    # ── 摘要統計 ──
    strong = [r for r in results if r['score'] >= 8]
    watch  = [r for r in results if 5 < r['score'] < 8]
    avoid  = [r for r in results if r['score'] <= 5]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("分析標的", len(results))
    c2.metric("🟢 積極關注", len(strong))
    c3.metric("🟡 觀察中", len(watch))
    c4.metric("🔴 迴避", len(avoid))

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
    if strong:
        st.subheader("🟢 積極關注（得分 ≥ 8）")
        filtered = [r for r in results if r['score'] >= min_score]

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
