"""Additional tests for the Michelsen TPD stability analysis module.

These focus on single-trial consistency, GDEM behavior (non-flaky/deterministic),
and robustness to trace components and intermittent EOS failures.
"""

from __future__ import annotations

import numpy as np

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.stability.analysis import (
    StabilityOptions,
    stability_analyze,
    tpd_single_trial,
)


def test_tpd_single_trial_matches_analyze_trial():
    comps = load_components()
    binary = [comps["C1"], comps["C10"]]
    eos = PengRobinsonEOS(binary)

    z = np.array([0.5, 0.5], dtype=float)
    T = 300.0
    P = 3e6

    opts = StabilityOptions(use_gdem=True)
    full = stability_analyze(z, P, T, eos, feed_phase="liquid", options=opts)

    single = tpd_single_trial(z, P, T, eos, feed_phase="liquid", trial_kind="vapor_like", options=opts)

    assert full.vapor_like is not None
    assert single.kind == "vapor_like"
    assert single.trial_phase == "vapor"
    assert np.isfinite(single.tpd)
    assert single.tpd == full.vapor_like.tpd
    np.testing.assert_allclose(single.w, full.vapor_like.w, rtol=0.0, atol=1e-12)


class _PowerLawPhiEOS:
    """Deterministic dummy EOS that induces slow SS convergence in log-space.

    We define: phi_i(w) = w_i**(-gamma). This yields a linear contraction in the
    log-space fixed point update with contraction ratio ~gamma.
    """

    def __init__(self, components, gamma: float = 0.93):
        self.components = list(components)
        self.n_components = len(self.components)
        self._gamma = float(gamma)

    def fugacity_coefficient(self, pressure, temperature, composition, phase, binary_interaction=None):
        w = np.asarray(composition, dtype=float)
        eps = 1e-300
        return np.maximum(w, eps) ** (-self._gamma)


def test_gdem_not_worse_than_plain_ss_on_slow_mapping():
    comps = load_components()
    fake_components = [comps["C1"], comps["C2"], comps["C3"]]
    eos = _PowerLawPhiEOS(fake_components, gamma=0.90)

    z = np.array([0.2, 0.3, 0.5], dtype=float)
    P = 1e6
    T = 300.0

    # Use a slow-but-convergent mapping and a max_iter large enough that
    # plain SS converges deterministically.
    opts_no = StabilityOptions(use_gdem=False, max_iter=600, tol_ln_w=1e-10)
    res_no = tpd_single_trial(z, P, T, eos, feed_phase="vapor", trial_kind="liquid_like", options=opts_no)
    assert res_no.converged is True

    # Lower the trigger slightly so GDEM engages on this synthetic mapping.
    opts_yes = StabilityOptions(use_gdem=True, gdem_lambda_trigger=0.85, max_iter=600, tol_ln_w=1e-10)
    res_yes = tpd_single_trial(z, P, T, eos, feed_phase="vapor", trial_kind="liquid_like", options=opts_yes)
    assert res_yes.converged is True

    assert res_yes.iterations <= res_no.iterations


def test_trace_component_does_not_crash_and_returns_finite_tpd():
    comps = load_components()
    ternary = [comps["C1"], comps["C3"], comps["C10"]]
    eos = PengRobinsonEOS(ternary)

    z = np.array([0.7, 0.3 - 1e-12, 1e-12], dtype=float)
    z = z / float(np.sum(z))
    P = 3e6
    T = 300.0

    res = stability_analyze(z, P, T, eos, feed_phase="auto")
    assert np.isfinite(res.tpd_min)
    assert isinstance(res.stable, bool)


class _FlakyEOS:
    """EOS wrapper that fails once to exercise recovery logic."""

    def __init__(self, base):
        self._base = base
        self.components = base.components
        self.n_components = base.n_components
        self._calls = 0

    def fugacity_coefficient(self, pressure, temperature, composition, phase, binary_interaction=None):
        self._calls += 1
        if self._calls == 2:
            raise RuntimeError("simulated EOS failure")
        return self._base.fugacity_coefficient(pressure, temperature, composition, phase, binary_interaction)


def test_eos_failure_recovery_does_not_crash():
    comps = load_components()
    binary = [comps["C1"], comps["C4"]]
    base = PengRobinsonEOS(binary)
    eos = _FlakyEOS(base)

    z = np.array([0.6, 0.4], dtype=float)
    P = 3e6
    T = 300.0

    opts = StabilityOptions(use_gdem=False, max_iter=200)
    trial = tpd_single_trial(z, P, T, eos, feed_phase="liquid", trial_kind="vapor_like", options=opts)

    assert trial.converged is True
    assert trial.n_eos_failures >= 1
    assert np.isfinite(trial.tpd)
