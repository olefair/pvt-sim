#!/usr/bin/env python3
"""Run the repo's phase-envelope validation lanes in a consistent order."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent


def _base_lanes() -> list[tuple[str, list[str], bool]]:
    python = sys.executable
    return [
        (
            "scalar-equation-benchmarks",
            [python, "-m", "pytest", "tests/validation/test_saturation_equation_benchmarks.py", "-q"],
            True,
        ),
        (
            "external-pure-component-saturation",
            [python, "-m", "pytest", "tests/validation/test_external_pure_component_saturation.py", "-q"],
            True,
        ),
        (
            "external-literature-vle",
            [python, "-m", "pytest", "tests/validation/test_external_literature_vle.py", "-q"],
            True,
        ),
        (
            "runtime-matrix",
            [python, "-m", "pytest", "tests/validation/test_phase_envelope_runtime_matrix.py", "-q"],
            True,
        ),
        (
            "release-gates",
            [python, "-m", "pytest", "tests/validation/test_phase_envelope_release_gates.py", "-q"],
            True,
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the canonical repo phase-envelope validation lanes. "
            "This covers deterministic/runtime/scalar signoff; DWSIM is intentionally excluded."
        )
    )
    parser.add_argument(
        "--with-thermopack",
        action="store_true",
        help="Also run the optional ThermoPack external-envelope comparison lane if the backend is installed",
    )
    parser.add_argument(
        "--with-mi-proxy",
        action="store_true",
        help="Also run the optional MI-PVT proxy comparison lane",
    )
    parser.add_argument(
        "--with-slow",
        action="store_true",
        help="Enable PVTSIM_RUN_SLOW=1 so the slow continuation release-gate cases execute",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the lane order and commands without executing them",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        help=(
            "Optional lane-name filter, for example "
            "--only release-gates or --only runtime-matrix release-gates"
        ),
    )
    args = parser.parse_args()

    lanes = _base_lanes()
    python = sys.executable

    if args.with_thermopack:
        lanes.append(
            (
                "thermopack-envelope-comparison",
                [python, "-m", "pytest", "tests/validation/test_thermopack_phase_envelope.py", "-q"],
                False,
            )
        )

    if args.with_mi_proxy:
        lanes.append(
            (
                "mi-pvt-proxy",
                [python, "-m", "pytest", "tests/validation/test_vs_mi_pvt.py", "-q"],
                False,
            )
        )

    if args.only:
        wanted = {value.strip() for value in args.only}
        lanes = [lane for lane in lanes if lane[0] in wanted]
        if not lanes:
            raise SystemExit(f"No validation lanes matched --only {sorted(wanted)}")

    if args.list:
        for lane_name, command, required in lanes:
            required_label = "required" if required else "optional"
            print(f"[{required_label}] {lane_name}: {' '.join(command)}")
        return 0

    env = os.environ.copy()
    if args.with_slow:
        env["PVTSIM_RUN_SLOW"] = "1"

    failures: list[str] = []
    for lane_name, command, required in lanes:
        print(f"\n== {lane_name} ==")
        completed = subprocess.run(command, cwd=str(REPO_ROOT), env=env)
        if completed.returncode == 0:
            continue
        label = "required" if required else "optional"
        failures.append(f"{lane_name} ({label})")
        if required:
            print(f"\nPhase-envelope signoff failed in required lane: {lane_name}")
            return completed.returncode

    if failures:
        print("\nCompleted required signoff lanes, but optional lanes failed:")
        for lane_name in failures:
            print(f"- {lane_name}")
        return 0

    print("\nPhase-envelope validation lanes completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
