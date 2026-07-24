from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .midi_writer import PPQ
from .resolver import resolve_energy, resolve_rhythm, resolve_sound_direction
from .sample_library import float_or_default, int_or_default


ROOT = Path(__file__).resolve().parent.parent
PATTERN_DIR = ROOT / "drum_patterns"
PATTERN_DB_PATH = PATTERN_DIR / "drum_patterns.json"

BAR_TICKS = PPQ * 4
GRID_STEPS = {"1/16": 16, "1/32": 32, "1/8T": 12, "1/16T": 24}
SOUND_DIRECTIONS = ("all", "ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic")
ENERGIES = ("静止", "高能", "流动")
RHYTHMS = ("any", "sparse", "flow", "standard", "groove", "aggressive")
DRUM_SLOTS = {
    "kick": {"label": "Kick", "midi_note": 36},
    "snare": {"label": "Snare", "midi_note": 38},
    "clap": {"label": "Clap", "midi_note": 39},
    "closed_hat": {"label": "Closed Hat", "midi_note": 42},
    "open_hat": {"label": "Open Hat", "midi_note": 46},
    "shaker": {"label": "Shaker", "midi_note": 70},
    "perc_1": {"label": "Perc 1", "midi_note": 75},
    "perc_2": {"label": "Perc 2", "midi_note": 76},
    "low_tom": {"label": "Low Tom", "midi_note": 45},
    "high_tom": {"label": "High Tom", "midi_note": 50},
    "crash": {"label": "Crash", "midi_note": 49},
    "ride": {"label": "Ride", "midi_note": 51},
    "impact": {"label": "Impact", "midi_note": 55},
    "fill_hit": {"label": "Fill Hit", "midi_note": 48},
    "texture_perc": {"label": "Texture Perc", "midi_note": 82},
}


def ensure_pattern_dir() -> None:
    PATTERN_DIR.mkdir(parents=True, exist_ok=True)


def default_db() -> dict[str, Any]:
    patterns = []
    for energy in ENERGIES:
        for rhythm in ("sparse", "flow", "standard", "groove", "aggressive"):
            patterns.append(default_pattern("all", energy, rhythm, 4))
    return {"version": "1.0", "drum_patterns": patterns}


def load_drum_patterns() -> dict[str, Any]:
    ensure_pattern_dir()
    if not PATTERN_DB_PATH.is_file():
        save_drum_patterns(default_db())
    try:
        data = json.loads(PATTERN_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = default_db()
    if isinstance(data, list):
        data = {"version": "1.0", "drum_patterns": data}
    if not isinstance(data, dict):
        data = default_db()
    patterns = data.get("drum_patterns") if isinstance(data.get("drum_patterns"), list) else data.get("patterns", [])
    return {"version": "1.0", "drum_patterns": [normalize_pattern(pattern) for pattern in patterns if isinstance(pattern, dict)]}


def save_drum_patterns(db: dict[str, Any]) -> dict[str, Any]:
    ensure_pattern_dir()
    patterns = db.get("drum_patterns", db.get("patterns", []))
    if not isinstance(patterns, list):
        patterns = []
    normalized = {"version": "1.0", "drum_patterns": [normalize_pattern(pattern) for pattern in patterns if isinstance(pattern, dict)]}
    PATTERN_DB_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def export_drum_patterns() -> dict[str, Any]:
    return {**load_drum_patterns(), "definitions": definitions()}


def definitions() -> dict[str, Any]:
    return {
        "sound_directions": list(SOUND_DIRECTIONS),
        "energies": list(ENERGIES),
        "rhythms": list(RHYTHMS),
        "grid_resolutions": list(GRID_STEPS),
        "drum_slots": DRUM_SLOTS,
    }


def upsert_drum_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    db = load_drum_patterns()
    normalized = normalize_pattern(pattern)
    patterns = db["drum_patterns"]
    for index, existing in enumerate(patterns):
        if existing["pattern_id"] == normalized["pattern_id"]:
            patterns[index] = normalized
            save_drum_patterns(db)
            return normalized
    patterns.append(normalized)
    save_drum_patterns(db)
    return normalized


def reset_drum_pattern(sound_direction: str, energy: str, rhythm: str, bars: int) -> dict[str, Any]:
    pattern = default_pattern(sound_direction, energy, rhythm, bars)
    return upsert_drum_pattern(pattern)


def duplicate_drum_pattern(source_pattern_id: str, tags: dict[str, Any]) -> dict[str, Any]:
    source = next((pattern for pattern in load_drum_patterns()["drum_patterns"] if pattern["pattern_id"] == source_pattern_id), None)
    if not source:
        source = default_pattern(tags.get("sound_direction", "all"), tags.get("energy", "流动"), tags.get("rhythm", "groove"), 4)
    duplicate = normalize_pattern({**source, "pattern_id": "", "tags": tags, "name": pattern_name(tags), "updated_at": utc_now()})
    return upsert_drum_pattern(duplicate)


def find_matching_drum_pattern(sound_direction: str, energy: str, rhythm: str, bars: int) -> dict[str, Any] | None:
    sound = normalize_sound(sound_direction)
    energy_label = normalize_energy(energy)
    rhythm_key = normalize_rhythm(rhythm)
    target_bars = 8 if int_or_default(bars, 4) >= 8 else 4
    patterns = [pattern for pattern in load_drum_patterns()["drum_patterns"] if pattern.get("enabled", True)]
    candidates = (
        (sound, energy_label, rhythm_key),
        ("all", energy_label, rhythm_key),
        (sound, energy_label, "any"),
        ("all", energy_label, "any"),
    )
    for target_sound, target_energy, target_rhythm in candidates:
        matching_tags = [
            pattern
            for pattern in patterns
            if pattern.get("tags", {}).get("sound_direction") == target_sound
            and pattern.get("tags", {}).get("energy") == target_energy
            and pattern.get("tags", {}).get("rhythm") == target_rhythm
        ]
        # Prefer a pattern authored for the requested loop length. An 8-bar loop
        # can safely repeat a saved 4-bar pattern, but an 8-bar pattern must not
        # be silently truncated into a different 4-bar groove.
        matching_tags.sort(
            key=lambda pattern: (
                0 if int_or_default(pattern.get("loop_length_bars"), 4) == target_bars else 1,
                0 if target_bars == 8 and int_or_default(pattern.get("loop_length_bars"), 4) == 4 else 1,
            )
        )
        for pattern in matching_tags:
            tags = pattern.get("tags", {})
            source_bars = int_or_default(pattern.get("loop_length_bars"), 4)
            if source_bars > target_bars:
                continue
            clone = normalize_pattern(pattern)
            clone["matched_for_bars"] = target_bars
            return clone
    return None


def event_start_tick(event: dict[str, Any]) -> int:
    grid = normalize_grid(event.get("grid_resolution"))
    step_ticks = BAR_TICKS / GRID_STEPS[grid]
    bar = max(1, int_or_default(event.get("bar"), 1))
    step = max(0, int_or_default(event.get("step"), 0))
    micro = max(-20, min(20, int_or_default(event.get("micro_timing"), 0)))
    return max(0, int(round((bar - 1) * BAR_TICKS + step * step_ticks + micro)))


def default_pattern(sound_direction: str = "all", energy: str = "流动", rhythm: str = "groove", bars: int = 4) -> dict[str, Any]:
    tags = {"sound_direction": normalize_sound(sound_direction), "energy": normalize_energy(energy), "rhythm": normalize_rhythm(rhythm)}
    length = 8 if int_or_default(bars, 4) >= 8 else 4
    events: list[dict[str, Any]] = []

    def add(slot: str, bar: int, step: int, velocity: int, probability: float = 1.0, grid: str = "1/16", duration: int = 80) -> None:
        events.append(event(slot, bar, step, velocity, probability, grid, duration))

    rhythm_key = tags["rhythm"]
    if tags["sound_direction"] == "electronic" and rhythm_key == "groove":
        # House profile: make the kick's four-on-the-floor pulse line up with
        # the dedicated House bass mode at steps 0, 4, 8 and 12.
        for bar in range(1, length + 1):
            for step in (0, 4, 8, 12):
                add("kick", bar, step, 104)
            for step in (4, 12):
                add("snare", bar, step, 88)
            for step in (2, 6, 10, 14):
                add("closed_hat", bar, step, 66, duration=45)
    elif rhythm_key == "sparse":
        for bar in (1, 3 if length >= 3 else 1):
            add("kick", bar, 0, 92)
        add("perc_1", length, 15, 58, 0.3, duration=60)
    elif rhythm_key == "flow":
        for bar in range(1, length + 1):
            for step in (0, 8):
                add("kick", bar, step, 88)
            add("snare", bar, 12, 60)
            for step in (0, 2, 4, 6, 8, 10, 12, 14):
                add("shaker", bar, step, 54, duration=50)
            add("perc_1", bar, 6 if bar % 2 else 14, 62, 0.4, duration=60)
    elif rhythm_key == "aggressive":
        for bar in range(1, length + 1):
            for step in (0, 3, 4, 8, 10, 12):
                add("kick", bar, step, 112)
            for step in (4, 12):
                add("snare", bar, step, 105)
            for step in range(16):
                add("closed_hat", bar, step, 68 if step % 4 else 78, duration=45)
            for step in (2, 6, 10, 14):
                add("open_hat", bar, step, 72, duration=80)
        add("crash", 1, 0, 105, duration=120)
        add("impact", length, 15, 112, duration=120)
        for step in (12, 13, 14, 15):
            add("fill_hit", length, step, 82 + (step - 12) * 8, duration=60)
    else:
        is_groove = rhythm_key == "groove"
        for bar in range(1, length + 1):
            for step in ((0, 3, 8, 10) if is_groove else (0, 8)):
                add("kick", bar, step, 102 if is_groove else 96)
            for step in (4, 12):
                add("snare", bar, step, 92)
            for step in ((0, 2, 5, 6, 8, 10, 13, 14) if is_groove else (0, 2, 4, 6, 8, 10, 12, 14)):
                add("closed_hat", bar, step, 62 if step % 4 else 74, duration=45)
            if is_groove:
                for step in (7, 15):
                    add("perc_1", bar, step, 64, 0.75, duration=60)
        for step in (14, 15):
            add("fill_hit", length, step, 76 + (step - 14) * 10, duration=60)
    return normalize_pattern(
        {
            "pattern_id": pattern_id(tags, length),
            "name": pattern_name(tags),
            "enabled": True,
            "tags": tags,
            "loop_length_bars": length,
            "default_grid_resolution": "1/16",
            "time_signature": "4/4",
            "events": events,
            "swing": {"enabled": False, "amount": 0.0},
            "humanize": humanize_defaults(tags["energy"]),
            "updated_at": utc_now(),
        }
    )


def event(slot: str, bar: int, step: int, velocity: int, probability: float = 1.0, grid: str = "1/16", duration: int = 80) -> dict[str, Any]:
    slot_key = normalize_slot(slot)
    return {
        "bar": int(bar),
        "step": int(step),
        "grid_resolution": normalize_grid(grid),
        "slot": slot_key,
        "midi_note": DRUM_SLOTS[slot_key]["midi_note"],
        "velocity": max(1, min(127, int(velocity))),
        "probability": max(0.0, min(1.0, float(probability))),
        "micro_timing": 0,
        "duration_ticks": max(1, int(duration)),
        "enabled": True,
    }


def normalize_pattern(pattern: dict[str, Any]) -> dict[str, Any]:
    tags = pattern.get("tags") if isinstance(pattern.get("tags"), dict) else {}
    normalized_tags = {
        "sound_direction": normalize_sound(tags.get("sound_direction", pattern.get("sound_direction", "all"))),
        "energy": normalize_energy(tags.get("energy", pattern.get("energy", "流动"))),
        "rhythm": normalize_rhythm(tags.get("rhythm", pattern.get("rhythm", "groove"))),
    }
    bars = 8 if int_or_default(pattern.get("loop_length_bars"), 4) >= 8 else 4
    grid = normalize_grid(pattern.get("default_grid_resolution"))
    events = [normalize_event(item, bars) for item in pattern.get("events", []) if isinstance(item, dict)]
    return {
        "pattern_id": str(pattern.get("pattern_id") or pattern_id(normalized_tags, bars)),
        "name": str(pattern.get("name") or pattern_name(normalized_tags)),
        "enabled": bool(pattern.get("enabled", True)),
        "tags": normalized_tags,
        "loop_length_bars": bars,
        "default_grid_resolution": grid,
        "time_signature": "4/4",
        "events": events,
        "swing": normalize_swing(pattern.get("swing")),
        "humanize": normalize_humanize(pattern.get("humanize"), normalized_tags["energy"]),
        "updated_at": str(pattern.get("updated_at") or utc_now()),
    }


def normalize_bar_overrides(value: Any, bars: int) -> list[int]:
    if not isinstance(value, list):
        return []
    return sorted({bar for bar in (int_or_default(item, 0) for item in value) if 1 < bar <= bars})


def effective_pattern_events(pattern: dict[str, Any], bars: int | None = None) -> list[dict[str, Any]]:
    source_bars = max(1, min(8, int_or_default(pattern.get("loop_length_bars"), bars or 4)))
    # The saved grid is the only playback source. Bars are never copied or
    # inherited while rendering: an event plays only in its saved bar.
    return [
        {**event}
        for event in pattern.get("events", [])
        if isinstance(event, dict) and 1 <= int_or_default(event.get("bar"), 1) <= source_bars
    ]


def normalize_event(item: dict[str, Any], bars: int) -> dict[str, Any]:
    slot = normalize_slot(item.get("slot"))
    grid = normalize_grid(item.get("grid_resolution"))
    max_step = GRID_STEPS[grid] - 1
    return {
        "bar": max(1, min(bars, int_or_default(item.get("bar"), 1))),
        "step": max(0, min(max_step, int_or_default(item.get("step"), 0))),
        "grid_resolution": grid,
        "slot": slot,
        "midi_note": max(0, min(127, int_or_default(item.get("midi_note"), DRUM_SLOTS[slot]["midi_note"]))),
        "velocity": max(1, min(127, int_or_default(item.get("velocity"), 96))),
        "probability": max(0.0, min(1.0, float_or_default(item.get("probability"), 1.0))),
        "micro_timing": max(-20, min(20, int_or_default(item.get("micro_timing"), 0))),
        "duration_ticks": max(1, min(960, int_or_default(item.get("duration_ticks"), 80))),
        "enabled": bool(item.get("enabled", True)),
    }


def normalize_swing(value: Any) -> dict[str, Any]:
    swing = value if isinstance(value, dict) else {}
    return {"enabled": bool(swing.get("enabled", False)), "amount": max(0.0, min(0.6, float_or_default(swing.get("amount"), 0.0)))}


def normalize_humanize(value: Any, energy: str) -> dict[str, Any]:
    humanize = humanize_defaults(energy)
    if isinstance(value, dict):
        humanize.update(value)
    return {
        "timing_ticks": max(0, min(20, int_or_default(humanize.get("timing_ticks"), 6))),
        "velocity_amount": max(0, min(20, int_or_default(humanize.get("velocity_amount"), 8))),
    }


def humanize_defaults(energy: str) -> dict[str, int]:
    if energy == "静止":
        return {"timing_ticks": 8, "velocity_amount": 8}
    if energy == "高能":
        return {"timing_ticks": 4, "velocity_amount": 6}
    return {"timing_ticks": 6, "velocity_amount": 10}


def normalize_sound(value: Any) -> str:
    text = str(value or "all").strip()
    if text == "all":
        return "all"
    return resolve_sound_direction(text).value


def normalize_energy(value: Any) -> str:
    # Energy value 0 is the valid "静止" state, not a missing value.
    source = "流动" if value is None or (isinstance(value, str) and not value.strip()) else value
    return resolve_energy(source).label


def normalize_rhythm(value: Any) -> str:
    text = str(value or "groove").strip()
    if text == "any":
        return "any"
    return resolve_rhythm(text).value


def normalize_grid(value: Any) -> str:
    text = str(value or "1/16").strip()
    return text if text in GRID_STEPS else "1/16"


def normalize_slot(value: Any) -> str:
    slot = str(value or "kick").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"perc": "perc_1", "tom_low": "low_tom", "tom_high": "high_tom", "fill": "fill_hit", "texture": "texture_perc"}
    slot = aliases.get(slot, slot)
    return slot if slot in DRUM_SLOTS else "kick"


def pattern_id(tags: dict[str, Any], bars: int) -> str:
    energy_slug = {"静止": "still", "流动": "flowing", "高能": "high"}.get(str(tags.get("energy")), str(tags.get("energy", "flowing")))
    raw = f"pattern_{tags.get('sound_direction', 'all')}_{energy_slug}_{tags.get('rhythm', 'groove')}_{bars}"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", raw).strip("_").lower()
    return slug or f"pattern_{uuid.uuid4().hex[:10]}"


def pattern_name(tags: dict[str, Any]) -> str:
    return f"{tags.get('sound_direction', 'all')} / {tags.get('energy', '流动')} / {tags.get('rhythm', 'groove')}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
