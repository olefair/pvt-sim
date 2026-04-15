"""Unit tests for cubic equation solver.

Tests Cardano's formula implementation with known analytical solutions,
root selection logic, EOS-specific solver, and diagnostics — all via
parametrised reference tables.
"""

import pytest
from pvtcore.core.numerics.cubic_solver import (
    eos_cubic_coefficients,
    solve_cubic,
    select_root,
    solve_cubic_eos,
    cubic_diagnostics,
)


# ═══════════════════════════════════════════════════════════════════════════
# 1. solve_cubic — real roots
# ═══════════════════════════════════════════════════════════════════════════
# (id, c2, c1, c0, expected_roots, abs_tol)

REAL_ROOT_CASES = [
    # Three distinct integer roots: (Z-1)(Z-2)(Z-3)
    ("three_simple",    -6.0, 11.0, -6.0,       [1.0, 2.0, 3.0],      1e-10),
    # Negative roots: (Z+1)(Z+2)(Z+3)
    ("three_negative",   6.0, 11.0,  6.0,       [-3.0, -2.0, -1.0],   1e-10),
    # Mixed sign: (Z-2)(Z+1)(Z+3)
    ("mixed_sign",       2.0, -5.0, -6.0,       [-3.0, -1.0, 2.0],    1e-9),
    # Fractional: (Z-0.5)(Z-1.5)(Z-2.5)
    ("fractional",      -4.5, 5.75, -1.875,     [0.5, 1.5, 2.5],      1e-9),
    # Large: roots scaled by 1000
    ("very_large",      -6000.0, 11e6, -6e9,    [1000.0, 2000.0, 3000.0], 1000 * 1e-5),
]


@pytest.mark.parametrize(
    "case_id, c2, c1, c0, expected, atol",
    REAL_ROOT_CASES,
    ids=[c[0] for c in REAL_ROOT_CASES],
)
def test_solve_cubic_real_roots(case_id, c2, c1, c0, expected, atol):
    roots = solve_cubic(c2, c1, c0)
    assert len(roots) == len(expected)
    for r, e in zip(roots, expected):
        assert r == pytest.approx(e, abs=atol)


# ═══════════════════════════════════════════════════════════════════════════
# 2. solve_cubic — degenerate / complex / single-real-root cases
# ═══════════════════════════════════════════════════════════════════════════

DEGENERATE_CASES = [
    # Triple root: (Z-2)³
    ("triple_root",   -6.0, 12.0, -8.0,  1, [2.0],     1e-10),
    # One real root: Z³ - 1 = 0
    ("one_real",       0.0,  0.0, -1.0,   1, [1.0],     1e-10),
    # Z³ = 0
    ("all_zeros",      0.0,  0.0,  0.0,   1, [0.0],     1e-10),
]


@pytest.mark.parametrize(
    "case_id, c2, c1, c0, n_roots, expected, atol",
    DEGENERATE_CASES,
    ids=[c[0] for c in DEGENERATE_CASES],
)
def test_solve_cubic_degenerate(case_id, c2, c1, c0, n_roots, expected, atol):
    roots = solve_cubic(c2, c1, c0)
    assert len(roots) == n_roots
    for r, e in zip(roots, expected):
        assert r == pytest.approx(e, abs=atol)


# ═══════════════════════════════════════════════════════════════════════════
# 3. solve_cubic — edge cases (double root, small coeffs, near-zero Δ)
# ═══════════════════════════════════════════════════════════════════════════

def test_double_root():
    """(Z-1)²(Z-3) = Z³ - 5Z² + 7Z - 3"""
    roots = solve_cubic(-5.0, 7.0, -3.0)
    assert len(roots) >= 1
    assert 1.0 in [pytest.approx(r, abs=1e-10) for r in roots]
    assert 3.0 in [pytest.approx(r, abs=1e-10) for r in roots]


def test_very_small_coefficients():
    k = 0.001
    roots = solve_cubic(-6 * k, 11 * k**2, -6 * k**3)
    assert 1 <= len(roots) <= 3
    for root in roots:
        assert 0.0 < root < 0.01


def test_near_zero_discriminant():
    """(Z-1)²(Z-2) = Z³ - 4Z² + 5Z - 2"""
    roots = solve_cubic(-4.0, 5.0, -2.0)
    assert 1.0 in [pytest.approx(r, abs=1e-8) for r in roots]
    assert 2.0 in [pytest.approx(r, abs=1e-8) for r in roots]


def test_typical_eos_case_vapor():
    roots = solve_cubic(-1.0, -0.5, 0.05)
    if len(roots) == 3:
        assert roots[0] < 0.5
        assert roots[-1] > 0.5
    else:
        assert len(roots) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 4. Vieta's formulas verification
# ═══════════════════════════════════════════════════════════════════════════

def test_vietas_formulas():
    c2, c1, c0 = -6.0, 11.0, -6.0
    roots = solve_cubic(c2, c1, c0)
    assert sum(roots) == pytest.approx(-c2, abs=1e-9)
    pairs_sum = roots[0] * roots[1] + roots[0] * roots[2] + roots[1] * roots[2]
    assert pairs_sum == pytest.approx(c1, abs=1e-9)
    assert roots[0] * roots[1] * roots[2] == pytest.approx(-c0, abs=1e-9)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Discriminant / diagnostics
# ═══════════════════════════════════════════════════════════════════════════

DIAG_CASES = [
    ("three_real",  -6.0, 11.0, -6.0,  "positive", 3),
    ("one_real",     0.0,  0.0, -1.0,   "negative", 1),
]


@pytest.mark.parametrize(
    "case_id, c2, c1, c0, sign, n_real",
    DIAG_CASES,
    ids=[c[0] for c in DIAG_CASES],
)
def test_discriminant(case_id, c2, c1, c0, sign, n_real):
    diag = cubic_diagnostics(c2, c1, c0)
    assert diag["discriminant_sign"] == sign
    assert diag["num_real_roots"] == n_real


def test_diagnostics_three_roots_detail():
    diag = cubic_diagnostics(-6.0, 11.0, -6.0)
    assert len(diag["roots"]) == 3
    assert diag["roots_sum"] == pytest.approx(6.0, abs=1e-9)


def test_diagnostics_one_root_detail():
    diag = cubic_diagnostics(0.0, 0.0, -1.0)
    assert len(diag["roots"]) == 1


def test_diagnostics_includes_coefficients():
    c2, c1, c0 = -6.0, 11.0, -6.0
    diag = cubic_diagnostics(c2, c1, c0)
    assert diag["c2"] == c2
    assert diag["c1"] == c1
    assert diag["c0"] == c0
    assert "p" in diag
    assert "q" in diag


# ═══════════════════════════════════════════════════════════════════════════
# 6. Root selection
# ═══════════════════════════════════════════════════════════════════════════

SELECT_CASES = [
    ("liquid",       [0.1, 0.5, 2.5], "liquid", None, 0.1),
    ("vapor",        [0.1, 0.5, 2.5], "vapor",  None, 2.5),
    ("single_liq",   [1.5],           "liquid", None, 1.5),
    ("single_vap",   [1.5],           "vapor",  None, 1.5),
]


@pytest.mark.parametrize(
    "case_id, roots, rtype, minv, expected",
    SELECT_CASES,
    ids=[c[0] for c in SELECT_CASES],
)
def test_select_root(case_id, roots, rtype, minv, expected):
    kw = {"root_type": rtype}
    if minv is not None:
        kw["min_value"] = minv
    assert select_root(roots, **kw) == expected


def test_select_all_roots():
    assert select_root([0.1, 0.5, 2.5], root_type="all") == [0.1, 0.5, 2.5]


def test_filter_negative_roots():
    valid = select_root([-0.5, 0.1, 2.5], root_type="all", min_value=0.0)
    assert -0.5 not in valid
    assert 0.1 in valid
    assert 2.5 in valid


def test_min_value_filtering():
    valid = select_root([0.05, 0.1, 2.5], root_type="all", min_value=0.08)
    assert 0.05 not in valid
    assert 0.1 in valid


def test_invalid_root_type_raises():
    with pytest.raises(ValueError, match="Invalid root_type"):
        select_root([0.1, 2.5], root_type="invalid")


def test_no_valid_roots_raises():
    with pytest.raises(ValueError, match="No valid roots found"):
        select_root([-1.0, -0.5], root_type="liquid", min_value=0.0)


# ═══════════════════════════════════════════════════════════════════════════
# 7. EOS-specific cubic solver
# ═══════════════════════════════════════════════════════════════════════════

EOS_CASES = [
    ("vapor_typical",  0.1, 0.05, "vapor",  lambda Z, B: Z > 0.5 and Z > B),
    ("ideal_gas",      1e-6, 1e-7, "vapor",  lambda Z, B: abs(Z - 1.0) < 1e-3),
]


@pytest.mark.parametrize(
    "case_id, A, B, rtype, check",
    EOS_CASES,
    ids=[c[0] for c in EOS_CASES],
)
def test_solve_cubic_eos(case_id, A, B, rtype, check):
    Z = solve_cubic_eos(A, B, root_type=rtype)
    assert check(Z, B), f"{case_id}: Z={Z}, B={B}"


def test_eos_liquid_case():
    Z = solve_cubic_eos(5.0, 0.08, root_type="liquid")
    assert Z >= 0.08
    assert Z < 0.5


def test_eos_two_phase_region():
    roots = solve_cubic_eos(1.5, 0.08, root_type="all")
    if len(roots) == 3:
        assert roots[0] < roots[-1]
        assert roots[0] >= 0.08
        assert roots[-1] > 0.5


def test_eos_z_greater_than_b():
    roots = solve_cubic_eos(2.0, 0.1, root_type="all")
    for Z in roots:
        assert Z >= 0.1, f"Root {Z} < B=0.1"


def test_eos_coefficient_calculation():
    A, B = 1.0, 0.1
    c2_exp = -(1.0 - B)
    c1_exp = A - 2.0 * B - 3.0 * B ** 2
    c0_exp = -(A * B - B ** 2 - B ** 3)
    roots_manual = solve_cubic(c2_exp, c1_exp, c0_exp)
    roots_eos = solve_cubic_eos(A, B, root_type="all")
    assert len(roots_manual) == len(roots_eos)
    for rm, re in zip(roots_manual, roots_eos):
        assert rm == pytest.approx(re, abs=1e-10)


def test_generalized_srk_coefficients():
    A, B = 1.0, 0.1
    c2, c1, c0 = eos_cubic_coefficients(A, B, u=1.0, w=0.0)
    assert c2 == pytest.approx(-1.0)
    assert c1 == pytest.approx(A - B - B ** 2)
    assert c0 == pytest.approx(-(A * B))
    roots_manual = solve_cubic(c2, c1, c0)
    roots_eos = solve_cubic_eos(A, B, root_type="all", u=1.0, w=0.0)
    assert len(roots_manual) == len(roots_eos)
    for rm, re in zip(roots_manual, roots_eos):
        assert rm == pytest.approx(re, abs=1e-10)
