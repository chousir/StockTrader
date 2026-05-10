"""
月度輪動投資組合回測引擎

策略：每月月底對股票池重新評分 → 持有得分最高的 top-N 支 → 等權重配置
交易成本：buy/sell 各 0.1425%×折扣，賣出加 0.3% 證交稅
基準：0050 買進持有
"""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
from loguru import logger


# ── 因子評分（輕量版，只需價量資料） ──────────────────────────────────────

def _score_stock(close: pd.Series, volume: pd.Series) -> float:
    """
    多因子評分：趨勢 + RSI + MACD + RAM動能 + OBV + StochRSI + 量能比
    滿分無上限，總體設計：強動能強趨勢約 +10~+15，弱勢約 -2~-5
    """
    from twquant.indicators.basic import (
        compute_ma, compute_rsi, compute_macd,
        compute_obv, compute_stoch_rsi,
    )

    n = len(close)
    if n < 120:
        return float("-inf")

    price = float(close.iloc[-1])
    if price <= 0:
        return float("-inf")

    score = 0.0

    # ── 1. 趨勢（三線排列：MA5/20/60） ─────────────────────────────────────
    ma20 = float(compute_ma(close, 20).iloc[-1])
    ma60 = float(compute_ma(close, 60).iloc[-1])
    ma120 = float(compute_ma(close, 120).iloc[-1])
    if price > ma20 > ma60 > ma120:   # 完整四線多頭排列
        score += 4.0
    elif price > ma20 > ma60:
        score += 2.5
    elif price > ma20:
        score += 1.0
    elif price < ma60:
        score -= 1.5

    # ── 量能比（先算，供後續使用） ──────────────────────────────────────────
    vol5  = float(volume.iloc[-5:].mean())
    vol20 = float(volume.iloc[-20:].mean())
    vol_ratio = vol5 / vol20 if vol20 > 0 else 1.0

    # ── 2. RSI 動能（帶超賣反彈判斷） ──────────────────────────────────────
    rsi = float(compute_rsi(close, 14).iloc[-1])
    if not math.isnan(rsi):
        if 50 <= rsi <= 68:
            score += 2.5   # 強勢健康區間
        elif 68 < rsi <= 74:
            score += 1.0   # 偏強但仍合理
        elif rsi > 74:
            score -= 2.0   # 超買
        elif rsi < 30:
            score += 2.0 if vol_ratio > 1.2 else 0.5   # 超賣量增，反彈機會
        elif rsi < 40:
            score -= 0.5
        else:
            score -= 0.5

    # ── 3. MACD 訊號 ────────────────────────────────────────────────────────
    try:
        _, _, hist = compute_macd(close)
        hv = float(hist.iloc[-1])
        hp = float(hist.iloc[-2])
        if not math.isnan(hv):
            if hv > 0 and hp <= 0:
                score += 3.0    # 柱狀剛翻正（金叉）
            elif hv > 0 and hv > hp:
                score += 1.5    # 柱狀持續擴大
            elif hv > 0:
                score += 0.5    # 柱狀正但縮小
            elif hv <= 0 and hp > 0:
                score -= 2.0    # 死叉
            else:
                score -= 1.0
    except Exception:
        pass

    # ── 4. RAM 風險調整動能（本平台核心因子） ───────────────────────────────
    # RAM = ret₂₀ / (σ₂₀ × √20)；RAM > 0.7 為強勢，> 1.0 為極強
    if n >= 22:
        ret20 = close.iloc[-1] / close.iloc[-21] - 1
        vol20_std = close.pct_change().iloc[-20:].std()
        if vol20_std > 0 and not math.isnan(vol20_std):
            ram = ret20 / (vol20_std * math.sqrt(20))
            if ram > 1.0:
                score += 3.0
            elif ram > 0.7:
                score += 2.0
            elif ram > 0.3:
                score += 1.0
            elif ram < -0.5:
                score -= 2.0
            elif ram < 0.0:
                score -= 0.5

    # ── 5. OBV 趨勢一致性 ───────────────────────────────────────────────────
    # OBV MA10 上穿 MA30 為量能配合趨勢的確認
    try:
        obv = compute_obv(close, volume)
        obv_ma10 = float(compute_ma(obv, 10).iloc[-1])
        obv_ma30 = float(compute_ma(obv, 30).iloc[-1])
        obv_ma10_prev = float(compute_ma(obv, 10).iloc[-2])
        obv_ma30_prev = float(compute_ma(obv, 30).iloc[-2])
        if obv_ma10 > obv_ma30 and obv_ma10_prev <= obv_ma30_prev:
            score += 2.0   # OBV剛金叉
        elif obv_ma10 > obv_ma30:
            score += 1.0   # OBV持續向上
        elif obv_ma10 < obv_ma30:
            score -= 1.0
    except Exception:
        pass

    # ── 6. StochRSI 超買超賣 ────────────────────────────────────────────────
    # K/D 均在 20 以下且 K 上穿 D 為超賣反彈訊號
    try:
        k, d = compute_stoch_rsi(close)
        kv = float(k.iloc[-1])
        dv = float(d.iloc[-1])
        kp = float(k.iloc[-2])
        if not math.isnan(kv) and not math.isnan(dv):
            if kv < 20 and dv < 20 and kv > kp:
                score += 2.0   # 超賣區域K線翻升
            elif kv < 20:
                score += 0.5   # 超賣但尚未翻升
            elif kv > 80 and dv > 80:
                score -= 1.5   # 超買區域
    except Exception:
        pass

    # ── 7. 量能比 ───────────────────────────────────────────────────────────
    if vol_ratio >= 1.5:
        score += 2.0
    elif vol_ratio >= 1.2:
        score += 1.0
    elif vol_ratio < 0.7:
        score -= 1.0

    return score


# ── 主要回測函數 ───────────────────────────────────────────────────────────

def run_portfolio_backtest(
    price_data: dict[str, pd.DataFrame],   # {sid: df with date, close, volume}
    start: str,
    end: str,
    top_n: int = 5,
    rebal_freq: str = "ME",                # 'ME'=月底, 'W-FRI'=週底
    init_cash: float = 1_000_000,
    broker_discount: float = 0.6,
    is_etf: bool = False,
    market_filter: bool = False,           # True=啟用市場趨勢濾網（0050<MA60 時全倉現金）
    market_sid: str = "0050",             # 濾網基準指數
) -> dict:
    """
    月度輪動回測。

    回傳 dict：
      equity_curve : {date_str: value}
      monthly_returns : {yyyymm: pct}
      holdings_log  : [{date, holdings: [{sid, weight, score}]}]
      total_return, max_drawdown, sharpe_ratio, calmar_ratio
      turnover_avg  : 平均月換手率
    """
    broker_fee = 0.001425 * broker_discount
    sell_tax   = 0.001 if is_etf else 0.003

    # ── 市場趨勢濾網（0050 vs MA60） ──
    market_price_series: pd.Series | None = None
    if market_filter and market_sid in price_data:
        mdf = price_data[market_sid].copy()
        mdf["date"] = pd.to_datetime(mdf["date"])
        market_price_series = mdf.set_index("date")["close"].astype(float)

    # ── 建立日期索引 ──
    all_dates: pd.DatetimeIndex = pd.date_range(start, end, freq="B")

    # ── 對每支股票，建立以 date 為 index 的收盤價 Series ──
    price_series: dict[str, pd.Series] = {}
    vol_series: dict[str, pd.Series] = {}
    for sid, df in price_data.items():
        df2 = df.copy()
        df2["date"] = pd.to_datetime(df2["date"])
        df2 = df2.set_index("date").sort_index()
        price_series[sid] = df2["close"].astype(float).reindex(all_dates, method="ffill")
        vol_series[sid]   = df2["volume"].astype(float).reindex(all_dates, method="ffill")

    # ── 建立再平衡日期清單（月底交易日） ──
    rebal_dates: list[pd.Timestamp] = (
        pd.date_range(start, end, freq=rebal_freq)
        .map(lambda d: all_dates[all_dates <= d][-1] if any(all_dates <= d) else None)
        .dropna()
        .tolist()
    )

    # ── 投組模擬 ──
    cash = init_cash
    holdings: dict[str, float] = {}          # {sid: shares}
    equity_values: list[tuple[pd.Timestamp, float]] = []
    holdings_log: list[dict] = []
    prev_sids: set[str] = set()

    def portfolio_value(dt: pd.Timestamp) -> float:
        v = cash
        for sid, sh in holdings.items():
            px = price_series.get(sid, pd.Series(dtype=float)).get(dt, float("nan"))
            if not math.isnan(px) and px > 0:
                v += sh * px
        return v

    for i, dt in enumerate(all_dates):
        # 在再平衡日執行換倉
        if dt in rebal_dates or i == 0:
            # 市場趨勢濾網：0050 < MA60 → 清空持倉，等待轉好
            if market_filter and market_price_series is not None:
                mhist = market_price_series.loc[:dt].dropna()
                if len(mhist) >= 60:
                    mma60 = float(mhist.rolling(60).mean().iloc[-1])
                    market_bearish = float(mhist.iloc[-1]) < mma60
                    if market_bearish:
                        # 清倉
                        for sid in list(holdings.keys()):
                            px = price_series[sid].get(dt, 0)
                            cash += holdings[sid] * px * (1 - sell_tax - broker_fee)
                            del holdings[sid]
                        equity_values.append((dt, portfolio_value(dt)))
                        continue  # 跳過選股

            # 1. 對所有股票評分（用截至今日的過去資料）
            scores: dict[str, float] = {}
            for sid in price_series:
                cl = price_series[sid].loc[:dt].dropna()
                vl = vol_series[sid].loc[:dt].dropna()
                if len(cl) < 60 or cl.iloc[-1] <= 0:
                    continue
                scores[sid] = _score_stock(cl, vl)

            # 2. 選 top_n
            ranked = sorted(scores, key=lambda s: -scores[s])
            selected = [s for s in ranked if scores[s] > -99][:top_n]

            if not selected:
                equity_values.append((dt, portfolio_value(dt)))
                continue

            # 3. 賣出不在新組合的持股
            port_val = portfolio_value(dt)
            sell_proceeds = 0.0
            for sid in list(holdings.keys()):
                if sid not in selected:
                    px = price_series[sid].get(dt, 0)
                    proceeds = holdings[sid] * px * (1 - sell_tax - broker_fee)
                    sell_proceeds += proceeds
                    del holdings[sid]
            cash += sell_proceeds

            # 4. 等權重買入新股票
            target_val = (portfolio_value(dt) / len(selected))
            for sid in selected:
                px = price_series[sid].get(dt, 0)
                if px <= 0:
                    continue
                current_val = holdings.get(sid, 0) * px
                buy_val = target_val - current_val
                if buy_val > 10:  # 至少買 10 元以上
                    cost = buy_val * (1 + broker_fee)
                    if cash >= cost:
                        shares = buy_val / px
                        holdings[sid] = holdings.get(sid, 0) + shares
                        cash -= cost

            # 5. 記錄本期持股
            holdings_log.append({
                "date": dt.strftime("%Y-%m-%d"),
                "holdings": [
                    {"sid": s, "score": round(scores[s], 2)} for s in selected
                ],
                "turnover": len(set(selected) - prev_sids) / max(len(selected), 1),
            })
            prev_sids = set(selected)

        equity_values.append((dt, portfolio_value(dt)))

    # ── 最後一天平倉（賣出所有持股，計算最終淨值） ──
    last_dt = all_dates[-1]
    final_val = cash
    for sid, sh in holdings.items():
        px = price_series[sid].get(last_dt, 0)
        final_val += sh * px * (1 - sell_tax - broker_fee)

    # ── 統計指標 ──
    equity_s = pd.Series(
        [v for _, v in equity_values],
        index=[d for d, _ in equity_values],
        dtype=float,
    )
    equity_s = equity_s.ffill()

    total_return = final_val / init_cash - 1
    daily_ret = equity_s.pct_change().dropna()
    sharpe = (
        float(daily_ret.mean() / daily_ret.std() * math.sqrt(252))
        if daily_ret.std() > 0 else float("nan")
    )

    roll_max = equity_s.cummax()
    drawdown = (equity_s - roll_max) / roll_max
    max_dd = float(drawdown.min())

    annual_ret = (1 + total_return) ** (252 / max(len(equity_s), 1)) - 1
    calmar = annual_ret / abs(max_dd) if max_dd < 0 else float("nan")

    monthly_ret = equity_s.resample("ME").last().pct_change().dropna()
    avg_turnover = float(
        pd.Series([h.get("turnover", 0) for h in holdings_log]).mean()
    ) if holdings_log else float("nan")

    return {
        "equity_curve": equity_s.to_dict(),
        "final_value": final_val,
        "total_return": total_return,
        "max_drawdown": max_dd,
        "sharpe_ratio": sharpe,
        "calmar_ratio": calmar,
        "monthly_returns": monthly_ret.to_dict(),
        "holdings_log": holdings_log,
        "turnover_avg": avg_turnover,
        "top_n": top_n,
        "n_stocks_screened": len(price_data),
    }
