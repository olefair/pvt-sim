"""Validation matrix for heavy-end PT-flash runtime and reported surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pvtapp.job_runner import rerun_saved_run, run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from tests.validation.test_plus_fraction_bubble_characterization import (
    PLUS_FRACTION_BUBBLE_CASES,
)
from tests.validation.test_plus_fraction_dew_characterization import (
    PLUS_FRACTION_DEW_CASES,
)


def _normalize_runtime_payload_from_resolved_plus(
    resolved_components: tuple[tuple[str, float], ...],
    *,
    z_plus: float,
    mw_plus_g_per_mol: float,
    sg_plus_60f: float,
) -> dict:
    total = float(sum(z for _, z in resolved_components) + z_plus)
    return {
        "components": [
            {"component_id": component_id, "mole_fraction": z / total}
            for component_id, z in resolved_components
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": z_plus / total,
            "mw_plus_g_per_mol": mw_plus_g_per_mol,
            "sg_plus_60f": sg_plus_60f,
        },
    }


def _normalize_runtime_payload_from_explicit_plus(
    explicit_components: tuple[tuple[str, float], ...],
    *,
    z_plus: float,
    mw_plus_g_per_mol: float,
    sg_plus_60f: float,
) -> dict:
    total = float(sum(z for _, z in explicit_components))
    normalized = [(component_id, z / total) for component_id, z in explicit_components]
    return {
        "components": [
            {"component_id": component_id, "mole_fraction": z}
            for component_id, z in normalized
            if not (
                component_id.upper().startswith("C")
                and component_id[1:].isdigit()
                and int(component_id[1:]) >= 7
            )
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": z_plus,
            "mw_plus_g_per_mol": mw_plus_g_per_mol,
            "sg_plus_60f": sg_plus_60f,
        },
    }


@dataclass(frozen=True)
class HeavyEndPTFlashCase:
    case_id: str
    resolved_preset: str
    composition_payload: dict
    temperature_k: float
    pressure_pa: float
    expected_phase: str
    expected_reported_surface_status: str
    expected_reported_component_basis: str | None
    expected_split_mw_model: str
    expected_max_carbon_number: int
    expected_lumping_n_groups: int


def _bubble_validation_case(
    case_id: str,
    *,
    pressure_factor: float,
    expected_phase: str,
    expected_reported_surface_status: str,
    resolved_preset: str,
) -> HeavyEndPTFlashCase:
    source = next(case for case in PLUS_FRACTION_BUBBLE_CASES if case.case_id == case_id)
    split_mw_model, max_carbon_number, lumping_n_groups = {
        "volatile_oil": ("table", 20, 6),
        "black_oil": ("table", 20, 6),
        "sour_oil": ("table", 20, 6),
    }[resolved_preset]
    return HeavyEndPTFlashCase(
        case_id=case_id,
        resolved_preset=resolved_preset,
        composition_payload=_normalize_runtime_payload_from_resolved_plus(
            source.resolved_components,
            z_plus=source.z_plus,
            mw_plus_g_per_mol=source.mw_plus_g_per_mol,
            sg_plus_60f=source.sg_plus_60f,
        ),
        temperature_k=source.temperature_k,
        pressure_pa=float(source.lumped_pressure_pa) * pressure_factor,
        expected_phase=expected_phase,
        expected_reported_surface_status=expected_reported_surface_status,
        expected_reported_component_basis=(
            "reconstructed_scn"
            if expected_reported_surface_status == "available"
            else None
        ),
        expected_split_mw_model=split_mw_model,
        expected_max_carbon_number=max_carbon_number,
        expected_lumping_n_groups=lumping_n_groups,
    )


def _dew_validation_case(
    case_id: str,
    *,
    pressure_factor: float | None = None,
    pressure_pa: float | None = None,
    expected_phase: str,
    expected_reported_surface_status: str,
    resolved_preset: str,
) -> HeavyEndPTFlashCase:
    source = next(case for case in PLUS_FRACTION_DEW_CASES if case.case_id == case_id)
    split_mw_model, max_carbon_number, lumping_n_groups = {
        "dry_gas": ("table", 11, 4),
        "co2_rich_gas": ("paraffin", 11, 4),
        "gas_condensate": ("paraffin", 18, 2),
    }[resolved_preset]
    if pressure_pa is None:
        assert pressure_factor is not None
        pressure_pa = float(source.lumped_pressure_pa) * pressure_factor
    return HeavyEndPTFlashCase(
        case_id=case_id,
        resolved_preset=resolved_preset,
        composition_payload=_normalize_runtime_payload_from_explicit_plus(
            source.explicit_components,
            z_plus=source.z_plus,
            mw_plus_g_per_mol=source.mw_plus_g_per_mol,
            sg_plus_60f=source.sg_plus_60f,
        ),
        temperature_k=source.temperature_k,
        pressure_pa=pressure_pa,
        expected_phase=expected_phase,
        expected_reported_surface_status=expected_reported_surface_status,
        expected_reported_component_basis=(
            "reconstructed_scn"
            if expected_reported_surface_status == "available"
            else None
        ),
        expected_split_mw_model=split_mw_model,
        expected_max_carbon_number=max_carbon_number,
        expected_lumping_n_groups=lumping_n_groups,
    )


TWO_PHASE_RECONSTRUCTION_CASES = (
    _bubble_validation_case(
        "plus_volatile_oil_characterized_bubble",
        pressure_factor=0.75,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="volatile_oil",
    ),
    _bubble_validation_case(
        "plus_black_oil_characterized_bubble",
        pressure_factor=0.75,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="black_oil",
    ),
    _bubble_validation_case(
        "plus_sour_oil_a_characterized_bubble",
        pressure_factor=0.75,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="sour_oil",
    ),
    _bubble_validation_case(
        "plus_sour_oil_b_characterized_bubble",
        pressure_factor=0.75,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="sour_oil",
    ),
    _dew_validation_case(
        "plus_dry_gas_a_characterized_dew",
        pressure_factor=5.0,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_dry_gas_b_characterized_dew",
        pressure_factor=5.0,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_gas_condensate_a_characterized_dew",
        pressure_factor=5.0,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="gas_condensate",
    ),
    _dew_validation_case(
        "plus_gas_condensate_b_characterized_dew",
        pressure_factor=5.0,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="gas_condensate",
    ),
    _dew_validation_case(
        "plus_co2_rich_gas_a_characterized_dew",
        pressure_pa=1.0e5,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="co2_rich_gas",
    ),
    _dew_validation_case(
        "plus_co2_rich_gas_b_characterized_dew",
        pressure_pa=1.0e5,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="co2_rich_gas",
    ),
)


NEAR_DEW_RECOVERY_CASES = (
    _dew_validation_case(
        "plus_dry_gas_a_characterized_dew",
        pressure_factor=1.2,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_dry_gas_b_characterized_dew",
        pressure_factor=1.2,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_gas_condensate_a_characterized_dew",
        pressure_factor=1.5,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="gas_condensate",
    ),
    _dew_validation_case(
        "plus_gas_condensate_b_characterized_dew",
        pressure_factor=1.5,
        expected_phase="two-phase",
        expected_reported_surface_status="available",
        resolved_preset="gas_condensate",
    ),
)


SINGLE_PHASE_WITHHELD_CASES = (
    _bubble_validation_case(
        "plus_volatile_oil_characterized_bubble",
        pressure_factor=1.2,
        expected_phase="liquid",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="volatile_oil",
    ),
    _bubble_validation_case(
        "plus_black_oil_characterized_bubble",
        pressure_factor=1.2,
        expected_phase="liquid",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="black_oil",
    ),
    _bubble_validation_case(
        "plus_sour_oil_a_characterized_bubble",
        pressure_factor=1.2,
        expected_phase="liquid",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="sour_oil",
    ),
    _bubble_validation_case(
        "plus_sour_oil_b_characterized_bubble",
        pressure_factor=1.5,
        expected_phase="liquid",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="sour_oil",
    ),
    _dew_validation_case(
        "plus_dry_gas_a_characterized_dew",
        pressure_factor=0.5,
        expected_phase="vapor",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_dry_gas_b_characterized_dew",
        pressure_factor=0.5,
        expected_phase="vapor",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="dry_gas",
    ),
    _dew_validation_case(
        "plus_gas_condensate_a_characterized_dew",
        pressure_factor=0.5,
        expected_phase="vapor",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="gas_condensate",
    ),
    _dew_validation_case(
        "plus_gas_condensate_b_characterized_dew",
        pressure_factor=0.5,
        expected_phase="vapor",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="gas_condensate",
    ),
    _dew_validation_case(
        "plus_co2_rich_gas_a_characterized_dew",
        pressure_pa=5.0e7,
        expected_phase="liquid",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="co2_rich_gas",
    ),
    _dew_validation_case(
        "plus_co2_rich_gas_b_characterized_dew",
        pressure_pa=1.0e3,
        expected_phase="vapor",
        expected_reported_surface_status="withheld_single_phase_runtime",
        resolved_preset="co2_rich_gas",
    ),
)


REPLAY_ROUNDTRIP_CASES = (
    next(case for case in TWO_PHASE_RECONSTRUCTION_CASES if case.case_id == "plus_volatile_oil_characterized_bubble"),
    next(case for case in TWO_PHASE_RECONSTRUCTION_CASES if case.case_id == "plus_dry_gas_a_characterized_dew"),
    next(case for case in TWO_PHASE_RECONSTRUCTION_CASES if case.case_id == "plus_co2_rich_gas_b_characterized_dew"),
)


def _pt_flash_config(case: HeavyEndPTFlashCase) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": case.case_id,
            "composition": case.composition_payload,
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": case.pressure_pa,
                "temperature_k": case.temperature_k,
            },
        }
    )


def _assert_plus_fraction_policy(case: HeavyEndPTFlashCase, result) -> None:
    plus_fraction = result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.resolved_characterization_preset is not None
    assert plus_fraction.resolved_characterization_preset.value == case.resolved_preset
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == case.expected_split_mw_model
    assert plus_fraction.max_carbon_number == case.expected_max_carbon_number
    assert plus_fraction.lumping_enabled is True
    assert plus_fraction.lumping_n_groups == case.expected_lumping_n_groups
    assert plus_fraction.lumping_method == "whitson"


def _assert_runtime_characterization_common(result) -> None:
    runtime = result.runtime_characterization
    assert runtime is not None
    assert runtime.source == "plus_fraction_runtime"
    assert runtime.runtime_component_basis == "lumped"
    assert runtime.lumping_method == "whitson"
    assert runtime.detailed_reconstruction is not None
    assert runtime.detailed_reconstruction_unavailable_reason is None
    assert runtime.runtime_component_ids
    assert any(component_id.startswith("LUMP") for component_id in runtime.runtime_component_ids)


def _assert_reported_surface_consistency(pt_flash_result) -> None:
    assert pt_flash_result.reported_liquid_composition is not None
    assert pt_flash_result.reported_vapor_composition is not None
    assert pt_flash_result.reported_k_values is not None
    assert pt_flash_result.reported_liquid_fugacity is not None
    assert pt_flash_result.reported_vapor_fugacity is not None
    assert pt_flash_result.has_reported_thermodynamic_surface is True
    assert sum(pt_flash_result.reported_liquid_composition.values()) == pytest.approx(1.0, abs=1e-12)
    assert sum(pt_flash_result.reported_vapor_composition.values()) == pytest.approx(1.0, abs=1e-12)
    assert "SCN7" in pt_flash_result.reported_liquid_composition
    assert not any(component_id.startswith("LUMP") for component_id in pt_flash_result.reported_liquid_composition)

    for component_id, reported_k in pt_flash_result.reported_k_values.items():
        reported_x = pt_flash_result.reported_liquid_composition[component_id]
        reported_y = pt_flash_result.reported_vapor_composition[component_id]
        reported_phi_l = pt_flash_result.reported_liquid_fugacity[component_id]
        reported_phi_v = pt_flash_result.reported_vapor_fugacity[component_id]
        assert reported_k == pytest.approx(reported_phi_l / reported_phi_v, rel=1e-8, abs=1e-10)
        if reported_x > 1.0e-12:
            assert reported_k == pytest.approx(reported_y / reported_x, rel=1e-5, abs=1e-8)


@pytest.mark.parametrize("case", TWO_PHASE_RECONSTRUCTION_CASES, ids=lambda case: case.case_id)
def test_heavy_end_pt_flash_runtime_matrix_emits_reconstructed_surface_for_two_phase_cases(
    case: HeavyEndPTFlashCase,
) -> None:
    result = run_calculation(config=_pt_flash_config(case), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    _assert_plus_fraction_policy(case, result)
    _assert_runtime_characterization_common(result)

    pt_flash_result = result.pt_flash_result
    assert pt_flash_result.phase == case.expected_phase
    assert pt_flash_result.reported_surface_status == case.expected_reported_surface_status
    assert pt_flash_result.reported_surface_reason is None
    assert pt_flash_result.reported_component_basis == case.expected_reported_component_basis
    _assert_reported_surface_consistency(pt_flash_result)


@pytest.mark.parametrize("case", NEAR_DEW_RECOVERY_CASES, ids=lambda case: case.case_id)
def test_heavy_end_pt_flash_runtime_matrix_recovers_near_dew_two_phase_cases(
    case: HeavyEndPTFlashCase,
) -> None:
    result = run_calculation(config=_pt_flash_config(case), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    _assert_plus_fraction_policy(case, result)
    _assert_runtime_characterization_common(result)

    pt_flash_result = result.pt_flash_result
    assert pt_flash_result.phase == case.expected_phase
    assert pt_flash_result.reported_surface_status == case.expected_reported_surface_status
    assert pt_flash_result.reported_surface_reason is None
    assert pt_flash_result.reported_component_basis == case.expected_reported_component_basis
    assert pt_flash_result.vapor_fraction > 0.95
    _assert_reported_surface_consistency(pt_flash_result)


@pytest.mark.parametrize("case", SINGLE_PHASE_WITHHELD_CASES, ids=lambda case: case.case_id)
def test_heavy_end_pt_flash_runtime_matrix_withholds_reported_surface_for_single_phase_cases(
    case: HeavyEndPTFlashCase,
) -> None:
    result = run_calculation(config=_pt_flash_config(case), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    assert result.error_message is None
    _assert_plus_fraction_policy(case, result)
    _assert_runtime_characterization_common(result)

    pt_flash_result = result.pt_flash_result
    assert pt_flash_result.phase == case.expected_phase
    assert pt_flash_result.reported_surface_status == case.expected_reported_surface_status
    assert pt_flash_result.reported_surface_reason is not None
    assert "two-phase" in pt_flash_result.reported_surface_reason.lower()
    assert pt_flash_result.reported_component_basis == case.expected_reported_component_basis
    assert pt_flash_result.has_reported_thermodynamic_surface is False
    assert pt_flash_result.reported_liquid_composition is None
    assert pt_flash_result.reported_vapor_composition is None
    assert pt_flash_result.reported_k_values is None
    assert pt_flash_result.reported_liquid_fugacity is None
    assert pt_flash_result.reported_vapor_fugacity is None


@pytest.mark.parametrize("case", REPLAY_ROUNDTRIP_CASES, ids=lambda case: case.case_id)
def test_heavy_end_pt_flash_runtime_matrix_saved_run_replay_preserves_reported_surface_contract(
    case: HeavyEndPTFlashCase,
    tmp_path: Path,
) -> None:
    case_dir = tmp_path / case.case_id
    original = run_calculation(
        config=_pt_flash_config(case),
        output_dir=case_dir,
        write_artifacts=True,
    )

    assert original.status == RunStatus.COMPLETED
    assert original.pt_flash_result is not None
    run_dirs = sorted(path for path in case_dir.iterdir() if path.is_dir())
    assert len(run_dirs) == 1

    replayed = rerun_saved_run(
        run_dirs[0],
        output_dir=case_dir,
        write_artifacts=True,
        run_name=f"{case.case_id} replay",
    )

    assert replayed.status == RunStatus.COMPLETED
    assert replayed.pt_flash_result is not None
    assert replayed.run_id != original.run_id
    assert replayed.run_name == f"{case.case_id} replay"
    _assert_plus_fraction_policy(case, replayed)
    _assert_runtime_characterization_common(replayed)
    assert replayed.pt_flash_result.phase == case.expected_phase
    assert replayed.pt_flash_result.reported_surface_status == case.expected_reported_surface_status
    assert replayed.pt_flash_result.reported_component_basis == case.expected_reported_component_basis
    _assert_reported_surface_consistency(replayed.pt_flash_result)
