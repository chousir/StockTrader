"""使用者設定讀取模組：從 data/user_config.json 讀取設定"""

import json
from pathlib import Path

_CONFIG_PATH = Path("data/user_config.json")

_DEFAULTS = {
    "broker_discount": 0.6,
    "init_cash": 1_000_000,
    "benchmark": "0050",
    "finmind_api_token": "",
    "sync_mode": "full",
    "history_start_date": "2015-01-01",
}


def load_user_config() -> dict:
    """讀取使用者設定，不存在時回傳預設值"""
    if not _CONFIG_PATH.exists():
        return dict(_DEFAULTS)
    try:
        cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return {**_DEFAULTS, **cfg}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def get_broker_discount() -> float:
    return load_user_config()["broker_discount"]


def get_init_cash() -> int:
    return int(load_user_config()["init_cash"])


def get_benchmark() -> str:
    return load_user_config()["benchmark"]


def get_finmind_token() -> str:
    return load_user_config()["finmind_api_token"]


def get_sync_mode() -> str:
    return load_user_config()["sync_mode"]


def get_history_start_date() -> str:
    return load_user_config()["history_start_date"]
