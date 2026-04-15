"""Workflow-level tests for remaining pvtapp calculation types."""

from __future__ import annotations

import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import ConvergenceStatusEnum, RunConfig, RunStatus


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
    assert result.bubble_point_result.diagnostics is not None
    assert result.bubble_point_result.diagnostics.status == ConvergenceStatusEnum.CONVERGED
    assert result.bubble_point_result.certificate is not None


def test_bubble_point_workflow_surfaces_degenerate_boundary_failure() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Bubble Point - CO2 rich repro",
            "composition": {
                "components": [
                    {"component_id": "CO2", "mole_fraction": 0.6498},
                    {"component_id": "C1", "mole_fraction": 0.1057},
                    {"component_id": "C2", "mole_fraction": 0.1058},
                    {"component_id": "C3", "mole_fraction": 0.1235},
                    {"component_id": "nC4", "mole_fraction": 0.0152},
                ]
            },
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 573.15,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.FAILED
    assert result.bubble_point_result is None
    assert result.error_message is not None
    assert "degenerate trivial stability solution" in result.error_message


def test_dew_point_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_dew_point_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dew_point_result is not None
    assert result.dew_point_result.pressure_pa > 0
    assert result.dew_point_result.diagnostics is not None
    assert result.dew_point_result.diagnostics.status == ConvergenceStatusEnum.CONVERGED
    assert result.dew_point_result.certificate is not None


def test_dl_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_dl_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dl_result is not None
    assert result.dl_result.converged is True
    assert result.dl_result.residual_oil_density_kg_per_m3 is not None
    assert result.dl_result.residual_oil_density_kg_per_m3 > 0.0
    assert len(result.dl_result.steps) > 0
    assert all(step.oil_density_kg_per_m3 is not None for step in result.dl_result.steps)
    assert all(step.oil_viscosity_pa_s is not None for step in result.dl_result.steps)
    assert all(step.gas_z_factor is not None for step in result.dl_result.steps)
    assert all(step.cumulative_gas_produced is not None for step in result.dl_result.steps)
    assert any(step.gas_viscosity_pa_s is not None for step in result.dl_result.steps[1:])


def test_dl_workflow_supports_explicit_pressure_list() -> None:
    config = RunConfig.model_validate(
        {
            **_dl_config(),
            "dl_config": {
                "temperature_k": 350.0,
                "bubble_pressure_pa": 15e6,
                "pressure_points_pa": [8e6, 3e6, 1e6],
            },
        }
    )
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dl_result is not None
    assert result.dl_result.converged is True
    assert [step.pressure_pa for step in result.dl_result.steps] == pytest.approx(
        [15e6, 8e6, 3e6, 1e6]
    )


def test_cvd_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_cvd_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.cvd_result is not None
    assert result.cvd_result.converged is True
    assert len(result.cvd_result.steps) > 0
    assert all(
        step.liquid_viscosity_pa_s is not None or step.vapor_viscosity_pa_s is not None
        for step in result.cvd_result.steps
    )


def test_separator_workflow_happy_path() -> None:
    config = RunConfig.model_validate(_separator_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.separator_result is not None
    assert result.separator_result.bo > 0
    assert result.separator_result.stock_tank_oil_mw_g_per_mol is not None
    assert result.separator_result.stock_tank_oil_specific_gravity is not None
    assert result.separator_result.total_gas_moles is not None
    assert result.separator_result.shrinkage is not None
    assert len(result.separator_result.stages) >= 2
