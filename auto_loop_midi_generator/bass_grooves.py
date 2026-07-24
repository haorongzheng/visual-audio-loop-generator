from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "bass_groove_modes.json"
MODE_IDS = (
    "sustain_root", "root_fifth", "pulse", "groove_pickup", "house_four_on_floor", "808_sync",
    "ethnic_drone", "middle_eastern_pulse", "cinematic_sub_sustain", "cinematic_emotional_movement",
)
ELECTRONIC_MODE_IDS = frozenset({"house_four_on_floor", "808_sync"})
ETHNIC_MODE_IDS = frozenset({"ethnic_drone", "middle_eastern_pulse"})
CINEMATIC_MODE_IDS = frozenset({"cinematic_sub_sustain", "cinematic_emotional_movement"})
ELECTRONIC_RHYTHM_PROFILES = {
    "groove": "house_groove",
    "aggressive": "edm_drive",
    "flow": "trap_hybrid",
}


def _event(step: int, degree: str, duration_steps: int, velocity_multiplier: float = 1.0, probability: float = 1.0, glide: bool = False) -> dict[str, Any]:
    return {
        "step": step, "degree": degree, "duration_steps": duration_steps,
        "velocity_multiplier": velocity_multiplier, "probability": probability,
        "glide": glide, "enabled": True,
    }


def default_bass_grooves() -> dict[str, dict[str, Any]]:
    return {
        "sustain_root": {"id": "sustain_root", "name": "Sustain Root", "label": "长音根音", "description": "稳定的根音长音", "grid": "1/8", "allowed_degrees": ["root", "fifth", "octave", "next_root_pickup"], "duration_ratio": .85, "velocity_range": [58, 78], "timing_amount": .04, "allowed_sound_directions": ["ambient", "cinematic", "ethnic"], "allowed_energy": ["静止", "流动", "高能"], "allowed_rhythm": ["sparse", "flow", "standard"], "bar_4_strategies": ["early_release", "next_root_pickup"], "priority": 10, "enabled": True, "variants": [
            {"id": "sustain_root_a", "name": "长根音", "events": [_event(0, "root", 15)]},
            {"id": "sustain_root_b", "name": "前半长音", "events": [_event(0, "root", 10)]},
            {"id": "sustain_root_c", "name": "根音加引导", "events": [_event(0, "root", 13), _event(15, "next_root_pickup", 1, .62)]},
            {"id": "sustain_root_d", "name": "根音五度支撑", "events": [_event(0, "root", 9), _event(10, "fifth", 4, .72)]},
        ]},
        "root_fifth": {"id": "root_fifth", "name": "Root Fifth", "label": "根音五度", "description": "有限运动的基础支撑", "grid": "1/8", "allowed_degrees": ["root", "fifth", "octave", "next_root_pickup", "ghost_root", "ghost_fifth"], "duration_ratio": .55, "velocity_range": [66, 90], "timing_amount": .07, "allowed_sound_directions": ["acoustic", "organic", "vintage", "ethnic", "ambient"], "allowed_energy": ["静止", "流动", "高能"], "allowed_rhythm": ["sparse", "flow", "standard", "groove"], "bar_4_strategies": ["next_root_pickup", "early_release"], "priority": 20, "enabled": True, "variants": [
            {"id": "root_fifth_a", "name": "根音五度", "events": [_event(0, "root", 6), _event(8, "fifth", 6, .82)]},
            {"id": "root_fifth_b", "name": "根音重复五度", "events": [_event(0, "root", 4), _event(6, "root", 3, .82), _event(12, "fifth", 3, .88)]},
            {"id": "root_fifth_c", "name": "根音五度引导", "events": [_event(0, "root", 6), _event(8, "fifth", 4, .84), _event(15, "next_root_pickup", 1, .66)]},
            {"id": "root_fifth_d", "name": "根音八度五度", "events": [_event(0, "root", 4), _event(6, "octave", 3, .78), _event(12, "fifth", 3, .88)]},
        ]},
        "pulse": {"id": "pulse", "name": "Pulse", "label": "脉冲低音", "description": "紧密且稳定的低频脉冲", "grid": "1/8", "allowed_degrees": ["root", "octave", "fifth", "next_root_pickup"], "duration_ratio": .30, "velocity_range": [78, 105], "timing_amount": .02, "allowed_sound_directions": ["electronic", "cinematic"], "allowed_energy": ["静止", "流动", "高能"], "allowed_rhythm": ["standard", "groove", "aggressive", "flow"], "bar_4_strategies": ["drop_last_pulse", "next_root_pickup", "octave_finish"], "priority": 30, "enabled": True, "variants": [
            {"id": "pulse_a", "name": "四分脉冲", "events": [_event(step, "root", 2, 1 if step in {0, 8} else .88) for step in (0, 4, 8, 12)]},
            {"id": "pulse_b", "name": "八分脉冲", "events": [_event(step, "root", 1, 1 if step % 4 == 0 else .82) for step in range(0, 16, 2)]},
            {"id": "pulse_c", "name": "根音八度脉冲", "events": [_event(step, "root" if index % 2 == 0 else "octave", 1, 1 if index % 2 == 0 else .82) for index, step in enumerate(range(0, 16, 2))]},
            {"id": "pulse_d", "name": "稀疏混合脉冲", "events": [_event(0, "root", 2), _event(4, "root", 2, .84), _event(8, "octave", 2, .88), _event(12, "root", 2)]},
        ]},
        "groove_pickup": {"id": "groove_pickup", "name": "Groove Pickup", "label": "律动过门", "description": "根音为主的自然回环", "grid": "1/16", "allowed_degrees": ["root", "fifth", "octave", "diatonic_passing", "chromatic_approach", "next_root_pickup", "ghost_root", "ghost_fifth"], "duration_ratio": .35, "velocity_range": [72, 104], "timing_amount": .10, "allowed_sound_directions": ["vintage", "electronic", "organic", "acoustic"], "allowed_energy": ["流动", "高能"], "allowed_rhythm": ["flow", "groove", "standard", "aggressive"], "bar_4_strategies": ["chromatic_pickup", "diatonic_pickup", "fifth_to_root", "short_silence_then_pickup"], "priority": 40, "enabled": True, "variants": [
            {"id": "groove_pickup_a", "name": "基础律动", "events": [_event(0, "root", 3), _event(6, "fifth", 2, .80), _event(12, "root", 2, .90)]},
            {"id": "groove_pickup_b", "name": "切分根音五度", "events": [_event(0, "root", 3), _event(5, "fifth", 2, .78), _event(10, "root", 2, .88), _event(14, "octave", 1, .70)]},
            {"id": "groove_pickup_c", "name": "引导律动", "events": [_event(0, "root", 3), _event(7, "fifth", 2, .80), _event(11, "root", 2, .88), _event(15, "next_root_pickup", 1, .66)]},
            {"id": "groove_pickup_d", "name": "八度律动", "events": [_event(0, "root", 3), _event(4, "octave", 2, .78), _event(9, "fifth", 2, .80), _event(13, "root", 2, .88)]},
        ]},
        "house_four_on_floor": {"id": "house_four_on_floor", "name": "House Four On Floor", "label": "House 四拍低音", "description": "四拍 Kick 对齐的根音、八度与五度低音", "category": "electronic", "grid": "1/4", "allowed_degrees": ["root", "octave_root", "fifth", "next_root"], "duration_ratio": .75, "velocity_range": [80, 110], "timing_amount": .02, "allowed_sound_directions": ["electronic"], "allowed_energy": ["流动", "高能"], "allowed_rhythm": ["groove", "aggressive"], "allowed_rhythm_profiles": ["house_groove", "edm_drive"], "bar_4_strategies": ["next_root_pickup", "drop_last", "octave_finish"], "root_weight": .65, "octave_weight": .25, "fifth_weight": .10, "ghost_probability": .05, "pickup_probability": .15, "glide_enabled": False, "glide_time_ms": 0, "pitch_bend_range": 2, "priority": 70, "enabled": True, "variants": [
            {"id": "house_four_on_floor_a", "name": "四拍根音八度", "events": [_event(0, "root", 3), _event(4, "octave_root", 3), _event(8, "root", 3), _event(12, "fifth", 3)]},
        ]},
        "808_sync": {"id": "808_sync", "name": "808 Sync", "label": "808 切分低音", "description": "长音切分、空拍与下一和弦 Pickup 的 808 低音", "category": "electronic", "grid": "1/16", "allowed_degrees": ["root", "octave_root", "next_root"], "duration_ratio": .95, "velocity_range": [90, 120], "timing_amount": .01, "allowed_sound_directions": ["electronic"], "allowed_energy": ["流动", "高能"], "allowed_rhythm": ["flow", "aggressive"], "allowed_rhythm_profiles": ["trap_hybrid", "edm_drive"], "bar_4_strategies": ["next_root_pickup", "drop_last"], "root_weight": .80, "octave_weight": .15, "pickup_weight": .05, "ghost_probability": 0, "slide_probability": .25, "glide_enabled": True, "glide_time_ms": 100, "pitch_bend_range": 2, "priority": 80, "enabled": True, "variants": [
            {"id": "808_sync_a", "name": "808 切分 Pickup", "events": [_event(0, "root", 8), _event(6, "root", 4), _event(10, "octave_root", 3), _event(14, "next_root", 2, 1.0, 1.0, True)]},
        ]},
        "ethnic_drone": {"id": "ethnic_drone", "name": "Ethnic Drone Bass", "label": "民族持续低音", "description": "中东、波斯与沙漠音乐的根音 Drone 支撑", "category": "ethnic", "style": "middle_eastern", "grid": "1/4", "allowed_degrees": ["root", "fifth"], "duration_ratio": .95, "velocity_range": [58, 82], "timing_amount": .02, "velocity_amount": .08, "density": .25, "sustain": .95, "root_probability": .85, "fifth_probability": .15, "ghost_probability": 0, "allowed_sound_directions": ["ethnic", "organic", "cinematic"], "allowed_energy": ["静止", "流动"], "allowed_rhythm": ["sparse", "standard"], "bar_4_strategies": ["repeat"], "priority": 90, "enabled": True, "variants": [
            {"id": "ethnic_drone_a", "name": "根音 Drone", "events": [_event(0, "root", 16), _event(8, "fifth", 4, .65), _event(12, "root", 4, .8)]},
        ]},
        "middle_eastern_pulse": {"id": "middle_eastern_pulse", "name": "Middle Eastern Pulse Bass", "label": "中东脉冲低音", "description": "跟随 Darbuka 与 Oud 循环的根音、五度民族脉冲", "category": "ethnic", "style": "middle_eastern", "grid": "1/16", "allowed_degrees": ["root", "fifth", "octave_root"], "duration_ratio": .65, "velocity_range": [68, 100], "timing_amount": .05, "velocity_amount": .12, "density": .45, "sustain": .65, "root_probability": .7, "fifth_probability": .2, "octave_probability": .1, "ghost_probability": .05, "allowed_sound_directions": ["ethnic", "organic", "cinematic"], "allowed_energy": ["流动", "高能"], "allowed_rhythm": ["flow", "standard", "groove"], "bar_4_strategies": ["repeat"], "priority": 88, "enabled": True, "variants": [
            {"id": "middle_eastern_pulse_a", "name": "Darbuka 脉冲", "events": [_event(0, "root", 3, 1.05), _event(3, "fifth", 2, .75), _event(6, "root", 2, .9), _event(8, "root", 3), _event(11, "fifth", 2, .7), _event(14, "octave_root", 2, .8)]},
        ]},
        "cinematic_sub_sustain": {"id": "cinematic_sub_sustain", "name": "Cinematic Sub Sustain", "label": "电影低频持续", "description": "以长根音和极少五度变化提供电影低频重量，不使用流行律动", "category": "cinematic", "style": "sub_sustain", "grid": "1 bar", "allowed_degrees": ["root", "fifth", "octave_root"], "duration_ratio": 1.0, "velocity_range": [62, 85], "timing_amount": .01, "velocity_amount": .08, "density": .15, "sustain": 1.0, "harmony_follow": True, "root_probability": .85, "fifth_probability": .15, "ghost_probability": 0, "allowed_sound_directions": ["ambient", "cinematic"], "allowed_emotions": ["深沉", "平静", "忧伤"], "allowed_energy": ["静止", "流动"], "allowed_rhythm": ["sparse", "flow", "standard", "groove"], "bar_4_strategies": ["repeat"], "priority": 96, "enabled": True, "variants": [
            {"id": "cinematic_sub_sustain_a", "name": "根音低频长音", "events": [_event(0, "root", 16)]},
        ]},
        "cinematic_emotional_movement": {"id": "cinematic_emotional_movement", "name": "Cinematic Emotional Movement", "label": "电影情绪推进低音", "description": "缓慢跟随和声变化的根音、八度与五度推进，避免切分和快速旋律", "category": "cinematic", "style": "emotional_low_movement", "grid": "1/2 bar", "allowed_degrees": ["root", "fifth", "octave_root"], "duration_ratio": .9, "velocity_range": [70, 95], "timing_amount": .02, "velocity_amount": .15, "density": .35, "sustain": .85, "harmony_follow": True, "root_probability": .7, "fifth_probability": .15, "octave_probability": .1, "third_probability": .05, "ghost_probability": 0, "allowed_sound_directions": ["ambient", "cinematic"], "allowed_emotions": ["忧伤", "明亮", "激昂"], "allowed_energy": ["流动", "高能"], "allowed_rhythm": ["flow", "standard", "groove", "aggressive"], "bar_4_strategies": ["return_to_root"], "priority": 95, "enabled": True, "variants": [
            {"id": "cinematic_emotional_movement_a", "name": "低频情绪推进", "events": [_event(0, "root", 8), _event(8, "octave_root", 7, .9)]},
        ]},
    }


def load_bass_grooves() -> dict[str, dict[str, Any]]:
    defaults = default_bass_grooves()
    try:
        saved = json.loads(DB_PATH.read_text(encoding="utf-8")) if DB_PATH.is_file() else []
    except (OSError, ValueError):
        saved = []
    for item in saved if isinstance(saved, list) else []:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id in defaults:
            defaults[mode_id].update({key: value for key, value in item.items() if key in defaults[mode_id]})
            defaults[mode_id]["variants"] = list(defaults[mode_id].get("variants", []))[:4]
    return defaults


def save_bass_grooves(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    modes = default_bass_grooves()
    allowed = {"name", "label", "description", "category", "style", "grid", "allowed_degrees", "duration_ratio", "velocity_range", "timing_amount", "velocity_amount", "density", "sustain", "harmony_follow", "allowed_sound_directions", "allowed_emotions", "allowed_energy", "allowed_rhythm", "allowed_rhythm_profiles", "bar_4_strategies", "root_weight", "octave_weight", "fifth_weight", "pickup_weight", "root_probability", "fifth_probability", "octave_probability", "ghost_probability", "pickup_probability", "slide_probability", "glide_enabled", "glide_time_ms", "pitch_bend_range", "priority", "enabled", "variants"}
    for item in items:
        mode_id = str(item.get("id", "")) if isinstance(item, dict) else ""
        if mode_id not in modes:
            continue
        modes[mode_id].update({key: value for key, value in item.items() if key in allowed})
        modes[mode_id]["id"] = mode_id
        modes[mode_id]["enabled"] = bool(modes[mode_id].get("enabled", True))
        modes[mode_id]["duration_ratio"] = max(.05, min(1.0, float(modes[mode_id].get("duration_ratio", .5))))
        modes[mode_id]["sustain"] = max(.05, min(1.0, float(modes[mode_id].get("sustain", modes[mode_id]["duration_ratio"]))))
        modes[mode_id]["timing_amount"] = max(0.0, min(.2, float(modes[mode_id].get("timing_amount", .05))))
        modes[mode_id]["harmony_follow"] = bool(modes[mode_id].get("harmony_follow", False))
        modes[mode_id]["glide_enabled"] = bool(modes[mode_id].get("glide_enabled", False))
        modes[mode_id]["glide_time_ms"] = max(0, min(300, int(modes[mode_id].get("glide_time_ms", 0) or 0)))
        modes[mode_id]["pitch_bend_range"] = max(0, min(24, int(modes[mode_id].get("pitch_bend_range", 2) or 0)))
        modes[mode_id]["variants"] = list(modes[mode_id].get("variants", []))[:4]
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(list(modes.values()), ensure_ascii=False, indent=2), encoding="utf-8")
    return modes


def reset_bass_grooves() -> dict[str, dict[str, Any]]:
    return save_bass_grooves(list(default_bass_grooves().values()))


def cinematic_mode_id(sound: str, energy: str, emotion: str, foundation_mode: str = "") -> str | None:
    """Return the one sparse cinematic bass language that matches the foundation."""
    if sound not in {"ambient", "cinematic"}:
        return None
    if foundation_mode == "string_long_pad":
        return "cinematic_sub_sustain"
    if foundation_mode == "string_emotional_movement":
        return "cinematic_emotional_movement"
    if sound == "cinematic":
        if energy == "静止" or emotion in {"深沉", "平静"}:
            return "cinematic_sub_sustain"
        if energy in {"流动", "高能"} or emotion in {"忧伤", "激昂", "明亮"}:
            return "cinematic_emotional_movement"
    return "cinematic_sub_sustain" if sound == "ambient" and energy == "静止" else None


def select_bass_groove(sound: str, energy: str, rhythm: str, emotion: str, rng: random.Random, mode_override: str = "auto", variant_override: str = "auto", foundation_mode: str = "") -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    modes = load_bass_grooves()
    enabled = [mode for mode in modes.values() if mode.get("enabled", True)]
    if not enabled:
        return None, None, "legacy_fallback"
    if mode_override in modes and modes[mode_override].get("enabled", True) and (mode_override not in ELECTRONIC_MODE_IDS or sound == "electronic") and (mode_override not in ETHNIC_MODE_IDS or sound in modes[mode_override].get("allowed_sound_directions", [])) and (mode_override not in CINEMATIC_MODE_IDS or sound in modes[mode_override].get("allowed_sound_directions", [])):
        mode, source = modes[mode_override], "manual"
    else:
        cinematic_candidate = modes.get(cinematic_mode_id(sound, energy, emotion, foundation_mode) or "")
        ethnic_mode_id = None
        if sound == "ethnic":
            if energy == "静止" or rhythm == "sparse" or (emotion in {"深沉", "平静"} and rhythm not in {"flow", "groove"}):
                ethnic_mode_id = "ethnic_drone"
            else:
                ethnic_mode_id = "middle_eastern_pulse"
        ethnic_candidate = modes.get(ethnic_mode_id) if ethnic_mode_id else None
        rhythm_profile = electronic_rhythm_profile(sound, rhythm)
        electronic_mode_id = None
        if sound == "electronic":
            if rhythm_profile == "house_groove":
                electronic_mode_id = "house_four_on_floor"
            elif rhythm_profile == "edm_drive":
                electronic_mode_id = "808_sync" if energy == "高能" else "house_four_on_floor"
            elif rhythm_profile == "trap_hybrid":
                electronic_mode_id = "808_sync"
        electronic_candidate = modes.get(electronic_mode_id) if electronic_mode_id else None
        if (
            cinematic_candidate
            and cinematic_candidate.get("enabled", True)
            and sound in cinematic_candidate.get("allowed_sound_directions", [])
            and (foundation_mode in {"string_long_pad", "string_emotional_movement"} or energy in cinematic_candidate.get("allowed_energy", []))
        ):
            mode, source = cinematic_candidate, "foundation_linked" if foundation_mode in {"string_long_pad", "string_emotional_movement"} else "auto"
        elif (
            ethnic_candidate
            and ethnic_candidate.get("enabled", True)
            and sound in ethnic_candidate.get("allowed_sound_directions", [])
            and energy in ethnic_candidate.get("allowed_energy", [])
            and rhythm in ethnic_candidate.get("allowed_rhythm", [])
        ):
            mode, source = ethnic_candidate, "auto"
        elif (
            electronic_candidate
            and electronic_candidate.get("enabled", True)
            and sound in electronic_candidate.get("allowed_sound_directions", [])
            and energy in electronic_candidate.get("allowed_energy", [])
            and rhythm in electronic_candidate.get("allowed_rhythm", [])
            and rhythm_profile in electronic_candidate.get("allowed_rhythm_profiles", [])
        ):
            mode, source = modes[electronic_mode_id], "auto"
        else:
            choices = {"ambient": ("sustain_root", "root_fifth"), "acoustic": ("root_fifth", "sustain_root"), "organic": ("root_fifth", "groove_pickup"), "vintage": ("groove_pickup", "root_fifth"), "electronic": ("pulse", "groove_pickup", "sustain_root"), "ethnic": ("root_fifth", "sustain_root"), "cinematic": ("cinematic_sub_sustain", "cinematic_emotional_movement")}.get(sound, MODE_IDS)
            def matches_tags(candidate: dict[str, Any]) -> bool:
                return sound in candidate.get("allowed_sound_directions", []) and energy in candidate.get("allowed_energy", []) and rhythm in candidate.get("allowed_rhythm", [])
            choices = [mode_id for mode_id in choices if mode_id in modes and modes[mode_id].get("enabled", True) and matches_tags(modes[mode_id])]
            if energy == "静止":
                static_modes = [mode_id for mode_id in choices if mode_id in {"sustain_root", "root_fifth", "cinematic_sub_sustain"}]
                if not static_modes:
                    static_modes = [item["id"] for item in enabled if item["id"] in {"sustain_root", "root_fifth", "cinematic_sub_sustain"}]
                choices = static_modes
            rhythm_bias = {"sparse": ("sustain_root", "root_fifth"), "flow": ("root_fifth", "groove_pickup"), "standard": ("root_fifth", "pulse"), "groove": ("groove_pickup", "root_fifth", "pulse"), "aggressive": ("pulse", "groove_pickup")}.get(rhythm, ())
            preferred = [mode_id for mode_id in choices if mode_id in rhythm_bias]
            candidates = preferred or choices or [item["id"] for item in enabled if matches_tags(item)] or [item["id"] for item in enabled]
            weights = [max(1, int(modes[mode_id].get("priority", 1))) for mode_id in candidates]
            mode, source = modes[rng.choices(candidates, weights=weights, k=1)[0]], "auto"
    variants = [variant for variant in mode.get("variants", []) if variant.get("enabled", True)]
    if not variants:
        return None, None, "legacy_fallback"
    selected = next((variant for variant in variants if variant.get("id") == variant_override), None)
    return mode, selected or rng.choice(variants), source


def clamp_pitch(pitch: int) -> int:
    while pitch < 24: pitch += 12
    while pitch > 60: pitch -= 12
    return pitch


def degree_pitch(degree: str, chord: Any, next_chord: Any) -> int:
    root = clamp_pitch(int(chord.bass_note))
    next_root = clamp_pitch(int(next_chord.bass_note))
    if degree in {"root", "ghost_root"}: return root
    if degree in {"fifth", "ghost_fifth"}: return clamp_pitch(root + 7)
    if degree in {"octave", "octave_root"}: return clamp_pitch(root + 12)
    if degree in {"next_root_pickup", "next_root"}: return next_root
    if degree == "chromatic_approach": return clamp_pitch(next_root - 1 if next_root >= root else next_root + 1)
    if degree == "diatonic_passing": return clamp_pitch(root + (2 if next_root >= root else -2))
    return root


def bass_groove_events(chords: list[Any], bars: int, velocity: int, sound: str, energy: str, rhythm: str, emotion: str, rng: random.Random, mode_override: str = "auto", variant_override: str = "auto", foundation_mode: str = "") -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    mode, variant, selection = select_bass_groove(sound, energy, rhythm, emotion, rng, mode_override, variant_override, foundation_mode)
    if not mode or not variant:
        return [], None
    output: list[dict[str, Any]] = []
    ghost_count = pickup_count = 0
    for bar in range(bars):
        if bar >= 4:
            for original in [event for event in output if event["bar"] == bar - 4]:
                repeated = dict(original)
                repeated["bar"] = bar
                output.append(repeated)
            continue
        events = [dict(event) for event in variant.get("events", []) if event.get("enabled", True)]
        role = bar % 4
        if mode["id"] not in ELECTRONIC_MODE_IDS and mode["id"] not in ETHNIC_MODE_IDS and mode["id"] not in CINEMATIC_MODE_IDS and role == 1 and len(events) > 2: events = events[:-1]
        if mode["id"] == "cinematic_emotional_movement":
            if role in {0, 1}:
                events = [_event(0, "root", 16)]
            elif role == 2:
                events = [_event(0, "root", 8), _event(8, "octave_root", 8, .9)]
            else:
                events = [_event(0, "fifth", 8, .82), _event(8, "root", 8, 1.05)]
        if role == 3:
            if mode["id"] == "sustain_root": events[0]["duration_steps"] = min(int(events[0]["duration_steps"]), 12)
            elif mode["id"] == "pulse" and events: events[-1] = _event(int(events[-1]["step"]), "next_root_pickup", 1, .65)
            elif mode["id"] in {"root_fifth", "groove_pickup"} and not any(event["degree"] == "next_root_pickup" for event in events): events.append(_event(15, "next_root_pickup", 1, .65))
            elif mode["id"] == "house_four_on_floor":
                strategy = mode.get("bar_4_strategies", ["next_root_pickup"])[0]
                if strategy == "drop_last": events = events[:-1]
                elif strategy == "octave_finish": events[-1]["degree"] = "octave_root"
                else: events[-1]["degree"] = "next_root"
            elif mode["id"] == "808_sync" and mode.get("bar_4_strategies", ["next_root_pickup"])[0] == "drop_last": events = events[:-1]
        for item in events:
            degree = str(item.get("degree", "root"))
            if degree == "rest" or degree not in mode.get("allowed_degrees", []):
                continue
            if rng.random() > max(0.0, min(1.0, float(item.get("probability", 1)))):
                continue
            if degree.startswith("ghost"):
                if mode["id"] == "sustain_root" or ghost_count >= (4 if mode["id"] == "groove_pickup" else 1): continue
                ghost_count += 1
            if degree in {"next_root_pickup", "next_root", "chromatic_approach"}:
                maximum = {"sustain_root": 1, "root_fifth": 2, "pulse": 2, "groove_pickup": 3, "house_four_on_floor": 1, "808_sync": 4, "ethnic_drone": 0, "middle_eastern_pulse": 0, "cinematic_sub_sustain": 0, "cinematic_emotional_movement": 0}[mode["id"]]
                if pickup_count >= maximum: continue
                pickup_count += 1
            duration = max(24, int(float(item.get("duration_steps", 1)) * 120 * float(mode["duration_ratio"])))
            low, high = mode.get("velocity_range", [60, 90])
            note_velocity = rng.randint(int(low), int(high))
            if degree.startswith("ghost"): note_velocity = rng.randint(22, 48); duration = min(duration, 80)
            timing = int(rng.uniform(-1, 1) * float(mode["timing_amount"]) * 30)
            pitch = degree_pitch(degree, chords[bar], chords[(bar + 1) % bars])
            # Electronic bass is intentionally voiced one octave above the shared bass range.
            # This keeps it audible with the selected synth and sampled bass sources.
            if sound == "electronic":
                pitch += 12
            output.append(
                {
                    "bar": bar,
                    "step": float(item.get("step", 0)),
                    "degree": degree,
                    "pitch": pitch,
                    "duration": duration,
                    "velocity": max(1, min(127, int(note_velocity * float(item.get("velocity_multiplier", 1))))),
                    "timing": timing,
                    "glide": bool(item.get("glide", False) and mode.get("glide_enabled", False)),
                }
            )
    configured_glide = bool(mode.get("glide_enabled", False))
    glide_active = bool(configured_glide and any(event.get("glide") for event in output))
    pattern_event_count = len([event for event in variant.get("events", []) if event.get("enabled", True)])
    manifest = {"mode": mode["id"], "mode_name": mode["name"], "variant_id": variant["id"], "variant_name": variant["name"], "selection_source": selection, "category": mode.get("category", "standard"), "style": mode.get("style", "standard"), "rhythm_profile": electronic_rhythm_profile(sound, rhythm), "octave_shift": 12 if sound == "electronic" else 0, "main_mode_locked": True, "main_variant_locked": True, "bar_4_strategy": mode["bar_4_strategies"][0], "allowed_degrees": mode["allowed_degrees"], "allowed_emotions": mode.get("allowed_emotions", []), "sustain": float(mode.get("sustain", mode["duration_ratio"])), "harmony_follow": bool(mode.get("harmony_follow", False)), "foundation_mode": foundation_mode or None, "foundation_linked": selection == "foundation_linked", "event_count": len(output) if bars else pattern_event_count, "events_per_bar": pattern_event_count, "ghost_note_count": ghost_count, "pickup_count": pickup_count, "slide_enabled": configured_glide, "slide_active": glide_active, "glide_time_ms": int(mode.get("glide_time_ms", 0) or 0) if configured_glide else 0, "pitch_bend_range": int(mode.get("pitch_bend_range", 0) or 0) if configured_glide else 0, "slide_strategy": "pickup_fallback" if configured_glide else "none", "humanize_limits": {"timing": mode["timing_amount"], "velocity": float(mode.get("velocity_amount", .16 if mode["id"] == "groove_pickup" else .10)), "duration": .12 if mode["id"] == "groove_pickup" else .08, "phrase": .10 if mode["id"] == "groove_pickup" else .05}}
    return output, manifest


def electronic_rhythm_profile(sound: str, rhythm: str) -> str | None:
    return ELECTRONIC_RHYTHM_PROFILES.get(rhythm) if sound == "electronic" else None
