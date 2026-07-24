from __future__ import annotations

import argparse
from pathlib import Path

from .generator import generate_batch
from .web import run_server


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate rule-based 4/8 bar MIDI loops from image annotation JSON.")
    parser.add_argument("input", type=Path, nargs="?", help="JSON file or directory containing annotated image JSON files.")
    parser.add_argument("-o", "--output", type=Path, default=Path("output_midi"), help="Directory for generated .mid files.")
    parser.add_argument("--serve", action="store_true", help="Start the browser UI.")
    parser.add_argument("--host", default="127.0.0.1", help="Host for the browser UI.")
    parser.add_argument("--port", type=int, default=8765, help="Port for the browser UI.")
    parser.add_argument("--open", action="store_true", help="Open the browser UI automatically.")
    args = parser.parse_args()

    if args.serve:
        run_server(args.host, args.port, args.open)
        return
    if args.input is None:
        parser.error("input is required unless --serve is used.")

    written = generate_batch(args.input, args.output)
    for path in written:
        print(path)
