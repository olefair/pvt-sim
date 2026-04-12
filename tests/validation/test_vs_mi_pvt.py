"""
Cross-check tests against MI-PVT reference outputs.

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
   - MI-PVT expected outputs (pressure, V, x, y, phase, etc.)

3) pytest will load each case and compare PVT-SIM outputs vs MI within
   tolerances specified in the case file.

Important boundary:
- PT-flash and envelope-style comparisons may be cross-checked here.
- Bubble and dew pressures are validated by independent equation-based
  benchmarks and are intentionally non-authoritative in this MI-PVT harness.

If no case files exist yet, these tests are skipped (suite remains green).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

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


# -----------------------------------------------------------------------------
# Case model + loaders
# -----------------------------------------------------------------------------

_CASES_DIR = Path(__file__).resolve().parent / "mi_pvt" / "cases"

# MI UI labels -> our component IDs
_MI_TO_PVTSIM_COMPONENT_ID = {
    "N2": "N2",
    "H2S": "H2S",
    "CO2": "CO2",
    "C1": "C1",
    "C2": "C2",
    "C3": "C3",
    "iC4": "iC4",
    "iC5": "iC5",
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
_LINEAR_COMPONENT_RE = re.compile(r"^(?P<prefix>[ni]?C)(?P<carbon>\d+)$", re.IGNORECASE)


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
        if unit in {"c", "degc", "celsius"}:
            return float(obj["value"]) + 273.15
        if unit in {"f", "degf", "fahrenheit"}:
            return (float(obj["value"]) - 32.0) * 5.0 / 9.0 + 273.15
        raise ValueError(f"Unsupported temperature unit: {unit!r}")
    raise TypeError(f"Invalid temperature format: {type(obj)}")


def _normalize_mi_component_id(mi_id: str) -> str | None:
    stripped = str(mi_id).strip()
    mapped = _MI_TO_PVTSIM_COMPONENT_ID.get(stripped)
    if mapped is not None or stripped in _MI_TO_PVTSIM_COMPONENT_ID:
        return mapped

    upper = stripped.upper()
    if upper in {"N2", "CO2", "H2S"}:
        return upper

    match = _LINEAR_COMPONENT_RE.fullmatch(stripped)
    if match is None:
        return None

    prefix = match.group("prefix").lower()
    carbon = str(int(match.group("carbon")))
    if prefix == "ic":
        return f"iC{carbon}"
    if prefix in {"nc", "c"}:
        return f"C{carbon}"
    return None


def _parse_composition(entries: List[Dict[str, Any]]) -> Tuple[List[str], np.ndarray]:
    """
    entries: [{"id": "C1", "z": 0.8}, ...]
    Returns:
      (component_ids, z_array)
    """
    ids: List[str] = []
    zs: List[float] = []
    for e in entries:
        mi_id = str(e["id"]).strip()
        mapped = _normalize_mi_component_id(mi_id)
        if mapped is None:
            raise ValueError(
                f"MI component {mi_id!r} cannot be mapped to the current PVT-SIM DB yet. "
                f"(If this is a heavy lump, wait until pseudo-components exist.)"
            )
        ids.append(mapped)
        zs.append(float(e["z"]))

    z = np.array(zs, dtype=float)
    if not np.isfinite(z).all():
        raise ValueError("Composition contains non-finite values")

    s = float(z.sum())
    if abs(s - 1.0) > 1e-10:
        # Normalize so MI rounding doesn't break tests
        z = z / s

    return ids, z


def _tol_get(tols: Dict[str, Any], key: str, default: float) -> float:
    v = tols.get(key, default)
    return float(v)


def _array_or_none(x: Any) -> Optional[np.ndarray]:
    if x is None:
        return None
    return np.array(x, dtype=float)


def _parse_phase_envelope_point(obj: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "temperature_k": _parse_temperature(obj["temperature"]),
        "pressure_pa": _parse_pressure(obj["pressure"]),
        "marker": str(obj.get("marker", "")).strip().lower() or None,
    }


def _parse_phase_envelope_points(entries: List[Dict[str, Any]] | None) -> List[Dict[str, Any]]:
    if not entries:
        return []
    return [_parse_phase_envelope_point(entry) for entry in entries]


def _find_marked_point(points: List[Dict[str, Any]], *markers: str) -> Optional[Dict[str, Any]]:
    wanted = {marker.strip().lower() for marker in markers}
    for point in points:
        if point.get("marker") in wanted:
            return point
    return None


def _extract_phase_envelope_key_points(
    expected: Dict[str, Any],
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    points = _parse_phase_envelope_points(expected.get("envelope_points"))

    critical = expected.get("critical_point")
    critical_point = _parse_phase_envelope_point(critical) if critical is not None else _find_marked_point(
        points,
        "crit",
        "critical",
    )

    cricondenbar = expected.get("cricondenbar")
    cricondenbar_point = (
        _parse_phase_envelope_point(cricondenbar)
        if cricondenbar is not None
        else _find_marked_point(points, "pmax", "cricondenbar")
    )

    cricondentherm = expected.get("cricondentherm")
    cricondentherm_point = (
        _parse_phase_envelope_point(cricondentherm)
        if cricondentherm is not None
        else _find_marked_point(points, "tmax", "cricondentherm")
    )

    return critical_point, cricondenbar_point, cricondentherm_point


def _split_phase_envelope_points(expected: Dict[str, Any]) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if expected.get("bubble_curve") and expected.get("dew_curve"):
        bubble = _parse_phase_envelope_points(expected.get("bubble_curve"))
        dew = _parse_phase_envelope_points(expected.get("dew_curve"))
        return (
            sorted(bubble, key=lambda point: point["temperature_k"]),
            sorted(dew, key=lambda point: point["temperature_k"]),
        )

    ordered = _parse_phase_envelope_points(expected.get("envelope_points"))
    if len(ordered) < 3:
        return [], []

    idx_pmax = int(np.argmax([point["pressure_pa"] for point in ordered]))
    dew = sorted(ordered[: idx_pmax + 1], key=lambda point: point["temperature_k"])
    bubble = sorted(ordered[idx_pmax + 1 :], key=lambda point: point["temperature_k"])
    return bubble, dew


def _interpolate_curve_pressure(points: List[Dict[str, Any]], temperature_k: float) -> Optional[float]:
    if not points:
        return None

    temperatures = np.array([point["temperature_k"] for point in points], dtype=float)
    pressures = np.array([point["pressure_pa"] for point in points], dtype=float)
    order = np.argsort(temperatures)
    temperatures = temperatures[order]
    pressures = pressures[order]

    if len(temperatures) == 1:
        if abs(float(temperatures[0]) - float(temperature_k)) <= 1e-12:
            return float(pressures[0])
        return None

    if float(temperature_k) < float(temperatures[0]) or float(temperature_k) > float(temperatures[-1]):
        return None

    return float(np.interp(float(temperature_k), temperatures, pressures))


def _assert_optional_key_point(
    actual: Optional[Dict[str, float]],
    expected: Optional[Dict[str, Any]],
    *,
    temperature_atol: float,
    pressure_atol: float,
) -> None:
    if expected is None:
        return
    assert actual is not None
    assert float(actual["temperature_k"]) == pytest.approx(float(expected["temperature_k"]), abs=temperature_atol)
    assert float(actual["pressure_pa"]) == pytest.approx(float(expected["pressure_pa"]), abs=pressure_atol)


def _assert_curve_alignment(
    actual_points: List[Dict[str, float]],
    expected_points: List[Dict[str, Any]],
    *,
    pressure_atol: float,
    min_fraction: float,
) -> None:
    if not expected_points:
        return
    assert actual_points, "Expected curve points were provided, but the simulator produced no matching curve."

    comparable = 0
    within_tol = 0
    for expected in expected_points:
        interpolated = _interpolate_curve_pressure(actual_points, float(expected["temperature_k"]))
        if interpolated is None:
            continue
        comparable += 1
        if abs(interpolated - float(expected["pressure_pa"])) <= pressure_atol:
            within_tol += 1

    assert comparable > 0, "No expected MI envelope points overlapped the simulated branch temperature range."
    assert float(within_tol) / float(comparable) >= float(min_fraction)


def _assert_optional_composition(
    actual: Any,
    expected: Any,
    *,
    atol: float,
) -> None:
    """Assert a composition only when the case file provides one."""
    exp = _array_or_none(expected)
    if exp is None:
        return
    np.testing.assert_allclose(
        np.array(actual, dtype=float),
        exp,
        atol=atol,
        rtol=0.0,
    )


@dataclass(frozen=True)
class MICase:
    case_id: str
    task: str  # "pt_flash" | "bubble_point" | "dew_point" | "phase_envelope"
    temperature_k: float
    pressure_pa: Optional[float]
    mi_composition: List[Dict[str, Any]]
    component_ids: Optional[List[str]]
    z: Optional[np.ndarray]
    expected: Dict[str, Any]
    tolerances: Dict[str, Any]
    trace: Dict[str, Any]
    runtime_skip_reason: Optional[str]


def _load_cases() -> List[MICase]:
    if not _CASES_DIR.exists():
        return []

    paths = sorted(_CASES_DIR.glob("*.json"))
    cases: List[MICase] = []

    for p in paths:
        obj = _load_json(p)

        case_id = obj.get("case_id", p.stem)
        task = obj["task"].strip()

        T = _parse_temperature(obj["temperature"])
        P = obj.get("pressure", None)
        P_pa = _parse_pressure(P) if P is not None else None

        mi_composition = obj["composition"]
        runtime_composition = obj.get("runtime_composition", mi_composition)
        runtime_supported = bool(obj.get("runtime_supported", True))

        comp_ids: Optional[List[str]] = None
        z: Optional[np.ndarray] = None
        runtime_skip_reason = str(obj.get("runtime_skip_reason", "")).strip() or None
        try:
            comp_ids, z = _parse_composition(runtime_composition)
        except ValueError as exc:
            if runtime_supported:
                raise
            runtime_skip_reason = runtime_skip_reason or str(exc)

        expected = obj.get("expected", {}) or {}
        tolerances = obj.get("tolerances", {}) or {}
        trace = obj.get("trace", {}) or {}

        cases.append(
            MICase(
                case_id=case_id,
                task=task,
                temperature_k=T,
                pressure_pa=P_pa,
                mi_composition=mi_composition,
                component_ids=comp_ids,
                z=z,
                expected=expected,
                tolerances=tolerances,
                trace=trace,
                runtime_skip_reason=runtime_skip_reason,
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


@pytest.mark.parametrize("case", _CASES, ids=lambda c: f"{c.case_id}:{c.task}")
def test_vs_mi_pvt(case: MICase) -> None:
    if case.runtime_skip_reason is not None:
        pytest.skip(f"Case {case.case_id} is archived only until runtime mapping exists: {case.runtime_skip_reason}")

    assert case.component_ids is not None
    assert case.z is not None

    comps_db = load_components()

    components = [comps_db[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(components)

    if case.task == "phase_envelope":
        expected_points = _parse_phase_envelope_points(case.expected.get("envelope_points"))
        critical_expected, cdb_expected, cdt_expected = _extract_phase_envelope_key_points(case.expected)
        bubble_expected, dew_expected = _split_phase_envelope_points(case.expected)

        if not expected_points and critical_expected is None and cdb_expected is None and cdt_expected is None:
            pytest.skip(f"Case {case.case_id} has no expected phase-envelope outputs yet.")

        trace_method = str(case.trace.get("method", "fixed_grid")).strip().lower()
        if trace_method == "continuation_dev":
            trace_method = "continuation"
        if trace_method not in {"fixed_grid", "continuation"}:
            raise ValueError(f"Unsupported phase-envelope trace method: {trace_method!r}")

        t_min = _parse_temperature(case.trace["temperature_min"]) if "temperature_min" in case.trace else None
        t_max = _parse_temperature(case.trace["temperature_max"]) if "temperature_max" in case.trace else None
        if t_min is None or t_max is None:
            if not expected_points:
                raise ValueError(
                    f"Case {case.case_id} must define trace.temperature_min / temperature_max when no envelope_points exist."
                )
            temperatures = np.array([point["temperature_k"] for point in expected_points], dtype=float)
            if t_min is None:
                t_min = float(np.min(temperatures))
            if t_max is None:
                t_max = float(np.max(temperatures))

        n_points = int(case.trace.get("n_points", max(80, len(expected_points) * 3 if expected_points else 80)))

        if trace_method == "fixed_grid":
            traced = trace_phase_envelope(
                composition=case.z,
                components=components,
                eos=eos,
                T_min=float(t_min),
                T_max=float(t_max),
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
        else:
            continuation = trace_envelope_continuation(
                temperatures=np.linspace(float(t_min), float(t_max), int(n_points), dtype=float).tolist(),
                composition=case.z,
                components=components,
                eos=eos,
            )
            bubble_actual = [
                {"temperature_k": float(state.temperature), "pressure_pa": float(state.pressure)}
                for state in continuation.bubble_states
            ]
            dew_actual = [
                {"temperature_k": float(state.temperature), "pressure_pa": float(state.pressure)}
                for state in continuation.dew_states
            ]
            critical_actual = None if continuation.critical_state is None else {
                "temperature_k": float(continuation.critical_state.temperature),
                "pressure_pa": float(continuation.critical_state.pressure),
            }
            cdb_actual = None
            cdt_actual = None
            all_points = bubble_actual + dew_actual + ([critical_actual] if critical_actual is not None else [])
            if all_points:
                cdb_actual = max(all_points, key=lambda point: float(point["pressure_pa"]))
                cdt_actual = max(all_points, key=lambda point: float(point["temperature_k"]))

        key_pressure_atol = _tol_get(case.tolerances, "key_pressure_pa_atol", 5.0e5)
        key_temperature_atol = _tol_get(case.tolerances, "key_temperature_k_atol", 1.0)
        curve_pressure_atol = _tol_get(case.tolerances, "curve_pressure_pa_atol", 7.5e5)
        curve_point_fraction_min = _tol_get(case.tolerances, "curve_point_fraction_min", 0.8)

        _assert_optional_key_point(
            critical_actual,
            critical_expected,
            temperature_atol=key_temperature_atol,
            pressure_atol=key_pressure_atol,
        )
        _assert_optional_key_point(
            cdb_actual,
            cdb_expected,
            temperature_atol=key_temperature_atol,
            pressure_atol=key_pressure_atol,
        )
        _assert_optional_key_point(
            cdt_actual,
            cdt_expected,
            temperature_atol=key_temperature_atol,
            pressure_atol=key_pressure_atol,
        )
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

    if case.task in {"bubble_point", "dew_point"}:
        pytest.skip(
            "Bubble/dew baselines are equation-based; MI-PVT is only a secondary cross-check for non-scalar surfaces."
        )

    if case.task == "pt_flash":
        assert case.pressure_pa is not None, "pt_flash requires pressure"

        res = pt_flash(case.pressure_pa, case.temperature_k, case.z, components, eos)

        # If expected outputs are missing, skip (case file is incomplete)
        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        # --- Phase ---
        exp_phase = case.expected.get("phase", None)
        if exp_phase is not None:
            assert res.phase == exp_phase

        # --- Vapor fraction ---
        exp_V = case.expected.get("vapor_fraction", None)
        if exp_V is not None:
            V_atol = _tol_get(case.tolerances, "vapor_fraction_atol", 1e-3)
            assert float(res.vapor_fraction) == pytest.approx(float(exp_V), abs=V_atol)

        # --- Compositions (optional) ---
        exp_x = _array_or_none(case.expected.get("x", None))
        exp_y = _array_or_none(case.expected.get("y", None))
        xy_atol = _tol_get(case.tolerances, "composition_atol", 1e-3)

        if exp_x is not None:
            np.testing.assert_allclose(
                np.array(res.liquid_composition, dtype=float),
                exp_x,
                atol=xy_atol,
                rtol=0.0,
            )
        if exp_y is not None:
            np.testing.assert_allclose(
                np.array(res.vapor_composition, dtype=float),
                exp_y,
                atol=xy_atol,
                rtol=0.0,
            )

        return

    if case.task == "bubble_point":
        bp = calculate_bubble_point(case.temperature_k, case.z, components, eos)

        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        exp_P = case.expected.get("pressure_pa", None)
        if exp_P is None:
            pytest.skip(f"Case {case.case_id} missing expected pressure_pa.")

        P_atol = _tol_get(case.tolerances, "pressure_pa_atol", 5e4)  # ~0.5 bar
        assert float(bp.pressure) == pytest.approx(float(exp_P), abs=P_atol)
        xy_atol = _tol_get(case.tolerances, "composition_atol", 1e-3)
        _assert_optional_composition(
            bp.vapor_composition,
            case.expected.get("y"),
            atol=xy_atol,
        )
        return

    if case.task == "dew_point":
        dp = calculate_dew_point(case.temperature_k, case.z, components, eos)

        if not case.expected:
            pytest.skip(f"Case {case.case_id} has no expected outputs yet.")

        exp_P = case.expected.get("pressure_pa", None)
        if exp_P is None:
            pytest.skip(f"Case {case.case_id} missing expected pressure_pa.")

        P_atol = _tol_get(case.tolerances, "pressure_pa_atol", 5e4)  # ~0.5 bar
        assert float(dp.pressure) == pytest.approx(float(exp_P), abs=P_atol)
        xy_atol = _tol_get(case.tolerances, "composition_atol", 1e-3)
        _assert_optional_composition(
            dp.liquid_composition,
            case.expected.get("x"),
            atol=xy_atol,
        )
        return

    raise ValueError(f"Unknown task: {case.task!r}")
