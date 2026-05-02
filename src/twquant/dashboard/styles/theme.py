"""台股慣用配色常數（深色主題版）"""


class TWStockColors:
    """台股慣用配色（深色主題版）"""

    # 漲跌色系（台股：紅漲綠跌）
    PRICE_UP = "#EF4444"
    PRICE_DOWN = "#22C55E"
    PRICE_FLAT = "#9CA3AF"

    VOLUME_UP = "rgba(239, 68, 68, 0.6)"
    VOLUME_DOWN = "rgba(34, 197, 94, 0.6)"

    CANDLE_UP_FILL = "#EF4444"
    CANDLE_UP_BORDER = "#DC2626"
    CANDLE_DOWN_FILL = "#22C55E"
    CANDLE_DOWN_BORDER = "#16A34A"

    MA_5 = "#FBBF24"
    MA_10 = "#F97316"
    MA_20 = "#3B82F6"
    MA_60 = "#A855F7"

    EQUITY_CURVE = "#00D4AA"
    BENCHMARK_CURVE = "#6B7280"
    DRAWDOWN_FILL = "rgba(239, 68, 68, 0.2)"

    FOREIGN_BUY = "#3B82F6"
    FOREIGN_SELL = "#EF4444"
    DEALER_COLOR = "#A855F7"
    TRUST_COLOR = "#F97316"

    CARD_BG = "#1E2130"
    CARD_BORDER = "#2A2D3A"
    ACCENT = "#00D4AA"
    MUTED_TEXT = "#6B7280"

    # MA 週期 → 色彩對應
    MA_COLORS: dict[int, str] = {5: MA_5, 10: MA_10, 20: MA_20, 60: MA_60}
