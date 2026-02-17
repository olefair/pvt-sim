import numpy as np
import pytest

from pvtcore.properties.ift_parachor import interfacial_tension_parachor
from pvtcore.properties.ift_parachor import interfacial_tension_parachor_after_flash
from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.pt_flash import pt_flash


def test_parachor_ift_zero_when_no_density_or_composition_contrast():
    # If both phases are identical (x=y and rhoL=rhoV), the Weinaug–Katz
    # expression gives sigma^(1/4)=0 -> sigma=0.
    x = np.array([0.4, 0.6])
    y = x.copy()
    mw = np.array([16.0, 142.0])  # g/mol
    P = np.array([100.0, 500.0])

    res = interfacial_tension_parachor(
        x,
        y,
        rho_liquid_kg_per_m3=600.0,
        rho_vapor_kg_per_m3=600.0,
        mw_components_g_per_mol=mw,
        parachor=P,
    )
    assert res.sigma_N_per_m == pytest.approx(0.0, abs=0.0)
    assert res.sigma_dyn_per_cm == pytest.approx(0.0, abs=0.0)


def test_parachor_ift_scales_as_fourth_power_of_parachor_scale():
    x = np.array([0.2, 0.8])
    y = np.array([0.8, 0.2])
    mw = np.array([16.0, 142.0])  # g/mol

    res1 = interfacial_tension_parachor(
        x,
        y,
        rho_liquid_kg_per_m3=700.0,
        rho_vapor_kg_per_m3=50.0,
        mw_components_g_per_mol=mw,
        parachor=np.array([100.0, 400.0]),
    )
    res2 = interfacial_tension_parachor(
        x,
        y,
        rho_liquid_kg_per_m3=700.0,
        rho_vapor_kg_per_m3=50.0,
        mw_components_g_per_mol=mw,
        parachor=2.0 * np.array([100.0, 400.0]),
    )

    # sigma^(1/4) is linear in P_i, so sigma is quartic.
    assert res2.sigma_N_per_m == pytest.approx(16.0 * res1.sigma_N_per_m, rel=1e-12, abs=0.0)


def test_parachor_ift_is_finite_and_non_negative_for_typical_inputs():
    x = np.array([0.05, 0.95])
    y = np.array([0.95, 0.05])
    mw = np.array([16.0, 142.0])  # g/mol
    P = np.array([90.0, 420.0])

    res = interfacial_tension_parachor(
        x,
        y,
        rho_liquid_kg_per_m3=650.0,
        rho_vapor_kg_per_m3=20.0,
        mw_components_g_per_mol=mw,
        parachor=P,
    )
    assert np.isfinite(res.sigma_N_per_m)
    assert res.sigma_N_per_m >= 0.0


def test_parachor_ift_after_flash_smoke():
    # Smoke test: ensure the post-flash helper can compute IFT end-to-end
    # when the flash is two-phase at the chosen conditions.
    comps = load_components()
    system = [comps["C1"], comps["C10"]]
    eos = PengRobinsonEOS(system)

    P = 3.0e6
    T = 300.0
    z = np.array([0.6, 0.4])
    flash = pt_flash(P, T, z, system, eos)

    if flash.phase != "two-phase":
        pytest.skip("Chosen conditions did not yield a two-phase flash in this model.")

    res = interfacial_tension_parachor_after_flash(flash, eos, system)
    assert np.isfinite(res.sigma_N_per_m)
    assert res.sigma_N_per_m >= 0.0
