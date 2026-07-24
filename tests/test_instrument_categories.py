from __future__ import annotations

import unittest

from auto_loop_midi_generator.instrument_library import CATEGORIES, normalize_instrument


class InstrumentCategoryTests(unittest.TestCase):
    def test_nylon_guitar_is_a_supported_foundation_category(self) -> None:
        self.assertIn("nylon_guitar", CATEGORIES)
        self.assertIn("ensemble_strings", CATEGORIES)
        self.assertIn("violin_section", CATEGORIES)
        self.assertIn("cello_section", CATEGORIES)
        instrument = normalize_instrument({"name": "Nylon Guitar", "track_role": "foundation", "category": "nylon_guitar"})
        self.assertEqual(instrument["category"], "nylon_guitar")

    def test_electric_guitar_infers_the_single_note_engine(self) -> None:
        instrument = normalize_instrument({"name": "Electric Guitar", "track_role": "foundation", "category": "electric_guitar"})
        self.assertEqual(instrument["performance_engine"], "guitar_single_note")
        self.assertEqual(instrument["guitar_type"], "electric")


if __name__ == "__main__":
    unittest.main()
