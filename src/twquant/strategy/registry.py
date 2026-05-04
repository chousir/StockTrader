"""策略註冊表：集中管理所有內建策略"""

from twquant.strategy.base import BaseStrategy
from twquant.strategy.builtin.bollinger_breakout import BollingerBreakout
from twquant.strategy.builtin.ma_crossover import MACrossover
from twquant.strategy.builtin.macd_divergence import MACDDivergence
from twquant.strategy.builtin.rsi_reversal import RSIReversal

try:
    from twquant.strategy.builtin.rust_custom import RustCustomStrategy
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False

_REGISTRY: dict[str, type[BaseStrategy]] = {
    "ma_crossover": MACrossover,
    "macd_divergence": MACDDivergence,
    "rsi_reversal": RSIReversal,
    "bollinger_breakout": BollingerBreakout,
}

if _RUST_AVAILABLE:
    _REGISTRY["rust_kalman"] = RustCustomStrategy


def list_strategies() -> list[dict]:
    """回傳所有已註冊策略的資訊列表。"""
    result = []
    for key, cls in _REGISTRY.items():
        instance = cls()
        result.append({
            "key": key,
            "name": cls.name,
            "description": cls.description,
            "parameters": instance.get_parameters(),
        })
    return result


def get_strategy(key: str, **kwargs) -> BaseStrategy:
    """依 key 取得策略實例，kwargs 傳入建構子。"""
    if key not in _REGISTRY:
        raise KeyError(f"未知策略 '{key}'，可用：{list(_REGISTRY.keys())}")
    return _REGISTRY[key](**kwargs)
