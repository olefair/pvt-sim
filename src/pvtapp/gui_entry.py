"""GUI entrypoint wrapper with friendly dependency errors."""

from __future__ import annotations

import importlib
import os
import sys


def _report_missing_gui_dependencies(message: str) -> None:
    """Emit a visible dependency error for both console and GUI-script launches."""
    print(message, file=sys.stderr)

    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, message, "PVT Simulator", 0x10)
        except Exception:
            # Stderr output above is the fallback if the native dialog fails.
            pass


def main() -> int:
    """Launch the GUI or print a clean dependency error."""
    try:
        gui_main = importlib.import_module("pvtapp.main").main
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.startswith("PySide6"):
            _report_missing_gui_dependencies(
                "GUI dependencies are not installed. Install them with "
                "`python -m pip install -e \".[gui]\"` and retry `pvtsim-gui`."
            )
            return 1
        raise

    return int(gui_main() or 0)
