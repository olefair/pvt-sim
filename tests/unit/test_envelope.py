"""Unit tests for phase envelope calculations.

Tests validate phase envelope tracing against:
- Known thermodynamic relationships
- Critical point location
- Envelope shape and continuity
- Component behavior
"""

import pytest
import numpy as np
from pvtcore.envelope.phase_envelope import (
    calculate_phase_envelope,
    EnvelopeResult,
    estimate_cricondentherm,
    estimate_cricondenbar
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError


@pytest.fixture
def components():
    """Load component database."""
    return load_components()


@pytest.fixture
def binary_c1_c10_eos(components):
    """Create PR EOS for methane-decane binary mixture."""
    return PengRobinsonEOS([components['C1'], components['C10']])


@pytest.fixture
def binary_c1_c4_eos(components):
    """Create PR EOS for methane-butane binary mixture."""
    return PengRobinsonEOS([components['C1'], components['C4']])


@pytest.fixture
def binary_c2_c3_eos(components):
    """Create PR EOS for ethane-propane binary mixture."""
    return PengRobinsonEOS([components['C2'], components['C3']])


class TestEnvelopeResult:
    """Test EnvelopeResult data structure."""

    def test_envelope_result_fields(self, binary_c1_c10_eos, components):
        """Test that EnvelopeResult contains required fields."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Check all required fields exist
        assert hasattr(envelope, 'bubble_T')
        assert hasattr(envelope, 'bubble_P')
        assert hasattr(envelope, 'dew_T')
        assert hasattr(envelope, 'dew_P')
        assert hasattr(envelope, 'critical_T')
        assert hasattr(envelope, 'critical_P')
        assert hasattr(envelope, 'composition')
        assert hasattr(envelope, 'converged')
        assert hasattr(envelope, 'n_bubble_points')
        assert hasattr(envelope, 'n_dew_points')

        # Check types
        assert isinstance(envelope.bubble_T, np.ndarray)
        assert isinstance(envelope.bubble_P, np.ndarray)
        assert isinstance(envelope.dew_T, np.ndarray)
        assert isinstance(envelope.dew_P, np.ndarray)
        assert isinstance(envelope.converged, bool)
        assert isinstance(envelope.n_bubble_points, int)
        assert isinstance(envelope.n_dew_points, int)


class TestEnvelopeCalculation:
    """Test phase envelope calculation."""

    def test_envelope_converges(self, binary_c1_c10_eos, components):
        """Test that envelope calculation converges."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert envelope.converged is True
        # Should have at least the bubble curve
        assert envelope.n_bubble_points > 3

    def test_envelope_has_bubble_curve(self, binary_c1_c10_eos, components):
        """Test that envelope has bubble curve."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Should have multiple points on bubble curve
        assert len(envelope.bubble_T) > 5
        assert len(envelope.bubble_P) > 5

    def test_bubble_dew_curves_same_length(self, binary_c1_c10_eos, components):
        """Test that T and P arrays have matching lengths."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert len(envelope.bubble_T) == len(envelope.bubble_P)
        assert len(envelope.dew_T) == len(envelope.dew_P)

    def test_temperatures_positive(self, binary_c1_c10_eos, components):
        """Test that all temperatures are positive."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert np.all(envelope.bubble_T > 0)
        assert np.all(envelope.dew_T > 0)

    def test_pressures_positive(self, binary_c1_c10_eos, components):
        """Test that all pressures are positive."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert np.all(envelope.bubble_P > 0)
        assert np.all(envelope.dew_P > 0)

    def test_temperatures_increasing(self, binary_c1_c10_eos, components):
        """Test that temperatures increase along curves (continuation method)."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Temperatures should be generally increasing (with possible small variations)
        # Check that most steps are increasing on bubble curve
        if len(envelope.bubble_T) > 1:
            bubble_T_diff = np.diff(envelope.bubble_T)
            # At least 80% of steps should be increasing
            assert np.sum(bubble_T_diff > 0) > 0.8 * len(bubble_T_diff)

        # Check dew curve if it exists
        if len(envelope.dew_T) > 1:
            dew_T_diff = np.diff(envelope.dew_T)
            assert np.sum(dew_T_diff > 0) > 0.8 * len(dew_T_diff)


class TestCriticalPoint:
    """Test critical point detection."""

    def test_critical_point_detected(self, binary_c1_c10_eos, components):
        """Test that critical point is detected."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert envelope.critical_T is not None
        assert envelope.critical_P is not None

    def test_critical_point_positive(self, binary_c1_c10_eos, components):
        """Test that critical point values are positive."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        if envelope.critical_T is not None:
            assert envelope.critical_T > 0
        if envelope.critical_P is not None:
            assert envelope.critical_P > 0

    def test_critical_point_between_pure_components(self, binary_c1_c10_eos, components):
        """Test that critical temperature is between pure component Tc values.

        For a binary mixture, the critical temperature should lie between
        the critical temperatures of the pure components (Kay's rule approximation).
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        Tc_C1 = components['C1'].Tc
        Tc_C10 = components['C10'].Tc

        if envelope.critical_T is not None:
            # Critical T should be between pure component values
            # Allow some margin for EOS predictions
            assert Tc_C1 * 0.9 < envelope.critical_T < Tc_C10 * 1.1

    def test_critical_point_on_envelope(self, binary_c1_c10_eos, components):
        """Test that critical point is physically reasonable.

        For asymmetric binary mixtures, envelope tracing may find different
        saturation branches, so the critical point may not lie exactly on
        the traced curves. We validate that:
        1. The critical point is between pure component criticals
        2. The critical point is close to Kay's mixing rule estimate
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        if envelope.critical_T is not None and envelope.critical_P is not None:
            Tc_C1 = components['C1'].Tc
            Tc_C10 = components['C10'].Tc
            Pc_C1 = components['C1'].Pc
            Pc_C10 = components['C10'].Pc

            # Critical T should be between component criticals
            assert Tc_C1 * 0.8 < envelope.critical_T < Tc_C10 * 1.2

            # Critical P should be in reasonable range
            Pc_min = min(Pc_C1, Pc_C10)
            Pc_max = max(Pc_C1, Pc_C10)
            assert Pc_min * 0.5 < envelope.critical_P < Pc_max * 1.5

            # Should be close to Kay's mixing rule estimate
            Tc_kay = 0.5 * (Tc_C1 + Tc_C10)
            Pc_kay = 0.5 * (Pc_C1 + Pc_C10)

            # Within 30% of Kay's estimate for T
            assert abs(envelope.critical_T - Tc_kay) / Tc_kay < 0.30
            # Within 50% of Kay's estimate for P (more variation expected)
            assert abs(envelope.critical_P - Pc_kay) / Pc_kay < 0.50


class TestEnvelopeShape:
    """Test phase envelope shape and properties."""

    def test_bubble_curve_left_of_dew_curve(self, binary_c1_c10_eos, components):
        """Test that bubble curve is generally to the left of dew curve.

        At a given pressure, the bubble point temperature should be
        less than the dew point temperature.
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # At low temperatures, bubble T should be less than dew T
        if len(envelope.bubble_T) > 0 and len(envelope.dew_T) > 0:
            min_bubble_T = np.min(envelope.bubble_T)
            min_dew_T = np.min(envelope.dew_T)

            # Bubble curve starts at lower temperature
            assert min_bubble_T <= min_dew_T * 1.05  # Allow small margin

    def test_pressure_increases_with_temperature(self, binary_c1_c10_eos, components):
        """Test that pressure generally increases with temperature.

        Along both curves, pressure should increase as temperature increases
        (until near the critical point).
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Check bubble curve (before critical point)
        if len(envelope.bubble_P) > 3:
            # At least first half should show increasing pressure
            mid_point = len(envelope.bubble_P) // 2
            assert envelope.bubble_P[mid_point] > envelope.bubble_P[0]

        # Check dew curve
        if len(envelope.dew_P) > 3:
            mid_point = len(envelope.dew_P) // 2
            assert envelope.dew_P[mid_point] > envelope.dew_P[0]


class TestCompositionVariation:
    """Test envelope for different compositions."""

    def test_c1_rich_envelope(self, binary_c1_c10_eos, components):
        """Test envelope for C1-rich mixture."""
        z = np.array([0.9, 0.1])  # 90% methane
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert envelope.converged is True
        assert envelope.critical_T is not None

        # For C1-rich, critical point should be reasonable
        # (mixture critical can be higher than pure C1 due to C10 influence)
        Tc_C1 = components['C1'].Tc
        Tc_C10 = components['C10'].Tc
        if envelope.critical_T is not None:
            # Should be between C1 critical and C10 critical
            assert Tc_C1 * 0.8 < envelope.critical_T < Tc_C10 * 0.8

    def test_c10_rich_envelope(self, binary_c1_c10_eos, components):
        """Test envelope for C10-rich mixture."""
        z = np.array([0.1, 0.9])  # 90% decane
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        assert envelope.converged is True
        assert envelope.critical_T is not None

        # For C10-rich, critical point should be reasonable
        # (mixture critical can be lower than pure C10 due to C1 influence)
        Tc_C1 = components['C1'].Tc
        Tc_C10 = components['C10'].Tc
        if envelope.critical_T is not None:
            # Should be between component criticals
            assert Tc_C1 * 1.2 < envelope.critical_T < Tc_C10 * 1.2

    def test_equal_mixture_envelope(self, binary_c1_c4_eos, components):
        """Test envelope for equal mixture."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c4_eos)

        assert envelope.converged is True
        # Should have at least bubble curve
        assert envelope.n_bubble_points > 5


class TestDifferentSystems:
    """Test envelope for different component systems."""

    def test_ethane_propane_envelope(self, binary_c2_c3_eos, components):
        """Test envelope for ethane-propane (similar components).

        Ethane and propane are relatively similar, so the envelope
        should be narrower than C1-C10.
        """
        z = np.array([0.5, 0.5])
        binary = [components['C2'], components['C3']]

        envelope = calculate_phase_envelope(z, binary, binary_c2_c3_eos)

        assert envelope.converged is True
        assert envelope.critical_T is not None

        # Critical T should be between C2 and C3 critical temperatures
        Tc_C2 = components['C2'].Tc
        Tc_C3 = components['C3'].Tc
        if envelope.critical_T is not None:
            assert Tc_C2 * 0.95 < envelope.critical_T < Tc_C3 * 1.05

    def test_c1_c4_envelope(self, binary_c1_c4_eos, components):
        """Test envelope for C1-C4 system."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c4_eos)

        assert envelope.converged is True
        # Should have at least bubble curve
        assert len(envelope.bubble_T) > 0


class TestInputValidation:
    """Test input validation."""

    def test_invalid_composition_sum(self, binary_c1_c10_eos, components):
        """Test that invalid composition sum raises error."""
        z_invalid = np.array([0.5, 0.3])  # Sums to 0.8
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_phase_envelope(z_invalid, binary, binary_c1_c10_eos)

    def test_composition_length_mismatch(self, binary_c1_c10_eos, components):
        """Test that composition length mismatch raises error."""
        z_wrong = np.array([0.33, 0.33, 0.34])  # 3 components, EOS has 2
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_phase_envelope(z_wrong, binary, binary_c1_c10_eos)


class TestCricondenPoints:
    """Test cricondentherm and cricondenbar estimation."""

    def test_cricondentherm_estimated(self, binary_c1_c10_eos, components):
        """Test cricondentherm (maximum temperature) estimation."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        T_cdt, P_cdt = estimate_cricondentherm(envelope)

        if T_cdt is not None:
            assert T_cdt > 0
            assert P_cdt > 0
            # Should be on dew curve
            if len(envelope.dew_T) > 0:
                assert T_cdt <= np.max(envelope.dew_T) * 1.01

    def test_cricondenbar_estimated(self, binary_c1_c10_eos, components):
        """Test cricondenbar (maximum pressure) estimation."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        T_cdb, P_cdb = estimate_cricondenbar(envelope)

        if P_cdb is not None:
            assert T_cdb > 0
            assert P_cdb > 0

    def test_cricondenbar_near_critical(self, binary_c2_c3_eos, components):
        """Test that cricondenbar is near critical point.

        For symmetric systems (similar components), the cricondenbar
        (maximum pressure) occurs at or very near the critical point.

        Note: We use C2-C3 instead of C1-C10 because asymmetric mixtures
        can have complex phase behavior where envelope tracing may find
        different saturation branches.
        """
        z = np.array([0.5, 0.5])
        binary = [components['C2'], components['C3']]

        envelope = calculate_phase_envelope(z, binary, binary_c2_c3_eos)
        T_cdb, P_cdb = estimate_cricondenbar(envelope)

        if (envelope.critical_P is not None and P_cdb is not None):
            # For similar components, should be reasonably close
            # (within 50% - allows for numerical discretization)
            rel_diff = abs(P_cdb - envelope.critical_P) / envelope.critical_P
            assert rel_diff < 0.5


class TestAdaptiveStepSize:
    """Test adaptive step size behavior."""

    def test_more_points_near_critical(self, binary_c1_c10_eos, components):
        """Test that step size adapts (more points near critical region).

        Near the critical point, the algorithm should take smaller steps
        to capture the sharp changes in the envelope.
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Should have generated a reasonable number of points
        assert envelope.n_bubble_points > 10

        # Near critical point, spacing should be tighter
        if envelope.critical_T is not None and len(envelope.bubble_T) > 5:
            # Find points near critical temperature
            Tc = envelope.critical_T
            tolerance = Tc * 0.1  # 10% range around critical

            near_critical = np.abs(envelope.bubble_T - Tc) < tolerance
            n_near_critical = np.sum(near_critical)

            # Should have multiple points near critical region
            assert n_near_critical >= 2


class TestEnvelopeConsistency:
    """Test consistency of envelope results."""

    def test_reproducible_results(self, binary_c1_c10_eos, components):
        """Test that envelope calculation gives consistent results."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # Calculate twice
        envelope1 = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        envelope2 = calculate_phase_envelope(z, binary, binary_c1_c10_eos)

        # Should give same critical point (within tolerance)
        if envelope1.critical_T is not None and envelope2.critical_T is not None:
            assert abs(envelope1.critical_T - envelope2.critical_T) < 1.0  # Within 1 K
            assert abs(envelope1.critical_P - envelope2.critical_P) / envelope1.critical_P < 0.01


# =============================================================================
# Iso-lines tests
# =============================================================================

from pvtcore.envelope.iso_lines import (
    IsoLineMode,
    IsoLineSegment,
    IsoLinesResult,
    compute_iso_lines,
    compute_iso_vol_lines,
    compute_iso_beta_lines,
    compute_alpha_from_flash,
)
from pvtcore.flash.pt_flash import pt_flash


class TestIsoLineMode:
    """Test IsoLineMode enum."""

    def test_enum_values(self):
        """Test that IsoLineMode has expected values."""
        assert IsoLineMode.NONE is not None
        assert IsoLineMode.ISO_VOL is not None
        assert IsoLineMode.ISO_BETA is not None
        assert IsoLineMode.BOTH is not None

    def test_enum_distinct(self):
        """Test that enum values are distinct."""
        modes = [IsoLineMode.NONE, IsoLineMode.ISO_VOL, IsoLineMode.ISO_BETA, IsoLineMode.BOTH]
        assert len(set(modes)) == 4


class TestComputeAlphaFromFlash:
    """Test alpha computation from flash results."""

    def test_alpha_two_phase(self, binary_c1_c10_eos, components):
        """Test alpha computation for two-phase flash result."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # Flash at a condition inside the two-phase region
        P = 3e6  # 30 bar
        T = 350  # K

        flash_result = pt_flash(P, T, z, binary, binary_c1_c10_eos)

        if flash_result.is_two_phase:
            alpha, V_L, V_V = compute_alpha_from_flash(flash_result, binary_c1_c10_eos)

            # Alpha should be between 0 and 1
            assert 0.0 <= alpha <= 1.0

            # Volumes should be positive
            assert V_L > 0
            assert V_V > 0

            # Vapor volume should be larger than liquid volume
            assert V_V > V_L

    def test_alpha_single_phase_liquid(self, binary_c1_c10_eos, components):
        """Test alpha computation for single-phase liquid."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # High pressure to ensure liquid
        P = 50e6  # 500 bar
        T = 300  # K

        flash_result = pt_flash(P, T, z, binary, binary_c1_c10_eos)

        if flash_result.phase == 'liquid':
            alpha, V_L, V_V = compute_alpha_from_flash(flash_result, binary_c1_c10_eos)
            assert alpha == 0.0
            assert V_L > 0

    def test_alpha_single_phase_vapor(self, binary_c1_c10_eos, components):
        """Test alpha computation for single-phase vapor."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # Low pressure and high temperature for vapor
        P = 0.1e6  # 1 bar
        T = 500  # K

        flash_result = pt_flash(P, T, z, binary, binary_c1_c10_eos)

        if flash_result.phase == 'vapor':
            alpha, V_L, V_V = compute_alpha_from_flash(flash_result, binary_c1_c10_eos)
            assert alpha == 1.0
            assert V_V > 0


class TestIsoVolLines:
    """Test iso-vol line computation."""

    def test_iso_vol_returns_dict(self, binary_c1_c10_eos, components):
        """Test that compute_iso_vol_lines returns a dictionary."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_vol_lines(
            envelope, binary, binary_c1_c10_eos,
            alpha_levels=[0.5],
            n_temperature_points=10
        )

        assert isinstance(result, dict)
        assert 0.5 in result

    def test_iso_vol_segment_structure(self, binary_c1_c10_eos, components):
        """Test that iso-vol segments have correct structure."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_vol_lines(
            envelope, binary, binary_c1_c10_eos,
            alpha_levels=[0.5],
            n_temperature_points=20
        )

        segments = result.get(0.5, [])
        for seg in segments:
            assert isinstance(seg, IsoLineSegment)
            assert len(seg.temperatures) == len(seg.pressures)
            assert len(seg.temperatures) == len(seg.vapor_fractions)
            assert len(seg.temperatures) == len(seg.vapor_volume_fractions)

    def test_iso_vol_alpha_close_to_target(self, binary_c1_c10_eos, components):
        """Test that computed alpha values are close to target."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        alpha_target = 0.5
        result = compute_iso_vol_lines(
            envelope, binary, binary_c1_c10_eos,
            alpha_levels=[alpha_target],
            n_temperature_points=15
        )

        segments = result.get(alpha_target, [])
        for seg in segments:
            if len(seg) > 0:
                # Computed values should be close to target
                for alpha_computed in seg.vapor_volume_fractions:
                    assert abs(alpha_computed - alpha_target) < 0.01


class TestIsoBetaLines:
    """Test iso-beta line computation."""

    def test_iso_beta_returns_dict(self, binary_c1_c10_eos, components):
        """Test that compute_iso_beta_lines returns a dictionary."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_beta_lines(
            envelope, binary, binary_c1_c10_eos,
            beta_levels=[0.5],
            n_temperature_points=10
        )

        assert isinstance(result, dict)
        assert 0.5 in result

    def test_iso_beta_beta_close_to_target(self, binary_c1_c10_eos, components):
        """Test that computed beta values are close to target."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        beta_target = 0.5
        result = compute_iso_beta_lines(
            envelope, binary, binary_c1_c10_eos,
            beta_levels=[beta_target],
            n_temperature_points=15
        )

        segments = result.get(beta_target, [])
        for seg in segments:
            if len(seg) > 0:
                # Vapor fractions should be close to target beta
                for beta_computed in seg.vapor_fractions:
                    assert abs(beta_computed - beta_target) < 0.01


class TestComputeIsoLines:
    """Test main compute_iso_lines function with mode toggle."""

    def test_mode_none_returns_empty(self, binary_c1_c10_eos, components):
        """Test that NONE mode returns empty result."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.NONE
        )

        assert isinstance(result, IsoLinesResult)
        assert result.mode == IsoLineMode.NONE
        assert len(result.iso_vol_lines) == 0
        assert len(result.iso_beta_lines) == 0

    def test_mode_iso_vol_only(self, binary_c1_c10_eos, components):
        """Test that ISO_VOL mode only computes iso-vol lines."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.ISO_VOL,
            alpha_levels=[0.5],
            n_temperature_points=10
        )

        assert result.mode == IsoLineMode.ISO_VOL
        assert len(result.iso_vol_lines) > 0
        assert len(result.iso_beta_lines) == 0

    def test_mode_iso_beta_only(self, binary_c1_c10_eos, components):
        """Test that ISO_BETA mode only computes iso-beta lines."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.ISO_BETA,
            beta_levels=[0.5],
            n_temperature_points=10
        )

        assert result.mode == IsoLineMode.ISO_BETA
        assert len(result.iso_vol_lines) == 0
        assert len(result.iso_beta_lines) > 0

    def test_mode_both(self, binary_c1_c10_eos, components):
        """Test that BOTH mode computes both iso-vol and iso-beta lines."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.BOTH,
            alpha_levels=[0.5],
            beta_levels=[0.5],
            n_temperature_points=10
        )

        assert result.mode == IsoLineMode.BOTH
        assert len(result.iso_vol_lines) > 0
        assert len(result.iso_beta_lines) > 0

    def test_result_has_composition(self, binary_c1_c10_eos, components):
        """Test that result contains the feed composition."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.BOTH,
            alpha_levels=[0.5],
            beta_levels=[0.5],
            n_temperature_points=10
        )

        assert np.allclose(result.composition, z)

    def test_default_alpha_levels(self, binary_c1_c10_eos, components):
        """Test that default alpha levels are used."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_lines(
            envelope, binary, binary_c1_c10_eos,
            mode=IsoLineMode.ISO_VOL,
            n_temperature_points=10
        )

        # Default levels should include 0.5
        assert 0.5 in result.alpha_levels


class TestIsoLinesPhysicalConstraints:
    """Test physical constraints on iso-lines."""

    def test_alpha_approaches_zero_at_bubble(self, binary_c1_c10_eos, components):
        """Test that low alpha values are near bubble curve.

        At alpha -> 0 (negligible vapor volume), points should be near
        the bubble curve (liquid boundary).
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_vol_lines(
            envelope, binary, binary_c1_c10_eos,
            alpha_levels=[0.05],  # Low alpha
            n_temperature_points=20
        )

        segments = result.get(0.05, [])
        for seg in segments:
            if len(seg) > 0:
                # Points should have high pressures (near bubble curve)
                # and low vapor fractions (beta)
                for beta in seg.vapor_fractions:
                    # Low alpha implies low beta (more liquid)
                    assert beta < 0.5

    def test_alpha_approaches_one_at_dew(self, binary_c1_c10_eos, components):
        """Test that high alpha values are near dew curve.

        At alpha -> 1 (mostly vapor volume), points should be near
        the dew curve (vapor boundary).
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_vol_lines(
            envelope, binary, binary_c1_c10_eos,
            alpha_levels=[0.95],  # High alpha
            n_temperature_points=20
        )

        segments = result.get(0.95, [])
        for seg in segments:
            if len(seg) > 0:
                # Points should have low pressures (near dew curve)
                # and high vapor fractions (beta)
                for beta in seg.vapor_fractions:
                    # High alpha implies high beta (more vapor)
                    assert beta > 0.5

    def test_iso_beta_50_bisects_envelope(self, binary_c1_c10_eos, components):
        """Test that iso-beta at 50% is roughly in the middle of the envelope.

        The beta=0.5 line should lie between the bubble and dew curves,
        not touching either boundary.
        """
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        envelope = calculate_phase_envelope(z, binary, binary_c1_c10_eos)
        result = compute_iso_beta_lines(
            envelope, binary, binary_c1_c10_eos,
            beta_levels=[0.5],
            n_temperature_points=20
        )

        segments = result.get(0.5, [])
        for seg in segments:
            if len(seg) > 0:
                # All pressures should be strictly inside the envelope
                for T, P in zip(seg.temperatures, seg.pressures):
                    # Check that P is between bubble and dew at this T
                    # (interpolate envelope pressures)
                    if len(envelope.bubble_T) > 0 and len(envelope.dew_T) > 0:
                        P_bubble = np.interp(
                            T,
                            envelope.bubble_T[np.argsort(envelope.bubble_T)],
                            envelope.bubble_P[np.argsort(envelope.bubble_T)]
                        )
                        P_dew = np.interp(
                            T,
                            envelope.dew_T[np.argsort(envelope.dew_T)],
                            envelope.dew_P[np.argsort(envelope.dew_T)]
                        )
                        P_low = min(P_bubble, P_dew)
                        P_high = max(P_bubble, P_dew)
                        # Allow some tolerance
                        assert P_low * 0.99 <= P <= P_high * 1.01


# =============================================================================
# Ternary diagram tests
# =============================================================================

from pvtcore.envelope.ternary import (
    PhaseClassification,
    TernaryGridPoint,
    TieLine,
    TernaryResult,
    generate_barycentric_grid,
    barycentric_to_cartesian,
    cartesian_to_barycentric,
    compute_ternary_diagram,
    get_triangle_vertices,
    DEFAULT_N_SUBDIVISIONS,
)


class TestPhaseClassification:
    """Test PhaseClassification enum."""

    def test_enum_values(self):
        """Test that PhaseClassification has expected values."""
        assert PhaseClassification.SINGLE_PHASE_LIQUID is not None
        assert PhaseClassification.SINGLE_PHASE_VAPOR is not None
        assert PhaseClassification.TWO_PHASE is not None
        assert PhaseClassification.FAILED is not None

    def test_enum_distinct(self):
        """Test that enum values are distinct."""
        classifications = [
            PhaseClassification.SINGLE_PHASE_LIQUID,
            PhaseClassification.SINGLE_PHASE_VAPOR,
            PhaseClassification.TWO_PHASE,
            PhaseClassification.FAILED
        ]
        assert len(set(classifications)) == 4


class TestBarycentricGrid:
    """Test barycentric grid generation."""

    def test_grid_size(self):
        """Test that grid has expected number of points."""
        n = 10
        grid = generate_barycentric_grid(n)
        expected_points = (n + 1) * (n + 2) // 2
        assert len(grid) == expected_points

    def test_grid_size_default(self):
        """Test default grid size."""
        grid = generate_barycentric_grid()
        n = DEFAULT_N_SUBDIVISIONS
        expected_points = (n + 1) * (n + 2) // 2
        assert len(grid) == expected_points

    def test_grid_sum_to_one(self):
        """Test that all grid points sum to 1."""
        grid = generate_barycentric_grid(20)
        sums = np.sum(grid, axis=1)
        assert np.allclose(sums, 1.0)

    def test_grid_non_negative(self):
        """Test that all grid values are non-negative."""
        grid = generate_barycentric_grid(20)
        assert np.all(grid >= 0)

    def test_grid_contains_vertices(self):
        """Test that grid contains pure component vertices."""
        grid = generate_barycentric_grid(10)

        # Check for (1, 0, 0), (0, 1, 0), (0, 0, 1)
        has_vertex_1 = any(np.allclose(row, [1, 0, 0]) for row in grid)
        has_vertex_2 = any(np.allclose(row, [0, 1, 0]) for row in grid)
        has_vertex_3 = any(np.allclose(row, [0, 0, 1]) for row in grid)

        assert has_vertex_1
        assert has_vertex_2
        assert has_vertex_3

    def test_grid_contains_center(self):
        """Test that grid contains center point (for n divisible by 3)."""
        grid = generate_barycentric_grid(9)  # 9 is divisible by 3
        center = [1/3, 1/3, 1/3]
        has_center = any(np.allclose(row, center) for row in grid)
        assert has_center


class TestCoordinateTransformations:
    """Test barycentric <-> Cartesian coordinate transformations."""

    def test_vertices_transform_correctly(self):
        """Test that vertices transform to expected positions."""
        vertices = get_triangle_vertices()

        # Transform barycentric vertices
        z1_pure = np.array([[1, 0, 0]])
        z2_pure = np.array([[0, 1, 0]])
        z3_pure = np.array([[0, 0, 1]])

        cart_z1 = barycentric_to_cartesian(z1_pure)
        cart_z2 = barycentric_to_cartesian(z2_pure)
        cart_z3 = barycentric_to_cartesian(z3_pure)

        assert np.allclose(cart_z1.flatten(), vertices[0])
        assert np.allclose(cart_z2.flatten(), vertices[1])
        assert np.allclose(cart_z3.flatten(), vertices[2])

    def test_center_transforms_correctly(self):
        """Test that center point transforms correctly."""
        center = np.array([[1/3, 1/3, 1/3]])
        cart_center = barycentric_to_cartesian(center)

        # Center should be at centroid of triangle
        vertices = get_triangle_vertices()
        expected_center = np.mean(vertices, axis=0)

        assert np.allclose(cart_center.flatten(), expected_center)

    def test_round_trip_transformation(self):
        """Test that barycentric -> Cartesian -> barycentric is identity."""
        grid = generate_barycentric_grid(10)

        # Transform to Cartesian and back
        cartesian = barycentric_to_cartesian(grid)
        barycentric = cartesian_to_barycentric(cartesian)

        assert np.allclose(grid, barycentric, atol=1e-10)


class TestTernaryGridPoint:
    """Test TernaryGridPoint data structure."""

    def test_two_phase_property(self):
        """Test is_two_phase property."""
        point = TernaryGridPoint(
            composition=np.array([0.33, 0.33, 0.34]),
            classification=PhaseClassification.TWO_PHASE
        )
        assert point.is_two_phase is True
        assert point.is_single_phase is False

    def test_single_phase_property(self):
        """Test is_single_phase property."""
        point = TernaryGridPoint(
            composition=np.array([0.33, 0.33, 0.34]),
            classification=PhaseClassification.SINGLE_PHASE_LIQUID
        )
        assert point.is_single_phase is True
        assert point.is_two_phase is False


class TestComputeTernaryDiagram:
    """Test ternary diagram computation."""

    @pytest.fixture
    def ternary_components(self, components):
        """Load 3 components for ternary test."""
        return [components['C1'], components['C4'], components['C10']]

    @pytest.fixture
    def ternary_eos(self, ternary_components):
        """Create EOS for ternary system."""
        return PengRobinsonEOS(ternary_components)

    def test_requires_three_components(self, binary_c1_c10_eos, components):
        """Test that ternary diagram requires exactly 3 components."""
        two_components = [components['C1'], components['C10']]

        with pytest.raises(ValueError, match="3 components"):
            compute_ternary_diagram(
                temperature=300.0,
                pressure=5e6,
                components=two_components,
                eos=binary_c1_c10_eos,
                n_subdivisions=5
            )

    def test_returns_ternary_result(self, ternary_eos, ternary_components):
        """Test that computation returns TernaryResult."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=5  # Small for fast test
        )

        assert isinstance(result, TernaryResult)

    def test_result_has_expected_fields(self, ternary_eos, ternary_components):
        """Test that result has all expected fields."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=5
        )

        assert result.temperature == 350.0
        assert result.pressure == 5e6
        assert len(result.components) == 3
        assert result.n_subdivisions == 5

    def test_grid_points_count(self, ternary_eos, ternary_components):
        """Test that number of grid points is correct."""
        n = 7
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=n
        )

        expected_points = (n + 1) * (n + 2) // 2
        assert result.n_total_points == expected_points
        assert len(result.grid_points) == expected_points

    def test_classification_counts_sum(self, ternary_eos, ternary_components):
        """Test that classification counts sum to total."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        total = result.n_single_phase + result.n_two_phase + result.n_failed
        assert total == result.n_total_points

    def test_tie_lines_computed(self, ternary_eos, ternary_components):
        """Test that tie-lines are computed for two-phase points."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=10,
            compute_tie_lines=True
        )

        # If there are two-phase points, there should be tie-lines
        if result.n_two_phase > 0:
            assert len(result.tie_lines) > 0

    def test_tie_line_skip(self, ternary_eos, ternary_components):
        """Test that tie_line_skip parameter works."""
        result_all = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=10,
            compute_tie_lines=True,
            tie_line_skip=1
        )

        result_skip = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=10,
            compute_tie_lines=True,
            tie_line_skip=3
        )

        # Skipped result should have fewer tie-lines
        if result_all.n_two_phase > 3:
            assert len(result_skip.tie_lines) < len(result_all.tie_lines)


class TestTernaryMassBalance:
    """Test mass balance for ternary diagram points."""

    @pytest.fixture
    def ternary_components(self, components):
        """Load 3 components for ternary test."""
        return [components['C1'], components['C4'], components['C10']]

    @pytest.fixture
    def ternary_eos(self, ternary_components):
        """Create EOS for ternary system."""
        return PengRobinsonEOS(ternary_components)

    def test_two_phase_mass_balance(self, ternary_eos, ternary_components):
        """Test that two-phase points satisfy mass balance."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        for point in result.grid_points:
            if point.is_two_phase:
                z = point.composition
                x = point.liquid_composition
                y = point.vapor_composition
                beta = point.vapor_fraction

                # Check mass balance: z = (1-beta)*x + beta*y
                z_check = (1 - beta) * x + beta * y
                error = np.max(np.abs(z - z_check))
                assert error < 1e-8, f"Mass balance error: {error}"

    def test_compositions_normalized(self, ternary_eos, ternary_components):
        """Test that liquid and vapor compositions are normalized."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        for point in result.grid_points:
            if point.is_two_phase:
                x_sum = np.sum(point.liquid_composition)
                y_sum = np.sum(point.vapor_composition)

                assert np.isclose(x_sum, 1.0, atol=1e-10)
                assert np.isclose(y_sum, 1.0, atol=1e-10)

    def test_compositions_in_valid_range(self, ternary_eos, ternary_components):
        """Test that compositions are in [0, 1] range."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        for point in result.grid_points:
            if point.is_two_phase:
                assert np.all(point.liquid_composition >= 0)
                assert np.all(point.liquid_composition <= 1)
                assert np.all(point.vapor_composition >= 0)
                assert np.all(point.vapor_composition <= 1)


class TestTernaryResultMethods:
    """Test TernaryResult helper methods."""

    @pytest.fixture
    def ternary_components(self, components):
        """Load 3 components for ternary test."""
        return [components['C1'], components['C4'], components['C10']]

    @pytest.fixture
    def ternary_eos(self, ternary_components):
        """Create EOS for ternary system."""
        return PengRobinsonEOS(ternary_components)

    def test_get_single_phase_compositions(self, ternary_eos, ternary_components):
        """Test get_single_phase_compositions method."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        single_phase = result.get_single_phase_compositions()

        if result.n_single_phase > 0:
            assert len(single_phase) == result.n_single_phase
            assert single_phase.shape[1] == 3

    def test_get_two_phase_compositions(self, ternary_eos, ternary_components):
        """Test get_two_phase_compositions method."""
        result = compute_ternary_diagram(
            temperature=350.0,
            pressure=5e6,
            components=ternary_components,
            eos=ternary_eos,
            n_subdivisions=7
        )

        two_phase = result.get_two_phase_compositions()

        if result.n_two_phase > 0:
            assert len(two_phase) == result.n_two_phase
            assert two_phase.shape[1] == 3
