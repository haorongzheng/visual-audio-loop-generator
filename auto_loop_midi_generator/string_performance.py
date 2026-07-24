from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "string_performance_modes.json"
MODE_IDS = ("string_long_pad", "string_emotional_movement")
STRING_CATEGORIES = frozenset({"strings", "ensemble_strings", "violin_section", "cello_section"})
DEGREES = ("root", "third", "fifth", "seventh", "octave_root", "octave_third", "octave_fifth")


def mode_event(bar: int, degrees: list[str], duration_bars: int) -> dict[str, Any]:
    return {"bar": int(bar), "degrees": [degree for degree in degrees if degree in DEGREES], "duration_bars": max(1, min(4, int(duration_bars))), "enabled": True}


def default_string_performance_modes() -> dict[str, dict[str, Any]]:
    return {
        "string_long_pad": {
            "id": "string_long_pad", "name": "String Long Pad", "label": "弦乐长音铺陈", "description": "两小节一次的长音和弦铺底，保持连贯与呼吸空间",
            "category": "strings", "style": "sustained_pad", "grid": "1/1 bar", "duration_ratio": 1.0, "sustain": .95,
            "velocity_range": [55, 75], "timing_amount": .01, "velocity_amount": .08, "density": .15, "retrigger_probability": .15,
            "voice_leading": True, "allowed_sound_directions": ["ambient", "organic", "ethnic", "cinematic"],
            "allowed_emotions": ["深沉", "平静", "忧伤"], "allowed_energy": ["静止", "流动", "高能"], "priority": 90, "enabled": True,
            "events": [
                mode_event(0, ["root", "third", "fifth"], 1), mode_event(1, ["root", "third", "fifth"], 1),
                mode_event(2, ["root", "third", "seventh"], 1), mode_event(3, ["root", "third", "fifth"], 1),
            ],
        },
        "string_emotional_movement": {
            "id": "string_emotional_movement", "name": "String Emotional Movement", "label": "弦乐情绪推进", "description": "每小节缓慢调整内声部，用共同音连接和声变化",
            "category": "strings", "style": "emotional_voice_leading", "grid": "1/2 bar", "duration_ratio": .9, "sustain": .85,
            "velocity_range": [65, 90], "timing_amount": .015, "velocity_amount": .12, "density": .3, "retrigger_probability": .12,
            "voice_leading": True, "allowed_sound_directions": ["organic", "ethnic", "cinematic"],
            "allowed_emotions": ["忧伤", "明亮", "激昂"], "allowed_energy": ["静止", "流动", "高能"], "priority": 88, "enabled": True,
            "events": [
                mode_event(0, ["root", "third", "fifth"], 1), mode_event(1, ["root", "seventh", "fifth"], 1),
                mode_event(2, ["octave_root", "third", "fifth"], 1), mode_event(3, ["root", "third", "fifth"], 1),
            ],
        },
    }


def normalize_event(value: dict[str, Any]) -> dict[str, Any]:
    return mode_event(value.get("bar", 0), [str(item) for item in value.get("degrees", [])], value.get("duration_bars", 1)) | {"enabled": bool(value.get("enabled", True))}


def load_string_performance_modes() -> dict[str, dict[str, Any]]:
    modes = default_string_performance_modes()
    try:
        saved = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.is_file() else []
    except (OSError, ValueError):
        saved = []
    for item in saved if isinstance(saved, list) else []:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id in modes:
            modes[mode_id].update({key: value for key, value in item.items() if key in modes[mode_id]})
            modes[mode_id]["events"] = [normalize_event(event) for event in modes[mode_id].get("events", []) if isinstance(event, dict)]
    return modes


def save_string_performance_modes(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    modes = default_string_performance_modes()
    allowed = {"name", "label", "description", "duration_ratio", "sustain", "velocity_range", "timing_amount", "velocity_amount", "density", "retrigger_probability", "voice_leading", "allowed_sound_directions", "allowed_emotions", "allowed_energy", "priority", "enabled", "events"}
    for item in items:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id not in modes:
            continue
        modes[mode_id].update({key: value for key, value in item.items() if key in allowed})
        modes[mode_id]["id"] = mode_id
        modes[mode_id]["enabled"] = bool(modes[mode_id].get("enabled", True))
        modes[mode_id]["duration_ratio"] = max(.1, min(1.0, float(modes[mode_id].get("duration_ratio", .9))))
        modes[mode_id]["sustain"] = max(.1, min(1.0, float(modes[mode_id].get("sustain", .9))))
        modes[mode_id]["timing_amount"] = max(0.0, min(.05, float(modes[mode_id].get("timing_amount", .01))))
        modes[mode_id]["velocity_amount"] = max(0.0, min(.3, float(modes[mode_id].get("velocity_amount", .1))))
        modes[mode_id]["events"] = [normalize_event(event) for event in modes[mode_id].get("events", []) if isinstance(event, dict)]
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(list(modes.values()), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return modes


def reset_string_performance_modes() -> dict[str, dict[str, Any]]:
    return save_string_performance_modes(list(default_string_performance_modes().values()))


def is_string_instrument(instrument: dict[str, Any] | None) -> bool:
    return bool(instrument and str(instrument.get("category", "")) in STRING_CATEGORIES)


def select_string_performance(sound: str, energy: str, emotion: str, rng: random.Random, mode_override: str = "auto", mode_data: dict[str, dict[str, Any]] | None = None) -> tuple[dict[str, Any] | None, str]:
    modes = mode_data or load_string_performance_modes()
    if mode_override in modes and modes[mode_override].get("enabled", True):
        return modes[mode_override], "manual"
    if sound in {"ambient", "ethnic"} or energy == "静止" or emotion in {"深沉", "平静"}:
        preferred = "string_long_pad"
    elif sound == "cinematic" or energy in {"流动", "高能"} or emotion in {"忧伤", "明亮", "激昂"}:
        preferred = "string_emotional_movement"
    else:
        preferred = "string_long_pad"
    candidate = modes.get(preferred)
    if candidate and candidate.get("enabled", True) and sound in candidate.get("allowed_sound_directions", []) and energy in candidate.get("allowed_energy", []):
        return candidate, "auto"
    available = [item for item in modes.values() if item.get("enabled", True) and sound in item.get("allowed_sound_directions", []) and energy in item.get("allowed_energy", [])]
    return (rng.choice(available), "auto") if available else (None, "standard_fallback")


def _fit(note: int, low: int = 43, high: int = 84) -> int:
    while note < low: note += 12
    while note > high: note -= 12
    return max(low, min(high, note))


def chord_pitches(degrees: list[str], chord: Any, previous: list[int] | None) -> list[int]:
    root_pc = int(chord.root_pc)
    tones = {tone.role: (root_pc + tone.interval) % 12 for tone in chord.tones}
    thirds = tones.get("3", tones.get("sus4", tones.get("sus2", (root_pc + 4) % 12)))
    seventh = tones.get("7", (root_pc + 10) % 12)
    pcs = {"root": root_pc, "third": thirds, "fifth": tones.get("5", (root_pc + 7) % 12), "seventh": seventh, "octave_root": root_pc, "octave_third": thirds, "octave_fifth": tones.get("5", (root_pc + 7) % 12)}
    output: list[int] = []
    for index, degree in enumerate(degrees):
        if degree not in pcs:
            continue
        base = 48 + ((pcs[degree] - 48) % 12) + (12 if degree.startswith("octave_") else 0)
        candidates = [_fit(base + shift) for shift in (-12, 0, 12)]
        target = previous[min(index, len(previous) - 1)] if previous else base
        selected = min(candidates, key=lambda note: abs(note - target))
        if selected in output:
            selected = _fit(selected + 12)
        output.append(selected)
    return sorted(output)


def string_events(chords: list[Any], bars: int, velocity: int, sound: str, energy: str, emotion: str, rng: random.Random, mode_override: str = "auto", mode_data: dict[str, dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    mode, selection = select_string_performance(sound, energy, emotion, rng, mode_override, mode_data)
    if not mode:
        return [], None
    pattern = {int(item["bar"]): item for item in mode.get("events", []) if item.get("enabled", True)}
    output: list[dict[str, Any]] = []
    previous: list[int] | None = None
    for bar in range(bars):
        source_bar = bar % 4
        item = pattern.get(source_bar)
        # A string pad may hold notes for almost a full bar, but it must always
        # re-voice the current harmony when the progression moves. For legacy
        # two-bar pad presets, keep the previous voicing shape and apply it to
        # the new chord instead of accidentally sustaining the old chord.
        if not item and mode.get("id") == "string_long_pad":
            item = next((pattern[index] for index in range(source_bar - 1, -1, -1) if index in pattern), None)
        if not item:
            continue
        pitches = chord_pitches(list(item.get("degrees", [])), chords[bar], previous if mode.get("voice_leading", True) else None)
        if not pitches:
            continue
        previous = pitches
        duration_bars = int(item.get("duration_bars", 1))
        duration = max(120, int(duration_bars * 4 * 480 * float(mode["duration_ratio"]) * float(mode["sustain"])))
        if mode.get("id") == "string_long_pad":
            # Do not leave a gap at the next harmony change. The short overlap
            # lets sampled strings release naturally while the new chord enters.
            duration = max(duration, duration_bars * 4 * 480) + 120
        low, high = mode.get("velocity_range", [60, 80])
        note_velocity = max(1, min(127, rng.randint(int(low), int(high))))
        for degree, pitch in zip(item.get("degrees", []), pitches):
            output.append({"bar": bar, "degree": degree, "pitch": pitch, "duration": duration, "velocity": note_velocity, "timing": 0})
    manifest = {"enabled": True, "category": "strings", "mode": mode["id"], "mode_name": mode["name"], "pattern": mode["id"], "style": mode["style"], "selection_source": selection, "main_mode_locked": True, "voice_leading": bool(mode.get("voice_leading", True)), "event_count": len({item["bar"] for item in output}), "note_count": len(output), "sustain": mode["sustain"], "legato_overlap_ticks": 120 if mode.get("id") == "string_long_pad" else 0, "humanize_limits": {"timing": mode["timing_amount"], "velocity": mode["velocity_amount"]}}
    return output, manifest
