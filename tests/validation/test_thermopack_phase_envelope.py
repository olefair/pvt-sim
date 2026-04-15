"""Optional ThermoPack-backed phase-envelope checks for heavier fluids.

This lane is intentionally validation-only. It exercises the runtime
continuation envelope against an approved external EOS backend when that backend
is available locally.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import PhaseEnvelopePoint, PhaseEnvelopeResult, RunConfig, RunStatus
from pvtcore.validation.prode_bridge import EnvelopePoint, NormalizedEnvelopeResult
from pvtcore.validation.thermopack_bridge import (
    detect_thermopack_validation_backend,
    load_thermopack_validation_backend,
)


_CASES_DIR = Path(__file__).resolve().parent / "thermopack" / "cases"


def _temperature_to_k(obj: Any) -> float:
    if isinstance(obj, (int, float)):
        return float(obj)
    if not isinstance(obj, Mapping):
        raise TypeError(f"Unsupported temperature spec: {obj!r}")

    value = float(obj["value"])
    unit = str(obj.get("unit", "K")).strip().lower()
    if unit == "k":
        return value
    if unit == "c":
        return value + 273.15
    if unit == "f":
        return (value - 32.0) * 5.0 / 9.0 + 273.15
    raise ValueError(f"Unsupported temperature unit: {unit!r}")


@dataclass(frozen=True)
class ThermoPackEnvelopeCase:
    case_id: str
    component_ids: tuple[str, ...]
    composition: np.ndarray
    tracing_method: str
    temperature_min_k: float
    temperature_max_k: float
    n_points: int
    reference_key_points: frozenset[str]
    reference_branches: frozenset[str]
    thermopack_options: dict[str, Any]
    tolerances: dict[str, float]


def _load_cases() -> list[ThermoPackEnvelopeCase]:
    if not _CASES_DIR.exists():
        return []

    cases: list[ThermoPackEnvelopeCase] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        if path.stem.startswith("template_") or path.stem.endswith("_template"):
            continue

        raw = json.loads(path.read_text(encoding="utf-8"))
        if str(raw.get("task", "")).strip().lower() != "phase_envelope":
            continue

        composition_entries = raw["composition"]
        component_ids = tuple(str(entry["id"]) for entry in composition_entries)
        composition = np.array([float(entry["z"]) for entry in composition_entries], dtype=float)
        composition /= float(composition.sum())

        trace = dict(raw.get("trace", {}) or {})
        tolerances = {str(key): float(value) for key, value in dict(raw.get("tolerances", {}) or {}).items()}
        thermopack_options = dict(raw.get("thermopack_options", {}) or {})
        reference_key_points = frozenset(
            str(value).strip()
            for value in raw.get("reference_key_points", ("critical_point", "cricondenbar", "cricondentherm"))
        )
        reference_branches = frozenset(
            str(value).strip()
            for value in raw.get("reference_branches", ("bubble", "dew"))
        )

        cases.append(
            ThermoPackEnvelopeCase(
                case_id=str(raw.get("case_id", path.stem)),
                component_ids=component_ids,
                composition=composition,
                tracing_method=str(trace.get("method", "continuation")).strip().lower(),
                temperature_min_k=_temperature_to_k(trace["temperature_min"]),
                temperature_max_k=_temperature_to_k(trace["temperature_max"]),
                n_points=int(trace["n_points"]),
                reference_key_points=reference_key_points,
                reference_branches=reference_branches,
                thermopack_options=thermopack_options,
                tolerances=tolerances,
            )
        )
    return cases


_CASES = _load_cases()
if not _CASES:
    pytest.skip(
        f"No ThermoPack phase-envelope cases found at: {_CASES_DIR}",
        allow_module_level=True,
    )

_THERMOPACK_AVAILABILITY = detect_thermopack_validation_backend()
if not _THERMOPACK_AVAILABILITY.available:
    pytest.skip(
        f"ThermoPack phase-envelope validation disabled: {_THERMOPACK_AVAILABILITY.reason}",
        allow_module_level=True,
    )

_THERMOPACK = load_thermopack_validation_backend()


def _runtime_phase_envelope(case: ThermoPackEnvelopeCase) -> PhaseEnvelopeResult:
    config = RunConfig.model_validate(
        {
            "run_name": case.case_id,
            "composition": {
                "components": [
                    {"component_id": component_id, "mole_fraction": float(z)}
                    for component_id, z in zip(case.component_ids, case.composition, strict=True)
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": case.temperature_min_k,
                "temperature_max_k": case.temperature_max_k,
                "n_points": case.n_points,
                "tracing_method": case.tracing_method,
            },
        }
    )
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status is RunStatus.COMPLETED
    assert result.phase_envelope_result is not None
    return result.phase_envelope_result


def _deduplicated_curve_arrays(
    points: Sequence[object],
    *,
    temperature_attr: str,
    pressure_attr: str,
) -> tuple[np.ndarray, np.ndarray]:
    ordered = sorted(points, key=lambda point: float(getattr(point, temperature_attr)))
    unique_temperatures: list[float] = []
    unique_pressures: list[float] = []
    for point in ordered:
        temperature = float(getattr(point, temperature_attr))
        pressure = float(getattr(point, pressure_attr))
        if unique_temperatures and abs(temperature - unique_temperatures[-1]) <= 1.0e-12:
            unique_pressures[-1] = pressure
            continue
        unique_temperatures.append(temperature)
        unique_pressures.append(pressure)
    return np.array(unique_temperatures, dtype=float), np.array(unique_pressures, dtype=float)


def _assert_key_point_close(
    label: str,
    runtime_point: PhaseEnvelopePoint | None,
    reference_point: EnvelopePoint | None,
    *,
    pressure_pa_atol: float,
    temperature_k_atol: float,
) -> None:
    if reference_point is None:
        return

    assert runtime_point is not None, f"{label} missing from runtime result"
    assert float(runtime_point.temperature_k) == pytest.approx(
        float(reference_point.temperature_k),
        abs=float(temperature_k_atol),
    )
    assert float(runtime_point.pressure_pa) == pytest.approx(
        float(reference_point.pressure_pa),
        abs=float(pressure_pa_atol),
    )


def _assert_branch_alignment(
    label: str,
    runtime_points: Sequence[PhaseEnvelopePoint],
    reference_points: Sequence[EnvelopePoint],
    *,
    pressure_pa_atol: float,
    curve_point_fraction_min: float,
) -> None:
    assert runtime_points, f"runtime {label} branch is empty"
    assert reference_points, f"reference {label} branch is empty"

    runtime_t, runtime_p = _deduplicated_curve_arrays(
        runtime_points,
        temperature_attr="temperature_k",
        pressure_attr="pressure_pa",
    )
    reference_t, reference_p = _deduplicated_curve_arrays(
        reference_points,
        temperature_attr="temperature_k",
        pressure_attr="pressure_pa",
    )

    comparable_mask = (
        (reference_t >= float(runtime_t[0]) - 1.0e-12)
        & (reference_t <= float(runtime_t[-1]) + 1.0e-12)
    )
    comparable_count = int(np.count_nonzero(comparable_mask))
    assert comparable_count > 0, f"{label} branch has no overlapping temperature span"

    overlap_fraction = comparable_count / float(reference_t.size)
    assert overlap_fraction >= float(curve_point_fraction_min), (
        f"{label} overlap fraction {overlap_fraction:.3f} is below "
        f"{float(curve_point_fraction_min):.3f}"
    )

    comparable_t = reference_t[comparable_mask]
    comparable_p = reference_p[comparable_mask]
    interpolated_runtime_p = np.interp(comparable_t, runtime_t, runtime_p)
    within_tolerance = np.abs(interpolated_runtime_p - comparable_p) <= float(pressure_pa_atol)
    within_fraction = float(np.mean(within_tolerance))
    assert within_fraction >= float(curve_point_fraction_min), (
        f"{label} within-tolerance fraction {within_fraction:.3f} is below "
        f"{float(curve_point_fraction_min):.3f}"
    )


def _assert_no_runtime_right_tail(envelope: PhaseEnvelopeResult) -> None:
    if envelope.critical_point is None or not envelope.dew_curve:
        return
    critical_temperature = float(envelope.critical_point.temperature_k)
    dew_temperatures = np.array([point.temperature_k for point in envelope.dew_curve], dtype=float)
    assert float(np.max(dew_temperatures)) <= critical_temperature + 1.0e-12


@pytest.mark.parametrize("case", _CASES, ids=lambda case: case.case_id)
def test_thermopack_phase_envelope_matches_runtime(case: ThermoPackEnvelopeCase) -> None:
    """Runtime continuation should stay aligned with the ThermoPack envelope."""
    reference = _THERMOPACK.phase_envelope(
        component_ids=case.component_ids,
        composition=case.composition,
        eos_name="peng_robinson",
        temperature_min_k=case.temperature_min_k,
        temperature_max_k=case.temperature_max_k,
        n_points=case.n_points,
        options=case.thermopack_options,
    )
    runtime = _runtime_phase_envelope(case)

    _assert_no_runtime_right_tail(runtime)

    key_pressure_pa_atol = float(case.tolerances.get("key_pressure_pa_atol", 1.0e6))
    key_temperature_k_atol = float(case.tolerances.get("key_temperature_k_atol", 3.0))
    curve_pressure_pa_atol = float(case.tolerances.get("curve_pressure_pa_atol", 1.5e6))
    curve_point_fraction_min = float(case.tolerances.get("curve_point_fraction_min", 0.65))

    if "critical_point" in case.reference_key_points:
        _assert_key_point_close(
            "critical_point",
            runtime.critical_point,
            reference.critical_point,
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )
    if "cricondenbar" in case.reference_key_points:
        _assert_key_point_close(
            "cricondenbar",
            runtime.cricondenbar,
            reference.cricondenbar,
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )
    if "cricondentherm" in case.reference_key_points:
        _assert_key_point_close(
            "cricondentherm",
            runtime.cricondentherm,
            reference.cricondentherm,
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )

    if "bubble" in case.reference_branches:
        _assert_branch_alignment(
            "bubble",
            runtime.bubble_curve,
            reference.bubble_curve,
            pressure_pa_atol=curve_pressure_pa_atol,
            curve_point_fraction_min=curve_point_fraction_min,
        )
    if "dew" in case.reference_branches:
        _assert_branch_alignment(
            "dew",
            runtime.dew_curve,
            reference.dew_curve,
            pressure_pa_atol=curve_pressure_pa_atol,
            curve_point_fraction_min=curve_point_fraction_min,
        )
