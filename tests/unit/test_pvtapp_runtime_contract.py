"""Runtime contract tests for pvtapp calculation dispatch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pvtapp.job_runner import (
    ProgressCallback,
    build_rerun_config,
    load_run_config,
    rerun_saved_run,
    run_calculation,
    validate_runtime_config,
)
from pvtapp.schemas import RunConfig, RunStatus


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


def _dew_point_plus_fraction_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "Dew Point - plus fraction solve",
            "composition": {
                "components": [
                    {"component_id": "N2", "mole_fraction": 0.0060},
                    {"component_id": "CO2", "mole_fraction": 0.0250},
                    {"component_id": "C1", "mole_fraction": 0.6400},
                    {"component_id": "C2", "mole_fraction": 0.1100},
                    {"component_id": "C3", "mole_fraction": 0.0750},
                    {"component_id": "iC4", "mole_fraction": 0.0250},
                    {"component_id": "C4", "mole_fraction": 0.0250},
                    {"component_id": "iC5", "mole_fraction": 0.0180},
                    {"component_id": "C5", "mole_fraction": 0.0160},
                    {"component_id": "C6", "mole_fraction": 0.0140},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.0460,
                    "mw_plus_g_per_mol": 128.25512173913043,
                    "sg_plus_60f": 0.7571304347826087,
                    "characterization_preset": "manual",
                    "max_carbon_number": 18,
                    "split_mw_model": "paraffin",
                    "lumping_enabled": True,
                    "lumping_n_groups": 2,
                },
            },
            "calculation_type": "dew_point",
            "eos_type": "peng_robinson",
            "dew_point_config": {
                "temperature_k": 320.0,
                "pressure_initial_pa": 1.0e5,
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


def _gas_plus_fraction_composition_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0060},
            {"component_id": "CO2", "mole_fraction": 0.0250},
            {"component_id": "C1", "mole_fraction": 0.6400},
            {"component_id": "C2", "mole_fraction": 0.1100},
            {"component_id": "C3", "mole_fraction": 0.0750},
            {"component_id": "iC4", "mole_fraction": 0.0250},
            {"component_id": "C4", "mole_fraction": 0.0250},
            {"component_id": "iC5", "mole_fraction": 0.0180},
            {"component_id": "C5", "mole_fraction": 0.0160},
            {"component_id": "C6", "mole_fraction": 0.0140},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.0460,
            "mw_plus_g_per_mol": 128.25512173913043,
            "sg_plus_60f": 0.7571304347826087,
        },
    }


def _assert_resolved_plus_fraction(
    config: RunConfig,
    *,
    resolved_preset: str,
    split_method: str,
    split_mw_model: str,
    max_carbon_number: int,
    lumping_n_groups: int,
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


def test_validate_runtime_config_accepts_peng_robinson() -> None:
    config = _pt_flash_config()

    validate_runtime_config(config)


def test_validate_runtime_config_accepts_component_aliases_and_bip_aliases() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - alias contract",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "nC4", "mole_fraction": 0.5},
                ]
            },
            "binary_interaction": {
                "C1-nC4": 0.01,
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    validate_runtime_config(config)


def test_validate_runtime_config_rejects_duplicate_alias_and_canonical_component_ids() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - duplicate alias contract",
            "composition": {
                "components": [
                    {"component_id": "C4", "mole_fraction": 0.5},
                    {"component_id": "nC4", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    with pytest.raises(ValueError, match="Duplicate component IDs after alias resolution"):
        validate_runtime_config(config)


def test_validate_runtime_config_accepts_plus_fraction_characterization_inputs() -> None:
    config = RunConfig.model_validate(
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
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    validate_runtime_config(config)


def test_validate_runtime_config_accepts_inline_pseudo_components() -> None:
    config = RunConfig.model_validate(
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
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    validate_runtime_config(config)


def test_validate_runtime_config_accepts_small_composition_rounding_drift() -> None:
    config = RunConfig.model_validate(
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
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    validate_runtime_config(config)


def test_run_calculation_executes_pt_flash_with_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - plus fraction solve",
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
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )


@pytest.mark.parametrize("split_method", ["katz", "lohrenz"])
def test_run_calculation_executes_pt_flash_with_supported_manual_split_methods(
    split_method: str,
) -> None:
    config = RunConfig.model_validate(
        {
            "run_name": f"PT Flash - {split_method} split",
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
                    "characterization_preset": "manual",
                    "max_carbon_number": 20,
                    "split_method": split_method,
                    "split_mw_model": "table",
                    "lumping_enabled": True,
                    "lumping_n_groups": 6,
                },
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    assert result.config.composition.plus_fraction is not None
    assert result.config.composition.plus_fraction.characterization_preset.value == "manual"
    assert result.config.composition.plus_fraction.split_method == split_method


def test_run_calculation_executes_bubble_point_with_plus_fraction_characterization() -> None:
    config = _bubble_point_plus_fraction_config()

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.bubble_point_result is not None
    assert result.error_message is None
    assert result.bubble_point_result.pressure_pa == pytest.approx(11466642.931388617, abs=3.0e4)
    assert result.bubble_point_result.certificate is not None
    assert "LUMP1_C7_C9" in result.bubble_point_result.vapor_composition
    assert result.bubble_point_result.vapor_composition["LUMP1_C7_C9"] > 0.0


def test_run_calculation_executes_dew_point_with_plus_fraction_characterization() -> None:
    config = _dew_point_plus_fraction_config()

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dew_point_result is not None
    assert result.error_message is None
    assert result.dew_point_result.pressure_pa == pytest.approx(3906.418983182879, abs=25.0)
    assert result.dew_point_result.certificate is not None
    assert "LUMP1_C7_C12" in result.dew_point_result.liquid_composition
    assert result.dew_point_result.liquid_composition["LUMP1_C7_C12"] > 0.0


def test_run_calculation_auto_resolves_bubble_point_plus_fraction_policy() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Bubble Point - auto plus fraction solve",
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

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.bubble_point_result is not None
    assert result.bubble_point_result.pressure_pa == pytest.approx(11466642.931388617, abs=3.0e4)
    plus_fraction = result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.characterization_preset.value == "auto"
    assert plus_fraction.resolved_characterization_preset.value == "volatile_oil"
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == "table"
    assert plus_fraction.max_carbon_number == 20
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == 6


def test_run_calculation_auto_resolves_dew_point_plus_fraction_policy() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Dew Point - auto plus fraction solve",
            "composition": {
                "components": [
                    {"component_id": "N2", "mole_fraction": 0.0060},
                    {"component_id": "CO2", "mole_fraction": 0.0250},
                    {"component_id": "C1", "mole_fraction": 0.6400},
                    {"component_id": "C2", "mole_fraction": 0.1100},
                    {"component_id": "C3", "mole_fraction": 0.0750},
                    {"component_id": "iC4", "mole_fraction": 0.0250},
                    {"component_id": "C4", "mole_fraction": 0.0250},
                    {"component_id": "iC5", "mole_fraction": 0.0180},
                    {"component_id": "C5", "mole_fraction": 0.0160},
                    {"component_id": "C6", "mole_fraction": 0.0140},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.0460,
                    "mw_plus_g_per_mol": 128.25512173913043,
                    "sg_plus_60f": 0.7571304347826087,
                },
            },
            "calculation_type": "dew_point",
            "eos_type": "peng_robinson",
            "dew_point_config": {
                "temperature_k": 320.0,
                "pressure_initial_pa": 1.0e5,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dew_point_result is not None
    assert result.dew_point_result.pressure_pa == pytest.approx(3906.418983182879, abs=25.0)
    plus_fraction = result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.characterization_preset.value == "auto"
    assert plus_fraction.resolved_characterization_preset.value == "gas_condensate"
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == "paraffin"
    assert plus_fraction.max_carbon_number == 18
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == 2


def test_run_calculation_executes_cce_with_auto_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "CCE - auto plus fraction",
            "composition": _oil_plus_fraction_composition_payload(),
            "calculation_type": "cce",
            "eos_type": "peng_robinson",
            "cce_config": {
                "temperature_k": 360.0,
                "pressure_start_pa": 2.0e7,
                "pressure_end_pa": 2.0e6,
                "n_steps": 6,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.cce_result is not None
    assert result.error_message is None
    assert len(result.cce_result.steps) == 6
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )


def test_run_calculation_executes_dl_with_auto_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "DL - auto plus fraction",
            "composition": _oil_plus_fraction_composition_payload(),
            "calculation_type": "differential_liberation",
            "eos_type": "peng_robinson",
            "dl_config": {
                "temperature_k": 360.0,
                "bubble_pressure_pa": 1.1466642931388617e7,
                "pressure_end_pa": 1.0e6,
                "n_steps": 6,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dl_result is not None
    assert result.error_message is None
    assert len(result.dl_result.steps) == 6
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )


def test_run_calculation_executes_cvd_with_auto_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "CVD - auto plus fraction",
            "composition": _gas_plus_fraction_composition_payload(),
            "calculation_type": "cvd",
            "eos_type": "peng_robinson",
            "cvd_config": {
                "temperature_k": 320.0,
                "dew_pressure_pa": 3906.418983182879,
                "pressure_end_pa": 1500.0,
                "n_steps": 5,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.cvd_result is not None
    assert result.error_message is None
    assert len(result.cvd_result.steps) == 5
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="gas_condensate",
        split_method="pedersen",
        split_mw_model="paraffin",
        max_carbon_number=18,
        lumping_n_groups=2,
    )


def test_run_calculation_executes_separator_with_auto_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Separator - auto plus fraction",
            "composition": _oil_plus_fraction_composition_payload(),
            "calculation_type": "separator",
            "eos_type": "peng_robinson",
            "separator_config": {
                "reservoir_pressure_pa": 2.0e7,
                "reservoir_temperature_k": 360.0,
                "include_stock_tank": False,
                "separator_stages": [
                    {"pressure_pa": 3.0e6, "temperature_k": 320.0, "name": "HP"},
                    {"pressure_pa": 5.0e5, "temperature_k": 300.0, "name": "LP"},
                ],
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.separator_result is not None
    assert result.error_message is None
    assert len(result.separator_result.stages) == 2
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )


def test_run_calculation_executes_phase_envelope_with_auto_plus_fraction_characterization() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "Phase Envelope - auto plus fraction",
            "composition": _gas_plus_fraction_composition_payload(),
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 250.0,
                "temperature_max_k": 420.0,
                "n_points": 12,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.phase_envelope_result is not None
    assert result.error_message is None
    assert len(result.phase_envelope_result.bubble_curve) > 0
    assert len(result.phase_envelope_result.dew_curve) > 0
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="gas_condensate",
        split_method="pedersen",
        split_mw_model="paraffin",
        max_carbon_number=18,
        lumping_n_groups=2,
    )


def test_validate_runtime_config_accepts_srk() -> None:
    config = _pt_flash_config(eos_type="srk")

    validate_runtime_config(config)


def test_validate_runtime_config_accepts_pr78() -> None:
    config = _pt_flash_config(eos_type="pr78")

    validate_runtime_config(config)


def test_run_calculation_executes_pt_flash_for_pr78() -> None:
    config = _pt_flash_config(eos_type="pr78")

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None


def test_run_calculation_executes_pt_flash_for_srk() -> None:
    config = _pt_flash_config(eos_type="srk")

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None


class _CancelAfterDispatchCallback(ProgressCallback):
    """Simulate a user cancelling once the runtime reaches the solve boundary."""

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
    """Simulate a user cancelling only after the solver has entered repeated checkpoints."""

    def __init__(self, cancel_after_checks: int) -> None:
        self.cancel_after_checks = cancel_after_checks
        self.check_count = 0
        self.cancelled_run_id: str | None = None

    def on_cancelled(self, run_id: str) -> None:
        self.cancelled_run_id = run_id

    def is_cancelled(self) -> bool:
        self.check_count += 1
        return self.check_count >= self.cancel_after_checks


def test_run_calculation_writes_cancelled_manifest_when_callback_requests_stop(
    tmp_path: Path,
) -> None:
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
    assert manifest["error_message"] == "Calculation was cancelled by user"
    assert stored_result["status"] == RunStatus.CANCELLED.value
    assert stored_result["error_message"] == "Calculation was cancelled by user"
    assert stored_result["pt_flash_result"] is None


@pytest.mark.parametrize("tracing_method", ["continuation", "fixed_grid"])
def test_run_calculation_cancels_mid_phase_envelope_trace(
    tracing_method: str,
) -> None:
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

    result = run_calculation(
        config=config,
        callback=callback,
        write_artifacts=False,
    )

    assert result.status == RunStatus.CANCELLED
    assert result.phase_envelope_result is None
    assert result.error_message == "Calculation was cancelled by user"
    assert callback.cancelled_run_id == result.run_id
    assert callback.check_count >= callback.cancel_after_checks

def test_load_run_config_reads_persisted_config_json(tmp_path: Path) -> None:
    config = _pt_flash_config()
    run_dir = tmp_path / "saved-run"
    run_dir.mkdir()
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config.model_dump(mode="json"), handle, indent=2)

    loaded = load_run_config(run_dir)

    assert loaded is not None
    assert loaded.model_dump(mode="json") == config.model_dump(mode="json")


def test_build_rerun_config_clears_old_run_id_and_preserves_inputs() -> None:
    config = _pt_flash_config().model_copy(update={"run_id": "abcd1234", "run_name": "Saved PT Flash"})

    rerun = build_rerun_config(config)

    assert rerun.run_id is None
    assert rerun.run_name == "Saved PT Flash"
    assert rerun.model_dump(mode="json", exclude={"run_id"}) == config.model_dump(
        mode="json",
        exclude={"run_id"},
    )


def test_rerun_saved_run_reuses_persisted_config_with_fresh_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _pt_flash_config().model_copy(update={"run_id": "original01", "run_name": "Saved PT Flash"})
    run_dir = tmp_path / "saved-run"
    run_dir.mkdir()
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config.model_dump(mode="json"), handle, indent=2)

    observed: dict[str, object] = {}

    def fake_run_calculation(
        config: RunConfig,
        output_dir: Path | None = None,
        callback: ProgressCallback | None = None,
        write_artifacts: bool = True,
    ) -> RunStatus:
        observed["config"] = config
        observed["output_dir"] = output_dir
        observed["callback"] = callback
        observed["write_artifacts"] = write_artifacts
        return RunStatus.COMPLETED

    monkeypatch.setattr("pvtapp.job_runner.run_calculation", fake_run_calculation)

    result = rerun_saved_run(run_dir, output_dir=tmp_path / "reruns", write_artifacts=False, run_name="Replay")

    assert result == RunStatus.COMPLETED
    rerun_config = observed["config"]
    assert isinstance(rerun_config, RunConfig)
    assert rerun_config.run_id is None
    assert rerun_config.run_name == "Replay"
    assert rerun_config.calculation_type == config.calculation_type
    assert rerun_config.composition.model_dump(mode="json") == config.composition.model_dump(mode="json")
    assert observed["write_artifacts"] is False


def test_calculation_thread_preserves_cancel_request_before_worker_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
