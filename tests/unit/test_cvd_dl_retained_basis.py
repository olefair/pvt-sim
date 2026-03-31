"""Regression tests for retained-basis depletion result fields."""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.experiments import simulate_cvd, simulate_dl
from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS


@pytest.fixture
def components():
    return load_components()


@pytest.fixture
def oil_components(components):
    return [components["C1"], components["C3"], components["C7"]]


@pytest.fixture
def gas_condensate_components(components):
    return [components["C1"], components["C7"]]


def test_dl_exposes_retained_liquid_inventory_step_to_step(oil_components) -> None:
    """DL steps should expose the retained liquid inventory carried forward."""
    eos = PengRobinsonEOS(oil_components)
    z = np.array([0.3, 0.4, 0.3])
    temperature = 350.0
    bubble_pressure = 15e6
    pressure_steps = np.linspace(15e6, 2e6, 8)

    result = simulate_dl(z, temperature, oil_components, eos, bubble_pressure, pressure_steps)

    assert result.steps[0].liquid_moles_remaining == pytest.approx(1.0)

    previous = result.steps[0].liquid_moles_remaining
    for step in result.steps[1:]:
        assert step.liquid_moles_remaining <= previous + 1e-12
        previous = step.liquid_moles_remaining


def test_cvd_exposes_moles_remaining_and_cumulative_gas(oil_components) -> None:
    """CVD steps should expose retained moles and cumulative produced gas."""
    eos = PengRobinsonEOS(oil_components)
    z = np.array([0.85, 0.10, 0.05])
    temperature = 380.0
    dew_pressure = 25e6
    pressure_steps = np.linspace(20e6, 5e6, 8)

    result = simulate_cvd(z, temperature, oil_components, eos, dew_pressure, pressure_steps)

    assert result.steps[0].moles_remaining == pytest.approx(1.0)
    previous_remaining = result.steps[0].moles_remaining
    previous_cumulative = result.steps[0].cumulative_gas_produced

    for step in result.steps[1:]:
        assert step.moles_remaining <= previous_remaining + 1e-12
        assert step.cumulative_gas_produced >= previous_cumulative - 1e-12
        previous_remaining = step.moles_remaining
        previous_cumulative = step.cumulative_gas_produced
