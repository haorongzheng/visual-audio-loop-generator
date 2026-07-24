from __future__ import annotations

import json
import random
import re
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .resolver import resolve_energy, resolve_rhythm, resolve_sound_direction
from .sample_library import analyze_audio_file, float_or_default, int_or_default, safe_name


ROOT = Path(__file__).resolve().parent.parent
DRUM_DIR = ROOT / "drums"
DRUM_FILE_DIR = DRUM_DIR / "files"
DRUM_DB_PATH = DRUM_DIR / "drum_kits.json"
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg"}


SLOT_DEFINITIONS: dict[str, dict[str, Any]] = {
    "kick": {"label": "Kick", "midi_note": 36, "choke_group": None},
    "snare": {"label": "Snare", "midi_note": 38, "choke_group": None},
    "clap": {"label": "Clap", "midi_note": 39, "choke_group": None},
    "closed_hat": {"label": "Closed Hat", "midi_note": 42, "choke_group": "hat"},
    "open_hat": {"label": "Open Hat", "midi_note": 46, "choke_group": "hat"},
    "shaker": {"label": "Shaker", "midi_note": 70, "choke_group": None},
    "perc_1": {"label": "Perc 1", "midi_note": 75, "choke_group": None},
    "perc_2": {"label": "Perc 2", "midi_note": 76, "choke_group": None},
    "low_tom": {"label": "Low Tom", "midi_note": 45, "choke_group": None},
    "high_tom": {"label": "High Tom", "midi_note": 50, "choke_group": None},
    "crash": {"label": "Crash", "midi_note": 49, "choke_group": "crash"},
    "ride": {"label": "Ride", "midi_note": 51, "choke_group": "crash"},
    "impact": {"label": "Impact", "midi_note": 55, "choke_group": None},
    "fill_hit": {"label": "Fill Hit", "midi_note": 48, "choke_group": None},
    "texture_perc": {"label": "Texture Perc", "midi_note": 82, "choke_group": "texture"},
}


MIDI_NOTE_TO_SLOT = {int(slot["midi_note"]): key for key, slot in SLOT_DEFINITIONS.items()}
MIDI_NOTE_TO_SLOT.update({54: "shaker", 39: "clap", 70: "shaker", 47: "low_tom"})


REQUIRED_BY_RHYTHM = {
    "sparse": (("kick", "texture_perc"),),
    "flow": (("kick",), ("shaker", "closed_hat")),
    "standard": (("kick",), ("snare", "clap"), ("closed_hat",)),
    "groove": (("kick",), ("snare", "clap"), ("closed_hat",)),
    "aggressive": (("kick",), ("snare",), ("closed_hat",), ("open_hat",), ("crash", "impact")),
}


def ensure_drum_dirs() -> None:
    DRUM_FILE_DIR.mkdir(parents=True, exist_ok=True)


def load_drum_kits() -> list[dict[str, Any]]:
    ensure_drum_dirs()
    if not DRUM_DB_PATH.is_file():
        DRUM_DB_PATH.write_text("[]\n", encoding="utf-8")
    try:
        data = json.loads(DRUM_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    if not isinstance(data, list):
        return []
    return [normalize_kit(kit) for kit in data if isinstance(kit, dict)]


def save_drum_kits(kits: list[dict[str, Any]]) -> None:
    ensure_drum_dirs()
    normalized = [normalize_kit(kit) for kit in kits]
    DRUM_DB_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_kit(sound_direction: str, energy: str, rhythm: str) -> dict[str, Any]:
    tags = normalize_tags(sound_direction, energy, rhythm)
    for kit in load_drum_kits():
        if kit["tags"] == tags:
            return kit
    return default_kit(tags["sound_direction"], tags["energy"], tags["rhythm"])


def upsert_kit(kit: dict[str, Any]) -> dict[str, Any]:
    kits = load_drum_kits()
    normalized = normalize_kit(kit)
    normalized["updated_at"] = utc_now()
    for index, existing in enumerate(kits):
        if existing["kit_id"] == normalized["kit_id"]:
            normalized["created_at"] = existing.get("created_at") or normalized.get("created_at") or utc_now()
            kits[index] = normalized
            save_drum_kits(kits)
            return normalized
    normalized["created_at"] = normalized.get("created_at") or utc_now()
    kits.append(normalized)
    save_drum_kits(kits)
    return normalized


def upload_drum_samples(files: list[tuple[str, bytes]], sound_direction: str, energy: str, rhythm: str, slot_type: str | None = None) -> dict[str, Any]:
    kit = get_kit(sound_direction, energy, rhythm)
    for file_name, data in files:
        slot = slot_type if slot_type in SLOT_DEFINITIONS else infer_slot_type(file_name)
        if slot not in SLOT_DEFINITIONS:
            slot = "texture_perc"
        sample = store_drum_sample(file_name, data, slot, kit["tags"])
        kit["slots"][slot]["samples"].append(sample)
    return upsert_kit(kit)


def store_drum_sample(file_name: str, data: bytes, slot_type: str, tags: dict[str, str]) -> dict[str, Any]:
    ensure_drum_dirs()
    original_name = Path(file_name or f"{slot_type}.wav").name
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported audio format. Use wav, mp3, aiff, flac, or ogg.")
    stored_name = f"{safe_name(Path(original_name).stem)}_{uuid.uuid4().hex[:8]}{ext}"
    path = DRUM_FILE_DIR / stored_name
    path.write_bytes(data)
    info = analyze_audio_file(path)
    now = utc_now()
    return {
        "sample_id": f"drum_sample_{uuid.uuid4().hex[:10]}",
        "name": title_from_file(original_name),
        "file_name": original_name,
        "file_url": f"/drums/files/{stored_name}",
        "slot_type": slot_type,
        "audio_info": {
            "duration_ms": int(float_or_default(info.get("duration_seconds"), 0) * 1000),
            "sample_rate": info.get("sample_rate"),
            "channels": info.get("channels"),
            "file_size": path.stat().st_size,
            "loudness_lufs": None,
            "peak_db": None,
        },
        "tags": {
            "sound_direction": [tags["sound_direction"]],
            "energy": [tags["energy"]],
            "rhythm": [tags["rhythm"]],
        },
        "playback": default_playback(),
        "priority": 50,
        "enabled": True,
        "created_at": now,
        "updated_at": now,
    }


def default_kit(sound_direction: str = "electronic", energy: str = "流动", rhythm: str = "groove") -> dict[str, Any]:
    tags = normalize_tags(sound_direction, energy, rhythm)
    now = utc_now()
    return {
        "kit_id": kit_id(tags["sound_direction"], tags["energy"], tags["rhythm"]),
        "name": f"{tags['sound_direction']} / {tags['energy']} / {tags['rhythm']}",
        "enabled": True,
        "tags": tags,
        "slots": {slot_id: default_slot(slot_id) for slot_id in SLOT_DEFINITIONS},
        "created_at": now,
        "updated_at": now,
    }


def default_slot(slot_id: str) -> dict[str, Any]:
    definition = SLOT_DEFINITIONS[slot_id]
    return {
        "slot_type": slot_id,
        "label": definition["label"],
        "midi_note": definition["midi_note"],
        "enabled": True,
        "round_robin_mode": "weighted_random",
        "choke_group": definition["choke_group"],
        "description": "",
        "samples": [],
    }


def default_playback() -> dict[str, Any]:
    return {
        "velocity_min": 1,
        "velocity_max": 127,
        "weight": 50,
        "gain_db": 0,
        "pan": 0,
        "start_offset_ms": 0,
        "fade_in_ms": 0,
        "fade_out_ms": 10,
        "pitch_shift_semitones": 0,
        "time_stretch": False,
        "reverse": False,
        "choke_group": None,
        "enabled": True,
    }


def normalize_kit(kit: dict[str, Any]) -> dict[str, Any]:
    tags = kit.get("tags") if isinstance(kit.get("tags"), dict) else {}
    normalized_tags = normalize_tags(tags.get("sound_direction", "electronic"), tags.get("energy", "流动"), tags.get("rhythm", "groove"))
    merged = default_kit(normalized_tags["sound_direction"], normalized_tags["energy"], normalized_tags["rhythm"])
    merged.update({key: value for key, value in kit.items() if key not in {"tags", "slots"}})
    merged["tags"] = normalized_tags
    merged["kit_id"] = str(merged.get("kit_id") or kit_id(normalized_tags["sound_direction"], normalized_tags["energy"], normalized_tags["rhythm"]))
    merged["enabled"] = bool(merged.get("enabled", True))
    source_slots = kit.get("slots") if isinstance(kit.get("slots"), dict) else {}
    for slot_id in SLOT_DEFINITIONS:
        slot = source_slots.get(slot_id) if isinstance(source_slots.get(slot_id), dict) else {}
        merged["slots"][slot_id].update({key: value for key, value in slot.items() if key != "samples"})
        merged["slots"][slot_id]["midi_note"] = int_or_default(merged["slots"][slot_id].get("midi_note"), SLOT_DEFINITIONS[slot_id]["midi_note"])
        merged["slots"][slot_id]["enabled"] = bool(merged["slots"][slot_id].get("enabled", True))
        merged["slots"][slot_id]["round_robin_mode"] = str(merged["slots"][slot_id].get("round_robin_mode") or "weighted_random")
        samples = slot.get("samples", [])
        merged["slots"][slot_id]["samples"] = [normalize_drum_sample(sample, slot_id, normalized_tags) for sample in samples if isinstance(sample, dict)]
    return merged


def normalize_drum_sample(sample: dict[str, Any], slot_id: str, tags: dict[str, str]) -> dict[str, Any]:
    playback = default_playback()
    if isinstance(sample.get("playback"), dict):
        playback.update(sample["playback"])
    playback["velocity_min"] = max(1, min(127, int_or_default(playback.get("velocity_min"), 1)))
    playback["velocity_max"] = max(playback["velocity_min"], min(127, int_or_default(playback.get("velocity_max"), 127)))
    playback["weight"] = max(1, int_or_default(playback.get("weight"), 50))
    playback["gain_db"] = float_or_default(playback.get("gain_db"), 0)
    playback["pan"] = max(-1.0, min(1.0, float_or_default(playback.get("pan"), 0)))
    playback["start_offset_ms"] = max(0, int_or_default(playback.get("start_offset_ms"), 0))
    playback["fade_in_ms"] = max(0, int_or_default(playback.get("fade_in_ms"), 0))
    playback["fade_out_ms"] = max(0, int_or_default(playback.get("fade_out_ms"), 10))
    playback["pitch_shift_semitones"] = float_or_default(playback.get("pitch_shift_semitones"), 0)
    playback["enabled"] = bool(playback.get("enabled", True))
    result = {
        "sample_id": str(sample.get("sample_id") or f"drum_sample_{uuid.uuid4().hex[:10]}"),
        "name": str(sample.get("name") or "Untitled Drum Sample"),
        "file_name": str(sample.get("file_name") or ""),
        "file_url": str(sample.get("file_url") or ""),
        "slot_type": str(sample.get("slot_type") or slot_id),
        "audio_info": sample.get("audio_info") if isinstance(sample.get("audio_info"), dict) else {},
        "tags": sample.get("tags") if isinstance(sample.get("tags"), dict) else {"sound_direction": [tags["sound_direction"]], "energy": [tags["energy"]], "rhythm": [tags["rhythm"]]},
        "playback": playback,
        "priority": int_or_default(sample.get("priority"), 50),
        "enabled": bool(sample.get("enabled", True)),
        "created_at": str(sample.get("created_at") or utc_now()),
        "updated_at": str(sample.get("updated_at") or utc_now()),
    }
    return result


def build_drum_source_context(annotation: Any, seed: int | None = None) -> dict[str, Any]:
    sound = resolve_sound_direction(str(getattr(annotation, "sound_direction", "electronic"))).value
    energy = resolve_energy(getattr(annotation, "energy", "流动")).label
    rhythm = resolve_rhythm(str(getattr(annotation, "rhythm", "groove"))).value
    return {
        "tags": {"sound_direction": sound, "energy": energy, "rhythm": rhythm},
        "kits": load_drum_kits(),
        "rng": random.Random(seed),
        "rr_counters": {},
    }


def resolve_drum_source_sample(context: dict[str, Any], midi_note: int, velocity: int) -> dict[str, Any] | None:
    slot_id = MIDI_NOTE_TO_SLOT.get(int(midi_note))
    if not slot_id:
        return None
    for kit in fallback_kits(context["kits"], context["tags"]):
        slot = slot_for_midi_note(kit, midi_note, slot_id)
        if not slot or not slot.get("enabled", True):
            continue
        candidates = drum_candidates(slot, velocity)
        if not candidates:
            continue
        selected = select_candidate(candidates, slot.get("round_robin_mode", "weighted_random"), context, f"{kit['kit_id']}:{slot_id}:{velocity}")
        if selected:
            playback = selected["playback"]
            return {
                "sample_id": selected["sample_id"],
                "slot_type": slot_id,
                "file_url": selected["file_url"],
                "gain_db": playback.get("gain_db", 0),
                "pan": playback.get("pan", 0),
                "start_offset_ms": playback.get("start_offset_ms", 0),
                "fade_in_ms": playback.get("fade_in_ms", 0),
                "fade_out_ms": playback.get("fade_out_ms", 10),
                "pitch_shift_semitones": playback.get("pitch_shift_semitones", 0),
                "reverse": playback.get("reverse", False),
                "choke_group": playback.get("choke_group") or slot.get("choke_group"),
            }
    return None


def fallback_kits(kits: list[dict[str, Any]], tags: dict[str, str]) -> list[dict[str, Any]]:
    enabled = [kit for kit in kits if kit.get("enabled", True)]
    order = [
        lambda kit: kit["tags"] == tags,
        lambda kit: kit["tags"]["sound_direction"] == tags["sound_direction"] and kit["tags"]["energy"] == tags["energy"],
        lambda kit: kit["tags"]["sound_direction"] == tags["sound_direction"],
        lambda kit: kit["tags"]["sound_direction"] == "default",
    ]
    result: list[dict[str, Any]] = []
    for matcher in order:
        for kit in enabled:
            if matcher(kit) and kit not in result:
                result.append(kit)
    return result


def slot_for_midi_note(kit: dict[str, Any], midi_note: int, fallback_slot_id: str) -> dict[str, Any] | None:
    for slot in kit.get("slots", {}).values():
        if int_or_default(slot.get("midi_note"), -1) == int(midi_note):
            return slot
    return kit.get("slots", {}).get(fallback_slot_id)


def drum_candidates(slot: dict[str, Any], velocity: int) -> list[dict[str, Any]]:
    candidates = []
    for sample in slot.get("samples", []):
        playback = sample.get("playback", {})
        if not sample.get("enabled", True) or not playback.get("enabled", True):
            continue
        if not sample.get("file_url"):
            continue
        if int(playback.get("velocity_min", 1)) <= velocity <= int(playback.get("velocity_max", 127)):
            candidates.append(sample)
    return candidates


def select_candidate(candidates: list[dict[str, Any]], mode: str, context: dict[str, Any], key: str) -> dict[str, Any] | None:
    if not candidates:
        return None
    if mode == "off":
        return candidates[0]
    if mode == "sequential":
        index = context["rr_counters"].get(key, 0)
        context["rr_counters"][key] = index + 1
        return candidates[index % len(candidates)]
    if mode == "random":
        return context["rng"].choice(candidates)
    weights = [max(1, int_or_default(sample.get("playback", {}).get("weight"), 50)) for sample in candidates]
    return context["rng"].choices(candidates, weights=weights, k=1)[0]


def kit_coverage(kit: dict[str, Any]) -> dict[str, Any]:
    slots = kit.get("slots", {})
    uploaded = {slot_id: len([sample for sample in slot.get("samples", []) if sample.get("enabled", True)]) for slot_id, slot in slots.items()}
    total = len(SLOT_DEFINITIONS)
    covered = len([slot_id for slot_id, count in uploaded.items() if count > 0])
    required_groups = REQUIRED_BY_RHYTHM.get(kit.get("tags", {}).get("rhythm", "groove"), ())
    missing = []
    for group in required_groups:
        if not any(uploaded.get(slot_id, 0) > 0 for slot_id in group):
            missing.append(" / ".join(SLOT_DEFINITIONS[slot_id]["label"] for slot_id in group))
    return {"percent": round(covered / total * 100), "uploaded": uploaded, "missing_required": missing}


def normalize_tags(sound_direction: Any, energy: Any, rhythm: Any) -> dict[str, str]:
    return {
        "sound_direction": resolve_sound_direction(str(sound_direction)).value,
        "energy": resolve_energy(energy).label,
        "rhythm": resolve_rhythm(str(rhythm)).value,
    }


def kit_id(sound_direction: str, energy: str, rhythm: str) -> str:
    energy_key = {"静止": "still", "流动": "flow", "高能": "high"}.get(str(energy), safe_name(str(energy)).lower())
    return "kit_" + safe_name(f"{sound_direction}_{energy_key}_{rhythm}").lower()


def infer_slot_type(file_name: str) -> str | None:
    text = Path(file_name or "").name.lower()
    patterns = (
        ("open_hat", ("openhat", "open_hat", "open-hat", "ohh", "open hat")),
        ("closed_hat", ("closedhat", "closed_hat", "closed-hat", "chh", "hat", "hihat", "hi_hat")),
        ("kick", ("kick", "bd", "bassdrum", "bass_drum")),
        ("snare", ("snare", "sd")),
        ("clap", ("clap",)),
        ("shaker", ("shaker",)),
        ("crash", ("crash",)),
        ("ride", ("ride",)),
        ("impact", ("impact", "boom", "braam")),
        ("low_tom", ("lowtom", "low_tom", "floor_tom")),
        ("high_tom", ("hitom", "high_tom", "tom")),
        ("perc_1", ("perc", "percussion")),
    )
    for slot, needles in patterns:
        if any(needle in text for needle in needles):
            return slot
    return None


def drum_path_from_url(file_url: str) -> Path:
    path = Path(str(file_url).split("?", 1)[0].lstrip("/"))
    return (ROOT / path).resolve()


def title_from_file(value: str) -> str:
    return Path(value).stem.replace("_", " ").replace("-", " ").strip().title() or "Untitled Drum Sample"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
