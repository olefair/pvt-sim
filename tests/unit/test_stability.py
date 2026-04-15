"""Consolidated unit tests for Michelsen TPD stability analysis.

Covers the legacy Michelsen wrapper, the new ``stability_analyze`` API,
GDEM acceleration, EOS failure recovery, legacy/new parity, and edge cases.
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError
from pvtcore.stability.michelsen import (
    michelsen_stability_test,
    is_stable,
    StabilityResult,
    TPD_TOLERANCE,
)
from pvtcore.stability.tpd import calculate_tpd, calculate_d_terms
from pvtcore.stability.analysis import (
    StabilityOptions,
    stability_analyze,
    tpd_single_trial,
)


# ── module-scoped EOS for the synthetic _PowerLawPhiEOS ──────────────


class _PowerLawPhiEOS:
    """Deterministic dummy EOS that induces slow SS convergence in log-space."""

    def __init__(self, components, gamma: float = 0.93):
        self.components = list(components)
        self.n_components = len(self.components)
        self._gamma = float(gamma)

    def fugacity_coefficient(self, pressure, temperature, composition, phase,
                             binary_interaction=None):
        w = np.asarray(composition, dtype=float)
        eps = 1e-300
        return np.maximum(w, eps) ** (-self._gamma)


class _FlakyEOS:
    """EOS wrapper that fails once to exercise recovery logic."""

    def __init__(self, base):
        self._base = base
        self.components = base.components
        self.n_components = base.n_components
        self._calls = 0

    def fugacity_coefficient(self, pressure, temperature, composition, phase,
                             binary_interaction=None):
        self._calls += 1
        if self._calls == 2:
            raise RuntimeError("simulated EOS failure")
        return self._base.fugacity_coefficient(
            pressure, temperature, composition, phase, binary_interaction
        )


# ── 1. test_tpd_and_stability ────────────────────────────────────────


_STABILITY_CASES = [
    # (fixture_key, P, T, z, expected_stable, id)
    #   fixture_key maps to an EOS fixture from conftest
    #
    # --- binary C1/C10 ---
    ("c1_c10_pr", 3e6,  300.0, [0.5, 0.5],  False, "c1c10-unstable-VLE"),
    ("c1_c10_pr", 1e4,  600.0, [0.5, 0.5],  True,  "c1c10-stable-high-T"),
    # --- binary C1/C4 ---
    ("c1_c4_pr",  4e6,  250.0, [0.7, 0.3],  False, "c1c4-unstable-VLE"),
    ("c1_c4_pr",  1e5,  400.0, [0.5, 0.5],  True,  "c1c4-stable-low-P-high-T"),
    # --- ternary C1/C4/C10 ---
    ("c1_c4_c10_pr", 3e6, 300.0, [0.6, 0.2, 0.2], False, "ternary-unstable"),
    ("c1_c4_c10_pr", 1e4, 600.0, [0.4, 0.3, 0.3], True,  "ternary-stable-high-T"),
]


@pytest.mark.parametrize(
    "eos_key, P, T, z_list, expected_stable",
    [(c[0], c[1], c[2], c[3], c[4]) for c in _STABILITY_CASES],
    ids=[c[5] for c in _STABILITY_CASES],
)
def test_tpd_and_stability(
    eos_key, P, T, z_list, expected_stable, request
):
    """Michelsen stability test agrees with known stable/unstable conditions."""
    eos = request.getfixturevalue(eos_key)
    z = np.array(z_list, dtype=float)

    result = michelsen_stability_test(z, P, T, eos, feed_phase="liquid")

    assert isinstance(result, StabilityResult)
    assert isinstance(result.stable, bool)
    assert isinstance(result.tpd_min, (float, np.floating))
    assert result.stable is expected_stable

    if expected_stable:
        assert result.tpd_min >= -TPD_TOLERANCE
        assert result.converged is True
    else:
        assert result.tpd_min < -TPD_TOLERANCE
        assert any(tpd < -TPD_TOLERANCE for tpd in result.tpd_values)

    assert len(result.trial_compositions) == 2
    for W in result.trial_compositions:
        assert abs(W.sum() - 1.0) < 1e-10


# ── 2. test_stability_analyze_api ────────────────────────────────────


def test_stability_analyze_api(components, c1_c10_pr):
    """New analysis API returns structured results with diagnostics."""
    eos = c1_c10_pr
    z = np.array([0.5, 0.5], dtype=float)

    # Stable case: pure methane, low P, high T
    eos_c1 = PengRobinsonEOS([components["C1"]])
    res_stable = stability_analyze(
        np.array([1.0]), 1e5, 400.0, eos_c1, feed_phase="auto"
    )

    assert res_stable.stable is True
    assert isinstance(res_stable.tpd_min, float)
    assert res_stable.vapor_like is not None
    assert res_stable.liquid_like is not None
    assert len(res_stable.trials) == 2
    assert res_stable.tpd_min >= -StabilityOptions().tpd_negative_tol

    # Unstable case: C1/C10 binary in VLE region
    res_unst = stability_analyze(z, 3e6, 300.0, eos, feed_phase="liquid")

    assert res_unst.stable is False
    assert res_unst.tpd_min < -StabilityOptions().tpd_negative_tol
    assert res_unst.best_unstable_trial is not None

    # Seed-level diagnostics (from test_stability_analysis.py)
    trial = res_unst.vapor_like
    assert trial is not None
    assert trial.seed_attempts == len(trial.seed_results) >= 1
    assert trial.candidate_seed_count == len(trial.candidate_seed_labels) >= 2
    assert trial.seed_attempts <= trial.candidate_seed_count
    assert trial.best_seed_index >= 0
    assert trial.best_seed.seed_index == trial.best_seed_index
    assert trial.best_seed.seed_label in {"wilson", "extreme_lightest"}
    assert trial.candidate_seed_labels[:2] == ("wilson", "extreme_lightest")
    assert trial.n_phi_calls == sum(
        seed.n_phi_calls for seed in trial.seed_results
    )
    assert trial.n_eos_failures == sum(
        seed.n_eos_failures for seed in trial.seed_results
    )
    assert trial.total_iterations == sum(
        seed.iterations for seed in trial.seed_results
    )
    assert all(seed.kind == trial.kind for seed in trial.seed_results)
    assert all(
        seed.trial_phase == trial.trial_phase for seed in trial.seed_results
    )
    assert trial.best_seed.tpd == pytest.approx(trial.tpd, abs=1e-12)
    np.testing.assert_allclose(
        trial.best_seed.w, trial.w, rtol=0.0, atol=1e-12
    )
    assert (
        trial.unattempted_seed_labels
        == trial.candidate_seed_labels[trial.seed_attempts:]
    )

    # tpd_single_trial matches the full analysis for vapor-like trial
    opts = StabilityOptions(use_gdem=True)
    full = stability_analyze(z, 3e6, 300.0, eos, feed_phase="liquid", options=opts)
    single = tpd_single_trial(
        z, 3e6, 300.0, eos,
        feed_phase="liquid", trial_kind="vapor_like", options=opts,
    )
    assert full.vapor_like is not None
    assert single.kind == "vapor_like"
    assert single.trial_phase == "vapor"
    assert np.isfinite(single.tpd)
    assert single.tpd == pytest.approx(full.vapor_like.tpd, abs=1e-12)
    np.testing.assert_allclose(
        single.w, full.vapor_like.w, rtol=0.0, atol=1e-12
    )


# ── 3. test_gdem_acceleration ────────────────────────────────────────


def test_gdem_acceleration(components):
    """GDEM converges no worse than plain successive substitution."""
    fake_components = [components["C1"], components["C2"], components["C3"]]
    eos = _PowerLawPhiEOS(fake_components, gamma=0.90)

    z = np.array([0.2, 0.3, 0.5], dtype=float)
    P, T = 1e6, 300.0

    opts_no = StabilityOptions(
        use_gdem=False, max_iter=600, tol_ln_w=1e-10
    )
    res_no = tpd_single_trial(
        z, P, T, eos,
        feed_phase="vapor", trial_kind="liquid_like", options=opts_no,
    )
    assert res_no.converged is True

    opts_yes = StabilityOptions(
        use_gdem=True, gdem_lambda_trigger=0.85,
        max_iter=600, tol_ln_w=1e-10,
    )
    res_yes = tpd_single_trial(
        z, P, T, eos,
        feed_phase="vapor", trial_kind="liquid_like", options=opts_yes,
    )
    assert res_yes.converged is True
    assert res_yes.iterations <= res_no.iterations


# ── 4. test_eos_failure_recovery ─────────────────────────────────────


def test_eos_failure_recovery(c1_c4_pr):
    """Single transient EOS failure is recovered without crashing."""
    eos = _FlakyEOS(c1_c4_pr)

    z = np.array([0.6, 0.4], dtype=float)
    opts = StabilityOptions(use_gdem=False, max_iter=200)
    trial = tpd_single_trial(
        z, 3e6, 300.0, eos,
        feed_phase="liquid", trial_kind="vapor_like", options=opts,
    )

    assert trial.converged is True
    assert trial.n_eos_failures == 1
    assert trial.seed_attempts == len(trial.seed_results) == 2
    assert trial.candidate_seed_count == 2
    assert trial.stopped_early is False
    assert sum(
        seed.n_eos_failures for seed in trial.seed_results
    ) == 1
    assert any(
        seed.n_eos_failures == 1 for seed in trial.seed_results
    )
    assert trial.message is not None
    assert "Recovered from 1 EOS evaluation failure" in trial.message
    assert np.isfinite(trial.tpd)


# ── 5. test_legacy_wrapper_parity ────────────────────────────────────


def test_legacy_wrapper_parity(c1_c10_pr):
    """Legacy Michelsen wrapper agrees numerically with the new analysis API."""
    z = np.array([0.5, 0.5])
    P, T = 5e6, 300.0

    legacy = michelsen_stability_test(z, P, T, c1_c10_pr, feed_phase="liquid")
    new = stability_analyze(z, P, T, c1_c10_pr, feed_phase="liquid")

    assert len(legacy.trial_compositions) == 2
    assert len(legacy.tpd_values) == 2

    assert legacy.tpd_values[0] == pytest.approx(
        new.vapor_like.tpd, abs=1e-10
    )
    assert legacy.tpd_values[1] == pytest.approx(
        new.liquid_like.tpd, abs=1e-10
    )
    assert np.allclose(
        legacy.trial_compositions[0], new.vapor_like.w, atol=1e-12
    )
    assert np.allclose(
        legacy.trial_compositions[1], new.liquid_like.w, atol=1e-12
    )
    assert legacy.tpd_min == pytest.approx(min(legacy.tpd_values), abs=1e-10)
    assert legacy.stable == (legacy.tpd_min >= -TPD_TOLERANCE)

    # Both APIs should agree on stability verdict
    assert legacy.stable == new.stable

    # Wrapper preserves exactly two trials
    legacy2 = michelsen_stability_test(
        z, 3e6, 300.0, c1_c10_pr, feed_phase="liquid"
    )
    assert len(legacy2.trial_compositions) == 2
    assert len(legacy2.tpd_values) == 2
    assert len(legacy2.iterations) == 2


# ── 6. test_stability_edge_cases ─────────────────────────────────────


class TestStabilityEdgeCases:
    """Near-critical points, single-phase guaranteed stable, input validation."""

    def test_supercritical_pure_component(self, components):
        """Pure component well above Tc is always single-phase stable."""
        comp = components["C1"]
        eos = PengRobinsonEOS([comp])
        T = 1.3 * comp.Tc
        z = np.array([1.0])

        result = michelsen_stability_test(z, 5e6, T, eos, feed_phase="vapor")
        assert result.stable is True
        assert result.tpd_min >= -TPD_TOLERANCE

    def test_is_stable_convenience(self, components):
        """is_stable() convenience function returns correct bool."""
        eos = PengRobinsonEOS([components["C1"]])
        assert is_stable(np.array([1.0]), 1e5, 400.0, eos, feed_phase="vapor") is True

    def test_pure_below_critical_runs(self, components):
        """Pure methane below Tc runs without error for both feed phases."""
        comp = components["C1"]
        eos = PengRobinsonEOS([comp])
        T = 0.8 * comp.Tc
        z = np.array([1.0])

        r_liq = michelsen_stability_test(z, 2e6, T, eos, feed_phase="liquid")
        r_vap = michelsen_stability_test(z, 2e6, T, eos, feed_phase="vapor")
        assert isinstance(r_liq.stable, bool)
        assert isinstance(r_vap.stable, bool)

    def test_trace_component_finite(self, components):
        """Trace-amount component does not crash and returns finite TPD."""
        ternary = [components["C1"], components["C3"], components["C10"]]
        eos = PengRobinsonEOS(ternary)
        z = np.array([0.7, 0.3 - 1e-12, 1e-12], dtype=float)
        z = z / float(np.sum(z))

        res = stability_analyze(z, 3e6, 300.0, eos, feed_phase="auto")
        assert np.isfinite(res.tpd_min)
        assert isinstance(res.stable, bool)

    def test_pressure_temperature_traversals(self, c1_c10_pr):
        """Stability test runs across P/T traversals without error."""
        z = np.array([0.5, 0.5])

        for T in [250.0, 300.0, 400.0, 600.0]:
            r = michelsen_stability_test(
                z, 5e6, T, c1_c10_pr, feed_phase="liquid"
            )
            assert isinstance(r.stable, bool)

        for P in [1e5, 1e6, 5e6, 10e6]:
            r = michelsen_stability_test(
                z, P, 400.0, c1_c10_pr, feed_phase="vapor"
            )
            assert isinstance(r.stable, bool)

    def test_invalid_composition_sum(self, components):
        """Bad composition sum raises ValidationError."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            michelsen_stability_test(
                np.array([0.5]), 5e6, 300.0, eos, feed_phase="liquid"
            )

    def test_negative_pressure(self, components):
        """Negative pressure raises ValidationError."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            michelsen_stability_test(
                np.array([1.0]), -1e6, 300.0, eos, feed_phase="liquid"
            )

    def test_negative_temperature(self, components):
        """Negative temperature raises ValidationError."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            michelsen_stability_test(
                np.array([1.0]), 5e6, -100.0, eos, feed_phase="liquid"
            )

    def test_invalid_feed_phase(self, components):
        """Invalid feed phase string raises ValidationError."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            michelsen_stability_test(
                np.array([1.0]), 5e6, 300.0, eos, feed_phase="supercritical"
            )

    def test_composition_eos_mismatch(self, components):
        """Composition size != EOS component count raises ValidationError."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            michelsen_stability_test(
                np.array([0.5, 0.5]), 5e6, 300.0, eos, feed_phase="liquid"
            )

    def test_new_api_rejects_bad_sum(self, c1_c10_pr):
        """New analysis API rejects bad composition sum."""
        z_bad = np.array([0.6, 0.6], dtype=float)
        with pytest.raises(ValidationError):
            stability_analyze(z_bad, 3e6, 300.0, c1_c10_pr, feed_phase="liquid")

    def test_new_api_rejects_negative_pressure(self, components):
        """New analysis API rejects negative pressure."""
        eos = PengRobinsonEOS([components["C1"]])
        with pytest.raises(ValidationError):
            stability_analyze(
                np.array([1.0]), -1e5, 300.0, eos, feed_phase="vapor"
            )
