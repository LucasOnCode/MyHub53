import json
import os
from pathlib import Path

APP_DIR = Path(os.environ.get("APPDATA", ".")) / "MyHub53"
APP_DIR.mkdir(parents=True, exist_ok=True)

_SETTINGS_FILE = APP_DIR / "settings.json"


def _load_all() -> dict:
    if _SETTINGS_FILE.exists():
        try:
            with open(_SETTINGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_all(data: dict):
    with open(_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load(tool_id: str) -> dict:
    return _load_all().get(tool_id, {})


def save(tool_id: str, data: dict):
    all_data = _load_all()
    all_data.setdefault(tool_id, {}).update(data)
    _save_all(all_data)


def history_file(tool_id: str) -> Path:
    return APP_DIR / f"{tool_id}_history.json"
