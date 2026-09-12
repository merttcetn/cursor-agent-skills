#!/usr/bin/env python3
"""Thin entry point; shared runtime lives in the repository checkout."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "shared"))
from cursor_runner import main

if __name__ == "__main__":
    raise SystemExit(main('grok'))
