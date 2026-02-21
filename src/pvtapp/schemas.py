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
from typing import Dict, List, Optional, Union
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
COMPOSITION_SUM_TOLERANCE = 1e-6


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


class FluidComposition(BaseModel):
    """Complete fluid composition specification."""

    components: List[ComponentEntry] = Field(
        ...,
        min_length=1,
        description="List of components with mole fractions"
    )

    @model_validator(mode='after')
    def validate_composition(self) -> 'FluidComposition':
        """Validate that composition sums to 1.0 and has no duplicate IDs."""
        if not self.components:
            raise ValueError("At least one component is required")

        # Check for duplicates
        ids = [c.component_id for c in self.components]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            raise ValueError(f"Duplicate component IDs: {set(duplicates)}")

        # Check sum
        total = sum(c.mole_fraction for c in self.components)
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
    pressure_start_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Starting pressure (Pa)"
    )
    pressure_end_pa: float = Field(
        ...,
        ge=PRESSURE_MIN_PA,
        le=PRESSURE_MAX_PA,
        description="Ending pressure (Pa)"
    )
    n_steps: int = Field(
        default=20,
        ge=5,
        le=200,
        description="Number of pressure steps"
    )

    @model_validator(mode='after')
    def validate_pressure_range(self) -> 'CCEConfig':
        """Ensure start > end pressure for depletion."""
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
    def validate_pressure_range(self) -> 'DLConfig':
        """Ensure bubble pressure is greater than final pressure."""
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


class DLStepResult(BaseModel):
    """Results for a single DL pressure step."""

    pressure_pa: float
    rs: float
    bo: float
    bt: float
    vapor_fraction: float


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
