import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtcore.stability.analysis import stability_analyze
from pvtcore.stability.michelsen import michelsen_stability_test, TPD_TOLERANCE


def test_michelsen_wrapper_matches_new_api_ordering_and_values() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z = np.array([0.5, 0.5])
    P = 5.0e6
    T = 300.0

    legacy = michelsen_stability_test(z, P, T, eos, feed_phase="liquid")
    new = stability_analyze(z, P, T, eos, feed_phase="liquid")

    assert len(legacy.trial_compositions) == 2
    assert len(legacy.tpd_values) == 2

    assert legacy.tpd_values[0] == pytest.approx(new.vapor_like.tpd, abs=1e-10)
    assert legacy.tpd_values[1] == pytest.approx(new.liquid_like.tpd, abs=1e-10)

    assert np.allclose(legacy.trial_compositions[0], new.vapor_like.w, atol=1e-12)
    assert np.allclose(legacy.trial_compositions[1], new.liquid_like.w, atol=1e-12)

    assert legacy.tpd_min == pytest.approx(min(legacy.tpd_values), abs=1e-10)
    assert legacy.stable == (legacy.tpd_min >= -TPD_TOLERANCE)


def test_wrapper_preserves_two_trials_only() -> None:
    comps = load_components()
    eos = PengRobinsonEOS([comps["C1"], comps["C10"]])

    z = np.array([0.5, 0.5])
    P = 3.0e6
    T = 300.0

    legacy = michelsen_stability_test(z, P, T, eos, feed_phase="liquid")

    assert len(legacy.trial_compositions) == 2
    assert len(legacy.tpd_values) == 2
    assert len(legacy.iterations) == 2
