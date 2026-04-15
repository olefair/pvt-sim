"""Constant Composition Expansion (CCE) simulation.

CCE is a standard PVT laboratory test where a reservoir fluid sample
is expanded at constant temperature by reducing pressure in steps.
The composition remains constant throughout the test.

Key measurements:
- Relative volume (V/Vsat)
- Compressibility factor (Z)
- Liquid dropout (below bubble point)
- Y-function for gas condensates

Units Convention:
- Pressure: Pa
- Temperature: K
- Volume: m³/mol (molar) or relative (dimensionless)

References
----------
[1] McCain, W.D. (1990). The Properties of Petroleum Fluids.
    2nd Edition, PennWell Books.
[2] Pedersen, K.S., Christensen, P.L., and Shaikh, J.A. (2015).
    Phase Behavior of Petroleum Reservoir Fluids. 2nd Edition, CRC Press.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from ..core.constants import R
from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..models.component import Component
from ..flash.pt_flash import pt_flash
from ..properties.density import calculate_density


@dataclass
class CCEStepResult:
    """Results from a single CCE pressure step.

    Attributes:
        pressure: Pressure at this step (Pa)
        temperature: Temperature (K)
        relative_volume: V/Vsat (dimensionless)
        compressibility_Z: Compressibility factor
        liquid_volume_fraction: Liquid volume / total volume
        vapor_fraction: Vapor mole fraction (0 to 1)
        liquid_density: Liquid mass density (kg/m³)
        vapor_density: Vapor mass density (kg/m³)
        liquid_compressibility: Liquid phase Z factor
        vapor_compressibility: Vapor phase Z factor
        phase: Phase state ('liquid', 'vapor', 'two-phase')
        liquid_composition: Liquid-phase mole fractions when present
        vapor_composition: Vapor-phase mole fractions when present
        Y_function: Y-function for gas condensates (optional)
    """
    pressure: float
    temperature: float
    relative_volume: float
    compressibility_Z: float
    liquid_volume_fraction: float
    vapor_fraction: float
    liquid_density: float
    vapor_density: float
    liquid_compressibility: float
    vapor_compressibility: float
    phase: str
    liquid_composition: NDArray[np.float64] = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    vapor_composition: NDArray[np.float64] = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    Y_function: Optional[float] = None


@dataclass
class CCEResult:
    """Complete results from CCE simulation.

    Attributes:
        temperature: Test temperature (K)
        saturation_pressure: Bubble/dew point pressure (Pa)
        saturation_type: 'bubble' or 'dew'
        steps: List of results for each pressure step
        pressures: Array of pressures (Pa)
        relative_volumes: Array of V/Vsat
        liquid_dropouts: Array of liquid volume fractions below Psat
        compressibility_above_sat: Z factor above saturation
        feed_composition: Original feed composition
        converged: True if all steps converged
    """
    temperature: float
    saturation_pressure: float
    saturation_type: str
    steps: List[CCEStepResult]
    pressures: NDArray[np.float64]
    relative_volumes: NDArray[np.float64]
    liquid_dropouts: NDArray[np.float64]
    compressibility_above_sat: float
    feed_composition: NDArray[np.float64]
    converged: bool


def simulate_cce(
    composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    pressure_start: float,
    pressure_end: float,
    n_steps: int = 20,
    pressure_steps: Optional[NDArray[np.float64]] = None,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    saturation_pressure: Optional[float] = None,
) -> CCEResult:
    """Simulate Constant Composition Expansion test.

    The CCE test expands a fluid sample at constant temperature
    by reducing pressure in steps. At each step:
    1. Perform flash calculation (or single-phase if above Psat)
    2. Calculate volumes and properties
    3. Record relative volume V/Vsat

    Parameters
    ----------
    composition : ndarray
        Feed mole fractions (constant throughout test).
    temperature : float
        Test temperature in K.
    components : list of Component
        Component objects.
    eos : CubicEOS
        Equation of state instance.
    pressure_start : float
        Starting pressure in Pa (typically above saturation).
    pressure_end : float
        Ending pressure in Pa (typically well below saturation).
    n_steps : int
        Number of pressure steps.
    pressure_steps : ndarray, optional
        Explicit descending pressure schedule in Pa. When provided, it
        overrides the linear pressure_start/pressure_end/n_steps grid.
    binary_interaction : ndarray, optional
        Binary interaction parameters.
    saturation_pressure : float, optional
        Known saturation pressure. If not provided, will be estimated.

    Returns
    -------
    CCEResult
        Complete CCE test results.

    Raises
    ------
    ValidationError
        If inputs are invalid.
    ConvergenceError
        If flash calculations fail.

    Notes
    -----
    The CCE test is used to determine:
    - Saturation pressure (bubble or dew point)
    - Oil/gas compressibility above saturation
    - Liquid dropout curve for gas condensates
    - Two-phase compressibility below saturation

    For oils (bubble point system):
        - Above Psat: single-phase liquid
        - Below Psat: two-phase with gas liberation

    For gas condensates (dew point system):
        - Above Psat: single-phase vapor
        - Below Psat: two-phase with liquid dropout

    Examples
    --------
    >>> from pvtcore.models.component import load_components
    >>> from pvtcore.eos.peng_robinson import PengRobinsonEOS
    >>> components = load_components()
    >>> oil = [components['C1'], components['C3'], components['C10']]
    >>> eos = PengRobinsonEOS(oil)
    >>> z = np.array([0.5, 0.3, 0.2])
    >>> result = simulate_cce(z, 350.0, oil, eos, 30e6, 5e6, n_steps=25)
    >>> print(f"Saturation P: {result.saturation_pressure/1e6:.2f} MPa")
    """
    # Validate inputs
    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    T = float(temperature)

    pressures = _build_cce_pressure_schedule(
        pressure_start=pressure_start,
        pressure_end=pressure_end,
        n_steps=n_steps,
        pressure_steps=pressure_steps,
    )
    _validate_cce_inputs(z, T, pressures, components)
    pressure_start = float(pressures[0])
    pressure_end = float(pressures[-1])

    # Determine saturation pressure if not provided
    if saturation_pressure is None:
        P_sat, sat_type = _find_saturation_pressure(
            z, T, components, eos, binary_interaction,
            pressure_start, pressure_end
        )
    else:
        P_sat = saturation_pressure
        sat_type = _determine_saturation_type(z, T, P_sat, components, eos, binary_interaction)

    # Calculate volume at saturation (reference)
    V_sat = _calculate_molar_volume(
        P_sat, T, z, components, eos, binary_interaction,
        phase='liquid' if sat_type == 'bubble' else 'vapor'
    )

    # Run CCE at each pressure step
    steps = []
    all_converged = True

    for P in pressures:
        try:
            step_result = _cce_step(
                P, T, z, components, eos, binary_interaction,
                P_sat, V_sat, sat_type
            )
            steps.append(step_result)
        except (ConvergenceError, PhaseError) as e:
            # Create placeholder for failed step
            steps.append(CCEStepResult(
                pressure=P,
                temperature=T,
                relative_volume=np.nan,
                compressibility_Z=np.nan,
                liquid_volume_fraction=np.nan,
                vapor_fraction=np.nan,
                liquid_density=np.nan,
                vapor_density=np.nan,
                liquid_compressibility=np.nan,
                vapor_compressibility=np.nan,
                phase='unknown',
                liquid_composition=np.zeros_like(z),
                vapor_composition=np.zeros_like(z),
            ))
            all_converged = False

    # Extract arrays
    relative_volumes = np.array([s.relative_volume for s in steps])
    liquid_dropouts = np.array([s.liquid_volume_fraction for s in steps])

    # Compressibility above saturation
    above_sat_steps = [s for s in steps if s.pressure > P_sat and s.phase != 'unknown']
    if above_sat_steps:
        Z_above = np.mean([s.compressibility_Z for s in above_sat_steps])
    else:
        Z_above = np.nan

    return CCEResult(
        temperature=T,
        saturation_pressure=P_sat,
        saturation_type=sat_type,
        steps=steps,
        pressures=pressures,
        relative_volumes=relative_volumes,
        liquid_dropouts=liquid_dropouts,
        compressibility_above_sat=Z_above,
        feed_composition=z,
        converged=all_converged,
    )


def _cce_step(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_sat: float,
    V_sat: float,
    sat_type: str,
) -> CCEStepResult:
    """Execute single CCE pressure step."""
    P = float(pressure)
    T = float(temperature)
    z = composition

    if P > P_sat:
        # Above saturation: single phase
        phase = 'liquid' if sat_type == 'bubble' else 'vapor'

        # Get compressibility
        Z = eos.compressibility(P, T, z, phase=phase, binary_interaction=binary_interaction)
        if isinstance(Z, list):
            Z = Z[0] if phase == 'liquid' else Z[-1]

        # Molar volume
        V = Z * R.Pa_m3_per_mol_K * T / P

        # Density
        rho_result = calculate_density(P, T, z, components, eos, phase, binary_interaction)

        return CCEStepResult(
            pressure=P,
            temperature=T,
            relative_volume=V / V_sat,
            compressibility_Z=Z,
            liquid_volume_fraction=1.0 if phase == 'liquid' else 0.0,
            vapor_fraction=0.0 if phase == 'liquid' else 1.0,
            liquid_density=rho_result.mass_density if phase == 'liquid' else 0.0,
            vapor_density=rho_result.mass_density if phase == 'vapor' else 0.0,
            liquid_compressibility=Z if phase == 'liquid' else 0.0,
            vapor_compressibility=Z if phase == 'vapor' else 0.0,
            phase=phase,
            liquid_composition=z.copy() if phase == 'liquid' else np.zeros_like(z),
            vapor_composition=z.copy() if phase == 'vapor' else np.zeros_like(z),
        )
    else:
        # Below saturation: two-phase flash
        flash_result = pt_flash(P, T, z, components, eos,
                               binary_interaction=binary_interaction)

        if flash_result.phase in ['liquid', 'vapor']:
            # Single phase result (edge case)
            phase = flash_result.phase
            Z = eos.compressibility(P, T, z, phase=phase, binary_interaction=binary_interaction)
            if isinstance(Z, list):
                Z = Z[0] if phase == 'liquid' else Z[-1]

            V = Z * R.Pa_m3_per_mol_K * T / P
            rho_result = calculate_density(P, T, z, components, eos, phase, binary_interaction)

            return CCEStepResult(
                pressure=P,
                temperature=T,
                relative_volume=V / V_sat,
                compressibility_Z=Z,
                liquid_volume_fraction=1.0 if phase == 'liquid' else 0.0,
                vapor_fraction=flash_result.vapor_fraction,
                liquid_density=rho_result.mass_density if phase == 'liquid' else 0.0,
                vapor_density=rho_result.mass_density if phase == 'vapor' else 0.0,
                liquid_compressibility=Z if phase == 'liquid' else 0.0,
                vapor_compressibility=Z if phase == 'vapor' else 0.0,
                phase=phase,
                liquid_composition=z.copy() if phase == 'liquid' else np.zeros_like(z),
                vapor_composition=z.copy() if phase == 'vapor' else np.zeros_like(z),
            )

        # Two-phase
        nv = flash_result.vapor_fraction
        x = flash_result.liquid_composition
        y = flash_result.vapor_composition

        # Get phase compressibilities
        Z_L = eos.compressibility(P, T, x, phase='liquid', binary_interaction=binary_interaction)
        Z_V = eos.compressibility(P, T, y, phase='vapor', binary_interaction=binary_interaction)
        if isinstance(Z_L, list):
            Z_L = Z_L[0]
        if isinstance(Z_V, list):
            Z_V = Z_V[-1]

        # Phase volumes (per mole of feed)
        V_L = (1 - nv) * Z_L * R.Pa_m3_per_mol_K * T / P
        V_V = nv * Z_V * R.Pa_m3_per_mol_K * T / P
        V_total = V_L + V_V

        # Overall Z
        Z_overall = P * V_total / (R.Pa_m3_per_mol_K * T)

        # Volume fractions
        liquid_vol_frac = V_L / V_total if V_total > 0 else 0.0

        # Densities
        rho_L = calculate_density(P, T, x, components, eos, 'liquid', binary_interaction)
        rho_V = calculate_density(P, T, y, components, eos, 'vapor', binary_interaction)

        # Y-function for gas condensates
        Y_func = None
        if sat_type == 'dew' and liquid_vol_frac > 0:
            # Y = (P_sat - P) / (P * (V/V_sat - 1))
            V_rel = V_total / V_sat
            if V_rel > 1.001:
                Y_func = (P_sat - P) / (P * (V_rel - 1))

        return CCEStepResult(
            pressure=P,
            temperature=T,
            relative_volume=V_total / V_sat,
            compressibility_Z=Z_overall,
            liquid_volume_fraction=liquid_vol_frac,
            vapor_fraction=nv,
            liquid_density=rho_L.mass_density,
            vapor_density=rho_V.mass_density,
            liquid_compressibility=Z_L,
            vapor_compressibility=Z_V,
            phase='two-phase',
            liquid_composition=x.copy(),
            vapor_composition=y.copy(),
            Y_function=Y_func,
        )


def _find_saturation_pressure(
    composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_high: float,
    P_low: float,
) -> tuple[float, str]:
    """Find saturation pressure by bisection."""
    from ..flash.bubble_point import calculate_bubble_point
    from ..flash.dew_point import calculate_dew_point

    candidates: list[tuple[float, str]] = []

    try:
        result = calculate_bubble_point(
            temperature, composition, components, eos,
            binary_interaction=binary_interaction,
        )
        candidates.append((float(result.pressure), 'bubble'))
    except (ConvergenceError, PhaseError):
        pass

    try:
        result = calculate_dew_point(
            temperature, composition, components, eos,
            binary_interaction=binary_interaction,
        )
        candidates.append((float(result.pressure), 'dew'))
    except (ConvergenceError, PhaseError):
        pass

    if candidates:
        in_schedule = [
            (pressure, sat_type)
            for pressure, sat_type in candidates
            if P_low < pressure < P_high
        ]
        if in_schedule:
            candidates = in_schedule

        if len(candidates) == 1:
            return candidates[0]

        avg_MW = sum(composition[i] * comp.MW for i, comp in enumerate(components))
        preferred_type = 'bubble' if avg_MW > 50 else 'dew'
        for pressure, sat_type in candidates:
            if sat_type == preferred_type:
                return pressure, sat_type
        return candidates[0]

    # Fallback: estimate from flash behavior
    P_mid = (P_high + P_low) / 2
    for _ in range(20):
        flash = pt_flash(P_mid, temperature, composition, components, eos,
                        binary_interaction=binary_interaction)
        if flash.phase == 'liquid':
            # Need to go lower
            P_high = P_mid
        elif flash.phase == 'vapor':
            # Need to go higher
            P_low = P_mid
        else:
            # Two-phase - getting close
            break
        P_mid = (P_high + P_low) / 2

    avg_MW = sum(composition[i] * comp.MW for i, comp in enumerate(components))
    sat_type = 'bubble' if avg_MW > 50 else 'dew'

    return P_mid, sat_type


def _determine_saturation_type(
    composition: NDArray[np.float64],
    temperature: float,
    P_sat: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> str:
    """Determine if saturation is bubble or dew point."""
    # Flash slightly below Psat
    P_test = P_sat * 0.95
    flash = pt_flash(P_test, temperature, composition, components, eos,
                    binary_interaction=binary_interaction)

    if flash.phase == 'two-phase':
        # If mostly liquid, it's bubble point
        if flash.vapor_fraction < 0.5:
            return 'bubble'
        else:
            return 'dew'
    elif flash.phase == 'liquid':
        return 'bubble'
    else:
        return 'dew'


def _calculate_molar_volume(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    phase: str,
) -> float:
    """Calculate molar volume for given conditions."""
    Z = eos.compressibility(pressure, temperature, composition,
                           phase=phase, binary_interaction=binary_interaction)
    if isinstance(Z, list):
        Z = Z[0] if phase == 'liquid' else Z[-1]

    return Z * R.Pa_m3_per_mol_K * temperature / pressure


def _validate_cce_inputs(
    composition: NDArray[np.float64],
    temperature: float,
    pressure_steps: NDArray[np.float64],
    components: List[Component],
) -> None:
    """Validate CCE inputs."""
    if temperature <= 0:
        raise ValidationError("Temperature must be positive", parameter="temperature")
    if len(pressure_steps) < 2:
        raise ValidationError(
            "CCE requires at least two pressure points",
            parameter="pressure_steps",
        )
    if np.any(pressure_steps <= 0):
        raise ValidationError("Pressures must be positive", parameter="pressure")
    if np.any(pressure_steps[:-1] <= pressure_steps[1:]):
        raise ValidationError(
            "CCE pressure schedule must be strictly descending",
            parameter="pressure"
        )
    if len(composition) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition"
        )


def _build_cce_pressure_schedule(
    *,
    pressure_start: float,
    pressure_end: float,
    n_steps: int,
    pressure_steps: Optional[NDArray[np.float64]],
) -> NDArray[np.float64]:
    """Build the CCE pressure schedule from either an explicit list or a linear grid."""
    if pressure_steps is not None:
        pressures = np.asarray(pressure_steps, dtype=np.float64)
        if pressures.ndim != 1:
            raise ValidationError(
                "pressure_steps must be a one-dimensional array",
                parameter="pressure_steps",
            )
        return pressures
    return np.linspace(pressure_start, pressure_end, n_steps, dtype=np.float64)
