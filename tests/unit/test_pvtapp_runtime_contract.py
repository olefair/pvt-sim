"""Runtime contract tests for pvtapp calculation dispatch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pvtapp.job_runner import (
    ProgressCallback,
    _prepare_fluid_inputs,
    build_rerun_config,
    load_run_config,
    load_run_result,
    rerun_saved_run,
    run_calculation,
    validate_runtime_config,
)
from pvtapp.schemas import (
    ConvergenceStatusEnum,
    PTFlashResult,
    RunConfig,
    RunStatus,
    SolverDiagnostics,
)


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


def _swelling_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "Swelling Runtime Contract",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.40},
                    {"component_id": "C4", "mole_fraction": 0.30},
                    {"component_id": "C10", "mole_fraction": 0.30},
                ]
            },
            "calculation_type": "swelling_test",
            "eos_type": "peng_robinson",
            "swelling_test_config": {
                "temperature_k": 350.0,
                "enrichment_steps_mol_per_mol_oil": [0.05, 0.10, 0.20, 0.35],
                "pressure_unit": "bar",
                "temperature_unit": "C",
                "injection_gas_composition": {
                    "components": [
                        {"component_id": "C1", "mole_fraction": 0.85},
                        {"component_id": "CO2", "mole_fraction": 0.15},
                    ]
                },
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


def _pt_flash_plus_fraction_tbp_fit_config() -> RunConfig:
    return RunConfig.model_validate(
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
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
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


def _co2_rich_gas_plus_fraction_composition_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.00816326530612245},
            {"component_id": "CO2", "mole_fraction": 0.46938775510204084},
            {"component_id": "H2S", "mole_fraction": 0.010204081632653062},
            {"component_id": "C1", "mole_fraction": 0.29591836734693877},
            {"component_id": "C2", "mole_fraction": 0.07142857142857144},
            {"component_id": "C3", "mole_fraction": 0.04591836734693878},
            {"component_id": "iC4", "mole_fraction": 0.020408163265306124},
            {"component_id": "C4", "mole_fraction": 0.01836734693877551},
            {"component_id": "iC5", "mole_fraction": 0.012244897959183675},
            {"component_id": "C5", "mole_fraction": 0.012244897959183675},
            {"component_id": "C6", "mole_fraction": 0.011224489795918367},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.024489795918367346,
            "mw_plus_g_per_mol": 115.39738333333332,
            "sg_plus_60f": 0.7436666666666666,
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


def test_validate_runtime_config_accepts_peng_robinson() -> None:
    config = _pt_flash_config()

    validate_runtime_config(config)


def test_validate_runtime_config_accepts_swelling_test() -> None:
    validate_runtime_config(_swelling_config())


def test_run_config_rejects_swelling_oil_plus_fraction_surface() -> None:
    with pytest.raises(ValueError, match="composition.plus_fraction is not supported for swelling_test"):
        RunConfig.model_validate(
            {
                **_swelling_config().model_dump(mode="json"),
                "composition": {
                    "components": [
                        {"component_id": "C1", "mole_fraction": 0.40},
                        {"component_id": "C4", "mole_fraction": 0.30},
                    ],
                    "plus_fraction": {
                        "label": "C7+",
                        "cut_start": 7,
                        "z_plus": 0.30,
                        "mw_plus_g_per_mol": 150.0,
                        "sg_plus_60f": 0.82,
                    },
                },
            }
        )


def test_run_config_rejects_swelling_injection_gas_plus_fraction_surface() -> None:
    with pytest.raises(
        ValueError,
        match="swelling_test_config.injection_gas_composition must not define plus_fraction",
    ):
        RunConfig.model_validate(
            {
                **_swelling_config().model_dump(mode="json"),
                "swelling_test_config": {
                    **_swelling_config().swelling_test_config.model_dump(mode="json"),
                    "injection_gas_composition": {
                        "components": [
                            {"component_id": "C1", "mole_fraction": 0.85},
                        ],
                        "plus_fraction": {
                            "label": "C7+",
                            "cut_start": 7,
                            "z_plus": 0.15,
                            "mw_plus_g_per_mol": 130.0,
                            "sg_plus_60f": 0.78,
                        },
                    },
                },
            }
        )


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


def test_run_calculation_executes_swelling_with_union_component_basis() -> None:
    result = run_calculation(config=_swelling_config(), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.swelling_test_result is not None
    assert result.error_message is None
    assert result.swelling_test_result.fully_certified is True
    assert result.swelling_test_result.overall_status == "complete"
    assert len(result.swelling_test_result.steps) == 5
    assert result.swelling_test_result.enrichment_steps_mol_per_mol_oil == pytest.approx(
        [0.0, 0.05, 0.10, 0.20, 0.35]
    )
    baseline_step = result.swelling_test_result.steps[0]
    enriched_step = result.swelling_test_result.steps[-1]
    assert baseline_step.enriched_feed_composition["CO2"] == pytest.approx(0.0)
    assert enriched_step.enriched_feed_composition["CO2"] > 0.0
    assert enriched_step.incipient_vapor_composition is not None
    assert enriched_step.k_values is not None


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


def test_prepare_fluid_inputs_returns_first_class_runtime_package_for_plus_fraction() -> None:
    prepared = _prepare_fluid_inputs(_bubble_point_plus_fraction_config())

    assert prepared.characterization_result is not None
    assert prepared.runtime_characterization is not None
    assert prepared.characterization_result.component_ids == prepared.component_ids
    assert prepared.runtime_characterization.runtime_component_ids == prepared.component_ids
    assert prepared.runtime_characterization.runtime_component_basis == "lumped"
    assert prepared.detailed_reconstruction is not None
    assert prepared.detailed_reconstruction_unavailable_reason is None
    assert prepared.runtime_characterization.detailed_reconstruction is not None
    assert prepared.runtime_characterization.detailed_reconstruction_unavailable_reason is None
    assert prepared.detailed_reconstruction.component_basis == "light_ends_plus_scn"
    assert prepared.detailed_reconstruction.components[0].component_id == "N2"
    assert any(entry.component_id == "SCN7" for entry in prepared.detailed_reconstruction.components)
    assert len(prepared.detailed_reconstruction.components) > len(prepared.component_ids)
    assert len(prepared.detailed_reconstruction.binary_interaction_matrix) == len(
        prepared.detailed_reconstruction.components
    )
    assert all(
        len(row) == len(prepared.detailed_reconstruction.components)
        for row in prepared.detailed_reconstruction.binary_interaction_matrix
    )


def test_prepare_fluid_inputs_omits_detailed_reconstruction_without_plus_fraction() -> None:
    prepared = _prepare_fluid_inputs(_pt_flash_config())

    assert prepared.characterization_result is None
    assert prepared.runtime_characterization is None
    assert prepared.detailed_reconstruction is None
    assert prepared.detailed_reconstruction_unavailable_reason is None


def test_prepare_fluid_inputs_preserves_detailed_bip_provenance_for_plus_fraction() -> None:
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
        for index, component_id in enumerate(component_ids)
        if component_id.startswith("SCN")
    ]

    assert reconstruction.component_basis == "light_ends_plus_scn"
    assert reconstruction.bip_provenance.default_kij == pytest.approx(0.0)
    assert "C1-C7+" in reconstruction.bip_provenance.override_pairs
    assert scn_indices
    for scn_index in scn_indices:
        assert reconstruction.binary_interaction_matrix[c1_index][scn_index] == pytest.approx(0.0125)
        assert reconstruction.binary_interaction_matrix[scn_index][c1_index] == pytest.approx(0.0125)


def test_run_calculation_reuses_prepared_fluid_context_for_plus_fraction(monkeypatch) -> None:
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


def test_validate_runtime_config_accepts_pedersen_fit_to_tbp_inputs() -> None:
    config = _pt_flash_plus_fraction_tbp_fit_config()

    validate_runtime_config(config)


def test_validate_runtime_config_rejects_plus_fraction_tbp_mw_mismatch() -> None:
    config = _pt_flash_plus_fraction_tbp_fit_config()
    config = config.model_copy(
        update={
            "composition": config.composition.model_copy(
                update={
                    "plus_fraction": config.composition.plus_fraction.model_copy(
                        update={"mw_plus_g_per_mol": 120.0}
                    )
                }
            )
        }
    )

    with pytest.raises(ValueError, match="mw_plus_g_per_mol does not match"):
        validate_runtime_config(config)


def test_validate_runtime_config_accepts_standalone_tbp_runtime() -> None:
    config = _tbp_config()

    validate_runtime_config(config)


def test_run_config_rejects_missing_composition_for_non_tbp_calculations() -> None:
    with pytest.raises(ValueError, match="composition is required for pt_flash calculation"):
        RunConfig.model_validate(
            {
                "run_name": "PT Flash - no composition",
                "calculation_type": "pt_flash",
                "pt_flash_config": {
                    "pressure_pa": 5.0e6,
                    "temperature_k": 350.0,
                },
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
                    "components": [
                        {"component_id": "C1", "mole_fraction": 1.0},
                    ]
                },
                "tbp_config": {
                    "cuts": [
                        {"name": "C7", "z": 0.020, "mw": 96.0},
                    ]
                },
            }
        )


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
    assert result.runtime_characterization is not None
    _assert_resolved_plus_fraction(
        result.config,
        resolved_preset="volatile_oil",
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_n_groups=6,
    )
    runtime = result.runtime_characterization
    pt_flash_result = result.pt_flash_result
    assert runtime.runtime_component_basis == "lumped"
    assert runtime.lumping_method == "whitson"
    assert pt_flash_result.phase == "two-phase"
    assert pt_flash_result.reported_surface_status == "available"
    assert pt_flash_result.reported_surface_reason is None
    assert pt_flash_result.reported_component_basis == "reconstructed_scn"
    assert pt_flash_result.has_reported_thermodynamic_surface is True
    assert pt_flash_result.reported_liquid_composition is not None
    assert pt_flash_result.reported_vapor_composition is not None
    assert pt_flash_result.reported_k_values is not None
    assert pt_flash_result.reported_liquid_fugacity is not None
    assert pt_flash_result.reported_vapor_fugacity is not None
    first_lump_id = next(
        component_id
        for component_id in runtime.runtime_component_ids
        if component_id.startswith("LUMP")
    )
    assert first_lump_id in pt_flash_result.liquid_composition
    assert first_lump_id not in pt_flash_result.reported_liquid_composition
    assert "SCN7" in pt_flash_result.reported_liquid_composition
    assert "SCN7" in pt_flash_result.reported_vapor_composition
    assert "SCN7" in pt_flash_result.reported_liquid_fugacity
    assert "SCN7" in pt_flash_result.reported_vapor_fugacity
    assert sum(pt_flash_result.reported_liquid_composition.values()) == pytest.approx(1.0, abs=1e-12)
    assert sum(pt_flash_result.reported_vapor_composition.values()) == pytest.approx(1.0, abs=1e-12)
    for component_id, reported_k in pt_flash_result.reported_k_values.items():
        reported_x = pt_flash_result.reported_liquid_composition[component_id]
        reported_y = pt_flash_result.reported_vapor_composition[component_id]
        reported_phi_l = pt_flash_result.reported_liquid_fugacity[component_id]
        reported_phi_v = pt_flash_result.reported_vapor_fugacity[component_id]
        assert reported_k == pytest.approx(reported_phi_l / reported_phi_v, rel=1e-8, abs=1e-10)
        if reported_x > 1.0e-12:
            assert reported_k == pytest.approx(reported_y / reported_x, rel=1e-5, abs=1e-8)


@pytest.mark.parametrize("eos_type", ["peng_robinson", "pr78", "srk"])
def test_run_calculation_executes_plus_fraction_pt_flash_reconstruction_across_supported_eos(
    eos_type: str,
) -> None:
    config = RunConfig.model_validate(
        {
            "run_name": f"PT Flash - plus fraction {eos_type}",
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
            "eos_type": eos_type,
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.pt_flash_result.phase == "two-phase"
    assert result.pt_flash_result.reported_surface_status == "available"
    assert result.pt_flash_result.reported_component_basis == "reconstructed_scn"
    assert result.pt_flash_result.has_reported_thermodynamic_surface is True


def test_run_calculation_withholds_reconstructed_pt_flash_surface_for_single_phase_lumped_runtime() -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - single phase plus fraction policy",
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
                "pressure_pa": 5.0e7,
                "temperature_k": 350.0,
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.runtime_characterization is not None
    assert result.runtime_characterization.runtime_component_basis == "lumped"
    assert result.pt_flash_result.phase == "liquid"
    assert result.pt_flash_result.reported_surface_status == "withheld_single_phase_runtime"
    assert result.pt_flash_result.reported_surface_reason is not None
    assert result.pt_flash_result.reported_component_basis is None
    assert result.pt_flash_result.reported_liquid_composition is None
    assert result.pt_flash_result.reported_vapor_composition is None
    assert result.pt_flash_result.reported_k_values is None
    assert result.pt_flash_result.reported_liquid_fugacity is None
    assert result.pt_flash_result.reported_vapor_fugacity is None
    assert result.pt_flash_result.has_reported_thermodynamic_surface is False


def test_run_calculation_keeps_runtime_pt_flash_when_reconstructed_surface_fails(
    monkeypatch,
) -> None:
    import pvtapp.job_runner as job_runner

    def _boom(**_kwargs):
        raise RuntimeError("reconstruction failed")

    monkeypatch.setattr(job_runner, "_build_reconstructed_pt_flash_reporting", _boom)

    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - reconstruction failure fallback",
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
    assert result.pt_flash_result.phase == "two-phase"
    assert result.pt_flash_result.reported_surface_status == "failed_reconstruction"
    assert result.pt_flash_result.reported_surface_reason is not None
    assert "reconstruction failed" in result.pt_flash_result.reported_surface_reason
    assert result.pt_flash_result.reported_component_basis is None
    assert result.pt_flash_result.has_reported_thermodynamic_surface is False
    assert any(component_id.startswith("LUMP") for component_id in result.pt_flash_result.liquid_composition)


def test_run_calculation_executes_pt_flash_with_pedersen_fit_to_tbp_characterization() -> None:
    config = _pt_flash_plus_fraction_tbp_fit_config()

    result = run_calculation(config, write_artifacts=False)

    assert result.pt_flash_result is not None
    assert result.config.composition.plus_fraction is not None
    assert result.config.composition.plus_fraction.characterization_preset.value == "manual"
    assert result.config.composition.plus_fraction.pedersen_solve_ab_from == "fit_to_tbp"
    assert result.config.composition.plus_fraction.tbp_cuts is not None
    assert len(result.config.composition.plus_fraction.tbp_cuts) == 3
    assert result.runtime_characterization is not None
    runtime = result.runtime_characterization
    assert runtime.source == "plus_fraction_runtime"
    assert runtime.split_method == "pedersen"
    assert runtime.runtime_component_basis == "scn_unlumped"
    assert runtime.pedersen_fit is not None
    assert runtime.pedersen_fit.solve_ab_from == "fit_to_tbp"
    assert runtime.cut_mappings
    assert runtime.cut_mappings[0].cut_name == "C7"
    assert runtime.scn_distribution
    assert runtime.runtime_component_ids[:3] == ["C1", "C2", "C3"]


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


def test_run_calculation_executes_standalone_tbp_runtime() -> None:
    config = _tbp_config()

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None
    assert result.tbp_result is not None
    assert result.config.composition is None
    assert result.tbp_result.cut_start == 7
    assert result.tbp_result.cut_end == 9
    assert result.tbp_result.z_plus == pytest.approx(0.05)
    assert result.tbp_result.mw_plus_g_per_mol == pytest.approx(108.6)
    assert [cut.name for cut in result.tbp_result.cuts] == ["C7", "C8", "C9"]
    assert all(cut.boiling_point_k is not None for cut in result.tbp_result.cuts)
    assert result.tbp_result.characterization_context is not None
    context = result.tbp_result.characterization_context
    assert context.plus_fraction_label == "C7+"
    assert context.bridge_status == "characterized_scn"
    assert context.characterization_method == "pedersen_fit_to_tbp"
    assert context.runtime_component_basis == "scn_unlumped"
    assert context.pedersen_fit is not None
    assert context.pedersen_fit.solve_ab_from == "fit_to_tbp"
    assert context.pedersen_fit.tbp_cut_rms_relative_error is not None
    assert context.scn_distribution
    assert len(context.scn_distribution) == 3
    assert context.scn_distribution[0].component_id == "SCN7"
    assert context.cut_mappings
    assert context.cut_mappings[0].cut_name == "C7"
    assert context.notes
    assert result.runtime_characterization is not None
    runtime = result.runtime_characterization
    assert runtime.source == "tbp_assay"
    assert runtime.runtime_component_basis == "scn_unlumped"
    assert runtime.scn_distribution
    assert len(runtime.scn_distribution) == 3
    assert runtime.cut_mappings
    assert runtime.cut_mappings[0].cut_name == "C7"
    assert runtime.pedersen_fit is not None
    assert runtime.pedersen_fit.solve_ab_from == "fit_to_tbp"
    assert result.pt_flash_result is None
    assert result.cce_result is None


def test_run_calculation_persists_tbp_run_artifacts(tmp_path: Path) -> None:
    config = _tbp_config().model_copy(update={"run_id": "tbpart01"})

    result = run_calculation(config=config, output_dir=tmp_path, write_artifacts=True)

    assert result.status == RunStatus.COMPLETED
    run_dirs = sorted(tmp_path.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    loaded_config = load_run_config(run_dir)
    loaded_result = load_run_result(run_dir)

    assert loaded_config is not None
    assert loaded_result is not None
    assert loaded_config.model_dump(mode="json") == result.config.model_dump(mode="json")
    assert loaded_result.tbp_result is not None
    assert loaded_result.tbp_result.z_plus == pytest.approx(0.05)
    assert loaded_result.tbp_result.cuts[0].boiling_point_k is not None
    assert loaded_result.tbp_result.characterization_context is not None
    assert loaded_result.tbp_result.characterization_context.plus_fraction_label == "C7+"
    assert loaded_result.tbp_result.characterization_context.bridge_status == "characterized_scn"
    assert loaded_result.tbp_result.characterization_context.pedersen_fit is not None
    assert loaded_result.runtime_characterization is not None
    assert loaded_result.runtime_characterization.source == "tbp_assay"
    assert loaded_result.runtime_characterization.scn_distribution


def test_run_calculation_persists_detailed_reconstruction_payload_for_plus_fraction(tmp_path: Path) -> None:
    config = _bubble_point_plus_fraction_config().model_copy(update={"run_id": "pfrecon01"})

    result = run_calculation(config=config, output_dir=tmp_path, write_artifacts=True)

    assert result.status == RunStatus.COMPLETED
    run_dirs = sorted(tmp_path.iterdir())
    assert len(run_dirs) == 1
    loaded_result = load_run_result(run_dirs[0])

    assert loaded_result is not None
    assert loaded_result.runtime_characterization is not None
    reconstruction = loaded_result.runtime_characterization.detailed_reconstruction
    assert reconstruction is not None
    assert reconstruction.component_basis == "light_ends_plus_scn"
    assert any(entry.component_id == "SCN7" for entry in reconstruction.components)
    assert len(reconstruction.components) > len(loaded_result.runtime_characterization.runtime_component_ids)
    assert len(reconstruction.binary_interaction_matrix) == len(reconstruction.components)


def test_run_calculation_persists_reconstructed_pt_flash_surface_artifacts(tmp_path: Path) -> None:
    config = RunConfig.model_validate(
        {
            "run_name": "PT Flash - persisted reconstructed SCN surface",
            "run_id": "ptflashrecon01",
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

    result = run_calculation(config=config, output_dir=tmp_path, write_artifacts=True)

    assert result.status == RunStatus.COMPLETED
    run_dirs = sorted(tmp_path.iterdir())
    assert len(run_dirs) == 1
    loaded_result = load_run_result(run_dirs[0])

    assert loaded_result is not None
    assert loaded_result.pt_flash_result is not None
    assert loaded_result.pt_flash_result.reported_surface_status == "available"
    assert loaded_result.pt_flash_result.reported_component_basis == "reconstructed_scn"
    assert loaded_result.pt_flash_result.reported_liquid_composition is not None
    assert loaded_result.pt_flash_result.reported_liquid_fugacity is not None
    assert "SCN7" in loaded_result.pt_flash_result.reported_liquid_composition
    assert "SCN7" in loaded_result.pt_flash_result.reported_liquid_fugacity


def test_run_calculation_executes_bubble_point_with_plus_fraction_characterization() -> None:
    config = _bubble_point_plus_fraction_config()

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.bubble_point_result is not None
    assert result.error_message is None
    assert result.bubble_point_result.pressure_pa == pytest.approx(11466642.931388617, abs=3.0e4)
    assert result.bubble_point_result.certificate is not None
    assert result.runtime_characterization is not None
    runtime = result.runtime_characterization
    assert runtime.runtime_component_basis == "lumped"
    assert runtime.lumping_method == "whitson"
    assert runtime.lump_distribution
    assert runtime.delumping_basis == "feed_scn_distribution"
    assert runtime.lump_distribution[0].members
    first_lump_id = runtime.lump_distribution[0].component_id
    assert first_lump_id in result.bubble_point_result.vapor_composition
    assert result.bubble_point_result.vapor_composition[first_lump_id] > 0.0
    assert result.bubble_point_result.reported_component_basis == "delumped_scn"
    assert result.bubble_point_result.reported_vapor_composition is not None
    assert result.bubble_point_result.reported_k_values is not None
    assert "SCN7" in result.bubble_point_result.reported_vapor_composition
    assert first_lump_id not in result.bubble_point_result.reported_vapor_composition
    assert sum(result.bubble_point_result.reported_vapor_composition.values()) == pytest.approx(1.0, abs=1e-12)
    assert sum(result.bubble_point_result.reported_k_values.values()) > 0.0
    raw_heavy_total = sum(
        value
        for component_id, value in result.bubble_point_result.vapor_composition.items()
        if component_id.startswith("LUMP")
    )
    reported_heavy_total = sum(
        value
        for component_id, value in result.bubble_point_result.reported_vapor_composition.items()
        if component_id.startswith("SCN")
    )
    assert reported_heavy_total == pytest.approx(raw_heavy_total, abs=1e-12)


def test_run_calculation_executes_dew_point_with_plus_fraction_characterization() -> None:
    config = _dew_point_plus_fraction_config()

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.dew_point_result is not None
    assert result.error_message is None
    assert result.dew_point_result.pressure_pa == pytest.approx(5598.741130684053, abs=25.0)
    assert result.dew_point_result.certificate is not None
    assert result.runtime_characterization is not None
    runtime = result.runtime_characterization
    assert runtime.lumping_method == "whitson"
    assert runtime.lump_distribution
    first_lump_id = runtime.lump_distribution[0].component_id
    assert first_lump_id in result.dew_point_result.liquid_composition
    assert result.dew_point_result.liquid_composition[first_lump_id] > 0.0
    assert result.dew_point_result.reported_component_basis == "delumped_scn"
    assert result.dew_point_result.reported_liquid_composition is not None
    assert result.dew_point_result.reported_k_values is not None
    assert "SCN7" in result.dew_point_result.reported_liquid_composition
    assert first_lump_id not in result.dew_point_result.reported_liquid_composition
    assert sum(result.dew_point_result.reported_liquid_composition.values()) == pytest.approx(1.0, abs=1e-12)
    raw_heavy_total = sum(
        value
        for component_id, value in result.dew_point_result.liquid_composition.items()
        if component_id.startswith("LUMP")
    )
    reported_heavy_total = sum(
        value
        for component_id, value in result.dew_point_result.reported_liquid_composition.items()
        if component_id.startswith("SCN")
    )
    assert reported_heavy_total == pytest.approx(raw_heavy_total, abs=1e-12)


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
    assert result.dew_point_result.pressure_pa == pytest.approx(5598.741130684053, abs=25.0)
    plus_fraction = result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.characterization_preset.value == "auto"
    assert plus_fraction.resolved_characterization_preset.value == "gas_condensate"
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == "paraffin"
    assert plus_fraction.max_carbon_number == 18
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == 2


def test_run_calculation_auto_resolves_pt_flash_co2_rich_plus_fraction_policy() -> None:
    result = run_calculation(
        RunConfig.model_validate(
            {
                "run_name": "PT Flash - auto co2 rich gas policy",
                "composition": _co2_rich_gas_plus_fraction_composition_payload(),
                "calculation_type": "pt_flash",
                "eos_type": "peng_robinson",
                "pt_flash_config": {
                    "pressure_pa": 1.0e5,
                    "temperature_k": 290.0,
                },
            }
        ),
        write_artifacts=False,
    )

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    plus_fraction = result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.characterization_preset.value == "auto"
    assert plus_fraction.resolved_characterization_preset.value == "co2_rich_gas"
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == "paraffin"
    assert plus_fraction.max_carbon_number == 11
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == 4
    assert plus_fraction.lumping_method == "whitson"


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
    assert all(
        step.liquid_viscosity_pa_s is not None or step.vapor_viscosity_pa_s is not None
        for step in result.cce_result.steps
    )
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
    assert all(step.oil_viscosity_pa_s is not None for step in result.dl_result.steps)
    assert any(step.gas_viscosity_pa_s is not None for step in result.dl_result.steps[1:])
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
                "dew_pressure_pa": 5598.741130684053,
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
    assert all(
        step.liquid_viscosity_pa_s is not None or step.vapor_viscosity_pa_s is not None
        for step in result.cvd_result.steps
    )
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
    assert result.pt_flash_result.reported_surface_status is None
    assert result.pt_flash_result.reported_surface_reason is None


def test_run_calculation_executes_pt_flash_for_srk() -> None:
    config = _pt_flash_config(eos_type="srk")

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    assert result.pt_flash_result.reported_surface_status is None
    assert result.pt_flash_result.reported_surface_reason is None


def test_pt_flash_result_keeps_runtime_surface_until_reported_thermodynamics_are_complete() -> None:
    result = PTFlashResult(
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

    assert result.has_reported_thermodynamic_surface is False
    assert result.display_liquid_composition == result.liquid_composition
    assert result.display_vapor_composition == result.vapor_composition
    assert result.display_k_values == result.K_values
    assert result.display_liquid_fugacity == result.liquid_fugacity
    assert result.display_vapor_fugacity == result.vapor_fugacity
    assert "LUMP1_C7_C9" in result.display_liquid_composition
    assert "SCN7" not in result.display_liquid_composition


def test_pt_flash_result_prefers_full_reported_thermodynamic_surface_when_available() -> None:
    result = PTFlashResult(
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

    assert result.has_reported_thermodynamic_surface is True
    assert result.display_liquid_composition == result.reported_liquid_composition
    assert result.display_vapor_composition == result.reported_vapor_composition
    assert result.display_k_values == result.reported_k_values
    assert result.display_liquid_fugacity == result.reported_liquid_fugacity
    assert result.display_vapor_fugacity == result.reported_vapor_fugacity
    assert "SCN7" in result.display_liquid_composition
    assert "LUMP1_C7_C9" not in result.display_liquid_composition


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
