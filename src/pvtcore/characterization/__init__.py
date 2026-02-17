"""
Fluid characterization utilities for petroleum reservoir fluids.

This module converts lab-style inputs (resolved components + plus fractions)
into a fully characterized component list ready for EOS calculations.

Main Components:
- CharacterizedFluid: Unified class for characterized fluids
- Plus-fraction splitting: Pedersen, Katz, Lohrenz methods
- SCN properties: Katz-Firoozabadi table + extrapolation
- Lumping/Delumping: Whitson method, K-value interpolation
- BIP correlations: Generalized kij estimation

Usage
-----
>>> from pvtcore.characterization import CharacterizedFluid
>>> fluid = CharacterizedFluid.from_composition(
...     pure_components={"N2": 0.005, "CO2": 0.01, "C1": 0.45, "C2": 0.08},
...     plus_fraction_z=0.25,
...     plus_fraction_MW=215.0,
...     plus_fraction_SG=0.85,
... )
>>> print(fluid)

Or use individual components:
>>> from pvtcore.characterization import split_plus_fraction_pedersen
>>> result = split_plus_fraction_pedersen(z_plus=0.25, MW_plus=215.0)
"""

# Plus-fraction splitting
from .plus_splitting import (
    PedersenSplitResult,
    split_plus_fraction_pedersen,
    KatzSplitResult,
    split_plus_fraction_katz,
    katz_classic_split,
    LohrenzSplitResult,
    split_plus_fraction_lohrenz,
    lohrenz_classic_coefficients,
)

# SCN properties
from .scn_properties import (
    SCNProperties,
    get_scn_properties,
)

# Lumping
from .lumping import (
    LumpedComponent,
    LumpingResult,
    lump_by_mw_groups,
    lump_by_indices,
    lee_mixing_rules,
    suggest_lumping_groups,
)

# Delumping
from .delumping import (
    DelumpingResult,
    delump_kvalue_interpolation,
    delump_simple_distribution,
    create_lump_mapping_from_result,
)

# BIP correlations
from .bip import (
    BIPMethod,
    BIPMatrix,
    build_bip_matrix,
    get_default_bip,
    chueh_prausnitz_kij,
    estimate_hc_hc_kij,
    estimate_n2_hc_kij,
    estimate_co2_hc_kij,
    estimate_h2s_hc_kij,
    scale_c7plus_bips,
)

# Main fluid class
from .fluid import (
    CharacterizedFluid,
    FluidComponent,
    PlusFractionMethod,
)


# Unified pipeline (schema-driven characterization)
from .pipeline import (
    PlusFractionSpec,
    BinaryInteractionOverride,
    CharacterizationConfig,
    SCNLumpingResult,
    CharacterizationResult,
    characterize_fluid,
)

__all__ = [
    # Plus-fraction splitting
    "PedersenSplitResult",
    "split_plus_fraction_pedersen",
    "KatzSplitResult",
    "split_plus_fraction_katz",
    "katz_classic_split",
    "LohrenzSplitResult",
    "split_plus_fraction_lohrenz",
    "lohrenz_classic_coefficients",
    # SCN properties
    "SCNProperties",
    "get_scn_properties",
    # Lumping
    "LumpedComponent",
    "LumpingResult",
    "lump_by_mw_groups",
    "lump_by_indices",
    "lee_mixing_rules",
    "suggest_lumping_groups",
    # Delumping
    "DelumpingResult",
    "delump_kvalue_interpolation",
    "delump_simple_distribution",
    "create_lump_mapping_from_result",
    # BIP
    "BIPMethod",
    "BIPMatrix",
    "build_bip_matrix",
    "get_default_bip",
    "chueh_prausnitz_kij",
    "estimate_hc_hc_kij",
    "estimate_n2_hc_kij",
    "estimate_co2_hc_kij",
    "estimate_h2s_hc_kij",
    "scale_c7plus_bips",
    # Main class
    "CharacterizedFluid",
    "FluidComponent",
    "PlusFractionMethod",
    "CharacterizationConfig",
    "PlusFractionSpec",
    "characterize_fluid",
    "CharacterizationResult",
    "SCNLumpingResult",
    "BinaryInteractionOverride",
]
