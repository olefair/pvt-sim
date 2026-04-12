"""Pydantic schemas for PVT Simulator configuration and results.

These schemas define the strict API contract between the GUI and the
pvtcore engine. All inputs are validated with explicit bounds and units.
Invalid inputs result in hard failures with actionable error messages.

Design principles:
- Strict validation: reject invalid inputs immediately
- Explicit units: all physical quantities have documented units
- Serializable: all schemas can be serialized to JSON for reproducibility
"""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Literal, Optional, Union
import platform
import sys

from pydantic import BaseModel, Field, field_validator, model_validator


# ==============================================================================
# Physical Constants and Bounds
# ==============================================================================

# Pressure bounds (Pa)
PRESSURE_MIN_PA = 1e3        # 0.01 bar - below this, gas behavior breaks down
PRESSURE_MAX_PA = 1e9        # 10,000 bar - far beyond any realistic reservoir

# Temperature bounds (K)
TEMPERATURE_MIN_K = 100.0    # Below this, most hydrocarbons are solid
TEMPERATURE_MAX_K = 800.0    # Above this, thermal cracking dominates

# Composition bounds
COMPOSITION_MIN = 0.0
COMPOSITION_MAX = 1.0
COMPOSITION_SUM_TOLERANCE = 1e-4


# ==============================================================================
# Enumerations
# ==============================================================================

class EOSType(str, Enum):
    """Equation of state selection."""
    PENG_ROBINSON = "peng_robinson"
    SRK = "srk"
    PR78 = "pr78"


class CalculationType(str, Enum):
    """Type of PVT calculation to perform."""
    PT_FLASH = "pt_flash"
    BUBBLE_POINT = "bubble_point"
    DEW_POINT = "dew_point"
    PHASE_ENVELOPE = "phase_envelope"
    CCE = "cce"
    DL = "differential_liberation"
    CVD = "cvd"
    SEPARATOR = "separator"


class PhaseEnvelopeTracingMethod(str, Enum):
    """Execution path for phase-envelope tracing."""
    CONTINUATION = "continuation"
    FIXED_GRID = "fixed_grid"


class PressureUnit(str, Enum):
    """Pressure unit for display/input."""
    PA = "Pa"
    KPA = "kPa"
    MPA = "MPa"
    BAR = "bar"
    PSI = "psi"
    PSIA = "psia"
    ATM = "atm"


class TemperatureUnit(str, Enum):
    """Temperature unit for display/input."""
    K = "K"
    C = "C"
    F = "F"
    R = "R"


class PlusFractionCharacterizationPreset(str, Enum):
    """Requested plus-fraction characterization policy/profile."""

    AUTO = "auto"
    MANUAL = "manual"
    DRY_GAS = "dry_gas"
    CO2_RICH_GAS = "co2_rich_gas"
    GAS_CONDENSATE = "gas_condensate"
    VOLATILE_OIL = "volatile_oil"
    BLACK_OIL = "black_oil"
    SOUR_OIL = "sour_oil"


class RunStatus(str, Enum):
    """Status of a calculation run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConvergenceStatusEnum(str, Enum):
    """Solver convergence status (mirrors pvtcore.core.errors.ConvergenceStatus)."""
    CONVERGED = "converged"
    MAX_ITERS = "max_iterations"
    DIVERGED = "diverged"
    STAGNATED = "stagnated"
    INVALID_INPUT = "invalid_input"
    NUMERIC_ERROR = "numeric_error"


# ==============================================================================
# Unit Conversion Helpers
# ==============================================================================

def pressure_to_pa(value: float, unit: PressureUnit) -> float:
    """Convert pressure from given unit to Pascal."""
    conversions = {
        PressureUnit.PA: 1.0,
        PressureUnit.KPA: 1e3,
        PressureUnit.MPA: 1e6,
        PressureUnit.BAR: 1e5,
        PressureUnit.PSI: 6894.757,
        PressureUnit.PSIA: 6894.757,
        PressureUnit.ATM: 101325.0,
    }
    return value * conversions[unit]


def pressure_from_pa(value: float, unit: PressureUnit) -> float:
    """Convert pressure from Pascal to given unit."""
    conversions = {
        PressureUnit.PA: 1.0,
        PressureUnit.KPA: 1e3,
        PressureUnit.MPA: 1e6,
        PressureUnit.BAR: 1e5,
        PressureUnit.PSI: 6894.757,
        PressureUnit.PSIA: 6894.757,
        PressureUnit.ATM: 101325.0,
    }
    return value / conversions[unit]


def temperature_to_k(value: float, unit: TemperatureUnit) -> float:
    """Convert temperature from given unit to Kelvin."""
    if unit == TemperatureUnit.K:
        return value
    elif unit == TemperatureUnit.C:
        return value + 273.15
    elif unit == TemperatureUnit.F:
        return (value - 32) * 5 / 9 + 273.15
    elif unit == TemperatureUnit.R:
        return value * 5 / 9
    raise ValueError(f"Unknown temperature unit: {unit}")


def temperature_from_k(value: float, unit: TemperatureUnit) -> float:
    """Convert temperature from Kelvin to given unit."""
    if unit == TemperatureUnit.K:
        return value
    elif unit == TemperatureUnit.C:
        return value - 273.15
    elif unit == TemperatureUnit.F:
        return (value - 273.15) * 9 / 5 + 32
    elif unit == TemperatureUnit.R:
        return value * 9 / 5
    raise ValueError(f"Unknown temperature unit: {unit}")


def _validate_descending_pressure_points(
    values: Optional[List[float]],
    *,
    label: str,
    min_points: int,
) -> Optional[List[float]]:
    """Validate an explicit descending pressure schedule in Pa."""
    if values is None:
        return None

    normalized = [float(value) for value in values]
    if len(normalized) < min_points:
        noun = "point" if min_points == 1 else "points"
        raise ValueError(
            f"{label} pressure_points_pa must contain at least {min_points} {noun}"
        )
    for pressure in normalized:
        if pressure < PRESSURE_MIN_PA or pressure > PRESSURE_MAX_PA:
            raise ValueError(
                f"{label} pressure point {pressure} Pa is outside the allowed bounds "
                f"[{PRESSURE_MIN_PA}, {PRESSURE_MAX_PA}]"
            )
    if any(normalized[i] <= normalized[i + 1] for i in range(len(normalized) - 1)):
        raise ValueError(f"{label} pressure_points_pa must be strictly descending")
    return normalized


# ==============================================================================
# Component Configuration
# ==============================================================================

class ComponentEntry(BaseModel):
    """Single component in the fluid composition."""

    component_id: str = Field(
        ...,
        description="Component identifier (e.g., 'C1', 'N2', 'CO2')",
        min_length=1,
        max_length=50
    )
    mole_fraction: float = Field(
        ...,
        ge=COMPOSITION_MIN,
        le=COMPOSITION_MAX,
        description="Mole fraction (0 to 1)"
    )

    @field_validator('component_id')
    @classmethod
    def validate_component_id(cls, v: str) -> str:
        """Validate component ID is not empty and strip whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Component ID cannot be empty")
        return v


class PlusFractionEntry(BaseModel):
    """Aggregate plus-fraction input for characterization."""

    label: str = Field(
        default="C7+",
        min_length=1,
        max_length=50,
        description="User-facing plus-fraction label (for example, 'C7+')",
    )
    cut_start: int = Field(
        default=7,
        ge=1,
        le=200,
        description="First carbon number included in the plus fraction",
    )
    z_plus: float = Field(
        ...,
        gt=0.0,
        le=COMPOSITION_MAX,
        description="Plus-fraction mole fraction",
    )
    mw_plus_g_per_mol: float = Field(
        ...,
        gt=0.0,
        description="Average molecular weight of the plus fraction in g/mol",
    )
    sg_plus_60f: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional plus-fraction specific gravity at 60F/60F",
    )
    characterization_preset: PlusFractionCharacterizationPreset = Field(
        default=PlusFractionCharacterizationPreset.AUTO,
        description=(
            "Requested characterization policy. 'auto' infers a validated family "
            "profile from the feed and calculation type; 'manual' uses the "
            "explicit split/lumping fields as entered."
        ),
    )
    resolved_characterization_preset: Optional[PlusFractionCharacterizationPreset] = Field(
        default=None,
        description="Resolved family preset actually applied after auto/preset policy resolution",
    )
    max_carbon_number: int = Field(
        default=45,
        ge=1,
        le=200,
        description="Maximum SCN carbon number to include when splitting the plus fraction",
    )
    split_mw_model: Literal["paraffin", "table"] = Field(
        default="paraffin",
        description="Pedersen SCN molecular-weight model",
    )
    lumping_enabled: bool = Field(
        default=False,
        description="Whether to lump the detailed SCN split into a smaller pseudo set",
    )
    lumping_n_groups: int = Field(
        default=8,
        ge=1,
        le=200,
        description="Target number of pseudo groups if lumping is enabled",
    )

    @model_validator(mode='after')
    def validate_bounds(self) -> 'PlusFractionEntry':
        if self.resolved_characterization_preset in {
            PlusFractionCharacterizationPreset.AUTO,
            PlusFractionCharacterizationPreset.MANUAL,
        }:
            raise ValueError("resolved_characterization_preset must be a concrete family preset when provided")
        if self.max_carbon_number < self.cut_start:
            raise ValueError("max_carbon_number must be >= cut_start")
        if self.lumping_enabled and self.lumping_n_groups > (self.max_carbon_number - self.cut_start + 1):
            raise ValueError("lumping_n_groups cannot exceed the number of SCNs in the split range")
        return self


class InlineComponentSpec(BaseModel):
    """Explicit user-supplied pseudo-component properties."""

    component_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Identifier used in the composition table for this inline pseudo-component",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Display name for the inline pseudo-component",
    )
    formula: str = Field(
        default="",
        max_length=100,
        description="Optional formula/label for the inline pseudo-component",
    )
    molecular_weight_g_per_mol: float = Field(
        ...,
        gt=0.0,
        description="Molecular weight in g/mol",
    )
    critical_temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Critical temperature in Kelvin",
    )
    critical_pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Critical pressure in Pa",
    )
    omega: float = Field(
        ...,
        ge=-5.0,
        le=10.0,
        description="Acentric factor",
    )

    @field_validator('component_id', 'name', 'formula')
    @classmethod
    def strip_text(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode='after')
    def validate_formula(self) -> 'InlineComponentSpec':
        if not self.component_id:
            raise ValueError("Inline component ID cannot be empty")
        if not self.name:
            raise ValueError("Inline component name cannot be empty")
        if not self.formula:
            self.formula = self.name
        return self


class FluidComposition(BaseModel):
    """Complete fluid composition specification."""

    components: List[ComponentEntry] = Field(
        ...,
        min_length=1,
        description="List of components with mole fractions"
    )
    plus_fraction: Optional[PlusFractionEntry] = Field(
        default=None,
        description="Optional aggregate plus-fraction characterization input",
    )
    inline_components: List[InlineComponentSpec] = Field(
        default_factory=list,
        description="Optional inline pseudo-components not present in the component database",
    )

    @model_validator(mode='after')
    def validate_composition(self) -> 'FluidComposition':
        """Validate that composition sums to 1.0 and has no duplicate IDs."""
        if not self.components and self.plus_fraction is None:
            raise ValueError("At least one component or a plus fraction is required")

        # Check for duplicates
        ids = [c.component_id for c in self.components]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            raise ValueError(f"Duplicate component IDs: {set(duplicates)}")

        if self.plus_fraction is not None and self.inline_components:
            raise ValueError("plus_fraction and inline_components are mutually exclusive in the current app contract")

        inline_ids = [spec.component_id for spec in self.inline_components]
        if len(inline_ids) != len(set(inline_ids)):
            duplicates = [id_ for id_ in inline_ids if inline_ids.count(id_) > 1]
            raise ValueError(f"Duplicate inline component IDs: {set(duplicates)}")

        missing_inline_rows = sorted(set(inline_ids) - set(ids))
        if missing_inline_rows:
            raise ValueError(
                "Each inline component must also appear in components with its mole fraction. "
                f"Missing rows: {missing_inline_rows}"
            )

        if self.plus_fraction is not None and self.plus_fraction.label in ids:
            raise ValueError(
                f"Plus-fraction label '{self.plus_fraction.label}' must not also appear as a component row"
            )

        # Check sum
        total = sum(c.mole_fraction for c in self.components)
        if self.plus_fraction is not None:
            total += self.plus_fraction.z_plus
        if abs(total - 1.0) > COMPOSITION_SUM_TOLERANCE:
            raise ValueError(
                f"Mole fractions must sum to 1.0 (got {total:.8f}). "
                f"Difference: {abs(total - 1.0):.2e}"
            )

        return self


# ==============================================================================
# Calculation Configuration
# ==============================================================================

class SolverSettings(BaseModel):
    """Numerical solver configuration."""

    tolerance: float = Field(
        default=1e-10,
        gt=0,
        lt=1,
        description="Convergence tolerance for iterative solvers"
    )
    max_iterations: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum iterations before failure"
    )
    stagnation_window: int = Field(
        default=10,
        ge=3,
        le=50,
        description="Number of iterations to detect stagnation"
    )
    stagnation_threshold: float = Field(
        default=0.001,
        gt=0,
        lt=1,
        description="Minimum relative improvement to avoid stagnation"
    )


class PTFlashConfig(BaseModel):
    """Configuration for PT flash calculation."""

    pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Pressure in Pascal"
    )
    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Temperature in Kelvin"
    )
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.BAR,
        description="Preferred pressure unit for GUI input/output"
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.C,
        description="Preferred temperature unit for GUI input/output"
    )


class PhaseEnvelopeConfig(BaseModel):
    """Configuration for phase envelope calculation."""

    temperature_min_k: float = Field(
        default=150.0,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Minimum temperature for envelope tracing (K)"
    )
    temperature_max_k: float = Field(
        default=600.0,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Maximum temperature for envelope tracing (K)"
    )
    n_points: int = Field(
        default=50,
        ge=10,
        le=500,
        description="Number of points on each branch"
    )
    tracing_method: PhaseEnvelopeTracingMethod = Field(
        default=PhaseEnvelopeTracingMethod.CONTINUATION,
        description="Tracing implementation to use for phase-envelope execution",
    )

    @field_validator('tracing_method', mode='before')
    @classmethod
    def validate_tracing_method(cls, v):
        if isinstance(v, str) and v.strip().lower() == "continuation_dev":
            return PhaseEnvelopeTracingMethod.CONTINUATION
        return v

    @model_validator(mode='after')
    def validate_temperature_range(self) -> 'PhaseEnvelopeConfig':
        """Ensure min < max temperature."""
        if self.temperature_min_k >= self.temperature_max_k:
            raise ValueError(
                f"temperature_min_k ({self.temperature_min_k}) must be less than "
                f"temperature_max_k ({self.temperature_max_k})"
            )
        return self


class CCEConfig(BaseModel):
    """Configuration for Constant Composition Expansion."""

    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Test temperature (K)"
    )
    pressure_start_pa: Optional[float] = Field(
        default=None,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Starting pressure (Pa)"
    )
    pressure_end_pa: Optional[float] = Field(
        default=None,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Ending pressure (Pa)"
    )
    n_steps: Optional[int] = Field(
        default=20,
        ge=2,
        le=200,
        description="Number of pressure steps"
    )
    pressure_points_pa: Optional[List[float]] = Field(
        default=None,
        description=(
            "Optional explicit descending pressure schedule in Pa. "
            "When provided, it overrides pressure_start_pa/pressure_end_pa/n_steps."
        ),
    )

    @field_validator('pressure_points_pa')
    @classmethod
    def validate_pressure_points(cls, values: Optional[List[float]]) -> Optional[List[float]]:
        return _validate_descending_pressure_points(values, label="CCE", min_points=2)

    @model_validator(mode='after')
    def validate_pressure_range(self) -> 'CCEConfig':
        """Ensure a valid depletion schedule is provided."""
        if self.pressure_points_pa:
            self.pressure_start_pa = self.pressure_points_pa[0]
            self.pressure_end_pa = self.pressure_points_pa[-1]
            self.n_steps = len(self.pressure_points_pa)
            return self

        if (
            self.pressure_start_pa is None
            or self.pressure_end_pa is None
            or self.n_steps is None
        ):
            raise ValueError(
                "CCE requires either pressure_points_pa or "
                "pressure_start_pa/pressure_end_pa/n_steps"
            )
        if self.pressure_start_pa <= self.pressure_end_pa:
            raise ValueError(
                f"pressure_start_pa ({self.pressure_start_pa}) must be greater than "
                f"pressure_end_pa ({self.pressure_end_pa}) for CCE"
            )
        return self


class SaturationPointConfig(BaseModel):
    """Configuration for bubble-point or dew-point calculation."""

    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Flash temperature (K)"
    )
    pressure_initial_pa: Optional[float] = Field(
        default=None,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Optional initial pressure guess (Pa)"
    )
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.BAR,
        description="Preferred pressure unit for GUI input/output"
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.C,
        description="Preferred temperature unit for GUI input/output"
    )


class DLConfig(BaseModel):
    """Configuration for Differential Liberation."""

    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Test temperature (K)"
    )
    bubble_pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Bubble-point pressure (Pa)"
    )
    pressure_end_pa: Optional[float] = Field(
        default=None,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Final depletion pressure (Pa)"
    )
    n_steps: Optional[int] = Field(
        default=15,
        ge=2,
        le=200,
        description="Total number of DL steps, including the bubble-point row"
    )
    pressure_points_pa: Optional[List[float]] = Field(
        default=None,
        description=(
            "Optional explicit descending pressure schedule below the bubble point in Pa. "
            "When provided, it overrides pressure_end_pa/n_steps."
        ),
    )

    @field_validator('pressure_points_pa')
    @classmethod
    def validate_pressure_points(cls, values: Optional[List[float]]) -> Optional[List[float]]:
        return _validate_descending_pressure_points(values, label="DL", min_points=1)

    @model_validator(mode='after')
    def validate_pressure_range(self) -> 'DLConfig':
        """Ensure a valid DL schedule is provided."""
        if self.pressure_points_pa:
            if any(pressure >= self.bubble_pressure_pa for pressure in self.pressure_points_pa):
                raise ValueError(
                    "DL pressure_points_pa must stay strictly below bubble_pressure_pa"
                )
            self.pressure_end_pa = self.pressure_points_pa[-1]
            self.n_steps = len(self.pressure_points_pa) + 1
            return self

        if self.pressure_end_pa is None or self.n_steps is None:
            raise ValueError(
                "DL requires either pressure_points_pa or pressure_end_pa/n_steps"
            )
        if self.bubble_pressure_pa <= self.pressure_end_pa:
            raise ValueError(
                f"bubble_pressure_pa ({self.bubble_pressure_pa}) must be greater than "
                f"pressure_end_pa ({self.pressure_end_pa}) for DL"
            )
        return self


class CVDConfig(BaseModel):
    """Configuration for Constant Volume Depletion."""

    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Test temperature (K)"
    )
    dew_pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Dew-point pressure (Pa)"
    )
    pressure_end_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Final depletion pressure (Pa)"
    )
    n_steps: int = Field(
        default=15,
        ge=5,
        le=200,
        description="Number of pressure steps"
    )

    @model_validator(mode='after')
    def validate_pressure_range(self) -> 'CVDConfig':
        """Ensure dew pressure is greater than final pressure."""
        if self.dew_pressure_pa <= self.pressure_end_pa:
            raise ValueError(
                f"dew_pressure_pa ({self.dew_pressure_pa}) must be greater than "
                f"pressure_end_pa ({self.pressure_end_pa}) for CVD"
            )
        return self


class SeparatorStageConfig(BaseModel):
    """Configuration for a single separator stage."""

    pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Separator pressure (Pa)"
    )
    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Separator temperature (K)"
    )
    name: str = Field(
        default="",
        max_length=100,
        description="Optional stage name"
    )


class SeparatorConfig(BaseModel):
    """Configuration for multi-stage separator train calculation."""

    reservoir_pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Reservoir pressure (Pa)"
    )
    reservoir_temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Reservoir temperature (K)"
    )
    separator_stages: List[SeparatorStageConfig] = Field(
        ...,
        min_length=1,
        description="Separator train stages, ordered by non-increasing pressure"
    )
    include_stock_tank: bool = Field(
        default=True,
        description="Include stock-tank flash stage"
    )

    @model_validator(mode='after')
    def validate_stage_order(self) -> 'SeparatorConfig':
        """Ensure separator stage pressures are non-increasing."""
        pressures = [stage.pressure_pa for stage in self.separator_stages]
        if any(pressures[i] < pressures[i + 1] for i in range(len(pressures) - 1)):
            raise ValueError("separator_stages must be ordered by non-increasing pressure")
        return self


# ==============================================================================
# Main Run Configuration
# ==============================================================================

class RunConfig(BaseModel):
    """Complete configuration for a PVT calculation run.

    This is the single entry point for all calculations. The GUI builds
    this object, validates it, and passes it to the job runner.
    """

    # Identification
    run_id: Optional[str] = Field(
        default=None,
        description="Unique run identifier (auto-generated if not provided)"
    )
    run_name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="User-friendly run name"
    )

    # Fluid specification
    composition: FluidComposition = Field(
        ...,
        description="Fluid composition"
    )

    # Calculation type and parameters
    calculation_type: CalculationType = Field(
        ...,
        description="Type of calculation to perform"
    )

    # EOS selection
    eos_type: EOSType = Field(
        default=EOSType.PENG_ROBINSON,
        description="Equation of state"
    )

    # Binary interaction parameters (optional override)
    binary_interaction: Optional[Dict[str, float]] = Field(
        default=None,
        description="Custom BIP values as {pair_key: kij} where pair_key is 'comp1-comp2'"
    )

    # Calculation-specific configuration (polymorphic)
    pt_flash_config: Optional[PTFlashConfig] = None
    bubble_point_config: Optional[SaturationPointConfig] = None
    dew_point_config: Optional[SaturationPointConfig] = None
    phase_envelope_config: Optional[PhaseEnvelopeConfig] = None
    cce_config: Optional[CCEConfig] = None
    dl_config: Optional[DLConfig] = None
    cvd_config: Optional[CVDConfig] = None
    separator_config: Optional[SeparatorConfig] = None

    # Solver settings
    solver_settings: SolverSettings = Field(
        default_factory=SolverSettings,
        description="Numerical solver configuration"
    )

    @model_validator(mode='after')
    def validate_calculation_config(self) -> 'RunConfig':
        """Ensure the appropriate config is provided for the calculation type."""
        if self.calculation_type == CalculationType.PT_FLASH:
            if self.pt_flash_config is None:
                raise ValueError("pt_flash_config is required for PT_FLASH calculation")
        elif self.calculation_type == CalculationType.BUBBLE_POINT:
            if self.bubble_point_config is None:
                raise ValueError("bubble_point_config is required for BUBBLE_POINT calculation")
        elif self.calculation_type == CalculationType.DEW_POINT:
            if self.dew_point_config is None:
                raise ValueError("dew_point_config is required for DEW_POINT calculation")
        elif self.calculation_type == CalculationType.PHASE_ENVELOPE:
            if self.phase_envelope_config is None:
                raise ValueError("phase_envelope_config is required for PHASE_ENVELOPE calculation")
        elif self.calculation_type == CalculationType.CCE:
            if self.cce_config is None:
                raise ValueError("cce_config is required for CCE calculation")
        elif self.calculation_type == CalculationType.DL:
            if self.dl_config is None:
                raise ValueError("dl_config is required for DL calculation")
        elif self.calculation_type == CalculationType.CVD:
            if self.cvd_config is None:
                raise ValueError("cvd_config is required for CVD calculation")
        elif self.calculation_type == CalculationType.SEPARATOR:
            if self.separator_config is None:
                raise ValueError("separator_config is required for SEPARATOR calculation")
        return self


# ==============================================================================
# Results Schemas
# ==============================================================================

class IterationRecord(BaseModel):
    """Record of a single iteration for diagnostics."""

    iteration: int
    residual: float
    step_norm: Optional[float] = None
    damping: Optional[float] = None
    accepted: bool = True
    timing_ms: Optional[float] = None


class SolverDiagnostics(BaseModel):
    """Detailed solver diagnostics for debugging and analysis."""

    status: ConvergenceStatusEnum
    iterations: int
    final_residual: float
    initial_residual: Optional[float] = None
    n_func_evals: int = 0
    n_jac_evals: int = 0
    iteration_history: List[IterationRecord] = Field(default_factory=list)

    @property
    def residual_reduction(self) -> Optional[float]:
        """Ratio of final to initial residual."""
        if self.initial_residual and self.initial_residual > 0:
            return self.final_residual / self.initial_residual
        return None


class InvariantCheck(BaseModel):
    """Single invariant check result."""

    name: str
    value: float
    threshold: float
    passed: bool
    applicable: bool = True
    details: Optional[Dict[str, Union[float, str]]] = None


class SolverCertificate(BaseModel):
    """Compact certificate containing solver status and invariant checks."""

    status: ConvergenceStatusEnum
    iterations: int
    residual: float
    passed: bool
    checks: List[InvariantCheck] = Field(default_factory=list)


class PTFlashResult(BaseModel):
    """Results from a PT flash calculation."""

    converged: bool
    phase: str  # 'vapor', 'liquid', 'two-phase'
    vapor_fraction: float
    liquid_composition: Dict[str, float]  # component_id -> mole_fraction
    vapor_composition: Dict[str, float]
    K_values: Dict[str, float]
    liquid_fugacity: Dict[str, float]
    vapor_fugacity: Dict[str, float]
    diagnostics: SolverDiagnostics
    certificate: Optional[SolverCertificate] = None


class PhaseEnvelopePoint(BaseModel):
    """Single point on the phase envelope."""

    temperature_k: float
    pressure_pa: float
    point_type: str  # 'bubble', 'dew', 'critical'


class PhaseEnvelopeResult(BaseModel):
    """Results from phase envelope calculation."""

    bubble_curve: List[PhaseEnvelopePoint]
    dew_curve: List[PhaseEnvelopePoint]
    critical_point: Optional[PhaseEnvelopePoint] = None
    cricondenbar: Optional[PhaseEnvelopePoint] = None
    cricondentherm: Optional[PhaseEnvelopePoint] = None
    tracing_method: PhaseEnvelopeTracingMethod = PhaseEnvelopeTracingMethod.CONTINUATION
    continuation_switched: Optional[bool] = None
    critical_source: Optional[str] = None
    bubble_termination_reason: Optional[str] = None
    dew_termination_reason: Optional[str] = None

    @field_validator('tracing_method', mode='before')
    @classmethod
    def validate_result_tracing_method(cls, v):
        if isinstance(v, str) and v.strip().lower() == "continuation_dev":
            return PhaseEnvelopeTracingMethod.CONTINUATION
        return v


class CCEStepResult(BaseModel):
    """Results for a single CCE pressure step."""

    pressure_pa: float
    relative_volume: float
    liquid_fraction: Optional[float] = None
    vapor_fraction: Optional[float] = None
    z_factor: Optional[float] = None


class CCEResult(BaseModel):
    """Results from CCE calculation."""

    temperature_k: float
    saturation_pressure_pa: Optional[float] = None
    steps: List[CCEStepResult]


class BubblePointResult(BaseModel):
    """Results from bubble-point pressure calculation."""

    converged: bool
    pressure_pa: float
    temperature_k: float
    iterations: int
    residual: float
    stable_liquid: bool
    liquid_composition: Dict[str, float]
    vapor_composition: Dict[str, float]
    k_values: Dict[str, float]
    diagnostics: Optional[SolverDiagnostics] = None
    certificate: Optional[SolverCertificate] = None


class DewPointResult(BaseModel):
    """Results from dew-point pressure calculation."""

    converged: bool
    pressure_pa: float
    temperature_k: float
    iterations: int
    residual: float
    stable_vapor: bool
    liquid_composition: Dict[str, float]
    vapor_composition: Dict[str, float]
    k_values: Dict[str, float]
    diagnostics: Optional[SolverDiagnostics] = None
    certificate: Optional[SolverCertificate] = None


class DLStepResult(BaseModel):
    """Results for a single DL pressure step."""

    pressure_pa: float
    rs: float
    bo: float
    bt: float
    vapor_fraction: float
    liquid_moles_remaining: Optional[float] = None


class DLResult(BaseModel):
    """Results from Differential Liberation."""

    temperature_k: float
    bubble_pressure_pa: float
    rsi: float
    boi: float
    converged: bool
    steps: List[DLStepResult]


class CVDStepResult(BaseModel):
    """Results for a single CVD pressure step."""

    pressure_pa: float
    liquid_dropout: float
    cumulative_gas_produced: float
    moles_remaining: Optional[float] = None
    z_two_phase: Optional[float] = None


class CVDResult(BaseModel):
    """Results from Constant Volume Depletion."""

    temperature_k: float
    dew_pressure_pa: float
    initial_z: float
    converged: bool
    steps: List[CVDStepResult]


class SeparatorStageResult(BaseModel):
    """Results for a single separator stage."""

    stage_number: int
    stage_name: str
    pressure_pa: float
    temperature_k: float
    vapor_fraction: Optional[float] = None
    liquid_moles: Optional[float] = None
    vapor_moles: Optional[float] = None
    converged: bool


class SeparatorResult(BaseModel):
    """Results from multi-stage separator train."""

    bo: float
    rs: float
    rs_scf_stb: float
    bg: float
    api_gravity: float
    stock_tank_oil_density: float
    converged: bool
    stages: List[SeparatorStageResult]


# ==============================================================================
# Run Result Container
# ==============================================================================

class RunResult(BaseModel):
    """Complete results from a calculation run."""

    # Run identification
    run_id: str
    run_name: Optional[str] = None

    # Status
    status: RunStatus
    error_message: Optional[str] = None

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Input echo (for reproducibility)
    config: RunConfig

    # Results (polymorphic based on calculation type)
    pt_flash_result: Optional[PTFlashResult] = None
    bubble_point_result: Optional[BubblePointResult] = None
    dew_point_result: Optional[DewPointResult] = None
    phase_envelope_result: Optional[PhaseEnvelopeResult] = None
    cce_result: Optional[CCEResult] = None
    dl_result: Optional[DLResult] = None
    cvd_result: Optional[CVDResult] = None
    separator_result: Optional[SeparatorResult] = None


# ==============================================================================
# Run Manifest (for reproducibility)
# ==============================================================================

class RunManifest(BaseModel):
    """Complete manifest for a calculation run, enabling full reproducibility.

    Every run creates a folder containing:
    - config.json: Input configuration
    - results.json: Calculation results
    - solver_stats.json: Iteration history
    - manifest.json: This file (versions, machine info, timestamps)
    """

    # Identification
    run_id: str
    run_name: Optional[str] = None

    # Timestamps
    created_at: datetime
    completed_at: Optional[datetime] = None

    # Version information
    pvt_simulator_version: str
    python_version: str = Field(default_factory=lambda: sys.version)
    platform: str = Field(default_factory=platform.platform)

    # File checksums (for integrity verification)
    config_sha256: Optional[str] = None
    results_sha256: Optional[str] = None

    # Status
    status: RunStatus
    error_message: Optional[str] = None
