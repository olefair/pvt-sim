"""External literature and corpus schema validation.

Consolidated from:
- test_external_literature_vle.py (tie-line bubble-point alignment)
- test_external_corpus_schema.py (template, case-file, manifest validation)

Two test functions:
1. test_literature_tieline_bubble_point_alignment — parametrized VLE tie-line checks
2. test_external_corpus_schema_and_manifest — schema + manifest integrity
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.models.component import load_components
from pvtcore.validation import LiteratureVLETieLineAnchor, load_external_anchor_case
from pvtcore.validation.external_corpus import (
    ExternalAcquisitionManifest,
    LabC7PlusSaturationAnchor,
    PureComponentSaturationAnchor,
    load_external_acquisition_manifest,
)


_EXTERNAL_DATA_DIR = Path(__file__).resolve().parent / "external_data"
_CASES_DIR = _EXTERNAL_DATA_DIR / "cases"
_TEMPLATE_DIR = _EXTERNAL_DATA_DIR / "templates"
_MANIFEST_PATH = _EXTERNAL_DATA_DIR / "acquisition_manifest.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    raise ValueError(f"Unsupported pressure unit: {unit!r}")


def _load_literature_cases() -> list[LiteratureVLETieLineAnchor]:
    cases: list[LiteratureVLETieLineAnchor] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, LiteratureVLETieLineAnchor):
            cases.append(case)
    return cases


# ---------------------------------------------------------------------------
# 1) Literature tie-line bubble-point alignment
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", _load_literature_cases(), ids=lambda c: c.case_id)
def test_literature_tieline_bubble_point_alignment(case: LiteratureVLETieLineAnchor) -> None:
    """Reported liquid tie lines should be close to the production bubble-point solve."""
    components_db = load_components()
    component_ids = [entry.component_id for entry in case.liquid_composition]
    comp_list = [components_db[cid] for cid in component_ids]
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


# ---------------------------------------------------------------------------
# 2) Corpus schema + manifest integrity
# ---------------------------------------------------------------------------

def test_external_corpus_schema_and_manifest() -> None:
    """Templates parse, case files validate, and manifest is internally consistent."""
    # Templates
    template_expectations = {
        "pure_component_saturation_template.json": PureComponentSaturationAnchor,
        "literature_vle_tieline_template.json": LiteratureVLETieLineAnchor,
        "lab_c7plus_saturation_template.json": LabC7PlusSaturationAnchor,
    }
    for filename, expected_type in template_expectations.items():
        case = load_external_anchor_case(_TEMPLATE_DIR / filename)
        assert isinstance(case, expected_type)

    # Case files
    case_paths = sorted(_CASES_DIR.glob("*.json"))
    cases = [load_external_anchor_case(path) for path in case_paths]

    expected_case_ids = {
        "nist_c1_saturation_batch",
        "nist_c2_saturation_batch",
        "nist_c3_saturation_batch",
        "nist_c4_saturation_batch",
        "nist_c5_saturation_batch",
        "nist_c6_saturation_batch",
        "nist_co2_saturation_batch",
        "thermoml_2015_ch4_c3_tieline_24361k_xch4_04857",
    }
    case_ids = {c.case_id for c in cases}
    assert expected_case_ids.issubset(case_ids)
    assert any(isinstance(c, PureComponentSaturationAnchor) for c in cases)
    assert any(isinstance(c, LiteratureVLETieLineAnchor) for c in cases)

    # Manifest
    manifest = load_external_acquisition_manifest(_MANIFEST_PATH)
    assert isinstance(manifest, ExternalAcquisitionManifest)
    ids = {entry.planned_case_id for entry in manifest.entries}
    assert "jced_2000_c1_co2_c3_vle" in ids
    assert "lab_gas_condensate_c7plus_dew_anchor" in ids

    # Promoted batches should not appear in manifest
    promoted = {
        "nist_c1_saturation_batch", "nist_c2_saturation_batch",
        "nist_c3_saturation_batch", "nist_c4_saturation_batch",
        "nist_c5_saturation_batch", "nist_c6_saturation_batch",
        "nist_co2_saturation_batch", "jced_2015_methane_binary_vle",
    }
    assert promoted.isdisjoint(ids)
