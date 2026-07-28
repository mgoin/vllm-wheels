#!/usr/bin/env python3
"""Compatibility wrapper for the v2 package CLI."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from vllm_wheels.cli import main


if __name__ == "__main__":
    raise SystemExit(main())
