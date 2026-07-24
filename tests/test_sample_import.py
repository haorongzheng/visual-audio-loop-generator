from __future__ import annotations

import io
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from auto_loop_midi_generator import instrument_library, sample_import


def wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(48000)
        output.writeframes(b"\0\0" * 480)
    return buffer.getvalue()


class SampleImportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.sample_patch = patch.multiple(
            "auto_loop_midi_generator.sample_import",
            ROOT=root,
            IMPORT_DIR=root / "sample_import",
            JOB_DIR=root / "sample_import" / "jobs",
            JOB_DB=root / "sample_import" / "sample_import_jobs.json",
            SOURCE_DB=root / "sample_import" / "sample_sources.json",
        )
        self.instrument_patch = patch.multiple(
            "auto_loop_midi_generator.instrument_library",
            ROOT=root,
            INSTRUMENT_DIR=root / "instruments",
            INSTRUMENT_FILE_DIR=root / "instruments" / "files",
            INSTRUMENT_DB_PATH=root / "instruments" / "instruments.json",
        )
        self.sample_patch.start()
        self.instrument_patch.start()

    def tearDown(self) -> None:
        self.instrument_patch.stop()
        self.sample_patch.stop()
        self.temp.cleanup()

    def test_folder_import_auto_detects_root_and_midpoint_ranges(self) -> None:
        job = sample_import.stage_upload("folder", [
            ("Keys_C2.wav", wav_bytes()),
            ("Keys_C3.wav", wav_bytes()),
            ("Keys_C4.wav", wav_bytes()),
        ])
        zones = job["preview"]["zones"]
        c3 = next(zone for zone in zones if zone["root_midi_note"] == 48)
        self.assertEqual((c3["low_midi_note"], c3["high_midi_note"]), (42, 53))
        self.assertEqual(job["preview"]["range"], {"low": 24, "high": 72})

    def test_sfz_import_honors_region_mapping_and_creates_foundation_instrument(self) -> None:
        sfz = b'<region> sample="Piano_C#3.wav" pitch_keycenter=49 lokey=45 hikey=54 lovel=1 hivel=100\n'
        job = sample_import.stage_upload("sfz", [("Piano.sfz", sfz), ("Piano_C#3.wav", wav_bytes())])
        zone = job["preview"]["zones"][0]
        self.assertEqual(zone["root_midi_note"], 49)
        self.assertEqual((zone["low_midi_note"], zone["high_midi_note"]), (45, 54))
        result = sample_import.create_instrument(job["id"], {"name": "Imported Piano", "track_role": "foundation", "category": "piano", "library": "Test Library"})
        instrument = result["instrument"]
        self.assertEqual(instrument["track_role"], "foundation")
        self.assertEqual(instrument["sample_zones"][0]["root_midi_note"], 49)
        self.assertTrue((Path(self.temp.name) / instrument["sample_zones"][0]["file_url"].lstrip("/")).is_file())
        self.assertEqual(instrument_library.get_instrument(instrument["id"])["name"], "Imported Piano")

    def test_uncreated_analysis_job_can_be_deleted(self) -> None:
        job = sample_import.stage_upload("folder", [("Keys_C3.wav", wav_bytes())])
        result = sample_import.delete_uncreated_job(job["id"])
        self.assertEqual(result["id"], job["id"])
        self.assertIsNone(sample_import.job_by_id(job["id"]))
        self.assertFalse((Path(self.temp.name) / "sample_import" / "jobs" / job["id"]).exists())

    def test_created_instrument_job_is_displayed_and_cannot_be_deleted(self) -> None:
        job = sample_import.stage_upload("folder", [("Keys_C3.wav", wav_bytes())])
        result = sample_import.create_instrument(job["id"], {"name": "Created Keys", "track_role": "foundation", "category": "piano"})
        exported = sample_import.export_jobs()["jobs"]
        completed = next(item for item in exported if item["id"] == job["id"])
        self.assertEqual(completed["created_instruments"], [{"id": result["instrument"]["id"], "name": "Created Keys"}])
        with self.assertRaisesRegex(ValueError, "已经创建乐器"):
            sample_import.delete_uncreated_job(job["id"])

    def test_cleanup_removes_completed_job_after_its_instrument_is_deleted(self) -> None:
        job = sample_import.stage_upload("folder", [("Keys_C3.wav", wav_bytes())])
        result = sample_import.create_instrument(job["id"], {"name": "Deleted Keys", "track_role": "foundation", "category": "piano"})
        instrument_library.delete_instrument(result["instrument"]["id"])
        cleanup = sample_import.cleanup_orphaned_completed_jobs()
        self.assertEqual(cleanup["job_ids"], [job["id"]])
        self.assertGreater(cleanup["bytes_freed"], 0)
        self.assertIsNone(sample_import.job_by_id(job["id"]))

    def test_rejects_unsafe_and_unsupported_files(self) -> None:
        with self.assertRaises(ValueError):
            sample_import.stage_upload("folder", [("../escape.wav", wav_bytes())])
        with self.assertRaises(ValueError):
            sample_import.stage_upload("folder", [("notes.txt", b"not audio")])

    def test_mappingchart_import_parses_notes_dynamics_rr_and_midpoint_ranges(self) -> None:
        mapping = b"""Sample Name Key
Player_dyn1_rr1_000.wav A0
Player_dyn1_rr2_000.wav A0
Player_dyn2_rr1_002.wav C#1
Player_dyn3_rr1_004.wav E1
"""
        job = sample_import.stage_upload("mappingchart", [
            ("Upright Piano/MappingChart.txt", mapping),
            ("Upright Piano/Player_dyn1_rr1_000.wav", wav_bytes()),
            ("Upright Piano/Player_dyn1_rr2_000.wav", wav_bytes()),
            ("Upright Piano/Player_dyn2_rr1_002.wav", wav_bytes()),
            ("Upright Piano/Player_dyn3_rr1_004.wav", wav_bytes()),
        ])
        preview = job["preview"]
        self.assertEqual(preview["format"], "MappingChart")
        self.assertEqual((preview["keys"], preview["velocity_layers"], preview["round_robin"]), (3, 3, 2))
        a0 = [zone for zone in preview["zones"] if zone["root_midi_note"] == 21]
        self.assertEqual(len(a0), 2)
        self.assertTrue(all((zone["low_midi_note"], zone["high_midi_note"]) == (17, 22) for zone in a0))
        self.assertEqual((a0[0]["velocity_low"], a0[0]["velocity_high"]), (1, 40))
        self.assertEqual(sorted(zone["round_robin_index"] for zone in a0), [1, 2])
        self.assertEqual(next(zone for zone in preview["zones"] if zone["velocity_layer"] == 2)["velocity_low"], 41)

    def test_mappingchart_warns_about_missing_audio_and_imports_rr_metadata(self) -> None:
        mapping = b"Player_dyn1_rr1_024.wav 60\nMissing_dyn1_rr1_025.wav 61\n"
        job = sample_import.stage_upload("mappingchart", [("MappingChart.txt", mapping), ("Player_dyn1_rr1_024.wav", wav_bytes())])
        self.assertEqual(len(job["preview"]["zones"]), 1)
        self.assertIn("Missing_dyn1_rr1_025.wav", job["preview"]["warnings"][0])
        result = sample_import.create_instrument(job["id"], {"name": "VSCO Piano", "track_role": "foundation", "category": "piano", "library": "VSCO2"})
        zone = result["instrument"]["sample_zones"][0]
        self.assertEqual(result["instrument"]["source_info"]["type"], "mappingchart")
        self.assertEqual((zone["velocity_layer"], zone["round_robin_index"], zone["source_library"]), (1, 1, "VSCO2"))
        self.assertEqual(result["instrument"]["playback"]["gain_db"], 12.0)

    def test_vsco_mappingchart_uses_filename_suffix_index(self) -> None:
        mapping = b"Notation=KeyNumber\n000=21\n002=25\n"
        job = sample_import.stage_upload("mappingchart", [
            ("Upright Piano/MappingChart.txt", mapping),
            ("Upright Piano/Player_dyn1_rr1_000.wav", wav_bytes()),
            ("Upright Piano/Player_dyn2_rr1_000.wav", wav_bytes()),
            ("Upright Piano/Player_dyn1_rr1_002.wav", wav_bytes()),
            ("Upright Piano/Player_dyn2_rr1_002.wav", wav_bytes()),
        ])
        zones = job["preview"]["zones"]
        self.assertEqual(len(zones), 4)
        self.assertEqual({zone["root_midi_note"] for zone in zones if zone["file_name"].endswith("_000.wav")}, {21})
        self.assertEqual({zone["root_midi_note"] for zone in zones if zone["file_name"].endswith("_002.wav")}, {25})
        self.assertEqual({(zone["velocity_low"], zone["velocity_high"]) for zone in zones if zone["velocity_layer"] == 1}, {(1, 63)})
        self.assertEqual({(zone["velocity_low"], zone["velocity_high"]) for zone in zones if zone["velocity_layer"] == 2}, {(64, 127)})

    def test_round_robin_selection_cycles_without_randomness(self) -> None:
        instrument = {"sample_zones": [
            {"id": "rr2", "enabled": True, "file_url": "/sample2.wav", "root_midi_note": 60, "note_range": {"low": 60, "high": 60}, "velocity_range": {"low": 1, "high": 127}, "round_robin_group": "1", "round_robin_index": 2},
            {"id": "rr1", "enabled": True, "file_url": "/sample1.wav", "root_midi_note": 60, "note_range": {"low": 60, "high": 60}, "velocity_range": {"low": 1, "high": 127}, "round_robin_group": "1", "round_robin_index": 1},
        ]}
        cursor: dict[str, int] = {}
        order = [instrument_library.select_zone(instrument, 60, 80, cursor)[0]["id"] for _ in range(4)]
        self.assertEqual(order, ["rr1", "rr2", "rr1", "rr2"])

    def test_vsco_bass_selection_ignores_release_noise_and_fixes_filename_layers(self) -> None:
        instrument = {"source_info": {"type": "vsco_library"}, "sample_zones": [
            {"id": "release", "enabled": True, "file_url": "/release.wav", "file_name": "a1_release_rr1.wav", "root_midi_note": 33, "note_range": {"low": 30, "high": 36}, "velocity_range": {"low": 111, "high": 110}},
            {"id": "noise", "enabled": True, "file_url": "/noise.wav", "file_name": "noise_fingering_rr1.wav", "root_midi_note": 33, "note_range": {"low": 30, "high": 36}, "velocity_range": {"low": 1, "high": 127}},
            {"id": "soft", "enabled": True, "file_url": "/p.wav", "file_name": "a1_p_rr1.wav", "root_midi_note": 33, "note_range": {"low": 30, "high": 36}, "velocity_range": {"low": 111, "high": 50}},
            {"id": "loud", "enabled": True, "file_url": "/fff.wav", "file_name": "a1_fff_rr1.wav", "root_midi_note": 33, "note_range": {"low": 30, "high": 36}, "velocity_range": {"low": 111, "high": 110}},
        ]}
        self.assertEqual(instrument_library.select_zone(instrument, 33, 30)[0]["id"], "soft")
        self.assertEqual(instrument_library.select_zone(instrument, 33, 120)[0]["id"], "loud")

    def test_vsco_library_recursively_resolves_default_path_and_sample(self) -> None:
        sfz = b"""<control>
default_path=Keys\\Upright Nr1\\
<group> group_label=rr_group
<region> sample=UR1_C3_pp_RR1.wav lokey=46 hikey=51 pitch_keycenter=48 lovel=0 hivel=80
"""
        job = sample_import.start_vsco_import()
        sample_import.append_vsco_file(job["id"], "VSCO/VSUpright1.sfz", sfz)
        sample_import.append_vsco_file(job["id"], "VSCO/Keys/Upright Nr1/UR1_C3_pp_RR1.wav", wav_bytes())
        analyzed = sample_import.analyze_vsco_job(job["id"])
        definition = analyzed["preview"]["instruments"][0]
        self.assertEqual(definition["name"], "VSUpright1")
        self.assertEqual(definition["zones"][0]["root_midi_note"], 48)
        self.assertEqual(definition["zones"][0]["relative_path"], "VSCO/Keys/Upright Nr1/UR1_C3_pp_RR1.wav")
        created = sample_import.create_vsco_instruments(job["id"], {"instrument_ids": [definition["id"]], "name": "Upright Piano", "track_role": "lead", "category": "strings", "library": "VSCO2"})
        self.assertEqual(len(created["instruments"]), 1)
        self.assertFalse(created["instruments"][0]["enabled"])
        self.assertEqual((created["instruments"][0]["name"], created["instruments"][0]["track_role"], created["instruments"][0]["category"]), ("Upright Piano", "lead", "strings"))

    def test_vsco_import_preserves_sfz_zone_volume(self) -> None:
        sfz = b'<region> sample="Strings/Violin_A3.wav" pitch_keycenter=69 lokey=68 hikey=70 lovel=0 hivel=62 volume=18\n'
        job = sample_import.start_vsco_import()
        sample_import.append_vsco_file(job["id"], "VSCO/Violin.sfz", sfz)
        sample_import.append_vsco_file(job["id"], "VSCO/Strings/Violin_A3.wav", wav_bytes())
        analyzed = sample_import.analyze_vsco_job(job["id"])
        zone = analyzed["preview"]["instruments"][0]["zones"][0]
        self.assertEqual(zone["gain_db"], 18.0)
        created = sample_import.create_vsco_instruments(job["id"], {"instrument_ids": [analyzed["preview"]["instruments"][0]["id"]], "track_role": "foundation", "category": "strings"})
        self.assertEqual(created["instruments"][0]["sample_zones"][0]["gain_db"], 18.0)

    def test_vsco_library_recognizes_flac_samples_from_sfz(self) -> None:
        sfz = b'<region> sample="Strings/Viola_C3.flac" pitch_keycenter=48 lokey=44 hikey=52\n'
        job = sample_import.start_vsco_import()
        sample_import.append_vsco_file(job["id"], "VSCO/Viola.sfz", sfz)
        sample_import.append_vsco_file(job["id"], "VSCO/Strings/Viola_C3.flac", b"fLaC\x00\x00\x00\x22")
        analyzed = sample_import.analyze_vsco_job(job["id"])
        zone = analyzed["preview"]["instruments"][0]["zones"][0]
        self.assertEqual(zone["file_name"], "Viola_C3.flac")
        self.assertEqual(zone["root_midi_note"], 48)


if __name__ == "__main__":
    unittest.main()
