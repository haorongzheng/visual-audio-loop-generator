from __future__ import annotations

import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from auto_loop_midi_generator.bass_grooves import (
    MODE_IDS,
    bass_groove_events,
    default_bass_grooves,
    select_bass_groove,
)


CHORDS = [
    SimpleNamespace(bass_note=36),
    SimpleNamespace(bass_note=33),
    SimpleNamespace(bass_note=29),
    SimpleNamespace(bass_note=31),
]


class BassGrooveTests(unittest.TestCase):
    def test_default_library_keeps_existing_modes_and_adds_electronic_ethnic_and_cinematic_modes(self) -> None:
        library = default_bass_grooves()
        self.assertEqual(tuple(library), MODE_IDS)
        self.assertTrue(all(len(library[mode_id]["variants"]) == 4 for mode_id in MODE_IDS[:4]))
        self.assertEqual(library["house_four_on_floor"]["category"], "electronic")
        self.assertEqual(library["808_sync"]["category"], "electronic")
        self.assertEqual(library["ethnic_drone"]["category"], "ethnic")
        self.assertEqual(library["middle_eastern_pulse"]["style"], "middle_eastern")
        self.assertEqual(library["cinematic_sub_sustain"]["category"], "cinematic")
        self.assertTrue(library["cinematic_sub_sustain"]["harmony_follow"])
        self.assertEqual(library["cinematic_emotional_movement"]["style"], "emotional_low_movement")
        self.assertEqual(library["house_four_on_floor"]["variants"][0]["events"], [
            {"step": 0, "degree": "root", "duration_steps": 3, "velocity_multiplier": 1.0, "probability": 1.0, "glide": False, "enabled": True},
            {"step": 4, "degree": "octave_root", "duration_steps": 3, "velocity_multiplier": 1.0, "probability": 1.0, "glide": False, "enabled": True},
            {"step": 8, "degree": "root", "duration_steps": 3, "velocity_multiplier": 1.0, "probability": 1.0, "glide": False, "enabled": True},
            {"step": 12, "degree": "fifth", "duration_steps": 3, "velocity_multiplier": 1.0, "probability": 1.0, "glide": False, "enabled": True},
        ])

    def test_manual_mode_and_variant_are_locked_for_the_whole_loop(self) -> None:
        events, manifest = bass_groove_events(
            CHORDS, 4, 92, "electronic", "流动", "groove", "欢快", random.Random(4), "pulse", "pulse_c"
        )
        self.assertEqual(manifest["mode"], "pulse")
        self.assertEqual(manifest["variant_id"], "pulse_c")
        self.assertTrue(manifest["main_mode_locked"])
        self.assertTrue(manifest["main_variant_locked"])
        self.assertTrue(events)

    def test_electronic_bass_notes_are_one_octave_higher(self) -> None:
        for mode in MODE_IDS:
            events, manifest = bass_groove_events(
                CHORDS, 4, 96, "electronic", "高能", "groove", "激昂", random.Random(9), mode
            )
            self.assertIsNotNone(manifest)
            self.assertEqual(manifest["octave_shift"], 12)
            self.assertTrue(all(36 <= event["pitch"] <= 72 for event in events), mode)
            self.assertTrue(all(event["degree"] in manifest["allowed_degrees"] for event in events), mode)

    def test_non_electronic_bass_keeps_its_original_register(self) -> None:
        events, manifest = bass_groove_events(
            CHORDS, 4, 84, "ambient", "流动", "flow", "平静", random.Random(9), "sustain_root", "sustain_root_a"
        )
        self.assertEqual(manifest["octave_shift"], 0)
        self.assertTrue(all(24 <= event["pitch"] <= 60 for event in events))

    def test_static_state_prefers_sustain_or_root_fifth(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            mode, _variant, source = select_bass_groove("electronic", "静止", "standard", "深沉", random.Random(2))
        self.assertEqual(source, "auto")
        self.assertIn(mode["id"], {"sustain_root", "root_fifth"})

    def test_electronic_auto_resolver_selects_house_and_808_from_rhythm_profile(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            house, _, _ = select_bass_groove("electronic", "流动", "groove", "欢快", random.Random(1))
            edm_low, _, _ = select_bass_groove("electronic", "流动", "aggressive", "欢快", random.Random(1))
            edm_high, _, _ = select_bass_groove("electronic", "高能", "aggressive", "欢快", random.Random(1))
            trap, _, _ = select_bass_groove("electronic", "流动", "flow", "欢快", random.Random(1))
        self.assertEqual(house["id"], "house_four_on_floor")
        self.assertEqual(edm_low["id"], "house_four_on_floor")
        self.assertEqual(edm_high["id"], "808_sync")
        self.assertEqual(trap["id"], "808_sync")

    def test_electronic_modes_do_not_leak_into_other_sound_directions(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            mode, _, _ = select_bass_groove("acoustic", "流动", "groove", "欢快", random.Random(3), "808_sync")
        self.assertNotEqual(mode["id"], "808_sync")

    def test_ethnic_auto_resolver_selects_drone_or_middle_eastern_pulse(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            drone, _, _ = select_bass_groove("ethnic", "静止", "sparse", "深沉", random.Random(1))
            deep, _, _ = select_bass_groove("ethnic", "流动", "standard", "深沉", random.Random(1))
            pulse, _, _ = select_bass_groove("ethnic", "流动", "flow", "欢快", random.Random(1))
            groove, _, _ = select_bass_groove("ethnic", "高能", "groove", "激昂", random.Random(1))
        self.assertEqual(drone["id"], "ethnic_drone")
        self.assertEqual(deep["id"], "ethnic_drone")
        self.assertEqual(pulse["id"], "middle_eastern_pulse")
        self.assertEqual(groove["id"], "middle_eastern_pulse")

    def test_ethnic_patterns_keep_their_declared_degrees_and_register(self) -> None:
        drone_events, drone = bass_groove_events(
            CHORDS, 4, 80, "ethnic", "静止", "sparse", "深沉", random.Random(3), "ethnic_drone", "ethnic_drone_a"
        )
        pulse_events, pulse = bass_groove_events(
            CHORDS, 4, 92, "ethnic", "流动", "flow", "欢快", random.Random(3), "middle_eastern_pulse", "middle_eastern_pulse_a"
        )
        self.assertEqual([(item["step"], item["degree"]) for item in drone_events if item["bar"] == 0], [(0.0, "root"), (8.0, "fifth"), (12.0, "root")])
        self.assertEqual([(item["step"], item["degree"]) for item in pulse_events if item["bar"] == 0], [(0.0, "root"), (3.0, "fifth"), (6.0, "root"), (8.0, "root"), (11.0, "fifth"), (14.0, "octave_root")])
        self.assertEqual(drone["style"], "middle_eastern")
        self.assertEqual(pulse["category"], "ethnic")
        self.assertTrue(all(24 <= item["pitch"] <= 60 for item in drone_events + pulse_events))

    def test_cinematic_auto_resolver_uses_sparse_or_emotional_mode(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            still, _, _ = select_bass_groove("cinematic", "静止", "standard", "深沉", random.Random(1))
            moving, _, _ = select_bass_groove("cinematic", "流动", "flow", "忧伤", random.Random(1))
        self.assertEqual(still["id"], "cinematic_sub_sustain")
        self.assertEqual(moving["id"], "cinematic_emotional_movement")

    def test_string_foundation_locks_matching_cinematic_bass_mode(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            long_pad_events, long_pad = bass_groove_events(
                CHORDS, 4, 80, "cinematic", "流动", "standard", "明亮", random.Random(3), "auto", "auto", "string_long_pad"
            )
            movement_events, movement = bass_groove_events(
                CHORDS, 4, 86, "cinematic", "静止", "standard", "深沉", random.Random(3), "auto", "auto", "string_emotional_movement"
            )
        self.assertEqual(long_pad["mode"], "cinematic_sub_sustain")
        self.assertTrue(long_pad["foundation_linked"])
        self.assertTrue(all(item["duration"] >= 1_800 for item in long_pad_events))
        self.assertEqual(movement["mode"], "cinematic_emotional_movement")
        self.assertTrue(movement["foundation_linked"])
        self.assertTrue(set(item["degree"] for item in movement_events) <= {"root", "fifth", "octave_root"})

    def test_disabled_mode_library_falls_back_to_legacy(self) -> None:
        disabled = default_bass_grooves()
        for mode in disabled.values():
            mode["enabled"] = False
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=disabled):
            mode, variant, reason = select_bass_groove("ambient", "静止", "sparse", "深沉", random.Random(1))
        self.assertIsNone(mode)
        self.assertIsNone(variant)
        self.assertEqual(reason, "legacy_fallback")

    def test_eight_bars_repeats_the_first_four_bass_bars(self) -> None:
        with patch("auto_loop_midi_generator.bass_grooves.load_bass_grooves", return_value=default_bass_grooves()):
            events, _manifest = bass_groove_events(
                CHORDS * 2, 8, 92, "electronic", "流动", "groove", "欢快", random.Random(4), "pulse", "pulse_c"
            )
        first = [{key: value for key, value in event.items() if key != "bar"} for event in events if event["bar"] < 4]
        second = [{key: value for key, value in event.items() if key != "bar"} for event in events if event["bar"] >= 4]
        self.assertEqual(first, second)

    def test_808_manifest_is_tight_and_uses_pickup_glide_fallback(self) -> None:
        events, manifest = bass_groove_events(
            CHORDS, 4, 112, "electronic", "高能", "flow", "激昂", random.Random(6), "808_sync", "808_sync_a"
        )
        self.assertEqual(manifest["category"], "electronic")
        self.assertEqual(manifest["rhythm_profile"], "trap_hybrid")
        self.assertTrue(manifest["slide_enabled"])
        self.assertEqual(manifest["slide_strategy"], "pickup_fallback")
        self.assertTrue(set(event["degree"] for event in events) <= {"root", "octave_root", "next_root"})
        self.assertLessEqual(manifest["humanize_limits"]["timing"], .02)


if __name__ == "__main__":
    unittest.main()
