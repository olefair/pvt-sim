"""Release-gate validation for the continuation phase-envelope tracer.

These checks do not claim experimental accuracy by themselves. They certify
the structural properties the continuation tracer must satisfy before it can
replace the legacy fixed-grid runtime path:

- deterministic repeated runs
- continuous local branch-family tracking
- no fake flat tails after the true boundary disappears
- explicit critical handoff instead of branch teleportation
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from pvtcore.envelope.continuation import (
    ContinuationState,
    EnvelopeContinuationResult,
    trace_branch_continuation,
    trace_envelope_continuation,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def _make_mixture(component_ids: tuple[str, ...]):
    components = load_components()
    mixture = [components[component_id] for component_id in component_ids]
    return mixture, PengRobinsonEOS(mixture)


def _state_temperatures(states: tuple[ContinuationState, ...]) -> np.ndarray:
    return np.array([state.temperature for state in states], dtype=float)


def _state_pressures(states: tuple[ContinuationState, ...]) -> np.ndarray:
    return np.array([state.pressure for state in states], dtype=float)


def _assert_temperatures_strictly_increasing(states: tuple[ContinuationState, ...]) -> None:
    temperatures = _state_temperatures(states)
    if len(temperatures) > 1:
        assert np.all(np.diff(temperatures) > 0.0)


def _assert_max_log_pressure_jump(
    states: tuple[ContinuationState, ...],
    *,
    maximum: float,
) -> None:
    pressures = _state_pressures(states)
    if len(pressures) > 1:
        jumps = np.abs(np.diff(np.log(pressures)))
        assert float(np.max(jumps)) < float(maximum)


def _assert_branch_trace_repeatable(first, second) -> None:
    assert first.branch == second.branch
    assert first.termination_reason == second.termination_reason
    assert first.termination_temperature == second.termination_temperature
    np.testing.assert_allclose(
        _state_temperatures(first.states),
        _state_temperatures(second.states),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        _state_pressures(first.states),
        _state_pressures(second.states),
        rtol=0.0,
        atol=1e-9,
    )


def _assert_envelope_result_repeatable(
    first: EnvelopeContinuationResult,
    second: EnvelopeContinuationResult,
) -> None:
    assert first.switched is second.switched
    assert first.bubble_termination_reason == second.bubble_termination_reason
    assert first.bubble_termination_temperature == second.bubble_termination_temperature
    assert first.dew_termination_reason == second.dew_termination_reason
    assert first.dew_termination_temperature == second.dew_termination_temperature

    if first.critical_state is None or second.critical_state is None:
        assert first.critical_state is None and second.critical_state is None
    else:
        assert first.critical_state.source == second.critical_state.source
        np.testing.assert_allclose(
            [first.critical_state.temperature, first.critical_state.pressure, first.critical_state.score],
            [second.critical_state.temperature, second.critical_state.pressure, second.critical_state.score],
            rtol=0.0,
            atol=1e-9,
        )

    np.testing.assert_allclose(
        _state_temperatures(first.bubble_states),
        _state_temperatures(second.bubble_states),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        _state_pressures(first.bubble_states),
        _state_pressures(second.bubble_states),
        rtol=0.0,
        atol=1e-9,
    )
    np.testing.assert_allclose(
        _state_temperatures(first.dew_states),
        _state_temperatures(second.dew_states),
        rtol=0.0,
        atol=0.0,
    )
    np.testing.assert_allclose(
        _state_pressures(first.dew_states),
        _state_pressures(second.dew_states),
        rtol=0.0,
        atol=1e-9,
    )


def test_release_gate_c1_c10_bubble_branch_is_repeatable_and_stays_on_one_family() -> None:
    """Asymmetric binary branch tracking must stay on one certified local family."""
    mixture, eos = _make_mixture(("C1", "C10"))
    z = np.array([0.5, 0.5], dtype=float)
    temperatures = [320.0, 360.0, 400.0, 440.0, 480.0]

    first = trace_branch_continuation(
        branch="bubble",
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=120,
    )
    second = trace_branch_continuation(
        branch="bubble",
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=120,
    )

    _assert_branch_trace_repeatable(first, second)
    assert first.termination_reason is None
    assert len(first.states) == len(temperatures)
    assert np.all(_state_pressures(first.states) / 1.0e5 > 130.0)
    _assert_temperatures_strictly_increasing(first.states)
    _assert_max_log_pressure_jump(first.states, maximum=0.20)


def test_release_gate_c2_c3_continuation_switches_cleanly_and_repeatably() -> None:
    """Similar-component envelope should switch once with a locally continuous handoff."""
    mixture, eos = _make_mixture(("C2", "C3"))
    z = np.array([0.5, 0.5], dtype=float)
    temperatures = [325.0, 330.0, 335.0, 340.0]

    first = trace_envelope_continuation(
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )
    second = trace_envelope_continuation(
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )

    _assert_envelope_result_repeatable(first, second)
    assert first.critical_state is not None
    assert first.critical_state.source == "branch_closest_approach"
    assert first.critical_state.score < 1.0
    assert first.switched is True
    assert first.bubble_termination_reason in {None, "no_local_root_candidates"}
    if first.bubble_termination_reason is not None:
        assert 330.0 <= first.bubble_termination_temperature <= 340.5
    assert first.dew_termination_reason is None
    assert len(first.bubble_states) >= 2
    assert len(first.dew_states) >= 3
    assert first.dew_states[0].temperature <= first.critical_state.temperature <= first.dew_states[-1].temperature
    critical_dew_neighbor = min(
        first.dew_states,
        key=lambda state: abs(state.temperature - first.critical_state.temperature),
    )
    assert abs(critical_dew_neighbor.temperature - first.critical_state.temperature) <= 0.6
    _assert_temperatures_strictly_increasing(first.bubble_states)
    _assert_temperatures_strictly_increasing(first.dew_states)
    _assert_max_log_pressure_jump(first.bubble_states, maximum=0.15)
    _assert_max_log_pressure_jump(first.dew_states, maximum=0.15)


def test_release_gate_co2_rich_case_stops_before_fake_flat_tail() -> None:
    """The CO2-rich default desktop fluid must stop before trivial flatlined tails appear."""
    if os.getenv("PVTSIM_RUN_SLOW") != "1":
        pytest.skip("Slow CO2-rich continuation trace (set PVTSIM_RUN_SLOW=1 to enable).")
    mixture, eos = _make_mixture(("CO2", "C1", "C2", "C3", "C4"))
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)
    temperatures = [280.0, 290.0, 300.0, 305.0, 310.0, 315.0]

    first = trace_envelope_continuation(
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )
    assert first.critical_state is not None
    assert first.critical_state.source == "branch_closest_approach"
    assert 307.0 <= first.critical_state.temperature <= 308.0
    assert 70.0 <= first.critical_state.pressure / 1.0e5 <= 73.0
    assert first.switched is True
    assert first.bubble_termination_reason == "no_local_root_candidates"
    assert 307.5 <= first.bubble_termination_temperature <= 308.5
    assert first.dew_termination_reason in {"branch_family_lost", "no_local_root_candidates"}
    assert first.dew_termination_temperature is not None
    assert len(first.bubble_states) >= 8
    assert len(first.dew_states) >= 1
    bubble_pressures = _state_pressures(first.bubble_states)
    dew_pressures = _state_pressures(first.dew_states)
    assert np.all(np.diff(bubble_pressures) > 0.0)
    _assert_temperatures_strictly_increasing(first.bubble_states)
    _assert_temperatures_strictly_increasing(first.dew_states)
    _assert_max_log_pressure_jump(first.dew_states, maximum=0.20)
    critical_dew_neighbor = min(
        first.dew_states,
        key=lambda state: abs(state.temperature - first.critical_state.temperature),
    )
    assert abs(critical_dew_neighbor.temperature - first.critical_state.temperature) <= 0.5
    assert critical_dew_neighbor.pressure < first.critical_state.pressure < bubble_pressures[-1]
    assert abs(np.log(first.critical_state.pressure / critical_dew_neighbor.pressure)) <= 0.03
