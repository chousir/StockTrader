"""回測引擎測試：空訊號、Buy&Hold、交易成本、記憶體釋放"""

import gc
import tracemalloc

import numpy as np
import pandas as pd
import pytest

import sys
sys.path.insert(0, "src")

from twquant.backtest.cost_model import tw_stock_fees
from twquant.backtest.engine import TWSEBacktestEngine


@pytest.fixture
def sample_price() -> pd.Series:
    df = pd.read_csv("data/sample/twse_2330_sample.csv", parse_dates=["date"])
    return df.set_index("date")["close"].astype(float)


def test_empty_signals(sample_price):
    """空訊號（無交易）回測不應崩潰"""
    n = len(sample_price)
    entries = np.zeros(n, dtype=bool)
    exits = np.zeros(n, dtype=bool)

    engine = TWSEBacktestEngine()
    result = engine.run(sample_price, entries, exits)

    assert "total_return" in result
    assert result["total_trades"] == 0
    assert engine._portfolio is None


def test_buy_and_hold(sample_price):
    """全期持有策略：第一天進場，最後一天出場"""
    n = len(sample_price)
    entries = np.zeros(n, dtype=bool)
    exits = np.zeros(n, dtype=bool)
    entries[0] = True
    exits[-1] = True

    engine = TWSEBacktestEngine()
    result = engine.run(sample_price, entries, exits)

    assert result["total_trades"] == 1
    assert "sharpe_ratio" in result
    assert "max_drawdown" in result


def test_cost_model_broker_fee():
    """買入 1 張台積電（成交額 100 萬元），手續費 855 元"""
    fee = tw_stock_fees(size=1000, price=1000, broker_discount=0.6)
    assert abs(fee - 855.0) < 1.0


def test_cost_model_sell_tax():
    """賣出時含證交稅 0.3%"""
    fee = tw_stock_fees(size=-1000, price=1000, broker_discount=0.6)
    expected = 1_000_000 * 0.001425 * 0.6 + 1_000_000 * 0.003
    assert abs(fee - expected) < 1.0


def test_cost_model_etf_tax():
    """ETF 證交稅 0.1%"""
    fee = tw_stock_fees(size=-1000, price=100, broker_discount=0.6, is_etf=True)
    expected = 100_000 * 0.001425 * 0.6 + 100_000 * 0.001
    assert abs(fee - expected) < 1.0


def test_cost_model_min_fee():
    """最低手續費 20 元（整股）"""
    fee = tw_stock_fees(size=1, price=1, broker_discount=0.6)
    assert fee == 20.0


def test_memory_released(sample_price):
    """Portfolio 物件使用後應被釋放（gc 後不佔用大量記憶體）"""
    n = len(sample_price)
    entries = np.zeros(n, dtype=bool)
    exits = np.zeros(n, dtype=bool)
    entries[0] = True
    exits[-1] = True

    tracemalloc.start()
    engine = TWSEBacktestEngine()
    engine.run(sample_price, entries, exits)
    gc.collect()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert engine._portfolio is None, "Portfolio 應已被設為 None"
    # 峰值記憶體 < 100 MB（合理上限）
    assert peak < 100 * 1024 * 1024, f"記憶體使用過高: {peak / 1024 / 1024:.1f} MB"
