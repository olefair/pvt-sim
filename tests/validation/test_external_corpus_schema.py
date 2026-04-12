"""Schema-level tests for the external saturation-validation corpus."""

from __future__ import annotations

from pathlib import Path

from pvtcore.validation.external_corpus import (
    ExternalAcquisitionManifest,
    LabC7PlusSaturationAnchor,
    LiteratureVLETieLineAnchor,
    PureComponentSaturationAnchor,
    load_external_acquisition_manifest,
    load_external_anchor_case,
)


_EXTERNAL_DATA_DIR = Path(__file__).resolve().parent / "external_data"
_CASES_DIR = _EXTERNAL_DATA_DIR / "cases"
_TEMPLATE_DIR = _EXTERNAL_DATA_DIR / "templates"
_MANIFEST_PATH = _EXTERNAL_DATA_DIR / "acquisition_manifest.json"


def test_external_corpus_templates_validate() -> None:
    template_expectations = {
        "pure_component_saturation_template.json": PureComponentSaturationAnchor,
        "literature_vle_tieline_template.json": LiteratureVLETieLineAnchor,
        "lab_c7plus_saturation_template.json": LabC7PlusSaturationAnchor,
    }

    for filename, expected_type in template_expectations.items():
        case = load_external_anchor_case(_TEMPLATE_DIR / filename)
        assert isinstance(case, expected_type)


def test_external_corpus_case_files_validate() -> None:
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
    case_ids = {case.case_id for case in cases}

    assert expected_case_ids.issubset(case_ids)
    assert any(isinstance(case, PureComponentSaturationAnchor) for case in cases)
    assert any(isinstance(case, LiteratureVLETieLineAnchor) for case in cases)


def test_external_acquisition_manifest_validates() -> None:
    manifest = load_external_acquisition_manifest(_MANIFEST_PATH)

    assert isinstance(manifest, ExternalAcquisitionManifest)

    ids = {entry.planned_case_id for entry in manifest.entries}
    assert "jced_2000_c1_co2_c3_vle" in ids
    assert "lab_gas_condensate_c7plus_dew_anchor" in ids


def test_external_acquisition_manifest_excludes_promoted_pure_component_batches() -> None:
    manifest = load_external_acquisition_manifest(_MANIFEST_PATH)
    planned_ids = {entry.planned_case_id for entry in manifest.entries}

    assert "nist_c1_saturation_batch" not in planned_ids
    assert "nist_c2_saturation_batch" not in planned_ids
    assert "nist_c3_saturation_batch" not in planned_ids
    assert "nist_c4_saturation_batch" not in planned_ids
    assert "nist_c5_saturation_batch" not in planned_ids
    assert "nist_c6_saturation_batch" not in planned_ids
    assert "nist_co2_saturation_batch" not in planned_ids
    assert "jced_2015_methane_binary_vle" not in planned_ids
