"""Workflow-level tests for pvtapp CCE execution."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError as PydanticValidationError

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus


def _cce_config(
    temperature_k: float = 350.0,
    pressure_start_pa: float = 30e6,
    pressure_end_pa: float = 5e6,
    n_steps: int = 8,
) -> dict:
    return {
        "run_name": "CCE - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.50},
                {"component_id": "C3", "mole_fraction": 0.30},
                {"component_id": "C10", "mole_fraction": 0.20},
            ]
        },
        "calculation_type": "cce",
        "eos_type": "peng_robinson",
        "cce_config": {
            "temperature_k": temperature_k,
            "pressure_start_pa": pressure_start_pa,
            "pressure_end_pa": pressure_end_pa,
            "n_steps": n_steps,
        },
    }


def test_cce_workflow_happy_path() -> None:
    """A valid CCE run should complete and return pressure-step results."""
    config = RunConfig.model_validate(_cce_config())

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.cce_result is not None
    assert result.phase_envelope_result is None
    assert result.pt_flash_result is None

    cce = result.cce_result
    assert cce.temperature_k == pytest.approx(config.cce_config.temperature_k)
    assert len(cce.steps) == config.cce_config.n_steps

    pressures = [step.pressure_pa for step in cce.steps]
    assert pressures[0] == pytest.approx(config.cce_config.pressure_start_pa)
    assert pressures[-1] == pytest.approx(config.cce_config.pressure_end_pa)
    assert all(pressures[i] >= pressures[i + 1] for i in range(len(pressures) - 1))
    assert all(step.relative_volume > 0 for step in cce.steps)

    if cce.saturation_pressure_pa is not None:
        assert cce.saturation_pressure_pa > 0


def test_cce_invalid_pressure_range_fails_schema_validation() -> None:
    """CCE config must use descending pressures from start to end."""
    config_data = _cce_config()
    bad_data = copy.deepcopy(config_data)
    bad_data["cce_config"]["pressure_start_pa"] = 5e6
    bad_data["cce_config"]["pressure_end_pa"] = 30e6

    with pytest.raises(
        PydanticValidationError,
        match="must be greater than",
    ):
        RunConfig.model_validate(bad_data)