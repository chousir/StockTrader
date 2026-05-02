"""除權息假跌破過濾器：前復權、訊號遮罩、假跌破偵測"""

import numpy as np
import pandas as pd
from loguru import logger


class ExDividendFilter:
    """
    處理台股除權息日造成的假跌破問題。

    策略（可配置）：
    A. 前復權 (Forward Adjust)：調整歷史價格，使除權息日無缺口（預設）
    B. 訊號遮罩 (Signal Mask)：在除權息日前後 N 日抑制交易訊號
    C. 假跌破偵測報告：標記哪些日期的價格缺口來自除權息
    """

    def __init__(self, provider=None):
        self.provider = provider
        self._dividend_cache: dict[str, pd.DataFrame] = {}

    def load_dividend_calendar(self, stock_id: str, dividend_df: pd.DataFrame) -> None:
        """直接載入除權息資料（已由外部取得）"""
        self._dividend_cache[stock_id] = dividend_df

    def forward_adjust_prices(
        self,
        price_df: pd.DataFrame,
        dividend_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        前復權處理：從最新日期往回調整，最新價格不變，歷史價格被還原。

        調整公式：adjusted = (price - cash) / (1 + stock_ratio)
        台股股票股利以「元」計，10 元 = 1 股，即 stock_ratio = dividend / 10
        """
        df = price_df.copy()
        df["date"] = pd.to_datetime(df["date"])

        for _, div_row in dividend_df.iterrows():
            ex_date = pd.to_datetime(div_row["date"])
            cash = float(div_row.get("cash_dividend", 0) or 0)
            stock_div = float(div_row.get("stock_dividend", 0) or 0)
            stock_ratio = stock_div / 10

            mask_before = df["date"] < ex_date
            if not mask_before.any():
                continue

            if cash > 0 or stock_ratio > 0:
                factor = 1 + stock_ratio
                for col in ["open", "high", "low", "close"]:
                    df.loc[mask_before, col] = (df.loc[mask_before, col] - cash) / factor
                df.loc[mask_before, "volume"] = df.loc[mask_before, "volume"] * factor

        df["date"] = df["date"].dt.date
        return df

    def generate_signal_mask(
        self,
        price_df: pd.DataFrame,
        dividend_df: pd.DataFrame,
        suppress_days_before: int = 1,
        suppress_days_after: int = 2,
    ) -> np.ndarray:
        """
        產生訊號遮罩：True = 允許交易，False = 抑制訊號。
        直接 AND 到 entries/exits 陣列上使用。
        """
        mask = np.ones(len(price_df), dtype=bool)
        dates = pd.to_datetime(price_df["date"])

        for _, div_row in dividend_df.iterrows():
            ex_date = pd.to_datetime(div_row["date"])
            suppress_start = ex_date - pd.Timedelta(days=suppress_days_before * 2)
            suppress_end = ex_date + pd.Timedelta(days=suppress_days_after * 2)
            mask &= ~((dates >= suppress_start) & (dates <= suppress_end))

        return mask

    def detect_false_breakdowns(
        self,
        price_df: pd.DataFrame,
        dividend_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        偵測並標記除權息造成的假跌破事件，供策略開發者參考。
        """
        ex_dates = set(pd.to_datetime(dividend_df["date"]).dt.date)

        events = []
        for i in range(1, len(price_df)):
            curr_date = pd.to_datetime(price_df.iloc[i]["date"]).date()
            if curr_date not in ex_dates:
                continue

            prev_close = price_df.iloc[i - 1]["close"]
            curr_open = price_df.iloc[i]["open"]
            gap_pct = (curr_open - prev_close) / prev_close

            div_info = dividend_df[
                pd.to_datetime(dividend_df["date"]).dt.date == curr_date
            ].iloc[0]

            events.append(
                {
                    "date": curr_date,
                    "prev_close": prev_close,
                    "ex_open": curr_open,
                    "gap_pct": gap_pct,
                    "cash_dividend": div_info.get("cash_dividend", 0),
                    "stock_dividend": div_info.get("stock_dividend", 0),
                    "is_false_breakdown": True,
                }
            )

        return pd.DataFrame(events) if events else pd.DataFrame()
