"""Workflow-level tests for remaining pvtapp calculation types."""

from __future__ import annotations

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus


def _bubble_point_config() -> dict:
    return {
        "run_name": "Bubble Point - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.50},
                {"component_id": "C10", "mole_fraction": 0.50},
            ]
        },
        "calculation_type": "bubble_point",
        "eos_type": "peng_robinson",
        "bubble_point_config": {
            "temperature_k": 350.0,
        },
    }


def _dew_point_config() -> dict:
    return {
        "run_name": "Dew Point - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.85},
                {"component_id": "C3", "mole_fraction": 0.10},
                {"component_id": "C7", "mole_fraction": 0.05},
            ]
        },
        "calculation_type": "dew_point",
        "eos_type": "peng_robinson",
        "dew_point_config": {
            "temperature_k": 380.0,
        },
    }


def _dl_config() -> dict:
    return {
        "run_name": "DL - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.40},
                {"component_id": "C3", "mole_fraction": 0.30},
                {"component_id": "C10", "mole_fraction": 0.30},
            ]
        },
        "calculation_type": "differential_liberation",
        "eos_type": "peng_robinson",
        "dl_config": {
            "temperature_k": 350.0,
            "bubble_pressure_pa": 15e6,
            "pressure_end_pa": 1e6,
            "n_steps": 8,
        },
    }


def _cvd_config() -> dict:
    return {
        "run_name": "CVD - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.85},
                {"component_id": "C3", "mole_fraction": 0.10},
                {"component_id": "C7", "mole_fraction": 0.05},
            ]
        },
        "calculation_type": "cvd",
        "eos_type": "peng_robinson",
        "cvd_config": {
            "temperature_k": 380.0,
            "dew_pressure_pa": 20e6,
            "pressure_end_pa": 5e6,
            "n_steps": 8,
        },
    }


def _separator_config() -> dict:
    return {
        "run_name": "Separator - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.40},
                {"component_id": "C4", "mole_fraction": 0.35},
                {"component_id": "C10", "mole_fraction": 0.25},
            ]
        },
        "calculation_type": "separator",
        "eos_type": "peng_robinson",
        "separator_config": {
            "reservoir_pressure_pa": 30e6,
            "reservoir_temperature_k": 380.0,
            "include_stock_tank": True,
            "separator_stages": [
                {
                    "pressure_pa": 3e6,
                    "temperature_k": 320.0,
                    "name": "HP",
                },
                {
                    "pressure_pa": 5e5,
                    "temperature_k": 300.0,
                    "name": "LP",
                },
            ],
        },
    }


def test_bubble_point_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_bubble_point_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.bubble_point_result is not None
    assert result.bubble_point_result.pressure_pa > 0


def test_dew_point_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_dew_point_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dew_point_result is not None
    assert result.dew_point_result.pressure_pa > 0


def test_dl_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_dl_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dl_result is not None
    assert result.dl_result.converged is True
    assert len(result.dl_result.steps) > 0


def test_cvd_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_cvd_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.cvd_result is not None
    assert result.cvd_result.converged is True
    assert len(result.cvd_result.steps) > 0


def test_separator_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_separator_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.separator_result is not None
    assert result.separator_result.bo > 0
    assert len(result.separator_result.stages) >= 2