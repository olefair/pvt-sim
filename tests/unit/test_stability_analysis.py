"""Tests for the new stability analysis API.

These tests validate that the additive API in `pvtcore.stability.analysis`
returns structured results and matches expected stability/instability outcomes
for simple systems.

The legacy Michelsen stability implementation has its own unit tests in
`tests/unit/test_stability.py`; this module focuses only on the new API surface.
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError
from pvtcore.stability.analysis import (
    StabilityOptions,
    stability_analyze,
    tpd_single_trial,
)


def test_stability_analyze_returns_structured_result_stable_case() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"]])

    z = np.array([1.0], dtype=float)
    P = 1.0e5
    T = 400.0

    res = stability_analyze(z, P, T, eos, feed_phase="auto")

    assert isinstance(res.stable, bool)
    assert isinstance(res.tpd_min, float)
    assert res.vapor_like is not None
    assert res.liquid_like is not None
    assert len(res.trials) == 2
    assert res.stable is True
    assert res.tpd_min >= -StabilityOptions().tpd_negative_tol


def test_stability_analyze_detects_unstable_binary_vle_case() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z = np.array([0.5, 0.5], dtype=float)
    P = 3.0e6
    T = 300.0

    res = stability_analyze(z, P, T, eos, feed_phase="liquid")

    assert res.stable is False
    assert res.tpd_min < -StabilityOptions().tpd_negative_tol
    assert res.best_unstable_trial is not None


def test_tpd_single_trial_matches_analyze_trial() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z = np.array([0.5, 0.5], dtype=float)
    P = 3.0e6
    T = 300.0

    opts = StabilityOptions(use_gdem=True)
    full = stability_analyze(z, P, T, eos, feed_phase="liquid", options=opts)

    single = tpd_single_trial(
        z, P, T, eos,
        feed_phase="liquid",
        trial_kind="vapor_like",
        options=opts,
    )

    assert full.vapor_like is not None
    assert single.kind == "vapor_like"
    assert single.trial_phase == "vapor"
    assert np.isfinite(single.tpd)
    assert single.tpd == pytest.approx(full.vapor_like.tpd, abs=1e-12)
    np.testing.assert_allclose(single.w, full.vapor_like.w, rtol=0.0, atol=1e-12)
    assert single.best_seed_index == full.vapor_like.best_seed_index
    assert single.seed_attempts == full.vapor_like.seed_attempts
    assert single.total_iterations == full.vapor_like.total_iterations


def test_trial_result_exposes_seed_history_and_aggregate_diagnostics() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z = np.array([0.5, 0.5], dtype=float)
    P = 3.0e6
    T = 300.0

    res = stability_analyze(z, P, T, eos, feed_phase="liquid")

    assert res.vapor_like is not None
    trial = res.vapor_like

    assert trial.seed_attempts == len(trial.seed_results) >= 1
    assert trial.candidate_seed_count == len(trial.candidate_seed_labels) >= 2
    assert trial.seed_attempts <= trial.candidate_seed_count
    assert trial.best_seed_index >= 0
    assert trial.best_seed.seed_index == trial.best_seed_index
    assert trial.best_seed.seed_label in {"wilson", "extreme_lightest"}
    assert trial.candidate_seed_labels[:2] == ("wilson", "extreme_lightest")
    assert trial.n_phi_calls == sum(seed.n_phi_calls for seed in trial.seed_results)
    assert trial.n_eos_failures == sum(seed.n_eos_failures for seed in trial.seed_results)
    assert trial.total_iterations == sum(seed.iterations for seed in trial.seed_results)
    assert all(seed.kind == trial.kind for seed in trial.seed_results)
    assert all(seed.trial_phase == trial.trial_phase for seed in trial.seed_results)
    assert trial.best_seed.tpd == pytest.approx(trial.tpd, abs=1e-12)
    np.testing.assert_allclose(trial.best_seed.w, trial.w, rtol=0.0, atol=1e-12)
    assert trial.unattempted_seed_labels == trial.candidate_seed_labels[trial.seed_attempts :]


def test_input_validation_rejects_bad_composition_sum() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z_bad = np.array([0.6, 0.6], dtype=float)  # sums to 1.2
    with pytest.raises(ValidationError):
        stability_analyze(z_bad, 3.0e6, 300.0, eos, feed_phase="liquid")


def test_input_validation_rejects_negative_pressure() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"]])

    z = np.array([1.0], dtype=float)
    with pytest.raises(ValidationError):
        stability_analyze(z, -1.0e5, 300.0, eos, feed_phase="vapor")
