"""Optional live cross-checks against a ThermoPack-backed validation bridge.

This lane is intentionally secondary and optional:

- it never participates in the runtime solver path
- it is skipped entirely unless both a case file and a working ThermoPack
  bridge are available
- it compares the current repo implementation against a live external solver
  surface, not against hard-coded expected JSON values
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json

import numpy as np
import pytest

from pvtcore.core.units import atm_to_pa, bar_to_pa, psi_to_pa
from pvtcore.envelope import trace_envelope_continuation
from pvtcore.envelope.trace import trace_phase_envelope
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.models.component import load_components
from pvtcore.validation import (
    detect_thermopack_validation_backend,
    load_thermopack_validation_backend,
)


_CASES_DIR = Path(__file__).resolve().parent / "thermopack" / "cases"


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_pa(value: float, unit: str) -> float:
    unit = unit.strip().lower()
    if unit in {"pa", "pascal", "pascals"}:
        return float(value)
    if unit == "bar":
        return float(bar_to_pa(value))
    if unit in {"atm", "atmosphere", "atmospheres"}:
        return float(atm_to_pa(value))
    if unit in {"psi", "psia"}:
        return float(psi_to_pa(value))
    raise ValueError(f"Unsupported pressure unit: {unit!r}")


def _parse_pressure(obj: Any) -> float:
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        return _to_pa(float(obj["value"]), str(obj.get("unit", "Pa")))
    raise TypeError(f"Invalid pressure format: {type(obj)}")


def _parse_temperature(obj: Any) -> float:
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        unit = str(obj.get("unit", "K")).strip().lower()
        value = float(obj["value"])
        if unit in {"k", "kelvin"}:
            return value
        if unit in {"c", "degc", "celsius"}:
            return value + 273.15
        if unit in {"f", "degf", "fahrenheit"}:
            return (value - 32.0) * 5.0 / 9.0 + 273.15
        raise ValueError(f"Unsupported temperature unit: {unit!r}")
    raise TypeError(f"Invalid temperature format: {type(obj)}")


def _parse_composition(entries: List[Dict[str, Any]]) -> Tuple[List[str], np.ndarray]:
    component_ids = [str(entry["id"]).strip() for entry in entries]
    z = np.array([float(entry["z"]) for entry in entries], dtype=float)
    z = z / float(np.sum(z))
    return component_ids, z


def _tol_get(tolerances: Dict[str, Any], key: str, default: float) -> float:
    return float(tolerances.get(key, default))


def _assert_optional_array_allclose(
    actual: Optional[Tuple[float, ...]],
    expected: Optional[np.ndarray],
    *,
    atol: float,
) -> None:
    if expected is None:
        return
    assert actual is not None
    np.testing.assert_allclose(np.array(actual, dtype=float), expected, atol=atol, rtol=0.0)


def _interpolate_curve_pressure(points: List[Dict[str, float]], temperature_k: float) -> Optional[float]:
    if not points:
        return None

    temperatures = np.array([point["temperature_k"] for point in points], dtype=float)
    pressures = np.array([point["pressure_pa"] for point in points], dtype=float)
    order = np.argsort(temperatures)
    temperatures = temperatures[order]
    pressures = pressures[order]

    if float(temperature_k) < float(temperatures[0]) or float(temperature_k) > float(temperatures[-1]):
        return None
    return float(np.interp(float(temperature_k), temperatures, pressures))


def _assert_curve_alignment(
    actual_points: List[Dict[str, float]],
    expected_points: List[Dict[str, float]],
    *,
    pressure_atol: float,
    min_fraction: float,
) -> None:
    if not expected_points:
        return

    comparable = 0
    within_tol = 0
    for expected in expected_points:
        interpolated = _interpolate_curve_pressure(actual_points, expected["temperature_k"])
        if interpolated is None:
            continue
        comparable += 1
        if abs(interpolated - expected["pressure_pa"]) <= pressure_atol:
            within_tol += 1

    assert comparable > 0, "No ThermoPack envelope points overlapped the simulated branch temperature range."
    assert float(within_tol) / float(comparable) >= float(min_fraction)


@dataclass(frozen=True)
class ThermoPackCase:
    case_id: str
    task: str
    temperature_k: float
    pressure_pa: Optional[float]
    component_ids: List[str]
    z: np.ndarray
    tolerances: Dict[str, Any]
    trace: Dict[str, Any]
    thermopack_options: Dict[str, Any]


def _load_cases() -> List[ThermoPackCase]:
    if not _CASES_DIR.exists():
        return []

    cases: List[ThermoPackCase] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        obj = _load_json(path)
        component_ids, z = _parse_composition(obj["composition"])
        pressure = obj.get("pressure")
        cases.append(
            ThermoPackCase(
                case_id=str(obj.get("case_id", path.stem)),
                task=str(obj["task"]).strip(),
                temperature_k=_parse_temperature(obj["temperature"]),
                pressure_pa=_parse_pressure(pressure) if pressure is not None else None,
                component_ids=component_ids,
                z=z,
                tolerances=obj.get("tolerances", {}) or {},
                trace=obj.get("trace", {}) or {},
                thermopack_options=obj.get("thermopack_options", {}) or {},
            )
        )
    return cases


_CASES = _load_cases()
if not _CASES:
    pytest.skip(
        f"No ThermoPack validation cases found at: {_CASES_DIR}. Add *.json case files to enable ThermoPack comparison tests.",
        allow_module_level=True,
    )

_THERMOPACK_AVAILABILITY = detect_thermopack_validation_backend()
if not _THERMOPACK_AVAILABILITY.available:
    pytest.skip(
        f"ThermoPack validation bridge unavailable: {_THERMOPACK_AVAILABILITY.reason}",
        allow_module_level=True,
    )

_THERMOPACK_BACKEND = load_thermopack_validation_backend()


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"{c.case_id}:{c.task}")
def test_vs_thermopack(case: ThermoPackCase) -> None:
    components_db = load_components()
    components = [components_db[component_id] for component_id in case.component_ids]
    eos = PengRobinsonEOS(components)

    composition_atol = _tol_get(case.tolerances, "composition_atol", 1e-3)
    pressure_atol = _tol_get(case.tolerances, "pressure_pa_atol", 5e4)

    if case.task == "pt_flash":
        assert case.pressure_pa is not None, "pt_flash requires pressure"

        actual = pt_flash(case.pressure_pa, case.temperature_k, case.z, components, eos)
        expected = _THERMOPACK_BACKEND.pt_flash(
            temperature_k=case.temperature_k,
            pressure_pa=case.pressure_pa,
            component_ids=case.component_ids,
            composition=case.z.tolist(),
            eos_name="Peng-Robinson",
            options=case.thermopack_options,
        )

        if expected.phase is not None:
            assert actual.phase == expected.phase
        if expected.vapor_fraction is not None:
            assert float(actual.vapor_fraction) == pytest.approx(float(expected.vapor_fraction), abs=1e-3)

        _assert_optional_array_allclose(
            actual.liquid_composition,
            None if expected.liquid_composition is None else np.array(expected.liquid_composition, dtype=float),
            atol=composition_atol,
        )
        _assert_optional_array_allclose(
            actual.vapor_composition,
            None if expected.vapor_composition is None else np.array(expected.vapor_composition, dtype=float),
            atol=composition_atol,
        )
        return

    if case.task == "bubble_point":
        actual = calculate_bubble_point(case.temperature_k, case.z, components, eos)
        expected = _THERMOPACK_BACKEND.bubble_point(
            temperature_k=case.temperature_k,
            component_ids=case.component_ids,
            composition=case.z.tolist(),
            eos_name="Peng-Robinson",
            options=case.thermopack_options,
        )
        assert float(actual.pressure) == pytest.approx(float(expected.pressure_pa), abs=pressure_atol)
        _assert_optional_array_allclose(
            actual.vapor_composition,
            None if expected.vapor_composition is None else np.array(expected.vapor_composition, dtype=float),
            atol=composition_atol,
        )
        return

    if case.task == "dew_point":
        actual = calculate_dew_point(case.temperature_k, case.z, components, eos)
        expected = _THERMOPACK_BACKEND.dew_point(
            temperature_k=case.temperature_k,
            component_ids=case.component_ids,
            composition=case.z.tolist(),
            eos_name="Peng-Robinson",
            options=case.thermopack_options,
        )
        assert float(actual.pressure) == pytest.approx(float(expected.pressure_pa), abs=pressure_atol)
        _assert_optional_array_allclose(
            actual.liquid_composition,
            None if expected.liquid_composition is None else np.array(expected.liquid_composition, dtype=float),
            atol=composition_atol,
        )
        return

    if case.task == "phase_envelope":
        trace_method = str(case.trace.get("method", "fixed_grid")).strip().lower()
        if trace_method == "continuation_dev":
            trace_method = "continuation"
        t_min = _parse_temperature(case.trace["temperature_min"]) if "temperature_min" in case.trace else None
        t_max = _parse_temperature(case.trace["temperature_max"]) if "temperature_max" in case.trace else None
        n_points = int(case.trace.get("n_points", 120))

        if trace_method == "fixed_grid":
            traced = trace_phase_envelope(
                composition=case.z,
                components=components,
                eos=eos,
                T_min=float(t_min if t_min is not None else case.temperature_k - 50.0),
                T_max=float(t_max if t_max is not None else case.temperature_k + 50.0),
                n_points=n_points,
            )
            bubble_actual = [
                {"temperature_k": float(T), "pressure_pa": float(P)}
                for T, P in zip(traced.bubble_T, traced.bubble_P)
            ]
            dew_actual = [
                {"temperature_k": float(T), "pressure_pa": float(P)}
                for T, P in zip(traced.dew_T, traced.dew_P)
            ]
            critical_actual = None if traced.critical_point is None else {
                "temperature_k": float(traced.critical_point[0]),
                "pressure_pa": float(traced.critical_point[1]),
            }
            cdb_actual = None if traced.cricondenbar is None else {
                "temperature_k": float(traced.cricondenbar[0]),
                "pressure_pa": float(traced.cricondenbar[1]),
            }
            cdt_actual = None if traced.cricondentherm is None else {
                "temperature_k": float(traced.cricondentherm[0]),
                "pressure_pa": float(traced.cricondentherm[1]),
            }
        elif trace_method == "continuation":
            traced = trace_envelope_continuation(
                temperatures=np.linspace(
                    float(t_min if t_min is not None else case.temperature_k - 50.0),
                    float(t_max if t_max is not None else case.temperature_k + 50.0),
                    n_points,
                    dtype=float,
                ).tolist(),
                composition=case.z,
                components=components,
                eos=eos,
            )
            bubble_actual = [
                {"temperature_k": float(state.temperature), "pressure_pa": float(state.pressure)}
                for state in traced.bubble_states
            ]
            dew_actual = [
                {"temperature_k": float(state.temperature), "pressure_pa": float(state.pressure)}
                for state in traced.dew_states
            ]
            critical_actual = None if traced.critical_state is None else {
                "temperature_k": float(traced.critical_state.temperature),
                "pressure_pa": float(traced.critical_state.pressure),
            }
            all_points = bubble_actual + dew_actual + ([critical_actual] if critical_actual is not None else [])
            cdb_actual = None if not all_points else max(all_points, key=lambda point: point["pressure_pa"])
            cdt_actual = None if not all_points else max(all_points, key=lambda point: point["temperature_k"])
        else:
            raise ValueError(f"Unsupported trace method: {trace_method!r}")

        expected = _THERMOPACK_BACKEND.phase_envelope(
            component_ids=case.component_ids,
            composition=case.z.tolist(),
            eos_name="Peng-Robinson",
            temperature_min_k=t_min,
            temperature_max_k=t_max,
            n_points=n_points,
            options=case.thermopack_options,
        )

        key_pressure_atol = _tol_get(case.tolerances, "key_pressure_pa_atol", 5.0e5)
        key_temperature_atol = _tol_get(case.tolerances, "key_temperature_k_atol", 1.0)
        curve_pressure_atol = _tol_get(case.tolerances, "curve_pressure_pa_atol", 7.5e5)
        curve_point_fraction_min = _tol_get(case.tolerances, "curve_point_fraction_min", 0.8)

        if expected.critical_point is not None:
            assert critical_actual is not None
            assert critical_actual["temperature_k"] == pytest.approx(
                expected.critical_point.temperature_k,
                abs=key_temperature_atol,
            )
            assert critical_actual["pressure_pa"] == pytest.approx(
                expected.critical_point.pressure_pa,
                abs=key_pressure_atol,
            )

        if expected.cricondenbar is not None:
            assert cdb_actual is not None
            assert cdb_actual["temperature_k"] == pytest.approx(
                expected.cricondenbar.temperature_k,
                abs=key_temperature_atol,
            )
            assert cdb_actual["pressure_pa"] == pytest.approx(
                expected.cricondenbar.pressure_pa,
                abs=key_pressure_atol,
            )

        if expected.cricondentherm is not None:
            assert cdt_actual is not None
            assert cdt_actual["temperature_k"] == pytest.approx(
                expected.cricondentherm.temperature_k,
                abs=key_temperature_atol,
            )
            assert cdt_actual["pressure_pa"] == pytest.approx(
                expected.cricondentherm.pressure_pa,
                abs=key_pressure_atol,
            )

        bubble_expected = [
            {"temperature_k": float(point.temperature_k), "pressure_pa": float(point.pressure_pa)}
            for point in expected.bubble_curve
        ]
        dew_expected = [
            {"temperature_k": float(point.temperature_k), "pressure_pa": float(point.pressure_pa)}
            for point in expected.dew_curve
        ]
        _assert_curve_alignment(
            bubble_actual,
            bubble_expected,
            pressure_atol=curve_pressure_atol,
            min_fraction=curve_point_fraction_min,
        )
        _assert_curve_alignment(
            dew_actual,
            dew_expected,
            pressure_atol=curve_pressure_atol,
            min_fraction=curve_point_fraction_min,
        )
        return

    raise ValueError(f"Unknown ThermoPack case task: {case.task!r}")
