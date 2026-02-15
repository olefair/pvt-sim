"""Iso-vol and iso-beta overlay computation for phase envelopes.

This module computes curves of constant vapor volume fraction (iso-vol, alpha)
and constant vapor mole fraction (iso-beta, beta) within the two-phase region
of a PT phase envelope.

Definitions:
- beta (vapor mole fraction): fraction of moles in the vapor phase
- alpha (vapor volume fraction): fraction of volume occupied by vapor

    alpha = beta * V_V / (beta * V_V + (1 - beta) * V_L)

where V_V and V_L are molar volumes of vapor and liquid phases.

References:
Whitson, C.H. and Brule, M.R. (2000). "Phase Behavior", SPE Monograph Vol. 20.
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple
from numpy.typing import NDArray

from ..models.component import Component
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash, FlashResult
from ..core.errors import ConvergenceStatus
from .phase_envelope import EnvelopeResult


class IsoLineMode(Enum):
    """Mode for iso-line computation.

    Attributes:
        NONE: No iso-lines computed
        ISO_VOL: Compute iso-vol lines (constant vapor volume fraction alpha)
        ISO_BETA: Compute iso-beta lines (constant vapor mole fraction beta)
        BOTH: Compute both iso-vol and iso-beta lines
    """
    NONE = auto()
    ISO_VOL = auto()
    ISO_BETA = auto()
    BOTH = auto()


@dataclass
class IsoLinePoint:
    """A single point on an iso-line.

    Attributes:
        temperature: Temperature (K)
        pressure: Pressure (Pa)
        target_value: Target iso-value (alpha or beta)
        computed_value: Actually computed value (should be close to target)
        vapor_fraction: Vapor mole fraction (beta) from flash
        vapor_volume_fraction: Vapor volume fraction (alpha)
        V_L: Liquid molar volume (m3/mol)
        V_V: Vapor molar volume (m3/mol)
        iterations: Flash iterations
        residual: Flash convergence residual
    """
    temperature: float
    pressure: float
    target_value: float
    computed_value: float
    vapor_fraction: float
    vapor_volume_fraction: float
    V_L: float
    V_V: float
    iterations: int
    residual: float


@dataclass
class IsoLineSegment:
    """A continuous segment of an iso-line.

    Phase envelopes may have multiple disconnected regions for a given
    iso-value, so results are stored as potentially multiple segments.

    Attributes:
        target_value: Target iso-value (alpha or beta)
        temperatures: Array of temperatures (K)
        pressures: Array of pressures (Pa)
        computed_values: Array of actually computed values
        vapor_fractions: Array of vapor mole fractions (beta)
        vapor_volume_fractions: Array of vapor volume fractions (alpha)
        V_L: Array of liquid molar volumes (m3/mol)
        V_V: Array of vapor molar volumes (m3/mol)
        converged: Array of convergence flags per point
    """
    target_value: float
    temperatures: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    pressures: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    computed_values: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    vapor_fractions: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    vapor_volume_fractions: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    V_L: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    V_V: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    converged: NDArray[np.bool_] = field(default_factory=lambda: np.array([], dtype=bool))

    def __len__(self) -> int:
        return len(self.temperatures)

    @property
    def is_empty(self) -> bool:
        return len(self.temperatures) == 0


@dataclass
class IsoLinesResult:
    """Complete results from iso-line computation.

    Attributes:
        mode: Computation mode used
        iso_vol_lines: List of iso-vol line segments (keyed by alpha value)
        iso_beta_lines: List of iso-beta line segments (keyed by beta value)
        alpha_levels: Alpha values requested for iso-vol
        beta_levels: Beta values requested for iso-beta
        composition: Feed composition used
        n_points_computed: Total number of points computed
        n_points_failed: Number of failed flash calculations
    """
    mode: IsoLineMode
    iso_vol_lines: dict[float, List[IsoLineSegment]] = field(default_factory=dict)
    iso_beta_lines: dict[float, List[IsoLineSegment]] = field(default_factory=dict)
    alpha_levels: List[float] = field(default_factory=list)
    beta_levels: List[float] = field(default_factory=list)
    composition: NDArray[np.float64] = field(default_factory=lambda: np.array([]))
    n_points_computed: int = 0
    n_points_failed: int = 0


# Default iso-value levels
DEFAULT_ALPHA_LEVELS: List[float] = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
DEFAULT_BETA_LEVELS: List[float] = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]

# Numerical tolerances
ISO_LINE_TOLERANCE: float = 1e-4  # Tolerance for iso-value matching
PRESSURE_BRACKET_EPSILON: float = 1e-3  # Fraction to shrink away from saturation bounds
ROOT_FINDING_XTOL: float = 100.0  # Pressure tolerance for root finder (Pa)
ROOT_FINDING_RTOL: float = 1e-6  # Relative tolerance for root finder


def _require_scipy_brentq():
    try:
        from scipy.optimize import brentq
    except Exception as exc:
        raise RuntimeError(
            "SciPy is required for iso-line calculations. Install with: pip install -e '.[full]'"
        ) from exc
    return brentq


def compute_alpha_from_flash(
    flash_result: FlashResult,
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None
) -> Tuple[float, float, float]:
    """Compute vapor volume fraction alpha from flash result.

    Parameters
    ----------
    flash_result : FlashResult
        Result from PT flash calculation
    eos : CubicEOS
        Equation of state for volume calculations
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters

    Returns
    -------
    Tuple[float, float, float]
        (alpha, V_L, V_V) where:
        - alpha: vapor volume fraction (0 to 1)
        - V_L: liquid molar volume (m3/mol)
        - V_V: vapor molar volume (m3/mol)

    Notes
    -----
    alpha = beta * V_V / (beta * V_V + (1 - beta) * V_L)

    For single-phase results, returns alpha = 0 (liquid) or 1 (vapor).
    """
    P = flash_result.pressure
    T = flash_result.temperature
    beta = flash_result.vapor_fraction

    if not flash_result.is_two_phase:
        if flash_result.phase == 'vapor':
            # All vapor
            V_V = eos.molar_volume(P, T, flash_result.vapor_composition, 'vapor', binary_interaction)
            return 1.0, 0.0, V_V
        else:
            # All liquid
            V_L = eos.molar_volume(P, T, flash_result.liquid_composition, 'liquid', binary_interaction)
            return 0.0, V_L, 0.0

    # Two-phase: compute molar volumes for each phase
    x = flash_result.liquid_composition
    y = flash_result.vapor_composition

    V_L = eos.molar_volume(P, T, x, 'liquid', binary_interaction)
    V_V = eos.molar_volume(P, T, y, 'vapor', binary_interaction)

    # Compute vapor volume fraction
    # alpha = (beta * V_V) / (beta * V_V + (1 - beta) * V_L)
    vol_vapor = beta * V_V
    vol_liquid = (1.0 - beta) * V_L
    vol_total = vol_vapor + vol_liquid

    if vol_total <= 0:
        return 0.0, V_L, V_V

    alpha = vol_vapor / vol_total

    return alpha, V_L, V_V


def _interpolate_envelope_pressure(
    T: float,
    envelope_T: NDArray[np.float64],
    envelope_P: NDArray[np.float64]
) -> Optional[float]:
    """Interpolate pressure at temperature T from envelope curve.

    Parameters
    ----------
    T : float
        Temperature to interpolate at
    envelope_T : NDArray[np.float64]
        Envelope temperature array
    envelope_P : NDArray[np.float64]
        Envelope pressure array

    Returns
    -------
    Optional[float]
        Interpolated pressure, or None if T is outside envelope range
    """
    if len(envelope_T) == 0:
        return None

    T_min = np.min(envelope_T)
    T_max = np.max(envelope_T)

    if T < T_min or T > T_max:
        return None

    # Sort by temperature for interpolation
    sort_idx = np.argsort(envelope_T)
    T_sorted = envelope_T[sort_idx]
    P_sorted = envelope_P[sort_idx]

    return float(np.interp(T, T_sorted, P_sorted))


def _get_pressure_bracket(
    T: float,
    envelope: EnvelopeResult,
    epsilon: float = PRESSURE_BRACKET_EPSILON
) -> Optional[Tuple[float, float]]:
    """Get pressure bracket [P_low, P_high] for two-phase region at temperature T.

    The bracket is defined by the bubble and dew pressures at the given temperature.

    Parameters
    ----------
    T : float
        Temperature (K)
    envelope : EnvelopeResult
        Phase envelope result
    epsilon : float
        Fraction to shrink away from exact saturation bounds

    Returns
    -------
    Optional[Tuple[float, float]]
        (P_low, P_high) bracket, or None if T is outside two-phase region
    """
    P_bubble = _interpolate_envelope_pressure(T, envelope.bubble_T, envelope.bubble_P)
    P_dew = _interpolate_envelope_pressure(T, envelope.dew_T, envelope.dew_P)

    if P_bubble is None or P_dew is None:
        return None

    # Bubble pressure is typically higher (liquid boundary)
    # Dew pressure is typically lower (vapor boundary)
    # But this can reverse near cricondenbar
    P_low = min(P_bubble, P_dew)
    P_high = max(P_bubble, P_dew)

    if P_high <= P_low:
        return None

    # Shrink bracket slightly to avoid singular behavior at exact saturation
    delta = (P_high - P_low) * epsilon
    P_low_shrunk = P_low + delta
    P_high_shrunk = P_high - delta

    if P_high_shrunk <= P_low_shrunk:
        return None

    return P_low_shrunk, P_high_shrunk


def _iso_vol_objective(
    P: float,
    T: float,
    alpha_target: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]]
) -> float:
    """Objective function for iso-vol root finding: alpha(T, P) - alpha_target.

    Parameters
    ----------
    P : float
        Pressure (Pa)
    T : float
        Temperature (K)
    alpha_target : float
        Target vapor volume fraction
    composition : NDArray[np.float64]
        Feed composition
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters

    Returns
    -------
    float
        alpha(T, P) - alpha_target

    Raises
    ------
    ValueError
        If flash fails or point is not two-phase
    """
    flash_result = pt_flash(
        pressure=P,
        temperature=T,
        composition=composition,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction
    )

    if not flash_result.converged or not flash_result.is_two_phase:
        # Return large residual to push solver away from this region
        raise ValueError("Flash failed or not two-phase")

    alpha, _, _ = compute_alpha_from_flash(flash_result, eos, binary_interaction)
    return alpha - alpha_target


def _iso_beta_objective(
    P: float,
    T: float,
    beta_target: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]]
) -> float:
    """Objective function for iso-beta root finding: beta(T, P) - beta_target.

    Parameters
    ----------
    P : float
        Pressure (Pa)
    T : float
        Temperature (K)
    beta_target : float
        Target vapor mole fraction
    composition : NDArray[np.float64]
        Feed composition
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters

    Returns
    -------
    float
        beta(T, P) - beta_target

    Raises
    ------
    ValueError
        If flash fails or point is not two-phase
    """
    flash_result = pt_flash(
        pressure=P,
        temperature=T,
        composition=composition,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction
    )

    if not flash_result.converged or not flash_result.is_two_phase:
        raise ValueError("Flash failed or not two-phase")

    return flash_result.vapor_fraction - beta_target


def _find_iso_line_at_T(
    T: float,
    target_value: float,
    envelope: EnvelopeResult,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    is_iso_vol: bool = True
) -> Optional[IsoLinePoint]:
    """Find the iso-line point at a specific temperature.

    Uses Brent's method to find pressure P such that the iso-value
    (alpha or beta) equals the target.

    Parameters
    ----------
    T : float
        Temperature (K)
    target_value : float
        Target iso-value (alpha for iso-vol, beta for iso-beta)
    envelope : EnvelopeResult
        Phase envelope for pressure bracketing
    composition : NDArray[np.float64]
        Feed composition
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters
    is_iso_vol : bool
        True for iso-vol (alpha), False for iso-beta

    Returns
    -------
    Optional[IsoLinePoint]
        Point on the iso-line, or None if no solution found
    """
    # Get pressure bracket
    bracket = _get_pressure_bracket(T, envelope)
    if bracket is None:
        return None

    P_low, P_high = bracket

    # Select objective function
    if is_iso_vol:
        objective = lambda P: _iso_vol_objective(
            P, T, target_value, composition, components, eos, binary_interaction
        )
    else:
        objective = lambda P: _iso_beta_objective(
            P, T, target_value, composition, components, eos, binary_interaction
        )

    # Check bracket validity (function must have opposite signs at endpoints)
    try:
        f_low = objective(P_low)
        f_high = objective(P_high)
    except (ValueError, Exception):
        return None

    # Check if bracket is valid
    if f_low * f_high > 0:
        # No sign change - target iso-value may not exist in this range
        return None

    # Use Brent's method to find root
    try:
        brentq = _require_scipy_brentq()
        P_solution = brentq(
            objective,
            P_low, P_high,
            xtol=ROOT_FINDING_XTOL,
            rtol=ROOT_FINDING_RTOL
        )
    except (ValueError, RuntimeError):
        return None

    # Compute final flash at solution point
    try:
        flash_result = pt_flash(
            pressure=P_solution,
            temperature=T,
            composition=composition,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction
        )
    except Exception:
        return None

    if not flash_result.converged or not flash_result.is_two_phase:
        return None

    # Compute volumes and alpha
    alpha, V_L, V_V = compute_alpha_from_flash(flash_result, eos, binary_interaction)
    beta = flash_result.vapor_fraction

    computed_value = alpha if is_iso_vol else beta

    return IsoLinePoint(
        temperature=T,
        pressure=P_solution,
        target_value=target_value,
        computed_value=computed_value,
        vapor_fraction=beta,
        vapor_volume_fraction=alpha,
        V_L=V_L,
        V_V=V_V,
        iterations=flash_result.iterations,
        residual=flash_result.residual
    )


def compute_iso_vol_lines(
    envelope: EnvelopeResult,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    alpha_levels: Optional[List[float]] = None,
    n_temperature_points: int = 50
) -> dict[float, List[IsoLineSegment]]:
    """Compute iso-vol lines (constant vapor volume fraction alpha).

    Parameters
    ----------
    envelope : EnvelopeResult
        Phase envelope result with bubble/dew curves
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters
    alpha_levels : Optional[List[float]]
        Alpha values to compute iso-lines for. Default is
        [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    n_temperature_points : int
        Number of temperature points to sample along envelope

    Returns
    -------
    dict[float, List[IsoLineSegment]]
        Dictionary mapping alpha value to list of iso-line segments
    """
    if alpha_levels is None:
        alpha_levels = DEFAULT_ALPHA_LEVELS.copy()

    composition = envelope.composition

    # Determine temperature range from envelope
    all_T = np.concatenate([envelope.bubble_T, envelope.dew_T])
    if len(all_T) == 0:
        return {alpha: [] for alpha in alpha_levels}

    T_min = float(np.min(all_T))
    T_max = float(np.max(all_T))

    # Generate temperature grid
    temperatures = np.linspace(T_min, T_max, n_temperature_points)

    result: dict[float, List[IsoLineSegment]] = {}

    for alpha in alpha_levels:
        # Collect points for this alpha level
        points: List[IsoLinePoint] = []

        for T in temperatures:
            point = _find_iso_line_at_T(
                T=T,
                target_value=alpha,
                envelope=envelope,
                composition=composition,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                is_iso_vol=True
            )
            if point is not None:
                points.append(point)

        # Convert points to segment(s)
        segments = _points_to_segments(points, alpha)
        result[alpha] = segments

    return result


def compute_iso_beta_lines(
    envelope: EnvelopeResult,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    beta_levels: Optional[List[float]] = None,
    n_temperature_points: int = 50
) -> dict[float, List[IsoLineSegment]]:
    """Compute iso-beta lines (constant vapor mole fraction beta).

    Parameters
    ----------
    envelope : EnvelopeResult
        Phase envelope result with bubble/dew curves
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters
    beta_levels : Optional[List[float]]
        Beta values to compute iso-lines for. Default is
        [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    n_temperature_points : int
        Number of temperature points to sample along envelope

    Returns
    -------
    dict[float, List[IsoLineSegment]]
        Dictionary mapping beta value to list of iso-line segments
    """
    if beta_levels is None:
        beta_levels = DEFAULT_BETA_LEVELS.copy()

    composition = envelope.composition

    # Determine temperature range from envelope
    all_T = np.concatenate([envelope.bubble_T, envelope.dew_T])
    if len(all_T) == 0:
        return {beta: [] for beta in beta_levels}

    T_min = float(np.min(all_T))
    T_max = float(np.max(all_T))

    # Generate temperature grid
    temperatures = np.linspace(T_min, T_max, n_temperature_points)

    result: dict[float, List[IsoLineSegment]] = {}

    for beta in beta_levels:
        # Collect points for this beta level
        points: List[IsoLinePoint] = []

        for T in temperatures:
            point = _find_iso_line_at_T(
                T=T,
                target_value=beta,
                envelope=envelope,
                composition=composition,
                components=components,
                eos=eos,
                binary_interaction=binary_interaction,
                is_iso_vol=False  # iso-beta mode
            )
            if point is not None:
                points.append(point)

        # Convert points to segment(s)
        segments = _points_to_segments(points, beta)
        result[beta] = segments

    return result


def _points_to_segments(
    points: List[IsoLinePoint],
    target_value: float,
    gap_threshold: float = 2.0
) -> List[IsoLineSegment]:
    """Convert a list of points to potentially multiple segments.

    Points are grouped into segments based on continuity (temperature gaps).

    Parameters
    ----------
    points : List[IsoLinePoint]
        List of iso-line points
    target_value : float
        Target iso-value
    gap_threshold : float
        Multiple of average temperature spacing to consider a gap

    Returns
    -------
    List[IsoLineSegment]
        List of continuous segments
    """
    if not points:
        return []

    # Sort by temperature
    points = sorted(points, key=lambda p: p.temperature)

    if len(points) == 1:
        p = points[0]
        return [IsoLineSegment(
            target_value=target_value,
            temperatures=np.array([p.temperature]),
            pressures=np.array([p.pressure]),
            computed_values=np.array([p.computed_value]),
            vapor_fractions=np.array([p.vapor_fraction]),
            vapor_volume_fractions=np.array([p.vapor_volume_fraction]),
            V_L=np.array([p.V_L]),
            V_V=np.array([p.V_V]),
            converged=np.array([True])
        )]

    # Compute temperature differences to detect gaps
    T_values = np.array([p.temperature for p in points])
    dT = np.diff(T_values)
    avg_dT = np.mean(dT) if len(dT) > 0 else 1.0

    # Find gap indices
    gap_indices = np.where(dT > gap_threshold * avg_dT)[0]

    # Split into segments
    segment_starts = [0] + list(gap_indices + 1)
    segment_ends = list(gap_indices + 1) + [len(points)]

    segments: List[IsoLineSegment] = []

    for start, end in zip(segment_starts, segment_ends):
        segment_points = points[start:end]
        if not segment_points:
            continue

        segment = IsoLineSegment(
            target_value=target_value,
            temperatures=np.array([p.temperature for p in segment_points]),
            pressures=np.array([p.pressure for p in segment_points]),
            computed_values=np.array([p.computed_value for p in segment_points]),
            vapor_fractions=np.array([p.vapor_fraction for p in segment_points]),
            vapor_volume_fractions=np.array([p.vapor_volume_fraction for p in segment_points]),
            V_L=np.array([p.V_L for p in segment_points]),
            V_V=np.array([p.V_V for p in segment_points]),
            converged=np.array([True] * len(segment_points))
        )
        segments.append(segment)

    return segments


def compute_iso_lines(
    envelope: EnvelopeResult,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    mode: IsoLineMode = IsoLineMode.BOTH,
    alpha_levels: Optional[List[float]] = None,
    beta_levels: Optional[List[float]] = None,
    n_temperature_points: int = 50
) -> IsoLinesResult:
    """Compute iso-lines for phase envelope overlay.

    Main entry point for iso-line computation with mode toggle.

    Parameters
    ----------
    envelope : EnvelopeResult
        Phase envelope result with bubble/dew curves
    components : List[Component]
        Component list
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters
    mode : IsoLineMode
        Computation mode:
        - NONE: Return empty result
        - ISO_VOL: Compute only iso-vol (alpha) lines
        - ISO_BETA: Compute only iso-beta lines
        - BOTH: Compute both iso-vol and iso-beta lines
    alpha_levels : Optional[List[float]]
        Alpha values for iso-vol lines. Default is
        [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    beta_levels : Optional[List[float]]
        Beta values for iso-beta lines. Default is
        [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
    n_temperature_points : int
        Number of temperature points to sample along envelope

    Returns
    -------
    IsoLinesResult
        Complete results with iso-vol and/or iso-beta lines

    Examples
    --------
    >>> from pvtcore.envelope import calculate_phase_envelope, compute_iso_lines, IsoLineMode
    >>> from pvtcore.eos import PengRobinsonEOS
    >>> from pvtcore.models import load_components
    >>>
    >>> components = [load_components()['C1'], load_components()['C10']]
    >>> eos = PengRobinsonEOS(components)
    >>> z = np.array([0.8, 0.2])
    >>>
    >>> envelope = calculate_phase_envelope(z, components, eos)
    >>> iso_lines = compute_iso_lines(envelope, components, eos, mode=IsoLineMode.BOTH)
    >>>
    >>> # Access iso-vol lines for alpha=0.5
    >>> alpha_05_segments = iso_lines.iso_vol_lines.get(0.5, [])
    >>> for seg in alpha_05_segments:
    ...     print(f"Segment with {len(seg)} points")
    """
    if alpha_levels is None:
        alpha_levels = DEFAULT_ALPHA_LEVELS.copy()
    if beta_levels is None:
        beta_levels = DEFAULT_BETA_LEVELS.copy()

    result = IsoLinesResult(
        mode=mode,
        alpha_levels=alpha_levels,
        beta_levels=beta_levels,
        composition=envelope.composition.copy()
    )

    if mode == IsoLineMode.NONE:
        return result

    n_computed = 0
    n_failed = 0

    # Compute iso-vol lines if requested
    if mode in (IsoLineMode.ISO_VOL, IsoLineMode.BOTH):
        result.iso_vol_lines = compute_iso_vol_lines(
            envelope=envelope,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            alpha_levels=alpha_levels,
            n_temperature_points=n_temperature_points
        )
        # Count points
        for segments in result.iso_vol_lines.values():
            for seg in segments:
                n_computed += len(seg)

    # Compute iso-beta lines if requested
    if mode in (IsoLineMode.ISO_BETA, IsoLineMode.BOTH):
        result.iso_beta_lines = compute_iso_beta_lines(
            envelope=envelope,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            beta_levels=beta_levels,
            n_temperature_points=n_temperature_points
        )
        # Count points
        for segments in result.iso_beta_lines.values():
            for seg in segments:
                n_computed += len(seg)

    # Estimate failed points (approximate)
    total_attempts = n_temperature_points * (
        len(alpha_levels) if mode in (IsoLineMode.ISO_VOL, IsoLineMode.BOTH) else 0
    ) + n_temperature_points * (
        len(beta_levels) if mode in (IsoLineMode.ISO_BETA, IsoLineMode.BOTH) else 0
    )
    n_failed = total_attempts - n_computed

    result.n_points_computed = n_computed
    result.n_points_failed = max(0, n_failed)

    return result
