"""Invariant checks and solver certificates.

These checks are designed to be fast, non-intrusive sanity checks that
can run on every solver output without altering numerical behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from ..eos.base import CubicEOS


DEFAULT_TOLERANCES = {
    "composition_sum": 1e-8,
    "phase_fraction": 1e-8,
    "material_balance": 1e-8,
    "fugacity_rel_max": 1e-5,
    "fugacity_rel_mean": 1e-5,
    "tpd_residual": 1e-8,
}


@dataclass
class InvariantCheck:
    """Single invariant check result."""

    name: str
    value: float
    threshold: float
    passed: bool
    applicable: bool = True
    details: Optional[Dict[str, object]] = None

    def to_dict(self) -> Dict[str, object]:
        """Serialize to a JSON-friendly dict."""
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
            "applicable": self.applicable,
            "details": self.details,
        }


@dataclass
class SolverCertificate:
    """Compact certificate containing solver status and invariant checks."""

    status: str
    iterations: int
    residual: float
    checks: List[InvariantCheck] = field(default_factory=list)
    passed: bool = True

    def to_dict(self) -> Dict[str, object]:
        """Serialize to a JSON-friendly dict."""
        return {
            "status": self.status,
            "iterations": self.iterations,
            "residual": self.residual,
            "passed": self.passed,
            "checks": [check.to_dict() for check in self.checks],
        }


def _is_all_zero(vec: np.ndarray, tol: float = 1e-14) -> bool:
    return bool(np.allclose(vec, 0.0, atol=tol))


def _coerce_array(values: Iterable[float]) -> np.ndarray:
    return np.asarray(values, dtype=float)


def _safe_float(value: float) -> float:
    try:
        return float(value)
    except Exception:
        return float("nan")


def _merge_tolerances(custom: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    merged = DEFAULT_TOLERANCES.copy()
    if custom:
        merged.update({k: float(v) for k, v in custom.items()})
    return merged


def check_composition_sum(
    name: str,
    composition: Iterable[float],
    tol: float,
    allow_all_zero: bool = False,
) -> InvariantCheck:
    comp = _coerce_array(composition)

    if comp.size == 0:
        return InvariantCheck(
            name=name,
            value=float("nan"),
            threshold=tol,
            passed=False,
            applicable=False,
            details={"reason": "empty"},
        )

    if allow_all_zero and _is_all_zero(comp):
        return InvariantCheck(
            name=name,
            value=0.0,
            threshold=tol,
            passed=True,
            applicable=False,
            details={"reason": "all_zero"},
        )

    if not np.all(np.isfinite(comp)):
        return InvariantCheck(
            name=name,
            value=float("inf"),
            threshold=tol,
            passed=False,
            applicable=True,
            details={"reason": "non_finite"},
        )

    value = abs(float(comp.sum()) - 1.0)
    return InvariantCheck(
        name=name,
        value=value,
        threshold=tol,
        passed=value <= tol,
        applicable=True,
    )


def check_phase_fraction_bounds(beta: float, tol: float) -> InvariantCheck:
    beta = _safe_float(beta)
    if not np.isfinite(beta):
        return InvariantCheck(
            name="phase_fraction_bounds",
            value=float("inf"),
            threshold=tol,
            passed=False,
            applicable=True,
            details={"reason": "non_finite"},
        )

    violation = max(0.0, -beta, beta - 1.0)
    return InvariantCheck(
        name="phase_fraction_bounds",
        value=violation,
        threshold=tol,
        passed=violation <= tol,
        applicable=True,
        details={"beta": beta},
    )


def check_material_balance(
    z: Iterable[float],
    x: Iterable[float],
    y: Iterable[float],
    beta: float,
    tol: float,
) -> InvariantCheck:
    z_arr = _coerce_array(z)
    x_arr = _coerce_array(x)
    y_arr = _coerce_array(y)

    if not (np.all(np.isfinite(z_arr)) and np.all(np.isfinite(x_arr)) and np.all(np.isfinite(y_arr))):
        return InvariantCheck(
            name="material_balance_max",
            value=float("inf"),
            threshold=tol,
            passed=False,
            applicable=True,
            details={"reason": "non_finite"},
        )

    beta = _safe_float(beta)
    if not np.isfinite(beta):
        return InvariantCheck(
            name="material_balance_max",
            value=float("inf"),
            threshold=tol,
            passed=False,
            applicable=True,
            details={"reason": "beta_non_finite"},
        )

    z_calc = (1.0 - beta) * x_arr + beta * y_arr
    max_abs = float(np.max(np.abs(z_arr - z_calc)))
    return InvariantCheck(
        name="material_balance_max",
        value=max_abs,
        threshold=tol,
        passed=max_abs <= tol,
        applicable=True,
    )


def check_fugacity_equality(
    x: Iterable[float],
    y: Iterable[float],
    phi_liquid: Iterable[float],
    phi_vapor: Iterable[float],
    tol_max: float,
    tol_mean: float,
    min_component: float = 1e-12,
) -> Tuple[InvariantCheck, InvariantCheck]:
    x_arr = _coerce_array(x)
    y_arr = _coerce_array(y)
    phi_l = _coerce_array(phi_liquid)
    phi_v = _coerce_array(phi_vapor)

    if not (np.all(np.isfinite(x_arr)) and np.all(np.isfinite(y_arr))):
        checks = (
            InvariantCheck(
                name="fugacity_rel_max",
                value=float("inf"),
                threshold=tol_max,
                passed=False,
                applicable=True,
                details={"reason": "composition_non_finite"},
            ),
            InvariantCheck(
                name="fugacity_rel_mean",
                value=float("inf"),
                threshold=tol_mean,
                passed=False,
                applicable=True,
                details={"reason": "composition_non_finite"},
            ),
        )
        return checks

    if not (np.all(np.isfinite(phi_l)) and np.all(np.isfinite(phi_v))):
        checks = (
            InvariantCheck(
                name="fugacity_rel_max",
                value=float("inf"),
                threshold=tol_max,
                passed=False,
                applicable=True,
                details={"reason": "phi_non_finite"},
            ),
            InvariantCheck(
                name="fugacity_rel_mean",
                value=float("inf"),
                threshold=tol_mean,
                passed=False,
                applicable=True,
                details={"reason": "phi_non_finite"},
            ),
        )
        return checks

    f_liquid = phi_l * x_arr
    f_vapor = phi_v * y_arr

    denom = np.maximum(np.maximum(np.abs(f_liquid), np.abs(f_vapor)), 1e-30)
    rel = np.abs(f_liquid - f_vapor) / denom
    mask = (x_arr > min_component) & (y_arr > min_component) & np.isfinite(rel)

    if not np.any(mask):
        checks = (
            InvariantCheck(
                name="fugacity_rel_max",
                value=0.0,
                threshold=tol_max,
                passed=True,
                applicable=False,
                details={"reason": "no_components"},
            ),
            InvariantCheck(
                name="fugacity_rel_mean",
                value=0.0,
                threshold=tol_mean,
                passed=True,
                applicable=False,
                details={"reason": "no_components"},
            ),
        )
        return checks

    max_rel = float(np.max(rel[mask]))
    mean_rel = float(np.mean(rel[mask]))
    details = {"components": float(np.count_nonzero(mask))}
    return (
        InvariantCheck(
            name="fugacity_rel_max",
            value=max_rel,
            threshold=tol_max,
            passed=max_rel <= tol_max,
            applicable=True,
            details=details,
        ),
        InvariantCheck(
            name="fugacity_rel_mean",
            value=mean_rel,
            threshold=tol_mean,
            passed=mean_rel <= tol_mean,
            applicable=True,
            details=details,
        ),
    )


def check_eos_sanity(
    eos: CubicEOS,
    pressure: float,
    temperature: float,
    compositions_by_phase: Dict[str, Iterable[float]],
    binary_interaction: Optional[np.ndarray] = None,
) -> List[InvariantCheck]:
    z_values: List[float] = []
    v_values: List[float] = []
    for phase, comp in compositions_by_phase.items():
        comp_arr = _coerce_array(comp)
        if comp_arr.size == 0 or _is_all_zero(comp_arr):
            continue
        try:
            z_value = float(eos.compressibility(
                pressure, temperature, comp_arr, phase=phase, binary_interaction=binary_interaction
            ))
            v_value = float(eos.molar_volume(
                pressure, temperature, comp_arr, phase=phase, binary_interaction=binary_interaction
            ))
        except Exception:
            z_value = float("nan")
            v_value = float("nan")
        z_values.append(z_value)
        v_values.append(v_value)

    if not z_values or not v_values:
        return [
            InvariantCheck(
                name="eos_z_positive",
                value=float("nan"),
                threshold=0.0,
                passed=False,
                applicable=False,
                details={"reason": "no_phases"},
            ),
            InvariantCheck(
                name="eos_volume_positive",
                value=float("nan"),
                threshold=0.0,
                passed=False,
                applicable=False,
                details={"reason": "no_phases"},
            ),
        ]

    min_z = float(np.min(z_values))
    min_v = float(np.min(v_values))

    if not np.isfinite(min_z):
        z_violation = float("inf")
    else:
        z_violation = max(0.0, -min_z)

    if not np.isfinite(min_v):
        v_violation = float("inf")
    else:
        v_violation = max(0.0, -min_v)

    return [
        InvariantCheck(
            name="eos_z_positive",
            value=z_violation,
            threshold=0.0,
            passed=z_violation <= 0.0,
            applicable=True,
            details={"min_z": min_z},
        ),
        InvariantCheck(
            name="eos_volume_positive",
            value=v_violation,
            threshold=0.0,
            passed=v_violation <= 0.0,
            applicable=True,
            details={"min_volume": min_v},
        ),
    ]


def check_stability_consistency(
    phase: str,
    stable_as_liquid: Optional[bool],
    stable_as_vapor: Optional[bool],
) -> InvariantCheck:
    if stable_as_liquid is None or stable_as_vapor is None:
        return InvariantCheck(
            name="stability_consistency",
            value=0.0,
            threshold=0.0,
            passed=True,
            applicable=False,
            details={"reason": "missing_inputs"},
        )

    stable_liquid = bool(stable_as_liquid)
    stable_vapor = bool(stable_as_vapor)

    if phase == "two-phase":
        violation = 1.0 if (stable_liquid or stable_vapor) else 0.0
    else:
        violation = 1.0 if not (stable_liquid or stable_vapor) else 0.0

    return InvariantCheck(
        name="stability_consistency",
        value=violation,
        threshold=0.0,
        passed=violation == 0.0,
        applicable=True,
        details={
            "phase": phase,
            "stable_as_liquid": float(stable_liquid),
            "stable_as_vapor": float(stable_vapor),
        },
    )


def build_flash_certificate(
    result,
    eos: CubicEOS,
    binary_interaction: Optional[np.ndarray] = None,
    stable_as_liquid: Optional[bool] = None,
    stable_as_vapor: Optional[bool] = None,
    tolerances: Optional[Dict[str, float]] = None,
) -> SolverCertificate:
    """Build a SolverCertificate for a PT flash result."""
    from ..stability import is_stable

    tol = _merge_tolerances(tolerances)
    checks: List[InvariantCheck] = []

    checks.append(check_composition_sum(
        "composition_sum_z",
        result.feed_composition,
        tol["composition_sum"],
        allow_all_zero=False,
    ))
    checks.append(check_composition_sum(
        "composition_sum_x",
        result.liquid_composition,
        tol["composition_sum"],
        allow_all_zero=True,
    ))
    checks.append(check_composition_sum(
        "composition_sum_y",
        result.vapor_composition,
        tol["composition_sum"],
        allow_all_zero=True,
    ))

    checks.append(check_phase_fraction_bounds(result.vapor_fraction, tol["phase_fraction"]))
    checks.append(check_material_balance(
        result.feed_composition,
        result.liquid_composition,
        result.vapor_composition,
        result.vapor_fraction,
        tol["material_balance"],
    ))

    if result.phase == "two-phase":
        fug_max, fug_mean = check_fugacity_equality(
            result.liquid_composition,
            result.vapor_composition,
            result.liquid_fugacity,
            result.vapor_fugacity,
            tol["fugacity_rel_max"],
            tol["fugacity_rel_mean"],
        )
        checks.extend([fug_max, fug_mean])
    else:
        checks.extend([
            InvariantCheck(
                name="fugacity_rel_max",
                value=0.0,
                threshold=tol["fugacity_rel_max"],
                passed=True,
                applicable=False,
                details={"reason": "single_phase"},
            ),
            InvariantCheck(
                name="fugacity_rel_mean",
                value=0.0,
                threshold=tol["fugacity_rel_mean"],
                passed=True,
                applicable=False,
                details={"reason": "single_phase"},
            ),
        ])

    phase_comps = {}
    if result.phase == "two-phase":
        phase_comps = {
            "liquid": result.liquid_composition,
            "vapor": result.vapor_composition,
        }
    elif result.phase == "liquid":
        phase_comps = {"liquid": result.liquid_composition}
    else:
        phase_comps = {"vapor": result.vapor_composition}

    checks.extend(check_eos_sanity(
        eos,
        result.pressure,
        result.temperature,
        phase_comps,
        binary_interaction=binary_interaction,
    ))

    if stable_as_liquid is None or stable_as_vapor is None:
        try:
            stable_as_liquid = is_stable(
                result.feed_composition,
                result.pressure,
                result.temperature,
                eos,
                feed_phase="liquid",
                binary_interaction=binary_interaction,
            )
            stable_as_vapor = is_stable(
                result.feed_composition,
                result.pressure,
                result.temperature,
                eos,
                feed_phase="vapor",
                binary_interaction=binary_interaction,
            )
        except Exception:
            stable_as_liquid = None
            stable_as_vapor = None

    checks.append(check_stability_consistency(
        result.phase,
        stable_as_liquid,
        stable_as_vapor,
    ))

    passed = all(check.passed for check in checks if check.applicable)

    status_name = getattr(result.status, "name", str(result.status))
    return SolverCertificate(
        status=status_name,
        iterations=int(result.iterations),
        residual=float(result.residual),
        checks=checks,
        passed=passed,
    )


def build_saturation_certificate(
    kind: str,
    result,
    eos: CubicEOS,
    binary_interaction: Optional[np.ndarray] = None,
    tolerances: Optional[Dict[str, float]] = None,
) -> SolverCertificate:
    """Build a SolverCertificate for bubble/dew point results."""
    tol = _merge_tolerances(tolerances)
    checks: List[InvariantCheck] = []

    checks.append(check_composition_sum(
        "composition_sum_liquid",
        result.liquid_composition,
        tol["composition_sum"],
        allow_all_zero=False,
    ))
    checks.append(check_composition_sum(
        "composition_sum_vapor",
        result.vapor_composition,
        tol["composition_sum"],
        allow_all_zero=False,
    ))

    try:
        phi_liquid = eos.fugacity_coefficient(
            result.pressure,
            result.temperature,
            result.liquid_composition,
            phase="liquid",
            binary_interaction=binary_interaction,
        )
    except Exception:
        phi_liquid = np.full_like(np.asarray(result.liquid_composition, dtype=float), np.nan)

    try:
        phi_vapor = eos.fugacity_coefficient(
            result.pressure,
            result.temperature,
            result.vapor_composition,
            phase="vapor",
            binary_interaction=binary_interaction,
        )
    except Exception:
        phi_vapor = np.full_like(np.asarray(result.vapor_composition, dtype=float), np.nan)

    fug_max, fug_mean = check_fugacity_equality(
        result.liquid_composition,
        result.vapor_composition,
        phi_liquid,
        phi_vapor,
        tol["fugacity_rel_max"],
        tol["fugacity_rel_mean"],
    )
    checks.extend([fug_max, fug_mean])

    checks.extend(check_eos_sanity(
        eos,
        result.pressure,
        result.temperature,
        {
            "liquid": result.liquid_composition,
            "vapor": result.vapor_composition,
        },
        binary_interaction=binary_interaction,
    ))

    tpd_value = abs(float(result.residual))
    checks.append(InvariantCheck(
        name=f"{kind}_tpd_residual",
        value=tpd_value,
        threshold=tol["tpd_residual"],
        passed=tpd_value <= tol["tpd_residual"],
        applicable=True,
    ))

    passed = all(check.passed for check in checks if check.applicable)
    status_name = getattr(result.status, "name", str(result.status))

    return SolverCertificate(
        status=status_name,
        iterations=int(result.iterations),
        residual=float(result.residual),
        checks=checks,
        passed=passed,
    )
