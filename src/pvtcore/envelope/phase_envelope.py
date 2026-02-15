"""Phase envelope calculation using continuation method.

The phase envelope shows the boundary between single-phase and two-phase regions
in pressure-temperature space for a given fluid composition.

The envelope consists of:
- Bubble point curve: Liquid boundary (left side)
- Dew point curve: Vapor boundary (right side)
- Critical point: Where bubble and dew curves meet (maximum T and P)

Reference:
Michelsen, M. L., "Calculation of Phase Envelopes and Critical Points for
Multicomponent Mixtures", Fluid Phase Equilibria, 4(1-2), 1-10 (1980).
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional, Tuple
from numpy.typing import NDArray

from ..models.component import Component
from ..eos.base import CubicEOS
from ..flash.bubble_point import calculate_bubble_point
from ..flash.dew_point import calculate_dew_point
from ..core.errors import ConvergenceError, ValidationError, PhaseError
from .critical_point import detect_critical_point


# Numerical parameters
DEFAULT_T_START: float = 150.0  # Starting temperature (K)
DEFAULT_T_STEP: float = 5.0  # Initial temperature step (K)
MIN_T_STEP: float = 0.5  # Minimum temperature step (K)
MAX_T_STEP: float = 20.0  # Maximum temperature step (K)
MAX_ENVELOPE_POINTS: int = 500  # Maximum points per curve
CRITICAL_POINT_TOLERANCE: float = 1e5  # Pressure tolerance for critical point (Pa)
CONVERGENCE_FAILURE_LIMIT: int = 10  # Max consecutive failures before stopping
T_SAFETY_FACTOR: float = 1.5  # Max temperature = max(Tc_i) * this factor


def _get_temperature_bound(
    composition: NDArray[np.float64],
    components: List[Component],
) -> float:
    """Get upper temperature bound based on component critical temperatures.

    The envelope cannot extend beyond the highest component critical temperature
    (with a safety margin). This prevents spurious extrapolation.
    """
    z = np.asarray(composition)
    # Consider only components with non-negligible mole fractions
    active_Tc = [comp.Tc for i, comp in enumerate(components) if z[i] > 1e-10]
    if not active_Tc:
        return 1000.0  # Default fallback
    return max(active_Tc) * T_SAFETY_FACTOR


@dataclass
class EnvelopeResult:
    """Results from phase envelope calculation."""
    bubble_T: NDArray[np.float64]
    bubble_P: NDArray[np.float64]
    dew_T: NDArray[np.float64]
    dew_P: NDArray[np.float64]
    critical_T: Optional[float]
    critical_P: Optional[float]
    composition: NDArray[np.float64]
    converged: bool
    n_bubble_points: int
    n_dew_points: int
    bubble_certificates: Optional[List["SolverCertificate"]] = None
    dew_certificates: Optional[List["SolverCertificate"]] = None


def calculate_phase_envelope(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    T_start: float = DEFAULT_T_START,
    T_step_initial: float = DEFAULT_T_STEP,
    max_points: int = MAX_ENVELOPE_POINTS,
    envelope_failure_mode: str = "raise",
    saturation_post_check_stability_flip: bool = False,
    saturation_post_check_action: str = "raise",
    saturation_post_check_rel_step: float = 0.01,
    detect_critical: bool = True
) -> EnvelopeResult:
    """Calculate phase envelope using continuation method."""
    # Validate inputs
    composition = np.asarray(composition, dtype=np.float64)

    if len(composition) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter='composition'
        )

    if not np.isclose(composition.sum(), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0, got {composition.sum():.6f}",
            parameter='composition'
        )

    if envelope_failure_mode not in {"raise", "partial"}:
        raise ValidationError(
            "envelope_failure_mode must be 'raise' or 'partial'",
            parameter="envelope_failure_mode",
            value=envelope_failure_mode,
        )
    if saturation_post_check_action not in {"raise", "warn"}:
        raise ValidationError(
            "saturation_post_check_action must be 'raise' or 'warn'",
            parameter="saturation_post_check_action",
            value=saturation_post_check_action,
        )
    if not (0.0 < float(saturation_post_check_rel_step) < 0.5):
        raise ValidationError(
            "saturation_post_check_rel_step must be in (0, 0.5)",
            parameter="saturation_post_check_rel_step",
            value=saturation_post_check_rel_step,
        )

    bubble_T, bubble_P, bubble_certificates = _trace_bubble_curve(
        composition, components, eos, binary_interaction,
        T_start, T_step_initial, max_points,
        envelope_failure_mode=envelope_failure_mode,
        post_check_stability_flip=saturation_post_check_stability_flip,
        post_check_action=saturation_post_check_action,
        post_check_rel_step=saturation_post_check_rel_step,
    )

    dew_T, dew_P, dew_certificates = _trace_dew_curve(
        composition, components, eos, binary_interaction,
        T_start, T_step_initial, max_points,
        envelope_failure_mode=envelope_failure_mode,
        post_check_stability_flip=saturation_post_check_stability_flip,
        post_check_action=saturation_post_check_action,
        post_check_rel_step=saturation_post_check_rel_step,
    )

    critical_T = None
    critical_P = None
    if detect_critical and (len(bubble_P) > 0 or len(dew_P) > 0):
        critical_T, critical_P = detect_critical_point(
            bubble_T, bubble_P, dew_T, dew_P,
            composition, components, eos, binary_interaction
        )

    converged = len(bubble_T) > 3 or len(dew_T) > 3

    return EnvelopeResult(
        bubble_T=bubble_T,
        bubble_P=bubble_P,
        dew_T=dew_T,
        dew_P=dew_P,
        critical_T=critical_T,
        critical_P=critical_P,
        composition=composition.copy(),
        converged=converged,
        n_bubble_points=len(bubble_T),
        n_dew_points=len(dew_T),
        bubble_certificates=bubble_certificates,
        dew_certificates=dew_certificates,
    )


def _trace_bubble_curve(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    T_start: float,
    T_step_initial: float,
    max_points: int,
    envelope_failure_mode: str,
    post_check_stability_flip: bool,
    post_check_action: str,
    post_check_rel_step: float,
) -> Tuple[NDArray[np.float64], NDArray[np.float64], List["SolverCertificate"]]:
    """Trace bubble point curve using continuation method."""
    T_list: List[float] = []
    P_list: List[float] = []
    certificates: List["SolverCertificate"] = []

    T = float(T_start)
    T_step = float(T_step_initial)
    P_prev: Optional[float] = None
    consecutive_failures = 0

    # Temperature upper bound based on component critical temperatures
    T_max = _get_temperature_bound(composition, components)

    # Track pressure trend to detect approach to critical point
    pressure_decreasing_count = 0

    for _ in range(max_points):
        # Check temperature bound
        if T > T_max:
            break

        try:
            result = calculate_bubble_point(
                T, composition, components, eos,
                pressure_initial=P_prev,
                binary_interaction=binary_interaction,
                check_stability=False,
                post_check_stability_flip=post_check_stability_flip,
                post_check_action=post_check_action,
                post_check_rel_step=post_check_rel_step,
            )

            T_list.append(float(T))
            P_list.append(float(result.pressure))
            certificates.append(result.certificate)

            # Check for pressure decreasing (approaching critical from bubble side)
            if len(P_list) >= 2:
                if P_list[-1] < P_list[-2]:
                    pressure_decreasing_count += 1
                    # Stop after several consecutive decreases past maximum
                    if pressure_decreasing_count >= 5:
                        break
                else:
                    pressure_decreasing_count = 0

            # Adaptive step sizing based on local slope
            if len(P_list) >= 2:
                dP_dT = abs(P_list[-1] - P_list[-2]) / max(T_step, 1e-12)

                if dP_dT > 1e5:
                    T_step = max(T_step * 0.7, MIN_T_STEP)
                elif dP_dT < 1e4:
                    T_step = min(T_step * 1.2, MAX_T_STEP)

            P_prev = float(result.pressure)
            T += T_step
            consecutive_failures = 0

        except PhaseError as e:
            # Normal termination: beyond cricondentherm (no saturation exists)
            if e.details.get("reason") == "no_saturation":
                break

            # Any other PhaseError indicates an unexpected state (e.g. inside envelope).
            if envelope_failure_mode == "raise":
                raise

            consecutive_failures += 1
            if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                break

            T_step = max(T_step * 0.5, MIN_T_STEP)
            T = (T_list[-1] + T_step) if T_list else (T + T_step)

        except (ConvergenceError, ValidationError) as e:
            if envelope_failure_mode == "raise":
                # Try adaptive step a few times; hard-fail if still not progressing.
                consecutive_failures += 1
                if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                    raise ConvergenceError(
                        "Phase envelope bubble curve failed to converge",
                        iterations=consecutive_failures,
                        temperature=float(T),
                        last_pressure=float(P_prev) if P_prev is not None else None,
                    ) from e

                T_step = max(T_step * 0.5, MIN_T_STEP)
                T = (T_list[-1] + T_step) if T_list else (T + T_step)
                continue

            # legacy partial-mode behavior
            consecutive_failures += 1
            if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                break
            T_step = max(T_step * 0.5, MIN_T_STEP)
            T = (T_list[-1] + T_step) if T_list else (T + T_step)

    return (
        np.array(T_list, dtype=np.float64),
        np.array(P_list, dtype=np.float64),
        certificates,
    )


def _find_first_dew_point(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    T_start: float,
    T_step_initial: float,
    post_check_stability_flip: bool,
    post_check_action: str,
    post_check_rel_step: float,
) -> Tuple[Optional[float], Optional[float], Optional["DewPointResult"]]:
    """Scan upward in temperature until a dew point exists; return (T, P)."""
    # Heuristic scan ceiling: high enough for light/heavy binaries in unit tests,
    # but still bounded to avoid infinite searching.
    Tc_max = max(float(c.Tc) for (c, zi) in zip(components, composition) if float(zi) > 0.0)
    T_scan_max = max(float(T_start), 2.0 * Tc_max)

    dT = max(5.0, float(T_step_initial))
    # Hard cap scan steps so we don't burn runtime on pathological inputs.
    max_scan_steps = int(min(250, max(1, (T_scan_max - float(T_start)) / dT + 1)))

    T = float(T_start)
    for _ in range(max_scan_steps):
        try:
            res = calculate_dew_point(
                T, composition, components, eos,
                pressure_initial=None,
                binary_interaction=binary_interaction,
                check_stability=False,
                post_check_stability_flip=post_check_stability_flip,
                post_check_action=post_check_action,
                post_check_rel_step=post_check_rel_step,
            )
            return float(T), float(res.pressure), res
        except PhaseError as e:
            if e.details.get("reason") != "no_saturation":
                # Unexpected: dew calculation indicates we are already inside the envelope or other issue
                raise
            T += dT

        except (ConvergenceError, ValidationError):
            T += dT

    return None, None, None


def _trace_dew_curve(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    T_start: float,
    T_step_initial: float,
    max_points: int,
    envelope_failure_mode: str,
    post_check_stability_flip: bool,
    post_check_action: str,
    post_check_rel_step: float,
) -> Tuple[NDArray[np.float64], NDArray[np.float64], List["SolverCertificate"]]:
    """Trace dew point curve using continuation method."""
    T_list: List[float] = []
    P_list: List[float] = []
    certificates: List["SolverCertificate"] = []

    # Temperature upper bound based on component critical temperatures
    T_max = _get_temperature_bound(composition, components)

    # NEW: find a temperature where dew actually exists, instead of assuming T_start works.
    T0, P0, res0 = _find_first_dew_point(
        composition, components, eos, binary_interaction,
        T_start=T_start, T_step_initial=T_step_initial,
        post_check_stability_flip=post_check_stability_flip,
        post_check_action=post_check_action,
        post_check_rel_step=post_check_rel_step,
    )
    if T0 is None or P0 is None or res0 is None:
        return np.array([], dtype=np.float64), np.array([], dtype=np.float64), []

    T = float(T0)
    T_step = float(T_step_initial)
    P_prev: Optional[float] = float(P0)
    consecutive_failures = 0

    # Track pressure trend to detect approach to critical point
    pressure_decreasing_count = 0

    # Seed with the first successful point
    T_list.append(float(T))
    P_list.append(float(P0))
    certificates.append(res0.certificate)
    T += T_step

    for _ in range(max_points - 1):
        # Check temperature bound
        if T > T_max:
            break

        try:
            result = calculate_dew_point(
                T, composition, components, eos,
                pressure_initial=P_prev,
                binary_interaction=binary_interaction,
                check_stability=False,
                post_check_stability_flip=post_check_stability_flip,
                post_check_action=post_check_action,
                post_check_rel_step=post_check_rel_step,
            )

            T_list.append(float(T))
            P_list.append(float(result.pressure))
            certificates.append(result.certificate)

            # Check for pressure decreasing (approaching critical from dew side)
            if len(P_list) >= 2:
                if P_list[-1] < P_list[-2]:
                    pressure_decreasing_count += 1
                    # Stop after several consecutive decreases past maximum
                    if pressure_decreasing_count >= 5:
                        break
                else:
                    pressure_decreasing_count = 0

            if len(P_list) >= 2:
                dP_dT = abs(P_list[-1] - P_list[-2]) / max(T_step, 1e-12)
                if dP_dT > 1e5:
                    T_step = max(T_step * 0.7, MIN_T_STEP)
                elif dP_dT < 1e4:
                    T_step = min(T_step * 1.2, MAX_T_STEP)

            P_prev = float(result.pressure)
            T += T_step
            consecutive_failures = 0

        except PhaseError as e:
            if e.details.get("reason") == "no_saturation":
                break
            if envelope_failure_mode == "raise":
                raise

            consecutive_failures += 1
            if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                break
            T_step = max(T_step * 0.5, MIN_T_STEP)
            T = (T_list[-1] + T_step) if T_list else (T + T_step)

        except (ConvergenceError, ValidationError) as e:
            if envelope_failure_mode == "raise":
                consecutive_failures += 1
                if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                    raise ConvergenceError(
                        "Phase envelope dew curve failed to converge",
                        iterations=consecutive_failures,
                        temperature=float(T),
                        last_pressure=float(P_prev) if P_prev is not None else None,
                    ) from e

                T_step = max(T_step * 0.5, MIN_T_STEP)
                T = (T_list[-1] + T_step) if T_list else (T + T_step)
                continue

            consecutive_failures += 1
            if consecutive_failures >= CONVERGENCE_FAILURE_LIMIT:
                break
            T_step = max(T_step * 0.5, MIN_T_STEP)
            T = (T_list[-1] + T_step) if T_list else (T + T_step)

    return (
        np.array(T_list, dtype=np.float64),
        np.array(P_list, dtype=np.float64),
        certificates,
    )


def _locate_critical_point(
    bubble_T: NDArray[np.float64],
    bubble_P: NDArray[np.float64],
    dew_T: NDArray[np.float64],
    dew_P: NDArray[np.float64]
) -> Tuple[Optional[float], Optional[float]]:
    """Locate critical point from bubble and dew curves.

    Numerically, we look in the overlap range where both curves are defined,
    find candidate temperatures where |Pb(T) - Pd(T)| <= tolerance, and choose
    the *highest temperature* such candidate (top of the two-phase boundary).
    """
    if len(bubble_P) == 0 or len(dew_P) == 0:
        return None, None

    T_min = max(float(np.min(bubble_T)), float(np.min(dew_T)))
    T_max = min(float(np.max(bubble_T)), float(np.max(dew_T)))
    if T_max <= T_min:
        return None, None

    b_sort = np.argsort(bubble_T)
    d_sort = np.argsort(dew_T)
    Tb = bubble_T[b_sort]
    Pb = bubble_P[b_sort]
    Td = dew_T[d_sort]
    Pd = dew_P[d_sort]

    mask = (Tb >= T_min) & (Tb <= T_max)
    if not np.any(mask):
        return None, None

    Tcand = Tb[mask]
    Pb_cand = Pb[mask]
    Pd_interp = np.interp(Tcand, Td, Pd)

    dP = np.abs(Pb_cand - Pd_interp)

    ok = dP <= CRITICAL_POINT_TOLERANCE
    if not np.any(ok):
        return None, None

    # Choose the highest-temperature meeting point (avoids spurious low-T intersections)
    Tc_ok = Tcand[ok]
    idx_local = int(np.argmax(Tc_ok))
    Tcrit = float(Tc_ok[idx_local])

    # Map back to full arrays to get the corresponding pressures
    # (find the index in Tcand nearest to Tcrit, which is exact from Tcand subset)
    j = int(np.where(Tcand == Tcrit)[0][0])
    Pcrit = float(0.5 * (Pb_cand[j] + Pd_interp[j]))
    return Tcrit, Pcrit


def estimate_cricondentherm(
    envelope: EnvelopeResult
) -> Tuple[Optional[float], Optional[float]]:
    """Estimate cricondentherm (maximum temperature on envelope)."""
    if len(envelope.dew_T) == 0:
        return None, None

    idx_max_T = int(np.argmax(envelope.dew_T))
    T_max = float(envelope.dew_T[idx_max_T])
    P_at_max_T = float(envelope.dew_P[idx_max_T])
    return T_max, P_at_max_T


def estimate_cricondenbar(
    envelope: EnvelopeResult
) -> Tuple[Optional[float], Optional[float]]:
    """Estimate cricondenbar (maximum pressure on envelope)."""
    all_P = np.concatenate([envelope.bubble_P, envelope.dew_P])
    all_T = np.concatenate([envelope.bubble_T, envelope.dew_T])

    if len(all_P) == 0:
        return None, None

    idx_max_P = int(np.argmax(all_P))
    P_max = float(all_P[idx_max_P])
    T_at_max_P = float(all_T[idx_max_P])
    return T_at_max_P, P_max
