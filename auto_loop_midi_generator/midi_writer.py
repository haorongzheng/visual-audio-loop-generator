from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


PPQ = 480


@dataclass(order=True)
class MidiEvent:
    tick: int
    order: int
    data: bytes = field(compare=False)


class MidiTrack:
    def __init__(self, name: str, channel: int):
        self.name = name
        self.channel = channel
        self.events: list[MidiEvent] = []
        self._order = 0

    def add_raw(self, tick: int, data: bytes) -> None:
        self.events.append(MidiEvent(max(0, int(tick)), self._order, data))
        self._order += 1

    def program_change(self, program: int, tick: int = 0) -> None:
        self.add_raw(tick, bytes([0xC0 | self.channel, program & 0x7F]))

    def note(self, pitch: int, start: int, duration: int, velocity: int) -> None:
        pitch = max(0, min(127, int(pitch)))
        velocity = max(1, min(127, int(velocity)))
        self.add_raw(start, bytes([0x90 | self.channel, pitch, velocity]))
        self.add_raw(start + max(1, int(duration)), bytes([0x80 | self.channel, pitch, 0]))


class MidiFile:
    def __init__(self, bpm: int):
        self.bpm = bpm
        self.tracks: list[MidiTrack] = []

    def add_track(self, name: str, channel: int, program: int | None = None) -> MidiTrack:
        track = MidiTrack(name, channel)
        track.add_raw(0, meta_text(0x03, name))
        if program is not None and channel != 9:
            track.program_change(program)
        self.tracks.append(track)
        return track

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        chunks = [header_chunk(len(self.tracks) + 1)]
        tempo_track = MidiTrack("Tempo", 0)
        microseconds_per_quarter = int(60_000_000 / self.bpm)
        tempo_track.add_raw(0, meta_text(0x03, "Tempo"))
        tempo_track.add_raw(0, b"\xFF\x51\x03" + microseconds_per_quarter.to_bytes(3, "big"))
        chunks.append(track_chunk(tempo_track.events))
        for track in self.tracks:
            chunks.append(track_chunk(track.events))
        path.write_bytes(b"".join(chunks))


def header_chunk(track_count: int) -> bytes:
    data = (1).to_bytes(2, "big") + track_count.to_bytes(2, "big") + PPQ.to_bytes(2, "big")
    return b"MThd" + len(data).to_bytes(4, "big") + data


def track_chunk(events: Iterable[MidiEvent]) -> bytes:
    out = bytearray()
    last_tick = 0
    for event in sorted(events):
        out.extend(var_len(event.tick - last_tick))
        out.extend(event.data)
        last_tick = event.tick
    out.extend(var_len(0))
    out.extend(b"\xFF\x2F\x00")
    return b"MTrk" + len(out).to_bytes(4, "big") + bytes(out)


def meta_text(meta_type: int, text: str) -> bytes:
    encoded = text.encode("utf-8")
    return bytes([0xFF, meta_type]) + var_len(len(encoded)) + encoded


def var_len(value: int) -> bytes:
    value = max(0, int(value))
    buffer = value & 0x7F
    while value >> 7:
        value >>= 7
        buffer <<= 8
        buffer |= ((value & 0x7F) | 0x80)
    result = bytearray()
    while True:
        result.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(result)

