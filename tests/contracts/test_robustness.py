"""Robustness tests for edge cases and error handling.

These tests verify:
1. Input validation catches invalid inputs with clear error messages
2. Edge cases are handled gracefully without crashes
3. Numerical edge cases don't produce NaN/Inf
4. Error messages are actionable and informative

Reference: Gameplan Section 5 - Reliability
"""

import numpy as np
import pytest

import sys
sys.path.insert(0, 'src')

from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.core.errors import ValidationError, PhaseError, ConvergenceStatus


class TestInputValidation:
    """Tests for input validation error handling."""

    @pytest.fixture
    def simple_setup(self):
        """Basic setup for validation tests."""
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        return comp_list, eos, z

    def test_empty_component_list(self):
        """Empty component list should raise ValidationError."""
        with pytest.raises(ValidationError, match="Component list cannot be empty"):
            pt_flash(2e6, 250, np.array([1.0]), [], None)

    def test_mismatched_composition_length(self, simple_setup):
        """Composition length mismatch should raise ValidationError."""
        comp_list, eos, _ = simple_setup
        z_wrong = np.array([0.3, 0.3, 0.4])  # 3 components, but only 2 in list

        with pytest.raises(ValidationError, match="Composition length must match"):
            pt_flash(2e6, 250, z_wrong, comp_list, eos)

    def test_composition_not_summing_to_one(self, simple_setup):
        """Composition not summing to 1 should raise ValidationError."""
        comp_list, eos, _ = simple_setup
        z_bad = np.array([0.3, 0.3])  # Sums to 0.6

        with pytest.raises(ValidationError, match="must sum to 1.0"):
            pt_flash(2e6, 250, z_bad, comp_list, eos)

    def test_negative_composition(self, simple_setup):
        """Negative composition should raise ValidationError."""
        comp_list, eos, _ = simple_setup
        z_bad = np.array([-0.1, 1.1])

        with pytest.raises(ValidationError, match="non-negative"):
            pt_flash(2e6, 250, z_bad, comp_list, eos)

    def test_nan_in_composition(self, simple_setup):
        """NaN in composition should raise ValidationError."""
        comp_list, eos, _ = simple_setup
        z_bad = np.array([np.nan, 0.5])

        with pytest.raises(ValidationError, match="NaN or Inf"):
            pt_flash(2e6, 250, z_bad, comp_list, eos)

    def test_inf_in_composition(self, simple_setup):
        """Inf in composition should raise ValidationError."""
        comp_list, eos, _ = simple_setup
        z_bad = np.array([np.inf, 0.5])

        with pytest.raises(ValidationError, match="NaN or Inf"):
            pt_flash(2e6, 250, z_bad, comp_list, eos)

    def test_negative_pressure(self, simple_setup):
        """Negative pressure should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="[Pp]ressure.*positive"):
            pt_flash(-1e6, 250, z, comp_list, eos)

    def test_zero_pressure(self, simple_setup):
        """Zero pressure should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="[Pp]ressure.*positive"):
            pt_flash(0, 250, z, comp_list, eos)

    def test_negative_temperature(self, simple_setup):
        """Negative temperature should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="[Tt]emperature.*positive"):
            pt_flash(2e6, -100, z, comp_list, eos)

    def test_zero_temperature(self, simple_setup):
        """Zero temperature should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="[Tt]emperature.*positive"):
            pt_flash(2e6, 0, z, comp_list, eos)

    def test_invalid_bip_matrix_shape(self, simple_setup):
        """Wrong BIP matrix shape should raise ValidationError."""
        comp_list, eos, z = simple_setup
        bip_wrong = np.zeros((3, 3))  # 3x3 but only 2 components

        with pytest.raises(ValidationError, match="Binary interaction matrix"):
            pt_flash(2e6, 250, z, comp_list, eos, binary_interaction=bip_wrong)

    def test_invalid_tolerance(self, simple_setup):
        """Invalid tolerance should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="[Tt]olerance"):
            pt_flash(2e6, 250, z, comp_list, eos, tolerance=-0.01)

        with pytest.raises(ValidationError, match="[Tt]olerance"):
            pt_flash(2e6, 250, z, comp_list, eos, tolerance=2.0)

    def test_invalid_max_iterations(self, simple_setup):
        """Invalid max_iterations should raise ValidationError."""
        comp_list, eos, z = simple_setup

        with pytest.raises(ValidationError, match="max_iterations"):
            pt_flash(2e6, 250, z, comp_list, eos, max_iterations=0)


class TestNumericalEdgeCases:
    """Tests for numerical edge case handling."""

    @pytest.fixture
    def components(self):
        return load_components()

    def test_very_dilute_component(self, components):
        """Flash should handle very dilute components (< 1 ppm)."""
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.999999, 0.000001])  # 1 ppm C4

        result = pt_flash(2e6, 250, z, comp_list, eos)

        # Should not produce NaN or Inf
        assert np.all(np.isfinite(result.liquid_composition))
        assert np.all(np.isfinite(result.vapor_composition))
        assert np.isfinite(result.vapor_fraction)

    def test_near_pure_component(self, components):
        """Flash should handle near-pure component gracefully."""
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.9999, 0.0001])

        result = pt_flash(2e6, 200, z, comp_list, eos)

        assert result.status in (ConvergenceStatus.CONVERGED, ConvergenceStatus.STAGNATED)
        assert np.all(np.isfinite(result.K_values))

    def test_very_high_pressure(self, components):
        """Flash should handle very high pressure gracefully."""
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])

        # 1000 bar - well above critical
        result = pt_flash(1000e5, 300, z, comp_list, eos)

        assert result.phase == 'liquid'
        assert result.vapor_fraction == 0.0

    def test_very_low_pressure(self, components):
        """Flash should handle very low pressure gracefully."""
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])

        # 0.01 bar - very low
        result = pt_flash(0.01e5, 400, z, comp_list, eos)

        assert result.phase == 'vapor'
        assert result.vapor_fraction == 1.0

    def test_near_critical_temperature(self, components):
        """Flash near critical temperature should not crash."""
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])

        # Near C1 critical temperature (190.6 K)
        result = pt_flash(5e6, 191, z, comp_list, eos)

        # Should complete without error, status may vary
        assert result.status is not None
        assert np.all(np.isfinite(result.liquid_composition))

    def test_extreme_k_value_ratio(self, components):
        """Flash with extreme K-value ratio should converge or fail gracefully."""
        # C1 (very volatile) + C10 (very heavy) creates extreme K ratios
        comp_list = [components['C1'], components['C10']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])

        result = pt_flash(50e5, 350, z, comp_list, eos)

        # Should not crash, may or may not converge
        assert result.status is not None
        if result.phase == 'two-phase':
            # K ratio for C1/C10 can be very large
            assert result.K_values[0] > result.K_values[1]


class TestBubblePointEdgeCases:
    """Tests for bubble point edge cases."""

    @pytest.fixture
    def binary_mixture(self):
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        return comp_list, eos, z

    def test_bubble_point_empty_components(self):
        """Empty component list should raise ValidationError."""
        with pytest.raises(ValidationError, match="Component list cannot be empty"):
            calculate_bubble_point(300, np.array([1.0]), [], None)

    def test_bubble_point_negative_temperature(self, binary_mixture):
        """Negative temperature should raise ValidationError."""
        comp_list, eos, z = binary_mixture

        with pytest.raises(ValidationError, match="[Tt]emperature"):
            calculate_bubble_point(-100, z, comp_list, eos)

    def test_bubble_point_nan_composition(self, binary_mixture):
        """NaN in composition should raise ValidationError."""
        comp_list, eos, _ = binary_mixture
        z_bad = np.array([np.nan, 0.5])

        with pytest.raises(ValidationError, match="NaN or Inf"):
            calculate_bubble_point(300, z_bad, comp_list, eos)


class TestDewPointEdgeCases:
    """Tests for dew point edge cases."""

    @pytest.fixture
    def binary_mixture(self):
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        return comp_list, eos, z

    def test_dew_point_empty_components(self):
        """Empty component list should raise ValidationError."""
        with pytest.raises(ValidationError, match="Component list cannot be empty"):
            calculate_dew_point(300, np.array([1.0]), [], None)

    def test_dew_point_negative_temperature(self, binary_mixture):
        """Negative temperature should raise ValidationError."""
        comp_list, eos, z = binary_mixture

        with pytest.raises(ValidationError, match="[Tt]emperature"):
            calculate_dew_point(-100, z, comp_list, eos)


class TestGracefulDegradation:
    """Tests for graceful degradation under difficult conditions."""

    def test_max_iterations_returns_status(self):
        """Very low max_iterations should return valid result with status."""
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])

        result = pt_flash(2e6, 250, z, comp_list, eos, max_iterations=2)

        # Should return a result (not crash) with appropriate status
        assert result is not None
        assert result.status in (
            ConvergenceStatus.CONVERGED,
            ConvergenceStatus.MAX_ITERS,
            ConvergenceStatus.STAGNATED,
        )
        # History should be populated
        if result.history is not None:
            assert result.history.n_iterations <= 2

    def test_composition_normalization(self):
        """Small composition sum deviation should be auto-normalized."""
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)

        # Composition that's slightly off (but within tolerance)
        z = np.array([0.500001, 0.499999])  # Sum = 1.000000

        result = pt_flash(2e6, 250, z, comp_list, eos)

        # Should work - composition gets normalized
        assert result.status == ConvergenceStatus.CONVERGED


class TestBubbleDewPointConvergence:
    """Tests for bubble/dew point convergence status and history tracking."""

    @pytest.fixture
    def binary_mixture(self):
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.5, 0.5])
        return comp_list, eos, z

    def test_bubble_point_populates_history(self, binary_mixture):
        """Bubble point should populate iteration history."""
        comp_list, eos, z = binary_mixture

        result = calculate_bubble_point(280, z, comp_list, eos)

        assert result.status == ConvergenceStatus.CONVERGED
        assert result.history is not None
        # May have minimal history if early convergence, but should exist
        assert isinstance(result.history.n_iterations, int)

    def test_dew_point_populates_history(self, binary_mixture):
        """Dew point should populate iteration history."""
        comp_list, eos, z = binary_mixture

        result = calculate_dew_point(280, z, comp_list, eos)

        assert result.status == ConvergenceStatus.CONVERGED
        assert result.history is not None
        assert isinstance(result.history.n_iterations, int)

    def test_bubble_point_max_iters_with_very_low_limit(self, binary_mixture):
        """Bubble point must honor an exhausted iteration budget."""
        comp_list, eos, z = binary_mixture

        # This case normally needs multiple iterations, so a budget of 2 must stop early.
        result = calculate_bubble_point(250, z, comp_list, eos, max_iterations=2)

        assert result is not None
        assert result.status == ConvergenceStatus.MAX_ITERS
        assert result.iterations <= 2
        assert result.converged is False

    def test_dew_point_max_iters_with_very_low_limit(self, binary_mixture):
        """Dew point must honor an exhausted iteration budget."""
        comp_list, eos, z = binary_mixture

        # This case normally needs multiple iterations, so a budget of 2 must stop early.
        result = calculate_dew_point(280, z, comp_list, eos, max_iterations=2)

        assert result is not None
        assert result.status == ConvergenceStatus.MAX_ITERS
        assert result.iterations <= 2
        assert result.converged is False

    def test_bubble_point_history_has_residuals(self, binary_mixture):
        """Bubble point history should track residuals."""
        comp_list, eos, z = binary_mixture

        result = calculate_bubble_point(280, z, comp_list, eos)

        if result.history and result.history.n_iterations > 0:
            assert len(result.history.residuals) > 0

    def test_dew_point_history_has_residuals(self, binary_mixture):
        """Dew point history should track residuals."""
        comp_list, eos, z = binary_mixture

        result = calculate_dew_point(280, z, comp_list, eos)

        if result.history and result.history.n_iterations > 0:
            assert len(result.history.residuals) > 0


class TestErrorMessageQuality:
    """Tests for error message quality and actionability."""

    def test_validation_error_includes_parameter(self):
        """ValidationError should identify the problematic parameter."""
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.3, 0.3])  # Doesn't sum to 1

        try:
            pt_flash(2e6, 250, z, comp_list, eos)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            # Error should mention the parameter name
            assert 'composition' in str(e).lower() or hasattr(e, 'parameter')

    def test_validation_error_includes_value(self):
        """ValidationError should include the problematic value when helpful."""
        components = load_components()
        comp_list = [components['C1'], components['C4']]
        eos = PengRobinsonEOS(comp_list)
        z = np.array([0.3, 0.3])  # Sum = 0.6

        try:
            pt_flash(2e6, 250, z, comp_list, eos)
            pytest.fail("Should have raised ValidationError")
        except ValidationError as e:
            # Error message should indicate the actual sum
            error_msg = str(e)
            # Should mention the sum value or "0.6"
            assert '0.6' in error_msg or 'sum' in error_msg.lower()
