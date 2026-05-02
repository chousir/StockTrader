"""Rust vs Python 效能基準測試：Kalman 濾波在 10 年日K線數據上的執行時間"""

import sys
import time

import numpy as np

sys.path.insert(0, "src")


def python_kalman(prices: np.ndarray, q: float = 0.01, r: float = 1.0) -> np.ndarray:
    n = len(prices)
    smoothed = np.empty(n)
    x = prices[0]
    p = 1.0
    for i, z in enumerate(prices):
        p_pred = p + q
        k = p_pred / (p_pred + r)
        x = x + k * (z - x)
        p = (1.0 - k) * p_pred
        smoothed[i] = x
    return smoothed


def benchmark(n_points: int = 2400, n_runs: int = 1000) -> dict:
    import twquant_core

    np.random.seed(42)
    prices = np.cumsum(np.random.normal(0, 1, n_points)) + 500.0
    prices = np.ascontiguousarray(prices, dtype=np.float64)

    # Python warm-up
    python_kalman(prices)

    # Python timing
    t0 = time.perf_counter()
    for _ in range(n_runs):
        python_kalman(prices)
    python_elapsed = time.perf_counter() - t0

    # Rust warm-up
    twquant_core.denoise_prices(prices)

    # Rust timing
    t0 = time.perf_counter()
    for _ in range(n_runs):
        twquant_core.denoise_prices(prices)
    rust_elapsed = time.perf_counter() - t0

    speedup = python_elapsed / rust_elapsed

    return {
        "n_points": n_points,
        "n_runs": n_runs,
        "python_total_ms": python_elapsed * 1000,
        "rust_total_ms": rust_elapsed * 1000,
        "python_per_run_us": python_elapsed / n_runs * 1e6,
        "rust_per_run_us": rust_elapsed / n_runs * 1e6,
        "speedup": speedup,
    }


if __name__ == "__main__":
    result = benchmark()
    print(f"\n=== Rust vs Python 效能比較 ===")
    print(f"數據量：{result['n_points']} 筆  |  執行次數：{result['n_runs']} 次")
    print(f"Python：{result['python_per_run_us']:.1f} μs/次")
    print(f"Rust：  {result['rust_per_run_us']:.1f} μs/次")
    print(f"加速比：{result['speedup']:.1f}x")

    if result["speedup"] >= 10:
        print("✅ Rust 比 Python 快 >= 10x，達成目標")
    else:
        print(f"⚠️  加速比 {result['speedup']:.1f}x，未達 10x 目標")
        print("   （注意：debug build 通常比 release build 慢，正式環境應使用 maturin build --release）")
