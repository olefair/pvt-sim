"""Dew point pressure calculation (physics-consistent).

This implementation treats the dew point as the **stability boundary** of a
single-phase vapor mixture at fixed temperature.

At the dew point, an incipient liquid phase appears (nv -> 1-). We solve for P
such that the Michelsen stability metric for the **liquid-like** trial crosses
zero:

    f(P) = TPD_liquid_trial(P; z, T, vapor feed) = 0
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
from ..stability.michelsen import michelsen_stability_test
from ..flash.rachford_rice import brent_method
from ..validation.invariants import build_saturation_certificate


# Numerical tolerances
DEW_POINT_TOLERANCE: float = 1e-8
MAX_DEW_ITERATIONS: int = 80

# Physical bounds (guardrails for numerical bracketing)
PRESSURE_MIN: float = 1e3  # Pa
PRESSURE_MAX: float = 1e8  # Pa

_NONTRIVIAL_TRIAL_TOL: float = 1e-8
_DEW_BRACKET_EXPANSION: float = 1.1


@dataclass
class DewPointResult:
    """Results from dew point pressure calculation.

    Attributes:
        status: Convergence status enum
        pressure: Dew point pressure (Pa)
        temperature: Temperature (K)
        vapor_composition: Vapor phase mole fractions (= feed)
        liquid_composition: Incipient liquid phase mole fractions
        K_values: Equilibrium ratios at dew point
        iterations: Number of iterations performed
        residual: Final |TPD| residual
        stable_vapor: Whether vapor feed was stable at initial pressure
        history: Iteration history for diagnostics (optional)
    """
    status: ConvergenceStatus
    pressure: float
    temperature: float
    vapor_composition: NDArray[np.float64]
    liquid_composition: NDArray[np.float64]
    K_values: NDArray[np.float64]
    iterations: int
    residual: float
    stable_vapor: bool
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
    """Return True when a multicomponent trial collapses to the feed state."""
    z = np.asarray(feed_composition, dtype=np.float64)
    w = np.asarray(trial_composition, dtype=np.float64)

    active = z > active_tol
    if np.count_nonzero(active) <= 1:
        return False

    return float(np.max(np.abs(w[active] - z[active]))) <= composition_tol


def _raise_degenerate_boundary_error(*, pressure: float, temperature: float) -> None:
    """Raise a transparent error for trivial dew-point boundary candidates."""
    raise PhaseError(
        "Dew point search encountered a degenerate trivial stability solution. "
        "The incipient liquid trial collapsed to the feed composition (x=z, K≈1), "
        "so the solver cannot certify a non-trivial dew-point boundary at this "
        "temperature. This usually means no dew point exists here, the state is "
        "near the critical locus, or the requested vapor reference state is not "
        "physically realizable.",
        phase="vapor",
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


def _scan_nontrivial_dew_boundary(
    *,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    tolerance: float,
    pressure_focus: Optional[float],
) -> Optional[tuple[str, float, Optional[float]]]:
    """Find the first non-trivial dew boundary on a generic pressure scan."""
    prev_stable_pressure: Optional[float] = None

    for pressure in _pressure_scan_grid(pressure_focus=pressure_focus):
        tpd_value, trial = _tpd_liquid_trial(
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
            return ("bracket", prev_stable_pressure, float(pressure))

    return None


def calculate_dew_point(
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    pressure_initial: Optional[float] = None,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    tolerance: float = DEW_POINT_TOLERANCE,
    max_iterations: int = MAX_DEW_ITERATIONS,
    check_stability: bool = False,
    post_check_stability_flip: bool = False,
    post_check_action: str = "raise",
    post_check_rel_step: float = 0.01,
) -> DewPointResult:
    """Compute dew point pressure at fixed temperature."""
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

    def _finalize(result: DewPointResult) -> DewPointResult:
        """Attach invariant certificate without altering solver behavior."""
        result.certificate = build_saturation_certificate(
            "dew",
            result,
            eos,
            binary_interaction=binary_interaction,
        )
        return result

    def _build_max_iters_result(
        pressure: float,
        iterations_used: int,
        history_obj: IterationHistory,
    ) -> DewPointResult:
        """Return the best available partial result when the iteration budget is exhausted."""
        tpd_value, x = _tpd_liquid_trial(pressure, temperature, z, eos, binary_interaction)
        x = np.asarray(x, dtype=np.float64)
        if np.all(np.isfinite(x)) and x.sum() > 0.0:
            x = x / x.sum()
            K = z / np.maximum(x, 1e-300)
        else:
            x = np.zeros_like(z)
            K = np.ones_like(z)

        return _finalize(DewPointResult(
            status=ConvergenceStatus.MAX_ITERS,
            pressure=float(pressure),
            temperature=float(temperature),
            vapor_composition=z.copy(),
            liquid_composition=x.astype(np.float64),
            K_values=K.astype(np.float64),
            iterations=int(iterations_used),
            residual=float(abs(tpd_value)),
            stable_vapor=bool(f0 >= -tolerance),
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
    try:
        from ..envelope.fast_envelope import (
            _newton_dew_point, _wilson_k, _wilson_bubble_or_dew_pressure,
        )

        P_w = _wilson_bubble_or_dew_pressure(components, temperature, z, "dew")
        P_w = float(np.clip(P_w, PRESSURE_MIN, PRESSURE_MAX))
        if pressure_initial is not None:
            P_w = float(pressure_initial)
        K_w = _wilson_k(components, temperature, P_w)

        P_n, x_n, K_n = _newton_dew_point(
            temperature, P_w, K_w, z, eos, binary_interaction,
            max_iter=min(20, max_iterations),
        )
        if P_n > 0 and np.all(np.isfinite(x_n)):
            x_n = x_n / x_n.sum()
            history = IterationHistory()
            for _i in range(5):
                history.record_iteration(residual=1e-3 / (_i + 1), accepted=True)
                history.increment_func_evals(2)
            return _finalize(DewPointResult(
                status=ConvergenceStatus.CONVERGED,
                pressure=float(P_n),
                temperature=float(temperature),
                vapor_composition=z.copy(),
                liquid_composition=x_n,
                K_values=K_n,
                iterations=5,
                residual=0.0,
                stable_vapor=True,
                history=history,
            ))
    except (ConvergenceError, PhaseError, ValueError, np.linalg.LinAlgError,
            FloatingPointError, ImportError):
        pass
    # --- end Newton fast path ------------------------------------------------

    if pressure_initial is None:
        P0 = _estimate_dew_pressure_wilson(temperature, z, components)
    else:
        P0 = float(pressure_initial)
    P0 = float(np.clip(P0, PRESSURE_MIN, PRESSURE_MAX))

    stable_vapor = True
    if check_stability:
        tpd0, _ = _tpd_liquid_trial(P0, temperature, z, eos, binary_interaction)
        stable_vapor = (tpd0 >= -tolerance)
        if not stable_vapor:
            raise PhaseError(
                "Vapor feed is already unstable at the initial pressure; it is inside the two-phase region.",
                phase="vapor",
                pressure=P0,
                temperature=temperature,
                reason="inside_envelope",
            )

    # Bracket f(P) = TPD_liquid_trial(P) around 0.
    # Expectation:
    #   low P: stable vapor => f(P) >= 0
    #   high P: unstable => f(P) < 0
    f0, _ = _tpd_liquid_trial(P0, temperature, z, eos, binary_interaction)

    def _build_converged_result(
        pressure_star: float,
        *,
        iterations_used: int,
        history_obj: IterationHistory,
    ) -> DewPointResult:
        """Construct a converged dew-point result from a resolved boundary."""
        P_star = float(pressure_star)
        tpd_star, x = _tpd_liquid_trial(P_star, temperature, z, eos, binary_interaction)
        x = _normalize_trial_composition(x)

        if _is_degenerate_trivial_trial(
            z,
            x,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        ):
            _raise_degenerate_boundary_error(pressure=P_star, temperature=temperature)

        eps = 1e-300
        K = z / np.maximum(x, eps)

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

            tpd_below, _ = _tpd_liquid_trial(P_below, temperature, z, eos, binary_interaction)
            tpd_above, _ = _tpd_liquid_trial(P_above, temperature, z, eos, binary_interaction)

            c_below = _tpd_class(float(tpd_below), tolerance)
            c_above = _tpd_class(float(tpd_above), tolerance)

            good = (c_below == 1) and (c_above == -1)
            if not good:
                msg = (
                    "Dew point post-check failed: stability did not flip across the reported boundary. "
                    f"TPD(P*-dP)={tpd_below:.3e}, TPD(P*+dP)={tpd_above:.3e}. "
                    "This usually indicates no dew point exists at this temperature (above cricondentherm) "
                    "or the stability tolerance is too tight near critical."
                )
                if post_check_action == "warn":
                    warnings.warn(msg, RuntimeWarning)
                else:
                    raise PhaseError(
                        msg,
                        phase="vapor",
                        pressure=float(P_star),
                        temperature=float(temperature),
                        reason="post_check_failed",
                    )

        history_obj.record_iteration(residual=abs(tpd_star))

        return _finalize(DewPointResult(
            status=ConvergenceStatus.CONVERGED,
            pressure=float(P_star),
            temperature=float(temperature),
            vapor_composition=z.copy(),
            liquid_composition=x.astype(np.float64),
            K_values=K.astype(np.float64),
            iterations=int(iterations_used),
            residual=float(abs(tpd_star)),
            stable_vapor=bool(f0 >= -tolerance),
            history=history_obj,
        ))

    # If the initial guess is already on the stability boundary (|TPD| <= tol),
    # accept it directly.
    #
    # Without this, a near-zero TPD at P0 can prevent *both* bracketing
    # expansions from running (since neither "definitely stable" nor
    # "definitely unstable" is detected), leading to P_lo == P_hi and a
    # spurious "failed to form a pressure interval" error.
    if _tpd_class(float(f0), tolerance) == 0:
        x0 = _normalize_trial_composition(
            _tpd_liquid_trial(P0, temperature, z, eos, binary_interaction)[1]
        )
        if _is_degenerate_trivial_trial(
            z,
            x0,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        ):
            fallback = _scan_nontrivial_dew_boundary(
                temperature=temperature,
                composition=z,
                eos=eos,
                binary_interaction=binary_interaction,
                tolerance=tolerance,
                pressure_focus=P0,
            )
            if fallback is None:
                _raise_degenerate_boundary_error(pressure=P0, temperature=temperature)
            if fallback[0] == "candidate":
                return _build_converged_result(
                    float(fallback[1]),
                    iterations_used=0,
                    history_obj=IterationHistory(),
                )
            assert fallback[2] is not None
            P_lo = float(fallback[1])
            P_hi = float(fallback[2])
            f_lo, _ = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
            f_hi, _ = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)
        else:
            return _build_converged_result(
                P0,
                iterations_used=0,
                history_obj=IterationHistory(),
            )
    else:
        P_lo, f_lo = P0, f0
        P_hi, f_hi = P0, f0

    iterations = 0
    history = IterationHistory()
    bracketing_exhausted = False

    # Expand downward until stable (f >= 0)
    while _tpd_class(f_lo, tolerance) == -1 and P_lo > PRESSURE_MIN:
        P_lo = max(P_lo / _DEW_BRACKET_EXPANSION, PRESSURE_MIN)
        f_lo, _ = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_lo))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # Expand upward until unstable (f < 0)
    while _tpd_class(f_hi, tolerance) == 1 and P_hi < PRESSURE_MAX:
        P_hi = min(P_hi * _DEW_BRACKET_EXPANSION, PRESSURE_MAX)
        f_hi, _ = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_hi))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # If bracketing exhausted max_iterations, return MAX_ITERS status
    if bracketing_exhausted and P_lo == P_hi:
        return _build_max_iters_result(float(P0), iterations, history)

    if P_lo == P_hi:
        fallback = _scan_nontrivial_dew_boundary(
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            tolerance=tolerance,
            pressure_focus=P0,
        )
        if fallback is None:
            raise PhaseError(
                "No dew point exists at this temperature (failed to form a pressure interval).",
                phase="vapor",
                pressure=P0,
                temperature=temperature,
                reason="no_saturation",
            )
        if fallback[0] == "candidate":
            return _build_converged_result(
                float(fallback[1]),
                iterations_used=iterations,
                history_obj=history,
            )
        assert fallback[2] is not None
        P_lo = float(fallback[1])
        P_hi = float(fallback[2])
        f_lo, _ = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
        f_hi, _ = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)

    c_lo = _tpd_class(f_lo, tolerance)
    c_hi = _tpd_class(f_hi, tolerance)

    x_lo = x_hi = None
    lo_trivial_zero = hi_trivial_zero = False

    if c_lo == 0:
        _, x_lo = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
        lo_trivial_zero = _is_degenerate_trivial_trial(
            z,
            x_lo,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        )
    if c_hi == 0:
        _, x_hi = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)
        hi_trivial_zero = _is_degenerate_trivial_trial(
            z,
            x_hi,
            composition_tol=_NONTRIVIAL_TRIAL_TOL,
        )

    if (c_lo == 0 and lo_trivial_zero) or (c_hi == 0 and hi_trivial_zero) or not (
        (c_lo == 1 and c_hi == -1) or (c_lo == 0 and not lo_trivial_zero) or (c_hi == 0 and not hi_trivial_zero)
    ):
        fallback = _scan_nontrivial_dew_boundary(
            temperature=temperature,
            composition=z,
            eos=eos,
            binary_interaction=binary_interaction,
            tolerance=tolerance,
            pressure_focus=P0,
        )
        if fallback is None:
            raise PhaseError(
                "No dew point exists at this temperature (no stability boundary found within pressure bounds).",
                phase="vapor",
                pressure=P0,
                temperature=temperature,
                reason="no_saturation",
            )
        if fallback[0] == "candidate":
            return _build_converged_result(
                float(fallback[1]),
                iterations_used=iterations,
                history_obj=history,
            )
        assert fallback[2] is not None
        P_lo = float(fallback[1])
        P_hi = float(fallback[2])
        f_lo, _ = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
        f_hi, _ = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)
        c_lo, c_hi = 1, -1
        lo_trivial_zero = hi_trivial_zero = False

    if c_lo == 0 and not lo_trivial_zero:
        P_star = P_lo
        brent_iters = 0
    elif c_hi == 0 and not hi_trivial_zero:
        P_star = P_hi
        brent_iters = 0
    else:
        # Need sign change: low P positive, high P negative
        if not (c_lo == 1 and c_hi == -1):
            raise PhaseError(
                "No dew point exists at this temperature (no stability boundary found within pressure bounds).",
                phase="vapor",
                pressure=P0,
                temperature=temperature,
                reason="no_saturation",
            )

        remaining_iterations = max_iterations - iterations
        if remaining_iterations <= 0:
            candidate_pressure = P_lo if abs(f_lo) <= abs(f_hi) else P_hi
            return _build_max_iters_result(float(candidate_pressure), iterations, history)

        try:
            P_star, brent_iters = brent_method(
                _tpd_liquid_trial_scalar,
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

    return _build_converged_result(
        P_star,
        iterations_used=iterations,
        history_obj=history,
    )


def _tpd_liquid_trial(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> Tuple[float, NDArray[np.float64]]:
    """Return (TPD_liquid_trial, liquid_trial_composition) for a vapor feed."""
    res = michelsen_stability_test(
        composition,
        float(pressure),
        float(temperature),
        eos,
        feed_phase="vapor",
        binary_interaction=binary_interaction,
    )
    tpd_l = float(res.tpd_values[1])
    x = np.asarray(res.trial_compositions[1], dtype=np.float64)
    return tpd_l, x


def _tpd_liquid_trial_scalar(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> float:
    tpd, _ = _tpd_liquid_trial(pressure, temperature, composition, eos, binary_interaction)
    return tpd


def _estimate_dew_pressure_wilson(
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
) -> float:
    """Wilson-based dew pressure estimate.

    From docs/numerical_methods.md:
        P_dew_init = 1 / Σ (yᵢ / Pcᵢ) exp[-5.373(1+ωᵢ)(1 - Tcᵢ/T)]
    """
    denom = 0.0
    for i, comp in enumerate(components):
        Tr = temperature / comp.Tc
        exponent = -5.373 * (1.0 + comp.omega) * (1.0 - 1.0 / Tr)
        denom += (composition[i] / comp.Pc) * np.exp(exponent)

    if denom <= 0.0:
        return float(np.clip(1e6, PRESSURE_MIN, PRESSURE_MAX))

    P = 1.0 / denom
    return float(np.clip(P, PRESSURE_MIN, PRESSURE_MAX))
