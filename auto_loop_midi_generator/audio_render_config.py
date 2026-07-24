from __future__ import annotations

from typing import Any


def build_audio_render_config(sound, energy, harmony) -> dict[str, Any]:
    return {
        "engine": "rule_synth",
        "output": "mp3",
        "midi_driven": True,
        "sound_direction": sound.value,
        "fx_color": sound.fx,
        "chord_language": harmony.chord_language,
        "chord_palette": harmony.chord_palette,
        "harmony_complexity": harmony.harmony_complexity,
        "voicing_style": harmony.voicing_style,
        "tracks": {
            "Foundation": {"instrument": sound.foundation, "program": sound.foundation_program},
            "Bass": {"instrument": sound.bass, "program": sound.bass_program},
            "Drums": {"instrument": sound.drums, "channel": 9},
        },
        "mix": {
            "velocity": energy.velocity,
            "variation": energy.variation,
        },
    }
