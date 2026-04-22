"""Differential Liberation (DL) simulation.

DL is a standard PVT laboratory test for oil systems where gas is
removed at each pressure step, simulating reservoir depletion.

At each pressure step:
1. Flash the current feed at reservoir temperature
2. Remove all liberated gas
3. The remaining liquid becomes the feed for the next step

Key measurements:
- Solution GOR (Rs)
- Oil formation volume factor (Bo)
- Oil density
- Gas gravity
- Total volume factor (Bt)

Units Convention:
- Pressure: Pa
- Temperature: K
- GOR: sm³/sm³ at standard conditions
- Bo: m³/sm³ (reservoir/stock-tank)

References
----------
[1] McCain, W.D. (1990). The Properties of Petroleum Fluids.
[2] Pedersen et al. (2015). Phase Behavior of Petroleum Reservoir Fluids.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from numpy.typing import NDArray

from ..core.constants import R, SC_IMPERIAL
from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..models.component import Component
from ..flash.pt_flash import pt_flash
from ..properties.density import calculate_density, mixture_molecular_weight


# 1 sm³/sm³ = 5.615 scf/STB (1 STB = 5.615 ft³).
SCF_PER_STB = 5.615


@dataclass
class DLStepResult:
    """Results from a single DL pressure step.

    Pressure Pa, temperature K, density kg/m³.
    Rs sm³/sm³; Rs_scf_stb is scf/STB (Rs * SCF_PER_STB).
    Bo / Bt rb/STB. gas_gravity, gas_Z dimensionless.
    """
    pressure: float
    temperature: float
    Rs: float
    Rs_scf_stb: float
    Bo: float
    oil_density: float
    gas_gravity: float
    gas_Z: float
    Bt: float
    liquid_composition: NDArray[np.float64]
    gas_composition: NDArray[np.float64]
    vapor_fraction: float
    cumulative_gas: float
    liquid_moles_remaining: float


@dataclass
class DLResult:
    """Complete DL simulation results.

    Rsi sm³/sm³; Rsi_scf_stb is scf/STB. Bo / Bt rb/STB. Pressures Pa,
    temperature K, densities kg/m³.
    """
    temperature: float
    bubble_pressure: float
    steps: List[DLStepResult]
    pressures: NDArray[np.float64]
    Rs_values: NDArray[np.float64]
    Bo_values: NDArray[np.float64]
    oil_densities: NDArray[np.float64]
    Bt_values: NDArray[np.float64]
    Rsi: float
    Rsi_scf_stb: float
    Boi: float
    residual_oil_density: float
    feed_composition: NDArray[np.float64]
    converged: bool


def simulate_dl(
    composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    bubble_pressure: float,
    pressure_steps: NDArray[np.float64],
    binary_interaction: Optional[NDArray[np.float64]] = None,
    standard_temperature: float = SC_IMPERIAL.T,
    standard_pressure: float = SC_IMPERIAL.P,
) -> DLResult:
    """Simulate Differential Liberation test.

    The DL test liberates gas at each pressure step and removes it.
    This simulates reservoir depletion below the bubble point.

    Parameters
    ----------
    composition : ndarray
        Initial feed mole fractions (saturated oil at bubble point).
    temperature : float
        Reservoir temperature in K.
    components : list of Component
        Component objects.
    eos : CubicEOS
        Equation of state instance.
    bubble_pressure : float
        Bubble point pressure in Pa.
    pressure_steps : ndarray
        Pressure steps for DL test (descending from Pb).
    binary_interaction : ndarray, optional
        Binary interaction parameters.
    standard_temperature : float
        Standard temperature for volume calculations (K).
    standard_pressure : float
        Standard pressure for volume calculations (Pa).

    Returns
    -------
    DLResult
        Complete DL test results.

    Notes
    -----
    Key outputs:
    - Rs: Gas remaining in solution (decreases with pressure)
    - Bo: Oil shrinkage as gas is removed
    - Bt: Total volume factor (includes freed gas)

    Material balance is strictly maintained:
    - Total moles tracked through liberation
    - Liquid from step n becomes feed for step n+1

    Examples
    --------
    >>> from pvtcore.models.component import load_components
    >>> from pvtcore.eos.peng_robinson import PengRobinsonEOS
    >>> components = load_components()
    >>> oil = [components['C1'], components['C3'], components['C10']]
    >>> eos = PengRobinsonEOS(oil)
    >>> z = np.array([0.4, 0.3, 0.3])
    >>> P_steps = np.linspace(15e6, 0.1e6, 15)
    >>> result = simulate_dl(z, 350.0, oil, eos, 15e6, P_steps)
    >>> print(f"Rsi = {result.Rsi:.1f} sm³/sm³")
    """
    # Validate inputs
    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    T = float(temperature)
    P_b = float(bubble_pressure)
    P_std = float(standard_pressure)
    T_std = float(standard_temperature)

    _validate_dl_inputs(z, T, P_b, pressure_steps, components)

    # Initial state: saturated liquid at bubble point
    # Calculate stock-tank oil volume basis
    # Flash to standard conditions to get residual oil
    residual = _flash_to_stock_tank(z, T, components, eos, binary_interaction, P_std, T_std)
    residual_oil_density = residual['oil_density']
    V_sto_initial = residual['oil_volume']  # Stock-tank oil volume per mole feed

    # Initial conditions at bubble point
    rho_initial = calculate_density(P_b, T, z, components, eos, 'liquid', binary_interaction)
    V_o_initial = 1.0 / rho_initial.molar_density  # m³/mol at Pb

    Boi = V_o_initial / V_sto_initial if V_sto_initial > 0 else 1.0

    # Calculate initial GOR (total gas that will be liberated)
    # This requires flashing to find how much gas can be released
    Rsi = _calculate_initial_gor(z, T, components, eos, binary_interaction, P_std, T_std)

    # Run DL steps
    steps = []
    current_liquid = z.copy()
    n_liquid = 1.0  # Moles of liquid (tracking)
    cumulative_gas = 0.0
    all_converged = True

    # Add bubble point as first step
    steps.append(DLStepResult(
        pressure=P_b,
        temperature=T,
        Rs=Rsi,
        Rs_scf_stb=Rsi * SCF_PER_STB,
        Bo=Boi,
        oil_density=rho_initial.mass_density,
        gas_gravity=0.0,
        gas_Z=1.0,
        Bt=Boi,
        liquid_composition=z.copy(),
        gas_composition=np.zeros_like(z),
        vapor_fraction=0.0,
        cumulative_gas=0.0,
        liquid_moles_remaining=1.0,
    ))

    for P in pressure_steps:
        if P >= P_b:
            continue  # Skip pressures at or above bubble point

        try:
            step_result, current_liquid, n_liquid, cumulative_gas = _dl_step(
                P, T, current_liquid, n_liquid, cumulative_gas,
                components, eos, binary_interaction,
                V_sto_initial, P_std, T_std, Rsi
            )
            steps.append(step_result)
        except (ConvergenceError, PhaseError) as e:
            all_converged = False
            # Create placeholder
            steps.append(DLStepResult(
                pressure=P,
                temperature=T,
                Rs=np.nan,
                Rs_scf_stb=np.nan,
                Bo=np.nan,
                oil_density=np.nan,
                gas_gravity=np.nan,
                gas_Z=np.nan,
                Bt=np.nan,
                liquid_composition=current_liquid.copy(),
                gas_composition=np.zeros_like(z),
                vapor_fraction=np.nan,
                cumulative_gas=cumulative_gas,
                liquid_moles_remaining=n_liquid,
            ))

    # Extract arrays
    pressures = np.array([s.pressure for s in steps])
    Rs_values = np.array([s.Rs for s in steps])
    Bo_values = np.array([s.Bo for s in steps])
    oil_densities = np.array([s.oil_density for s in steps])
    Bt_values = np.array([s.Bt for s in steps])

    return DLResult(
        temperature=T,
        bubble_pressure=P_b,
        steps=steps,
        pressures=pressures,
        Rs_values=Rs_values,
        Bo_values=Bo_values,
        oil_densities=oil_densities,
        Bt_values=Bt_values,
        Rsi=Rsi,
        Rsi_scf_stb=Rsi * SCF_PER_STB,
        Boi=Boi,
        residual_oil_density=residual_oil_density,
        feed_composition=z,
        converged=all_converged,
    )


def _dl_step(
    pressure: float,
    temperature: float,
    liquid_composition: NDArray[np.float64],
    n_liquid: float,
    cumulative_gas: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    V_sto_initial: float,
    P_std: float,
    T_std: float,
    Rsi: float,
) -> tuple[DLStepResult, NDArray[np.float64], float, float]:
    """Execute single DL pressure step."""
    P = float(pressure)
    T = float(temperature)
    z = liquid_composition

    # Flash at current P, T
    flash = pt_flash(P, T, z, components, eos, binary_interaction=binary_interaction)

    if flash.phase == 'liquid':
        # No gas liberation at this pressure
        rho = calculate_density(P, T, z, components, eos, 'liquid', binary_interaction)
        V_o = 1.0 / rho.molar_density

        # Rs calculation
        remaining_gas = _calculate_remaining_gas(z, T, components, eos, binary_interaction, P_std, T_std)
        Rs = remaining_gas * V_sto_initial  # Normalize to stock-tank basis

        return (
            DLStepResult(
                pressure=P,
                temperature=T,
                Rs=Rs,
                Rs_scf_stb=Rs * SCF_PER_STB,
                Bo=V_o / V_sto_initial,
                oil_density=rho.mass_density,
                gas_gravity=0.0,
                gas_Z=1.0,
                Bt=V_o / V_sto_initial,
                liquid_composition=z.copy(),
                gas_composition=np.zeros_like(z),
                vapor_fraction=0.0,
                cumulative_gas=cumulative_gas,
                liquid_moles_remaining=n_liquid,
            ),
            z.copy(),
            n_liquid,
            cumulative_gas,
        )

    # Two-phase: gas is liberated
    nv = flash.vapor_fraction
    x = flash.liquid_composition
    y = flash.vapor_composition

    # Moles of gas liberated (per mole of feed to this step)
    n_gas = nv * n_liquid
    n_liquid_new = (1 - nv) * n_liquid

    # Cumulative gas (in standard volumes per initial oil)
    gas_at_std = _calculate_gas_volume_at_std(y, n_gas, components, eos, binary_interaction, P_std, T_std)
    cumulative_gas += gas_at_std / V_sto_initial

    # Liquid properties
    rho_L = calculate_density(P, T, x, components, eos, 'liquid', binary_interaction)
    V_o = n_liquid_new / rho_L.molar_density  # Volume of remaining oil

    # Gas properties
    rho_V = calculate_density(P, T, y, components, eos, 'vapor', binary_interaction)
    MW_gas = mixture_molecular_weight(y, components)
    gas_gravity = MW_gas / 28.97  # Relative to air

    Z_gas = eos.compressibility(P, T, y, phase='vapor', binary_interaction=binary_interaction)
    if isinstance(Z_gas, list):
        Z_gas = Z_gas[-1]

    # Remaining solution GOR
    remaining_gas = _calculate_remaining_gas(x, T, components, eos, binary_interaction, P_std, T_std)
    Rs = remaining_gas

    # Bo and Bt
    Bo = V_o / V_sto_initial
    V_gas_at_P = n_gas * Z_gas * R.Pa_m3_per_mol_K * T / P
    Bt = (V_o + V_gas_at_P) / V_sto_initial

    return (
        DLStepResult(
            pressure=P,
            temperature=T,
            Rs=Rs,
            Rs_scf_stb=Rs * SCF_PER_STB,
            Bo=Bo,
            oil_density=rho_L.mass_density,
            gas_gravity=gas_gravity,
            gas_Z=Z_gas,
            Bt=Bt,
            liquid_composition=x.copy(),
            gas_composition=y.copy(),
            vapor_fraction=nv,
            cumulative_gas=cumulative_gas,
            liquid_moles_remaining=n_liquid_new,
        ),
        x.copy(),  # New liquid composition
        n_liquid_new,  # Updated liquid moles
        cumulative_gas,
    )


def _flash_to_stock_tank(
    composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_std: float,
    T_std: float,
) -> dict:
    """Flash to stock-tank conditions to get residual oil."""
    try:
        flash = pt_flash(P_std, T_std, composition, components, eos,
                        binary_interaction=binary_interaction)

        if flash.phase == 'liquid':
            x = composition
        elif flash.phase == 'two-phase':
            x = flash.liquid_composition
        else:
            # All vapor - no stock-tank oil
            return {'oil_density': 800.0, 'oil_volume': 0.01}  # Placeholder

        rho = calculate_density(P_std, T_std, x, components, eos, 'liquid', binary_interaction)
        V_oil = (1 - flash.vapor_fraction) / rho.molar_density

        return {'oil_density': rho.mass_density, 'oil_volume': V_oil}

    except Exception:
        # Fallback
        return {'oil_density': 800.0, 'oil_volume': 0.01}


def _calculate_initial_gor(
    composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_std: float,
    T_std: float,
) -> float:
    """Calculate initial solution GOR (total gas that can be liberated)."""
    try:
        flash = pt_flash(P_std, T_std, composition, components, eos,
                        binary_interaction=binary_interaction)

        if flash.phase == 'vapor':
            return 1000.0  # All gas

        nv = flash.vapor_fraction
        y = flash.vapor_composition

        if nv < 1e-6:
            return 0.0

        # Gas volume at standard conditions
        Z_gas = eos.compressibility(P_std, T_std, y, phase='vapor', binary_interaction=binary_interaction)
        if isinstance(Z_gas, list):
            Z_gas = Z_gas[-1]

        V_gas = nv * Z_gas * R.Pa_m3_per_mol_K * T_std / P_std

        # Oil volume at standard conditions
        x = flash.liquid_composition
        rho_oil = calculate_density(P_std, T_std, x, components, eos, 'liquid', binary_interaction)
        V_oil = (1 - nv) / rho_oil.molar_density

        return V_gas / V_oil if V_oil > 0 else 0.0

    except Exception:
        return 100.0  # Default estimate


def _calculate_remaining_gas(
    liquid_composition: NDArray[np.float64],
    temperature: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_std: float,
    T_std: float,
) -> float:
    """Calculate gas remaining in solution (can still be liberated)."""
    return _calculate_initial_gor(
        liquid_composition, temperature, components, eos,
        binary_interaction, P_std, T_std
    )


def _calculate_gas_volume_at_std(
    gas_composition: NDArray[np.float64],
    n_moles: float,
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_std: float,
    T_std: float,
) -> float:
    """Calculate gas volume at standard conditions."""
    Z = eos.compressibility(P_std, T_std, gas_composition, phase='vapor',
                           binary_interaction=binary_interaction)
    if isinstance(Z, list):
        Z = Z[-1]

    return n_moles * Z * R.Pa_m3_per_mol_K * T_std / P_std


def _validate_dl_inputs(
    composition: NDArray[np.float64],
    temperature: float,
    bubble_pressure: float,
    pressure_steps: NDArray[np.float64],
    components: List[Component],
) -> None:
    """Validate DL inputs."""
    if temperature <= 0:
        raise ValidationError("Temperature must be positive", parameter="temperature")
    if bubble_pressure <= 0:
        raise ValidationError("Bubble pressure must be positive", parameter="bubble_pressure")
    if len(composition) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition"
        )
    if np.any(pressure_steps <= 0):
        raise ValidationError("All pressure steps must be positive", parameter="pressure_steps")
