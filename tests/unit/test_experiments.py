"""Consolidated unit tests for the experiments module (CCE, DL, CVD, separators).

Covers:
- Constant Composition Expansion (CCE)
- Differential Liberation (DL) including retained-basis inventory
- Constant Volume Depletion (CVD) including volume-closure regression
- Multi-stage separator calculations and optimization
- Edge-case / invalid-input validation
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.experiments import (
    simulate_cce,
    CCEResult,
    simulate_dl,
    DLResult,
    simulate_cvd,
    CVDResult,
    CVDStepResult,
    calculate_separator_train,
    optimize_separator_pressures,
    SeparatorConditions,
    SeparatorTrainResult,
)
from pvtcore.experiments.cvd import _cvd_step
from pvtcore.models.component import get_component
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.core.constants import R
from pvtcore.core.errors import ValidationError
from pvtcore.flash import calculate_bubble_point
from pvtcore.validation.pete665_assignment import (
    build_assignment_fluid,
    fahrenheit_to_kelvin,
    load_assignment_case,
    psia_to_pa,
    resolve_assignment_temperature_f,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_cell_volume_match(
    *,
    pressure: float,
    temperature: float,
    z_factor: float,
    moles: float,
    target_volume: float,
) -> None:
    reconstructed = moles * z_factor * R.Pa_m3_per_mol_K * temperature / pressure
    assert reconstructed == pytest.approx(target_volume, rel=1e-10, abs=1e-15)


# ---------------------------------------------------------------------------
# CCE
# ---------------------------------------------------------------------------

def test_cce(components):
    """CCE simulation: structure, monotonicity, saturation detection."""
    c1, c3 = components["C1"], components["C3"]
    comps = [c1, c3]
    eos = PengRobinsonEOS(comps)
    z = np.array([0.5, 0.5])
    T = 300.0

    # --- basic run ---
    result = simulate_cce(z, T, comps, eos, 10e6, 1e6, n_steps=10)
    assert isinstance(result, CCEResult)
    assert len(result.steps) > 0
    assert len(result.pressures) == len(result.steps)
    assert len(result.relative_volumes) == len(result.steps)
    assert result.temperature == T
    assert all(len(s.liquid_composition) == len(z) for s in result.steps)
    assert all(len(s.vapor_composition) == len(z) for s in result.steps)

    # --- relative-volume trend ---
    valid = result.relative_volumes[~np.isnan(result.relative_volumes)]
    if len(valid) > 1:
        assert valid[-1] >= valid[0]

    # --- array consistency ---
    result2 = simulate_cce(z, T, comps, eos, 10e6, 1e6, n_steps=15)
    n = len(result2.steps)
    assert len(result2.pressures) == n
    assert len(result2.relative_volumes) == n
    assert len(result2.liquid_dropouts) == n
    for step in result2.steps:
        assert hasattr(step, "compressibility_Z")

    # --- saturation detection above bubble point ---
    case = load_assignment_case()
    temperature_f, _ = resolve_assignment_temperature_f(case, initials="TANS")
    temperature_k = fahrenheit_to_kelvin(temperature_f)
    _ids, asgn_comps, composition = build_assignment_fluid(case)
    asgn_eos = PengRobinsonEOS(asgn_comps)
    bip = np.zeros((len(asgn_comps), len(asgn_comps)), dtype=float)
    bubble = calculate_bubble_point(temperature_k, composition, asgn_comps, asgn_eos, binary_interaction=bip)
    pressure_steps = np.asarray([psia_to_pa(v) for v in case.cce_pressures_psia], dtype=np.float64)

    assert float(bubble.pressure) < float(pressure_steps[-1])

    res_sat = simulate_cce(
        composition, temperature_k, asgn_comps, asgn_eos,
        float(pressure_steps[0]), float(pressure_steps[-1]),
        n_steps=len(pressure_steps), pressure_steps=pressure_steps,
        binary_interaction=bip,
    )
    assert res_sat.saturation_type == "bubble"
    assert res_sat.saturation_pressure == pytest.approx(float(bubble.pressure), abs=250.0)


# ---------------------------------------------------------------------------
# Differential Liberation
# ---------------------------------------------------------------------------

def test_differential_liberation(components):
    """DL simulation: structure, Rs/Bo trends, retained-basis inventory."""
    c1, c3, c7 = components["C1"], components["C3"], components["C7"]
    comps = [c1, c3, c7]
    eos = PengRobinsonEOS(comps)
    z = np.array([0.3, 0.4, 0.3])
    T = 350.0
    P_bubble = 15e6
    P_steps = np.linspace(15e6, 2e6, 8)

    result = simulate_dl(z, T, comps, eos, P_bubble, P_steps)

    # --- basic structure ---
    assert isinstance(result, DLResult)
    assert len(result.steps) > 0
    assert result.temperature == T
    assert result.bubble_pressure == P_bubble
    assert hasattr(result, "Rs_values")
    assert hasattr(result, "Bo_values")
    assert hasattr(result, "converged")

    # --- Rs decreases ---
    valid_Rs = result.Rs_values[~np.isnan(result.Rs_values)]
    if len(valid_Rs) > 1:
        assert valid_Rs[0] >= valid_Rs[-1] * 0.9

    # --- Bo decreases ---
    valid_Bo = result.Bo_values[~np.isnan(result.Bo_values)]
    if len(valid_Bo) > 1:
        assert valid_Bo[0] >= valid_Bo[-1] * 0.8

    # --- retained-basis inventory (from test_cvd_dl_retained_basis) ---
    assert result.steps[0].liquid_moles_remaining == pytest.approx(1.0)
    prev = result.steps[0].liquid_moles_remaining
    for step in result.steps[1:]:
        assert step.liquid_moles_remaining <= prev + 1e-12
        prev = step.liquid_moles_remaining


# ---------------------------------------------------------------------------
# CVD
# ---------------------------------------------------------------------------

def test_cvd(components):
    """CVD simulation: structure, liquid dropout, cumulative gas, volume closure, repeatability."""
    c1, c7 = components["C1"], components["C7"]
    comps_gc = [c1, c7]
    eos_gc = PengRobinsonEOS(comps_gc)
    z_gc = np.array([0.85, 0.15])
    T_gc = 380.0
    P_dew = 25e6

    # --- basic run ---
    result = simulate_cvd(z_gc, T_gc, comps_gc, eos_gc, P_dew, np.linspace(20e6, 5e6, 8))
    assert isinstance(result, CVDResult)
    assert len(result.steps) > 0
    assert result.temperature == T_gc
    assert result.dew_pressure == P_dew
    assert hasattr(result, "liquid_dropouts")
    assert hasattr(result, "cumulative_gas")
    assert hasattr(result, "converged")

    # --- liquid dropout ---
    valid_dropouts = result.liquid_dropouts[~np.isnan(result.liquid_dropouts)]
    if len(valid_dropouts) > 1:
        assert np.max(valid_dropouts) >= 0

    # --- cumulative gas monotonic ---
    valid_gas = result.cumulative_gas[~np.isnan(result.cumulative_gas)]
    if len(valid_gas) > 1:
        for i in range(1, len(valid_gas)):
            assert valid_gas[i] >= valid_gas[i - 1] - 1e-10

    # --- retained moles / cumulative gas fields (from test_cvd_dl_retained_basis) ---
    oil_comps = [c1, components["C3"], c7]
    eos_oil = PengRobinsonEOS(oil_comps)
    z_oil = np.array([0.85, 0.10, 0.05])
    res_oil = simulate_cvd(z_oil, T_gc, oil_comps, eos_oil, P_dew, np.linspace(20e6, 5e6, 8))
    assert res_oil.steps[0].moles_remaining == pytest.approx(1.0)
    prev_rem = res_oil.steps[0].moles_remaining
    prev_cum = res_oil.steps[0].cumulative_gas_produced
    for step in res_oil.steps[1:]:
        assert step.moles_remaining <= prev_rem + 1e-12
        assert step.cumulative_gas_produced >= prev_cum - 1e-12
        prev_rem = step.moles_remaining
        prev_cum = step.cumulative_gas_produced

    # --- single-phase volume closure (from test_cvd_volume_closure) ---
    methane = [c1]
    eos_ch4 = PengRobinsonEOS(methane)
    z_ch4 = np.array([1.0])
    T_ch4 = 250.0
    P_dew_ch4 = 16_758_331.369557615
    P_step_ch4 = 14_080_000.0

    Z_init = eos_ch4.compressibility(P_dew_ch4, T_ch4, z_ch4, phase="vapor")
    if isinstance(Z_init, list):
        Z_init = Z_init[-1]
    V_cell = Z_init * R.Pa_m3_per_mol_K * T_ch4 / P_dew_ch4

    step, z_new, n_new, cumulative_gas = _cvd_step(
        P_step_ch4, T_ch4, z_ch4, 1.0, 0.0, V_cell, methane, eos_ch4, None,
    )
    assert step.gas_produced > 0.0
    assert cumulative_gas == pytest.approx(step.gas_produced)
    assert np.allclose(z_new, z_ch4)
    assert n_new == pytest.approx(step.moles_remaining)
    _assert_cell_volume_match(
        pressure=step.pressure, temperature=T_ch4,
        z_factor=step.Z_two_phase, moles=step.moles_remaining,
        target_volume=V_cell,
    )

    # --- full-path volume closure + repeatability ---
    P_path = np.linspace(P_dew_ch4, max(1e5, P_dew_ch4 * 0.2), 6)
    r1 = simulate_cvd(z_ch4, T_ch4, methane, eos_ch4, P_dew_ch4, P_path)
    r2 = simulate_cvd(z_ch4, T_ch4, methane, eos_ch4, P_dew_ch4, P_path)

    assert r1.converged is True
    assert r2.converged is True
    assert np.array_equal(r1.pressures, r2.pressures)
    assert np.array_equal(r1.liquid_dropouts, r2.liquid_dropouts)
    assert np.array_equal(r1.cumulative_gas, r2.cumulative_gas)

    for s in r1.steps:
        if np.isnan(s.Z_two_phase):
            continue
        if np.isclose(s.liquid_dropout, 0.0) or np.isclose(s.liquid_dropout, 1.0):
            _assert_cell_volume_match(
                pressure=s.pressure, temperature=T_ch4,
                z_factor=s.Z_two_phase, moles=s.moles_remaining,
                target_volume=V_cell,
            )


# ---------------------------------------------------------------------------
# Separator
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n_stages", [1, 2], ids=["single-stage", "two-stage"])
def test_separator(components, n_stages):
    """Separator train: Bo, API, material balance, gas production, optimization."""
    c1, c3, c7 = components["C1"], components["C3"], components["C7"]
    comps = [c1, c3, c7]
    eos = PengRobinsonEOS(comps)
    z = np.array([0.3, 0.4, 0.3])

    stages = [SeparatorConditions(pressure=3e6, temperature=320.0, name="HP Sep")]
    if n_stages == 2:
        stages.append(SeparatorConditions(pressure=0.5e6, temperature=300.0, name="LP Sep"))

    result = calculate_separator_train(
        z, comps, eos, stages,
        reservoir_pressure=30e6, reservoir_temperature=380.0,
    )

    assert isinstance(result, SeparatorTrainResult)
    assert len(result.stages) >= n_stages
    assert result.Bo > 0
    assert 0 <= result.stock_tank_oil_moles <= 1
    assert result.total_gas_moles >= 0
    assert hasattr(result, "stock_tank_oil_composition")
    assert hasattr(result, "Rs")
    assert hasattr(result, "API_gravity")
    assert hasattr(result, "converged")

    if not np.isnan(result.Bo):
        assert 0.5 < result.Bo < 5.0
    if not np.isnan(result.API_gravity):
        assert -10 < result.API_gravity < 100

    total_out = result.stock_tank_oil_moles + result.total_gas_moles
    assert abs(total_out - 1.0) < 0.01

    # --- optimization ---
    opt_stages, opt_result = optimize_separator_pressures(
        z, comps, eos,
        reservoir_pressure=30e6, reservoir_temperature=380.0,
        n_stages=n_stages, temperature=310.0,
    )
    assert len(opt_stages) == n_stages
    assert isinstance(opt_result, SeparatorTrainResult)


# ---------------------------------------------------------------------------
# Edge cases / invalid inputs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "experiment, args, exc",
    [
        pytest.param(
            "cce_neg_temperature",
            dict(fn="cce", T=-100.0, P_start=10e6, P_end=1e6),
            ValidationError,
            id="cce-neg-temperature",
        ),
        pytest.param(
            "cce_neg_pressure",
            dict(fn="cce", T=300.0, P_start=-10e6, P_end=1e6),
            ValidationError,
            id="cce-neg-pressure",
        ),
        pytest.param(
            "dl_neg_bubble",
            dict(fn="dl"),
            ValidationError,
            id="dl-neg-bubble-pressure",
        ),
        pytest.param(
            "cvd_neg_dew",
            dict(fn="cvd"),
            ValidationError,
            id="cvd-neg-dew-pressure",
        ),
        pytest.param(
            "sep_empty_stages",
            dict(fn="sep_empty"),
            ValidationError,
            id="sep-empty-stages",
        ),
        pytest.param(
            "sep_neg_pressure",
            dict(fn="sep_neg"),
            ValidationError,
            id="sep-neg-stage-pressure",
        ),
        pytest.param(
            "opt_zero_stages",
            dict(fn="opt_zero"),
            ValidationError,
            id="opt-zero-stages",
        ),
    ],
)
def test_experiment_edge_cases(components, experiment, args, exc):
    """Invalid inputs must raise ValidationError."""
    c1, c3, c7 = components["C1"], components["C3"], components["C7"]

    fn = args["fn"]
    if fn == "cce":
        comps = [c1, c3]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.5, 0.5])
        with pytest.raises(exc):
            simulate_cce(z, args["T"], comps, eos, args["P_start"], args["P_end"])

    elif fn == "dl":
        comps = [c1, c3, c7]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.3, 0.4, 0.3])
        with pytest.raises(exc):
            simulate_dl(z, 350.0, comps, eos, -15e6, np.linspace(15e6, 1e6, 5))

    elif fn == "cvd":
        comps = [c1, components["C7"]]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.85, 0.15])
        with pytest.raises(exc):
            simulate_cvd(z, 380.0, comps, eos, -25e6, np.linspace(20e6, 5e6, 5))

    elif fn == "sep_empty":
        comps = [c1, c3, c7]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.3, 0.4, 0.3])
        with pytest.raises(exc):
            calculate_separator_train(z, comps, eos, [], reservoir_pressure=30e6, reservoir_temperature=380.0)

    elif fn == "sep_neg":
        comps = [c1, c3, c7]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.3, 0.4, 0.3])
        with pytest.raises(exc):
            calculate_separator_train(
                z, comps, eos, [SeparatorConditions(pressure=-3e6, temperature=320.0)],
                reservoir_pressure=30e6, reservoir_temperature=380.0,
            )

    elif fn == "opt_zero":
        comps = [c1, c3, c7]
        eos = PengRobinsonEOS(comps)
        z = np.array([0.3, 0.4, 0.3])
        with pytest.raises(exc):
            optimize_separator_pressures(
                z, comps, eos, reservoir_pressure=30e6, reservoir_temperature=380.0, n_stages=0,
            )
