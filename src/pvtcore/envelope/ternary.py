"""Ternary diagram computation for 3-component systems.

This module computes phase behavior classification and tie-lines for a
3-component (or 3-lump) system at fixed temperature and pressure.

For a triangular grid of overall compositions z=(z1, z2, z3), each point
is classified as:
- single-phase (stable)
- two-phase (unstable, flash converged)
- failed (numerical failure)

Two-phase points provide tie-lines connecting liquid composition x
to vapor composition y in ternary space.

References:
Whitson, C.H. and Brule, M.R. (2000). "Phase Behavior", SPE Monograph Vol. 20.
Michelsen, M.L. and Mollerup, J.M. (2007). "Thermodynamic Models:
    Fundamentals & Computational Aspects", 2nd Ed.
"""

import numpy as np
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple
from numpy.typing import NDArray

from ..models.component import Component
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash, FlashResult
from ..stability import is_stable
from ..core.errors import ConvergenceStatus
from .iso_lines import compute_alpha_from_flash


class PhaseClassification(Enum):
    """Classification of a ternary grid point.

    Attributes:
        SINGLE_PHASE_LIQUID: Stable single-phase liquid
        SINGLE_PHASE_VAPOR: Stable single-phase vapor
        TWO_PHASE: Unstable, two-phase (flash converged)
        FAILED: Numerical failure during calculation
    """
    SINGLE_PHASE_LIQUID = auto()
    SINGLE_PHASE_VAPOR = auto()
    TWO_PHASE = auto()
    FAILED = auto()


@dataclass
class TernaryGridPoint:
    """A single point on the ternary grid.

    Attributes:
        composition: Overall composition z = (z1, z2, z3)
        classification: Phase classification result
        vapor_fraction: Vapor mole fraction beta (0 to 1), NaN if single-phase
        vapor_volume_fraction: Vapor volume fraction alpha, NaN if single-phase
        liquid_composition: Liquid phase composition x, None if single-phase
        vapor_composition: Vapor phase composition y, None if single-phase
        K_values: Equilibrium ratios Ki = yi/xi, None if single-phase
        V_L: Liquid molar volume (m3/mol), NaN if not computed
        V_V: Vapor molar volume (m3/mol), NaN if not computed
        flash_iterations: Number of flash iterations, 0 if single-phase
        flash_residual: Flash convergence residual
        failure_reason: Reason for failure if classification is FAILED
    """
    composition: NDArray[np.float64]
    classification: PhaseClassification
    vapor_fraction: float = np.nan
    vapor_volume_fraction: float = np.nan
    liquid_composition: Optional[NDArray[np.float64]] = None
    vapor_composition: Optional[NDArray[np.float64]] = None
    K_values: Optional[NDArray[np.float64]] = None
    V_L: float = np.nan
    V_V: float = np.nan
    flash_iterations: int = 0
    flash_residual: float = np.nan
    failure_reason: Optional[str] = None

    @property
    def is_two_phase(self) -> bool:
        """Check if point is in two-phase region."""
        return self.classification == PhaseClassification.TWO_PHASE

    @property
    def is_single_phase(self) -> bool:
        """Check if point is in single-phase region."""
        return self.classification in (
            PhaseClassification.SINGLE_PHASE_LIQUID,
            PhaseClassification.SINGLE_PHASE_VAPOR
        )


@dataclass
class TieLine:
    """A tie-line connecting liquid and vapor compositions.

    Attributes:
        feed_composition: Overall composition z where flash was performed
        liquid_composition: Liquid phase composition x
        vapor_composition: Vapor phase composition y
        vapor_fraction: Vapor mole fraction beta
        vapor_volume_fraction: Vapor volume fraction alpha
    """
    feed_composition: NDArray[np.float64]
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    vapor_fraction: float
    vapor_volume_fraction: float = np.nan


@dataclass
class TernaryResult:
    """Complete results from ternary diagram computation.

    Attributes:
        temperature: Temperature used (K)
        pressure: Pressure used (Pa)
        components: List of 3 component names
        grid_points: List of all grid points with classifications
        tie_lines: List of tie-lines for two-phase points
        n_subdivisions: Number of subdivisions along edges
        n_total_points: Total number of grid points
        n_single_phase: Number of single-phase points
        n_two_phase: Number of two-phase points
        n_failed: Number of failed points
    """
    temperature: float
    pressure: float
    components: List[str]
    grid_points: List[TernaryGridPoint] = field(default_factory=list)
    tie_lines: List[TieLine] = field(default_factory=list)
    n_subdivisions: int = 31
    n_total_points: int = 0
    n_single_phase: int = 0
    n_two_phase: int = 0
    n_failed: int = 0

    def get_compositions_by_classification(
        self,
        classification: PhaseClassification
    ) -> NDArray[np.float64]:
        """Get all compositions with a specific classification.

        Parameters
        ----------
        classification : PhaseClassification
            The classification to filter by

        Returns
        -------
        NDArray[np.float64]
            Array of shape (n_points, 3) with compositions
        """
        points = [p for p in self.grid_points if p.classification == classification]
        if not points:
            return np.array([]).reshape(0, 3)
        return np.array([p.composition for p in points])

    def get_single_phase_compositions(self) -> NDArray[np.float64]:
        """Get all single-phase compositions."""
        liquid = self.get_compositions_by_classification(
            PhaseClassification.SINGLE_PHASE_LIQUID
        )
        vapor = self.get_compositions_by_classification(
            PhaseClassification.SINGLE_PHASE_VAPOR
        )
        if len(liquid) == 0:
            return vapor
        if len(vapor) == 0:
            return liquid
        return np.vstack([liquid, vapor])

    def get_two_phase_compositions(self) -> NDArray[np.float64]:
        """Get all two-phase compositions."""
        return self.get_compositions_by_classification(PhaseClassification.TWO_PHASE)


# Default parameters
DEFAULT_N_SUBDIVISIONS: int = 31  # ~496 grid points
MASS_BALANCE_TOLERANCE: float = 1e-8  # Tolerance for mass balance check


def generate_barycentric_grid(n_subdivisions: int = DEFAULT_N_SUBDIVISIONS) -> NDArray[np.float64]:
    """Generate a triangular grid of barycentric coordinates.

    Creates all compositions z = (z1, z2, z3) where:
    - z_i = i / n_subdivisions for integer i
    - z1 + z2 + z3 = 1

    Parameters
    ----------
    n_subdivisions : int
        Number of subdivisions along each edge. Total points = (n+1)(n+2)/2.

    Returns
    -------
    NDArray[np.float64]
        Array of shape (n_points, 3) with all grid compositions
    """
    n = n_subdivisions
    compositions = []

    for i in range(n + 1):
        for j in range(n + 1 - i):
            k = n - i - j
            z1 = i / n
            z2 = j / n
            z3 = k / n
            compositions.append([z1, z2, z3])

    return np.array(compositions, dtype=np.float64)


def barycentric_to_cartesian(
    compositions: NDArray[np.float64],
    vertices: Optional[NDArray[np.float64]] = None
) -> NDArray[np.float64]:
    """Convert barycentric coordinates to 2D Cartesian coordinates.

    Default vertices form an equilateral triangle:
    - A = (0, 0) for z1 = 1
    - B = (1, 0) for z2 = 1
    - C = (0.5, sqrt(3)/2) for z3 = 1

    Parameters
    ----------
    compositions : NDArray[np.float64]
        Array of shape (n_points, 3) with barycentric coordinates
    vertices : Optional[NDArray[np.float64]]
        Custom vertex positions, shape (3, 2). If None, uses default equilateral.

    Returns
    -------
    NDArray[np.float64]
        Array of shape (n_points, 2) with Cartesian coordinates
    """
    if vertices is None:
        # Default equilateral triangle vertices
        vertices = np.array([
            [0.0, 0.0],           # A (z1 = 1)
            [1.0, 0.0],           # B (z2 = 1)
            [0.5, np.sqrt(3) / 2]  # C (z3 = 1)
        ])

    compositions = np.atleast_2d(compositions)

    # p = z1 * A + z2 * B + z3 * C
    cartesian = compositions @ vertices

    return cartesian


def cartesian_to_barycentric(
    points: NDArray[np.float64],
    vertices: Optional[NDArray[np.float64]] = None
) -> NDArray[np.float64]:
    """Convert 2D Cartesian coordinates to barycentric coordinates.

    Inverse of barycentric_to_cartesian.

    Parameters
    ----------
    points : NDArray[np.float64]
        Array of shape (n_points, 2) with Cartesian coordinates
    vertices : Optional[NDArray[np.float64]]
        Custom vertex positions, shape (3, 2). If None, uses default equilateral.

    Returns
    -------
    NDArray[np.float64]
        Array of shape (n_points, 3) with barycentric coordinates
    """
    if vertices is None:
        vertices = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [0.5, np.sqrt(3) / 2]
        ])

    points = np.atleast_2d(points)
    A, B, C = vertices

    # Solve the linear system for barycentric coordinates
    # Using the formula for barycentric coordinates in a triangle
    v0 = C - A
    v1 = B - A
    v2 = points - A

    dot00 = np.dot(v0, v0)
    dot01 = np.dot(v0, v1)
    dot11 = np.dot(v1, v1)

    denom = dot00 * dot11 - dot01 * dot01

    dot02 = np.sum(v2 * v0, axis=1)
    dot12 = np.sum(v2 * v1, axis=1)

    z3 = (dot11 * dot02 - dot01 * dot12) / denom
    z2 = (dot00 * dot12 - dot01 * dot02) / denom
    z1 = 1.0 - z2 - z3

    return np.column_stack([z1, z2, z3])


def _classify_point(
    composition: NDArray[np.float64],
    pressure: float,
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    compute_volumes: bool = True
) -> TernaryGridPoint:
    """Classify a single ternary grid point.

    Parameters
    ----------
    composition : NDArray[np.float64]
        Overall composition z = (z1, z2, z3)
    pressure : float
        Pressure (Pa)
    temperature : float
        Temperature (K)
    components : List[Component]
        List of 3 components
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters (3x3 matrix)
    compute_volumes : bool
        Whether to compute molar volumes and alpha

    Returns
    -------
    TernaryGridPoint
        Classified grid point with all computed properties
    """
    z = np.asarray(composition, dtype=np.float64)

    # Skip points at pure component vertices (z_i = 1)
    # These are trivially single-phase
    if np.any(z > 0.9999):
        idx = np.argmax(z)
        # Determine phase at this pure component condition
        try:
            flash_result = pt_flash(
                pressure, temperature, z, components, eos,
                binary_interaction=binary_interaction
            )
            if flash_result.phase == 'liquid':
                classification = PhaseClassification.SINGLE_PHASE_LIQUID
            else:
                classification = PhaseClassification.SINGLE_PHASE_VAPOR
        except Exception:
            classification = PhaseClassification.SINGLE_PHASE_LIQUID  # Default

        return TernaryGridPoint(
            composition=z.copy(),
            classification=classification
        )

    # Skip points with any component at zero (edge of triangle)
    # These need special handling
    if np.any(z < 1e-10):
        z = np.maximum(z, 1e-10)
        z = z / z.sum()

    try:
        # Perform flash calculation
        flash_result = pt_flash(
            pressure, temperature, z, components, eos,
            binary_interaction=binary_interaction
        )

        if not flash_result.converged:
            return TernaryGridPoint(
                composition=z.copy(),
                classification=PhaseClassification.FAILED,
                failure_reason=f"Flash did not converge: {flash_result.status.name}"
            )

        if flash_result.is_two_phase:
            # Two-phase point
            beta = flash_result.vapor_fraction
            x = flash_result.liquid_composition
            y = flash_result.vapor_composition
            K = flash_result.K_values

            # Compute volumes and alpha if requested
            V_L = np.nan
            V_V = np.nan
            alpha = np.nan

            if compute_volumes:
                try:
                    alpha, V_L, V_V = compute_alpha_from_flash(
                        flash_result, eos, binary_interaction
                    )
                except Exception:
                    pass  # Keep NaN values

            # Verify mass balance
            z_check = (1 - beta) * x + beta * y
            mass_balance_error = np.max(np.abs(z - z_check))

            if mass_balance_error > MASS_BALANCE_TOLERANCE:
                return TernaryGridPoint(
                    composition=z.copy(),
                    classification=PhaseClassification.FAILED,
                    failure_reason=f"Mass balance error: {mass_balance_error:.2e}"
                )

            return TernaryGridPoint(
                composition=z.copy(),
                classification=PhaseClassification.TWO_PHASE,
                vapor_fraction=beta,
                vapor_volume_fraction=alpha,
                liquid_composition=x.copy(),
                vapor_composition=y.copy(),
                K_values=K.copy(),
                V_L=V_L,
                V_V=V_V,
                flash_iterations=flash_result.iterations,
                flash_residual=flash_result.residual
            )

        else:
            # Single-phase point
            if flash_result.phase == 'liquid':
                classification = PhaseClassification.SINGLE_PHASE_LIQUID
            else:
                classification = PhaseClassification.SINGLE_PHASE_VAPOR

            return TernaryGridPoint(
                composition=z.copy(),
                classification=classification,
                flash_iterations=flash_result.iterations
            )

    except Exception as e:
        return TernaryGridPoint(
            composition=z.copy(),
            classification=PhaseClassification.FAILED,
            failure_reason=str(e)
        )


def compute_ternary_diagram(
    temperature: float,
    pressure: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    n_subdivisions: int = DEFAULT_N_SUBDIVISIONS,
    compute_volumes: bool = True,
    compute_tie_lines: bool = True,
    tie_line_skip: int = 1
) -> TernaryResult:
    """Compute ternary phase diagram at fixed temperature and pressure.

    Parameters
    ----------
    temperature : float
        Temperature (K)
    pressure : float
        Pressure (Pa)
    components : List[Component]
        List of exactly 3 components
    eos : CubicEOS
        Equation of state
    binary_interaction : Optional[NDArray[np.float64]]
        Binary interaction parameters (3x3 matrix)
    n_subdivisions : int
        Number of subdivisions along triangle edges.
        Total points = (n+1)(n+2)/2. Default is 31 (~496 points).
    compute_volumes : bool
        Whether to compute molar volumes and vapor volume fraction alpha.
    compute_tie_lines : bool
        Whether to compute and store tie-lines for two-phase points.
    tie_line_skip : int
        Store every Nth tie-line to reduce clutter. Default is 1 (all).

    Returns
    -------
    TernaryResult
        Complete ternary diagram results

    Raises
    ------
    ValueError
        If number of components is not exactly 3

    Examples
    --------
    >>> from pvtcore.envelope.ternary import compute_ternary_diagram
    >>> from pvtcore.eos import PengRobinsonEOS
    >>> from pvtcore.models import load_components
    >>>
    >>> comps = load_components()
    >>> components = [comps['C1'], comps['C4'], comps['C10']]
    >>> eos = PengRobinsonEOS(components)
    >>>
    >>> result = compute_ternary_diagram(
    ...     temperature=350.0,  # K
    ...     pressure=5e6,       # 50 bar
    ...     components=components,
    ...     eos=eos,
    ...     n_subdivisions=21
    ... )
    >>>
    >>> print(f"Total points: {result.n_total_points}")
    >>> print(f"Two-phase points: {result.n_two_phase}")
    >>> print(f"Tie-lines: {len(result.tie_lines)}")
    """
    if len(components) != 3:
        raise ValueError(f"Ternary diagram requires exactly 3 components, got {len(components)}")

    # Generate grid
    compositions = generate_barycentric_grid(n_subdivisions)

    result = TernaryResult(
        temperature=temperature,
        pressure=pressure,
        components=[c.name for c in components],
        n_subdivisions=n_subdivisions,
        n_total_points=len(compositions)
    )

    n_single = 0
    n_two = 0
    n_failed = 0
    tie_line_counter = 0

    for z in compositions:
        point = _classify_point(
            composition=z,
            pressure=pressure,
            temperature=temperature,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            compute_volumes=compute_volumes
        )

        result.grid_points.append(point)

        # Update counts
        if point.classification == PhaseClassification.TWO_PHASE:
            n_two += 1

            # Store tie-line if requested
            if compute_tie_lines and point.liquid_composition is not None:
                tie_line_counter += 1
                if tie_line_counter % tie_line_skip == 0:
                    tie_line = TieLine(
                        feed_composition=point.composition.copy(),
                        liquid_composition=point.liquid_composition.copy(),
                        vapor_composition=point.vapor_composition.copy(),
                        vapor_fraction=point.vapor_fraction,
                        vapor_volume_fraction=point.vapor_volume_fraction
                    )
                    result.tie_lines.append(tie_line)

        elif point.classification == PhaseClassification.FAILED:
            n_failed += 1
        else:
            n_single += 1

    result.n_single_phase = n_single
    result.n_two_phase = n_two
    result.n_failed = n_failed

    return result


def get_tie_line_cartesian(
    tie_line: TieLine,
    vertices: Optional[NDArray[np.float64]] = None
) -> Tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Get tie-line endpoints in Cartesian coordinates for plotting.

    Parameters
    ----------
    tie_line : TieLine
        A tie-line object
    vertices : Optional[NDArray[np.float64]]
        Custom triangle vertices. If None, uses default equilateral.

    Returns
    -------
    Tuple[NDArray[np.float64], NDArray[np.float64]]
        (liquid_point, vapor_point) as 2D Cartesian coordinates
    """
    liquid_cart = barycentric_to_cartesian(
        tie_line.liquid_composition.reshape(1, 3), vertices
    ).flatten()

    vapor_cart = barycentric_to_cartesian(
        tie_line.vapor_composition.reshape(1, 3), vertices
    ).flatten()

    return liquid_cart, vapor_cart


def get_triangle_vertices() -> NDArray[np.float64]:
    """Get default equilateral triangle vertices.

    Returns
    -------
    NDArray[np.float64]
        Array of shape (3, 2) with vertex coordinates:
        - [0]: vertex for component 1 (z1=1)
        - [1]: vertex for component 2 (z2=1)
        - [2]: vertex for component 3 (z3=1)
    """
    return np.array([
        [0.0, 0.0],
        [1.0, 0.0],
        [0.5, np.sqrt(3) / 2]
    ])


def get_triangle_edges() -> List[Tuple[NDArray[np.float64], NDArray[np.float64]]]:
    """Get triangle edge line segments for plotting.

    Returns
    -------
    List[Tuple[NDArray[np.float64], NDArray[np.float64]]]
        List of (start, end) coordinate pairs for each edge
    """
    vertices = get_triangle_vertices()
    edges = [
        (vertices[0], vertices[1]),  # Bottom edge (component 3 = 0)
        (vertices[1], vertices[2]),  # Right edge (component 1 = 0)
        (vertices[2], vertices[0]),  # Left edge (component 2 = 0)
    ]
    return edges


def plot_ternary_diagram(
    result: TernaryResult,
    ax=None,
    show_tie_lines: bool = True,
    tie_line_alpha: float = 0.3,
    tie_line_color: str = 'gray',
    single_phase_color: str = 'blue',
    two_phase_color: str = 'red',
    failed_color: str = 'black',
    marker_size: float = 10.0,
    show_labels: bool = True,
    title: Optional[str] = None
):
    """Plot ternary diagram with phase classification.

    Parameters
    ----------
    result : TernaryResult
        Ternary computation result
    ax : matplotlib Axes, optional
        Axes to plot on. If None, creates new figure.
    show_tie_lines : bool
        Whether to show tie-lines
    tie_line_alpha : float
        Transparency for tie-lines
    tie_line_color : str
        Color for tie-lines
    single_phase_color : str
        Color for single-phase points
    two_phase_color : str
        Color for two-phase points
    failed_color : str
        Color for failed points
    marker_size : float
        Size of scatter markers
    show_labels : bool
        Whether to show component labels at vertices
    title : Optional[str]
        Plot title. If None, generates from T and P.

    Returns
    -------
    matplotlib Axes
        The axes with the plot
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for plotting")

    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(8, 7))

    vertices = get_triangle_vertices()

    # Draw triangle outline
    for start, end in get_triangle_edges():
        ax.plot([start[0], end[0]], [start[1], end[1]], 'k-', linewidth=1.5)

    # Plot single-phase points
    single_phase_points = []
    for p in result.grid_points:
        if p.is_single_phase:
            single_phase_points.append(p.composition)

    if single_phase_points:
        coords = barycentric_to_cartesian(np.array(single_phase_points), vertices)
        ax.scatter(coords[:, 0], coords[:, 1], c=single_phase_color,
                   s=marker_size, alpha=0.6, label='Single-phase')

    # Plot two-phase points
    two_phase_points = []
    for p in result.grid_points:
        if p.is_two_phase:
            two_phase_points.append(p.composition)

    if two_phase_points:
        coords = barycentric_to_cartesian(np.array(two_phase_points), vertices)
        ax.scatter(coords[:, 0], coords[:, 1], c=two_phase_color,
                   s=marker_size, alpha=0.6, label='Two-phase')

    # Plot failed points
    failed_points = []
    for p in result.grid_points:
        if p.classification == PhaseClassification.FAILED:
            failed_points.append(p.composition)

    if failed_points:
        coords = barycentric_to_cartesian(np.array(failed_points), vertices)
        ax.scatter(coords[:, 0], coords[:, 1], c=failed_color,
                   s=marker_size, marker='x', alpha=0.8, label='Failed')

    # Draw tie-lines
    if show_tie_lines and result.tie_lines:
        for tie_line in result.tie_lines:
            liq_pt, vap_pt = get_tie_line_cartesian(tie_line, vertices)
            ax.plot([liq_pt[0], vap_pt[0]], [liq_pt[1], vap_pt[1]],
                    color=tie_line_color, alpha=tie_line_alpha, linewidth=0.5)

    # Add component labels
    if show_labels:
        offset = 0.05
        ax.text(vertices[0, 0] - offset, vertices[0, 1] - offset,
                result.components[0], ha='right', va='top', fontsize=10)
        ax.text(vertices[1, 0] + offset, vertices[1, 1] - offset,
                result.components[1], ha='left', va='top', fontsize=10)
        ax.text(vertices[2, 0], vertices[2, 1] + offset,
                result.components[2], ha='center', va='bottom', fontsize=10)

    # Title
    if title is None:
        title = f"Ternary Diagram at T={result.temperature:.1f} K, P={result.pressure/1e6:.2f} MPa"
    ax.set_title(title)

    ax.set_xlim(-0.1, 1.1)
    ax.set_ylim(-0.1, 1.0)
    ax.set_aspect('equal')
    ax.axis('off')
    ax.legend(loc='upper right')

    return ax
