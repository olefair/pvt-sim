"""Phase-envelope continuation validation.

Consolidated from:
- test_phase_envelope_runtime_matrix.py (continuation vs fixed-grid, PETE 665)
- test_phase_envelope_release_gates.py (repeatability, branch tracking, no fake tails)
- test_phase_envelope_breadth_roster.py (breadth roster normalization)

Two test functions:
1. test_phase_envelope_runtime_and_release_gates — runtime agreement + release-gate topology
2. test_phase_envelope_breadth_roster — roster JSON integrity
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest

from pvtcore.envelope.continuation import (
    ContinuationState,
    EnvelopeContinuationResult,
    resolve_continuation_runtime_policy,
    trace_branch_continuation,
    trace_envelope_continuation,
)
from pvtcore.envelope.trace import trace_phase_envelope
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus
import math


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mixture(component_ids: tuple[str, ...]):
    components = load_components()
    mixture = [components[cid] for cid in component_ids]
    return mixture, PengRobinsonEOS(mixture)


def _state_temperatures(states: tuple[ContinuationState, ...]) -> np.ndarray:
    return np.array([s.temperature for s in states], dtype=float)


def _state_pressures(states: tuple[ContinuationState, ...]) -> np.ndarray:
    return np.array([s.pressure for s in states], dtype=float)


def _assert_temperatures_strictly_increasing(states: tuple[ContinuationState, ...]) -> None:
    t = _state_temperatures(states)
    if len(t) > 1:
        assert np.all(np.diff(t) > 0.0)


def _assert_max_log_pressure_jump(states: tuple[ContinuationState, ...], *, maximum: float) -> None:
    p = _state_pressures(states)
    if len(p) > 1:
        assert float(np.max(np.abs(np.diff(np.log(p))))) < float(maximum)


def _assert_critical_matches_a_traced_state(result: EnvelopeContinuationResult) -> None:
    assert result.critical_state is not None
    c = result.critical_state
    assert any(
        abs(s.temperature - c.temperature) <= 1e-12 and abs(s.pressure - c.pressure) <= 1e-9
        for s in (*result.bubble_states, *result.dew_states)
    )


def _assert_envelope_result_repeatable(first: EnvelopeContinuationResult, second: EnvelopeContinuationResult) -> None:
    assert first.switched is second.switched
    assert first.bubble_termination_reason == second.bubble_termination_reason
    assert first.dew_termination_reason == second.dew_termination_reason
    if first.critical_state is None or second.critical_state is None:
        assert first.critical_state is None and second.critical_state is None
    else:
        assert first.critical_state.source == second.critical_state.source
        np.testing.assert_allclose(
            [first.critical_state.temperature, first.critical_state.pressure, first.critical_state.score],
            [second.critical_state.temperature, second.critical_state.pressure, second.critical_state.score],
            rtol=0.0, atol=1e-9,
        )
    for attr in ("bubble_states", "dew_states"):
        np.testing.assert_allclose(
            _state_temperatures(getattr(first, attr)),
            _state_temperatures(getattr(second, attr)),
            rtol=0.0, atol=0.0,
        )
        np.testing.assert_allclose(
            _state_pressures(getattr(first, attr)),
            _state_pressures(getattr(second, attr)),
            rtol=0.0, atol=1e-9,
        )


# ---------------------------------------------------------------------------
# 1) Runtime agreement + release-gate topology
# ---------------------------------------------------------------------------

def test_phase_envelope_runtime_and_release_gates() -> None:
    """Continuation matches fixed grid; branch repeatability; critical handoff; no fake tails."""

    # --- Runtime matrix: continuation vs fixed-grid for C1/C10 ---
    mixture, eos = _make_mixture(("C1", "C10"))
    z = np.array([0.5, 0.5], dtype=float)
    temperatures = np.linspace(220.0, 480.0, 24, dtype=float)

    fixed_grid = trace_phase_envelope(
        composition=z, components=mixture, eos=eos,
        T_min=float(temperatures[0]), T_max=float(temperatures[-1]),
        n_points=len(temperatures),
    )
    continuation = trace_envelope_continuation(
        temperatures=temperatures.tolist(), composition=z,
        components=mixture, eos=eos, n_pressure_points=160,
    )

    ct = np.array([s.temperature for s in continuation.dew_states], dtype=float)
    cp = np.array([s.pressure for s in continuation.dew_states], dtype=float)
    interp_p = np.interp(fixed_grid.dew_T, ct, cp)
    rel_err = np.abs(interp_p - fixed_grid.dew_P) / fixed_grid.dew_P
    assert len(fixed_grid.dew_T) >= 10
    assert float(np.max(rel_err)) < 2.0e-3

    # --- Runtime matrix: PETE 665 density handoff ---
    payload = json.loads(Path("examples/pete665_assignment_case.json").read_text(encoding="utf-8"))
    pseudo = payload["fluid"]["inline_components"]["PSEUDO_PLUS"]
    config = RunConfig.model_validate({
        "run_name": "PETE665 phase envelope",
        "composition": {
            "components": [
                {
                    "component_id": ("PSEUDO_PLUS" if c["id"] == "PSEUDO_PLUS" else c["id"]),
                    "mole_fraction": c["z"],
                }
                for c in payload["fluid"]["components"]
            ],
            "inline_components": [{
                "component_id": "PSEUDO_PLUS",
                "name": "PSEUDO+", "formula": "PSEUDO+",
                "molecular_weight_g_per_mol": pseudo["mw_g_per_mol"],
                "critical_temperature_k": (pseudo["tc_value"] - 32.0) * 5.0 / 9.0 + 273.15,
                "critical_pressure_pa": pseudo["pc_value"] * 6894.757293168,
                "critical_temperature_unit": "F",
                "critical_pressure_unit": "psia",
                "omega": pseudo["omega"],
            }],
        },
        "calculation_type": "phase_envelope",
        "eos_type": "peng_robinson",
        "phase_envelope_config": {
            "temperature_min_k": 150.0, "temperature_max_k": 600.0,
            "n_points": 50, "tracing_method": "continuation",
        },
    })
    result = run_calculation(config=config, write_artifacts=False)
    assert result.status is RunStatus.COMPLETED
    env = result.phase_envelope_result
    assert env.continuation_switched is True
    assert env.critical_point is not None
    assert len(env.dew_curve) >= 35

    # --- Release gate: C1/C10 bubble branch repeatability ---
    mixture2, eos2 = _make_mixture(("C1", "C10"))
    z2 = np.array([0.5, 0.5], dtype=float)
    b1 = trace_branch_continuation(branch="bubble", temperatures=[320.0, 360.0, 400.0, 440.0, 480.0],
                                    composition=z2, components=mixture2, eos=eos2, n_pressure_points=120)
    b2 = trace_branch_continuation(branch="bubble", temperatures=[320.0, 360.0, 400.0, 440.0, 480.0],
                                    composition=z2, components=mixture2, eos=eos2, n_pressure_points=120)
    assert b1.termination_reason == b2.termination_reason
    assert len(b1.states) == 5
    np.testing.assert_allclose(_state_pressures(b1.states), _state_pressures(b2.states), rtol=0.0, atol=1e-9)
    _assert_temperatures_strictly_increasing(b1.states)

    # --- Release gate: C2/C3 clean switch + repeatability ---
    mixture3, eos3 = _make_mixture(("C2", "C3"))
    z3 = np.array([0.5, 0.5], dtype=float)
    e1 = trace_envelope_continuation(
        temperatures=[325.0, 330.0, 335.0, 340.0],
        composition=z3, components=mixture3, eos=eos3, n_pressure_points=160,
    )
    e2 = trace_envelope_continuation(
        temperatures=[325.0, 330.0, 335.0, 340.0],
        composition=z3, components=mixture3, eos=eos3, n_pressure_points=160,
    )
    _assert_envelope_result_repeatable(e1, e2)
    assert e1.critical_state is not None
    assert e1.switched is True
    _assert_critical_matches_a_traced_state(e1)
    _assert_temperatures_strictly_increasing(e1.bubble_states)
    _assert_temperatures_strictly_increasing(e1.dew_states)


# ---------------------------------------------------------------------------
# 2) Breadth roster normalization
# ---------------------------------------------------------------------------

_ROSTER_PATH = Path(__file__).resolve().parents[2] / "scripts" / "data" / "phase_envelope_breadth_roster.json"


def test_phase_envelope_breadth_roster() -> None:
    """Breadth roster JSON is normalized and complete."""
    raw = json.loads(_ROSTER_PATH.read_text(encoding="utf-8"))
    component_ids = {str(entry["component_id"]) for entry in raw["component_order"]}
    cases = list(raw["cases"])
    assert len(cases) == 17
    assert [int(c["tag"]) for c in cases] == list(range(1, 18))
    assert len({c["name"] for c in cases}) == len(cases)
    for case in cases:
        composition = {str(k): float(v) for k, v in dict(case["composition"]).items()}
        assert composition
        assert set(composition).issubset(component_ids)
        assert math.isclose(sum(composition.values()), 1.0, rel_tol=0.0, abs_tol=1e-12)
