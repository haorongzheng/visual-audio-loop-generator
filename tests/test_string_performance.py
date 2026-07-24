from __future__ import annotations

import random
import unittest

from auto_loop_midi_generator.generator import expanded_chords, write_foundation
from auto_loop_midi_generator.midi_writer import MidiTrack
from auto_loop_midi_generator.string_performance import (
    MODE_IDS,
    default_string_performance_modes,
    is_string_instrument,
    select_string_performance,
    string_events,
)


class StringPerformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.modes = default_string_performance_modes()
        self.chords = expanded_chords(("Cmaj7", "Am7", "Fmaj7", "G7"), 4)

    def test_default_modes_and_categories(self) -> None:
        self.assertEqual(MODE_IDS, ("string_long_pad", "string_emotional_movement"))
        self.assertTrue(is_string_instrument({"category": "strings"}))
        self.assertTrue(is_string_instrument({"category": "violin_section"}))
        self.assertFalse(is_string_instrument({"category": "piano"}))

    def test_resolver_mapping_uses_long_pad_for_still_ambient(self) -> None:
        mode, source = select_string_performance("ambient", "静止", "深沉", random.Random(1), mode_data=self.modes)
        self.assertEqual(mode["id"], "string_long_pad")
        self.assertEqual(source, "auto")

    def test_resolver_mapping_uses_emotional_movement_for_cinematic_flow(self) -> None:
        mode, source = select_string_performance("cinematic", "流动", "忧伤", random.Random(1), mode_data=self.modes)
        self.assertEqual(mode["id"], "string_emotional_movement")
        self.assertEqual(source, "auto")

    def test_long_pad_changes_to_each_bar_current_harmony(self) -> None:
        events, manifest = string_events(self.chords, 4, 86, "ambient", "静止", "深沉", random.Random(2), "string_long_pad", self.modes)
        self.assertEqual({item["bar"] for item in events}, {0, 1, 2, 3})
        self.assertTrue(all(item["duration"] > 1_920 for item in events))
        self.assertEqual(manifest["style"], "sustained_pad")
        self.assertEqual(manifest["legato_overlap_ticks"], 120)

    def test_write_foundation_uses_string_engine_only_for_string_instrument(self) -> None:
        track = MidiTrack("Foundation", 0)
        manifest = write_foundation(
            track, self.chords, 86, 4, .1, foundation_instrument={"category": "ensemble_strings"},
            sound_value="cinematic", energy_label="流动", emotion_label="忧伤", string_performance_mode="string_emotional_movement",
        )
        self.assertEqual(manifest["source"], "string_foundation")
        self.assertEqual(manifest["mode"], "string_emotional_movement")
        self.assertGreater(len(track.events), 0)


if __name__ == "__main__":
    unittest.main()
