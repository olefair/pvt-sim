"""Unit tests for local saturation-root scanning used by continuation work."""

from __future__ import annotations

import numpy as np

from pvtcore.envelope.local_roots import scan_branch_roots
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def test_local_root_scan_reveals_multiple_co2_rich_root_families() -> None:
    """CO2-rich fluid should show multiple local branch candidates near the top."""
    components = load_components()
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)

    bubble_roots = scan_branch_roots(
        branch="bubble",
        temperature=300.0,
        composition=z,
        eos=eos,
        n_pressure_points=120,
    )
    dew_roots = scan_branch_roots(
        branch="dew",
        temperature=300.0,
        composition=z,
        eos=eos,
        n_pressure_points=120,
    )

    assert len(bubble_roots) >= 3
    assert len(dew_roots) >= 2

    # The upper branch terminates into a trivial/coalescent state instead of a
    # clean single-root disappearance. The continuation solver will need to
    # treat that junction differently from an ordinary no-saturation failure.
    assert bubble_roots[-1].trivial_hi is True
    assert dew_roots[-1].trivial_hi is True


def test_local_root_scan_exposes_asymmetric_binary_multiple_branches() -> None:
    """Highly asymmetric binaries should expose distinct local root families."""
    components = load_components()
    mixture = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.5, 0.5], dtype=float)

    bubble_roots = scan_branch_roots(
        branch="bubble",
        temperature=440.0,
        composition=z,
        eos=eos,
        n_pressure_points=120,
    )
    dew_roots = scan_branch_roots(
        branch="dew",
        temperature=440.0,
        composition=z,
        eos=eos,
        n_pressure_points=120,
    )

    assert len(bubble_roots) >= 3
    assert len(dew_roots) >= 2

    # We expect at least one high-pressure bubble-family transition and a
    # separate low-pressure dew-family transition at the same temperature.
    assert max(root.pressure_hi_bar for root in bubble_roots) > 150.0
    assert min(root.pressure_lo_bar for root in dew_roots) < 2.0
