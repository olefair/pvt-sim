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
    STABILITY_ANALYSIS = "stability_analysis"
    BUBBLE_POINT = "bubble_point"
    DEW_POINT = "dew_point"
    PHASE_ENVELOPE = "phase_envelope"
    TBP = "tbp"
    CCE = "cce"
    DL = "differential_liberation"
    CVD = "cvd"
    SWELLING_TEST = "swelling_test"
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


RuntimeComponentBasis = Literal["scn_unlumped", "lumped"]
ReportedComponentBasis = Literal["delumped_scn", "reconstructed_scn"]
DetailedReconstructionComponentBasis = Literal["light_ends_plus_scn", "scn_only"]
PTFlashReportedSurfaceStatus = Literal[
    "available",
    "withheld_single_phase_runtime",
    "unavailable_no_detailed_reconstruction",
    "failed_reconstruction",
]


def describe_runtime_component_basis(basis: Optional[RuntimeComponentBasis]) -> Optional[str]:
    """Return a user-facing label for the runtime component basis."""
    if basis is None:
        return None
    return "SCN (unlumped)" if basis == "scn_unlumped" else "Lumped"


def describe_reported_component_basis(basis: Optional[ReportedComponentBasis]) -> Optional[str]:
    """Return a user-facing label for a reported detailed component basis."""
    if basis is None:
        return None
    return {
        "delumped_scn": "Delumped SCN detail",
        "reconstructed_scn": "Reconstructed SCN thermodynamics",
    }[basis]


def describe_pt_flash_reported_surface_status(
    status: Optional[PTFlashReportedSurfaceStatus],
) -> Optional[str]:
    """Return a user-facing label for PT-flash reported-surface availability."""
    if status is None:
        return None
    return {
        "available": "Available",
        "withheld_single_phase_runtime": "Withheld for single-phase runtime",
        "unavailable_no_detailed_reconstruction": "Unavailable (no detailed reconstruction)",
        "failed_reconstruction": "Reconstruction failed",
    }[status]


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


class StabilityFeedPhase(str, Enum):
    """Feed-phase policy for Michelsen / TPD stability analysis."""

    AUTO = "auto"
    LIQUID = "liquid"
    VAPOR = "vapor"


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


class PlusFractionTBPCutEntry(BaseModel):
    """Optional TBP cut used to constrain Pedersen plus-fraction fitting."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="TBP cut label such as 'C7' or 'C7-C9'",
    )
    z: float = Field(
        ...,
        gt=0.0,
        le=COMPOSITION_MAX,
        description="Cut mole fraction on the assay basis",
    )
    mw: float = Field(
        ...,
        gt=0.0,
        description="Cut molecular weight in g/mol",
    )
    sg: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional cut specific gravity",
    )
    carbon_number: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional explicit cut start carbon number; must match the name suffix/range when provided",
    )
    carbon_number_end: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional explicit cut end carbon number; must match the name suffix/range when provided",
    )
    tb_k: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional cut normal boiling point in Kelvin",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("TBP cut name cannot be empty")
        return normalized

    @model_validator(mode='after')
    def validate_cut_bounds(self) -> 'PlusFractionTBPCutEntry':
        if self.carbon_number_end is not None and self.carbon_number is not None:
            if self.carbon_number_end < self.carbon_number:
                raise ValueError("carbon_number_end must be >= carbon_number")
        return self


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
    split_method: Literal["pedersen", "katz", "lohrenz"] = Field(
        default="pedersen",
        description="Canonical plus-fraction splitting method",
    )
    split_mw_model: Literal["paraffin", "table"] = Field(
        default="paraffin",
        description="Pedersen SCN molecular-weight model",
    )
    pedersen_solve_ab_from: Literal["balances", "fit_to_tbp"] = Field(
        default="balances",
        description="How Pedersen coefficients A/B are resolved when split_method='pedersen'",
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
    lumping_method: Literal["whitson", "contiguous"] = Field(
        default="whitson",
        description="Heavy-end lumping method used when lumping is enabled",
    )
    tbp_cuts: Optional[List[PlusFractionTBPCutEntry]] = Field(
        default=None,
        description="Optional ordered TBP cuts used to constrain Pedersen fit_to_tbp characterization",
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
        if self.tbp_cuts and self.split_method != "pedersen":
            raise ValueError("tbp_cuts are only supported with split_method='pedersen'")
        if self.pedersen_solve_ab_from == "fit_to_tbp":
            if self.split_method != "pedersen":
                raise ValueError("pedersen_solve_ab_from='fit_to_tbp' requires split_method='pedersen'")
            if not self.tbp_cuts:
                raise ValueError("pedersen_solve_ab_from='fit_to_tbp' requires tbp_cuts")
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
    critical_temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.K,
        description="Preferred GUI display unit for the critical temperature",
    )
    critical_pressure_unit: PressureUnit = Field(
        default=PressureUnit.PA,
        description="Preferred GUI display unit for the critical pressure",
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
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output"
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
        description="Preferred temperature unit for GUI input/output"
    )


class StabilityAnalysisConfig(BaseModel):
    """Configuration for standalone Michelsen / TPD stability analysis."""

    pressure_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Pressure in Pascal",
    )
    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Temperature in Kelvin",
    )
    feed_phase: StabilityFeedPhase = Field(
        default=StabilityFeedPhase.AUTO,
        description="Feed-phase policy used to anchor the TPD reference state",
    )
    use_gdem: bool = Field(
        default=True,
        description="Enable GDEM acceleration for the log-space TPD solver",
    )
    n_random_trials: int = Field(
        default=0,
        ge=0,
        le=12,
        description="Additional random seed trials to probe alternative stationary points",
    )
    random_seed: Optional[int] = Field(
        default=0,
        ge=0,
        le=2**31 - 1,
        description="Deterministic seed used when random trials are enabled",
    )
    max_eos_failures_per_trial: int = Field(
        default=5,
        ge=0,
        le=50,
        description="Maximum transient EOS evaluation failures tolerated per trial branch",
    )
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output",
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
        description="Preferred temperature unit for GUI input/output",
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
        default=PhaseEnvelopeTracingMethod.FIXED_GRID,
        description=(
            "Fixed grid: one bubble + one dew saturation solve per temperature node with "
            "pressure warm-start (typical interactive cost, seconds). Continuation: adaptive "
            "branch tracing with critical handling for difficult multi-root fluids (slower)."
        ),
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
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output",
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
        description="Preferred temperature unit for GUI input/output",
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
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output"
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
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
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output",
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
        description="Preferred temperature unit for GUI input/output",
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


class SwellingTestConfig(BaseModel):
    """Configuration for the first-slice swelling-test workflow."""

    temperature_k: float = Field(
        ...,
        ge=TEMPERATURE_MIN_K,
        le=TEMPERATURE_MAX_K,
        description="Test temperature (K)",
    )
    enrichment_steps_mol_per_mol_oil: List[float] = Field(
        ...,
        min_length=1,
        description=(
            "Strictly increasing gas additions expressed as gas moles added "
            "per initial mole of oil. The runtime inserts the baseline row at 0.0."
        ),
    )
    injection_gas_composition: FluidComposition = Field(
        ...,
        description="Explicit resolved injection-gas composition on a component-row basis",
    )
    pressure_unit: PressureUnit = Field(
        default=PressureUnit.PSIA,
        description="Preferred pressure unit for GUI input/output",
    )
    temperature_unit: TemperatureUnit = Field(
        default=TemperatureUnit.F,
        description="Preferred temperature unit for GUI input/output",
    )

    @field_validator("enrichment_steps_mol_per_mol_oil")
    @classmethod
    def validate_enrichment_steps(cls, values: List[float]) -> List[float]:
        normalized = [float(value) for value in values]
        if any(value < 0.0 for value in normalized):
            raise ValueError("enrichment_steps_mol_per_mol_oil must be non-negative")
        if any(normalized[index] >= normalized[index + 1] for index in range(len(normalized) - 1)):
            raise ValueError(
                "enrichment_steps_mol_per_mol_oil must be strictly increasing and duplicate-free"
            )
        return normalized

    @model_validator(mode='after')
    def validate_feed_surface(self) -> 'SwellingTestConfig':
        if self.injection_gas_composition.plus_fraction is not None:
            raise ValueError(
                "swelling_test_config.injection_gas_composition must not define plus_fraction "
                "in the current first-draft runtime surface"
            )
        if self.injection_gas_composition.inline_components:
            raise ValueError(
                "swelling_test_config.injection_gas_composition must not define inline_components "
                "in the current first-draft runtime surface"
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


class TBPCutConfig(BaseModel):
    """Single cut in the standalone TBP assay runtime."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="TBP cut label such as 'C7' or 'C7-C9'",
    )
    z: float = Field(
        ...,
        gt=0.0,
        le=COMPOSITION_MAX,
        description="Cut mole fraction on the assay basis",
    )
    mw: float = Field(
        ...,
        gt=0.0,
        description="Cut molecular weight in g/mol",
    )
    sg: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional cut specific gravity",
    )
    carbon_number: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional explicit cut start carbon number; must match the name suffix/range when provided",
    )
    carbon_number_end: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional explicit cut end carbon number; must match the name suffix/range when provided",
    )
    tb_k: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Optional cut normal boiling point in Kelvin",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("TBP cut name cannot be empty")
        return normalized

    @model_validator(mode='after')
    def validate_cut_bounds(self) -> 'TBPCutConfig':
        if self.carbon_number_end is not None and self.carbon_number is not None:
            if self.carbon_number_end < self.carbon_number:
                raise ValueError("carbon_number_end must be >= carbon_number")
        return self


class TBPConfig(BaseModel):
    """Configuration for the standalone TBP assay runtime."""

    cuts: List[TBPCutConfig] = Field(
        ...,
        min_length=1,
        description="Ordered non-overlapping TBP cuts, including optional intervals and gaps",
    )
    cut_start: Optional[int] = Field(
        default=None,
        ge=1,
        le=200,
        description="Optional expected first carbon number in the assay",
    )


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
    composition: Optional[FluidComposition] = Field(
        default=None,
        description="Fluid composition for EOS-backed calculations",
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
    stability_analysis_config: Optional[StabilityAnalysisConfig] = None
    bubble_point_config: Optional[SaturationPointConfig] = None
    dew_point_config: Optional[SaturationPointConfig] = None
    phase_envelope_config: Optional[PhaseEnvelopeConfig] = None
    tbp_config: Optional[TBPConfig] = None
    cce_config: Optional[CCEConfig] = None
    dl_config: Optional[DLConfig] = None
    cvd_config: Optional[CVDConfig] = None
    swelling_test_config: Optional[SwellingTestConfig] = None
    separator_config: Optional[SeparatorConfig] = None

    # Solver settings
    solver_settings: SolverSettings = Field(
        default_factory=SolverSettings,
        description="Numerical solver configuration"
    )

    @model_validator(mode='after')
    def validate_calculation_config(self) -> 'RunConfig':
        """Ensure the appropriate config is provided for the calculation type."""
        if self.calculation_type == CalculationType.TBP:
            if self.tbp_config is None:
                raise ValueError("tbp_config is required for TBP calculation")
            if self.composition is not None:
                raise ValueError("TBP calculation uses tbp_config only and must not also define composition")
            return self

        if self.composition is None:
            raise ValueError(f"composition is required for {self.calculation_type.value} calculation")

        if self.tbp_config is not None:
            raise ValueError("tbp_config is only valid for TBP calculations")

        if self.calculation_type == CalculationType.PT_FLASH:
            if self.pt_flash_config is None:
                raise ValueError("pt_flash_config is required for PT_FLASH calculation")
        elif self.calculation_type == CalculationType.STABILITY_ANALYSIS:
            if self.stability_analysis_config is None:
                raise ValueError("stability_analysis_config is required for STABILITY_ANALYSIS calculation")
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
        elif self.calculation_type == CalculationType.SWELLING_TEST:
            if self.swelling_test_config is None:
                raise ValueError("swelling_test_config is required for SWELLING_TEST calculation")
            if self.composition.plus_fraction is not None:
                raise ValueError(
                    "composition.plus_fraction is not supported for swelling_test in the current first-draft runtime surface"
                )
            if self.composition.inline_components:
                raise ValueError(
                    "composition.inline_components are not supported for swelling_test in the current first-draft runtime surface"
                )
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
    reported_surface_status: Optional[PTFlashReportedSurfaceStatus] = None
    reported_surface_reason: Optional[str] = None
    reported_component_basis: Optional[ReportedComponentBasis] = None
    reported_liquid_composition: Optional[Dict[str, float]] = None
    reported_vapor_composition: Optional[Dict[str, float]] = None
    reported_k_values: Optional[Dict[str, float]] = None
    reported_liquid_fugacity: Optional[Dict[str, float]] = None
    reported_vapor_fugacity: Optional[Dict[str, float]] = None
    liquid_density_kg_per_m3: Optional[float] = None
    vapor_density_kg_per_m3: Optional[float] = None
    liquid_viscosity_pa_s: Optional[float] = None
    vapor_viscosity_pa_s: Optional[float] = None
    interfacial_tension_n_per_m: Optional[float] = None
    diagnostics: SolverDiagnostics
    certificate: Optional[SolverCertificate] = None

    @property
    def has_reported_thermodynamic_surface(self) -> bool:
        """Return True only when the reported PT-flash surface is complete."""
        return (
            self.reported_component_basis is not None
            and self.reported_liquid_composition is not None
            and self.reported_vapor_composition is not None
            and self.reported_k_values is not None
            and self.reported_liquid_fugacity is not None
            and self.reported_vapor_fugacity is not None
        )

    @property
    def display_liquid_composition(self) -> Dict[str, float]:
        """Return the currently renderable liquid composition surface."""
        if not self.has_reported_thermodynamic_surface:
            return self.liquid_composition
        return self.reported_liquid_composition  # type: ignore[return-value]

    @property
    def display_vapor_composition(self) -> Dict[str, float]:
        """Return the currently renderable vapor composition surface."""
        if not self.has_reported_thermodynamic_surface:
            return self.vapor_composition
        return self.reported_vapor_composition  # type: ignore[return-value]

    @property
    def display_k_values(self) -> Dict[str, float]:
        """Return the currently renderable K-value surface."""
        if not self.has_reported_thermodynamic_surface:
            return self.K_values
        return self.reported_k_values  # type: ignore[return-value]

    @property
    def display_liquid_fugacity(self) -> Dict[str, float]:
        """Return the currently renderable liquid fugacity surface."""
        if not self.has_reported_thermodynamic_surface:
            return self.liquid_fugacity
        return self.reported_liquid_fugacity  # type: ignore[return-value]

    @property
    def display_vapor_fugacity(self) -> Dict[str, float]:
        """Return the currently renderable vapor fugacity surface."""
        if not self.has_reported_thermodynamic_surface:
            return self.vapor_fugacity
        return self.reported_vapor_fugacity  # type: ignore[return-value]

    @property
    def liquid_viscosity_cp(self) -> Optional[float]:
        """Liquid viscosity converted to centipoise for UI display."""
        if self.liquid_viscosity_pa_s is None:
            return None
        return self.liquid_viscosity_pa_s * 1000.0

    @property
    def vapor_viscosity_cp(self) -> Optional[float]:
        """Vapor viscosity converted to centipoise for UI display."""
        if self.vapor_viscosity_pa_s is None:
            return None
        return self.vapor_viscosity_pa_s * 1000.0

    @property
    def interfacial_tension_mn_per_m(self) -> Optional[float]:
        """Interfacial tension converted to mN/m for UI display."""
        if self.interfacial_tension_n_per_m is None:
            return None
        return self.interfacial_tension_n_per_m * 1000.0


class StabilitySeedResultData(BaseModel):
    """Single seed attempt reported on the app/runtime surface."""

    kind: str
    trial_phase: str
    seed_index: int
    seed_label: str
    initial_composition: Dict[str, float]
    composition: Dict[str, float]
    tpd: float
    iterations: int
    converged: bool
    early_exit_unstable: bool
    n_phi_calls: int
    n_eos_failures: int
    message: Optional[str] = None


class StabilityTrialResultData(BaseModel):
    """Aggregated trial-branch diagnostics for standalone stability analysis."""

    kind: str
    trial_phase: str
    composition: Dict[str, float]
    tpd: float
    iterations: int
    total_iterations: int
    converged: bool
    early_exit_unstable: bool
    n_phi_calls: int
    n_eos_failures: int
    message: Optional[str] = None
    best_seed_index: int
    candidate_seed_labels: List[str] = Field(default_factory=list)
    diagnostic_messages: List[str] = Field(default_factory=list)
    seed_results: List[StabilitySeedResultData] = Field(default_factory=list)

    @property
    def seed_attempts(self) -> int:
        return len(self.seed_results)

    @property
    def candidate_seed_count(self) -> int:
        return len(self.candidate_seed_labels)

    @property
    def stopped_early(self) -> bool:
        return self.seed_attempts < self.candidate_seed_count

    @property
    def best_seed(self) -> StabilitySeedResultData:
        return self.seed_results[self.best_seed_index]


class StabilityAnalysisResult(BaseModel):
    """Standalone Michelsen / TPD stability-analysis result."""

    stable: bool
    tpd_min: float
    pressure_pa: float
    temperature_k: float
    requested_feed_phase: StabilityFeedPhase
    resolved_feed_phase: str
    reference_root_used: str
    phase_regime: Literal["single_phase", "two_phase"]
    physical_state_hint: Literal[
        "two_phase",
        "single_phase_vapor_like",
        "single_phase_liquid_like",
        "single_phase_ambiguous",
    ]
    physical_state_hint_basis: Literal[
        "two_phase_regime",
        "direct_root_split",
        "saturation_window",
        "supercritical_guard",
        "no_boundary_guard",
        "heuristic_fallback",
    ] = "heuristic_fallback"
    physical_state_hint_confidence: Literal["high", "medium", "low"] = "low"
    liquid_root_z: Optional[float] = None
    vapor_root_z: Optional[float] = None
    root_gap: Optional[float] = None
    gibbs_gap: Optional[float] = None
    average_reduced_pressure: Optional[float] = None
    bubble_pressure_hint_pa: Optional[float] = None
    dew_pressure_hint_pa: Optional[float] = None
    bubble_boundary_reason: Optional[str] = None
    dew_boundary_reason: Optional[str] = None
    feed_composition: Dict[str, float]
    best_unstable_trial_kind: Optional[str] = None
    vapor_like_trial: Optional[StabilityTrialResultData] = None
    liquid_like_trial: Optional[StabilityTrialResultData] = None

    @model_validator(mode="before")
    @classmethod
    def _backfill_legacy_fields(cls, data):
        """Preserve compatibility with older saved runs."""
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if "reference_root_used" not in normalized and "resolved_reference_phase" in normalized:
            normalized["reference_root_used"] = normalized["resolved_reference_phase"]
        if "phase_regime" not in normalized:
            normalized["phase_regime"] = "single_phase" if normalized.get("stable") else "two_phase"
        if "physical_state_hint" not in normalized:
            normalized["physical_state_hint"] = (
                "two_phase"
                if normalized.get("phase_regime") == "two_phase" or normalized.get("stable") is False
                else "single_phase_ambiguous"
            )
        if "physical_state_hint_basis" not in normalized:
            normalized["physical_state_hint_basis"] = (
                "two_phase_regime"
                if normalized.get("phase_regime") == "two_phase" or normalized.get("stable") is False
                else "heuristic_fallback"
            )
        if "physical_state_hint_confidence" not in normalized:
            normalized["physical_state_hint_confidence"] = (
                "high"
                if normalized.get("phase_regime") == "two_phase" or normalized.get("stable") is False
                else "low"
            )
        return normalized

    @property
    def resolved_reference_phase(self) -> str:
        """Backward-compatible alias for the old field name."""
        return self.reference_root_used


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
    tracing_method: PhaseEnvelopeTracingMethod = PhaseEnvelopeTracingMethod.FIXED_GRID
    continuation_switched: Optional[bool] = None
    critical_source: Optional[str] = None
    bubble_termination_reason: Optional[str] = None
    bubble_termination_temperature_k: Optional[float] = None
    dew_termination_reason: Optional[str] = None
    dew_termination_temperature_k: Optional[float] = None

    @field_validator('tracing_method', mode='before')
    @classmethod
    def validate_result_tracing_method(cls, v):
        if isinstance(v, str) and v.strip().lower() == "continuation_dev":
            return PhaseEnvelopeTracingMethod.CONTINUATION
        return v

    def continuous_curve_points(self) -> List[PhaseEnvelopePoint]:
        """Return bubble rows followed by the dew branch from critical downward."""
        ordered = list(self.bubble_curve)
        dew_descending = list(reversed(self.dew_curve))

        if ordered and dew_descending:
            last_bubble = ordered[-1]
            first_dew = dew_descending[0]
            same_temperature = abs(float(last_bubble.temperature_k) - float(first_dew.temperature_k)) <= 1.0e-12
            same_pressure = abs(float(last_bubble.pressure_pa) - float(first_dew.pressure_pa)) <= 1.0e-9
            if same_temperature and same_pressure:
                dew_descending = dew_descending[1:]

        ordered.extend(dew_descending)
        return ordered

    def continuous_curve_payload(self) -> List[Dict[str, float | str]]:
        """Return the continuous phase-envelope row order as JSON-ready records."""
        return [point.model_dump(mode="json") for point in self.continuous_curve_points()]


class CCEStepResult(BaseModel):
    """Results for a single CCE pressure step."""

    pressure_pa: float
    relative_volume: float
    liquid_fraction: Optional[float] = None
    vapor_fraction: Optional[float] = None
    z_factor: Optional[float] = None
    liquid_density_kg_per_m3: Optional[float] = None
    vapor_density_kg_per_m3: Optional[float] = None
    liquid_viscosity_pa_s: Optional[float] = None
    vapor_viscosity_pa_s: Optional[float] = None
    liquid_composition: Optional[Dict[str, float]] = None
    vapor_composition: Optional[Dict[str, float]] = None

    @property
    def liquid_viscosity_cp(self) -> Optional[float]:
        """Liquid viscosity converted to centipoise for UI display."""
        if self.liquid_viscosity_pa_s is None:
            return None
        return self.liquid_viscosity_pa_s * 1000.0

    @property
    def vapor_viscosity_cp(self) -> Optional[float]:
        """Vapor viscosity converted to centipoise for UI display."""
        if self.vapor_viscosity_pa_s is None:
            return None
        return self.vapor_viscosity_pa_s * 1000.0


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
    reported_component_basis: Optional[ReportedComponentBasis] = None
    reported_liquid_composition: Optional[Dict[str, float]] = None
    reported_vapor_composition: Optional[Dict[str, float]] = None
    reported_k_values: Optional[Dict[str, float]] = None
    diagnostics: Optional[SolverDiagnostics] = None
    certificate: Optional[SolverCertificate] = None

    @property
    def has_reported_surface(self) -> bool:
        """Return True only when the reported saturation surface is complete."""
        return (
            self.reported_component_basis is not None
            and self.reported_liquid_composition is not None
            and self.reported_vapor_composition is not None
            and self.reported_k_values is not None
        )

    @property
    def display_liquid_composition(self) -> Dict[str, float]:
        """Return the user-facing liquid composition basis."""
        return self.liquid_composition if not self.has_reported_surface else self.reported_liquid_composition  # type: ignore[return-value]

    @property
    def display_vapor_composition(self) -> Dict[str, float]:
        """Return the user-facing vapor composition basis."""
        return self.vapor_composition if not self.has_reported_surface else self.reported_vapor_composition  # type: ignore[return-value]

    @property
    def display_k_values(self) -> Dict[str, float]:
        """Return the user-facing K-value basis."""
        return self.k_values if not self.has_reported_surface else self.reported_k_values  # type: ignore[return-value]


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
    reported_component_basis: Optional[ReportedComponentBasis] = None
    reported_liquid_composition: Optional[Dict[str, float]] = None
    reported_vapor_composition: Optional[Dict[str, float]] = None
    reported_k_values: Optional[Dict[str, float]] = None
    diagnostics: Optional[SolverDiagnostics] = None
    certificate: Optional[SolverCertificate] = None

    @property
    def has_reported_surface(self) -> bool:
        """Return True only when the reported saturation surface is complete."""
        return (
            self.reported_component_basis is not None
            and self.reported_liquid_composition is not None
            and self.reported_vapor_composition is not None
            and self.reported_k_values is not None
        )

    @property
    def display_liquid_composition(self) -> Dict[str, float]:
        """Return the user-facing liquid composition basis."""
        return self.liquid_composition if not self.has_reported_surface else self.reported_liquid_composition  # type: ignore[return-value]

    @property
    def display_vapor_composition(self) -> Dict[str, float]:
        """Return the user-facing vapor composition basis."""
        return self.vapor_composition if not self.has_reported_surface else self.reported_vapor_composition  # type: ignore[return-value]

    @property
    def display_k_values(self) -> Dict[str, float]:
        """Return the user-facing K-value basis."""
        return self.k_values if not self.has_reported_surface else self.reported_k_values  # type: ignore[return-value]


class DLStepResult(BaseModel):
    """Results for a single DL pressure step.

    ``rs`` is sm³/sm³; ``rs_scf_stb`` is scf/STB. Conversion lives in
    ``pvtcore.experiments.dl``.
    """

    pressure_pa: float
    rs: float
    rs_scf_stb: float
    bg: Optional[float] = None
    bo: float
    bt: float
    vapor_fraction: float
    oil_density_kg_per_m3: Optional[float] = None
    oil_viscosity_pa_s: Optional[float] = None
    gas_gravity: Optional[float] = None
    gas_z_factor: Optional[float] = None
    gas_viscosity_pa_s: Optional[float] = None
    cumulative_gas_produced: Optional[float] = None
    liquid_moles_remaining: Optional[float] = None
    liquid_composition: Optional[Dict[str, float]] = None
    gas_composition: Optional[Dict[str, float]] = None

    @property
    def oil_viscosity_cp(self) -> Optional[float]:
        """Oil viscosity converted to centipoise for UI display."""
        if self.oil_viscosity_pa_s is None:
            return None
        return self.oil_viscosity_pa_s * 1000.0

    @property
    def gas_viscosity_cp(self) -> Optional[float]:
        """Gas viscosity converted to centipoise for UI display."""
        if self.gas_viscosity_pa_s is None:
            return None
        return self.gas_viscosity_pa_s * 1000.0


class DLResult(BaseModel):
    """Results from Differential Liberation.

    ``rsi`` is sm³/sm³; ``rsi_scf_stb`` is scf/STB.
    """

    temperature_k: float
    bubble_pressure_pa: float
    rsi: float
    rsi_scf_stb: float
    boi: float
    residual_oil_density_kg_per_m3: Optional[float] = None
    converged: bool
    steps: List[DLStepResult]


class CVDStepResult(BaseModel):
    """Results for a single CVD pressure step."""

    pressure_pa: float
    liquid_dropout: float
    gas_produced: Optional[float] = None
    cumulative_gas_produced: float
    moles_remaining: Optional[float] = None
    z_two_phase: Optional[float] = None
    liquid_density_kg_per_m3: Optional[float] = None
    vapor_density_kg_per_m3: Optional[float] = None
    liquid_viscosity_pa_s: Optional[float] = None
    vapor_viscosity_pa_s: Optional[float] = None

    @property
    def liquid_viscosity_cp(self) -> Optional[float]:
        """Liquid viscosity converted to centipoise for UI display."""
        if self.liquid_viscosity_pa_s is None:
            return None
        return self.liquid_viscosity_pa_s * 1000.0

    @property
    def vapor_viscosity_cp(self) -> Optional[float]:
        """Vapor viscosity converted to centipoise for UI display."""
        if self.vapor_viscosity_pa_s is None:
            return None
        return self.vapor_viscosity_pa_s * 1000.0


class CVDResult(BaseModel):
    """Results from Constant Volume Depletion."""

    temperature_k: float
    dew_pressure_pa: float
    initial_z: float
    converged: bool
    steps: List[CVDStepResult]


class SwellingStepResultData(BaseModel):
    """Results for a single swelling-test enrichment step."""

    step_index: int
    added_gas_moles_per_mole_oil: float
    total_mixture_moles_per_mole_oil: float
    bubble_pressure_pa: Optional[float] = None
    swelling_factor: Optional[float] = None
    saturated_liquid_molar_volume_m3_per_mol: Optional[float] = None
    saturated_liquid_density_kg_per_m3: Optional[float] = None
    enriched_feed_composition: Dict[str, float] = Field(default_factory=dict)
    incipient_vapor_composition: Optional[Dict[str, float]] = None
    k_values: Optional[Dict[str, float]] = None
    status: Literal[
        "certified",
        "failed_solver",
        "failed_no_boundary",
        "failed_ambiguous_boundary",
    ]
    message: Optional[str] = None


class SwellingTestResult(BaseModel):
    """Results from the first-slice swelling-test workflow."""

    temperature_k: float
    baseline_bubble_pressure_pa: Optional[float] = None
    baseline_saturated_liquid_molar_volume_m3_per_mol: Optional[float] = None
    enrichment_steps_mol_per_mol_oil: List[float]
    steps: List[SwellingStepResultData]
    bubble_pressures_pa: List[Optional[float]]
    swelling_factors: List[Optional[float]]
    fully_certified: bool
    overall_status: Literal["complete", "partial", "failed"]


class SeparatorStageResult(BaseModel):
    """Results for a single separator stage."""

    stage_number: int
    stage_name: str
    pressure_pa: float
    temperature_k: float
    vapor_fraction: Optional[float] = None
    liquid_moles: Optional[float] = None
    vapor_moles: Optional[float] = None
    liquid_density_kg_per_m3: Optional[float] = None
    vapor_density_kg_per_m3: Optional[float] = None
    liquid_z_factor: Optional[float] = None
    vapor_z_factor: Optional[float] = None
    converged: bool


class SeparatorResult(BaseModel):
    """Results from multi-stage separator train."""

    bo: float
    rs: float
    rs_scf_stb: float
    bg: float
    api_gravity: float
    stock_tank_oil_density: float
    stock_tank_oil_mw_g_per_mol: Optional[float] = None
    stock_tank_oil_specific_gravity: Optional[float] = None
    total_gas_moles: Optional[float] = None
    shrinkage: Optional[float] = None
    converged: bool
    stages: List[SeparatorStageResult]


class TBPExperimentCutResult(BaseModel):
    """Cut-level results for the standalone TBP assay runtime."""

    name: str
    carbon_number: int
    carbon_number_end: int = Field(
        description="End carbon number for interval cuts; equals carbon_number for single cuts",
    )
    mole_fraction: float
    normalized_mole_fraction: float
    cumulative_mole_fraction: float
    molecular_weight_g_per_mol: float
    normalized_mass_fraction: float
    cumulative_mass_fraction: float
    specific_gravity: Optional[float] = None
    boiling_point_k: Optional[float] = None
    boiling_point_source: Optional[Literal["input", "estimated_soreide"]] = None


class TBPCharacterizationPedersenFit(BaseModel):
    """Resolved Pedersen fit metadata for a TBP-derived characterization bridge."""

    solve_ab_from: Literal["balances", "fit_to_tbp"] = Field(
        ...,
        description="How the Pedersen A/B coefficients were resolved",
    )
    A: float
    B: float
    tbp_cut_rms_relative_error: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="RMS relative cut-fit mismatch when TBP cuts constrained the split",
    )


class TBPCharacterizationSCNEntry(BaseModel):
    """Derived SCN-level runtime characterization entry."""

    component_id: str = Field(..., min_length=1, max_length=50)
    carbon_number: int = Field(..., ge=1, le=200)
    assay_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    normalized_mole_fraction: float = Field(..., ge=0.0, le=1.0)
    normalized_mass_fraction: float = Field(..., ge=0.0, le=1.0)
    molecular_weight_g_per_mol: float = Field(..., gt=0.0)
    specific_gravity_60f: float = Field(..., gt=0.0)
    boiling_point_k: float = Field(..., gt=0.0)
    critical_temperature_k: float = Field(..., gt=0.0)
    critical_pressure_pa: float = Field(..., gt=0.0)
    critical_volume_m3_per_mol: float = Field(..., gt=0.0)
    omega: float


class TBPCharacterizationCutMapping(BaseModel):
    """Observed TBP cut compared to the derived SCN split over the same range."""

    cut_name: str = Field(..., min_length=1, max_length=50)
    carbon_number: int = Field(..., ge=1, le=200)
    carbon_number_end: int = Field(..., ge=1, le=200)
    observed_mole_fraction: float = Field(..., gt=0.0, le=COMPOSITION_MAX)
    observed_normalized_mole_fraction: float = Field(..., gt=0.0, le=1.0)
    characterized_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    characterized_normalized_mole_fraction: float = Field(..., ge=0.0, le=1.0)
    characterized_average_molecular_weight_g_per_mol: Optional[float] = Field(
        default=None,
        gt=0.0,
    )
    normalized_relative_error: Optional[float] = None
    scn_members: List[int] = Field(
        default_factory=list,
        description="SCN carbon numbers allocated inside this observed TBP cut",
    )


class TBPCharacterizationContext(BaseModel):
    """Derived heavy-end characterization context for a standalone TBP assay."""

    source: Literal["tbp_assay"] = Field(
        default="tbp_assay",
        description="Source used to derive this heavy-end bridge context",
    )
    bridge_status: Literal["aggregate_only", "characterized_scn"] = Field(
        default="aggregate_only",
        description="Current bridge fidelity into the broader runtime surface",
    )
    plus_fraction_label: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Aggregate plus-fraction label that downstream workflows can reuse",
    )
    cut_start: int = Field(..., ge=1, le=200)
    cut_end: int = Field(..., ge=1, le=200)
    cut_count: int = Field(..., ge=1)
    z_plus: float = Field(..., gt=0.0, le=COMPOSITION_MAX)
    mw_plus_g_per_mol: float = Field(..., gt=0.0)
    sg_plus_60f: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Aggregate plus-fraction specific gravity when explicitly available",
    )
    characterization_method: Optional[str] = Field(
        default=None,
        description="Derived heavy-end characterization method used for the runtime bridge",
    )
    split_mw_model: Optional[str] = Field(
        default=None,
        description="SCN molecular-weight basis used while deriving the bridge context",
    )
    pseudo_property_correlation: Optional[str] = Field(
        default=None,
        description="Pseudo-component property correlation used for the derived SCN property table",
    )
    runtime_component_basis: Optional[RuntimeComponentBasis] = Field(
        default=None,
        description="Component basis represented by the derived runtime characterization context",
    )
    pedersen_fit: Optional[TBPCharacterizationPedersenFit] = None
    cut_mappings: List[TBPCharacterizationCutMapping] = Field(
        default_factory=list,
        description="Observed TBP cuts compared to the derived SCN allocation over the same ranges",
    )
    scn_distribution: List[TBPCharacterizationSCNEntry] = Field(
        default_factory=list,
        description="Derived SCN-level property table and split distribution used by the runtime bridge",
    )
    notes: List[str] = Field(
        default_factory=list,
        description="Auditable limitations and handoff notes for downstream runtime reuse",
    )


class TBPExperimentResult(BaseModel):
    """Results from a standalone TBP assay run."""

    cut_start: int
    cut_end: int
    z_plus: float
    mw_plus_g_per_mol: float
    cuts: List[TBPExperimentCutResult]
    characterization_context: Optional[TBPCharacterizationContext] = None

    @model_validator(mode='after')
    def populate_characterization_context(self) -> 'TBPExperimentResult':
        if self.characterization_context is not None:
            return self

        notes = [
            (
                "Aggregate-only runtime bridge derived from the TBP assay; "
                "downstream split, lumping, BIP, and EOS choices remain separate."
            )
        ]
        if any(cut.specific_gravity is not None for cut in self.cuts):
            notes.append(
                "SG+ is not auto-derived from cut-level specific gravities in the current bridge."
            )

        self.characterization_context = TBPCharacterizationContext(
            plus_fraction_label=f"C{self.cut_start}+",
            cut_start=self.cut_start,
            cut_end=self.cut_end,
            cut_count=len(self.cuts),
            z_plus=self.z_plus,
            mw_plus_g_per_mol=self.mw_plus_g_per_mol,
            sg_plus_60f=None,
            notes=notes,
        )
        return self


class RuntimeCharacterizationSCNEntry(BaseModel):
    """Resolved SCN-level characterization entry preserved for runtime reuse."""

    component_id: str = Field(..., min_length=1, max_length=50)
    carbon_number: int = Field(..., ge=1, le=200)
    feed_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    normalized_plus_mole_fraction: float = Field(..., ge=0.0, le=1.0)
    normalized_plus_mass_fraction: float = Field(..., ge=0.0, le=1.0)
    molecular_weight_g_per_mol: float = Field(..., gt=0.0)
    specific_gravity_60f: float = Field(..., gt=0.0)
    boiling_point_k: float = Field(..., gt=0.0)
    critical_temperature_k: float = Field(..., gt=0.0)
    critical_pressure_pa: float = Field(..., gt=0.0)
    critical_volume_m3_per_mol: float = Field(..., gt=0.0)
    omega: float


class RuntimeCharacterizationLumpMember(BaseModel):
    """SCN member retained inside a runtime lump for delumping reconstruction."""

    component_id: str = Field(..., min_length=1, max_length=50)
    carbon_number: int = Field(..., ge=1, le=200)
    feed_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    normalized_plus_mole_fraction: float = Field(..., ge=0.0, le=1.0)
    delumping_weight: float = Field(..., ge=0.0, le=1.0)


class RuntimeCharacterizationLumpEntry(BaseModel):
    """Lumped runtime heavy-end group plus the SCN members needed to delump it."""

    component_id: str = Field(..., min_length=1, max_length=50)
    carbon_number_start: int = Field(..., ge=1, le=200)
    carbon_number_end: int = Field(..., ge=1, le=200)
    feed_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    normalized_plus_mole_fraction: float = Field(..., ge=0.0, le=1.0)
    molecular_weight_g_per_mol: float = Field(..., gt=0.0)
    member_count: int = Field(..., ge=1)
    members: List[RuntimeCharacterizationLumpMember] = Field(default_factory=list)


class RuntimeReconstructionComponentEntry(BaseModel):
    """Detailed-basis component entry preserved for a second EOS pass."""

    component_id: str = Field(..., min_length=1, max_length=50)
    source: Literal["resolved_feed_component", "characterized_scn"] = Field(
        ...,
        description="Whether this detailed component came from the resolved feed or SCN characterization",
    )
    feed_mole_fraction: float = Field(..., ge=0.0, le=COMPOSITION_MAX)
    molecular_weight_g_per_mol: float = Field(..., gt=0.0)
    critical_temperature_k: float = Field(..., gt=0.0)
    critical_pressure_pa: float = Field(..., gt=0.0)
    critical_volume_m3_per_mol: float = Field(..., gt=0.0)
    omega: float
    boiling_point_k: Optional[float] = Field(default=None, gt=0.0)
    specific_gravity_60f: Optional[float] = Field(default=None, gt=0.0)


class RuntimeReconstructionBIPProvenance(BaseModel):
    """How the preserved detailed-basis BIP matrix was materialized."""

    source: Literal["characterization_static_matrix"] = Field(
        default="characterization_static_matrix",
        description="Detailed BIP matrix source used for reconstruction",
    )
    materialization: Literal["stored_matrix"] = Field(
        default="stored_matrix",
        description="Whether the detailed matrix is stored directly or must be rebuilt",
    )
    temperature_policy: Literal["static"] = Field(
        default="static",
        description="Whether the preserved detailed matrix is temperature-dependent",
    )
    materialized_temperature_k: Optional[float] = Field(
        default=None,
        gt=0.0,
        description="Run temperature used to materialize the matrix when temperature-dependent",
    )
    default_kij: float = Field(
        default=0.0,
        description="Default kij used before applying explicit overrides in the current runtime path",
    )
    override_pairs: List[str] = Field(
        default_factory=list,
        description="Override pair selectors applied while building the preserved detailed matrix",
    )
    notes: List[str] = Field(default_factory=list)


class RuntimeDetailedReconstructionContext(BaseModel):
    """Detailed component basis preserved for honest second-pass reconstruction."""

    component_basis: DetailedReconstructionComponentBasis = Field(
        ...,
        description="Detailed component basis preserved for second-pass reconstruction",
    )
    components: List[RuntimeReconstructionComponentEntry] = Field(
        default_factory=list,
        description="Ordered detailed component entries; matrix rows and columns follow this order",
    )
    binary_interaction_matrix: List[List[float]] = Field(
        default_factory=list,
        description="Stored detailed-basis BIP matrix aligned to the preserved component order",
    )
    bip_provenance: RuntimeReconstructionBIPProvenance
    notes: List[str] = Field(default_factory=list)


class RuntimeCharacterizationResult(BaseModel):
    """Reusable heavy-end characterization package preserved alongside a run."""

    source: Literal["plus_fraction_runtime", "tbp_assay"] = Field(
        ...,
        description="Where the preserved runtime characterization originated",
    )
    plus_fraction_label: str = Field(..., min_length=1, max_length=50)
    cut_start: int = Field(..., ge=1, le=200)
    cut_end: int = Field(..., ge=1, le=200)
    z_plus: float = Field(..., gt=0.0, le=COMPOSITION_MAX)
    mw_plus_g_per_mol: float = Field(..., gt=0.0)
    sg_plus_60f: Optional[float] = Field(default=None, gt=0.0)
    split_method: Literal["pedersen", "katz", "lohrenz"] = Field(
        ...,
        description="Configured runtime split method that produced the preserved SCN basis",
    )
    split_mw_model: Optional[Literal["paraffin", "table"]] = Field(default=None)
    pseudo_property_correlation: Optional[str] = Field(default=None)
    lumping_method: Optional[Literal["whitson", "contiguous"]] = Field(
        default=None,
        description="Lumping method actually used when the runtime solved on lumped heavy-end groups",
    )
    runtime_component_basis: RuntimeComponentBasis = Field(
        ...,
        description="Whether the actual runtime solved on full SCNs or lumped heavy-end groups",
    )
    runtime_component_ids: List[str] = Field(
        default_factory=list,
        description="Component IDs used by the runtime after heavy-end preparation",
    )
    pedersen_fit: Optional[TBPCharacterizationPedersenFit] = None
    cut_mappings: List[TBPCharacterizationCutMapping] = Field(default_factory=list)
    scn_distribution: List[RuntimeCharacterizationSCNEntry] = Field(default_factory=list)
    lump_distribution: List[RuntimeCharacterizationLumpEntry] = Field(default_factory=list)
    delumping_basis: Optional[Literal["feed_scn_distribution"]] = Field(default=None)
    detailed_reconstruction: Optional[RuntimeDetailedReconstructionContext] = Field(
        default=None,
        description="Detailed-basis component and BIP payload preserved for a second EOS pass",
    )
    detailed_reconstruction_unavailable_reason: Optional[str] = Field(
        default=None,
        description="Explicit reason when a detailed reconstruction payload could not be preserved",
    )
    notes: List[str] = Field(default_factory=list)


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
    stability_analysis_result: Optional[StabilityAnalysisResult] = None
    bubble_point_result: Optional[BubblePointResult] = None
    dew_point_result: Optional[DewPointResult] = None
    phase_envelope_result: Optional[PhaseEnvelopeResult] = None
    tbp_result: Optional[TBPExperimentResult] = None
    cce_result: Optional[CCEResult] = None
    dl_result: Optional[DLResult] = None
    cvd_result: Optional[CVDResult] = None
    swelling_test_result: Optional[SwellingTestResult] = None
    separator_result: Optional[SeparatorResult] = None
    runtime_characterization: Optional[RuntimeCharacterizationResult] = None


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
