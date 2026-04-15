"""Single-contact swelling-test simulation.

This module implements the first admitted swelling-test protocol for the repo:

- fixed temperature;
- one normalized oil feed basis;
- one normalized injection-gas feed basis;
- a strictly increasing enrichment schedule expressed as gas moles added per
  initial mole of oil;
- bubble-pressure recomputation plus saturated-liquid properties at each step.

Units Convention:
- Pressure: Pa
- Temperature: K
- Density: kg/m³
- Molar volume: m³/mol

The enriched-feed composition at each enrichment ratio ``r`` is:

    z(r) = (z_oil + r * y_gas) / (1 + r)

The first-slice swelling factor is reported on an initial-oil basis:

    SF(r) = ((1 + r) * v_sat(r)) / v_sat(0)

where ``v_sat(r)`` is the saturated-liquid molar volume at the certified
bubble-pressure boundary for the enriched state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, PropertyError, ValidationError
from ..eos.base import CubicEOS
from ..flash.bubble_point import calculate_bubble_point
from ..models.component import Component
from ..properties.density import calculate_density

_COMPOSITION_TOLERANCE = 1.0e-6

SWELLING_STATUS_CERTIFIED = "certified"
SWELLING_STATUS_FAILED_SOLVER = "failed_solver"
SWELLING_STATUS_FAILED_NO_BOUNDARY = "failed_no_boundary"
SWELLING_STATUS_FAILED_AMBIGUOUS_BOUNDARY = "failed_ambiguous_boundary"

SWELLING_RESULT_COMPLETE = "complete"
SWELLING_RESULT_PARTIAL = "partial"
SWELLING_RESULT_FAILED = "failed"


@dataclass
class SwellingStepResult:
    """Per-step swelling-test output."""

    step_index: int
    added_gas_moles_per_mole_oil: float
    total_mixture_moles_per_mole_oil: float
    bubble_pressure: Optional[float]
    swelling_factor: Optional[float]
    saturated_liquid_molar_volume: Optional[float]
    saturated_liquid_density: Optional[float]
    enriched_feed_composition: NDArray[np.float64]
    incipient_vapor_composition: NDArray[np.float64]
    k_values: NDArray[np.float64]
    status: str
    message: Optional[str] = None


@dataclass
class SwellingResult:
    """Complete swelling-test output."""

    temperature: float
    baseline_bubble_pressure: Optional[float]
    baseline_saturated_liquid_molar_volume: Optional[float]
    enrichment_steps: NDArray[np.float64]
    steps: List[SwellingStepResult]
    bubble_pressures: NDArray[np.float64]
    swelling_factors: NDArray[np.float64]
    fully_certified: bool
    overall_status: str


def _normalize_validated_composition(
    composition: NDArray[np.float64] | Sequence[float],
    *,
    label: str,
    expected_length: int,
) -> NDArray[np.float64]:
    """Validate and normalize a 1D composition vector."""
    vector = np.asarray(composition, dtype=np.float64)
    if vector.ndim != 1:
        raise ValidationError(
            f"{label} must be a 1D array",
            parameter=label,
            value=f"shape={vector.shape}",
        )
    if vector.size != expected_length:
        raise ValidationError(
            f"{label} length must match number of components",
            parameter=label,
            value={"got": int(vector.size), "expected": int(expected_length)},
        )
    if not np.all(np.isfinite(vector)):
        raise ValidationError(
            f"{label} must contain only finite values",
            parameter=label,
        )
    if np.any(vector < -1.0e-16):
        raise ValidationError(
            f"{label} must be non-negative",
            parameter=label,
            value={"min": float(np.min(vector))},
        )
    total = float(np.sum(vector))
    if not np.isclose(total, 1.0, atol=_COMPOSITION_TOLERANCE):
        raise ValidationError(
            f"{label} must sum to 1.0, got {total:.8f}",
            parameter=label,
            value=total,
        )
    return vector / total


def _validate_enrichment_schedule(
    enrichment_steps: NDArray[np.float64] | Sequence[float],
) -> NDArray[np.float64]:
    """Validate the user-authored enrichment schedule and insert the baseline."""
    schedule = np.asarray(list(enrichment_steps), dtype=np.float64)
    if schedule.ndim != 1:
        raise ValidationError(
            "enrichment_steps must be a 1D array",
            parameter="enrichment_steps",
            value=f"shape={schedule.shape}",
        )
    if schedule.size == 0:
        raise ValidationError(
            "enrichment_steps must contain at least one enrichment ratio",
            parameter="enrichment_steps",
        )
    if not np.all(np.isfinite(schedule)):
        raise ValidationError(
            "enrichment_steps must contain only finite values",
            parameter="enrichment_steps",
        )
    if np.any(schedule < 0.0):
        raise ValidationError(
            "enrichment_steps must be non-negative",
            parameter="enrichment_steps",
            value={"min": float(np.min(schedule))},
        )
    if np.any(np.diff(schedule) <= 0.0):
        raise ValidationError(
            "enrichment_steps must be strictly increasing and duplicate-free",
            parameter="enrichment_steps",
        )
    if schedule[0] == 0.0:
        return schedule
    return np.concatenate([np.array([0.0], dtype=np.float64), schedule], dtype=np.float64)


def _failure_arrays(size: int) -> NDArray[np.float64]:
    """Return a consistent failed-step vector payload."""
    return np.full(size, np.nan, dtype=np.float64)


def _classify_step_failure(exc: Exception) -> tuple[str, str]:
    """Map kernel exceptions onto the bounded swelling-step status surface."""
    message = str(exc)
    if isinstance(exc, PhaseError):
        reason = getattr(exc, "details", {}).get("reason")
        if reason == "no_saturation":
            return SWELLING_STATUS_FAILED_NO_BOUNDARY, message
        if reason in {"degenerate_trivial_boundary", "post_check_failed", "inside_envelope"}:
            return SWELLING_STATUS_FAILED_AMBIGUOUS_BOUNDARY, message
        return SWELLING_STATUS_FAILED_NO_BOUNDARY, message
    if isinstance(exc, (ConvergenceError, PropertyError)):
        return SWELLING_STATUS_FAILED_SOLVER, message
    return SWELLING_STATUS_FAILED_SOLVER, message


def _build_enriched_feed(
    oil_composition: NDArray[np.float64],
    injection_gas_composition: NDArray[np.float64],
    added_gas_moles_per_mole_oil: float,
) -> NDArray[np.float64]:
    """Return the enriched feed on the total-mixture basis."""
    ratio = float(added_gas_moles_per_mole_oil)
    total_moles = 1.0 + ratio
    return (oil_composition + ratio * injection_gas_composition) / total_moles


def simulate_swelling(
    oil_composition: NDArray[np.float64] | Sequence[float],
    injection_gas_composition: NDArray[np.float64] | Sequence[float],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    enrichment_steps: NDArray[np.float64] | Sequence[float],
    binary_interaction: Optional[NDArray[np.float64]] = None,
) -> SwellingResult:
    """Simulate a fixed-temperature single-contact swelling test."""
    if not components:
        raise ValidationError(
            "components cannot be empty",
            parameter="components",
            value="empty list",
        )
    if not np.isfinite(temperature) or float(temperature) <= 0.0:
        raise ValidationError(
            "temperature must be a finite positive number",
            parameter="temperature",
            value=temperature,
        )

    n_components = len(components)
    z_oil = _normalize_validated_composition(
        oil_composition,
        label="oil_composition",
        expected_length=n_components,
    )
    y_gas = _normalize_validated_composition(
        injection_gas_composition,
        label="injection_gas_composition",
        expected_length=n_components,
    )
    effective_schedule = _validate_enrichment_schedule(enrichment_steps)

    if binary_interaction is not None:
        binary_interaction = np.asarray(binary_interaction, dtype=np.float64)
        if binary_interaction.shape != (n_components, n_components):
            raise ValidationError(
                "binary_interaction shape must match the component basis",
                parameter="binary_interaction",
                value=f"shape={binary_interaction.shape}",
            )
        if not np.all(np.isfinite(binary_interaction)):
            raise ValidationError(
                "binary_interaction must contain only finite values",
                parameter="binary_interaction",
            )

    bubble_pressures = np.full(effective_schedule.shape, np.nan, dtype=np.float64)
    swelling_factors = np.full(effective_schedule.shape, np.nan, dtype=np.float64)
    steps: list[SwellingStepResult] = []
    baseline_volume: Optional[float] = None
    baseline_pressure: Optional[float] = None

    for index, ratio in enumerate(effective_schedule):
        enriched_feed = _build_enriched_feed(z_oil, y_gas, float(ratio))
        total_moles = 1.0 + float(ratio)
        empty_arrays = _failure_arrays(n_components)

        try:
            bubble_result = calculate_bubble_point(
                temperature=float(temperature),
                composition=enriched_feed,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
            )
            if not bubble_result.converged:
                message = (
                    "Bubble-point solver did not converge for this enrichment step "
                    f"(status={bubble_result.status.name.lower()})."
                )
                steps.append(
                    SwellingStepResult(
                        step_index=index,
                        added_gas_moles_per_mole_oil=float(ratio),
                        total_mixture_moles_per_mole_oil=total_moles,
                        bubble_pressure=None,
                        swelling_factor=None,
                        saturated_liquid_molar_volume=None,
                        saturated_liquid_density=None,
                        enriched_feed_composition=enriched_feed.copy(),
                        incipient_vapor_composition=empty_arrays.copy(),
                        k_values=empty_arrays.copy(),
                        status=SWELLING_STATUS_FAILED_SOLVER,
                        message=message,
                    )
                )
                continue

            density_result = calculate_density(
                pressure=float(bubble_result.pressure),
                temperature=float(temperature),
                composition=bubble_result.liquid_composition,
                components=components,
                eos=eos,
                phase="liquid",
                binary_interaction=binary_interaction,
            )

            saturated_liquid_molar_volume = float(density_result.molar_volume)
            saturated_liquid_density = float(density_result.mass_density)
            bubble_pressure = float(bubble_result.pressure)

            if baseline_volume is None:
                baseline_volume = saturated_liquid_molar_volume
                baseline_pressure = bubble_pressure

            if baseline_volume is None or baseline_volume <= 0.0:
                message = (
                    "Baseline saturated-liquid molar volume is unavailable, so the swelling "
                    "factor cannot be certified for this step."
                )
                steps.append(
                    SwellingStepResult(
                        step_index=index,
                        added_gas_moles_per_mole_oil=float(ratio),
                        total_mixture_moles_per_mole_oil=total_moles,
                        bubble_pressure=bubble_pressure,
                        swelling_factor=None,
                        saturated_liquid_molar_volume=saturated_liquid_molar_volume,
                        saturated_liquid_density=saturated_liquid_density,
                        enriched_feed_composition=enriched_feed.copy(),
                        incipient_vapor_composition=np.asarray(
                            bubble_result.vapor_composition, dtype=np.float64
                        ).copy(),
                        k_values=np.asarray(bubble_result.K_values, dtype=np.float64).copy(),
                        status=SWELLING_STATUS_FAILED_SOLVER,
                        message=message,
                    )
                )
                continue

            swelling_factor = float((total_moles * saturated_liquid_molar_volume) / baseline_volume)
            bubble_pressures[index] = bubble_pressure
            swelling_factors[index] = swelling_factor
            steps.append(
                SwellingStepResult(
                    step_index=index,
                    added_gas_moles_per_mole_oil=float(ratio),
                    total_mixture_moles_per_mole_oil=total_moles,
                    bubble_pressure=bubble_pressure,
                    swelling_factor=swelling_factor,
                    saturated_liquid_molar_volume=saturated_liquid_molar_volume,
                    saturated_liquid_density=saturated_liquid_density,
                    enriched_feed_composition=enriched_feed.copy(),
                    incipient_vapor_composition=np.asarray(
                        bubble_result.vapor_composition, dtype=np.float64
                    ).copy(),
                    k_values=np.asarray(bubble_result.K_values, dtype=np.float64).copy(),
                    status=SWELLING_STATUS_CERTIFIED,
                    message=None,
                )
            )
        except Exception as exc:
            status, message = _classify_step_failure(exc)
            steps.append(
                SwellingStepResult(
                    step_index=index,
                    added_gas_moles_per_mole_oil=float(ratio),
                    total_mixture_moles_per_mole_oil=total_moles,
                    bubble_pressure=None,
                    swelling_factor=None,
                    saturated_liquid_molar_volume=None,
                    saturated_liquid_density=None,
                    enriched_feed_composition=enriched_feed.copy(),
                    incipient_vapor_composition=empty_arrays.copy(),
                    k_values=empty_arrays.copy(),
                    status=status,
                    message=message,
                )
            )

    fully_certified = all(step.status == SWELLING_STATUS_CERTIFIED for step in steps)
    certified_steps = sum(step.status == SWELLING_STATUS_CERTIFIED for step in steps)
    if certified_steps == len(steps):
        overall_status = SWELLING_RESULT_COMPLETE
    elif certified_steps == 0:
        overall_status = SWELLING_RESULT_FAILED
    else:
        overall_status = SWELLING_RESULT_PARTIAL

    return SwellingResult(
        temperature=float(temperature),
        baseline_bubble_pressure=baseline_pressure,
        baseline_saturated_liquid_molar_volume=baseline_volume,
        enrichment_steps=effective_schedule,
        steps=steps,
        bubble_pressures=bubble_pressures,
        swelling_factors=swelling_factors,
        fully_certified=fully_certified,
        overall_status=overall_status,
    )
