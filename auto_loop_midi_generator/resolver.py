from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .audio_render_config import build_audio_render_config
from .harmony_rules import get_harmony_rule


NOTE_TO_PC = {
    "C": 0,
    "C#": 1,
    "Db": 1,
    "D": 2,
    "D#": 3,
    "Eb": 3,
    "E": 4,
    "F": 5,
    "F#": 6,
    "Gb": 6,
    "G": 7,
    "G#": 8,
    "Ab": 8,
    "A": 9,
    "A#": 10,
    "Bb": 10,
    "B": 11,
}


@dataclass(frozen=True)
class EmotionRule:
    label: str
    value: float
    key: str
    scale: tuple[int, ...]
    mode: str
    chord_colors: tuple[str, ...]
    progression_candidates: tuple[tuple[str, ...], ...]
    bass_movement: str
    foundation_feeling: str


@dataclass(frozen=True)
class EnergyRule:
    label: str
    value: float
    bpm: int
    velocity: int
    variation: float
    fill_probability: float


@dataclass(frozen=True)
class SoundRule:
    label: str
    value: str
    foundation: str
    bass: str
    drums: str
    fx: str
    foundation_program: int
    bass_program: int


@dataclass(frozen=True)
class RhythmRule:
    label: str
    value: str
    kick_steps: tuple[int, ...]
    snare_steps: tuple[int, ...]
    hat_steps: tuple[int, ...]
    open_hat_steps: tuple[int, ...]
    percussion_steps: tuple[int, ...]
    fill: str
    swing: float = 0.0


MAJOR = (0, 2, 4, 5, 7, 9, 11)
MINOR = (0, 2, 3, 5, 7, 8, 10)


EMOTION_RULES = {
    "deep": EmotionRule(
        "深沉", -1.0, "A", MINOR, "A minor / A harmonic minor / A aeolian",
        ("m9", "m11", "maj7(#11)", "m7b5", "7b9", "7alt"),
        (
            ("Am9", "Fmaj7(#11)", "Dm9", "E7(b9)"),
            ("Am11", "G13sus4", "Fmaj9", "E7alt"),
            ("Am(add9)", "Fmaj9", "Bm7b5", "E7(b9)"),
            ("Am9", "Dm11", "Fmaj7(#11)", "E7#9"),
        ),
        "deep_roots", "厚重、暗色、深处、有压迫感",
    ),
    "gloomy": EmotionRule(
        "阴郁", -0.75, "A", MINOR, "A minor / A phrygian color / A aeolian",
        ("m9", "m11", "maj7", "7b9", "7#9", "sus(b9)", "chromatic approach"),
        (
            ("Am9", "Gmaj7", "Fmaj7(#11)", "E7(b9)"),
            ("Am11", "Em7/G", "Fmaj9", "E7#9"),
            ("Am9", "Bbmaj7(#11)", "Fmaj7", "E7alt"),
            ("Am(add9)", "G6", "Fmaj9", "Esus4(b9)"),
        ),
        "root_fifth_chromatic", "冷、暗、压抑、不稳定",
    ),
    "sad": EmotionRule(
        "忧伤", -0.5, "A", MINOR, "A minor / C major relative minor",
        ("m7", "m9", "maj7", "maj9", "add9", "sus4", "6/9"),
        (
            ("Am9", "Fmaj9", "Cmaj9", "G13sus4"),
            ("Am7", "Dm9", "G13", "Cmaj9"),
            ("Am9", "Em7", "Fmaj9", "Gsus4(add9)"),
            ("Am(add9)", "Fmaj7", "Dm9", "E7sus4"),
        ),
        "slow_passing", "悲伤、抒情、柔软、带回忆感",
    ),
    "calm": EmotionRule(
        "平静", -0.25, "C", MAJOR, "C major / C lydian soft color",
        ("maj7", "maj9", "6/9", "m7", "m9", "sus2", "add9"),
        (
            ("Cmaj9", "G6/9", "Am9", "Em7"),
            ("C6/9", "Dm9", "G13sus4", "Cmaj9"),
            ("Cmaj7", "Fmaj9", "Em7", "Dm9"),
            ("Cadd9", "Gsus4", "Am7", "Fmaj9"),
        ),
        "long_roots", "稳定、安静、松弛、中性",
    ),
    "warm": EmotionRule(
        "温暖", 0.25, "C", MAJOR, "C major",
        ("maj7", "maj9", "6/9", "add9", "m9", "13sus4"),
        (
            ("Cmaj9", "Fmaj9", "Am9", "G13sus4"),
            ("C6/9", "Em7", "Fmaj9", "G13"),
            ("Cmaj9", "Dm9", "Fmaj7", "G13sus4"),
            ("Cadd9", "Fmaj7", "Am7", "G6/9"),
        ),
        "smooth_root_fifth", "柔和、亲近、温暖、有阳光感",
    ),
    "bright": EmotionRule(
        "明亮", 0.5, "C", MAJOR, "C major / C lydian",
        ("maj9", "maj7(#11)", "6/9", "add9", "13", "sus2"),
        (
            ("Cmaj9", "G13", "Am9", "Fmaj9"),
            ("Cmaj7(#11)", "D13sus4", "Fmaj9", "G13"),
            ("C6/9", "Em9", "Fmaj7(#11)", "G13"),
            ("Cadd9", "Gsus2", "Am9", "Fmaj9"),
        ),
        "root_fifth_octave", "清新、明亮、开放、有空气感",
    ),
    "happy": EmotionRule(
        "欢快", 0.75, "C", MAJOR, "C major",
        ("6/9", "maj9", "13", "add9", "sus4", "m9"),
        (
            ("C6/9", "G13", "Fmaj9", "C6/9"),
            ("Cmaj9", "Am9", "Dm9", "G13"),
            ("Cadd9", "G13sus4", "Am9", "Fmaj9"),
            ("C6/9", "E7#9", "Am9", "G13"),
        ),
        "short_root_fifth", "快乐、活泼、轻松、有跳动感",
    ),
    "heroic": EmotionRule(
        "激昂", 1.0, "D", MINOR, "D minor / D dorian / D cinematic minor",
        ("m9", "m11", "maj9", "7sus4", "9sus4", "13sus4", "add9", "altered dominant"),
        (
            ("Dm9", "Bbmaj9", "Fadd9", "C9sus4"),
            ("Dm11", "Bbmaj7(#11)", "F/A", "C13sus4"),
            ("Dm9", "Gm11", "Bbmaj9", "A7alt"),
            ("Dm(add9)", "Bbmaj9", "Fmaj9", "Csus4(add9)"),
        ),
        "eighth_pulse", "强烈、上升、戏剧性、燃、冲击",
    ),
}


ENERGY_RULES = {
    "still": EnergyRule("静止", 0.0, 72, 50, 0.05, 0.0),
    "flowing": EnergyRule("流动", 0.5, 98, 72, 0.36, 0.2),
    "high": EnergyRule("高能", 1.0, 130, 112, 0.82, 0.5),
}


SOUND_RULES = {
    "ambient": SoundRule("氛围", "ambient", "Air Pad", "Sub Bass", "Soft Perc", "Long Reverb / Delay", 89, 38),
    "acoustic": SoundRule("原声", "acoustic", "Piano", "Acoustic Bass", "Shaker Kit", "Room Reverb", 0, 32),
    "organic": SoundRule("自然", "organic", "Warm Pad", "Soft Bass", "Wood Percussion", "Natural Room / Gentle Reverb", 89, 34),
    "vintage": SoundRule("复古", "vintage", "Rhodes / Felt Piano", "Soft Bass", "Brush Kit", "Tape / Saturation", 4, 34),
    "electronic": SoundRule("电子", "electronic", "Synth Pad", "Synth Bass", "Electronic Kit", "Delay / Filter / Bitcrush", 90, 38),
    "ethnic": SoundRule("民族", "ethnic", "Handpan", "Drone Bass", "World Percussion", "World Room / Natural Reverb", 14, 38),
    "cinematic": SoundRule("电影", "cinematic", "Hybrid Strings", "Low Bass", "Cinematic Percussion", "Large Hall / Impact FX", 50, 38),
}


RHYTHM_RULES = {
    "sparse": RhythmRule("极简", "sparse", (0,), (), (), (), (14,), "none"),
    "flow": RhythmRule("流动", "flow", (0, 8), (12,), (0, 2, 4, 6, 8, 10, 12, 14), (), (6, 14), "light_shaker", 0.04),
    "standard": RhythmRule("标准", "standard", (0, 8), (4, 12), (0, 2, 4, 6, 8, 10, 12, 14), (), (15,), "short_fill"),
    "groove": RhythmRule("律动", "groove", (0, 3, 8, 10), (4, 12), (0, 2, 5, 6, 8, 10, 13, 14), (), (7, 15), "ghost_or_hat_roll", 0.06),
    "aggressive": RhythmRule("激烈", "aggressive", (0, 3, 4, 8, 10, 12), (4, 12), tuple(range(16)), (2, 6, 10, 14), (7, 11, 15), "required_heavy_fill"),
}


EMOTION_ALIASES = {
    "深沉": "deep",
    "阴郁": "gloomy",
    "忧伤": "sad",
    "平静": "calm",
    "温暖": "warm",
    "明亮": "bright",
    "欢快": "happy",
    "激昂": "heroic",
    "joy": "happy",
    "happy": "happy",
    "hopeful": "bright",
    "neutral": "calm",
    "melancholy": "sad",
    "tense": "gloomy",
    "angry": "heroic",
}

ENERGY_ALIASES = {
    "静止": "still",
    "平缓": "still",
    "流动": "flowing",
    "活跃": "high",
    "高能": "high",
    "low": "still",
    "medium": "flowing",
    "mid": "flowing",
    "high": "high",
    "very_high": "high",
}

SOUND_ALIASES = {
    "氛围": "ambient",
    "原声": "acoustic",
    "自然": "organic",
    "复古": "vintage",
    "电子": "electronic",
    "民族": "ethnic",
    "管弦": "cinematic",
    "orchestral": "cinematic",
    "电影": "cinematic",
    "lofi": "vintage",
    "pop": "electronic",
    "jazz": "vintage",
    "rock": "acoustic",
}

RHYTHM_ALIASES = {
    "极简": "sparse",
    "流动": "flow",
    "标准": "standard",
    "律动": "groove",
    "激烈": "aggressive",
    "straight": "standard",
    "four_on_floor": "standard",
    "house_groove": "groove",
    "edm_drive": "aggressive",
    "trap_hybrid": "flow",
    "syncopated": "groove",
    "trap": "aggressive",
    "swing": "flow",
    "latin": "groove",
}


def resolve_emotion(value: str | int | float) -> EmotionRule:
    return EMOTION_RULES[resolve_emotion_key(value)]


def resolve_emotion_key(value: str | int | float) -> str:
    if isinstance(value, (int, float)):
        if value <= -0.875:
            return "deep"
        if value <= -0.625:
            return "gloomy"
        if value <= -0.375:
            return "sad"
        if value <= 0:
            return "calm"
        if value <= 0.375:
            return "warm"
        if value <= 0.625:
            return "bright"
        if value <= 0.875:
            return "happy"
        return "heroic"
    return EMOTION_ALIASES.get(str(value).strip()) or EMOTION_ALIASES.get(normalize(value), "calm")


def resolve_energy(value: str | int | float) -> EnergyRule:
    return ENERGY_RULES[resolve_energy_key(value)]


def resolve_energy_key(value: str | int | float) -> str:
    if isinstance(value, (int, float)):
        if value <= 0.25:
            return "still"
        if value < 0.75:
            return "flowing"
        return "high"
    return ENERGY_ALIASES.get(str(value).strip()) or ENERGY_ALIASES.get(normalize(value), "flowing")


def resolve_sound_direction(value: str) -> SoundRule:
    return SOUND_RULES.get(resolve_sound_key(value), SOUND_RULES["electronic"])


def resolve_sound_key(value: str) -> str:
    return SOUND_ALIASES.get(str(value).strip()) or SOUND_ALIASES.get(normalize(value), normalize(value))


def resolve_rhythm(value: str) -> RhythmRule:
    return RHYTHM_RULES.get(resolve_rhythm_key(value), RHYTHM_RULES["standard"])


def resolve_rhythm_key(value: str) -> str:
    return RHYTHM_ALIASES.get(str(value).strip()) or RHYTHM_ALIASES.get(normalize(value), normalize(value))


def resolve_music_rules(emotion_value: str | int | float, energy_value: str | int | float, sound_value: str, rhythm_value: str, length_bars: int) -> dict[str, Any]:
    emotion_key = resolve_emotion_key(emotion_value)
    energy_key = resolve_energy_key(energy_value)
    sound_key = resolve_sound_key(sound_value)
    rhythm_key = resolve_rhythm_key(rhythm_value)
    emotion = EMOTION_RULES[emotion_key]
    energy = ENERGY_RULES[energy_key]
    sound = SOUND_RULES.get(sound_key, SOUND_RULES["electronic"])
    rhythm = RHYTHM_RULES.get(rhythm_key, RHYTHM_RULES["standard"])
    harmony = get_harmony_rule(emotion_key)
    bars = 8 if int(length_bars) >= 8 else 4
    # Harmony is a fixed four-bar emotion loop. Eight-bar output repeats it exactly.
    manual_rule = find_manual_harmony_rule_safe(emotion.label, 4)
    if manual_rule:
        base_progression = [item["chord"] for item in manual_rule["chords"]][:4]
        base_note_filters = [item.get("allowed_notes") for item in manual_rule["chords"]][:4]
        base_pitch_filters = [item.get("selected_notes") for item in manual_rule["chords"]][:4]
        harmony_source = "manual_admin"
        voicing_style = manual_rule.get("voicing_style") or harmony.voicing_style
    else:
        base_progression = list(harmony.chord_progression)[:4]
        base_note_filters = [None for _ in base_progression]
        base_pitch_filters = [None for _ in base_progression]
        harmony_source = "default_fallback"
        voicing_style = harmony.voicing_style
    chord_progression = repeat_four_bar_harmony(base_progression, bars)
    chord_note_filters = repeat_four_bar_harmony(base_note_filters, bars)
    chord_pitch_filters = repeat_four_bar_harmony(base_pitch_filters, bars)
    audio_config = build_audio_render_config(sound, energy, harmony)
    return {
        "bpm": energy.bpm,
        "key": f"{emotion.key} {'minor' if emotion.scale[2] == 3 else 'major'}",
        "mode": emotion.mode,
        "chord_progression": chord_progression,
        "chord_note_filters": chord_note_filters,
        "chord_pitch_filters": chord_pitch_filters,
        "harmony_source": harmony_source,
        "chord_palette": harmony.chord_palette,
        "harmony_complexity": harmony.harmony_complexity,
        "voicing_style": voicing_style,
        "foundation_rule": {
            "source": "Emotion",
            "instrument": sound.foundation,
            "voicing_style": voicing_style,
            "omit_root_when_bass_plays_root": True,
            "rootless": True,
            "octave_shift": "+12",
            "inversion_rule": "voice-led inversions between chords",
            "note_filters": chord_note_filters,
            "pitch_filters": chord_pitch_filters,
        },
        "bass_rule": {
            "source": "Emotion + Chord Progression",
            "movement": emotion.bass_movement,
            "range": "C1-B2",
            "allowed_tones": ["root", "fifth", "octave", "passing", "ghost", "pickup", "pedal_pulse"],
        },
        "drum_rule": {
            "source": "Rhythm + Energy",
            "rhythm": rhythm.value,
            "kick_steps": list(rhythm.kick_steps),
            "snare_steps": list(rhythm.snare_steps),
            "hat_steps": list(rhythm.hat_steps),
            "percussion_steps": list(rhythm.percussion_steps),
            "fill_probability": energy.fill_probability,
        },
        "audio_render_config": audio_config,
        "loop": {
            "length_bars": bars,
            "time_signature": "4/4",
            "ppq": 480,
            "grid": "16 steps per bar",
        },
        "tags": {
            "emotion": {"key": emotion_key, "label": emotion.label, "value": emotion.value},
            "energy": {"key": energy_key, "label": energy.label, "value": energy.value},
            "sound_direction": {"key": sound.value, "label": sound.label, "value": sound.value},
            "rhythm": {"key": rhythm.value, "label": rhythm.label, "value": rhythm.value},
        },
    }


def find_manual_harmony_rule_safe(emotion_value: str, length_bars: int) -> dict[str, Any] | None:
    try:
        from .harmony_admin import find_manual_harmony_rule

        return find_manual_harmony_rule(emotion_value, length_bars)
    except Exception:
        return None


def repeat_four_bar_harmony(values: list[Any], bars: int) -> list[Any]:
    base = list(values[:4])
    if not base:
        return []
    return [base[index % len(base)] for index in range(bars)]


def normalize(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")
