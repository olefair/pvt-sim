"""
Unit tests for property correlations module.

Tests critical property correlations, acentric factor correlations,
boiling point correlations, parachor correlations, and low-level
Riazi-Daubert (Tb,SG) / (MW,SG) correlations.

All pure-math correlation functions are exercised through a single
parametrised reference table (CORRELATION_CASES) plus a handful of
structural / trend / error-handling tests that don't reduce to a
single (function, inputs, expected, tolerance) row.
"""

import pytest
import numpy as np

from pvtcore.correlations import (
    # Critical properties
    CriticalPropsMethod,
    riazi_daubert_Tc,
    riazi_daubert_Pc,
    riazi_daubert_Vc,
    riazi_daubert_critical_props,
    kesler_lee_Tc,
    kesler_lee_Pc,
    kesler_lee_critical_props,
    cavett_Tc,
    cavett_Pc,
    cavett_critical_props,
    estimate_critical_props,
    # Acentric factor
    AcentricMethod,
    edmister_omega,
    kesler_lee_omega,
    estimate_omega,
    # Boiling point
    BoilingPointMethod,
    soreide_Tb,
    riazi_daubert_Tb,
    estimate_Tb,
    # Parachor
    fanchi_parachor,
    estimate_parachor,
)

from pvtcore.correlations.critical_props.riazi_daubert import (
    estimate_from_tb_sg,
    estimate_from_mw_sg,
    edmister_acentric_factor,
)


# n-Heptane (C7) reference properties from NIST
C7 = dict(MW=100.20, Tc=540.2, Pc=2.74e6, omega=0.350, Tb=371.6, SG=0.684)


# ── Helpers for lambda-based cases ──────────────────────────────────────────

def _call_kesler_lee_Tc():
    return kesler_lee_Tc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_kesler_lee_Pc():
    return kesler_lee_Pc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_riazi_daubert_Tc():
    return riazi_daubert_Tc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_riazi_daubert_Tc_no_tb():
    return riazi_daubert_Tc(MW=C7["MW"], SG=C7["SG"], Tb=None)

def _call_riazi_daubert_Pc():
    return riazi_daubert_Pc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_riazi_daubert_Vc():
    return riazi_daubert_Vc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_cavett_Tc():
    return cavett_Tc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_cavett_Pc():
    return cavett_Pc(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])

def _call_edmister_omega():
    return edmister_omega(Tb=C7["Tb"], Tc=C7["Tc"], Pc=C7["Pc"])

def _call_kesler_lee_omega():
    return kesler_lee_omega(Tb=C7["Tb"], Tc=C7["Tc"], Pc=C7["Pc"])

def _call_estimate_omega_edmister():
    return estimate_omega(Tb=C7["Tb"], Tc=C7["Tc"], Pc=C7["Pc"], method=AcentricMethod.EDMISTER)

def _call_estimate_omega_kl():
    return estimate_omega(Tb=C7["Tb"], Tc=C7["Tc"], Pc=C7["Pc"], method=AcentricMethod.KESLER_LEE)

def _call_edmister_omega_generic():
    return edmister_omega(Tb=400.0, Tc=600.0, Pc=3e6)

def _call_soreide_Tb_100():
    return soreide_Tb(MW=100.0, SG=0.75)

def _call_riazi_daubert_Tb_100():
    return riazi_daubert_Tb(MW=100.0, SG=0.75)

def _call_estimate_Tb_soreide():
    return estimate_Tb(MW=150.0, SG=0.80, method=BoilingPointMethod.SOREIDE)

def _call_estimate_Tb_rd():
    return estimate_Tb(MW=150.0, SG=0.80, method=BoilingPointMethod.RIAZI_DAUBERT)

def _call_fanchi_parachor_c7():
    return fanchi_parachor(MW=C7["MW"])

def _call_estimate_parachor_c1():
    return estimate_parachor(MW=16.04, component_id="C1")

def _call_estimate_parachor_c7():
    return estimate_parachor(MW=C7["MW"])


# ── Reference table ─────────────────────────────────────────────────────────
# Each entry: (id, callable, lo, hi)
# The test asserts  lo <= result <= hi.  For "approx equal" checks the bounds
# are set tightly around the expected value.

CORRELATION_CASES = [
    # --- Kesler-Lee critical props (C7 reference) ---
    ("kesler_lee_Tc_c7",       _call_kesler_lee_Tc,       C7["Tc"] * 0.98, C7["Tc"] * 1.02),
    ("kesler_lee_Pc_c7",       _call_kesler_lee_Pc,       C7["Pc"] * 0.90, C7["Pc"] * 1.10),

    # --- Riazi-Daubert critical props (range checks) ---
    ("rd_Tc_with_tb",          _call_riazi_daubert_Tc,    C7["Tb"] + 0.01, 800.0),
    ("rd_Tc_no_tb",            _call_riazi_daubert_Tc_no_tb, 400.0, 1000.0),
    ("rd_Pc",                  _call_riazi_daubert_Pc,    1e6, 5e6),
    ("rd_Vc",                  _call_riazi_daubert_Vc,    0.0001, 1e10),

    # --- Cavett critical props ---
    ("cavett_Tc",              _call_cavett_Tc,           C7["Tb"] + 0.01, 800.0),
    ("cavett_Pc",              _call_cavett_Pc,           1e6, 5e6),

    # --- Acentric factor ---
    ("edmister_omega_c7",      _call_edmister_omega,      C7["omega"] - 0.07, C7["omega"] + 0.07),
    ("kesler_lee_omega_c7",    _call_kesler_lee_omega,    0.2, 0.5),
    ("estimate_omega_edmister",_call_estimate_omega_edmister, 0.0, 1.0),
    ("estimate_omega_kl",      _call_estimate_omega_kl,   0.0, 1.0),
    ("edmister_omega_generic", _call_edmister_omega_generic, -0.5, 2.0),

    # --- Boiling point ---
    ("soreide_Tb_100",         _call_soreide_Tb_100,      300.0, 450.0),
    ("rd_Tb_100",              _call_riazi_daubert_Tb_100, 300.0, 450.0),
    ("estimate_Tb_soreide",    _call_estimate_Tb_soreide,  350.0, 600.0),
    ("estimate_Tb_rd",         _call_estimate_Tb_rd,       350.0, 600.0),

    # --- Parachor ---
    ("fanchi_parachor_c7",     _call_fanchi_parachor_c7,  312.5 * 0.85, 312.5 * 1.15),
    ("estimate_parachor_c1",   _call_estimate_parachor_c1, 77.0, 77.0),
    ("estimate_parachor_c7",   _call_estimate_parachor_c7, 250.0, 400.0),
]


@pytest.mark.parametrize("case_id, fn, lo, hi", CORRELATION_CASES, ids=[c[0] for c in CORRELATION_CASES])
def test_correlation(case_id, fn, lo, hi):
    result = fn()
    assert lo <= result <= hi, f"{case_id}: {result} not in [{lo}, {hi}]"


# ── Riazi-Daubert low-level (Tb,SG) and (MW,SG) reference data ─────────────
# Merged from tests/unit/test_riazi_daubert.py

RIAZI_DAUBERT_CASES = [
    (
        "tb_sg_form",
        lambda: estimate_from_tb_sg(np.array([658.0]), np.array([0.7365])),
        lambda r: (
            r[0][0] == pytest.approx(986.7, abs=0.5)
            and r[1][0] == pytest.approx(465.83, abs=1.0)
            and r[2][0] == pytest.approx(0.06257, abs=5e-4)
        ),
    ),
    (
        "mw_sg_form_Tc",
        lambda: estimate_from_mw_sg(np.array([150.0]), np.array([0.78])),
        lambda r: r[0][0] == pytest.approx(1139.4, abs=1.0),
    ),
    (
        "mw_sg_form_Pc",
        lambda: estimate_from_mw_sg(np.array([150.0]), np.array([0.78])),
        lambda r: r[1][0] == pytest.approx(320.3, abs=1.0),
    ),
    (
        "mw_sg_form_Tb",
        lambda: estimate_from_mw_sg(np.array([150.0]), np.array([0.78])),
        lambda r: r[3][0] == pytest.approx(825.3, abs=1.0),
    ),
    (
        "mw_sg_edmister_omega",
        lambda: (
            lambda res: edmister_acentric_factor(res[0], res[1], res[3])
        )(estimate_from_mw_sg(np.array([150.0]), np.array([0.78]))),
        lambda r: r[0] == pytest.approx(0.5067, abs=0.01),
    ),
]


@pytest.mark.parametrize(
    "case_id, fn, check",
    RIAZI_DAUBERT_CASES,
    ids=[c[0] for c in RIAZI_DAUBERT_CASES],
)
def test_riazi_daubert_low_level(case_id, fn, check):
    result = fn()
    assert check(result), f"{case_id}: check failed on {result}"


# ── Structural / method-tag tests ───────────────────────────────────────────

def test_riazi_daubert_critical_props_result_type():
    result = riazi_daubert_critical_props(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])
    assert hasattr(result, "Tc")
    assert hasattr(result, "Pc")
    assert hasattr(result, "Vc")
    assert result.method == CriticalPropsMethod.RIAZI_DAUBERT


def test_kesler_lee_critical_props_complete():
    result = kesler_lee_critical_props(MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"])
    assert result.method == CriticalPropsMethod.KESLER_LEE
    assert abs(result.Tc - C7["Tc"]) / C7["Tc"] < 0.02
    assert result.Vc > 0


def test_estimate_critical_props_method_selection():
    result_kl = estimate_critical_props(
        MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"],
        method=CriticalPropsMethod.KESLER_LEE,
    )
    result_cv = estimate_critical_props(
        MW=C7["MW"], SG=C7["SG"], Tb=C7["Tb"],
        method=CriticalPropsMethod.CAVETT,
    )
    assert result_kl.method == CriticalPropsMethod.KESLER_LEE
    assert result_cv.method == CriticalPropsMethod.CAVETT
    assert 400 < result_kl.Tc < 700
    assert 400 < result_cv.Tc < 850


# ── Error-handling tests ────────────────────────────────────────────────────

INVALID_INPUT_CASES = [
    ("negative_MW",   lambda: riazi_daubert_Tc(MW=-100.0, SG=0.7)),
    ("negative_SG",   lambda: riazi_daubert_Tc(MW=100.0, SG=-0.7)),
    ("nan_MW",        lambda: riazi_daubert_Tc(MW=float("nan"), SG=0.7)),
    ("Tb_gt_Tc",      lambda: edmister_omega(Tb=600.0, Tc=500.0, Pc=3e6)),
    ("kl_no_Tb",      lambda: kesler_lee_Tc(MW=100.0, SG=0.7, Tb=None)),
    ("soreide_neg_MW", lambda: soreide_Tb(MW=-100.0, SG=0.7)),
    ("soreide_neg_SG", lambda: soreide_Tb(MW=100.0, SG=-0.7)),
]


@pytest.mark.parametrize(
    "case_id, fn",
    INVALID_INPUT_CASES,
    ids=[c[0] for c in INVALID_INPUT_CASES],
)
def test_invalid_inputs_raise(case_id, fn):
    with pytest.raises(ValueError):
        fn()


# ── Monotonicity / trend tests ──────────────────────────────────────────────

def test_Tb_increases_with_MW():
    Tb1 = soreide_Tb(MW=100.0, SG=0.75)
    Tb2 = soreide_Tb(MW=150.0, SG=0.80)
    Tb3 = soreide_Tb(MW=200.0, SG=0.85)
    assert Tb1 < Tb2 < Tb3


def test_parachor_increases_with_MW():
    P1 = fanchi_parachor(MW=100.0)
    P2 = fanchi_parachor(MW=150.0)
    P3 = fanchi_parachor(MW=200.0)
    assert P1 < P2 < P3


def test_roundtrip_consistency():
    MW, SG = 150.0, 0.82
    Tb = estimate_Tb(MW=MW, SG=SG)
    crit = estimate_critical_props(MW=MW, SG=SG, Tb=Tb, method=CriticalPropsMethod.KESLER_LEE)
    omega = estimate_omega(Tb=Tb, Tc=crit.Tc, Pc=crit.Pc)
    assert 350 < Tb < 700
    assert Tb < crit.Tc < 900
    assert 1e6 < crit.Pc < 5e6
    assert 0.0 < omega < 1.5


def test_scn_property_trends():
    MWs = [100, 150, 200, 250, 300]
    SG = 0.82
    Tbs = [estimate_Tb(MW=mw, SG=SG) for mw in MWs]
    Tcs, Pcs, omegas = [], [], []
    for mw, tb in zip(MWs, Tbs):
        crit = estimate_critical_props(MW=mw, SG=SG, Tb=tb, method=CriticalPropsMethod.KESLER_LEE)
        Tcs.append(crit.Tc)
        Pcs.append(crit.Pc)
        omegas.append(estimate_omega(Tb=tb, Tc=crit.Tc, Pc=crit.Pc))
    assert all(Tbs[i] < Tbs[i + 1] for i in range(len(Tbs) - 1))
    assert all(Tcs[i] < Tcs[i + 1] for i in range(len(Tcs) - 1))
    assert all(Pcs[i] > Pcs[i + 1] for i in range(len(Pcs) - 1))
    assert all(omegas[i] < omegas[i + 1] for i in range(len(omegas) - 1))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
