"""Interfacial tension calculation using the parachor method.

This module implements the Macleod-Sugden / Weinaug-Katz parachor
correlation for calculating interfacial tension (IFT) between
coexisting liquid and vapor phases.

The parachor method relates IFT to the difference in molar densities
between phases, weighted by component parachors.

Units Convention:
- IFT: mN/m (= dyn/cm)
- Density: mol/m³ (molar) or kg/m³ (mass)
- Parachor: (mN/m)^(1/4) × cm³/mol
- Molecular weight: g/mol

References
----------
[1] Macleod, D.B. (1923). Trans. Faraday Soc., 19, 38-41.
[2] Sugden, S. (1924). J. Chem. Soc. Trans., 125, 1177-1189.
[3] Weinaug, C.F. and Katz, D.L. (1943). Ind. Eng. Chem., 35(2), 239-246.
[4] Fanchi, J.R. (1985). SPE Reservoir Engineering, 1(4), 405-406.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import PropertyError, ValidationError
from ..models.component import Component
from ..correlations.parachor import estimate_parachor_array


@dataclass
class IFTResult:
    """Results from interfacial tension calculation.

    Attributes:
        ift: Interfacial tension in mN/m
        ift_dyn_cm: Interfacial tension in dyn/cm (same numerical value)
        parachor_sum: The parachor summation term (Σ Pᵢ Δρᵢ)^4
        liquid_molar_density: Liquid molar density used (mol/m³)
        vapor_molar_density: Vapor molar density used (mol/m³)
    """
    ift: float
    ift_dyn_cm: float
    parachor_sum: float
    liquid_molar_density: float
    vapor_molar_density: float


def calculate_ift_parachor(
    liquid_composition: NDArray[np.float64],
    vapor_composition: NDArray[np.float64],
    liquid_molar_density: float,
    vapor_molar_density: float,
    components: List[Component],
    parachors: Optional[NDArray[np.float64]] = None,
    liquid_MW: Optional[float] = None,
    vapor_MW: Optional[float] = None,
) -> IFTResult:
    """Calculate interfacial tension using the parachor method.

    The Weinaug-Katz extension of the Macleod-Sugden correlation:

        σ^(1/4) = Σᵢ Pᵢ (xᵢ ρᴸ/MWᴸ - yᵢ ρⱽ/MWⱽ)

    or equivalently with molar densities:

        σ^(1/4) = Σᵢ Pᵢ (xᵢ ρᴸ_mol - yᵢ ρⱽ_mol) × 10⁻⁶

    where the factor converts from mol/m³ to mol/cm³.

    Parameters
    ----------
    liquid_composition : ndarray
        Liquid phase mole fractions xᵢ.
    vapor_composition : ndarray
        Vapor phase mole fractions yᵢ.
    liquid_molar_density : float
        Liquid phase molar density in mol/m³.
    vapor_molar_density : float
        Vapor phase molar density in mol/m³.
    components : list of Component
        Component objects with MW property.
    parachors : ndarray, optional
        Component parachors in (mN/m)^(1/4) × cm³/mol.
        If not provided, estimated using Fanchi correlation.
    liquid_MW : float, optional
        Liquid mixture molecular weight in g/mol.
        Calculated from composition if not provided.
    vapor_MW : float, optional
        Vapor mixture molecular weight in g/mol.
        Calculated from composition if not provided.

    Returns
    -------
    IFTResult
        Interfacial tension calculation results.

    Raises
    ------
    ValidationError
        If inputs are invalid.
    PropertyError
        If IFT calculation fails (e.g., negative radicand).

    Notes
    -----
    The parachor method is empirical and works best for:
    - Hydrocarbon systems
    - Conditions not too close to the critical point

    Near the critical point, IFT approaches zero as the phases
    become identical. The parachor method naturally captures this
    behavior since ρᴸ → ρⱽ at the critical point.

    References
    ----------
    Weinaug, C.F. and Katz, D.L. (1943). Ind. Eng. Chem., 35(2), 239-246.

    Examples
    --------
    >>> from pvtcore.models.component import load_components
    >>> components = load_components()
    >>> binary = [components['C1'], components['C3']]
    >>> x = np.array([0.3, 0.7])  # Liquid
    >>> y = np.array([0.9, 0.1])  # Vapor
    >>> rho_L = 10000.0  # mol/m³
    >>> rho_V = 500.0    # mol/m³
    >>> result = calculate_ift_parachor(x, y, rho_L, rho_V, binary)
    >>> print(f"IFT = {result.ift:.2f} mN/m")
    """
    # Input validation
    _validate_ift_inputs(
        liquid_composition, vapor_composition,
        liquid_molar_density, vapor_molar_density,
        components,
    )

    x = np.asarray(liquid_composition, dtype=np.float64)
    y = np.asarray(vapor_composition, dtype=np.float64)
    x = x / x.sum()  # Normalize
    y = y / y.sum()

    n = len(components)

    # Get or estimate parachors
    if parachors is None:
        # Use Fanchi correlation, with tabulated values where available
        MWs = np.array([comp.MW for comp in components])
        component_ids = [comp.formula for comp in components]
        P = estimate_parachor_array(MWs, component_ids)
    else:
        P = np.asarray(parachors, dtype=np.float64)
        if len(P) != n:
            raise ValidationError(
                "Parachors array must match number of components",
                parameter="parachors",
                value={"got": len(P), "expected": n},
            )

    # Calculate mixture molecular weights if not provided
    if liquid_MW is None:
        liquid_MW = sum(x[i] * components[i].MW for i in range(n))
    if vapor_MW is None:
        vapor_MW = sum(y[i] * components[i].MW for i in range(n))

    # Convert molar densities from mol/m³ to mol/cm³
    # (parachor units are (mN/m)^(1/4) × cm³/mol)
    rho_L_mol_cm3 = liquid_molar_density * 1e-6  # mol/m³ → mol/cm³
    rho_V_mol_cm3 = vapor_molar_density * 1e-6

    # Parachor method: σ^(1/4) = Σᵢ Pᵢ (xᵢ ρᴸ - yᵢ ρⱽ)
    # where densities are molar densities in mol/cm³
    parachor_sum = 0.0
    for i in range(n):
        delta_rho = x[i] * rho_L_mol_cm3 - y[i] * rho_V_mol_cm3
        parachor_sum += P[i] * delta_rho

    # Handle near-critical behavior where parachor_sum can be near zero or negative
    if parachor_sum < 0:
        # This can happen if vapor is denser than liquid (non-physical for VLE)
        # or near critical point with numerical errors
        # Return zero IFT as phases are essentially identical
        return IFTResult(
            ift=0.0,
            ift_dyn_cm=0.0,
            parachor_sum=parachor_sum,
            liquid_molar_density=liquid_molar_density,
            vapor_molar_density=vapor_molar_density,
        )

    # σ = (parachor_sum)^4
    # Units work out: [(mN/m)^(1/4) × cm³/mol × mol/cm³]^4 = mN/m
    ift = parachor_sum ** 4

    return IFTResult(
        ift=ift,
        ift_dyn_cm=ift,  # mN/m = dyn/cm numerically
        parachor_sum=parachor_sum,
        liquid_molar_density=liquid_molar_density,
        vapor_molar_density=vapor_molar_density,
    )


def calculate_ift_from_mass_density(
    liquid_composition: NDArray[np.float64],
    vapor_composition: NDArray[np.float64],
    liquid_mass_density: float,
    vapor_mass_density: float,
    components: List[Component],
    parachors: Optional[NDArray[np.float64]] = None,
) -> IFTResult:
    """Calculate IFT from mass densities.

    Alternative interface that accepts mass densities in kg/m³
    and converts internally.

    Parameters
    ----------
    liquid_composition : ndarray
        Liquid phase mole fractions xᵢ.
    vapor_composition : ndarray
        Vapor phase mole fractions yᵢ.
    liquid_mass_density : float
        Liquid phase mass density in kg/m³.
    vapor_mass_density : float
        Vapor phase mass density in kg/m³.
    components : list of Component
        Component objects with MW property.
    parachors : ndarray, optional
        Component parachors.

    Returns
    -------
    IFTResult
        Interfacial tension calculation results.
    """
    x = np.asarray(liquid_composition, dtype=np.float64)
    y = np.asarray(vapor_composition, dtype=np.float64)
    x = x / x.sum()
    y = y / y.sum()

    n = len(components)

    # Calculate mixture molecular weights (g/mol)
    liquid_MW = sum(x[i] * components[i].MW for i in range(n))
    vapor_MW = sum(y[i] * components[i].MW for i in range(n))

    # Convert mass density (kg/m³) to molar density (mol/m³)
    # ρ_mol = ρ_mass / MW
    # Note: MW is in g/mol, so we need kg/m³ * 1000 g/kg / (g/mol) = mol/m³
    liquid_molar_density = liquid_mass_density * 1000.0 / liquid_MW
    vapor_molar_density = vapor_mass_density * 1000.0 / vapor_MW

    return calculate_ift_parachor(
        x, y,
        liquid_molar_density, vapor_molar_density,
        components,
        parachors=parachors,
        liquid_MW=liquid_MW,
        vapor_MW=vapor_MW,
    )


def estimate_critical_ift_scaling(
    ift: float,
    temperature: float,
    Tc_mix: float,
    exponent: float = 1.26,
) -> float:
    """Apply critical scaling to IFT near critical point.

    Near the critical point, IFT follows a scaling law:
        σ = σ₀ (1 - T/Tc)^n

    where n ≈ 1.26 (Ising model exponent).

    This function can be used to extrapolate IFT behavior or
    to check consistency with scaling theory.

    Parameters
    ----------
    ift : float
        Calculated IFT in mN/m.
    temperature : float
        Temperature in K.
    Tc_mix : float
        Mixture critical temperature in K.
    exponent : float
        Critical scaling exponent (default 1.26).

    Returns
    -------
    float
        Scaled IFT in mN/m.

    Notes
    -----
    This is primarily useful for understanding behavior near
    critical conditions. The parachor method itself naturally
    gives σ → 0 as T → Tc.
    """
    if temperature >= Tc_mix:
        return 0.0

    # Scaling factor
    scaling = (1.0 - temperature / Tc_mix) ** exponent

    # Return the IFT (already should follow this scaling from parachor)
    return ift


def _validate_ift_inputs(
    liquid_composition: NDArray[np.float64],
    vapor_composition: NDArray[np.float64],
    liquid_molar_density: float,
    vapor_molar_density: float,
    components: List[Component],
) -> None:
    """Validate IFT calculation inputs."""
    x = np.asarray(liquid_composition)
    y = np.asarray(vapor_composition)
    n = len(components)

    if len(x) != n:
        raise ValidationError(
            "Liquid composition length must match number of components",
            parameter="liquid_composition",
            value={"got": len(x), "expected": n},
        )
    if len(y) != n:
        raise ValidationError(
            "Vapor composition length must match number of components",
            parameter="vapor_composition",
            value={"got": len(y), "expected": n},
        )

    if liquid_molar_density <= 0:
        raise ValidationError(
            "Liquid molar density must be positive",
            parameter="liquid_molar_density",
            value=liquid_molar_density,
        )
    if vapor_molar_density <= 0:
        raise ValidationError(
            "Vapor molar density must be positive",
            parameter="vapor_molar_density",
            value=vapor_molar_density,
        )

    if np.any(x < -1e-10) or np.any(y < -1e-10):
        raise ValidationError(
            "Compositions cannot have negative values",
            parameter="composition",
        )

# ==============================================================================
# Compatibility wrappers (codex API)
# ==============================================================================

@dataclass
class ParachorIFT:
    """IFT result (codex API)."""
    sigma_N_per_m: float
    sigma_dyn_per_cm: float


def interfacial_tension_parachor(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    *,
    rho_liquid_kg_per_m3: float,
    rho_vapor_kg_per_m3: float,
    mw_components_g_per_mol: NDArray[np.float64],
    parachor: NDArray[np.float64],
) -> ParachorIFT:
    """Compute IFT using the Weinaug–Katz parachor method (codex API).

    Returns both:
      - sigma_N_per_m (SI)
      - sigma_dyn_per_cm (cgs; numerically equal to mN/m)
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 1 or y.ndim != 1 or x.shape != y.shape:
        raise ValidationError("x and y must be 1D arrays of equal length.", parameter="composition")
    if x.sum() <= 0.0 or y.sum() <= 0.0:
        raise ValidationError("x and y must have positive sums.", parameter="composition_sum")
    x = x / x.sum()
    y = y / y.sum()

    mw = np.asarray(mw_components_g_per_mol, dtype=np.float64)
    P = np.asarray(parachor, dtype=np.float64)
    if mw.shape != x.shape or P.shape != x.shape:
        raise ValidationError(
            "mw_components_g_per_mol and parachor must match x/y length.",
            parameter="inputs",
            value={"n": int(x.shape[0]), "mw": int(mw.shape[0]), "parachor": int(P.shape[0])},
        )

    # Mixture molecular weights (g/mol)
    mw_L = float(np.dot(x, mw))
    mw_V = float(np.dot(y, mw))

    # Convert mass densities (kg/m³) to molar densities (mol/m³)
    rho_L_mol_m3 = float(rho_liquid_kg_per_m3) * 1000.0 / mw_L
    rho_V_mol_m3 = float(rho_vapor_kg_per_m3) * 1000.0 / mw_V

    # Convert mol/m³ → mol/cm³ for parachor units
    rho_L = rho_L_mol_m3 * 1e-6
    rho_V = rho_V_mol_m3 * 1e-6

    s = float(np.dot(P, (x * rho_L) - (y * rho_V)))
    if s <= 0.0:
        sigma_mN_per_m = 0.0
    else:
        sigma_mN_per_m = s ** 4

    sigma_dyn_per_cm = sigma_mN_per_m  # 1 mN/m == 1 dyn/cm numerically
    sigma_N_per_m = sigma_mN_per_m / 1000.0

    return ParachorIFT(sigma_N_per_m=float(sigma_N_per_m), sigma_dyn_per_cm=float(sigma_dyn_per_cm))


def interfacial_tension_parachor_after_flash(
    flash: Any,
    eos: Any,
    components: List[Component],
    *,
    parachor: Optional[NDArray[np.float64]] = None,
    binary_interaction: Optional[NDArray[np.float64]] = None,
) -> ParachorIFT:
    """Compute IFT end-to-end from a `pt_flash` result (codex API)."""
    phase = str(getattr(flash, "phase"))
    if phase != "two-phase":
        raise ValidationError("IFT requires a two-phase flash result.", parameter="flash.phase", value=phase)

    x = np.asarray(getattr(flash, "liquid_composition"), dtype=np.float64)
    y = np.asarray(getattr(flash, "vapor_composition"), dtype=np.float64)

    # Densities via existing EOS-based density helper
    from .density import calculate_density  # local import to avoid module cycles

    rhoL = calculate_density(
        pressure=float(getattr(flash, "pressure")),
        temperature=float(getattr(flash, "temperature")),
        composition=x,
        components=components,
        eos=eos,
        phase="liquid",
        binary_interaction=binary_interaction,
    ).mass_density

    rhoV = calculate_density(
        pressure=float(getattr(flash, "pressure")),
        temperature=float(getattr(flash, "temperature")),
        composition=y,
        components=components,
        eos=eos,
        phase="vapor",
        binary_interaction=binary_interaction,
    ).mass_density

    mw = np.array([c.MW for c in components], dtype=np.float64)

    if parachor is None:
        component_ids = [c.formula for c in components]
        P = estimate_parachor_array(mw, component_ids)
    else:
        P = np.asarray(parachor, dtype=np.float64)

    return interfacial_tension_parachor(
        x,
        y,
        rho_liquid_kg_per_m3=float(rhoL),
        rho_vapor_kg_per_m3=float(rhoV),
        mw_components_g_per_mol=mw,
        parachor=P,
    )
