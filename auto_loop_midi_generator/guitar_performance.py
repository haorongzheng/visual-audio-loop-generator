from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "guitar_performance_modes.json"
MODE_IDS = (
    "sparse_response", "sparse_swell", "sparse_downstroke", "sparse_open_strum",
    "oud_style_picking", "desert_pulse",
)
ETHNIC_MODE_IDS = frozenset({"oud_style_picking", "desert_pulse"})
DEGREES = (
    "root", "third", "fifth", "seventh", "ninth", "octave_root", "octave_third", "octave_fifth",
    "next_root", "next_fifth",
)
PLAY_MODES = ("single", "stack", "roll_up", "roll_down")
GUITAR_TYPES = ("nylon", "electric")


def event(
    step: int,
    notes: list[str] | tuple[str, ...] | str,
    play_mode: str = "single",
    roll_time_ms: int = 0,
    duration_steps: int = 2,
    velocity_multiplier: float = 1.0,
) -> dict[str, Any]:
    if isinstance(notes, str):
        notes = [] if notes == "rest" else [notes]
    return {
        "step": int(step), "notes": [degree for degree in notes if degree in DEGREES][:4],
        "play_mode": play_mode if play_mode in PLAY_MODES else "single",
        "roll_time_ms": max(0, min(90, int(roll_time_ms))), "duration_steps": max(1, min(16, int(duration_steps))),
        "velocity_multiplier": max(.1, min(2.0, float(velocity_multiplier))), "probability": 1, "enabled": True,
        "note_end_mode": "shared_end",
    }


def _mode(
    mode_id: str,
    name: str,
    label: str,
    description: str,
    events: list[dict[str, Any]],
    *,
    grid: str = "1/8",
    duration: float,
    velocity: tuple[int, int],
    timing: float,
    velocity_amount: float,
    guitar_types: tuple[str, ...] = GUITAR_TYPES,
    sound: tuple[str, ...] = (),
    energy: tuple[str, ...] = ("静止", "流动", "高能"),
    rhythm: tuple[str, ...] = ("sparse", "flow", "standard", "groove", "aggressive"),
    bar4: tuple[str, ...] = ("end_on_root",),
    priority: int = 10,
    category: str = "standard",
    style: str = "guitar",
    humanize_style: str = "natural",
    roll_probability: float = 0.0,
) -> dict[str, Any]:
    return {
        "id": mode_id, "name": name, "label": label, "description": description, "grid": grid,
        "duration_ratio": duration, "velocity_range": list(velocity), "timing_amount": timing,
        "velocity_amount": velocity_amount, "octave_range": [3, 5], "allowed_guitar_types": list(guitar_types),
        "allowed_sound_directions": list(sound or ("ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic")),
        "allowed_energy": list(energy), "allowed_rhythm": list(rhythm), "bar_4_strategies": list(bar4),
        "priority": priority, "enabled": True, "version": 2, "category": category, "style": style,
        "humanize_style": humanize_style, "roll_probability": max(0.0, min(1.0, roll_probability)),
        "variants": [{"id": f"{mode_id}_a", "name": "Variant A", "grid": grid, "events": events, "priority": 10, "enabled": True, "version": 2}],
    }


def default_guitar_performance_modes() -> dict[str, dict[str, Any]]:
    modes = {
        "sparse_response": _mode("sparse_response", "Sparse Response", "留白扫弦回应", "少量长音与慢速轻扫弦", [
            event(0, ["root", "fifth", "seventh", "octave_third"], "roll_up", 38, 5), event(8, "fifth"), event(12, ["third", "fifth", "seventh"], "roll_down", 32, 4),
        ], duration=.72, velocity=(56, 82), timing=0, velocity_amount=.14, rhythm=("sparse", "flow", "standard"), bar4=("early_release", "end_on_root", "remove_last_event"), priority=25),
        "sparse_swell": _mode("sparse_swell", "Sparse Swell", "留白渐强扫弦", "每小节只留下两次缓慢向上扫弦", [
            event(0, ["root", "fifth", "seventh", "octave_third"], "roll_up", 42, 6, .92), event(8, ["third", "fifth", "seventh"], "roll_up", 34, 4, .78),
        ], duration=.82, velocity=(52, 78), timing=0, velocity_amount=.13, rhythm=("sparse", "flow", "standard"), bar4=("early_release", "end_on_root"), priority=24),
        "sparse_downstroke": _mode("sparse_downstroke", "Sparse Downstroke", "留白向下扫弦", "向下扫弦后留出完整呼吸空间", [
            event(0, ["root", "third", "fifth", "seventh"], "roll_down", 36, 5, .9), event(8, "fifth", duration_steps=2, velocity_multiplier=.72), event(12, ["third", "fifth", "seventh"], "roll_down", 28, 3, .8),
        ], duration=.76, velocity=(54, 80), timing=0, velocity_amount=.13, rhythm=("sparse", "flow", "standard"), bar4=("early_release", "remove_last_event"), priority=23),
        "sparse_open_strum": _mode("sparse_open_strum", "Sparse Open Strum", "留白开放扫弦", "在整拍直接起音的开放扫弦", [
            event(0, ["root", "fifth", "seventh", "octave_third"], "roll_up", 34, 5, .88), event(8, ["third", "fifth", "seventh"], "roll_down", 30, 4, .8),
        ], duration=.78, velocity=(54, 80), timing=0, velocity_amount=.14, rhythm=("sparse", "flow", "standard"), bar4=("end_on_root", "early_release", "remove_last_event"), priority=23),
        "oud_style_picking": _mode("oud_style_picking", "Oud Style Picking", "乌德琴式拨弦", "低音 Drone 与不规则高音回应的中东式尼龙吉他拨弦", [
            event(0, "root", "single", 0, 4, 1.1),
            event(3, ["fifth", "octave_root"], "roll_up", 35, 3, .85),
            event(6, "third", "single", 0, 2, .75),
            event(8, ["root", "fifth", "seventh"], "roll_up", 45, 4, .95),
            event(12, "octave_third", "single", 0, 2, .8),
            event(14, "fifth", "single", 0, 2, .7),
        ], grid="1/16", duration=.78, velocity=(58, 88), timing=.08, velocity_amount=.15,
        guitar_types=("nylon",), sound=("ethnic", "organic", "cinematic"), energy=("静止", "流动"),
        rhythm=("sparse", "flow", "standard", "groove"), bar4=("end_on_root", "early_release"), priority=90,
        category="ethnic", style="middle_eastern", humanize_style="organic", roll_probability=.45),
        "desert_pulse": _mode("desert_pulse", "Desert Pulse", "沙漠脉冲", "Root Drone 与高音回应组成的民族电影循环", [
            event(0, ["root", "fifth"], "roll_up", 28, 3, 1.0),
            event(4, "octave_root", "single", 0, 2, .8),
            event(6, ["third", "fifth"], "stack", 0, 2, .75),
            event(8, "root", "single", 0, 4, 1.05),
            event(12, ["fifth", "seventh", "octave_third"], "roll_down", 40, 3, .85),
            event(15, "fifth", "single", 0, 1, .7),
        ], grid="1/16", duration=.72, velocity=(62, 96), timing=.06, velocity_amount=.18,
        guitar_types=("nylon",), sound=("ethnic", "organic", "cinematic"), energy=("静止", "流动"),
        rhythm=("flow", "standard", "groove"), bar4=("end_on_root", "remove_last_event"), priority=88,
        category="ethnic", style="middle_eastern", humanize_style="organic", roll_probability=.35),
    }
    return modes


def normalize_event(raw: dict[str, Any]) -> dict[str, Any]:
    notes = raw.get("notes")
    if not isinstance(notes, list):
        degree = str(raw.get("degree", ""))
        notes = [] if degree in {"", "rest"} else [degree]
    normalized = event(
        int(raw.get("step", 0) or 0), [str(degree) for degree in notes], str(raw.get("play_mode") or "single"),
        int(raw.get("roll_time_ms", 0) or 0), int(raw.get("duration_steps", 2) or 2), float(raw.get("velocity_multiplier", 1) or 1),
    )
    normalized["probability"] = max(0, min(1, float(raw.get("probability", 1) or 0)))
    normalized["enabled"] = bool(raw.get("enabled", True))
    return normalized


def _normalize_mode(mode: dict[str, Any]) -> dict[str, Any]:
    copy = dict(mode)
    copy["variants"] = []
    for variant in mode.get("variants", [])[:4] if isinstance(mode.get("variants"), list) else []:
        if not isinstance(variant, dict):
            continue
        item = dict(variant)
        item["events"] = [normalize_event(event_data) for event_data in variant.get("events", []) if isinstance(event_data, dict)]
        copy["variants"].append(item)
    return copy


def load_guitar_performance_modes() -> dict[str, dict[str, Any]]:
    modes = default_guitar_performance_modes()
    try:
        saved = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.is_file() else []
    except (OSError, ValueError):
        saved = []
    for item in saved if isinstance(saved, list) else []:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id in modes:
            modes[mode_id].update({key: value for key, value in _normalize_mode(item).items() if key in modes[mode_id]})
    return {mode_id: _normalize_mode(mode) for mode_id, mode in modes.items()}


def save_guitar_performance_modes(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    modes = default_guitar_performance_modes()
    allowed = {"name", "label", "description", "grid", "duration_ratio", "velocity_range", "timing_amount", "velocity_amount", "octave_range", "allowed_guitar_types", "allowed_sound_directions", "allowed_energy", "allowed_rhythm", "bar_4_strategies", "priority", "enabled", "version", "category", "style", "humanize_style", "roll_probability", "variants"}
    for item in items:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id not in modes:
            continue
        modes[mode_id].update({key: value for key, value in _normalize_mode(item).items() if key in allowed})
        modes[mode_id]["id"] = mode_id
        modes[mode_id]["enabled"] = bool(modes[mode_id].get("enabled", True))
        modes[mode_id]["duration_ratio"] = max(.05, min(1.0, float(modes[mode_id].get("duration_ratio", .6))))
        modes[mode_id]["timing_amount"] = max(0.0, min(.2, float(modes[mode_id].get("timing_amount", .04))))
        modes[mode_id]["velocity_amount"] = max(0.0, min(.3, float(modes[mode_id].get("velocity_amount", .1))))
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(list(modes.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    return {mode_id: _normalize_mode(mode) for mode_id, mode in modes.items()}


def reset_guitar_performance_modes() -> dict[str, dict[str, Any]]:
    return save_guitar_performance_modes(list(default_guitar_performance_modes().values()))


def is_guitar_instrument(instrument: dict[str, Any] | None) -> bool:
    return bool(instrument and instrument.get("performance_engine") == "guitar_single_note" and instrument.get("guitar_type") in GUITAR_TYPES)


def guitar_range(guitar_type: str) -> tuple[int, int]:
    return (40, 76) if guitar_type == "nylon" else (45, 81)


AUTO_BY_TYPE_AND_SOUND = {guitar_type: {sound: MODE_IDS[:4] for sound in ("ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic")} for guitar_type in GUITAR_TYPES}


def ethnic_auto_mode(guitar_type: str, sound: str, energy: str, rhythm: str, emotion: str) -> str | None:
    if guitar_type != "nylon" or sound not in {"ethnic", "organic", "cinematic"}:
        return None
    if sound == "cinematic" or energy == "静止" or emotion in {"深沉", "平静", "忧伤"} and rhythm != "groove":
        return "oud_style_picking"
    if rhythm == "groove" or energy == "流动":
        return "desert_pulse"
    return "oud_style_picking"


def select_guitar_performance(guitar_type: str, sound: str, energy: str, rhythm: str, rng: random.Random, mode_override: str = "auto", variant_override: str = "auto", mode_data: dict[str, dict[str, Any]] | None = None, emotion: str = "") -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    modes = mode_data or load_guitar_performance_modes()
    if mode_override in modes and modes[mode_override].get("enabled", True) and guitar_type in modes[mode_override].get("allowed_guitar_types", []) and sound in modes[mode_override].get("allowed_sound_directions", []):
        mode, source = modes[mode_override], "manual"
    else:
        ethnic_mode_id = ethnic_auto_mode(guitar_type, sound, energy, rhythm, emotion)
        candidates = [ethnic_mode_id] if ethnic_mode_id else list(AUTO_BY_TYPE_AND_SOUND.get(guitar_type, {}).get(sound, MODE_IDS[:4]))
        candidates = [mode_id for mode_id in candidates if mode_id in modes and modes[mode_id].get("enabled", True) and guitar_type in modes[mode_id].get("allowed_guitar_types", []) and sound in modes[mode_id].get("allowed_sound_directions", []) and energy in modes[mode_id].get("allowed_energy", []) and rhythm in modes[mode_id].get("allowed_rhythm", [])]
        valid = candidates
        if not valid:
            valid = [mode_id for mode_id, item in modes.items() if item.get("enabled", True) and guitar_type in item.get("allowed_guitar_types", [])]
        if not valid:
            return None, None, "standard_fallback"
        weights = [max(1, int(modes[mode_id].get("priority", 1))) for mode_id in valid]
        mode, source = modes[rng.choices(valid, weights=weights, k=1)[0]], "auto"
    variants = [variant for variant in mode.get("variants", []) if variant.get("enabled", True)]
    variant = next((item for item in variants if item.get("id") == variant_override), None) or (rng.choice(variants) if variants else None)
    return mode, variant, source if variant else "standard_fallback"


def _place(pc: int, low: int, high: int) -> int:
    return _fit_range(low + ((pc - low) % 12), low, high)


def _fit_range(note: int, low: int, high: int) -> int:
    while note < low:
        note += 12
    while note > high:
        note -= 12
    return max(low, min(high, note))


def chord_degree_pitch(degree: str, chord: Any, next_chord: Any, previous_pitch: int | None, guitar_type: str) -> int | None:
    low, high = guitar_range(guitar_type)
    root_pc = int(chord.root_pc)
    tones = {tone.role: (root_pc + tone.interval) % 12 for tone in chord.tones}
    root = _place(root_pc, max(low, 48 if guitar_type == "electric" else 43), high)
    third = tones.get("3", tones.get("sus4", tones.get("sus2", (root_pc + 4) % 12)))
    fifth = tones.get("5", (root_pc + 7) % 12)
    seventh = tones.get("7", fifth)
    if degree == "next_root":
        return _place(int(next_chord.root_pc), root, high)
    if degree == "next_fifth":
        return _place((int(next_chord.root_pc) + 7) % 12, root, high)
    if degree == "ninth" and "9" not in tones:
        return _fit_range(root + 12, low, high)
    pcs = {"root": root_pc, "third": third, "fifth": fifth, "seventh": seventh, "ninth": tones.get("9", root_pc), "octave_root": root_pc, "octave_third": third, "octave_fifth": fifth}
    if degree not in pcs:
        return None
    pitch = _place(pcs[degree], root, high)
    return _fit_range(pitch + (12 if degree.startswith("octave_") else 0), low, high)


def guitar_voicing(degrees: list[str], chord: Any, next_chord: Any, guitar_type: str) -> list[tuple[str, int]]:
    low, high = guitar_range(guitar_type)
    pairs = [(degree, chord_degree_pitch(degree, chord, next_chord, None, guitar_type)) for degree in degrees[:4]]
    pairs = [(degree, pitch) for degree, pitch in pairs if pitch is not None]
    deduped: list[tuple[str, int]] = []
    seen: set[int] = set()
    for degree, pitch in pairs:
        if pitch not in seen:
            seen.add(pitch)
            deduped.append((degree, pitch))
    pairs = deduped
    for index, (degree, pitch) in enumerate(pairs):
        while pitch - min(item[1] for item in pairs) > 19 and pitch - 12 >= low:
            pitch -= 12
        pairs[index] = (degree, pitch)
    remove_order = ("ninth", "seventh", "octave_fifth", "octave_third")
    while len(pairs) > 1 and max(item[1] for item in pairs) - min(item[1] for item in pairs) > 19:
        removable = next((degree for degree in remove_order if any(item[0] == degree for item in pairs)), None)
        if removable is None:
            highest = max(range(len(pairs)), key=lambda index: pairs[index][1])
            degree, pitch = pairs[highest]
            if pitch - 12 >= low:
                pairs[highest] = (degree, pitch - 12)
            else:
                break
        else:
            pairs = [item for item in pairs if item[0] != removable]
    return [(degree, _fit_range(pitch, low, high)) for degree, pitch in pairs]


def _event_variant(events: list[dict[str, Any]], bar: int, strategy: str) -> list[dict[str, Any]]:
    items = [dict(item) for item in events if item.get("enabled", True) and item.get("notes")]
    if bar == 1 and items:
        single_index = next((index for index, item in reversed(list(enumerate(items))) if item.get("play_mode") == "single"), len(items) - 1)
        items.pop(single_index)
    elif bar == 2:
        for item in items:
            if item.get("play_mode") == "stack":
                item["play_mode"] = "roll_up"
                item["roll_time_ms"] = 32
                break
        else:
            for item in items:
                if "seventh" in item.get("notes", []):
                    item["notes"] = ["fifth" if degree == "seventh" else degree for degree in item["notes"]]
                    break
    elif bar == 3 and items:
        if strategy in {"early_release", "remove_last_event"}:
            items.pop()
        elif strategy.startswith("end_on_"):
            items[-1]["notes"] = [strategy.replace("end_on_", "")]
            items[-1]["play_mode"] = "single"
        elif strategy == "next_chord_pickup":
            items[-1]["notes"] = ["next_root"]
            items[-1]["play_mode"] = "single"
        elif items[-1].get("play_mode") in {"roll_up", "roll_down"}:
            items[-1]["roll_time_ms"] = min(90, int(items[-1].get("roll_time_ms", 45) * 1.08))
    return items


def guitar_events(
    chords: list[Any], bars: int, velocity: int, guitar_type: str, sound: str, energy: str, rhythm: str,
    rng: random.Random, mode_override: str = "auto", variant_override: str = "auto", mode_data: dict[str, dict[str, Any]] | None = None,
    bpm: int = 100, roll_amount: float = 1.0, emotion: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    mode, variant, selection = select_guitar_performance(guitar_type, sound, energy, rhythm, rng, mode_override, variant_override, mode_data, emotion)
    if not mode or not variant:
        return [], None
    roll_amount = max(0.0, min(1.5, float(roll_amount)))
    profile = {"nylon": (1.08, 1.08, .94), "electric": (.92, .90, 1.02)}[guitar_type]
    energy_roll = {"静止": 1.12, "流动": 1.0, "高能": .86}.get(energy, 1.0)
    output: list[dict[str, Any]] = []
    event_records: list[dict[str, Any]] = []
    for bar in range(bars):
        if bar >= 4:
            output.extend([{**item, "bar": bar} for item in output if item["bar"] == bar - 4])
            event_records.extend([{**item, "bar": bar} for item in event_records if item["bar"] == bar - 4])
            continue
        raw_events = _event_variant(variant.get("events", []), bar, mode.get("bar_4_strategies", ["end_on_root"])[0])
        if energy == "静止" and mode.get("category") != "ethnic" and len(raw_events) > 4:
            raw_events = [item for index, item in enumerate(raw_events) if index % 2 == 0 or item.get("play_mode") != "single"][:6]
        for event_index, item in enumerate(raw_events):
            notes = [degree for degree in item.get("notes", []) if degree in DEGREES][:4]
            if not notes:
                continue
            play_mode = str(item.get("play_mode", "single"))
            if play_mode not in PLAY_MODES:
                play_mode = "single"
            if play_mode == "single":
                notes = notes[:1]
            if roll_amount == 0 and play_mode in {"roll_up", "roll_down"}:
                play_mode = "stack"
            voiced = guitar_voicing(notes, chords[bar], chords[(bar + 1) % bars], guitar_type)
            if not voiced:
                continue
            if play_mode == "single":
                voiced = voiced[:1]
            if play_mode == "roll_up":
                voiced.sort(key=lambda item: item[1])
            elif play_mode == "roll_down":
                voiced.sort(key=lambda item: item[1], reverse=True)
            requested_roll = int(item.get("roll_time_ms", 45) or 45)
            roll_time = 0 if play_mode not in {"roll_up", "roll_down"} else max(12, min(90, int(requested_roll * roll_amount * profile[0] * energy_roll)))
            base_duration = max(24, int(int(item.get("duration_steps", 1)) * 120 * float(mode["duration_ratio"]) * profile[1]))
            duration_limits = {mode_id: .12 for mode_id in MODE_IDS}
            base_duration = max(24, int(base_duration * (1 + rng.uniform(-duration_limits.get(mode["id"], .08), duration_limits.get(mode["id"], .08)))))
            # Guitar attacks stay exactly on the selected grid; the short roll only spreads strings within a strum.
            event_timing = 0
            roll_ticks = int(round(roll_time * max(1, bpm) * 480 / 60_000))
            offsets = [0] if len(voiced) <= 1 else [int(round(roll_ticks * index / (len(voiced) - 1))) for index in range(len(voiced))]
            low_velocity, high_velocity = mode.get("velocity_range", [60, 90])
            base_velocity = int(rng.randint(int(low_velocity), int(high_velocity)) * float(item.get("velocity_multiplier", 1)) * profile[2])
            event_id = f"{bar}:{event_index}"
            event_records.append({"bar": bar, "event_id": event_id, "step": int(item.get("step", 0)), "notes": [degree for degree, _ in voiced], "play_mode": play_mode, "roll_time_ms": roll_time, "duration": base_duration, "event_timing": event_timing})
            for note_index, ((degree, pitch), offset) in enumerate(zip(voiced, offsets)):
                curve = (1.0, .96, .92, .90)[min(3, note_index)] if play_mode in {"roll_up", "roll_down"} else 1.0
                note_velocity = max(1, min(127, int(base_velocity * curve)))
                duration = max(12, base_duration - offset)
                output.append({"bar": bar, "step": float(item.get("step", 0)), "event_id": event_id, "degree": degree, "pitch": pitch, "duration": duration, "velocity": note_velocity, "timing": event_timing, "offset_ticks": offset, "play_mode": play_mode, "roll_time_ms": roll_time, "note_end_mode": "shared_end"})
    counts = {kind: sum(1 for item in event_records if item["play_mode"] == kind) for kind in PLAY_MODES}
    average_roll = round(sum(item["roll_time_ms"] for item in event_records if item["play_mode"] in {"roll_up", "roll_down"}) / max(1, counts["roll_up"] + counts["roll_down"]), 1)
    manifest = {"enabled": True, "guitar_type": guitar_type, "instrument": "nylon_guitar" if guitar_type == "nylon" else "electric_guitar", "category": mode.get("category", "standard"), "pattern": mode["id"], "style": mode.get("style", "guitar"), "humanize_style": mode.get("humanize_style", "natural"), "roll_probability": mode.get("roll_probability", 0), "mode": mode["id"], "mode_name": mode["name"], "variant_id": variant["id"], "variant_name": variant.get("name", "Variant A"), "selection_source": selection, "reason": f"{guitar_type} guitar + {sound} + {energy} + {rhythm}", "main_mode_locked": True, "main_variant_locked": True, "bar_4_strategy": mode.get("bar_4_strategies", ["end_on_root"])[0], "event_count": len(event_records), "note_count": len(output), "single_event_count": counts["single"], "stack_event_count": counts["stack"], "roll_up_event_count": counts["roll_up"], "roll_down_event_count": counts["roll_down"], "average_roll_time_ms": average_roll, "maximum_notes_per_event": max((len(item["notes"]) for item in event_records), default=0), "midi_range": list(guitar_range(guitar_type)), "special_articulation_used": False, "midi_roll_simulation_used": bool(counts["roll_up"] or counts["roll_down"]), "humanize_limits": {"timing": mode["timing_amount"], "velocity": mode["velocity_amount"], "duration": duration_limits.get(mode["id"], .08)}}
    return output, manifest
