"""同步排程設定管理：讀寫 data/sync_config.json"""

import json
from datetime import date
from pathlib import Path

_CONFIG_PATH = Path("data/sync_config.json")

_DEFAULTS: dict = {
    "auto_sync_enabled": True,
    "nightly_time": "21:00",
    "history_start": "2020-01-01",
    "run_scan_after_sync": True,
    "universe_last_updated": "",
}


def load() -> dict:
    if _CONFIG_PATH.exists():
        try:
            cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            return {**_DEFAULTS, **cfg}
        except Exception:
            pass
    return dict(_DEFAULTS)


def save(cfg: dict) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    merged = {**_DEFAULTS, **cfg}
    _CONFIG_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")


def is_enabled() -> bool:
    return bool(load().get("auto_sync_enabled", True))


def get_nightly_time() -> tuple[int, int]:
    """回傳 (hour, minute)"""
    t = load().get("nightly_time", "21:00")
    try:
        h, m = t.split(":")
        return int(h), int(m)
    except Exception:
        return 21, 0


def get_history_start() -> str:
    return load().get("history_start", "2020-01-01")


def universe_needs_refresh() -> bool:
    last = load().get("universe_last_updated", "")
    if not last:
        return True
    try:
        return (date.today() - date.fromisoformat(last)).days >= 7
    except Exception:
        return True


def mark_universe_updated() -> None:
    cfg = load()
    cfg["universe_last_updated"] = date.today().isoformat()
    save(cfg)
