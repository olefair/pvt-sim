"""Local saturation-root scanning utilities for continuation development.

These helpers do not build the phase envelope directly. They expose the local
sign-change structure of the bubble/dew stability boundary at a fixed
temperature so a continuation tracer can follow the correct neighboring root
family instead of rescanning globally at every step.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Literal

import numpy as np
from numpy.typing import NDArray

from ..eos.base import CubicEOS
from ..flash.bubble_point import (
    _is_degenerate_trivial_trial as is_bubble_trivial,
    _tpd_vapor_trial,
)
from ..flash.dew_point import (
    _is_degenerate_trivial_trial as is_dew_trivial,
    _tpd_liquid_trial,
)

PRESSURE_MIN: float = 1.0e3
PRESSURE_MAX: float = 1.0e8
TPD_ZERO_TOL: float = 1.0e-8

BranchName = Literal["bubble", "dew"]


@dataclass(frozen=True)
class RootBracket:
    """Pressure interval where the local boundary classification changes."""

    branch: BranchName
    pressure_lo_bar: float
    pressure_hi_bar: float
    class_lo: int
    class_hi: int
    trivial_lo: bool
    trivial_hi: bool


def tpd_class(value: float, tol: float = TPD_ZERO_TOL) -> int:
    """Classify a TPD value as positive, near-zero, or negative."""
    if value > tol:
        return 1
    if value < -tol:
        return -1
    return 0


def normalize_trial(trial: NDArray[np.float64]) -> NDArray[np.float64]:
    """Normalize a trial composition when it is finite and has positive total."""
    trial = np.asarray(trial, dtype=float)
    total = float(np.sum(trial))
    if not np.all(np.isfinite(trial)) or total <= 0.0:
        return trial
    return trial / total


def scan_branch_roots(
    *,
    branch: BranchName,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    binary_interaction: NDArray[np.float64] | None = None,
    n_pressure_points: int = 120,
    pressure_min: float = PRESSURE_MIN,
    pressure_max: float = PRESSURE_MAX,
) -> List[RootBracket]:
    """Scan the fixed-temperature local root structure for one saturation branch.

    Parameters
    ----------
    branch:
        ``"bubble"`` or ``"dew"``.
    temperature:
        Temperature in K.
    composition:
        Feed mole fractions.
    eos:
        Equation of state.
    binary_interaction:
        Optional BIP matrix.
    n_pressure_points:
        Number of log-spaced sample pressures.
    pressure_min, pressure_max:
        Pressure scan bounds in Pa.
    """
    metric: Callable[[float, float, NDArray[np.float64], CubicEOS, NDArray[np.float64] | None], tuple[float, NDArray[np.float64]]]
    trivial_check: Callable[[NDArray[np.float64], NDArray[np.float64]], bool]

    if branch == "bubble":
        metric = _tpd_vapor_trial
        trivial_check = is_bubble_trivial
    elif branch == "dew":
        metric = _tpd_liquid_trial
        trivial_check = is_dew_trivial
    else:
        raise ValueError(f"Unsupported branch: {branch}")

    z = np.asarray(composition, dtype=float)
    pressures = np.geomspace(float(pressure_min), float(pressure_max), int(n_pressure_points))

    previous = None
    brackets: List[RootBracket] = []

    for pressure in pressures:
        tpd_value, trial = metric(
            float(pressure),
            float(temperature),
            z,
            eos,
            binary_interaction,
        )
        trial = normalize_trial(trial)
        klass = tpd_class(float(tpd_value))
        trivial = bool(klass == 0 and trivial_check(z, trial))
        current = (float(pressure), klass, trivial)

        if previous is not None and previous[1] != current[1]:
            brackets.append(
                RootBracket(
                    branch=branch,
                    pressure_lo_bar=previous[0] / 1.0e5,
                    pressure_hi_bar=current[0] / 1.0e5,
                    class_lo=previous[1],
                    class_hi=current[1],
                    trivial_lo=previous[2],
                    trivial_hi=current[2],
                )
            )

        previous = current

    return brackets
