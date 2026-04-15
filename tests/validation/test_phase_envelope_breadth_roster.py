from __future__ import annotations

import json
import math
from pathlib import Path


_ROSTER_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "data" / "phase_envelope_breadth_roster.json"
)


def test_phase_envelope_breadth_roster_is_normalized_and_complete() -> None:
    raw = json.loads(_ROSTER_PATH.read_text(encoding="utf-8"))

    component_ids = {str(entry["component_id"]) for entry in raw["component_order"]}
    cases = list(raw["cases"])

    assert len(cases) == 17
    assert [int(case["tag"]) for case in cases] == list(range(1, 18))
    assert len({case["name"] for case in cases}) == len(cases)

    for case in cases:
        composition = {str(key): float(value) for key, value in dict(case["composition"]).items()}
        assert composition
        assert set(composition).issubset(component_ids)
        assert math.isclose(sum(composition.values()), 1.0, rel_tol=0.0, abs_tol=1.0e-12)
