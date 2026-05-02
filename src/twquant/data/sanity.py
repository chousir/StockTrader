"""台股 OHLCV 數據合理性過濾器：7 項檢查，可疑數據隔離而非丟棄"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from loguru import logger


@dataclass
class SanityResult:
    passed: pd.DataFrame
    quarantined: pd.DataFrame
    report: list[str]


class TWSEDataSanityChecker:
    """台股數據合理性檢查器"""

    def run_all_checks(self, df: pd.DataFrame, stock_id: str) -> SanityResult:
        report: list[str] = []
        mask_bad = pd.Series(False, index=df.index)

        price_cols = ["open", "high", "low", "close"]

        # ── 檢查 1：OHLC 邏輯關係 ──
        ohlc_invalid = (
            (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["high"] < df["low"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )
        if ohlc_invalid.any():
            report.append(f"[{stock_id}] {ohlc_invalid.sum()} 筆 OHLC 邏輯關係異常")
            mask_bad |= ohlc_invalid

        # ── 檢查 2：價格非正數 ──
        non_positive = (df[price_cols] <= 0).any(axis=1)
        if non_positive.any():
            report.append(f"[{stock_id}] {non_positive.sum()} 筆價格 <= 0")
            mask_bad |= non_positive

        # ── 檢查 3：成交量異常 ──
        vol_invalid = (df["volume"] < 0) | df["volume"].isna()
        if vol_invalid.any():
            report.append(f"[{stock_id}] {vol_invalid.sum()} 筆成交量異常")
            mask_bad |= vol_invalid

        # ── 檢查 4：日期重複 ──
        date_dup = df.duplicated(subset=["date"], keep="last")
        if date_dup.any():
            report.append(f"[{stock_id}] {date_dup.sum()} 筆日期重複，保留最後一筆")
            mask_bad |= date_dup

        # ── 檢查 5：單日漲跌幅超過 ±11%（除權息日留 1% 容差） ──
        if len(df) > 1:
            pct_change = df["close"].pct_change(fill_method=None)
            extreme_move = pct_change.abs() > 0.11
            if extreme_move.any():
                report.append(
                    f"[{stock_id}] {extreme_move.sum()} 筆漲跌幅超過 ±11%，需確認除權息"
                )
                # 不直接隔離，交由除權息過濾器處理

        # ── 檢查 6：NaN / Inf ──
        has_nan = df[price_cols + ["volume"]].isna().any(axis=1)
        has_inf = np.isinf(df[price_cols].select_dtypes(include=[np.number])).any(axis=1)
        null_inf = has_nan | has_inf
        if null_inf.any():
            report.append(f"[{stock_id}] {null_inf.sum()} 筆含有 NaN 或 Inf")
            mask_bad |= null_inf

        # ── 檢查 7：日期合理性 ──
        df_dates = pd.to_datetime(df["date"])
        date_oor = (df_dates < "1990-01-01") | (df_dates > pd.Timestamp.now())
        if date_oor.any():
            report.append(f"[{stock_id}] {date_oor.sum()} 筆日期超出合理範圍")
            mask_bad |= date_oor

        for msg in report:
            logger.warning(msg)

        return SanityResult(
            passed=df[~mask_bad].copy(),
            quarantined=df[mask_bad].copy(),
            report=report,
        )
