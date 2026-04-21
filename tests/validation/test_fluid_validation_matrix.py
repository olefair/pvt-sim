"""Executable first-checkpoint slice for the two-fluid validation matrix."""

from __future__ import annotations

from pathlib import Path

import pytest

from pvtapp.assignment_case import build_assignment_desktop_preset
from pvtapp.job_runner import rerun_saved_run, run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from pvtcore.validation.pete665_assignment import run_assignment_case


def _assignment_runtime_config(calculation_type: str) -> RunConfig:
    preset = build_assignment_desktop_preset(initials="TANS")
    payload: dict = {
        "run_name": f"Assignment {calculation_type}",
        "composition": preset.composition.model_dump(mode="json"),
        "calculation_type": calculation_type,
        "eos_type": "peng_robinson",
    }
    if calculation_type == "bubble_point":
        payload["bubble_point_config"] = preset.bubble_point_config.model_dump(mode="json")
    elif calculation_type == "cce":
        payload["cce_config"] = preset.cce_config.model_dump(mode="json")
    elif calculation_type == "differential_liberation":
        payload["dl_config"] = preset.dl_config.model_dump(mode="json")
    else:  # pragma: no cover - guardrail for future edits
        raise AssertionError(f"Unsupported assignment calculation type: {calculation_type}")
    return RunConfig.model_validate(payload)


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


def _gas_dew_config(*, dew_pressure_pa: float | None = None) -> RunConfig:
    payload: dict = {
        "run_name": "Matrix gas dew",
        "composition": _gas_plus_fraction_composition_payload(),
        "calculation_type": "dew_point",
        "eos_type": "peng_robinson",
        "dew_point_config": {
            "temperature_k": 320.0,
            "pressure_initial_pa": 1.0e5,
        },
    }
    if dew_pressure_pa is not None:
        payload["dew_point_config"]["pressure_initial_pa"] = dew_pressure_pa
    return RunConfig.model_validate(payload)


def _gas_cvd_config(*, dew_pressure_pa: float) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "Matrix gas cvd",
            "composition": _gas_plus_fraction_composition_payload(),
            "calculation_type": "cvd",
            "eos_type": "peng_robinson",
            "cvd_config": {
                "temperature_k": 320.0,
                "dew_pressure_pa": dew_pressure_pa,
                "pressure_end_pa": 1500.0,
                "n_steps": 5,
            },
        }
    )


def test_assignment_reference_and_general_runtime_agree_across_bubble_cce_and_dl() -> None:
    reference = run_assignment_case(initials="TANS")

    bubble_result = run_calculation(
        config=_assignment_runtime_config("bubble_point"),
        write_artifacts=False,
    )
    cce_result = run_calculation(
        config=_assignment_runtime_config("cce"),
        write_artifacts=False,
    )
    dl_result = run_calculation(
        config=_assignment_runtime_config("differential_liberation"),
        write_artifacts=False,
    )

    assert bubble_result.status == RunStatus.COMPLETED
    assert cce_result.status == RunStatus.COMPLETED
    assert dl_result.status == RunStatus.COMPLETED

    # The assignment reference path runs on PR78 per the course spec while the
    # general desktop runtime still runs on PR76. A ~20 kPa (~3 psi) spread at
    # Pb is expected; we assert ballpark agreement rather than equality.
    eos_tolerance_pa = 25_000.0

    assert bubble_result.bubble_point_result is not None
    assert bubble_result.bubble_point_result.pressure_pa == pytest.approx(
        reference["saturation_pressure"]["pressure_pa"],
        abs=eos_tolerance_pa,
    )

    assert cce_result.cce_result is not None
    assert cce_result.cce_result.saturation_pressure_pa == pytest.approx(
        reference["cce"]["saturation_pressure_pa"],
        abs=eos_tolerance_pa,
    )
    assert [step.pressure_pa for step in cce_result.cce_result.steps] == pytest.approx(
        [step["pressure_pa"] for step in reference["cce"]["steps"]]
    )
    assert [step.relative_volume for step in cce_result.cce_result.steps] == pytest.approx(
        [step["relative_volume"] for step in reference["cce"]["steps"]],
        rel=5.0e-3,
        abs=1.0e-5,
    )

    reference_dl_reservoir = [
        step for step in reference["dl"]["steps"] if step.get("phase") == "reservoir"
    ]
    assert len(reference_dl_reservoir) == 3

    assert dl_result.dl_result is not None
    assert dl_result.dl_result.bubble_pressure_pa == pytest.approx(
        reference["dl"]["bubble_pressure_pa"],
        abs=eos_tolerance_pa,
    )
    assert dl_result.dl_result.steps[0].pressure_pa == pytest.approx(
        dl_result.dl_result.bubble_pressure_pa,
        abs=eos_tolerance_pa,
    )
    runtime_dl_steps = dl_result.dl_result.steps[1:]
    assert [step.pressure_pa for step in runtime_dl_steps] == pytest.approx(
        [step["pressure_pa"] for step in reference_dl_reservoir]
    )


def test_gas_condensate_runtime_matrix_preserves_fluid_intent_across_dew_cvd_and_replay(
    tmp_path: Path,
) -> None:
    dew_result = run_calculation(
        config=_gas_dew_config(),
        output_dir=tmp_path,
        write_artifacts=True,
    )

    assert dew_result.status == RunStatus.COMPLETED
    assert dew_result.dew_point_result is not None
    plus_fraction = dew_result.config.composition.plus_fraction
    assert plus_fraction is not None
    assert plus_fraction.resolved_characterization_preset is not None
    assert plus_fraction.resolved_characterization_preset.value == "gas_condensate"
    assert plus_fraction.split_method == "pedersen"
    assert plus_fraction.split_mw_model == "paraffin"
    assert plus_fraction.max_carbon_number == 18
    assert plus_fraction.lumping_n_groups == 2

    dew_pressure_pa = dew_result.dew_point_result.pressure_pa
    cvd_result = run_calculation(
        config=_gas_cvd_config(dew_pressure_pa=dew_pressure_pa),
        write_artifacts=False,
    )

    assert cvd_result.status == RunStatus.COMPLETED
    assert cvd_result.cvd_result is not None
    assert cvd_result.cvd_result.dew_pressure_pa == pytest.approx(dew_pressure_pa, abs=1.0e-6)

    run_dirs = sorted(path for path in tmp_path.iterdir() if path.is_dir())
    assert len(run_dirs) == 1

    replayed = rerun_saved_run(
        run_dirs[0],
        output_dir=tmp_path,
        write_artifacts=True,
        run_name="Matrix gas dew replay",
    )

    assert replayed.status == RunStatus.COMPLETED
    assert replayed.dew_point_result is not None
    assert replayed.run_id != dew_result.run_id
    assert replayed.run_name == "Matrix gas dew replay"
    assert replayed.dew_point_result.pressure_pa == pytest.approx(dew_pressure_pa, abs=1.0e-6)

    replay_plus = replayed.config.composition.plus_fraction
    assert replay_plus is not None
    assert replay_plus.resolved_characterization_preset is not None
    assert replay_plus.resolved_characterization_preset.value == "gas_condensate"
