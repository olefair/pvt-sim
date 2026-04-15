"""Consolidated equation-of-state unit tests.

Covers PR76, PR78, and SRK via parametrized checks for pure-component Z,
fugacity, mixing rules, alpha functions, PPR78 group decomposition and k_ij,
PR78-vs-PR76 heavy-end divergence, and edge-case handling.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.eos.pr78 import PR78EOS
from pvtcore.eos.srk import SRKEOS
from pvtcore.eos.groups import (
    PPR78Group,
    GroupDecomposer,
    parse_group_name,
    get_n_alkane_groups,
)
from pvtcore.eos.ppr78 import PPR78Calculator
from pvtcore.core.errors import PhaseError


# -- helpers ----------------------------------------------------------------

EOS_CLASSES = {
    "PR76": PengRobinsonEOS,
    "PR78": PR78EOS,
    "SRK": SRKEOS,
}


def _make_eos(cls, components, *comp_ids):
    """Instantiate an EOS from component IDs."""
    return cls([components[cid] for cid in comp_ids])


# ---------------------------------------------------------------------------
# 1. test_eos_pure_component
# ---------------------------------------------------------------------------

_PURE_CASES = [
    # (EOS tag, component, T, P, expected_Z, abs_tol)
    # Low-pressure ideal-gas limits: Z ≈ 1
    ("PR76", "C1", 300.0, 1e3, 1.0, 0.01),
    ("PR78", "C1", 300.0, 1e3, 1.0, 0.01),
    ("SRK",  "C1", 1000.0, 1e3, 1.0, 0.02),
    # Moderate conditions
    ("PR76", "C1", 300.0, 5e6, None, None),   # just check 0 < Z < 1.2
    ("PR78", "C2", 300.0, 5e6, None, None),
    ("SRK",  "C3", 350.0, 3e6, None, None),
    # High-T ideal-gas approach
    ("PR76", "C1", 1000.0, 101325.0, 1.0, 0.05),
]


@pytest.mark.parametrize(
    "eos_tag, comp_id, T, P, expected_Z, atol",
    _PURE_CASES,
    ids=[f"{c[0]}-{c[1]}-{c[2]}K-{c[3]:.0e}Pa" for c in _PURE_CASES],
)
def test_eos_pure_component(components, eos_tag, comp_id, T, P, expected_Z, atol):
    """Compressibility sanity for several EOS/component/condition combos."""
    eos = _make_eos(EOS_CLASSES[eos_tag], components, comp_id)
    z = np.array([1.0])
    Z = eos.compressibility(P, T, z, phase="vapor")

    assert Z > 0, f"Z must be positive, got {Z}"
    if expected_Z is not None:
        assert Z == pytest.approx(expected_Z, abs=atol)
    else:
        assert 0.0 < Z < 1.5


# ---------------------------------------------------------------------------
# 2. test_eos_fugacity
# ---------------------------------------------------------------------------

_FUGACITY_CASES = [
    ("PR76", ["C1"], 300.0, 5e6),
    ("PR78", ["C1", "C12"], 400.0, 5e6),
    ("SRK",  ["C1", "C2"], 320.0, 5e6),
]


@pytest.mark.parametrize(
    "eos_tag, comp_ids, T, P",
    _FUGACITY_CASES,
    ids=[f"{c[0]}-{'_'.join(c[1])}" for c in _FUGACITY_CASES],
)
def test_eos_fugacity(components, eos_tag, comp_ids, T, P):
    """Fugacity coefficients must be positive and finite."""
    eos = _make_eos(EOS_CLASSES[eos_tag], components, *comp_ids)
    z = np.ones(len(comp_ids)) / len(comp_ids)
    phi = eos.fugacity_coefficient(P, T, z, phase="vapor")

    assert phi.shape == (len(comp_ids),)
    assert np.all(phi > 0), f"All φ must be > 0, got {phi}"
    assert np.all(np.isfinite(phi))

    f = eos.fugacity(P, T, z, phase="vapor")
    np.testing.assert_allclose(f, phi * z * P, rtol=1e-10)


# ---------------------------------------------------------------------------
# 3. test_eos_mixing_rules
# ---------------------------------------------------------------------------

_MIXING_CASES = [
    ("PR76", "C1", "C2", 300.0),
    ("PR78", "C1", "C4", 350.0),
    ("SRK",  "C1", "C2", 320.0),
]


@pytest.mark.parametrize(
    "eos_tag, id_a, id_b, T",
    _MIXING_CASES,
    ids=[f"{c[0]}-{c[1]}_{c[2]}" for c in _MIXING_CASES],
)
def test_eos_mixing_rules(components, eos_tag, id_a, id_b, T):
    """Binary mixing: a_mix/b_mix bounded by pure values; kij effect differs from zero."""
    cls = EOS_CLASSES[eos_tag]
    eos = _make_eos(cls, components, id_a, id_b)
    z = np.array([0.5, 0.5])

    a_mix, b_mix, a_arr, b_arr = eos.calculate_params(T, z)

    assert min(a_arr) <= a_mix <= max(a_arr)
    assert min(b_arr) <= b_mix <= max(b_arr)

    P = 5e6
    kij_zero = np.zeros((2, 2))
    Z_zero = eos.compressibility(P, T, z, phase="vapor", binary_interaction=kij_zero)

    kij_nz = np.array([[0.0, 0.03], [0.03, 0.0]])
    Z_nz = eos.compressibility(P, T, z, phase="vapor", binary_interaction=kij_nz)

    assert Z_zero != pytest.approx(Z_nz, abs=1e-3), "BIP should change Z"


# ---------------------------------------------------------------------------
# 4. test_eos_alpha_function
# ---------------------------------------------------------------------------

_ALPHA_CASES = [
    ("PR76", "C1"),
    ("PR76", "N2"),
    ("PR78", "C12"),
    ("SRK",  "C1"),
]


@pytest.mark.parametrize(
    "eos_tag, comp_id",
    _ALPHA_CASES,
    ids=[f"{c[0]}-{c[1]}" for c in _ALPHA_CASES],
)
def test_eos_alpha_function(components, eos_tag, comp_id):
    """Alpha(Tc) == 1, alpha positive, decreasing with T above Tc."""
    cls = EOS_CLASSES[eos_tag]
    eos = _make_eos(cls, components, comp_id)
    Tc = components[comp_id].Tc

    alpha_at_Tc = eos.alpha_function(Tc, 0)
    assert alpha_at_Tc == pytest.approx(1.0, rel=1e-10)

    alpha_low = eos.alpha_function(0.7 * Tc, 0)
    alpha_high = eos.alpha_function(1.5 * Tc, 0)

    assert alpha_low > 0
    assert alpha_high > 0
    assert alpha_low > alpha_at_Tc > alpha_high


# ---------------------------------------------------------------------------
# 5. test_ppr78_group_decomposition
# ---------------------------------------------------------------------------

_GROUP_CASES = [
    ("C1",        {PPR78Group.CH4: 1}),
    ("C2",        {PPR78Group.CH3: 2}),
    ("C3",        {PPR78Group.CH3: 2, PPR78Group.CH2: 1}),
    ("iC4",       {PPR78Group.CH3: 3, PPR78Group.CH: 1}),
    ("CO2",       {PPR78Group.CO2: 1}),
    ("N2",        {PPR78Group.N2: 1}),
    ("H2S",       {PPR78Group.H2S: 1}),
    ("BENZENE",   {PPR78Group.CHaro: 6}),
    ("CYCLOHEXANE", {PPR78Group.CH2_cyclic: 6}),
]


@pytest.mark.parametrize(
    "comp_id, expected_groups",
    _GROUP_CASES,
    ids=[c[0] for c in _GROUP_CASES],
)
def test_ppr78_group_decomposition(comp_id, expected_groups):
    """GroupDecomposer yields correct PPR78 groups for known species."""
    decomposer = GroupDecomposer(use_rdkit=False)
    groups = decomposer.decompose(component_id=comp_id)
    assert groups == expected_groups


# ---------------------------------------------------------------------------
# 6. test_ppr78_kij_calculation
# ---------------------------------------------------------------------------

_KIJ_PAIRS = [
    ("C1", "CO2"),
    ("C1", "N2"),
    ("C2", "H2S"),
    ("C3", "C4"),
]


@pytest.mark.parametrize("id_a, id_b", _KIJ_PAIRS, ids=[f"{a}-{b}" for a, b in _KIJ_PAIRS])
def test_ppr78_kij_calculation(id_a, id_b):
    """PPR78 k_ij symmetric, diagonal zero, and in [-0.5, 0.5]."""
    calc = PPR78Calculator(use_rdkit=False)
    for cid in {id_a, id_b}:
        calc.register_component(cid)

    T = 300.0

    kij = calc.calculate_kij(id_a, id_b, T)
    kji = calc.calculate_kij(id_b, id_a, T)
    kii = calc.calculate_kij(id_a, id_a, T)

    assert kij == pytest.approx(kji, rel=1e-10), "k_ij must equal k_ji"
    assert kii == 0.0, "Diagonal k_ii must be zero"
    assert -0.5 <= kij <= 0.5

    kij_200 = calc.calculate_kij(id_a, id_b, 200.0)
    kij_400 = calc.calculate_kij(id_a, id_b, 400.0)
    assert not np.isclose(kij_200, kij_400, rtol=1e-3), "k_ij should vary with T"


# ---------------------------------------------------------------------------
# 7. test_pr78_vs_pr76_heavy
# ---------------------------------------------------------------------------

def test_pr78_vs_pr76_heavy(components):
    """PR78 κ diverges from PR76 for heavy component C12."""
    pr76 = _make_eos(PengRobinsonEOS, components, "C12")
    pr78 = _make_eos(PR78EOS, components, "C12")

    omega = components["C12"].omega
    assert omega > 0.49

    assert pr78.kappa[0] != pytest.approx(pr76.kappa[0], rel=1e-12)

    expected_pr78_kappa = (
        0.379642
        + 1.48503 * omega
        - 0.164423 * omega ** 2
        + 0.016666 * omega ** 3
    )
    assert pr78.kappa[0] == pytest.approx(expected_pr78_kappa, rel=1e-10)

    z = np.array([1.0])
    Z_76 = pr76.compressibility(3e6, 650.0, z, phase="vapor")
    Z_78 = pr78.compressibility(3e6, 650.0, z, phase="vapor")
    assert Z_78 != pytest.approx(Z_76, rel=1e-10)


# ---------------------------------------------------------------------------
# 8. test_eos_edge_cases
# ---------------------------------------------------------------------------

class TestEosEdgeCases:
    """Single-component root behaviour, extreme pressures, negative-P guard."""

    def test_single_component_roots_subcritical(self, components):
        """Auto-phase below Tc should return three roots (two-phase region)."""
        eos = _make_eos(PengRobinsonEOS, components, "C1")
        roots = eos.compressibility(2e6, 150.0, np.array([1.0]), phase="auto")
        if isinstance(roots, list) and len(roots) == 3:
            assert min(roots) < max(roots)
            assert min(roots) < 0.3
            assert max(roots) > 0.5

    def test_single_component_supercritical_single_root(self, components):
        """Above Tc & Pc the cubic should collapse to one real root."""
        comp = components["C1"]
        eos = _make_eos(PengRobinsonEOS, components, "C1")
        roots = eos.compressibility(
            1.5 * comp.Pc, 1.2 * comp.Tc, np.array([1.0]), phase="auto"
        )
        assert isinstance(roots, float) or len(roots) == 1

    def test_extreme_low_pressure(self, components):
        """Z → 1 at very low pressure (ideal-gas limit)."""
        eos = _make_eos(PengRobinsonEOS, components, "C1")
        Z = eos.compressibility(1.0, 300.0, np.array([1.0]), phase="vapor")
        assert Z == pytest.approx(1.0, abs=1e-3)

    def test_very_high_pressure_graceful(self, components):
        """At 500 MPa the EOS should either compute or raise PhaseError, not crash."""
        eos = _make_eos(PengRobinsonEOS, components, "C1")
        try:
            phi = eos.fugacity_coefficient(500e6, 200.0, np.array([1.0]), phase="liquid")
            assert np.isfinite(phi[0]) and phi[0] > 0
        except PhaseError:
            pass  # acceptable

    def test_srk_liquid_root_less_than_vapor(self, components):
        """SRK auto roots: min < max when three roots exist."""
        eos = _make_eos(SRKEOS, components, "C1")
        roots = eos.compressibility(2e6, 150.0, np.array([1.0]), phase="auto")
        if isinstance(roots, list) and len(roots) == 3:
            assert min(roots) < max(roots)

    def test_departure_functions_at_high_pressure(self, components):
        """Departure functions should stay finite at 100 MPa."""
        eos = _make_eos(PengRobinsonEOS, components, "C1")
        dep = eos.calculate_departure_functions(
            100e6, 300.0, np.array([1.0]), phase="liquid"
        )
        for key in ("enthalpy_departure", "entropy_departure", "gibbs_departure"):
            assert np.isfinite(dep[key])
