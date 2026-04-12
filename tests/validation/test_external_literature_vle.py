"""External literature VLE checks backed by the external corpus."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.models.component import load_components
from pvtcore.validation import LiteratureVLETieLineAnchor, load_external_anchor_case


_CASES_DIR = Path(__file__).resolve().parent / "external_data" / "cases"


def _pressure_to_pa(case: LiteratureVLETieLineAnchor) -> float:
    unit = case.pressure.unit.value
    value = float(case.pressure.value)
    if unit == "Pa":
        return value
    if unit == "kPa":
        return value * 1e3
    if unit == "MPa":
        return value * 1e6
    if unit == "bar":
        return value * 1e5
    raise ValueError(f"Unsupported pressure unit for literature tie-line test: {unit!r}")


def _load_literature_cases() -> list[LiteratureVLETieLineAnchor]:
    cases: list[LiteratureVLETieLineAnchor] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, LiteratureVLETieLineAnchor):
            cases.append(case)
    return cases


@pytest.mark.parametrize("case", _load_literature_cases(), ids=lambda case: case.case_id)
def test_literature_tieline_bubble_point_alignment(case: LiteratureVLETieLineAnchor) -> None:
    """Reported liquid tie lines should be close to the production bubble-point solve."""
    components_db = load_components()
    component_ids = [entry.component_id for entry in case.liquid_composition]
    comp_list = [components_db[component_id] for component_id in component_ids]
    eos = PengRobinsonEOS(comp_list)

    x = np.array([entry.mole_fraction for entry in case.liquid_composition], dtype=float)
    expected_y = np.array([entry.mole_fraction for entry in case.vapor_composition], dtype=float)
    expected_pressure_pa = _pressure_to_pa(case)

    result = calculate_bubble_point(
        temperature=float(case.temperature.value),
        composition=x,
        components=comp_list,
        eos=eos,
    )

    assert result.converged
    assert float(result.pressure) == pytest.approx(expected_pressure_pa, rel=0.03)
    np.testing.assert_allclose(
        np.asarray(result.vapor_composition, dtype=float),
        expected_y,
        atol=0.01,
        rtol=0.0,
    )
