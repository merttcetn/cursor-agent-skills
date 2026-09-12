#!/usr/bin/env python3
"""Thin entry point for the Grok Cursor skill."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve()
repo_shared = HERE.parents[3] / "shared"
local_runtime = HERE.parent
runtime_dir = repo_shared if (repo_shared / "cursor_runner.py").is_file() else local_runtime
sys.path.insert(0, str(runtime_dir))
from cursor_runner import main

if __name__ == "__main__":
    raise SystemExit(main('grok'))
