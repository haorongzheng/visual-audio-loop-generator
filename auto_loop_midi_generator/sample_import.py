from __future__ import annotations

import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .instrument_library import CATEGORIES, TRACK_ROLES, blank_instrument, get_instrument, normalize_zone, root_note_from_file_name, upsert_instrument
from .sample_library import analyze_audio_file, convert_to_wav_if_needed, safe_name


ROOT = Path(__file__).resolve().parent.parent
IMPORT_DIR = ROOT / "sample_import"
JOB_DIR = IMPORT_DIR / "jobs"
JOB_DB = IMPORT_DIR / "sample_import_jobs.json"
SOURCE_DB = IMPORT_DIR / "sample_sources.json"
MAX_FILES = 512
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
VSCO_MAX_FILES = 6000
VSCO_MAX_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
AUDIO_EXTENSIONS = {".wav", ".aif", ".aiff", ".flac"}
ALLOWED_EXTENSIONS = {*AUDIO_EXTENSIONS, ".sfz", ".txt"}
SFZ_PAIR = re.compile(r"([A-Za-z_]+)\s*=\s*(?:\"([^\"]*)\"|([^\s]+))")
MAPPING_CHART_LINE = re.compile(r"^\s*(?P<sample>.+?\.(?:wav|aif|aiff|flac))\s+(?P<key>[A-Ga-g](?:#|b)?-?\d+|\d{1,3})\s*$", re.IGNORECASE)
MAPPING_CHART_INDEX = re.compile(r"^\s*(?P<index>\d{1,4})\s*=\s*(?P<key>[A-Ga-g](?:#|b)?-?\d+|\d{1,3})\s*$", re.IGNORECASE)
DYNAMIC_RE = re.compile(r"(?:^|[_\-.])dyn(?:amic)?[_\-.]?(\d+)(?:$|[_\-.])", re.IGNORECASE)
ROUND_ROBIN_RE = re.compile(r"(?:^|[_\-.])rr[_\-.]?(\d+)(?:$|[_\-.])", re.IGNORECASE)


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _jobs() -> list[dict[str, Any]]:
    data = _read(JOB_DB, {"jobs": []})
    return data.get("jobs", []) if isinstance(data, dict) and isinstance(data.get("jobs"), list) else []


def _save_jobs(jobs: list[dict[str, Any]]) -> None:
    _write(JOB_DB, {"jobs": jobs})


def safe_relative_path(value: str) -> Path:
    raw = str(value or "").replace("\\", "/")
    path = Path(raw)
    if "\x00" in raw or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("不允许包含绝对路径或 ../ 的文件名。")
    # Keep C#3 and Bb2 intact: the note token is part of the import contract.
    # The resolved target below is still constrained to the job directory.
    if not path.parts:
        raise ValueError("文件名无效。")
    return Path(*path.parts)


def job_by_id(job_id: str) -> dict[str, Any] | None:
    return next((job for job in _jobs() if job.get("id") == job_id), None)


def save_job(updated: dict[str, Any]) -> dict[str, Any]:
    jobs = _jobs()
    for index, job in enumerate(jobs):
        if job.get("id") == updated.get("id"):
            jobs[index] = updated
            break
    else:
        jobs.append(updated)
    _save_jobs(jobs)
    return updated


def created_instruments(job: dict[str, Any]) -> list[dict[str, str]]:
    """Return the instruments that were actually created from an import job."""
    instrument_ids = [str(job.get("instrument_id") or "")]
    instrument_ids.extend(str(item) for item in job.get("instrument_ids", []) if item)
    seen: set[str] = set()
    result: list[dict[str, str]] = []
    for instrument_id in instrument_ids:
        if not instrument_id or instrument_id in seen:
            continue
        seen.add(instrument_id)
        instrument = get_instrument(instrument_id)
        result.append({"id": instrument_id, "name": str((instrument or {}).get("name") or instrument_id)})
    return result


def _job_instrument_ids(job: dict[str, Any]) -> list[str]:
    instrument_ids = [str(job.get("instrument_id") or "")]
    instrument_ids.extend(str(item) for item in job.get("instrument_ids", []) if item)
    return list(dict.fromkeys(item for item in instrument_ids if item))


def _job_folder(job_id: str) -> Path:
    root = JOB_DIR.resolve()
    folder = (JOB_DIR / job_id).resolve()
    if not folder.is_relative_to(root):
        raise ValueError("导入任务路径无效。")
    return folder


def _folder_size(folder: Path) -> int:
    return sum(item.stat().st_size for item in folder.rglob("*") if item.is_file()) if folder.exists() else 0


def delete_uncreated_job(job_id: str) -> dict[str, Any]:
    """Delete a staged analysis job only when it has not created any instrument."""
    jobs = _jobs()
    job = next((item for item in jobs if item.get("id") == job_id), None)
    if not job:
        raise ValueError("导入任务不存在。")
    if job.get("status") == "completed" or job.get("instrument_id") or job.get("instrument_ids"):
        raise ValueError("该任务已经创建乐器，不能从导入任务中删除。")

    shutil.rmtree(_job_folder(job_id), ignore_errors=True)
    _save_jobs([item for item in jobs if item.get("id") != job_id])
    return {"id": job_id}


def cleanup_orphaned_completed_jobs() -> dict[str, Any]:
    """Remove old staged imports whose only created instruments were deleted."""
    jobs = _jobs()
    kept: list[dict[str, Any]] = []
    deleted: list[str] = []
    bytes_freed = 0
    for job in jobs:
        instrument_ids = _job_instrument_ids(job)
        is_orphan = job.get("status") == "completed" and bool(instrument_ids) and not any(get_instrument(item) for item in instrument_ids)
        if not is_orphan:
            kept.append(job)
            continue
        folder = _job_folder(str(job.get("id") or ""))
        bytes_freed += _folder_size(folder)
        shutil.rmtree(folder, ignore_errors=True)
        deleted.append(str(job["id"]))
    if deleted:
        _save_jobs(kept)
    return {"job_ids": deleted, "count": len(deleted), "bytes_freed": bytes_freed}


def stage_upload(source_type: str, files: list[tuple[str, bytes]]) -> dict[str, Any]:
    source_type = source_type if source_type in {"single_wav", "folder", "sfz", "mappingchart"} else "folder"
    if not files:
        raise ValueError("请选择 WAV、文件夹或 SFZ 文件。")
    if len(files) > MAX_FILES:
        raise ValueError(f"一次最多导入 {MAX_FILES} 个文件。")
    if sum(len(data) for _, data in files) > MAX_TOTAL_BYTES:
        raise ValueError("导入文件总大小超过 256MB 限制。")
    job_id = f"import_{uuid.uuid4().hex[:12]}"
    folder = JOB_DIR / job_id
    stored_files = []
    for original_name, data in files:
        relative = safe_relative_path(original_name)
        suffix = relative.suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS or (suffix == ".txt" and source_type != "mappingchart"):
            raise ValueError("仅支持 .wav、.aif、.aiff、.flac、.sfz；MappingChart 模式可额外包含 .txt 文件。")
        if len(data) > MAX_FILE_BYTES:
            raise ValueError(f"{relative.name} 超过 64MB 限制。")
        target = (folder / relative).resolve()
        if not target.is_relative_to(folder.resolve()):
            raise ValueError("文件路径无效。")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        stored_files.append({"relative_path": relative.as_posix(), "file_name": relative.name, "size": len(data), "extension": suffix})
    extensions = {item["extension"] for item in stored_files}
    if source_type == "single_wav" and extensions != {".wav"}:
        raise ValueError("单个 WAV 模式只能上传一个 .wav 文件。")
    if source_type == "single_wav" and len(stored_files) != 1:
        raise ValueError("单个 WAV 模式只能上传一个文件。")
    if source_type == "sfz" and ".sfz" not in extensions:
        raise ValueError("SFZ 模式请同时选择 .sfz 文件和其引用的采样。")
    if source_type == "mappingchart" and not any(item["file_name"].lower() == "mappingchart.txt" for item in stored_files):
        raise ValueError("MappingChart 模式需要完整文件夹中的 MappingChart.txt。")
    job = {"id": job_id, "source_type": source_type, "source_path": f"sample_import/jobs/{job_id}", "status": "pending", "total_files": len(stored_files), "processed_files": 0, "error_count": 0, "created_at": now(), "files": stored_files}
    save_job(job)
    return analyze_job(job_id)


def parse_sfz(text: str) -> list[dict[str, str]]:
    regions: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    inherited: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        tags = re.findall(r"<([^>]+)>", line)
        if tags:
            header = tags[-1].strip().lower()
            if header == "region":
                current = dict(inherited)
                regions.append(current)
            elif header in {"global", "control", "group"}:
                current = inherited
            line = re.sub(r"<[^>]+>", "", line).strip()
        pairs = {key.lower(): quoted or plain or "" for key, quoted, plain in SFZ_PAIR.findall(line)}
        default_path = re.search(r"\bdefault_path\s*=\s*(.+)$", line, re.IGNORECASE)
        if default_path:
            pairs["default_path"] = default_path.group(1).strip().strip('"')
        if current is None:
            inherited.update(pairs)
        else:
            current.update(pairs)
    return [region for region in regions if region.get("sample")]


def start_vsco_import() -> dict[str, Any]:
    job = {
        "id": f"vsco_{uuid.uuid4().hex[:12]}", "source_type": "vsco_library", "source_path": "",
        "status": "uploading", "total_files": 0, "processed_files": 0, "error_count": 0,
        "total_bytes": 0, "created_at": now(), "files": [],
    }
    job["source_path"] = f"sample_import/jobs/{job['id']}"
    save_job(job)
    return job


def append_vsco_file(job_id: str, file_name: str, data: bytes) -> dict[str, Any]:
    job = job_by_id(job_id)
    if not job or job.get("source_type") != "vsco_library":
        raise ValueError("VSCO 导入任务不存在。")
    relative = safe_relative_path(file_name)
    suffix = relative.suffix.lower()
    if suffix not in {*AUDIO_EXTENSIONS, ".sfz"}:
        raise ValueError("VSCO 导入仅接收 .sfz、.wav、.aif、.aiff、.flac。")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"{relative.name} 超过 64MB 限制。")
    existing = {item["relative_path"] for item in job.get("files", [])}
    if relative.as_posix() in existing:
        return job
    if len(existing) >= VSCO_MAX_FILES:
        raise ValueError(f"VSCO 导入最多支持 {VSCO_MAX_FILES} 个文件。")
    if int(job.get("total_bytes", 0)) + len(data) > VSCO_MAX_TOTAL_BYTES:
        raise ValueError("VSCO 导入总大小超过 8GB 限制。")
    root = (JOB_DIR / job_id).resolve()
    target = (root / relative).resolve()
    if not target.is_relative_to(root):
        raise ValueError("文件路径无效。")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    job["files"].append({"relative_path": relative.as_posix(), "file_name": relative.name, "size": len(data), "extension": suffix})
    job["total_files"] = len(job["files"])
    job["total_bytes"] = int(job.get("total_bytes", 0)) + len(data)
    job["processed_files"] = job["total_files"]
    save_job(job)
    return job


def _sfz_zone(region: dict[str, str], entry: dict[str, Any], folder: Path, source_library: str) -> dict[str, Any]:
    metadata = filename_metadata(entry["file_name"])
    root = midi_value(region.get("pitch_keycenter"), root_note_from_file_name(entry["file_name"]))
    group = str(region.get("group_label") or "")
    return {
        "file_name": entry["file_name"], "relative_path": entry["relative_path"], "root_midi_note": root,
        "low_midi_note": midi_value(region.get("lokey"), root), "high_midi_note": midi_value(region.get("hikey"), root),
        "velocity_low": max(1, midi_value(region.get("lovel"), 1)), "velocity_high": max(1, midi_value(region.get("hivel"), 127)),
        "gain_db": sfz_volume_db(region.get("volume")),
        "round_robin_group": group or ("sfz_rr" if metadata["round_robin_index"] > 1 else ""),
        "articulation": str(region.get("group_label") or metadata["articulation"]), "source_library": source_library,
        **metadata, **_audio_metadata(folder / entry["relative_path"]),
    }


def sfz_volume_db(value: Any) -> float:
    try:
        return max(-36.0, min(24.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def analyze_vsco_job(job_id: str) -> dict[str, Any]:
    job = job_by_id(job_id)
    if not job or job.get("source_type") != "vsco_library":
        raise ValueError("VSCO 导入任务不存在。")
    folder = JOB_DIR / job_id
    files = job.get("files", [])
    sfz_files = [item for item in files if item.get("extension") == ".sfz"]
    audio_by_relative = {str(item["relative_path"]).lower(): item for item in files if item.get("extension") in AUDIO_EXTENSIONS}
    audio_by_name: dict[str, list[dict[str, Any]]] = {}
    for item in audio_by_relative.values():
        audio_by_name.setdefault(str(item["file_name"]).lower(), []).append(item)
    instruments: list[dict[str, Any]] = []
    all_warnings: list[str] = []
    for sfz in sfz_files:
        sfz_path = folder / sfz["relative_path"]
        regions = parse_sfz(sfz_path.read_text(encoding="utf-8", errors="replace"))
        zones: list[dict[str, Any]] = []
        warnings: list[str] = []
        for region in regions:
            sample = str(region.get("sample", "")).replace("\\", "/")
            default_path = str(region.get("default_path", "")).replace("\\", "/").strip("/")
            relative = (Path(sfz["relative_path"]).parent / default_path / sample).as_posix().lower()
            entries = [audio_by_relative.get(relative)] if relative in audio_by_relative else audio_by_name.get(Path(sample).name.lower(), [])
            entries = [entry for entry in entries if entry]
            if not entries:
                warnings.append(f"未找到 {sample}")
                continue
            zones.append(_sfz_zone(region, entries[0], folder, "VSCO2"))
        if not zones:
            continue
        instruments.append({
            "id": f"vsco_{safe_name(Path(sfz['file_name']).stem)}", "name": Path(sfz["file_name"]).stem,
            "sfz_file": sfz["relative_path"], "track_role": "", "category": "",
            "sample_count": len(zones), "zone_count": len(zones), "keys": len({zone["root_midi_note"] for zone in zones}),
            "velocity_layers": len({(zone["velocity_low"], zone["velocity_high"]) for zone in zones}), "round_robin": max((zone["round_robin_index"] for zone in zones), default=1),
            "range": {"low": min(zone["low_midi_note"] for zone in zones), "high": max(zone["high_midi_note"] for zone in zones)}, "warnings": warnings, "zones": zones,
        })
        all_warnings.extend(f"{sfz['file_name']}: {warning}" for warning in warnings)
    if not instruments:
        raise ValueError("没有从 VSCO 文件夹中的 SFZ 解析出可关联的音频采样。")
    job["status"] = "pending"
    job["preview"] = {"instrument_name": "VSCO2 Library", "source": "vsco_library", "format": "VSCO Library", "sample_count": sum(item["sample_count"] for item in instruments), "zone_count": sum(item["zone_count"] for item in instruments), "keys": sum(item["keys"] for item in instruments), "velocity_layers": max(item["velocity_layers"] for item in instruments), "round_robin": max(item["round_robin"] for item in instruments), "range": {"low": min(item["range"]["low"] for item in instruments), "high": max(item["range"]["high"] for item in instruments)}, "warnings": all_warnings, "instruments": instruments, "zones": []}
    save_job(job)
    return job


def parse_mappingchart(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    mappings: list[dict[str, Any]] = []
    warnings: list[str] = []
    for line_number, raw_line in enumerate(text.replace("\ufeff", "").splitlines(), start=1):
        line = re.sub(r"\s+#.*$", "", raw_line.split("//", 1)[0]).strip()
        if not line or line.lower().startswith(("sample name", "sample\t", "filename")):
            continue
        index_match = MAPPING_CHART_INDEX.match(line)
        match = MAPPING_CHART_LINE.match(line)
        if index_match:
            value = index_match.group("key")
            root = midi_value(value, 60) if value.isdigit() else root_note_from_file_name(f"note_{value}.wav")
            mappings.append({"index": index_match.group("index").zfill(3), "root_midi_note": root, "line": line_number})
        elif match:
            value = match.group("key")
            root = midi_value(value, 60) if value.isdigit() else root_note_from_file_name(f"note_{value}.wav")
            mappings.append({"sample": match.group("sample").strip().replace("\\", "/"), "root_midi_note": root, "line": line_number})
        else:
            if any(extension in line.lower() for extension in (".wav", ".aif", ".flac")):
                warnings.append(f"第 {line_number} 行无法识别：{raw_line.strip()}")
            continue
    return mappings, warnings


def filename_metadata(file_name: str) -> dict[str, Any]:
    stem = Path(file_name).stem
    dynamic = DYNAMIC_RE.search(stem)
    round_robin = ROUND_ROBIN_RE.search(stem)
    return {
        "velocity_layer": int(dynamic.group(1)) if dynamic else 1,
        "round_robin_index": int(round_robin.group(1)) if round_robin else 1,
        "articulation": "sustain",
    }


def mapping_index_from_file_name(file_name: str) -> str | None:
    match = re.search(r"(?:^|[_\-.])(\d{1,4})$", Path(file_name).stem)
    return match.group(1).zfill(3) if match else None


def velocity_ranges(layers: set[int]) -> dict[int, tuple[int, int]]:
    ordered = sorted(layers) or [1]
    if len(ordered) == 1:
        return {ordered[0]: (1, 127)}
    if len(ordered) == 3:
        return {ordered[0]: (1, 40), ordered[1]: (41, 90), ordered[2]: (91, 127)}
    result: dict[int, tuple[int, int]] = {}
    for index, layer in enumerate(ordered):
        low = 1 if index == 0 else int(index * 127 / len(ordered)) + 1
        high = 127 if index == len(ordered) - 1 else int((index + 1) * 127 / len(ordered))
        result[layer] = (low, high)
    return result


def midi_value(value: Any, fallback: int) -> int:
    try:
        return max(0, min(127, int(float(value))))
    except (TypeError, ValueError):
        return fallback


def auto_ranges(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(items, key=lambda item: (int(item["root_midi_note"]), item["file_name"]))
    roots = sorted({int(item["root_midi_note"]) for item in ordered})
    ranges: dict[int, tuple[int, int]] = {}
    for index, root in enumerate(roots):
        previous = roots[index - 1] if index else None
        following = roots[index + 1] if index + 1 < len(roots) else None
        low = root - (following - root) if previous is None and following is not None else (previous + root + 1) // 2 if previous is not None else 0
        high = root + (root - previous) if following is None and previous is not None else (root + following) // 2 - 1 if following is not None else 127
        ranges[root] = (max(0, min(root, low)), min(127, max(root, high)))
    for item in ordered:
        item["low_midi_note"], item["high_midi_note"] = ranges[int(item["root_midi_note"])]
    return ordered


def _audio_metadata(path: Path) -> dict[str, Any]:
    if path.suffix.lower() != ".wav":
        return {"sample_rate": None, "bit_depth": None, "channels": None, "duration_ms": 0, "warning": "导入时会转换为 WAV；预览阶段暂不读取该格式的详细元数据。"}
    info = analyze_audio_file(path)
    return {"sample_rate": info.get("sample_rate"), "bit_depth": info.get("bit_depth"), "channels": info.get("channels"), "duration_ms": int(float(info.get("duration_seconds") or 0) * 1000)}


def analyze_mappingchart_job(job: dict[str, Any]) -> dict[str, Any]:
    folder = JOB_DIR / job["id"]
    files = job.get("files", [])
    mapping_file = next((item for item in files if item.get("file_name", "").lower() == "mappingchart.txt"), None)
    if not mapping_file:
        raise ValueError("未找到 MappingChart.txt。")
    mappings, warnings = parse_mappingchart((folder / mapping_file["relative_path"]).read_text(encoding="utf-8", errors="replace"))
    by_relative = {str(item["relative_path"]).lower(): item for item in files}
    by_name = {str(item["file_name"]).lower(): item for item in files}
    zones: list[dict[str, Any]] = []
    indexed_audio: dict[str, list[dict[str, Any]]] = {}
    for entry in files:
        if entry.get("extension") in AUDIO_EXTENSIONS:
            index = mapping_index_from_file_name(entry["file_name"])
            if index:
                indexed_audio.setdefault(index, []).append(entry)
    used_paths: set[str] = set()
    for mapping in mappings:
        sample_ref = mapping.get("sample")
        if sample_ref:
            entries = [by_relative.get(sample_ref.lower()) or by_name.get(Path(sample_ref).name.lower())]
            missing_name = sample_ref
        else:
            entries = indexed_audio.get(str(mapping.get("index") or ""), [])
            missing_name = f"编号 {mapping.get('index', '')}"
        entries = [entry for entry in entries if entry and entry.get("extension") in AUDIO_EXTENSIONS]
        if not entries:
            warnings.append(f"MappingChart 第 {mapping['line']} 行引用的采样不存在：{missing_name}")
            continue
        for entry in entries:
            if entry["relative_path"] in used_paths:
                continue
            used_paths.add(entry["relative_path"])
            metadata = filename_metadata(entry["file_name"])
            path = folder / entry["relative_path"]
            zones.append({
                "file_name": entry["file_name"], "relative_path": entry["relative_path"], "root_midi_note": mapping["root_midi_note"],
                "low_midi_note": mapping["root_midi_note"], "high_midi_note": mapping["root_midi_note"],
                "velocity_low": 1, "velocity_high": 127, "round_robin_group": "1", **metadata, **_audio_metadata(path),
            })
    if not zones:
        raise ValueError("MappingChart 中没有找到可用的音频采样。")
    ranges = velocity_ranges({int(zone["velocity_layer"]) for zone in zones})
    for zone in zones:
        zone["velocity_low"], zone["velocity_high"] = ranges[int(zone["velocity_layer"])]
    zones = auto_ranges(zones)
    name_source = Path(mapping_file["relative_path"]).parent.name or Path(job["source_path"]).name
    if name_source in {"", job["id"]}:
        name_source = Path(zones[0]["file_name"]).stem.split("_")[0]
    rr_per_key: dict[tuple[int, int], set[int]] = {}
    for zone in zones:
        rr_per_key.setdefault((int(zone["root_midi_note"]), int(zone["velocity_layer"])), set()).add(int(zone["round_robin_index"]))
    job["preview"] = {
        "instrument_name": name_source.replace("_", " ").strip() or "Imported Instrument", "source": "mappingchart", "format": "MappingChart",
        "mapping_file": mapping_file["relative_path"], "sample_count": len(zones), "zone_count": len(zones),
        "keys": len({int(item["root_midi_note"]) for item in zones}), "velocity_layers": len(ranges),
        "round_robin": max((len(values) for values in rr_per_key.values()), default=1),
        "range": {"low": min(item["low_midi_note"] for item in zones), "high": max(item["high_midi_note"] for item in zones)},
        "warnings": warnings, "zones": zones,
    }
    return job


def analyze_job(job_id: str) -> dict[str, Any]:
    job = job_by_id(job_id)
    if not job:
        raise ValueError("导入任务不存在。")
    folder = JOB_DIR / job_id
    files = job.get("files", [])
    if job.get("source_type") == "mappingchart":
        try:
            job = analyze_mappingchart_job(job)
        except Exception:
            job["status"] = "failed"
            job["error_count"] = 1
            save_job(job)
            raise
        job["status"] = "pending"
        save_job(job)
        return job
    sfz_file = next((item for item in files if item.get("extension") == ".sfz"), None)
    zones: list[dict[str, Any]] = []
    if sfz_file:
        sfz_path = folder / sfz_file["relative_path"]
        regions = parse_sfz(sfz_path.read_text(encoding="utf-8", errors="replace"))
        by_name = {str(item["relative_path"]).lower(): item for item in files}
        by_basename = {str(item["file_name"]).lower(): item for item in files}
        for region in regions:
            sample_ref = str(region.get("sample", "")).replace("\\", "/")
            entry = by_name.get(sample_ref.lower()) or by_basename.get(Path(sample_ref).name.lower())
            if not entry or entry.get("extension") not in AUDIO_EXTENSIONS:
                continue
            path = folder / entry["relative_path"]
            root = midi_value(region.get("pitch_keycenter"), root_note_from_file_name(entry["file_name"]))
            zones.append({"file_name": entry["file_name"], "relative_path": entry["relative_path"], "root_midi_note": root, "low_midi_note": midi_value(region.get("lokey"), root), "high_midi_note": midi_value(region.get("hikey"), root), "velocity_low": midi_value(region.get("lovel"), 1), "velocity_high": midi_value(region.get("hivel"), 127), **_audio_metadata(path)})
    else:
        for entry in files:
            if entry.get("extension") not in AUDIO_EXTENSIONS:
                continue
            path = folder / entry["relative_path"]
            root = root_note_from_file_name(entry["file_name"])
            zones.append({"file_name": entry["file_name"], "relative_path": entry["relative_path"], "root_midi_note": root, "low_midi_note": root, "high_midi_note": root, "velocity_low": 1, "velocity_high": 127, **_audio_metadata(path)})
        zones = auto_ranges(zones)
    if not zones:
        job["status"] = "failed"
        job["error_count"] = 1
        save_job(job)
        raise ValueError("未找到可导入的音频采样或有效 SFZ Region。")
    name_source = Path(sfz_file["file_name"]).stem if sfz_file else Path(zones[0]["file_name"]).stem.split("_")[0]
    job["status"] = "pending"
    job["preview"] = {"instrument_name": name_source.replace("_", " ").strip() or "Imported Instrument", "source": "sfz" if sfz_file else "folder", "format": "SFZ" if sfz_file else "WAV", "sample_count": len(zones), "zone_count": len(zones), "keys": len({int(item["root_midi_note"]) for item in zones}), "velocity_layers": len({(item["velocity_low"], item["velocity_high"]) for item in zones}), "round_robin": 1, "range": {"low": min(item["low_midi_note"] for item in zones), "high": max(item["high_midi_note"] for item in zones)}, "warnings": [], "zones": zones}
    save_job(job)
    return job


def create_instrument(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = analyze_job(job_id)
    preview = job["preview"]
    role = str(payload.get("track_role") or "foundation")
    role = role if role in TRACK_ROLES else "foundation"
    instrument = blank_instrument(role)
    instrument["name"] = str(payload.get("name") or preview["instrument_name"]).strip() or "Imported Instrument"
    category = str(payload.get("category") or ("piano" if role == "foundation" else "electric_bass"))
    instrument["category"] = category if category in CATEGORIES else "other"
    instrument["priority"] = int(payload.get("priority") or 100)
    source_type = "mappingchart" if preview.get("source") == "mappingchart" else "sfz_import" if preview["format"] == "SFZ" else "folder_import"
    if source_type == "mappingchart":
        # VSCO2-style libraries are mastered quietly; keep their natural
        # dynamic layers while compensating the shared Foundation render gain.
        instrument["playback"]["gain_db"] = 12.0
    instrument["source_info"] = {"type": source_type, "library": str(payload.get("library") or instrument["name"]), "license": str(payload.get("license") or ""), "author": str(payload.get("author") or ""), "url": str(payload.get("url") or ""), "original_folder": job["source_path"], "mapping_file": preview.get("mapping_file", "")}
    destination = ROOT / "instruments" / "files" / safe_name(instrument["id"])
    destination.mkdir(parents=True, exist_ok=True)
    for zone_data in preview["zones"]:
        source = (JOB_DIR / job_id / zone_data["relative_path"]).resolve()
        converted: Path | None = None
        if source.suffix.lower() != ".wav":
            try:
                converted = convert_to_wav_if_needed(source)
                source = converted
            except Exception as exc:
                raise ValueError(f"无法将 {zone_data['file_name']} 转换为 WAV：{exc}") from exc
        stored_name = f"{safe_name(Path(zone_data['file_name']).stem)}_{uuid.uuid4().hex[:8]}.wav"
        target = destination / stored_name
        try:
            shutil.copy2(source, target)
        finally:
            if converted and converted != (JOB_DIR / job_id / zone_data["relative_path"]):
                converted.unlink(missing_ok=True)
        zone = normalize_zone({"instrument_id": instrument["id"], "name": Path(zone_data["file_name"]).stem, "file_name": zone_data["file_name"], "file_url": f"/instruments/files/{safe_name(instrument['id'])}/{stored_name}", "mime_type": "audio/wav", "file_size": target.stat().st_size, "sample_rate": zone_data.get("sample_rate"), "bit_depth": zone_data.get("bit_depth"), "channels": zone_data.get("channels"), "duration_ms": zone_data.get("duration_ms", 0), "root_midi_note": zone_data["root_midi_note"], "note_range": {"low": zone_data["low_midi_note"], "high": zone_data["high_midi_note"]}, "velocity_range": {"low": zone_data["velocity_low"], "high": zone_data["velocity_high"]}, "gain_db": zone_data.get("gain_db", 0), "round_robin_group": zone_data.get("round_robin_group", ""), "round_robin_index": zone_data.get("round_robin_index", 1), "velocity_layer": zone_data.get("velocity_layer", 1), "articulation": zone_data.get("articulation", "sustain"), "source_library": str(payload.get("library") or instrument["name"]), "enabled": True}, instrument["id"])
        instrument["sample_zones"].append(zone)
    if not instrument["sample_zones"]:
        raise ValueError("第一版只能将 WAV Sample 创建为可播放乐器。")
    created = upsert_instrument(instrument)
    sources = _read(SOURCE_DB, {"sources": []})
    source = {"id": f"source_{uuid.uuid4().hex[:10]}", "name": instrument["source_info"]["library"], "type": instrument["source_info"]["type"], "license": instrument["source_info"]["license"], "author": instrument["source_info"]["author"], "url": instrument["source_info"]["url"], "created_at": now()}
    _write(SOURCE_DB, {"sources": [*sources.get("sources", []), source]})
    job.update({"status": "completed", "processed_files": len(instrument["sample_zones"]), "instrument_id": created["id"], "created_instruments": [{"id": created["id"], "name": created["name"]}], "completed_at": now()})
    save_job(job)
    return {"instrument": created, "job": job}


def create_vsco_instruments(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    job = analyze_vsco_job(job_id)
    requested = {str(item) for item in payload.get("instrument_ids", []) if str(item)}
    definitions = [item for item in job["preview"]["instruments"] if not requested or item["id"] in requested]
    if not definitions:
        raise ValueError("没有选择要导入的 VSCO 乐器。")
    created: list[dict[str, Any]] = []
    library = str(payload.get("library") or "VSCO2")
    for definition in definitions:
        role = str(payload.get("track_role") or "")
        if role not in TRACK_ROLES:
            raise ValueError("请为 VSCO 乐器选择轨道。")
        instrument = blank_instrument(role)
        instrument["name"] = str(payload.get("name") or definition["name"]) if len(definitions) == 1 else str(definition["name"])
        category = str(payload.get("category") or "")
        instrument["category"] = category if category in CATEGORIES else ""
        instrument["enabled"] = bool(payload.get("enable_after_import", False))
        instrument["priority"] = int(payload.get("priority") or 0)
        instrument["source_info"] = {"type": "vsco_library", "library": library, "sfz_file": definition["sfz_file"], "original_folder": job["source_path"]}
        destination = ROOT / "instruments" / "files" / safe_name(instrument["id"])
        destination.mkdir(parents=True, exist_ok=True)
        for zone_data in definition["zones"]:
            source = (JOB_DIR / job_id / zone_data["relative_path"]).resolve()
            converted: Path | None = None
            if source.suffix.lower() != ".wav":
                converted = convert_to_wav_if_needed(source)
                source = converted
            stored_name = f"{safe_name(Path(zone_data['file_name']).stem)}_{uuid.uuid4().hex[:8]}.wav"
            target = destination / stored_name
            try:
                shutil.copy2(source, target)
            finally:
                if converted:
                    converted.unlink(missing_ok=True)
            instrument["sample_zones"].append(normalize_zone({"instrument_id": instrument["id"], "name": Path(zone_data["file_name"]).stem, "file_name": zone_data["file_name"], "file_url": f"/instruments/files/{safe_name(instrument['id'])}/{stored_name}", "mime_type": "audio/wav", "file_size": target.stat().st_size, "sample_rate": zone_data.get("sample_rate"), "channels": zone_data.get("channels"), "duration_ms": zone_data.get("duration_ms", 0), "root_midi_note": zone_data["root_midi_note"], "note_range": {"low": zone_data["low_midi_note"], "high": zone_data["high_midi_note"]}, "velocity_range": {"low": zone_data["velocity_low"], "high": zone_data["velocity_high"]}, "gain_db": zone_data.get("gain_db", 0), "round_robin_group": zone_data.get("round_robin_group", ""), "round_robin_index": zone_data.get("round_robin_index", 1), "velocity_layer": zone_data.get("velocity_layer", 1), "articulation": zone_data.get("articulation", "sustain"), "source_library": library, "enabled": True}, instrument["id"]))
        created.append(upsert_instrument(instrument))
    job.update({"status": "completed", "processed_files": len(job.get("files", [])), "instrument_ids": [item["id"] for item in created], "created_instruments": [{"id": item["id"], "name": item["name"]} for item in created], "completed_at": now()})
    save_job(job)
    return {"instruments": created, "job": job}


def repair_vsco_instrument_gain(instrument_id: str) -> dict[str, Any]:
    instrument = get_instrument(instrument_id)
    if not instrument or instrument.get("source_info", {}).get("type") != "vsco_library":
        raise ValueError("该乐器不是可修复的 VSCO 乐器。")
    source_info = instrument["source_info"]
    sfz_path = ROOT / str(source_info.get("original_folder", "")) / str(source_info.get("sfz_file", ""))
    if not sfz_path.is_file():
        raise ValueError("未找到此 VSCO 乐器的原始 SFZ 文件。")
    regions = parse_sfz(sfz_path.read_text(encoding="utf-8", errors="replace"))
    volume_by_zone = {
        (Path(region.get("sample", "")).name.lower(), max(1, midi_value(region.get("lovel"), 1)), max(1, midi_value(region.get("hivel"), 127))): sfz_volume_db(region.get("volume"))
        for region in regions
        if region.get("sample")
    }
    repaired = 0
    for zone in instrument.get("sample_zones", []):
        velocity = zone.get("velocity_range", {})
        key = (str(zone.get("file_name", "")).lower(), int(velocity.get("low", 1)), int(velocity.get("high", 127)))
        if key in volume_by_zone:
            zone["gain_db"] = volume_by_zone[key]
            repaired += 1
    if not repaired:
        raise ValueError("原始 SFZ 中没有找到可对应的 Sample Zone。")
    result = upsert_instrument(instrument)
    return {"instrument": result, "repaired_zones": repaired}


def export_jobs() -> dict[str, Any]:
    jobs = []
    for job in _jobs():
        item = {**job}
        item["created_instruments"] = created_instruments(item)
        jobs.append(item)
    jobs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"jobs": jobs}


def preview_audio_path(job_id: str, index: int) -> Path | None:
    job = job_by_id(job_id)
    zones = (job or {}).get("preview", {}).get("zones", [])
    if not isinstance(index, int) or index < 0 or index >= len(zones):
        return None
    path = (JOB_DIR / job_id / str(zones[index].get("relative_path", ""))).resolve()
    root = (JOB_DIR / job_id).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None
