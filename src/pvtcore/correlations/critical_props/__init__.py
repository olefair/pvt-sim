"""Critical property correlations for petroleum pseudo-components.

This package intentionally *re-exports* the public API from the legacy module
``pvtcore.correlations.critical_props.py``. A directory package was introduced
to host additional correlation implementations (e.g., Riazi-Daubert vectorized
forms), but the project historically used a single-module API.

To avoid breaking imports like ``from pvtcore.correlations import estimate_critical_props``,
this package loads the legacy module under an internal name and re-exports its
public symbols.
"""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import ModuleType
import sys as _sys


def _load_legacy_module() -> ModuleType:
    legacy_name = "pvtcore.correlations._critical_props_legacy"
    if legacy_name in _sys.modules:
        mod = _sys.modules[legacy_name]
        if isinstance(mod, ModuleType):
            return mod
    legacy_path = Path(__file__).resolve().parent.parent / "critical_props.py"
    spec = spec_from_file_location(legacy_name, legacy_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load legacy critical_props module: {legacy_path}")
    mod = module_from_spec(spec)
    _sys.modules[legacy_name] = mod
    spec.loader.exec_module(mod)
    return mod


_legacy = _load_legacy_module()

# ---------------------------------------------------------------------------
# Legacy API re-exports (kept for backwards compatibility)
# ---------------------------------------------------------------------------

CriticalPropsMethod = _legacy.CriticalPropsMethod
CriticalPropsResult = _legacy.CriticalPropsResult

riazi_daubert_Tc = _legacy.riazi_daubert_Tc
riazi_daubert_Pc = _legacy.riazi_daubert_Pc
riazi_daubert_Vc = _legacy.riazi_daubert_Vc
riazi_daubert_critical_props = _legacy.riazi_daubert_critical_props

kesler_lee_Tc = _legacy.kesler_lee_Tc
kesler_lee_Pc = _legacy.kesler_lee_Pc
kesler_lee_critical_props = _legacy.kesler_lee_critical_props

cavett_Tc = _legacy.cavett_Tc
cavett_Pc = _legacy.cavett_Pc
cavett_critical_props = _legacy.cavett_critical_props

estimate_critical_props = _legacy.estimate_critical_props

# Optional vectorized helpers (not part of the original minimal API, but useful)
riazi_daubert_Tc_array = getattr(_legacy, "riazi_daubert_Tc_array", None)
riazi_daubert_Pc_array = getattr(_legacy, "riazi_daubert_Pc_array", None)
riazi_daubert_Vc_array = getattr(_legacy, "riazi_daubert_Vc_array", None)

# ---------------------------------------------------------------------------
# Newer, vectorized Riazi-Daubert helpers (codex additions)
# ---------------------------------------------------------------------------

from .riazi_daubert import (  # noqa: E402
    RiaziDaubertCoefficients,
    estimate_from_mw_sg,
    estimate_from_tb_sg,
    edmister_acentric_factor,
)

__all__ = [
    # Legacy API
    "CriticalPropsMethod",
    "CriticalPropsResult",
    "riazi_daubert_Tc",
    "riazi_daubert_Pc",
    "riazi_daubert_Vc",
    "riazi_daubert_critical_props",
    "kesler_lee_Tc",
    "kesler_lee_Pc",
    "kesler_lee_critical_props",
    "cavett_Tc",
    "cavett_Pc",
    "cavett_critical_props",
    "estimate_critical_props",
    # Optional vectorized helpers from legacy module (if present)
    "riazi_daubert_Tc_array",
    "riazi_daubert_Pc_array",
    "riazi_daubert_Vc_array",
    # Codex additions
    "RiaziDaubertCoefficients",
    "estimate_from_mw_sg",
    "estimate_from_tb_sg",
    "edmister_acentric_factor",
]
