import json
from pathlib import Path

import numpy as np
import pytest

from pvtcore.core.errors import ConfigurationError
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
                "lumping": {"enabled": True, "n_groups": 4, "method": "contiguous"},
            },
            "correlations": {"critical_props": "riazi_daubert_1987"},
            "eos": {
                "model": "PR",
                "mixing_rule": "vdW1",
                "kij": {"overrides": [{"pair": ["CO2", "C7+"], "kij": 0.12}]},
            },
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


def test_schema_rejects_unsupported_lumping_method() -> None:
    doc = _example_doc()
    doc["fluid"]["plus_fraction"]["lumping"]["method"] = "whitson"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(doc)


def test_schema_rejects_unsupported_correlation() -> None:
    doc = _example_doc()
    doc["fluid"]["correlations"]["critical_props"] = "kesler_lee_1976"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(doc)


def test_repo_tbp_example_characterizes() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    example_path = repo_root / "examples" / "tbp_fluid_definition.json"

    loaded = load_fluid_definition(example_path)
    res = characterize_from_schema(loaded)

    assert res.plus_fraction is not None
    assert np.isclose(float(res.composition.sum()), 1.0)
