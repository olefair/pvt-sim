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
   - task type (pt_flash / bubble_point / dew_point)
   - MI-PVT expected outputs (pressure, V, x, y, phase, etc.)

3) pytest will load each case and compare PVT-SIM outputs vs MI within
   tolerances specified in the case file.

If no case files exist yet, these tests are skipped (suite remains green).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pytest

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
        mapped = _MI_TO_PVTSIM_COMPONENT_ID.get(mi_id, None)
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


@dataclass(frozen=True)
class MICase:
    case_id: str
    task: str  # "pt_flash" | "bubble_point" | "dew_point"
    temperature_k: float
    pressure_pa: Optional[float]
    component_ids: List[str]
    z: np.ndarray
    expected: Dict[str, Any]
    tolerances: Dict[str, Any]


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

        comp_ids, z = _parse_composition(obj["composition"])

        expected = obj.get("expected", {}) or {}
        tolerances = obj.get("tolerances", {}) or {}

        cases.append(
            MICase(
                case_id=case_id,
                task=task,
                temperature_k=T,
                pressure_pa=P_pa,
                component_ids=comp_ids,
                z=z,
                expected=expected,
                tolerances=tolerances,
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
    comps_db = load_components()

    components = [comps_db[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(components)

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
        return

    raise ValueError(f"Unknown task: {case.task!r}")
