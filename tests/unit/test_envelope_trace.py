"""Focused regressions for the app-facing fixed-grid envelope tracer."""

from __future__ import annotations

import numpy as np

from pvtcore.envelope.phase_envelope import calculate_phase_envelope
from pvtcore.envelope.trace import trace_phase_envelope
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components


def test_trace_phase_envelope_co2_rich_gas_avoids_flatline_tail() -> None:
    """CO2-rich desktop fluid should stop before trivial flatlined saturation points."""
    components = load_components()
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)

    T_min = 150.0
    T_max = 600.0
    n_points = 50

    result = trace_phase_envelope(
        composition=z,
        components=mixture,
        eos=eos,
        T_min=T_min,
        T_max=T_max,
        n_points=n_points,
    )

    assert len(result.bubble_T) > 0
    assert len(result.dew_T) > 0

    # The previous regression accepted degenerate trivial boundaries and then
    # repeated a constant pressure all the way to the requested T_max.
    assert np.all(np.diff(result.bubble_P) > 0.0)
    assert np.all(np.diff(result.dew_P) > 0.0)
    assert float(result.bubble_T[-1]) > (273.15 + 30.0)
    assert float(result.dew_T[-1]) < T_max
    assert result.cricondentherm is not None
    assert float(result.cricondentherm[0]) < T_max
    assert result.critical_point is not None
    assert float(result.critical_point[0]) > (273.15 + 30.0)


def test_continuation_phase_envelope_handles_co2_rich_branch_termination() -> None:
    """Continuation envelope path should terminate cleanly on trivial branch endings."""
    components = load_components()
    z = np.array([0.6498, 0.1057, 0.1058, 0.1235, 0.0152], dtype=float)
    mixture = [
        components["CO2"],
        components["C1"],
        components["C2"],
        components["C3"],
        components["C4"],
    ]
    eos = PengRobinsonEOS(mixture)

    result = calculate_phase_envelope(
        composition=z,
        components=mixture,
        eos=eos,
    )

    assert result.converged
    assert result.n_bubble_points > 0
    assert result.n_dew_points > 0
    assert np.all(np.diff(result.bubble_P) > 0.0)
    assert np.all(np.diff(result.dew_P) > 0.0)
