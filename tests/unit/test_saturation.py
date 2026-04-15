"""Consolidated saturation-point tests (bubble and dew point).

Covers convergence, pressure physicality, composition shifts, composition
variation, convergence options (tolerance, initial guess), and edge cases
(near-critical, degenerate/trivial boundaries, pure component limits).

Session-scoped fixtures from conftest.py are used where possible.
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.flash.bubble_point import (
    calculate_bubble_point,
    BubblePointResult,
    BUBBLE_POINT_TOLERANCE,
)
from pvtcore.flash.dew_point import (
    calculate_dew_point,
    DewPointResult,
    DEW_POINT_TOLERANCE,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError, ConvergenceError, PhaseError, ConvergenceStatus


# ---------------------------------------------------------------------------
# 1. Bubble point — convergence, pressure physical, composition shift
# ---------------------------------------------------------------------------

class TestBubblePoint:

    def test_bubble_point(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        T, z = 300.0, np.array([0.5, 0.5])
        result = calculate_bubble_point(T, z, binary, c1_c10_pr)

        assert result.converged is True
        assert result.iterations < 120
        assert result.residual < BUBBLE_POINT_TOLERANCE
        assert 1e4 < result.pressure < 1e8

        np.testing.assert_allclose(result.liquid_composition, z, rtol=1e-6)
        assert abs(result.vapor_composition.sum() - 1.0) < 1e-10

        assert result.vapor_composition[0] > z[0]
        assert result.vapor_composition[1] < z[1]
        assert result.K_values[0] > 1.0
        assert result.K_values[1] < 1.0

        for attr in ("converged", "pressure", "temperature",
                      "liquid_composition", "vapor_composition",
                      "K_values", "iterations", "residual", "stable_liquid"):
            assert hasattr(result, attr)

    def test_bubble_increases_with_light_component(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        r1 = calculate_bubble_point(300.0, np.array([0.3, 0.7]), binary, c1_c10_pr)
        r2 = calculate_bubble_point(300.0, np.array([0.7, 0.3]), binary, c1_c10_pr)
        assert r2.pressure > r1.pressure

    def test_bubble_increases_with_temperature(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        z = np.array([0.5, 0.5])
        r1 = calculate_bubble_point(280.0, z, binary, c1_c10_pr)
        r2 = calculate_bubble_point(320.0, z, binary, c1_c10_pr)
        assert r2.pressure > r1.pressure


# ---------------------------------------------------------------------------
# 2. Dew point — same pattern
# ---------------------------------------------------------------------------

class TestDewPoint:

    def test_dew_point(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        T, z = 250.0, np.array([0.5, 0.5])
        result = calculate_dew_point(T, z, binary, c1_c4_pr)

        assert result.converged is True
        assert result.iterations < 120
        assert result.residual < DEW_POINT_TOLERANCE
        assert 1e4 < result.pressure < 1e7

        np.testing.assert_allclose(result.vapor_composition, z, rtol=1e-6)
        assert abs(result.liquid_composition.sum() - 1.0) < 1e-10

        assert result.liquid_composition[0] < z[0]
        assert result.liquid_composition[1] > z[1]

    def test_dew_increases_with_temperature(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        z = np.array([0.5, 0.5])
        r1 = calculate_dew_point(230.0, z, binary, c1_c4_pr)
        r2 = calculate_dew_point(270.0, z, binary, c1_c4_pr)
        assert r2.pressure > r1.pressure

    def test_dew_less_than_bubble(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        z = np.array([0.5, 0.5])
        bp = calculate_bubble_point(250.0, z, binary, c1_c4_pr)
        dp = calculate_dew_point(250.0, z, binary, c1_c4_pr)
        assert dp.pressure < bp.pressure


# ---------------------------------------------------------------------------
# 3. Composition variation — parametrised over z
# ---------------------------------------------------------------------------

class TestCompositionVariation:

    @pytest.mark.parametrize(
        "z",
        [np.array([0.2, 0.8]), np.array([0.5, 0.5]), np.array([0.8, 0.2])],
        ids=["C4-rich", "50-50", "C1-rich"],
    )
    def test_composition_variation(self, components, c1_c4_pr, z):
        binary = [components["C1"], components["C4"]]
        bp = calculate_bubble_point(250.0, z, binary, c1_c4_pr)
        dp = calculate_dew_point(250.0, z, binary, c1_c4_pr)
        assert bp.converged is True
        assert dp.converged is True
        assert dp.pressure < bp.pressure

    def test_c1_rich_c1_c10(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = calculate_bubble_point(300.0, np.array([0.7, 0.3]), binary, c1_c10_pr)
        assert result.converged is True

    def test_c10_rich_c1_c10(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = calculate_bubble_point(300.0, np.array([0.1, 0.9]), binary, c1_c10_pr)
        assert result.converged is True

    def test_ethane_propane(self, components, c2_c3_pr):
        binary = [components["C2"], components["C3"]]
        z = np.array([0.5, 0.5])
        bp = calculate_bubble_point(280.0, z, binary, c2_c3_pr)
        dp = calculate_dew_point(280.0, z, binary, c2_c3_pr)
        assert bp.converged and dp.converged
        assert dp.pressure < bp.pressure


# ---------------------------------------------------------------------------
# 4. Convergence options — tolerance, initial guess effects
# ---------------------------------------------------------------------------

class TestConvergenceOptions:

    def test_custom_tolerance_bubble(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = calculate_bubble_point(300.0, np.array([0.5, 0.5]), binary, c1_c10_pr, tolerance=1e-6)
        assert result.converged is True
        assert result.residual < 1e-6

    def test_custom_tolerance_dew(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_dew_point(250.0, np.array([0.5, 0.5]), binary, c1_c4_pr, tolerance=1e-6)
        assert result.converged is True
        assert result.residual < 1e-6

    def test_initial_pressure_guess_bubble(self, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        result = calculate_bubble_point(300.0, np.array([0.5, 0.5]), binary, c1_c10_pr, pressure_initial=5e6)
        assert result.converged is True

    def test_initial_pressure_guess_dew(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_dew_point(250.0, np.array([0.5, 0.5]), binary, c1_c4_pr, pressure_initial=5e5)
        assert result.converged is True


# ---------------------------------------------------------------------------
# 5. Edge cases — near-critical, degenerate boundaries, input validation
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_bubble_rejects_degenerate_trivial(self, components):
        T = 573.15
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [components[c] for c in ("CO2", "C1", "C2", "C3", "C4")]
        eos = PengRobinsonEOS(mixture)
        with pytest.raises(PhaseError, match="degenerate trivial stability solution"):
            calculate_bubble_point(T, z, mixture, eos)

    def test_dew_rejects_degenerate_trivial(self, components):
        T = 573.15
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [components[c] for c in ("CO2", "C1", "C2", "C3", "C4")]
        eos = PengRobinsonEOS(mixture)
        with pytest.raises(PhaseError, match="degenerate trivial stability solution"):
            calculate_dew_point(T, z, mixture, eos)

    def test_bubble_recovers_upper_branch(self, components):
        T = 296.93928571428575
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [components[c] for c in ("CO2", "C1", "C2", "C3", "C4")]
        eos = PengRobinsonEOS(mixture)
        result = calculate_bubble_point(
            T, z, mixture, eos,
            pressure_initial=55.38207428791868e5,
            post_check_stability_flip=True,
            post_check_action="raise",
        )
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.pressure > 6.0e6

    def test_bubble_guess_robust_volatile_oil(self, components):
        T = 360.0
        ids = ["N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"]
        z = np.array([0.0021, 0.0187, 0.3478, 0.0712, 0.0934, 0.0302, 0.0431, 0.0276, 0.0418, 0.0574, 0.0835, 0.0886, 0.0946], dtype=float)
        z /= z.sum()
        mixture = [components[c] for c in ids]
        eos = PengRobinsonEOS(mixture)

        ref = calculate_bubble_point(T, z, mixture, eos, post_check_stability_flip=True)
        assert ref.status == ConvergenceStatus.CONVERGED

        for guess in [1e5, 1e6, 5e7]:
            result = calculate_bubble_point(T, z, mixture, eos, pressure_initial=guess, post_check_stability_flip=True)
            assert result.status == ConvergenceStatus.CONVERGED
            assert result.pressure == pytest.approx(ref.pressure, abs=5e3)

    @pytest.mark.parametrize(
        "func",
        [calculate_bubble_point, calculate_dew_point],
        ids=["bubble", "dew"],
    )
    def test_invalid_composition_sum(self, func, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        with pytest.raises(ValidationError):
            func(300.0, np.array([0.5, 0.3]), binary, c1_c10_pr)

    @pytest.mark.parametrize(
        "func",
        [calculate_bubble_point, calculate_dew_point],
        ids=["bubble", "dew"],
    )
    def test_negative_temperature(self, func, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        with pytest.raises(ValidationError):
            func(-100.0, np.array([0.5, 0.5]), binary, c1_c10_pr)

    @pytest.mark.parametrize(
        "func",
        [calculate_bubble_point, calculate_dew_point],
        ids=["bubble", "dew"],
    )
    def test_composition_length_mismatch(self, func, components, c1_c10_pr):
        binary = [components["C1"], components["C10"]]
        with pytest.raises(ValidationError):
            func(300.0, np.array([0.33, 0.33, 0.34]), binary, c1_c10_pr)

    @pytest.mark.parametrize(
        "func",
        [calculate_bubble_point, calculate_dew_point],
        ids=["bubble", "dew"],
    )
    def test_empty_component_list(self, func):
        with pytest.raises(ValidationError, match="Component list cannot be empty"):
            func(300.0, np.array([1.0]), [], None)

    def test_bubble_point_nan_composition(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        with pytest.raises(ValidationError, match="NaN or Inf"):
            calculate_bubble_point(300.0, np.array([np.nan, 0.5]), binary, c1_c4_pr)


# ---------------------------------------------------------------------------
# 6. Convergence history and iteration-budget tracking
#    (absorbed from contracts/test_robustness.py)
# ---------------------------------------------------------------------------

class TestSaturationConvergenceTracking:

    def test_bubble_point_populates_history(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_bubble_point(280.0, np.array([0.5, 0.5]), binary, c1_c4_pr)
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.history is not None
        assert isinstance(result.history.n_iterations, int)

    def test_dew_point_populates_history(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_dew_point(280.0, np.array([0.5, 0.5]), binary, c1_c4_pr)
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.history is not None
        assert isinstance(result.history.n_iterations, int)

    def test_bubble_point_max_iters_with_very_low_limit(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_bubble_point(250.0, np.array([0.5, 0.5]), binary, c1_c4_pr,
                                        max_iterations=2)
        assert result is not None
        assert result.status == ConvergenceStatus.MAX_ITERS
        assert result.iterations <= 2
        assert result.converged is False

    def test_dew_point_max_iters_with_very_low_limit(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_dew_point(280.0, np.array([0.5, 0.5]), binary, c1_c4_pr,
                                     max_iterations=2)
        assert result is not None
        assert result.status == ConvergenceStatus.MAX_ITERS
        assert result.iterations <= 2
        assert result.converged is False

    def test_bubble_point_history_has_residuals(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_bubble_point(280.0, np.array([0.5, 0.5]), binary, c1_c4_pr)
        if result.history and result.history.n_iterations > 0:
            assert len(result.history.residuals) > 0

    def test_dew_point_history_has_residuals(self, components, c1_c4_pr):
        binary = [components["C1"], components["C4"]]
        result = calculate_dew_point(280.0, np.array([0.5, 0.5]), binary, c1_c4_pr)
        if result.history and result.history.n_iterations > 0:
            assert len(result.history.residuals) > 0
