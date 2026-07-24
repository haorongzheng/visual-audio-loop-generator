from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SAMPLE_DIR = ROOT / "samples"
SAMPLE_FILE_DIR = SAMPLE_DIR / "files"
SAMPLE_DB_PATH = SAMPLE_DIR / "samples.json"
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg"}


SAMPLE_TYPES = ("texture", "one_shot", "drum_one_shot", "drum_loop", "tonal_loop", "transition")
PLAYBACK_TYPES = ("one_shot", "loop", "sync_loop", "random_one_shot", "fill")
TRIGGER_MODES = ("on_loop_start", "on_bar", "on_step", "random_step", "on_fill", "continuous")


@dataclass(frozen=True)
class MatchedOverlay:
    sample_id: str
    file_url: str
    sample_type: str
    playback_type: str
    trigger_mode: str
    bar: int
    step: int
    gain_db: float
    pan: float
    fade_in_ms: int
    fade_out_ms: int
    max_uses_per_loop: int
    sample: dict[str, Any]


def load_samples() -> list[dict[str, Any]]:
    ensure_sample_dirs()
    if not SAMPLE_DB_PATH.is_file():
        SAMPLE_DB_PATH.write_text("[]\n", encoding="utf-8")
    try:
        data = json.loads(SAMPLE_DB_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        data = []
    if not isinstance(data, list):
        return []
    return [normalize_sample(item) for item in data if isinstance(item, dict)]


def save_samples(samples: list[dict[str, Any]]) -> None:
    ensure_sample_dirs()
    normalized = [normalize_sample(sample) for sample in samples]
    SAMPLE_DB_PATH.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def upsert_sample(sample: dict[str, Any]) -> dict[str, Any]:
    samples = load_samples()
    normalized = normalize_sample(sample)
    now = utc_now()
    normalized["updated_at"] = now
    if not normalized.get("created_at"):
        normalized["created_at"] = now
    for index, item in enumerate(samples):
        if item["sample_id"] == normalized["sample_id"]:
            normalized["created_at"] = item.get("created_at") or normalized["created_at"]
            samples[index] = normalized
            save_samples(samples)
            return normalized
    samples.append(normalized)
    save_samples(samples)
    return normalized


def upload_sample_file(file_name: str, data: bytes) -> dict[str, Any]:
    ensure_sample_dirs()
    original_name = Path(file_name or "sample.wav").name
    ext = Path(original_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("Unsupported audio format. Use wav, mp3, aiff, flac, or ogg.")
    safe_stem = safe_name(Path(original_name).stem)
    stored_name = f"{safe_stem}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = SAMPLE_FILE_DIR / stored_name
    file_path.write_bytes(data)
    info = analyze_audio_file(file_path)
    now = utc_now()
    sample = default_sample()
    sample.update(
        {
            "sample_id": f"sample_{uuid.uuid4().hex[:10]}",
            "name": title_from_file(original_name),
            "file_url": f"/samples/files/{stored_name}",
            "file_name": original_name,
            "file_size": file_path.stat().st_size,
            "created_at": now,
            "updated_at": now,
        }
    )
    sample["audio_info"].update(info)
    return upsert_sample(sample)


def default_sample() -> dict[str, Any]:
    return {
        "sample_id": f"sample_{uuid.uuid4().hex[:10]}",
        "name": "Untitled Sample",
        "description": "",
        "file_url": "",
        "file_name": "",
        "file_size": 0,
        "enabled": True,
        "sample_type": "texture",
        "playback_type": "loop",
        "audio_info": {
            "duration_seconds": 0.0,
            "sample_rate": None,
            "channels": None,
            "bpm": None,
            "key": None,
            "root_note": None,
            "length_bars": 4,
            "is_loop": True,
            "loudness": None,
            "transient_density": None,
        },
        "tag_rules": {"emotion": [], "energy": [], "sound_direction": [], "rhythm": []},
        "trigger_rule": {
            "trigger_mode": "on_loop_start",
            "bar": 1,
            "step": 0,
            "probability": 0.65,
            "max_uses_per_loop": 1,
        },
        "mix": {"gain_db": -12, "pan": 0, "fade_in_ms": 20, "fade_out_ms": 80},
        "fx": {"reverb": "room", "delay": "none", "filter": "none", "sidechain": False},
        "priority": 50,
        "created_at": "",
        "updated_at": "",
    }


def normalize_sample(sample: dict[str, Any]) -> dict[str, Any]:
    merged = default_sample()
    merged.update({key: value for key, value in sample.items() if key not in {"audio_info", "tag_rules", "trigger_rule", "mix", "fx"}})
    for key in ("audio_info", "tag_rules", "trigger_rule", "mix", "fx"):
        value = sample.get(key) if isinstance(sample.get(key), dict) else {}
        merged[key].update(value)
    merged["sample_id"] = str(merged.get("sample_id") or f"sample_{uuid.uuid4().hex[:10]}")
    merged["name"] = str(merged.get("name") or "Untitled Sample")
    merged["enabled"] = bool(merged.get("enabled"))
    merged["sample_type"] = enum_value(merged.get("sample_type"), SAMPLE_TYPES, "texture")
    merged["playback_type"] = enum_value(merged.get("playback_type"), PLAYBACK_TYPES, "loop")
    merged["trigger_rule"]["trigger_mode"] = enum_value(merged["trigger_rule"].get("trigger_mode"), TRIGGER_MODES, "on_loop_start")
    for key in ("emotion", "energy", "sound_direction", "rhythm"):
        values = merged["tag_rules"].get(key, [])
        merged["tag_rules"][key] = normalize_tag_values(key, values) if isinstance(values, list) else []
    merged["trigger_rule"]["bar"] = int_or_default(merged["trigger_rule"].get("bar"), 1)
    merged["trigger_rule"]["step"] = max(0, min(15, int_or_default(merged["trigger_rule"].get("step"), 0)))
    merged["trigger_rule"]["probability"] = max(0.0, min(1.0, float_or_default(merged["trigger_rule"].get("probability"), 0.65)))
    merged["trigger_rule"]["max_uses_per_loop"] = max(1, int_or_default(merged["trigger_rule"].get("max_uses_per_loop"), 1))
    merged["mix"]["gain_db"] = float_or_default(merged["mix"].get("gain_db"), -12)
    merged["mix"]["pan"] = max(-1.0, min(1.0, float_or_default(merged["mix"].get("pan"), 0)))
    merged["mix"]["fade_in_ms"] = max(0, int_or_default(merged["mix"].get("fade_in_ms"), 20))
    merged["mix"]["fade_out_ms"] = max(0, int_or_default(merged["mix"].get("fade_out_ms"), 80))
    merged["fx"]["sidechain"] = bool(merged["fx"].get("sidechain"))
    merged["priority"] = int_or_default(merged.get("priority"), 50)
    merged["file_size"] = int_or_default(merged.get("file_size"), 0)
    return merged


def resolve_sample_overlays(annotation: Any, bpm: int, bars: int, seed: int | None = None) -> list[dict[str, Any]]:
    samples = sorted((sample for sample in load_samples() if sample_has_audio_file(sample)), key=lambda item: item.get("priority", 0), reverse=True)
    matched = [sample for sample in samples if sample_matches_state(sample, annotation)]
    rng = __import__("random").Random(seed if seed is not None else repr(annotation))
    selected: list[dict[str, Any]] = []
    type_limits = {"texture": 2, "one_shot": 3, "transition": 1, "drum_loop": 1, "tonal_loop": 1}
    counts: dict[str, int] = {}
    for sample in matched:
        sample_type = sample.get("sample_type", "texture")
        limit = type_limits.get(sample_type, 8)
        if counts.get(sample_type, 0) >= limit:
            continue
        probability = sample["trigger_rule"].get("probability", 1)
        if rng.random() > probability:
            continue
        selected.append(overlay_payload(sample, bars))
        counts[sample_type] = counts.get(sample_type, 0) + 1
    return selected


def resolve_drum_sample_bank(annotation: Any) -> dict[str, dict[str, Any]]:
    samples = sorted((sample for sample in load_samples() if sample_has_audio_file(sample)), key=lambda item: item.get("priority", 0), reverse=True)
    bank: dict[str, dict[str, Any]] = {}
    for sample in samples:
        if sample.get("sample_type") != "drum_one_shot":
            continue
        if not sample_matches_state(sample, annotation):
            continue
        role = infer_drum_role(sample)
        if role and role not in bank:
            bank[role] = drum_sample_payload(sample, role)
    return bank


def infer_drum_role(sample: dict[str, Any]) -> str | None:
    text = " ".join(str(sample.get(key, "")) for key in ("name", "description", "file_name", "file_url")).lower()
    role_patterns = (
        ("kick", ("kick", "bd", "bass drum", "bassdrum", "大鼓", "底鼓")),
        ("snare", ("snare", "sd", "rim", "clap", "军鼓", "拍手")),
        ("open_hat", ("open hat", "open_hat", "oh", "开放镲", "开镲")),
        ("hat", ("hat", "hihat", "hi hat", "hh", "closed hat", "闭镲")),
        ("perc", ("perc", "percussion", "tom", "wood", "shaker", "rimshot", "打击", "敲击")),
    )
    for role, needles in role_patterns:
        if any(needle in text for needle in needles):
            return role
    return None


def drum_role_for_pitch(pitch: int) -> str | None:
    if pitch == 36:
        return "kick"
    if pitch in {38, 39}:
        return "snare"
    if pitch == 46:
        return "open_hat"
    if pitch == 42:
        return "hat"
    if pitch in {45, 47, 49, 50, 54, 70}:
        return "perc"
    return None


def drum_sample_payload(sample: dict[str, Any], role: str) -> dict[str, Any]:
    return {
        "sample_id": sample["sample_id"],
        "role": role,
        "file_url": sample.get("file_url", ""),
        "gain_db": float_or_default(sample.get("mix", {}).get("gain_db"), -6),
        "pan": max(-1.0, min(1.0, float_or_default(sample.get("mix", {}).get("pan"), 0))),
        "fade_in_ms": max(0, int_or_default(sample.get("mix", {}).get("fade_in_ms"), 0)),
        "fade_out_ms": max(0, int_or_default(sample.get("mix", {}).get("fade_out_ms"), 20)),
    }


def sample_matches_state(sample: dict[str, Any], annotation: Any) -> bool:
    if not sample.get("enabled", True):
        return False
    if not sample_has_audio_file(sample):
        return False
    from .resolver import resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction

    emotion = resolve_emotion(getattr(annotation, "emotion", "")).label
    energy = resolve_energy(getattr(annotation, "energy", "")).label
    sound_direction = resolve_sound_direction(getattr(annotation, "sound_direction", "")).value
    rhythm = resolve_rhythm(getattr(annotation, "rhythm", "")).value
    values = {
        "emotion": emotion,
        "energy": energy,
        "sound_direction": sound_direction,
        "rhythm": rhythm,
    }
    rules = sample.get("tag_rules", {})
    return all(rule_matches(rules.get(key, []), value) for key, value in values.items())


def overlay_payload(sample: dict[str, Any], bars: int) -> dict[str, Any]:
    trigger = sample["trigger_rule"]
    mix = sample["mix"]
    trigger_mode = trigger.get("trigger_mode", "on_loop_start")
    bar = int_or_default(trigger.get("bar"), 1)
    if trigger_mode in {"on_fill", "fill"} or sample.get("playback_type") == "fill":
        bar = bars
    return {
        "sample_id": sample["sample_id"],
        "name": sample.get("name") or sample["sample_id"],
        "source_type": "sample",
        "file_url": sample.get("file_url", ""),
        "sample_type": sample.get("sample_type", "texture"),
        "playback_type": sample.get("playback_type", "loop"),
        "trigger_mode": trigger_mode,
        "bar": max(1, min(bars, bar)),
        "step": max(0, min(15, int_or_default(trigger.get("step"), 0))),
        "gain_db": float_or_default(mix.get("gain_db"), -12),
        "pan": max(-1.0, min(1.0, float_or_default(mix.get("pan"), 0))),
        "fade_in_ms": max(0, int_or_default(mix.get("fade_in_ms"), 20)),
        "fade_out_ms": max(0, int_or_default(mix.get("fade_out_ms"), 80)),
        "max_uses_per_loop": max(1, int_or_default(trigger.get("max_uses_per_loop"), 1)),
    }


def sample_path_from_url(file_url: str) -> Path:
    path = Path(str(file_url).split("?", 1)[0].lstrip("/"))
    return (ROOT / path).resolve()


def sample_has_audio_file(sample: dict[str, Any]) -> bool:
    file_url = str(sample.get("file_url") or "").strip()
    if not file_url:
        return False
    return sample_path_from_url(file_url).is_file()


def analyze_audio_file(path: Path) -> dict[str, Any]:
    info = {"duration_seconds": 0.0, "sample_rate": None, "channels": None}
    try:
        with wave.open(str(path), "rb") as handle:
            frames = handle.getnframes()
            sample_rate = handle.getframerate()
            info.update(
                {
                    "duration_seconds": round(frames / sample_rate, 3) if sample_rate else 0.0,
                    "sample_rate": sample_rate,
                    "channels": handle.getnchannels(),
                }
            )
            return info
    except Exception:
        pass
    try:
        output = subprocess.run(["afinfo", str(path)], check=True, capture_output=True, text=True).stdout
        duration_match = re.search(r"estimated duration: ([0-9.]+) sec", output)
        rate_match = re.search(r"([0-9.]+) Hz", output)
        channels_match = re.search(r"(\d+) ch", output)
        if duration_match:
            info["duration_seconds"] = round(float(duration_match.group(1)), 3)
        if rate_match:
            info["sample_rate"] = int(float(rate_match.group(1)))
        if channels_match:
            info["channels"] = int(channels_match.group(1))
    except Exception:
        pass
    return info


def convert_to_wav_if_needed(path: Path) -> Path:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as handle:
                if handle.getcomptype() == "NONE":
                    return path
        except wave.Error:
            # WAV may still use IEEE float samples, which Python's wave reader
            # cannot mix directly. Convert it to PCM below.
            pass
    temp_path = Path(tempfile.gettempdir()) / f"sample_overlay_{uuid.uuid4().hex}.wav"
    converter = shutil.which("afconvert")
    if converter is None:
        raise RuntimeError("This sample format needs afconvert to render.")
    subprocess.run([converter, "-f", "WAVE", "-d", "LEI16", str(path), str(temp_path)], check=True, capture_output=True)
    return temp_path


def db_to_gain(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def ensure_sample_dirs() -> None:
    SAMPLE_FILE_DIR.mkdir(parents=True, exist_ok=True)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return name or "sample"


def title_from_file(value: str) -> str:
    return Path(value).stem.replace("_", " ").replace("-", " ").strip().title() or "Untitled Sample"


def enum_value(value: Any, options: tuple[str, ...], fallback: str) -> str:
    return str(value) if str(value) in options else fallback


def int_or_default(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def float_or_default(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def rule_matches(rule_values: list[str], value: str) -> bool:
    return not rule_values or value in rule_values


def normalize_tag_values(key: str, values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = normalize_tag_value(key, value)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def normalize_tag_value(key: str, value: Any) -> str:
    try:
        from .resolver import resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction

        if key == "emotion":
            return resolve_emotion(value).label
        if key == "energy":
            return resolve_energy(value).label
        if key == "sound_direction":
            return resolve_sound_direction(str(value)).value
        if key == "rhythm":
            return resolve_rhythm(str(value)).value
    except Exception:
        pass
    return str(value)
