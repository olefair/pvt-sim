"""Unit tests for the development continuation kernel."""

from __future__ import annotations

import os

import numpy as np
import pytest

from pvtcore.envelope.continuation import (
    _critical_probe_temperatures,
    _shared_trivial_endpoint_pressures,
    resolve_local_branch_candidates,
    seed_continuation_state,
    trace_branch_continuation_adaptive,
    trace_branch_continuation,
    trace_envelope_continuation,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def test_local_continuation_candidates_capture_multiple_c1_c10_bubble_families() -> None:
    """Continuation candidates should keep only the certified C1/C10 bubble family."""
    components = load_components()
    mixture = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.5, 0.5], dtype=float)

    candidates = resolve_local_branch_candidates(
        branch="bubble",
        temperature=440.0,
        composition=z,
        eos=eos,
        n_pressure_points=120,
    )

    pressures_bar = [candidate.pressure / 1.0e5 for candidate in candidates]

    assert len(candidates) == 1
    assert 150.0 < pressures_bar[0] < 175.0


def test_seed_continuation_state_can_target_low_pressure_local_family() -> None:
    """Explicit pressure seeds should still land on the only certified branch family."""
    components = load_components()
    mixture = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.5, 0.5], dtype=float)

    state = seed_continuation_state(
        branch="bubble",
        temperature=440.0,
        composition=z,
        components=mixture,
        eos=eos,
        pressure_seed=12.5e5,
        n_pressure_points=120,
    )

    assert 150.0 < state.pressure / 1.0e5 < 175.0


def test_local_continuation_recovery_finds_narrow_co2_rich_upper_bubble_root() -> None:
    """Interval refinement should recover narrow upper bubble roots consistently."""
    components = load_components()
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)

    candidates_300 = resolve_local_branch_candidates(
        branch="bubble",
        temperature=300.0,
        composition=z,
        eos=eos,
        n_pressure_points=160,
    )
    candidates_310 = resolve_local_branch_candidates(
        branch="bubble",
        temperature=310.0,
        composition=z,
        eos=eos,
        n_pressure_points=160,
    )

    assert len(candidates_300) == 1
    assert len(candidates_310) == 0
    assert 66.0 < candidates_300[0].pressure / 1.0e5 < 67.0


def test_trace_branch_continuation_stays_on_high_pressure_c1_c10_family() -> None:
    """Continuation should stay on the nearby high-pressure bubble family."""
    components = load_components()
    mixture = [components["C1"], components["C10"]]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.5, 0.5], dtype=float)

    trace = trace_branch_continuation(
        branch="bubble",
        temperatures=[320.0, 360.0, 400.0, 440.0, 480.0],
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=120,
    )

    pressures_bar = np.array([state.pressure / 1.0e5 for state in trace.states], dtype=float)

    assert trace.termination_reason is None
    assert len(trace.states) == 5
    assert np.all(pressures_bar > 130.0)
    assert np.max(np.abs(np.diff(pressures_bar))) < 25.0


def test_trace_branch_continuation_reports_trivial_collapse_for_co2_rich_bubble() -> None:
    """CO2-rich bubble branch should stop once only trivial local roots remain."""
    components = load_components()
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)

    trace = trace_branch_continuation(
        branch="bubble",
        temperatures=[280.0, 290.0, 300.0, 305.0, 310.0, 315.0],
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )

    pressures_bar = [state.pressure / 1.0e5 for state in trace.states]

    assert len(trace.states) == 4
    assert 45.0 < pressures_bar[0] < 55.0
    assert 52.0 < pressures_bar[1] < 62.0
    assert 62.0 < pressures_bar[2] < 70.0
    assert 69.0 < pressures_bar[3] < 72.0
    assert trace.termination_reason == "no_local_root_candidates"
    assert trace.termination_temperature == 310.0


def test_trace_envelope_continuation_switches_c2_c3_near_critical() -> None:
    """Combined continuation should promote a critical junction and switch to dew."""
    components = load_components()
    mixture = [components["C2"], components["C3"]]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.5, 0.5], dtype=float)

    result = trace_envelope_continuation(
        temperatures=[325.0, 330.0, 335.0, 340.0],
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )

    assert result.critical_state is not None
    assert 329.5 <= result.critical_state.temperature <= 336.0
    assert 37.0 <= result.critical_state.pressure / 1.0e5 <= 45.0
    assert result.switched is True
    assert len(result.bubble_states) >= 2
    assert len(result.dew_states) >= 3
    assert result.dew_states[0].temperature <= result.critical_state.temperature <= result.dew_states[-1].temperature
    critical_dew_neighbor = min(
        result.dew_states,
        key=lambda state: abs(state.temperature - result.critical_state.temperature),
    )
    assert abs(critical_dew_neighbor.temperature - result.critical_state.temperature) <= 0.6


def test_trace_envelope_continuation_detects_co2_rich_critical_from_branch_closest_approach() -> None:
    """Adaptive continuation should resolve the CO2-rich upper critical neighborhood consistently."""
    if os.getenv("PVTSIM_RUN_SLOW") != "1":
        pytest.skip("Slow CO2-rich continuation trace (set PVTSIM_RUN_SLOW=1 to enable).")
    components = load_components()
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)

    result = trace_envelope_continuation(
        temperatures=[280.0, 290.0, 300.0, 305.0, 310.0, 315.0],
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )

    assert result.critical_state is not None
    assert result.critical_state.source == "branch_closest_approach"
    assert 307.0 <= result.critical_state.temperature <= 308.0
    assert 70.0 <= result.critical_state.pressure / 1.0e5 <= 73.0
    assert result.switched is True
    assert len(result.dew_states) >= 1
    assert result.dew_states[0].temperature < result.critical_state.temperature < result.dew_states[-1].temperature


def test_critical_probe_temperatures_keep_seeded_shared_trivial_endpoint() -> None:
    """Seeded high-pressure probe traces should expose the shared trivial endpoint."""
    components = load_components()
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)

    bubble_trace = trace_branch_continuation_adaptive(
        branch="bubble",
        temperature_start=280.0,
        temperature_end=315.0,
        target_points=6,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )
    dew_probe_trace = trace_branch_continuation_adaptive(
        branch="dew",
        temperature_start=bubble_trace.states[-1].temperature,
        temperature_end=315.0,
        target_points=6,
        composition=z,
        components=mixture,
        eos=eos,
        pressure_seed=bubble_trace.states[-1].pressure,
        n_pressure_points=160,
    )

    bubble_probe_temperatures = _critical_probe_temperatures(bubble_trace)
    dew_probe_temperatures = _critical_probe_temperatures(dew_probe_trace)

    assert bubble_trace.states[-1].temperature in bubble_probe_temperatures
    assert dew_probe_trace.states[0].temperature in dew_probe_temperatures

    bubble_shared = _shared_trivial_endpoint_pressures(
        temperature=bubble_trace.states[-1].temperature,
        composition=z,
        eos=eos,
        binary_interaction=None,
        n_pressure_points=160,
    )
    dew_shared = _shared_trivial_endpoint_pressures(
        temperature=dew_probe_trace.states[0].temperature,
        composition=z,
        eos=eos,
        binary_interaction=None,
        n_pressure_points=160,
    )

    assert len(bubble_shared) == 1
    assert len(dew_shared) == 1
    assert bubble_shared[0] == dew_shared[0]
