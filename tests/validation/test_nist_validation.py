"""NIST-anchored pure-component saturation validation.

Consolidated from:
- test_nist_vapor_pressure.py (convergence, physical behavior, acentric factor,
  Clausius-Clapeyron, regression)
- test_external_pure_component_saturation.py (external corpus NIST anchors)

Two test functions:
1. test_nist_vapor_pressure_physical_and_regression — parametrized PR EOS checks
2. test_pure_component_saturation_matches_nist — parametrized external-corpus checks
"""

from __future__ import annotations

from pathlib import Path
from typing import Tuple

import numpy as np
import pytest

from pvtcore.core.units import pa_to_bar
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components
from pvtcore.validation import PureComponentSaturationAnchor, load_external_anchor_case


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calculate_vapor_pressure(
    component_id: str,
    temperature_k: float,
    components: dict,
) -> Tuple[float, bool]:
    component = components[component_id]
    eos = PengRobinsonEOS([component])
    z = np.array([1.0])
    try:
        result = calculate_bubble_point(
            temperature=temperature_k,
            composition=z,
            components=[component],
            eos=eos,
            tolerance=1e-9,
            max_iterations=100,
        )
        return result.pressure, result.converged
    except Exception:
        return float('nan'), False


# ---------------------------------------------------------------------------
# 1) PR EOS vapor-pressure parametrized checks
# ---------------------------------------------------------------------------

_PR_COMPONENTS = ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C10"]
_TR_RANGE = [0.6, 0.65, 0.7, 0.75, 0.8, 0.85]

_REGRESSION_CASES = [
    ("C1", 452100),
    ("C3", 298100),
    ("C7", 122400),
]


@pytest.mark.parametrize("component_id", _PR_COMPONENTS)
def test_nist_vapor_pressure_physical_and_regression(component_id: str) -> None:
    """PR EOS vapor pressure: convergence, monotonicity, Pc bound, omega, CC linearity, regression."""
    components = load_components()
    comp = components[component_id]

    pressures = []
    for Tr in _TR_RANGE:
        T = Tr * comp.Tc
        P, converged = _calculate_vapor_pressure(component_id, T, components)
        assert converged, f"{component_id} did not converge at Tr={Tr}"
        assert np.isfinite(P) and P > 0
        assert P < comp.Pc, f"{component_id} Psat exceeds Pc at Tr={Tr}"
        pressures.append(P)

    for i in range(1, len(pressures)):
        assert pressures[i] > pressures[i - 1], (
            f"{component_id}: non-monotonic at Tr={_TR_RANGE[i]}"
        )

    P_07, _ = _calculate_vapor_pressure(component_id, 0.7 * comp.Tc, components)
    omega_calc = -np.log10(P_07 / comp.Pc) - 1.0
    assert abs(omega_calc - comp.omega) < 0.05, (
        f"{component_id}: omega mismatch {omega_calc:.4f} vs {comp.omega:.4f}"
    )

    ln_P = np.log(np.array(pressures[1:]))
    inv_T = 1.0 / np.array([Tr * comp.Tc for Tr in _TR_RANGE[1:]])
    coeffs = np.polyfit(inv_T, ln_P, 1)
    fitted = np.polyval(coeffs, inv_T)
    ss_res = np.sum((ln_P - fitted) ** 2)
    ss_tot = np.sum((ln_P - np.mean(ln_P)) ** 2)
    r_sq = 1 - ss_res / ss_tot
    assert r_sq > 0.999, f"{component_id}: Clausius-Clapeyron R²={r_sq:.6f}"

    for reg_id, expected_P in _REGRESSION_CASES:
        if reg_id == component_id:
            assert abs(P_07 - expected_P) / expected_P < 0.01, (
                f"{component_id} regression: {P_07:.0f} vs {expected_P}"
            )


# ---------------------------------------------------------------------------
# 2) External corpus NIST anchor checks
# ---------------------------------------------------------------------------

_CASES_DIR = Path(__file__).resolve().parent / "external_data" / "cases"
_PRESSURE_RTOL_BY_COMPONENT = {"CO2": 0.04}
_DEFAULT_PRESSURE_RTOL = 0.02


def _load_pure_component_cases() -> list[PureComponentSaturationAnchor]:
    cases: list[PureComponentSaturationAnchor] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, PureComponentSaturationAnchor):
            cases.append(case)
    return cases


@pytest.mark.parametrize("case", _load_pure_component_cases(), ids=lambda c: c.case_id)
def test_pure_component_saturation_matches_nist(case: PureComponentSaturationAnchor) -> None:
    """Pure-component bubble/dew pressures should stay close to NIST anchors."""
    components = load_components()
    component = components[case.component_id]
    eos = PengRobinsonEOS([component])
    z = [1.0]
    pressure_rtol = _PRESSURE_RTOL_BY_COMPONENT.get(case.component_id, _DEFAULT_PRESSURE_RTOL)

    for point in case.points:
        temperature_k = float(point.temperature.value)
        expected_pressure_bar = float(point.pressure.value)

        bubble = calculate_bubble_point(temperature_k, z, [component], eos)
        dew = calculate_dew_point(temperature_k, z, [component], eos)

        assert bubble.converged
        assert dew.converged

        bubble_pressure_bar = float(pa_to_bar(bubble.pressure))
        dew_pressure_bar = float(pa_to_bar(dew.pressure))

        assert bubble_pressure_bar == pytest.approx(expected_pressure_bar, rel=pressure_rtol)
        assert dew_pressure_bar == pytest.approx(expected_pressure_bar, rel=pressure_rtol)
        assert bubble_pressure_bar == pytest.approx(dew_pressure_bar, abs=1e-6)
