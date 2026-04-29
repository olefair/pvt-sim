"""Fluid characterization."""

# Plus-fraction splitting
from .plus_splitting import (
    PedersenTBPCutConstraint,
    PedersenSplitResult,
    plus_frac_split_pedersen,
    split_plus_fraction_pedersen,
    KatzResidualSplitResult,
    KatzSplitResult,
    split_plus_fraction_katz,
    katz_classic_split,
    katz_residual_plus_split,
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
    "PedersenTBPCutConstraint",
    "PedersenSplitResult",
    "plus_frac_split_pedersen",
    "split_plus_fraction_pedersen",
    "KatzResidualSplitResult",
    "KatzSplitResult",
    "split_plus_fraction_katz",
    "katz_classic_split",
    "katz_residual_plus_split",
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
