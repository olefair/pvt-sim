"""External pure-component saturation checks against NIST anchors."""

from __future__ import annotations

from pathlib import Path

import pytest

from pvtcore.core.units import pa_to_bar
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components
from pvtcore.validation import PureComponentSaturationAnchor, load_external_anchor_case


_CASES_DIR = Path(__file__).resolve().parent / "external_data" / "cases"
_PRESSURE_RTOL_BY_COMPONENT = {
    "CO2": 0.04,
}
_DEFAULT_PRESSURE_RTOL = 0.02


def _load_pure_component_cases() -> list[PureComponentSaturationAnchor]:
    cases: list[PureComponentSaturationAnchor] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, PureComponentSaturationAnchor):
            cases.append(case)
    return cases


@pytest.mark.parametrize("case", _load_pure_component_cases(), ids=lambda case: case.case_id)
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
