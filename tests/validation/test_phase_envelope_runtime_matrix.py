"""Runtime-agreement checks for the continuation phase-envelope kernel."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from pvtcore.envelope.continuation import trace_envelope_continuation
from pvtcore.envelope.trace import trace_phase_envelope
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.models.component import load_components
from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus


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


def test_runtime_matrix_pete665_assignment_density_handoff_preserves_dew_branch() -> None:
    """PETE 665 inline-pseudo runtime path should keep the dew branch after the critical handoff."""
    payload = json.loads(
        Path("examples/pete665_assignment_case.json").read_text(encoding="utf-8")
    )
    pseudo = payload["fluid"]["inline_components"]["PSEUDO_PLUS"]
    config = RunConfig.model_validate(
        {
            "run_name": "PETE665 phase envelope",
            "composition": {
                "components": [
                    {
                        "component_id": (
                            "PSEUDO_PLUS" if component["id"] == "PSEUDO_PLUS" else component["id"]
                        ),
                        "mole_fraction": component["z"],
                    }
                    for component in payload["fluid"]["components"]
                ],
                "inline_components": [
                    {
                        "component_id": "PSEUDO_PLUS",
                        "name": "PSEUDO+",
                        "formula": "PSEUDO+",
                        "molecular_weight_g_per_mol": pseudo["mw_g_per_mol"],
                        "critical_temperature_k": (pseudo["tc_value"] - 32.0) * 5.0 / 9.0 + 273.15,
                        "critical_pressure_pa": pseudo["pc_value"] * 6894.757293168,
                        "critical_temperature_unit": "F",
                        "critical_pressure_unit": "psia",
                        "omega": pseudo["omega"],
                    }
                ],
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 150.0,
                "temperature_max_k": 600.0,
                "n_points": 50,
                "tracing_method": "continuation",
            },
        }
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status is RunStatus.COMPLETED
    assert result.phase_envelope_result is not None

    envelope = result.phase_envelope_result
    assert envelope.continuation_switched is True
    assert envelope.critical_point is not None
    assert len(envelope.dew_curve) >= 35
    assert min(point.temperature_k for point in envelope.dew_curve) < 220.0
    assert max(point.pressure_pa for point in envelope.dew_curve) >= 0.9 * envelope.critical_point.pressure_pa
    assert any(
        abs(point.temperature_k - envelope.critical_point.temperature_k) <= 1.0e-12
        and abs(point.pressure_pa - envelope.critical_point.pressure_pa) <= 1.0e-9
        for point in envelope.dew_curve
    )
    assert abs(envelope.dew_curve[-1].temperature_k - envelope.critical_point.temperature_k) <= 1.0e-12
    assert abs(envelope.dew_curve[-1].pressure_pa - envelope.critical_point.pressure_pa) <= 1.0e-9
