import json
from pathlib import Path

import numpy as np
import pytest

from pvtcore.characterization import KatzSplitResult, LohrenzSplitResult
from pvtcore.core.errors import ConfigurationError, ValidationError
from pvtcore.io import characterize_from_schema, load_fluid_definition


def _example_doc() -> dict:
    return {
        "fluid": {
            "name": "Example Fluid",
            "basis": "mole",
            "components": [
                {"id": "CO2", "z": 0.02},
                {"id": "C1", "z": 0.70},
                {"id": "C2", "z": 0.08},
                {"id": "C3", "z": 0.05},
                {"id": "C4", "z": 0.05},
                {"id": "C5", "z": 0.03},
                {"id": "C6", "z": 0.02},
            ],
            "plus_fraction": {
                "label": "C7+",
                "z_plus": 0.05,
                "cut_start": 7,
                "mw_plus_g_per_mol": 215.0,
                "sg_plus_60F": 0.85,
                "splitting": {
                    "method": "pedersen",
                    "max_carbon_number": 45,
                    "pedersen": {"mw_model": "MWn = 14n - 4"},
                },
                "lumping": {"enabled": True, "n_groups": 4},
            },
            "correlations": {"critical_props": "riazi_daubert_1987"},
            "eos": {
                "model": "PR",
                "mixing_rule": "vdW1",
                "kij": {"overrides": [{"pair": ["CO2", "C7+"], "kij": 0.12}]},
            },
        }
    }


def _tbp_example_doc() -> dict:
    return {
        "fluid": {
            "name": "TBP-backed Example Fluid",
            "basis": "mole",
            "components": [
                {"id": "CO2", "z": 0.02},
                {"id": "C1", "z": 0.70},
                {"id": "C2", "z": 0.08},
                {"id": "C3", "z": 0.05},
                {"id": "C4", "z": 0.05},
                {"id": "C5", "z": 0.03},
                {"id": "C6", "z": 0.02},
            ],
            "plus_fraction": {
                "label": "C7+",
                "cut_start": 7,
                "sg_plus_60F": 0.85,
                "tbp_data": {
                    "cuts": [
                        {"name": "C7", "z": 0.020, "mw": 96.0},
                        {"name": "C8", "z": 0.015, "mw": 110.0},
                        {"name": "C9", "z": 0.015, "mw": 124.0},
                    ]
                },
                "splitting": {
                    "method": "pedersen",
                    "max_carbon_number": 12,
                    "pedersen": {
                        "mw_model": "MWn = 14n - 4",
                        "solve_AB_from": "balances",
                    },
                },
                "lumping": {"enabled": False},
            },
            "correlations": {"critical_props": "riazi_daubert_1987"},
        }
    }


def test_characterize_from_schema_basic_and_kij_override() -> None:
    doc = _example_doc()
    res = characterize_from_schema(doc)

    assert np.isclose(float(res.composition.sum()), 1.0)
    assert res.lumping is not None  # enabled in schema

    # Expect resolved + 4 lumped pseudo-components
    assert len(res.component_ids) == 7 + 4

    idx_co2 = res.component_ids.index("CO2")
    pseudo_start = 7  # resolved count
    for j in range(pseudo_start, len(res.component_ids)):
        assert res.binary_interaction[idx_co2, j] == pytest.approx(0.12, abs=0.0)
        assert res.binary_interaction[j, idx_co2] == pytest.approx(0.12, abs=0.0)


def test_load_fluid_definition_json(tmp_path: Path) -> None:
    doc = _example_doc()
    path = tmp_path / "fluid.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    loaded = load_fluid_definition(path)
    res = characterize_from_schema(loaded)
    assert np.isclose(float(res.composition.sum()), 1.0)


def test_schema_rejects_non_mole_basis() -> None:
    doc = _example_doc()
    doc["fluid"]["basis"] = "mass"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(doc)


def test_schema_accepts_legacy_contiguous_lumping_method() -> None:
    doc = _example_doc()
    doc["fluid"]["plus_fraction"]["lumping"]["method"] = "contiguous"

    res = characterize_from_schema(doc)

    assert res.lumping is not None


def test_schema_rejects_unsupported_lumping_method() -> None:
    doc = _example_doc()
    doc["fluid"]["plus_fraction"]["lumping"]["method"] = "lee"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(doc)


@pytest.mark.parametrize(
    ("split_method", "expected_result_type"),
    [
        ("katz", KatzSplitResult),
        ("lohrenz", LohrenzSplitResult),
        ("lohrens", LohrenzSplitResult),
    ],
)
def test_schema_accepts_supported_plus_fraction_split_methods(
    split_method: str,
    expected_result_type: type,
) -> None:
    doc = _example_doc()
    doc["fluid"]["plus_fraction"]["splitting"]["method"] = split_method

    res = characterize_from_schema(doc)

    assert res.plus_fraction is not None
    assert np.isclose(float(res.composition.sum()), 1.0)
    assert isinstance(res.split_result, expected_result_type)


def test_schema_rejects_unsupported_correlation() -> None:
    doc = _example_doc()
    doc["fluid"]["correlations"]["critical_props"] = "kesler_lee_1976"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(doc)


def test_schema_derives_plus_fraction_inputs_from_tbp_cuts() -> None:
    doc = _tbp_example_doc()

    res = characterize_from_schema(doc)

    assert res.plus_fraction is not None
    assert res.plus_fraction.z_plus == pytest.approx(0.05)
    assert res.plus_fraction.mw_plus == pytest.approx(108.6)
    assert res.plus_fraction.sg_plus == pytest.approx(0.85)
    assert res.plus_fraction.n_start == 7
    assert np.isclose(float(res.composition.sum()), 1.0)


def test_schema_accepts_matching_explicit_aggregate_plus_values_with_tbp_cuts() -> None:
    doc = _tbp_example_doc()
    plus_fraction = doc["fluid"]["plus_fraction"]
    plus_fraction["z_plus"] = 0.05
    plus_fraction["mw_plus_g_per_mol"] = 108.6

    res = characterize_from_schema(doc)

    assert res.plus_fraction is not None
    assert res.plus_fraction.z_plus == pytest.approx(0.05)
    assert res.plus_fraction.mw_plus == pytest.approx(108.6)


def test_schema_rejects_tbp_z_plus_mismatch() -> None:
    doc = _tbp_example_doc()
    doc["fluid"]["plus_fraction"]["z_plus"] = 0.051

    with pytest.raises(ValidationError, match="fluid.plus_fraction.z_plus"):
        characterize_from_schema(doc)


def test_schema_rejects_tbp_mw_plus_mismatch() -> None:
    doc = _tbp_example_doc()
    doc["fluid"]["plus_fraction"]["mw_plus_g_per_mol"] = 120.0

    with pytest.raises(ValidationError, match="fluid.plus_fraction.mw_plus_g_per_mol"):
        characterize_from_schema(doc)


def test_schema_accepts_gapped_tbp_cuts() -> None:
    doc = _tbp_example_doc()
    doc["fluid"]["plus_fraction"]["tbp_data"]["cuts"] = [
        {"name": "C7", "z": 0.02, "mw": 96.0},
        {"name": "C9-C10", "z": 0.03, "mw": 130.0, "tb_k": 430.0},
    ]

    res = characterize_from_schema(doc)

    assert res.plus_fraction is not None
    assert res.plus_fraction.z_plus == pytest.approx(0.05)
    assert res.plus_fraction.mw_plus == pytest.approx((0.02 * 96.0 + 0.03 * 130.0) / 0.05)


@pytest.mark.parametrize(
    ("cut_name", "match_text"),
    [
        ("heavy", "must look like 'C7' or 'C7-C9'"),
        ("C6", "must not start below"),
    ],
)
def test_schema_rejects_invalid_tbp_cut_names(
    cut_name: str,
    match_text: str,
) -> None:
    doc = _tbp_example_doc()
    doc["fluid"]["plus_fraction"]["tbp_data"]["cuts"][0]["name"] = cut_name

    with pytest.raises(ValidationError, match=match_text):
        characterize_from_schema(doc)


def test_schema_accepts_fit_to_tbp_for_pedersen_characterization() -> None:
    doc = _tbp_example_doc()
    doc["fluid"]["plus_fraction"]["splitting"]["pedersen"]["solve_AB_from"] = "fit_to_tbp"

    res = characterize_from_schema(doc)

    assert res.split_result is not None
    assert res.split_result.solve_ab_from == "fit_to_tbp"
    assert res.split_result.tbp_cut_rms_relative_error is not None
    assert np.isclose(float(res.composition.sum()), 1.0)


def test_repo_tbp_example_characterizes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    example_path = repo_root / "examples" / "tbp_fluid_definition.json"

    loaded = load_fluid_definition(example_path)
    res = characterize_from_schema(loaded)

    assert res.plus_fraction is not None
    assert np.isclose(float(res.composition.sum()), 1.0)
