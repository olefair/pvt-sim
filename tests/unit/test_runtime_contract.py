"""Consolidated runtime-contract tests for pvtapp calculation dispatch.

Covers: config validation, all workflow types, plus-fraction characterization,
phase envelope tracers and result structure, stability analysis, run-history
rerun, cancellation, progress callbacks, assignment presets, PT-flash transport
properties, and fluid-input preparation edge cases.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from pvtapp.assignment_case import build_assignment_desktop_preset
from pvtapp.job_runner import (
    ProgressCallback,
    _infer_phase_envelope_runtime_family,
    _prepare_fluid_inputs,
    build_rerun_config,
    execute_cvd,
    load_run_config,
    load_run_result,
    rerun_saved_run,
    run_calculation,
    validate_runtime_config,
)
from pvtapp.schemas import (
    EOSType,
    ConvergenceStatusEnum,
    PhaseEnvelopePoint,
    PhaseEnvelopeResult,
    PhaseEnvelopeTracingMethod,
    PTFlashResult,
    RunConfig,
    RunStatus,
    SolverDiagnostics,
    StabilityAnalysisResult,
)
from pvtcore.eos import PR78EOS
from pvtcore.flash import calculate_bubble_point
from pvtcore.validation.pete665_assignment import (
    build_assignment_fluid,
    load_assignment_case,
    psia_to_pa,
)

# ---------------------------------------------------------------------------
# Shared config builders
# ---------------------------------------------------------------------------


def _pt_flash_config(*, eos_type: str = "peng_robinson") -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": f"PT Flash - {eos_type}",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": eos_type,
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )


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


def _cce_config() -> dict:
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
            "temperature_k": 350.0,
            "pressure_start_pa": 30e6,
            "pressure_end_pa": 5e6,
            "n_steps": 8,
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


def test_execute_cvd_uses_explicit_pressure_points(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_simulate_cvd(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            temperature=kwargs["temperature"],
            dew_pressure=kwargs["dew_pressure"],
            initial_Z=1.0,
            converged=True,
            steps=[],
        )

    monkeypatch.setattr("pvtcore.experiments.simulate_cvd", fake_simulate_cvd)
    config = RunConfig.model_validate({
        **_cvd_config(),
        "cvd_config": {
            "temperature_k": 380.0,
            "dew_pressure_pa": 20e6,
            "pressure_points_pa": [15e6, 10e6, 5e6],
        },
    })

    result = execute_cvd(config)

    assert result.dew_pressure_pa == pytest.approx(20e6)
    assert list(captured["pressure_steps"]) == pytest.approx([15e6, 10e6, 5e6])


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
                {"pressure_pa": 3e6, "temperature_k": 320.0, "name": "HP"},
                {"pressure_pa": 5e5, "temperature_k": 300.0, "name": "LP"},
            ],
        },
    }


def _stability_config() -> dict:
    return {
        "run_name": "Stability Analysis - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.5},
                {"component_id": "C10", "mole_fraction": 0.5},
            ]
        },
        "calculation_type": "stability_analysis",
        "eos_type": "peng_robinson",
        "stability_analysis_config": {
            "pressure_pa": 3.0e6,
            "temperature_k": 300.0,
            "feed_phase": "liquid",
            "use_gdem": True,
            "n_random_trials": 1,
            "random_seed": 7,
            "max_eos_failures_per_trial": 4,
            "pressure_unit": "bar",
            "temperature_unit": "C",
        },
    }


def _phase_envelope_config() -> dict:
    return {
        "run_name": "Phase Envelope - Test",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.50},
                {"component_id": "C10", "mole_fraction": 0.50},
            ]
        },
        "calculation_type": "phase_envelope",
        "eos_type": "peng_robinson",
        "phase_envelope_config": {
            "temperature_min_k": 150.0,
            "temperature_max_k": 600.0,
            "n_points": 20,
        },
    }


def _tbp_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "TBP Runtime Contract",
            "calculation_type": "tbp",
            "tbp_config": {
                "cuts": [
                    {"name": "C7", "z": 0.020, "mw": 96.0, "sg": 0.74},
                    {"name": "C8", "z": 0.015, "mw": 110.0, "sg": 0.77},
                    {"name": "C9", "z": 0.015, "mw": 124.0, "sg": 0.80},
                ]
            },
        }
    )


def _oil_plus_fraction_composition_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0021},
            {"component_id": "CO2", "mole_fraction": 0.0187},
            {"component_id": "C1", "mole_fraction": 0.3478},
            {"component_id": "C2", "mole_fraction": 0.0712},
            {"component_id": "C3", "mole_fraction": 0.0934},
            {"component_id": "iC4", "mole_fraction": 0.0302},
            {"component_id": "nC4", "mole_fraction": 0.0431},
            {"component_id": "iC5", "mole_fraction": 0.0276},
            {"component_id": "nC5", "mole_fraction": 0.0418},
            {"component_id": "C6", "mole_fraction": 0.0574},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.2667,
            "mw_plus_g_per_mol": 119.78759868766404,
            "sg_plus_60f": 0.82,
        },
    }


def _bubble_point_plus_fraction_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "Bubble Point - plus fraction solve",
            "composition": {
                "components": [
                    {"component_id": "N2", "mole_fraction": 0.0021},
                    {"component_id": "CO2", "mole_fraction": 0.0187},
                    {"component_id": "C1", "mole_fraction": 0.3478},
                    {"component_id": "C2", "mole_fraction": 0.0712},
                    {"component_id": "C3", "mole_fraction": 0.0934},
                    {"component_id": "iC4", "mole_fraction": 0.0302},
                    {"component_id": "nC4", "mole_fraction": 0.0431},
                    {"component_id": "iC5", "mole_fraction": 0.0276},
                    {"component_id": "nC5", "mole_fraction": 0.0418},
                    {"component_id": "C6", "mole_fraction": 0.0574},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.2667,
                    "mw_plus_g_per_mol": 119.78759868766404,
                    "sg_plus_60f": 0.82,
                    "characterization_preset": "manual",
                    "max_carbon_number": 20,
                    "split_mw_model": "table",
                    "lumping_enabled": True,
                    "lumping_n_groups": 6,
                },
            },
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 360.0,
                "pressure_initial_pa": 1.0e5,
            },
        }
    )


def _assert_resolved_plus_fraction(
    config: RunConfig,
    *,
    resolved_preset: str,
    split_method: str,
    split_mw_model: str,
    max_carbon_number: int,
    lumping_n_groups: int,
    lumping_method: str = "whitson",
) -> None:
    plus_fraction = config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.characterization_preset.value == "auto"
    assert plus_fraction.resolved_characterization_preset is not None
    assert plus_fraction.resolved_characterization_preset.value == resolved_preset
    assert plus_fraction.split_method == split_method
    assert plus_fraction.split_mw_model == split_mw_model
    assert plus_fraction.max_carbon_number == max_carbon_number
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == lumping_n_groups
    assert plus_fraction.lumping_method == lumping_method


# ---------------------------------------------------------------------------
# Cancellation callback helpers
# ---------------------------------------------------------------------------


class _CancelAfterDispatchCallback(ProgressCallback):
    def __init__(self) -> None:
        self._cancelled = False
        self.cancelled_run_id: str | None = None

    def on_progress(self, run_id: str, progress: float, message: str) -> None:
        if progress >= 0.3:
            self._cancelled = True

    def on_cancelled(self, run_id: str) -> None:
        self.cancelled_run_id = run_id

    def is_cancelled(self) -> bool:
        return self._cancelled


class _CancelAfterNChecksCallback(ProgressCallback):
    def __init__(self, cancel_after_checks: int) -> None:
        self.cancel_after_checks = cancel_after_checks
        self.check_count = 0
        self.cancelled_run_id: str | None = None

    def on_cancelled(self, run_id: str) -> None:
        self.cancelled_run_id = run_id

    def is_cancelled(self) -> bool:
        self.check_count += 1
        return self.check_count >= self.cancel_after_checks


# ===================================================================
# 1. test_validate_runtime_config
# ===================================================================

_VALID_CONFIGS: list[tuple[str, dict[str, Any]]] = [
    (
        "pr",
        {
            "run_name": "PT Flash - PR",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "srk",
        {
            "run_name": "PT Flash - SRK",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "srk",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "pr78",
        {
            "run_name": "PT Flash - PR78",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "pr78",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "alias_bip",
        {
            "run_name": "PT Flash - alias contract",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "nC4", "mole_fraction": 0.5},
                ]
            },
            "binary_interaction": {"C1-nC4": 0.01},
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "plus_fraction",
        {
            "run_name": "PT Flash - plus fraction",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.35},
                    {"component_id": "C2", "mole_fraction": 0.20},
                    {"component_id": "C3", "mole_fraction": 0.15},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.30,
                    "mw_plus_g_per_mol": 150.0,
                    "sg_plus_60f": 0.82,
                    "max_carbon_number": 20,
                },
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "pedersen_tbp_fit",
        {
            "run_name": "PT Flash - TBP-backed Pedersen fit",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.35},
                    {"component_id": "C2", "mole_fraction": 0.20},
                    {"component_id": "C3", "mole_fraction": 0.15},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.30,
                    "mw_plus_g_per_mol": 108.13333333333334,
                    "sg_plus_60f": 0.82,
                    "characterization_preset": "manual",
                    "max_carbon_number": 12,
                    "split_method": "pedersen",
                    "split_mw_model": "paraffin",
                    "pedersen_solve_ab_from": "fit_to_tbp",
                    "tbp_cuts": [
                        {"name": "C7", "z": 0.120, "mw": 96.0},
                        {"name": "C8", "z": 0.100, "mw": 110.0},
                        {"name": "C9", "z": 0.080, "mw": 124.0, "tb_k": 425.0},
                    ],
                },
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "inline_pseudo",
        {
            "run_name": "PT Flash - inline pseudo",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.55},
                    {"component_id": "PSEUDO_PLUS", "mole_fraction": 0.45},
                ],
                "inline_components": [
                    {
                        "component_id": "PSEUDO_PLUS",
                        "name": "PSEUDO+",
                        "formula": "PSEUDO+",
                        "molecular_weight_g_per_mol": 150.0,
                        "critical_temperature_k": 520.0,
                        "critical_pressure_pa": 3.5e6,
                        "omega": 0.45,
                    }
                ],
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "rounding_drift",
        {
            "run_name": "PT Flash - rounded composition",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.70001},
                    {"component_id": "C10", "mole_fraction": 0.30000},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
    ),
    (
        "standalone_tbp",
        {
            "run_name": "TBP Runtime Contract",
            "calculation_type": "tbp",
            "tbp_config": {
                "cuts": [
                    {"name": "C7", "z": 0.020, "mw": 96.0, "sg": 0.74},
                ]
            },
        },
    ),
    (
        "stability_analysis",
        _stability_config(),
    ),
]

_INVALID_CONFIGS: list[tuple[str, dict[str, Any], str]] = [
    (
        "duplicate_alias_canonical",
        {
            "run_name": "PT Flash - dup",
            "composition": {
                "components": [
                    {"component_id": "C4", "mole_fraction": 0.5},
                    {"component_id": "nC4", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
        "Duplicate component IDs after alias resolution",
    ),
    (
        "tbp_mw_mismatch",
        {
            "run_name": "PT Flash - mw mismatch",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.35},
                    {"component_id": "C2", "mole_fraction": 0.20},
                    {"component_id": "C3", "mole_fraction": 0.15},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.30,
                    "mw_plus_g_per_mol": 120.0,
                    "sg_plus_60f": 0.82,
                    "characterization_preset": "manual",
                    "max_carbon_number": 12,
                    "split_method": "pedersen",
                    "split_mw_model": "paraffin",
                    "pedersen_solve_ab_from": "fit_to_tbp",
                    "tbp_cuts": [
                        {"name": "C7", "z": 0.120, "mw": 96.0},
                        {"name": "C8", "z": 0.100, "mw": 110.0},
                        {"name": "C9", "z": 0.080, "mw": 124.0, "tb_k": 425.0},
                    ],
                },
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        },
        "mw_plus_g_per_mol does not match",
    ),
]


@pytest.mark.parametrize(
    "label,config_data",
    _VALID_CONFIGS,
    ids=[c[0] for c in _VALID_CONFIGS],
)
def test_validate_runtime_config_accepts(label: str, config_data: dict) -> None:
    config = RunConfig.model_validate(config_data)
    validate_runtime_config(config)


@pytest.mark.parametrize(
    "label,config_data,match",
    _INVALID_CONFIGS,
    ids=[c[0] for c in _INVALID_CONFIGS],
)
def test_validate_runtime_config_rejects(label: str, config_data: dict, match: str) -> None:
    config = RunConfig.model_validate(config_data)
    with pytest.raises(ValueError, match=match):
        validate_runtime_config(config)


def test_run_config_rejects_missing_composition_for_non_tbp() -> None:
    with pytest.raises(ValueError, match="composition is required for pt_flash calculation"):
        RunConfig.model_validate(
            {
                "run_name": "PT Flash - no composition",
                "calculation_type": "pt_flash",
                "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
            }
        )


def test_run_config_rejects_tbp_with_legacy_composition_payload() -> None:
    with pytest.raises(
        ValueError,
        match="TBP calculation uses tbp_config only and must not also define composition",
    ):
        RunConfig.model_validate(
            {
                "run_name": "TBP - mixed payload",
                "calculation_type": "tbp",
                "composition": {
                    "components": [{"component_id": "C1", "mole_fraction": 1.0}]
                },
                "tbp_config": {"cuts": [{"name": "C7", "z": 0.020, "mw": 96.0}]},
            }
        )


# ===================================================================
# 2. test_run_calculation_all_workflows
# ===================================================================

_WORKFLOW_CASES: list[tuple[str, dict[str, Any]]] = [
    ("pt_flash", {
        "run_name": "PT Flash",
        "composition": {
            "components": [
                {"component_id": "C1", "mole_fraction": 0.5},
                {"component_id": "C10", "mole_fraction": 0.5},
            ]
        },
        "calculation_type": "pt_flash",
        "eos_type": "peng_robinson",
        "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
    }),
    ("bubble_point", _bubble_point_config()),
    ("dew_point", _dew_point_config()),
    ("cce", _cce_config()),
    ("differential_liberation", _dl_config()),
    ("cvd", _cvd_config()),
    ("separator", _separator_config()),
    ("stability_analysis", _stability_config()),
    ("phase_envelope", _phase_envelope_config()),
]


@pytest.mark.parametrize(
    "calc_type,config_data",
    _WORKFLOW_CASES,
    ids=[c[0] for c in _WORKFLOW_CASES],
)
def test_run_calculation_all_workflows(calc_type: str, config_data: dict) -> None:
    config = RunConfig.model_validate(config_data)
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None

    if calc_type == "pt_flash":
        assert result.pt_flash_result is not None
    elif calc_type == "bubble_point":
        assert result.bubble_point_result is not None
        assert result.bubble_point_result.pressure_pa > 0
        assert result.bubble_point_result.diagnostics is not None
        assert result.bubble_point_result.diagnostics.status == ConvergenceStatusEnum.CONVERGED
        assert result.bubble_point_result.certificate is not None
    elif calc_type == "dew_point":
        assert result.dew_point_result is not None
        assert result.dew_point_result.pressure_pa > 0
        assert result.dew_point_result.diagnostics is not None
        assert result.dew_point_result.diagnostics.status == ConvergenceStatusEnum.CONVERGED
        assert result.dew_point_result.certificate is not None
    elif calc_type == "cce":
        assert result.cce_result is not None
        cce = result.cce_result
        assert len(cce.steps) == 8
        pressures = [step.pressure_pa for step in cce.steps]
        assert all(pressures[i] >= pressures[i + 1] for i in range(len(pressures) - 1))
        assert all(step.relative_volume > 0 for step in cce.steps)
        assert all(
            step.liquid_viscosity_pa_s is not None or step.vapor_viscosity_pa_s is not None
            for step in cce.steps
        )
    elif calc_type == "differential_liberation":
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
    elif calc_type == "cvd":
        assert result.cvd_result is not None
        assert result.cvd_result.converged is True
        assert len(result.cvd_result.steps) > 0
        assert all(
            step.liquid_viscosity_pa_s is not None or step.vapor_viscosity_pa_s is not None
            for step in result.cvd_result.steps
        )
    elif calc_type == "separator":
        assert result.separator_result is not None
        assert result.separator_result.bo > 0
        assert result.separator_result.stock_tank_oil_mw_g_per_mol is not None
        assert result.separator_result.stock_tank_oil_specific_gravity is not None
        assert result.separator_result.total_gas_moles is not None
        assert result.separator_result.shrinkage is not None
        assert len(result.separator_result.stages) >= 2
    elif calc_type == "stability_analysis":
        assert result.stability_analysis_result is not None
        stability = result.stability_analysis_result
        assert stability.stable is False
        assert math.isfinite(stability.tpd_min)
        assert stability.tpd_min < 0.0
    elif calc_type == "phase_envelope":
        assert result.phase_envelope_result is not None
        assert len(result.phase_envelope_result.bubble_curve) > 0
        assert len(result.phase_envelope_result.dew_curve) > 0


def test_bubble_point_surfaces_degenerate_boundary_failure() -> None:
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
            "bubble_point_config": {"temperature_k": 573.15},
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.FAILED
    assert result.bubble_point_result is None
    assert result.error_message is not None
    assert "degenerate trivial stability solution" in result.error_message


def test_phase_envelope_no_saturation_range_fails_hard() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Phase Envelope - no saturation",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.50},
                    {"component_id": "C10", "mole_fraction": 0.50},
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 790.0,
                "temperature_max_k": 800.0,
                "n_points": 20,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.FAILED
    assert result.phase_envelope_result is None
    assert result.error_message is not None
    msg = result.error_message.lower()
    assert "phase envelope failed" in msg
    assert "suggestions:" in msg
    assert "widen the temperature range" in msg


# ===================================================================
# 3. test_plus_fraction_auto_characterization
# ===================================================================

def test_plus_fraction_auto_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Bubble Point - auto plus fraction solve",
            "composition": _oil_plus_fraction_composition_payload(),
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 360.0,
                "pressure_initial_pa": 1.0e5,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.bubble_point_result is not None
    assert result.bubble_point_result.pressure_pa == pytest.approx(11466642.931388617, abs=3.0e4)
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )
    runtime = result.runtime_characterization
    assert runtime is not None
    assert runtime.runtime_component_basis == "lumped"
    assert runtime.lumping_method == "whitson"
    assert runtime.lump_distribution
    assert runtime.delumping_basis == "feed_scn_distribution"
    first_lump_id = runtime.lump_distribution[0].component_id
    assert first_lump_id in result.bubble_point_result.vapor_composition
    assert result.bubble_point_result.reported_component_basis == "delumped_scn"
    assert result.bubble_point_result.reported_vapor_composition is not None
    assert "SCN7" in result.bubble_point_result.reported_vapor_composition
    assert first_lump_id not in result.bubble_point_result.reported_vapor_composition


# ===================================================================
# 4. test_phase_envelope_tracers
# ===================================================================

@pytest.mark.parametrize("tracing_method", ["continuation", "fixed_grid"])
def test_phase_envelope_tracers(tracing_method: str) -> None:
    config = RunConfig.model_validate(
        {
            "run_name": f"Phase Envelope - {tracing_method}",
            "composition": {
                "components": [
                    {"component_id": "C2", "mole_fraction": 0.5},
                    {"component_id": "C3", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 325.0,
                "temperature_max_k": 340.0,
                "n_points": 10,
                "tracing_method": tracing_method,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.phase_envelope_result is not None

    envelope = result.phase_envelope_result
    expected = (
        PhaseEnvelopeTracingMethod.CONTINUATION
        if tracing_method == "continuation"
        else PhaseEnvelopeTracingMethod.FIXED_GRID
    )
    assert envelope.tracing_method is expected

    if tracing_method == "continuation":
        # The continuation path now routes through the fast Newton tracer
        # (``calculate_phase_envelope_fast``) and H-K critical-point detection,
        # so continuation-specific handoff/termination metadata is no longer
        # produced and a thermodynamically-certified critical point is expected.
        assert envelope.continuation_switched is None
        assert envelope.critical_point is not None
        assert envelope.critical_source == "heidemann_khalil"
        assert len(envelope.bubble_curve) >= 2
        assert len(envelope.dew_curve) >= 3


@pytest.mark.parametrize(
    ("config_data", "expected_family"),
    [
        (
            {
                "run_name": "Dry gas baseline",
                "composition": {
                    "components": [
                        {"component_id": "N2", "mole_fraction": 0.01},
                        {"component_id": "CO2", "mole_fraction": 0.02},
                        {"component_id": "C1", "mole_fraction": 0.82},
                        {"component_id": "C2", "mole_fraction": 0.08},
                        {"component_id": "C3", "mole_fraction": 0.04},
                        {"component_id": "C4", "mole_fraction": 0.03},
                    ],
                },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 200.0,
                    "temperature_max_k": 360.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "dry_gas",
        ),
        (
            {
                "run_name": "Light condensate baseline",
                "composition": {
                    "components": [
                        {"component_id": "CO2", "mole_fraction": 0.02},
                        {"component_id": "C1", "mole_fraction": 0.71},
                        {"component_id": "C2", "mole_fraction": 0.09},
                        {"component_id": "C3", "mole_fraction": 0.06},
                        {"component_id": "C4", "mole_fraction": 0.03},
                        {"component_id": "C5", "mole_fraction": 0.03},
                        {"component_id": "C6", "mole_fraction": 0.02},
                        {"component_id": "C7", "mole_fraction": 0.04},
                    ],
                },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 240.0,
                    "temperature_max_k": 420.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "gas_condensate_light",
        ),
        (
            {
                "run_name": "Heavy condensate baseline",
                "composition": {
                    "components": [
                        {"component_id": "CO2", "mole_fraction": 0.02},
                        {"component_id": "C1", "mole_fraction": 0.62},
                        {"component_id": "C2", "mole_fraction": 0.10},
                        {"component_id": "C3", "mole_fraction": 0.08},
                        {"component_id": "C4", "mole_fraction": 0.05},
                        {"component_id": "C5", "mole_fraction": 0.04},
                    ],
                    "plus_fraction": {
                        "label": "C7+",
                        "z_plus": 0.09,
                        "mw_plus_g_per_mol": 165.0,
                        "sg_plus_60f": 0.78,
                        "characterization_preset": "auto",
                    },
                },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 240.0,
                    "temperature_max_k": 440.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "gas_condensate_heavy",
        ),
    ],
    ids=["dry_gas", "gas_condensate_light", "gas_condensate_heavy"],
)
def test_phase_envelope_runtime_family(config_data: dict, expected_family: str) -> None:
    config = RunConfig.model_validate(config_data)
    assert _infer_phase_envelope_runtime_family(config) == expected_family


# ===================================================================
# 5. test_phase_envelope_result_structure
# ===================================================================

def test_phase_envelope_result_structure() -> None:
    result = PhaseEnvelopeResult(
        bubble_curve=[
            PhaseEnvelopePoint(temperature_k=250.0, pressure_pa=2.0e6, point_type="bubble"),
            PhaseEnvelopePoint(temperature_k=300.0, pressure_pa=7.0e6, point_type="bubble"),
        ],
        dew_curve=[
            PhaseEnvelopePoint(temperature_k=180.0, pressure_pa=1.0e5, point_type="dew"),
            PhaseEnvelopePoint(temperature_k=240.0, pressure_pa=1.2e6, point_type="dew"),
            PhaseEnvelopePoint(temperature_k=320.0, pressure_pa=6.5e6, point_type="dew"),
        ],
    )

    ordered = result.continuous_curve_points()
    assert [p.point_type for p in ordered] == ["bubble", "bubble", "dew", "dew", "dew"]
    assert [p.temperature_k for p in ordered] == [250.0, 300.0, 320.0, 240.0, 180.0]

    payload = result.continuous_curve_payload()
    assert [p["point_type"] for p in payload] == ["bubble", "bubble", "dew", "dew", "dew"]
    assert [p["temperature_k"] for p in payload] == [250.0, 300.0, 320.0, 240.0, 180.0]


# ===================================================================
# 6. test_stability_analysis_runtime
# ===================================================================

def test_stability_analysis_runtime() -> None:
    config = RunConfig.model_validate(_stability_config())
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None
    assert result.stability_analysis_result is not None

    stability = result.stability_analysis_result
    assert stability.stable is False
    assert stability.best_unstable_trial_kind is not None
    assert math.isfinite(stability.tpd_min)
    assert stability.tpd_min < 0.0
    assert stability.phase_regime == "two_phase"
    assert stability.physical_state_hint == "two_phase"
    assert stability.physical_state_hint_basis == "two_phase_regime"
    assert stability.physical_state_hint_confidence == "high"
    assert stability.requested_feed_phase.value == "liquid"
    assert stability.reference_root_used == "liquid"
    assert set(stability.feed_composition) == {"C1", "C10"}

    assert stability.vapor_like_trial is not None
    assert stability.liquid_like_trial is not None

    for trial in (stability.vapor_like_trial, stability.liquid_like_trial):
        assert math.isfinite(trial.tpd)
        assert trial.seed_attempts >= 1
        assert trial.candidate_seed_count >= trial.seed_attempts
        assert trial.n_phi_calls == sum(seed.n_phi_calls for seed in trial.seed_results)
        assert trial.n_eos_failures == sum(seed.n_eos_failures for seed in trial.seed_results)
        assert trial.total_iterations == sum(seed.iterations for seed in trial.seed_results)
        assert trial.best_seed.seed_index == trial.best_seed_index
        assert trial.best_seed.seed_label in trial.candidate_seed_labels


def test_stability_supercritical_ambiguous() -> None:
    result = run_calculation(
        config=RunConfig.model_validate(
            {
                "run_name": "Stability Analysis Ambiguous Single Phase",
                "composition": {
                    "components": [{"component_id": "C1", "mole_fraction": 1.0}]
                },
                "calculation_type": "stability_analysis",
                "eos_type": "peng_robinson",
                "stability_analysis_config": {
                    "pressure_pa": 1.0e7,
                    "temperature_k": 320.0,
                    "feed_phase": "auto",
                },
            }
        ),
        write_artifacts=False,
    )

    assert result.status == RunStatus.COMPLETED
    assert result.stability_analysis_result is not None
    stability = result.stability_analysis_result
    assert stability.stable is True
    assert stability.phase_regime == "single_phase"
    assert stability.physical_state_hint == "single_phase_ambiguous"
    assert stability.physical_state_hint_basis == "supercritical_guard"
    assert stability.physical_state_hint_confidence == "low"
    assert stability.liquid_root_z is not None
    assert stability.vapor_root_z is not None
    assert stability.root_gap is not None
    assert abs(stability.root_gap) < 1.0e-12
    assert stability.average_reduced_pressure is not None


def test_stability_result_accepts_legacy_reference_phase_field() -> None:
    result = StabilityAnalysisResult.model_validate(
        {
            "stable": True,
            "tpd_min": 0.0,
            "pressure_pa": 1.0e5,
            "temperature_k": 300.0,
            "requested_feed_phase": "auto",
            "resolved_feed_phase": "auto_selected:vapor",
            "resolved_reference_phase": "vapor",
            "feed_composition": {"C1": 1.0},
        }
    )

    assert result.reference_root_used == "vapor"
    assert result.resolved_reference_phase == "vapor"
    assert result.phase_regime == "single_phase"
    assert result.physical_state_hint == "single_phase_ambiguous"
    assert result.physical_state_hint_basis == "heuristic_fallback"
    assert result.physical_state_hint_confidence == "low"


# ===================================================================
# 7. test_rerun_saved_run
# ===================================================================

def test_rerun_saved_run(tmp_path: Path) -> None:
    config = RunConfig.model_validate(
        {
            "run_id": "seed-run",
            "run_name": "PT Flash seed",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {"pressure_pa": 5.0e6, "temperature_k": 350.0},
        }
    )

    seed_result = run_calculation(config=config, output_dir=tmp_path, write_artifacts=True)
    seed_run_dir = next(p for p in tmp_path.iterdir() if p.is_dir())

    loaded = load_run_config(seed_run_dir)
    assert loaded is not None
    assert loaded.model_dump(mode="json") == seed_result.config.model_dump(mode="json")

    rerun_config = build_rerun_config(config, run_name="PT Flash rerun")
    assert rerun_config.run_id is None
    assert rerun_config.run_name == "PT Flash rerun"

    rerun_result = rerun_saved_run(
        seed_run_dir,
        output_dir=tmp_path,
        write_artifacts=True,
        run_name="PT Flash rerun",
    )

    run_dirs = sorted(p for p in tmp_path.iterdir() if p.is_dir())
    assert len(run_dirs) == 2
    assert seed_result.status == RunStatus.COMPLETED
    assert rerun_result.status == RunStatus.COMPLETED
    assert rerun_result.run_id != seed_result.run_id
    assert rerun_result.run_name == "PT Flash rerun"
    assert rerun_result.pt_flash_result is not None
    assert seed_result.pt_flash_result is not None
    assert rerun_result.pt_flash_result.phase == seed_result.pt_flash_result.phase
    assert rerun_result.pt_flash_result.vapor_fraction == seed_result.pt_flash_result.vapor_fraction


# ===================================================================
# 8. test_cancel_calculation
# ===================================================================

def test_cancel_calculation(tmp_path: Path) -> None:
    config = _pt_flash_config()
    callback = _CancelAfterDispatchCallback()

    result = run_calculation(
        config=config,
        output_dir=tmp_path,
        callback=callback,
        write_artifacts=True,
    )

    assert result.status == RunStatus.CANCELLED
    assert result.error_message == "Calculation was cancelled by user"
    assert result.pt_flash_result is None
    assert callback.cancelled_run_id == result.run_id

    run_dirs = sorted(tmp_path.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    with (run_dir / "manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    with (run_dir / "results.json").open("r", encoding="utf-8") as handle:
        stored_result = json.load(handle)

    assert manifest["status"] == RunStatus.CANCELLED.value
    assert stored_result["status"] == RunStatus.CANCELLED.value
    assert stored_result["pt_flash_result"] is None


@pytest.mark.parametrize("tracing_method", ["continuation", "fixed_grid"])
def test_cancel_mid_phase_envelope(tracing_method: str) -> None:
    config = RunConfig.model_validate(
        {
            "run_name": f"Phase Envelope - cancel {tracing_method}",
            "composition": {
                "components": [
                    {"component_id": "C2", "mole_fraction": 0.5},
                    {"component_id": "C3", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 325.0,
                "temperature_max_k": 340.0,
                "n_points": 10,
                "tracing_method": tracing_method,
            },
        }
    )
    callback = _CancelAfterNChecksCallback(cancel_after_checks=6)

    result = run_calculation(config=config, callback=callback, write_artifacts=False)

    assert result.status == RunStatus.CANCELLED
    assert result.phase_envelope_result is None
    assert result.error_message == "Calculation was cancelled by user"
    assert callback.cancelled_run_id == result.run_id
    assert callback.check_count >= callback.cancel_after_checks


def test_calculation_thread_preserves_cancel_before_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("PySide6")
    from pvtapp.workers import CalculationThread, CalculationWorker

    observed: dict[str, bool] = {}

    def fake_run(self: CalculationWorker) -> None:
        observed["cancelled"] = self._cancelled

    monkeypatch.setattr(CalculationWorker, "run", fake_run)

    thread = CalculationThread(config=_pt_flash_config())
    thread.cancel()
    thread.run()

    assert observed["cancelled"] is True


# ===================================================================
# 9. test_progress_callback
# ===================================================================

def test_progress_callback() -> None:
    class _ProgressRecorder(ProgressCallback):
        def __init__(self) -> None:
            self.events: list[tuple[str, float, str]] = []
            self.completed_run_id: str | None = None

        def on_progress(self, run_id: str, progress: float, message: str) -> None:
            self.events.append((run_id, progress, message))

        def on_completed(self, run_id: str, result: Any = None) -> None:
            self.completed_run_id = run_id

        def is_cancelled(self) -> bool:
            return False

    recorder = _ProgressRecorder()
    config = _pt_flash_config()

    result = run_calculation(config=config, callback=recorder, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert len(recorder.events) > 0
    assert recorder.completed_run_id == result.run_id
    progress_values = [e[1] for e in recorder.events]
    assert progress_values[-1] >= 0.5


# ===================================================================
# 10. test_assignment_preset
# ===================================================================

def test_assignment_preset() -> None:
    preset = build_assignment_desktop_preset(initials="TANS")
    case = load_assignment_case()
    _component_ids, components, composition = build_assignment_fluid(case)
    reference = calculate_bubble_point(
        preset.temperature_k,
        composition,
        components,
        PR78EOS(components),
    )

    assert preset.eos_type is EOSType.PR78
    assert preset.selected_initials == "TANS"
    assert preset.temperature_f == pytest.approx(125.0)
    assert preset.temperature_k > 0.0
    assert sum(e.mole_fraction for e in preset.composition.components) == pytest.approx(1.00001)
    assert [e.component_id for e in preset.composition.components][-1] == "PSEUDO_PLUS"
    assert len(preset.composition.inline_components) == 1
    assert preset.cce_config.pressure_points_pa == pytest.approx(
        [psia_to_pa(1500.0), psia_to_pa(1250.0), psia_to_pa(1000.0)]
    )
    assert preset.dl_config.pressure_points_pa == pytest.approx(
        [psia_to_pa(500.0), psia_to_pa(300.0), psia_to_pa(100.0)]
    )
    assert preset.bubble_pressure_pa == pytest.approx(float(reference.pressure))
    assert preset.bubble_point_config.pressure_initial_pa == pytest.approx(preset.bubble_pressure_pa)
    assert preset.dl_config.bubble_pressure_pa == pytest.approx(preset.bubble_pressure_pa)
    assert preset.dl_config.bubble_pressure_pa > max(preset.dl_config.pressure_points_pa)


# ===================================================================
# 11. test_pt_flash_result_properties
# ===================================================================

def test_pt_flash_result_properties() -> None:
    result = run_calculation(_pt_flash_config(), write_artifacts=False)
    assert result.status == RunStatus.COMPLETED
    flash = result.pt_flash_result
    assert flash is not None
    assert flash.phase == "two-phase"

    assert flash.liquid_density_kg_per_m3 is not None
    assert flash.vapor_density_kg_per_m3 is not None
    assert flash.liquid_density_kg_per_m3 > flash.vapor_density_kg_per_m3 > 0.0

    assert flash.liquid_viscosity_pa_s is not None
    assert flash.vapor_viscosity_pa_s is not None
    assert flash.liquid_viscosity_pa_s > flash.vapor_viscosity_pa_s > 0.0

    assert flash.liquid_viscosity_cp is not None
    assert flash.vapor_viscosity_cp is not None
    assert flash.liquid_viscosity_cp == pytest.approx(flash.liquid_viscosity_pa_s * 1000.0)
    assert flash.vapor_viscosity_cp == pytest.approx(flash.vapor_viscosity_pa_s * 1000.0)

    assert flash.interfacial_tension_n_per_m is not None
    assert flash.interfacial_tension_n_per_m > 0.0
    assert flash.interfacial_tension_mn_per_m is not None
    assert flash.interfacial_tension_mn_per_m == pytest.approx(
        flash.interfacial_tension_n_per_m * 1000.0
    )

    result_model = PTFlashResult(
        converged=True,
        phase="two-phase",
        vapor_fraction=0.35,
        liquid_composition={"C1": 0.25, "LUMP1_C7_C9": 0.75},
        vapor_composition={"C1": 0.92, "LUMP1_C7_C9": 0.08},
        K_values={"C1": 3.68, "LUMP1_C7_C9": 0.11},
        liquid_fugacity={"C1": 1.0, "LUMP1_C7_C9": 2.0},
        vapor_fugacity={"C1": 1.1, "LUMP1_C7_C9": 2.1},
        reported_component_basis="delumped_scn",
        reported_liquid_composition={"C1": 0.25, "SCN7": 0.35, "SCN8": 0.40},
        reported_vapor_composition={"C1": 0.92, "SCN7": 0.05, "SCN8": 0.03},
        reported_k_values={"C1": 3.68, "SCN7": 0.16, "SCN8": 0.08},
        diagnostics=SolverDiagnostics(
            status=ConvergenceStatusEnum.CONVERGED,
            iterations=4,
            final_residual=1.0e-12,
        ),
    )

    assert result_model.has_reported_thermodynamic_surface is False
    assert result_model.display_liquid_composition == result_model.liquid_composition
    assert "LUMP1_C7_C9" in result_model.display_liquid_composition

    full_model = PTFlashResult(
        converged=True,
        phase="two-phase",
        vapor_fraction=0.35,
        liquid_composition={"C1": 0.25, "LUMP1_C7_C9": 0.75},
        vapor_composition={"C1": 0.92, "LUMP1_C7_C9": 0.08},
        K_values={"C1": 3.68, "LUMP1_C7_C9": 0.11},
        liquid_fugacity={"C1": 1.0, "LUMP1_C7_C9": 2.0},
        vapor_fugacity={"C1": 1.1, "LUMP1_C7_C9": 2.1},
        reported_surface_status="available",
        reported_component_basis="reconstructed_scn",
        reported_liquid_composition={"C1": 0.25, "SCN7": 0.35, "SCN8": 0.40},
        reported_vapor_composition={"C1": 0.92, "SCN7": 0.05, "SCN8": 0.03},
        reported_k_values={"C1": 3.68, "SCN7": 0.16, "SCN8": 0.08},
        reported_liquid_fugacity={"C1": 1.0, "SCN7": 1.8, "SCN8": 1.9},
        reported_vapor_fugacity={"C1": 1.1, "SCN7": 1.2, "SCN8": 1.3},
        diagnostics=SolverDiagnostics(
            status=ConvergenceStatusEnum.CONVERGED,
            iterations=4,
            final_residual=1.0e-12,
        ),
    )

    assert full_model.has_reported_thermodynamic_surface is True
    assert full_model.display_liquid_composition == full_model.reported_liquid_composition
    assert "SCN7" in full_model.display_liquid_composition


# ===================================================================
# 12. test_prepare_fluid_inputs
# ===================================================================

def test_prepare_fluid_inputs() -> None:
    prepared_pf = _prepare_fluid_inputs(_bubble_point_plus_fraction_config())

    assert prepared_pf.characterization_result is not None
    assert prepared_pf.runtime_characterization is not None
    assert prepared_pf.characterization_result.component_ids == prepared_pf.component_ids
    assert prepared_pf.runtime_characterization.runtime_component_ids == prepared_pf.component_ids
    assert prepared_pf.runtime_characterization.runtime_component_basis == "lumped"
    assert prepared_pf.detailed_reconstruction is not None
    assert prepared_pf.detailed_reconstruction_unavailable_reason is None
    assert prepared_pf.detailed_reconstruction.component_basis == "light_ends_plus_scn"
    assert prepared_pf.detailed_reconstruction.components[0].component_id == "N2"
    assert any(e.component_id == "SCN7" for e in prepared_pf.detailed_reconstruction.components)
    assert len(prepared_pf.detailed_reconstruction.components) > len(prepared_pf.component_ids)
    assert len(prepared_pf.detailed_reconstruction.binary_interaction_matrix) == len(
        prepared_pf.detailed_reconstruction.components
    )

    prepared_simple = _prepare_fluid_inputs(_pt_flash_config())

    assert prepared_simple.characterization_result is None
    assert prepared_simple.runtime_characterization is None
    assert prepared_simple.detailed_reconstruction is None
    assert prepared_simple.detailed_reconstruction_unavailable_reason is None


def test_prepare_fluid_inputs_bip_provenance() -> None:
    config = _bubble_point_plus_fraction_config().model_copy(
        update={"binary_interaction": {"C1-C7+": 0.0125}}
    )

    prepared = _prepare_fluid_inputs(config)

    assert prepared.detailed_reconstruction is not None
    reconstruction = prepared.detailed_reconstruction
    component_ids = [entry.component_id for entry in reconstruction.components]
    c1_index = component_ids.index("C1")
    scn_indices = [
        index
        for index, cid in enumerate(component_ids)
        if cid.startswith("SCN")
    ]

    assert reconstruction.component_basis == "light_ends_plus_scn"
    assert reconstruction.bip_provenance.default_kij == pytest.approx(0.0)
    assert "C1-C7+" in reconstruction.bip_provenance.override_pairs
    assert scn_indices
    for scn_index in scn_indices:
        assert reconstruction.binary_interaction_matrix[c1_index][scn_index] == pytest.approx(0.0125)
        assert reconstruction.binary_interaction_matrix[scn_index][c1_index] == pytest.approx(0.0125)


def test_run_calculation_reuses_prepared_fluid_context(monkeypatch) -> None:
    import pvtcore.characterization as characterization

    original = characterization.characterize_fluid
    calls = 0

    def wrapped(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(characterization, "characterize_fluid", wrapped)

    result = run_calculation(config=_bubble_point_plus_fraction_config(), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert calls == 1
