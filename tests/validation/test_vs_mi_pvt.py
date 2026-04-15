"""
Regression/validation tests against MI-PVT reference outputs.

Canonical MI-PVT bundle location:
  tests/validation/mi_pvt/
    README.md
    mi_pvt_mixtures.md
    cases/*.json

Workflow:
1) Create one or more JSON case files under:
   tests/validation/mi_pvt/cases/*.json

2) Each case file stores:
   - inputs (T, P, composition, components)
   - task type (pt_flash / bubble_point / dew_point / phase_envelope)
   - MI-PVT expected outputs (pressure, V, x, y, phase, envelope points, etc.)

3) pytest will load each case and compare PVT-SIM outputs vs MI within
   tolerances specified in the case file.

If no case files exist yet, these tests are skipped (suite remains green).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import PhaseEnvelopePoint, PhaseEnvelopeResult, RunConfig, RunStatus
from pvtcore.core.units import atm_to_pa, bar_to_pa, psi_to_pa
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.models.component import load_components


# -----------------------------------------------------------------------------
# Case model + loaders
# -----------------------------------------------------------------------------

_CASES_DIR = Path(__file__).resolve().parent / "mi_pvt" / "cases"

# MI UI labels -> our component IDs
_MI_TO_PVTSIM_COMPONENT_ID = {
    "CO2": "CO2",
    "C1": "C1",
    "C2": "C2",
    "C3": "C3",
    "nC4": "C4",
    "C4": "C4",
    "nC5": "C5",
    "C5": "C5",
    "C6": "C6",
    # Heavy-lump labels exist in MI, but we do NOT support them yet in this repo snapshot.
    # When we add lump/pseudo components, we can extend this mapping.
    "C7-C12": None,
    "C13-C18": None,
    "C19-C26": None,
    "C27-C37": None,
    "C38-C85": None,
}


def _load_json(path: Path) -> Dict[str, Any]:
    import json

    return json.loads(path.read_text(encoding="utf-8"))


def _to_pa(value: float, unit: str) -> float:
    unit = unit.strip().lower()
    if unit in {"pa", "pascal", "pascals"}:
        return float(value)
    if unit in {"bar"}:
        return float(bar_to_pa(value))
    if unit in {"atm", "atmosphere", "atmospheres"}:
        return float(atm_to_pa(value))
    if unit in {"psi", "psia"}:
        return float(psi_to_pa(value))
    raise ValueError(f"Unsupported pressure unit: {unit!r}")


def _parse_pressure(obj: Any) -> float:
    """
    Accept either:
      - {"value": 250.0, "unit": "atm"}
      - 2.5e7  (assumed Pa)
    """
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        return _to_pa(obj["value"], obj.get("unit", "Pa"))
    raise TypeError(f"Invalid pressure format: {type(obj)}")


def _parse_temperature(obj: Any) -> float:
    """
    Accept either:
      - {"value": 373.0, "unit": "K"}
      - 373.0 (assumed K)
    """
    if isinstance(obj, (int, float)):
        return float(obj)
    if isinstance(obj, dict):
        unit = obj.get("unit", "K").strip().lower()
        if unit in {"k", "kelvin"}:
            return float(obj["value"])
        raise ValueError(f"Unsupported temperature unit: {unit!r}")
    raise TypeError(f"Invalid temperature format: {type(obj)}")


def _parse_composition(entries: Sequence[Dict[str, Any]]) -> Tuple[List[str], np.ndarray]:
    """
    entries: [{"id": "C1", "z": 0.8}, ...]
    Returns:
      (component_ids, z_array)
    """
    ids: List[str] = []
    zs: List[float] = []
    for entry in entries:
        mi_id = str(entry["id"]).strip()
        mapped = _MI_TO_PVTSIM_COMPONENT_ID.get(mi_id, None)
        if mapped is None:
            raise ValueError(
                f"MI component {mi_id!r} cannot be mapped to the current PVT-SIM DB yet. "
                f"(If this is a heavy lump, wait until pseudo-components exist.)"
            )
        ids.append(mapped)
        zs.append(float(entry["z"]))

    z = np.array(zs, dtype=float)
    if not np.isfinite(z).all():
        raise ValueError("Composition contains non-finite values")

    total = float(z.sum())
    if abs(total - 1.0) > 1.0e-10:
        z = z / total

    return ids, z


def _tol_get(tols: Dict[str, Any], key: str, default: float) -> float:
    return float(tols.get(key, default))


def _optional_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    raise TypeError(f"Invalid boolean field: {value!r}")


def _array_or_none(x: Any) -> Optional[np.ndarray]:
    if x is None:
        return None
    return np.array(x, dtype=float)


@dataclass(frozen=True)
class MIEnvelopePoint:
    temperature_k: float
    pressure_pa: float
    marker: Optional[str] = None


@dataclass(frozen=True)
class MICase:
    case_id: str
    task: str  # "pt_flash" | "bubble_point" | "dew_point" | "phase_envelope"
    temperature_k: float
    pressure_pa: Optional[float]
    component_ids: Optional[List[str]]
    z: Optional[np.ndarray]
    runtime_supported: bool
    runtime_skip_reason: Optional[str]
    trace: Dict[str, Any]
    expected: Dict[str, Any]
    tolerances: Dict[str, Any]


def _load_cases() -> List[MICase]:
    if not _CASES_DIR.exists():
        return []

    cases: List[MICase] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        if path.stem.endswith("_template") or "template" in path.stem:
            continue

        obj = _load_json(path)
        case_id = obj.get("case_id", path.stem)
        task = str(obj["task"]).strip()
        temperature_k = _parse_temperature(obj["temperature"])
        pressure_obj = obj.get("pressure")
        pressure_pa = _parse_pressure(pressure_obj) if pressure_obj is not None else None

        runtime_supported = _optional_bool(obj.get("runtime_supported"), default=True)
        runtime_skip_reason = obj.get("runtime_skip_reason")
        runtime_entries = obj.get("runtime_composition", obj["composition"])

        component_ids: Optional[List[str]]
        z: Optional[np.ndarray]
        if runtime_supported:
            component_ids, z = _parse_composition(runtime_entries)
        else:
            component_ids, z = None, None

        cases.append(
            MICase(
                case_id=str(case_id),
                task=task,
                temperature_k=temperature_k,
                pressure_pa=pressure_pa,
                component_ids=component_ids,
                z=z,
                runtime_supported=runtime_supported,
                runtime_skip_reason=runtime_skip_reason,
                trace=dict(obj.get("trace", {}) or {}),
                expected=dict(obj.get("expected", {}) or {}),
                tolerances=dict(obj.get("tolerances", {}) or {}),
            )
        )

    return cases


_CASES = _load_cases()
if not _CASES:
    pytest.skip(
        f"No MI-PVT reference cases found at: {_CASES_DIR}. "
        f"Add *.json case files to enable MI validation tests.",
        allow_module_level=True,
    )


def _parse_envelope_point(obj: Dict[str, Any]) -> MIEnvelopePoint:
    marker = obj.get("marker")
    return MIEnvelopePoint(
        temperature_k=_parse_temperature(obj["temperature"]),
        pressure_pa=_parse_pressure(obj["pressure"]),
        marker=None if marker in {None, ""} else str(marker).strip().lower(),
    )


def _parse_optional_key_point(obj: Any) -> Optional[MIEnvelopePoint]:
    if obj is None or obj == "":
        return None
    return _parse_envelope_point(obj)


def _expected_envelope_branches(expected: Dict[str, Any]) -> Tuple[Tuple[MIEnvelopePoint, ...], Tuple[MIEnvelopePoint, ...]]:
    bubble_entries = expected.get("bubble_curve")
    dew_entries = expected.get("dew_curve")
    if bubble_entries or dew_entries:
        bubble_curve = tuple(_parse_envelope_point(entry) for entry in (bubble_entries or []))
        dew_curve = tuple(_parse_envelope_point(entry) for entry in (dew_entries or []))
        return bubble_curve, dew_curve

    ordered_points = tuple(_parse_envelope_point(entry) for entry in expected.get("envelope_points", []))
    if not ordered_points:
        return tuple(), tuple()

    split_index = next((idx for idx, point in enumerate(ordered_points) if point.marker == "pmax"), None)
    if split_index is None:
        split_index = int(np.argmax(np.array([point.pressure_pa for point in ordered_points], dtype=float)))

    dew_curve = ordered_points[: split_index + 1]
    bubble_curve = ordered_points[split_index:]
    return bubble_curve, dew_curve


def _runtime_trace_config(case: MICase) -> Dict[str, Any]:
    trace = dict(case.trace or {})
    config: Dict[str, Any] = {
        "method": str(trace.get("method", "continuation")).strip().lower(),
        "n_points": int(trace.get("n_points", 96)),
    }
    if "temperature_min" in trace:
        config["temperature_min_k"] = _parse_temperature(trace["temperature_min"])
    if "temperature_max" in trace:
        config["temperature_max_k"] = _parse_temperature(trace["temperature_max"])

    if "temperature_min_k" not in config or "temperature_max_k" not in config:
        bubble_curve, dew_curve = _expected_envelope_branches(case.expected)
        temperatures = [point.temperature_k for point in (*bubble_curve, *dew_curve)]
        if temperatures:
            config.setdefault("temperature_min_k", float(min(temperatures)))
            config.setdefault("temperature_max_k", float(max(temperatures)))
        else:
            config.setdefault("temperature_min_k", max(100.0, case.temperature_k - 50.0))
            config.setdefault("temperature_max_k", case.temperature_k + 50.0)

    return config


def _run_phase_envelope_case(case: MICase) -> PhaseEnvelopeResult:
    assert case.component_ids is not None
    assert case.z is not None

    trace = _runtime_trace_config(case)
    config = RunConfig.model_validate(
        {
            "run_name": case.case_id,
            "composition": {
                "components": [
                    {"component_id": component_id, "mole_fraction": float(z)}
                    for component_id, z in zip(case.component_ids, case.z, strict=True)
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": trace["temperature_min_k"],
                "temperature_max_k": trace["temperature_max_k"],
                "n_points": trace["n_points"],
                "tracing_method": trace["method"],
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
) -> Tuple[np.ndarray, np.ndarray]:
    ordered = sorted(points, key=lambda point: float(getattr(point, temperature_attr)))
    unique_temperatures: List[float] = []
    unique_pressures: List[float] = []
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
    reference_point: MIEnvelopePoint | None,
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
    reference_points: Sequence[MIEnvelopePoint],
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


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"{c.case_id}:{c.task}")
def test_vs_mi_pvt(case: MICase) -> None:
    if not case.runtime_supported:
        reason = case.runtime_skip_reason or "MI-PVT capture is archived-only until the runtime feed surface matches it."
        pytest.skip(reason)

    assert case.component_ids is not None
    assert case.z is not None

    comps_db = load_components()
    components = [comps_db[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(components)

    if case.task == "pt_flash":
        assert case.pressure_pa is not None, "pt_flash requires pressure"

        res = pt_flash(case.pressure_pa, case.temperature_k, case.z, components, eos)

        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        exp_phase = case.expected.get("phase")
        if exp_phase is not None:
            assert res.phase == exp_phase

        exp_vapor_fraction = case.expected.get("vapor_fraction")
        if exp_vapor_fraction is not None:
            vapor_fraction_atol = _tol_get(case.tolerances, "vapor_fraction_atol", 1.0e-3)
            assert float(res.vapor_fraction) == pytest.approx(float(exp_vapor_fraction), abs=vapor_fraction_atol)

        exp_x = _array_or_none(case.expected.get("x"))
        exp_y = _array_or_none(case.expected.get("y"))
        composition_atol = _tol_get(case.tolerances, "composition_atol", 1.0e-3)

        if exp_x is not None:
            np.testing.assert_allclose(
                np.array(res.liquid_composition, dtype=float),
                exp_x,
                atol=composition_atol,
                rtol=0.0,
            )
        if exp_y is not None:
            np.testing.assert_allclose(
                np.array(res.vapor_composition, dtype=float),
                exp_y,
                atol=composition_atol,
                rtol=0.0,
            )
        return

    if case.task == "bubble_point":
        bubble = calculate_bubble_point(case.temperature_k, case.z, components, eos)

        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        exp_pressure = case.expected.get("pressure_pa")
        if exp_pressure is None:
            pytest.skip(f"Case {case.case_id} missing expected pressure_pa.")

        pressure_atol = _tol_get(case.tolerances, "pressure_pa_atol", 5.0e4)
        assert float(bubble.pressure) == pytest.approx(float(exp_pressure), abs=pressure_atol)
        return

    if case.task == "dew_point":
        dew = calculate_dew_point(case.temperature_k, case.z, components, eos)

        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        exp_pressure = case.expected.get("pressure_pa")
        if exp_pressure is None:
            pytest.skip(f"Case {case.case_id} missing expected pressure_pa.")

        pressure_atol = _tol_get(case.tolerances, "pressure_pa_atol", 5.0e4)
        assert float(dew.pressure) == pytest.approx(float(exp_pressure), abs=pressure_atol)
        return

    if case.task == "phase_envelope":
        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        runtime = _run_phase_envelope_case(case)
        _assert_no_runtime_right_tail(runtime)

        key_pressure_pa_atol = _tol_get(case.tolerances, "key_pressure_pa_atol", 1.5e6)
        key_temperature_k_atol = _tol_get(case.tolerances, "key_temperature_k_atol", 3.0)
        curve_pressure_pa_atol = _tol_get(case.tolerances, "curve_pressure_pa_atol", 2.0e6)
        curve_point_fraction_min = _tol_get(case.tolerances, "curve_point_fraction_min", 0.65)

        _assert_key_point_close(
            "critical_point",
            runtime.critical_point,
            _parse_optional_key_point(case.expected.get("critical_point")),
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )
        _assert_key_point_close(
            "cricondenbar",
            runtime.cricondenbar,
            _parse_optional_key_point(case.expected.get("cricondenbar")),
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )
        _assert_key_point_close(
            "cricondentherm",
            runtime.cricondentherm,
            _parse_optional_key_point(case.expected.get("cricondentherm")),
            pressure_pa_atol=key_pressure_pa_atol,
            temperature_k_atol=key_temperature_k_atol,
        )

        bubble_curve, dew_curve = _expected_envelope_branches(case.expected)
        if bubble_curve:
            _assert_branch_alignment(
                "bubble",
                runtime.bubble_curve,
                bubble_curve,
                pressure_pa_atol=curve_pressure_pa_atol,
                curve_point_fraction_min=curve_point_fraction_min,
            )
        if dew_curve:
            _assert_branch_alignment(
                "dew",
                runtime.dew_curve,
                dew_curve,
                pressure_pa_atol=curve_pressure_pa_atol,
                curve_point_fraction_min=curve_point_fraction_min,
            )
        return

    raise ValueError(f"Unknown task: {case.task!r}")
