"""Pytest configuration.

The project uses a `src/` layout, but we want `pytest` to work without requiring
`pip install -e .` first. We therefore prepend `<repo>/src` to `sys.path` at
collection time.

This mirrors what the development helper scripts under `scripts/` do.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-gui-contracts",
        action="store_true",
        default=False,
        help="include optional desktop GUI contract/layout tests",
    )


def pytest_configure() -> None:
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    sys.path.insert(0, str(src_path))


def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--run-gui-contracts"):
        return

    deselected = [item for item in items if "gui_contract" in item.keywords]
    if not deselected:
        return

    kept = [item for item in items if "gui_contract" not in item.keywords]
    config.hook.pytest_deselected(items=deselected)
    items[:] = kept
