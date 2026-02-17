"""Fixed-grid phase envelope tracing (pvtapp-facing API).

This module provides a deterministic, range-constrained trace suitable for UI/workflow usage.
It is intentionally separate from the continuation-method implementation in `phase_envelope.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.bubble_point import PRESSURE_MAX as _P_MAX, PRESSURE_MIN as _P_MIN, calculate_bubble_point
from ..flash.dew_point import calculate_dew_point
from ..models.component import Component
from .critical_point import detect_critical_point


@dataclass
class TracedEnvelopeResult:
    """Fixed-grid trace result expected by the application layer."""

    bubble_T: NDArray[np.float64]
    bubble_P: NDArray[np.float64]
    dew_T: NDArray[np.float64]
    dew_P: NDArray[np.float64]
    critical_point: Optional[Tuple[float, float]]
    cricondenbar: Optional[Tuple[float, float]]
    cricondentherm: Optional[Tuple[float, float]]


def trace_phase_envelope(
    *,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    T_min: float,
    T_max: float,
    n_points: int = 50,
    binary_interaction: Optional[NDArray[np.float64]] = None,
) -> TracedEnvelopeResult:
    """Trace bubble/dew curves on a fixed temperature grid.

    Raises
    ------
    RuntimeError
        When no saturation points exist in the requested range, or when only one
        branch is found (bubble or dew), since the application workflow expects both.
    """
    z = np.asarray(composition, dtype=np.float64)
    if z.ndim != 1:
        raise ValidationError("Composition must be 1D.", parameter="composition", value=f"shape={z.shape}")
    if len(z) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition",
            value={"got": len(z), "expected": len(components)},
        )
    if not np.isclose(float(z.sum()), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0, got {float(z.sum()):.6f}",
            parameter="composition",
        )
    if n_points < 2:
        raise ValidationError("n_points must be >= 2", parameter="n_points", value=n_points)
    if not (np.isfinite(T_min) and np.isfinite(T_max) and T_min > 0.0 and T_max > 0.0 and T_max > T_min):
        raise ValidationError(
            "Temperature range must be finite, positive, and satisfy T_max > T_min.",
            parameter="temperature_range",
            value={"T_min": T_min, "T_max": T_max},
        )

    T_grid = np.linspace(float(T_min), float(T_max), int(n_points), dtype=np.float64)

    bubble_T_list: List[float] = []
    bubble_P_list: List[float] = []
    dew_T_list: List[float] = []
    dew_P_list: List[float] = []

    P_bubble_prev: Optional[float] = None
    P_dew_prev: Optional[float] = None

    for T in T_grid:
        try:
            br = calculate_bubble_point(
                float(T),
                z,
                components,
                eos,
                pressure_initial=P_bubble_prev,
                binary_interaction=binary_interaction,
                check_stability=False,
            )
            # Reject non-converged or bound-clamped results; these indicate no saturation within the search bounds.
            if not getattr(br, 'converged', True):
                raise PhaseError(
                    "No bubble point exists at this temperature (solver did not converge within bounds).",
                    phase="liquid",
                    pressure=float(getattr(br, 'pressure', float('nan'))),
                    temperature=float(T),
                    reason="no_saturation",
                )
            if float(br.pressure) >= float(_P_MAX) * 0.999 or float(br.pressure) <= float(_P_MIN) * 1.001:
                raise PhaseError(
                    "No bubble point exists at this temperature (pressure bounds reached).",
                    phase="liquid",
                    pressure=float(br.pressure),
                    temperature=float(T),
                    reason="no_saturation",
                )
            bubble_T_list.append(float(T))
            bubble_P_list.append(float(br.pressure))
            P_bubble_prev = float(br.pressure)
        except PhaseError as e:
            if e.details.get("reason") != "no_saturation":
                raise
        except (ConvergenceError, ValidationError):
            pass

        try:
            dr = calculate_dew_point(
                float(T),
                z,
                components,
                eos,
                pressure_initial=P_dew_prev,
                binary_interaction=binary_interaction,
                check_stability=False,
            )
            # Reject non-converged or bound-clamped results; these indicate no saturation within the search bounds.
            if not getattr(dr, 'converged', True):
                raise PhaseError(
                    "No dew point exists at this temperature (solver did not converge within bounds).",
                    phase="vapor",
                    pressure=float(getattr(dr, 'pressure', float('nan'))),
                    temperature=float(T),
                    reason="no_saturation",
                )
            if float(dr.pressure) >= float(_P_MAX) * 0.999 or float(dr.pressure) <= float(_P_MIN) * 1.001:
                raise PhaseError(
                    "No dew point exists at this temperature (pressure bounds reached).",
                    phase="vapor",
                    pressure=float(dr.pressure),
                    temperature=float(T),
                    reason="no_saturation",
                )
            dew_T_list.append(float(T))
            dew_P_list.append(float(dr.pressure))
            P_dew_prev = float(dr.pressure)
        except PhaseError as e:
            if e.details.get("reason") != "no_saturation":
                raise
        except (ConvergenceError, ValidationError):
            pass

    bubble_T = np.asarray(bubble_T_list, dtype=np.float64)
    bubble_P = np.asarray(bubble_P_list, dtype=np.float64)
    dew_T = np.asarray(dew_T_list, dtype=np.float64)
    dew_P = np.asarray(dew_P_list, dtype=np.float64)

    if len(bubble_T) == 0 and len(dew_T) == 0:
        raise RuntimeError(
            "Phase envelope failed: no saturation points found in the requested temperature range. "
            "Suggestions: widen the temperature range; lower temperature_min_k; verify inputs are in K/Pa; "
            "confirm composition sums to 1.0 and components are valid."
        )

    if len(bubble_T) == 0 or len(dew_T) == 0:
        raise RuntimeError(
            "Phase envelope failed: could not trace both bubble and dew branches in the requested range. "
            "Suggestions: widen the temperature range; adjust the mixture to include both light/heavy components; "
            "verify EOS and binary interaction parameters."
        )

    Tc, Pc = detect_critical_point(
        bubble_T=bubble_T,
        bubble_P=bubble_P,
        dew_T=dew_T,
        dew_P=dew_P,
        composition=z,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
    )
    critical_point = (float(Tc), float(Pc)) if (Tc is not None and Pc is not None) else None

    all_T = np.concatenate([bubble_T, dew_T])
    all_P = np.concatenate([bubble_P, dew_P])
    idx = int(np.argmax(all_P))
    cricondenbar = (float(all_T[idx]), float(all_P[idx]))

    idx_t = int(np.argmax(dew_T))
    cricondentherm = (float(dew_T[idx_t]), float(dew_P[idx_t]))

    return TracedEnvelopeResult(
        bubble_T=bubble_T,
        bubble_P=bubble_P,
        dew_T=dew_T,
        dew_P=dew_P,
        critical_point=critical_point,
        cricondenbar=cricondenbar,
        cricondentherm=cricondentherm,
    )
