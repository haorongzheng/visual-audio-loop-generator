from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DEFAULT_LOOP_LENGTH = 4


@dataclass(frozen=True)
class ImageAnnotation:
    image_id: str
    name: str
    description: str
    tags: tuple[str, ...]
    ref_image_url: str
    emotion: str | int | float
    energy: str | int | float
    sound_direction: str
    rhythm: str
    loop_length: int
    output_type: str = "audio_loop"
    midi_driven: bool = True


def coerce_annotation(item: dict[str, Any], index: int = 1) -> ImageAnnotation:
    music_state = item.get("music_state") if isinstance(item.get("music_state"), dict) else {}
    loop = item.get("loop") if isinstance(item.get("loop"), dict) else {}
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    return ImageAnnotation(
        image_id=str(item.get("state_id") or item.get("image_id") or item.get("id") or item.get("filename") or f"loop_{index}"),
        name=str(item.get("name") or f"Loop {index}"),
        description=str(item.get("description") or ""),
        tags=tuple(str(tag) for tag in tags),
        ref_image_url=str(item.get("ref_image_url") or ""),
        emotion=nested_value(music_state, "emotion", item.get("emotion", "平静")),
        energy=nested_value(music_state, "energy", item.get("energy", "流动")),
        sound_direction=str(nested_value(music_state, "sound_direction", item.get("sound_direction") or item.get("music_style") or "electronic")),
        rhythm=str(nested_value(music_state, "rhythm", item.get("rhythm") or item.get("rhythm_grammar") or "standard")),
        loop_length=normalize_loop_length(loop.get("length_bars") or item.get("loop_length") or DEFAULT_LOOP_LENGTH),
        output_type=str(loop.get("output_type") or "audio_loop"),
        midi_driven=bool(loop.get("midi_driven", True)),
    )


def standard_json(annotation: ImageAnnotation, resolved: dict[str, Any] | None = None) -> dict[str, Any]:
    emotion = {"label": str(annotation.emotion), "value": annotation.emotion}
    energy = {"label": str(annotation.energy), "value": annotation.energy}
    sound_direction = {"label": annotation.sound_direction, "value": annotation.sound_direction}
    rhythm = {"label": annotation.rhythm, "value": annotation.rhythm}
    if resolved:
        resolver = resolved.get("resolver", {})
        emotion = {"label": resolver.get("emotion", {}).get("label", emotion["label"]), "value": resolver.get("emotion", {}).get("value", emotion["value"])}
        energy = {"label": resolver.get("energy", {}).get("label", energy["label"]), "value": resolver.get("energy", {}).get("value", energy["value"])}
        sound_direction = {
            "label": resolver.get("sound_direction", {}).get("label", sound_direction["label"]),
            "value": resolver.get("sound_direction", {}).get("value", sound_direction["value"]),
        }
        rhythm = {"label": resolver.get("rhythm", {}).get("label", rhythm["label"]), "value": resolver.get("rhythm", {}).get("value", rhythm["value"])}
    return {
        "state_id": annotation.image_id,
        "name": annotation.name,
        "description": annotation.description,
        "tags": list(annotation.tags),
        "ref_image_url": annotation.ref_image_url,
        "music_state": {
            "emotion": emotion,
            "energy": energy,
            "sound_direction": sound_direction,
            "rhythm": rhythm,
        },
        "loop": {
            "length_bars": annotation.loop_length,
            "output_type": annotation.output_type,
            "midi_driven": annotation.midi_driven,
        },
    }


def nested_value(music_state: dict[str, Any], key: str, fallback: Any) -> Any:
    value = music_state.get(key)
    if isinstance(value, dict):
        return value.get("value") if value.get("value") is not None else value.get("label", fallback)
    return value if value is not None else fallback


def normalize_loop_length(value: object) -> int:
    try:
        length = int(value)
    except (TypeError, ValueError):
        length = DEFAULT_LOOP_LENGTH
    return 8 if length >= 8 else 4
