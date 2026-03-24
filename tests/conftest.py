"""Pytest bootstrap for stable local-import resolution."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT_STR = str(PROJECT_ROOT)

# Ensure tests always import the `src/` package from the active worktree.
if PROJECT_ROOT_STR in sys.path:
    sys.path = [entry for entry in sys.path if entry != PROJECT_ROOT_STR]
sys.path.insert(0, PROJECT_ROOT_STR)
