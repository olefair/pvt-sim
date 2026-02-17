import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.stability.analysis import StabilityOptions, stability_analyze


def test_stability_analyze_returns_structured_result_stable_case() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"]])

    z = np.array([1.0])
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

    z = np.array([0.5, 0.5])
    P = 3.0e6
    T = 300.0

    res = stability_analyze(z, P, T, eos, feed_phase="liquid")

    assert res.stable is False
    assert res.tpd_min < -StabilityOptions().tpd_negative_tol
    assert res.best_unstable_trial is not None
