"""Consolidated flash-calculation tests.

Covers Wilson K-values, Rachford-Rice solver, PT flash convergence + physics
invariants (material balance, fugacity equality, K-value consistency, phase
identification), special cases (BIP, initial K-values), single-phase limits,
edge cases (near-critical, max iterations), and validation-invariant solver
certificates.

Session-scoped fixtures from conftest.py are used where possible.
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.stability.wilson import (
    wilson_k_values,
    wilson_k_value_single,
    is_trivial_solution,
    wilson_correlation_valid,
)
from pvtcore.flash.rachford_rice import (
    rachford_rice_function,
    solve_rachford_rice,
    calculate_phase_compositions,
    find_valid_brackets,
)
from pvtcore.flash.pt_flash import pt_flash, FlashResult
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError, ConvergenceError
from pvtcore.validation.invariants import (
    build_flash_certificate,
    check_composition_sum,
    check_eos_sanity,
    check_fugacity_equality,
    check_material_balance,
    check_phase_fraction_bounds,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_simplex(
    x: np.ndarray,
    *,
    tol_sum: float = 1e-10,
    allow_all_zero: bool = False,
) -> None:
    x = np.asarray(x, dtype=float)
    assert x.ndim == 1
    assert np.all(np.isfinite(x))
    if allow_all_zero and np.allclose(x, 0.0, atol=1e-15):
        return
    assert np.all(x >= -1e-12)
    assert np.all(x <= 1.0 + 1e-12)
    assert abs(float(x.sum()) - 1.0) < tol_sum


def _assert_positive_finite(arr: np.ndarray) -> None:
    arr = np.asarray(arr, dtype=float)
    assert np.all(np.isfinite(arr))
    assert np.all(arr > 0.0)


# ---------------------------------------------------------------------------
# 1. Wilson K-values (cheap, no EOS required)
# ---------------------------------------------------------------------------

_WILSON_CASES = [
    ("light_K>1", "C1", 3e6, 300.0, "gt1"),
    ("heavy_K<1", "C10", 3e6, 300.0, "lt1"),
    ("K_decreases_with_P", "C1", None, 300.0, "P_decrease"),
    ("K_increases_with_T", "C1", 3e6, None, "T_increase"),
    ("acentric_C1_vs_C2", None, 3e6, 300.0, "acentric"),
]


class TestWilsonKValues:
    """Wilson K-value correlation — parametrised over component/condition combos."""

    @pytest.mark.parametrize(
        "comp_id, P, T",
        [("C1", 3e6, 300.0), ("C10", 3e6, 300.0), ("C2", 3e6, 300.0)],
        ids=["C1-light", "C10-heavy", "C2-mid"],
    )
    def test_wilson_k_values(self, components, comp_id, P, T):
        comp = components[comp_id]
        K = wilson_k_values(P, T, [comp])
        assert np.all(K > 0)
        assert np.all(K > 1e-6)
        assert np.all(K < 1e3)

        K_single = wilson_k_value_single(P, T, comp)
        assert K[0] == pytest.approx(K_single, rel=1e-10)

        if comp_id == "C1":
            assert K[0] > 1.0
        elif comp_id == "C10":
            assert K[0] < 1.0

    def test_k_decreases_with_pressure(self, components):
        K_lo = wilson_k_values(1e6, 300.0, [components["C1"]])
        K_hi = wilson_k_values(5e6, 300.0, [components["C1"]])
        assert K_lo[0] > K_hi[0]

    def test_k_increases_with_temperature(self, components):
        K_lo = wilson_k_values(3e6, 250.0, [components["C1"]])
        K_hi = wilson_k_values(3e6, 350.0, [components["C1"]])
        assert K_hi[0] > K_lo[0]

    def test_acentric_factor_ordering(self, components):
        K_c1 = wilson_k_values(3e6, 300.0, [components["C1"]])[0]
        K_c2 = wilson_k_values(3e6, 300.0, [components["C2"]])[0]
        assert K_c1 > K_c2

    @pytest.mark.parametrize(
        "K, z, expected_phase",
        [
            (np.array([2.0, 3.0, 4.0]), np.array([0.5, 0.3, 0.2]), "vapor"),
            (np.array([0.3, 0.5, 0.7]), np.array([0.5, 0.3, 0.2]), "liquid"),
            (np.array([2.0, 1.0, 0.5]), np.array([0.5, 0.3, 0.2]), None),
        ],
        ids=["all-vapor", "all-liquid", "two-phase"],
    )
    def test_trivial_solution_detection(self, K, z, expected_phase):
        is_trivial, phase = is_trivial_solution(K, z)
        if expected_phase is None:
            assert is_trivial is False
            assert phase is None
        else:
            assert is_trivial is True
            assert phase == expected_phase

    def test_wilson_correlation_validity(self, components):
        ok, _ = wilson_correlation_valid(3e6, 300.0, [components["C1"]])
        assert ok is True
        bad, _ = wilson_correlation_valid(100e6, 300.0, [components["C1"]])
        assert bad is False

    def test_binary_range(self, components):
        binary = [components["C1"], components["C10"]]
        K = wilson_k_values(3e6, 300.0, binary)
        assert np.all(K > 0)
        assert np.all(K > 1e-6)
        assert np.all(K < 1e3)


# ---------------------------------------------------------------------------
# 2. Rachford-Rice solver — parametrised over (K, z, expected_beta)
# ---------------------------------------------------------------------------

class TestRachfordRiceSolver:

    @pytest.mark.parametrize(
        "K, z, expected_beta",
        [
            (np.array([2.0, 0.5]), np.array([0.5, 0.5]), None),
            (np.array([3.0, 1.0, 0.3]), np.array([0.4, 0.3, 0.3]), None),
            (np.array([2.0, 3.0, 4.0]), np.array([0.5, 0.3, 0.2]), 1.0),
            (np.array([0.3, 0.5, 0.7]), np.array([0.5, 0.3, 0.2]), 0.0),
        ],
        ids=["binary-twophase", "ternary-twophase", "all-vapor", "all-liquid"],
    )
    def test_rachford_rice_solver(self, K, z, expected_beta):
        nv, x, y = solve_rachford_rice(K, z)

        assert 0.0 <= nv <= 1.0
        assert np.sum(x) == pytest.approx(1.0, abs=1e-10) or np.allclose(x, 0.0, atol=1e-10)
        assert np.sum(y) == pytest.approx(1.0, abs=1e-10) or np.allclose(y, 0.0, atol=1e-10)

        z_calc = (1 - nv) * x + nv * y
        assert np.allclose(z_calc, z, atol=1e-10)

        if expected_beta is not None:
            assert nv == pytest.approx(expected_beta, abs=1e-10)
        else:
            assert 0.0 < nv < 1.0
            K_calc = y / x
            assert np.allclose(K_calc, K, atol=1e-8)

    def test_rachford_rice_function_at_zero(self):
        K = np.array([2.0, 0.5])
        z = np.array([0.5, 0.5])
        f = rachford_rice_function(0.0, K, z)
        expected = np.sum(z * (K - 1.0))
        assert f == pytest.approx(expected, abs=1e-10)

    def test_rachford_rice_function_monotonic(self):
        K = np.array([3.0, 0.5])
        z = np.array([0.6, 0.4])
        nv_values = np.linspace(0.1, 0.9, 10)
        f_values = [rachford_rice_function(nv, K, z) for nv in nv_values]
        for i in range(len(f_values) - 1):
            assert f_values[i] > f_values[i + 1]

    def test_calculate_phase_compositions(self):
        K = np.array([2.0, 0.5])
        z = np.array([0.5, 0.5])
        x, y = calculate_phase_compositions(0.5, K, z)
        assert np.sum(x) == pytest.approx(1.0, abs=1e-10)
        assert np.sum(y) == pytest.approx(1.0, abs=1e-10)
        assert np.allclose(y / x, K, atol=1e-10)

    def test_find_valid_brackets(self):
        K = np.array([3.0, 0.5])
        z = np.array([0.5, 0.5])
        nv_min, nv_max = find_valid_brackets(K, z)
        assert 0.0 <= nv_min < nv_max <= 1.0
        f_min = rachford_rice_function(nv_min, K, z)
        f_max = rachford_rice_function(nv_max, K, z)
        assert f_min * f_max < 0

    def test_invalid_composition_raises_error(self):
        with pytest.raises(ValidationError):
            solve_rachford_rice(np.array([2.0, 0.5]), np.array([0.5, 0.6]))

    def test_mismatched_lengths_raises_error(self):
        with pytest.raises(ValidationError):
            solve_rachford_rice(np.array([2.0, 0.5]), np.array([0.5, 0.3, 0.2]))


# ---------------------------------------------------------------------------
# 3. PT flash — convergence + physics invariants (absorbs test_invariants.py)
# ---------------------------------------------------------------------------

class TestPTFlashConvergesAndPhysics:
    """Use session fixtures; assert convergence, material balance, fugacity
    equality, K-value consistency, and phase identification."""

    def test_c1_c10_flash_physics(self, c1_c10_flash, components, c1_c10_pr):
        res = c1_c10_flash
        z = np.array([0.5, 0.5])

        assert res.converged is True
        assert res.iterations < 50
        assert 0.0 <= res.vapor_fraction <= 1.0

        assert np.sum(res.liquid_composition) == pytest.approx(1.0, abs=1e-6)
        assert np.sum(res.vapor_composition) == pytest.approx(1.0, abs=1e-6)

        z_calc = (1 - res.vapor_fraction) * res.liquid_composition + res.vapor_fraction * res.vapor_composition
        assert np.allclose(z_calc, z, atol=1e-6)

        if res.phase == "two-phase":
            assert res.vapor_composition[0] > res.liquid_composition[0]
            assert res.liquid_composition[1] > res.vapor_composition[1]

            K_calc = res.vapor_composition / res.liquid_composition
            assert np.allclose(K_calc, res.K_values, rtol=1e-3)

            P = res.pressure
            f_L = res.liquid_fugacity * res.liquid_composition * P
            f_V = res.vapor_fugacity * res.vapor_composition * P
            assert np.allclose(f_L, f_V, rtol=1e-4)

    def test_c1_c4_flash_physics(self, c1_c4_flash):
        res = c1_c4_flash
        z = np.array([0.5, 0.5])

        assert res.converged is True
        z_calc = (1 - res.vapor_fraction) * res.liquid_composition + res.vapor_fraction * res.vapor_composition
        assert np.allclose(z_calc, z, atol=1e-6)

    @pytest.mark.parametrize(
        "pressure",
        [1.0e6, 3.0e6, 1.0e7],
        ids=["10bar", "30bar", "100bar"],
    )
    def test_invariant_mass_balance_and_bounds(self, pressure, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.6, 0.4])
        result = pt_flash(pressure, 300.0, z, binary, c1_c10_pr)

        assert result.converged is True
        assert result.phase in {"two-phase", "vapor", "liquid"}
        assert 0.0 <= result.vapor_fraction <= 1.0

        _assert_simplex(result.feed_composition)
        np.testing.assert_allclose(result.feed_composition, z, atol=1e-12)

        if result.phase == "two-phase":
            _assert_simplex(result.liquid_composition)
            _assert_simplex(result.vapor_composition)
            assert np.all(result.K_values > 0.0)
            x, y = result.liquid_composition, result.vapor_composition
            for i in range(len(x)):
                if x[i] > 1e-14:
                    assert y[i] / x[i] == pytest.approx(result.K_values[i], rel=2e-5, abs=1e-10)
            _assert_positive_finite(result.liquid_fugacity)
            _assert_positive_finite(result.vapor_fugacity)
        elif result.phase == "liquid":
            assert result.vapor_fraction == pytest.approx(0.0, abs=0.0)
            _assert_simplex(result.liquid_composition)
            _assert_simplex(result.vapor_composition, allow_all_zero=True)
            np.testing.assert_allclose(result.liquid_composition, z, atol=1e-12)
        else:
            assert result.vapor_fraction == pytest.approx(1.0, abs=0.0)
            _assert_simplex(result.vapor_composition)
            _assert_simplex(result.liquid_composition, allow_all_zero=True)
            np.testing.assert_allclose(result.vapor_composition, z, atol=1e-12)

    def test_ternary_flash(self, components):
        ternary = [components["C1"], components["C3"], components["C10"]]
        eos = PengRobinsonEOS(ternary)
        z = np.array([0.5, 0.3, 0.2])
        result = pt_flash(3e6, 300.0, z, ternary, eos)
        assert result.converged is True
        if result.phase == "two-phase":
            z_calc = (1 - result.vapor_fraction) * result.liquid_composition + result.vapor_fraction * result.vapor_composition
            assert np.allclose(z_calc, z, atol=1e-6)

    def test_flash_result_dataclass(self, c1_c10_flash):
        res = c1_c10_flash
        for attr in ("converged", "iterations", "vapor_fraction",
                      "liquid_composition", "vapor_composition", "K_values",
                      "liquid_fugacity", "vapor_fugacity", "phase",
                      "pressure", "temperature", "residual"):
            assert hasattr(res, attr)
        assert isinstance(res.converged, bool)
        assert isinstance(res.iterations, int)
        assert isinstance(res.liquid_composition, np.ndarray)

    def test_flash_invalid_composition(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        with pytest.raises(ValidationError):
            pt_flash(3e6, 300.0, np.array([0.5, 0.6]), binary, c1_c10_pr)

    def test_flash_negative_pressure(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        with pytest.raises(ValidationError):
            pt_flash(-1e6, 300.0, np.array([0.5, 0.5]), binary, c1_c10_pr)

    def test_eos_covolume_and_fugacity(self, c1_c10_pr):
        z = np.array([0.6, 0.4])
        result = c1_c10_pr.calculate(3.0e6, 300.0, z, phase="auto")
        assert result.B > 0.0
        for r in result.roots:
            assert r >= result.B - 1e-14

        phi_L = c1_c10_pr.fugacity_coefficient(3.0e6, 300.0, z, phase="liquid")
        phi_V = c1_c10_pr.fugacity_coefficient(3.0e6, 300.0, z, phase="vapor")
        _assert_positive_finite(phi_L)
        _assert_positive_finite(phi_V)

    def test_component_database_invariants(self, components):
        for comp_id, c in components.items():
            assert np.isfinite(c.Tc) and c.Tc > 0.0, comp_id
            assert np.isfinite(c.Pc) and c.Pc > 0.0, comp_id
            assert np.isfinite(c.Vc) and c.Vc > 0.0, comp_id
            assert np.isfinite(c.MW) and c.MW > 0.0, comp_id
            assert np.isfinite(c.Tb) and c.Tb > 0.0, comp_id
            assert np.isfinite(c.omega), comp_id
            assert 1e3 < c.Pc < 1e9, comp_id
            assert 1.0 < c.Tc < 2_000.0, comp_id
            assert 1.0 < c.MW < 1_000.0, comp_id
            assert c.Tc > c.Tb, comp_id


# ---------------------------------------------------------------------------
# 4. Flash special cases — BIP, initial K-values (parametrised)
# ---------------------------------------------------------------------------

class TestFlashSpecialCases:

    @pytest.mark.parametrize(
        "label, kij, K_init",
        [
            ("with_bip", np.array([[0.0, 0.03], [0.03, 0.0]]), None),
            ("with_initial_K", None, np.array([3.0, 0.1])),
            ("bip_and_K", np.array([[0.0, 0.03], [0.03, 0.0]]), np.array([3.0, 0.1])),
        ],
        ids=["bip-only", "K-init-only", "bip-and-K"],
    )
    def test_flash_special_cases(self, components, c1_c10_pr, label, kij, K_init):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.5, 0.5])
        kwargs: dict = {}
        if kij is not None:
            kwargs["binary_interaction"] = kij
        if K_init is not None:
            kwargs["K_initial"] = K_init
        result = pt_flash(3e6, 300.0, z, binary, c1_c10_pr, **kwargs)
        assert result.converged is True

    def test_pure_component_flash(self, components):
        eos = PengRobinsonEOS([components["C1"]])
        result = pt_flash(2e6, 150.0, np.array([1.0]), [components["C1"]], eos)
        assert result.converged is True


# ---------------------------------------------------------------------------
# 5. Single-phase detection — high-P liquid, low-P vapor
# ---------------------------------------------------------------------------

class TestFlashSinglePhase:

    def test_single_phase_liquid_high_pressure(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.3, 0.7])
        result = pt_flash(5e7, 200.0, z, binary, c1_c10_pr)
        assert result.converged is True
        assert result.phase == "liquid"
        assert result.vapor_fraction == pytest.approx(0.0, abs=1e-6)
        assert np.allclose(result.liquid_composition, z, atol=1e-6)
        assert np.all(result.vapor_composition == 0.0)
        assert result.iterations == 0

    def test_single_phase_vapor_low_pressure(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.7, 0.3])
        result = pt_flash(1e5, 500.0, z, binary, c1_c10_pr)
        assert result.converged is True
        assert result.phase == "vapor"
        assert result.vapor_fraction == pytest.approx(1.0, abs=1e-6)
        assert np.allclose(result.vapor_composition, z, atol=1e-6)
        assert np.all(result.liquid_composition == 0.0)
        assert result.iterations == 0

    def test_extreme_conditions(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.8, 0.2])

        res_v = pt_flash(1.0e5, 600.0, z, binary, c1_c10_pr)
        assert res_v.phase == "vapor"
        _assert_simplex(res_v.vapor_composition)

        res_l = pt_flash(5.0e7, 250.0, z, binary, c1_c10_pr)
        assert res_l.phase == "liquid"
        _assert_simplex(res_l.liquid_composition)

    def test_high_pressure_low_vapor_fraction(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = pt_flash(50e6, 300.0, np.array([0.5, 0.5]), binary, c1_c10_pr)
        assert result.vapor_fraction < 0.1

    def test_low_pressure_high_vapor_fraction(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = pt_flash(0.3e6, 500.0, np.array([0.5, 0.5]), binary, c1_c10_pr)
        assert result.vapor_fraction > 0.9


# ---------------------------------------------------------------------------
# 6. Edge cases — near-critical, max iterations
# ---------------------------------------------------------------------------

class TestFlashEdgeCases:

    def test_near_critical_point(self, components):
        eos = PengRobinsonEOS([components["C1"]])
        T = components["C1"].Tc * 0.99
        P = components["C1"].Pc * 1.01
        result = pt_flash(P, T, np.array([1.0]), [components["C1"]], eos)
        assert result.converged is True


# ---------------------------------------------------------------------------
# 7. Validation invariant solver certificates (from test_validation_invariants.py)
# ---------------------------------------------------------------------------

class TestValidationInvariants:

    def test_composition_sum_check(self):
        ok = check_composition_sum("sum", [0.2, 0.8], tol=1e-8, allow_all_zero=False)
        assert ok.passed is True
        assert ok.value == pytest.approx(0.0)

        bad = check_composition_sum("sum", [0.2, 0.7], tol=1e-8, allow_all_zero=False)
        assert bad.passed is False
        assert bad.value > 0.0

    def test_phase_fraction_bounds_check(self):
        ok = check_phase_fraction_bounds(0.5, tol=1e-8)
        assert ok.passed is True
        bad = check_phase_fraction_bounds(1.2, tol=1e-8)
        assert bad.passed is False

    def test_material_balance_check(self):
        z = np.array([0.2, 0.8])
        x = np.array([0.1, 0.9])
        y = np.array([0.3, 0.7])
        chk = check_material_balance(z, x, y, 0.5, tol=1e-8)
        assert chk.passed is True
        bad = check_material_balance(z, x, y, 0.9, tol=1e-8)
        assert bad.passed is False

    def test_fugacity_equality_check(self):
        x = np.array([0.3, 0.7])
        y = np.array([0.3, 0.7])
        phi_l = np.array([1.0, 1.0])
        phi_v = np.array([1.0, 1.0])
        max_chk, mean_chk = check_fugacity_equality(x, y, phi_l, phi_v, tol_max=1e-8, tol_mean=1e-8)
        assert max_chk.passed is True
        assert mean_chk.passed is True

    def test_eos_sanity_check(self, components, c1_c10_pr):
        z = np.array([0.6, 0.4])
        checks = check_eos_sanity(c1_c10_pr, pressure=3.0e6, temperature=300.0, compositions_by_phase={"vapor": z})
        assert all(c.passed for c in checks if c.applicable)

    def test_build_flash_certificate(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.6, 0.4])
        res = pt_flash(3.0e6, 300.0, z, binary, c1_c10_pr)
        cert = build_flash_certificate(res, c1_c10_pr)
        assert cert.passed is True
        names = {c.name for c in cert.checks}
        assert "composition_sum_z" in names
        assert "phase_fraction_bounds" in names
        assert "material_balance_max" in names


# ---------------------------------------------------------------------------
# 8. Input validation (absorbed from contracts/test_robustness.py)
# ---------------------------------------------------------------------------

class TestFlashInputValidation:
    """Comprehensive input-validation edge cases for pt_flash."""

    def test_empty_component_list(self):
        with pytest.raises(ValidationError, match="Component list cannot be empty"):
            pt_flash(2e6, 250, np.array([1.0]), [], None)

    def test_mismatched_composition_length(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="Composition length must match"):
            pt_flash(2e6, 250, np.array([0.3, 0.3, 0.4]), binary, c1_c4_pr)

    def test_composition_not_summing_to_one(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="must sum to 1.0"):
            pt_flash(2e6, 250, np.array([0.3, 0.3]), binary, c1_c4_pr)

    def test_negative_composition(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="non-negative"):
            pt_flash(2e6, 250, np.array([-0.1, 1.1]), binary, c1_c4_pr)

    def test_nan_in_composition(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="NaN or Inf"):
            pt_flash(2e6, 250, np.array([np.nan, 0.5]), binary, c1_c4_pr)

    def test_inf_in_composition(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="NaN or Inf"):
            pt_flash(2e6, 250, np.array([np.inf, 0.5]), binary, c1_c4_pr)

    def test_zero_pressure(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="[Pp]ressure.*positive"):
            pt_flash(0, 250, np.array([0.5, 0.5]), binary, c1_c4_pr)

    def test_negative_temperature(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="[Tt]emperature.*positive"):
            pt_flash(2e6, -100, np.array([0.5, 0.5]), binary, c1_c4_pr)

    def test_zero_temperature(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="[Tt]emperature.*positive"):
            pt_flash(2e6, 0, np.array([0.5, 0.5]), binary, c1_c4_pr)

    def test_invalid_bip_matrix_shape(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="Binary interaction matrix"):
            pt_flash(2e6, 250, np.array([0.5, 0.5]), binary, c1_c4_pr,
                     binary_interaction=np.zeros((3, 3)))

    def test_invalid_tolerance(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="[Tt]olerance"):
            pt_flash(2e6, 250, np.array([0.5, 0.5]), binary, c1_c4_pr,
                     tolerance=-0.01)
        with pytest.raises(ValidationError, match="[Tt]olerance"):
            pt_flash(2e6, 250, np.array([0.5, 0.5]), binary, c1_c4_pr,
                     tolerance=2.0)

    def test_invalid_max_iterations(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="max_iterations"):
            pt_flash(2e6, 250, np.array([0.5, 0.5]), binary, c1_c4_pr,
                     max_iterations=0)

    def test_error_message_includes_parameter(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError) as exc_info:
            pt_flash(2e6, 250, np.array([0.3, 0.3]), binary, c1_c4_pr)
        assert 'composition' in str(exc_info.value).lower() or hasattr(exc_info.value, 'parameter')

    def test_error_message_includes_value(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError) as exc_info:
            pt_flash(2e6, 250, np.array([0.3, 0.3]), binary, c1_c4_pr)
        error_msg = str(exc_info.value)
        assert '0.6' in error_msg or 'sum' in error_msg.lower()


# ---------------------------------------------------------------------------
# 9. Numerical robustness (absorbed from contracts/test_robustness.py)
# ---------------------------------------------------------------------------

class TestFlashNumericalRobustness:
    """Numerical edge cases: trace components, extreme conditions, graceful
    degradation under tight iteration budgets."""

    def test_trace_component_handling(self, components):
        from pvtcore.core.errors import ConvergenceStatus
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.999999, 0.000001])
        result = pt_flash(2e6, 250, z, comp_list, eos)

        assert result.status != ConvergenceStatus.NUMERIC_ERROR
        assert np.all(np.isfinite(result.liquid_composition))
        assert np.all(np.isfinite(result.vapor_composition))
        assert np.isfinite(result.vapor_fraction)

    def test_near_pure_component(self, components):
        from pvtcore.core.errors import ConvergenceStatus
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.9999, 0.0001])
        result = pt_flash(2e6, 200, z, comp_list, eos)

        assert result.status in (ConvergenceStatus.CONVERGED, ConvergenceStatus.STAGNATED)
        assert np.all(np.isfinite(result.K_values))

    def test_very_high_pressure(self, components):
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(1000e5, 300, z, comp_list, eos)
        assert result.phase == "liquid"
        assert result.vapor_fraction == 0.0

    def test_very_low_pressure(self, components):
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(0.01e5, 400, z, comp_list, eos)
        assert result.phase == "vapor"
        assert result.vapor_fraction == 1.0

    def test_near_critical_temperature(self, components):
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(5e6, 191, z, comp_list, eos)
        assert result.status is not None
        assert np.all(np.isfinite(result.liquid_composition))

    def test_extreme_k_value_ratio(self, components):
        comp_list = [components["C1"], components["C10"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(50e5, 350, z, comp_list, eos)
        assert result.status is not None
        if result.phase == "two-phase":
            assert result.K_values[0] > result.K_values[1]

    def test_max_iterations_graceful_degradation(self, components):
        from pvtcore.core.errors import ConvergenceStatus
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(2e6, 250, z, comp_list, eos, max_iterations=2)

        assert result is not None
        assert result.status in (
            ConvergenceStatus.CONVERGED,
            ConvergenceStatus.MAX_ITERS,
            ConvergenceStatus.STAGNATED,
        )
        if result.history is not None:
            assert result.history.n_iterations <= 2

    def test_composition_normalization(self, components):
        from pvtcore.core.errors import ConvergenceStatus
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.500001, 0.499999])
        result = pt_flash(2e6, 250, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

    def test_convergence_returns_valid_status(self, components):
        from pvtcore.core.errors import ConvergenceStatus
        comp_list = [components["C1"], components["C4"]]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        result = pt_flash(2e6, 250, z, comp_list, eos)
        assert isinstance(result.status, ConvergenceStatus)
        assert result.status in [
            ConvergenceStatus.CONVERGED,
            ConvergenceStatus.MAX_ITERS,
            ConvergenceStatus.DIVERGED,
            ConvergenceStatus.STAGNATED,
            ConvergenceStatus.NUMERIC_ERROR,
        ]
