from __future__ import annotations

import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .sample_library import analyze_audio_file, float_or_default, safe_name
from .resolver import resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction


ROOT = Path(__file__).resolve().parent.parent
INSTRUMENT_DIR = ROOT / "instruments"
INSTRUMENT_FILE_DIR = INSTRUMENT_DIR / "files"
INSTRUMENT_DB_PATH = INSTRUMENT_DIR / "instruments.json"
TRACK_ROLES = ("foundation", "bass", "lead", "texture")
CATEGORIES = (
    "piano", "electric_piano", "organ", "keyboard", "pad", "synth", "strings", "ensemble_strings", "violin_section", "cello_section", "choir", "bell", "pluck", "nylon_guitar", "electric_guitar",
    "acoustic_bass", "electric_bass", "synth_bass", "sub_bass", "brass", "woodwinds", "mallet", "other",
)
TAG_OPTIONS = {
    "emotion": ("深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"),
    "energy": ("静止", "高能", "流动"),
    "sound_direction": ("ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"),
    "rhythm": ("sparse", "flow", "standard", "groove", "aggressive"),
}
NOTE_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d+)$")
FILENAME_NOTE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Ga-g](?:#|b)?-?\d+)(?![A-Za-z0-9])")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_dirs() -> None:
    INSTRUMENT_FILE_DIR.mkdir(parents=True, exist_ok=True)


def note_to_midi(value: Any, fallback: int = 60) -> int:
    if isinstance(value, (int, float)) or str(value).strip().lstrip("-").isdigit():
        return max(0, min(127, int(float(value))))
    match = NOTE_RE.match(str(value).strip())
    if not match:
        return fallback
    name = match.group(1).upper() + match.group(2)
    pcs = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
    return max(0, min(127, (int(match.group(3)) + 1) * 12 + pcs.get(name, 0)))


def midi_to_note(midi: Any) -> str:
    value = max(0, min(127, int(float(midi))))
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[value % 12]}{value // 12 - 1}"


def root_note_from_file_name(file_name: str, fallback: int = 60) -> int:
    """Read a note token such as C3, F#2, or Bb1 from an uploaded file name."""
    matches = FILENAME_NOTE_RE.findall(Path(file_name).stem)
    return note_to_midi(matches[-1], fallback) if matches else fallback


def default_playback(role: str) -> dict[str, Any]:
    return {
        "gain_db": 0.0,
        "pan": 0.0,
        "attack_ms": 5 if role == "foundation" else 3,
        "release_ms": 30 if role == "foundation" else 20,
        "polyphony": 32 if role == "foundation" else 8,
        "velocity_curve": "linear",
        "pitch_bend_range": 2,
        "transpose": 0,
    }


def blank_instrument(role: str = "foundation") -> dict[str, Any]:
    role = role if role in TRACK_ROLES else "foundation"
    stamp = now()
    return {
        "id": f"instrument_{uuid.uuid4().hex[:10]}", "name": "未命名乐器", "description": "", "track_role": role,
        "category": "electric_piano" if role == "foundation" else "electric_bass", "enabled": True, "priority": 100,
        "version": "1.0.0", "performance_engine": "foundation", "guitar_type": "", "tag_rules": {key: [] for key in TAG_OPTIONS}, "playback": default_playback(role),
        "sample_zones": [], "created_at": stamp, "updated_at": stamp,
    }


def normalize_tag_values(key: str, values: Any) -> list[str]:
    values = values if isinstance(values, list) else []
    result = []
    for value in values:
        if key == "emotion": normalized = resolve_emotion(value).label
        elif key == "energy": normalized = resolve_energy(value).label
        elif key == "sound_direction": normalized = resolve_sound_direction(str(value)).value
        else: normalized = resolve_rhythm(str(value)).value
        if normalized in TAG_OPTIONS[key] and normalized not in result:
            result.append(normalized)
    return result


def normalize_zone(zone: dict[str, Any], instrument_id: str) -> dict[str, Any]:
    stamp = now()
    root = note_to_midi(zone.get("root_midi_note", zone.get("root_note", 60)))
    note_range = zone.get("note_range") if isinstance(zone.get("note_range"), dict) else {}
    velocity_range = zone.get("velocity_range") if isinstance(zone.get("velocity_range"), dict) else {}
    low = note_to_midi(note_range.get("low", zone.get("low_midi_note", root)), root)
    high = note_to_midi(note_range.get("high", zone.get("high_midi_note", root)), root)
    if low > high: low, high = high, low
    round_robin_index = max(1, int(float_or_default(zone.get("round_robin_index"), 1)))
    return {
        "id": str(zone.get("id") or f"zone_{uuid.uuid4().hex[:10]}"), "instrument_id": instrument_id,
        "name": str(zone.get("name") or f"{midi_to_note(root)} Zone"), "file_name": str(zone.get("file_name") or ""),
        "file_url": str(zone.get("file_url") or ""), "mime_type": str(zone.get("mime_type") or "audio/wav"),
        "file_size": int(float_or_default(zone.get("file_size"), 0)), "sample_rate": zone.get("sample_rate"),
        "bit_depth": zone.get("bit_depth"), "channels": zone.get("channels"), "duration_ms": int(float_or_default(zone.get("duration_ms"), 0)),
        "root_midi_note": root, "note_range": {"low": low, "high": high},
        "velocity_range": {"low": max(1, min(127, int(float_or_default(velocity_range.get("low", zone.get("velocity_low", 1)), 1)))), "high": max(1, min(127, int(float_or_default(velocity_range.get("high", zone.get("velocity_high", 127)), 127))))},
        "gain_db": float_or_default(zone.get("gain_db"), 0), "pan": max(-1.0, min(1.0, float_or_default(zone.get("pan"), 0))),
        "round_robin_group": str(zone.get("round_robin_group") or ""), "round_robin_index": round_robin_index,
        "velocity_layer": max(1, int(float_or_default(zone.get("velocity_layer"), 1))),
        "articulation": str(zone.get("articulation") or "sustain"), "source_library": str(zone.get("source_library") or ""),
        "enabled": bool(zone.get("enabled", True)), "created_at": str(zone.get("created_at") or stamp), "updated_at": str(zone.get("updated_at") or stamp),
    }


def normalize_instrument(raw: dict[str, Any]) -> dict[str, Any]:
    role = str(raw.get("track_role") or "foundation")
    base = blank_instrument(role)
    role = role if role in TRACK_ROLES else "foundation"
    tag_rules = raw.get("tag_rules") if isinstance(raw.get("tag_rules"), dict) else {}
    playback = raw.get("playback") if isinstance(raw.get("playback"), dict) else {}
    zones = raw.get("sample_zones") if isinstance(raw.get("sample_zones"), list) else []
    merged = {**base, **raw, "track_role": role, "id": str(raw.get("id") or base["id"]), "name": str(raw.get("name") or base["name"]), "category": str(raw.get("category") or base["category"]), "enabled": bool(raw.get("enabled", True)), "priority": int(float_or_default(raw.get("priority"), 100)), "version": str(raw.get("version") or "1.0.0")}
    merged["category"] = merged["category"] if merged["category"] in CATEGORIES or merged["category"] == "" else "other"
    category_engine = {"nylon_guitar": ("guitar_single_note", "nylon"), "electric_guitar": ("guitar_single_note", "electric")}
    inferred_engine, inferred_type = category_engine.get(merged["category"], ("foundation", ""))
    engine = str(raw.get("performance_engine") or inferred_engine)
    merged["performance_engine"] = engine if engine in {"foundation", "guitar_single_note"} else inferred_engine
    guitar_type = str(raw.get("guitar_type") or inferred_type)
    merged["guitar_type"] = guitar_type if merged["performance_engine"] == "guitar_single_note" and guitar_type in {"nylon", "electric"} else ""
    merged["tag_rules"] = {key: normalize_tag_values(key, tag_rules.get(key)) for key in TAG_OPTIONS}
    defaults = default_playback(role)
    merged["playback"] = {
        "gain_db": float_or_default(playback.get("gain_db"), defaults["gain_db"]), "pan": max(-1.0, min(1.0, float_or_default(playback.get("pan"), defaults["pan"]))),
        "attack_ms": max(0, int(float_or_default(playback.get("attack_ms"), defaults["attack_ms"]))), "release_ms": max(0, int(float_or_default(playback.get("release_ms"), defaults["release_ms"]))),
        "polyphony": max(1, min(64, int(float_or_default(playback.get("polyphony"), defaults["polyphony"])))),
        "velocity_curve": str(playback.get("velocity_curve") or "linear") if str(playback.get("velocity_curve") or "linear") in {"linear", "soft", "hard"} else "linear",
        "pitch_bend_range": max(0, min(24, int(float_or_default(playback.get("pitch_bend_range"), 2)))), "transpose": max(-24, min(24, int(float_or_default(playback.get("transpose"), 0)))),
    }
    merged["sample_zones"] = [normalize_zone(zone, merged["id"]) for zone in zones if isinstance(zone, dict)]
    return merged


def load_instruments() -> list[dict[str, Any]]:
    ensure_dirs()
    if not INSTRUMENT_DB_PATH.is_file():
        INSTRUMENT_DB_PATH.write_text('{"instruments": []}\n', encoding="utf-8")
    try: data = json.loads(INSTRUMENT_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError: data = {}
    rows = data.get("instruments", data if isinstance(data, list) else [])
    return [normalize_instrument(row) for row in rows if isinstance(row, dict)]


def save_instruments(instruments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ensure_dirs()
    normalized = [normalize_instrument(item) for item in instruments if isinstance(item, dict)]
    INSTRUMENT_DB_PATH.write_text(json.dumps({"instruments": normalized}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def export_instruments() -> dict[str, Any]:
    return {"instruments": load_instruments(), "definitions": {"track_roles": list(TRACK_ROLES), "categories": list(CATEGORIES), "tags": {key: list(value) for key, value in TAG_OPTIONS.items()}}}


def get_instrument(instrument_id: str) -> dict[str, Any] | None:
    return next((item for item in load_instruments() if item["id"] == instrument_id), None)


def upsert_instrument(payload: dict[str, Any]) -> dict[str, Any]:
    item = normalize_instrument(payload)
    item["updated_at"] = now()
    rows = load_instruments()
    for index, current in enumerate(rows):
        if current["id"] == item["id"]: rows[index] = item; break
    else: rows.append(item)
    save_instruments(rows)
    return item


def delete_instrument(instrument_id: str) -> list[dict[str, Any]]:
    rows = [item for item in load_instruments() if item["id"] != instrument_id]
    save_instruments(rows)
    folder = (INSTRUMENT_FILE_DIR / safe_name(instrument_id)).resolve()
    if folder.is_relative_to(INSTRUMENT_FILE_DIR.resolve()): shutil.rmtree(folder, ignore_errors=True)
    return rows


def duplicate_instrument(instrument_id: str) -> dict[str, Any]:
    original = get_instrument(instrument_id)
    if not original: raise ValueError("Instrument not found.")
    copied = json.loads(json.dumps(original)); copied["id"] = f"instrument_{uuid.uuid4().hex[:10]}"; copied["name"] = f"{original['name']} Copy"; copied["sample_zones"] = []
    return upsert_instrument(copied)


def save_zone(instrument_id: str, zone_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    item = get_instrument(instrument_id)
    if not item: raise ValueError("Instrument not found.")
    zone = normalize_zone({**payload, "id": zone_id, "instrument_id": instrument_id}, instrument_id); zone["updated_at"] = now()
    item["sample_zones"] = [zone if current["id"] == zone_id else current for current in item["sample_zones"]]
    if not any(current["id"] == zone_id for current in item["sample_zones"]): item["sample_zones"].append(zone)
    upsert_instrument(item); return zone


def delete_zone(instrument_id: str, zone_id: str) -> dict[str, Any]:
    item = get_instrument(instrument_id)
    if not item: raise ValueError("Instrument not found.")
    item["sample_zones"] = [zone for zone in item["sample_zones"] if zone["id"] != zone_id]; return upsert_instrument(item)


def upload_zone(instrument_id: str, file_name: str, data: bytes, fields: dict[str, Any]) -> dict[str, Any]:
    item = get_instrument(instrument_id)
    if not item: raise ValueError("Instrument not found.")
    if Path(file_name).suffix.lower() != ".wav": raise ValueError("Instrument Library 仅支持 WAV 文件。")
    folder = INSTRUMENT_FILE_DIR / safe_name(instrument_id); folder.mkdir(parents=True, exist_ok=True)
    stored = f"{safe_name(Path(file_name).stem)}_{uuid.uuid4().hex[:8]}.wav"; path = folder / stored; path.write_bytes(data)
    info = analyze_audio_file(path)
    root = note_to_midi(fields.get("root_midi_note"), root_note_from_file_name(file_name))
    zone = normalize_zone({"id": f"zone_{uuid.uuid4().hex[:10]}", "instrument_id": instrument_id, "name": fields.get("name") or Path(file_name).stem, "file_name": Path(file_name).name, "file_url": f"/instruments/files/{safe_name(instrument_id)}/{stored}", "file_size": path.stat().st_size, "sample_rate": info.get("sample_rate"), "channels": info.get("channels"), "duration_ms": int(float_or_default(info.get("duration_seconds"), 0) * 1000), "root_midi_note": root, "note_range": {"low": note_to_midi(fields.get("low_midi_note", root)), "high": note_to_midi(fields.get("high_midi_note", root))}, "velocity_range": {"low": fields.get("velocity_low", 1), "high": fields.get("velocity_high", 127)}, "gain_db": fields.get("gain_db", 0), "pan": fields.get("pan", 0), "enabled": True}, instrument_id)
    item["sample_zones"].append(zone)
    upsert_instrument(item)
    auto_map(instrument_id)
    return next(entry for entry in get_instrument(instrument_id)["sample_zones"] if entry["id"] == zone["id"])


def auto_map(instrument_id: str) -> dict[str, Any]:
    item = get_instrument(instrument_id)
    if not item: raise ValueError("Instrument not found.")
    zones = sorted(item["sample_zones"], key=lambda zone: (zone["root_midi_note"], zone["id"]))
    for zone in zones:
        # Each recorded pitch initially covers its immediate semitone neighbors.
        # Example: C2 (36) maps to B1-C#2 (35-37).
        lower = max(0, zone["root_midi_note"] - 1)
        upper = min(127, zone["root_midi_note"] + 1)
        zone["note_range"] = {"low": lower, "high": upper}; zone["updated_at"] = now()
    item["sample_zones"] = zones; return upsert_instrument(item)


def annotation_tags(annotation: Any) -> dict[str, str]:
    return {"emotion": resolve_emotion(getattr(annotation, "emotion", "平静")).label, "energy": resolve_energy(getattr(annotation, "energy", "流动")).label, "sound_direction": resolve_sound_direction(str(getattr(annotation, "sound_direction", "electronic"))).value, "rhythm": resolve_rhythm(str(getattr(annotation, "rhythm", "standard"))).value}


def match_instrument(annotation: Any, role: str, seed: int = 0, override_id: str | None = None) -> dict[str, Any] | None:
    if role not in TRACK_ROLES: return None
    tags = annotation_tags(annotation); candidates = []
    for item in load_instruments():
        if not item["enabled"] or item["track_role"] != role: continue
        if override_id and item["id"] != override_id: continue
        if role == "bass" and tags["sound_direction"] == "ethnic":
            source_text = " ".join(str(value) for value in (item.get("name"), item.get("category"), item.get("source_info"))).lower()
            if "808" in source_text:
                continue
        matched = [key for key, values in item["tag_rules"].items() if values and tags[key] in values]
        # A user-selected instrument is an explicit choice. Its tags rank automatic matching,
        # but must not silently reject a valid manual selection.
        if not override_id and any(values and tags[key] not in values for key, values in item["tag_rules"].items()): continue
        if not any(zone["enabled"] and zone["file_url"] for zone in item["sample_zones"]): continue
        tie = hashlib.sha256(f"{seed}:{item['id']}".encode()).hexdigest()
        candidates.append((len(matched), item["priority"], tie, item, matched))
    if not candidates: return None
    candidates.sort(key=lambda value: (-value[0], -value[1], value[2]))
    _, _, _, item, matched = candidates[0]
    return {"instrument": item, "matched_tags": matched, "tags": tags}


def _is_playable_zone(instrument: dict[str, Any], zone: dict[str, Any]) -> bool:
    if not (zone.get("enabled") and zone.get("file_url")):
        return False
    source_type = str((instrument.get("source_info") or {}).get("type", ""))
    name = str(zone.get("file_name") or zone.get("name") or "").lower()
    # VSCO SFZ libraries contain key-release and performance-noise WAVs in the
    # same directory. They are not note-on bass samples and must not be picked.
    return not (source_type == "vsco_library" and any(token in name for token in ("release", "noise", "keyoff")))


def _zone_velocity_range(instrument: dict[str, Any], zone: dict[str, Any]) -> tuple[int, int]:
    source_type = str((instrument.get("source_info") or {}).get("type", ""))
    name = str(zone.get("file_name") or zone.get("name") or "").lower()
    # Swagbass and similar VSCO SFZ patches encode three dynamic layers in the
    # filename. Some SFZ regions inherit the previous velocity boundary, so use
    # their explicit sample layer instead of a malformed imported range.
    if source_type == "vsco_library":
        if "_fff_" in name:
            return 111, 127
        if "_f_" in name:
            return 51, 110
        if "_p_" in name:
            return 1, 50
    values = zone.get("velocity_range") if isinstance(zone.get("velocity_range"), dict) else {}
    low = max(1, min(127, int(float_or_default(values.get("low"), 1))))
    high = max(1, min(127, int(float_or_default(values.get("high"), 127))))
    return (low, high) if low <= high else (high, low)


def select_zone(instrument: dict[str, Any], midi_note: int, velocity: int, round_robin_cursors: dict[str, int] | None = None) -> tuple[dict[str, Any] | None, str | None]:
    zones = [zone for zone in instrument.get("sample_zones", []) if _is_playable_zone(instrument, zone)]
    inside = [zone for zone in zones if zone["note_range"]["low"] <= midi_note <= zone["note_range"]["high"] and _zone_velocity_range(instrument, zone)[0] <= velocity <= _zone_velocity_range(instrument, zone)[1]]
    candidates = inside or zones
    if not candidates: return None, "Instrument has no usable sample zones."
    score = lambda zone: (abs(zone["root_midi_note"] - midi_note), abs((sum(_zone_velocity_range(instrument, zone)) / 2) - velocity))
    best_score = min(score(zone) for zone in candidates)
    preferred = [zone for zone in candidates if score(zone) == best_score]
    groups: dict[str, list[dict[str, Any]]] = {}
    for zone in preferred:
        group = str(zone.get("round_robin_group") or "")
        if group:
            groups.setdefault(group, []).append(zone)
    rr_group, rr_zones = next(((group, entries) for group, entries in sorted(groups.items()) if len(entries) > 1), ("", []))
    if rr_zones:
        rr_zones.sort(key=lambda zone: (int(zone.get("round_robin_index", 1)), zone["id"]))
        velocity_low, velocity_high = _zone_velocity_range(instrument, rr_zones[0])
        cursor_key = f"{midi_note}:{rr_group}:{rr_zones[0].get('velocity_layer', 1)}:{velocity_low}-{velocity_high}"
        cursor = (round_robin_cursors or {}).get(cursor_key, 0)
        selected = rr_zones[cursor % len(rr_zones)]
        if round_robin_cursors is not None:
            round_robin_cursors[cursor_key] = cursor + 1
    else:
        selected = min(preferred, key=lambda zone: zone["id"])
    return selected, None if inside else f"MIDI note {midi_note} is outside all preferred zones; nearest zone was used."


def instrument_file_path(file_url: str) -> Path:
    return (ROOT / str(file_url).split("?", 1)[0].lstrip("/")).resolve()
