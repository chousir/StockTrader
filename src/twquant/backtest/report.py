"""績效報告產出：dict 輸出與 Markdown 格式"""

import math
from datetime import date

import numpy as np
import pandas as pd


def generate_report(
    metrics: dict,
    strategy_name: str = "Strategy",
    benchmark_name: str = "0050",
    start_date: str = "",
    end_date: str = "",
    init_cash: float = 1_000_000,
) -> dict:
    """
    整合回測結果產出完整績效報告 dict。

    Parameters:
        metrics:        TWSEBacktestEngine.run() 的回傳值
        strategy_name:  策略名稱
        benchmark_name: 基準名稱
        start_date/end_date: 回測期間
        init_cash:      初始資金

    Returns:
        含全部指標的 dict，可直接傳給 Streamlit st.metric()
    """
    total_return = metrics.get("total_return", float("nan"))
    final_value = metrics.get("final_value", init_cash)

    # 年化報酬率（CAGR）
    equity_curve = metrics.get("equity_curve", {})
    cagr = float("nan")
    if equity_curve and start_date and end_date:
        try:
            years = (pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25
            if years > 0 and total_return > -1:
                cagr = (1 + total_return) ** (1 / years) - 1
        except Exception:
            pass

    return {
        "strategy_name": strategy_name,
        "benchmark_name": benchmark_name,
        "start_date": start_date,
        "end_date": end_date,
        "init_cash": init_cash,
        "final_value": final_value,
        # 報酬
        "total_return": total_return,
        "cagr": cagr,
        # 風險
        "max_drawdown": metrics.get("max_drawdown", float("nan")),
        "sharpe_ratio": metrics.get("sharpe_ratio", float("nan")),
        "sortino_ratio": metrics.get("sortino_ratio", float("nan")),
        "calmar_ratio": metrics.get("calmar_ratio", float("nan")),
        # 交易統計
        "total_trades": metrics.get("total_trades", 0),
        "win_rate": metrics.get("win_rate", float("nan")),
        "profit_factor": metrics.get("profit_factor", float("nan")),
        "avg_trade_duration": metrics.get("avg_trade_duration", float("nan")),
        # 台股特有：含稅估算
        "estimated_tax": final_value * metrics.get("total_return", 0) * 0.003
        if total_return > 0
        else 0.0,
        # 資金曲線
        "equity_curve": metrics.get("equity_curve", {}),
    }


def to_markdown(report: dict) -> str:
    """將績效報告轉為 Markdown 字串（供匯出使用）"""

    def fmt_pct(v):
        return f"{v:.2%}" if not (isinstance(v, float) and math.isnan(v)) else "N/A"

    def fmt_float(v):
        return f"{v:.4f}" if not (isinstance(v, float) and math.isnan(v)) else "N/A"

    def fmt_int(v):
        return str(int(v)) if v is not None else "N/A"

    lines = [
        f"# 回測績效報告：{report.get('strategy_name', '')}",
        f"",
        f"- **回測期間**：{report.get('start_date', '')} ~ {report.get('end_date', '')}",
        f"- **初始資金**：{report.get('init_cash', 0):,.0f} 元",
        f"- **最終資金**：{report.get('final_value', 0):,.0f} 元",
        f"",
        f"## 報酬指標",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 累積報酬率 | {fmt_pct(report.get('total_return', float('nan')))} |",
        f"| 年化報酬率 (CAGR) | {fmt_pct(report.get('cagr', float('nan')))} |",
        f"",
        f"## 風險指標",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 最大回撤 | {fmt_pct(report.get('max_drawdown', float('nan')))} |",
        f"| 夏普率 | {fmt_float(report.get('sharpe_ratio', float('nan')))} |",
        f"| Sortino Ratio | {fmt_float(report.get('sortino_ratio', float('nan')))} |",
        f"| Calmar Ratio | {fmt_float(report.get('calmar_ratio', float('nan')))} |",
        f"",
        f"## 交易統計",
        f"| 指標 | 數值 |",
        f"|------|------|",
        f"| 總交易次數 | {fmt_int(report.get('total_trades'))} |",
        f"| 勝率 | {fmt_pct(report.get('win_rate', float('nan')))} |",
        f"| 盈虧比 | {fmt_float(report.get('profit_factor', float('nan')))} |",
        f"| 平均持有天數 | {fmt_float(report.get('avg_trade_duration', float('nan')))} |",
    ]
    return "\n".join(lines)
