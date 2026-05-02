"""台股交易成本模型：手續費 + 證交稅，供 VectorBT 使用"""

import numpy as np


def tw_stock_fees(
    size: np.ndarray | float,
    price: np.ndarray | float,
    broker_discount: float = 0.6,
    is_etf: bool = False,
    is_day_trade: bool = False,
    odd_lot: bool = False,
) -> np.ndarray | float:
    """
    計算台股真實交易成本。

    買入成本：成交金額 × 0.1425% × 折扣（最低 20 元，零股 1 元）
    賣出成本：手續費 + 證交稅（僅賣出時收取）

    Parameters:
        size:            交易股數（正=買入，負=賣出）
        price:           成交價格
        broker_discount: 券商手續費折扣（預設六折 0.6）
        is_etf:          是否為 ETF（影響證交稅：0.1%，股票 0.3%）
        is_day_trade:    是否為當沖（證交稅 0.15%，優惠至 2027 底）
        odd_lot:         是否為零股（最低手續費 1 元）
    """
    trade_value = np.abs(np.asarray(size, dtype=float) * np.asarray(price, dtype=float))
    broker_fee = trade_value * 0.001425 * broker_discount
    min_fee = 1.0 if odd_lot else 20.0
    broker_fee = np.maximum(broker_fee, min_fee)

    size_arr = np.asarray(size, dtype=float)
    if is_day_trade:
        tax_rate = 0.0015
    elif is_etf:
        tax_rate = 0.001
    else:
        tax_rate = 0.003
    sell_tax = np.where(size_arr < 0, trade_value * tax_rate, 0.0)

    return broker_fee + sell_tax


def tw_vbt_fees(
    broker_discount: float = 0.6,
    is_etf: bool = False,
) -> float:
    """
    回傳 VectorBT Portfolio.from_signals 用的單邊手續費率。

    注意：VectorBT 的 fees 參數是對稱的（買賣各計一次），
    賣出時的證交稅需額外透過 slippage 或自訂 fee function 處理。
    此函數回傳買入手續費率，適用於快速回測估算。
    """
    return 0.001425 * broker_discount
