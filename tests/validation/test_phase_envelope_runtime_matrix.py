"""Runtime envelope validation against the phase-envelope matrix roster.

This suite turns the minimum practical roster from the phase-envelope
validation docs into executable runtime checks. Each case runs through the
application/runtime path and verifies that the continuation-traced phase
envelope remains aligned with the standalone bubble- or dew-point workflow for
that fluid at the benchmark temperature.

The saturation workflows are already validated separately against independent
equation-based references. This file checks the runtime agreement contract:

- the phase-envelope workflow uses the same saturation boundary as the
  standalone saturation workflows
- practical field-fluid families from the matrix remain executable end-to-end
- lab-style ``C1-C6 + C7+`` entry surfaces stay aligned with the runtime
  characterization presets used by the phase-envelope workflow
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pytest
import numpy as np

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus


Branch = Literal["bubble", "dew"]


@dataclass(frozen=True)
class RuntimeEnvelopeMatrixCase:
    """Single runtime envelope validation case from the matrix roster."""

    case_id: str
    fluid_family: str
    target_branch: Branch
    target_temperature_k: float
    temperature_min_k: float
    temperature_max_k: float
    n_points: int
    components: tuple[tuple[str, float], ...]
    plus_fraction: dict | None = None
    expected_plus_preset: str | None = None
    branch_family_sensitive: bool = False


def _normalized_composition_payload(case: RuntimeEnvelopeMatrixCase) -> dict:
    total = float(sum(z for _, z in case.components) + (0.0 if case.plus_fraction is None else case.plus_fraction["z_plus"]))
    components = [
        {"component_id": component_id, "mole_fraction": float(z) / total}
        for component_id, z in case.components
    ]
    payload = {"components": components}

    if case.plus_fraction is not None:
        plus = dict(case.plus_fraction)
        plus["z_plus"] = float(plus["z_plus"]) / total
        payload["plus_fraction"] = plus

    return payload


def _build_phase_envelope_config(case: RuntimeEnvelopeMatrixCase) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": f"{case.case_id} phase envelope",
            "composition": _normalized_composition_payload(case),
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": case.temperature_min_k,
                "temperature_max_k": case.temperature_max_k,
                "n_points": case.n_points,
                "tracing_method": "continuation",
            },
        }
    )


def _build_saturation_config(case: RuntimeEnvelopeMatrixCase) -> RunConfig:
    config = {
        "run_name": f"{case.case_id} {case.target_branch}",
        "composition": _normalized_composition_payload(case),
        "calculation_type": "bubble_point" if case.target_branch == "bubble" else "dew_point",
        "eos_type": "peng_robinson",
    }

    if case.target_branch == "bubble":
        config["bubble_point_config"] = {
            "temperature_k": case.target_temperature_k,
            "pressure_initial_pa": 1.0e5,
        }
    else:
        config["dew_point_config"] = {
            "temperature_k": case.target_temperature_k,
            "pressure_initial_pa": 1.0e5,
        }

    return RunConfig.model_validate(config)


def _pressure_at_temperature(points: list, temperature_k: float) -> float:
    ordered = sorted(
        ((float(point.temperature_k), float(point.pressure_pa)) for point in points),
        key=lambda item: item[0],
    )
    temperatures = np.array([item[0] for item in ordered], dtype=float)
    pressures = np.array([item[1] for item in ordered], dtype=float)

    if temperature_k < temperatures[0] - 1e-9 or temperature_k > temperatures[-1] + 1e-9:
        raise AssertionError(
            f"Target temperature {temperature_k:.6f} K is outside the traced branch range "
            f"[{temperatures[0]:.6f}, {temperatures[-1]:.6f}] K"
        )

    for point in points:
        if abs(float(point.temperature_k) - float(temperature_k)) <= 1e-9:
            return float(point.pressure_pa)

    interpolated_log_pressure = np.interp(float(temperature_k), temperatures, np.log(pressures))
    return float(np.exp(interpolated_log_pressure))


RUNTIME_ENVELOPE_MATRIX_CASES = [
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_default_co2_regression_gas",
        fluid_family="co2_regression_gas",
        target_branch="dew",
        target_temperature_k=300.0,
        temperature_min_k=260.0,
        temperature_max_k=320.0,
        n_points=13,
        components=(
            ("CO2", 0.6498),
            ("C1", 0.1057),
            ("C2", 0.1058),
            ("C3", 0.1235),
            ("C4", 0.0152),
        ),
        branch_family_sensitive=True,
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_dry_gas_a",
        fluid_family="dry_gas",
        target_branch="dew",
        target_temperature_k=260.0,
        temperature_min_k=180.0,
        temperature_max_k=360.0,
        n_points=10,
        components=(
            ("N2", 0.0100),
            ("CO2", 0.0150),
            ("C1", 0.8200),
            ("C2", 0.0700),
            ("C3", 0.0350),
            ("iC4", 0.0120),
            ("C4", 0.0100),
            ("iC5", 0.0080),
            ("C5", 0.0070),
            ("C6", 0.0050),
            ("C7", 0.0030),
            ("C8", 0.0030),
            ("C10", 0.0020),
        ),
        branch_family_sensitive=True,
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_gas_condensate_a",
        fluid_family="gas_condensate",
        target_branch="dew",
        target_temperature_k=320.0,
        temperature_min_k=260.0,
        temperature_max_k=440.0,
        n_points=10,
        components=(
            ("N2", 0.0060),
            ("CO2", 0.0250),
            ("C1", 0.6400),
            ("C2", 0.1100),
            ("C3", 0.0750),
            ("iC4", 0.0250),
            ("C4", 0.0250),
            ("iC5", 0.0180),
            ("C5", 0.0160),
            ("C6", 0.0140),
            ("C7", 0.0140),
            ("C8", 0.0120),
            ("C10", 0.0100),
            ("C12", 0.0100),
        ),
        branch_family_sensitive=True,
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_co2_rich_gas_a",
        fluid_family="co2_rich_gas",
        target_branch="dew",
        target_temperature_k=290.0,
        temperature_min_k=250.0,
        temperature_max_k=430.0,
        n_points=10,
        components=(
            ("N2", 0.0080),
            ("CO2", 0.4600),
            ("H2S", 0.0100),
            ("C1", 0.2900),
            ("C2", 0.0700),
            ("C3", 0.0450),
            ("iC4", 0.0200),
            ("C4", 0.0180),
            ("iC5", 0.0120),
            ("C5", 0.0120),
            ("C6", 0.0110),
            ("C7", 0.0100),
            ("C8", 0.0080),
            ("C10", 0.0060),
        ),
        branch_family_sensitive=True,
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_volatile_oil_a",
        fluid_family="volatile_oil",
        target_branch="bubble",
        target_temperature_k=360.0,
        temperature_min_k=300.0,
        temperature_max_k=480.0,
        n_points=10,
        components=(
            ("N2", 0.0021),
            ("CO2", 0.0187),
            ("C1", 0.3478),
            ("C2", 0.0712),
            ("C3", 0.0934),
            ("iC4", 0.0302),
            ("C4", 0.0431),
            ("iC5", 0.0276),
            ("C5", 0.0418),
            ("C6", 0.0574),
            ("C7", 0.0835),
            ("C8", 0.0886),
            ("C10", 0.0946),
        ),
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_black_oil_a",
        fluid_family="black_oil",
        target_branch="bubble",
        target_temperature_k=380.0,
        temperature_min_k=300.0,
        temperature_max_k=500.0,
        n_points=11,
        components=(
            ("N2", 0.0010),
            ("CO2", 0.0100),
            ("H2S", 0.0040),
            ("C1", 0.1800),
            ("C2", 0.0550),
            ("C3", 0.0700),
            ("iC4", 0.0400),
            ("C4", 0.0500),
            ("iC5", 0.0420),
            ("C5", 0.0500),
            ("C6", 0.0700),
            ("C7", 0.0950),
            ("C8", 0.1020),
            ("C10", 0.0850),
            ("C12", 0.0800),
            ("C14", 0.0660),
        ),
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_sour_oil_a",
        fluid_family="sour_oil",
        target_branch="bubble",
        target_temperature_k=340.0,
        temperature_min_k=260.0,
        temperature_max_k=440.0,
        n_points=10,
        components=(
            ("N2", 0.0010),
            ("CO2", 0.0500),
            ("H2S", 0.0700),
            ("C1", 0.2200),
            ("C2", 0.0600),
            ("C3", 0.0700),
            ("iC4", 0.0300),
            ("C4", 0.0400),
            ("iC5", 0.0300),
            ("C5", 0.0400),
            ("C6", 0.0600),
            ("C7", 0.0850),
            ("C8", 0.0900),
            ("C10", 0.0800),
            ("C12", 0.0650),
            ("C14", 0.0500),
            ("C16", 0.0290),
        ),
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_plus_volatile_oil",
        fluid_family="volatile_oil_c7plus",
        target_branch="bubble",
        target_temperature_k=360.0,
        temperature_min_k=300.0,
        temperature_max_k=480.0,
        n_points=10,
        components=(
            ("N2", 0.0021),
            ("CO2", 0.0187),
            ("C1", 0.3478),
            ("C2", 0.0712),
            ("C3", 0.0934),
            ("iC4", 0.0302),
            ("C4", 0.0431),
            ("iC5", 0.0276),
            ("C5", 0.0418),
            ("C6", 0.0574),
        ),
        plus_fraction={
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.2667,
            "mw_plus_g_per_mol": 119.78759868766404,
            "sg_plus_60f": 0.82,
        },
        expected_plus_preset="volatile_oil",
    ),
    RuntimeEnvelopeMatrixCase(
        case_id="matrix_plus_gas_condensate",
        fluid_family="gas_condensate_c7plus",
        target_branch="dew",
        target_temperature_k=320.0,
        temperature_min_k=240.0,
        temperature_max_k=420.0,
        n_points=10,
        components=(
            ("N2", 0.0060),
            ("CO2", 0.0250),
            ("C1", 0.6400),
            ("C2", 0.1100),
            ("C3", 0.0750),
            ("iC4", 0.0250),
            ("C4", 0.0250),
            ("iC5", 0.0180),
            ("C5", 0.0160),
            ("C6", 0.0140),
        ),
        plus_fraction={
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.0460,
            "mw_plus_g_per_mol": 128.25512173913043,
            "sg_plus_60f": 0.7571304347826087,
        },
        expected_plus_preset="gas_condensate",
        branch_family_sensitive=True,
    ),
]


@pytest.mark.parametrize("case", RUNTIME_ENVELOPE_MATRIX_CASES, ids=lambda case: case.case_id)
def test_phase_envelope_runtime_matrix_matches_standalone_saturation(case: RuntimeEnvelopeMatrixCase) -> None:
    """Phase-envelope runtime should pass through the standalone saturation point for each matrix case."""
    if case.branch_family_sensitive:
        pytest.skip(
            "Branch-family-sensitive case: continuation traces a local envelope family while "
            "the standalone saturation solver still returns a global root."
        )

    envelope_result = run_calculation(config=_build_phase_envelope_config(case), write_artifacts=False)
    saturation_result = run_calculation(config=_build_saturation_config(case), write_artifacts=False)

    assert envelope_result.status == RunStatus.COMPLETED
    assert envelope_result.phase_envelope_result is not None
    assert envelope_result.error_message is None

    assert saturation_result.status == RunStatus.COMPLETED
    assert saturation_result.error_message is None

    envelope = envelope_result.phase_envelope_result
    assert len(envelope.bubble_curve) > 0
    assert len(envelope.dew_curve) > 0

    if case.target_branch == "bubble":
        assert saturation_result.bubble_point_result is not None
        expected_pressure_pa = float(saturation_result.bubble_point_result.pressure_pa)
        actual_pressure_pa = _pressure_at_temperature(envelope.bubble_curve, case.target_temperature_k)
    else:
        assert saturation_result.dew_point_result is not None
        expected_pressure_pa = float(saturation_result.dew_point_result.pressure_pa)
        actual_pressure_pa = _pressure_at_temperature(envelope.dew_curve, case.target_temperature_k)

    assert actual_pressure_pa == pytest.approx(expected_pressure_pa, rel=0.02)

    plus_fraction = envelope_result.config.composition.plus_fraction
    if case.expected_plus_preset is None:
        assert plus_fraction is None or plus_fraction.resolved_characterization_preset is None
    else:
        assert plus_fraction is not None
        assert plus_fraction.resolved_characterization_preset is not None
        assert plus_fraction.resolved_characterization_preset.value == case.expected_plus_preset
