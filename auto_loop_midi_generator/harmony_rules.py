from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HarmonyRule:
    chord_progression: tuple[str, ...]
    harmony_complexity: str
    voicing_style: str
    chord_language: str
    chord_palette: str


SOUND_LANGUAGE = {
    "ambient": ("lo-fi jazz / ambient jazz", "maj9, m9, m11, 6/9, 13sus4", "wide_rootless_soft"),
    "acoustic": ("natural songwriter harmony", "add9, sus2, sus4, maj7, m7", "close_songwriter"),
    "organic": ("modal drone harmony", "add9, sus2, sus4, m7, open fifth", "open_modal"),
    "vintage": ("Rhodes soul / neo-soul / jazz pop", "maj9, m9, 13, 7b9, 7#9, secondary dominant", "rootless_rhodes"),
    "electronic": ("synth loop vamp", "add9, m7, maj7, sus2, sus4, m9", "compact_synth"),
    "ethnic": ("modal pentatonic drone", "sus2, sus4, add9, open fifth", "drone_open_fifth"),
    "cinematic": ("simple power harmony", "triad, add9, sus2, sus4, open fifth", "wide_power"),
}


HARMONY_RULES: dict[str, dict[str, HarmonyRule]] = {
    "deep": {
        "ambient": HarmonyRule(("Am9", "Fmaj9", "Dm11", "E13sus4"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Am(add9)", "Fsus2", "Dm7", "E7sus4"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Am(add9)", "Fsus2", "Dm7", "Esus4"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Am9", "Fmaj9", "Bm7b5", "E7(b9)"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Am9", "Fmaj7", "Dm9", "Esus4"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Asus2", "Fsus2", "Dm(add9)", "Esus4"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("Am", "F", "Dm(add9)", "Esus4"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "gloomy": {
        "ambient": HarmonyRule(("Am9", "Gmaj9", "Fmaj7(#11)", "E13sus4"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Am(add9)", "Gsus4", "Fmaj7", "E7sus4"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Asus2", "Gsus2", "Fsus2", "Esus4"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Am9", "Gmaj7", "Fmaj9", "E7#9"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Am9", "Gmaj7", "Fmaj7", "Esus4"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Asus2", "Bb(add9)", "Fsus2", "Esus4"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("Am", "Bb", "F", "Esus4"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "sad": {
        "ambient": HarmonyRule(("Am9", "Fmaj9", "Cmaj9", "G13sus4"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Am(add9)", "Fmaj7", "Csus2", "Gsus4"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Asus2", "Fadd9", "Csus2", "Gsus4"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Am9", "Dm9", "G13", "Cmaj9"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Am9", "Fmaj7", "Cmaj7", "Gsus4"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Asus2", "Fsus2", "Csus2", "Gsus4"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("Am", "F", "C(add9)", "Gsus4"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "calm": {
        "ambient": HarmonyRule(("Cmaj9", "G6/9", "Am9", "Em7"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Cadd9", "Gsus4", "Am7", "Fmaj7"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Csus2", "Gsus4", "Am7", "Fsus2"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Cmaj9", "Dm9", "G13", "C6/9"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Cadd9", "Gmaj7", "Am7", "Fsus2"), "medium", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Csus2", "Gsus2", "Asus2", "Fsus2"), "low_medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("C", "Gsus4", "Am", "Fadd9"), "low", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "warm": {
        "ambient": HarmonyRule(("Cmaj9", "Fmaj9", "Am9", "G13sus4"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Cadd9", "Fmaj7", "Am7", "Gsus4"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Csus2", "Fadd9", "Am7", "Gsus4"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Cmaj9", "E7#9", "Am9", "G13"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Cadd9", "Fmaj7", "Am9", "Gsus4"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Csus2", "Fsus2", "Asus2", "Gsus4"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("C", "Fadd9", "Am", "Gsus4"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "bright": {
        "ambient": HarmonyRule(("Cmaj9", "G13", "Am9", "Fmaj9"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Cadd9", "Gsus2", "Am7", "Fmaj7"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Csus2", "Gsus2", "Am7", "Fadd9"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Cmaj9", "D13sus4", "Fmaj9", "G13"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Cadd9", "Gmaj7", "Am9", "Fsus2"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Csus2", "Gsus2", "Asus2", "Fsus2"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("C", "Gadd9", "Am", "Fadd9"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "happy": {
        "ambient": HarmonyRule(("C6/9", "G13", "Fmaj9", "C6/9"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Cadd9", "Gsus4", "Fadd9", "Cadd9"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Csus2", "Gsus2", "Fsus2", "Cadd9"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("C6/9", "E7#9", "Am9", "G13"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Cadd9", "Gmaj7", "Fm9", "Cadd9"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Csus2", "Gsus2", "Fsus2", "Csus2"), "low_medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("C", "Gadd9", "F", "C"), "low", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
    "heroic": {
        "ambient": HarmonyRule(("Dm9", "Bbmaj9", "Fmaj9", "C13sus4"), "high", "wide_rootless_soft", *SOUND_LANGUAGE["ambient"][:2]),
        "acoustic": HarmonyRule(("Dm(add9)", "Bbadd9", "Fadd9", "Csus4"), "medium", "close_songwriter", *SOUND_LANGUAGE["acoustic"][:2]),
        "organic": HarmonyRule(("Dsus2", "Bbsus2", "Fsus2", "Csus4"), "medium", "open_modal", *SOUND_LANGUAGE["organic"][:2]),
        "vintage": HarmonyRule(("Dm9", "Gm11", "Bbmaj9", "A7alt"), "very_high", "rootless_rhodes", *SOUND_LANGUAGE["vintage"][:2]),
        "electronic": HarmonyRule(("Dm9", "Bbmaj7", "Fadd9", "Csus4"), "medium_high", "compact_synth", *SOUND_LANGUAGE["electronic"][:2]),
        "ethnic": HarmonyRule(("Dsus2", "Bbsus2", "Fsus2", "Csus2"), "medium", "drone_open_fifth", *SOUND_LANGUAGE["ethnic"][:2]),
        "cinematic": HarmonyRule(("Dm", "Bb", "Fadd9", "Csus4"), "low_medium", "wide_power", *SOUND_LANGUAGE["cinematic"][:2]),
    },
}


# The fixed emotion palette is intentionally independent of Sound Direction.
# It reuses the existing electronic-language entries as the single base for each emotion.
EMOTION_HARMONY_RULES: dict[str, HarmonyRule] = {
    emotion: directions["electronic"] for emotion, directions in HARMONY_RULES.items()
}


def get_harmony_rule(emotion_key: str, sound_key: str | None = None) -> HarmonyRule:
    return EMOTION_HARMONY_RULES.get(emotion_key, EMOTION_HARMONY_RULES["calm"])
