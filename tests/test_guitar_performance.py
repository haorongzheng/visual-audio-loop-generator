from __future__ import annotations

import random
import unittest
from unittest.mock import patch

from auto_loop_midi_generator.generator import expanded_chords, write_foundation
from auto_loop_midi_generator.guitar_performance import MODE_IDS, chord_degree_pitch, default_guitar_performance_modes, guitar_events, guitar_range, is_guitar_instrument, normalize_event
from auto_loop_midi_generator.midi_writer import MidiFile


class GuitarPerformanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chords = expanded_chords(("Cmaj7", "Am7", "Fmaj7", "G7"), 4)
        self.modes = default_guitar_performance_modes()

    def events(self, guitar_type: str, mode: str, variant: str = "auto"):
        sound = "ethnic" if mode in {"oud_style_picking", "desert_pulse"} else "ambient"
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=self.modes):
            return guitar_events(self.chords, 4, 88, guitar_type, sound, "流动", "flow", random.Random(12), mode, variant)

    def test_keeps_four_sparse_modes_and_adds_two_ethnic_nylon_modes(self) -> None:
        self.assertEqual(set(MODE_IDS), set(self.modes))
        self.assertEqual(len(self.modes), 6)
        self.assertTrue(all(len(mode["variants"]) == 1 for mode in self.modes.values()))
        self.assertEqual(self.modes["oud_style_picking"]["category"], "ethnic")
        self.assertEqual(self.modes["desert_pulse"]["allowed_guitar_types"], ["nylon"])

    def test_ethnic_auto_modes_use_nylon_and_middle_eastern_patterns(self) -> None:
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=self.modes):
            oud_events, oud = guitar_events(self.chords, 4, 82, "nylon", "ethnic", "静止", "flow", random.Random(4), emotion="深沉")
            desert_events, desert = guitar_events(self.chords, 4, 88, "nylon", "ethnic", "流动", "groove", random.Random(4), emotion="欢快")
        self.assertEqual(oud["pattern"], "oud_style_picking")
        self.assertEqual(desert["pattern"], "desert_pulse")
        self.assertEqual(oud["category"], "ethnic")
        self.assertEqual(oud["instrument"], "nylon_guitar")
        self.assertEqual(oud["style"], "middle_eastern")
        self.assertTrue(any(item["play_mode"] == "roll_up" for item in oud_events))
        self.assertTrue(any(item["play_mode"] == "roll_down" for item in desert_events))

    def test_ethnic_modes_keep_attacks_on_grid(self) -> None:
        for mode_id in ("oud_style_picking", "desert_pulse"):
            events, manifest = self.events("nylon", mode_id, f"{mode_id}_a")
            self.assertTrue(all(item["timing"] == 0 for item in events))
            self.assertEqual(manifest["style"], "middle_eastern")

    def test_guitar_engine_is_explicit(self) -> None:
        self.assertTrue(is_guitar_instrument({"performance_engine": "guitar_single_note", "guitar_type": "nylon"}))
        self.assertTrue(is_guitar_instrument({"performance_engine": "guitar_single_note", "guitar_type": "electric"}))
        self.assertFalse(is_guitar_instrument({"performance_engine": "foundation", "guitar_type": "nylon"}))

    def test_every_mode_outputs_midi_notes_in_guitar_range(self) -> None:
        for mode_id in MODE_IDS:
            guitar_type = "electric" if mode_id == "sparse_downstroke" else "nylon"
            events, manifest = self.events(guitar_type, mode_id, f"{mode_id}_a")
            self.assertIsNotNone(manifest)
            low, high = guitar_range(guitar_type)
            self.assertTrue(events)
            self.assertTrue(all(low <= event["pitch"] <= high for event in events))
            self.assertTrue(all("string" not in event and "fret" not in event for event in events))
            self.assertEqual(manifest["mode"], mode_id)

    def test_ninth_falls_back_to_octave_root(self) -> None:
        chord = expanded_chords(("C",), 1)[0]
        root = chord_degree_pitch("root", chord, chord, None, "nylon")
        ninth = chord_degree_pitch("ninth", chord, chord, None, "nylon")
        self.assertEqual(ninth, root + 12)

    def test_bar_variations_keep_mode_and_variant_locked(self) -> None:
        events, manifest = self.events("nylon", "sparse_swell", "sparse_swell_a")
        self.assertTrue(manifest["main_mode_locked"])
        self.assertTrue(manifest["main_variant_locked"])
        self.assertLess(len([event for event in events if event["bar"] == 1]), len([event for event in events if event["bar"] == 0]))
        self.assertTrue(any(event["play_mode"] == "roll_up" for event in events if event["bar"] == 2))

    def test_legacy_degree_event_is_migrated_to_notes_array(self) -> None:
        item = normalize_event({"step": 3, "degree": "fifth", "duration_steps": 1})
        self.assertEqual(item["notes"], ["fifth"])
        self.assertEqual(item["play_mode"], "single")

    def test_rolls_share_event_end(self) -> None:
        events, _ = self.events("nylon", "sparse_response", "sparse_response_a")
        roll = [item for item in events if item["bar"] == 0 and item["play_mode"] == "roll_up"]
        roll = [item for item in roll if item["event_id"] == roll[0]["event_id"]]
        self.assertGreaterEqual(len(roll), 2)
        starts = [item["offset_ticks"] for item in roll]
        self.assertEqual(starts, sorted(starts))
        self.assertEqual({item["offset_ticks"] + item["duration"] for item in roll}, {roll[0]["duration"]})

    def test_roll_down_orders_by_pitch_descending(self) -> None:
        events, _ = self.events("nylon", "sparse_downstroke", "sparse_downstroke_a")
        roll = [item for item in events if item["bar"] == 0 and item["play_mode"] == "roll_down"]
        roll = [item for item in roll if item["event_id"] == roll[0]["event_id"]]
        self.assertEqual([item["pitch"] for item in roll], sorted((item["pitch"] for item in roll), reverse=True))
        self.assertEqual([item["offset_ticks"] for item in roll], sorted(item["offset_ticks"] for item in roll))

    def test_roll_amount_zero_turns_roll_into_stack(self) -> None:
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=self.modes):
            events, manifest = guitar_events(self.chords, 4, 88, "nylon", "ambient", "流动", "flow", random.Random(12), "sparse_response", "sparse_response_a", roll_amount=0)
        self.assertEqual(manifest["roll_up_event_count"], 0)
        self.assertTrue(any(item["play_mode"] == "stack" for item in events))

    def test_eight_bars_repeat_the_first_four_guitar_bars(self) -> None:
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=self.modes):
            events, _ = guitar_events(self.chords * 2, 8, 88, "nylon", "ambient", "流动", "flow", random.Random(12), "sparse_response", "sparse_response_a")
        first = [{key: value for key, value in item.items() if key != "bar"} for item in events if item["bar"] == 0]
        fifth = [{key: value for key, value in item.items() if key != "bar"} for item in events if item["bar"] == 4]
        self.assertEqual(first, fifth)

    def test_no_available_guitar_mode_falls_back_to_standard_foundation(self) -> None:
        disabled = self.modes.copy()
        for mode in disabled.values():
            mode["enabled"] = False
        midi = MidiFile(96)
        track = midi.add_track("Foundation", 0)
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=disabled):
            result = write_foundation(track, self.chords, 88, 4, .1, foundation_instrument={"performance_engine": "guitar_single_note", "guitar_type": "nylon"})
        self.assertEqual(result["source"], "foundation_performance_mode")

    def test_write_foundation_uses_guitar_events_before_uploaded_template(self) -> None:
        midi = MidiFile(96)
        track = midi.add_track("Foundation", 0)
        with patch("auto_loop_midi_generator.guitar_performance.load_guitar_performance_modes", return_value=self.modes):
            result = write_foundation(
                track, self.chords, 88, 4, .1, sound_value="ambient", energy_label="流动", rhythm_value="flow",
                foundation_instrument={"performance_engine": "guitar_single_note", "guitar_type": "nylon"},
                guitar_performance_mode="sparse_response", guitar_pattern_variant="sparse_response_a",
                uploaded_pattern={"id": "must_not_use", "events": []},
            )
        note_on = [event for event in track.events if event.data and event.data[0] == 0x90]
        self.assertEqual(result["source"], "guitar_single_note")
        self.assertEqual(result["mode"], "sparse_response")
        self.assertEqual(len(note_on), result["trigger_count"])


if __name__ == "__main__":
    unittest.main()
