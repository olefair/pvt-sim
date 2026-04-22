"""Thin wrapper for the PETE 665 assignment runner."""

from __future__ import annotations

import sys
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pvtcore.validation.pete665_assignment import main


if __name__ == "__main__":
    raise SystemExit(main())
