"""Reference-style validation for standalone stability against fixture phase anchors.

These checks use the repo's existing fixture PT points and expected PT-flash
phase outcomes as the accuracy anchor for the desktop/runtime stability
surface. The goal is not just "the solver runs" but "the standalone stability
workflow agrees with the canonical phase-regime expectations already curated in
the repository."
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from pvtcore.stability.analysis import StabilityOptions

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FLUIDS_DIR = FIXTURES_DIR / "fluids"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("fluid_id", ["dry_gas", "co2_rich_gas", "black_oil"])
def test_standalone_stability_matches_fixture_phase_regimes(fluid_id: str) -> None:
    """Validate standalone stability against the repo's expected PT-flash phase anchors."""
    fluid = _load_json(FLUIDS_DIR / f"{fluid_id}.json")
    expected = _load_json(EXPECTED_DIR / f"{fluid_id}_pt_flash.json")

    tol = StabilityOptions().tpd_negative_tol
    composition_payload = {"components": fluid["components"]}

    assert len(fluid["pt_points"]) == len(expected["points"])
    for point, exp in zip(fluid["pt_points"], expected["points"], strict=True):
        pressure_pa = float(point["pressure_pa"])
        temperature_k = float(point["temperature_k"])
        expected_phase = exp["phase"]

        pt_flash_config = RunConfig.model_validate(
            {
                "run_name": f"{fluid_id}-ptflash-{point['label']}",
                "composition": composition_payload,
                "calculation_type": "pt_flash",
                "eos_type": "peng_robinson",
                "pt_flash_config": {
                    "pressure_pa": pressure_pa,
                    "temperature_k": temperature_k,
                },
            }
        )
        stability_config = RunConfig.model_validate(
            {
                "run_name": f"{fluid_id}-stability-{point['label']}",
                "composition": composition_payload,
                "calculation_type": "stability_analysis",
                "eos_type": "peng_robinson",
                "stability_analysis_config": {
                    "pressure_pa": pressure_pa,
                    "temperature_k": temperature_k,
                    "feed_phase": "auto",
                    "use_gdem": True,
                    "n_random_trials": 1,
                    "random_seed": 7,
                    "max_eos_failures_per_trial": 4,
                },
            }
        )

        pt_flash_result = run_calculation(config=pt_flash_config, write_artifacts=False)
        stability_result = run_calculation(config=stability_config, write_artifacts=False)

        assert pt_flash_result.status == RunStatus.COMPLETED
        assert stability_result.status == RunStatus.COMPLETED
        assert pt_flash_result.pt_flash_result is not None
        assert stability_result.stability_analysis_result is not None

        flash = pt_flash_result.pt_flash_result
        stability = stability_result.stability_analysis_result

        # First anchor: the app/runtime PT-flash path still matches the expected fixture phase.
        assert flash.phase == expected_phase

        # Second anchor: standalone stability classifies the same phase regime.
        if expected_phase == "two-phase":
            assert stability.stable is False
            assert stability.phase_regime == "two_phase"
            assert stability.physical_state_hint == "two_phase"
            assert stability.physical_state_hint_basis == "two_phase_regime"
            assert stability.physical_state_hint_confidence == "high"
            assert stability.tpd_min < -tol
            assert stability.best_unstable_trial_kind in {"vapor_like", "liquid_like"}
        else:
            assert stability.stable is True
            assert stability.phase_regime == "single_phase"
            assert stability.physical_state_hint.startswith("single_phase_")
            assert stability.physical_state_hint_basis in {
                "direct_root_split",
                "saturation_window",
                "supercritical_guard",
                "no_boundary_guard",
                "heuristic_fallback",
            }
            assert stability.physical_state_hint_confidence in {"high", "medium", "low"}
            assert stability.tpd_min >= -tol
            assert stability.best_unstable_trial_kind is None

        # The standalone surface should remain internally self-consistent.
        assert stability.vapor_like_trial is not None
        assert stability.liquid_like_trial is not None
        assert stability.tpd_min == pytest.approx(
            min(stability.vapor_like_trial.tpd, stability.liquid_like_trial.tpd),
            abs=1.0e-12,
        )
