from __future__ import annotations

from pathlib import Path
from typing import Any

from .generator import generate_loop
from .music_state_schema import ImageAnnotation
from .resolver import resolve_music_rules


def generate_five_track_midi(annotation: ImageAnnotation, output_path: Path) -> dict[str, Any]:
    return generate_loop(annotation, output_path)


def resolve_then_generate(annotation: ImageAnnotation, output_path: Path) -> dict[str, Any]:
    resolved = resolve_music_rules(annotation.emotion, annotation.energy, annotation.sound_direction, annotation.rhythm, annotation.loop_length)
    midi_payload = generate_five_track_midi(annotation, output_path)
    return {"resolved": resolved, "midi": midi_payload}
