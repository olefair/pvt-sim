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
    resolve_continuation_runtime_policy,
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


def _assert_critical_matches_a_traced_state(result: EnvelopeContinuationResult) -> None:
    assert result.critical_state is not None
    critical = result.critical_state
    assert any(
        abs(state.temperature - critical.temperature) <= 1.0e-12
        and abs(state.pressure - critical.pressure) <= 1.0e-9
        for state in (*result.bubble_states, *result.dew_states)
    )


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
    _assert_critical_matches_a_traced_state(first)
    assert first.dew_states[0].temperature <= first.critical_state.temperature <= first.dew_states[-1].temperature
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
    assert 310.0 <= first.critical_state.temperature <= 312.0
    assert 73.0 <= first.critical_state.pressure / 1.0e5 <= 75.0
    assert first.switched is True
    assert first.bubble_termination_reason == "no_local_root_candidates"
    assert 307.0 <= first.bubble_termination_temperature <= 308.5
    assert first.dew_termination_reason in {"branch_family_lost", "no_local_root_candidates"}
    assert first.dew_termination_temperature is not None
    assert len(first.bubble_states) >= 8
    assert len(first.dew_states) >= 1
    _assert_critical_matches_a_traced_state(first)
    bubble_pressures = _state_pressures(first.bubble_states)
    dew_pressures = _state_pressures(first.dew_states)
    assert np.all(np.diff(bubble_pressures) > 0.0)
    _assert_temperatures_strictly_increasing(first.bubble_states)
    _assert_temperatures_strictly_increasing(first.dew_states)
    _assert_max_log_pressure_jump(first.dew_states[:-1], maximum=0.08)
    assert dew_pressures[0] <= first.critical_state.pressure
    assert first.critical_state.pressure >= bubble_pressures[-1]
    assert abs(first.dew_states[-1].temperature - first.critical_state.temperature) <= 1.0e-12
    assert abs(np.log(first.dew_states[-1].pressure / first.critical_state.pressure)) <= 1.0e-9


def test_release_gate_heavy_gas_condensate_switches_without_hot_side_tail() -> None:
    """The explicit heavy gas-condensate lane must switch and stop at the critical point."""
    if os.getenv("PVTSIM_RUN_SLOW") != "1":
        pytest.skip("Slow heavy gas-condensate continuation trace (set PVTSIM_RUN_SLOW=1 to enable).")

    # Runtime-family inference is already covered in unit tests. This release
    # gate should certify the heavy-policy topology without paying for a dense
    # runtime-grid sweep on every signoff run.
    mixture, eos = _make_mixture(
        ("N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "C4", "iC5", "C5", "C6", "C7", "C8", "C10", "C12")
    )
    z = np.array(
        [0.004, 0.018, 0.008, 0.580, 0.120, 0.085, 0.030, 0.028, 0.020, 0.019, 0.018, 0.018, 0.017, 0.020, 0.015],
        dtype=float,
    )
    temperatures = [220.0, 250.0, 280.0, 310.0, 330.0, 345.0, 352.0, 358.0, 364.0, 370.0]
    policy = resolve_continuation_runtime_policy("gas_condensate_heavy")

    envelope = trace_envelope_continuation(
        temperatures=temperatures,
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=policy.n_pressure_points,
        runtime_policy=policy,
    )

    assert envelope.converged is True
    assert envelope.critical_state is not None
    assert envelope.switched is True
    assert 360.0 <= envelope.critical_state.temperature <= 372.0
    assert 175.0 <= envelope.critical_state.pressure / 1.0e5 <= 195.0
    assert len(envelope.bubble_states) >= 8
    assert len(envelope.dew_states) >= 6
    _assert_critical_matches_a_traced_state(envelope)
    _assert_temperatures_strictly_increasing(envelope.bubble_states)
    _assert_temperatures_strictly_increasing(envelope.dew_states)
    _assert_max_log_pressure_jump(envelope.bubble_states, maximum=0.22)
    _assert_max_log_pressure_jump(envelope.dew_states, maximum=0.22)
    dew_temperatures = _state_temperatures(envelope.dew_states)
    assert float(np.max(dew_temperatures)) <= envelope.critical_state.temperature + 1.0e-12
    assert abs(envelope.dew_states[-1].temperature - envelope.critical_state.temperature) <= 1.0e-12
    assert abs(np.log(envelope.dew_states[-1].pressure / envelope.critical_state.pressure)) <= 1.0e-9
