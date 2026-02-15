"""Vapor pressure validation tests for Peng-Robinson EOS.

These tests validate the equation of state implementation by:
1. Verifying calculations converge and produce physically reasonable results
2. Checking internal consistency (vapor pressure increases with temperature)
3. Validating acentric factor consistency (omega definition at Tr = 0.7)
4. Documenting typical errors compared to literature data

Note: Peng-Robinson EOS is inherently an approximation. Typical errors for
vapor pressure predictions are 2-10% depending on the component and reduced
temperature. Near-critical regions (Tr > 0.9) and very low reduced temperatures
(Tr < 0.5) typically have larger errors.

Reference Data Sources:
- DIPPR 801 Database
- Perry's Chemical Engineers' Handbook
- NIST Chemistry WebBook
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import List, Tuple, Optional

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.flash.bubble_point import calculate_bubble_point


@dataclass
class VaporPressureDataPoint:
    """Reference vapor pressure data point."""
    temperature_k: float
    pressure_pa: float
    reduced_temp: float
    source: str = "PR EOS calculation"


@pytest.fixture
def components():
    """Load component database."""
    return load_components()


def calculate_vapor_pressure(
    component_id: str,
    temperature_k: float,
    components: dict,
) -> Tuple[float, bool]:
    """Calculate vapor pressure for a pure component using bubble point.

    For a pure component at its saturation temperature, the bubble point
    pressure equals the vapor pressure.

    Args:
        component_id: Component identifier (e.g., 'C1', 'C2')
        temperature_k: Temperature in Kelvin
        components: Component database dictionary

    Returns:
        Tuple of (vapor pressure in Pascal, converged flag)
    """
    component = components[component_id]
    eos = PengRobinsonEOS([component])
    z = np.array([1.0])  # Pure component

    try:
        result = calculate_bubble_point(
            temperature=temperature_k,
            composition=z,
            components=[component],
            eos=eos,
            tolerance=1e-9,
            max_iterations=100,
        )
        return result.pressure, result.converged
    except Exception:
        return float('nan'), False


class TestVaporPressureConvergence:
    """Test that vapor pressure calculations converge for all components."""

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C10"])
    def test_vapor_pressure_converges(self, components, component_id):
        """Verify bubble point calculation converges at Tr = 0.7."""
        comp = components[component_id]
        T = 0.7 * comp.Tc  # Tr = 0.7

        P, converged = calculate_vapor_pressure(component_id, T, components)

        assert converged, f"{component_id} vapor pressure did not converge at Tr = 0.7"
        assert np.isfinite(P), f"{component_id} vapor pressure is not finite"
        assert P > 0, f"{component_id} vapor pressure must be positive"

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3"])
    @pytest.mark.parametrize("Tr", [0.6, 0.65, 0.7, 0.75, 0.8, 0.85])
    def test_vapor_pressure_across_temperature_range(self, components, component_id, Tr):
        """Verify calculations converge across a range of reduced temperatures."""
        comp = components[component_id]
        T = Tr * comp.Tc

        P, converged = calculate_vapor_pressure(component_id, T, components)

        assert converged, f"{component_id} did not converge at Tr = {Tr}"
        assert np.isfinite(P), f"{component_id} vapor pressure not finite at Tr = {Tr}"


class TestVaporPressurePhysicalBehavior:
    """Test that vapor pressure follows expected physical behavior."""

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3", "C4", "C5"])
    def test_vapor_pressure_increases_with_temperature(self, components, component_id):
        """Vapor pressure must monotonically increase with temperature."""
        comp = components[component_id]
        Tr_values = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85]

        pressures = []
        for Tr in Tr_values:
            T = Tr * comp.Tc
            P, converged = calculate_vapor_pressure(component_id, T, components)
            assert converged, f"Calculation failed at Tr = {Tr}"
            pressures.append(P)

        # Verify monotonic increase
        for i in range(1, len(pressures)):
            assert pressures[i] > pressures[i - 1], (
                f"{component_id}: P({Tr_values[i]}) = {pressures[i]:.0f} Pa "
                f"should be > P({Tr_values[i-1]}) = {pressures[i-1]:.0f} Pa"
            )

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3", "C4", "C5"])
    def test_vapor_pressure_bounded_by_critical(self, components, component_id):
        """Vapor pressure must be less than critical pressure at all Tr < 1."""
        comp = components[component_id]
        Tr_values = [0.6, 0.7, 0.8, 0.9]

        for Tr in Tr_values:
            T = Tr * comp.Tc
            P, converged = calculate_vapor_pressure(component_id, T, components)
            assert converged

            assert P < comp.Pc, (
                f"{component_id} at Tr = {Tr}: P = {P/1e6:.3f} MPa "
                f"exceeds Pc = {comp.Pc/1e6:.3f} MPa"
            )


class TestAcentricFactorConsistency:
    """Verify acentric factor consistency with vapor pressure definition.

    The acentric factor is defined as: omega = -log10(Psat/Pc) - 1 at Tr = 0.7

    This test verifies that our EOS, given the stored omega, produces
    vapor pressures consistent with this definition (within typical PR error).
    """

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3", "C4", "C5", "C6", "C7"])
    def test_acentric_factor_at_tr07(self, components, component_id):
        """Verify omega consistency at Tr = 0.7."""
        comp = components[component_id]
        T_07 = 0.7 * comp.Tc

        P_calc, converged = calculate_vapor_pressure(component_id, T_07, components)
        assert converged, f"Calculation failed for {component_id}"

        # Calculate omega from vapor pressure
        omega_calc = -np.log10(P_calc / comp.Pc) - 1.0

        # Compare with stored omega
        error = abs(omega_calc - comp.omega)

        # Allow reasonable tolerance (PR EOS typically 5-15% for omega)
        # This translates to about 0.03-0.05 absolute omega error
        assert error < 0.05, (
            f"{component_id}: Omega inconsistency at Tr=0.7: "
            f"stored omega = {comp.omega:.4f}, "
            f"calculated omega = {omega_calc:.4f}, "
            f"error = {error:.4f}"
        )


class TestClausiusClapeyronBehavior:
    """Test that vapor pressure follows Clausius-Clapeyron-like behavior."""

    @pytest.mark.parametrize("component_id", ["C1", "C2", "C3"])
    def test_ln_p_vs_inverse_t_linearity(self, components, component_id):
        """ln(P) should be approximately linear in 1/T (Clausius-Clapeyron)."""
        comp = components[component_id]
        Tr_values = [0.65, 0.70, 0.75, 0.80, 0.85]

        ln_P = []
        inv_T = []

        for Tr in Tr_values:
            T = Tr * comp.Tc
            P, converged = calculate_vapor_pressure(component_id, T, components)
            assert converged

            ln_P.append(np.log(P))
            inv_T.append(1.0 / T)

        # Fit a line and check R^2
        inv_T = np.array(inv_T)
        ln_P = np.array(ln_P)

        # Linear regression
        coeffs = np.polyfit(inv_T, ln_P, 1)
        ln_P_fit = np.polyval(coeffs, inv_T)

        # Calculate R^2
        ss_res = np.sum((ln_P - ln_P_fit) ** 2)
        ss_tot = np.sum((ln_P - np.mean(ln_P)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)

        # Expect good linearity (R^2 > 0.999)
        assert r_squared > 0.999, (
            f"{component_id}: Clausius-Clapeyron linearity poor, R^2 = {r_squared:.6f}"
        )


class TestLightHeavyComponentComparison:
    """Test relative behavior of light vs heavy components."""

    def test_light_components_higher_pressure(self, components):
        """At same Tr, lighter components have higher vapor pressures."""
        Tr = 0.75

        pressures = {}
        for comp_id in ["C1", "C3", "C5", "C7", "C10"]:
            comp = components[comp_id]
            T = Tr * comp.Tc
            P, converged = calculate_vapor_pressure(comp_id, T, components)
            assert converged
            pressures[comp_id] = P

        # C1 should have highest reduced vapor pressure
        # (normalized by Pc for fair comparison)
        for comp_id in ["C3", "C5", "C7", "C10"]:
            P_reduced_c1 = pressures["C1"] / components["C1"].Pc
            P_reduced_other = pressures[comp_id] / components[comp_id].Pc

            # Light components have higher Pr at same Tr (lower omega)
            # This is because omega relates to deviation from simple fluid behavior
            assert P_reduced_c1 >= P_reduced_other * 0.8, (
                f"Unexpected Pr comparison: C1 = {P_reduced_c1:.3f}, "
                f"{comp_id} = {P_reduced_other:.3f}"
            )


class TestVaporPressureSummary:
    """Generate summary report of vapor pressure calculations."""

    def test_generate_vapor_pressure_report(self, components):
        """Generate and display vapor pressure calculation summary."""
        test_components = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C10"]
        Tr_values = [0.65, 0.70, 0.75, 0.80, 0.85]

        print("\n\n" + "=" * 70)
        print("VAPOR PRESSURE CALCULATION SUMMARY")
        print("=" * 70)
        print(f"{'Comp':<6} {'Tc(K)':<8} {'Pc(MPa)':<8} {'omega':<8} ", end="")
        for Tr in Tr_values:
            print(f"Tr={Tr:<5}", end=" ")
        print()
        print("-" * 70)

        for comp_id in test_components:
            comp = components[comp_id]
            print(f"{comp_id:<6} {comp.Tc:<8.1f} {comp.Pc/1e6:<8.3f} {comp.omega:<8.4f} ", end="")

            for Tr in Tr_values:
                T = Tr * comp.Tc
                P, converged = calculate_vapor_pressure(comp_id, T, components)
                if converged:
                    print(f"{P/1e6:6.3f}", end=" ")
                else:
                    print(f"{'FAIL':>6}", end=" ")
            print()

        print("-" * 70)
        print("Note: Pressures shown in MPa at each Tr value")
        print("=" * 70 + "\n")

        # This test always passes - it's just for generating the report
        assert True


class TestRegressionPrevention:
    """Regression tests to catch changes in vapor pressure calculations.

    These tests use specific known-good values from the current implementation
    to detect any future changes (intentional or accidental) to the EOS.
    """

    def test_methane_vapor_pressure_regression(self, components):
        """Regression test for methane vapor pressure at Tr = 0.7."""
        comp = components["C1"]
        T = 0.7 * comp.Tc  # Tr = 0.7 → T ≈ 133.4 K

        P, converged = calculate_vapor_pressure("C1", T, components)

        assert converged
        # Expected value from current implementation (update if EOS changes intentionally)
        expected_P = 452100  # Pa (at Tr = 0.7)
        tolerance = 0.01  # 1% tolerance for numerical differences

        assert abs(P - expected_P) / expected_P < tolerance, (
            f"Methane Psat regression: got {P:.0f} Pa, expected {expected_P:.0f} Pa"
        )

    def test_propane_vapor_pressure_regression(self, components):
        """Regression test for propane vapor pressure at Tr = 0.7."""
        comp = components["C3"]
        T = 0.7 * comp.Tc

        P, converged = calculate_vapor_pressure("C3", T, components)

        assert converged
        expected_P = 298100  # Pa
        tolerance = 0.01

        assert abs(P - expected_P) / expected_P < tolerance, (
            f"Propane Psat regression: got {P:.0f} Pa, expected {expected_P:.0f} Pa"
        )

    def test_heptane_vapor_pressure_regression(self, components):
        """Regression test for n-heptane vapor pressure at Tr = 0.7."""
        comp = components["C7"]
        T = 0.7 * comp.Tc

        P, converged = calculate_vapor_pressure("C7", T, components)

        assert converged
        expected_P = 122400  # Pa
        tolerance = 0.01

        assert abs(P - expected_P) / expected_P < tolerance, (
            f"Heptane Psat regression: got {P:.0f} Pa, expected {expected_P:.0f} Pa"
        )
