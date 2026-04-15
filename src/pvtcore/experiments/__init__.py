"""Laboratory PVT experiments module.

This module provides simulations of standard laboratory PVT tests:
- CCE (Constant Composition Expansion)
- DL (Differential Liberation)
- CVD (Constant Volume Depletion)
- single-contact swelling tests
- Multi-stage separator calculations

These experiments are fundamental for:
- Characterizing reservoir fluid behavior
- Generating PVT tables for reservoir simulation
- Validating equation of state models

Units Convention:
- Pressure: Pa
- Temperature: K
- Volume: relative to reference volume
- GOR: m³/m³ (scf/STB with conversion)
- Bo: dimensionless (reservoir/stock tank volume)

References
----------
[1] McCain, W.D. (1990). The Properties of Petroleum Fluids.
[2] Pedersen et al. (2015). Phase Behavior of Petroleum Reservoir Fluids.
[3] Whitson & Brule (2000). Phase Behavior. SPE Monograph.
"""

# CCE - Constant Composition Expansion
from .cce import (
    simulate_cce,
    CCEResult,
    CCEStepResult,
)

# DL - Differential Liberation
from .dl import (
    simulate_dl,
    DLResult,
    DLStepResult,
)

# CVD - Constant Volume Depletion
from .cvd import (
    simulate_cvd,
    CVDResult,
    CVDStepResult,
)

# Swelling - Single-contact enrichment
from .swelling import (
    simulate_swelling,
    SwellingResult,
    SwellingStepResult,
)

# Multi-stage separators
from .separators import (
    calculate_separator_train,
    optimize_separator_pressures,
    SeparatorConditions,
    SeparatorStageResult,
    SeparatorTrainResult,
)

__all__ = [
    # CCE
    "simulate_cce",
    "CCEResult",
    "CCEStepResult",
    # DL
    "simulate_dl",
    "DLResult",
    "DLStepResult",
    # CVD
    "simulate_cvd",
    "CVDResult",
    "CVDStepResult",
    # Swelling
    "simulate_swelling",
    "SwellingResult",
    "SwellingStepResult",
    # Separators
    "calculate_separator_train",
    "optimize_separator_pressures",
    "SeparatorConditions",
    "SeparatorStageResult",
    "SeparatorTrainResult",
]
