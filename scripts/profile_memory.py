"""記憶體 Profiling：連續 100 次回測，確認無記憶體洩漏"""

import gc
import sys
import tracemalloc

import numpy as np
import pandas as pd

sys.path.insert(0, "src")

from twquant.backtest.engine import TWSEBacktestEngine
from twquant.strategy.builtin.ma_crossover import MACrossover


def run_loop(n_iterations: int = 100) -> dict:
    df = pd.read_csv("data/sample/twse_2330_sample.csv", parse_dates=["date"])
    df_idx = df.set_index("date")
    strategy = MACrossover(5, 20)
    entries, exits = strategy.generate_signals(df)
    price = df_idx["close"].astype(float)

    memory_snapshots = []
    tracemalloc.start()

    for i in range(n_iterations):
        engine = TWSEBacktestEngine()
        engine.run(price, entries, exits)
        gc.collect()

        if i % 10 == 9:
            current, _ = tracemalloc.get_traced_memory()
            memory_snapshots.append(current / 1024 / 1024)

    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # 線性回歸檢測記憶體增長趨勢
    x = np.arange(len(memory_snapshots), dtype=float)
    slope = np.polyfit(x, memory_snapshots, 1)[0]

    return {
        "n_iterations": n_iterations,
        "snapshots_mb": memory_snapshots,
        "peak_mb": peak / 1024 / 1024,
        "slope_mb_per_10iter": slope,
        "leaked": slope > 0.5,
    }


if __name__ == "__main__":
    print("=== 記憶體 Profiling：100 次回測迴圈 ===")
    result = run_loop(100)
    print(f"峰值記憶體：{result['peak_mb']:.1f} MB")
    print(f"記憶體快照（每 10 次）：{[f'{v:.1f}' for v in result['snapshots_mb']]} MB")
    print(f"增長趨勢：{result['slope_mb_per_10iter']:.3f} MB/10次迭代")

    if not result["leaked"]:
        print("✅ 無記憶體洩漏（增長率 < 0.5 MB/10次）")
    else:
        print(f"⚠️  疑似記憶體洩漏（{result['slope_mb_per_10iter']:.2f} MB/10次）")
