from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EFFECTS_DIR = ROOT / "mixer"
EFFECTS_PATH = EFFECTS_DIR / "effects_settings.json"


def number(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def default_effects() -> dict[str, dict[str, Any]]:
    return {
        "delay": {"enabled": False, "mix": 0.08, "beats": 0.75},
        "reverb": {"enabled": False, "mix": 0.18, "decay": 0.45},
        "filter": {"enabled": False, "mode": "lowpass", "cutoff_hz": 12_000},
        "sidechain": {"enabled": False, "amount": 0.35, "release_ms": 140},
    }


def normalize_effects(value: Any) -> dict[str, dict[str, Any]]:
    raw = value if isinstance(value, dict) else {}
    defaults = default_effects()
    delay = raw.get("delay") if isinstance(raw.get("delay"), dict) else {}
    reverb = raw.get("reverb") if isinstance(raw.get("reverb"), dict) else {}
    filter_config = raw.get("filter") if isinstance(raw.get("filter"), dict) else {}
    sidechain = raw.get("sidechain") if isinstance(raw.get("sidechain"), dict) else {}
    filter_mode = str(filter_config.get("mode") or defaults["filter"]["mode"])
    if filter_mode not in {"lowpass", "highpass", "bandpass", "telephone"}:
        filter_mode = "lowpass"
    return {
        "delay": {
            "enabled": bool(delay.get("enabled", defaults["delay"]["enabled"])),
            "mix": max(0.0, min(0.35, number(delay.get("mix"), defaults["delay"]["mix"]))),
            "beats": max(0.25, min(1.5, number(delay.get("beats"), defaults["delay"]["beats"]))),
        },
        "reverb": {
            "enabled": bool(reverb.get("enabled", defaults["reverb"]["enabled"])),
            "mix": max(0.0, min(0.6, number(reverb.get("mix"), defaults["reverb"]["mix"]))),
            "decay": max(0.1, min(0.9, number(reverb.get("decay"), defaults["reverb"]["decay"]))),
        },
        "filter": {
            "enabled": bool(filter_config.get("enabled", defaults["filter"]["enabled"])),
            "mode": filter_mode,
            "cutoff_hz": max(250, min(18_000, int(number(filter_config.get("cutoff_hz"), defaults["filter"]["cutoff_hz"])))),
        },
        "sidechain": {
            "enabled": bool(sidechain.get("enabled", defaults["sidechain"]["enabled"])),
            "amount": max(0.0, min(0.9, number(sidechain.get("amount"), defaults["sidechain"]["amount"]))),
            "release_ms": max(30, min(800, int(number(sidechain.get("release_ms"), defaults["sidechain"]["release_ms"])))),
        },
    }


def load_effects() -> dict[str, dict[str, Any]]:
    EFFECTS_DIR.mkdir(parents=True, exist_ok=True)
    if not EFFECTS_PATH.is_file():
        return save_effects(default_effects())
    try:
        return normalize_effects(json.loads(EFFECTS_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return default_effects()


def save_effects(value: Any) -> dict[str, dict[str, Any]]:
    EFFECTS_DIR.mkdir(parents=True, exist_ok=True)
    normalized = normalize_effects(value)
    EFFECTS_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized
