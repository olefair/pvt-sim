"""Regression tests for CVD cell-volume closure behavior."""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.core.constants import R
from pvtcore.experiments.cvd import _cvd_step, simulate_cvd
from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS


def _assert_cell_volume_match(*, pressure: float, temperature: float, z_factor: float, moles: float, target_volume: float) -> None:
    reconstructed = moles * z_factor * R.Pa_m3_per_mol_K * temperature / pressure
    assert reconstructed == pytest.approx(target_volume, rel=1e-10, abs=1e-15)


def test_single_phase_cvd_step_preserves_target_cell_volume() -> None:
    """A single-phase depletion step must still close exactly to the target volume."""
    components = load_components()
    methane = [components["C1"]]
    eos = PengRobinsonEOS(methane)

    z = np.array([1.0])
    temperature = 250.0
    dew_pressure = 16_758_331.369557615
    step_pressure = 14_080_000.0

    z_initial = eos.compressibility(dew_pressure, temperature, z, phase="vapor")
    if isinstance(z_initial, list):
        z_initial = z_initial[-1]
    target_volume = z_initial * R.Pa_m3_per_mol_K * temperature / dew_pressure

    step, z_new, n_new, cumulative_gas = _cvd_step(
        step_pressure,
        temperature,
        z,
        1.0,
        0.0,
        target_volume,
        methane,
        eos,
        None,
    )

    assert step.gas_produced > 0.0
    assert cumulative_gas == pytest.approx(step.gas_produced)
    assert np.allclose(z_new, z)
    assert n_new == pytest.approx(step.moles_remaining)
    _assert_cell_volume_match(
        pressure=step.pressure,
        temperature=temperature,
        z_factor=step.Z_two_phase,
        moles=step.moles_remaining,
        target_volume=target_volume,
    )


def test_single_phase_cvd_run_keeps_volume_closed_for_each_step() -> None:
    """A pure-methane CVD path should preserve the target cell volume at every step."""
    components = load_components()
    methane = [components["C1"]]
    eos = PengRobinsonEOS(methane)

    z = np.array([1.0])
    temperature = 250.0
    dew_pressure = 16_758_331.369557615
    pressure_steps = np.linspace(dew_pressure, max(1e5, dew_pressure * 0.2), 6)

    z_initial = eos.compressibility(dew_pressure, temperature, z, phase="vapor")
    if isinstance(z_initial, list):
        z_initial = z_initial[-1]
    target_volume = z_initial * R.Pa_m3_per_mol_K * temperature / dew_pressure

    result = simulate_cvd(z, temperature, methane, eos, dew_pressure, pressure_steps)

    assert result.converged is True
    for step in result.steps:
        if np.isnan(step.Z_two_phase):
            continue
        if np.isclose(step.liquid_dropout, 0.0) or np.isclose(step.liquid_dropout, 1.0):
            _assert_cell_volume_match(
                pressure=step.pressure,
                temperature=temperature,
                z_factor=step.Z_two_phase,
                moles=step.moles_remaining,
                target_volume=target_volume,
            )
