"""Runtime-agreement checks for the continuation phase-envelope kernel."""

from __future__ import annotations

import numpy as np

from pvtcore.envelope.continuation import trace_envelope_continuation
from pvtcore.envelope.trace import trace_phase_envelope
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def _make_mixture(component_ids: tuple[str, ...]):
    components = load_components()
    mixture = [components[component_id] for component_id in component_ids]
    return mixture, PengRobinsonEOS(mixture)


def test_runtime_matrix_c1_c10_continuation_matches_fixed_grid_dew_pressures() -> None:
    """Continuation should preserve the asymmetric C1/C10 dew branch seen by the runtime grid."""
    mixture, eos = _make_mixture(("C1", "C10"))
    z = np.array([0.5, 0.5], dtype=float)
    temperatures = np.linspace(220.0, 480.0, 24, dtype=float)

    fixed_grid = trace_phase_envelope(
        composition=z,
        components=mixture,
        eos=eos,
        T_min=float(temperatures[0]),
        T_max=float(temperatures[-1]),
        n_points=len(temperatures),
    )
    continuation = trace_envelope_continuation(
        temperatures=temperatures.tolist(),
        composition=z,
        components=mixture,
        eos=eos,
        n_pressure_points=160,
    )

    continuation_t = np.array([state.temperature for state in continuation.dew_states], dtype=float)
    continuation_p = np.array([state.pressure for state in continuation.dew_states], dtype=float)
    interpolated_pressures = np.interp(fixed_grid.dew_T, continuation_t, continuation_p)
    relative_error = np.abs(interpolated_pressures - fixed_grid.dew_P) / fixed_grid.dew_P

    assert len(fixed_grid.dew_T) >= 10
    assert len(continuation.dew_states) >= len(fixed_grid.dew_T)
    assert continuation.dew_states[0].temperature <= fixed_grid.dew_T[0]
    assert continuation.dew_states[-1].temperature == fixed_grid.dew_T[-1]
    assert float(np.max(relative_error)) < 2.0e-3
