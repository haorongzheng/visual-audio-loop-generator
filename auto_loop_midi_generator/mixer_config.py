from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
MIXER_DIR = ROOT / "mixer"
MIXER_PATH = MIXER_DIR / "mixer_settings.json"
TRACKS = ("Foundation", "Bass", "Drums", "Sample")


def default_mixer() -> dict[str, dict[str, float]]:
    return {track: {"gain_db": 0.0, "pan": 0.0} for track in TRACKS}


def number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def normalize_mixer(value: Any) -> dict[str, dict[str, float]]:
    raw = value if isinstance(value, dict) else {}
    result = default_mixer()
    for track in TRACKS:
        item = raw.get(track) if isinstance(raw.get(track), dict) else raw.get(track.lower()) if isinstance(raw.get(track.lower()), dict) else {}
        result[track] = {
            "gain_db": max(-36.0, min(12.0, number(item.get("gain_db"), 0.0))),
            "pan": max(-1.0, min(1.0, number(item.get("pan"), 0.0))),
        }
    return result


def load_mixer() -> dict[str, dict[str, float]]:
    MIXER_DIR.mkdir(parents=True, exist_ok=True)
    if not MIXER_PATH.is_file():
        save_mixer(default_mixer())
    try:
        return normalize_mixer(json.loads(MIXER_PATH.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return default_mixer()


def save_mixer(value: Any) -> dict[str, dict[str, float]]:
    MIXER_DIR.mkdir(parents=True, exist_ok=True)
    normalized = normalize_mixer(value)
    MIXER_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
