from dataclasses import dataclass, field
from decimal import Decimal

# 升降單位表（模組層級，避免 frozen dataclass 的 mutable default 限制）
_TICK_SIZE_TABLE: dict[tuple[int | float, int | float], Decimal] = {
    (0, 10):              Decimal("0.01"),
    (10, 50):             Decimal("0.05"),
    (50, 100):            Decimal("0.1"),
    (100, 500):           Decimal("0.5"),
    (500, 1000):          Decimal("1"),
    (1000, float("inf")): Decimal("5"),
}


@dataclass(frozen=True)
class TWSEConstants:
    """台灣證券交易所交易規則常數"""

    # 手續費
    BROKER_FEE_RATE: Decimal = Decimal("0.001425")  # 0.1425%，買賣各一次
    BROKER_FEE_DISCOUNT: Decimal = Decimal("0.6")   # 預設六折
    BROKER_FEE_MIN: int = 20                         # 整股最低 20 元
    BROKER_FEE_MIN_ODD_LOT: int = 1                  # 零股最低 1 元

    # 證券交易稅（僅賣出時課徵）
    STOCK_TAX_RATE: Decimal = Decimal("0.003")       # 股票 0.3%
    ETF_TAX_RATE: Decimal = Decimal("0.001")         # ETF 0.1%
    DAY_TRADE_TAX_RATE: Decimal = Decimal("0.0015")  # 當沖 0.15%（優惠至 2027 年底）
    BOND_ETF_TAX_RATE: Decimal = Decimal("0")        # 債券 ETF 免稅（至 2026 年底）

    # 漲跌幅限制
    PRICE_LIMIT_PCT: Decimal = Decimal("0.10")       # ±10%

    # 交易單位
    BOARD_LOT_SIZE: int = 1000                       # 1 張 = 1000 股

    # 交割
    SETTLEMENT_DAYS: int = 2                         # T+2 交割

    # 交易時間
    MARKET_OPEN: str = "09:00"
    MARKET_CLOSE: str = "13:30"
    ODD_LOT_START: str = "09:00"                     # 盤中零股
    ODD_LOT_MATCH_INTERVAL: int = 3                  # 每 3 分鐘撮合一次
    AFTER_HOUR_ODD_LOT: str = "14:00-14:30"          # 盤後零股

    # 升降單位（參考模組層級 _TICK_SIZE_TABLE）
    TICK_SIZE_TABLE: dict = field(
        default_factory=lambda: dict(_TICK_SIZE_TABLE)
    )

    def get_tick_size(self, price: float) -> Decimal:
        """依據價格查詢升降單位"""
        for (low, high), tick in self.TICK_SIZE_TABLE.items():
            if low <= price < high:
                return tick
        return Decimal("5")  # fallback


# 全域單例，供各模組直接 import 使用
TWSE = TWSEConstants()
