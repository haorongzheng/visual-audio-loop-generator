from __future__ import annotations

import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .drum_patterns import effective_pattern_events, event_start_tick, find_matching_drum_pattern
from .foundation_midi_patterns import match_foundation_pattern
from .foundation_performance import PERFORMANCE_MODES, performance_events, performance_mode_settings, performance_selection_reason, select_performance_mode
from .bass_grooves import bass_groove_events
from .guitar_performance import guitar_events, is_guitar_instrument
from .string_performance import is_string_instrument, string_events
from .instrument_library import match_instrument
from .midi_writer import PPQ, MidiFile, MidiTrack
from .music_state_schema import ImageAnnotation, coerce_annotation
from .resolver import NOTE_TO_PC, resolve_emotion, resolve_energy, resolve_music_rules, resolve_rhythm, resolve_sound_direction
from .sample_library import resolve_sample_overlays
from .sound_sources import resolve_texture_overlays, sound_source_summary


ROOT_RE = re.compile(r"^([A-G](?:#|b)?)(.*)$")


@dataclass(frozen=True)
class ChordTone:
    interval: int
    role: str


@dataclass(frozen=True)
class Chord:
    symbol: str
    root_pc: int
    bass_pc: int
    root_note: int
    bass_note: int
    tones: tuple[ChordTone, ...]


def generate_batch(input_path: Path, output_dir: Path) -> list[Path]:
    annotations = load_annotations(input_path)
    written = []
    for index, annotation in enumerate(annotations, start=1):
        output_name = safe_name(annotation.image_id or f"loop_{index}") + ".mid"
        output_path = output_dir / output_name
        generate_loop(annotation, output_path)
        written.append(output_path)
    return written


def generate_loop(
    annotation: ImageAnnotation,
    output_path: Path,
    foundation_pattern_source: str = "auto",
    foundation_uploaded_pattern_id: str | None = None,
    preserve_uploaded_performance: bool = True,
    foundation_performance_mode: str = "block",
    override_uploaded_performance: bool = False,
    bass_source: str = "groove_modes",
    bass_groove_mode: str = "sustain_root",
    bass_groove_variant: str = "auto",
    instrument_overrides: dict[str, str] | None = None,
    guitar_performance_mode: str = "auto",
    guitar_pattern_variant: str = "auto",
    guitar_roll_amount: float = 1.0,
    string_performance_mode: str = "auto",
) -> dict[str, Any]:
    emotion = resolve_emotion(annotation.emotion)
    energy = resolve_energy(annotation.energy)
    sound = resolve_sound_direction(annotation.sound_direction)
    rhythm = resolve_rhythm(annotation.rhythm)
    bars = 8 if int(annotation.loop_length) >= 8 else 4
    rng = random.Random(stable_seed(annotation))

    midi = MidiFile(energy.bpm)
    foundation = midi.add_track("Foundation", 0, None)
    bass = midi.add_track("Bass", 1, None)
    drums = midi.add_track("Drums", 9, None)

    resolved = resolve_music_rules(annotation.emotion, annotation.energy, annotation.sound_direction, annotation.rhythm, annotation.loop_length)
    chords = expanded_chords(tuple(resolved["chord_progression"]), bars)
    uploaded_pattern, matched_tags = resolve_uploaded_foundation_pattern(annotation, bars, foundation_pattern_source, foundation_uploaded_pattern_id)
    foundation_match = match_instrument(
        annotation, "foundation", stable_seed(annotation), (instrument_overrides or {}).get("foundation") or (instrument_overrides or {}).get("Foundation"),
    )
    foundation_instrument = foundation_match.get("instrument") if foundation_match else None
    foundation_performance = write_foundation(
        foundation, chords, energy.velocity, bars, energy.variation, resolved.get("chord_note_filters"), resolved.get("chord_pitch_filters"),
        sound.value, energy.label, rhythm.value, energy.bpm, random.Random(stable_seed(annotation) ^ 0xF0A71),
        uploaded_pattern, matched_tags, preserve_uploaded_performance, foundation_performance_mode, override_uploaded_performance,
        foundation_instrument, guitar_performance_mode, guitar_pattern_variant, guitar_roll_amount, emotion.label, string_performance_mode,
    )
    bass_groove = write_bass(
        bass, chords, emotion.bass_movement, emotion.label, energy.label, energy.value, sound.value, rhythm.value,
        energy.velocity, bars, rng, energy.variation, bass_source, bass_groove_mode, bass_groove_variant,
        str(foundation_performance.get("mode", "")),
    )
    write_drums_for_state(drums, annotation, rhythm, energy.velocity, bars, rng, energy.fill_probability)
    midi.save(output_path)
    result = resolved_payload(
        annotation, foundation_performance_mode, bass_source, bass_groove_mode, bass_groove_variant,
        instrument_overrides, guitar_performance_mode, guitar_pattern_variant, guitar_roll_amount, string_performance_mode,
    )
    result["foundation_performance"] = foundation_performance
    result["audio_render"]["foundation_performance"] = foundation_performance
    result["foundation_pattern"] = foundation_performance
    result["bass_groove"] = bass_groove
    result["audio_render"]["bass_groove"] = bass_groove
    return result


def resolve_uploaded_foundation_pattern(
    annotation: ImageAnnotation, bars: int, source: str = "auto", pattern_id: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if source == "uploaded":
        return match_foundation_pattern(annotation, bars, stable_seed(annotation), pattern_id) if pattern_id else (None, [])
    return match_foundation_pattern(annotation, bars, stable_seed(annotation))


def resolved_payload(
    annotation: ImageAnnotation,
    foundation_performance_mode: str = "block",
    bass_source: str = "groove_modes",
    bass_groove_mode: str = "sustain_root",
    bass_groove_variant: str = "auto",
    instrument_overrides: dict[str, str] | None = None,
    guitar_performance_mode: str = "auto",
    guitar_pattern_variant: str = "auto",
    guitar_roll_amount: float = 1.0,
    string_performance_mode: str = "auto",
) -> dict[str, Any]:
    emotion = resolve_emotion(annotation.emotion)
    energy = resolve_energy(annotation.energy)
    sound = resolve_sound_direction(annotation.sound_direction)
    rhythm = resolve_rhythm(annotation.rhythm)
    bars = 8 if int(annotation.loop_length) >= 8 else 4
    resolved = resolve_music_rules(annotation.emotion, annotation.energy, annotation.sound_direction, annotation.rhythm, annotation.loop_length)
    sample_overlays = resolve_sample_overlays(annotation, resolved["bpm"], bars, stable_seed(annotation))
    sample_overlays.extend(resolve_texture_overlays(annotation, bars, stable_seed(annotation)))
    sound_sources = sound_source_summary(annotation)
    drum_pattern = find_matching_drum_pattern(annotation.sound_direction, annotation.energy, annotation.rhythm, bars)
    drum_rule = {
        **resolved["drum_rule"],
        "source": "Drum Pattern Admin" if drum_pattern else resolved["drum_rule"].get("source", "Rhythm + Energy"),
        "pattern_id": drum_pattern.get("pattern_id") if drum_pattern else None,
        "pattern_name": drum_pattern.get("name") if drum_pattern else None,
        "pattern_length_bars": drum_pattern.get("loop_length_bars") if drum_pattern else None,
        "effective_event_count": len(effective_pattern_events(drum_pattern, bars)) if drum_pattern else None,
        "event_count": len(drum_pattern.get("events", [])) if drum_pattern else None,
    }
    performance_mode, performance_selection = select_performance_mode(
        sound.value, energy.label, rhythm.value, random.Random(stable_seed(annotation) ^ 0xF0A71), foundation_performance_mode,
    )
    performance_settings = performance_mode_settings(performance_mode)
    foundation_match = match_instrument(
        annotation, "foundation", stable_seed(annotation), (instrument_overrides or {}).get("foundation") or (instrument_overrides or {}).get("Foundation"),
    )
    foundation_instrument = foundation_match.get("instrument") if foundation_match else None
    guitar_manifest = None
    string_manifest = None
    if is_guitar_instrument(foundation_instrument):
        _, guitar_manifest = guitar_events(
            expanded_chords(tuple(resolved["chord_progression"]), bars), bars, energy.velocity,
            str(foundation_instrument["guitar_type"]), sound.value, energy.label, rhythm.value,
            random.Random(stable_seed(annotation) ^ 0xF0A71), guitar_performance_mode, guitar_pattern_variant,
            bpm=energy.bpm, roll_amount=guitar_roll_amount, emotion=emotion.label,
        )
    elif is_string_instrument(foundation_instrument):
        _, string_manifest = string_events(
            expanded_chords(tuple(resolved["chord_progression"]), bars), bars, energy.velocity,
            sound.value, energy.label, emotion.label, random.Random(stable_seed(annotation) ^ 0x57A1),
            string_performance_mode,
        )
    foundation_manifest = string_manifest or guitar_manifest or {
        "mode": performance_mode,
        "mode_name": performance_settings["name"],
        "pattern_name": performance_settings["label"],
        "selection": performance_selection,
        "selection_source": performance_selection,
        "reason": performance_selection_reason(sound.value, energy.label, rhythm.value, performance_mode, performance_selection),
        "main_mode_locked": True,
        "bar_4_variation": performance_settings["bar4"],
        "humanize_limits": {"timing": performance_settings["timing"], "velocity": performance_settings["velocity"], "phrase": 0.05},
    }
    if bass_source == "groove_modes":
        _, bass_groove = bass_groove_events(
            [], 0, energy.velocity, sound.value, energy.label, rhythm.value, emotion.label,
            random.Random(stable_seed(annotation)), bass_groove_mode, bass_groove_variant,
            str(foundation_manifest.get("mode", "")),
        )
    else:
        bass_groove = None
    if not bass_groove:
        bass_groove = {"source": "legacy_generator", "mode": "legacy", "mode_name": "旧生成器", "variant_name": "旧 Bass 规则"}
    return {
        "loop": {"length_bars": bars, "output_type": "audio_loop", "midi_driven": True, "ppq": PPQ, "grid": "16 steps per bar"},
        "audio_render": {
            "output_type": "audio_loop",
            "midi_driven": True,
            "format": "wav",
            "loop_safe": True,
            "sample_overlays": sample_overlays,
            "sound_sources": sound_sources,
            "fx": {
                "space": resolved["audio_render_config"].get("fx_color", "room_reverb"),
                "delay": resolved["audio_render_config"].get("delay", "none"),
                "drums": "none",
            },
        },
        "music_rules": {
            "bpm": resolved["bpm"],
            "key": resolved["key"],
            "chord_progression": resolved["chord_progression"],
            "harmony_source": resolved["harmony_source"],
            "chord_palette": resolved["chord_palette"],
            "harmony_complexity": resolved["harmony_complexity"],
            "voicing_style": resolved["voicing_style"],
            "foundation_rule": resolved["foundation_rule"],
            "chord_note_filters": resolved.get("chord_note_filters", []),
            "chord_pitch_filters": resolved.get("chord_pitch_filters", []),
            "bass_rule": resolved["bass_rule"],
            "drum_rule": drum_rule,
            "audio_render_config": {**resolved["audio_render_config"], "sample_overlays": sample_overlays, "sound_sources": sound_sources},
        },
        "foundation_performance": foundation_manifest,
        "guitar_performance": guitar_manifest or {"enabled": False},
        "string_performance": string_manifest or {"enabled": False},
        "bass_groove": bass_groove,
        "resolver": {
            "emotion": {
                "label": emotion.label,
                "value": emotion.value,
                "key": resolved["key"],
                "mode": emotion.mode,
                "chord_palette": resolved["chord_palette"],
                "chord_progression": resolved["chord_progression"],
                "harmony_source": resolved["harmony_source"],
                "harmony_complexity": resolved["harmony_complexity"],
                "voicing_style": resolved["voicing_style"],
                "bass_rule": emotion.bass_movement,
                "foundation_feeling": emotion.foundation_feeling,
            },
            "energy": {
                "label": energy.label,
                "value": energy.value,
                "bpm": energy.bpm,
                "velocity": energy.velocity,
                "variation": energy.variation,
                "fill_probability": energy.fill_probability,
            },
            "sound_direction": {
                "label": sound.label,
                "value": sound.value,
                "foundation": sound.foundation,
                "bass": sound.bass,
                "drums": sound.drums,
                "fx": sound.fx,
            },
            "rhythm": {
                "label": rhythm.label,
                "value": rhythm.value,
                "kick_steps": list(rhythm.kick_steps),
                "snare_steps": list(rhythm.snare_steps),
                "hat_steps": list(rhythm.hat_steps),
                "open_hat_steps": list(rhythm.open_hat_steps),
                "percussion_steps": list(rhythm.percussion_steps),
                "fill": rhythm.fill,
            },
        },
        "tracks": ["Foundation", "Bass", "Drums"],
    }


def load_annotations(path: Path) -> list[ImageAnnotation]:
    if path.is_dir():
        items: list[ImageAnnotation] = []
        for json_file in sorted(path.glob("*.json")):
            items.extend(load_annotations(json_file))
        return items

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "images" in data:
        data = data["images"]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Input JSON must be an object, an array, or an object with an images array.")
    return [coerce_annotation(item, i) for i, item in enumerate(data, start=1)]


def choose_progression(candidates: tuple[tuple[str, ...], ...], annotation: ImageAnnotation) -> tuple[str, ...]:
    return candidates[0]


def expanded_chords(progression: tuple[str, ...], bars: int) -> list[Chord]:
    return [parse_chord_symbol(progression[bar % len(progression)]) for bar in range(bars)]


def parse_chord_symbol(symbol: str) -> Chord:
    root_symbol, slash, bass_symbol = symbol.partition("/")
    match = ROOT_RE.match(root_symbol)
    if not match:
        raise ValueError(f"Unsupported chord symbol: {symbol}")
    root_name, quality = match.groups()
    root_pc = NOTE_TO_PC[root_name]
    bass_pc = NOTE_TO_PC.get(bass_symbol, root_pc) if slash else root_pc
    return Chord(
        symbol=symbol,
        root_pc=root_pc,
        bass_pc=bass_pc,
        root_note=place_pc(root_pc, 48, 59),
        bass_note=place_pc(bass_pc, 36, 47),
        tones=chord_tones(quality),
    )


def chord_tones(quality: str) -> tuple[ChordTone, ...]:
    q = quality.replace("(", "").replace(")", "")
    is_minor = q.startswith("m") and not q.startswith("maj")
    is_sus2 = "sus2" in q
    is_sus = ("sus" in q and not is_sus2) or "sus4" in q
    third_interval = 5 if is_sus else 2 if is_sus2 else 3 if is_minor else 4
    third_role = "sus4" if is_sus else "sus2" if is_sus2 else "3"
    tones = [ChordTone(0, "root"), ChordTone(third_interval, third_role)]

    if not is_sus2:
        tones.append(ChordTone(6 if "m7b5" in q else 7, "5"))

    if "maj7" in q or "maj9" in q:
        tones.append(ChordTone(11, "7"))
    elif any(token in q for token in ("m7", "m9", "m11", "13", "7", "9sus", "7sus", "alt")):
        tones.append(ChordTone(10, "7"))

    if "6/9" in q or q == "6":
        tones.append(ChordTone(9, "6"))
    if "b9" in q:
        tones.append(ChordTone(13, "b9"))
    elif "#9" in q:
        tones.append(ChordTone(15, "#9"))
    elif any(token in q for token in ("add9", "maj9", "m9", "13", "9sus", "6/9")):
        tones.append(ChordTone(14, "9"))
    if "m11" in q:
        tones.append(ChordTone(17, "11"))
    if "#11" in q:
        tones.append(ChordTone(18, "#11"))
    if "13" in q:
        tones.append(ChordTone(21, "13"))
    if "alt" in q:
        tones.extend((ChordTone(13, "b9"), ChordTone(15, "#9"), ChordTone(18, "#11")))
    return dedupe_tones(tuple(tones))


def dedupe_tones(tones: tuple[ChordTone, ...]) -> tuple[ChordTone, ...]:
    seen: set[tuple[int, str]] = set()
    result = []
    for tone in tones:
        key = (tone.interval, tone.role)
        if key not in seen:
            seen.add(key)
            result.append(tone)
    return tuple(result)


def place_pc(pc: int, low: int, high: int) -> int:
    note = low + ((pc - low) % 12)
    while note > high:
        note -= 12
    return note


def write_foundation(
    track: MidiTrack,
    chords: list[Chord],
    velocity: int,
    bars: int,
    variation: float,
    note_filters: list[list[str] | None] | None = None,
    pitch_filters: list[list[str] | None] | None = None,
    sound_value: str = "electronic",
    energy_label: str = "流动",
    rhythm_value: str = "standard",
    bpm: int = 100,
    rng: random.Random | None = None,
    uploaded_pattern: dict[str, Any] | None = None,
    matched_tags: list[str] | None = None,
    preserve_uploaded_performance: bool = True,
    performance_mode: str = "block",
    override_uploaded_performance: bool = False,
    foundation_instrument: dict[str, Any] | None = None,
    guitar_performance_mode: str = "auto",
    guitar_pattern_variant: str = "auto",
    guitar_roll_amount: float = 1.0,
    emotion_label: str = "",
    string_performance_mode: str = "auto",
) -> dict[str, Any]:
    rng = rng or random.Random(0)
    if is_guitar_instrument(foundation_instrument):
        events, manifest = guitar_events(
            chords, bars, velocity, str(foundation_instrument["guitar_type"]), sound_value, energy_label, rhythm_value,
            rng, guitar_performance_mode, guitar_pattern_variant, bpm=bpm, roll_amount=guitar_roll_amount, emotion=emotion_label,
        )
        if manifest:
            for item in events:
                track.note(
                    int(item["pitch"]),
                    max(0, int(item["bar"]) * 4 * PPQ + step_ticks(float(item["step"])) + int(item["timing"]) + int(item.get("offset_ticks", 0))),
                    int(item["duration"]),
                    int(item["velocity"]),
                )
            return {
                "source": "guitar_single_note", "pattern_id": f"guitar_{manifest['mode']}", "pattern_name": manifest["mode_name"],
                "mode": manifest["mode"], "mode_name": manifest["mode_name"], "selection": manifest["selection_source"],
                "selection_source": manifest["selection_source"], "trigger_count": manifest["note_count"],
                "triggers_per_bar": [sum(1 for item in events if item["bar"] == bar) for bar in range(bars)],
                "guitar_performance": manifest, **manifest,
            }
    if is_string_instrument(foundation_instrument):
        events, manifest = string_events(
            chords, bars, velocity, sound_value, energy_label, emotion_label, rng, string_performance_mode,
        )
        if manifest:
            for item in events:
                track.note(
                    int(item["pitch"]),
                    max(0, int(item["bar"]) * 4 * PPQ + int(item.get("timing", 0))),
                    int(item["duration"]),
                    int(item["velocity"]),
                )
            return {
                "source": "string_foundation", "pattern_id": manifest["mode"], "pattern_name": manifest["mode_name"],
                "mode": manifest["mode"], "mode_name": manifest["mode_name"], "selection": manifest["selection_source"],
                "selection_source": manifest["selection_source"], "trigger_count": manifest["note_count"],
                "triggers_per_bar": [sum(1 for item in events if item["bar"] == bar) for bar in range(bars)],
                "string_performance": manifest, **manifest,
            }
    mode, selection = select_performance_mode(sound_value, energy_label, rhythm_value, rng, performance_mode)
    if uploaded_pattern and not override_uploaded_performance:
        result = write_uploaded_foundation(track, chords, bars, uploaded_pattern, matched_tags or [], preserve_uploaded_performance)
        result.update({"mode": mode, "mode_name": performance_mode_settings(mode)["name"], "selection": selection, "selection_source": selection, "main_mode_locked": True, "override_uploaded_performance": False, "bar_4_variation": performance_mode_settings(mode)["bar4"]})
        return result
    settings = performance_mode_settings(mode)
    timing_limit = int(18 * float(settings["timing"]))
    roll_spread_ms = int(20 * (0.05 if mode in {"pulse", "arpeggio"} else float(settings["timing"])))
    phrase_shape = []
    trigger_count = 0
    previous_notes: tuple[int, ...] | None = None
    for bar, chord in enumerate(chords[:bars]):
        role = ("statement", "variation", "development", "turnaround")[bar % 4]
        phrase_shape.append(role)
        start = bar * 4 * PPQ
        events = performance_events(mode, energy_label, bar)
        notes = foundation_voicing(chord, previous_notes)
        selected_pitches = selected_pitch_midis(pitch_filters[bar] if pitch_filters and bar < len(pitch_filters) else None)
        if selected_pitches is not None:
            notes = selected_pitches
        else:
            allowed_pcs = note_filter_pcs(note_filters[bar] if note_filters and bar < len(note_filters) else None)
            if allowed_pcs is not None:
                notes = tuple(note for note in notes if note % 12 in allowed_pcs)
        for event_index, (step, duration_steps, multiplier, note_mode) in enumerate(events):
            event_notes = foundation_mode_notes(notes, chord, note_mode, event_index)
            if not event_notes:
                continue
            trigger_count += 1
            step_tick = start + step_ticks(step)
            strong = step in {0, 4, 8, 12}
            timing_ms = rng.randint(-timing_limit, timing_limit)
            if strong:
                timing_ms = int(timing_ms * 0.35)
            timing_ticks = max(-step_ticks(step), ms_to_ticks(timing_ms, bpm))
            duration = max(20, int(step_ticks(duration_steps) * (0.9 if mode == "wide_pad" else 0.78 if mode == "block" else 0.55 if mode == "broken" else 0.35 if mode in {"pulse", "rhythm_chop"} else 0.7)))
            bar_scale = foundation_bar_velocity_scale(role, energy_label)
            if note_mode == "arp_up":
                note_duration = max(20, int(duration * .9))
                for note_index, note in enumerate(event_notes):
                    foundation_note(track, note, step_tick + timing_ticks + note_index * max(1, step_ticks(2)), note_duration, velocity, multiplier, bar_scale, note_index, len(event_notes), rng)
            elif note_mode in {"broken_up", "broken_down"}:
                note_duration = max(20, int(duration / len(event_notes) * 1.14))
                for note_index, note in enumerate(event_notes):
                    note_start = step_tick + timing_ticks + int(note_index * duration / len(event_notes))
                    foundation_note(track, note, note_start, note_duration, velocity, multiplier, bar_scale, note_index, len(event_notes), rng)
            else:
                spread_ticks = ms_to_ticks(roll_spread_ms, bpm)
                for note_index, note in enumerate(event_notes):
                    offset = int(spread_ticks * note_index / max(1, len(event_notes) - 1))
                    foundation_note(track, note, step_tick + timing_ticks + offset, duration, velocity, multiplier, bar_scale, note_index, len(event_notes), rng)
        previous_notes = notes
    return {
        "source": "foundation_performance_mode", "mode": mode, "mode_name": settings["name"], "selection": selection, "selection_source": selection, "main_mode_locked": True,
        "pattern_id": f"foundation_mode_{mode}", "pattern_name": settings["label"], "phrase_shape": phrase_shape,
        "bar_4_strategy": settings["bar4"], "roll_direction": "up" if mode == "arpeggio" else "simultaneous", "roll_spread_ms": roll_spread_ms,
        "timing_range_ms": [-timing_limit, timing_limit], "velocity_curve": [foundation_bar_velocity_scale(role, energy_label) for role in ("statement", "variation", "development", "turnaround")],
        "bar_4_variation": settings["bar4"], "triggers_per_bar": [len(performance_events(mode, energy_label, bar)) for bar in range(bars)],
        "humanize_limits": {"timing": settings["timing"], "velocity": settings["velocity"], "phrase": 0.05}, "trigger_count": trigger_count,
    }


def write_uploaded_foundation(
    track: MidiTrack,
    target_chords: list[Chord],
    bars: int,
    pattern: dict[str, Any],
    matched_tags: list[str],
    preserve_uploaded_performance: bool,
) -> dict[str, Any]:
    source_harmony = pattern.get("source_harmony", {})
    source_symbols = list(source_harmony.get("chords", []))
    try:
        source_chords = [parse_chord_symbol(symbol) for symbol in source_symbols]
    except ValueError:
        source_chords = []
    source_bars = max(1, int(pattern.get("loop_length_bars", 4) or 4))
    loop_ticks = source_bars * 4 * PPQ
    source_events = pattern.get("events", [])
    source_range = [min((int(event.get("note", 60)) for event in source_events), default=60), max((int(event.get("note", 60)) for event in source_events), default=60)]
    count = 0
    for repeat_start in range(0, bars, source_bars):
        for event in pattern.get("events", []):
            local_start = int(event.get("start_tick", 0))
            target_bar = repeat_start + local_start // (4 * PPQ)
            if target_bar >= bars:
                continue
            # Uploaded MIDI is the Foundation performance source: preserve its exact pitch register.
            pitch = max(0, min(127, int(event.get("note", 60))))
            start = repeat_start * 4 * PPQ + local_start % loop_ticks
            duration = min(max(1, int(event.get("duration_ticks", 1))), bars * 4 * PPQ - start)
            if duration <= 0:
                continue
            track.note(pitch, start, duration, max(1, min(127, int(event.get("velocity", 80)))))
            count += 1
    target_symbols = [chord.symbol for chord in target_chords[:bars]]
    return {
        "source": "uploaded_midi", "pattern_id": pattern.get("id"), "pattern_name": pattern.get("name"),
        "source_file": pattern.get("source_file", {}).get("file_name"), "source_track_index": pattern.get("source_file", {}).get("track_index"),
        "source_key": f"{source_harmony.get('key_root', 'C')} {source_harmony.get('mode', 'major')}", "source_chords": source_symbols,
        "target_chords": target_symbols, "matched_tags": matched_tags, "adaptation": "none_preserve_uploaded_midi_pitches",
        "preserve_uploaded_performance": preserve_uploaded_performance, "source_midi_range": source_range,
        "pitch_source": "uploaded_midi_exact",
        "trigger_count": count,
    }


def adapt_uploaded_pitch(note: int, source_chord: Chord, target_chord: Chord) -> int:
    transposed = note + ((target_chord.root_pc - source_chord.root_pc + 6) % 12 - 6)
    allowed_pcs = {(target_chord.root_pc + tone.interval) % 12 for tone in target_chord.tones}
    if transposed % 12 in allowed_pcs:
        return max(0, min(127, transposed))
    candidates = [candidate for candidate in range(max(0, transposed - 12), min(127, transposed + 12) + 1) if candidate % 12 in allowed_pcs]
    return min(candidates, key=lambda candidate: (abs(candidate - transposed), candidate)) if candidates else max(0, min(127, transposed))


def foundation_mode_notes(notes: tuple[int, ...], chord: Chord, mode: str, event_index: int) -> tuple[int, ...]:
    ordered = tuple(sorted(notes))
    if not ordered:
        return ()
    if mode in {"upper_chord", "split_upper"}: return ordered[len(ordered) // 2:] or ordered
    if mode == "split_lower": return ordered[:max(1, len(ordered) // 2)]
    if mode == "upper_or_full": return ordered if event_index % 2 == 0 else (ordered[1:] or ordered)
    if mode == "arp_up": return (ordered[event_index % len(ordered)],)
    if mode == "octave_support":
        support = place_pc(chord.root_pc, 48, 59)
        return tuple(sorted({support, support + 12, *(note for note in ordered if note >= 60)}))
    if mode == "wide_pad":
        wide = list(ordered)
        if len(wide) > 2: wide[-1] = min(96, wide[-1] + 12)
        if len(wide) > 3: wide[0] = max(55, wide[0] - 5)
        return tuple(sorted(set(wide)))
    if mode == "cluster":
        base = 64
        return tuple(sorted({place_pc(note % 12, base, 78) for note in ordered}))
    return ordered


def foundation_bar_velocity_scale(role: str, energy_label: str) -> float:
    values = {"statement": 1.0, "variation": 0.96, "development": 1.05, "turnaround": {"静止": 0.9, "流动": 1.04, "高能": 1.1}.get(energy_label, 1.0)}
    return values[role]


def ms_to_ticks(ms: int, bpm: int) -> int:
    return int(ms * max(1, bpm) * PPQ / 60_000)


def foundation_note(track: MidiTrack, note: int, start: int, duration: int, velocity: int, multiplier: float, bar_scale: float, index: int, total: int, rng: random.Random) -> None:
    inner = -6 + (12 * index / max(1, total - 1))
    value = int(velocity * 0.66 * multiplier * bar_scale + inner + rng.randint(-2, 2))
    track.note(note, max(0, start), max(20, duration), max(1, min(127, value)))


def note_filter_pcs(notes: list[str] | None) -> set[int] | None:
    if notes is None:
        return None
    return {NOTE_TO_PC[note] for note in notes if note in NOTE_TO_PC}


def selected_pitch_midis(notes: list[str] | None) -> tuple[int, ...] | None:
    if notes is None:
        return None
    midis = []
    for note in notes:
        pitch = pitch_name_to_midi(note)
        if pitch is not None:
            midis.append(pitch)
    return tuple(sorted(set(midis)))


def pitch_name_to_midi(note: str) -> int | None:
    match = re.match(r"^([A-G](?:#|b)?)([0-8])$", str(note).strip())
    if not match:
        return None
    name, octave = match.groups()
    if name not in NOTE_TO_PC:
        return None
    midi = (int(octave) + 1) * 12 + NOTE_TO_PC[name]
    return midi if 0 <= midi <= 127 else None


def foundation_voicing(chord: Chord, previous_notes: tuple[int, ...] | None = None) -> tuple[int, ...]:
    kept = [tone for tone in chord.tones if tone.role != "root"]
    if len(kept) > 4:
        kept = [tone for tone in kept if tone.role != "5"]
    priority = {"3": 0, "sus4": 0, "sus2": 0, "7": 1, "6": 2, "9": 3, "b9": 3, "#9": 3, "11": 4, "#11": 4, "13": 5}
    notes: list[int] = []
    for tone in sorted(kept, key=lambda item: priority.get(item.role, 6))[:4]:
        pc = (chord.root_pc + tone.interval) % 12
        if pc == chord.root_pc:
            continue
        low = 64 if tone.role in {"9", "b9", "#9", "11", "#11", "13"} else 60
        notes.append(place_pc(pc, low, 91))
    if previous_notes:
        notes = voice_lead_notes(notes, previous_notes)
    return tuple(sorted(note for note in notes if note % 12 != chord.root_pc))


def voice_lead_notes(notes: list[int], previous_notes: tuple[int, ...]) -> list[int]:
    led = []
    previous_sorted = sorted(previous_notes)
    for index, note in enumerate(sorted(notes)):
        target = previous_sorted[min(index, len(previous_sorted) - 1)]
        candidates = [note + shift for shift in (-12, 0, 12)]
        candidates = [candidate for candidate in candidates if 60 <= candidate <= 91]
        led.append(min(candidates or [note], key=lambda candidate: abs(candidate - target)))
    if tuple(sorted(led)) == tuple(sorted(notes)) and len(led) > 1:
        rotated = [led[0] + 12 if led[0] + 12 <= 91 else led[0]] + led[1:]
        return rotated
    return led


def write_bass(
    track: MidiTrack,
    chords: list[Chord],
    movement: str,
    emotion_label: str,
    energy_label: str,
    energy_value: float,
    sound_value: str,
    rhythm_value: str,
    velocity: int,
    bars: int,
    rng: random.Random,
    variation: float,
    source: str = "groove_modes",
    mode_override: str = "sustain_root",
    variant_override: str = "auto",
    foundation_mode: str = "",
) -> dict[str, Any]:
    if source == "groove_modes":
        events, manifest = bass_groove_events(
            chords, bars, velocity, sound_value, energy_label, rhythm_value, emotion_label, rng,
            mode_override, variant_override, foundation_mode,
        )
        if manifest:
            for event in events:
                track.note(event["pitch"], int(event["bar"] * 4 * PPQ + step_ticks(event["step"]) + event["timing"]), event["duration"], event["velocity"])
            return manifest
    write_bass_legacy(track, chords, movement, emotion_label, energy_label, energy_value, sound_value, velocity, bars, rng, variation)
    return {"source": "legacy_generator", "mode": "legacy", "mode_name": "Legacy Bass Generator", "main_mode_locked": True}


def write_bass_legacy(
    track: MidiTrack,
    chords: list[Chord],
    movement: str,
    emotion_label: str,
    energy_label: str,
    energy_value: float,
    sound_value: str,
    velocity: int,
    bars: int,
    rng: random.Random,
    variation: float,
) -> None:
    for bar, chord in enumerate(chords[:bars]):
        start = bar * 4 * PPQ
        bass_root = chord.bass_note
        fifth = place_pc((chord.bass_pc + 7) % 12, 36, 47)
        octave = bass_root + 12 if bass_root + 12 <= 59 else bass_root
        next_root = chords[(bar + 1) % bars].bass_note
        main_events = choose_main_bass_events(movement, emotion_label, energy_label, energy_value, bass_root, fifth, octave, next_root)
        main_steps = {event[0] for event in main_events}
        for step, pitch, duration_ticks, velocity_scale in main_events:
            track.note(
                pitch,
                start + humanized_step_ticks(step, rng, is_main=True),
                duration_ticks,
                humanized_velocity(int(velocity * velocity_scale), rng, is_main=True),
            )

        for step in choose_ghost_steps(energy_value, emotion_label, sound_value, main_steps, rng):
            pitch = choose_ghost_pitch(step, bass_root, fifth, octave, next_root, sound_value, rng)
            track.note(
                pitch,
                start + humanized_step_ticks(step, rng, is_main=False),
                rng.randint(30, 80),
                ghost_velocity(energy_value, emotion_label, sound_value, rng),
            )


def choose_main_bass_events(
    movement: str,
    emotion_label: str,
    energy_label: str,
    energy_value: float,
    root: int,
    fifth: int,
    octave: int,
    next_root: int,
) -> tuple[tuple[int, int, int, float], ...]:
    if energy_value >= 0.875 or emotion_label == "激昂":
        return (
            (0, root, step_duration(2), 0.98),
            (2, root, step_duration(1), 0.76),
            (4, root, step_duration(2), 1.0),
            (6, octave, step_duration(1), 0.76),
            (8, octave, step_duration(2), 0.94),
            (12, root, step_duration(2), 1.0),
            (14, root, step_duration(1), 0.74),
        )
    if energy_value >= 0.625:
        return (
            (0, root, step_duration(3), 0.94),
            (4, root, step_duration(2), 0.9),
            (8, octave, step_duration(3), 0.88),
            (12, root, step_duration(2), 0.92),
        )
    if energy_value >= 0.375:
        return ((0, root, step_duration(6), 0.9), (8, fifth, step_duration(5), 0.82))
    if energy_value >= 0.125:
        events = [(0, root, step_duration(8), 0.82)]
        if movement not in {"deep_roots", "long_roots"}:
            events.append((8, fifth, step_duration(4), 0.62))
        return tuple(events)
    return ((0, root, step_duration(16) - 12, 0.72),)


def choose_ghost_steps(energy_value: float, emotion_label: str, sound_value: str, main_steps: set[int], rng: random.Random) -> tuple[int, ...]:
    if energy_value < 0.125:
        return ()
    if energy_value < 0.375:
        base = rng.choice((0, 1))
    elif energy_value < 0.625:
        base = rng.randint(1, 2)
    elif energy_value < 0.875:
        base = rng.randint(2, 4)
    else:
        base = rng.randint(4, 7)
    count = round(base * emotion_ghost_multiplier(emotion_label) * sound_ghost_multiplier(sound_value))
    count = max(0, min(7, count))
    preferred = [3, 7, 11, 15, 1, 6, 10, 14]
    available = [step for step in preferred if step not in main_steps and step not in {0, 4, 8, 12}]
    if sound_value in {"ambient", "ethnic"}:
        available = [step for step in (7, 15, 11, 14) if step in available]
    rng.shuffle(available)
    return tuple(sorted(available[:count]))


def choose_ghost_pitch(step: int, root: int, fifth: int, octave: int, next_root: int, sound_value: str, rng: random.Random) -> int:
    lower_pickup = clamp_bass_pitch(next_root - 1)
    upper_pickup = clamp_bass_pitch(next_root + 1)
    diatonic = clamp_bass_pitch(root + (2 if next_root >= root else -2))
    neighbor = clamp_bass_pitch(root - 1)
    if step == 15:
        if sound_value in {"cinematic", "electronic", "vintage"}:
            return rng.choice((lower_pickup, upper_pickup, fifth))
        return rng.choice((lower_pickup, diatonic, root))
    if sound_value == "ambient":
        return rng.choice((root, fifth))
    if sound_value == "acoustic":
        return rng.choice((diatonic, fifth, lower_pickup))
    if sound_value == "organic":
        return rng.choice((diatonic, root, fifth))
    if sound_value == "vintage":
        return rng.choice((lower_pickup, upper_pickup, fifth, octave, neighbor))
    if sound_value == "electronic":
        return rng.choice((root, octave, lower_pickup))
    if sound_value == "ethnic":
        return rng.choice((root, fifth, diatonic))
    if sound_value == "cinematic":
        return rng.choice((fifth, octave, lower_pickup))
    return rng.choice((root, fifth, octave, lower_pickup))


def emotion_ghost_multiplier(label: str) -> float:
    return {
        "深沉": 0.5,
        "阴郁": 0.8,
        "忧伤": 0.6,
        "平静": 0.3,
        "温暖": 0.8,
        "明亮": 1.0,
        "欢快": 1.2,
        "激昂": 1.5,
    }.get(label, 1.0)


def sound_ghost_multiplier(value: str) -> float:
    return {
        "ambient": 0.4,
        "acoustic": 0.8,
        "organic": 0.7,
        "vintage": 1.4,
        "electronic": 1.0,
        "ethnic": 0.6,
        "cinematic": 0.8,
    }.get(value, 1.0)


def ghost_velocity(energy_value: float, emotion_label: str, sound_value: str, rng: random.Random) -> int:
    if energy_value < 0.375:
        low, high = 18, 30
    elif energy_value < 0.625:
        low, high = 25, 38
    elif energy_value < 0.875:
        low, high = 30, 45
    else:
        low, high = 35, 55
    if sound_value == "ambient":
        high = min(high, 32)
    if emotion_label in {"深沉", "平静", "忧伤"}:
        high = min(high, 38)
    return rng.randint(low, max(low, high))


def humanized_step_ticks(step: int, rng: random.Random, is_main: bool) -> int:
    amount = rng.randint(3, 12)
    if step in {0, 4, 8, 12} and is_main:
        return step_ticks(step)
    return max(0, step_ticks(step) + rng.randint(-amount, amount))


def humanized_velocity(value: int, rng: random.Random, is_main: bool) -> int:
    amount = rng.randint(5, 12)
    lower = 70 if is_main else 18
    upper = 120 if is_main else 55
    return max(lower, min(upper, value + rng.randint(-amount, amount)))


def clamp_bass_pitch(pitch: int) -> int:
    while pitch < 36:
        pitch += 12
    while pitch > 47:
        pitch -= 12
    return pitch


def step_duration(steps: int) -> int:
    return max(1, int(steps * PPQ / 4) - 8)


def write_drums(track: MidiTrack, rhythm, velocity: int, bars: int, rng: random.Random, fill_probability: float) -> None:
    for bar in range(bars):
        start = bar * 4 * PPQ
        for step in rhythm.kick_steps:
            track.note(36, start + step_ticks(step, rhythm.swing), beat_ticks(0.12), velocity)
        for step in rhythm.snare_steps:
            track.note(38, start + step_ticks(step, rhythm.swing), beat_ticks(0.12), int(velocity * 0.88))
        for step in rhythm.hat_steps:
            hat_velocity = int(velocity * (0.45 if step % 4 else 0.58))
            track.note(42, start + step_ticks(step, rhythm.swing), beat_ticks(0.08), hat_velocity)
        for step in rhythm.open_hat_steps:
            track.note(46, start + step_ticks(step, rhythm.swing), beat_ticks(0.22), int(velocity * 0.55))
        for step in rhythm.percussion_steps:
            track.note(39 if step % 2 else 70, start + step_ticks(step, rhythm.swing), beat_ticks(0.1), int(velocity * 0.56))
        if bar == bars - 1 or rng.random() < fill_probability:
            write_fill(track, start, velocity, rhythm.fill, fill_probability)


def write_drums_for_state(track: Any, annotation: ImageAnnotation, rhythm, velocity: int, bars: int, rng: random.Random, fill_probability: float) -> dict[str, Any] | None:
    pattern = find_matching_drum_pattern(annotation.sound_direction, annotation.energy, annotation.rhythm, bars)
    if not pattern:
        write_drums(track, rhythm, velocity, bars, rng, fill_probability)
        return None
    write_drum_pattern(track, pattern, bars, rng)
    return pattern


def write_drum_pattern(track: Any, pattern: dict[str, Any], bars: int, rng: random.Random) -> None:
    events = [event for event in effective_pattern_events(pattern, bars) if event.get("enabled", True)]
    if not events:
        return
    source_bars = max(1, min(8, int(pattern.get("loop_length_bars", bars) or bars)))
    repeats = max(1, (bars + source_bars - 1) // source_bars)
    humanize = pattern.get("humanize", {})
    timing_amount = max(0, min(20, int(humanize.get("timing_ticks", 0) or 0)))
    velocity_amount = max(0, min(20, int(humanize.get("velocity_amount", 0) or 0)))
    swing = pattern.get("swing", {})
    swing_amount = float(swing.get("amount", 0) or 0) if swing.get("enabled") else 0.0
    for repeat in range(repeats):
        bar_offset = repeat * source_bars
        for event in events:
            source_bar = int(event.get("bar", 1) or 1)
            target_bar = source_bar + bar_offset
            if target_bar > bars:
                continue
            if rng.random() > float(event.get("probability", 1) or 1):
                continue
            shifted_event = {**event, "bar": target_bar}
            start = event_start_tick(shifted_event)
            start += swing_ticks(shifted_event, swing_amount)
            if timing_amount:
                start += rng.randint(-timing_amount, timing_amount)
            note_velocity = int(event.get("velocity", 96) or 96)
            if velocity_amount:
                note_velocity += rng.randint(-velocity_amount, velocity_amount)
            track.note(
                int(event.get("midi_note", 36) or 36),
                max(0, start),
                max(1, int(event.get("duration_ticks", 80) or 80)),
                max(1, min(127, note_velocity)),
            )


def swing_ticks(event: dict[str, Any], amount: float) -> int:
    if amount <= 0:
        return 0
    grid = str(event.get("grid_resolution", "1/16"))
    step = int(event.get("step", 0) or 0)
    if grid not in {"1/16", "1/32"} or step % 2 == 0:
        return 0
    return int(PPQ * max(0.0, min(0.6, amount)) / 2)


def write_fill(track: MidiTrack, bar_start: int, velocity: int, fill: str, fill_probability: float) -> None:
    if fill == "none":
        return
    if fill == "light_shaker":
        for step in (12, 13, 14, 15):
            track.note(70, bar_start + step_ticks(step), beat_ticks(0.08), int(velocity * 0.42))
        return
    pitches = (38, 45, 47, 50) if fill_probability < 0.45 else (38, 41, 43, 45, 47, 50, 49)
    start_step = 12 if fill_probability < 0.45 else 8
    for i, step in enumerate(range(start_step, 16)):
        pitch = pitches[i % len(pitches)]
        track.note(pitch, bar_start + step_ticks(step), beat_ticks(0.09), int(velocity * (0.62 + i * 0.035)))


def beat_ticks(beat: float) -> int:
    return int(round(beat * PPQ))


def step_ticks(step: int, swing: float = 0.0) -> int:
    tick = int(round(step * PPQ / 4))
    if swing and step % 2 == 1:
        tick += int(PPQ * swing)
    return tick


def safe_name(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return name or "loop"


def stable_seed(annotation: ImageAnnotation) -> int:
    payload = repr(annotation).encode("utf-8")
    return int(hashlib.sha256(payload).hexdigest()[:16], 16)
