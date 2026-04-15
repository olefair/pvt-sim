"""Consolidated unit tests for the characterization pipeline.

Covers:
- Pedersen plus-fraction splitting (parametrized C7+ inputs, TBP mode)
- Katz / Lohrenz splitting methods
- Lumping, delumping, round-trip closure
- BIP matrix construction and correlations
- Edge-case / invalid-input validation
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.characterization import (
    # Plus-fraction splitting
    split_plus_fraction_pedersen,
    split_plus_fraction_katz,
    katz_classic_split,
    split_plus_fraction_lohrenz,
    PedersenSplitResult,
    KatzSplitResult,
    LohrenzSplitResult,
    # SCN properties
    get_scn_properties,
    SCNProperties,
    # Lumping
    lump_by_mw_groups,
    lump_by_indices,
    suggest_lumping_groups,
    LumpingResult,
    # Delumping
    delump_kvalue_interpolation,
    delump_simple_distribution,
    DelumpingResult,
    # BIP
    build_bip_matrix,
    BIPMethod,
    get_default_bip,
    chueh_prausnitz_kij,
    # High-level pipeline
    CharacterizationConfig,
    PlusFractionSpec,
    characterize_fluid,
)
from pvtcore.characterization.plus_splitting.pedersen import PedersenTBPCutConstraint
from pvtcore.core.errors import CharacterizationError


# ---------------------------------------------------------------------------
# Pedersen split (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "z_plus, mw_plus, n_start, n_end",
    [
        pytest.param(0.25, 215.0, 7, 20, id="C7+-default-range"),
        pytest.param(0.25, 215.0, 7, 30, id="C7+-wide-range"),
        pytest.param(0.10, 180.0, 7, 20, id="lighter-C7+"),
    ],
)
def test_pedersen_split(z_plus, mw_plus, n_start, n_end):
    """Pedersen split: structure, mole-balance, MW balance, decay shape, TBP mode."""
    result = split_plus_fraction_pedersen(z_plus=z_plus, MW_plus=mw_plus, n_start=n_start, n_end=n_end)

    assert isinstance(result, PedersenSplitResult)
    assert len(result.n) == len(result.z) == len(result.MW)
    assert result.n[0] == n_start
    assert result.n[-1] == n_end
    assert len(result.n) == n_end - n_start + 1
    assert np.all(result.z > 0.0)

    # mole-fraction closure
    assert float(result.z.sum()) == pytest.approx(z_plus, abs=1e-10)

    # mass-balance closure
    assert float((result.z * result.MW).sum()) == pytest.approx(z_plus * mw_plus, abs=1e-8)

    # weighted MW close to target
    z_norm = result.z / result.z.sum()
    mw_avg = float((z_norm * result.MW).sum())
    assert abs(mw_avg - mw_plus) / mw_plus < 0.05

    # exponential decay (only meaningful when the range is wide enough)
    if n_end - n_start >= 20:
        assert result.z[0] > result.z[-1]

    # --- TBP fit mode (only for the default parameterization) ---
    if z_plus == 0.25 and mw_plus == 215.0 and n_start == 7:
        tbp_cuts = (
            PedersenTBPCutConstraint(name="C7", carbon_number=7, carbon_number_end=7, z=0.020, mw=96.0),
            PedersenTBPCutConstraint(name="C8", carbon_number=8, carbon_number_end=8, z=0.015, mw=110.0),
            PedersenTBPCutConstraint(name="C9", carbon_number=9, carbon_number_end=9, z=0.015, mw=124.0),
        )
        tbp_res = split_plus_fraction_pedersen(
            z_plus=0.05, MW_plus=108.6, n_start=7, n_end=12,
            solve_ab_from="fit_to_tbp", tbp_cuts=tbp_cuts,
        )
        assert tbp_res.solve_ab_from == "fit_to_tbp"
        assert tbp_res.tbp_cut_rms_relative_error is not None
        assert tbp_res.tbp_cut_rms_relative_error < 0.35
        assert float(tbp_res.z.sum()) == pytest.approx(0.05, abs=1e-10)


# ---------------------------------------------------------------------------
# Katz / Lohrenz splitting
# ---------------------------------------------------------------------------

def test_split_methods():
    """Katz and Lohrenz splits: structure, mole balance, reasonable MW."""
    z_plus = 0.25
    mw_plus = 215.0

    # --- Katz ---
    katz_res = split_plus_fraction_katz(z_plus=z_plus, MW_plus=mw_plus)
    assert isinstance(katz_res, KatzSplitResult)
    assert katz_res.z.sum() > 0
    assert abs(katz_res.z.sum() - z_plus) / z_plus < 1e-6

    classic = katz_classic_split(z_plus=z_plus)
    assert abs(classic.A - 1.38205 * z_plus) < 0.01
    assert abs(classic.B - 0.25903) < 0.01

    # --- Lohrenz ---
    lohrenz_res = split_plus_fraction_lohrenz(z_plus=z_plus, MW_plus=mw_plus)
    assert isinstance(lohrenz_res, LohrenzSplitResult)
    assert len(lohrenz_res.z) > 0
    assert abs(lohrenz_res.z.sum() - z_plus) / z_plus < 1e-6
    assert lohrenz_res.A < 0.01

    # --- All methods: mole balance + MW reasonableness ---
    for name, fn in [
        ("Pedersen", split_plus_fraction_pedersen),
        ("Katz", split_plus_fraction_katz),
        ("Lohrenz", split_plus_fraction_lohrenz),
    ]:
        r = fn(z_plus=z_plus, MW_plus=mw_plus)
        assert abs(r.z.sum() - z_plus) / z_plus < 1e-5, f"{name} mole balance"
        z_n = r.z / r.z.sum()
        mw_avg = float((z_n * r.MW).sum())
        assert abs(mw_avg - mw_plus) / mw_plus < 0.20, f"{name} MW avg {mw_avg:.1f} vs {mw_plus}"


# ---------------------------------------------------------------------------
# Lumping → delumping round-trip
# ---------------------------------------------------------------------------

def test_lumping_delumping_roundtrip():
    """Split, lump, delump — assert mole-fraction and MW closure."""
    # Build resolved + plus-fraction input
    resolved = [
        ("C1", 0.50), ("C2", 0.10), ("C3", 0.05),
        ("C4", 0.05), ("C5", 0.03), ("C6", 0.02),
    ]
    plus = PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7)
    cfg = CharacterizationConfig(lumping_enabled=True, lumping_n_groups=8)

    result = characterize_fluid(resolved, plus_fraction=plus, config=cfg)

    assert result.lumping is not None
    assert len(result.component_ids) == len(resolved) + 8
    assert np.isclose(float(result.composition.sum()), 1.0)

    # pseudo part sums to z_plus
    z_pseudo = result.composition[len(resolved):]
    assert np.isclose(float(z_pseudo.sum()), plus.z_plus)

    # MW balance preserved
    scn_z = result.lumping.scn_z
    scn_mw = result.lumping.scn_props.mw
    lump_z = result.lumping.lump_z
    lump_mw = np.array([c.MW for c in result.lumping.lump_components], dtype=float)

    assert float(np.dot(lump_z, lump_mw)) == pytest.approx(float(np.dot(scn_z, scn_mw)), abs=1e-12)

    # delumping exactly reconstructs SCN distribution
    scn_recon = result.lumping.delump_scn(lump_z)
    assert np.allclose(scn_recon, scn_z, atol=1e-14, rtol=0.0)

    # --- legacy contiguous method ---
    cfg_cont = CharacterizationConfig(lumping_enabled=True, lumping_n_groups=4, lumping_method="contiguous")
    result_cont = characterize_fluid(
        [("C1", 0.50), ("C2", 0.25)],
        plus_fraction=PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7),
        config=cfg_cont,
    )
    assert result_cont.lumping is not None
    assert len(result_cont.lumping.lump_component_ids) == 4

    # --- too many groups → error ---
    with pytest.raises(CharacterizationError):
        characterize_fluid(
            [("C1", 0.75)],
            plus_fraction=PlusFractionSpec(z_plus=0.25, mw_plus=215.0, n_start=7),
            config=CharacterizationConfig(lumping_enabled=True, lumping_n_groups=100),
        )

    # --- standalone lump / delump helpers ---
    n_comp = 20
    sample = {
        "z": np.random.dirichlet(np.ones(n_comp)),
        "MW": np.linspace(100, 400, n_comp),
        "Tc": np.linspace(500, 800, n_comp),
        "Pc": np.linspace(3e6, 1.5e6, n_comp),
        "Vc": np.linspace(0.0004, 0.001, n_comp),
        "omega": np.linspace(0.3, 0.8, n_comp),
    }
    lump_res = lump_by_mw_groups(n_groups=5, **sample)
    assert isinstance(lump_res, LumpingResult)
    assert lump_res.n_lumped <= 5
    assert lump_res.n_original == n_comp
    assert abs(sum(c.z for c in lump_res.components) - sample["z"].sum()) < 1e-10
    for c in lump_res.components:
        assert sample["MW"].min() <= c.MW <= sample["MW"].max()
        assert sample["Tc"].min() <= c.Tc <= sample["Tc"].max()

    idx_res = lump_by_indices(group_indices=[[0, 1, 2], [3, 4, 5], [6, 7, 8, 9], list(range(10, 20))], **sample)
    assert idx_res.n_lumped == 4

    groups = suggest_lumping_groups(MW=sample["MW"], n_groups=8, preserve_light=3)
    assert len(groups) == 8
    assert all(len(g) == 1 for g in groups[:3])

    # --- simple delumping ---
    z_det = np.array([0.1, 0.1, 0.1, 0.1, 0.1, 0.15, 0.15, 0.2])
    x_l = np.array([0.55, 0.45])
    y_l = np.array([0.65, 0.35])
    mapping = [[0, 1, 2, 3, 4], [5, 6, 7]]
    x_d, y_d = delump_simple_distribution(x_lumped=x_l, y_lumped=y_l, z_detailed=z_det, lump_mapping=mapping)
    assert abs(x_d.sum() - 1.0) < 1e-10
    assert abs(y_d.sum() - 1.0) < 1e-10

    # --- K-value delumping ---
    MW_det = np.array([100, 120, 140, 160, 180, 200, 220, 250])
    kv_res = delump_kvalue_interpolation(
        K_lumped=np.array([2.0, 0.5]),
        x_lumped=np.array([0.4, 0.6]),
        y_lumped=np.array([0.7, 0.3]),
        MW_lumped=np.array([140, 220]),
        z_detailed=z_det, MW_detailed=MW_det, lump_mapping=mapping,
    )
    assert isinstance(kv_res, DelumpingResult)
    assert len(kv_res.x) == 8
    assert abs(kv_res.x.sum() - 1.0) < 1e-10


# ---------------------------------------------------------------------------
# BIP matrix
# ---------------------------------------------------------------------------

def test_bip_matrix():
    """BIP correlations: defaults, symmetry, custom overrides, Chueh-Prausnitz."""
    # --- default lookup ---
    assert get_default_bip("N2", "C1") == 0.025
    assert get_default_bip("CO2", "C1") == 0.105
    assert get_default_bip("N2", "C1") == get_default_bip("C1", "N2")

    # --- Chueh-Prausnitz ---
    kij = chueh_prausnitz_kij(190.6, 540.2, A=0.01, B=3.0)
    assert 0.0 <= kij <= 0.05
    assert abs(chueh_prausnitz_kij(300.0, 300.0, A=0.1, B=1.0)) < 1e-10

    # --- zero matrix ---
    names = ["C1", "C2", "C3"]
    Tc = np.array([190.6, 305.3, 369.9])
    zero_res = build_bip_matrix(component_ids=names, Tc=Tc, method=BIPMethod.ZERO)
    assert zero_res.kij.shape == (3, 3)
    assert np.allclose(zero_res.kij, 0.0)

    # --- defaults matrix ---
    names5 = ["N2", "CO2", "C1", "C2", "C3"]
    Tc5 = np.array([126.19, 304.18, 190.6, 305.3, 369.9])
    def_res = build_bip_matrix(component_ids=names5, Tc=Tc5, method=BIPMethod.DEFAULT_VALUES)
    assert def_res.kij.shape == (5, 5)
    assert np.allclose(def_res.kij, def_res.kij.T)
    assert np.allclose(np.diag(def_res.kij), 0.0)
    assert def_res.get_kij_by_name("N2", "C1") == 0.025

    # --- custom override ---
    cust_res = build_bip_matrix(
        component_ids=names, Tc=Tc, method=BIPMethod.DEFAULT_VALUES,
        custom_bips={("C1", "C3"): 0.05},
    )
    assert cust_res.get_kij_by_name("C1", "C3") == 0.05
    assert cust_res.get_kij_by_name("C3", "C1") == 0.05

    # --- SCN properties ---
    props = get_scn_properties(n_start=7, n_end=20)
    assert isinstance(props, SCNProperties)
    assert len(props.n) == 14
    assert props.n[0] == 7
    assert props.n[-1] == 20
    assert len(props.mw) == len(props.n)
    assert all(props.mw[i] < props.mw[i + 1] for i in range(len(props.mw) - 1))
    assert all(props.tb_k[i] < props.tb_k[i + 1] for i in range(len(props.tb_k) - 1))

    ext = get_scn_properties(n_start=7, n_end=60, extrapolate=True)
    assert ext.n[-1] == 60
    assert np.isfinite(ext.mw[-1])


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kind, kwargs",
    [
        pytest.param("pedersen_neg_z", dict(z_plus=-0.1, MW_plus=200.0), id="pedersen-neg-z"),
        pytest.param("pedersen_neg_mw", dict(z_plus=0.25, MW_plus=-200.0), id="pedersen-neg-mw"),
        pytest.param("pedersen_zero_z", dict(z_plus=0.0, MW_plus=200.0), id="pedersen-zero-z"),
        pytest.param("pedersen_zero_mw", dict(z_plus=0.1, MW_plus=0.0), id="pedersen-zero-mw"),
        pytest.param("pedersen_inverted_range", dict(z_plus=0.1, MW_plus=200.0, n_start=10, n_end=7), id="pedersen-inverted-range"),
        pytest.param("scn_no_extrapolate", dict(), id="scn-no-extrapolate"),
    ],
)
def test_characterization_edge_cases(kind, kwargs):
    """Invalid characterization inputs must raise ValueError."""
    if kind.startswith("pedersen"):
        with pytest.raises(ValueError):
            split_plus_fraction_pedersen(**kwargs)
    elif kind == "scn_no_extrapolate":
        with pytest.raises(ValueError):
            get_scn_properties(n_start=7, n_end=50, extrapolate=False)
