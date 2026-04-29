"""
Unified CharacterizedFluid class for petroleum reservoir fluid modeling.

This module provides the main entry point for the characterization pipeline,
combining:
- Pure component database
- Plus-fraction splitting (Pedersen, Katz, Lohrenz)
- Critical property correlations (Riazi-Daubert, Kesler-Lee, Cavett)
- Acentric factor estimation
- Parachor for IFT calculations
- BIP matrix generation
- Lumping/delumping support

The CharacterizedFluid class represents a fully characterized petroleum fluid
ready for EOS calculations (flash, phase envelope, etc.).

Usage
-----
>>> from pvtcore.characterization import CharacterizedFluid
>>> fluid = CharacterizedFluid.from_composition(
...     pure_components={"N2": 0.005, "CO2": 0.012, "C1": 0.45, "C2": 0.08, "C3": 0.05},
...     plus_fraction_z=0.25,
...     plus_fraction_MW=215.0,
...     plus_fraction_SG=0.85,
... )
>>> print(f"Number of components: {fluid.n_components}")
>>> print(f"Bubble point estimate: {fluid.estimate_bubble_point(T=373.0):.0f} Pa")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from numpy.typing import NDArray

# Local imports from characterization package
from .plus_splitting import (
    katz_residual_plus_split,
    split_plus_fraction_pedersen,
    split_plus_fraction_katz,
    split_plus_fraction_lohrenz,
    KatzResidualSplitResult,
    PedersenSplitResult,
    KatzSplitResult,
    LohrenzSplitResult,
)
from .scn_properties import get_scn_properties, SCNProperties
from .bip import build_bip_matrix, BIPMatrix, BIPMethod
from .lumping import lump_by_mw_groups, LumpingResult

# Import from correlations package (must be available)
try:
    from ..correlations import (
        estimate_critical_props,
        CriticalPropsMethod,
        estimate_omega,
        AcentricMethod,
        estimate_Tb,
        BoilingPointMethod,
        estimate_parachor,
    )
    CORRELATIONS_AVAILABLE = True
except ImportError:
    CORRELATIONS_AVAILABLE = False

# Import component database
from ..models import Component, get_components_cached


class PlusFractionMethod(Enum):
    """Plus-fraction splitting method selection."""
    PEDERSEN = auto()
    KATZ = auto()
    KATZ_RESIDUAL = auto()
    LOHRENZ = auto()


@dataclass
class FluidComponent:
    """
    Represents a single component in a characterized fluid.

    Attributes
    ----------
    name : str
        Component identifier (e.g., "C1", "C7", "C12").
    z : float
        Mole fraction.
    MW : float
        Molecular weight in g/mol.
    Tc : float
        Critical temperature in Kelvin.
    Pc : float
        Critical pressure in Pascal.
    Vc : float
        Critical molar volume in m³/mol.
    omega : float
        Acentric factor.
    Tb : float
        Normal boiling point in Kelvin.
    SG : float
        Specific gravity at 60°F/60°F.
    parachor : float
        Parachor for IFT calculation.
    is_pure : bool
        True if this is a pure (database) component.
    is_pseudo : bool
        True if this is a pseudo-component (SCN or lumped).
    """
    name: str
    z: float
    MW: float
    Tc: float
    Pc: float
    Vc: float
    omega: float
    Tb: float
    SG: float
    parachor: float
    is_pure: bool = False
    is_pseudo: bool = False


@dataclass
class CharacterizedFluid:
    """
    A fully characterized petroleum reservoir fluid.

    This class represents a fluid composition with all properties needed
    for EOS calculations. It can be created from:
    - Lab compositions with resolved components and a plus fraction
    - Predefined component lists with full properties
    - Loaded from files

    Attributes
    ----------
    components : list of FluidComponent
        All components in the fluid.
    bip_matrix : BIPMatrix
        Binary interaction parameters.
    temperature_ref : float
        Reference temperature for characterization (K).
    notes : str
        Optional notes about the fluid.
    """
    components: List[FluidComponent]
    bip_matrix: Optional[BIPMatrix] = None
    temperature_ref: float = 288.71  # 60°F in K
    notes: str = ""

    # Cached arrays for EOS calculations
    _z: Optional[NDArray[np.float64]] = field(default=None, repr=False)
    _MW: Optional[NDArray[np.float64]] = field(default=None, repr=False)
    _Tc: Optional[NDArray[np.float64]] = field(default=None, repr=False)
    _Pc: Optional[NDArray[np.float64]] = field(default=None, repr=False)
    _Vc: Optional[NDArray[np.float64]] = field(default=None, repr=False)
    _omega: Optional[NDArray[np.float64]] = field(default=None, repr=False)

    def __post_init__(self):
        """Initialize cached arrays."""
        self._build_arrays()

    def _build_arrays(self) -> None:
        """Build numpy arrays from component list."""
        n = len(self.components)
        self._z = np.array([c.z for c in self.components], dtype=np.float64)
        self._MW = np.array([c.MW for c in self.components], dtype=np.float64)
        self._Tc = np.array([c.Tc for c in self.components], dtype=np.float64)
        self._Pc = np.array([c.Pc for c in self.components], dtype=np.float64)
        self._Vc = np.array([c.Vc for c in self.components], dtype=np.float64)
        self._omega = np.array([c.omega for c in self.components], dtype=np.float64)

    @property
    def n_components(self) -> int:
        """Number of components."""
        return len(self.components)

    @property
    def z(self) -> NDArray[np.float64]:
        """Mole fractions array."""
        if self._z is None:
            self._build_arrays()
        return self._z

    @property
    def MW(self) -> NDArray[np.float64]:
        """Molecular weights array (g/mol)."""
        if self._MW is None:
            self._build_arrays()
        return self._MW

    @property
    def Tc(self) -> NDArray[np.float64]:
        """Critical temperatures array (K)."""
        if self._Tc is None:
            self._build_arrays()
        return self._Tc

    @property
    def Pc(self) -> NDArray[np.float64]:
        """Critical pressures array (Pa)."""
        if self._Pc is None:
            self._build_arrays()
        return self._Pc

    @property
    def Vc(self) -> NDArray[np.float64]:
        """Critical molar volumes array (m³/mol)."""
        if self._Vc is None:
            self._build_arrays()
        return self._Vc

    @property
    def omega(self) -> NDArray[np.float64]:
        """Acentric factors array."""
        if self._omega is None:
            self._build_arrays()
        return self._omega

    @property
    def component_names(self) -> List[str]:
        """List of component names."""
        return [c.name for c in self.components]

    @property
    def kij(self) -> Optional[NDArray[np.float64]]:
        """BIP matrix as numpy array."""
        if self.bip_matrix is not None:
            return self.bip_matrix.kij
        return None

    @property
    def MW_mixture(self) -> float:
        """Mixture molecular weight (g/mol)."""
        return float((self.z * self.MW).sum())

    @property
    def z_C7plus(self) -> float:
        """Total mole fraction of C7+ components."""
        total = 0.0
        for c in self.components:
            name = c.name.upper()
            if name.startswith("C") and len(name) > 1:
                try:
                    cn = int(name[1:])
                    if cn >= 7:
                        total += c.z
                except ValueError:
                    pass
        return total

    @classmethod
    def from_composition(
        cls,
        *,
        pure_components: Dict[str, float],
        plus_fraction_z: float,
        plus_fraction_MW: float,
        plus_fraction_SG: float,
        plus_fraction_method: PlusFractionMethod = PlusFractionMethod.PEDERSEN,
        critical_props_method: CriticalPropsMethod = CriticalPropsMethod.RIAZI_DAUBERT,
        acentric_method: AcentricMethod = AcentricMethod.EDMISTER,
        n_scn_end: int = 45,
        build_bips: bool = True,
        bip_method: BIPMethod = BIPMethod.DEFAULT_VALUES,
        normalize: bool = True,
    ) -> "CharacterizedFluid":
        """
        Create a characterized fluid from laboratory composition data.

        Parameters
        ----------
        pure_components : dict
            Dictionary of {component_id: mole_fraction} for resolved components.
            Component IDs should match database (e.g., "N2", "CO2", "C1", ..., "C6").
        plus_fraction_z : float
            Total mole fraction of the plus fraction (e.g., C7+).
        plus_fraction_MW : float
            Molecular weight of plus fraction in g/mol.
        plus_fraction_SG : float
            Specific gravity of plus fraction at 60°F/60°F.
        plus_fraction_method : PlusFractionMethod
            Method for splitting plus fraction.
        critical_props_method : CriticalPropsMethod
            Method for estimating critical properties of pseudo-components.
        acentric_method : AcentricMethod
            Method for estimating acentric factors.
        n_scn_end : int
            Maximum SCN to include in plus-fraction split (default 45).
        build_bips : bool
            Whether to build BIP matrix (default True).
        bip_method : BIPMethod
            Method for BIP estimation.
        normalize : bool
            Whether to normalize total mole fraction to 1.0.

        Returns
        -------
        CharacterizedFluid
            Fully characterized fluid ready for EOS calculations.

        Examples
        --------
        >>> fluid = CharacterizedFluid.from_composition(
        ...     pure_components={
        ...         "N2": 0.005, "CO2": 0.012,
        ...         "C1": 0.45, "C2": 0.08, "C3": 0.05,
        ...         "iC4": 0.01, "nC4": 0.02,
        ...         "iC5": 0.01, "nC5": 0.015,
        ...         "C6": 0.03,
        ...     },
        ...     plus_fraction_z=0.318,
        ...     plus_fraction_MW=215.0,
        ...     plus_fraction_SG=0.85,
        ... )
        """
        if not CORRELATIONS_AVAILABLE:
            raise ImportError(
                "Correlations module not available. "
                "Please ensure pvtcore.correlations is properly installed."
            )

        components: List[FluidComponent] = []

        # Load pure component database
        db_components = get_components_cached()

        # Process pure components
        for comp_id, z in pure_components.items():
            if z <= 0:
                continue

            db_comp = db_components.get(comp_id.upper())
            if db_comp is None:
                raise ValueError(f"Component '{comp_id}' not found in database")

            components.append(FluidComponent(
                name=comp_id,
                z=z,
                MW=db_comp.MW,
                Tc=db_comp.Tc,
                Pc=db_comp.Pc,
                Vc=db_comp.Vc,
                omega=db_comp.omega,
                Tb=db_comp.Tb,
                SG=db_comp.MW / (db_comp.Vc * 1e6),  # Approximate SG
                parachor=estimate_parachor(db_comp.MW, comp_id),
                is_pure=True,
                is_pseudo=False,
            ))

        # Split plus fraction
        if plus_fraction_z > 0:
            # Get SCN properties
            scn_props = get_scn_properties(n_start=7, n_end=n_scn_end)

            # Split using selected method
            if plus_fraction_method == PlusFractionMethod.PEDERSEN:
                split = split_plus_fraction_pedersen(
                    z_plus=plus_fraction_z,
                    MW_plus=plus_fraction_MW,
                    n_start=7,
                    n_end=n_scn_end,
                )
            elif plus_fraction_method == PlusFractionMethod.KATZ:
                split = split_plus_fraction_katz(
                    z_plus=plus_fraction_z,
                    MW_plus=plus_fraction_MW,
                    n_start=7,
                    n_end=n_scn_end,
                )
            elif plus_fraction_method == PlusFractionMethod.KATZ_RESIDUAL:
                def scn_sg_fn(n: np.ndarray) -> np.ndarray:
                    idx = n.astype(int) - 7
                    return scn_props.sg_6060[idx]

                split = katz_residual_plus_split(
                    z_plus=plus_fraction_z,
                    MW_plus=plus_fraction_MW,
                    n_start=7,
                    n_terminal=n_scn_end,
                    SG_plus=plus_fraction_SG,
                    scn_sg_fn=scn_sg_fn,
                )
            elif plus_fraction_method == PlusFractionMethod.LOHRENZ:
                split = split_plus_fraction_lohrenz(
                    z_plus=plus_fraction_z,
                    MW_plus=plus_fraction_MW,
                    n_start=7,
                    n_end=n_scn_end,
                )
            else:
                raise ValueError(f"Unknown plus fraction method: {plus_fraction_method}")

            # Create pseudo-components for each SCN
            for i, n_scn in enumerate(split.n):
                z_i = split.z[i]
                if z_i <= 1e-15:
                    continue

                # Get MW from split result
                MW_i = split.MW[i]

                # Estimate SG for this SCN
                # Use SCN table if available, otherwise interpolate from plus fraction
                scn_idx = n_scn - 7  # Index into scn_props
                split_sg = getattr(split, "sg", None)
                if split_sg is not None:
                    SG_i = split_sg[i]
                    Tb_i = scn_props.tb_k[scn_idx] if scn_idx < len(scn_props.tb_k) else estimate_Tb(
                        MW_i,
                        SG_i,
                        BoilingPointMethod.SOREIDE,
                    )
                elif scn_idx < len(scn_props.sg_6060):
                    SG_i = scn_props.sg_6060[scn_idx]
                    Tb_i = scn_props.tb_k[scn_idx]
                else:
                    # Extrapolate - use correlation
                    SG_i = plus_fraction_SG  # Approximate
                    Tb_i = estimate_Tb(MW_i, SG_i, BoilingPointMethod.SOREIDE)

                # Estimate critical properties
                crit = estimate_critical_props(
                    MW=MW_i,
                    SG=SG_i,
                    Tb=Tb_i,
                    method=critical_props_method,
                )

                # Estimate acentric factor
                omega_i = estimate_omega(
                    Tb=Tb_i,
                    Tc=crit.Tc,
                    Pc=crit.Pc,
                    method=acentric_method,
                )

                # Estimate parachor
                parachor_i = estimate_parachor(MW_i)

                components.append(FluidComponent(
                    name=f"C{n_scn}",
                    z=z_i,
                    MW=MW_i,
                    Tc=crit.Tc,
                    Pc=crit.Pc,
                    Vc=crit.Vc,
                    omega=omega_i,
                    Tb=Tb_i,
                    SG=SG_i,
                    parachor=parachor_i,
                    is_pure=False,
                    is_pseudo=True,
                ))

        # Normalize if requested
        if normalize:
            z_total = sum(c.z for c in components)
            if z_total > 0:
                for c in components:
                    c.z = c.z / z_total

        # Build BIP matrix
        bip_matrix = None
        if build_bips:
            Tc_array = np.array([c.Tc for c in components])
            names = [c.name for c in components]
            bip_matrix = build_bip_matrix(
                component_ids=names,
                Tc=Tc_array,
                method=bip_method,
            )

        return cls(
            components=components,
            bip_matrix=bip_matrix,
            notes=f"Created from composition with {plus_fraction_method.name} splitting",
        )

    def get_lumped(
        self,
        n_groups: int,
        preserve_pure: bool = True,
    ) -> "CharacterizedFluid":
        """
        Create a lumped version of this fluid.

        Parameters
        ----------
        n_groups : int
            Target number of total groups.
        preserve_pure : bool
            If True, keep pure (non-pseudo) components separate.

        Returns
        -------
        CharacterizedFluid
            Lumped fluid with fewer components.
        """
        # Get number of pure components
        n_pure = sum(1 for c in self.components if c.is_pure)

        if preserve_pure and n_pure > 0:
            n_pseudo_groups = n_groups - n_pure
            if n_pseudo_groups < 1:
                n_pseudo_groups = 1
        else:
            n_pseudo_groups = n_groups

        # Perform lumping
        result = lump_by_mw_groups(
            z=self.z,
            MW=self.MW,
            Tc=self.Tc,
            Pc=self.Pc,
            Vc=self.Vc,
            omega=self.omega,
            n_groups=n_groups,
            names=self.component_names,
        )

        # Convert to FluidComponent list
        lumped_components = []
        for lc in result.components:
            # Get parachor for lumped MW
            parachor = estimate_parachor(lc.MW) if CORRELATIONS_AVAILABLE else 0.0

            # Estimate Tb from averaged properties
            Tb_est = 0.7 * lc.Tc  # Rough approximation

            lumped_components.append(FluidComponent(
                name=lc.name,
                z=lc.z,
                MW=lc.MW,
                Tc=lc.Tc,
                Pc=lc.Pc,
                Vc=lc.Vc,
                omega=lc.omega,
                Tb=Tb_est,
                SG=lc.MW / (lc.Vc * 1e6) if lc.Vc > 0 else 0.8,
                parachor=parachor,
                is_pure=False,
                is_pseudo=True,
            ))

        # Build new BIP matrix
        bip_matrix = None
        if self.bip_matrix is not None:
            Tc_array = np.array([c.Tc for c in lumped_components])
            bip_matrix = build_bip_matrix(
                component_ids=[c.name for c in lumped_components],
                Tc=Tc_array,
                method=BIPMethod.DEFAULT_VALUES,
            )

        return CharacterizedFluid(
            components=lumped_components,
            bip_matrix=bip_matrix,
            temperature_ref=self.temperature_ref,
            notes=f"Lumped from {self.n_components} to {len(lumped_components)} components",
        )

    def to_dict(self) -> Dict:
        """
        Convert to dictionary for serialization.

        Returns
        -------
        dict
            Dictionary representation of the fluid.
        """
        return {
            "n_components": self.n_components,
            "components": [
                {
                    "name": c.name,
                    "z": c.z,
                    "MW": c.MW,
                    "Tc": c.Tc,
                    "Pc": c.Pc,
                    "Vc": c.Vc,
                    "omega": c.omega,
                    "Tb": c.Tb,
                    "SG": c.SG,
                    "parachor": c.parachor,
                    "is_pure": c.is_pure,
                    "is_pseudo": c.is_pseudo,
                }
                for c in self.components
            ],
            "notes": self.notes,
        }

    def summary(self) -> str:
        """
        Generate a text summary of the fluid.

        Returns
        -------
        str
            Multi-line summary string.
        """
        lines = [
            "=" * 60,
            "Characterized Fluid Summary",
            "=" * 60,
            f"Number of components: {self.n_components}",
            f"Mixture MW: {self.MW_mixture:.2f} g/mol",
            f"C7+ fraction: {self.z_C7plus:.4f}",
            "",
            "Component Properties:",
            "-" * 60,
            f"{'Name':>8} {'z':>8} {'MW':>8} {'Tc(K)':>8} {'Pc(MPa)':>8} {'omega':>8}",
            "-" * 60,
        ]

        for c in self.components[:20]:  # Limit output
            lines.append(
                f"{c.name:>8} {c.z:>8.4f} {c.MW:>8.2f} {c.Tc:>8.1f} "
                f"{c.Pc/1e6:>8.3f} {c.omega:>8.4f}"
            )

        if len(self.components) > 20:
            lines.append(f"... and {len(self.components) - 20} more components")

        lines.append("-" * 60)

        if self.notes:
            lines.append(f"Notes: {self.notes}")

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"CharacterizedFluid(n_components={self.n_components}, MW_mix={self.MW_mixture:.1f})"

    def __str__(self) -> str:
        return self.summary()


# Make FluidComponent mutable for z normalization
FluidComponent.__setattr__ = object.__setattr__
