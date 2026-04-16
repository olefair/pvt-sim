"""Pytest configuration and shared fixtures for PVT-SIM test suite.

Session-scoped fixtures for expensive objects (component DB, EOS instances,
phase envelopes, flash results) so that no computation is repeated across
tests. Module-scoped fixtures for objects that are only needed in specific
test files.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--run-gui-contracts",
        action="store_true",
        default=False,
        help="include optional desktop GUI contract/layout tests",
    )
    parser.addoption(
        "--run-nightly",
        action="store_true",
        default=False,
        help="include nightly/extended robustness tests in collection",
    )


def pytest_configure() -> None:
    project_root = Path(__file__).resolve().parents[1]
    src_path = project_root / "src"
    sys.path.insert(0, str(src_path))


def pytest_collection_modifyitems(config, items) -> None:
    run_gui_contracts = config.getoption("--run-gui-contracts")
    run_nightly = config.getoption("--run-nightly")

    deselected = []
    kept = []
    for item in items:
        if not run_gui_contracts and "gui_contract" in item.keywords:
            deselected.append(item)
            continue
        if not run_nightly and "nightly" in item.keywords:
            deselected.append(item)
            continue
        kept.append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = kept


# ---------------------------------------------------------------------------
# Session-scoped: component database
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def components():
    """Load the full component database once per session."""
    from pvtcore.models.component import load_components
    return load_components()


# ---------------------------------------------------------------------------
# Session-scoped: EOS instances (deterministic, safe to share)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def c1_c10_pr(components):
    """Peng-Robinson EOS for C1/C10 binary."""
    from pvtcore.eos.peng_robinson import PengRobinsonEOS
    return PengRobinsonEOS([components["C1"], components["C10"]])


@pytest.fixture(scope="session")
def c1_c4_pr(components):
    """Peng-Robinson EOS for C1/C4 binary."""
    from pvtcore.eos.peng_robinson import PengRobinsonEOS
    return PengRobinsonEOS([components["C1"], components["C4"]])


@pytest.fixture(scope="session")
def c2_c3_pr(components):
    """Peng-Robinson EOS for C2/C3 binary."""
    from pvtcore.eos.peng_robinson import PengRobinsonEOS
    return PengRobinsonEOS([components["C2"], components["C3"]])


@pytest.fixture(scope="session")
def c1_c4_c10_pr(components):
    """Peng-Robinson EOS for C1/C4/C10 ternary."""
    from pvtcore.eos.peng_robinson import PengRobinsonEOS
    return PengRobinsonEOS([components["C1"], components["C4"], components["C10"]])


# ---------------------------------------------------------------------------
# Session-scoped: phase envelopes (most expensive single computation)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def c1_c10_envelope(components, c1_c10_pr):
    """Phase envelope for C1/C10 50/50 binary — reused by all envelope tests."""
    from pvtcore.envelope.phase_envelope import calculate_phase_envelope
    z = np.array([0.5, 0.5])
    return calculate_phase_envelope(z, [components["C1"], components["C10"]], c1_c10_pr)


@pytest.fixture(scope="session")
def c1_c4_envelope(components, c1_c4_pr):
    """Phase envelope for C1/C4 50/50 binary."""
    from pvtcore.envelope.phase_envelope import calculate_phase_envelope
    z = np.array([0.5, 0.5])
    return calculate_phase_envelope(z, [components["C1"], components["C4"]], c1_c4_pr)


@pytest.fixture(scope="session")
def c2_c3_envelope(components, c2_c3_pr):
    """Phase envelope for C2/C3 50/50 binary."""
    from pvtcore.envelope.phase_envelope import calculate_phase_envelope
    z = np.array([0.5, 0.5])
    return calculate_phase_envelope(z, [components["C2"], components["C3"]], c2_c3_pr)


# ---------------------------------------------------------------------------
# Session-scoped: flash results
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def c1_c10_flash(components, c1_c10_pr):
    """PT flash for C1/C10 50/50 at 5 MPa, 350 K."""
    from pvtcore.flash.pt_flash import pt_flash
    z = np.array([0.5, 0.5])
    return pt_flash(5e6, 350.0, z, [components["C1"], components["C10"]], c1_c10_pr)


@pytest.fixture(scope="session")
def c1_c4_flash(components, c1_c4_pr):
    """PT flash for C1/C4 50/50 at 3 MPa, 250 K."""
    from pvtcore.flash.pt_flash import pt_flash
    z = np.array([0.5, 0.5])
    return pt_flash(3e6, 250.0, z, [components["C1"], components["C4"]], c1_c4_pr)
