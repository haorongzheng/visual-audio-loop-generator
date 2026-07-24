from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_loop_midi_generator.foundation_midi_patterns import (
    analyze_midi,
    match_foundation_pattern,
    parse_midi,
    save_staged_pattern,
    stage_upload,
)
from auto_loop_midi_generator.generator import generate_loop
from auto_loop_midi_generator.midi_writer import MidiFile
from auto_loop_midi_generator.music_state_schema import coerce_annotation


class FoundationMidiPatternTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.patches = patch.multiple(
            "auto_loop_midi_generator.foundation_midi_patterns",
            DATA_DIR=root,
            FILES_DIR=root / "files",
            TEMP_DIR=root / "temp",
            DB_PATH=root / "foundation_patterns.json",
            PENDING_PATH=root / "temp" / "pending_uploads.json",
        )
        self.patches.start()

    def tearDown(self) -> None:
        self.patches.stop()
        self.temp.cleanup()

    def recorded_midi(self) -> bytes:
        path = Path(self.temp.name) / "recorded.mid"
        midi = MidiFile(96)
        track = midi.add_track("Recorded Rhodes", 0, None)
        for note, start in ((60, 0), (64, 30), (67, 60), (57, 1920), (60, 1950), (64, 1980)):
            track.note(note, start, 360, 88)
        midi.save(path)
        return path.read_bytes()

    def state(self):
        return coerce_annotation({
            "state_id": "foundation_test",
            "music_state": {
                "emotion": {"label": "深沉", "value": -1},
                "energy": {"label": "静止", "value": 0},
                "sound_direction": {"label": "氛围", "value": "ambient"},
                "rhythm": {"label": "标准", "value": "standard"},
            },
            "loop": {"length_bars": 4, "output_type": "audio_loop", "midi_driven": True},
        })

    def save_pattern(self):
        staged = stage_upload("Recorded_C.mid", self.recorded_midi())
        return save_staged_pattern(staged["upload_id"], {
            "name": "Recorded Test", "source_track_index": staged["auto_selected_track_index"],
            "loop_length_bars": 4, "source_key_root": "C", "source_mode": "major",
            "source_chords": "Cmaj9, Am9, Fmaj9, Gsus13", "emotion": ["深沉"],
            "energy": ["静止"], "sound_direction": ["ambient"], "rhythm": ["standard"],
            "enabled": True, "priority": 100,
        })

    def test_analyzes_and_normalizes_uploaded_midi(self) -> None:
        analysis = analyze_midi(self.recorded_midi())
        self.assertEqual(analysis["ppq"], 480)
        self.assertEqual(len(analysis["note_tracks"]), 1)
        pattern = self.save_pattern()
        self.assertEqual(pattern["ppq"], 480)
        self.assertEqual(pattern["time_signature"], "4/4")
        self.assertTrue(all(event["start_tick"] >= 0 for event in pattern["events"]))
        self.assertTrue(all(1 <= event["velocity"] <= 127 for event in pattern["events"]))

    def test_rejects_non_midi_upload(self) -> None:
        with self.assertRaises(ValueError):
            stage_upload("not-midi.txt", b"not a MIDI file")

    def test_uploaded_pattern_preserves_saved_midi_pitches(self) -> None:
        pattern = self.save_pattern()
        matched, fields = match_foundation_pattern(self.state(), 4, 99)
        self.assertEqual(matched["id"], pattern["id"])
        self.assertEqual(fields, ["emotion", "energy", "sound_direction", "rhythm"])
        output = Path(self.temp.name) / "adapted.mid"
        with patch("auto_loop_midi_generator.generator.match_instrument", return_value=None):
            result = generate_loop(self.state(), output, foundation_pattern_source="uploaded", foundation_uploaded_pattern_id=pattern["id"])
        self.assertTrue(output.is_file())
        self.assertEqual(result["foundation_performance"]["source"], "uploaded_midi")
        self.assertEqual(result["foundation_performance"]["pattern_id"], pattern["id"])
        self.assertEqual(result["foundation_performance"]["trigger_count"], len(pattern["events"]))
        rendered_foundation = parse_midi(output.read_bytes())["tracks"][1]["events"]
        self.assertEqual([event["note"] for event in rendered_foundation], [event["note"] for event in pattern["events"]])
        self.assertEqual(result["foundation_performance"]["pitch_source"], "uploaded_midi_exact")


if __name__ == "__main__":
    unittest.main()
