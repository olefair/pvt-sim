"""Phase envelope calculations."""

from importlib.util import find_spec

from .phase_envelope import (
    calculate_phase_envelope,
    EnvelopeResult,
    estimate_cricondentherm,
    estimate_cricondenbar
)

from .critical_point import (
    detect_critical_point,
    estimate_critical_point_kays,
    find_critical_from_envelope,
    CriticalPointResult,
)

from .ternary import (
    PhaseClassification,
    TernaryGridPoint,
    TieLine,
    TernaryResult,
    generate_barycentric_grid,
    barycentric_to_cartesian,
    cartesian_to_barycentric,
    compute_ternary_diagram,
    get_tie_line_cartesian,
    get_triangle_vertices,
    get_triangle_edges,
    plot_ternary_diagram,
    DEFAULT_N_SUBDIVISIONS,
)

_ISO_LINES_AVAILABLE = find_spec("scipy") is not None

if _ISO_LINES_AVAILABLE:
    from .iso_lines import (
        IsoLineMode,
        IsoLinePoint,
        IsoLineSegment,
        IsoLinesResult,
        compute_iso_lines,
        compute_iso_vol_lines,
        compute_iso_beta_lines,
        compute_alpha_from_flash,
        DEFAULT_ALPHA_LEVELS,
        DEFAULT_BETA_LEVELS,
    )

__all__ = [
    # Phase envelope
    'calculate_phase_envelope',
    'EnvelopeResult',
    'estimate_cricondentherm',
    'estimate_cricondenbar',
    # Critical point
    'detect_critical_point',
    'estimate_critical_point_kays',
    'find_critical_from_envelope',
    'CriticalPointResult',
    # Ternary diagrams
    'PhaseClassification',
    'TernaryGridPoint',
    'TieLine',
    'TernaryResult',
    'generate_barycentric_grid',
    'barycentric_to_cartesian',
    'cartesian_to_barycentric',
    'compute_ternary_diagram',
    'get_tie_line_cartesian',
    'get_triangle_vertices',
    'get_triangle_edges',
    'plot_ternary_diagram',
    'DEFAULT_N_SUBDIVISIONS',
]

if _ISO_LINES_AVAILABLE:
    __all__.extend([
        'IsoLineMode',
        'IsoLinePoint',
        'IsoLineSegment',
        'IsoLinesResult',
        'compute_iso_lines',
        'compute_iso_vol_lines',
        'compute_iso_beta_lines',
        'compute_alpha_from_flash',
        'DEFAULT_ALPHA_LEVELS',
        'DEFAULT_BETA_LEVELS',
    ])
