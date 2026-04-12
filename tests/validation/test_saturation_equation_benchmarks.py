"""Equation-based benchmark tests for bubble and dew point solvers.

These tests do not use MI-PVT as a scalar truth baseline for saturation
pressures. Instead, they solve the classical fugacity-equilibrium equations
with an independent fixed-point plus bisection reference method and compare the
production saturation solvers against that reference.

MI-PVT remains useful for phase-envelope and other graphical cross-checks, but
it is intentionally not the authoritative baseline here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Literal

import numpy as np
import pytest

from pvtcore.core.errors import PhaseError
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components
from pvtcore.stability.wilson import wilson_k_values


_PRESSURE_SCAN = np.geomspace(1e3, 1e8, 81)
_INNER_SUM_TOL = 1e-11
_INNER_COMP_TOL = 1e-9
_TRIVIAL_TRIAL_TOL = 1e-8


class _NoPhysicalSaturation(RuntimeError):
    """Raised when the reference solve finds only the trivial saturation state."""


@dataclass(frozen=True)
class SaturationReferenceCase:
    """Single equation-based saturation benchmark case."""

    case_id: str
    task: Literal["bubble", "dew"]
    temperature_k: float
    component_ids: tuple[str, ...]
    feed: tuple[float, ...]
    fluid_family: str = "generic"
    pressure_atol_pa: float = 1e3
    composition_atol: float = 1e-6
    guess_pressures_pa: tuple[float | None, ...] = (None, 1e5, 1e6, 5e7)


@dataclass(frozen=True)
class ReferenceSaturationResult:
    """Independent reference saturation solve result."""

    pressure_pa: float
    incipient_composition: np.ndarray
    residual: float


def _normalize(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    arr = np.clip(arr, 1e-300, None)
    return arr / arr.sum()


def _is_trivial_trial(
    feed: np.ndarray,
    trial: np.ndarray,
    *,
    tol: float = _TRIVIAL_TRIAL_TOL,
    active_tol: float = 1e-12,
) -> bool:
    """Return True when a multicomponent trial collapses to the feed state."""
    active = feed > active_tol
    if np.count_nonzero(active) <= 1:
        return False
    return float(np.max(np.abs(trial[active] - feed[active]))) <= tol


def _dew_residual(
    pressure: float,
    temperature_k: float,
    vapor_feed: np.ndarray,
    comp_list: list,
    eos: PengRobinsonEOS,
) -> tuple[float, np.ndarray]:
    """Return dew residual sum(y/K)-1 and the incipient liquid trial."""
    y = _normalize(vapor_feed)
    phi_v = eos.fugacity_coefficient(pressure, temperature_k, y, phase="vapor")
    K = np.clip(wilson_k_values(pressure, temperature_k, comp_list), 1e-12, 1e12)
    x = _normalize(y / K)

    residual = float("nan")
    for _ in range(100):
        phi_l = eos.fugacity_coefficient(pressure, temperature_k, x, phase="liquid")
        K = np.clip(phi_l / phi_v, 1e-12, 1e12)
        x_unnormalized = y / K
        residual = float(np.sum(x_unnormalized) - 1.0)
        x_new = _normalize(x_unnormalized)

        if _is_trivial_trial(y, x_new):
            raise _NoPhysicalSaturation("Dew reference solve collapsed to the trivial x=y state.")

        if abs(residual) < _INNER_SUM_TOL and np.max(np.abs(x_new - x)) < _INNER_COMP_TOL:
            return residual, x_new

        x = _normalize(0.5 * x + 0.5 * x_new)

    return residual, x


def _bubble_residual(
    pressure: float,
    temperature_k: float,
    liquid_feed: np.ndarray,
    comp_list: list,
    eos: PengRobinsonEOS,
) -> tuple[float, np.ndarray]:
    """Return bubble residual sum(Kx)-1 and the incipient vapor trial."""
    x = _normalize(liquid_feed)
    phi_l = eos.fugacity_coefficient(pressure, temperature_k, x, phase="liquid")
    K = np.clip(wilson_k_values(pressure, temperature_k, comp_list), 1e-12, 1e12)
    y = _normalize(K * x)

    residual = float("nan")
    for _ in range(100):
        phi_v = eos.fugacity_coefficient(pressure, temperature_k, y, phase="vapor")
        K = np.clip(phi_l / phi_v, 1e-12, 1e12)
        y_unnormalized = K * x
        residual = float(np.sum(y_unnormalized) - 1.0)
        y_new = _normalize(y_unnormalized)

        if _is_trivial_trial(x, y_new):
            raise _NoPhysicalSaturation("Bubble reference solve collapsed to the trivial y=x state.")

        if abs(residual) < _INNER_SUM_TOL and np.max(np.abs(y_new - y)) < _INNER_COMP_TOL:
            return residual, y_new

        y = _normalize(0.5 * y + 0.5 * y_new)

    return residual, y


def _find_pressure_bracket(
    residual_fn,
) -> tuple[float, float] | None:
    """Scan log-pressure space for the first usable sign-change bracket."""
    previous_pressure: float | None = None
    previous_residual: float | None = None

    for pressure in _PRESSURE_SCAN:
        try:
            residual, _ = residual_fn(float(pressure))
        except (PhaseError, _NoPhysicalSaturation, FloatingPointError, ValueError):
            continue

        if not np.isfinite(residual):
            continue

        if abs(residual) < 1e-12:
            return float(pressure), float(pressure)

        if previous_residual is not None and previous_residual * residual < 0.0:
            return previous_pressure, float(pressure)

        previous_pressure = float(pressure)
        previous_residual = float(residual)

    return None


def _bisect_reference_root(
    residual_fn,
    bracket: tuple[float, float],
) -> ReferenceSaturationResult:
    """Solve a scalar saturation residual on a bracketing interval."""
    lo, hi = bracket
    if lo == hi:
        residual, trial = residual_fn(lo)
        return ReferenceSaturationResult(lo, np.asarray(trial, dtype=float), float(residual))

    flo, _ = residual_fn(lo)
    mid = lo
    trial = None
    residual = float("nan")

    for _ in range(100):
        mid = math.sqrt(lo * hi)
        residual, trial = residual_fn(mid)
        if abs(residual) < 1e-10:
            break
        if flo * residual < 0.0:
            hi = mid
        else:
            lo = mid
            flo = residual

    return ReferenceSaturationResult(
        pressure_pa=float(mid),
        incipient_composition=np.asarray(trial, dtype=float),
        residual=float(residual),
    )


def _solve_reference_case(case: SaturationReferenceCase) -> ReferenceSaturationResult:
    """Solve a benchmark case with the independent equation-based reference method."""
    components = load_components()
    comp_list = [components[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(comp_list)
    feed = _normalize(case.feed)

    if case.task == "dew":
        residual_fn = lambda pressure: _dew_residual(pressure, case.temperature_k, feed, comp_list, eos)
    else:
        residual_fn = lambda pressure: _bubble_residual(pressure, case.temperature_k, feed, comp_list, eos)

    bracket = _find_pressure_bracket(residual_fn)
    if bracket is None:
        raise _NoPhysicalSaturation(f"No non-trivial {case.task} reference bracket found for {case.case_id}.")
    return _bisect_reference_root(residual_fn, bracket)


def _phase_average_mw(comp_list: list, composition: np.ndarray) -> float:
    """Return the composition-weighted average molecular weight."""
    weights = np.array([component.MW for component in comp_list], dtype=float)
    return float(np.dot(np.asarray(composition, dtype=float), weights))


def _run_production_case(
    case: SaturationReferenceCase,
    comp_list: list,
    eos: PengRobinsonEOS,
    *,
    pressure_initial: float | None,
):
    """Run the production saturation solver with a selected initial pressure."""
    feed = _normalize(case.feed)
    kwargs = {
        "pressure_initial": pressure_initial,
        "post_check_stability_flip": True,
    }
    if case.task == "dew":
        return calculate_dew_point(case.temperature_k, feed, comp_list, eos, **kwargs)
    return calculate_bubble_point(case.temperature_k, feed, comp_list, eos, **kwargs)


def _assert_production_matches_reference(case: SaturationReferenceCase, reference: ReferenceSaturationResult) -> None:
    """Compare the production solver against the independent reference across guesses."""
    components = load_components()
    comp_list = [components[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(comp_list)
    feed = _normalize(case.feed)
    feed_mw = _phase_average_mw(comp_list, feed)
    solved_pressures: list[float] = []

    for guess in case.guess_pressures_pa:
        production = _run_production_case(
            case,
            comp_list,
            eos,
            pressure_initial=guess,
        )
        solved_pressures.append(float(production.pressure))

        assert production.converged, f"{case.case_id} {case.task} solver did not converge for guess={guess!r}"
        assert float(production.pressure) == pytest.approx(reference.pressure_pa, abs=case.pressure_atol_pa)

        if case.task == "dew":
            incipient = np.asarray(production.liquid_composition, dtype=float)
            assert _phase_average_mw(comp_list, incipient) > feed_mw
        else:
            incipient = np.asarray(production.vapor_composition, dtype=float)
            assert _phase_average_mw(comp_list, incipient) < feed_mw

        np.testing.assert_allclose(
            incipient,
            reference.incipient_composition,
            atol=case.composition_atol,
            rtol=0.0,
        )

    guess_span_atol = max(case.pressure_atol_pa, 5e2)
    for pressure_pa in solved_pressures[1:]:
        assert pressure_pa == pytest.approx(solved_pressures[0], abs=guess_span_atol)


DEW_CASES = [
    SaturationReferenceCase(
        case_id="synthetic_c1_c4_dew_equation",
        task="dew",
        temperature_k=280.0,
        component_ids=("C1", "C4"),
        feed=(0.4, 0.6),
        fluid_family="control_binary",
    ),
    SaturationReferenceCase(
        case_id="literature_c1_c3_sage_lacey_dew_equation",
        task="dew",
        temperature_k=277.59,
        component_ids=("C1", "C3"),
        feed=(0.778, 0.222),
        fluid_family="lean_gas",
    ),
    SaturationReferenceCase(
        case_id="literature_co2_c3_reamer_sage_dew_equation",
        task="dew",
        temperature_k=310.93,
        component_ids=("CO2", "C3"),
        feed=(0.663, 0.337),
        fluid_family="co2_rich_binary",
    ),
    SaturationReferenceCase(
        case_id="multicomponent_co2_rich_dew_equation",
        task="dew",
        temperature_k=260.0,
        component_ids=("CO2", "C1", "C2", "C3", "C4", "C5"),
        feed=(0.30, 0.55, 0.08, 0.04, 0.02, 0.01),
        fluid_family="co2_rich_gas",
        pressure_atol_pa=2e3,
        composition_atol=2e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_dry_gas_a_dew_equation",
        task="dew",
        temperature_k=260.0,
        component_ids=("N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"),
        feed=(0.010, 0.015, 0.820, 0.070, 0.035, 0.012, 0.010, 0.008, 0.007, 0.005, 0.003, 0.003, 0.002),
        fluid_family="dry_gas",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_dry_gas_b_dew_equation",
        task="dew",
        temperature_k=280.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"),
        feed=(0.012, 0.045, 0.003, 0.760, 0.080, 0.045, 0.012, 0.012, 0.008, 0.007, 0.006, 0.004, 0.003, 0.003),
        fluid_family="dry_gas",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_gas_condensate_a_dew_equation",
        task="dew",
        temperature_k=320.0,
        component_ids=("N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12"),
        feed=(0.006, 0.025, 0.640, 0.110, 0.075, 0.025, 0.025, 0.018, 0.016, 0.014, 0.014, 0.012, 0.010, 0.010),
        fluid_family="gas_condensate",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_gas_condensate_b_dew_equation",
        task="dew",
        temperature_k=330.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12"),
        feed=(0.004, 0.018, 0.008, 0.580, 0.120, 0.085, 0.030, 0.028, 0.020, 0.019, 0.018, 0.018, 0.017, 0.020, 0.015),
        fluid_family="gas_condensate",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_co2_rich_gas_a_dew_equation",
        task="dew",
        temperature_k=290.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"),
        feed=(0.008, 0.460, 0.010, 0.290, 0.070, 0.045, 0.020, 0.018, 0.012, 0.012, 0.011, 0.010, 0.008, 0.006),
        fluid_family="co2_rich_gas",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_co2_rich_gas_b_dew_equation",
        task="dew",
        temperature_k=300.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"),
        feed=(0.010, 0.360, 0.030, 0.370, 0.080, 0.055, 0.020, 0.020, 0.013, 0.013, 0.011, 0.009, 0.006, 0.003),
        fluid_family="co2_rich_gas",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
]


BUBBLE_CASES = [
    SaturationReferenceCase(
        case_id="synthetic_c1_c4_bubble_equation",
        task="bubble",
        temperature_k=280.0,
        component_ids=("C1", "C4"),
        feed=(0.4, 0.6),
        fluid_family="control_binary",
    ),
    SaturationReferenceCase(
        case_id="literature_c1_c3_sage_lacey_bubble_equation",
        task="bubble",
        temperature_k=277.59,
        component_ids=("C1", "C3"),
        feed=(0.207, 0.793),
        fluid_family="lean_oil_binary",
    ),
    SaturationReferenceCase(
        case_id="reservoir_volatile_oil_a_bubble_equation",
        task="bubble",
        temperature_k=360.0,
        component_ids=("N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10"),
        feed=(0.0021, 0.0187, 0.3478, 0.0712, 0.0934, 0.0302, 0.0431, 0.0276, 0.0418, 0.0574, 0.0835, 0.0886, 0.0946),
        fluid_family="volatile_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_volatile_oil_b_bubble_equation",
        task="bubble",
        temperature_k=350.0,
        component_ids=("N2", "CO2", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12"),
        feed=(0.0015, 0.015, 0.290, 0.080, 0.095, 0.034, 0.046, 0.032, 0.046, 0.065, 0.094, 0.092, 0.065, 0.045),
        fluid_family="volatile_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_black_oil_a_bubble_equation",
        task="bubble",
        temperature_k=380.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12", "C14"),
        feed=(0.001, 0.010, 0.004, 0.180, 0.055, 0.070, 0.040, 0.050, 0.042, 0.050, 0.070, 0.095, 0.102, 0.085, 0.080, 0.066),
        fluid_family="black_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_black_oil_b_bubble_equation",
        task="bubble",
        temperature_k=390.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12", "C14", "C16"),
        feed=(0.001, 0.008, 0.006, 0.140, 0.045, 0.060, 0.038, 0.045, 0.042, 0.048, 0.070, 0.095, 0.105, 0.100, 0.090, 0.070, 0.043),
        fluid_family="black_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_sour_oil_a_bubble_equation",
        task="bubble",
        temperature_k=340.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12", "C14", "C16"),
        feed=(0.001, 0.050, 0.070, 0.220, 0.060, 0.070, 0.030, 0.040, 0.030, 0.040, 0.060, 0.085, 0.090, 0.080, 0.065, 0.050, 0.029),
        fluid_family="sour_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
    SaturationReferenceCase(
        case_id="reservoir_sour_oil_b_bubble_equation",
        task="bubble",
        temperature_k=330.0,
        component_ids=("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12", "C14", "C16"),
        feed=(0.001, 0.035, 0.090, 0.180, 0.055, 0.065, 0.030, 0.040, 0.030, 0.040, 0.065, 0.090, 0.095, 0.085, 0.070, 0.055, 0.039),
        fluid_family="sour_oil",
        pressure_atol_pa=5e3,
        composition_atol=5e-6,
    ),
]


@pytest.mark.parametrize("case", DEW_CASES, ids=lambda case: case.case_id)
def test_dew_point_matches_independent_equation_reference(case: SaturationReferenceCase) -> None:
    """Production dew solver should match an independent fugacity-equation reference solve."""
    reference = _solve_reference_case(case)
    _assert_production_matches_reference(case, reference)


@pytest.mark.parametrize("case", BUBBLE_CASES, ids=lambda case: case.case_id)
def test_bubble_point_matches_independent_equation_reference(case: SaturationReferenceCase) -> None:
    """Production bubble solver should match an independent fugacity-equation reference solve."""
    reference = _solve_reference_case(case)
    _assert_production_matches_reference(case, reference)


@pytest.mark.parametrize("component_id", ["C1", "C3", "C6"])
def test_pure_component_dew_equals_bubble(component_id: str) -> None:
    """For a pure component below Tc, dew and bubble pressures must coincide."""
    components = load_components()
    component = components[component_id]
    temperature_k = 0.7 * component.Tc
    comp_list = [component]
    eos = PengRobinsonEOS(comp_list)
    z = np.array([1.0], dtype=float)

    bubble = calculate_bubble_point(temperature_k, z, comp_list, eos)
    dew = calculate_dew_point(temperature_k, z, comp_list, eos)

    assert bubble.converged
    assert dew.converged
    assert float(dew.pressure) == pytest.approx(float(bubble.pressure), abs=1e-3)


def test_dew_point_negative_path_has_no_nontrivial_reference_bracket() -> None:
    """Above the practical dew regime, the reference solve should find no non-trivial dew boundary."""
    case = SaturationReferenceCase(
        case_id="c1_c4_high_temperature_no_nontrivial_dew",
        task="dew",
        temperature_k=450.0,
        component_ids=("C1", "C4"),
        feed=(0.4, 0.6),
    )

    components = load_components()
    comp_list = [components[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(comp_list)
    feed = _normalize(case.feed)
    residual_fn = lambda pressure: _dew_residual(pressure, case.temperature_k, feed, comp_list, eos)

    assert _find_pressure_bracket(residual_fn) is None

    with pytest.raises(PhaseError) as excinfo:
        calculate_dew_point(case.temperature_k, feed, comp_list, eos)

    assert excinfo.value.details.get("reason") in {"no_saturation", "degenerate_trivial_boundary"}


def test_bubble_point_negative_path_has_no_nontrivial_reference_bracket() -> None:
    """A degenerate high-temperature CO2-rich liquid should not certify a bubble boundary."""
    case = SaturationReferenceCase(
        case_id="co2_rich_high_temperature_no_nontrivial_bubble",
        task="bubble",
        temperature_k=573.15,
        component_ids=("CO2", "C1", "C2", "C3", "C4"),
        feed=(0.6498, 0.1057, 0.1058, 0.1235, 0.0152),
        fluid_family="co2_rich_near_critical",
    )

    components = load_components()
    comp_list = [components[cid] for cid in case.component_ids]
    eos = PengRobinsonEOS(comp_list)
    feed = _normalize(case.feed)
    residual_fn = lambda pressure: _bubble_residual(pressure, case.temperature_k, feed, comp_list, eos)

    assert _find_pressure_bracket(residual_fn) is None

    with pytest.raises(PhaseError) as excinfo:
        calculate_bubble_point(case.temperature_k, feed, comp_list, eos)

    assert excinfo.value.details.get("reason") in {"no_saturation", "degenerate_trivial_boundary"}
