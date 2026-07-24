from __future__ import annotations

import math
import random
import shutil
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .generator import (
    ImageAnnotation,
    choose_progression,
    expanded_chords,
    stable_seed,
    step_ticks,
    write_bass,
    write_drums_for_state,
    write_foundation,
)
from .midi_writer import PPQ
from .resolver import NOTE_TO_PC, resolve_emotion, resolve_energy, resolve_rhythm, resolve_sound_direction
from .resolver import resolve_music_rules
from .sample_library import convert_to_wav_if_needed, db_to_gain, resolve_sample_overlays, sample_path_from_url
from .sound_sources import build_sound_source_context, resolve_drum_source_sample, resolve_texture_overlays, resolve_tonal_source_sample, source_path_from_url
from .instrument_library import instrument_file_path, match_instrument, select_zone
from .effects_config import normalize_effects
from .mixer_config import normalize_mixer


SAMPLE_RATE = 44_100


@dataclass(frozen=True)
class RenderNote:
    track: str
    style: str
    pitch: int
    start: int
    duration: int
    velocity: int


class RenderTrack:
    def __init__(self, name: str, style: str):
        self.name = name
        self.style = style
        self.notes: list[RenderNote] = []

    def note(self, pitch: int, start: int, duration: int, velocity: int) -> None:
        self.notes.append(RenderNote(self.name, self.style, int(pitch), int(start), int(duration), int(velocity)))


def generate_audio_loop(
    annotation: ImageAnnotation,
    wav_path: Path,
    mp3_path: Path | None = None,
    render_tracks: set[str] | None = None,
    render_sample_overlays: bool = True,
    instrument_overrides: dict[str, str] | None = None,
    mixer_settings: dict[str, Any] | None = None,
    effects_settings: dict[str, Any] | None = None,
    foundation_pattern_source: str = "auto",
    foundation_uploaded_pattern_id: str | None = None,
    preserve_uploaded_performance: bool = True,
    foundation_performance_mode: str = "block",
    override_uploaded_performance: bool = False,
    bass_source: str = "groove_modes",
    bass_groove_mode: str = "sustain_root",
    bass_groove_variant: str = "auto",
    guitar_performance_mode: str = "auto",
    guitar_pattern_variant: str = "auto",
    guitar_roll_amount: float = 1.0,
    string_performance_mode: str = "auto",
) -> dict[str, Any]:
    instrument_context = build_instrument_context(annotation, stable_seed(annotation), instrument_overrides)
    foundation_instrument = (instrument_context.get("Foundation") or {}).get("instrument")
    notes, bpm, bars = collect_notes(
        annotation, render_tracks, foundation_pattern_source, foundation_uploaded_pattern_id, preserve_uploaded_performance,
        foundation_performance_mode, override_uploaded_performance, bass_source, bass_groove_mode, bass_groove_variant,
        foundation_instrument, guitar_performance_mode, guitar_pattern_variant, guitar_roll_amount, string_performance_mode,
    )
    overlays = []
    if render_sample_overlays:
        overlays = resolve_sample_overlays(annotation, bpm, bars, stable_seed(annotation))
        overlays.extend(resolve_texture_overlays(annotation, bars, stable_seed(annotation)))
    sound_source_context = build_sound_source_context(annotation, stable_seed(annotation))
    usage = render_notes_to_wav(
        notes, bpm, bars, wav_path, overlays, sound_source_context, instrument_context,
        normalize_mixer(mixer_settings), normalize_effects(effects_settings),
    )
    result = {"wav_path": str(wav_path), "instruments": usage}
    if mp3_path is not None:
        mp3_error = convert_wav_to_mp3(wav_path, mp3_path)
        if mp3_error is None:
            result["mp3_path"] = str(mp3_path)
        else:
            result["mp3_error"] = mp3_error
    return result


def collect_notes(
    annotation: ImageAnnotation,
    render_tracks: set[str] | None = None,
    foundation_pattern_source: str = "auto",
    foundation_uploaded_pattern_id: str | None = None,
    preserve_uploaded_performance: bool = True,
    foundation_performance_mode: str = "block",
    override_uploaded_performance: bool = False,
    bass_source: str = "groove_modes",
    bass_groove_mode: str = "sustain_root",
    bass_groove_variant: str = "auto",
    foundation_instrument: dict[str, Any] | None = None,
    guitar_performance_mode: str = "auto",
    guitar_pattern_variant: str = "auto",
    guitar_roll_amount: float = 1.0,
    string_performance_mode: str = "auto",
) -> tuple[list[RenderNote], int, int]:
    emotion = resolve_emotion(annotation.emotion)
    energy = resolve_energy(annotation.energy)
    sound = resolve_sound_direction(annotation.sound_direction)
    rhythm = resolve_rhythm(annotation.rhythm)
    bars = 8 if int(annotation.loop_length) >= 8 else 4
    rng = random.Random(stable_seed(annotation))
    resolved = resolve_music_rules(annotation.emotion, annotation.energy, annotation.sound_direction, annotation.rhythm, annotation.loop_length)
    chords = expanded_chords(tuple(resolved["chord_progression"]), bars)
    from .generator import resolve_uploaded_foundation_pattern
    uploaded_pattern, matched_tags = resolve_uploaded_foundation_pattern(annotation, bars, foundation_pattern_source, foundation_uploaded_pattern_id)

    foundation = RenderTrack("Foundation", sound.value)
    bass = RenderTrack("Bass", sound.value)
    drums = RenderTrack("Drums", sound.value)

    foundation_performance = write_foundation(
        foundation, chords, energy.velocity, bars, energy.variation, resolved.get("chord_note_filters"), resolved.get("chord_pitch_filters"),
        sound.value, energy.label, rhythm.value, energy.bpm, random.Random(stable_seed(annotation) ^ 0xF0A71),
        uploaded_pattern, matched_tags, preserve_uploaded_performance, foundation_performance_mode, override_uploaded_performance,
        foundation_instrument, guitar_performance_mode, guitar_pattern_variant, guitar_roll_amount, emotion.label, string_performance_mode,
    )
    write_bass(
        bass,
        chords,
        emotion.bass_movement,
        emotion.label,
        energy.label,
        energy.value,
        sound.value,
        rhythm.value,
        energy.velocity,
        bars,
        rng,
        energy.variation,
        bass_source,
        bass_groove_mode,
        bass_groove_variant,
        str(foundation_performance.get("mode", "")),
    )
    write_drums_for_state(drums, annotation, rhythm, energy.velocity, bars, rng, energy.fill_probability)
    all_notes = foundation.notes + bass.notes + drums.notes
    notes = [note for note in all_notes if render_tracks is None or note.track in render_tracks]
    return notes, energy.bpm, bars


def render_notes_to_wav(
    notes: list[RenderNote],
    bpm: int,
    bars: int,
    wav_path: Path,
    sample_overlays: list[dict[str, Any]] | None = None,
    sound_source_context: dict[str, Any] | None = None,
    instrument_context: dict[str, Any] | None = None,
    mixer: dict[str, dict[str, float]] | None = None,
    effects: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    seconds_per_tick = 60.0 / bpm / PPQ
    total_seconds = bars * 4 * 60.0 / bpm + 0.7
    samples = int(total_seconds * SAMPLE_RATE)
    music_left = [0.0] * samples
    music_right = [0.0] * samples
    drum_left = [0.0] * samples
    drum_right = [0.0] * samples
    source_cache: dict[str, tuple[list[float], list[float], int]] = {}
    active_chokes: dict[str, dict[str, Any]] = {}
    instrument_usage: dict[str, dict[str, Any]] = {}

    for note in sorted(notes, key=lambda item: item.start):
        start = int(note.start * seconds_per_tick * SAMPLE_RATE)
        target_left = drum_left if note.track == "Drums" else music_left
        target_right = drum_right if note.track == "Drums" else music_right
        if note.track in {"Foundation", "Bass"} and instrument_context:
            if mix_instrument_sample_note(target_left, target_right, start, note, seconds_per_tick, instrument_context, source_cache, instrument_usage, mixer):
                continue
        if note.track in {"Foundation", "Bass"} and sound_source_context:
            if mix_tonal_sample_note(target_left, target_right, start, note, sound_source_context, source_cache, mixer):
                continue
        if note.track == "Drums" and sound_source_context and mix_drum_sample_note(target_left, target_right, start, note, sound_source_context, source_cache, active_chokes, mixer):
            continue
        if note.track == "Drums":
            continue
        duration = max(0.04, note.duration * seconds_per_tick)
        count = min(samples - start, int(duration * SAMPLE_RATE))
        if start >= samples or count <= 0:
            continue
        velocity = max(0.0, min(1.0, note.velocity / 127.0))
        channel_gain, channel_pan = mixer_values(mixer, note.track)
        pan = max(0.0, min(1.0, track_pan(note.track, note.style, note.pitch) + channel_pan * 0.5))
        gain = track_gain(note.track, note.style) * velocity * channel_gain
        for i in range(count):
            t = i / SAMPLE_RATE
            env = envelope(t, duration, note.track, note.style)
            value = synth_sample(note.track, note.style, note.pitch, t, velocity) * env * gain
            index = start + i
            target_left[index] += value * (1.0 - pan)
            target_right[index] += value * pan

    mix_sample_overlays(music_left, music_right, bpm, bars, sample_overlays or [], mixer)
    apply_music_effects(music_left, music_right, drum_left, drum_right, bpm, normalize_effects(effects))
    soft_limit(music_left, music_right)
    left = [music_left[i] + drum_left[i] for i in range(samples)]
    right = [music_right[i] + drum_right[i] for i in range(samples)]
    normalize_linear(left, right)
    write_wav(wav_path, left, right)
    return instrument_usage


def build_instrument_context(annotation: ImageAnnotation, seed: int, overrides: dict[str, str] | None = None) -> dict[str, Any]:
    overrides = overrides or {}
    context: dict[str, Any] = {}
    for track, role in (("Foundation", "foundation"), ("Bass", "bass")):
        match = match_instrument(annotation, role, seed, str(overrides.get(role) or overrides.get(role.lower()) or "") or None)
        if match:
            context[track] = {**match, "round_robin_cursors": {}}
    return context


def velocity_curve_gain(velocity: int, curve: str) -> float:
    linear = max(0.0, min(1.0, velocity / 127.0))
    if curve == "soft":
        return linear * linear
    if curve == "hard":
        return linear ** 0.65
    return linear


def mixer_values(mixer: dict[str, dict[str, float]] | None, track: str) -> tuple[float, float]:
    item = (mixer or {}).get(track, {})
    return db_to_gain(float(item.get("gain_db", 0))), max(-1.0, min(1.0, float(item.get("pan", 0))))


def mix_instrument_sample_note(
    left: list[float], right: list[float], start: int, note: RenderNote, seconds_per_tick: float,
    instrument_context: dict[str, Any], source_cache: dict[str, tuple[list[float], list[float], int]], usage: dict[str, dict[str, Any]], mixer: dict[str, dict[str, float]] | None,
) -> bool:
    match = instrument_context.get(note.track)
    if not match:
        return False
    instrument = match["instrument"]
    playback = instrument["playback"]
    target_note = max(0, min(127, note.pitch + int(playback.get("transpose", 0))))
    zone, warning = select_zone(instrument, target_note, note.velocity, match.get("round_robin_cursors"))
    if not zone:
        return False
    file_url = str(zone.get("file_url", ""))
    try:
        if file_url not in source_cache:
            path = instrument_file_path(file_url)
            if not path.is_file():
                return False
            wav_path = convert_to_wav_if_needed(path)
            source_cache[file_url] = read_wav_float(wav_path)
            if wav_path != path:
                wav_path.unlink(missing_ok=True)
        sample_left, sample_right, sample_rate = source_cache[file_url]
    except Exception:
        return False
    gain = db_to_gain(float(playback.get("gain_db", 0)) + float(zone.get("gain_db", 0)))
    gain *= velocity_curve_gain(note.velocity, str(playback.get("velocity_curve", "linear")))
    channel_gain, channel_pan = mixer_values(mixer, note.track)
    gain *= (0.38 if note.track == "Foundation" else 0.7) * channel_gain
    pan = max(-1.0, min(1.0, float(playback.get("pan", 0)) + float(zone.get("pan", 0)) + channel_pan))
    left_gain = gain * (1.0 - max(0.0, pan))
    right_gain = gain * (1.0 + min(0.0, pan))
    attack = int(SAMPLE_RATE * max(0, int(playback.get("attack_ms", 0))) / 1000)
    release = int(SAMPLE_RATE * max(0, int(playback.get("release_ms", 0))) / 1000)
    ratio = 2 ** ((target_note - int(zone["root_midi_note"])) / 12)
    duration_samples = max(1, int(note.duration * seconds_per_tick * SAMPLE_RATE))
    mixed = mix_one_overlay(left, right, start, sample_left, sample_right, sample_rate, left_gain, right_gain, attack, release, ratio, duration_samples)
    if mixed <= 0:
        return False
    entry = usage.setdefault(note.track, {"instrument_id": instrument["id"], "instrument_name": instrument["name"], "source": "instrument_library", "matched_tags": match["matched_tags"], "sample_zones_used": [], "warnings": []})
    zone_usage = next((item for item in entry["sample_zones_used"] if item["zone_id"] == zone["id"]), None)
    if zone_usage:
        zone_usage["event_count"] += 1
    else:
        entry["sample_zones_used"].append({"zone_id": zone["id"], "root_midi_note": zone["root_midi_note"], "event_count": 1})
    if warning and warning not in entry["warnings"]:
        entry["warnings"].append(warning)
    return True


def mix_tonal_sample_note(
    left: list[float],
    right: list[float],
    start: int,
    note: RenderNote,
    sound_source_context: dict[str, Any],
    source_cache: dict[str, tuple[list[float], list[float], int]], mixer: dict[str, dict[str, float]] | None,
) -> bool:
    sample = resolve_tonal_source_sample(sound_source_context, note.track, note.pitch, note.velocity)
    if sample is None:
        return False
    file_url = str(sample.get("file_url", ""))
    if not file_url:
        return False
    try:
        if file_url not in source_cache:
            path = source_path_from_url(file_url)
            if not path.is_file():
                return False
            wav_path = convert_to_wav_if_needed(path)
            source_cache[file_url] = read_wav_float(wav_path)
            if wav_path != path:
                wav_path.unlink(missing_ok=True)
        sample_left, sample_right, sample_rate = source_cache[file_url]
    except Exception:
        return False
    velocity_gain = max(0.0, min(1.0, note.velocity / 127.0))
    channel_gain, channel_pan = mixer_values(mixer, note.track)
    gain = db_to_gain(float(sample.get("gain_db", 0))) * velocity_gain * (0.38 if note.track == "Foundation" else 0.7) * channel_gain
    pan = max(-1.0, min(1.0, float(sample.get("pan", 0)) + channel_pan))
    left_gain = gain * (1.0 - max(0.0, pan))
    right_gain = gain * (1.0 + min(0.0, pan))
    fade_in = int(SAMPLE_RATE * max(0, int(sample.get("fade_in_ms", 0))) / 1000)
    fade_out = int(SAMPLE_RATE * max(0, int(sample.get("fade_out_ms", 30))) / 1000)
    target = int(sample.get("target_midi_note", note.pitch))
    root = int(sample.get("root_midi_note", target))
    ratio = 2 ** ((target - root) / 12) if sample.get("pitch_shift_allowed", True) else 1.0
    return mix_one_overlay(left, right, start, sample_left, sample_right, sample_rate, left_gain, right_gain, fade_in, fade_out, ratio) > 0


def mix_drum_sample_note(
    left: list[float],
    right: list[float],
    start: int,
    note: RenderNote,
    sound_source_context: dict[str, Any],
    source_cache: dict[str, tuple[list[float], list[float], int]],
    active_chokes: dict[str, dict[str, Any]], mixer: dict[str, dict[str, float]] | None,
) -> bool:
    sample = resolve_drum_source_sample(sound_source_context, note.pitch, note.velocity)
    if sample is None:
        return False
    file_url = str(sample.get("file_url", ""))
    if not file_url:
        return False
    try:
        if file_url not in source_cache:
            path = source_path_from_url(file_url)
            if not path.is_file():
                return False
            wav_path = convert_to_wav_if_needed(path)
            source_cache[file_url] = read_wav_float(wav_path)
            if wav_path != path:
                wav_path.unlink(missing_ok=True)
        sample_left, sample_right, sample_rate = source_cache[file_url]
    except Exception:
        return False
    velocity_gain = max(0.0, min(1.0, note.velocity / 127.0))
    channel_gain, channel_pan = mixer_values(mixer, "Drums")
    gain = db_to_gain(float(sample.get("gain_db", -6))) * velocity_gain * channel_gain
    pan = max(-1.0, min(1.0, float(sample.get("pan", 0)) + channel_pan))
    left_gain = gain * (1.0 - max(0.0, pan))
    right_gain = gain * (1.0 + min(0.0, pan))
    fade_in = int(SAMPLE_RATE * max(0, int(sample.get("fade_in_ms", 0))) / 1000)
    fade_out = int(SAMPLE_RATE * max(0, int(sample.get("fade_out_ms", 20))) / 1000)
    choke_group = sample.get("choke_group")
    if choke_group:
        apply_choke(left, right, start, active_chokes.get(choke_group))
    mixed = mix_one_overlay(left, right, start, sample_left, sample_right, sample_rate, left_gain, right_gain, fade_in, fade_out)
    if choke_group and mixed > 0:
        active_chokes[choke_group] = {
            "start": start,
            "available": mixed,
            "sample_left": sample_left,
            "sample_right": sample_right,
            "sample_rate": sample_rate,
            "left_gain": left_gain,
            "right_gain": right_gain,
            "fade_in": fade_in,
            "fade_out": fade_out,
        }
    return mixed > 0


def apply_choke(left: list[float], right: list[float], choke_start: int, previous: dict[str, Any] | None) -> None:
    if not previous:
        return
    previous_start = int(previous["start"])
    available = int(previous["available"])
    offset = max(0, choke_start - previous_start)
    if offset >= available:
        return
    quick_fade = max(1, int(SAMPLE_RATE * 0.012))
    for i in range(offset, available):
        target = previous_start + i
        if target >= len(left):
            break
        source_index = min(len(previous["sample_left"]) - 1, int(i * previous["sample_rate"] / SAMPLE_RATE))
        old_env = overlay_env(i, available, previous["fade_in"], previous["fade_out"])
        new_env = old_env * max(0.0, 1.0 - ((i - offset) / quick_fade))
        if i - offset > quick_fade:
            new_env = 0.0
        left[target] -= previous["sample_left"][source_index] * previous["left_gain"] * old_env
        right[target] -= previous["sample_right"][source_index] * previous["right_gain"] * old_env
        left[target] += previous["sample_left"][source_index] * previous["left_gain"] * new_env
        right[target] += previous["sample_right"][source_index] * previous["right_gain"] * new_env


def mix_sample_overlays(left: list[float], right: list[float], bpm: int, bars: int, overlays: list[dict[str, Any]], mixer: dict[str, dict[str, float]] | None = None) -> None:
    if not overlays:
        return
    loop_seconds = bars * 4 * 60.0 / bpm
    for overlay in overlays:
        try:
            path = sample_path_from_url(str(overlay.get("file_url", "")))
            if not path.is_file():
                continue
            wav_path = convert_to_wav_if_needed(path)
            sample_left, sample_right, sample_rate = read_wav_float(wav_path)
            if wav_path != path:
                wav_path.unlink(missing_ok=True)
        except Exception:
            continue
        if not sample_left:
            continue
        start = overlay_start_sample(overlay, bpm, bars)
        channel_gain, channel_pan = mixer_values(mixer, "Sample")
        gain = db_to_gain(float(overlay.get("gain_db", -12))) * channel_gain
        pan = max(-1.0, min(1.0, float(overlay.get("pan", 0)) + channel_pan))
        left_gain = gain * (1.0 - max(0.0, pan))
        right_gain = gain * (1.0 + min(0.0, pan))
        fade_in = int(SAMPLE_RATE * max(0, int(overlay.get("fade_in_ms", 20))) / 1000)
        fade_out = int(SAMPLE_RATE * max(0, int(overlay.get("fade_out_ms", 80))) / 1000)
        loop_playback = overlay.get("playback_type") in {"loop", "sync_loop"} or overlay.get("trigger_mode") == "continuous"
        end_limit = min(len(left), int(loop_seconds * SAMPLE_RATE))
        cursor = start
        uses = 0
        max_uses = max(1, int(overlay.get("max_uses_per_loop", 1)))
        while cursor < end_limit and (loop_playback or uses < max_uses):
            mixed = mix_one_overlay(left, right, cursor, sample_left, sample_right, sample_rate, left_gain, right_gain, fade_in, fade_out)
            if not loop_playback or mixed <= 0:
                break
            cursor += mixed
            uses += 1


def mix_one_overlay(
    left: list[float],
    right: list[float],
    start: int,
    sample_left: list[float],
    sample_right: list[float],
    sample_rate: int,
    left_gain: float,
    right_gain: float,
    fade_in: int,
    fade_out: int,
    pitch_ratio: float = 1.0,
    max_duration_samples: int | None = None,
) -> int:
    if start >= len(left):
        return 0
    ratio = max(0.125, min(8.0, float(pitch_ratio or 1.0)))
    available = min(len(left) - start, int(len(sample_left) * SAMPLE_RATE / sample_rate / ratio))
    if max_duration_samples is not None:
        available = min(available, max(1, int(max_duration_samples)))
    if available <= 0:
        return 0
    for i in range(available):
        source_index = min(len(sample_left) - 1, int(i * sample_rate * ratio / SAMPLE_RATE))
        env = overlay_env(i, available, fade_in, fade_out)
        target = start + i
        left[target] += sample_left[source_index] * left_gain * env
        right[target] += sample_right[source_index] * right_gain * env
    return available


def overlay_env(index: int, available: int, fade_in: int, fade_out: int) -> float:
    env = 1.0
    if fade_in and index < fade_in:
        env *= index / fade_in
    if fade_out and available - index < fade_out:
        env *= max(0.0, (available - index) / fade_out)
    return env


def overlay_start_sample(overlay: dict[str, Any], bpm: int, bars: int) -> int:
    mode = str(overlay.get("trigger_mode", "on_loop_start"))
    if mode in {"on_loop_start", "continuous"}:
        bar, step = 1, 0
    elif mode == "on_fill":
        bar, step = bars, 12
    elif mode == "random_step":
        seed = sum(ord(ch) for ch in str(overlay.get("sample_id", "")))
        bar = seed % bars + 1
        step = (3, 7, 11, 15)[seed % 4]
    else:
        bar = int(overlay.get("bar", 1))
        step = int(overlay.get("step", 0))
    bar = max(1, min(bars, bar))
    step = max(0, min(15, step))
    beats = (bar - 1) * 4 + step / 4
    return int(beats * 60.0 / bpm * SAMPLE_RATE)


def read_wav_float(path: Path) -> tuple[list[float], list[float], int]:
    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        sample_rate = handle.getframerate()
        sample_width = handle.getsampwidth()
        raw = handle.readframes(handle.getnframes())
    values = pcm_to_float(raw, sample_width)
    left: list[float] = []
    right: list[float] = []
    for index in range(0, len(values), channels):
        l_sample = values[index]
        r_sample = values[index + 1] if channels > 1 and index + 1 < len(values) else l_sample
        left.append(l_sample)
        right.append(r_sample)
    return left, right, sample_rate


def pcm_to_float(raw: bytes, sample_width: int) -> list[float]:
    values: list[float] = []
    if sample_width == 1:
        return [(byte - 128) / 128 for byte in raw]
    if sample_width == 2:
        for index in range(0, len(raw), 2):
            values.append(int.from_bytes(raw[index : index + 2], "little", signed=True) / 32768)
        return values
    if sample_width == 3:
        for index in range(0, len(raw), 3):
            chunk = raw[index : index + 3] + (b"\xff" if raw[index + 2] & 0x80 else b"\x00")
            values.append(int.from_bytes(chunk, "little", signed=True) / 8388608)
        return values
    if sample_width == 4:
        for index in range(0, len(raw), 4):
            values.append(int.from_bytes(raw[index : index + 4], "little", signed=True) / 2147483648)
    return values


def synth_sample(track: str, style: str, pitch: int, t: float, velocity: float) -> float:
    if track == "Drums":
        return drum_sample(style, pitch, t, velocity)
    hz = midi_to_hz(pitch)
    if track == "Foundation":
        return foundation_sample(style, hz, t, velocity)
    if track == "Bass":
        return bass_sample(style, hz, t, velocity)
    return sine(hz, t)


def foundation_sample(style: str, hz: float, t: float, velocity: float) -> float:
    slow = 0.5 + 0.5 * sine(0.23, t)
    if style == "ambient":
        return 0.58 * sine(hz, t) + 0.26 * sine(hz * 1.5, t) + 0.16 * triangle(hz * 0.5, t)
    if style == "acoustic":
        return piano_body(hz, t) * math.exp(-t * 0.55)
    if style == "organic":
        return 0.5 * triangle(hz, t) + 0.3 * sine(hz * 2.01, t) + 0.2 * sine(hz * 3.02, t)
    if style == "vintage":
        tremolo = 0.78 + 0.22 * sine(5.1, t)
        return tremolo * (0.45 * sine(hz, t) + 0.35 * triangle(hz * 2, t) + 0.2 * sine(hz * 3, t))
    if style == "ethnic":
        return 0.48 * sine(hz, t) + 0.34 * sine(hz * 2.98, t) + 0.18 * triangle(hz * 4.02, t)
    if style == "cinematic":
        return 0.5 * saw(hz * 0.5, t) + 0.32 * saw(hz, t) + 0.18 * sine(hz * 2.01, t)
    return 0.5 * saw(hz, t) + 0.28 * square(hz * 0.5, t) + 0.22 * sine(hz * 2.01, t)


def bass_sample(style: str, hz: float, t: float, velocity: float) -> float:
    if style == "ambient":
        return 0.86 * sine(hz, t) + 0.14 * sine(hz * 2, t)
    if style == "acoustic":
        return (0.7 * triangle(hz, t) + 0.18 * sine(hz * 2, t) + 0.12 * random_noise(int(hz), t)) * math.exp(-t * 0.9)
    if style == "organic":
        return 0.62 * sine(hz, t) + 0.24 * triangle(hz * 2, t) + 0.14 * sine(hz * 3, t)
    if style == "vintage":
        return soft_clip(0.76 * sine(hz, t) + 0.3 * square(hz * 0.5, t))
    if style == "ethnic":
        return 0.72 * sine(hz * 0.5, t) + 0.2 * triangle(hz, t) + 0.08 * sine(hz * 1.5, t)
    if style == "cinematic":
        return soft_clip(0.78 * sine(hz * 0.5, t) + 0.44 * saw(hz, t))
    return soft_clip(0.64 * sine(hz, t) + 0.32 * square(hz * 0.5, t) + 0.18 * saw(hz, t))


def piano_body(hz: float, t: float) -> float:
    return 0.48 * sine(hz, t) + 0.28 * sine(hz * 2.01, t) + 0.16 * sine(hz * 3.02, t) + 0.08 * sine(hz * 4.01, t)


def drum_sample(style: str, pitch: int, t: float, velocity: float) -> float:
    noise = random_noise(pitch, t)
    if pitch == 36:
        base = 46
        sweep = 70
        freq = base + sweep * math.exp(-t * 36)
        return sine(freq, t) * math.exp(-t * 9) + 0.16 * noise * math.exp(-t * 34)
    if pitch in {38, 39}:
        return (0.6 * noise + 0.22 * sine(170, t)) * math.exp(-t * 18)
    if pitch in {42, 46, 70, 54}:
        decay = 34 if pitch != 46 else 12
        return highpass_noise(noise, t) * math.exp(-t * decay)
    if pitch == 49:
        return highpass_noise(noise, t) * math.exp(-t * 5)
    return (noise + 0.2 * sine(120 + pitch * 2, t)) * math.exp(-t * 13)


def envelope(t: float, duration: float, track: str, style: str) -> float:
    if track == "Foundation":
        attack = 0.18 if style == "ambient" else 0.12 if style == "cinematic" else 0.03 if style == "acoustic" else 0.08
        release = min(0.5 if style in {"ambient", "cinematic"} else 0.35, duration * 0.35)
    elif track == "Bass":
        attack, release = 0.006 if style in {"electronic", "cinematic"} else 0.018, min(0.12, duration * 0.35)
    elif track == "Drums":
        attack, release = 0.001, min(0.05, duration * 0.5)
    else:
        attack = 0.004 if style in {"electronic", "organic", "ethnic"} else 0.012
        release = min(0.22 if style == "ambient" else 0.16, duration * 0.45)
    if t < attack:
        return t / attack
    if t > duration - release:
        return max(0.0, (duration - t) / release)
    return 1.0


def track_gain(track: str, style: str) -> float:
    base = {
        "Foundation": 0.055,
        "Bass": 0.12,
        "Drums": 0.16,
    }.get(track, 0.08)
    style_gain = {
        "ambient": 0.82,
        "acoustic": 0.95,
        "organic": 0.9,
        "vintage": 0.88,
        "electronic": 1.08,
        "ethnic": 0.92,
        "cinematic": 1.12,
    }.get(style, 1.0)
    return base * style_gain


def track_pan(track: str, style: str, pitch: int) -> float:
    if track == "Foundation":
        return 0.44 if style == "ambient" else 0.48
    if track == "Bass":
        return 0.5
    return 0.5


def apply_music_effects(
    left: list[float],
    right: list[float],
    drum_left: list[float],
    drum_right: list[float],
    bpm: int,
    effects: dict[str, dict[str, Any]],
) -> None:
    filter_config = effects["filter"]
    if filter_config["enabled"]:
        apply_filter(left, right, filter_config["mode"], int(filter_config["cutoff_hz"]))
    reverb = effects["reverb"]
    if reverb["enabled"] and reverb["mix"] > 0:
        apply_reverb(left, right, float(reverb["mix"]), float(reverb["decay"]))
    delay = effects["delay"]
    if delay["enabled"] and delay["mix"] > 0:
        apply_delay(left, right, bpm, float(delay["beats"]), float(delay["mix"]))
    sidechain = effects["sidechain"]
    if sidechain["enabled"] and sidechain["amount"] > 0:
        apply_sidechain(left, right, drum_left, drum_right, float(sidechain["amount"]), int(sidechain["release_ms"]))


def apply_delay(left: list[float], right: list[float], bpm: int, beats: float, mix: float) -> None:
    delay = max(1, int(SAMPLE_RATE * (60 / max(1, bpm)) * beats))
    for index in range(delay, len(left)):
        # The recursive cross-feed deliberately preserves the character of the legacy master delay.
        left[index] += right[index - delay] * mix
        right[index] += left[index - delay] * mix


def apply_reverb(left: list[float], right: list[float], mix: float, decay: float) -> None:
    taps = ((29, 0.48), (43, 0.37), (67, 0.27), (101, 0.18))
    for milliseconds, gain in taps:
        delay = max(1, int(SAMPLE_RATE * milliseconds / 1000))
        amount = mix * gain * decay
        for index in range(delay, len(left)):
            left[index] += (left[index - delay] * 0.72 + right[index - delay] * 0.28) * amount
            right[index] += (right[index - delay] * 0.72 + left[index - delay] * 0.28) * amount


def apply_filter(left: list[float], right: list[float], mode: str, cutoff_hz: int) -> None:
    def lowpass(channel: list[float], cutoff: int) -> list[float]:
        alpha = 1.0 - math.exp(-2.0 * math.pi * max(20, cutoff) / SAMPLE_RATE)
        previous = 0.0
        output: list[float] = []
        for value in channel:
            previous += alpha * (value - previous)
            output.append(previous)
        return output

    def highpass(channel: list[float], cutoff: int) -> list[float]:
        alpha = math.exp(-2.0 * math.pi * max(20, cutoff) / SAMPLE_RATE)
        previous_input = 0.0
        previous_output = 0.0
        output: list[float] = []
        for value in channel:
            current = alpha * (previous_output + value - previous_input)
            output.append(current)
            previous_input = value
            previous_output = current
        return output

    if mode == "highpass":
        left[:], right[:] = highpass(left, cutoff_hz), highpass(right, cutoff_hz)
    elif mode == "bandpass":
        left[:], right[:] = lowpass(highpass(left, max(100, cutoff_hz // 3)), cutoff_hz), lowpass(highpass(right, max(100, cutoff_hz // 3)), cutoff_hz)
    elif mode == "telephone":
        left[:], right[:] = lowpass(highpass(left, 400), 3_000), lowpass(highpass(right, 400), 3_000)
    else:
        left[:], right[:] = lowpass(left, cutoff_hz), lowpass(right, cutoff_hz)


def apply_sidechain(
    left: list[float], right: list[float], drum_left: list[float], drum_right: list[float], amount: float, release_ms: int,
) -> None:
    release = math.exp(-1.0 / max(1.0, SAMPLE_RATE * release_ms / 1000))
    envelope = 0.0
    for index in range(len(left)):
        trigger = min(1.0, (abs(drum_left[index]) + abs(drum_right[index])) * 3.0)
        envelope = max(trigger, envelope * release)
        gain = 1.0 - amount * envelope
        left[index] *= gain
        right[index] *= gain


def normalize(left: list[float], right: list[float]) -> None:
    peak = max(max(abs(x) for x in left), max(abs(x) for x in right), 0.01)
    scale = min(0.96 / peak, 1.8)
    for i in range(len(left)):
        left[i] = soft_clip(left[i] * scale)
        right[i] = soft_clip(right[i] * scale)


def soft_limit(left: list[float], right: list[float]) -> None:
    peak = max(max(abs(x) for x in left), max(abs(x) for x in right), 0.01)
    scale = min(0.96 / peak, 1.8)
    for i in range(len(left)):
        left[i] = soft_clip(left[i] * scale)
        right[i] = soft_clip(right[i] * scale)


def normalize_linear(left: list[float], right: list[float]) -> None:
    peak = max(max(abs(x) for x in left), max(abs(x) for x in right), 0.01)
    scale = min(0.96 / peak, 1.8)
    for i in range(len(left)):
        left[i] *= scale
        right[i] *= scale


def write_wav(path: Path, left: list[float], right: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for l_sample, r_sample in zip(left, right):
            frames.extend(int(max(-1, min(1, l_sample)) * 32767).to_bytes(2, "little", signed=True))
            frames.extend(int(max(-1, min(1, r_sample)) * 32767).to_bytes(2, "little", signed=True))
        handle.writeframes(frames)


def convert_wav_to_mp3(wav_path: Path, mp3_path: Path) -> str | None:
    """Return an error message when no local MP3 encoder can handle the WAV."""
    mp3_path.parent.mkdir(parents=True, exist_ok=True)
    mp3_path.unlink(missing_ok=True)
    try:
        vendor = Path(__file__).resolve().parent.parent / ".vendor"
        if vendor.exists() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        import lameenc

        with wave.open(str(wav_path), "rb") as handle:
            pcm = handle.readframes(handle.getnframes())
            encoder = lameenc.Encoder()
            encoder.set_bit_rate(192)
            encoder.set_in_sample_rate(handle.getframerate())
            encoder.set_channels(handle.getnchannels())
            encoder.set_quality(2)
            mp3_data = encoder.encode(pcm) + encoder.flush()
        mp3_path.write_bytes(mp3_data)
        if mp3_path.stat().st_size > 0:
            return None
    except Exception:
        pass

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            subprocess.run(
                [ffmpeg_path, "-y", "-i", str(wav_path), "-codec:a", "libmp3lame", "-b:a", "192k", str(mp3_path)],
                check=True,
                capture_output=True,
            )
            if mp3_path.exists() and mp3_path.stat().st_size > 0:
                return None
        except (OSError, subprocess.SubprocessError):
            pass

    try:
        subprocess.run(
            ["afconvert", "-f", "MPG3", "-d", ".mp3", str(wav_path), str(mp3_path)],
            check=True,
            capture_output=True,
        )
        if mp3_path.exists() and mp3_path.stat().st_size > 0:
            return None
    except (OSError, subprocess.SubprocessError):
        pass

    mp3_path.unlink(missing_ok=True)
    return "本机 MP3 编码器不可用，已保留 WAV 供播放和下载。"


def midi_to_hz(pitch: int) -> float:
    return 440.0 * (2 ** ((pitch - 69) / 12))


def sine(freq: float, t: float) -> float:
    return math.sin(2 * math.pi * freq * t)


def saw(freq: float, t: float) -> float:
    phase = (freq * t) % 1.0
    return 2 * phase - 1


def square(freq: float, t: float) -> float:
    return 1.0 if (freq * t) % 1.0 < 0.5 else -1.0


def triangle(freq: float, t: float) -> float:
    return 2 * abs(2 * ((freq * t) % 1.0) - 1) - 1


def random_noise(seed: int, t: float) -> float:
    value = math.sin((seed * 917.31 + int(t * SAMPLE_RATE) * 12.9898) * 78.233) * 43758.5453
    return 2 * (value - math.floor(value)) - 1


def highpass_noise(noise: float, t: float) -> float:
    return noise * (0.5 + 0.5 * math.sin(2 * math.pi * 8200 * t))


def soft_clip(value: float) -> float:
    return math.tanh(value * 1.2)
