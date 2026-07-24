from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Any

from .midi_writer import PPQ


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "foundation-patterns"
FILES_DIR = DATA_DIR / "files"
TEMP_DIR = DATA_DIR / "temp"
DB_PATH = DATA_DIR / "foundation_patterns.json"
PENDING_PATH = TEMP_DIR / "pending_uploads.json"
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
EMOTIONS = ["深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂"]
ENERGIES = ["静止", "高能", "流动"]
SOUNDS = ["ambient", "acoustic", "organic", "vintage", "electronic", "ethnic", "cinematic"]
RHYTHMS = ["sparse", "flow", "standard", "groove", "aggressive"]


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _safe_filename(name: str) -> str:
    original = Path(name).name
    suffix = Path(original).suffix.lower()
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(original).stem).strip("._") or "foundation"
    return f"{stem}{suffix}" if suffix else stem


def _load_patterns() -> list[dict[str, Any]]:
    data = _read_json(DB_PATH, {"patterns": []})
    patterns = data.get("patterns", []) if isinstance(data, dict) and isinstance(data.get("patterns"), list) else []
    changed = False
    for pattern in patterns:
        # Logic labels MIDI 60 as C3; the sampler uses the standard C4=60 convention.
        # Legacy uploads were saved before this conversion and must be brought into the same register.
        if pattern.get("midi_note_octave_offset") is None:
            for event in pattern.get("events", []):
                event["note"] = max(0, min(127, int(event.get("note", 60)) - 12))
            analysis = pattern.get("analysis") if isinstance(pattern.get("analysis"), dict) else {}
            notes = [int(event["note"]) for event in pattern.get("events", [])]
            if notes:
                analysis["lowest_note"] = min(notes)
                analysis["highest_note"] = max(notes)
            pattern["analysis"] = analysis
            pattern["midi_note_octave_offset"] = -12
            pattern["midi_note_convention"] = "logic_c3_is_midi_60"
            changed = True
    if changed:
        _write_json(DB_PATH, {"patterns": patterns})
    return patterns


def _save_patterns(patterns: list[dict[str, Any]]) -> None:
    _write_json(DB_PATH, {"patterns": patterns})


def _load_pending() -> dict[str, Any]:
    data = _read_json(PENDING_PATH, {})
    return data if isinstance(data, dict) else {}


def _save_pending(pending: dict[str, Any]) -> None:
    _write_json(PENDING_PATH, pending)


def read_vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    for _ in range(4):
        if offset >= len(data):
            raise ValueError("MIDI variable length value is incomplete.")
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset
    return value, offset


def parse_midi(data: bytes) -> dict[str, Any]:
    if len(data) < 14 or data[:4] != b"MThd":
        raise ValueError("只支持标准 MIDI 文件（.mid / .midi）。")
    header_len = int.from_bytes(data[4:8], "big")
    if header_len < 6 or len(data) < 8 + header_len:
        raise ValueError("MIDI 文件头无效。")
    fmt = int.from_bytes(data[8:10], "big")
    track_count = int.from_bytes(data[10:12], "big")
    division = int.from_bytes(data[12:14], "big")
    if division & 0x8000:
        raise ValueError("暂不支持 SMPTE 时间格式 MIDI。")
    ppq = division
    if ppq <= 0:
        raise ValueError("MIDI PPQ 无效。")
    offset = 8 + header_len
    tracks = []
    global_meta: dict[str, Any] = {"tempo": None, "time_signature": "4/4"}
    for index in range(track_count):
        if offset + 8 > len(data) or data[offset:offset + 4] != b"MTrk":
            raise ValueError("MIDI 轨道数据无效。")
        length = int.from_bytes(data[offset + 4:offset + 8], "big")
        raw = data[offset + 8:offset + 8 + length]
        if len(raw) != length:
            raise ValueError("MIDI 轨道被截断。")
        tracks.append(_parse_track(raw, index, global_meta))
        offset += 8 + length
    return {"format": fmt, "ppq": ppq, "track_count": track_count, "tempo": global_meta["tempo"], "time_signature": global_meta["time_signature"], "tracks": tracks}


def _parse_track(raw: bytes, index: int, global_meta: dict[str, Any]) -> dict[str, Any]:
    offset = 0
    tick = 0
    running_status: int | None = None
    name = f"Track {index + 1}"
    notes: list[dict[str, int]] = []
    active: dict[tuple[int, int], list[tuple[int, int]]] = {}
    channels: set[int] = set()
    while offset < len(raw):
        delta, offset = read_vlq(raw, offset)
        tick += delta
        if offset >= len(raw):
            break
        first = raw[offset]
        if first < 0x80:
            if running_status is None:
                raise ValueError("MIDI running status 无效。")
            status = running_status
        else:
            status = first
            offset += 1
            if status < 0xF0:
                running_status = status
        if status == 0xFF:
            if offset >= len(raw):
                break
            meta_type = raw[offset]
            offset += 1
            size, offset = read_vlq(raw, offset)
            payload = raw[offset:offset + size]
            offset += size
            if meta_type == 0x03:
                name = payload.decode("utf-8", errors="replace") or name
            elif meta_type == 0x51 and len(payload) == 3 and global_meta.get("tempo") is None:
                global_meta["tempo"] = int.from_bytes(payload, "big")
            elif meta_type == 0x58 and len(payload) >= 2:
                global_meta["time_signature"] = f"{payload[0]}" + "/" + str(2 ** payload[1])
            continue
        if status in {0xF0, 0xF7}:
            size, offset = read_vlq(raw, offset)
            offset += size
            continue
        command, channel = status & 0xF0, status & 0x0F
        data_len = 1 if command in {0xC0, 0xD0} else 2
        if offset + data_len > len(raw):
            break
        values = raw[offset:offset + data_len]
        offset += data_len
        channels.add(channel)
        if command not in {0x80, 0x90}:
            continue
        note = int(values[0])
        velocity = int(values[1]) if data_len > 1 else 0
        key = (channel, note)
        if command == 0x90 and velocity > 0:
            # Duplicate Note On is closed at the new onset so it cannot create a hanging note.
            for start, prior_velocity in active.pop(key, []):
                if tick > start:
                    notes.append({"start_tick": start, "duration_ticks": tick - start, "note": note, "velocity": prior_velocity, "channel": channel})
            active.setdefault(key, []).append((tick, velocity))
        else:
            starts = active.get(key, [])
            if starts:
                start, prior_velocity = starts.pop(0)
                if tick > start:
                    notes.append({"start_tick": start, "duration_ticks": tick - start, "note": note, "velocity": prior_velocity, "channel": channel})
                if not starts:
                    active.pop(key, None)
    for (channel, note), starts in active.items():
        for start, velocity in starts:
            if tick > start:
                notes.append({"start_tick": start, "duration_ticks": tick - start, "note": note, "velocity": velocity, "channel": channel})
    notes.sort(key=lambda item: (item["start_tick"], item["note"], item["channel"]))
    return {"index": index, "name": name, "events": notes, "channels": sorted(channels), "length_ticks": tick}


def _polyphony(events: list[dict[str, int]]) -> int:
    changes: list[tuple[int, int]] = []
    for event in events:
        changes.extend(((event["start_tick"], 1), (event["start_tick"] + event["duration_ticks"], -1)))
    active = peak = 0
    for _, delta in sorted(changes, key=lambda item: (item[0], item[1])):
        active += delta
        peak = max(peak, active)
    return peak


def analyze_track(track: dict[str, Any], ppq: int) -> dict[str, Any]:
    events = track["events"]
    if not events:
        return {"track_index": track["index"], "track_name": track["name"], "note_count": 0, "channels": track["channels"], "length_ticks": track["length_ticks"], "estimated_bars": 0}
    first = min(item["start_tick"] for item in events)
    last = max(item["start_tick"] + item["duration_ticks"] for item in events)
    duration = max(0, last - first)
    return {
        "track_index": track["index"], "track_name": track["name"], "note_count": len(events), "channels": track["channels"],
        "first_note_tick": first, "last_note_tick": last, "length_ticks": duration, "estimated_bars": round(duration / max(1, ppq * 4), 2),
        "lowest_note": min(item["note"] for item in events), "highest_note": max(item["note"] for item in events),
        "average_velocity": round(sum(item["velocity"] for item in events) / len(events), 2), "min_velocity": min(item["velocity"] for item in events), "max_velocity": max(item["velocity"] for item in events),
        "average_duration_ticks": round(sum(item["duration_ticks"] for item in events) / len(events), 2), "polyphony_peak": _polyphony(events),
    }


def analyze_midi(data: bytes) -> dict[str, Any]:
    parsed = parse_midi(data)
    tracks = [analyze_track(track, parsed["ppq"]) for track in parsed["tracks"] if track["events"]]
    suggested = 4 if any(3.8 <= item["estimated_bars"] <= 4.2 for item in tracks) else 8 if any(7.8 <= item["estimated_bars"] <= 8.2 for item in tracks) else None
    return {"ppq": parsed["ppq"], "tempo_microseconds": parsed["tempo"], "time_signature": parsed["time_signature"], "track_count": parsed["track_count"], "note_tracks": tracks, "suggested_loop_length_bars": suggested}


def normalize_events(events: list[dict[str, int]], original_ppq: int, bars: int) -> list[dict[str, int]]:
    if bars not in {4, 8}:
        raise ValueError("Foundation Pattern 只支持 4 或 8 小节。")
    if not events:
        raise ValueError("选择的轨道没有可用的 MIDI 音符。")
    first_tick = min(item["start_tick"] for item in events)
    end_limit = bars * 4 * PPQ
    normalized: list[dict[str, int]] = []
    for item in events:
        start = round((item["start_tick"] - first_tick) * PPQ / original_ppq)
        duration = round(item["duration_ticks"] * PPQ / original_ppq)
        start = max(0, start)
        duration = max(1, duration)
        if start >= end_limit:
            continue
        duration = min(duration, end_limit - start)
        if duration <= 0:
            continue
        normalized.append({"start_tick": start, "duration_ticks": duration, "note": max(0, min(127, int(item["note"]) - 12)), "velocity": max(1, min(127, int(item["velocity"]))), "channel": max(0, min(15, int(item.get("channel", 0))))})
    normalized.sort(key=lambda item: (item["start_tick"], item["note"], item["channel"]))
    if not normalized:
        raise ValueError("选择的 MIDI 音符都落在 Pattern 长度之外。")
    return normalized


def _tags(value: Any, allowed: list[str]) -> list[str]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",")]
    return [str(item) for item in (value or []) if str(item) in allowed]


def _chords(value: Any, bars: int) -> list[str]:
    if isinstance(value, str):
        value = [item.strip() for item in re.split(r"[,|\n]+", value)]
    chords = [str(item).strip() for item in (value or []) if str(item).strip()]
    if len(chords) != bars:
        raise ValueError(f"Source Chords 必须填写 {bars} 个和弦，每小节一个。")
    return chords


def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000):x}_{hashlib.sha1(str(time.time_ns()).encode()).hexdigest()[:6]}"


def cleanup_pending(max_age_seconds: int = 24 * 60 * 60) -> None:
    pending = _load_pending()
    now = time.time()
    for upload_id, entry in list(pending.items()):
        if now - float(entry.get("created_epoch", 0)) > max_age_seconds:
            path = TEMP_DIR / str(entry.get("file_name", ""))
            path.unlink(missing_ok=True)
            pending.pop(upload_id, None)
    _save_pending(pending)


def stage_upload(file_name: str, data: bytes) -> dict[str, Any]:
    cleanup_pending()
    safe_name = _safe_filename(file_name)
    if Path(safe_name).suffix.lower() not in {".mid", ".midi"}:
        raise ValueError("只允许上传 .mid 或 .midi 文件。")
    if not data or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("MIDI 文件为空或超过 12MB 限制。")
    analysis = analyze_midi(data)
    if not analysis["note_tracks"]:
        raise ValueError("MIDI 文件中没有可用的音符轨道。")
    upload_id = _new_id("foundation_upload")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_name = f"{upload_id}_{safe_name}"
    (TEMP_DIR / temp_name).write_bytes(data)
    pending = _load_pending()
    pending[upload_id] = {"file_name": temp_name, "original_file_name": safe_name, "analysis": analysis, "created_epoch": time.time()}
    _save_pending(pending)
    selected = analysis["note_tracks"][0]["track_index"] if len(analysis["note_tracks"]) == 1 else None
    return {"upload_id": upload_id, "analysis": analysis, "auto_selected_track_index": selected}


def save_staged_pattern(upload_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    pending = _load_pending()
    entry = pending.get(upload_id)
    if not entry:
        raise ValueError("临时上传已过期，请重新上传 MIDI。")
    temp_path = TEMP_DIR / str(entry["file_name"])
    data = temp_path.read_bytes() if temp_path.is_file() else b""
    if not data:
        raise ValueError("临时 MIDI 文件不存在，请重新上传。")
    parsed = parse_midi(data)
    tracks = [track for track in parsed["tracks"] if track["events"]]
    requested_index = payload.get("source_track_index")
    if requested_index is None and len(tracks) == 1:
        requested_index = tracks[0]["index"]
    try:
        requested_index = int(requested_index)
    except (TypeError, ValueError):
        raise ValueError("请先选择一个含音符的 Foundation 源轨道。")
    track = next((item for item in tracks if item["index"] == requested_index), None)
    if not track:
        raise ValueError("选择的 MIDI 轨道不存在或没有音符。")
    bars = int(payload.get("loop_length_bars") or entry["analysis"].get("suggested_loop_length_bars") or 4)
    events = normalize_events(track["events"], parsed["ppq"], bars)
    analysis = analyze_track({**track, "events": events, "length_ticks": max(item["start_tick"] + item["duration_ticks"] for item in events)}, PPQ)
    original_analysis = analyze_track(track, parsed["ppq"])
    warnings = []
    estimated = original_analysis.get("estimated_bars", 0)
    if not ((bars == 4 and 3.8 <= estimated <= 4.2) or (bars == 8 and 7.8 <= estimated <= 8.2)):
        warnings.append("Foundation Pattern 长度与 4/8 小节建议不完全一致，已按所选长度裁切或补静音。")
    if analysis.get("lowest_note", 48) < 48:
        warnings.append("Pattern contains notes below recommended Foundation range (C3).")
    if analysis.get("highest_note", 84) > 84:
        warnings.append("Pattern contains notes above recommended Foundation range (C6).")
    pattern_id = _new_id("foundation_pattern")
    destination_name = f"{pattern_id}_{entry['original_file_name']}"
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    shutil.move(str(temp_path), str(FILES_DIR / destination_name))
    pattern = {
        "id": pattern_id, "name": str(payload.get("name") or Path(entry["original_file_name"]).stem).strip(), "description": str(payload.get("description") or "").strip(),
        "enabled": bool(payload.get("enabled", True)), "priority": int(payload.get("priority", 100)), "version": str(payload.get("version") or "1.0.0"),
        "loop_length_bars": bars, "ppq": PPQ, "time_signature": "4/4",
        "midi_note_octave_offset": -12, "midi_note_convention": "logic_c3_is_midi_60",
        "source_file": {"file_name": entry["original_file_name"], "file_path": f"data/foundation-patterns/files/{destination_name}", "track_index": requested_index, "track_name": track["name"]},
        "source_harmony": {"key_root": normalize_key_root(payload.get("source_key_root") or "C"), "mode": str(payload.get("source_mode") or "major"), "chords": _chords(payload.get("source_chords"), bars)},
        "tag_rules": {"emotion": _tags(payload.get("emotion"), EMOTIONS), "energy": _tags(payload.get("energy"), ENERGIES), "sound_direction": _tags(payload.get("sound_direction"), SOUNDS), "rhythm": _tags(payload.get("rhythm"), RHYTHMS)},
        "events": events, "analysis": {**analysis, "original_ppq": parsed["ppq"], "normalized_ppq": PPQ, "original": original_analysis, "warnings": warnings}, "created_at": _now(), "updated_at": _now(),
    }
    if not pattern["name"]:
        raise ValueError("Pattern Name 不能为空。")
    patterns = _load_patterns()
    patterns.append(pattern)
    _save_patterns(patterns)
    pending.pop(upload_id, None)
    _save_pending(pending)
    return pattern


def export_foundation_patterns() -> dict[str, Any]:
    patterns = sorted(_load_patterns(), key=lambda item: (-int(item.get("priority", 0)), item.get("name", "")))
    return {"patterns": patterns, "definitions": {"emotion": EMOTIONS, "energy": ENERGIES, "sound_direction": SOUNDS, "rhythm": RHYTHMS, "loop_lengths": [4, 8], "source_modes": ["major", "minor", "modal", "chromatic", "unknown"]}}


def get_foundation_pattern(pattern_id: str) -> dict[str, Any] | None:
    return next((item for item in _load_patterns() if item.get("id") == pattern_id), None)


def update_foundation_pattern(pattern_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    patterns = _load_patterns()
    for index, pattern in enumerate(patterns):
        if pattern.get("id") != pattern_id:
            continue
        updated = {**pattern, **{key: value for key, value in payload.items() if key in {"name", "description", "enabled", "priority", "version"}}}
        if "source_harmony" in payload:
            source = payload["source_harmony"] if isinstance(payload["source_harmony"], dict) else {}
            updated["source_harmony"] = {"key_root": normalize_key_root(source.get("key_root") or pattern["source_harmony"]["key_root"]), "mode": str(source.get("mode") or pattern["source_harmony"]["mode"]), "chords": _chords(source.get("chords"), int(updated["loop_length_bars"]))}
        if "tag_rules" in payload and isinstance(payload["tag_rules"], dict):
            tags = payload["tag_rules"]
            updated["tag_rules"] = {"emotion": _tags(tags.get("emotion"), EMOTIONS), "energy": _tags(tags.get("energy"), ENERGIES), "sound_direction": _tags(tags.get("sound_direction"), SOUNDS), "rhythm": _tags(tags.get("rhythm"), RHYTHMS)}
        updated["updated_at"] = _now()
        patterns[index] = updated
        _save_patterns(patterns)
        return updated
    raise ValueError("Foundation Pattern 不存在。")


def delete_foundation_pattern(pattern_id: str) -> list[dict[str, Any]]:
    patterns = _load_patterns()
    current = next((item for item in patterns if item.get("id") == pattern_id), None)
    if current:
        (ROOT / current.get("source_file", {}).get("file_path", "")).unlink(missing_ok=True)
    patterns = [item for item in patterns if item.get("id") != pattern_id]
    _save_patterns(patterns)
    return patterns


def duplicate_foundation_pattern(pattern_id: str) -> dict[str, Any]:
    source = get_foundation_pattern(pattern_id)
    if not source:
        raise ValueError("Foundation Pattern 不存在。")
    copy = json.loads(json.dumps(source))
    copy["id"] = _new_id("foundation_pattern")
    copy["name"] = f"{source.get('name', 'Pattern')} Copy"
    copy["created_at"] = _now()
    copy["updated_at"] = _now()
    patterns = _load_patterns()
    patterns.append(copy)
    _save_patterns(patterns)
    return copy


def normalize_register(pattern_id: str) -> dict[str, Any]:
    pattern = get_foundation_pattern(pattern_id)
    if not pattern:
        raise ValueError("Foundation Pattern 不存在。")
    events = []
    for event in pattern.get("events", []):
        note = int(event["note"])
        while note < 48:
            note += 12
        while note > 84:
            note -= 12
        events.append({**event, "note": note})
    return _replace_events(pattern_id, events)


def normalize_key_root(value: Any) -> str:
    root = str(value).strip()
    if not re.fullmatch(r"[A-Ga-g](?:#|b)?", root):
        raise ValueError("Source Key Root 必须是 C、F# 或 Bb 这类音名。")
    return root[:1].upper() + root[1:]


def _replace_events(pattern_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    patterns = _load_patterns()
    for index, pattern in enumerate(patterns):
        if pattern.get("id") == pattern_id:
            pattern["events"] = events
            pattern["analysis"] = {**pattern.get("analysis", {}), **analyze_track({"index": pattern["source_file"]["track_index"], "name": pattern["source_file"]["track_name"], "events": events, "channels": sorted({item["channel"] for item in events}), "length_ticks": max((item["start_tick"] + item["duration_ticks"] for item in events), default=0)}, PPQ)}
            pattern["updated_at"] = _now()
            patterns[index] = pattern
            _save_patterns(patterns)
            return pattern
    raise ValueError("Foundation Pattern 不存在。")


def _state_values(annotation: Any) -> dict[str, str]:
    from .resolver import resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction
    return {
        "emotion": resolve_emotion(annotation.emotion).label,
        "energy": resolve_energy(annotation.energy).label,
        "sound_direction": resolve_sound_direction(annotation.sound_direction).value,
        "rhythm": resolve_rhythm(annotation.rhythm).value,
    }


def match_foundation_pattern(annotation: Any, bars: int, seed: int, pattern_id: str | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    patterns = _load_patterns()
    if pattern_id:
        pattern = next((item for item in patterns if item.get("id") == pattern_id and item.get("enabled", True) and int(item.get("loop_length_bars", 4)) == bars), None)
        return pattern, ["manual"] if pattern else []
    values = _state_values(annotation)
    matches: list[tuple[int, int, dict[str, Any], list[str]]] = []
    for pattern in patterns:
        if not pattern.get("enabled", True) or int(pattern.get("loop_length_bars", 4)) != bars:
            continue
        matched = []
        ok = True
        for field, value in values.items():
            allowed = pattern.get("tag_rules", {}).get(field, [])
            if allowed and value not in allowed:
                ok = False
                break
            if allowed:
                matched.append(field)
        if ok:
            matches.append((len(matched), int(pattern.get("priority", 0)), pattern, matched))
    if not matches:
        return None, []
    top_score = max((score, priority) for score, priority, _, _ in matches)
    finalists = [item for item in matches if item[:2] == top_score]
    finalists.sort(key=lambda item: item[2].get("id", ""))
    selected = finalists[seed % len(finalists)]
    return selected[2], selected[3]
