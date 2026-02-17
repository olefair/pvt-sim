import numpy as np
import pytest

from pvtcore.correlations.critical_props.riazi_daubert import (
    estimate_from_tb_sg,
    estimate_from_mw_sg,
    edmister_acentric_factor,
)


def test_riazi_daubert_tb_sg_example() -> None:
    # Example values from published tables (Tb=658 R, SG=0.7365)
    tb_r = np.array([658.0])
    sg = np.array([0.7365])

    Tc_r, Pc_psia, Vc_ft3_lb = estimate_from_tb_sg(tb_r, sg)

    assert Tc_r[0] == pytest.approx(986.7, abs=0.5)
    assert Pc_psia[0] == pytest.approx(465.83, abs=1.0)
    assert Vc_ft3_lb[0] == pytest.approx(0.06257, abs=5e-4)


def test_riazi_daubert_mw_sg_example_and_omega() -> None:
    mw = np.array([150.0])
    sg = np.array([0.78])

    Tc_r, Pc_psia, Vc_ft3_lb, Tb_r = estimate_from_mw_sg(mw, sg)

    assert Tc_r[0] == pytest.approx(1139.4, abs=1.0)
    assert Pc_psia[0] == pytest.approx(320.3, abs=1.0)
    assert Tb_r[0] == pytest.approx(825.3, abs=1.0)

    omega = edmister_acentric_factor(Tc_r, Pc_psia, Tb_r)
    assert omega[0] == pytest.approx(0.5067, abs=0.01)
