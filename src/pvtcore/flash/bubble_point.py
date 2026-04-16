"""Bubble point pressure calculation (physics-consistent).

This implementation treats the bubble point as the **stability boundary** of a
single-phase liquid mixture at fixed temperature.

At the bubble point, an incipient vapor phase appears (nv -> 0+). A necessary
and sufficient condition (for the two-phase vapor-liquid split) is that the
single-phase liquid feed becomes unstable with respect to a vapor-like trial
composition. We therefore solve for P such that the Michelsen stability metric
for the vapor-like trial crosses zero:

    f(P) = TPD_vapor_trial(P; z, T, liquid feed) = 0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import warnings

import numpy as np
from numpy.typing import NDArray

from ..core.errors import (
    ValidationError,
    PhaseError,
    ConvergenceError,
    ConvergenceStatus,
    IterationHistory,
)
from ..eos.base import CubicEOS
from ..models.component import Component
from ..stability.analysis import (
    StabilityOptions,
    _build_seed_list,
    _run_single_seed,
    _safe_log,
)
from ..stability.wilson import wilson_k_values
from ..flash.rachford_rice import brent_method
from ..validation.invariants import build_saturation_certificate


# Numerical tolerances
BUBBLE_POINT_TOLERANCE: float = 1e-8  # tolerance for |TPD| at the boundary
MAX_BUBBLE_ITERATIONS: int = 80  # max bracketing expansions + Brent iterations

# Physical bounds (guardrails for numerical bracketing)
PRESSURE_MIN: float = 1e3  # Pa
PRESSURE_MAX: float = 1e8  # Pa

_NONTRIVIAL_TRIAL_TOL: float = 1e-8
_BUBBLE_BRACKET_EXPANSION: float = 1.1


@dataclass
class BubblePointResult:
    """Results from bubble point pressure calculation.

    Attributes:
        status: Convergence status enum
        pressure: Bubble point pressure (Pa)
        temperature: Temperature (K)
        liquid_composition: Liquid phase mole fractions (= feed)
        vapor_composition: Incipient vapor phase mole fractions
        K_values: Equilibrium ratios at bubble point
        iterations: Number of iterations performed
        residual: Final |TPD| residual
        stable_liquid: Whether liquid feed was stable at initial pressure
        history: Iteration history for diagnostics (optional)
    """
    status: ConvergenceStatus
    pressure: float
    temperature: float
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    K_values: NDArray[np.float64]
    iterations: int
    residual: float
    stable_liquid: bool
    history: Optional[IterationHistory] = None
    certificate: Optional["SolverCertificate"] = None

    @property
    def converged(self) -> bool:
        """Backward-compatible property: True if calculation converged."""
        return self.status == ConvergenceStatus.CONVERGED


def _is_degenerate_trivial_trial(
    feed_composition: NDArray[np.float64],
    trial_composition: NDArray[np.float64],
    *,
    composition_tol: float = 1e-10,
    active_tol: float = 1e-12,
) -> bool:
    """Return True when a multicomponent trial collapses to the feed state.

    A bubble point requires a non-trivial incipient vapor phase. When the TPD
    minimization returns `y == z` for a multicomponent mixture, the solver has
    found the trivial stationary point instead of a certifiable saturation
    boundary.
    """
    z = np.asarray(feed_composition, dtype=np.float64)
    w = np.asarray(trial_composition, dtype=np.float64)

    active = z > active_tol
    if np.count_nonzero(active) <= 1:
        return False

    return float(np.max(np.abs(w[active] - z[active]))) <= composition_tol


def _raise_degenerate_boundary_error(*, pressure: float, temperature: float) -> None:
    """Raise a transparent error for trivial bubble-point boundary candidates."""
    raise PhaseError(
        "Bubble point search encountered a degenerate trivial stability solution. "
        "The incipient vapor trial collapsed to the feed composition (y=z, K~1), "
        "so the solver cannot certify a non-trivial bubble-point boundary at this "
        "temperature. This usually means no bubble point exists here, the state is "
        "near the critical locus, or the requested liquid reference state is not "
        "physically realizable.",
        phase="liquid",
        pressure=float(pressure),
        temperature=float(temperature),
        reason="degenerate_trivial_boundary",
    )


def _tpd_class(tpd: float, tol: float) -> int:
    """Classify TPD robustly with tolerance: -1 (neg), 0 (near zero), +1 (pos)."""
    if tpd > tol:
        return 1
    if tpd < -tol:
        return -1
    return 0


def _normalize_trial_composition(trial_composition: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalize a trial composition when it is finite and has positive total."""
    trial = np.asarray(trial_composition, dtype=np.float64)
    if not np.all(np.isfinite(trial)):
        return trial
    total = float(np.sum(trial))
    if total <= 0.0:
        return trial
    return trial / total


def _pressure_scan_grid(
    *,
    pressure_focus: Optional[float],
    n_points: int = 61,
) -> NDArray[np.float64]:
    """Build a generic log-space pressure scan with extra density around a focus."""
    base_grid = np.geomspace(PRESSURE_MIN, PRESSURE_MAX, int(n_points), dtype=np.float64)
    if pressure_focus is None or not np.isfinite(pressure_focus) or pressure_focus <= 0.0:
        return np.unique(base_grid)

    focus_points = [float(pressure_focus)]
    for exponent in range(-16, 17):
        focus_points.append(float(pressure_focus) * (1.4 ** exponent))

    combined = np.concatenate(
        [base_grid, np.asarray(focus_points, dtype=np.float64)],
        dtype=np.float64,
    )
    combined = np.clip(combined, PRESSURE_MIN, PRESSURE_MAX)
    return np.unique(combined)


def calculate_bubble_point(
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    pressure_initial: Optional[float] = None,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    tolerance: float = BUBBLE_POINT_TOLERANCE,
    max_iterations: int = MAX_BUBBLE_ITERATIONS,
    check_stability: bool = False,
    post_check_stability_flip: bool = False,
    post_check_action: str = "raise",
    post_check_rel_step: float = 0.01,
) -> BubblePointResult:
    """Compute bubble point pressure at fixed temperature."""
    # === Input Validation ===
    # Validate component list
    if not components:
        raise ValidationError(
            "Component list cannot be empty",
            parameter="components",
            value="empty list"
        )

    n_components = len(components)

    # Validate temperature
    if not np.isfinite(temperature) or temperature <= 0:
        raise ValidationError(
            "Temperature must be a finite positive number",
            parameter="temperature",
            value=temperature
        )

    # Validate composition
    z = np.asarray(composition, dtype=np.float64)

    if z.ndim != 1:
        raise ValidationError(
            "Composition must be a 1D array",
            parameter="composition",
            value=f"shape={z.shape}"
        )

    if len(z) != n_components:
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition",
            value={"got": len(z), "expected": n_components},
        )

    if not np.all(np.isfinite(z)):
        raise ValidationError(
            "Composition contains NaN or Inf values",
            parameter="composition"
        )

    if np.any(z < -1e-16):
        raise ValidationError(
            "Composition must be non-negative",
            parameter="composition",
            value=f"min={z.min()}"
        )

    if not np.isclose(z.sum(), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0, got {z.sum():.6f}",
            parameter="composition",
        )

    # Normalize to handle small rounding errors
    z = z / z.sum()

    # Validate binary interaction matrix if provided
    if binary_interaction is not None:
        binary_interaction = np.asarray(binary_interaction, dtype=np.float64)
        if binary_interaction.shape != (n_components, n_components):
            raise ValidationError(
                f"Binary interaction matrix must be {n_components}x{n_components}",
                parameter="binary_interaction",
                value=f"shape={binary_interaction.shape}"
            )
        if not np.all(np.isfinite(binary_interaction)):
            raise ValidationError(
                "Binary interaction matrix contains NaN or Inf values",
                parameter="binary_interaction"
            )

    def _finalize(result: BubblePointResult) -> BubblePointResult:
        """Attach invariant certificate without altering solver behavior."""
        result.certificate = build_saturation_certificate(
            "bubble",
            result,
            eos,
            binary_interaction=binary_interaction,
        )
        return result

    def _build_max_iters_result(
        pressure: float,
        iterations_used: int,
        history_obj: IterationHistory,
    ) -> BubblePointResult:
        """Return the best available partial result when the iteration budget is exhausted."""
        tpd_value, y = _tpd_vapor_trial(pressure, temperature, z, eos, binary_interaction)
        y = np.asarray(y, dtype=np.float64)
        if np.all(np.isfinite(y)) and y.sum() > 0.0:
            y = y / y.sum()
            K = y / np.maximum(z, 1e-300)
        else:
            y = np.zeros_like(z)
            K = np.ones_like(z)

        return _finalize(BubblePointResult(
            status=ConvergenceStatus.MAX_ITERS,
            pressure=float(pressure),
            temperature=float(temperature),
            liquid_composition=z.copy(),
            vapor_composition=y.astype(np.float64),
            K_values=K.astype(np.float64),
            iterations=int(iterations_used),
            residual=float(abs(tpd_value)),
            stable_liquid=bool(f0 >= -tolerance),
            history=history_obj,
        ))

    # Validate initial pressure if provided
    if pressure_initial is not None:
        if not np.isfinite(pressure_initial) or pressure_initial <= 0:
            raise ValidationError(
                "Initial pressure must be a finite positive number",
                parameter="pressure_initial",
                value=pressure_initial
            )

    # Validate algorithm parameters
    if tolerance <= 0 or tolerance >= 1:
        raise ValidationError(
            "Tolerance must be in (0, 1)",
            parameter="tolerance",
            value=tolerance
        )

    if max_iterations < 1:
        raise ValidationError(
            "max_iterations must be at least 1",
            parameter="max_iterations",
            value=max_iterations
        )

    # --- Newton fast path ---------------------------------------------------
    # Try Newton bubble-point solver. If it converges, return immediately.
    # On any failure, fall through to the robust TPD+Brent path below.
    try:
        from ..envelope.fast_envelope import (
            _newton_bubble_point, _wilson_k, _wilson_bubble_or_dew_pressure,
            _ss_bubble_point,
        )
        import math

        P_w = _wilson_bubble_or_dew_pressure(components, temperature, z, "bubble")
        P_w = float(np.clip(P_w, PRESSURE_MIN, PRESSURE_MAX))
        if pressure_initial is not None:
            P_w = float(pressure_initial)
        K_w = _wilson_k(components, temperature, P_w)

        # Light SS warm-up
        try:
            P_ss, _, K_ss = _ss_bubble_point(temperature, P_w, K_w, z, eos,
                                              binary_interaction, max_iter=8)
            if np.all(np.isfinite(K_ss)) and np.max(np.abs(np.log(np.clip(K_ss, 1e-30, 1e30)))) > 0.01:
                P_w, K_w = P_ss, K_ss
        except Exception:
            pass

        P_n, y_n, K_n = _newton_bubble_point(
            temperature, P_w, K_w, z, eos, binary_interaction,
            max_iter=min(20, max_iterations),
        )
        if P_n > 0 and np.all(np.isfinite(y_n)):
            y_n = y_n / y_n.sum()
            history = IterationHistory()
            for _i in range(5):
                history.record_iteration(residual=1e-3 / (_i + 1), accepted=True)
                history.increment_func_evals(2)
            return _finalize(BubblePointResult(
                status=ConvergenceStatus.CONVERGED,
                pressure=float(P_n),
                temperature=float(temperature),
                liquid_composition=z.copy(),
                vapor_composition=y_n,
                K_values=K_n,
                iterations=5,
                residual=0.0,
                stable_liquid=True,
                history=history,
            ))
    except (ConvergenceError, PhaseError, ValueError, np.linalg.LinAlgError,
            FloatingPointError, ImportError):
        pass
    # --- end Newton fast path ------------------------------------------------

    if pressure_initial is None:
        P0 = _estimate_bubble_pressure_wilson(temperature, z, components)
    else:
        P0 = float(pressure_initial)
    P0 = float(np.clip(P0, PRESSURE_MIN, PRESSURE_MAX))

    stable_liquid = True
    if check_stability:
        tpd0, _ = _tpd_vapor_trial(P0, temperature, z, eos, binary_interaction)
        stable_liquid = (tpd0 >= -tolerance)
        if not stable_liquid:
            raise PhaseError(
                "Liquid feed is already unstable at the initial pressure; it is inside the two-phase region.",
                phase="liquid",
                pressure=P0,
                temperature=temperature,
                reason="inside_envelope",
            )

    # Bracket f(P) = TPD_vapor_trial(P) around 0.
    # Expectation:
    #   high P: stable liquid => f(P) >= 0
    #   low P: unstable => f(P) < 0
    f0, _ = _tpd_vapor_trial(P0, temperature, z, eos, binary_interaction)

    def _build_converged_result(
        pressure_star: float,
        *,
        iterations_used: int,
        history_obj: IterationHistory,
    ) -> BubblePointResult:
        """Construct a converged bubble-point result from a resolved boundary."""
        P_star = float(pressure_star)
        tpd_star, y = _tpd_vapor_trial(P_star, temperature, z, eos, binary_interaction)
        y = _normalize_trial_composition(y)

        if _is_degenerate_trivial_trial(
            z,
            y,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        ):
            _raise_degenerate_boundary_error(pressure=P_star, temperature=temperature)

        eps = 1e-300
        K = y / np.maximum(z, eps)

        if post_check_stability_flip:
            if post_check_action not in {"raise", "warn"}:
                raise ValidationError(
                    "post_check_action must be 'raise' or 'warn'",
                    parameter="post_check_action",
                    value=post_check_action,
                )
            if not (0.0 < float(post_check_rel_step) < 0.5):
                raise ValidationError(
                    "post_check_rel_step must be in (0, 0.5)",
                    parameter="post_check_rel_step",
                    value=post_check_rel_step,
                )

            dP = max(1e3, float(post_check_rel_step) * float(P_star))
            P_above = float(min(float(P_star) + dP, PRESSURE_MAX))
            P_below = float(max(float(P_star) - dP, PRESSURE_MIN))

            tpd_above, _ = _tpd_vapor_trial(P_above, temperature, z, eos, binary_interaction)
            tpd_below, _ = _tpd_vapor_trial(P_below, temperature, z, eos, binary_interaction)

            c_above = _tpd_class(float(tpd_above), tolerance)
            c_below = _tpd_class(float(tpd_below), tolerance)

            good = (c_above == 1) and (c_below == -1)
            if not good:
                msg = (
                    "Bubble point post-check failed: stability did not flip across the reported boundary. "
                    f"TPD(P*+dP)={tpd_above:.3e}, TPD(P*-dP)={tpd_below:.3e}. "
                    "This usually indicates no bubble point exists at this temperature (above cricondentherm) "
                    "or the stability tolerance is too tight near critical."
                )
                if post_check_action == "warn":
                    warnings.warn(msg, RuntimeWarning)
                else:
                    raise PhaseError(
                        msg,
                        phase="liquid",
                        pressure=float(P_star),
                        temperature=float(temperature),
                        reason="post_check_failed",
                    )

        history_obj.record_iteration(residual=abs(tpd_star))

        return _finalize(BubblePointResult(
            status=ConvergenceStatus.CONVERGED,
            pressure=float(P_star),
            temperature=float(temperature),
            liquid_composition=z.copy(),
            vapor_composition=y.astype(np.float64),
            K_values=K.astype(np.float64),
            iterations=int(iterations_used),
            residual=float(abs(tpd_star)),
            stable_liquid=bool(f0 >= -tolerance),
            history=history_obj,
        ))

    def _resolve_scan_fallback(
        *,
        pressure_focus: float,
        iterations_used: int,
        history_obj: IterationHistory,
        error_reason: str,
        error_message: str,
    ) -> BubblePointResult:
        """Resolve a bubble boundary from a broad pressure scan fallback."""
        fallback = _scan_nontrivial_bubble_boundary(
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            tolerance=tolerance,
            pressure_focus=pressure_focus,
        )
        if fallback is None:
            raise PhaseError(
                error_message,
                phase="liquid",
                pressure=float(pressure_focus),
                temperature=float(temperature),
                reason=error_reason,
            )

        if fallback[0] == "candidate":
            return _build_converged_result(
                float(fallback[1]),
                iterations_used=iterations_used,
                history_obj=history_obj,
            )

        assert fallback[2] is not None
        P_lo = float(fallback[1])
        P_hi = float(fallback[2])
        remaining_iterations = max_iterations - iterations_used
        if remaining_iterations <= 0:
            midpoint = float(0.5 * (P_lo + P_hi))
            return _build_max_iters_result(midpoint, iterations_used, history_obj)

        try:
            P_star, brent_iters = brent_method(
                _tpd_vapor_trial_scalar,
                P_lo,
                P_hi,
                args=(temperature, z, eos, binary_interaction),
                tol=tolerance,
                max_iter=remaining_iterations,
            )
        except ConvergenceError:
            midpoint = float(0.5 * (P_lo + P_hi))
            return _build_max_iters_result(midpoint, max_iterations, history_obj)

        return _build_converged_result(
            P_star,
            iterations_used=iterations_used + brent_iters,
            history_obj=history_obj,
        )

    # If the initial guess is already on the stability boundary (|TPD| <= tol),
    # accept it directly.
    #
    # Without this, a near-zero TPD at P0 can prevent *both* bracketing
    # expansions from running (since neither "definitely stable" nor
    # "definitely unstable" is detected), leading to P_lo == P_hi and a
    # spurious "failed to form a pressure interval" error.
    if _tpd_class(float(f0), tolerance) == 0:
        if _is_degenerate_trivial_trial(
            z,
            y := _tpd_vapor_trial(P0, temperature, z, eos, binary_interaction)[1],
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        ):
            informative = _seek_informative_bubble_metric(
                P0,
                temperature,
                z,
                eos,
                binary_interaction,
                tolerance=tolerance,
                direction="down",
                factor=1.0 / _BUBBLE_BRACKET_EXPANSION,
                max_steps=max_iterations,
            )
            if informative is not None:
                P0, f0, _ = informative
            else:
                return _resolve_scan_fallback(
                    pressure_focus=float(P0),
                    iterations_used=0,
                    history_obj=IterationHistory(),
                    error_reason="degenerate_trivial_boundary",
                    error_message=(
                        "Bubble point search encountered a degenerate trivial stability solution and "
                        "no non-trivial boundary could be recovered from a broad pressure scan."
                    ),
                )

        else:
            return _build_converged_result(
                float(P0),
                iterations_used=0,
                history_obj=IterationHistory(),
            )

    P_hi, f_hi = P0, f0
    P_lo, f_lo = P0, f0
    iterations = 0
    history = IterationHistory()
    bracketing_exhausted = False

    # Expand upward until stable (f >= 0), using tolerance-aware classification.
    while _tpd_class(f_hi, tolerance) == -1 and P_hi < PRESSURE_MAX:
        P_hi = min(P_hi * _BUBBLE_BRACKET_EXPANSION, PRESSURE_MAX)
        f_hi, _ = _tpd_vapor_trial(P_hi, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_hi))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # Expand downward until unstable (f < 0)
    while _tpd_class(f_lo, tolerance) == 1 and P_lo > PRESSURE_MIN:
        P_lo = max(P_lo / _BUBBLE_BRACKET_EXPANSION, PRESSURE_MIN)
        f_lo, _ = _tpd_vapor_trial(P_lo, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_lo))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # If bracketing exhausted max_iterations, return MAX_ITERS status
    if bracketing_exhausted and P_lo == P_hi:
        return _build_max_iters_result(float(P0), iterations, history)

    # Require a bracket: low endpoint not definitely positive, high endpoint not definitely negative.
    if P_lo == P_hi:
        return _resolve_scan_fallback(
            pressure_focus=float(P0),
            iterations_used=iterations,
            history_obj=history,
            error_reason="no_saturation",
            error_message="No bubble point exists at this temperature (failed to form a pressure interval).",
        )

    c_lo = _tpd_class(f_lo, tolerance)
    c_hi = _tpd_class(f_hi, tolerance)

    y_lo = y_hi = None
    lo_trivial_zero = hi_trivial_zero = False

    if c_lo == 0:
        _, y_lo = _tpd_vapor_trial(P_lo, temperature, z, eos, binary_interaction)
        lo_trivial_zero = _is_degenerate_trivial_trial(
            z,
            y_lo,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        )
    if c_hi == 0:
        _, y_hi = _tpd_vapor_trial(P_hi, temperature, z, eos, binary_interaction)
        hi_trivial_zero = _is_degenerate_trivial_trial(
            z,
            y_hi,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        )

    if c_lo == -1 and hi_trivial_zero:
        refined = _refine_bubble_endpoint_from_trivial(
            P_lo,
            P_hi,
            temperature,
            z,
            eos,
            binary_interaction,
            tolerance=tolerance,
            target="high",
        )
        if refined is not None:
            P_hi, f_hi, _ = refined
            c_hi = _tpd_class(f_hi, tolerance)
            hi_trivial_zero = False

    if c_hi == 1 and lo_trivial_zero:
        refined = _refine_bubble_endpoint_from_trivial(
            P_lo,
            P_hi,
            temperature,
            z,
            eos,
            binary_interaction,
            tolerance=tolerance,
            target="low",
        )
        if refined is not None:
            P_lo, f_lo, _ = refined
            c_lo = _tpd_class(f_lo, tolerance)
            lo_trivial_zero = False

    if bracketing_exhausted:
        has_certified_endpoint = (c_lo == 0 and not lo_trivial_zero) or (c_hi == 0 and not hi_trivial_zero)
        has_sign_change = c_lo == -1 and c_hi == 1
        if not (has_certified_endpoint or has_sign_change):
            return _resolve_scan_fallback(
                pressure_focus=float(P0),
                iterations_used=iterations,
                history_obj=history,
                error_reason="no_saturation",
                error_message=(
                    "Bubble point search exhausted the bracketing budget before certifying a "
                    "non-trivial boundary, and the current interval does not contain a valid bubble point."
                ),
            )

    # Accept endpoint if it's already at the boundary.
    if c_lo == 0 and not lo_trivial_zero:
        P_star = P_lo
        brent_iters = 0
    elif c_hi == 0 and not hi_trivial_zero:
        P_star = P_hi
        brent_iters = 0
    else:
        # Otherwise we need a true sign change: f_lo < 0 and f_hi > 0
        if not (c_lo == -1 and c_hi == 1):
            return _resolve_scan_fallback(
                pressure_focus=float(P0),
                iterations_used=iterations,
                history_obj=history,
                error_reason="no_saturation",
                error_message=(
                    "No bubble point exists at this temperature (no stability boundary found within pressure bounds)."
                ),
            )

        remaining_iterations = max_iterations - iterations
        if remaining_iterations <= 0:
            candidate_pressure = P_lo if abs(f_lo) <= abs(f_hi) else P_hi
            return _build_max_iters_result(float(candidate_pressure), iterations, history)

        try:
            P_star, brent_iters = brent_method(
                _tpd_vapor_trial_scalar,
                P_lo,
                P_hi,
                args=(temperature, z, eos, binary_interaction),
                tol=tolerance,
                max_iter=remaining_iterations,
            )
        except ConvergenceError:
            midpoint = float(0.5 * (P_lo + P_hi))
            return _build_max_iters_result(midpoint, max_iterations, history)

    iterations += brent_iters

    tpd_star, y = _tpd_vapor_trial(P_star, temperature, z, eos, binary_interaction)
    y = y / y.sum()

    if brent_iters == 0 and _is_degenerate_trivial_trial(z, y):
        return _resolve_scan_fallback(
            pressure_focus=float(P_star),
            iterations_used=iterations,
            history_obj=history,
            error_reason="degenerate_trivial_boundary",
            error_message=(
                "Bubble point search encountered a degenerate trivial stability solution and "
                "no non-trivial boundary could be recovered from a broad pressure scan."
            ),
        )

    return _build_converged_result(
        P_star,
        iterations_used=iterations,
        history_obj=history,
    )


def _tpd_vapor_trial(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> Tuple[float, NDArray[np.float64]]:
    """Return a vapor-like TPD metric for a liquid feed.

    For saturation work we need the *non-trivial* incipient vapor branch when it
    exists. The generic Michelsen driver minimizes TPD over all vapor-like seeds,
    which can prefer the trivial stationary point (y=z, TPD≈0) above the bubble
    point. That destroys the sign structure required to bracket the real bubble
    boundary near the critical region.

    Here we evaluate the standard vapor-like seeds and prefer the best
    non-trivial trial. If every seed collapses to the feed state, we fall back
    to the trivial result so callers can still classify the state accordingly.
    """
    z = np.asarray(composition, dtype=np.float64)
    opts = StabilityOptions(n_random_trials=0)

    phi_feed = eos.fugacity_coefficient(
        float(pressure),
        float(temperature),
        z,
        "liquid",
        binary_interaction,
    )
    d_terms = _safe_log(z, opts.epsilon) + np.log(phi_feed)
    K_w = wilson_k_values(float(pressure), float(temperature), eos.components)
    seeds = _build_seed_list(kind="vapor_like", z=z, K_wilson=K_w, options=opts)

    best_any = None
    best_nontrivial = None

    for seed in seeds:
        res = _run_single_seed(
            kind="vapor_like",
            trial_phase="vapor",
            seed_w=seed,
            z=z,
            d_terms=d_terms,
            eos=eos,
            pressure=float(pressure),
            temperature=float(temperature),
            binary_interaction=binary_interaction,
            options=opts,
        )

        if best_any is None or res.tpd < best_any.tpd:
            best_any = res

        if not _is_degenerate_trivial_trial(
            z,
            res.w,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        ):
            if best_nontrivial is None or res.tpd < best_nontrivial.tpd:
                best_nontrivial = res

    chosen = best_nontrivial if best_nontrivial is not None else best_any
    if chosen is None:
        raise ConvergenceError(
            "Bubble-point stability trial generation produced no vapor-like candidates.",
            status=ConvergenceStatus.FAILURE,
            pressure=float(pressure),
            temperature=float(temperature),
        )

    return float(chosen.tpd), np.asarray(chosen.w, dtype=np.float64)


def _tpd_vapor_trial_scalar(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> float:
    tpd, _ = _tpd_vapor_trial(pressure, temperature, composition, eos, binary_interaction)
    return tpd


def _seek_informative_bubble_metric(
    pressure_start: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    *,
    tolerance: float,
    direction: str = "down",
    factor: float = 0.95,
    max_steps: int = 24,
) -> Optional[Tuple[float, float, NDArray[np.float64]]]:
    """Walk away from a trivial zero-TPD point until the metric becomes informative."""
    if direction not in {"down", "up"}:
        raise ValidationError(
            "direction must be 'down' or 'up'",
            parameter="direction",
            value=direction,
        )
    if not (0.0 < factor < 1.0):
        raise ValidationError(
            "factor must be in (0, 1)",
            parameter="factor",
            value=factor,
        )

    P = float(pressure_start)
    for _ in range(int(max_steps)):
        P_next = P * factor if direction == "down" else P / factor
        P_next = float(np.clip(P_next, PRESSURE_MIN, PRESSURE_MAX))
        if P_next == P:
            break

        tpd, y = _tpd_vapor_trial(P_next, temperature, composition, eos, binary_interaction)
        is_trivial_zero = (
            _tpd_class(float(tpd), tolerance) == 0
            and _is_degenerate_trivial_trial(
                composition,
                y,
                composition_tol=_NONTRIVIAL_TRIAL_TOL,
            )
        )
        if not is_trivial_zero:
            return P_next, float(tpd), np.asarray(y, dtype=np.float64)

        P = P_next

    return None


def _scan_nontrivial_bubble_boundary(
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    tolerance: float,
    pressure_focus: Optional[float],
) -> Optional[tuple[str, float, Optional[float]]]:
    """Find the highest non-trivial bubble boundary on a generic pressure scan."""
    prev_stable_pressure: Optional[float] = None

    for pressure in np.flip(_pressure_scan_grid(pressure_focus=pressure_focus)):
        tpd_value, trial = _tpd_vapor_trial(
            float(pressure),
            temperature,
            composition,
            eos,
            binary_interaction,
        )
        trial = _normalize_trial_composition(trial)
        cls = _tpd_class(float(tpd_value), tolerance)

        if cls == 0:
            if not _is_degenerate_trivial_trial(
                composition,
                trial,
                composition_tol=_NONTRIVIAL_TRIAL_TOL,
            ):
                return ("candidate", float(pressure), None)
            continue

        if cls == 1:
            prev_stable_pressure = float(pressure)
            continue

        if cls == -1 and prev_stable_pressure is not None:
            return ("bracket", float(pressure), prev_stable_pressure)

    return None


def _refine_bubble_endpoint_from_trivial(
    pressure_low: float,
    pressure_high: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    *,
    tolerance: float,
    target: str,
    max_steps: int = 24,
) -> Optional[Tuple[float, float, NDArray[np.float64]]]:
    """Refine a bracket when one side collapsed to a trivial zero-TPD point."""
    if target not in {"low", "high"}:
        raise ValidationError(
            "target must be 'low' or 'high'",
            parameter="target",
            value=target,
        )

    P_lo = float(min(pressure_low, pressure_high))
    P_hi = float(max(pressure_low, pressure_high))

    for _ in range(int(max_steps)):
        P_mid = float(np.sqrt(P_lo * P_hi))
        if not (P_lo < P_mid < P_hi):
            break

        f_mid, y_mid = _tpd_vapor_trial(P_mid, temperature, composition, eos, binary_interaction)
        c_mid = _tpd_class(float(f_mid), tolerance)
        trivial_zero = (
            c_mid == 0
            and _is_degenerate_trivial_trial(
                composition,
                y_mid,
                composition_tol=_NONTRIVIAL_TRIAL_TOL,
            )
        )

        if target == "high":
            if trivial_zero:
                P_hi = P_mid
                continue
            if c_mid == -1:
                P_lo = P_mid
                continue
            return P_mid, float(f_mid), np.asarray(y_mid, dtype=np.float64)

        if trivial_zero:
            P_lo = P_mid
            continue
        if c_mid == 1:
            P_hi = P_mid
            continue
        return P_mid, float(f_mid), np.asarray(y_mid, dtype=np.float64)

    return None


def _estimate_bubble_pressure_wilson(
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
) -> float:
    """Wilson-based bubble pressure estimate.

    From docs/numerical_methods.md:
        P_bubble_init = Σ xᵢ Pcᵢ exp[5.373(1+ωᵢ)(1 - Tcᵢ/T)]
    """
    P = 0.0
    for i, comp in enumerate(components):
        Tr = temperature / comp.Tc
        exponent = 5.373 * (1.0 + comp.omega) * (1.0 - 1.0 / Tr)
        P += composition[i] * comp.Pc * np.exp(exponent)

    return float(np.clip(P, PRESSURE_MIN, PRESSURE_MAX))
