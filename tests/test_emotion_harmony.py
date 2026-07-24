from __future__ import annotations

import unittest

from auto_loop_midi_generator.resolver import resolve_music_rules


class EmotionHarmonyTests(unittest.TestCase):
    def test_every_emotion_uses_one_progression_across_sound_directions(self) -> None:
        emotions = ("深沉", "阴郁", "忧伤", "平静", "温暖", "明亮", "欢快", "激昂")
        for emotion in emotions:
            ambient = resolve_music_rules(emotion, "流动", "ambient", "standard", 4)["chord_progression"]
            electronic = resolve_music_rules(emotion, "流动", "electronic", "standard", 4)["chord_progression"]
            cinematic = resolve_music_rules(emotion, "流动", "cinematic", "standard", 4)["chord_progression"]
            self.assertEqual(ambient, electronic, emotion)
            self.assertEqual(electronic, cinematic, emotion)

    def test_eight_bars_repeats_the_first_four_bars_exactly(self) -> None:
        progression = resolve_music_rules("温暖", "流动", "ambient", "standard", 8)["chord_progression"]
        self.assertEqual(len(progression), 8)
        self.assertEqual(progression[:4], progression[4:])


if __name__ == "__main__":
    unittest.main()
