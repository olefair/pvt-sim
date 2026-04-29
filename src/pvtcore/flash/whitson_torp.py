"""Whitson-Torp K-value calculations.

The Whitson-Torp equation is a petroleum-engineering K-value correlation,
not an EOS fugacity solve. Pressures in the published equation are psia and
temperatures are absolute; this module accepts the simulator's internal
Pa/K values and converts only at the equation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pvtcore.core.constants import PSI_TO_PA


ATM_PRESSURE_PSIA = 14.7
ATM_PRESSURE_PA = ATM_PRESSURE_PSIA * PSI_TO_PA


@dataclass(frozen=True)
class WhitsonTorpFlashResult:
    pressure_pa: float
    temperature_k: float
    vapor_fraction: float
    liquid_fraction: float
    liquid_composition: np.ndarray
    vapor_composition: np.ndarray
    k_values: np.ndarray
    rachford_rice_residual: float
    phase_state: str


@dataclass(frozen=True)
class WhitsonTorpDLStepResult:
    step_index: int
    pressure_pa: float
    feed_moles: float
    vapor_moles_actual: float
    liquid_moles_actual: float
    flash: WhitsonTorpFlashResult


def standing_convergence_pressure_psia(mw_c7plus_g_per_mol: float) -> float:
    """Standing convergence pressure from C7+ molecular weight."""
    mw = float(mw_c7plus_g_per_mol)
    if not np.isfinite(mw) or mw <= 0.0:
        raise ValueError("C7+ molecular weight must be finite and positive")
    pk = 60.0 * mw - 4200.0
    if not np.isfinite(pk) or pk <= ATM_PRESSURE_PSIA:
        raise ValueError(
            "Standing convergence pressure must be greater than 14.7 psia; "
            f"got {pk:.6g} psia from MW_C7+={mw:.6g}"
        )
    return pk


def standing_convergence_pressure_pa(mw_c7plus_g_per_mol: float) -> float:
    return standing_convergence_pressure_psia(mw_c7plus_g_per_mol) * PSI_TO_PA


def whitson_torp_a(pressure_pa: float, convergence_pressure_pa: float) -> float:
    """Return the Whitson-Torp A factor."""
    p_psia = float(pressure_pa) / PSI_TO_PA
    pk_psia = float(convergence_pressure_pa) / PSI_TO_PA
    if pk_psia <= ATM_PRESSURE_PSIA:
        raise ValueError("convergence pressure must be greater than 14.7 psia")
    if p_psia < ATM_PRESSURE_PSIA:
        raise ValueError("Whitson-Torp pressure must be at least 14.7 psia")
    if p_psia > pk_psia:
        raise ValueError("Whitson-Torp pressure must not exceed convergence pressure")

    ratio = (p_psia - ATM_PRESSURE_PSIA) / (pk_psia - ATM_PRESSURE_PSIA)
    ratio = min(max(ratio, 0.0), 1.0)
    return 1.0 - ratio ** 0.6


def _component_arrays(components: list[object]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    tc = np.asarray([float(component.Tc) for component in components], dtype=float)
    pc = np.asarray([float(component.Pc) for component in components], dtype=float)
    omega = np.asarray([float(component.omega) for component in components], dtype=float)
    if not np.isfinite(tc).all() or np.any(tc <= 0.0):
        raise ValueError("All components must define positive critical temperatures")
    if not np.isfinite(pc).all() or np.any(pc <= 0.0):
        raise ValueError("All components must define positive critical pressures")
    if not np.isfinite(omega).all():
        raise ValueError("All components must define finite acentric factors")
    return tc, pc, omega


def whitson_torp_k_values(
    *,
    pressure_pa: float,
    temperature_k: float,
    components: list[object],
    convergence_pressure_pa: float,
) -> np.ndarray:
    """Calculate Whitson-Torp K-values for the supplied components."""
    pressure = float(pressure_pa)
    temperature = float(temperature_k)
    pk = float(convergence_pressure_pa)
    if pressure <= 0.0 or temperature <= 0.0 or pk <= 0.0:
        raise ValueError("pressure, temperature, and convergence pressure must be positive")

    a = whitson_torp_a(pressure, pk)
    tc, pc, omega = _component_arrays(components)
    return (pc / pk) ** (a - 1.0) * (pc / pressure) * np.exp(
        5.37 * a * (1.0 + omega) * (1.0 - tc / temperature)
    )


def _normalize_composition(composition: np.ndarray) -> np.ndarray:
    z = np.asarray(composition, dtype=float)
    total = float(z.sum())
    if not np.isfinite(total) or total <= 0.0:
        raise ValueError("composition must have a positive finite sum")
    z = z / total
    if np.any(z < 0.0):
        raise ValueError("composition cannot contain negative entries")
    return z


def _bubble_residual(
    pressure_pa: float,
    *,
    temperature_k: float,
    composition: np.ndarray,
    components: list[object],
    convergence_pressure_pa: float,
) -> float:
    k = whitson_torp_k_values(
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
        components=components,
        convergence_pressure_pa=convergence_pressure_pa,
    )
    return float(np.dot(composition, k) - 1.0)


def solve_whitson_torp_bubble_point(
    *,
    temperature_k: float,
    composition: np.ndarray,
    components: list[object],
    convergence_pressure_pa: float,
    tolerance: float = 1.0e-8,
    max_iterations: int = 100,
) -> tuple[float, np.ndarray, np.ndarray]:
    """Solve the bubble-point pressure and incipient vapor composition."""
    z = _normalize_composition(composition)
    pk = float(convergence_pressure_pa)
    if pk <= ATM_PRESSURE_PA:
        raise ValueError("convergence pressure must be greater than 14.7 psia")

    low = ATM_PRESSURE_PA * (1.0 + 1.0e-10)
    high = pk * (1.0 - 1.0e-8)
    scan = np.geomspace(low, high, 600)
    p_left = float(scan[0])
    f_left = _bubble_residual(
        p_left,
        temperature_k=temperature_k,
        composition=z,
        components=components,
        convergence_pressure_pa=pk,
    )
    bracket: tuple[float, float] | None = None
    for p_right_raw in scan[1:]:
        p_right = float(p_right_raw)
        f_right = _bubble_residual(
            p_right,
            temperature_k=temperature_k,
            composition=z,
            components=components,
            convergence_pressure_pa=pk,
        )
        if f_left == 0.0:
            bracket = (p_left, p_left)
            break
        if f_left * f_right < 0.0:
            bracket = (p_left, p_right)
            break
        p_left, f_left = p_right, f_right

    if bracket is None:
        raise RuntimeError(
            "Could not bracket a non-trivial Whitson-Torp bubble point below convergence pressure"
        )

    lo, hi = bracket
    if lo == hi:
        pressure = lo
    else:
        f_lo = _bubble_residual(
            lo,
            temperature_k=temperature_k,
            composition=z,
            components=components,
            convergence_pressure_pa=pk,
        )
        pressure = 0.5 * (lo + hi)
        for _ in range(max_iterations):
            pressure = 0.5 * (lo + hi)
            f_mid = _bubble_residual(
                pressure,
                temperature_k=temperature_k,
                composition=z,
                components=components,
                convergence_pressure_pa=pk,
            )
            if abs(f_mid) <= tolerance or abs(hi - lo) <= tolerance * max(pressure, 1.0):
                break
            if f_lo * f_mid <= 0.0:
                hi = pressure
            else:
                lo = pressure
                f_lo = f_mid

    k = whitson_torp_k_values(
        pressure_pa=pressure,
        temperature_k=temperature_k,
        components=components,
        convergence_pressure_pa=pk,
    )
    vapor = z * k
    vapor = vapor / float(vapor.sum())
    return float(pressure), k, vapor


def _rachford_rice(vapor_fraction: float, z: np.ndarray, k: np.ndarray) -> float:
    return float(np.sum(z * (k - 1.0) / (1.0 + vapor_fraction * (k - 1.0))))


def flash_whitson_torp(
    *,
    pressure_pa: float,
    temperature_k: float,
    composition: np.ndarray,
    components: list[object],
    convergence_pressure_pa: float,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
) -> WhitsonTorpFlashResult:
    """Flash a feed using Whitson-Torp K-values and Rachford-Rice."""
    z = _normalize_composition(composition)
    k = whitson_torp_k_values(
        pressure_pa=pressure_pa,
        temperature_k=temperature_k,
        components=components,
        convergence_pressure_pa=convergence_pressure_pa,
    )
    f0 = _rachford_rice(0.0, z, k)
    f1 = _rachford_rice(1.0, z, k)

    if f0 <= 0.0:
        beta = 0.0
        phase_state = "liquid"
        residual = f0
    elif f1 >= 0.0:
        beta = 1.0
        phase_state = "vapor"
        residual = f1
    else:
        lo, hi = 0.0, 1.0
        beta = 0.5
        residual = _rachford_rice(beta, z, k)
        for _ in range(max_iterations):
            beta = 0.5 * (lo + hi)
            residual = _rachford_rice(beta, z, k)
            if abs(residual) <= tolerance or abs(hi - lo) <= tolerance:
                break
            if f0 * residual <= 0.0:
                hi = beta
            else:
                lo = beta
                f0 = residual
        phase_state = "two_phase"

    denom = 1.0 + beta * (k - 1.0)
    liquid = z / denom
    vapor = k * liquid
    liquid = liquid / float(liquid.sum())
    vapor = vapor / float(vapor.sum())
    return WhitsonTorpFlashResult(
        pressure_pa=float(pressure_pa),
        temperature_k=float(temperature_k),
        vapor_fraction=float(beta),
        liquid_fraction=float(1.0 - beta),
        liquid_composition=liquid,
        vapor_composition=vapor,
        k_values=k,
        rachford_rice_residual=float(residual),
        phase_state=phase_state,
    )


def simulate_whitson_torp_differential_liberation(
    *,
    pressure_points_pa: list[float],
    temperature_k: float,
    composition: np.ndarray,
    components: list[object],
    convergence_pressure_pa: float,
    tolerance: float = 1.0e-12,
    max_iterations: int = 100,
) -> list[WhitsonTorpDLStepResult]:
    """Run flash-removal DL steps from highest to lowest pressure."""
    if any(float(p) < ATM_PRESSURE_PA for p in pressure_points_pa):
        raise ValueError("Whitson-Torp DL pressure points must be at least 14.7 psia")
    if any(
        float(pressure_points_pa[i]) <= float(pressure_points_pa[i + 1])
        for i in range(len(pressure_points_pa) - 1)
    ):
        raise ValueError("Whitson-Torp DL pressure points must be strictly descending")

    feed_moles = 1.0
    feed_composition = _normalize_composition(composition)
    steps: list[WhitsonTorpDLStepResult] = []
    for idx, pressure in enumerate(pressure_points_pa, start=1):
        flash = flash_whitson_torp(
            pressure_pa=float(pressure),
            temperature_k=temperature_k,
            composition=feed_composition,
            components=components,
            convergence_pressure_pa=convergence_pressure_pa,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        vapor_moles = feed_moles * flash.vapor_fraction
        liquid_moles = feed_moles * flash.liquid_fraction
        steps.append(
            WhitsonTorpDLStepResult(
                step_index=idx,
                pressure_pa=float(pressure),
                feed_moles=float(feed_moles),
                vapor_moles_actual=float(vapor_moles),
                liquid_moles_actual=float(liquid_moles),
                flash=flash,
            )
        )
        if liquid_moles <= 0.0:
            break
        feed_moles = liquid_moles
        feed_composition = flash.liquid_composition
    return steps
