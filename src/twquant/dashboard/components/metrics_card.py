"""卡片式績效摘要元件：3×4 卡片群"""

import streamlit as st


def render_metrics_cards(result: dict, benchmark_result: dict = None) -> None:
    """
    渲染回測績效卡片群（3 行 × 4 列 = 12 張卡片）

    第一行：累積報酬、CAGR、Alpha、勝率
    第二行：最大回撤、夏普率、Sortino、盈虧比
    第三行：總交易、持有天數、手續費、含稅淨報酬
    """
    row1 = st.columns(4)
    with row1[0]:
        _metric_card(
            label="累積報酬",
            value=f"{result['total_return']:.1%}",
            delta=_compare(result, benchmark_result, "total_return"),
            is_good=result["total_return"] > 0,
        )
    with row1[1]:
        _metric_card(
            label="年化報酬 (CAGR)",
            value=f"{result.get('cagr', 0):.1%}",
            is_good=result.get("cagr", 0) > 0,
        )
    with row1[2]:
        _metric_card(
            label="Alpha",
            value=f"{result.get('alpha', 0):.2%}",
            is_good=result.get("alpha", 0) > 0,
        )
    with row1[3]:
        _metric_card(
            label="勝率",
            value=f"{result['win_rate']:.1%}",
            is_good=result["win_rate"] > 0.5,
        )

    row2 = st.columns(4)
    with row2[0]:
        _metric_card(
            label="最大回撤",
            value=f"{result['max_drawdown']:.1%}",
            is_good=False,
            invert_color=True,
        )
    with row2[1]:
        _metric_card(
            label="夏普率",
            value=f"{result['sharpe_ratio']:.2f}",
            is_good=result["sharpe_ratio"] > 1.0,
        )
    with row2[2]:
        _metric_card(
            label="Sortino",
            value=f"{result['sortino_ratio']:.2f}",
            is_good=result["sortino_ratio"] > 1.0,
        )
    with row2[3]:
        _metric_card(
            label="盈虧比",
            value=f"{result['profit_factor']:.2f}",
            is_good=result["profit_factor"] > 1.0,
        )

    row3 = st.columns(4)
    with row3[0]:
        _metric_card(
            label="總交易次數",
            value=str(result["total_trades"]),
        )
    with row3[1]:
        _metric_card(
            label="平均持有天數",
            value=f"{result.get('avg_trade_duration', 0):.0f}",
        )
    with row3[2]:
        _metric_card(
            label="手續費累計",
            value=f"${result.get('total_fees', 0):,.0f}",
            is_good=False,
            invert_color=True,
        )
    with row3[3]:
        _metric_card(
            label="含稅淨報酬",
            value=f"{result.get('net_return_after_tax', result['total_return']):.1%}",
            is_good=result.get("net_return_after_tax", result["total_return"]) > 0,
        )


def _metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    is_good: bool | None = None,
    invert_color: bool = False,
) -> None:
    with st.container(border=True):
        st.caption(label)
        if is_good is not None:
            color = ("#EF4444" if is_good else "#22C55E") if invert_color else ("#22C55E" if is_good else "#EF4444")
            st.markdown(f"<h2 style='color:{color};margin:0'>{value}</h2>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h2 style='margin:0'>{value}</h2>", unsafe_allow_html=True)
        if delta:
            st.caption(delta)


def _compare(result: dict, benchmark: dict | None, key: str) -> str | None:
    if benchmark is None or key not in benchmark:
        return None
    diff = result[key] - benchmark[key]
    arrow = "↑" if diff > 0 else "↓"
    return f"{arrow} 較基準 {diff:+.1%}"
