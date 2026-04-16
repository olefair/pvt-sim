#!/usr/bin/env python3
"""Run the extended validation surface.

This script is intentionally separate from the routine pre-merge checks. It is
the longer, more robust lane that should run on a relaxed cadence, before
release decisions, or whenever you explicitly want the full validation surface.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable


@dataclass(frozen=True)
class ValidationStep:
    """A single extended validation command."""

    name: str
    command: tuple[str, ...]


DEFAULT_STEPS = (
    ValidationStep(
        "validation-suite",
        (
            PYTHON,
            "-m",
            "pytest",
            "tests/validation",
            "-q",
        ),
    ),
    ValidationStep(
        "nightly-robustness",
        (
            PYTHON,
            "-m",
            "pytest",
            "--run-nightly",
            "tests/contracts/test_robustness.py",
            "tests/unit/test_envelope_continuation.py",
            "-q",
        ),
    ),
)


def _command_env(*, with_slow: bool) -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else src_path + os.pathsep + existing
    env.setdefault("PYTHONUTF8", "1")
    if with_slow:
        env["PVTSIM_RUN_SLOW"] = "1"
    return env


def _print_plan(*, with_slow: bool) -> None:
    print("Full validation plan")
    print("=" * 72)
    print(f"PVTSIM_RUN_SLOW={'1' if with_slow else '0'}")
    print("")
    for step in DEFAULT_STEPS:
        print(f"- {step.name}: {' '.join(step.command)}")


def _run_steps(*, with_slow: bool) -> int:
    env = _command_env(with_slow=with_slow)
    for step in DEFAULT_STEPS:
        print(f"\n== {step.name} ==")
        completed = subprocess.run(step.command, cwd=REPO_ROOT, env=env)
        if completed.returncode != 0:
            print(f"\nFull validation failed in step: {step.name}")
            return completed.returncode
    print("\nFull validation surface completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the long-form validation surface. "
            "Use this instead of the routine pre-merge checks when you want the "
            "full repo validation lane."
        )
    )
    parser.add_argument(
        "--without-slow",
        action="store_true",
        help="Skip PVTSIM_RUN_SLOW=1 so slow continuation cases stay disabled",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected commands without executing them",
    )
    args = parser.parse_args()

    with_slow = not args.without_slow
    if args.list:
        _print_plan(with_slow=with_slow)
        return 0

    return _run_steps(with_slow=with_slow)


if __name__ == "__main__":
    raise SystemExit(main())
