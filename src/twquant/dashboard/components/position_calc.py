"""停損 / 部位計算器 — ATR-based stop-loss + lot sizing"""
from __future__ import annotations
import streamlit as st


def render_position_calc(close: float, atr14: float):
    """
    close:  當前股價
    atr14:  14 日 ATR
    """
    risk_budget = st.number_input(
        "風險預算（元）", min_value=10_000, max_value=500_000,
        value=50_000, step=10_000, key="pos_calc_budget",
    )

    stop = close - 1.5 * atr14
    risk_per_share = max(close - stop, 0.01)
    lots = int(risk_budget / (risk_per_share * 1000))
    target_r1 = close + 2 * (close - stop)
    target_r2 = close + 3 * (close - stop)

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("停損點", f"{stop:.2f}", delta=f"-{risk_per_share:.2f}/股", delta_color="inverse")
    c2.metric("風險/股", f"{risk_per_share:.2f}")
    c3.metric("建議張數", f"{lots} 張",
              help=f"以風險預算 ${risk_budget:,.0f} 計算，每張 1000 股")
    c4.metric("目標 R1 (2:1)", f"{target_r1:.2f}")
    c5.metric("目標 R2 (3:1)", f"{target_r2:.2f}")
