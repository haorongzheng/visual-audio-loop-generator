from __future__ import annotations

import json
import mimetypes
import random
import re
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .audio_renderer import generate_audio_loop
from .effects_config import load_effects, save_effects
from .drum_patterns import duplicate_drum_pattern, export_drum_patterns, reset_drum_pattern, save_drum_patterns, upsert_drum_pattern
from .foundation_midi_patterns import (
    delete_foundation_pattern, duplicate_foundation_pattern, export_foundation_patterns,
    get_foundation_pattern, normalize_register, save_staged_pattern, stage_upload,
    update_foundation_pattern,
)
from .foundation_performance import MODE_OPTIONS, load_performance_modes, reset_performance_modes, save_performance_modes
from .bass_grooves import MODE_IDS as BASS_GROOVE_MODE_IDS, load_bass_grooves, reset_bass_grooves, save_bass_grooves
from .guitar_performance import MODE_IDS as GUITAR_MODE_IDS, guitar_events, load_guitar_performance_modes, reset_guitar_performance_modes, save_guitar_performance_modes
from .string_performance import MODE_IDS as STRING_PERFORMANCE_MODE_IDS, load_string_performance_modes, reset_string_performance_modes, save_string_performance_modes
from .generator import expanded_chords, generate_loop, resolved_payload
from .harmony_admin import delete_harmony_rule, export_harmony_admin, reset_harmony_rule, save_harmony_rules, upsert_harmony_rule
from .instrument_library import auto_map, delete_instrument, delete_zone, duplicate_instrument, export_instruments, get_instrument, match_instrument, note_to_midi, save_zone, select_zone, upsert_instrument, upload_zone
from .music_state_schema import ImageAnnotation, coerce_annotation, standard_json as schema_standard_json
from .mixer_config import load_mixer, save_mixer
from .sample_library import load_samples, save_samples, upload_sample_file, upsert_sample
from .sample_import import analyze_job as analyze_sample_import_job, analyze_vsco_job, append_vsco_file, create_instrument as create_imported_instrument, create_vsco_instruments, export_jobs as export_sample_import_jobs, job_by_id as sample_import_job_by_id, preview_audio_path as sample_import_preview_audio_path, repair_vsco_instrument_gain, stage_upload as stage_sample_import_upload, start_vsco_import
from .sound_sources import export_sound_sources, save_sound_db, upload_sound_samples, upsert_sound_sources


ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "web"
OUTPUT_DIR = ROOT / "output_midi"


class LoopRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self.send_file(STATIC_DIR / "index.html")
            return
        if parsed.path in {"/admin", "/admin/", "/admin/index.html"}:
            self.send_file(STATIC_DIR / "samples_admin.html")
            return
        if parsed.path in {"/admin/samples", "/admin/sound-sources", "/admin/drum-sources"}:
            self.send_file(STATIC_DIR / "sound_sources_admin.html")
            return
        if parsed.path == "/admin/drum-patterns":
            self.send_file(STATIC_DIR / "drum_patterns_admin.html")
            return
        if parsed.path == "/admin/instruments":
            self.send_file(STATIC_DIR / "instrument_library_admin.html")
            return
        if parsed.path == "/admin/sample-import":
            self.send_file(STATIC_DIR / "sample_import.html")
            return
        if parsed.path == "/admin/foundation-patterns":
            self.send_file(STATIC_DIR / "foundation_patterns_admin.html")
            return
        if parsed.path == "/admin/harmony":
            self.send_file(STATIC_DIR / "harmony_admin.html")
            return
        if parsed.path == "/admin/foundation-performance-modes":
            self.send_file(STATIC_DIR / "foundation_performance_modes_admin.html")
            return
        if parsed.path == "/admin/bass-groove-modes":
            self.send_file(STATIC_DIR / "bass_groove_modes_admin.html")
            return
        if parsed.path == "/admin/guitar-performance-modes":
            self.send_file(STATIC_DIR / "guitar_performance_modes_admin.html")
            return
        if parsed.path == "/admin/string-performance":
            self.send_file(STATIC_DIR / "string_performance_admin.html")
            return
        if parsed.path == "/admin/styles.css":
            self.send_file(STATIC_DIR / "styles.css")
            return
        if parsed.path == "/admin/samples_admin.js":
            self.send_file(STATIC_DIR / "samples_admin.js")
            return
        if parsed.path == "/admin/drum_sources_admin.js":
            self.send_file(STATIC_DIR / "drum_sources_admin.js")
            return
        if parsed.path == "/admin/sound_sources_admin.js":
            self.send_file(STATIC_DIR / "sound_sources_admin.js")
            return
        if parsed.path == "/admin/drum_patterns_admin.js":
            self.send_file(STATIC_DIR / "drum_patterns_admin.js")
            return
        if parsed.path == "/admin/instrument_library_admin.js":
            self.send_file(STATIC_DIR / "instrument_library_admin.js")
            return
        if parsed.path == "/admin/sample_import.js":
            self.send_file(STATIC_DIR / "sample_import.js")
            return
        if parsed.path == "/admin/foundation_patterns_admin.js":
            self.send_file(STATIC_DIR / "foundation_patterns_admin.js")
            return
        if parsed.path == "/admin/harmony_admin.js":
            self.send_file(STATIC_DIR / "harmony_admin.js")
            return
        if parsed.path == "/admin/bass_groove_modes_admin.js":
            self.send_file(STATIC_DIR / "bass_groove_modes_admin.js")
            return
        if parsed.path == "/admin/guitar_performance_modes_admin.js":
            self.send_file(STATIC_DIR / "guitar_performance_modes_admin.js")
            return
        if parsed.path == "/admin/string_performance_admin.js":
            self.send_file(STATIC_DIR / "string_performance_admin.js")
            return
        if parsed.path == "/api/foundation-performance-modes":
            self.send_json({"ok": True, "modes": list(load_performance_modes().values())})
            return
        if parsed.path == "/api/bass-groove-modes":
            self.send_json({"ok": True, "modes": list(load_bass_grooves().values())})
            return
        if parsed.path == "/api/guitar-performance-modes":
            self.send_json({"ok": True, "modes": list(load_guitar_performance_modes().values())})
            return
        if parsed.path == "/api/string-performance-modes":
            self.send_json({"ok": True, "modes": list(load_string_performance_modes().values())})
            return
        if parsed.path == "/api/harmony":
            self.send_json({"ok": True, **export_harmony_admin()})
            return
        if parsed.path == "/api/samples":
            self.send_json({"ok": True, "samples": load_samples()})
            return
        if parsed.path == "/api/sound-sources":
            self.send_json({"ok": True, **export_sound_sources()})
            return
        if parsed.path == "/api/drum-patterns":
            self.send_json({"ok": True, **export_drum_patterns()})
            return
        if parsed.path == "/api/instruments":
            self.send_json({"ok": True, **export_instruments()})
            return
        if parsed.path == "/api/sample-import/jobs":
            self.send_json({"ok": True, **export_sample_import_jobs()})
            return
        if parsed.path.startswith("/api/sample-import/") and parsed.path.endswith("/status"):
            parts = parsed.path.split("/")
            job = sample_import_job_by_id(parts[3] if len(parts) >= 5 else "")
            if job:
                self.send_json({"ok": True, "job": job})
            else:
                self.send_json({"ok": False, "error": "Import job not found."}, status=404)
            return
        if parsed.path.startswith("/api/sample-import/jobs/") and "/audio/" in parsed.path:
            parts = parsed.path.split("/")
            try:
                job_id = parts[4]
                audio_index = int(parts[6])
                audio_path = sample_import_preview_audio_path(job_id, audio_index)
                if not audio_path:
                    raise ValueError("Preview audio not found.")
                self.send_file(audio_path)
            except (IndexError, ValueError):
                self.send_json({"error": "Not found"}, status=404)
            return
        if parsed.path == "/api/foundation-patterns":
            self.send_json({"ok": True, **export_foundation_patterns()})
            return
        if parsed.path == "/api/mixer":
            self.send_json({"ok": True, "mixer": load_mixer()})
            return
        if parsed.path == "/api/effects":
            self.send_json({"ok": True, "effects": load_effects()})
            return
        if parsed.path.startswith("/api/instruments/") and parsed.path.endswith("/audio"):
            parts = parsed.path.split("/")
            instrument = get_instrument(parts[3]) if len(parts) >= 7 else None
            zone = next((item for item in (instrument or {}).get("sample_zones", []) if item["id"] == parts[5]), None)
            if zone:
                self.send_file(ROOT / str(zone["file_url"]).lstrip("/"))
            else:
                self.send_json({"error": "Not found"}, status=404)
            return
        if parsed.path.startswith("/api/instruments/"):
            instrument_id = parsed.path.split("/")[3] if len(parsed.path.split("/")) > 3 else ""
            instrument = get_instrument(instrument_id)
            if instrument:
                self.send_json({"ok": True, "instrument": instrument})
            else:
                self.send_json({"ok": False, "error": "Instrument not found."}, status=404)
            return
        if parsed.path.startswith("/api/foundation-patterns/"):
            pattern_id = parsed.path.split("/")[3] if len(parsed.path.split("/")) > 3 else ""
            pattern = get_foundation_pattern(pattern_id)
            if pattern:
                self.send_json({"ok": True, "pattern": pattern})
            else:
                self.send_json({"ok": False, "error": "Foundation Pattern not found."}, status=404)
            return
        if parsed.path.startswith("/output_midi/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/output_audio/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/samples/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/drums/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/sound_sources/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/instruments/"):
            self.send_file(ROOT / parsed.path.lstrip("/"))
            return
        candidate = STATIC_DIR / parsed.path.lstrip("/")
        if candidate.is_file():
            self.send_file(candidate)
            return
        self.send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/samples/upload":
            self.handle_sample_upload()
            return
        if path == "/api/samples/upsert":
            self.handle_sample_upsert()
            return
        if path == "/api/samples/delete":
            self.handle_sample_delete()
            return
        if path == "/api/sound-sources/save":
            self.handle_sound_sources_save()
            return
        if path == "/api/sound-sources/upload":
            self.handle_sound_sources_upload()
            return
        if path == "/api/sound-sources/import":
            self.handle_sound_sources_import()
            return
        if path == "/api/harmony/save":
            self.handle_harmony_save()
            return
        if path == "/api/harmony/delete":
            self.handle_harmony_delete()
            return
        if path == "/api/harmony/import":
            self.handle_harmony_import()
            return
        if path == "/api/harmony/reset":
            self.handle_harmony_reset()
            return
        if path == "/api/drum-patterns/save":
            self.handle_drum_pattern_save()
            return
        if path == "/api/drum-patterns/import":
            self.handle_drum_patterns_import()
            return
        if path == "/api/drum-patterns/reset":
            self.handle_drum_pattern_reset()
            return
        if path == "/api/drum-patterns/duplicate":
            self.handle_drum_pattern_duplicate()
            return
        if path == "/api/instruments":
            self.handle_instrument_create()
            return
        if path == "/api/sample-import/upload":
            self.handle_sample_import_upload()
            return
        if path in {"/api/sample-import/analyze", "/api/sample-import/sfz-parse"}:
            self.handle_sample_import_analyze()
            return
        if path == "/api/sample-import/mappingchart/analyze":
            self.handle_sample_import_analyze()
            return
        if path == "/api/sample-import/create-instrument":
            self.handle_sample_import_create_instrument()
            return
        if path == "/api/sample-import/mappingchart/import":
            self.handle_sample_import_create_instrument()
            return
        if path == "/api/sample-import/vsco/start":
            self.handle_vsco_start()
            return
        if path == "/api/sample-import/vsco/file":
            self.handle_vsco_file()
            return
        if path == "/api/sample-import/vsco/analyze":
            self.handle_vsco_analyze()
            return
        if path == "/api/sample-import/vsco/import":
            self.handle_vsco_import()
            return
        if path == "/api/instruments/match":
            self.handle_instrument_match()
            return
        if path == "/api/foundation-patterns/upload":
            self.handle_foundation_pattern_upload()
            return
        if path == "/api/foundation-patterns/match":
            self.handle_foundation_pattern_match()
            return
        if path == "/api/foundation-performance-modes/save":
            self.handle_foundation_performance_modes_save()
            return
        if path == "/api/foundation-performance-modes/reset":
            self.send_json({"ok": True, "modes": list(reset_performance_modes().values())})
            return
        if path == "/api/bass-groove-modes/save":
            self.handle_bass_groove_modes_save()
            return
        if path == "/api/bass-groove-modes/reset":
            self.send_json({"ok": True, "modes": list(reset_bass_grooves().values())})
            return
        if path == "/api/guitar-performance-modes/save":
            self.handle_guitar_performance_modes_save()
            return
        if path == "/api/guitar-performance-modes/reset":
            self.send_json({"ok": True, "modes": list(reset_guitar_performance_modes().values())})
            return
        if path == "/api/guitar-performance-modes/preview":
            self.handle_guitar_performance_preview()
            return
        if path == "/api/string-performance-modes/save":
            self.handle_string_performance_modes_save()
            return
        if path == "/api/string-performance-modes/reset":
            self.send_json({"ok": True, "modes": list(reset_string_performance_modes().values())})
            return
        if path.startswith("/api/foundation-patterns/"):
            self.handle_foundation_pattern_post(path)
            return
        if path == "/api/mixer/save":
            self.handle_mixer_save()
            return
        if path == "/api/effects/save":
            self.handle_effects_save()
            return
        if path.startswith("/api/instruments/"):
            self.handle_instrument_post(path)
            return
        if path == "/api/resolve":
            self.handle_resolve()
            return
        if path != "/api/generate":
            self.send_json({"error": "Not found"}, status=404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            data = json.loads(body or "{}")
            annotation = annotation_from_payload(data)
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            audio_dir = ROOT / "output_audio"
            audio_dir.mkdir(parents=True, exist_ok=True)
            output_path = OUTPUT_DIR / f"{safe_output_name(annotation.image_id)}.mid"
            wav_path = audio_dir / f"{safe_output_name(annotation.image_id)}.wav"
            mp3_path = audio_dir / f"{safe_output_name(annotation.image_id)}.mp3"
            generation_options = {**resolve_foundation_pattern_options(data), **resolve_bass_groove_options(data), **resolve_guitar_performance_options(data), **resolve_string_performance_options(data)}
            instrument_overrides = resolve_instrument_overrides(data)
            result = generate_loop(annotation, output_path, instrument_overrides=instrument_overrides, **generation_options)
            render_tracks, render_sample_overlays = resolve_render_options(data)
            effects_settings = resolve_effects_settings(data)
            render_result = generate_audio_loop(
                annotation, wav_path, mp3_path, render_tracks, render_sample_overlays, instrument_overrides,
                resolve_mixer_settings(data), effects_settings, **generation_options,
            )
            result.setdefault("audio_render", {})["effects"] = effects_settings
            result.setdefault("audio_render_config", {})["effects"] = effects_settings
            if render_result.get("instruments"):
                result.setdefault("audio_render", {})["instruments"] = render_result["instruments"]
                result.setdefault("audio_render_config", {})["instruments"] = render_result["instruments"]
            if not render_sample_overlays:
                clear_sample_overlays(result)
            rendered_tracks = sorted(render_tracks) if render_tracks is not None else result["tracks"]
            if render_sample_overlays:
                rendered_tracks = [*rendered_tracks, "Sample"]
            mp3_available = bool(render_result.get("mp3_path"))
            wav_url = f"/output_audio/{wav_path.name}"
            mp3_url = f"/output_audio/{mp3_path.name}" if mp3_available else None
            audio_format = "mp3" if mp3_available else "wav"
            result.setdefault("audio_render", {})["format"] = audio_format
            result.setdefault("audio_render_config", {})["output"] = audio_format
            self.send_json(
                {
                    "ok": True,
                    "midi_url": f"/output_midi/{output_path.name}",
                    "mp3_url": mp3_url,
                    "wav_url": wav_url,
                    "audio_url": mp3_url or wav_url,
                    "audio_format": audio_format,
                    "audio_warning": render_result.get("mp3_error"),
                    "midi_path": str(output_path),
                    "mp3_path": render_result.get("mp3_path"),
                    "render_tracks": rendered_tracks,
                    "resolved": result,
                    "input_json": standard_json(annotation),
                }
            )
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        parts = path.split("/")
        try:
            if len(parts) == 4 and parts[:3] == ["", "api", "instruments"]:
                instrument = upsert_instrument({**self.read_json_body(), "id": parts[3]})
                self.send_json({"ok": True, "instrument": instrument, **export_instruments()})
                return
            if len(parts) == 6 and parts[4] == "zones":
                zone = save_zone(parts[3], parts[5], self.read_json_body())
                self.send_json({"ok": True, "zone": zone, "instrument": get_instrument(parts[3])})
                return
            if len(parts) == 4 and parts[:3] == ["", "api", "foundation-patterns"]:
                pattern = update_foundation_pattern(parts[3], self.read_json_body())
                self.send_json({"ok": True, "pattern": pattern, **export_foundation_patterns()})
                return
            self.send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        parts = path.split("/")
        try:
            if len(parts) == 4 and parts[:3] == ["", "api", "instruments"]:
                self.send_json({"ok": True, "instruments": delete_instrument(parts[3])})
                return
            if len(parts) == 6 and parts[4] == "zones":
                self.send_json({"ok": True, "instrument": delete_zone(parts[3], parts[5])})
                return
            if len(parts) == 4 and parts[:3] == ["", "api", "foundation-patterns"]:
                self.send_json({"ok": True, "patterns": delete_foundation_pattern(parts[3])})
                return
            self.send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            content_type = self.headers.get("Content-Type", "")
            fields, files = parse_multipart(body, content_type)
            if "file" not in files:
                raise ValueError("Missing upload file.")
            file_name, data = files["file"]
            sample = upload_sample_file(file_name, data)
            if fields.get("sample"):
                edits = json.loads(fields["sample"])
                edits["sample_id"] = sample["sample_id"]
                edits["file_url"] = sample["file_url"]
                edits["file_name"] = sample.get("file_name", "")
                edits["file_size"] = sample.get("file_size", 0)
                sample = upsert_sample({**sample, **edits})
            self.send_json({"ok": True, "sample": sample, "samples": load_samples()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_instrument_create(self) -> None:
        try:
            instrument = upsert_instrument(self.read_json_body())
            self.send_json({"ok": True, "instrument": instrument, **export_instruments()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_import_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            fields, files = parse_multipart_multi(self.rfile.read(length), self.headers.get("Content-Type", ""))
            uploads = files.get("files") or files.get("file") or []
            job = stage_sample_import_upload(str(fields.get("source_type") or "folder"), uploads)
            self.send_json({"ok": True, "job": job})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_import_analyze(self) -> None:
        try:
            data = self.read_json_body()
            job = analyze_sample_import_job(str(data.get("job_id") or ""))
            self.send_json({"ok": True, "job": job})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_import_create_instrument(self) -> None:
        try:
            data = self.read_json_body()
            result = create_imported_instrument(str(data.get("job_id") or ""), data)
            self.send_json({"ok": True, **result, **export_instruments()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_vsco_start(self) -> None:
        try:
            self.send_json({"ok": True, "job": start_vsco_import()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_vsco_file(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            fields, files = parse_multipart_multi(self.rfile.read(length), self.headers.get("Content-Type", ""))
            upload = (files.get("file") or files.get("files") or [None])[0]
            if not upload:
                raise ValueError("缺少 VSCO 文件。")
            job = append_vsco_file(str(fields.get("job_id") or ""), upload[0], upload[1])
            self.send_json({"ok": True, "job": job})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_vsco_analyze(self) -> None:
        try:
            data = self.read_json_body()
            self.send_json({"ok": True, "job": analyze_vsco_job(str(data.get("job_id") or ""))})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_vsco_import(self) -> None:
        try:
            data = self.read_json_body()
            result = create_vsco_instruments(str(data.get("job_id") or ""), data)
            self.send_json({"ok": True, **result, **export_instruments()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_instrument_post(self, path: str) -> None:
        parts = path.split("/")
        if len(parts) < 5:
            self.send_json({"error": "Not found"}, status=404)
            return
        instrument_id, action = parts[3], parts[4]
        try:
            if action == "duplicate":
                item = duplicate_instrument(instrument_id)
                self.send_json({"ok": True, "instrument": item, **export_instruments()})
                return
            if action == "auto-map":
                item = auto_map(instrument_id)
                self.send_json({"ok": True, "instrument": item})
                return
            if action == "repair-vsco-gain":
                result = repair_vsco_instrument_gain(instrument_id)
                self.send_json({"ok": True, **result})
                return
            if action == "upload-sample":
                length = int(self.headers.get("Content-Length", "0"))
                fields, files = parse_multipart(self.rfile.read(length), self.headers.get("Content-Type", ""))
                if "file" not in files:
                    raise ValueError("Missing upload file.")
                file_name, data = files["file"]
                zone = upload_zone(instrument_id, file_name, data, fields)
                self.send_json({"ok": True, "zone": zone, "instrument": get_instrument(instrument_id)})
                return
            if action in {"preview-note", "preview-chord", "generate-test"}:
                data = self.read_json_body()
                item = get_instrument(instrument_id)
                if not item:
                    raise ValueError("Instrument not found.")
                note = note_to_midi(data.get("midi_note", data.get("root_note", 60)))
                zone, warning = select_zone(item, note, int(data.get("velocity", 90)))
                if not zone:
                    raise ValueError("Instrument has no usable sample zones.")
                rate = 2 ** ((note + int(item["playback"].get("transpose", 0)) - zone["root_midi_note"]) / 12)
                self.send_json({"ok": True, "instrument_id": item["id"], "target_midi_note": note, "zone": zone, "playback_rate": rate, "warning": warning})
                return
            self.send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_instrument_match(self) -> None:
        try:
            data = self.read_json_body()
            annotation = annotation_from_payload(data.get("state", data))
            role = str(data.get("track_role", "foundation"))
            match = match_instrument(annotation, role, int(data.get("seed", 0)), str(data.get("instrument_id") or "") or None)
            self.send_json({"ok": True, "match": match})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_mixer_save(self) -> None:
        try:
            data = self.read_json_body()
            self.send_json({"ok": True, "mixer": save_mixer(data.get("mixer", data))})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_effects_save(self) -> None:
        try:
            data = self.read_json_body()
            self.send_json({"ok": True, "effects": save_effects(data.get("effects", data))})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_foundation_performance_modes_save(self) -> None:
        try:
            data = self.read_json_body()
            modes = data.get("modes", data)
            if not isinstance(modes, list):
                raise ValueError("模式数据格式不正确。")
            self.send_json({"ok": True, "modes": list(save_performance_modes(modes).values())})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_bass_groove_modes_save(self) -> None:
        try:
            data = self.read_json_body()
            modes = data.get("modes", data)
            if not isinstance(modes, list):
                raise ValueError("Bass 模式数据格式不正确。")
            self.send_json({"ok": True, "modes": list(save_bass_grooves(modes).values())})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_guitar_performance_modes_save(self) -> None:
        try:
            data = self.read_json_body()
            modes = data.get("modes", data)
            if not isinstance(modes, list):
                raise ValueError("吉他模式数据格式不正确。")
            self.send_json({"ok": True, "modes": list(save_guitar_performance_modes(modes).values())})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_string_performance_modes_save(self) -> None:
        try:
            data = self.read_json_body()
            modes = data.get("modes", data)
            if not isinstance(modes, list):
                raise ValueError("弦乐模式数据格式不正确。")
            self.send_json({"ok": True, "modes": list(save_string_performance_modes(modes).values())})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_guitar_performance_preview(self) -> None:
        try:
            data = self.read_json_body()
            modes = load_guitar_performance_modes()
            for item in data.get("modes", []):
                if isinstance(item, dict) and str(item.get("id")) in modes:
                    modes[str(item["id"])].update(item)
            chord_symbols = data.get("chords") if isinstance(data.get("chords"), list) else ["Cmaj7", "Am7", "Fmaj7", "G7"]
            chords = expanded_chords(tuple(str(item) for item in chord_symbols[:4]), 4)
            events, manifest = guitar_events(
                chords, 4, int(data.get("velocity", 86)), str(data.get("guitar_type", "nylon")),
                str(data.get("sound_direction", "ambient")), str(data.get("energy", "流动")), str(data.get("rhythm", "flow")),
                random.Random(22), str(data.get("mode", "auto")), str(data.get("variant", "auto")), modes,
                bpm=int(data.get("bpm", 100)), roll_amount=float(data.get("guitar_roll_amount", 1)),
            )
            self.send_json({"ok": True, "events": events, "manifest": manifest})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_foundation_pattern_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            fields, files = parse_multipart(self.rfile.read(length), self.headers.get("Content-Type", ""))
            if "midi_file" not in files:
                raise ValueError("请选择 MIDI 文件。")
            file_name, data = files["midi_file"]
            self.send_json({"ok": True, **stage_upload(file_name, data)})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_foundation_pattern_match(self) -> None:
        try:
            from .foundation_midi_patterns import match_foundation_pattern
            data = self.read_json_body()
            annotation = annotation_from_payload(data.get("state", data))
            bars = 8 if int(annotation.loop_length) >= 8 else 4
            pattern, tags = match_foundation_pattern(annotation, bars, int(data.get("seed", 0)))
            self.send_json({"ok": True, "pattern": pattern, "matched_tags": tags})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_foundation_pattern_post(self, path: str) -> None:
        parts = path.split("/")
        try:
            if path == "/api/foundation-patterns/analyze-upload":
                self.handle_foundation_pattern_upload()
                return
            if len(parts) == 5 and parts[4] == "save":
                pattern = save_staged_pattern(parts[3], self.read_json_body())
                self.send_json({"ok": True, "pattern": pattern, **export_foundation_patterns()})
                return
            if len(parts) == 5 and parts[4] == "duplicate":
                self.send_json({"ok": True, "pattern": duplicate_foundation_pattern(parts[3]), **export_foundation_patterns()})
                return
            if len(parts) == 5 and parts[4] == "normalize-register":
                self.send_json({"ok": True, "pattern": normalize_register(parts[3])})
                return
            if len(parts) == 5 and parts[4] in {"preview-original", "preview-adapted"}:
                pattern = get_foundation_pattern(parts[3])
                if not pattern:
                    raise ValueError("Foundation Pattern 不存在。")
                events = pattern.get("events", [])
                target_chords = []
                if parts[4] == "preview-adapted":
                    data = self.read_json_body()
                    target_chords = [item.strip() for item in re.split(r"[,|\n]+", str(data.get("target_chords") or "")) if item.strip()]
                    source_chords = pattern.get("source_harmony", {}).get("chords", [])
                    if len(target_chords) != len(source_chords):
                        raise ValueError(f"目标和弦必须填写 {len(source_chords)} 个，每小节一个。")
                    from .generator import adapt_uploaded_pitch, parse_chord_symbol
                    source = [parse_chord_symbol(item) for item in source_chords]
                    target = [parse_chord_symbol(item) for item in target_chords]
                    events = [{**event, "note": adapt_uploaded_pitch(int(event["note"]), source[(int(event["start_tick"]) // (4 * 480)) % len(source)], target[(int(event["start_tick"]) // (4 * 480)) % len(target)])} for event in events]
                self.send_json({"ok": True, "pattern": pattern, "events": events, "target_chords": target_chords, "preview": parts[4]})
                return
            self.send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_upsert(self) -> None:
        try:
            data = self.read_json_body()
            sample = upsert_sample(data.get("sample", data))
            self.send_json({"ok": True, "sample": sample, "samples": load_samples()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sample_delete(self) -> None:
        try:
            data = self.read_json_body()
            sample_id = str(data.get("sample_id", ""))
            samples = [sample for sample in load_samples() if sample.get("sample_id") != sample_id]
            save_samples(samples)
            self.send_json({"ok": True, "samples": samples})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sound_sources_save(self) -> None:
        try:
            data = self.read_json_body()
            saved = upsert_sound_sources(data.get("sound_sources", data))
            self.send_json({"ok": True, **export_sound_sources(), "saved": saved})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sound_sources_upload(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length)
            fields, files = parse_multipart_multi(body, self.headers.get("Content-Type", ""))
            uploads = files.get("files") or files.get("file") or []
            if not uploads:
                raise ValueError("Missing upload file.")
            self.send_json({"ok": True, **upload_sound_samples(uploads, fields)})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_sound_sources_import(self) -> None:
        try:
            data = self.read_json_body()
            payload = data.get("sound_sources", data)
            if not isinstance(payload, dict):
                raise ValueError("Import JSON must be a sound source config object.")
            save_sound_db(payload)
            self.send_json({"ok": True, **export_sound_sources()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_harmony_save(self) -> None:
        try:
            data = self.read_json_body()
            rule = upsert_harmony_rule(data.get("rule", data))
            self.send_json({"ok": True, "rule": rule, **export_harmony_admin()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_harmony_delete(self) -> None:
        try:
            data = self.read_json_body()
            self.send_json({"ok": True, "harmony_rules": delete_harmony_rule(str(data.get("rule_id", ""))), "definitions": export_harmony_admin()["definitions"]})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_harmony_import(self) -> None:
        try:
            data = self.read_json_body()
            rules = data.get("harmony_rules", data.get("rules", []))
            if not isinstance(rules, list):
                raise ValueError("Import JSON must include harmony_rules array.")
            save_harmony_rules(rules)
            self.send_json({"ok": True, **export_harmony_admin()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_harmony_reset(self) -> None:
        try:
            data = self.read_json_body()
            rule = reset_harmony_rule(data.get("emotion", "欢快"), data.get("sound_direction", "electronic"), int(data.get("loop_length_bars", 4)))
            self.send_json({"ok": True, "rule": rule, **export_harmony_admin()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_resolve(self) -> None:
        try:
            data = self.read_json_body()
            annotation = annotation_from_payload(data)
            foundation_options = resolve_foundation_pattern_options(data)
            bass_options = resolve_bass_groove_options(data)
            guitar_options = resolve_guitar_performance_options(data)
            string_options = resolve_string_performance_options(data)
            resolved = resolved_payload(annotation, foundation_options["foundation_performance_mode"], **bass_options, instrument_overrides=resolve_instrument_overrides(data), **guitar_options, **string_options)
            resolved.setdefault("audio_render", {})["effects"] = resolve_effects_settings(data)
            self.send_json({"ok": True, "resolved": resolved})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_drum_pattern_save(self) -> None:
        try:
            data = self.read_json_body()
            pattern = upsert_drum_pattern(data.get("pattern", data))
            self.send_json({"ok": True, "pattern": pattern, **export_drum_patterns()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_drum_patterns_import(self) -> None:
        try:
            data = self.read_json_body()
            payload = data.get("drum_patterns", data.get("patterns", data))
            db = save_drum_patterns({"drum_patterns": payload} if isinstance(payload, list) else data)
            self.send_json({"ok": True, **db, "definitions": export_drum_patterns()["definitions"]})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_drum_pattern_reset(self) -> None:
        try:
            data = self.read_json_body()
            tags = data.get("tags", data)
            pattern = reset_drum_pattern(tags.get("sound_direction", "all"), tags.get("energy", "流动"), tags.get("rhythm", "groove"), int(data.get("loop_length_bars", 4)))
            self.send_json({"ok": True, "pattern": pattern, **export_drum_patterns()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def handle_drum_pattern_duplicate(self) -> None:
        try:
            data = self.read_json_body()
            pattern = duplicate_drum_pattern(str(data.get("pattern_id", "")), data.get("tags", {}))
            self.send_json({"ok": True, "pattern": pattern, **export_drum_patterns()})
        except Exception as exc:
            self.send_json({"ok": False, "error": str(exc)}, status=400)

    def read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        data = json.loads(body or "{}")
        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")
        return data

    def send_file(self, path: Path) -> None:
        if not path.is_file():
            self.send_json({"error": "Not found"}, status=404)
            return
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        return


def run_server(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False) -> None:
    server = ThreadingHTTPServer((host, port), LoopRequestHandler)
    url = f"http://{host}:{port}"
    print(f"Audio Loop Generator is running at {url}")
    if open_browser:
        webbrowser.open(url)
    server.serve_forever()


def annotation_from_payload(data: dict) -> ImageAnnotation:
    return coerce_annotation(data)


def standard_json(annotation: ImageAnnotation) -> dict:
    return schema_standard_json(annotation, resolved_payload(annotation))


def resolve_render_options(data: dict) -> tuple[set[str] | None, bool]:
    midi_tracks = {"Foundation", "Bass", "Drums"}
    all_tracks = {*midi_tracks, "Sample"}
    options = data.get("render_options") if isinstance(data.get("render_options"), dict) else {}
    solo_tracks = {str(track) for track in options.get("solo_tracks", []) if str(track) in all_tracks}
    muted_tracks = {str(track) for track in options.get("muted_tracks", []) if str(track) in all_tracks}
    if solo_tracks:
        return solo_tracks & midi_tracks, "Sample" in solo_tracks
    if muted_tracks:
        return midi_tracks - muted_tracks, "Sample" not in muted_tracks
    return None, True


def resolve_instrument_overrides(data: dict) -> dict[str, str]:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    overrides = options.get("instrument_overrides") if isinstance(options.get("instrument_overrides"), dict) else {}
    return {key: str(value) for key, value in overrides.items() if key in {"foundation", "bass", "Foundation", "Bass"} and value}


def resolve_mixer_settings(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    return options.get("mixer") if isinstance(options.get("mixer"), dict) else load_mixer()


def resolve_effects_settings(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    return options.get("effects") if isinstance(options.get("effects"), dict) else load_effects()


def resolve_foundation_pattern_options(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    source = str(options.get("foundation_pattern_source") or "auto")
    if source not in {"auto", "uploaded"}:
        source = "auto"
    performance_mode = str(options.get("foundation_performance_mode") or "block")
    if performance_mode not in {"auto", *MODE_OPTIONS}:
        performance_mode = "auto"
    return {
        "foundation_pattern_source": source,
        "foundation_uploaded_pattern_id": str(options.get("foundation_uploaded_pattern_id") or "") or None,
        "preserve_uploaded_performance": bool(options.get("preserve_uploaded_performance", True)),
        "foundation_performance_mode": performance_mode,
        "override_uploaded_performance": bool(options.get("override_uploaded_performance", False)),
    }


def resolve_bass_groove_options(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    source = str(options.get("bass_source") or "groove_modes")
    if source not in {"groove_modes", "legacy_generator"}:
        source = "groove_modes"
    mode = str(options.get("bass_groove_mode") or "sustain_root")
    if mode not in {"auto", *BASS_GROOVE_MODE_IDS}:
        mode = "auto"
    variant = str(options.get("bass_groove_variant") or "auto")
    known_variants = {variant["id"] for groove in load_bass_grooves().values() for variant in groove.get("variants", [])}
    if variant not in {"auto", *known_variants}:
        variant = "auto"
    return {
        "bass_source": source,
        "bass_groove_mode": mode,
        "bass_groove_variant": variant,
    }


def resolve_guitar_performance_options(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    mode = str(options.get("guitar_performance_mode") or "auto")
    if mode not in {"auto", *GUITAR_MODE_IDS}:
        mode = "auto"
    variant = str(options.get("guitar_pattern_variant") or "auto")
    known_variants = {item.get("id") for guitar_mode in load_guitar_performance_modes().values() for item in guitar_mode.get("variants", [])}
    if variant not in {"auto", *known_variants}:
        variant = "auto"
    try:
        roll_amount = float(options.get("guitar_roll_amount", 1))
    except (TypeError, ValueError):
        roll_amount = 1.0
    return {"guitar_performance_mode": mode, "guitar_pattern_variant": variant, "guitar_roll_amount": max(0.0, min(1.5, roll_amount))}


def resolve_string_performance_options(data: dict) -> dict:
    options = data.get("generation_settings") if isinstance(data.get("generation_settings"), dict) else {}
    mode = str(options.get("string_performance_mode") or "auto")
    if mode not in {"auto", *STRING_PERFORMANCE_MODE_IDS}:
        mode = "auto"
    return {"string_performance_mode": mode}


def clear_sample_overlays(result: dict) -> None:
    audio_render = result.get("audio_render")
    if isinstance(audio_render, dict):
        audio_render["sample_overlays"] = []
    music_rules = result.get("music_rules")
    if isinstance(music_rules, dict):
        audio_config = music_rules.get("audio_render_config")
        if isinstance(audio_config, dict):
            audio_config["sample_overlays"] = []


def safe_output_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value).strip("._") or next(tempfile._get_candidate_names())


def parse_multipart(body: bytes, content_type: str) -> tuple[dict[str, str], dict[str, tuple[str, bytes]]]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("Missing multipart boundary.")
    boundary = match.group("boundary").strip('"')
    marker = f"--{boundary}".encode("utf-8")
    fields: dict[str, str] = {}
    files: dict[str, tuple[str, bytes]] = {}
    for part in body.split(marker):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_bytes, content = part.split(b"\r\n\r\n", 1)
        content = content.removesuffix(b"\r\n").removesuffix(b"--")
        headers = header_bytes.decode("utf-8", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match:
            files[name] = (filename_match.group(1), content)
        else:
            fields[name] = content.decode("utf-8", errors="replace")
    return fields, files


def parse_multipart_multi(body: bytes, content_type: str) -> tuple[dict[str, str], dict[str, list[tuple[str, bytes]]]]:
    match = re.search(r"boundary=(?P<boundary>[^;]+)", content_type)
    if not match:
        raise ValueError("Missing multipart boundary.")
    boundary = match.group("boundary").strip('"')
    marker = f"--{boundary}".encode("utf-8")
    fields: dict[str, str] = {}
    files: dict[str, list[tuple[str, bytes]]] = {}
    for part in body.split(marker):
        part = part.strip(b"\r\n")
        if not part or part == b"--" or b"\r\n\r\n" not in part:
            continue
        header_bytes, content = part.split(b"\r\n\r\n", 1)
        content = content.removesuffix(b"\r\n").removesuffix(b"--")
        headers = header_bytes.decode("utf-8", errors="ignore")
        disposition = next((line for line in headers.split("\r\n") if line.lower().startswith("content-disposition:")), "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename_match = re.search(r'filename="([^"]*)"', disposition)
        if filename_match:
            files.setdefault(name, []).append((filename_match.group(1), content))
        else:
            fields[name] = content.decode("utf-8", errors="replace")
    return fields, files
