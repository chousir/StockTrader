"""
驗證 FinMind 是否支援「一次抓全市場單日資料」（bulk-by-date）。

用法：
    docker exec twquant-app python scripts/verify_bulk_fetch.py
    python scripts/verify_bulk_fetch.py

結果：
  - 若 bulk 成功 → 一次 API request 取得所有股票當日資料
  - 若 bulk 失敗 → 回傳空或錯誤，需逐支抓取（約 3000 req/天）

此結果影響夜間同步效率：bulk 可行時，全市場增量只需 1-2 requests/天。
"""
import sys
import os
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import requests
from loguru import logger
from twquant.dashboard.config import get_finmind_token


def _last_trading_day() -> str:
    d = date.today() - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def test_bulk_rest(token: str, target_date: str) -> dict:
    """直接打 FinMind REST API，不指定 stock_id"""
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockPrice",
        "start_date": target_date,
        "end_date": target_date,
    }
    if token:
        params["token"] = token

    logger.info(f"[bulk] 打 REST API：{target_date}（無 stock_id）")
    resp = requests.get(url, params=params, timeout=60)
    if resp.status_code != 200:
        return {"ok": False, "reason": f"HTTP {resp.status_code}", "rows": 0}

    data = resp.json()
    records = data.get("data", [])
    if not records:
        return {"ok": False, "reason": "回傳 data 為空", "rows": 0}

    stocks = {r.get("stock_id") for r in records}
    return {
        "ok": True,
        "rows": len(records),
        "stocks": len(stocks),
        "sample": records[:3],
    }


def test_bulk_dataloader(token: str, target_date: str) -> dict:
    """用 FinMind DataLoader，不傳 stock_id（測試 Python wrapper 支不支援）"""
    try:
        from FinMind.data import DataLoader
        dl = DataLoader()
        if token:
            dl.login_by_token(api_token=token)
        df = dl.taiwan_stock_daily(start_date=target_date, end_date=target_date)
        if df is None or df.empty:
            return {"ok": False, "reason": "DataLoader 回傳空", "rows": 0}
        return {"ok": True, "rows": len(df), "stocks": df["stock_id"].nunique()}
    except TypeError as e:
        return {"ok": False, "reason": f"DataLoader 不支援省略 stock_id: {e}", "rows": 0}
    except Exception as e:
        return {"ok": False, "reason": str(e), "rows": 0}


def main():
    token = get_finmind_token() or os.getenv("FINMIND_API_TOKEN", "")
    target_date = _last_trading_day()

    logger.info(f"=== FinMind Bulk-by-Date 驗證 ===")
    logger.info(f"Token: {'✅ 已設定' if token else '⚠️ 匿名（限速較低）'}")
    logger.info(f"目標日期: {target_date}")

    logger.info("\n[A] 測試 REST API（不帶 stock_id）")
    rest = test_bulk_rest(token, target_date)
    if rest["ok"]:
        logger.info(f"  ✅ 成功！取得 {rest['rows']} 筆 / {rest['stocks']} 支股票")
        logger.info(f"  範例: {rest.get('sample', [])[:1]}")
        logger.info("  → 可用 1 request/天 抓全市場，大幅節省 API 額度")
    else:
        logger.warning(f"  ❌ 失敗：{rest['reason']}")
        logger.warning("  → 需逐支抓取（~3000 req/天）")

    logger.info("\n[B] 測試 DataLoader（Python wrapper）")
    dl = test_bulk_dataloader(token, target_date)
    if dl["ok"]:
        logger.info(f"  ✅ 成功！取得 {dl['rows']} 筆 / {dl['stocks']} 支")
    else:
        logger.warning(f"  ❌ 失敗：{dl['reason']}")

    logger.info("\n=== 結論 ===")
    if rest["ok"]:
        logger.info("✅ REST bulk 可行 → finmind.py 可加入 fetch_all_for_date() 優化")
    elif dl["ok"]:
        logger.info("✅ DataLoader bulk 可行")
    else:
        logger.info("❌ Bulk 不可行 → 維持逐支抓取（夜間盤後跑通宵）")


if __name__ == "__main__":
    main()
