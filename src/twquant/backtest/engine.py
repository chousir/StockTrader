"""VectorBT 回測引擎封裝：台股交易成本整合 + 記憶體安全釋放 + 追蹤停損"""

import gc
import math

import numpy as np
import pandas as pd
import vectorbt as vbt
from loguru import logger

from .cost_model import tw_vbt_fees


def apply_trailing_stop(
    price: pd.Series,
    entries: np.ndarray,
    exits: np.ndarray,
    trail_pct: float = 0.08,
) -> np.ndarray:
    """
    在原有出場訊號之上疊加追蹤停損（Trailing Stop）。
    trail_pct：從峰值回撤多少百分比觸發停損（預設 8%）。
    回傳新的 exits 陣列（只加不減）。
    """
    prices = price.values
    n = len(prices)
    new_exits = exits.copy()
    in_pos = False
    peak = 0.0

    for i in range(n):
        if not in_pos and entries[i]:
            in_pos = True
            peak = prices[i]
        elif in_pos:
            if prices[i] > peak:
                peak = prices[i]
            # 追蹤停損觸發
            if prices[i] < peak * (1 - trail_pct):
                new_exits[i] = True
                in_pos = False
                peak = 0.0
            elif exits[i]:
                in_pos = False
                peak = 0.0

    return new_exits


class TWSEBacktestEngine:
    """台股回測引擎，封裝 VectorBT 並整合台股交易成本"""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._portfolio = None

    def run(
        self,
        price: pd.Series,
        entries: np.ndarray,
        exits: np.ndarray,
        init_cash: float = 1_000_000,
        broker_discount: float = 0.6,
        is_etf: bool = False,
        slippage: float = 0.001,
        trail_stop: float = 0.0,   # 0.0 = 不啟用；0.08 = 8% 追蹤停損
    ) -> dict:
        """
        執行回測。

        Parameters:
            price:           日收盤價 Series（index 為日期）
            entries/exits:   bool 陣列，True 表示該日進出場
            init_cash:       初始資金（元）
            broker_discount: 券商折扣（預設六折）
            is_etf:          是否 ETF（影響證交稅計算）
            slippage:        滑價比例
            trail_stop:      追蹤停損比例（0 = 關閉）

        Returns:
            績效指標 dict
        """
        if trail_stop > 0:
            exits = apply_trailing_stop(price, entries, exits, trail_stop)

        fees = tw_vbt_fees(broker_discount=broker_discount, is_etf=is_etf)

        self._portfolio = vbt.Portfolio.from_signals(
            close=price,
            entries=entries,
            exits=exits,
            init_cash=init_cash,
            fees=fees,
            slippage=slippage,
            freq="1D",
        )

        result = self._extract_metrics()
        self._cleanup()
        return result

    def _extract_metrics(self) -> dict:
        pf = self._portfolio
        try:
            win_rate = float(pf.trades.win_rate())
        except Exception:
            win_rate = float("nan")
        try:
            profit_factor = float(pf.trades.profit_factor())
        except Exception:
            profit_factor = float("nan")
        try:
            total_trades = int(pf.trades.count())
        except Exception:
            total_trades = 0
        try:
            avg_duration = float(pf.trades.duration.mean())
        except Exception:
            avg_duration = float("nan")

        # 年化報酬
        equity = pf.value()
        n_days = max(len(equity), 1)
        total_ret = float(pf.total_return())
        annual_ret = (1 + total_ret) ** (252 / n_days) - 1

        # 交易明細
        trades_list = []
        try:
            tr = pf.trades.records_readable
            for _, row in tr.iterrows():
                trades_list.append({
                    "進場日": str(row.get("Entry Timestamp", ""))[:10],
                    "出場日": str(row.get("Exit Timestamp", ""))[:10],
                    "進場價": round(float(row.get("Avg Entry Price", 0)), 2),
                    "出場價": round(float(row.get("Avg Exit Price", 0)), 2),
                    "報酬率": float(row.get('Return', 0)),
                    "損益（元）": round(float(row.get("PnL", 0)), 0),
                })
        except Exception:
            pass

        return {
            "total_return": total_ret,
            "annual_return": annual_ret,
            "max_drawdown": float(pf.max_drawdown()),
            "sharpe_ratio": float(pf.sharpe_ratio()),
            "sortino_ratio": float(pf.sortino_ratio()),
            "calmar_ratio": float(pf.calmar_ratio()),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "avg_trade_duration": avg_duration,
            "equity_curve": equity.to_dict(),
            "final_value": float(pf.final_value()),
            "trades": trades_list,
        }

    def _cleanup(self) -> None:
        """顯式釋放記憶體"""
        if self._portfolio is not None:
            del self._portfolio
            self._portfolio = None
            gc.collect()
