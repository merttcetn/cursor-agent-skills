#!/usr/bin/env python3
"""Thin entry point for the self-contained third-party Cursor skill."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cursor_runner import main

if __name__ == "__main__":
    raise SystemExit(main('third-party'))
