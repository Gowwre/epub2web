"""Compatibility wrapper for the package fidelity gate."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from epub2web.verify import main

if __name__ == "__main__":
    raise SystemExit(main())
