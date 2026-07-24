from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from auto_loop_midi_generator.foundation_performance import MODE_OPTIONS, performance_events, select_performance_mode
from auto_loop_midi_generator.generator import generate_loop
from auto_loop_midi_generator.music_state_schema import coerce_annotation


class FoundationPerformanceModeTests(unittest.TestCase):
    def state(self, sound: str = "electronic", energy: str = "高能", rhythm: str = "groove"):
        return coerce_annotation({
            "state_id": "performance_mode_test",
            "music_state": {
                "emotion": {"label": "深沉", "value": -1},
                "energy": {"label": energy, "value": 1 if energy == "高能" else 0},
                "sound_direction": {"label": sound, "value": sound},
                "rhythm": {"label": rhythm, "value": rhythm},
            },
            "loop": {"length_bars": 4, "output_type": "audio_loop", "midi_driven": True},
        })

    def test_all_eight_modes_are_available(self) -> None:
        self.assertEqual(len(MODE_OPTIONS), 8)
        self.assertEqual(set(MODE_OPTIONS), {"block", "broken", "pulse", "rhythm_chop", "arpeggio", "octave_support", "wide_pad", "cluster"})

    def test_manual_mode_is_used_for_the_entire_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch("auto_loop_midi_generator.generator.match_instrument", return_value=None):
                result = generate_loop(self.state(), Path(directory) / "loop.mid", foundation_pattern_source="auto", foundation_performance_mode="block")
        performance = result["foundation_performance"]
        self.assertEqual(performance["mode"], "block")
        self.assertEqual(performance["selection"], "manual")
        self.assertTrue(performance["main_mode_locked"])
        self.assertLessEqual(max(performance["triggers_per_bar"]), 1)

    def test_auto_is_seeded_and_static_avoids_chop(self) -> None:
        import random
        first = select_performance_mode("ambient", "静止", "standard", random.Random(42))
        second = select_performance_mode("ambient", "静止", "standard", random.Random(42))
        self.assertEqual(first, second)
        self.assertNotIn(first[0], {"pulse", "rhythm_chop"})

    def test_pulse_and_chop_keep_fixed_event_structure(self) -> None:
        self.assertEqual(performance_events("pulse", "高能", 0), performance_events("pulse", "高能", 1))
        self.assertEqual([step for step, *_ in performance_events("rhythm_chop", "高能", 0)], [2, 7, 12])

    def test_arpeggio_is_even_five_tuplets_in_every_energy_level(self) -> None:
        expected_steps = [0.0, 3.2, 6.4, 9.6, 12.8]
        for energy in ("静止", "流动", "高能"):
            events = performance_events("arpeggio", energy, 0)
            self.assertEqual([round(event[0], 1) for event in events], expected_steps)
            self.assertEqual(len(events), 5)


if __name__ == "__main__":
    unittest.main()
