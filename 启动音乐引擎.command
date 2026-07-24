#!/bin/zsh
cd "$(dirname "$0")"
python3 -m auto_loop_midi_generator --serve --port 8766
