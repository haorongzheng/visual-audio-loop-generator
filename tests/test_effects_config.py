from __future__ import annotations

import unittest

from auto_loop_midi_generator.effects_config import default_effects, normalize_effects
from auto_loop_midi_generator.audio_renderer import apply_delay, apply_sidechain


class EffectsConfigTests(unittest.TestCase):
    def test_defaults_start_with_effects_disabled(self) -> None:
        effects = default_effects()
        self.assertFalse(effects["delay"]["enabled"])
        self.assertEqual(effects["delay"]["mix"], 0.08)
        self.assertFalse(effects["reverb"]["enabled"])
        self.assertFalse(effects["filter"]["enabled"])
        self.assertFalse(effects["sidechain"]["enabled"])

    def test_normalizer_clamps_and_rejects_unknown_filter(self) -> None:
        effects = normalize_effects({
            "delay": {"mix": 9, "beats": 0},
            "reverb": {"mix": -1, "decay": 9},
            "filter": {"mode": "unknown", "cutoff_hz": 99_999},
            "sidechain": {"amount": 9, "release_ms": 1},
        })
        self.assertEqual(effects["delay"]["mix"], 0.35)
        self.assertEqual(effects["delay"]["beats"], 0.25)
        self.assertEqual(effects["reverb"]["mix"], 0.0)
        self.assertEqual(effects["reverb"]["decay"], 0.9)
        self.assertEqual(effects["filter"]["mode"], "lowpass")
        self.assertEqual(effects["filter"]["cutoff_hz"], 18_000)
        self.assertEqual(effects["sidechain"]["amount"], 0.9)
        self.assertEqual(effects["sidechain"]["release_ms"], 30)

    def test_delay_and_sidechain_change_the_music_bus(self) -> None:
        left = [1.0] + [0.0] * 99
        right = [0.0] * 100
        apply_delay(left, right, 26_728, 1.0, 0.5)
        self.assertGreater(right[98], 0.0)

        music_left = [1.0] * 4
        music_right = [1.0] * 4
        drums_left = [1.0] + [0.0] * 3
        drums_right = [0.0] * 4
        apply_sidechain(music_left, music_right, drums_left, drums_right, 0.5, 100)
        self.assertLess(music_left[0], 1.0)


if __name__ == "__main__":
    unittest.main()
