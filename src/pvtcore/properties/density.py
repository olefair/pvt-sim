"""Density calculations for petroleum fluids.

This module provides density calculations using equation of state
compressibility factors with optional volume translation (Peneloux correction).

Units Convention:
- Pressure: Pa
- Temperature: K
- Density: kg/m³ (molar: mol/m³)
- Molar volume: m³/mol
- Molecular weight: g/mol

References
----------
[1] Peng, D.Y. and Robinson, D.B. (1976). Ind. Eng. Chem. Fundam., 15(1), 59-64.
[2] Peneloux, A., Rauzy, E., and Freze, R. (1982). Fluid Phase Equilibria, 8(1), 7-23.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Literal, Optional

import numpy as np
from numpy.typing import NDArray

from ..core.constants import R
from ..core.errors import PropertyError, ValidationError
from ..eos.base import CubicEOS
from ..models.component import Component


@dataclass
class DensityResult:
    """Results from density calculation.

    Attributes:
        molar_density: Molar density (mol/m³)
        mass_density: Mass density (kg/m³)
        molar_volume: Molar volume (m³/mol)
        Z: Compressibility factor used
        MW_mix: Mixture molecular weight (g/mol)
        volume_translated: Whether volume translation was applied
    """
    molar_density: float
    mass_density: float
    molar_volume: float
    Z: float
    MW_mix: float
    volume_translated: bool


def calculate_density(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    phase: Literal['liquid', 'vapor'] = 'liquid',
    binary_interaction: Optional[NDArray[np.float64]] = None,
    volume_shift: Optional[NDArray[np.float64]] = None,
) -> DensityResult:
    """Calculate phase density using equation of state.

    Computes density from:
        ρ_molar = P / (Z * R * T)  [mol/m³]
        ρ_mass = ρ_molar * MW_mix  [kg/m³]

    With optional Peneloux volume translation:
        V_corrected = V_eos + Σ xᵢ cᵢ
        ρ_corrected = 1 / V_corrected

    Parameters
    ----------
    pressure : float
        Pressure in Pa.
    temperature : float
        Temperature in K.
    composition : ndarray
        Mole fractions of each component.
    components : list of Component
        Component objects with MW property.
    eos : CubicEOS
        Equation of state instance.
    phase : {'liquid', 'vapor'}
        Phase for which to calculate density.
    binary_interaction : ndarray, optional
        Binary interaction parameters (n×n matrix).
    volume_shift : ndarray, optional
        Peneloux volume shift parameters cᵢ (m³/mol) for each component.
        If provided, applies volume translation correction.

    Returns
    -------
    DensityResult
        Density calculation results including molar and mass densities.

    Raises
    ------
    ValidationError
        If inputs are invalid (negative P or T, composition doesn't sum to 1).
    PropertyError
        If density calculation fails.

    Examples
    --------
    >>> from pvtcore.models.component import load_components
    >>> from pvtcore.eos.peng_robinson import PengRobinsonEOS
    >>> components = load_components()
    >>> binary = [components['C1'], components['C3']]
    >>> eos = PengRobinsonEOS(binary)
    >>> z = np.array([0.7, 0.3])
    >>> result = calculate_density(5e6, 300.0, z, binary, eos, phase='liquid')
    >>> print(f"Density = {result.mass_density:.1f} kg/m³")
    """
    # Input validation
    _validate_inputs(pressure, temperature, composition, components)

    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()  # Normalize

    # Calculate mixture molecular weight (g/mol)
    MW_mix = sum(z[i] * comp.MW for i, comp in enumerate(components))

    # Get compressibility factor from EOS
    try:
        Z = eos.compressibility(
            pressure, temperature, z, phase=phase,
            binary_interaction=binary_interaction
        )
    except Exception as e:
        raise PropertyError(
            f"Failed to calculate compressibility factor: {e}",
            property_name="density",
            pressure=pressure,
            temperature=temperature,
        )

    # Handle case where Z is returned as list/array
    if isinstance(Z, (list, np.ndarray)):
        Z = float(Z[0] if phase == 'liquid' else Z[-1])

    # Calculate molar volume from EOS (m³/mol)
    V_molar_eos = Z * R.Pa_m3_per_mol_K * temperature / pressure

    # Apply volume translation if provided
    volume_translated = False
    if volume_shift is not None:
        c_shift = np.asarray(volume_shift, dtype=np.float64)
        if len(c_shift) != len(components):
            raise ValidationError(
                "Volume shift array must match number of components",
                parameter="volume_shift",
                value={"got": len(c_shift), "expected": len(components)},
            )
        # Peneloux correction: V_corr = V_eos + Σ xᵢ cᵢ
        delta_V = float(np.dot(z, c_shift))
        V_molar = V_molar_eos + delta_V
        volume_translated = True
    else:
        V_molar = V_molar_eos

    # Check for physical validity
    if V_molar <= 0:
        raise PropertyError(
            f"Calculated molar volume is non-positive: {V_molar:.6e} m³/mol. "
            f"This may indicate conditions outside EOS validity range.",
            property_name="density",
            pressure=pressure,
            temperature=temperature,
        )

    # Calculate densities
    molar_density = 1.0 / V_molar  # mol/m³
    mass_density = molar_density * MW_mix / 1000.0  # kg/m³ (MW in g/mol → kg/kmol)

    return DensityResult(
        molar_density=molar_density,
        mass_density=mass_density,
        molar_volume=V_molar,
        Z=float(Z),
        MW_mix=MW_mix,
        volume_translated=volume_translated,
    )


def calculate_phase_densities(
    pressure: float,
    temperature: float,
    liquid_composition: NDArray[np.float64],
    vapor_composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    volume_shift: Optional[NDArray[np.float64]] = None,
) -> tuple[DensityResult, DensityResult]:
    """Calculate both liquid and vapor phase densities.

    Convenience function to calculate densities for both phases
    after a flash calculation.

    Parameters
    ----------
    pressure : float
        Pressure in Pa.
    temperature : float
        Temperature in K.
    liquid_composition : ndarray
        Liquid phase mole fractions.
    vapor_composition : ndarray
        Vapor phase mole fractions.
    components : list of Component
        Component objects.
    eos : CubicEOS
        Equation of state instance.
    binary_interaction : ndarray, optional
        Binary interaction parameters.
    volume_shift : ndarray, optional
        Peneloux volume shift parameters.

    Returns
    -------
    tuple of DensityResult
        (liquid_density_result, vapor_density_result)
    """
    liquid_result = calculate_density(
        pressure, temperature, liquid_composition, components, eos,
        phase='liquid', binary_interaction=binary_interaction,
        volume_shift=volume_shift,
    )

    vapor_result = calculate_density(
        pressure, temperature, vapor_composition, components, eos,
        phase='vapor', binary_interaction=binary_interaction,
        volume_shift=volume_shift,
    )

    return liquid_result, vapor_result


def mixture_molecular_weight(
    composition: NDArray[np.float64],
    components: List[Component],
) -> float:
    """Calculate mixture molecular weight.

    MW_mix = Σ xᵢ MWᵢ

    Parameters
    ----------
    composition : ndarray
        Mole fractions.
    components : list of Component
        Component objects.

    Returns
    -------
    float
        Mixture molecular weight in g/mol.
    """
    z = np.asarray(composition, dtype=np.float64)
    return float(sum(z[i] * comp.MW for i, comp in enumerate(components)))


def estimate_volume_shift_peneloux(
    components: List[Component],
    eos_type: str = 'PR',
) -> NDArray[np.float64]:
    """Estimate Peneloux volume shift parameters.

    The Peneloux volume shift improves liquid density predictions
    without affecting vapor-liquid equilibrium calculations.

    For PR EOS, a common correlation is:
        cᵢ = 0.40768 * (R * Tcᵢ / Pcᵢ) * (0.29441 - ZRA)

    where ZRA is the Rackett compressibility factor, often
    approximated as ZRA ≈ 0.29056 - 0.08775 * ω.

    Parameters
    ----------
    components : list of Component
        Component objects with Tc, Pc, omega properties.
    eos_type : str
        Equation of state type ('PR' or 'SRK').

    Returns
    -------
    ndarray
        Volume shift parameters cᵢ in m³/mol.

    References
    ----------
    Peneloux, A., Rauzy, E., and Freze, R. (1982).
    Fluid Phase Equilibria, 8(1), 7-23.
    """
    n = len(components)
    c = np.zeros(n)

    for i, comp in enumerate(components):
        # Rackett compressibility factor correlation
        ZRA = 0.29056 - 0.08775 * comp.omega

        if eos_type.upper() == 'PR':
            # PR volume shift correlation
            c[i] = 0.40768 * (R.Pa_m3_per_mol_K * comp.Tc / comp.Pc) * (0.29441 - ZRA)
        elif eos_type.upper() == 'SRK':
            # SRK volume shift correlation
            c[i] = 0.40768 * (R.Pa_m3_per_mol_K * comp.Tc / comp.Pc) * (0.29441 - ZRA)
        else:
            raise ValueError(f"Unsupported EOS type: {eos_type}")

    return c


def _validate_inputs(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    components: List[Component],
) -> None:
    """Validate density calculation inputs."""
    if pressure <= 0:
        raise ValidationError(
            "Pressure must be positive",
            parameter="pressure",
            value=pressure,
        )
    if temperature <= 0:
        raise ValidationError(
            "Temperature must be positive",
            parameter="temperature",
            value=temperature,
        )

    z = np.asarray(composition)
    if len(z) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition",
            value={"got": len(z), "expected": len(components)},
        )

    if np.any(z < -1e-10):
        raise ValidationError(
            "Composition cannot have negative values",
            parameter="composition",
        )

    if not np.isclose(z.sum(), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0, got {z.sum():.6f}",
            parameter="composition",
        )

# ==============================================================================
# Compatibility wrappers (codex API)
# ==============================================================================

@dataclass
class PhaseDensity:
    """Per-phase density convenience view (codex API)."""
    molar_density_mol_per_m3: float
    mass_density_kg_per_m3: float
    molecular_weight_g_per_mol: float


@dataclass
class FlashDensities:
    """Densities after a flash calculation (codex API)."""
    liquid: Optional[PhaseDensity]
    vapor: Optional[PhaseDensity]


def phase_molecular_weight_g_per_mol(
    composition: NDArray[np.float64],
    components: List[Component],
) -> float:
    """Mixture molecular weight (g/mol) for a phase composition."""
    x = np.asarray(composition, dtype=np.float64)
    if x.ndim != 1:
        raise ValidationError("Composition must be 1D.", parameter="composition", value=f"shape={x.shape}")
    if len(x) != len(components):
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition",
            value={"got": len(x), "expected": len(components)},
        )
    if x.sum() <= 0.0:
        raise ValidationError("Composition sum must be positive.", parameter="composition_sum", value=float(x.sum()))
    x = x / x.sum()
    return float(sum(x[i] * components[i].MW for i in range(len(components))))


def mass_density_kg_per_m3(
    pressure: float,
    temperature: float,
    composition: NDArray[np.float64],
    eos: CubicEOS,
    components: List[Component],
    *,
    phase: Literal["liquid", "vapor"] = "liquid",
    binary_interaction: Optional[NDArray[np.float64]] = None,
    volume_shift: Optional[NDArray[np.float64]] = None,
) -> float:
    """Mass density (kg/m³) wrapper around `calculate_density(...)`."""
    res = calculate_density(
        pressure=pressure,
        temperature=temperature,
        composition=composition,
        components=components,
        eos=eos,
        phase=phase,
        binary_interaction=binary_interaction,
        volume_shift=volume_shift,
    )
    return float(res.mass_density)


def densities_after_flash(
    flash: Any,
    eos: CubicEOS,
    components: List[Component],
    *,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    volume_shift: Optional[NDArray[np.float64]] = None,
) -> FlashDensities:
    """Compute per-phase densities from a `pt_flash` result (codex API)."""
    # Delay import typing to avoid hard coupling to flash module types.
    pressure = float(getattr(flash, "pressure"))
    temperature = float(getattr(flash, "temperature"))
    phase = str(getattr(flash, "phase"))

    def _one(comp: NDArray[np.float64], phase_label: Literal["liquid", "vapor"]) -> PhaseDensity:
        res = calculate_density(
            pressure=pressure,
            temperature=temperature,
            composition=comp,
            components=components,
            eos=eos,
            phase=phase_label,
            binary_interaction=binary_interaction,
            volume_shift=volume_shift,
        )
        return PhaseDensity(
            molar_density_mol_per_m3=float(res.molar_density),
            mass_density_kg_per_m3=float(res.mass_density),
            molecular_weight_g_per_mol=float(res.MW_mix),
        )

    if phase == "two-phase":
        liquid = _one(np.asarray(getattr(flash, "liquid_composition")), "liquid")
        vapor = _one(np.asarray(getattr(flash, "vapor_composition")), "vapor")
        return FlashDensities(liquid=liquid, vapor=vapor)

    if phase == "liquid":
        liquid = _one(np.asarray(getattr(flash, "liquid_composition", getattr(flash, "feed_composition"))), "liquid")
        return FlashDensities(liquid=liquid, vapor=None)

    if phase == "vapor":
        vapor = _one(np.asarray(getattr(flash, "vapor_composition", getattr(flash, "feed_composition"))), "vapor")
        return FlashDensities(liquid=None, vapor=vapor)

    raise ValidationError("Unknown flash phase label.", parameter="flash.phase", value=phase)
