from __future__ import annotations

import json
import random
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .resolver import resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction
from .sample_library import analyze_audio_file, float_or_default, int_or_default, safe_name


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "sound_sources"
SOURCE_FILE_DIR = SOURCE_DIR / "files"
SOURCE_DB_PATH = SOURCE_DIR / "sound_sources.json"
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg"}

TRACK_ROLES = ("foundation", "bass", "drums", "texture_fx")
SOUND_DIRECTIONS = ("ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic")
ENERGIES = ("静止", "高能", "流动")
RHYTHMS = ("sparse", "flow", "standard", "groove", "aggressive")
EMOTIONS = ("深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂")
DRUM_SLOTS = {
    "kick": {"label": "Kick", "midi_notes": (36,)},
    "snare": {"label": "Snare", "midi_notes": (38,)},
    "clap": {"label": "Clap", "midi_notes": (39,)},
    "closed_hat": {"label": "Closed Hat", "midi_notes": (42, 54)},
    "open_hat": {"label": "Open Hat", "midi_notes": (46,)},
    "shaker": {"label": "Shaker", "midi_notes": (70, 54)},
    "perc": {"label": "Perc", "midi_notes": (75, 76)},
    "perc_1": {"label": "Perc 1", "midi_notes": (75,)},
    "perc_2": {"label": "Perc 2", "midi_notes": (76,)},
    "low_tom": {"label": "Low Tom", "midi_notes": (45,)},
    "high_tom": {"label": "High Tom", "midi_notes": (50,)},
    "crash": {"label": "Crash", "midi_notes": (49,)},
    "ride": {"label": "Ride", "midi_notes": (51,)},
    "impact": {"label": "Impact", "midi_notes": (55,)},
    "fill_hit": {"label": "Fill Hit", "midi_notes": (48,)},
    "texture_perc": {"label": "Texture Perc", "midi_notes": (82,)},
}


def ensure_source_dirs() -> None:
    SOURCE_FILE_DIR.mkdir(parents=True, exist_ok=True)


def default_db() -> dict[str, Any]:
    return {"samples": []}


def load_sound_db() -> dict[str, Any]:
    ensure_source_dirs()
    if not SOURCE_DB_PATH.is_file():
        SOURCE_DB_PATH.write_text(json.dumps(default_db(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        data = json.loads(SOURCE_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = default_db()
    if isinstance(data, list):
        data = {"samples": data}
    if not isinstance(data, dict):
        data = default_db()
    samples = data.get("samples") if isinstance(data.get("samples"), list) else []
    return {"samples": [normalize_sample(sample) for sample in samples if isinstance(sample, dict)]}


def save_sound_db(db: dict[str, Any]) -> dict[str, Any]:
    ensure_source_dirs()
    normalized = {"samples": [normalize_sample(sample) for sample in db.get("samples", []) if isinstance(sample, dict)]}
    SOURCE_DB_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return normalized


def export_sound_sources() -> dict[str, Any]:
    db = load_sound_db()
    return {**db, "definitions": definitions()}


def definitions() -> dict[str, Any]:
    return {
        "track_roles": list(TRACK_ROLES),
        "sound_directions": list(SOUND_DIRECTIONS),
        "energies": list(ENERGIES),
        "rhythms": list(RHYTHMS),
        "emotions": list(EMOTIONS),
        "drum_slots": DRUM_SLOTS,
    }


def upload_sound_samples(files: list[tuple[str, bytes]], fields: dict[str, str]) -> dict[str, Any]:
    db = load_sound_db()
    uploaded = []
    for file_name, data in files:
        sample = store_sample_file(file_name, data, fields)
        uploaded.append(sample)
        db["samples"] = upsert_sample(db["samples"], sample)
    save_sound_db(db)
    return {"uploaded": uploaded, **export_sound_sources()}


def store_sample_file(file_name: str, data: bytes, fields: dict[str, str]) -> dict[str, Any]:
    ensure_source_dirs()
    original = Path(file_name or "sample.wav").name
    ext = Path(original).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported audio format. Use wav, mp3, aiff, flac, or ogg.")
    stored_name = f"{safe_name(Path(original).stem)}_{uuid.uuid4().hex[:8]}{ext}"
    path = SOURCE_FILE_DIR / stored_name
    path.write_bytes(data)
    info = analyze_audio_file(path)
    now = utc_now()
    role = normalize_track_role(fields.get("track_role") or infer_track_role(original))
    return normalize_sample(
        {
            "sample_id": f"sample_{uuid.uuid4().hex[:10]}",
            "name": fields.get("name") or title_from_file(original),
            "description": fields.get("description") or "",
            "file_name": original,
            "file_url": f"/sound_sources/files/{stored_name}",
            "enabled": fields.get("enabled", "true") != "false",
            "target": {"track_role": role, "slot": normalize_slot(fields.get("slot") or infer_slot(original)) if role == "drums" else ""},
            "tag_rules": {
                "sound_direction": parse_array_field(fields.get("sound_direction")),
                "energy": parse_array_field(fields.get("energy")),
                "rhythm": parse_array_field(fields.get("rhythm")),
                "emotion": parse_array_field(fields.get("emotion")),
            },
            "playback": {
                "gain_db": float_or_default(fields.get("gain_db"), 0),
                "pan": float_or_default(fields.get("pan"), 0),
                "probability": float_or_default(fields.get("probability"), 1),
                "bar": int_or_default(fields.get("bar"), 1),
            },
            "audio_info": {
                "duration_ms": int(float_or_default(info.get("duration_seconds"), 0) * 1000),
                "format": ext.lstrip("."),
                "sample_rate": info.get("sample_rate"),
                "channels": info.get("channels"),
                "file_size": path.stat().st_size,
            },
            "created_at": now,
            "updated_at": now,
        }
    )


def upsert_sound_sources(payload: dict[str, Any]) -> dict[str, Any]:
    samples = payload.get("samples", payload if isinstance(payload, list) else [])
    if not isinstance(samples, list):
        samples = []
    return save_sound_db({"samples": samples})


def build_sound_source_context(annotation: Any, seed: int | None = None) -> dict[str, Any]:
    return {
        "tags": {
            "sound_direction": resolve_sound_direction(str(getattr(annotation, "sound_direction", "electronic"))).value,
            "energy": resolve_energy(getattr(annotation, "energy", "流动")).label,
            "rhythm": resolve_rhythm(str(getattr(annotation, "rhythm", "groove"))).value,
            "emotion": resolve_emotion(getattr(annotation, "emotion", "平静")).label,
        },
        "samples": load_sound_db()["samples"],
        "rng": random.Random(seed),
    }


def resolve_tonal_source_sample(context: dict[str, Any], track: str, midi_note: int, velocity: int) -> dict[str, Any] | None:
    role = "foundation" if track == "Foundation" else "bass" if track == "Bass" else ""
    selected = choose_sample(context, role)
    if not selected:
        return None
    playback = selected["playback"]
    return {
        "sample_id": selected["sample_id"],
        "file_url": selected["file_url"],
        "root_midi_note": int(midi_note),
        "target_midi_note": int(midi_note),
        "gain_db": playback.get("gain_db", 0),
        "pan": playback.get("pan", 0),
        "fade_in_ms": 0,
        "fade_out_ms": 20,
        "pitch_shift_allowed": False,
    }


def resolve_drum_source_sample(context: dict[str, Any], midi_note: int, velocity: int) -> dict[str, Any] | None:
    slot = slot_for_midi(midi_note)
    selected = choose_sample(context, "drums", slot)
    if not selected:
        # Keep a real uploaded drum kit active even when the pattern asks for a
        # secondary articulation with no dedicated sample assigned yet.
        fallbacks = {
            "perc_1": ("perc", "closed_hat", "snare"),
            "perc_2": ("perc", "closed_hat", "snare"),
            "perc": ("closed_hat", "snare"),
            "shaker": ("closed_hat", "open_hat"),
            "fill_hit": ("snare", "closed_hat"),
            "crash": ("open_hat", "closed_hat"),
            "impact": ("kick", "snare"),
            "low_tom": ("kick", "snare"),
            "high_tom": ("snare", "closed_hat"),
            "ride": ("closed_hat", "open_hat"),
            "clap": ("snare",),
        }
        for fallback_slot in fallbacks.get(slot, ()): 
            selected = choose_sample(context, "drums", fallback_slot)
            if selected:
                break
    if not selected:
        return None
    playback = selected["playback"]
    return {
        "sample_id": selected["sample_id"],
        "slot_type": slot,
        "file_url": selected["file_url"],
        "gain_db": playback.get("gain_db", 0),
        "pan": playback.get("pan", 0),
        "fade_in_ms": 0,
        "fade_out_ms": 20,
    }


def resolve_texture_overlays(annotation: Any, bars: int, seed: int | None = None) -> list[dict[str, Any]]:
    context = build_sound_source_context(annotation, seed)
    selected = choose_sample(context, "texture_fx")
    if not selected:
        return []
    playback = selected["playback"]
    bar = max(1, min(int(bars), int_or_default(playback.get("bar"), 1)))
    return [
        {
            "sample_id": selected["sample_id"],
            "name": selected.get("name") or selected["sample_id"],
            "source_type": "sample",
            "sample_type": "sample",
            "file_url": selected["file_url"],
            "trigger_mode": "on_bar",
            "bar": bar,
            "step": 0,
            "playback_type": "one_shot",
            "gain_db": playback.get("gain_db", 0),
            "pan": playback.get("pan", 0),
            "fade_in_ms": 20,
            "fade_out_ms": 80,
            "max_uses_per_loop": 1,
        }
    ]


def sound_source_summary(annotation: Any) -> dict[str, Any]:
    context = build_sound_source_context(annotation)
    foundation = choose_sample(context, "foundation")
    bass = choose_sample(context, "bass")
    drums = choose_sample(context, "drums")
    return {
        "foundation": sample_summary(foundation) or {"mode": "built_in", "name": "原先 Foundation 音源"},
        "bass": sample_summary(bass) or {"mode": "built_in", "name": "原先 Bass 音源"},
        "drums": sample_summary(drums),
        "texture_fx": sample_summary(choose_sample(context, "texture_fx")),
        "missing": ["drums"] if drums is None else [],
    }


def choose_sample(context: dict[str, Any], role: str, slot: str | None = None) -> dict[str, Any] | None:
    candidates = []
    for sample in context.get("samples", []):
        if not sample_matches(sample, context["tags"], role, slot):
            continue
        probability = max(0.0, min(1.0, float_or_default(sample.get("playback", {}).get("probability"), 1)))
        if context["rng"].random() <= probability:
            candidates.append(sample)
    if not candidates:
        # Tagged samples are intentionally strict. A failed match must not
        # make an ambient sample leak into an acoustic loop. Untagged samples
        # remain available as explicit all-purpose fallbacks.
        candidates = [
            sample
            for sample in context.get("samples", [])
            if target_matches(sample, role, slot) and is_unrestricted_sample(sample)
        ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return candidates[0]


def sample_matches(sample: dict[str, Any], tags: dict[str, str], role: str, slot: str | None = None) -> bool:
    if not target_matches(sample, role, slot):
        return False
    rules = sample.get("tag_rules", {})
    return all(
        rule_matches(rules.get(key), tags[key])
        for key in ("sound_direction", "energy", "rhythm", "emotion")
    )


def target_matches(sample: dict[str, Any], role: str, slot: str | None = None) -> bool:
    if not sample.get("enabled", True) or not sample.get("file_url"):
        return False
    target = sample.get("target", {})
    if target.get("track_role") != role:
        return False
    if role == "drums" and slot and target.get("slot") != slot:
        return False
    return True


def rule_matches(values: Any, current: str) -> bool:
    if not values:
        return True
    return str(current) in {str(value) for value in values}


def is_unrestricted_sample(sample: dict[str, Any]) -> bool:
    rules = sample.get("tag_rules")
    if not isinstance(rules, dict):
        return True
    return not any(rules.get(key) for key in ("sound_direction", "energy", "rhythm", "emotion"))


def normalize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    now = utc_now()
    target = sample.get("target") if isinstance(sample.get("target"), dict) else {}
    if not target:
        target = {
            "track_role": normalize_track_role(sample.get("track_role")),
            "slot": normalize_slot(sample.get("slot_type") or sample.get("slot")),
        }
    role = normalize_track_role(target.get("track_role"))
    tag_rules = sample.get("tag_rules") if isinstance(sample.get("tag_rules"), dict) else sample.get("tags") if isinstance(sample.get("tags"), dict) else {}
    playback = sample.get("playback") if isinstance(sample.get("playback"), dict) else {}
    audio_info = sample.get("audio_info") if isinstance(sample.get("audio_info"), dict) else {}
    return {
        "sample_id": str(sample.get("sample_id") or f"sample_{uuid.uuid4().hex[:10]}"),
        "name": str(sample.get("name") or "未命名采样"),
        "description": str(sample.get("description") or ""),
        "file_name": str(sample.get("file_name") or ""),
        "file_url": str(sample.get("file_url") or ""),
        "enabled": bool(sample.get("enabled", True)),
        "target": {"track_role": role, "slot": normalize_slot(target.get("slot")) if role == "drums" else ""},
        "tag_rules": {
            "sound_direction": normalize_sound_list(tag_rules.get("sound_direction"), "sound_direction"),
            "energy": normalize_sound_list(tag_rules.get("energy"), "energy"),
            "rhythm": normalize_sound_list(tag_rules.get("rhythm"), "rhythm"),
            "emotion": normalize_sound_list(tag_rules.get("emotion"), "emotion"),
        },
        "playback": {
            "gain_db": float_or_default(playback.get("gain_db"), 0),
            "pan": max(-1.0, min(1.0, float_or_default(playback.get("pan"), 0))),
            "probability": max(0.0, min(1.0, float_or_default(playback.get("probability"), 1))),
            "bar": max(1, min(8, int_or_default(playback.get("bar"), 1))),
        },
        "audio_info": {
            "duration_ms": int(float_or_default(audio_info.get("duration_ms"), 0)),
            "format": str(audio_info.get("format") or Path(str(sample.get("file_url", ""))).suffix.lstrip(".")),
            "sample_rate": audio_info.get("sample_rate"),
            "channels": audio_info.get("channels"),
            "file_size": int(float_or_default(audio_info.get("file_size"), float_or_default(sample.get("file_size"), 0))),
        },
        "created_at": str(sample.get("created_at") or now),
        "updated_at": str(sample.get("updated_at") or now),
    }


def normalize_sound_list(values: Any, kind: str) -> list[str]:
    result = []
    for value in parse_array_value(values):
        if kind == "sound_direction":
            result.append(resolve_sound_direction(str(value)).value)
        elif kind == "energy":
            result.append(resolve_energy(value).label)
        elif kind == "rhythm":
            result.append(resolve_rhythm(str(value)).value)
        elif kind == "emotion":
            result.append(resolve_emotion(str(value)).label)
    return list(dict.fromkeys(result))


def parse_array_field(value: Any) -> list[str]:
    return parse_array_value(value)


def parse_array_value(value: Any) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(parse_array_value(item))
        return result
    text = str(value)
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item)]
        except json.JSONDecodeError:
            pass
    return [item.strip() for item in text.split(",") if item.strip()]


def upsert_sample(samples: list[dict[str, Any]], sample: dict[str, Any]) -> list[dict[str, Any]]:
    for index, existing in enumerate(samples):
        if existing.get("sample_id") == sample.get("sample_id"):
            samples[index] = sample
            return samples
    samples.append(sample)
    return samples


def source_path_from_url(file_url: str) -> Path:
    path = Path(str(file_url).split("?", 1)[0].lstrip("/"))
    return (ROOT / path).resolve()


def normalize_track_role(value: Any) -> str:
    role = str(value or "").lower()
    aliases = {"texture": "texture_fx", "texture fx": "texture_fx", "fx": "texture_fx"}
    role = aliases.get(role, role)
    return role if role in TRACK_ROLES else "foundation"


def normalize_slot(value: Any) -> str:
    slot = str(value or "").lower().replace("-", "_").replace(" ", "_")
    aliases = {"hat": "closed_hat", "tom_low": "low_tom", "tom_high": "high_tom", "fill": "fill_hit"}
    slot = aliases.get(slot, slot)
    return slot if slot in DRUM_SLOTS else "kick"


def slot_for_midi(midi_note: int) -> str | None:
    for slot, config in DRUM_SLOTS.items():
        if int(midi_note) in config["midi_notes"]:
            return slot
    return "perc"


def infer_track_role(file_name: str) -> str:
    text = Path(file_name or "").name.lower()
    if any(token in text for token in ("kick", "snare", "clap", "hat", "shaker", "perc", "crash", "impact")):
        return "drums"
    if any(token in text for token in ("bass", "sub", "low")):
        return "bass"
    if any(token in text for token in ("fx", "texture", "noise", "riser", "sweep", "ambience")):
        return "texture_fx"
    return "foundation"


def infer_slot(file_name: str) -> str:
    text = Path(file_name or "").name.lower()
    patterns = (
        ("open_hat", ("openhat", "open_hat", "open-hat", "ohh", "open hat")),
        ("closed_hat", ("closedhat", "closed_hat", "closed-hat", "chh", "hat", "hihat", "hi_hat")),
        ("kick", ("kick", "bd", "bassdrum")),
        ("snare", ("snare", "sd")),
        ("clap", ("clap",)),
        ("shaker", ("shaker",)),
        ("crash", ("crash",)),
        ("ride", ("ride",)),
        ("low_tom", ("lowtom", "low_tom", "low-tom", "floor_tom", "floor tom")),
        ("high_tom", ("hightom", "high_tom", "high-tom")),
        ("impact", ("impact", "boom", "braam")),
        ("fill_hit", ("fill", "fillhit", "fill_hit")),
        ("texture_perc", ("texture_perc", "texture perc", "wood", "rim")),
        ("perc", ("perc", "tom", "hit")),
    )
    for slot, needles in patterns:
        if any(needle in text for needle in needles):
            return slot
    return "kick"


def sample_summary(sample: dict[str, Any] | None) -> dict[str, Any] | None:
    if not sample:
        return None
    return {
        "sample_id": sample.get("sample_id"),
        "name": sample.get("name"),
        "target": sample.get("target"),
        "tag_rules": sample.get("tag_rules"),
    }


def title_from_file(value: str) -> str:
    return Path(value).stem.replace("_", " ").replace("-", " ").strip().title() or "未命名采样"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
