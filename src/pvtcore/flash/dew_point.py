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

from ..core.errors import ValidationError, PhaseError, ConvergenceStatus, IterationHistory
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


def _tpd_class(tpd: float, tol: float) -> int:
    """Classify TPD robustly with tolerance: -1 (neg), 0 (near zero), +1 (pos)."""
    if tpd > tol:
        return 1
    if tpd < -tol:
        return -1
    return 0


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

    # If the initial guess is already on the stability boundary (|TPD| <= tol),
    # accept it directly.
    #
    # Without this, a near-zero TPD at P0 can prevent *both* bracketing
    # expansions from running (since neither "definitely stable" nor
    # "definitely unstable" is detected), leading to P_lo == P_hi and a
    # spurious "failed to form a pressure interval" error.
    if _tpd_class(float(f0), tolerance) == 0:
        P_star = float(P0)
        iterations = 0

        tpd_star, x = _tpd_liquid_trial(P_star, temperature, z, eos, binary_interaction)
        x = x / x.sum()

        eps = 1e-300
        K = z / np.maximum(x, eps)

        # Optional diagnostic check: ensure stability flips across P*.
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

            # For a dew point boundary (vapor feed): below stable, above unstable.
            bad = (c_below == -1) or (c_above == 1)
            if bad:
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

        return _finalize(DewPointResult(
            status=ConvergenceStatus.CONVERGED,
            pressure=float(P_star),
            temperature=float(temperature),
            vapor_composition=z.copy(),
            liquid_composition=x.astype(np.float64),
            K_values=K.astype(np.float64),
            iterations=int(iterations),
            residual=float(abs(tpd_star)),
            stable_vapor=bool(f0 >= -tolerance),
            history=IterationHistory(),  # Early convergence - minimal history
        ))

    P_lo, f_lo = P0, f0
    P_hi, f_hi = P0, f0
    iterations = 0
    history = IterationHistory()
    bracketing_exhausted = False

    # Expand downward until stable (f >= 0)
    while _tpd_class(f_lo, tolerance) == -1 and P_lo > PRESSURE_MIN:
        P_lo = max(P_lo / 1.6, PRESSURE_MIN)
        f_lo, _ = _tpd_liquid_trial(P_lo, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_lo))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # Expand upward until unstable (f < 0)
    while _tpd_class(f_hi, tolerance) == 1 and P_hi < PRESSURE_MAX:
        P_hi = min(P_hi * 1.6, PRESSURE_MAX)
        f_hi, _ = _tpd_liquid_trial(P_hi, temperature, z, eos, binary_interaction)
        iterations += 1
        history.record_iteration(residual=abs(f_hi))
        if iterations > max_iterations // 2:
            bracketing_exhausted = True
            break

    # If bracketing exhausted max_iterations, return MAX_ITERS status
    if bracketing_exhausted and P_lo == P_hi:
        return _finalize(DewPointResult(
            status=ConvergenceStatus.MAX_ITERS,
            pressure=float(P0),
            temperature=float(temperature),
            vapor_composition=z.copy(),
            liquid_composition=np.zeros_like(z),
            K_values=np.ones_like(z),
            iterations=int(iterations),
            residual=float(abs(f0)),
            stable_vapor=bool(f0 >= -tolerance),
            history=history,
        ))

    if P_lo == P_hi:
        raise PhaseError(
            "No dew point exists at this temperature (failed to form a pressure interval).",
            phase="vapor",
            pressure=P0,
            temperature=temperature,
            reason="no_saturation",
        )

    c_lo = _tpd_class(f_lo, tolerance)
    c_hi = _tpd_class(f_hi, tolerance)

    if c_lo == 0:
        P_star = P_lo
        brent_iters = 0
    elif c_hi == 0:
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

        P_star, brent_iters = brent_method(
            _tpd_liquid_trial_scalar,
            P_lo,
            P_hi,
            args=(temperature, z, eos, binary_interaction),
            tol=tolerance,
            max_iter=max(20, max_iterations - iterations),
        )

    iterations += brent_iters

    tpd_star, x = _tpd_liquid_trial(P_star, temperature, z, eos, binary_interaction)
    x = x / x.sum()

    eps = 1e-300
    K = z / np.maximum(x, eps)  # K = y/x, y=z at dew

    # POST-CHECK (optional): verify the stability metric flips sign across P*.
    # For a real dew point at fixed T, the vapor feed should be:
    #   - stable at pressures slightly BELOW Pd
    #   - unstable at pressures slightly ABOVE Pd
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

        # For a dew point boundary (vapor feed):
        #   below P*: stable vapor => TPD >= 0
        #   above P*: unstable     => TPD < 0
        bad = (c_below == -1) or (c_above == 1)
        if bad:
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

    # Record final residual in history
    history.record_iteration(residual=abs(tpd_star))

    return _finalize(DewPointResult(
        status=ConvergenceStatus.CONVERGED,
        pressure=float(P_star),
        temperature=float(temperature),
        vapor_composition=z.copy(),
        liquid_composition=x.astype(np.float64),
        K_values=K.astype(np.float64),
        iterations=int(iterations),
        residual=float(abs(tpd_star)),
        stable_vapor=bool(f0 >= -tolerance),
        history=history,
    ))


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
