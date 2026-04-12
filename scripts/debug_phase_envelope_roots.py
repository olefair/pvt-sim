"""Scan local saturation-root families for phase-envelope debugging.

This is a thin CLI wrapper around `pvtcore.envelope.local_roots`.
"""

from __future__ import annotations

import argparse
import numpy as np

from pvtcore.envelope.local_roots import scan_branch_roots
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--components",
        nargs="+",
        required=True,
        help="Component IDs as they appear in the component database, e.g. CO2 C1 C2 C3 C4",
    )
    parser.add_argument(
        "--z",
        nargs="+",
        type=float,
        required=True,
        help="Feed mole fractions matching --components",
    )
    parser.add_argument(
        "--temperatures",
        nargs="+",
        type=float,
        required=True,
        help="Temperatures in K to scan",
    )
    parser.add_argument(
        "--pressure-points",
        type=int,
        default=120,
        help="Number of log-spaced pressure samples between 1e3 and 1e8 Pa",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if len(args.components) != len(args.z):
        raise SystemExit("--components and --z must have the same length")

    z = np.asarray(args.z, dtype=float)
    if not np.isclose(float(z.sum()), 1.0, atol=1.0e-8):
        raise SystemExit(f"Composition must sum to 1.0; got {float(z.sum()):.8f}")

    component_db = load_components()
    try:
        mixture = [component_db[name] for name in args.components]
    except KeyError as exc:
        raise SystemExit(f"Unknown component: {exc.args[0]}") from exc

    eos = PengRobinsonEOS(mixture)

    print("components:", " ".join(args.components))
    print("z:", " ".join(f"{value:.6f}" for value in z))
    print()

    for temperature in args.temperatures:
        print(f"T = {float(temperature):.3f} K")
        for branch in ("bubble", "dew"):
            brackets = scan_branch_roots(
                branch=branch,
                temperature=float(temperature),
                composition=z,
                eos=eos,
                n_pressure_points=int(args.pressure_points),
            )
            print(f"  {branch}:")
            if not brackets:
                print("    no sign changes detected")
                continue
            for bracket in brackets:
                print(
                    "    "
                    f"{bracket.pressure_lo_bar:10.4f} -> {bracket.pressure_hi_bar:10.4f} bar | "
                    f"class {bracket.class_lo:+d} -> {bracket.class_hi:+d} | "
                    f"trivial {bracket.trivial_lo} -> {bracket.trivial_hi}"
                )
        print()


if __name__ == "__main__":
    main()
