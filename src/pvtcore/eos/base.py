"""Base classes and protocols for equation of state implementations.

This module defines the interface that all cubic EOS implementations must follow,
along with common data structures for EOS results.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional, Protocol
import numpy as np


@dataclass
class EOSResult:
    """Results from an equation of state calculation.

    Attributes:
        Z: Compressibility factor(s). Float for single phase, array for multiphase
        phase: Phase identifier ('liquid', 'vapor', or 'two-phase')
        fugacity_coef: Fugacity coefficients for each component
        A: Dimensionless attraction parameter (aP/R²T²)
        B: Dimensionless repulsion parameter (bP/RT)
        a_mix: Mixture attraction parameter (J·m³/mol²)
        b_mix: Mixture covolume parameter (m³/mol)
        roots: All roots from cubic equation (for diagnostics)
        pressure: Pressure used in calculation (Pa)
        temperature: Temperature used in calculation (K)
    """
    Z: float | np.ndarray
    phase: Literal['liquid', 'vapor', 'two-phase']
    fugacity_coef: np.ndarray
    A: float
    B: float
    a_mix: float
    b_mix: float
    roots: List[float]
    pressure: float
    temperature: float

    def __post_init__(self):
        """Ensure fugacity coefficients are numpy arrays."""
        if not isinstance(self.fugacity_coef, np.ndarray):
            self.fugacity_coef = np.array(self.fugacity_coef)


class CubicEOS(ABC):
    """Abstract base class for cubic equations of state.

    All cubic EOS implementations (Peng-Robinson, Soave-Redlich-Kwong, etc.)
    must inherit from this class and implement the required methods.

    The general form of a cubic EOS is:
        P = RT/(V-b) - a(T)/(V² + ubV + wb²)

    where u and w are EOS-specific constants:
    - Peng-Robinson: u = 2, w = -1
    - Soave-Redlich-Kwong: u = 1, w = 0

    Attributes:
        name: Name of the equation of state
        components: List of Component objects
        u: EOS parameter (e.g., 2 for PR)
        w: EOS parameter (e.g., -1 for PR)
    """

    def __init__(self, components: List, name: str = "Cubic EOS"):
        """Initialize cubic EOS.

        Args:
            components: List of Component objects with Tc, Pc, omega, etc.
            name: Name of the EOS
        """
        self.name = name
        self.components = components
        self.n_components = len(components)

        # EOS-specific constants (must be set by subclass)
        self.u: float = 0.0
        self.w: float = 0.0

    @abstractmethod
    def calculate_params(
        self,
        temperature: float,
        composition: np.ndarray,
        binary_interaction: Optional[np.ndarray] = None
    ) -> tuple[float, float, np.ndarray, np.ndarray]:
        """Calculate EOS parameters a and b for mixture.

        Args:
            temperature: Temperature (K)
            composition: Mole fractions (array of length n_components)
            binary_interaction: Binary interaction parameters kij matrix (n×n)

        Returns:
            Tuple of (a_mix, b_mix, a_array, b_array) where:
            - a_mix: Mixture attraction parameter (J·m³/mol²)
            - b_mix: Mixture covolume parameter (m³/mol)
            - a_array: Pure component attraction parameters (array)
            - b_array: Pure component covolume parameters (array)
        """
        pass

    @abstractmethod
    def alpha_function(self, temperature: float, component_idx: int) -> float:
        """Calculate alpha function α(T) for a component.

        The alpha function accounts for temperature dependence of attraction:
            a(T) = a_c × α(T)

        Args:
            temperature: Temperature (K)
            component_idx: Index of component

        Returns:
            Alpha value (dimensionless)
        """
        pass

    def compressibility(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor', 'auto'] = 'auto',
        binary_interaction: Optional[np.ndarray] = None
    ) -> float | List[float]:
        """Calculate compressibility factor Z.

        Solves the cubic equation:
            Z³ + c₂Z² + c₁Z + c₀ = 0

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase to calculate ('liquid', 'vapor', or 'auto')
            binary_interaction: Binary interaction parameters kij

        Returns:
            Compressibility factor Z (float for single phase, list for 'auto')
        """
        from ..core.numerics.cubic_solver import solve_cubic_eos

        # Calculate mixture parameters
        a_mix, b_mix, _, _ = self.calculate_params(
            temperature, composition, binary_interaction
        )

        # Calculate dimensionless parameters
        from ..core.constants import R
        A = a_mix * pressure / (R.Pa_m3_per_mol_K * temperature) ** 2
        B = b_mix * pressure / (R.Pa_m3_per_mol_K * temperature)

        # Solve cubic equation
        if phase == 'auto':
            return solve_cubic_eos(A, B, root_type='all', u=self.u, w=self.w)
        else:
            return solve_cubic_eos(A, B, root_type=phase, u=self.u, w=self.w)

    @abstractmethod
    def fugacity_coefficient(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Calculate fugacity coefficients for all components.

        The fugacity coefficient φᵢ relates fugacity to composition:
            fᵢ = φᵢ × xᵢ × P

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase for calculation
            binary_interaction: Binary interaction parameters kij

        Returns:
            Array of fugacity coefficients, one per component
        """
        pass

    def ln_fugacity_coefficient(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Return ln(φ_i) for all components.

        Default implementation takes log of fugacity_coefficient().
        Subclasses may override for efficiency (avoids exp then log).
        """
        return np.log(self.fugacity_coefficient(
            pressure, temperature, composition, phase, binary_interaction
        ))

    def d_ln_phi_dP(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """∂ln(φ_i)/∂P at constant T, x. Analytical for cubic EOS.

        Default: central finite-difference fallback. Subclasses should
        override with the closed-form expression.
        """
        dP = max(pressure * 1e-6, 1.0)
        ln_phi_p = self.ln_fugacity_coefficient(
            pressure + dP, temperature, composition, phase, binary_interaction)
        ln_phi_m = self.ln_fugacity_coefficient(
            pressure - dP, temperature, composition, phase, binary_interaction)
        return (ln_phi_p - ln_phi_m) / (2.0 * dP)

    def d_ln_phi_dn(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """∂ln(φ_i)/∂n_j matrix (n_c × n_c) at constant T, P, n_{k≠j}.

        This is the mole-number derivative used in the Newton Jacobian for
        flash and saturation solvers.  Related to the composition derivative
        by the chain rule, but the n-derivative form is what appears directly
        in the Michelsen formulation.

        Default: central finite-difference fallback. Subclasses should
        override with the closed-form expression.
        """
        nc = len(composition)
        x = np.asarray(composition, dtype=np.float64)
        n_total = 1.0
        n = x * n_total

        dn = 1e-6
        J = np.zeros((nc, nc))
        for j in range(nc):
            n_p = n.copy()
            n_m = n.copy()
            n_p[j] += dn
            n_m[j] -= dn
            x_p = n_p / n_p.sum()
            x_m = n_m / n_m.sum()
            ln_phi_p = self.ln_fugacity_coefficient(
                pressure, temperature, x_p, phase, binary_interaction)
            ln_phi_m = self.ln_fugacity_coefficient(
                pressure, temperature, x_m, phase, binary_interaction)
            J[:, j] = (ln_phi_p - ln_phi_m) / (2.0 * dn)
        return J

    def fugacity(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Calculate component fugacities.

        Fugacity: fᵢ = φᵢ × xᵢ × P

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase for calculation
            binary_interaction: Binary interaction parameters kij

        Returns:
            Array of fugacities (Pa), one per component
        """
        phi = self.fugacity_coefficient(
            pressure, temperature, composition, phase, binary_interaction
        )
        return phi * composition * pressure

    def calculate(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor', 'auto'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> EOSResult:
        """Perform complete EOS calculation.

        This is the main entry point for EOS calculations, returning
        a comprehensive EOSResult object.

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase to calculate
            binary_interaction: Binary interaction parameters kij

        Returns:
            EOSResult object with all calculated properties
        """
        from ..core.numerics.cubic_solver import solve_cubic_eos
        from ..core.constants import R

        # Normalize composition
        composition = np.asarray(composition)
        composition = composition / composition.sum()

        # Calculate mixture parameters
        a_mix, b_mix, _, _ = self.calculate_params(
            temperature, composition, binary_interaction
        )

        # Calculate dimensionless parameters
        A = a_mix * pressure / (R.Pa_m3_per_mol_K * temperature) ** 2
        B = b_mix * pressure / (R.Pa_m3_per_mol_K * temperature)

        # Get all roots for diagnostics
        all_roots = solve_cubic_eos(A, B, root_type='all', u=self.u, w=self.w)

        # Determine phase
        if phase == 'auto':
            if len(all_roots) == 3:
                phase_result = 'two-phase'
                Z = np.array([min(all_roots), max(all_roots)])
            else:
                # Single root - need additional logic to determine phase
                # For now, assume vapor if Z > 0.3, liquid otherwise
                phase_result = 'vapor' if all_roots[0] > 0.3 else 'liquid'
                Z = all_roots[0]
        else:
            phase_result = phase
            Z = solve_cubic_eos(A, B, root_type=phase, u=self.u, w=self.w)

        # Calculate fugacity coefficients
        if isinstance(Z, (list, np.ndarray)) and len(Z) > 1:
            # Two-phase: calculate for both phases
            phi_liquid = self.fugacity_coefficient(
                pressure, temperature, composition, 'liquid', binary_interaction
            )
            phi_vapor = self.fugacity_coefficient(
                pressure, temperature, composition, 'vapor', binary_interaction
            )
            phi = np.array([phi_liquid, phi_vapor])
        else:
            phi = self.fugacity_coefficient(
                pressure, temperature, composition, phase_result, binary_interaction
            )

        return EOSResult(
            Z=Z,
            phase=phase_result,
            fugacity_coef=phi,
            A=A,
            B=B,
            a_mix=a_mix,
            b_mix=b_mix,
            roots=all_roots,
            pressure=pressure,
            temperature=temperature
        )

    def density(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> float:
        """Calculate molar density.

        ρ = P/(ZRT)

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase for calculation
            binary_interaction: Binary interaction parameters kij

        Returns:
            Molar density (mol/m³)
        """
        from ..core.constants import R

        Z = self.compressibility(
            pressure, temperature, composition, phase, binary_interaction
        )

        return pressure / (Z * R.Pa_m3_per_mol_K * temperature)

    def molar_volume(
        self,
        pressure: float,
        temperature: float,
        composition: np.ndarray,
        phase: Literal['liquid', 'vapor'] = 'vapor',
        binary_interaction: Optional[np.ndarray] = None
    ) -> float:
        """Calculate molar volume.

        V = ZRT/P

        Args:
            pressure: Pressure (Pa)
            temperature: Temperature (K)
            composition: Mole fractions
            phase: Phase for calculation
            binary_interaction: Binary interaction parameters kij

        Returns:
            Molar volume (m³/mol)
        """
        from ..core.constants import R

        Z = self.compressibility(
            pressure, temperature, composition, phase, binary_interaction
        )

        return Z * R.Pa_m3_per_mol_K * temperature / pressure

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.name}(n_components={self.n_components})"
