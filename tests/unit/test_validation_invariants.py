"""Unit tests for invariant checks and solver certificates."""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.validation.invariants import (
    build_flash_certificate,
    check_composition_sum,
    check_eos_sanity,
    check_fugacity_equality,
    check_material_balance,
    check_phase_fraction_bounds,
)


def test_composition_sum_check():
    ok = check_composition_sum("sum", [0.2, 0.8], tol=1e-8, allow_all_zero=False)
    assert ok.passed is True
    assert ok.value == pytest.approx(0.0)

    bad = check_composition_sum("sum", [0.2, 0.7], tol=1e-8, allow_all_zero=False)
    assert bad.passed is False
    assert bad.value > 0.0


def test_phase_fraction_bounds_check():
    ok = check_phase_fraction_bounds(0.5, tol=1e-8)
    assert ok.passed is True

    bad = check_phase_fraction_bounds(1.2, tol=1e-8)
    assert bad.passed is False
    assert bad.value > 0.0


def test_material_balance_check():
    z = np.array([0.2, 0.8])
    x = np.array([0.1, 0.9])
    y = np.array([0.3, 0.7])
    beta = 0.5
    chk = check_material_balance(z, x, y, beta, tol=1e-8)
    assert chk.passed is True
    assert chk.value == pytest.approx(0.0)

    bad = check_material_balance(z, x, y, 0.9, tol=1e-8)
    assert bad.passed is False


def test_fugacity_equality_check():
    x = np.array([0.3, 0.7])
    y = np.array([0.3, 0.7])
    phi_l = np.array([1.0, 1.0])
    phi_v = np.array([1.0, 1.0])

    max_check, mean_check = check_fugacity_equality(
        x,
        y,
        phi_l,
        phi_v,
        tol_max=1e-8,
        tol_mean=1e-8,
    )
    assert max_check.passed is True
    assert mean_check.passed is True


def test_eos_sanity_check():
    components = load_components()
    comp_list = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(comp_list)
    z = np.array([0.6, 0.4])

    checks = check_eos_sanity(
        eos,
        pressure=3.0e6,
        temperature=300.0,
        compositions_by_phase={"vapor": z},
    )
    assert all(check.passed for check in checks if check.applicable)


def test_build_flash_certificate():
    components = load_components()
    comp_list = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(comp_list)
    z = np.array([0.6, 0.4])

    res = pt_flash(3.0e6, 300.0, z, comp_list, eos)
    cert = build_flash_certificate(res, eos)

    assert cert.passed is True
    names = {check.name for check in cert.checks}
    assert "composition_sum_z" in names
    assert "phase_fraction_bounds" in names
    assert "material_balance_max" in names
