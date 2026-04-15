"""Automated robustness matrix for the standalone stability-analysis workflow.

This matrix is intentionally broader than the focused widget/runtime contract
tests. It exercises representative fluid families, EOS variants, feed-phase
policies, and persisted-run replay to catch solver-surface regressions before
they show up as user-facing failures.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import pytest

from pvtapp.job_runner import load_run_config, load_run_result, rerun_saved_run, run_calculation
from pvtapp.schemas import RunConfig, RunStatus


@dataclass(frozen=True)
class StabilityMatrixCase:
    """Single representative runtime case for the standalone stability surface."""

    case_id: str
    composition_payload: dict
    pressure_pa: float
    temperature_k: float
    eos_type: str
    feed_phase: str


def _fixture_payload(fluid_id: str) -> dict:
    fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "fluids" / f"{fluid_id}.json"
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return {"components": payload["components"]}


def _plus_gas_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0060},
            {"component_id": "CO2", "mole_fraction": 0.0250},
            {"component_id": "C1", "mole_fraction": 0.6400},
            {"component_id": "C2", "mole_fraction": 0.1100},
            {"component_id": "C3", "mole_fraction": 0.0750},
            {"component_id": "iC4", "mole_fraction": 0.0250},
            {"component_id": "C4", "mole_fraction": 0.0250},
            {"component_id": "iC5", "mole_fraction": 0.0180},
            {"component_id": "C5", "mole_fraction": 0.0160},
            {"component_id": "C6", "mole_fraction": 0.0140},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.0460,
            "mw_plus_g_per_mol": 128.25512173913043,
            "sg_plus_60f": 0.7571304347826087,
            "characterization_preset": "manual",
            "max_carbon_number": 18,
            "split_method": "pedersen",
            "split_mw_model": "paraffin",
            "lumping_enabled": True,
            "lumping_n_groups": 2,
        },
    }


def _plus_oil_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0021},
            {"component_id": "CO2", "mole_fraction": 0.0187},
            {"component_id": "C1", "mole_fraction": 0.3478},
            {"component_id": "C2", "mole_fraction": 0.0712},
            {"component_id": "C3", "mole_fraction": 0.0934},
            {"component_id": "iC4", "mole_fraction": 0.0302},
            {"component_id": "nC4", "mole_fraction": 0.0431},
            {"component_id": "iC5", "mole_fraction": 0.0276},
            {"component_id": "nC5", "mole_fraction": 0.0418},
            {"component_id": "C6", "mole_fraction": 0.0574},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.2667,
            "mw_plus_g_per_mol": 119.78759868766404,
            "sg_plus_60f": 0.82,
            "characterization_preset": "auto",
            "max_carbon_number": 20,
            "split_method": "pedersen",
            "split_mw_model": "table",
            "lumping_enabled": True,
            "lumping_n_groups": 6,
        },
    }


def _inline_pseudo_payload() -> dict:
    return {
        "components": [
            {"component_id": "C1", "mole_fraction": 0.55},
            {"component_id": "PSEUDO_PLUS", "mole_fraction": 0.45},
        ],
        "inline_components": [
            {
                "component_id": "PSEUDO_PLUS",
                "name": "Pseudo+",
                "formula": "Pseudo+",
                "molecular_weight_g_per_mol": 110.0,
                "critical_temperature_k": 650.0,
                "critical_pressure_pa": 2.2e6,
                "omega": 0.55,
            }
        ],
    }


def _build_config(case: StabilityMatrixCase) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": case.case_id,
            "composition": case.composition_payload,
            "calculation_type": "stability_analysis",
            "eos_type": case.eos_type,
            "stability_analysis_config": {
                "pressure_pa": case.pressure_pa,
                "temperature_k": case.temperature_k,
                "feed_phase": case.feed_phase,
                "use_gdem": True,
                "n_random_trials": 1,
                "random_seed": 7,
                "max_eos_failures_per_trial": 4,
            },
        }
    )


def _matrix_cases() -> list[StabilityMatrixCase]:
    cases: list[StabilityMatrixCase] = []

    fixture_points = {
        "dry_gas": [
            {"pressure_pa": 1.0e5, "temperature_k": 200.0, "label": "vapor_low_p"},
            {"pressure_pa": 5.0e5, "temperature_k": 200.0, "label": "two_phase_low_t"},
        ],
        "co2_rich_gas": [
            {"pressure_pa": 1.0e5, "temperature_k": 300.0, "label": "vapor_low_p"},
            {"pressure_pa": 5.0e6, "temperature_k": 300.0, "label": "two_phase_mid_p"},
        ],
        "black_oil": [
            {"pressure_pa": 1.0e5, "temperature_k": 300.0, "label": "two_phase_low_p"},
            {"pressure_pa": 1.0e6, "temperature_k": 300.0, "label": "two_phase_mid_p"},
        ],
    }
    for fluid_id, points in fixture_points.items():
        payload = _fixture_payload(fluid_id)
        for point in points:
            for eos_type in ("peng_robinson", "pr78", "srk"):
                for feed_phase in ("auto", "liquid", "vapor"):
                    cases.append(
                        StabilityMatrixCase(
                            case_id=f"{fluid_id}-{point['label']}-{eos_type}-{feed_phase}",
                            composition_payload=payload,
                            pressure_pa=point["pressure_pa"],
                            temperature_k=point["temperature_k"],
                            eos_type=eos_type,
                            feed_phase=feed_phase,
                        )
                    )

    extra_cases = {
        "gas_condensate_plus": (_plus_gas_payload(), 3.0e6, 320.0),
        "volatile_oil_plus": (_plus_oil_payload(), 8.0e6, 360.0),
        "inline_pseudo": (_inline_pseudo_payload(), 5.0e6, 350.0),
    }
    for fluid_id, (payload, pressure_pa, temperature_k) in extra_cases.items():
        for eos_type in ("peng_robinson", "pr78", "srk"):
            for feed_phase in ("auto", "liquid", "vapor"):
                cases.append(
                    StabilityMatrixCase(
                        case_id=f"{fluid_id}-matrix-{eos_type}-{feed_phase}",
                        composition_payload=payload,
                        pressure_pa=pressure_pa,
                        temperature_k=temperature_k,
                        eos_type=eos_type,
                        feed_phase=feed_phase,
                    )
                )

    return cases


@pytest.mark.parametrize("case", _matrix_cases(), ids=lambda case: case.case_id)
def test_stability_runtime_matrix_executes_with_surface_invariants(case: StabilityMatrixCase) -> None:
    """Ensure representative standalone stability runs complete and stay self-consistent."""
    config = _build_config(case)

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None
    assert result.stability_analysis_result is not None

    stability = result.stability_analysis_result
    assert math.isfinite(stability.tpd_min)
    assert sum(stability.feed_composition.values()) == pytest.approx(1.0, abs=1.0e-9)
    assert stability.reference_root_used in {"liquid", "vapor"}
    assert stability.phase_regime in {"single_phase", "two_phase"}
    assert stability.physical_state_hint in {
        "two_phase",
        "single_phase_vapor_like",
        "single_phase_liquid_like",
        "single_phase_ambiguous",
    }
    assert stability.physical_state_hint_basis in {
        "two_phase_regime",
        "direct_root_split",
        "saturation_window",
        "supercritical_guard",
        "no_boundary_guard",
        "heuristic_fallback",
    }
    assert stability.physical_state_hint_confidence in {"high", "medium", "low"}
    assert stability.vapor_like_trial is not None
    assert stability.liquid_like_trial is not None
    assert stability.tpd_min == pytest.approx(
        min(stability.vapor_like_trial.tpd, stability.liquid_like_trial.tpd),
        abs=1.0e-12,
    )

    if case.feed_phase == "auto":
        assert stability.resolved_feed_phase.endswith(stability.reference_root_used)
    else:
        assert stability.resolved_feed_phase == case.feed_phase
        assert stability.reference_root_used == case.feed_phase

    if stability.stable:
        assert stability.phase_regime == "single_phase"
        assert stability.physical_state_hint.startswith("single_phase_")
        assert stability.best_unstable_trial_kind is None
    else:
        assert stability.phase_regime == "two_phase"
        assert stability.physical_state_hint == "two_phase"
        assert stability.physical_state_hint_basis == "two_phase_regime"
        assert stability.physical_state_hint_confidence == "high"
        assert stability.best_unstable_trial_kind in {"vapor_like", "liquid_like"}

    for trial in (stability.vapor_like_trial, stability.liquid_like_trial):
        assert math.isfinite(trial.tpd)
        assert trial.seed_attempts >= 1
        assert trial.candidate_seed_count >= trial.seed_attempts
        assert 0 <= trial.best_seed_index < len(trial.seed_results)
        assert trial.best_seed.seed_label in trial.candidate_seed_labels
        assert trial.best_seed.tpd == pytest.approx(trial.tpd, abs=1.0e-12)
        assert trial.n_phi_calls == sum(seed.n_phi_calls for seed in trial.seed_results)
        assert trial.n_eos_failures == sum(seed.n_eos_failures for seed in trial.seed_results)
        assert trial.total_iterations == sum(seed.iterations for seed in trial.seed_results)
        assert all(seed.kind == trial.kind for seed in trial.seed_results)
        assert all(seed.trial_phase == trial.trial_phase for seed in trial.seed_results)


@pytest.mark.parametrize(
    "case",
    [
        StabilityMatrixCase(
            case_id="dry_gas-replay",
            composition_payload=_fixture_payload("dry_gas"),
            pressure_pa=5.0e5,
            temperature_k=200.0,
            eos_type="srk",
            feed_phase="auto",
        ),
        StabilityMatrixCase(
            case_id="black_oil-replay",
            composition_payload=_fixture_payload("black_oil"),
            pressure_pa=1.0e6,
            temperature_k=300.0,
            eos_type="pr78",
            feed_phase="liquid",
        ),
        StabilityMatrixCase(
            case_id="gas_condensate_plus-replay",
            composition_payload=_plus_gas_payload(),
            pressure_pa=3.0e6,
            temperature_k=320.0,
            eos_type="peng_robinson",
            feed_phase="vapor",
        ),
        StabilityMatrixCase(
            case_id="inline_pseudo-replay",
            composition_payload=_inline_pseudo_payload(),
            pressure_pa=5.0e6,
            temperature_k=350.0,
            eos_type="peng_robinson",
            feed_phase="auto",
        ),
    ],
    ids=lambda case: case.case_id,
)
def test_stability_saved_run_replay_preserves_runtime_surface(
    tmp_path: Path,
    case: StabilityMatrixCase,
) -> None:
    """Ensure saved standalone stability runs reload and rerun cleanly."""
    output_dir = tmp_path / case.case_id
    config = _build_config(case)

    result = run_calculation(config=config, output_dir=output_dir, write_artifacts=True)

    assert result.status == RunStatus.COMPLETED
    run_dirs = sorted(path for path in output_dir.iterdir() if path.is_dir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    loaded_result = load_run_result(run_dir)
    loaded_config = load_run_config(run_dir)
    assert loaded_result is not None
    assert loaded_config is not None
    assert loaded_result.status == RunStatus.COMPLETED
    assert loaded_result.stability_analysis_result is not None
    assert loaded_config.calculation_type.value == "stability_analysis"
    assert loaded_config.stability_analysis_config is not None
    assert loaded_config.stability_analysis_config.feed_phase.value == case.feed_phase
    assert loaded_result.stability_analysis_result.tpd_min == pytest.approx(
        result.stability_analysis_result.tpd_min,
        abs=1.0e-12,
    )

    replayed = rerun_saved_run(
        run_dir,
        output_dir=tmp_path / f"{case.case_id}-rerun",
        write_artifacts=True,
        run_name=f"{case.case_id}-rerun",
    )

    assert replayed.status == RunStatus.COMPLETED
    assert replayed.run_id != result.run_id
    assert replayed.run_name == f"{case.case_id}-rerun"
    assert replayed.stability_analysis_result is not None
    assert replayed.stability_analysis_result.reference_root_used in {"liquid", "vapor"}
    assert replayed.stability_analysis_result.phase_regime in {"single_phase", "two_phase"}
    assert replayed.stability_analysis_result.physical_state_hint in {
        "two_phase",
        "single_phase_vapor_like",
        "single_phase_liquid_like",
        "single_phase_ambiguous",
    }
    assert replayed.stability_analysis_result.physical_state_hint_basis in {
        "two_phase_regime",
        "direct_root_split",
        "saturation_window",
        "supercritical_guard",
        "no_boundary_guard",
        "heuristic_fallback",
    }
    assert replayed.stability_analysis_result.physical_state_hint_confidence in {"high", "medium", "low"}
    assert math.isfinite(replayed.stability_analysis_result.tpd_min)
