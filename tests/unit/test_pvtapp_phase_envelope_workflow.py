"""Workflow-level tests for pvtapp phase envelope execution."""

from __future__ import annotations

import copy

import pytest
from pydantic import ValidationError as PydanticValidationError

from pvtapp.job_runner import _infer_phase_envelope_runtime_family, run_calculation
from pvtapp.schemas import PhaseEnvelopeTracingMethod, RunConfig, RunStatus


def _phase_envelope_config(
    temperature_min_k: float = 150.0,
    temperature_max_k: float = 600.0,
    n_points: int = 20,
    *,
    tracing_method: str | None = None,
    component_ids: tuple[str, ...] = ("C1", "C10"),
) -> dict:
    components = [
        {"component_id": component_id, "mole_fraction": 1.0 / len(component_ids)}
        for component_id in component_ids
    ]
    phase_envelope_config = {
        "temperature_min_k": temperature_min_k,
        "temperature_max_k": temperature_max_k,
        "n_points": n_points,
    }
    if tracing_method is not None:
        phase_envelope_config["tracing_method"] = tracing_method
    return {
        "run_name": "Phase Envelope - Test",
        "composition": {"components": components},
        "calculation_type": "phase_envelope",
        "eos_type": "peng_robinson",
        "phase_envelope_config": phase_envelope_config,
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


@pytest.mark.parametrize(
    ("config_data", "expected_family"),
    [
        (
            {
                "run_name": "Dry gas baseline",
                "composition": {
                    "components": [
                        {"component_id": "N2", "mole_fraction": 0.01},
                        {"component_id": "CO2", "mole_fraction": 0.02},
                        {"component_id": "C1", "mole_fraction": 0.82},
                        {"component_id": "C2", "mole_fraction": 0.08},
                        {"component_id": "C3", "mole_fraction": 0.04},
                        {"component_id": "C4", "mole_fraction": 0.03},
                    ],
                },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 200.0,
                    "temperature_max_k": 360.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "dry_gas",
        ),
        (
            {
                "run_name": "Light condensate baseline",
                "composition": {
                        "components": [
                            {"component_id": "CO2", "mole_fraction": 0.02},
                            {"component_id": "C1", "mole_fraction": 0.71},
                            {"component_id": "C2", "mole_fraction": 0.09},
                            {"component_id": "C3", "mole_fraction": 0.06},
                            {"component_id": "C4", "mole_fraction": 0.03},
                            {"component_id": "C5", "mole_fraction": 0.03},
                            {"component_id": "C6", "mole_fraction": 0.02},
                            {"component_id": "C7", "mole_fraction": 0.04},
                        ],
                    },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 240.0,
                    "temperature_max_k": 420.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "gas_condensate_light",
        ),
        (
            {
                "run_name": "Heavy condensate baseline",
                "composition": {
                    "components": [
                        {"component_id": "CO2", "mole_fraction": 0.02},
                        {"component_id": "C1", "mole_fraction": 0.62},
                        {"component_id": "C2", "mole_fraction": 0.10},
                        {"component_id": "C3", "mole_fraction": 0.08},
                        {"component_id": "C4", "mole_fraction": 0.05},
                        {"component_id": "C5", "mole_fraction": 0.04},
                    ],
                    "plus_fraction": {
                        "label": "C7+",
                        "z_plus": 0.09,
                        "mw_plus_g_per_mol": 165.0,
                        "sg_plus_60f": 0.78,
                        "characterization_preset": "auto",
                    },
                },
                "calculation_type": "phase_envelope",
                "eos_type": "peng_robinson",
                "phase_envelope_config": {
                    "temperature_min_k": 240.0,
                    "temperature_max_k": 440.0,
                    "n_points": 12,
                    "tracing_method": "continuation",
                },
            },
            "gas_condensate_heavy",
        ),
    ],
)
def test_phase_envelope_runtime_family_selects_closest_baseline(
    config_data: dict,
    expected_family: str,
) -> None:
    """Continuation runtime should choose a narrow baseline family before tracing."""
    config = RunConfig.model_validate(config_data)
    assert _infer_phase_envelope_runtime_family(config) == expected_family
