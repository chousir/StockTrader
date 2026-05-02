"""台股基準對比：0050 ETF / 加權指數，計算 Alpha / Beta"""

import numpy as np
import pandas as pd

BENCHMARKS = {
    "TAIEX": {
        "name": "加權股價指數",
        "description": "台灣加權股價報酬指數",
    },
    "0050": {
        "name": "元大台灣50 ETF",
        "stock_id": "0050",
        "description": "台灣市值前50大公司 ETF",
    },
    "006208": {
        "name": "富邦台50 ETF",
        "stock_id": "006208",
        "description": "台灣市值前50大公司 ETF（內扣費用較低）",
    },
}


def fetch_benchmark(
    benchmark_id: str,
    start_date: str,
    end_date: str,
    provider=None,
) -> pd.Series:
    """
    取得基準指數的日收盤價 Series（index 為日期）。
    若未傳入 provider，使用本地 CSV（0050）。
    """
    if provider is not None:
        stock_id = BENCHMARKS.get(benchmark_id, {}).get("stock_id", benchmark_id)
        df = provider.fetch_daily(stock_id, start_date, end_date)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date")["close"]

    from ..data.providers.csv_local import CsvLocalProvider
    from ..data.providers.base import EmptyDataError

    try:
        p = CsvLocalProvider("data/sample")
        stock_id = BENCHMARKS.get(benchmark_id, {}).get("stock_id", benchmark_id)
        df = p.fetch_daily(stock_id, start_date, end_date)
        df["date"] = pd.to_datetime(df["date"])
        return df.set_index("date")["close"]
    except EmptyDataError:
        return pd.Series(dtype=float)


def compute_alpha_beta(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
    risk_free_rate: float = 0.015,
) -> dict:
    """
    計算 Alpha 與 Beta。

    Parameters:
        strategy_returns:  策略日報酬率 Series
        benchmark_returns: 基準日報酬率 Series
        risk_free_rate:    年化無風險利率（台灣定存利率約 1.5%）

    Returns:
        dict with alpha, beta, correlation
    """
    # 對齊日期
    common = strategy_returns.index.intersection(benchmark_returns.index)
    s = strategy_returns.loc[common].dropna()
    b = benchmark_returns.loc[common].dropna()

    common2 = s.index.intersection(b.index)
    s = s.loc[common2]
    b = b.loc[common2]

    if len(s) < 2:
        return {"alpha": float("nan"), "beta": float("nan"), "correlation": float("nan")}

    daily_rf = risk_free_rate / 252
    excess_s = s - daily_rf
    excess_b = b - daily_rf

    beta = float(np.cov(excess_s, excess_b)[0, 1] / np.var(excess_b))
    alpha = float((excess_s.mean() - beta * excess_b.mean()) * 252)
    correlation = float(np.corrcoef(s, b)[0, 1])

    return {"alpha": alpha, "beta": beta, "correlation": correlation}


def build_equity_curves(
    strategy_value: pd.Series,
    benchmark_price: pd.Series,
    init_cash: float = 1_000_000,
) -> pd.DataFrame:
    """
    對齊策略資金曲線與基準指數，統一基準為 init_cash。
    回傳 DataFrame，欄位：strategy, benchmark。
    """
    bench_idx = benchmark_price.index.intersection(strategy_value.index)
    if bench_idx.empty:
        return pd.DataFrame({"strategy": strategy_value})

    bench_normalized = (
        benchmark_price.loc[bench_idx] / benchmark_price.loc[bench_idx].iloc[0] * init_cash
    )
    strat_aligned = strategy_value.loc[bench_idx]

    return pd.DataFrame(
        {"strategy": strat_aligned, "benchmark": bench_normalized}
    )
