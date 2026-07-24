from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .harmony_rules import get_harmony_rule
from .resolver import resolve_emotion, resolve_emotion_key, resolve_sound_direction, resolve_sound_key


ROOT = Path(__file__).resolve().parent.parent
HARMONY_DIR = ROOT / "harmony"
HARMONY_DB_PATH = HARMONY_DIR / "harmony_rules.json"

EMOTIONS = ("深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂")
SOUND_DIRECTIONS = ("ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic")
VOICING_BY_SOUND = {
    "ambient": "open",
    "acoustic": "simple",
    "organic": "open",
    "vintage": "rootless",
    "electronic": "close",
    "ethnic": "open",
    "cinematic": "wide",
}
CHORD_RE = re.compile(r"^[A-G](?:#|b)?(?:maj|min|m|dim|aug|sus2|sus4|add9|6/9|6|7|9|11|13|maj7|maj9|m7|m9|m11|m7b5|dim7|7b9|7#9|7b13|7alt|alt|13sus4|9sus4|7sus4|maj7#11|maj9|add9|\\([^)]*\\))*?(?:/[A-G](?:#|b)?)?$")
NOTE_RE = re.compile(r"^[A-G](?:#|b)?$")
PITCH_RE = re.compile(r"^[A-G](?:#|b)?(?:-1|[0-9])$")


def ensure_harmony_dir() -> None:
    HARMONY_DIR.mkdir(parents=True, exist_ok=True)


def load_harmony_rules() -> list[dict[str, Any]]:
    ensure_harmony_dir()
    if not HARMONY_DB_PATH.is_file():
        HARMONY_DB_PATH.write_text("[]\n", encoding="utf-8")
    try:
        data = json.loads(HARMONY_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    if isinstance(data, dict):
        data = data.get("harmony_rules", [])
    if not isinstance(data, list):
        data = []
    return [normalize_rule(rule) for rule in data if isinstance(rule, dict)]


def save_harmony_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ensure_harmony_dir()
    normalized = [normalize_rule(rule) for rule in rules if isinstance(rule, dict)]
    HARMONY_DB_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def export_harmony_admin() -> dict[str, Any]:
    return {
        "harmony_rules": load_harmony_rules(),
        "default_rules": [
            default_rule(emotion, "all", bars)
            for emotion in EMOTIONS
            for bars in (4, 8)
        ],
        "definitions": definitions(),
    }


def definitions() -> dict[str, Any]:
    return {
        "emotions": list(EMOTIONS),
        "sound_directions": ["all"],
        "voicing_styles": ["simple", "rootless", "open", "wide", "close"],
    }


def upsert_harmony_rule(rule: dict[str, Any]) -> dict[str, Any]:
    rules = load_harmony_rules()
    normalized = normalize_rule(rule)
    normalized["updated_at"] = utc_now()
    for index, existing in enumerate(rules):
        if existing["rule_id"] == normalized["rule_id"]:
            rules[index] = normalized
            save_harmony_rules(rules)
            return normalized
    rules.append(normalized)
    save_harmony_rules(rules)
    return normalized


def delete_harmony_rule(rule_id: str) -> list[dict[str, Any]]:
    rules = [rule for rule in load_harmony_rules() if rule.get("rule_id") != rule_id]
    return save_harmony_rules(rules)


def find_manual_harmony_rule(emotion_value: str | int | float, length_bars: int) -> dict[str, Any] | None:
    emotion_label = resolve_emotion(emotion_value).label
    bars = 8 if int(length_bars) >= 8 else 4
    candidates = [rule for rule in load_harmony_rules() if rule.get("enabled", True) and rule.get("emotion") == emotion_label and int(rule.get("loop_length_bars", 4)) == bars]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return candidates[0]


def default_rule(emotion_value: str | int | float = "欢快", sound_value: str = "all", length_bars: int = 4) -> dict[str, Any]:
    emotion_key = resolve_emotion_key(emotion_value)
    emotion = resolve_emotion(emotion_value)
    harmony = get_harmony_rule(emotion_key)
    bars = 8 if int(length_bars) >= 8 else 4
    progression = list(harmony.chord_progression)
    while len(progression) < bars:
        progression.extend(harmony.chord_progression)
    return normalize_rule(
        {
            "rule_id": rule_id(emotion.label, "all", bars),
            "emotion": emotion.label,
            "sound_direction": "all",
            "loop_length_bars": bars,
            "chords": progression[:bars],
            "key_hint": f"{emotion.key} {'minor' if emotion.scale[2] == 3 else 'major'}",
            "voicing_style": harmony.voicing_style,
            "enabled": True,
            "updated_at": utc_now(),
        }
    )


def reset_harmony_rule(emotion_value: str | int | float, sound_value: str, length_bars: int) -> dict[str, Any]:
    rule = default_rule(emotion_value, sound_value, length_bars)
    return upsert_harmony_rule(rule)


def normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    emotion = resolve_emotion(rule.get("emotion", "欢快")).label
    sound_value = str(rule.get("sound_direction", "all"))
    sound = "all" if sound_value == "all" else resolve_sound_direction(sound_value).value
    bars = 8 if int(rule.get("loop_length_bars", 4) or 4) >= 8 else 4
    raw_chords = rule.get("chords", [])
    raw_allowed_notes: list[Any] = []
    raw_selected_notes: list[Any] = []
    if raw_chords and isinstance(raw_chords[0], dict):
        chords = [str(item.get("chord", "")).strip() for item in raw_chords]
        raw_allowed_notes = [item.get("allowed_notes", None) for item in raw_chords]
        raw_selected_notes = [item.get("selected_notes", None) for item in raw_chords]
    else:
        chords = [str(item).strip() for item in raw_chords] if isinstance(raw_chords, list) else []
        raw_allowed_notes = rule.get("allowed_notes", []) if isinstance(rule.get("allowed_notes"), list) else []
        raw_selected_notes = rule.get("selected_notes", []) if isinstance(rule.get("selected_notes"), list) else []
    fallback = list(default_rule_chords(emotion, bars))
    while len(chords) < bars:
        chords.append(fallback[len(chords) % len(fallback)])
        raw_allowed_notes.append(None)
        raw_selected_notes.append(None)
    inherited_chords = []
    for index, chord in enumerate(chords[:bars]):
        previous = inherited_chords[-1] if inherited_chords else fallback[index % len(fallback)]
        inherited_chords.append(chord or previous)
    chord_items = []
    previous_allowed = None
    previous_selected = None
    for index, chord in enumerate(inherited_chords):
        allowed = normalize_allowed_notes(raw_allowed_notes[index] if index < len(raw_allowed_notes) else None)
        selected = normalize_selected_notes(raw_selected_notes[index] if index < len(raw_selected_notes) else None)
        if not (chords[index] if index < len(chords) else ""):
            allowed = previous_allowed
            selected = previous_selected
        item = {"bar": index + 1, "chord": chord}
        if allowed is not None:
            item["allowed_notes"] = allowed
        if selected is not None:
            item["selected_notes"] = selected
        chord_items.append(item)
        previous_allowed = allowed
        previous_selected = selected
    return {
        "rule_id": str(rule.get("rule_id") or rule_id(emotion, sound, bars)),
        "emotion": emotion,
        "sound_direction": sound,
        "loop_length_bars": bars,
        "chords": chord_items,
        "key_hint": str(rule.get("key_hint") or ""),
        "voicing_style": str(rule.get("voicing_style") or VOICING_BY_SOUND.get(sound, "simple")),
        "enabled": bool(rule.get("enabled", True)),
        "updated_at": str(rule.get("updated_at") or utc_now()),
    }


def normalize_allowed_notes(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    seen = set()
    notes = []
    for item in value:
        note = str(item).strip()
        if not NOTE_RE.match(note):
            continue
        if note not in seen:
            seen.add(note)
            notes.append(note)
    return notes


def normalize_selected_notes(value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        return None
    seen = set()
    notes = []
    for item in value:
        note = str(item).strip()
        if not PITCH_RE.match(note):
            continue
        if note not in seen:
            seen.add(note)
            notes.append(note)
    return notes


def default_rule_chords(emotion: str, bars: int) -> tuple[str, ...]:
    emotion_key = resolve_emotion_key(emotion)
    progression = list(get_harmony_rule(emotion_key).chord_progression)
    repeated = list(progression)
    while len(repeated) < bars:
        repeated.extend(progression)
    return tuple(repeated[:bars])


def chord_validity(chords: list[str]) -> list[dict[str, Any]]:
    return [{"chord": chord, "valid": is_valid_chord(chord)} for chord in chords]


def is_valid_chord(chord: str) -> bool:
    return bool(CHORD_RE.match(str(chord or "").strip().replace(" ", "")))


def rule_id(emotion: str, sound: str, bars: int) -> str:
    slug = f"{emotion}_{sound}_{bars}".replace(" ", "_").lower()
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in slug)
    return f"harmony_{safe}" or f"harmony_{uuid.uuid4().hex[:8]}"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
