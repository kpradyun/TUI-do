#!/usr/bin/env bash
# TUI-do launcher for macOS / Linux
# Usage: ./tuido.sh  OR  chmod +x tuido.sh && ln -s "$(pwd)/tuido.sh" ~/.local/bin/tuido

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Activate venv if present
if [[ -f "$SCRIPT_DIR/venv/bin/activate" ]]; then
    source "$SCRIPT_DIR/venv/bin/activate"
elif [[ -f "$SCRIPT_DIR/.venv/bin/activate" ]]; then
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Run via CLI entry point if installed, otherwise fall back to main.py
if command -v tuido &>/dev/null; then
    exec tuido "$@"
else
    exec python "$SCRIPT_DIR/main.py" "$@"
fi
