"""分析師桌面：市場快報 + 自選股輪盤 + 今日訊號 + 系統健康"""

import streamlit as st

st.set_page_config(
    page_title="twquant 台股量化", page_icon="📈", layout="wide",
    initial_sidebar_state="expanded",
)

import sys
sys.path.insert(0, "src")

from twquant.dashboard.components.onboarding import should_show_onboarding, render_onboarding_wizard

if should_show_onboarding():
    render_onboarding_wizard()
    st.stop()

DB_PATH = "data/twquant.db"
_POPULAR = ["2330", "2317", "2454", "2308", "0050"]
_STRAT_LABEL = {"momentum_concentrate": "F動能精選", "volume_breakout": "H量價突破"}

with st.sidebar:
    st.title("twquant 台股量化")
    from twquant.dashboard.config import get_broker_discount, get_init_cash
    st.caption(f"手續費折扣 {get_broker_discount():.0%}  初始資金 ${get_init_cash():,}")
    st.divider()
    if st.button("🔄 清除快取", use_container_width=True, key="home_clear"):
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=1800, show_spinner=False)
def _market_status() -> dict | None:
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    from twquant.indicators.basic import compute_rsi, compute_ma
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    df = storage.load("daily_price/0050",
                      start_date=(today - pd.DateOffset(days=90)).strftime("%Y-%m-%d"),
                      end_date=(today - pd.Timedelta(days=1)).strftime("%Y-%m-%d"))
    if df.empty or len(df) < 20:
        return None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    close = df["close"].astype(float)
    price = float(close.iloc[-1])
    prev  = float(close.iloc[-2]) if len(close) >= 2 else price
    ma20  = float(compute_ma(close, 20).iloc[-1])
    return {
        "price": price, "chg_pct": (price / prev - 1) * 100,
        "ma20": ma20, "ma20_dist": (price / ma20 - 1) * 100,
        "rsi": float(compute_rsi(close, 14).iloc[-1]),
        "bull": price > ma20,
    }


@st.cache_data(ttl=1800, show_spinner=False)
def _watchlist_prices(stock_ids: tuple) -> dict:
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    if not stock_ids:
        return {}
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    start = (today - pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    end   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    out = {}
    for sid in stock_ids:
        df = storage.load(f"daily_price/{sid}", start_date=start, end_date=end)
        if df.empty:
            continue
        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        price = float(close.iloc[-1])
        prev  = float(close.iloc[-2]) if len(close) >= 2 else price
        out[sid] = {"price": price, "chg_pct": (price / prev - 1) * 100}
    return out


@st.cache_data(ttl=900, show_spinner=False)
def _home_signals(stock_ids: tuple) -> list[dict]:
    import pandas as pd
    from twquant.data.storage import SQLiteStorage
    from twquant.strategy.registry import get_strategy
    if not stock_ids:
        return []
    storage = SQLiteStorage(DB_PATH)
    today = pd.Timestamp.today().normalize()
    end_str   = (today - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    start_str = (today - pd.DateOffset(days=200)).strftime("%Y-%m-%d")
    results = []
    for sid in stock_ids:
        df = storage.load(f"daily_price/{sid}", start_date=start_str, end_date=end_str)
        if df.empty or len(df) < 120:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        close = df["close"].astype(float)
        for key, label in _STRAT_LABEL.items():
            try:
                entries, _ = get_strategy(key).generate_signals(df)
                if len(entries) > 0 and bool(entries[-1]):
                    results.append({"代號": sid, "策略": label,
                                    "現價": f"{float(close.iloc[-1]):.1f}",
                                    "截止": str(df["date"].iloc[-1].date())})
            except Exception:
                continue
    return results


def _system_health() -> dict:
    try:
        from twquant.data.storage import SQLiteStorage
        from twquant.dashboard.config import get_finmind_token
        storage = SQLiteStorage(DB_PATH)
        syms = storage.list_symbols()
        hwm  = storage.get_hwm("daily_price/2330")
        return {"stock_count": len([s for s in syms if s.startswith("daily_price/")]),
                "last_date": str(hwm) if hwm else "未入庫",
                "has_token": bool(get_finmind_token())}
    except Exception:
        return {"stock_count": 0, "last_date": "讀取失敗", "has_token": False}


def main():
    from twquant.data.watchlist import Watchlist

    # ── 市場狀態 ────────────────────────────────────────────────────────────
    status = _market_status()
    if status:
        chg_color  = "#EF4444" if status["chg_pct"] > 0 else ("#22C55E" if status["chg_pct"] < 0 else "#9CA3AF")
        regime_color = "#22C55E" if status["bull"] else "#EF4444"
        arrow = "▲" if status["chg_pct"] > 0 else ("▼" if status["chg_pct"] < 0 else "─")
        st.markdown(
            f"<div style='background:{regime_color}18;border-left:3px solid {regime_color};"
            f"padding:8px 14px;border-radius:4px'>"
            f"<b style='color:{regime_color}'>{'🐂 多頭' if status['bull'] else '🐻 空頭'}</b> — "
            f"<b>0050</b> <span style='color:{chg_color}'>{status['price']:.1f} "
            f"{arrow}{abs(status['chg_pct']):.2f}%</span>　"
            f"MA20: {status['ma20']:.1f}（<span style='color:{chg_color}'>{status['ma20_dist']:+.1f}%</span>）"
            f"　RSI: {status['rsi']:.0f}</div>",
            unsafe_allow_html=True,
        )
    else:
        st.caption("市場資料未入庫，請先執行 `python scripts/seed_data.py`")

    # ── 自選股輪盤 ──────────────────────────────────────────────────────────
    wl = Watchlist()
    wl_stocks = wl.list_all()
    scan_targets = tuple((wl_stocks + _POPULAR)[:20])
    price_map = _watchlist_prices(tuple(wl_stocks[:6])) if wl_stocks else {}

    if wl_stocks:
        st.caption("⭐ 自選股")
        cols = st.columns(min(len(wl_stocks), 6))
        for i, sid in enumerate(wl_stocks[:6]):
            info = price_map.get(sid, {})
            with cols[i]:
                if info:
                    st.metric(sid, f"{info['price']:.1f}", f"{info['chg_pct']:+.2f}%")
                    if st.button("查看", key=f"home_wl_{sid}", use_container_width=True):
                        st.session_state.update({"g_current_stock": sid, "current_stock": sid})
                else:
                    st.metric(sid, "無資料")
    else:
        st.caption("⭐ 自選股（空）— 在個股分析頁加入關注")

    st.divider()

    # ── 今日訊號 + 系統健康 ─────────────────────────────────────────────────
    col_sig, col_health = st.columns([3, 2])

    with col_sig:
        st.caption("📡 今日訊號（自選 + 熱門，前 10 筆）")
        signals = []
        try:
            signals = _home_signals(scan_targets)
        except Exception:
            pass
        if signals:
            import pandas as pd
            st.dataframe(pd.DataFrame(signals[:10]), use_container_width=True,
                         hide_index=True, height=220)
            st.caption(f"共 {len(signals)} 筆 — 完整掃描請到 📡 訊號掃描")
        else:
            st.info("今日無新訊號（自選 + 熱門股）— 完整掃描請至 📡 訊號掃描")

    with col_health:
        st.caption("🔧 系統健康")
        health = _system_health()
        h1, h2 = st.columns(2)
        h1.metric("已入庫股票", f"{health['stock_count']} 支")
        h2.metric("最後資料日", health["last_date"])
        st.caption(f"FinMind Token：{'✅ 已設定' if health['has_token'] else '⚠️ 未設定'}")
        if not health["has_token"]:
            st.warning("Token 未設定，無法即時拉取新資料", icon="⚠️")
        try:
            from twquant.data.alerts import unread_count
            n_unread = unread_count(DB_PATH)
            if n_unread > 0:
                st.warning(f"🔔 未讀告警 **{n_unread}** 筆 — 前往 🔔 告警中心查看")
            else:
                st.caption("🔔 告警：無未讀")
        except Exception:
            pass


if __name__ == "__main__":
    main()
