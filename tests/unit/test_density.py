import numpy as np
import pytest

from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.models.component import load_components
from pvtcore.properties.density import (
    densities_after_flash,
    mass_density_kg_per_m3,
    phase_molecular_weight_g_per_mol,
)


def test_phase_molecular_weight_matches_weighted_average():
    comps = load_components()
    system = [comps["C1"], comps["C10"]]
    x = np.array([0.25, 0.75])

    mw = phase_molecular_weight_g_per_mol(x, system)
    expected = 0.25 * system[0].MW + 0.75 * system[1].MW
    assert mw == pytest.approx(expected, rel=0.0, abs=1e-12)


def test_mass_density_matches_eos_molar_density_times_mw():
    comps = load_components()
    system = [comps["C1"]]
    eos = PengRobinsonEOS(system)

    P = 5.0e6
    T = 300.0
    z = np.array([1.0])

    rho_mol = float(eos.density(P, T, z, phase="vapor"))
    mw_kg_mol = system[0].MW / 1000.0
    expected = rho_mol * mw_kg_mol

    rho = mass_density_kg_per_m3(P, T, z, eos, system, phase="vapor")
    assert rho == pytest.approx(expected, rel=1e-12, abs=0.0)


def test_densities_after_flash_two_phase_smoke():
    comps = load_components()
    system = [comps["C1"], comps["C10"]]
    eos = PengRobinsonEOS(system)

    P = 3.0e6
    T = 300.0
    z = np.array([0.6, 0.4])
    flash = pt_flash(P, T, z, system, eos)

    if flash.phase != "two-phase":
        pytest.skip("Chosen conditions did not yield a two-phase flash in this model.")

    res = densities_after_flash(flash, eos, system)
    assert res.liquid is not None
    assert res.vapor is not None
    assert np.isfinite(res.liquid.mass_density_kg_per_m3)
    assert np.isfinite(res.vapor.mass_density_kg_per_m3)
    assert res.liquid.mass_density_kg_per_m3 > res.vapor.mass_density_kg_per_m3
