"""VectorBT 回測引擎封裝：台股交易成本整合 + 記憶體安全釋放"""

import gc

import numpy as np
import pandas as pd
import vectorbt as vbt
from loguru import logger

from .cost_model import tw_vbt_fees


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

        Returns:
            績效指標 dict
        """
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

        return {
            "total_return": float(pf.total_return()),
            "max_drawdown": float(pf.max_drawdown()),
            "sharpe_ratio": float(pf.sharpe_ratio()),
            "sortino_ratio": float(pf.sortino_ratio()),
            "calmar_ratio": float(pf.calmar_ratio()),
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "total_trades": total_trades,
            "avg_trade_duration": avg_duration,
            "equity_curve": pf.value().to_dict(),
            "final_value": float(pf.final_value()),
        }

    def _cleanup(self) -> None:
        """顯式釋放記憶體"""
        if self._portfolio is not None:
            del self._portfolio
            self._portfolio = None
            gc.collect()
