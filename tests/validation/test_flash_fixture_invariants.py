"""Fixture-based PT flash invariants and regression checks."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.pt_flash import pt_flash

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FLUIDS_DIR = FIXTURES_DIR / "fluids"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.mark.parametrize("fluid_id", [
    "dry_gas",
    "black_oil",
    "co2_rich_gas",
])
def test_flash_fixture_invariants_and_regressions(fluid_id: str) -> None:
    fluid_path = FLUIDS_DIR / f"{fluid_id}.json"
    expected_path = EXPECTED_DIR / f"{fluid_id}_pt_flash.json"

    fluid = _load_json(fluid_path)
    expected = _load_json(expected_path)

    assert fluid["fluid_id"] == expected["fluid_id"]

    component_ids = [c["component_id"] for c in fluid["components"]]
    z = np.array([c["mole_fraction"] for c in fluid["components"]], dtype=float)

    components_db = load_components()
    comps = [components_db[cid] for cid in component_ids]
    eos = PengRobinsonEOS(comps)

    assert len(fluid["pt_points"]) == len(expected["points"])

    for point, exp in zip(fluid["pt_points"], expected["points"]):
        assert float(point["pressure_pa"]) == pytest.approx(exp["pressure_pa"], rel=0, abs=0)
        assert float(point["temperature_k"]) == pytest.approx(exp["temperature_k"], rel=0, abs=0)

        res = pt_flash(
            pressure=float(point["pressure_pa"]),
            temperature=float(point["temperature_k"]),
            composition=z,
            components=comps,
            eos=eos,
            binary_interaction=None,
        )

        assert res.certificate is not None
        assert res.certificate.passed is True

        assert res.phase == exp["phase"]
        assert float(res.vapor_fraction) == pytest.approx(exp["vapor_fraction"], rel=0, abs=1e-6)

        np.testing.assert_allclose(
            res.liquid_composition,
            np.array(exp["liquid_composition"], dtype=float),
            rtol=0,
            atol=1e-6,
        )
        np.testing.assert_allclose(
            res.vapor_composition,
            np.array(exp["vapor_composition"], dtype=float),
            rtol=0,
            atol=1e-6,
        )
        np.testing.assert_allclose(
            res.K_values,
            np.array(exp["K_values"], dtype=float),
            rtol=0,
            atol=1e-6,
        )
