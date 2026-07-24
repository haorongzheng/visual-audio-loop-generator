from __future__ import annotations

import random
import json
from pathlib import Path
from typing import Any

PERFORMANCE_MODES: dict[str, dict[str, Any]] = {
    "block": {"name": "Block Chord", "label": "柱式和弦", "description": "稳定、长音、不抢戏", "timing": 0.05, "velocity": 0.12, "events": [(0, 12, 1.0, "full_chord")], "bar4": "early_release"},
    "broken": {"name": "Broken Chord", "label": "分解和弦", "description": "清楚的上下声部交替", "timing": 0.12, "velocity": 0.18, "events": [(0, 5, 0.94, "split_lower"), (8, 5, 0.86, "split_upper")], "bar4": "reduced_group"},
    "pulse": {"name": "Chord Pulse", "label": "和弦脉冲", "description": "固定节拍重复", "timing": 0.03, "velocity": 0.10, "events": [(step, 2, 1.0 if step % 4 == 0 else 0.82, "upper_or_full") for step in range(0, 16, 2)], "bar4": "drop_last_pulse"},
    "rhythm_chop": {"name": "Rhythm Chop", "label": "节奏切分", "description": "短促切分，保留空拍", "timing": 0.08, "velocity": 0.18, "events": [(2, 2, .84, "upper_chord"), (7, 2, .98, "rootless"), (12, 2, .90, "upper_chord")], "bar4": "short_fill"},
    "arpeggio": {"name": "Arpeggio", "label": "琶音", "description": "每小节均匀五连音，固定向上", "timing": 0.06, "velocity": 0.12, "events": [(index * 16 / 5, 16 / 5, 1.0 if index == 0 else .86, "arp_up") for index in range(5)], "bar4": "changed_ending"},
    "octave_support": {"name": "Octave Support", "label": "八度支撑", "description": "低区支撑加中高区和弦", "timing": 0.08, "velocity": 0.15, "events": [(0, 10, 1.0, "octave_support"), (10, 4, .82, "upper_chord")], "bar4": "release_low_support"},
    "wide_pad": {"name": "Wide Pad", "label": "宽音域铺底", "description": "开放 Voicing、长音", "timing": 0.12, "velocity": 0.10, "events": [(0, 15, 1.0, "wide_pad")], "bar4": "early_release"},
    "cluster": {"name": "Cluster", "label": "音簇和弦", "description": "合法和弦音的紧密排列", "timing": 0.08, "velocity": 0.16, "events": [(0, 7, 1.0, "cluster"), (9, 5, .86, "cluster")], "bar4": "shorten_last"},
}

MODE_OPTIONS = tuple(PERFORMANCE_MODES)
ROOT = Path(__file__).resolve().parent.parent
MODE_DB_PATH = ROOT / "data" / "foundation_performance_modes.json"
AUTO_BY_SOUND = {
    "ambient": ("wide_pad", "block", "broken", "arpeggio"), "acoustic": ("block", "broken", "arpeggio", "octave_support"),
    "organic": ("broken", "arpeggio", "block"), "vintage": ("rhythm_chop", "cluster", "block", "broken"),
    "electronic": ("pulse", "rhythm_chop", "arpeggio", "block"), "ethnic": ("broken", "arpeggio", "wide_pad", "block"),
    "cinematic": ("block", "octave_support", "wide_pad", "pulse", "arpeggio"),
}


def default_performance_modes() -> dict[str, dict[str, Any]]:
    """Return editable defaults without allowing persisted data to mutate code defaults."""
    result: dict[str, dict[str, Any]] = {}
    for index, (mode_id, settings) in enumerate(PERFORMANCE_MODES.items(), start=1):
        result[mode_id] = {
            "id": mode_id,
            **settings,
            "allowed_sound_directions": list(AUTO_BY_SOUND.keys()),
            "allowed_energy": ["静止", "流动", "高能"],
            "allowed_rhythm": ["standard", "sparse", "flow", "groove", "aggressive"],
            "priority": index * 10,
            "enabled": True,
            "version": 1,
        }
    return result


def load_performance_modes() -> dict[str, dict[str, Any]]:
    defaults = default_performance_modes()
    if not MODE_DB_PATH.is_file():
        return defaults
    try:
        saved = json.loads(MODE_DB_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(saved, list):
        return defaults
    for item in saved:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id not in defaults:
            continue
        defaults[mode_id].update({key: value for key, value in item.items() if key in defaults[mode_id]})
    return defaults


def save_performance_modes(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    modes = default_performance_modes()
    for item in items:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id not in modes:
            continue
        allowed = {"name", "label", "description", "timing", "velocity", "events", "bar4", "allowed_sound_directions", "allowed_energy", "allowed_rhythm", "priority", "enabled", "version"}
        modes[mode_id].update({key: value for key, value in item.items() if key in allowed})
        modes[mode_id]["id"] = mode_id
        modes[mode_id]["enabled"] = bool(modes[mode_id]["enabled"])
        modes[mode_id]["timing"] = max(0.0, min(0.5, float(modes[mode_id]["timing"])))
        modes[mode_id]["velocity"] = max(0.0, min(0.5, float(modes[mode_id]["velocity"])))
    MODE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODE_DB_PATH.write_text(json.dumps(list(modes.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    return modes


def reset_performance_modes() -> dict[str, dict[str, Any]]:
    return save_performance_modes(list(default_performance_modes().values()))


def performance_mode_settings(mode: str) -> dict[str, Any]:
    return load_performance_modes().get(mode, PERFORMANCE_MODES["block"])


def select_performance_mode(sound: str, energy: str, rhythm: str, rng: random.Random, override: str = "auto") -> tuple[str, str]:
    modes = load_performance_modes()
    if override in modes and modes[override].get("enabled", True):
        return override, "manual"
    choices = list(AUTO_BY_SOUND.get(sound, AUTO_BY_SOUND["electronic"]))
    choices = [mode for mode in choices if modes.get(mode, {}).get("enabled", True)]
    choices = [mode for mode in choices if sound in modes[mode].get("allowed_sound_directions", []) and energy in modes[mode].get("allowed_energy", []) and rhythm in modes[mode].get("allowed_rhythm", [])]
    if energy == "静止": choices = [mode for mode in choices if mode not in {"rhythm_chop", "pulse"}] or ["block"]
    if energy == "高能" and sound != "cinematic": choices = [mode for mode in choices if mode != "wide_pad"] or choices
    rhythm_preferences = {"sparse": ("block", "wide_pad", "octave_support"), "flow": ("broken", "arpeggio", "pulse"), "groove": ("rhythm_chop", "cluster", "pulse", "broken"), "aggressive": ("pulse", "octave_support", "block")}
    preferred = [mode for mode in choices if mode in rhythm_preferences.get(rhythm, choices)]
    return rng.choice(preferred or choices), "auto"


def performance_selection_reason(sound: str, energy: str, rhythm: str, mode: str, selection: str) -> str:
    settings = performance_mode_settings(mode)
    if selection == "manual":
        return f"已手动选择 {settings['label']}。"
    return f"{sound} + {energy} + {rhythm} 自动选择 {settings['label']}，并在整个 Loop 内固定使用。"


def performance_events(mode: str, energy: str, bar: int) -> list[tuple[int, int, float, str]]:
    settings = performance_mode_settings(mode)
    events = [tuple(event) for event in settings["events"]]
    if mode == "pulse" and energy == "静止": events = [(step, duration, gain, kind) for step, duration, gain, kind in events if step % 4 == 0]
    if bar % 4 == 3:
        change = settings["bar4"]
        if change in {"early_release", "shorten_last", "drop_last_pulse"}: events = events[:-1] if len(events) > 1 else [(events[0][0], max(4, events[0][1] - 4), events[0][2], events[0][3])]
        elif change == "short_fill": events.append((14, 1, .76, "upper_chord"))
    return events
