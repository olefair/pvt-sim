"""Local-root continuation helpers for phase envelopes.

This module now provides the continuation kernel used by the app/runtime path,
while still exposing lower-level branch-local helpers for validation and
development. It exposes two layers:

1. A branch-local continuation kernel that follows certified bubble/dew roots
   from one temperature to the next.
2. A continuation envelope wrapper that promotes near-trivial ``K -> 1``
   collapses into an explicit critical-junction candidate instead of treating
   them as a hard dead-end.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Sequence

import numpy as np
from numpy.typing import NDArray

from ..core.errors import PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.bubble_point import (
    BUBBLE_POINT_TOLERANCE,
    _is_degenerate_trivial_trial as _is_bubble_trivial,
    _tpd_vapor_trial,
    _tpd_vapor_trial_scalar,
    calculate_bubble_point,
)
from ..flash.dew_point import (
    DEW_POINT_TOLERANCE,
    _is_degenerate_trivial_trial as _is_dew_trivial,
    _tpd_liquid_trial,
    _tpd_liquid_trial_scalar,
    calculate_dew_point,
)
from ..flash.rachford_rice import brent_method
from ..models.component import Component
from .local_roots import (
    BranchName,
    PRESSURE_MAX,
    PRESSURE_MIN,
    RootBracket,
    normalize_trial,
    scan_branch_roots,
    tpd_class,
)


REFINEMENT_PRESSURE_POINTS: int = 65
DEFAULT_CONTINUATION_PRESSURE_POINTS: int = 160
DEFAULT_PRESSURE_WINDOW_LOG_SPAN: float = 0.9
CRITICAL_PAIR_MAX_TEMP_GAP: float = 15.0  # K
CRITICAL_PAIR_MAX_LOG_PRESSURE_GAP: float = 0.20
CRITICAL_CANDIDATE_MAX_SCORE: float = 2.0
CRITICAL_TRIVIAL_MAX_NEIGHBOR_TEMP_GAP: float = 2.0
CRITICAL_TRIVIAL_ENDPOINT_PENALTY: float = 0.25
SWITCH_MAX_LOG_PRESSURE_GAP: float = 0.15
SWITCH_MAX_PHASE_GAP: float = 0.20
DEFAULT_MAX_LOG_PRESSURE_JUMP: float = 0.20
DEFAULT_MAX_PHASE_COMPOSITION_JUMP: float = 0.15
DEFAULT_MAX_K_VALUE_JUMP: float = 2.5
DEFAULT_MIN_TEMPERATURE_STEP_K: float = 0.25
DEFAULT_MAX_TEMPERATURE_STEP_K: float = 2.0
DEFAULT_STEP_GROWTH: float = 1.35
CRITICAL_PROBE_MIN_SPAN_K: float = 18.0
CRITICAL_PROBE_STEP_MULTIPLIER: float = 3.5
DENSITY_HANDOFF_SEARCH_POINTS_MIN: int = 8
DENSITY_HANDOFF_SEARCH_POINTS_MAX: int = 12
DENSITY_MARCH_MIDPOINT_JUMP_MAX: float = 0.12
NEAR_TRIVIAL_PHASE_GAP: float = 1.0e-4
NEAR_TRIVIAL_K_DEVIATION: float = 1.0e-4
CRITICAL_COLLAPSE_PHASE_GAP: float = 0.035
CRITICAL_COLLAPSE_K_DEVIATION: float = 0.40
CRITICAL_REFINEMENT_PRESSURE_POINTS: int = 480
ARCLENGTH_PHASE_GAP_THRESHOLD: float = 0.20
ARCLENGTH_K_DEVIATION_THRESHOLD: float = 0.40


@dataclass(frozen=True)
class ContinuationRuntimePolicy:
    """Runtime tuning profile for continuation tracing."""

    name: str
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS
    seed_window_log_span: float = DEFAULT_PRESSURE_WINDOW_LOG_SPAN
    hint_window_log_span: float = DEFAULT_PRESSURE_WINDOW_LOG_SPAN
    pressure_window_log_span: float = DEFAULT_PRESSURE_WINDOW_LOG_SPAN
    bracket_window_log_span: float = 0.4
    allow_full_rescan_on_advance: bool = True
    use_predictive_pressure_hint: bool = True
    min_temperature_step_k: float = DEFAULT_MIN_TEMPERATURE_STEP_K
    max_temperature_step_k: float = DEFAULT_MAX_TEMPERATURE_STEP_K
    step_growth: float = DEFAULT_STEP_GROWTH


DEFAULT_CONTINUATION_RUNTIME_POLICY = ContinuationRuntimePolicy(name="generic")

_CONTINUATION_RUNTIME_POLICIES = {
    "generic": DEFAULT_CONTINUATION_RUNTIME_POLICY,
    "dry_gas": ContinuationRuntimePolicy(
        name="dry_gas",
        n_pressure_points=80,
        seed_window_log_span=0.45,
        hint_window_log_span=0.40,
        pressure_window_log_span=0.45,
        bracket_window_log_span=0.25,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.50,
        max_temperature_step_k=14.0,
        step_growth=1.55,
    ),
    "gas_condensate_light": ContinuationRuntimePolicy(
        name="gas_condensate_light",
        n_pressure_points=88,
        seed_window_log_span=0.50,
        hint_window_log_span=0.45,
        pressure_window_log_span=0.50,
        bracket_window_log_span=0.28,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.40,
        max_temperature_step_k=12.0,
        step_growth=1.45,
    ),
    "gas_condensate_heavy": ContinuationRuntimePolicy(
        name="gas_condensate_heavy",
        n_pressure_points=104,
        seed_window_log_span=0.58,
        hint_window_log_span=0.52,
        pressure_window_log_span=0.58,
        bracket_window_log_span=0.32,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.35,
        max_temperature_step_k=10.0,
        step_growth=1.35,
    ),
    "volatile_oil": ContinuationRuntimePolicy(
        name="volatile_oil",
        n_pressure_points=96,
        seed_window_log_span=0.60,
        hint_window_log_span=0.55,
        pressure_window_log_span=0.60,
        bracket_window_log_span=0.35,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.35,
        max_temperature_step_k=10.0,
        step_growth=1.35,
    ),
    "black_oil": ContinuationRuntimePolicy(
        name="black_oil",
        n_pressure_points=104,
        seed_window_log_span=0.65,
        hint_window_log_span=0.60,
        pressure_window_log_span=0.65,
        bracket_window_log_span=0.38,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.35,
        max_temperature_step_k=8.0,
        step_growth=1.30,
    ),
    "sour_oil": ContinuationRuntimePolicy(
        name="sour_oil",
        n_pressure_points=112,
        seed_window_log_span=0.68,
        hint_window_log_span=0.62,
        pressure_window_log_span=0.68,
        bracket_window_log_span=0.40,
        allow_full_rescan_on_advance=False,
        min_temperature_step_k=0.35,
        max_temperature_step_k=7.0,
        step_growth=1.25,
    ),
    "co2_rich_gas": ContinuationRuntimePolicy(
        name="co2_rich_gas",
        n_pressure_points=192,
        seed_window_log_span=0.75,
        hint_window_log_span=0.72,
        pressure_window_log_span=0.75,
        bracket_window_log_span=0.35,
        allow_full_rescan_on_advance=True,
        min_temperature_step_k=0.25,
        max_temperature_step_k=2.0,
        step_growth=1.20,
    ),
}

_CONTINUATION_RUNTIME_POLICY_ALIASES = {
    "gas_condensate": "gas_condensate_light",
    "gas_condensate_c7plus": "gas_condensate_heavy",
    "volatile_oil_c7plus": "volatile_oil",
    "co2_regression_gas": "co2_rich_gas",
    "co2_rich_near_critical": "co2_rich_gas",
}


def resolve_continuation_runtime_policy(fluid_family: Optional[str]) -> ContinuationRuntimePolicy:
    """Return the continuation tuning profile for one runtime fluid family."""
    if fluid_family is None:
        return DEFAULT_CONTINUATION_RUNTIME_POLICY

    normalized = str(fluid_family).strip().lower().replace("-", "_").replace(" ", "_")
    key = _CONTINUATION_RUNTIME_POLICY_ALIASES.get(normalized, normalized)
    return _CONTINUATION_RUNTIME_POLICIES.get(key, DEFAULT_CONTINUATION_RUNTIME_POLICY)


def _coerce_runtime_policy(
    runtime_policy: Optional[ContinuationRuntimePolicy],
) -> ContinuationRuntimePolicy:
    """Return the active continuation policy, falling back to the generic runtime profile."""
    if runtime_policy is None:
        return DEFAULT_CONTINUATION_RUNTIME_POLICY
    return runtime_policy


@dataclass(frozen=True)
class ContinuationState:
    """One certified continuation point on a bubble or dew branch."""

    branch: BranchName
    temperature: float
    pressure: float
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    liquid_density: float
    vapor_density: float
    K_values: NDArray[np.float64]
    residual: float
    bracket: RootBracket


@dataclass(frozen=True)
class ContinuationTraceResult:
    """Trace of one local branch family over a temperature sequence."""

    branch: BranchName
    states: tuple[ContinuationState, ...]
    termination_reason: Optional[str] = None
    termination_temperature: Optional[float] = None

    @property
    def converged(self) -> bool:
        """Return True when at least one continuation state was resolved."""
        return len(self.states) > 0


@dataclass(frozen=True)
class CriticalJunction:
    """Estimated critical-junction marker for a continuation envelope."""

    temperature: float
    pressure: float
    source: str
    score: float
    phase_gap: float
    k_deviation: float


@dataclass(frozen=True)
class EnvelopeContinuationResult:
    """Development envelope result assembled from continuation branch traces."""

    bubble_states: tuple[ContinuationState, ...]
    dew_states: tuple[ContinuationState, ...]
    critical_state: Optional[CriticalJunction]
    switched: bool
    bubble_termination_reason: Optional[str]
    bubble_termination_temperature: Optional[float]
    dew_termination_reason: Optional[str]
    dew_termination_temperature: Optional[float]

    @property
    def converged(self) -> bool:
        """Return True when the result contains any branch states."""
        return bool(self.bubble_states or self.dew_states)


@dataclass(frozen=True)
class _BranchPointClassification:
    """Internal branch classification at a single pressure."""

    pressure: float
    klass: int
    trivial: bool


@dataclass(frozen=True)
class _ContinuationTransitionMetrics:
    """Continuity metrics between two neighboring branch states."""

    log_pressure_jump: float
    phase_component_jump: float
    k_value_jump: float
    midpoint_density_rel_jump: float


def _pressure_bar_to_pa(pressure_bar: float) -> float:
    return float(pressure_bar) * 1.0e5


def _branch_tolerance(branch: BranchName) -> float:
    if branch == "bubble":
        return float(BUBBLE_POINT_TOLERANCE)
    if branch == "dew":
        return float(DEW_POINT_TOLERANCE)
    raise ValueError(f"Unsupported branch: {branch}")


def _evaluate_branch_trial(
    branch: BranchName,
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> tuple[float, NDArray[np.float64]]:
    if branch == "bubble":
        return _tpd_vapor_trial(pressure, temperature, composition, eos, binary_interaction)
    if branch == "dew":
        return _tpd_liquid_trial(pressure, temperature, composition, eos, binary_interaction)
    raise ValueError(f"Unsupported branch: {branch}")


def _evaluate_branch_scalar(
    pressure: float,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> float:
    if branch == "bubble":
        return float(_tpd_vapor_trial_scalar(pressure, temperature, composition, eos, binary_interaction))
    if branch == "dew":
        return float(_tpd_liquid_trial_scalar(pressure, temperature, composition, eos, binary_interaction))
    raise ValueError(f"Unsupported branch: {branch}")


def _is_trivial_branch_trial(
    branch: BranchName,
    composition: NDArray[np.float64],
    trial: NDArray[np.float64],
) -> bool:
    if branch == "bubble":
        return bool(_is_bubble_trivial(composition, trial))
    if branch == "dew":
        return bool(_is_dew_trivial(composition, trial))
    raise ValueError(f"Unsupported branch: {branch}")


def _classify_branch_point(
    *,
    branch: BranchName,
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> _BranchPointClassification:
    """Classify one branch point as stable, unstable, or trivial zero."""
    tpd_value, trial = _evaluate_branch_trial(
        branch,
        float(pressure),
        float(temperature),
        composition,
        eos,
        binary_interaction,
    )
    trial = normalize_trial(trial)
    klass = tpd_class(float(tpd_value), _branch_tolerance(branch))
    trivial = bool(klass == 0 and _is_trivial_branch_trial(branch, composition, trial))
    return _BranchPointClassification(
        pressure=float(pressure),
        klass=int(klass),
        trivial=trivial,
    )


def _sign_change_matches(branch: BranchName, class_lo: int, class_hi: int) -> bool:
    """Return True when a class transition brackets the target branch root."""
    return (
        (branch == "bubble" and class_lo == -1 and class_hi == 1)
        or (branch == "dew" and class_lo == 1 and class_hi == -1)
    )


def _search_interval_for_nontrivial_boundary(
    *,
    branch: BranchName,
    pressure_lo: float,
    pressure_hi: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_points: int = REFINEMENT_PRESSURE_POINTS,
) -> tuple[str, float, Optional[float]] | None:
    """Recover a narrow non-trivial boundary hidden inside a coarse interval."""
    if pressure_hi <= pressure_lo:
        return None

    pressures = np.geomspace(float(pressure_lo), float(pressure_hi), int(n_points))
    samples = [
        _classify_branch_point(
            branch=branch,
            pressure=float(pressure),
            temperature=float(temperature),
            composition=composition,
            eos=eos,
            binary_interaction=binary_interaction,
        )
        for pressure in pressures
    ]

    for sample in samples:
        if sample.klass == 0 and not sample.trivial:
            return ("point", float(sample.pressure), None)

    for left, right in zip(samples, samples[1:]):
        if _sign_change_matches(branch, left.klass, right.klass):
            return ("bracket", float(left.pressure), float(right.pressure))

    return None


def _synthetic_point_bracket(branch: BranchName, pressure: float) -> RootBracket:
    """Build a synthetic zero-width bracket for a directly resolved boundary point."""
    pressure_bar = float(pressure) / 1.0e5
    return RootBracket(
        branch=branch,
        pressure_lo_bar=pressure_bar,
        pressure_hi_bar=pressure_bar,
        class_lo=0,
        class_hi=0,
        trivial_lo=False,
        trivial_hi=False,
    )


def _seek_local_candidate_near_pressure(
    *,
    branch: BranchName,
    pressure_center: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    log_span: float,
    n_expansions: int = 12,
) -> Optional[ContinuationState]:
    """Try to certify a nearby boundary with a small local search around one pressure guess."""
    if not np.isfinite(float(pressure_center)) or float(pressure_center) <= 0.0:
        return None

    pressure_min, pressure_max = _pressure_window(float(pressure_center), log_span=log_span)
    if pressure_max <= pressure_min:
        return None

    span_ratio = max(float(np.exp(log_span)), 1.0001)
    ratios = np.geomspace(1.0, span_ratio, max(int(n_expansions), 3))
    candidate_pressures = [float(pressure_center)]
    for ratio in ratios:
        candidate_pressures.append(max(float(pressure_min), float(pressure_center) / float(ratio)))
        candidate_pressures.append(min(float(pressure_max), float(pressure_center) * float(ratio)))

    unique_pressures: List[float] = []
    for pressure in sorted(candidate_pressures):
        if not unique_pressures or abs(np.log(pressure / unique_pressures[-1])) > 1.0e-6:
            unique_pressures.append(float(pressure))

    samples = [
        _classify_branch_point(
            branch=branch,
            pressure=float(pressure),
            temperature=float(temperature),
            composition=composition,
            eos=eos,
            binary_interaction=binary_interaction,
        )
        for pressure in unique_pressures
    ]

    for sample in samples:
        if sample.klass == 0 and not sample.trivial:
            try:
                return _build_state(
                    branch=branch,
                    pressure=float(sample.pressure),
                    temperature=float(temperature),
                    composition=composition,
                    eos=eos,
                    binary_interaction=binary_interaction,
                    bracket=_synthetic_point_bracket(branch, float(sample.pressure)),
                )
            except PhaseError:
                continue

    for left, right in zip(samples, samples[1:]):
        if not _sign_change_matches(branch, left.klass, right.klass):
            continue
        try:
            return _resolve_local_bracket(
                branch=branch,
                bracket=RootBracket(
                    branch=branch,
                    pressure_lo_bar=float(left.pressure) / 1.0e5,
                    pressure_hi_bar=float(right.pressure) / 1.0e5,
                    class_lo=int(left.klass),
                    class_hi=int(right.klass),
                    trivial_lo=bool(left.trivial),
                    trivial_hi=bool(right.trivial),
                ),
                temperature=float(temperature),
                composition=composition,
                eos=eos,
                binary_interaction=binary_interaction,
            )
        except PhaseError:
            continue

    return None


def _build_state(
    *,
    branch: BranchName,
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    bracket: RootBracket,
) -> ContinuationState:
    residual, trial = _evaluate_branch_trial(
        branch,
        float(pressure),
        float(temperature),
        composition,
        eos,
        binary_interaction,
    )
    trial = normalize_trial(trial)
    if _is_trivial_branch_trial(branch, composition, trial):
        raise PhaseError(
            "Local continuation root collapsed to a trivial trial state and cannot be certified.",
            pressure=float(pressure),
            temperature=float(temperature),
            reason="degenerate_trivial_boundary",
            phase="liquid" if branch == "bubble" else "vapor",
        )

    z = np.asarray(composition, dtype=np.float64)
    eps = 1e-300

    if branch == "bubble":
        liquid = z.copy()
        vapor = np.asarray(trial, dtype=np.float64)
        k_values = vapor / np.maximum(liquid, eps)
    else:
        vapor = z.copy()
        liquid = np.asarray(trial, dtype=np.float64)
        k_values = vapor / np.maximum(liquid, eps)

    phase_gap = float(np.max(np.abs(vapor - liquid)))
    k_deviation = float(np.max(np.abs(k_values - 1.0)))
    if _is_near_trivial_state(phase_gap, k_deviation):
        raise PhaseError(
            "Local continuation root is numerically indistinguishable from the trivial critical state.",
            pressure=float(pressure),
            temperature=float(temperature),
            reason="degenerate_trivial_boundary",
            phase="liquid" if branch == "bubble" else "vapor",
        )

    liquid_density = float(
        eos.density(
            float(pressure),
            float(temperature),
            liquid,
            phase="liquid",
            binary_interaction=binary_interaction,
        )
    )
    vapor_density = float(
        eos.density(
            float(pressure),
            float(temperature),
            vapor,
            phase="vapor",
            binary_interaction=binary_interaction,
        )
    )

    return ContinuationState(
        branch=branch,
        temperature=float(temperature),
        pressure=float(pressure),
        liquid_composition=liquid.astype(np.float64),
        vapor_composition=vapor.astype(np.float64),
        liquid_density=liquid_density,
        vapor_density=vapor_density,
        K_values=k_values.astype(np.float64),
        residual=float(abs(residual)),
        bracket=bracket,
    )


def _resolve_local_bracket(
    *,
    branch: BranchName,
    bracket: RootBracket,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> ContinuationState:
    """Resolve one certified local saturation bracket into a continuation state."""
    z = np.asarray(composition, dtype=np.float64)
    tol = _branch_tolerance(branch)
    pressure_lo = _pressure_bar_to_pa(bracket.pressure_lo_bar)
    pressure_hi = _pressure_bar_to_pa(bracket.pressure_hi_bar)

    lo = _classify_branch_point(
        branch=branch,
        pressure=pressure_lo,
        temperature=temperature,
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
    )
    hi = _classify_branch_point(
        branch=branch,
        pressure=pressure_hi,
        temperature=temperature,
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
    )

    if lo.klass == 0 and not lo.trivial:
        return _build_state(
            branch=branch,
            pressure=lo.pressure,
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            bracket=bracket,
        )

    if hi.klass == 0 and not hi.trivial:
        return _build_state(
            branch=branch,
            pressure=hi.pressure,
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            bracket=bracket,
        )

    recovered = None
    if _sign_change_matches(branch, lo.klass, hi.klass):
        recovered = ("bracket", float(pressure_lo), float(pressure_hi))
    else:
        recovered = _search_interval_for_nontrivial_boundary(
            branch=branch,
            pressure_lo=pressure_lo,
            pressure_hi=pressure_hi,
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
        )

    if recovered is None:
        raise PhaseError(
            "Local transition is not a certified non-trivial saturation root.",
            pressure=float(np.sqrt(pressure_lo * pressure_hi)),
            temperature=float(temperature),
            reason="uncertified_local_transition",
            phase="liquid" if branch == "bubble" else "vapor",
        )

    if recovered[0] == "point":
        return _build_state(
            branch=branch,
            pressure=float(recovered[1]),
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            bracket=bracket,
        )

    assert recovered[2] is not None
    pressure_star, _ = brent_method(
        _evaluate_branch_scalar,
        float(recovered[1]),
        float(recovered[2]),
        args=(branch, temperature, z, eos, binary_interaction),
        tol=tol,
        max_iter=80,
    )
    return _build_state(
        branch=branch,
        pressure=float(pressure_star),
        temperature=temperature,
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
        bracket=bracket,
    )


def _pressure_window(
    pressure: float,
    *,
    log_span: float = DEFAULT_PRESSURE_WINDOW_LOG_SPAN,
) -> tuple[float, float]:
    """Return a bounded pressure window around a target pressure."""
    span = max(float(log_span), 0.1)
    lower = float(pressure) * float(np.exp(-span))
    upper = float(pressure) * float(np.exp(span))
    return (
        max(float(PRESSURE_MIN), lower),
        min(float(PRESSURE_MAX), upper),
    )


def _bracket_window(
    bracket: RootBracket,
    *,
    padding_log_span: float = 0.4,
) -> tuple[float, float]:
    """Return a bounded pressure window around a prior root bracket."""
    lo = _pressure_bar_to_pa(bracket.pressure_lo_bar)
    hi = _pressure_bar_to_pa(bracket.pressure_hi_bar)
    if lo <= 0.0 or hi <= 0.0 or not np.isfinite(lo) or not np.isfinite(hi):
        return _pressure_window(max(lo, hi, PRESSURE_MIN))
    center = float(np.sqrt(lo * hi))
    base_min = float(min(lo, hi))
    base_max = float(max(lo, hi))
    span_min, span_max = _pressure_window(center, log_span=padding_log_span)
    return (
        max(float(PRESSURE_MIN), min(base_min, span_min)),
        min(float(PRESSURE_MAX), max(base_max, span_max)),
    )


def _should_use_arclength(previous: ContinuationState) -> bool:
    """Return True when the branch is close enough to critical to justify arclength hints."""
    return (
        _state_phase_gap(previous) <= ARCLENGTH_PHASE_GAP_THRESHOLD
        or _state_k_deviation(previous) <= ARCLENGTH_K_DEVIATION_THRESHOLD
    )


def _arclength_pressure_hint(
    previous: ContinuationState,
    prior: ContinuationState,
    *,
    temperature_target: float,
) -> float:
    """Predict next pressure using a local secant slope in (T, P) space."""
    dt = float(previous.temperature - prior.temperature)
    if abs(dt) <= 1.0e-12:
        return float(previous.pressure)
    slope = float((previous.pressure - prior.pressure) / dt)
    return float(previous.pressure + slope * (float(temperature_target) - previous.temperature))


def resolve_local_branch_candidates(
    *,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    pressure_min: Optional[float] = None,
    pressure_max: Optional[float] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> List[ContinuationState]:
    """Resolve all certified local saturation candidates at one temperature."""
    z = np.asarray(composition, dtype=np.float64)
    candidates: List[ContinuationState] = []

    for bracket in scan_branch_roots(
        branch=branch,
        temperature=float(temperature),
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        pressure_min=float(pressure_min) if pressure_min is not None else PRESSURE_MIN,
        pressure_max=float(pressure_max) if pressure_max is not None else PRESSURE_MAX,
    ):
        if cancel_check is not None:
            cancel_check()
        try:
            candidates.append(
                _resolve_local_bracket(
                    branch=branch,
                    bracket=bracket,
                    temperature=float(temperature),
                    composition=z,
                    eos=eos,
                    binary_interaction=binary_interaction,
                )
            )
        except PhaseError as exc:
            if exc.details.get("reason") not in {
                "uncertified_local_transition",
                "degenerate_trivial_boundary",
            }:
                raise

    candidates.sort(key=lambda state: state.pressure)
    return candidates


def _state_phase_gap(state: ContinuationState) -> float:
    """Return max|x - y| for one continuation state."""
    return float(np.max(np.abs(state.vapor_composition - state.liquid_composition)))


def _state_k_deviation(state: ContinuationState) -> float:
    """Return max|K - 1| for one continuation state."""
    return float(np.max(np.abs(state.K_values - 1.0)))


def _state_midpoint_density(state: ContinuationState) -> float:
    """Return the branch midpoint density used for density-marched continuation."""
    return 0.5 * (float(state.liquid_density) + float(state.vapor_density))


def _is_near_trivial_state(phase_gap: float, k_deviation: float) -> bool:
    """Return True when a resolved state has effectively collapsed to critical triviality."""
    return (
        float(phase_gap) <= NEAR_TRIVIAL_PHASE_GAP
        and float(k_deviation) <= NEAR_TRIVIAL_K_DEVIATION
    )


def _state_branch_phase(state: ContinuationState) -> NDArray[np.float64]:
    """Return the incipient-phase composition used for branch-family tracking."""
    if state.branch == "bubble":
        return state.vapor_composition
    return state.liquid_composition


def _k_value_transition_jump(
    previous: ContinuationState,
    candidate: ContinuationState,
) -> float:
    """Return a scale-stable K-value continuity metric for branch tracking.

    Raw ``|K_new - K_old|`` can explode on legitimate low-pressure dew branches
    where one component has a very large but smoothly varying ``K`` value. Use a
    log-ratio jump instead so continuity follows relative motion of the root
    family rather than the absolute magnitude of ``K``.
    """
    eps = 1.0e-300
    previous_k = np.maximum(previous.K_values, eps)
    candidate_k = np.maximum(candidate.K_values, eps)
    return float(np.max(np.abs(np.log(candidate_k / previous_k))))


def _continuation_transition_metrics(
    previous: ContinuationState,
    candidate: ContinuationState,
) -> _ContinuationTransitionMetrics:
    """Return continuity metrics between two neighboring continuation states."""
    midpoint_density = max(abs(_state_midpoint_density(previous)), 1.0)
    return _ContinuationTransitionMetrics(
        log_pressure_jump=float(abs(np.log(candidate.pressure / previous.pressure))),
        phase_component_jump=float(
            np.max(np.abs(_state_branch_phase(candidate) - _state_branch_phase(previous)))
        ),
        k_value_jump=_k_value_transition_jump(previous, candidate),
        midpoint_density_rel_jump=float(
            abs(_state_midpoint_density(candidate) - _state_midpoint_density(previous)) / midpoint_density
        ),
    )


def _transition_is_acceptable(
    metrics: _ContinuationTransitionMetrics,
    *,
    max_log_pressure_jump: float,
    max_phase_composition_jump: float,
    max_k_value_jump: float,
    density_march: bool = False,
) -> bool:
    """Return True when the neighboring state looks like the same root family."""
    if density_march and metrics.midpoint_density_rel_jump <= DENSITY_MARCH_MIDPOINT_JUMP_MAX:
        return True
    return (
        metrics.log_pressure_jump <= float(max_log_pressure_jump)
        and metrics.phase_component_jump <= float(max_phase_composition_jump)
        and metrics.k_value_jump <= float(max_k_value_jump)
    )


def _continuation_score(
    previous: ContinuationState,
    candidate: ContinuationState,
    *,
    density_march: bool = False,
) -> float:
    metrics = _continuation_transition_metrics(previous, candidate)
    if density_march:
        return float(
            2.0 * metrics.midpoint_density_rel_jump
            + 0.35 * metrics.phase_component_jump
            + 0.05 * metrics.k_value_jump
            + 0.05 * metrics.log_pressure_jump
        )
    return float(
        metrics.log_pressure_jump
        + 0.50 * metrics.phase_component_jump
        + 0.05 * metrics.k_value_jump
    )


def _candidate_collapses_to_critical_junction(candidate: ContinuationState) -> bool:
    """Return True when a step should stop at the critical handoff neighborhood."""
    return (
        _state_phase_gap(candidate) <= CRITICAL_COLLAPSE_PHASE_GAP
        and _state_k_deviation(candidate) <= CRITICAL_COLLAPSE_K_DEVIATION
    )


def _accept_advanced_candidate(
    candidate: ContinuationState,
    *,
    temperature: float,
) -> ContinuationState:
    """Reject candidates that have already collapsed into the critical junction."""
    if candidate.branch == "bubble" and _candidate_collapses_to_critical_junction(candidate):
        raise PhaseError(
            "Continuation branch collapsed into the critical junction neighborhood.",
            pressure=float(candidate.pressure),
            temperature=float(temperature),
            reason="no_local_root_candidates",
        )
    return candidate


def _select_candidate(
    *,
    candidates: Sequence[ContinuationState],
    pressure_seed: Optional[float] = None,
    previous_state: Optional[ContinuationState] = None,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    density_march: bool = False,
) -> ContinuationState:
    if not candidates:
        raise PhaseError(
            "No certified local continuation roots exist at this temperature.",
            pressure=float(pressure_seed) if pressure_seed is not None else None,
            temperature=float(previous_state.temperature) if previous_state is not None else None,
            reason="no_local_root_candidates",
        )

    if previous_state is not None:
        scored = sorted(
            (
                (
                    _continuation_score(
                        previous_state,
                        candidate,
                        density_march=density_march,
                    ),
                    candidate,
                )
                for candidate in candidates
            ),
            key=lambda item: item[0],
        )
        _, best_candidate = scored[0]
        metrics = _continuation_transition_metrics(previous_state, best_candidate)
        if not _transition_is_acceptable(
            metrics,
            max_log_pressure_jump=max_log_pressure_jump,
            max_phase_composition_jump=max_phase_composition_jump,
            max_k_value_jump=max_k_value_jump,
            density_march=density_march,
        ):
            raise PhaseError(
                "The continuation branch could not be matched to a nearby local root family.",
                pressure=float(best_candidate.pressure),
                temperature=float(best_candidate.temperature),
                reason="branch_family_lost",
                phase_jump=float(metrics.phase_component_jump),
                k_jump=float(metrics.k_value_jump),
            )
        return best_candidate

    if pressure_seed is None:
        return candidates[0]

    return min(candidates, key=lambda candidate: abs(np.log(candidate.pressure / float(pressure_seed))))


def seed_continuation_state(
    *,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    pressure_seed: Optional[float] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationState:
    """Seed a continuation branch from certified local roots at one temperature."""
    policy = _coerce_runtime_policy(runtime_policy)
    z = np.asarray(composition, dtype=np.float64)
    if pressure_seed is None:
        if branch == "bubble":
            pressure_seed = float(
                calculate_bubble_point(
                    float(temperature),
                    z,
                    components,
                    eos,
                    binary_interaction=binary_interaction,
                ).pressure
            )
        else:
            pressure_seed = float(
                calculate_dew_point(
                    float(temperature),
                    z,
                    components,
                    eos,
                    binary_interaction=binary_interaction,
                ).pressure
            )

    candidates = resolve_local_branch_candidates(
        branch=branch,
        temperature=float(temperature),
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        pressure_min=(
            _pressure_window(float(pressure_seed), log_span=policy.seed_window_log_span)[0]
            if pressure_seed is not None
            else None
        ),
        pressure_max=(
            _pressure_window(float(pressure_seed), log_span=policy.seed_window_log_span)[1]
            if pressure_seed is not None
            else None
        ),
        cancel_check=cancel_check,
    )
    if not candidates and pressure_seed is not None:
        candidates = resolve_local_branch_candidates(
            branch=branch,
            temperature=float(temperature),
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            cancel_check=cancel_check,
        )
    return _select_candidate(
        candidates=candidates,
        pressure_seed=pressure_seed,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
    )


def advance_continuation_state(
    previous_state: ContinuationState,
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    pressure_hint: Optional[float] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationState:
    """Advance one continuation branch to the next temperature."""
    policy = _coerce_runtime_policy(runtime_policy)
    use_arclength_region = (
        pressure_hint is not None
        and np.isfinite(pressure_hint)
        and _should_use_arclength(previous_state)
    )
    if pressure_hint is not None and np.isfinite(pressure_hint):
        hint_min, hint_max = _pressure_window(
            float(pressure_hint),
            log_span=policy.hint_window_log_span,
        )
    else:
        hint_min, hint_max = None, None

    if hint_min is not None:
        local_candidate = _seek_local_candidate_near_pressure(
            branch=previous_state.branch,
            pressure_center=float(pressure_hint),
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            log_span=policy.hint_window_log_span,
        )
        if local_candidate is not None:
            try:
                local_candidate = _select_candidate(
                    candidates=[local_candidate],
                    previous_state=previous_state,
                    max_log_pressure_jump=max_log_pressure_jump,
                    max_phase_composition_jump=max_phase_composition_jump,
                    max_k_value_jump=max_k_value_jump,
                    density_march=density_march,
                )
                return _accept_advanced_candidate(
                    local_candidate,
                    temperature=float(temperature),
                )
            except PhaseError as exc:
                if exc.details.get("reason") not in {"branch_family_lost"}:
                    raise

        candidates = resolve_local_branch_candidates(
            branch=previous_state.branch,
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            pressure_min=hint_min,
            pressure_max=hint_max,
            cancel_check=cancel_check,
        )
        if candidates:
            try:
                candidate = _select_candidate(
                    candidates=candidates,
                    previous_state=previous_state,
                    max_log_pressure_jump=max_log_pressure_jump,
                    max_phase_composition_jump=max_phase_composition_jump,
                    max_k_value_jump=max_k_value_jump,
                    density_march=density_march,
                )
                return _accept_advanced_candidate(
                    candidate,
                    temperature=float(temperature),
                )
            except PhaseError as exc:
                if exc.details.get("reason") not in {"branch_family_lost"}:
                    raise

    pressure_min, pressure_max = _pressure_window(
        previous_state.pressure,
        log_span=policy.pressure_window_log_span,
    )
    local_candidate = _seek_local_candidate_near_pressure(
        branch=previous_state.branch,
        pressure_center=float(previous_state.pressure),
        temperature=float(temperature),
        composition=np.asarray(composition, dtype=np.float64),
        eos=eos,
        binary_interaction=binary_interaction,
        log_span=policy.pressure_window_log_span,
    )
    if local_candidate is not None:
        try:
            local_candidate = _select_candidate(
                candidates=[local_candidate],
                previous_state=previous_state,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                density_march=density_march,
            )
            return _accept_advanced_candidate(
                local_candidate,
                temperature=float(temperature),
            )
        except PhaseError as exc:
            if exc.details.get("reason") not in {"branch_family_lost"}:
                raise

    candidates = resolve_local_branch_candidates(
        branch=previous_state.branch,
        temperature=float(temperature),
        composition=np.asarray(composition, dtype=np.float64),
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        pressure_min=pressure_min,
        pressure_max=pressure_max,
        cancel_check=cancel_check,
    )
    if candidates:
        try:
            candidate = _select_candidate(
                candidates=candidates,
                previous_state=previous_state,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                density_march=density_march,
            )
            return _accept_advanced_candidate(
                candidate,
                temperature=float(temperature),
            )
        except PhaseError as exc:
            if exc.details.get("reason") not in {"branch_family_lost"}:
                raise

    if not use_arclength_region:
        bracket_min, bracket_max = _bracket_window(
            previous_state.bracket,
            padding_log_span=policy.bracket_window_log_span,
        )
        candidates = resolve_local_branch_candidates(
            branch=previous_state.branch,
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            pressure_min=bracket_min,
            pressure_max=bracket_max,
            cancel_check=cancel_check,
        )
        if candidates:
            try:
                candidate = _select_candidate(
                    candidates=candidates,
                    previous_state=previous_state,
                    max_log_pressure_jump=max_log_pressure_jump,
                    max_phase_composition_jump=max_phase_composition_jump,
                    max_k_value_jump=max_k_value_jump,
                    density_march=density_march,
                )
                return _accept_advanced_candidate(
                    candidate,
                    temperature=float(temperature),
                )
            except PhaseError as exc:
                if exc.details.get("reason") not in {"branch_family_lost"}:
                    raise

    if not candidates and policy.allow_full_rescan_on_advance:
        candidates = resolve_local_branch_candidates(
            branch=previous_state.branch,
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            cancel_check=cancel_check,
        )
    candidate = _select_candidate(
        candidates=candidates,
        previous_state=previous_state,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
        density_march=density_march,
    )
    return _accept_advanced_candidate(
        candidate,
        temperature=float(temperature),
    )


def trace_branch_continuation(
    *,
    branch: BranchName,
    temperatures: Sequence[float],
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    pressure_seed: Optional[float] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationTraceResult:
    """Trace one certified local branch family across a temperature sequence."""
    if len(temperatures) == 0:
        raise ValidationError(
            "temperatures cannot be empty",
            parameter="temperatures",
            value=[],
        )

    temps = [float(value) for value in temperatures]
    if any(not np.isfinite(value) or value <= 0.0 for value in temps):
        raise ValidationError(
            "temperatures must contain finite positive values",
            parameter="temperatures",
            value=temps,
        )

    states: List[ContinuationState] = []
    termination_reason: Optional[str] = None
    termination_temperature: Optional[float] = None

    try:
        state = seed_continuation_state(
            branch=branch,
            temperature=temps[0],
            composition=np.asarray(composition, dtype=np.float64),
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            pressure_seed=pressure_seed,
            n_pressure_points=n_pressure_points,
            max_log_pressure_jump=max_log_pressure_jump,
            max_phase_composition_jump=max_phase_composition_jump,
            max_k_value_jump=max_k_value_jump,
            runtime_policy=runtime_policy,
            cancel_check=cancel_check,
        )
        states.append(state)
    except PhaseError as exc:
        return ContinuationTraceResult(
            branch=branch,
            states=tuple(),
            termination_reason=exc.details.get("reason", "seed_failed"),
            termination_temperature=temps[0],
        )

    previous = state
    for temperature in temps[1:]:
        if cancel_check is not None:
            cancel_check()
        try:
            previous = advance_continuation_state(
                previous,
                temperature=float(temperature),
                composition=np.asarray(composition, dtype=np.float64),
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            states.append(previous)
        except PhaseError as exc:
            termination_reason = exc.details.get("reason", "advance_failed")
            termination_temperature = float(temperature)
            break

    return ContinuationTraceResult(
        branch=branch,
        states=tuple(states),
        termination_reason=termination_reason,
        termination_temperature=termination_temperature,
    )


def _recoverable_branch_failure(exc: PhaseError) -> bool:
    """Return True when a failed advance should trigger step rollback."""
    return exc.details.get("reason") in {
        "no_local_root_candidates",
        "branch_family_lost",
        "uncertified_local_transition",
        "degenerate_trivial_boundary",
    }


def _adaptive_step_bounds(
    *,
    temperature_start: float,
    temperature_end: float,
    target_points: int,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
) -> tuple[float, float, float]:
    """Return initial/min/max temperature steps for adaptive tracing."""
    policy = _coerce_runtime_policy(runtime_policy)
    span = max(abs(float(temperature_end) - float(temperature_start)), DEFAULT_MIN_TEMPERATURE_STEP_K)
    target = max(int(target_points), 2)
    initial = max(float(policy.min_temperature_step_k), span / float(target))
    initial = min(initial, float(policy.max_temperature_step_k))
    minimum = max(float(policy.min_temperature_step_k), initial / 8.0)
    maximum = min(float(policy.max_temperature_step_k), max(initial, 2.0 * initial))
    return float(initial), float(minimum), float(maximum)


def _seed_continuation_state_with_search(
    *,
    branch: BranchName,
    temperature_start: float,
    temperature_end: float,
    target_points: int,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    pressure_seed: Optional[float] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> tuple[Optional[ContinuationState], Optional[str], Optional[float]]:
    """Seed a branch, searching forward in temperature if the first point has no root."""
    search_points = max(8, min(32, int(target_points) * 2))
    temperatures = np.linspace(float(temperature_start), float(temperature_end), search_points, dtype=float)

    last_exc: Optional[PhaseError] = None
    for temperature in temperatures:
        if cancel_check is not None:
            cancel_check()
        try:
            candidate = seed_continuation_state(
                branch=branch,
                temperature=float(temperature),
                composition=np.asarray(composition, dtype=np.float64),
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                pressure_seed=pressure_seed,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            candidate = _refine_seed_candidate(
                candidate,
                branch=branch,
                temperature=float(temperature),
                composition=np.asarray(composition, dtype=np.float64),
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                pressure_seed=pressure_seed,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            return (
                candidate,
                None,
                None,
            )
        except PhaseError as exc:
            last_exc = exc

    reason = "seed_failed" if last_exc is None else last_exc.details.get("reason", "seed_failed")
    return None, reason, float(temperatures[0]) if len(temperatures) else float(temperature_start)


def _refine_seed_candidate(
    candidate: ContinuationState,
    *,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    pressure_seed: Optional[float],
    n_pressure_points: int,
    max_log_pressure_jump: float,
    max_phase_composition_jump: float,
    max_k_value_jump: float,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationState:
    """Retry ambiguous seed states with a denser pressure scan."""
    if pressure_seed is None or n_pressure_points >= 220:
        return candidate

    candidate_gap = abs(np.log(candidate.pressure / float(pressure_seed)))
    if candidate_gap <= 0.05:
        return candidate

    try:
        refined = seed_continuation_state(
            branch=branch,
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            pressure_seed=pressure_seed,
            n_pressure_points=max(220, int(n_pressure_points) * 2),
            max_log_pressure_jump=max_log_pressure_jump,
            max_phase_composition_jump=max_phase_composition_jump,
            max_k_value_jump=max_k_value_jump,
            runtime_policy=runtime_policy,
            cancel_check=cancel_check,
        )
    except PhaseError:
        return candidate

    refined_gap = abs(np.log(refined.pressure / float(pressure_seed)))
    if refined_gap < candidate_gap:
        return refined
    return candidate


def _refine_ambiguous_candidate(
    previous_state: ContinuationState,
    candidate: ContinuationState,
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
    max_log_pressure_jump: float,
    max_phase_composition_jump: float,
    max_k_value_jump: float,
    pressure_hint: Optional[float] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationState:
    """Retry ambiguous steps with a denser pressure scan before accepting them."""
    metrics = _continuation_transition_metrics(previous_state, candidate)
    needs_refinement = (
        n_pressure_points < 220
        and (
            metrics.log_pressure_jump > 0.08
            or metrics.phase_component_jump > 0.05
            or candidate.pressure < 0.98 * previous_state.pressure
        )
    )
    if not needs_refinement:
        return candidate

    refined = _best_refined_candidate(
        previous_state,
        temperature=float(temperature),
        composition=np.asarray(composition, dtype=np.float64),
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
        pressure_hint=pressure_hint,
        density_march=density_march,
        runtime_policy=runtime_policy,
        cancel_check=cancel_check,
    )
    if refined is not None and _continuation_score(
        previous_state,
        refined,
        density_march=density_march,
    ) < _continuation_score(
        previous_state,
        candidate,
        density_march=density_march,
    ):
        return refined
    return candidate


def _refined_pressure_point_options(
    n_pressure_points: int,
    *,
    critical_region: bool,
    use_pressure_hint: bool,
) -> tuple[int, ...]:
    """Return deterministic scan-density refinements for ambiguous local steps."""
    options: List[int] = []
    for value in (
        220,
        max(220, int(n_pressure_points) * 2),
        (
            CRITICAL_REFINEMENT_PRESSURE_POINTS
            if critical_region and use_pressure_hint
            else None
        ),
    ):
        if value is None:
            continue
        points = int(value)
        if points <= int(n_pressure_points) or points in options:
            continue
        options.append(points)
    return tuple(options)


def _best_refined_candidate(
    previous_state: ContinuationState,
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
    max_log_pressure_jump: float,
    max_phase_composition_jump: float,
    max_k_value_jump: float,
    pressure_hint: Optional[float] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> Optional[ContinuationState]:
    """Return the best refined candidate from a small set of deterministic rescans."""
    best_candidate: Optional[ContinuationState] = None
    best_score: Optional[float] = None
    for refined_points in _refined_pressure_point_options(
        n_pressure_points,
        critical_region=_should_use_arclength(previous_state),
        use_pressure_hint=pressure_hint is not None and np.isfinite(pressure_hint),
    ):
        if cancel_check is not None:
            cancel_check()
        try:
            refined = advance_continuation_state(
                previous_state,
                temperature=float(temperature),
                composition=np.asarray(composition, dtype=np.float64),
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=refined_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                pressure_hint=pressure_hint,
                density_march=density_march,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
        except PhaseError:
            continue

        score = _continuation_score(previous_state, refined, density_march=density_march)
        if best_score is None or score < best_score:
            best_candidate = refined
            best_score = score

    return best_candidate


def _retry_failed_candidate_with_refined_scan(
    previous_state: ContinuationState,
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
    max_log_pressure_jump: float,
    max_phase_composition_jump: float,
    max_k_value_jump: float,
    pressure_hint: Optional[float] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> Optional[ContinuationState]:
    """Retry a failed local step with a denser pressure scan before rolling back."""
    if n_pressure_points >= 220:
        return None

    return _best_refined_candidate(
        previous_state,
        temperature=float(temperature),
        composition=np.asarray(composition, dtype=np.float64),
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
        pressure_hint=pressure_hint,
        density_march=density_march,
        runtime_policy=runtime_policy,
        cancel_check=cancel_check,
    )


def _attempt_adaptive_branch_step(
    previous_state: ContinuationState,
    *,
    step_k: float,
    temperature_end: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    min_temperature_step_k: float = DEFAULT_MIN_TEMPERATURE_STEP_K,
    pressure_hint: Optional[float] = None,
    prior_state: Optional[ContinuationState] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> tuple[Optional[ContinuationState], float, Optional[str], Optional[float]]:
    """Advance one branch with rollback on ambiguous or failed steps."""
    policy = _coerce_runtime_policy(runtime_policy)
    direction = 1.0 if float(temperature_end) >= previous_state.temperature else -1.0
    remaining_span = abs(float(temperature_end) - previous_state.temperature)
    attempt_step = float(min(step_k, remaining_span))
    last_exc: Optional[PhaseError] = None
    last_temperature = previous_state.temperature

    while attempt_step >= float(min_temperature_step_k) - 1.0e-12:
        if cancel_check is not None:
            cancel_check()
        if direction > 0.0:
            candidate_temperature = min(previous_state.temperature + attempt_step, float(temperature_end))
        else:
            candidate_temperature = max(previous_state.temperature - attempt_step, float(temperature_end))
        last_temperature = float(candidate_temperature)
        candidate_pressure_hint = pressure_hint
        if prior_state is not None and policy.use_predictive_pressure_hint:
            candidate_pressure_hint = _arclength_pressure_hint(
                previous_state,
                prior_state,
                temperature_target=float(candidate_temperature),
            )
        try:
            candidate = advance_continuation_state(
                previous_state,
                temperature=float(candidate_temperature),
                composition=np.asarray(composition, dtype=np.float64),
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                pressure_hint=candidate_pressure_hint,
                density_march=density_march,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            candidate = _refine_ambiguous_candidate(
                previous_state,
                candidate,
                temperature=float(candidate_temperature),
                composition=np.asarray(composition, dtype=np.float64),
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                pressure_hint=candidate_pressure_hint,
                density_march=density_march,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            return candidate, float(attempt_step), None, None
        except PhaseError as exc:
            last_exc = exc
            if not _recoverable_branch_failure(exc):
                raise
            refined_candidate = _retry_failed_candidate_with_refined_scan(
                previous_state,
                temperature=float(candidate_temperature),
                composition=np.asarray(composition, dtype=np.float64),
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                max_phase_composition_jump=max_phase_composition_jump,
                max_k_value_jump=max_k_value_jump,
                pressure_hint=candidate_pressure_hint,
                density_march=density_march,
                runtime_policy=runtime_policy,
                cancel_check=cancel_check,
            )
            if refined_candidate is not None:
                refined_candidate = _refine_ambiguous_candidate(
                    previous_state,
                    refined_candidate,
                    temperature=float(candidate_temperature),
                    composition=np.asarray(composition, dtype=np.float64),
                    eos=eos,
                    binary_interaction=binary_interaction,
                    n_pressure_points=max(220, int(n_pressure_points) * 2),
                    max_log_pressure_jump=max_log_pressure_jump,
                    max_phase_composition_jump=max_phase_composition_jump,
                    max_k_value_jump=max_k_value_jump,
                    pressure_hint=candidate_pressure_hint,
                    density_march=density_march,
                    runtime_policy=runtime_policy,
                    cancel_check=cancel_check,
                )
                return refined_candidate, float(attempt_step), None, None
            attempt_step *= 0.5

    reason = "advance_failed" if last_exc is None else last_exc.details.get("reason", "advance_failed")
    return None, float(step_k), reason, float(last_temperature)


def _next_adaptive_temperature_step(
    previous_step_k: float,
    metrics: _ContinuationTransitionMetrics,
    *,
    min_step_k: float,
    max_step_k: float,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
) -> float:
    """Grow or hold the next temperature step based on continuity quality."""
    policy = _coerce_runtime_policy(runtime_policy)
    medium_growth = 1.0 + 0.5 * (float(policy.step_growth) - 1.0)
    if (
        metrics.log_pressure_jump <= 0.04
        and metrics.phase_component_jump <= 0.03
        and metrics.k_value_jump <= 0.50
    ):
        factor = float(policy.step_growth)
    elif (
        metrics.log_pressure_jump <= 0.08
        and metrics.phase_component_jump <= 0.06
        and metrics.k_value_jump <= 1.00
    ):
        factor = medium_growth
    else:
        factor = 1.0
    return float(min(float(max_step_k), max(float(min_step_k), previous_step_k * factor)))


def trace_branch_continuation_adaptive(
    *,
    branch: BranchName,
    temperature_start: float,
    temperature_end: float,
    target_points: int,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    pressure_seed: Optional[float] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationTraceResult:
    """Trace one branch adaptively with rollback and branch-family acceptance gates."""
    policy = _coerce_runtime_policy(runtime_policy)
    t_start = float(temperature_start)
    t_end = float(temperature_end)
    if not np.isfinite(t_start) or not np.isfinite(t_end) or t_start <= 0.0 or t_end <= 0.0:
        raise ValidationError(
            "temperature bounds must be finite and positive",
            parameter="temperatures",
            value=[temperature_start, temperature_end],
        )
    if abs(t_start - t_end) <= 1.0e-12:
        raise ValidationError(
            "temperature_start and temperature_end must differ",
            parameter="temperatures",
            value=[temperature_start, temperature_end],
        )

    initial_step_k, min_step_k, max_step_k = _adaptive_step_bounds(
        temperature_start=t_start,
        temperature_end=t_end,
        target_points=target_points,
        runtime_policy=policy,
    )

    state, termination_reason, termination_temperature = _seed_continuation_state_with_search(
        branch=branch,
        temperature_start=t_start,
        temperature_end=t_end,
        target_points=target_points,
        composition=np.asarray(composition, dtype=np.float64),
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
        pressure_seed=pressure_seed,
        n_pressure_points=n_pressure_points,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
        runtime_policy=policy,
        cancel_check=cancel_check,
    )
    if state is None:
        return ContinuationTraceResult(
            branch=branch,
            states=tuple(),
            termination_reason=termination_reason,
            termination_temperature=termination_temperature,
        )

    states: List[ContinuationState] = [state]
    step_k = initial_step_k
    previous = state
    prior: Optional[ContinuationState] = None
    direction = 1.0 if t_end >= previous.temperature else -1.0

    while direction * (t_end - previous.temperature) > 1.0e-12:
        if cancel_check is not None:
            cancel_check()
        candidate, accepted_step_k, failure_reason, failure_temperature = _attempt_adaptive_branch_step(
            previous,
            step_k=step_k,
            temperature_end=t_end,
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            max_log_pressure_jump=max_log_pressure_jump,
            max_phase_composition_jump=max_phase_composition_jump,
            max_k_value_jump=max_k_value_jump,
            min_temperature_step_k=min_step_k,
            prior_state=prior,
            density_march=density_march,
            runtime_policy=policy,
            cancel_check=cancel_check,
        )
        if candidate is None:
            termination_reason = failure_reason
            termination_temperature = failure_temperature
            break

        metrics = _continuation_transition_metrics(previous, candidate)
        states.append(candidate)
        prior = previous
        previous = candidate
        step_k = _next_adaptive_temperature_step(
            accepted_step_k,
            metrics,
            min_step_k=min_step_k,
            max_step_k=max_step_k,
            runtime_policy=policy,
        )

    return ContinuationTraceResult(
        branch=branch,
        states=tuple(states),
        termination_reason=termination_reason,
        termination_temperature=termination_temperature,
    )


def _density_handoff_score(reference_state: ContinuationState, candidate: ContinuationState) -> float:
    """Score a cross-branch handoff candidate by midpoint-density continuity."""
    reference_density = max(abs(_state_midpoint_density(reference_state)), 1.0)
    midpoint_density_gap = abs(_state_midpoint_density(candidate) - _state_midpoint_density(reference_state)) / reference_density
    pressure_gap = abs(np.log(candidate.pressure / reference_state.pressure))
    return float(
        2.0 * midpoint_density_gap
        + 0.50 * _state_phase_gap(candidate)
        + 0.10 * _state_k_deviation(candidate)
        + 0.05 * pressure_gap
    )


def _critical_probe_temperature_end(
    reference_temperature: float,
    temperature_end: float,
    *,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
) -> float:
    """Clamp exploratory hot-side tracing to the near-critical neighborhood."""
    policy = _coerce_runtime_policy(runtime_policy)
    span_k = max(
        CRITICAL_PROBE_MIN_SPAN_K,
        2.0 * CRITICAL_PAIR_MAX_TEMP_GAP,
        CRITICAL_PROBE_STEP_MULTIPLIER * float(policy.max_temperature_step_k),
    )
    t_start = float(reference_temperature)
    t_end = float(temperature_end)
    if t_end >= t_start:
        return float(min(t_end, t_start + span_k))
    return float(max(t_end, t_start - span_k))


def _density_handoff_temperatures(
    temperature_start: float,
    temperature_end: float,
    *,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
) -> NDArray[np.float64]:
    """Return a short, start-biased temperature grid for cross-branch handoff search."""
    policy = _coerce_runtime_policy(runtime_policy)
    t_start = float(temperature_start)
    t_end = float(temperature_end)
    if abs(t_end - t_start) <= 1.0e-12:
        return np.array([t_start], dtype=np.float64)

    span_k = abs(t_end - t_start)
    nominal_step_k = max(2.0, 1.5 * float(policy.max_temperature_step_k))
    search_points = int(np.ceil(span_k / nominal_step_k)) + 1
    search_points = max(
        DENSITY_HANDOFF_SEARCH_POINTS_MIN,
        min(DENSITY_HANDOFF_SEARCH_POINTS_MAX, search_points),
    )
    weights = np.linspace(0.0, 1.0, search_points, dtype=np.float64) ** 1.75
    return np.asarray(t_start + (t_end - t_start) * weights, dtype=np.float64)


def _find_density_handoff_seed(
    *,
    branch: BranchName,
    reference_state: ContinuationState,
    temperature_end: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> Optional[ContinuationState]:
    """Find the best cross-branch restart seed by midpoint-density continuity."""
    t_start = float(reference_state.temperature)
    t_end = _critical_probe_temperature_end(
        t_start,
        float(temperature_end),
        runtime_policy=runtime_policy,
    )
    if abs(t_end - t_start) <= 1.0e-12:
        return None

    temperatures = _density_handoff_temperatures(
        t_start,
        t_end,
        runtime_policy=runtime_policy,
    )
    best_candidate: Optional[ContinuationState] = None
    best_score: Optional[float] = None

    for temperature in temperatures:
        if cancel_check is not None:
            cancel_check()
        candidates = resolve_local_branch_candidates(
            branch=branch,
            temperature=float(temperature),
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            cancel_check=cancel_check,
        )
        for candidate in candidates:
            score = _density_handoff_score(reference_state, candidate)
            if best_score is None or score < best_score:
                best_candidate = candidate
                best_score = score

    return best_candidate


def trace_branch_continuation_adaptive_from_seed(
    seed_state: ContinuationState,
    *,
    temperature_end: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    target_points: int,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    prior_state: Optional[ContinuationState] = None,
    density_march: bool = False,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationTraceResult:
    """Trace one branch adaptively from an already-resolved seed state."""
    policy = _coerce_runtime_policy(runtime_policy)
    t_end = float(temperature_end)
    if not np.isfinite(t_end) or t_end <= 0.0:
        raise ValidationError(
            "temperature_end must be finite and positive",
            parameter="temperature_end",
            value=temperature_end,
        )
    if abs(seed_state.temperature - t_end) <= 1.0e-12:
        return ContinuationTraceResult(branch=seed_state.branch, states=(seed_state,))

    initial_step_k, min_step_k, max_step_k = _adaptive_step_bounds(
        temperature_start=float(seed_state.temperature),
        temperature_end=t_end,
        target_points=target_points,
        runtime_policy=policy,
    )
    if prior_state is not None:
        prior_step = abs(float(seed_state.temperature) - float(prior_state.temperature))
        if prior_step > 1.0e-12:
            initial_step_k = min(max_step_k, max(min_step_k, prior_step))

    states: List[ContinuationState] = [seed_state]
    step_k = initial_step_k
    previous = seed_state
    prior = prior_state
    direction = 1.0 if t_end >= previous.temperature else -1.0
    termination_reason: Optional[str] = None
    termination_temperature: Optional[float] = None

    while direction * (t_end - previous.temperature) > 1.0e-12:
        if cancel_check is not None:
            cancel_check()
        candidate, accepted_step_k, failure_reason, failure_temperature = _attempt_adaptive_branch_step(
            previous,
            step_k=step_k,
            temperature_end=t_end,
            composition=np.asarray(composition, dtype=np.float64),
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            max_log_pressure_jump=max_log_pressure_jump,
            max_phase_composition_jump=max_phase_composition_jump,
            max_k_value_jump=max_k_value_jump,
            min_temperature_step_k=min_step_k,
            prior_state=prior,
            density_march=density_march,
            runtime_policy=policy,
            cancel_check=cancel_check,
        )
        if candidate is None:
            termination_reason = failure_reason
            termination_temperature = failure_temperature
            break

        metrics = _continuation_transition_metrics(previous, candidate)
        states.append(candidate)
        prior = previous
        previous = candidate
        step_k = _next_adaptive_temperature_step(
            accepted_step_k,
            metrics,
            min_step_k=min_step_k,
            max_step_k=max_step_k,
            runtime_policy=policy,
        )

    return ContinuationTraceResult(
        branch=seed_state.branch,
        states=tuple(states),
        termination_reason=termination_reason,
        termination_temperature=termination_temperature,
    )


def _temperature_scale(temperatures: Sequence[float]) -> float:
    """Return a normalization scale for temperature-gap scoring."""
    if len(temperatures) <= 1:
        return 5.0
    span = max(float(value) for value in temperatures) - min(float(value) for value in temperatures)
    return max(5.0, 0.25 * span)


def _pair_phase_gap(bubble_state: ContinuationState, dew_state: ContinuationState) -> float:
    """Return a critical-proximity phase gap for one bubble/dew pair."""
    return float(
        max(
            _state_phase_gap(bubble_state),
            _state_phase_gap(dew_state),
            np.max(np.abs(bubble_state.vapor_composition - dew_state.liquid_composition)),
        )
    )


def _critical_anchor_score(state: ContinuationState) -> float:
    """Return how close one traced state is to the critical collapse."""
    return float(_state_phase_gap(state) + 0.25 * _state_k_deviation(state))


def _critical_anchor_state(*states: ContinuationState) -> ContinuationState:
    """Return the most critical-like traced state from a small candidate set."""
    return min(states, key=_critical_anchor_score)


def _build_pair_critical_candidate(
    bubble_state: ContinuationState,
    dew_state: ContinuationState,
    *,
    temperature_scale: float,
) -> CriticalJunction:
    """Build a critical candidate from one bubble/dew closest-approach pair."""
    anchor_state = _critical_anchor_state(bubble_state, dew_state)
    pressure_gap = abs(np.log(bubble_state.pressure / dew_state.pressure))
    temperature_gap = abs(bubble_state.temperature - dew_state.temperature) / max(temperature_scale, 1e-12)
    phase_gap = _pair_phase_gap(bubble_state, dew_state)
    k_deviation = max(_state_k_deviation(bubble_state), _state_k_deviation(dew_state))
    score = (
        pressure_gap
        + temperature_gap
        + phase_gap
        + 0.25 * k_deviation
    )

    return CriticalJunction(
        temperature=float(anchor_state.temperature),
        pressure=float(anchor_state.pressure),
        source="branch_closest_approach",
        score=float(score),
        phase_gap=float(phase_gap),
        k_deviation=float(k_deviation),
    )


def _nearest_state(
    states: Sequence[ContinuationState],
    *,
    temperature: float,
    pressure: float,
    temperature_scale: float,
) -> Optional[ContinuationState]:
    """Return the nearest continuation state to a trial critical marker."""
    if not states:
        return None
    return min(
        states,
        key=lambda state: (
            abs(state.temperature - float(temperature)) / max(temperature_scale, 1e-12)
            + abs(np.log(state.pressure / float(pressure)))
        ),
    )


def _trivial_endpoint_pressures(
    *,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
) -> List[float]:
    """Return de-duplicated trivial endpoint pressures from local root scans."""
    pressures: List[float] = []
    for bracket in scan_branch_roots(
        branch=branch,
        temperature=float(temperature),
        composition=np.asarray(composition, dtype=np.float64),
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
    ):
        if bracket.trivial_lo:
            pressures.append(_pressure_bar_to_pa(bracket.pressure_lo_bar))
        if bracket.trivial_hi:
            pressures.append(_pressure_bar_to_pa(bracket.pressure_hi_bar))

    unique: List[float] = []
    for pressure in sorted(pressures):
        if not unique or abs(np.log(pressure / unique[-1])) > 1e-3:
            unique.append(float(pressure))
    if not unique:
        return unique
    return [float(unique[-1])]


def _shared_trivial_endpoint_pressures(
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    n_pressure_points: int,
) -> List[float]:
    """Return shared high-pressure trivial endpoints exposed by both bubble and dew probes."""
    bubble_pressures = _trivial_endpoint_pressures(
        branch="bubble",
        temperature=float(temperature),
        composition=composition,
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
    )
    dew_pressures = _trivial_endpoint_pressures(
        branch="dew",
        temperature=float(temperature),
        composition=composition,
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
    )

    shared: List[float] = []
    for bubble_pressure in bubble_pressures:
        for dew_pressure in dew_pressures:
            if abs(np.log(bubble_pressure / dew_pressure)) <= 1e-3:
                shared.append(float(0.5 * (bubble_pressure + dew_pressure)))

    unique: List[float] = []
    for pressure in sorted(shared):
        if not unique or abs(np.log(pressure / unique[-1])) > 1e-6:
            unique.append(float(pressure))
    return unique


def _build_trivial_endpoint_candidate(
    *,
    branch: str,
    temperature: float,
    pressure: float,
    bubble_states: Sequence[ContinuationState],
    dew_states: Sequence[ContinuationState],
    temperature_scale: float,
) -> Optional[CriticalJunction]:
    """Promote a trivial ``K≈1`` endpoint into a critical-junction candidate."""
    bubble_neighbor = _nearest_state(
        bubble_states,
        temperature=float(temperature),
        pressure=float(pressure),
        temperature_scale=temperature_scale,
    )
    dew_neighbor = _nearest_state(
        dew_states,
        temperature=float(temperature),
        pressure=float(pressure),
        temperature_scale=temperature_scale,
    )

    if bubble_neighbor is None and dew_neighbor is None:
        return None
    if bubble_neighbor is None or dew_neighbor is None:
        return None

    max_neighbor_temperature_gap = max(
        abs(bubble_neighbor.temperature - float(temperature)),
        abs(dew_neighbor.temperature - float(temperature)),
    )
    if max_neighbor_temperature_gap > CRITICAL_TRIVIAL_MAX_NEIGHBOR_TEMP_GAP:
        return None

    neighbors = [bubble_neighbor, dew_neighbor]
    pressure_gap = float(
        np.mean([abs(np.log(state.pressure / float(pressure))) for state in neighbors])
    )
    temperature_gap = float(
        np.mean([
            abs(state.temperature - float(temperature)) / max(temperature_scale, 1e-12)
            for state in neighbors
        ])
    )
    phase_gap = max(_state_phase_gap(state) for state in neighbors)
    k_deviation = max(_state_k_deviation(state) for state in neighbors)
    score = (
        pressure_gap
        + temperature_gap
        + phase_gap
        + 0.25 * k_deviation
        + CRITICAL_TRIVIAL_ENDPOINT_PENALTY
    )
    anchor_state = _critical_anchor_state(*neighbors)

    return CriticalJunction(
        temperature=float(anchor_state.temperature),
        pressure=float(anchor_state.pressure),
        source=f"{branch}_trivial_endpoint",
        score=float(score),
        phase_gap=float(phase_gap),
        k_deviation=float(k_deviation),
    )


def _critical_probe_temperatures(trace: ContinuationTraceResult) -> List[float]:
    """Return trace temperatures worth probing for trivial critical markers.

    Seeded probe traces can begin exactly on the shared high-pressure trivial
    endpoint, so retain the first resolved state in addition to the tail and
    termination marker.
    """
    probes: List[float] = []
    if trace.states:
        probes.append(float(trace.states[0].temperature))
        probes.append(float(trace.states[-1].temperature))
    if trace.termination_temperature is not None:
        probes.append(float(trace.termination_temperature))

    unique: List[float] = []
    for value in probes:
        if not unique or all(abs(value - existing) > 1.0e-9 for existing in unique):
            unique.append(value)
    return unique


def _trim_trace_at_first_critical_collapse(
    trace: ContinuationTraceResult,
) -> ContinuationTraceResult:
    """Trim a probe trace once it first collapses into the critical neighborhood.

    The upward dew probe is only a locator for the handoff neighborhood. Once it
    reaches the first certified near-trivial state, any hotter continuation
    points are outside the physical envelope and should not participate in the
    returned dew branch or in later critical matching.
    """
    if not trace.states:
        return trace

    kept: List[ContinuationState] = []
    for state in trace.states:
        kept.append(state)
        if _candidate_collapses_to_critical_junction(state):
            return ContinuationTraceResult(
                branch=trace.branch,
                states=tuple(kept),
                termination_reason=trace.termination_reason,
                termination_temperature=trace.termination_temperature,
            )
    return trace


def detect_continuation_critical_junction(
    *,
    temperatures: Sequence[float],
    composition: NDArray[np.float64],
    eos: CubicEOS,
    bubble_trace: ContinuationTraceResult,
    dew_trace: ContinuationTraceResult,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    cancel_check: Optional[Callable[[], None]] = None,
) -> Optional[CriticalJunction]:
    """Estimate a critical junction from continuation traces and trivial endpoints."""
    temp_scale = _temperature_scale(temperatures)
    z = np.asarray(composition, dtype=np.float64)
    candidates: List[CriticalJunction] = []

    for bubble_state in bubble_trace.states:
        if cancel_check is not None:
            cancel_check()
        for dew_state in dew_trace.states:
            if abs(bubble_state.temperature - dew_state.temperature) > CRITICAL_PAIR_MAX_TEMP_GAP:
                continue
            if abs(np.log(bubble_state.pressure / dew_state.pressure)) > CRITICAL_PAIR_MAX_LOG_PRESSURE_GAP:
                continue
            candidates.append(
                _build_pair_critical_candidate(
                    bubble_state,
                    dew_state,
                    temperature_scale=temp_scale,
                )
            )

    branch_traces = {
        "bubble": bubble_trace,
        "dew": dew_trace,
    }
    shared_probe_temperatures = sorted(
        {
            *(_critical_probe_temperatures(bubble_trace)),
            *(_critical_probe_temperatures(dew_trace)),
        }
    )
    temperatures_with_shared: set[float] = set()
    for temperature in shared_probe_temperatures:
        if cancel_check is not None:
            cancel_check()
        shared_pressures = _shared_trivial_endpoint_pressures(
            temperature=float(temperature),
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
        )
        if not shared_pressures:
            continue
        temperatures_with_shared.add(float(temperature))
        for pressure in shared_pressures:
            candidate = _build_trivial_endpoint_candidate(
                branch="shared",
                temperature=float(temperature),
                pressure=float(pressure),
                bubble_states=bubble_trace.states,
                dew_states=dew_trace.states,
                temperature_scale=temp_scale,
            )
            if candidate is not None:
                candidates.append(candidate)

    for branch in ("bubble", "dew"):
        trivial_entries: List[tuple[float, List[float]]] = []
        for temperature in _critical_probe_temperatures(branch_traces[branch]):
            if cancel_check is not None:
                cancel_check()
            if float(temperature) in temperatures_with_shared:
                continue
            pressures = _trivial_endpoint_pressures(
                branch=branch,
                temperature=float(temperature),
                composition=z,
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
            )
            if pressures:
                trivial_entries.append((float(temperature), pressures))

        if not trivial_entries:
            continue

        for temperature, pressures in trivial_entries:
            for pressure in pressures:
                candidate = _build_trivial_endpoint_candidate(
                    branch=branch,
                    temperature=float(temperature),
                    pressure=float(pressure),
                    bubble_states=bubble_trace.states,
                    dew_states=dew_trace.states,
                    temperature_scale=temp_scale,
                )
                if candidate is not None:
                    candidates.append(candidate)

    if not candidates:
        return None

    best = min(candidates, key=lambda candidate: candidate.score)
    if best.score > CRITICAL_CANDIDATE_MAX_SCORE:
        return None
    return best


def _switch_is_continuous(critical_state: CriticalJunction, dew_state: ContinuationState) -> bool:
    """Return True when a dew restart is plausibly connected to the critical marker."""
    pressure_gap = abs(np.log(dew_state.pressure / critical_state.pressure))
    return (
        pressure_gap <= SWITCH_MAX_LOG_PRESSURE_GAP
        and _state_phase_gap(dew_state) <= SWITCH_MAX_PHASE_GAP
    )


def _merge_branch_states(*state_groups: Sequence[ContinuationState]) -> tuple[ContinuationState, ...]:
    """Merge branch-state groups into one temperature-ordered sequence without duplicates."""
    merged = sorted(
        [state for group in state_groups for state in group],
        key=lambda state: (state.temperature, state.pressure),
    )
    unique: List[ContinuationState] = []
    for state in merged:
        if not unique:
            unique.append(state)
            continue
        previous = unique[-1]
        same_temperature = abs(previous.temperature - state.temperature) <= 1.0e-9
        same_pressure = abs(np.log(previous.pressure / state.pressure)) <= 1.0e-6
        if same_temperature and same_pressure:
            continue
        if same_temperature and abs(np.log(previous.pressure / state.pressure)) <= SWITCH_MAX_LOG_PRESSURE_GAP:
            previous_gap = (_state_phase_gap(previous), _state_k_deviation(previous))
            current_gap = (_state_phase_gap(state), _state_k_deviation(state))
            if current_gap < previous_gap:
                unique[-1] = state
            continue
        unique.append(state)
    return tuple(unique)


def _adjacent_trace_state(
    states: Sequence[ContinuationState],
    seed_state: ContinuationState,
    *,
    toward_higher_temperature: bool,
) -> Optional[ContinuationState]:
    """Return the nearest neighboring state on the same trace side as the march direction."""
    ordered = sorted(states, key=lambda state: state.temperature)
    for state in ordered:
        if toward_higher_temperature and state.temperature > seed_state.temperature + 1.0e-12:
            return state
        if (not toward_higher_temperature) and state.temperature < seed_state.temperature - 1.0e-12:
            return state
    return None


def _trace_optional_branch_continuation(
    *,
    branch: BranchName,
    temperature_start: float,
    temperature_end: float,
    target_points: int,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    pressure_seed: Optional[float] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    max_phase_composition_jump: float = DEFAULT_MAX_PHASE_COMPOSITION_JUMP,
    max_k_value_jump: float = DEFAULT_MAX_K_VALUE_JUMP,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> ContinuationTraceResult:
    """Trace a branch only when the requested temperature span is non-degenerate."""
    if abs(float(temperature_start) - float(temperature_end)) <= 1.0e-12:
        return ContinuationTraceResult(branch=branch, states=tuple())

    return trace_branch_continuation_adaptive(
        branch=branch,
        temperature_start=float(temperature_start),
        temperature_end=float(temperature_end),
        target_points=target_points,
        composition=composition,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
        pressure_seed=pressure_seed,
        n_pressure_points=n_pressure_points,
        max_log_pressure_jump=max_log_pressure_jump,
        max_phase_composition_jump=max_phase_composition_jump,
        max_k_value_jump=max_k_value_jump,
        runtime_policy=runtime_policy,
        cancel_check=cancel_check,
    )


def trace_envelope_continuation(
    *,
    temperatures: Sequence[float],
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_pressure_points: int = DEFAULT_CONTINUATION_PRESSURE_POINTS,
    max_log_pressure_jump: float = DEFAULT_MAX_LOG_PRESSURE_JUMP,
    runtime_policy: Optional[ContinuationRuntimePolicy] = None,
    cancel_check: Optional[Callable[[], None]] = None,
) -> EnvelopeContinuationResult:
    """Trace a continuation envelope with adaptive stepping and explicit critical handling."""
    policy = _coerce_runtime_policy(runtime_policy)
    if len(temperatures) == 0:
        raise ValidationError(
            "temperatures cannot be empty",
            parameter="temperatures",
            value=[],
        )

    temps = [float(value) for value in temperatures]
    if any(not np.isfinite(value) or value <= 0.0 for value in temps):
        raise ValidationError(
            "temperatures must contain finite positive values",
            parameter="temperatures",
            value=temps,
        )

    temperature_min = min(temps)
    temperature_max = max(temps)
    target_points = max(len(temps), 24)
    z = np.asarray(composition, dtype=np.float64)

    bubble_trace = trace_branch_continuation_adaptive(
        branch="bubble",
        temperature_start=temperature_min,
        temperature_end=temperature_max,
        target_points=target_points,
        composition=z,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        max_log_pressure_jump=max_log_pressure_jump,
        runtime_policy=policy,
        cancel_check=cancel_check,
    )

    dew_boundary_trace = ContinuationTraceResult(branch="dew", states=tuple())

    dew_probe_trace = ContinuationTraceResult(branch="dew", states=tuple())
    if bubble_trace.states:
        dew_probe_temperature_end = _critical_probe_temperature_end(
            bubble_trace.states[-1].temperature,
            temperature_max,
            runtime_policy=policy,
        )
        dew_handoff_seed = _find_density_handoff_seed(
            branch="dew",
            reference_state=bubble_trace.states[-1],
            temperature_end=dew_probe_temperature_end,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            runtime_policy=policy,
            cancel_check=cancel_check,
        )
        if dew_handoff_seed is not None:
            # The density-selected handoff seed is already the near-critical dew
            # anchor we need for matching and for the downward dew march. Chasing
            # a hotter synthetic probe here only adds cost and can reintroduce a
            # nonphysical right tail before we trim it away.
            dew_probe_trace = ContinuationTraceResult(
                branch="dew",
                states=(dew_handoff_seed,),
            )
        else:
            dew_probe_trace = _trace_optional_branch_continuation(
                branch="dew",
                temperature_start=max(temperature_min, bubble_trace.states[-1].temperature),
                temperature_end=dew_probe_temperature_end,
                target_points=target_points,
                composition=z,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                pressure_seed=bubble_trace.states[-1].pressure,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                runtime_policy=policy,
                cancel_check=cancel_check,
            )
        dew_probe_trace = _trim_trace_at_first_critical_collapse(dew_probe_trace)

    critical_state = detect_continuation_critical_junction(
        temperatures=([state.temperature for state in bubble_trace.states] + [state.temperature for state in dew_probe_trace.states] + temps),
        composition=z,
        eos=eos,
        bubble_trace=bubble_trace,
        dew_trace=dew_probe_trace,
        binary_interaction=binary_interaction,
        n_pressure_points=n_pressure_points,
        cancel_check=cancel_check,
    )
    if critical_state is None:
        dew_boundary_trace = trace_branch_continuation_adaptive(
            branch="dew",
            temperature_start=temperature_min,
            temperature_end=temperature_max,
            target_points=target_points,
            composition=z,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            max_log_pressure_jump=max_log_pressure_jump,
            runtime_policy=policy,
            cancel_check=cancel_check,
        )
        critical_state = detect_continuation_critical_junction(
            temperatures=(
                [state.temperature for state in bubble_trace.states]
                + [state.temperature for state in dew_boundary_trace.states]
                + temps
            ),
            composition=z,
            eos=eos,
            bubble_trace=bubble_trace,
            dew_trace=dew_boundary_trace,
            binary_interaction=binary_interaction,
            n_pressure_points=n_pressure_points,
            cancel_check=cancel_check,
        )

    bubble_states = bubble_trace.states
    dew_states = dew_boundary_trace.states
    dew_termination_reason = dew_boundary_trace.termination_reason
    dew_termination_temperature = dew_boundary_trace.termination_temperature
    switched = critical_state is not None

    if critical_state is not None:
        if cancel_check is not None:
            cancel_check()
        bubble_states = tuple(
            state
            for state in bubble_trace.states
            if state.temperature <= critical_state.temperature + 1e-12
        )
        dew_upper_trace = dew_probe_trace
        dew_seed_state = _nearest_state(
            dew_probe_trace.states,
            temperature=float(critical_state.temperature),
            pressure=float(critical_state.pressure),
            temperature_scale=_temperature_scale(temps),
        )
        if dew_seed_state is not None:
            dew_seed_prior = _adjacent_trace_state(
                dew_probe_trace.states,
                dew_seed_state,
                toward_higher_temperature=True,
            )
            dew_lower_trace = trace_branch_continuation_adaptive_from_seed(
                dew_seed_state,
                temperature_end=temperature_min,
                target_points=target_points,
                composition=z,
                eos=eos,
                binary_interaction=binary_interaction,
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                prior_state=dew_seed_prior,
                density_march=True,
                runtime_policy=policy,
                cancel_check=cancel_check,
            )
        else:
            dew_lower_trace = _trace_optional_branch_continuation(
                branch="dew",
                temperature_start=float(critical_state.temperature),
                temperature_end=temperature_min,
                target_points=target_points,
                composition=z,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                pressure_seed=float(critical_state.pressure),
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                runtime_policy=policy,
                cancel_check=cancel_check,
            )
        if not dew_upper_trace.states:
            dew_upper_trace = _trace_optional_branch_continuation(
                branch="dew",
                temperature_start=float(critical_state.temperature),
                temperature_end=temperature_max,
                target_points=target_points,
                composition=z,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                pressure_seed=float(critical_state.pressure),
                n_pressure_points=n_pressure_points,
                max_log_pressure_jump=max_log_pressure_jump,
                runtime_policy=policy,
                cancel_check=cancel_check,
            )
            dew_upper_trace = _trim_trace_at_first_critical_collapse(dew_upper_trace)

        dew_segments: List[tuple[ContinuationState, ...]] = []
        for trace in (dew_lower_trace, dew_upper_trace):
            if cancel_check is not None:
                cancel_check()
            if not trace.states:
                continue
            nearest = _nearest_state(
                trace.states,
                temperature=float(critical_state.temperature),
                pressure=float(critical_state.pressure),
                temperature_scale=_temperature_scale(temps),
            )
            if nearest is None or not _switch_is_continuous(critical_state, nearest):
                continue
            dew_segments.append(trace.states)

        if dew_segments:
            dew_states = _merge_branch_states(*dew_segments)
            if dew_upper_trace.states:
                dew_termination_reason = dew_upper_trace.termination_reason
                dew_termination_temperature = dew_upper_trace.termination_temperature
            elif dew_lower_trace.states:
                dew_termination_reason = dew_lower_trace.termination_reason
                dew_termination_temperature = dew_lower_trace.termination_temperature
        elif dew_probe_trace.states:
            dew_states = dew_probe_trace.states
            dew_termination_reason = dew_probe_trace.termination_reason
            dew_termination_temperature = dew_probe_trace.termination_temperature
    else:
        switched = False

    if cancel_check is not None:
        cancel_check()

    return EnvelopeContinuationResult(
        bubble_states=tuple(bubble_states),
        dew_states=tuple(dew_states),
        critical_state=critical_state,
        switched=switched,
        bubble_termination_reason=bubble_trace.termination_reason,
        bubble_termination_temperature=bubble_trace.termination_temperature,
        dew_termination_reason=dew_termination_reason,
        dew_termination_temperature=dew_termination_temperature,
    )
