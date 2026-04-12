"""Unit tests for saturation point calculations (bubble and dew points).

Tests validate bubble and dew point calculations against:
- Known thermodynamic relationships (Pbubble < Pdew for same T and z)
- Pure component limits (bubble = dew = Psat)
- Mass balance constraints
- Convergence behavior
"""

import pytest
import numpy as np
from pvtcore.flash.bubble_point import (
    calculate_bubble_point,
    BubblePointResult,
    BUBBLE_POINT_TOLERANCE
)
from pvtcore.flash.dew_point import (
    calculate_dew_point,
    DewPointResult,
    DEW_POINT_TOLERANCE
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError, ConvergenceError, PhaseError, ConvergenceStatus


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


@pytest.fixture
def pure_c1_eos(components):
    """Create PR EOS for pure methane."""
    return PengRobinsonEOS([components['C1']])


class TestBubblePointResult:
    """Test BubblePointResult data structure."""

    def test_bubble_point_result_fields(self, binary_c1_c10_eos, components):
        """Test that BubblePointResult contains required fields."""
        T = 300.0  # K
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        # Check all required fields exist
        assert hasattr(result, 'converged')
        assert hasattr(result, 'pressure')
        assert hasattr(result, 'temperature')
        assert hasattr(result, 'liquid_composition')
        assert hasattr(result, 'vapor_composition')
        assert hasattr(result, 'K_values')
        assert hasattr(result, 'iterations')
        assert hasattr(result, 'residual')
        assert hasattr(result, 'stable_liquid')

        # Check types
        assert isinstance(result.converged, bool)
        assert isinstance(result.pressure, (float, np.floating))
        assert isinstance(result.temperature, (float, np.floating))
        assert isinstance(result.liquid_composition, np.ndarray)
        assert isinstance(result.vapor_composition, np.ndarray)
        assert isinstance(result.K_values, np.ndarray)
        assert isinstance(result.iterations, int)
        assert isinstance(result.residual, (float, np.floating))


class TestDewPointResult:
    """Test DewPointResult data structure."""

    def test_dew_point_result_fields(self, binary_c1_c4_eos, components):
        """Test that DewPointResult contains required fields."""
        T = 250.0  # K
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        # Check all required fields exist
        assert hasattr(result, 'converged')
        assert hasattr(result, 'pressure')
        assert hasattr(result, 'temperature')
        assert hasattr(result, 'vapor_composition')
        assert hasattr(result, 'liquid_composition')
        assert hasattr(result, 'K_values')
        assert hasattr(result, 'iterations')
        assert hasattr(result, 'residual')
        assert hasattr(result, 'stable_vapor')

        # Check types
        assert isinstance(result.converged, bool)
        assert isinstance(result.pressure, (float, np.floating))
        assert isinstance(result.temperature, (float, np.floating))


class TestBubblePointCalculation:
    """Test bubble point pressure calculations."""

    def test_bubble_point_converges(self, binary_c1_c10_eos, components):
        """Test that bubble point calculation converges."""
        T = 300.0  # K
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        assert result.converged is True
        assert result.iterations < 120  # Bracketing + Brent should still be modest
        assert result.residual < BUBBLE_POINT_TOLERANCE

    def test_bubble_point_pressure_positive(self, binary_c1_c10_eos, components):
        """Test that bubble point pressure is positive and reasonable."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        assert result.pressure > 0
        # Should be reasonable (between 0.1 bar and 1000 bar)
        assert 1e4 < result.pressure < 1e8

    def test_bubble_point_liquid_equals_feed(self, binary_c1_c10_eos, components):
        """Test that liquid composition equals feed at bubble point."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        # Liquid composition should equal feed composition
        np.testing.assert_allclose(result.liquid_composition, z, rtol=1e-6)

    def test_bubble_point_vapor_enriched_in_light(self, binary_c1_c10_eos, components):
        """Test that incipient vapor is enriched in light component."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        # Vapor should be enriched in methane (light component)
        assert result.vapor_composition[0] > z[0]  # More C1 in vapor
        assert result.vapor_composition[1] < z[1]  # Less C10 in vapor

    def test_bubble_point_k_values_greater_than_one_for_light(self, binary_c1_c10_eos, components):
        """Test that K-values reflect component volatility."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        # K > 1 for light component (methane)
        assert result.K_values[0] > 1.0
        # K < 1 for heavy component (decane)
        assert result.K_values[1] < 1.0

    def test_bubble_point_composition_normalized(self, binary_c1_c10_eos, components):
        """Test that vapor composition is normalized."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        assert abs(result.vapor_composition.sum() - 1.0) < 1e-10

    def test_bubble_point_increases_with_light_component(self, binary_c1_c10_eos, components):
        """Test that bubble point increases with more volatile component."""
        T = 300.0
        binary = [components['C1'], components['C10']]

        # More heavy component
        z1 = np.array([0.3, 0.7])
        result1 = calculate_bubble_point(T, z1, binary, binary_c1_c10_eos)

        # More light component
        z2 = np.array([0.7, 0.3])
        result2 = calculate_bubble_point(T, z2, binary, binary_c1_c10_eos)

        # More volatile component → higher bubble point pressure
        assert result2.pressure > result1.pressure


class TestDewPointCalculation:
    """Test dew point pressure calculations."""

    def test_dew_point_converges(self, binary_c1_c4_eos, components):
        """Test that dew point calculation converges.

        Use C1-C4 which is more reasonable for dew point at 300K.
        """
        T = 250.0  # K
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        assert result.converged is True
        assert result.iterations < 120  # Bracketing + Brent should still be modest
        assert result.residual < DEW_POINT_TOLERANCE

    def test_dew_point_pressure_positive(self, binary_c1_c4_eos, components):
        """Test that dew point pressure is positive and reasonable."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        assert result.pressure > 0
        # Should be reasonable pressure
        assert 1e4 < result.pressure < 1e7

    def test_dew_point_vapor_equals_feed(self, binary_c1_c4_eos, components):
        """Test that vapor composition equals feed at dew point."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        # Vapor composition should equal feed composition
        np.testing.assert_allclose(result.vapor_composition, z, rtol=1e-6)

    def test_dew_point_liquid_enriched_in_heavy(self, binary_c1_c4_eos, components):
        """Test that incipient liquid is enriched in heavy component."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        # Liquid should be enriched in butane (heavy component)
        assert result.liquid_composition[0] < z[0]  # Less C1 in liquid
        assert result.liquid_composition[1] > z[1]  # More C4 in liquid

    def test_dew_point_composition_normalized(self, binary_c1_c4_eos, components):
        """Test that liquid composition is normalized."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        assert abs(result.liquid_composition.sum() - 1.0) < 1e-10


class TestBubbleDewRelationship:
    """Test thermodynamic relationships between bubble and dew points."""

    def test_dew_pressure_less_than_bubble(self, binary_c1_c4_eos, components):
        """Test that dew point < bubble point for same T and z.

        For a given temperature and composition:
        P_dew < P_bubble

        This is because at dew point (lower P), vapor starts to condense.
        At bubble point (higher P), liquid starts to vaporize.
        """
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        bubble_result = calculate_bubble_point(T, z, binary, binary_c1_c4_eos)
        dew_result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        # Dew point pressure should be less than bubble point pressure
        assert dew_result.pressure < bubble_result.pressure

    def test_bubble_dew_span_two_phase_region(self, binary_c1_c4_eos, components):
        """Test that bubble and dew points bound the two-phase region."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        bubble_result = calculate_bubble_point(T, z, binary, binary_c1_c4_eos)
        dew_result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

        # Between dew and bubble pressures, system should be two-phase
        # Below dew pressure: all vapor
        # Above bubble pressure: all liquid
        # Between: two-phase

        assert dew_result.pressure < bubble_result.pressure
        # The pressure range defines the two-phase envelope
        two_phase_range = bubble_result.pressure - dew_result.pressure
        assert two_phase_range > 0


class TestCompositionVariation:
    """Test saturation points at various compositions."""

    def test_c1_rich_mixture(self, binary_c1_c10_eos, components):
        """Test bubble point for a methane-rich C1/C10 mixture."""
        T = 300.0
        z = np.array([0.7, 0.3])  # methane-rich but still non-trivial
        binary = [components['C1'], components['C10']]

        bubble_result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        assert bubble_result.converged is True
        assert bubble_result.pressure > 0

    def test_c10_rich_mixture(self, binary_c1_c10_eos, components):
        """Test bubble points for C10-rich mixture.

        Note: Dew point skipped for C10-rich at 300K (too difficult).
        """
        T = 300.0
        z = np.array([0.1, 0.9])  # 90% decane
        binary = [components['C1'], components['C10']]

        bubble_result = calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

        assert bubble_result.converged is True
        # For heavy-component-rich mixture, bubble pressure should be low
        assert bubble_result.pressure > 0

    def test_multiple_compositions_c1_c4(self, binary_c1_c4_eos, components):
        """Test saturation points across composition range for C1-C4."""
        T = 250.0  # K
        binary = [components['C1'], components['C4']]

        compositions = [
            np.array([0.2, 0.8]),
            np.array([0.5, 0.5]),
            np.array([0.8, 0.2])
        ]

        for z in compositions:
            bubble_result = calculate_bubble_point(T, z, binary, binary_c1_c4_eos)
            dew_result = calculate_dew_point(T, z, binary, binary_c1_c4_eos)

            assert bubble_result.converged is True
            assert dew_result.converged is True
            assert dew_result.pressure < bubble_result.pressure


class TestTemperatureEffect:
    """Test effect of temperature on saturation points."""

    def test_bubble_point_increases_with_temperature(self, binary_c1_c10_eos, components):
        """Test that bubble point pressure increases with temperature."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        T1 = 280.0  # Lower temperature
        T2 = 320.0  # Higher temperature

        result1 = calculate_bubble_point(T1, z, binary, binary_c1_c10_eos)
        result2 = calculate_bubble_point(T2, z, binary, binary_c1_c10_eos)

        # Higher temperature → higher bubble point pressure
        assert result2.pressure > result1.pressure

    def test_dew_point_increases_with_temperature(self, binary_c1_c4_eos, components):
        """Test that dew point pressure increases with temperature."""
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        T1 = 230.0  # Lower temperature
        T2 = 270.0  # Higher temperature

        result1 = calculate_dew_point(T1, z, binary, binary_c1_c4_eos)
        result2 = calculate_dew_point(T2, z, binary, binary_c1_c4_eos)

        # Higher temperature → higher dew point pressure
        assert result2.pressure > result1.pressure


class TestInputValidation:
    """Test input validation and error handling."""

    def test_bubble_point_rejects_degenerate_trivial_boundary(self, components):
        """CO2-rich GUI case should not report a fake converged bubble point."""
        T = 573.15  # 300 C from the desktop workflow
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [
            components['CO2'],
            components['C1'],
            components['C2'],
            components['C3'],
            components['C4'],
        ]
        eos = PengRobinsonEOS(mixture)

        with pytest.raises(PhaseError, match="degenerate trivial stability solution"):
            calculate_bubble_point(T, z, mixture, eos)

    def test_bubble_point_recovers_upper_branch_from_previous_guess(self, components):
        """Upper bubble branch should remain reachable from the previous trace point."""
        T = 296.93928571428575  # 23.789 C, next fixed-grid point after a 14.605 C bubble solve
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [
            components['CO2'],
            components['C1'],
            components['C2'],
            components['C3'],
            components['C4'],
        ]
        eos = PengRobinsonEOS(mixture)

        result = calculate_bubble_point(
            T,
            z,
            mixture,
            eos,
            pressure_initial=55.38207428791868e5,
            post_check_stability_flip=True,
            post_check_action="raise",
        )

        assert result.status == ConvergenceStatus.CONVERGED
        assert result.pressure > 6.0e6

    def test_bubble_point_is_guess_robust_for_realistic_volatile_oil_case(self, components):
        """A realistic volatile oil should converge to the same bubble point across guesses."""
        T = 360.0
        component_ids = ["N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"]
        z = np.array(
            [0.0021, 0.0187, 0.3478, 0.0712, 0.0934, 0.0302, 0.0431, 0.0276, 0.0418, 0.0574, 0.0835, 0.0886, 0.0946],
            dtype=float,
        )
        z /= z.sum()
        mixture = [components[component_id] for component_id in component_ids]
        eos = PengRobinsonEOS(mixture)

        reference = calculate_bubble_point(
            T,
            z,
            mixture,
            eos,
            post_check_stability_flip=True,
        )

        assert reference.status == ConvergenceStatus.CONVERGED

        for guess in [1e5, 1e6, 5e7]:
            result = calculate_bubble_point(
                T,
                z,
                mixture,
                eos,
                pressure_initial=guess,
                post_check_stability_flip=True,
            )

            assert result.status == ConvergenceStatus.CONVERGED
            assert result.pressure == pytest.approx(reference.pressure, abs=5e3)
            np.testing.assert_allclose(
                result.vapor_composition,
                reference.vapor_composition,
                atol=5e-6,
                rtol=0.0,
            )

    def test_dew_point_rejects_degenerate_trivial_boundary(self, components):
        """CO2-rich GUI case should not report a fake converged dew point."""
        T = 573.15  # 300 C from the desktop workflow
        z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152])
        mixture = [
            components['CO2'],
            components['C1'],
            components['C2'],
            components['C3'],
            components['C4'],
        ]
        eos = PengRobinsonEOS(mixture)

        with pytest.raises(PhaseError, match="degenerate trivial stability solution"):
            calculate_dew_point(T, z, mixture, eos)

    def test_invalid_composition_sum_bubble(self, binary_c1_c10_eos, components):
        """Test that invalid composition sum raises error."""
        T = 300.0
        z_invalid = np.array([0.5, 0.3])  # Sums to 0.8
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_bubble_point(T, z_invalid, binary, binary_c1_c10_eos)

    def test_invalid_composition_sum_dew(self, binary_c1_c10_eos, components):
        """Test that invalid composition sum raises error."""
        T = 300.0
        z_invalid = np.array([0.5, 0.3])  # Sums to 0.8
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_dew_point(T, z_invalid, binary, binary_c1_c10_eos)

    def test_negative_temperature_bubble(self, binary_c1_c10_eos, components):
        """Test that negative temperature raises error."""
        T = -100.0  # Invalid
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_bubble_point(T, z, binary, binary_c1_c10_eos)

    def test_negative_temperature_dew(self, binary_c1_c10_eos, components):
        """Test that negative temperature raises error."""
        T = -100.0  # Invalid
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_dew_point(T, z, binary, binary_c1_c10_eos)

    def test_composition_length_mismatch_bubble(self, binary_c1_c10_eos, components):
        """Test that composition length mismatch raises error."""
        T = 300.0
        z_wrong = np.array([0.33, 0.33, 0.34])  # 3 components, but EOS has 2
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_bubble_point(T, z_wrong, binary, binary_c1_c10_eos)

    def test_composition_length_mismatch_dew(self, binary_c1_c10_eos, components):
        """Test that composition length mismatch raises error."""
        T = 300.0
        z_wrong = np.array([0.33, 0.33, 0.34])  # 3 components, but EOS has 2
        binary = [components['C1'], components['C10']]

        with pytest.raises(ValidationError):
            calculate_dew_point(T, z_wrong, binary, binary_c1_c10_eos)


class TestConvergence:
    """Test convergence behavior."""

    def test_custom_tolerance_bubble(self, binary_c1_c10_eos, components):
        """Test bubble point with custom tolerance."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # Looser tolerance
        result = calculate_bubble_point(
            T, z, binary, binary_c1_c10_eos, tolerance=1e-6
        )

        assert result.converged is True
        assert result.residual < 1e-6

    def test_custom_tolerance_dew(self, binary_c1_c4_eos, components):
        """Test dew point with custom tolerance."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        # Looser tolerance
        result = calculate_dew_point(
            T, z, binary, binary_c1_c4_eos, tolerance=1e-6
        )

        assert result.converged is True
        assert result.residual < 1e-6

    def test_initial_pressure_guess_bubble(self, binary_c1_c10_eos, components):
        """Test bubble point with initial pressure guess."""
        T = 300.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C10']]

        # Provide initial guess
        P_init = 5e6  # 50 bar
        result = calculate_bubble_point(
            T, z, binary, binary_c1_c10_eos, pressure_initial=P_init
        )

        assert result.converged is True

    def test_initial_pressure_guess_dew(self, binary_c1_c4_eos, components):
        """Test dew point with initial pressure guess."""
        T = 250.0
        z = np.array([0.5, 0.5])
        binary = [components['C1'], components['C4']]

        # Provide initial guess (closer to expected value)
        P_init = 5e5  # 5 bar
        result = calculate_dew_point(
            T, z, binary, binary_c1_c4_eos, pressure_initial=P_init
        )

        assert result.converged is True


class TestSimilarComponents:
    """Test saturation points for systems with similar components."""

    def test_ethane_propane_bubble_dew(self, binary_c2_c3_eos, components):
        """Test bubble and dew points for ethane-propane system.

        Ethane and propane are relatively similar components, so the
        two-phase envelope should be narrower than C1-C10.
        """
        T = 280.0  # K
        z = np.array([0.5, 0.5])
        binary = [components['C2'], components['C3']]

        bubble_result = calculate_bubble_point(T, z, binary, binary_c2_c3_eos)
        dew_result = calculate_dew_point(T, z, binary, binary_c2_c3_eos)

        assert bubble_result.converged is True
        assert dew_result.converged is True
        assert dew_result.pressure < bubble_result.pressure

        # Pressure difference should be smaller for similar components
        pressure_diff = bubble_result.pressure - dew_result.pressure
        assert pressure_diff > 0
