"""關注清單管理：本地 JSON 持久化"""

import json
from datetime import datetime
from pathlib import Path


class Watchlist:
    """
    關注清單管理

    儲存方式：本地 JSON 檔案（data/watchlist.json）
    與系統整合：數據同步優先權、多標的回測股票池
    """

    WATCHLIST_PATH = Path("data/watchlist.json")

    def __init__(self):
        self._stocks: dict[str, dict] = {}
        self._load()

    def add(self, stock_id: str, stock_name: str = "") -> None:
        if stock_id not in self._stocks:
            self._stocks[stock_id] = {
                "stock_name": stock_name,
                "added_at": datetime.now().isoformat(),
            }
            self._save()

    def remove(self, stock_id: str) -> None:
        self._stocks.pop(stock_id, None)
        self._save()

    def contains(self, stock_id: str) -> bool:
        return stock_id in self._stocks

    def list_all(self) -> list[str]:
        return list(self._stocks.keys())

    def list_with_details(self) -> list[dict]:
        return [{"stock_id": sid, **info} for sid, info in self._stocks.items()]

    def _load(self) -> None:
        if self.WATCHLIST_PATH.exists():
            try:
                self._stocks = json.loads(self.WATCHLIST_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._stocks = {}

    def _save(self) -> None:
        self.WATCHLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.WATCHLIST_PATH.write_text(
            json.dumps(self._stocks, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
