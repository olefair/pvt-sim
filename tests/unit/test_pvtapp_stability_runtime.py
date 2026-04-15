"""Focused runtime-contract coverage for standalone stability analysis."""

from __future__ import annotations

import math

from pvtapp.job_runner import run_calculation, validate_runtime_config
from pvtapp.schemas import RunConfig, RunStatus, StabilityAnalysisResult


def _stability_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "Stability Analysis Runtime Contract",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "stability_analysis",
            "eos_type": "peng_robinson",
            "stability_analysis_config": {
                "pressure_pa": 3.0e6,
                "temperature_k": 300.0,
                "feed_phase": "liquid",
                "use_gdem": True,
                "n_random_trials": 1,
                "random_seed": 7,
                "max_eos_failures_per_trial": 4,
                "pressure_unit": "bar",
                "temperature_unit": "C",
            },
        }
    )


def test_validate_runtime_config_accepts_stability_analysis() -> None:
    validate_runtime_config(_stability_config())


def test_run_calculation_executes_stability_analysis_with_trial_diagnostics() -> None:
    result = run_calculation(config=_stability_config(), write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None
    assert result.stability_analysis_result is not None

    stability = result.stability_analysis_result
    assert stability.stable is False
    assert stability.best_unstable_trial_kind is not None
    assert math.isfinite(stability.tpd_min)
    assert stability.tpd_min < 0.0
    assert stability.phase_regime == "two_phase"
    assert stability.physical_state_hint == "two_phase"
    assert stability.physical_state_hint_basis == "two_phase_regime"
    assert stability.physical_state_hint_confidence == "high"
    assert stability.requested_feed_phase.value == "liquid"
    assert stability.reference_root_used == "liquid"
    assert set(stability.feed_composition) == {"C1", "C10"}

    assert stability.vapor_like_trial is not None
    assert stability.liquid_like_trial is not None

    for trial in (stability.vapor_like_trial, stability.liquid_like_trial):
        assert math.isfinite(trial.tpd)
        assert trial.seed_attempts >= 1
        assert trial.candidate_seed_count >= trial.seed_attempts
        assert trial.n_phi_calls == sum(seed.n_phi_calls for seed in trial.seed_results)
        assert trial.n_eos_failures == sum(seed.n_eos_failures for seed in trial.seed_results)
        assert trial.total_iterations == sum(seed.iterations for seed in trial.seed_results)
        assert trial.best_seed.seed_index == trial.best_seed_index
        assert trial.best_seed.seed_label in trial.candidate_seed_labels


def test_run_calculation_marks_supercritical_single_phase_as_ambiguous_when_evidence_is_mixed() -> None:
    result = run_calculation(
        config=RunConfig.model_validate(
            {
                "run_name": "Stability Analysis Ambiguous Single Phase",
                "composition": {
                    "components": [
                        {"component_id": "C1", "mole_fraction": 1.0},
                    ]
                },
                "calculation_type": "stability_analysis",
                "eos_type": "peng_robinson",
                "stability_analysis_config": {
                    "pressure_pa": 1.0e7,
                    "temperature_k": 320.0,
                    "feed_phase": "auto",
                },
            }
        ),
        write_artifacts=False,
    )

    assert result.status == RunStatus.COMPLETED
    assert result.stability_analysis_result is not None
    stability = result.stability_analysis_result
    assert stability.stable is True
    assert stability.phase_regime == "single_phase"
    assert stability.physical_state_hint == "single_phase_ambiguous"
    assert stability.physical_state_hint_basis == "supercritical_guard"
    assert stability.physical_state_hint_confidence == "low"
    assert stability.liquid_root_z is not None
    assert stability.vapor_root_z is not None
    assert stability.root_gap is not None
    assert abs(stability.root_gap) < 1.0e-12
    assert stability.average_reduced_pressure is not None


def test_stability_result_schema_accepts_legacy_reference_phase_field() -> None:
    result = StabilityAnalysisResult.model_validate(
        {
            "stable": True,
            "tpd_min": 0.0,
            "pressure_pa": 1.0e5,
            "temperature_k": 300.0,
            "requested_feed_phase": "auto",
            "resolved_feed_phase": "auto_selected:vapor",
            "resolved_reference_phase": "vapor",
            "feed_composition": {"C1": 1.0},
        }
    )

    assert result.reference_root_used == "vapor"
    assert result.resolved_reference_phase == "vapor"
    assert result.phase_regime == "single_phase"
    assert result.physical_state_hint == "single_phase_ambiguous"
    assert result.physical_state_hint_basis == "heuristic_fallback"
    assert result.physical_state_hint_confidence == "low"
