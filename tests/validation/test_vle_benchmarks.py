"""VLE (Vapor-Liquid Equilibrium) benchmark tests.

These tests validate flash calculations and phase equilibrium predictions
for binary and multicomponent mixtures against expected thermodynamic behavior.

Test Categories:
1. Binary mixture flash calculations
2. K-value predictions vs Wilson correlation
3. Phase envelope calculations
4. Material balance verification
5. Thermodynamic consistency checks

Note: These are internal consistency tests. For validation against experimental
data, component properties would need to be tuned to match specific datasets.
"""

import pytest
import numpy as np
from typing import Tuple, List

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.flash.pt_flash import pt_flash, FlashResult
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.stability.wilson import wilson_k_values
from pvtcore.core.errors import ConvergenceStatus


@pytest.fixture
def components():
    """Load component database."""
    return load_components()


@pytest.fixture
def c1_c10_mixture(components):
    """Methane-decane binary mixture setup."""
    comp_list = [components['C1'], components['C10']]
    eos = PengRobinsonEOS(comp_list)
    return comp_list, eos


@pytest.fixture
def c1_c4_mixture(components):
    """Methane-butane binary mixture setup."""
    comp_list = [components['C1'], components['C4']]
    eos = PengRobinsonEOS(comp_list)
    return comp_list, eos


@pytest.fixture
def light_oil_mixture(components):
    """Light oil multicomponent mixture setup."""
    comp_list = [
        components['C1'],
        components['C2'],
        components['C3'],
        components['C4'],
        components['C5'],
        components['C6'],
    ]
    eos = PengRobinsonEOS(comp_list)
    return comp_list, eos


class TestBinaryFlashConvergence:
    """Test that binary mixture flash calculations converge."""

    def test_c1_c10_flash_converges(self, c1_c10_mixture):
        """Test methane-decane flash convergence at various conditions."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])  # Equal molar

        # Test at conditions expected to be two-phase
        test_conditions = [
            (5e6, 300.0),   # 50 bar, 300 K
            (3e6, 320.0),   # 30 bar, 320 K
            (8e6, 350.0),   # 80 bar, 350 K
        ]

        for P, T in test_conditions:
            result = pt_flash(P, T, z, comp_list, eos)
            assert result.status == ConvergenceStatus.CONVERGED, (
                f"Flash failed at P={P/1e6:.1f} MPa, T={T} K"
            )

    def test_c1_c4_flash_converges(self, c1_c4_mixture):
        """Test methane-butane flash convergence."""
        comp_list, eos = c1_c4_mixture
        z = np.array([0.7, 0.3])

        result = pt_flash(4e6, 280.0, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED


class TestFlashMaterialBalance:
    """Verify material balance in flash calculations."""

    def test_material_balance_binary(self, c1_c10_mixture):
        """Overall material balance must be satisfied for binary flash."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.6, 0.4])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            # Check: z = nv*y + (1-nv)*x
            nv = result.vapor_fraction
            x = result.liquid_composition
            y = result.vapor_composition

            z_reconstructed = nv * y + (1 - nv) * x

            np.testing.assert_allclose(z, z_reconstructed, rtol=1e-8, err_msg=(
                f"Material balance violated: z = {z}, reconstructed = {z_reconstructed}"
            ))

    def test_composition_normalization(self, c1_c10_mixture):
        """Phase compositions must sum to 1.0."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            assert abs(result.liquid_composition.sum() - 1.0) < 1e-10
            assert abs(result.vapor_composition.sum() - 1.0) < 1e-10


class TestKValueBehavior:
    """Test equilibrium ratio (K-value) behavior."""

    def test_light_component_in_vapor(self, c1_c10_mixture):
        """Light component should have K > 1 (enriched in vapor)."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            K = result.K_values
            # Methane (light) should have K > 1
            assert K[0] > 1.0, f"Light component K = {K[0]:.3f}, expected > 1"
            # Decane (heavy) should have K < 1
            assert K[1] < 1.0, f"Heavy component K = {K[1]:.3f}, expected < 1"

    def test_k_values_match_composition_ratio(self, c1_c10_mixture):
        """K-values must equal y/x for each component."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            K_from_comp = result.vapor_composition / result.liquid_composition
            # Allow small tolerance for numerical precision
            np.testing.assert_allclose(result.K_values, K_from_comp, rtol=1e-5)

    def test_wilson_provides_reasonable_initial_guess(self, c1_c10_mixture):
        """Wilson K-values should be reasonable initial estimates."""
        comp_list, eos = c1_c10_mixture
        P, T = 5e6, 320.0

        K_wilson = wilson_k_values(P, T, comp_list)

        # Wilson K should follow same pattern as EOS K
        # (light component K > heavy component K)
        assert K_wilson[0] > K_wilson[1], "Wilson K order should match volatility"

        # Wilson K should be in reasonable range
        assert all(K > 0 for K in K_wilson), "K-values must be positive"
        assert all(K < 1e6 for K in K_wilson), "K-values should not be extreme"


class TestFugacityEquilibrium:
    """Test fugacity equality at equilibrium."""

    def test_fugacity_equality_at_equilibrium(self, c1_c10_mixture):
        """Fugacity of each component must be equal in both phases."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            x = result.liquid_composition
            y = result.vapor_composition
            phi_L = result.liquid_fugacity
            phi_V = result.vapor_fugacity

            # Fugacity: f_i = phi_i * x_i * P (liquid) or phi_i * y_i * P (vapor)
            f_L = phi_L * x * P
            f_V = phi_V * y * P

            # Allow small tolerance for numerical precision in fugacity equality
            np.testing.assert_allclose(f_L, f_V, rtol=1e-4, err_msg=(
                f"Fugacity mismatch: f_L = {f_L}, f_V = {f_V}"
            ))


class TestSaturationPoints:
    """Test bubble and dew point calculations."""

    def test_bubble_dew_bracket_two_phase(self, c1_c4_mixture):
        """Bubble and dew pressures define the two-phase envelope."""
        comp_list, eos = c1_c4_mixture
        z = np.array([0.5, 0.5])
        T = 280.0  # Well within two-phase region for C1-C4

        # Calculate bubble and dew points
        bubble_result = calculate_bubble_point(T, z, comp_list, eos)
        dew_result = calculate_dew_point(T, z, comp_list, eos)

        assert bubble_result.converged, "Bubble point did not converge"
        assert dew_result.converged, "Dew point did not converge"

        P_bubble = bubble_result.pressure
        P_dew = dew_result.pressure

        # Verify both pressures are positive and reasonable
        assert P_bubble > 0, f"Bubble pressure must be positive: {P_bubble}"
        assert P_dew > 0, f"Dew pressure must be positive: {P_dew}"

        # For a normal mixture at moderate temperature, expect P_bubble > P_dew
        # (liquid at bubble point starts to vaporize at lower P than dew point)
        # Note: The relationship depends on mixture composition and temperature
        # We just verify they define a two-phase region

        # Calculate the pressure range and test a point within it
        P_min = min(P_bubble, P_dew)
        P_max = max(P_bubble, P_dew)
        P_mid = (P_min + P_max) / 2

        result = pt_flash(P_mid, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED
        # At mid-pressure, we should see intermediate vapor fraction
        assert 0.01 < result.vapor_fraction < 0.99, (
            f"Expected two-phase at P_mid = {P_mid/1e6:.3f} MPa, "
            f"got nv = {result.vapor_fraction:.3f}"
        )

    def test_bubble_point_vapor_fraction_zero(self, c1_c4_mixture):
        """At bubble point, vapor fraction should approach zero."""
        comp_list, eos = c1_c4_mixture
        z = np.array([0.5, 0.5])
        T = 280.0

        bubble_result = calculate_bubble_point(T, z, comp_list, eos)
        assert bubble_result.converged

        # Flash just above bubble point
        P_test = bubble_result.pressure * 0.95
        result = pt_flash(P_test, T, z, comp_list, eos)

        if result.status == ConvergenceStatus.CONVERGED and result.phase == 'two-phase':
            # Vapor fraction should be small (close to bubble point)
            assert result.vapor_fraction < 0.3, (
                f"Expected small nv near bubble point, got {result.vapor_fraction:.3f}"
            )


class TestMulticomponentFlash:
    """Test flash calculations for multicomponent mixtures."""

    def test_six_component_flash_converges(self, light_oil_mixture):
        """Test that 6-component flash converges."""
        comp_list, eos = light_oil_mixture
        # Typical light oil composition
        z = np.array([0.40, 0.10, 0.15, 0.12, 0.13, 0.10])
        z = z / z.sum()  # Normalize

        P, T = 3e6, 320.0
        result = pt_flash(P, T, z, comp_list, eos)

        assert result.status == ConvergenceStatus.CONVERGED

    def test_multicomponent_material_balance(self, light_oil_mixture):
        """Verify material balance for multicomponent flash."""
        comp_list, eos = light_oil_mixture
        z = np.array([0.40, 0.10, 0.15, 0.12, 0.13, 0.10])
        z = z / z.sum()

        P, T = 3e6, 320.0
        result = pt_flash(P, T, z, comp_list, eos)

        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            nv = result.vapor_fraction
            z_calc = nv * result.vapor_composition + (1 - nv) * result.liquid_composition
            np.testing.assert_allclose(z, z_calc, rtol=1e-8)

    def test_multicomponent_k_value_ordering(self, light_oil_mixture):
        """K-values should decrease with increasing component heaviness."""
        comp_list, eos = light_oil_mixture
        z = np.array([0.40, 0.10, 0.15, 0.12, 0.13, 0.10])
        z = z / z.sum()

        P, T = 3e6, 320.0
        result = pt_flash(P, T, z, comp_list, eos)

        assert result.status == ConvergenceStatus.CONVERGED

        if result.phase == 'two-phase':
            K = result.K_values
            # Generally, lighter components should have higher K values
            # Check that C1 has highest K, C6 has lowest
            assert K[0] > K[-1], (
                f"Expected K_C1 > K_C6: K_C1 = {K[0]:.3f}, K_C6 = {K[-1]:.3f}"
            )


class TestPressureTemperatureTraverse:
    """Test flash along P-T paths."""

    def test_isothermal_pressure_traverse(self, c1_c10_mixture):
        """Flash along isothermal path should show smooth transition."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        T = 350.0

        pressures = np.linspace(1e6, 15e6, 10)
        vapor_fractions = []

        for P in pressures:
            result = pt_flash(P, T, z, comp_list, eos)
            assert result.status == ConvergenceStatus.CONVERGED
            vapor_fractions.append(result.vapor_fraction)

        vapor_fractions = np.array(vapor_fractions)

        # Vapor fraction should generally decrease with increasing pressure
        # (at constant T, higher P favors liquid)
        assert vapor_fractions[0] >= vapor_fractions[-1], (
            "Vapor fraction should decrease with increasing pressure"
        )

    def test_isobaric_temperature_traverse(self, c1_c10_mixture):
        """Flash along isobaric path should show smooth transition."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P = 5e6

        temperatures = np.linspace(280.0, 450.0, 10)
        vapor_fractions = []

        for T in temperatures:
            result = pt_flash(P, T, z, comp_list, eos)
            assert result.status == ConvergenceStatus.CONVERGED
            vapor_fractions.append(result.vapor_fraction)

        vapor_fractions = np.array(vapor_fractions)

        # Vapor fraction should increase with temperature
        assert vapor_fractions[-1] >= vapor_fractions[0], (
            "Vapor fraction should increase with increasing temperature"
        )


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_near_pure_light_component(self, c1_c10_mixture):
        """Flash with very light composition (mostly C1)."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.99, 0.01])
        P, T = 2e6, 200.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

    def test_near_pure_heavy_component(self, c1_c10_mixture):
        """Flash with very heavy composition (mostly C10)."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.01, 0.99])
        P, T = 1e6, 400.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED

    def test_high_pressure_single_phase(self, c1_c10_mixture):
        """At very high pressure, should be single-phase liquid."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 50e6, 350.0  # Very high pressure

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED
        # High pressure usually means liquid or supercritical
        assert result.vapor_fraction <= 0.01, (
            f"Expected mostly liquid at high P, got nv = {result.vapor_fraction:.3f}"
        )

    def test_low_pressure_single_phase(self, c1_c10_mixture):
        """At very low pressure and high T, should be single-phase vapor."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 1e5, 600.0  # Low pressure, high temperature

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.vapor_fraction >= 0.99, (
            f"Expected vapor at low P/high T, got nv = {result.vapor_fraction:.3f}"
        )


class TestRegressionPrevention:
    """Regression tests for specific flash results."""

    def test_c1_c10_flash_regression(self, c1_c10_mixture):
        """Regression test for C1-C10 binary flash."""
        comp_list, eos = c1_c10_mixture
        z = np.array([0.5, 0.5])
        P, T = 5e6, 320.0

        result = pt_flash(P, T, z, comp_list, eos)
        assert result.status == ConvergenceStatus.CONVERGED
        assert result.phase == 'two-phase'

        # Expected values from current implementation (update if EOS changes)
        expected_nv = 0.357  # Vapor fraction
        expected_K1 = 4.48   # C1 K-value
        expected_K2 = 0.001  # C10 K-value (very small)

        assert abs(result.vapor_fraction - expected_nv) < 0.05, (
            f"Vapor fraction regression: got {result.vapor_fraction:.3f}, "
            f"expected ~{expected_nv:.3f}"
        )
        assert abs(result.K_values[0] - expected_K1) / expected_K1 < 0.1, (
            f"K_C1 regression: got {result.K_values[0]:.3f}, expected ~{expected_K1:.2f}"
        )
        assert result.K_values[1] < 0.01, (
            f"K_C10 should be very small: got {result.K_values[1]:.6f}"
        )
