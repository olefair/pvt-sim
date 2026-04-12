"""Workflow-level tests for pvtapp phase envelope execution."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError as PydanticValidationError

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import PhaseEnvelopeTracingMethod, RunConfig, RunStatus


def _phase_envelope_config(
    temperature_min_k: float = 150.0,
    temperature_max_k: float = 600.0,
    n_points: int = 20,
    tracing_method: str = "continuation",
    component_ids: tuple[str, str] = ("C1", "C10"),
) -> dict:
    return {
        "run_name": "Phase Envelope - Test",
        "composition": {
            "components": [
                {"component_id": component_ids[0], "mole_fraction": 0.50},
                {"component_id": component_ids[1], "mole_fraction": 0.50},
            ]
        },
        "calculation_type": "phase_envelope",
        "eos_type": "peng_robinson",
        "phase_envelope_config": {
            "temperature_min_k": temperature_min_k,
            "temperature_max_k": temperature_max_k,
            "n_points": n_points,
            "tracing_method": tracing_method,
        },
    }


def test_phase_envelope_workflow_happy_path() -> None:
    """A valid phase-envelope run should complete with meaningful curves."""
    config = RunConfig.model_validate(_phase_envelope_config())

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.phase_envelope_result is not None

    envelope = result.phase_envelope_result
    assert len(envelope.bubble_curve) > 0
    assert len(envelope.dew_curve) > 0
    assert envelope.tracing_method is PhaseEnvelopeTracingMethod.CONTINUATION

    t_min = config.phase_envelope_config.temperature_min_k
    t_max = config.phase_envelope_config.temperature_max_k

    assert all(t_min <= p.temperature_k <= t_max for p in envelope.bubble_curve)
    assert all(t_min <= p.temperature_k <= t_max for p in envelope.dew_curve)


def test_phase_envelope_invalid_composition_fails_schema_validation() -> None:
    """Mole fractions that do not sum to 1.0 must be rejected by schema."""
    config_data = _phase_envelope_config()
    bad_data = copy.deepcopy(config_data)
    bad_data["composition"]["components"][0]["mole_fraction"] = 0.70  # Total = 0.90

    with pytest.raises(PydanticValidationError, match="Mole fractions must sum to 1.0"):
        RunConfig.model_validate(bad_data)


def test_phase_envelope_no_saturation_range_fails_hard() -> None:
    """If no saturation exists in the requested range, run should fail hard."""
    config = RunConfig.model_validate(
        _phase_envelope_config(
            temperature_min_k=790.0,
            temperature_max_k=800.0,
            n_points=20,
        )
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.FAILED
    assert result.phase_envelope_result is None
    assert result.error_message is not None

    msg = result.error_message.lower()
    assert "phase envelope failed" in msg
    assert "suggestions:" in msg
    assert "widen the temperature range" in msg


def test_phase_envelope_workflow_continuation_route_completes() -> None:
    """The continuation route should run through the normal app workflow."""
    config = RunConfig.model_validate(
        _phase_envelope_config(
            temperature_min_k=325.0,
            temperature_max_k=340.0,
            n_points=10,
            tracing_method="continuation",
            component_ids=("C2", "C3"),
        )
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.phase_envelope_result is not None

    envelope = result.phase_envelope_result
    assert envelope.tracing_method is PhaseEnvelopeTracingMethod.CONTINUATION
    assert envelope.continuation_switched is True
    assert envelope.critical_source is not None
    assert len(envelope.bubble_curve) >= 2
    assert len(envelope.dew_curve) >= 3


def test_phase_envelope_workflow_fixed_grid_route_remains_available() -> None:
    """The legacy fixed-grid tracer should remain available when selected explicitly."""
    config = RunConfig.model_validate(
        _phase_envelope_config(
            temperature_min_k=325.0,
            temperature_max_k=340.0,
            n_points=10,
            tracing_method="fixed_grid",
            component_ids=("C2", "C3"),
        )
    )

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.phase_envelope_result is not None
    assert result.phase_envelope_result.tracing_method is PhaseEnvelopeTracingMethod.FIXED_GRID
