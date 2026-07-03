"""Small persisted app settings (currently just the sound-effect volume)."""
from __future__ import annotations

import json
from pathlib import Path

SETTINGS_PATH = Path.home() / ".yt-dlp-gui" / "settings.json"

DEFAULTS = {"sound_volume": 100}


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**DEFAULTS, **data}
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f)
