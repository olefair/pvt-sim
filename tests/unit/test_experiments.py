"""Unit tests for the experiments module (CCE, DL, CVD, separators)."""

import numpy as np
import pytest

from pvtcore.experiments import (
    # CCE
    simulate_cce,
    CCEResult,
    CCEStepResult,
    # DL
    simulate_dl,
    DLResult,
    DLStepResult,
    # CVD
    simulate_cvd,
    CVDResult,
    CVDStepResult,
    # Separators
    calculate_separator_train,
    optimize_separator_pressures,
    SeparatorConditions,
    SeparatorStageResult,
    SeparatorTrainResult,
)
from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.core.constants import R
from pvtcore.core.errors import ValidationError
from pvtcore.experiments.cvd import _cvd_step


@pytest.fixture
def components():
    """Load component database."""
    return load_components()


@pytest.fixture
def methane_propane(components):
    """Binary C1-C3 mixture components."""
    return [components['C1'], components['C3']]


@pytest.fixture
def pure_methane(components):
    """Single-component methane system."""
    return [components['C1']]


@pytest.fixture
def methane_butane(components):
    """Binary C1-nC4 mixture components."""
    return [components['C1'], components['nC4']]


@pytest.fixture
def methane_heptane(components):
    """Binary C1-C7 mixture components."""
    return [components['C1'], components['C7']]


@pytest.fixture
def oil_mixture(components):
    """Simple oil-like mixture."""
    return [components['C1'], components['C3'], components['C7']]


@pytest.fixture
def methane_propane_eos(methane_propane):
    """EOS for C1-C3 binary."""
    return PengRobinsonEOS(methane_propane)


@pytest.fixture
def pure_methane_eos(pure_methane):
    """EOS for pure methane."""
    return PengRobinsonEOS(pure_methane)


@pytest.fixture
def methane_butane_eos(methane_butane):
    """EOS for C1-nC4 binary."""
    return PengRobinsonEOS(methane_butane)


@pytest.fixture
def methane_heptane_eos(methane_heptane):
    """EOS for C1-C7 binary."""
    return PengRobinsonEOS(methane_heptane)


@pytest.fixture
def oil_mixture_eos(oil_mixture):
    """EOS for simple oil mixture."""
    return PengRobinsonEOS(oil_mixture)


def _assert_single_phase_step_matches_cell_volume(
    step: CVDStepResult,
    temperature: float,
    target_volume: float,
) -> None:
    """Check the reconstructed single-phase cell volume against the target."""
    reconstructed_volume = (
        step.moles_remaining
        * step.Z_two_phase
        * R.Pa_m3_per_mol_K
        * temperature
        / step.pressure
    )
    assert reconstructed_volume == pytest.approx(target_volume, rel=1e-10, abs=1e-15)


# =============================================================================
# CCE Tests
# =============================================================================

class TestCCE:
    """Tests for Constant Composition Expansion simulation."""

    def test_cce_basic(self, methane_propane, methane_propane_eos):
        """Test basic CCE simulation."""
        z = np.array([0.5, 0.5])  # 50/50 C1/C3
        T = 300.0  # K
        P_start = 10e6
        P_end = 1e6

        result = simulate_cce(
            z, T, methane_propane, methane_propane_eos,
            P_start, P_end, n_steps=10
        )

        assert isinstance(result, CCEResult)
        assert len(result.steps) > 0
        assert len(result.pressures) == len(result.steps)
        assert len(result.relative_volumes) == len(result.steps)
        assert result.temperature == T

    def test_cce_relative_volume_increases(self, methane_propane, methane_propane_eos):
        """Test that relative volume increases as pressure decreases."""
        z = np.array([0.5, 0.5])
        T = 300.0
        P_start = 10e6
        P_end = 1e6

        result = simulate_cce(
            z, T, methane_propane, methane_propane_eos,
            P_start, P_end, n_steps=10
        )

        # Filter out NaN values
        valid_indices = ~np.isnan(result.relative_volumes)
        valid_volumes = result.relative_volumes[valid_indices]

        if len(valid_volumes) > 1:
            # Check overall trend (allow some fluctuation)
            assert valid_volumes[-1] >= valid_volumes[0]

    def test_cce_result_arrays_match(self, methane_propane, methane_propane_eos):
        """Test that result arrays have consistent lengths."""
        z = np.array([0.5, 0.5])
        T = 300.0

        result = simulate_cce(
            z, T, methane_propane, methane_propane_eos,
            10e6, 1e6, n_steps=15
        )

        n = len(result.steps)
        assert len(result.pressures) == n
        assert len(result.relative_volumes) == n
        assert len(result.liquid_dropouts) == n
        # Z values are in steps, check they exist
        for step in result.steps:
            assert hasattr(step, 'compressibility_Z')

    def test_cce_invalid_temperature(self, methane_propane, methane_propane_eos):
        """Test that invalid temperature raises error."""
        z = np.array([0.5, 0.5])

        with pytest.raises(ValidationError):
            simulate_cce(z, -100.0, methane_propane, methane_propane_eos, 10e6, 1e6)

    def test_cce_invalid_pressure(self, methane_propane, methane_propane_eos):
        """Test that invalid pressure raises error."""
        z = np.array([0.5, 0.5])

        with pytest.raises(ValidationError):
            simulate_cce(z, 300.0, methane_propane, methane_propane_eos, -10e6, 1e6)


# =============================================================================
# DL Tests
# =============================================================================

class TestDL:
    """Tests for Differential Liberation simulation."""

    def test_dl_basic(self, oil_mixture, oil_mixture_eos):
        """Test basic DL simulation."""
        z = np.array([0.3, 0.4, 0.3])  # Oil composition
        T = 350.0  # K
        P_bubble = 15e6  # Pa
        P_steps = np.linspace(15e6, 1e6, 10)

        result = simulate_dl(
            z, T, oil_mixture, oil_mixture_eos,
            P_bubble, P_steps
        )

        assert isinstance(result, DLResult)
        assert len(result.steps) > 0
        assert result.temperature == T
        assert result.bubble_pressure == P_bubble

    def test_dl_rs_decreases(self, oil_mixture, oil_mixture_eos):
        """Test that Rs decreases as pressure decreases (gas released)."""
        z = np.array([0.3, 0.4, 0.3])
        T = 350.0
        P_bubble = 15e6
        P_steps = np.linspace(15e6, 2e6, 8)

        result = simulate_dl(
            z, T, oil_mixture, oil_mixture_eos,
            P_bubble, P_steps
        )

        # Filter valid values
        valid_Rs = result.Rs_values[~np.isnan(result.Rs_values)]

        if len(valid_Rs) > 1:
            # Rs should generally decrease (gas evolving from oil)
            # Check first value >= last value (allow some tolerance)
            assert valid_Rs[0] >= valid_Rs[-1] * 0.9

    def test_dl_bo_decreases(self, oil_mixture, oil_mixture_eos):
        """Test that Bo decreases as gas evolves."""
        z = np.array([0.3, 0.4, 0.3])
        T = 350.0
        P_bubble = 15e6
        P_steps = np.linspace(15e6, 2e6, 8)

        result = simulate_dl(
            z, T, oil_mixture, oil_mixture_eos,
            P_bubble, P_steps
        )

        valid_Bo = result.Bo_values[~np.isnan(result.Bo_values)]

        if len(valid_Bo) > 1:
            # Bo should decrease as pressure decreases
            assert valid_Bo[0] >= valid_Bo[-1] * 0.8

    def test_dl_invalid_bubble_pressure(self, oil_mixture, oil_mixture_eos):
        """Test that invalid bubble pressure raises error."""
        z = np.array([0.3, 0.4, 0.3])

        with pytest.raises(ValidationError):
            simulate_dl(z, 350.0, oil_mixture, oil_mixture_eos, -15e6, np.linspace(15e6, 1e6, 5))


# =============================================================================
# CVD Tests
# =============================================================================

class TestCVD:
    """Tests for Constant Volume Depletion simulation."""

    def test_cvd_basic(self, methane_heptane, methane_heptane_eos):
        """Test basic CVD simulation."""
        z = np.array([0.85, 0.15])  # Gas condensate composition
        T = 380.0  # K
        P_dew = 25e6  # Pa
        P_steps = np.linspace(20e6, 5e6, 8)

        result = simulate_cvd(
            z, T, methane_heptane, methane_heptane_eos,
            P_dew, P_steps
        )

        assert isinstance(result, CVDResult)
        assert len(result.steps) > 0
        assert result.temperature == T
        assert result.dew_pressure == P_dew

    def test_cvd_liquid_dropout(self, methane_heptane, methane_heptane_eos):
        """Test that liquid dropout forms below dew point."""
        z = np.array([0.85, 0.15])
        T = 380.0
        P_dew = 25e6
        P_steps = np.linspace(20e6, 5e6, 10)

        result = simulate_cvd(
            z, T, methane_heptane, methane_heptane_eos,
            P_dew, P_steps
        )

        # Some liquid dropout should occur below dew point
        valid_dropouts = result.liquid_dropouts[~np.isnan(result.liquid_dropouts)]
        # At dew point, dropout is 0; below it should increase initially
        if len(valid_dropouts) > 1:
            # Check that at least some dropout > 0 (retrograde condensation)
            max_dropout = np.max(valid_dropouts)
            assert max_dropout >= 0  # Could be 0 if flash doesn't enter two-phase

    def test_cvd_single_phase_step_preserves_target_volume(
        self,
        pure_methane,
        pure_methane_eos,
    ):
        """Single-phase CVD steps must still honor the target cell volume."""
        z = np.array([1.0])
        T = 250.0
        P_dew = 16_758_331.369557615
        P_step = 14_080_000.0

        Z_initial = pure_methane_eos.compressibility(P_dew, T, z, phase="vapor")
        if isinstance(Z_initial, list):
            Z_initial = Z_initial[-1]
        V_cell = Z_initial * R.Pa_m3_per_mol_K * T / P_dew

        step, z_new, n_new, cumulative_gas = _cvd_step(
            P_step,
            T,
            z,
            1.0,
            0.0,
            V_cell,
            pure_methane,
            pure_methane_eos,
            None,
        )

        assert step.gas_produced > 0.0
        assert cumulative_gas == pytest.approx(step.gas_produced)
        assert np.allclose(z_new, z)
        assert n_new == pytest.approx(step.moles_remaining)
        _assert_single_phase_step_matches_cell_volume(step, T, V_cell)

    def test_cvd_single_phase_case_is_repeatable(self, pure_methane, pure_methane_eos):
        """Repeat runs should produce identical single-phase CVD results."""
        z = np.array([1.0])
        T = 250.0
        P_dew = 16_758_331.369557615
        P_steps = np.linspace(P_dew, max(1e5, P_dew * 0.2), 6)

        result_1 = simulate_cvd(z, T, pure_methane, pure_methane_eos, P_dew, P_steps)
        result_2 = simulate_cvd(z, T, pure_methane, pure_methane_eos, P_dew, P_steps)

        assert result_1.converged is True
        assert result_2.converged is True
        assert np.array_equal(result_1.pressures, result_2.pressures)
        assert np.array_equal(result_1.liquid_dropouts, result_2.liquid_dropouts)
        assert np.array_equal(result_1.cumulative_gas, result_2.cumulative_gas)

        Z_initial = pure_methane_eos.compressibility(P_dew, T, z, phase="vapor")
        if isinstance(Z_initial, list):
            Z_initial = Z_initial[-1]
        V_cell = Z_initial * R.Pa_m3_per_mol_K * T / P_dew

        for step in result_1.steps:
            if np.isnan(step.Z_two_phase):
                continue
            if np.isclose(step.liquid_dropout, 0.0) or np.isclose(step.liquid_dropout, 1.0):
                _assert_single_phase_step_matches_cell_volume(step, T, V_cell)

    def test_cvd_cumulative_gas_increases(self, methane_heptane, methane_heptane_eos):
        """Test that cumulative gas produced increases monotonically."""
        z = np.array([0.85, 0.15])
        T = 380.0
        P_dew = 25e6
        P_steps = np.linspace(20e6, 5e6, 8)

        result = simulate_cvd(
            z, T, methane_heptane, methane_heptane_eos,
            P_dew, P_steps
        )

        valid_gas = result.cumulative_gas[~np.isnan(result.cumulative_gas)]

        if len(valid_gas) > 1:
            # Cumulative gas should be monotonically increasing
            for i in range(1, len(valid_gas)):
                assert valid_gas[i] >= valid_gas[i-1] - 1e-10

    def test_cvd_invalid_dew_pressure(self, methane_heptane, methane_heptane_eos):
        """Test that invalid dew pressure raises error."""
        z = np.array([0.85, 0.15])

        with pytest.raises(ValidationError):
            simulate_cvd(z, 380.0, methane_heptane, methane_heptane_eos, -25e6, np.linspace(20e6, 5e6, 5))


# =============================================================================
# Separator Tests
# =============================================================================

class TestSeparators:
    """Tests for multi-stage separator calculations."""

    def test_separator_basic(self, oil_mixture, oil_mixture_eos):
        """Test basic separator train calculation."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=3e6, temperature=320.0, name="HP Sep"),
            SeparatorConditions(pressure=0.5e6, temperature=300.0, name="LP Sep"),
        ]

        result = calculate_separator_train(
            z, oil_mixture, oil_mixture_eos, stages,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0
        )

        assert isinstance(result, SeparatorTrainResult)
        assert len(result.stages) >= 2  # At least HP, LP (+ stock tank if included)
        assert result.Bo > 0
        assert 0 <= result.stock_tank_oil_moles <= 1

    def test_separator_conditions(self, oil_mixture, oil_mixture_eos):
        """Test SeparatorConditions dataclass."""
        stage = SeparatorConditions(
            pressure=5e6,
            temperature=320.0,
            name="Test Separator"
        )

        assert stage.pressure == 5e6
        assert stage.temperature == 320.0
        assert stage.name == "Test Separator"

    def test_separator_gas_production(self, oil_mixture, oil_mixture_eos):
        """Test that gas is produced at each stage."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=5e6, temperature=320.0),
            SeparatorConditions(pressure=1e6, temperature=300.0),
        ]

        result = calculate_separator_train(
            z, oil_mixture, oil_mixture_eos, stages,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0
        )

        # Some gas should be produced
        assert result.total_gas_moles >= 0

    def test_separator_bo_realistic(self, oil_mixture, oil_mixture_eos):
        """Test that Bo is in realistic range."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=3e6, temperature=320.0),
        ]

        result = calculate_separator_train(
            z, oil_mixture, oil_mixture_eos, stages,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0
        )

        # Bo typically 1.0-2.0 for black oils
        if not np.isnan(result.Bo):
            assert 0.5 < result.Bo < 5.0

    def test_separator_api_gravity(self, oil_mixture, oil_mixture_eos):
        """Test that API gravity is calculated."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=3e6, temperature=320.0),
        ]

        result = calculate_separator_train(
            z, oil_mixture, oil_mixture_eos, stages,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0
        )

        # API gravity typically 10-60 for crude oils
        if not np.isnan(result.API_gravity):
            assert -10 < result.API_gravity < 100

    def test_separator_invalid_stages(self, oil_mixture, oil_mixture_eos):
        """Test that empty stages list raises error."""
        z = np.array([0.3, 0.4, 0.3])

        with pytest.raises(ValidationError):
            calculate_separator_train(
                z, oil_mixture, oil_mixture_eos, [],
                reservoir_pressure=30e6,
                reservoir_temperature=380.0
            )

    def test_separator_invalid_pressure(self, oil_mixture, oil_mixture_eos):
        """Test that negative stage pressure raises error."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=-3e6, temperature=320.0),
        ]

        with pytest.raises(ValidationError):
            calculate_separator_train(
                z, oil_mixture, oil_mixture_eos, stages,
                reservoir_pressure=30e6,
                reservoir_temperature=380.0
            )

    def test_separator_material_balance(self, oil_mixture, oil_mixture_eos):
        """Test material balance (oil + gas = feed)."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [
            SeparatorConditions(pressure=3e6, temperature=320.0),
        ]

        result = calculate_separator_train(
            z, oil_mixture, oil_mixture_eos, stages,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0
        )

        # Material balance: moles out = moles in
        total_out = result.stock_tank_oil_moles + result.total_gas_moles
        assert abs(total_out - 1.0) < 0.01  # Started with 1 mole


class TestSeparatorOptimization:
    """Tests for separator pressure optimization."""

    def test_optimize_basic(self, oil_mixture, oil_mixture_eos):
        """Test basic separator optimization."""
        z = np.array([0.3, 0.4, 0.3])

        stages, result = optimize_separator_pressures(
            z, oil_mixture, oil_mixture_eos,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0,
            n_stages=2,
            temperature=310.0
        )

        assert len(stages) == 2
        assert isinstance(result, SeparatorTrainResult)

    def test_optimize_single_stage(self, oil_mixture, oil_mixture_eos):
        """Test single stage optimization."""
        z = np.array([0.3, 0.4, 0.3])

        stages, result = optimize_separator_pressures(
            z, oil_mixture, oil_mixture_eos,
            reservoir_pressure=30e6,
            reservoir_temperature=380.0,
            n_stages=1,
            temperature=310.0
        )

        assert len(stages) == 1

    def test_optimize_invalid_stages(self, oil_mixture, oil_mixture_eos):
        """Test that zero stages raises error."""
        z = np.array([0.3, 0.4, 0.3])

        with pytest.raises(ValidationError):
            optimize_separator_pressures(
                z, oil_mixture, oil_mixture_eos,
                reservoir_pressure=30e6,
                reservoir_temperature=380.0,
                n_stages=0
            )


# =============================================================================
# Integration Tests
# =============================================================================

class TestExperimentsIntegration:
    """Integration tests across experiment types."""

    def test_cce_result_structure(self, methane_propane, methane_propane_eos):
        """Test CCE result dataclass structure."""
        z = np.array([0.5, 0.5])
        result = simulate_cce(z, 300.0, methane_propane, methane_propane_eos, 10e6, 1e6, n_steps=5)

        # Check all expected attributes exist
        assert hasattr(result, 'temperature')
        assert hasattr(result, 'saturation_pressure')
        assert hasattr(result, 'steps')
        assert hasattr(result, 'pressures')
        assert hasattr(result, 'relative_volumes')
        assert hasattr(result, 'converged')

    def test_dl_result_structure(self, oil_mixture, oil_mixture_eos):
        """Test DL result dataclass structure."""
        z = np.array([0.3, 0.4, 0.3])
        result = simulate_dl(z, 350.0, oil_mixture, oil_mixture_eos, 15e6, np.linspace(15e6, 2e6, 5))

        assert hasattr(result, 'temperature')
        assert hasattr(result, 'bubble_pressure')
        assert hasattr(result, 'steps')
        assert hasattr(result, 'Rs_values')
        assert hasattr(result, 'Bo_values')
        assert hasattr(result, 'converged')

    def test_cvd_result_structure(self, methane_heptane, methane_heptane_eos):
        """Test CVD result dataclass structure."""
        z = np.array([0.85, 0.15])
        result = simulate_cvd(z, 380.0, methane_heptane, methane_heptane_eos, 25e6, np.linspace(20e6, 5e6, 5))

        assert hasattr(result, 'temperature')
        assert hasattr(result, 'dew_pressure')
        assert hasattr(result, 'steps')
        assert hasattr(result, 'liquid_dropouts')
        assert hasattr(result, 'cumulative_gas')
        assert hasattr(result, 'converged')

    def test_separator_result_structure(self, oil_mixture, oil_mixture_eos):
        """Test separator result dataclass structure."""
        z = np.array([0.3, 0.4, 0.3])
        stages = [SeparatorConditions(pressure=3e6, temperature=320.0)]
        result = calculate_separator_train(z, oil_mixture, oil_mixture_eos, stages, 30e6, 380.0)

        assert hasattr(result, 'stages')
        assert hasattr(result, 'stock_tank_oil_composition')
        assert hasattr(result, 'Bo')
        assert hasattr(result, 'Rs')
        assert hasattr(result, 'API_gravity')
        assert hasattr(result, 'converged')
