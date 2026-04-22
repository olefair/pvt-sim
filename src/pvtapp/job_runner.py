"""Job runner and artifact writer for PVT calculations.

This module handles:
- Executing calculations from RunConfig
- Writing run artifacts (config, results, manifest) to run folders
- Managing run history index
- Providing progress callbacks for GUI integration

Design principles:
- No UI imports: this is pure Python, callable from CLI or GUI
- Deterministic: same config produces same results (within numeric tolerance)
- Auditable: every run creates a complete artifact trail
"""

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import numpy as np

from pvtcore.core.constants import R, SC_IMPERIAL
from pvtapp.schemas import (
    RunConfig, RunResult, RunManifest, RunStatus,
    CalculationType, EOSType, PhaseEnvelopeTracingMethod,
    PlusFractionCharacterizationPreset,
    TBPExperimentResult, TBPExperimentCutResult,
    TBPCharacterizationContext, TBPCharacterizationCutMapping,
    TBPCharacterizationPedersenFit, TBPCharacterizationSCNEntry,
    RuntimeCharacterizationResult, RuntimeCharacterizationSCNEntry,
    RuntimeCharacterizationLumpEntry, RuntimeCharacterizationLumpMember,
    RuntimeDetailedReconstructionContext, RuntimeReconstructionComponentEntry,
    RuntimeReconstructionBIPProvenance,
    PTFlashResult, PhaseEnvelopeResult, PhaseEnvelopePoint,
    StabilityAnalysisResult, StabilityTrialResultData, StabilitySeedResultData,
    CCEResult, CCEStepResult,
    BubblePointResult, DewPointResult,
    DLResult, DLStepResult,
    CVDResult, CVDStepResult,
    SwellingTestResult, SwellingStepResultData,
    SeparatorResult, SeparatorStageResult,
    SolverDiagnostics, IterationRecord, ConvergenceStatusEnum,
    InvariantCheck, SolverCertificate,
)
from pvtapp import __version__
from pvtapp.capabilities import RUNTIME_UNSUPPORTED_EOS_MESSAGES
from pvtapp.plus_fraction_policy import resolve_plus_fraction_entry


# ==============================================================================
# Run Directory Management
# ==============================================================================

def get_default_runs_directory() -> Path:
    """Get the default directory for storing run artifacts.

    On Windows: %LOCALAPPDATA%/PVTSimulator/runs
    On Unix: ~/.pvtsimulator/runs
    """
    if os.name == 'nt':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
    else:
        base = Path.home() / '.pvtsimulator'

    runs_dir = base / 'PVTSimulator' / 'runs'
    runs_dir.mkdir(parents=True, exist_ok=True)
    return runs_dir


def create_run_directory(run_id: str, base_dir: Optional[Path] = None) -> Path:
    """Create a directory for a new run.

    Args:
        run_id: Unique run identifier
        base_dir: Base directory for runs (default: get_default_runs_directory())

    Returns:
        Path to the created run directory
    """
    if base_dir is None:
        base_dir = get_default_runs_directory()

    # Use timestamp prefix for chronological ordering
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"{timestamp}_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


# ==============================================================================
# Artifact Writing
# ==============================================================================

def write_config_artifact(config: RunConfig, run_dir: Path) -> Path:
    """Write configuration to config.json in run directory."""
    config_path = run_dir / 'config.json'
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(mode='json'), f, indent=2, default=str)
    return config_path


def write_results_artifact(result: RunResult, run_dir: Path) -> Path:
    """Write results to results.json in run directory."""
    results_path = run_dir / 'results.json'
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(result.model_dump(mode='json'), f, indent=2, default=str)
    return results_path


def write_manifest_artifact(manifest: RunManifest, run_dir: Path) -> Path:
    """Write manifest to manifest.json in run directory."""
    manifest_path = run_dir / 'manifest.json'
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest.model_dump(mode='json'), f, indent=2, default=str)
    return manifest_path


def write_solver_stats_artifact(diagnostics: SolverDiagnostics, run_dir: Path) -> Path:
    """Write solver statistics to solver_stats.json in run directory."""
    stats_path = run_dir / 'solver_stats.json'
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(diagnostics.model_dump(mode='json'), f, indent=2, default=str)
    return stats_path


# ==============================================================================
# Progress Callback Protocol
# ==============================================================================

class ProgressCallback:
    """Protocol for progress updates during calculation.

    GUI can provide an implementation to update progress bars and status.
    """

    def on_started(self, run_id: str, calculation_type: str) -> None:
        """Called when calculation starts."""
        pass

    def on_progress(self, run_id: str, progress: float, message: str) -> None:
        """Called during calculation with progress (0.0 to 1.0)."""
        pass

    def on_completed(self, run_id: str, result: RunResult) -> None:
        """Called when calculation completes successfully."""
        pass

    def on_failed(self, run_id: str, error: str) -> None:
        """Called when calculation fails."""
        pass

    def on_cancelled(self, run_id: str) -> None:
        """Called when calculation is cancelled."""
        pass

    def is_cancelled(self) -> bool:
        """Return whether the current run should stop cooperatively."""
        return False


class CalculationCancelledError(RuntimeError):
    """Raised when the caller requests cooperative cancellation."""


def _raise_if_cancelled(
    callback: Optional[ProgressCallback],
    *,
    message: str = "Calculation was cancelled by user",
) -> None:
    """Abort the current run if the callback reports cancellation."""
    is_cancelled = getattr(callback, "is_cancelled", None)
    if callback is not None and callable(is_cancelled) and bool(is_cancelled()):
        raise CalculationCancelledError(message)


_C2_TO_C6_IDS = ("C2", "C3", "IC4", "C4", "IC5", "C5", "C6")
PLUS_FRACTION_TBP_Z_ABS_TOLERANCE = 1e-12
PLUS_FRACTION_TBP_MW_ABS_TOLERANCE = 1e-9


@dataclass(frozen=True)
class PreparedFluidContext:
    """First-class runtime package produced by canonical fluid preparation."""

    component_ids: list[str]
    components: list[object]
    composition: np.ndarray
    eos: object
    binary_interaction: np.ndarray | None
    characterization_result: object | None = None
    runtime_characterization: RuntimeCharacterizationResult | None = None
    detailed_reconstruction: RuntimeDetailedReconstructionContext | None = None
    detailed_reconstruction_unavailable_reason: str | None = None


@dataclass(frozen=True)
class PreparedSwellingContext:
    """Explicit two-feed swelling runtime package on a shared component basis."""

    component_ids: list[str]
    components: list[object]
    oil_composition: np.ndarray
    injection_gas_composition: np.ndarray
    eos: object
    binary_interaction: np.ndarray | None


@dataclass(frozen=True)
class ReportedEquilibriumCompositions:
    """User-facing equilibrium compositions derived from the runtime solve basis."""

    component_basis: str
    liquid_composition: dict[str, float]
    vapor_composition: dict[str, float]
    k_values: dict[str, float]


@dataclass(frozen=True)
class DelumpedRuntimeEquilibriumSurface:
    """Detailed equilibrium surface reconstructed from a lumped runtime solve."""

    component_ids: list[str]
    liquid_composition: np.ndarray
    vapor_composition: np.ndarray
    k_values: np.ndarray


@dataclass(frozen=True)
class ReportedPTFlashThermodynamicSurface:
    """User-facing PT-flash thermodynamic surface reconstructed on SCNs."""

    component_basis: str
    liquid_composition: dict[str, float]
    vapor_composition: dict[str, float]
    k_values: dict[str, float]
    liquid_fugacity: dict[str, float]
    vapor_fugacity: dict[str, float]


@dataclass(frozen=True)
class ReportedPTFlashSurfaceOutcome:
    """Availability and diagnostics for the optional reported PT-flash surface."""

    surface: ReportedPTFlashThermodynamicSurface | None
    status: str | None = None
    reason: str | None = None


def _phase_envelope_component_fractions(config: RunConfig) -> Dict[str, float]:
    """Resolve the feed into canonical component fractions for runtime family selection."""
    from pvtcore.models import load_components, resolve_component_id

    all_components = load_components()
    fractions: Dict[str, float] = {}
    inline_ids = {spec.component_id for spec in config.composition.inline_components}
    for entry in config.composition.components:
        raw_id = entry.component_id
        if raw_id in inline_ids:
            canonical_id = raw_id.strip().upper()
        else:
            try:
                canonical_id = resolve_component_id(raw_id, all_components).upper()
            except KeyError:
                canonical_id = raw_id.strip().upper()
        fractions[canonical_id] = fractions.get(canonical_id, 0.0) + float(entry.mole_fraction)
    return fractions


def _infer_phase_envelope_runtime_family(config: RunConfig) -> str:
    """Classify the feed into the closest continuation runtime baseline family."""
    plus_fraction = config.composition.plus_fraction
    fractions = _phase_envelope_component_fractions(config)
    methane = fractions.get("C1", 0.0)
    co2 = fractions.get("CO2", 0.0)
    h2s = fractions.get("H2S", 0.0)
    acid = co2 + h2s
    c2_to_c6 = sum(fractions.get(component_id, 0.0) for component_id in _C2_TO_C6_IDS)
    plus_z = 0.0 if plus_fraction is None else float(plus_fraction.z_plus)

    resolved_preset = None
    if plus_fraction is not None:
        resolved_preset = (
            plus_fraction.resolved_characterization_preset
            if plus_fraction.resolved_characterization_preset not in {
                None,
                PlusFractionCharacterizationPreset.AUTO,
                PlusFractionCharacterizationPreset.MANUAL,
            }
            else None
        )

    if resolved_preset is PlusFractionCharacterizationPreset.CO2_RICH_GAS:
        return "co2_rich_gas"
    if resolved_preset is PlusFractionCharacterizationPreset.DRY_GAS:
        return "dry_gas"
    if resolved_preset is PlusFractionCharacterizationPreset.VOLATILE_OIL:
        return "volatile_oil"
    if resolved_preset is PlusFractionCharacterizationPreset.BLACK_OIL:
        return "black_oil"
    if resolved_preset is PlusFractionCharacterizationPreset.SOUR_OIL:
        return "sour_oil"
    if resolved_preset is PlusFractionCharacterizationPreset.GAS_CONDENSATE:
        return "gas_condensate_heavy" if (plus_z >= 0.08 or c2_to_c6 >= 0.28) else "gas_condensate_light"

    gas_like = methane >= 0.55 and plus_z <= 0.12
    if gas_like:
        if acid >= 0.20:
            return "co2_rich_gas"
        if plus_z >= 0.035 or c2_to_c6 >= 0.20:
            return "gas_condensate_heavy" if (plus_z >= 0.08 or c2_to_c6 >= 0.28) else "gas_condensate_light"
        return "dry_gas"

    if h2s >= 0.05 or acid >= 0.10:
        return "sour_oil"
    if methane >= 0.25:
        return "volatile_oil"
    return "black_oil"


# ==============================================================================
# Calculation Execution
# ==============================================================================

def _convert_convergence_status(status) -> ConvergenceStatusEnum:
    """Convert pvtcore ConvergenceStatus to schema enum."""
    from pvtcore.core.errors import ConvergenceStatus

    mapping = {
        ConvergenceStatus.CONVERGED: ConvergenceStatusEnum.CONVERGED,
        ConvergenceStatus.MAX_ITERS: ConvergenceStatusEnum.MAX_ITERS,
        ConvergenceStatus.DIVERGED: ConvergenceStatusEnum.DIVERGED,
        ConvergenceStatus.STAGNATED: ConvergenceStatusEnum.STAGNATED,
        ConvergenceStatus.INVALID_INPUT: ConvergenceStatusEnum.INVALID_INPUT,
        ConvergenceStatus.NUMERIC_ERROR: ConvergenceStatusEnum.NUMERIC_ERROR,
    }
    return mapping.get(status, ConvergenceStatusEnum.NUMERIC_ERROR)


def _build_solver_diagnostics(solver_result) -> SolverDiagnostics:
    """Build SolverDiagnostics from a pvtcore result with optional iteration history."""
    history_records = []
    if solver_result.history is not None:
        for i, residual in enumerate(solver_result.history.residuals):
            record = IterationRecord(
                iteration=i + 1,
                residual=residual,
                step_norm=solver_result.history.step_norms[i] if i < len(solver_result.history.step_norms) else None,
                damping=solver_result.history.damping_factors[i] if i < len(solver_result.history.damping_factors) else None,
                accepted=solver_result.history.accepted[i] if i < len(solver_result.history.accepted) else True,
                timing_ms=solver_result.history.timings_ms[i] if i < len(solver_result.history.timings_ms) else None,
            )
            history_records.append(record)

    return SolverDiagnostics(
        status=_convert_convergence_status(solver_result.status),
        iterations=solver_result.iterations,
        final_residual=solver_result.residual,
        initial_residual=solver_result.history.initial_residual if solver_result.history else None,
        n_func_evals=solver_result.history.n_func_evals if solver_result.history else 0,
        n_jac_evals=solver_result.history.n_jac_evals if solver_result.history else 0,
        iteration_history=history_records,
    )


def _build_solver_certificate(flash_result) -> Optional[SolverCertificate]:
    """Build SolverCertificate schema from pvtcore certificate."""
    cert = getattr(flash_result, "certificate", None)
    if cert is None:
        return None

    try:
        status = ConvergenceStatusEnum[cert.status]
    except Exception:
        status = ConvergenceStatusEnum.NUMERIC_ERROR

    checks = []
    for check in cert.checks:
        checks.append(InvariantCheck(
            name=check.name,
            value=float(check.value),
            threshold=float(check.threshold),
            passed=bool(check.passed),
            applicable=bool(check.applicable),
            details=check.details,
        ))

    return SolverCertificate(
        status=status,
        iterations=int(cert.iterations),
        residual=float(cert.residual),
        passed=bool(cert.passed),
        checks=checks,
    )


def _resolve_stability_reference_root_used(feed_phase_label: str) -> str:
    """Collapse the additive stability feed-phase label to the actual EOS root used."""
    if feed_phase_label.startswith("auto_selected:"):
        return feed_phase_label.split(":", 1)[1]
    return feed_phase_label


def _classify_stability_phase_regime(stable: bool) -> str:
    """Return a conservative physical regime label for the standalone stability surface."""
    return "single_phase" if stable else "two_phase"


@dataclass(frozen=True)
class _PhysicalStateHintProvenance:
    """Structured interpretation result for the standalone stability surface."""

    hint: str
    basis: str
    confidence: str
    liquid_root_z: float | None = None
    vapor_root_z: float | None = None
    root_gap: float | None = None
    gibbs_gap: float | None = None
    average_reduced_pressure: float | None = None
    bubble_pressure_hint_pa: float | None = None
    dew_pressure_hint_pa: float | None = None
    bubble_boundary_reason: str | None = None
    dew_boundary_reason: str | None = None


def _infer_stability_physical_state_hint(
    *,
    stable: bool,
    pressure_pa: float,
    temperature_k: float,
    composition: np.ndarray,
    eos,
    binary_interaction: np.ndarray | None,
) -> _PhysicalStateHintProvenance:
    """Infer a conservative single-phase physical-state hint for stability results.

    The goal is not to force a liquid/vapor label in every stable state. We
    only emit a vapor-like or liquid-like hint when the EOS evidence is strong;
    otherwise the result remains explicitly ambiguous.
    """
    if not stable:
        return _PhysicalStateHintProvenance(
            hint="two_phase",
            basis="two_phase_regime",
            confidence="high",
        )

    from pvtcore.core.errors import PhaseError
    from pvtcore.flash import calculate_bubble_point, calculate_dew_point

    try:
        roots_raw = eos.compressibility(
            pressure_pa,
            temperature_k,
            composition,
            phase="auto",
            binary_interaction=binary_interaction,
        )
        z_liquid = float(
            eos.compressibility(
                pressure_pa,
                temperature_k,
                composition,
                phase="liquid",
                binary_interaction=binary_interaction,
            )
        )
        z_vapor = float(
            eos.compressibility(
                pressure_pa,
                temperature_k,
                composition,
                phase="vapor",
                binary_interaction=binary_interaction,
            )
        )
        phi_liquid = eos.fugacity_coefficient(
            pressure_pa,
            temperature_k,
            composition,
            "liquid",
            binary_interaction,
        )
        phi_vapor = eos.fugacity_coefficient(
            pressure_pa,
            temperature_k,
            composition,
            "vapor",
            binary_interaction,
        )
    except Exception:
        return _PhysicalStateHintProvenance(
            hint="single_phase_ambiguous",
            basis="heuristic_fallback",
            confidence="low",
        )

    if isinstance(roots_raw, (list, tuple, np.ndarray)):
        roots = [float(root) for root in roots_raw]
    else:
        roots = [float(roots_raw)]

    g_liquid = float(np.sum(composition * np.log(phi_liquid)))
    g_vapor = float(np.sum(composition * np.log(phi_vapor)))
    gibbs_gap = abs(g_liquid - g_vapor)
    root_gap = abs(z_vapor - z_liquid)
    pc_avg = float(np.sum(composition * np.array([component.Pc for component in eos.components], dtype=float)))
    p_reduced = pressure_pa / pc_avg if pc_avg > 0.0 else np.inf
    pure_component_supercritical = (
        composition.size == 1 and temperature_k >= float(eos.components[0].Tc)
    )

    def _provenance(
        *,
        hint: str,
        basis: str,
        confidence: str,
        bubble_pressure_hint_pa: float | None = None,
        dew_pressure_hint_pa: float | None = None,
        bubble_boundary_reason: str | None = None,
        dew_boundary_reason: str | None = None,
    ) -> _PhysicalStateHintProvenance:
        return _PhysicalStateHintProvenance(
            hint=hint,
            basis=basis,
            confidence=confidence,
            liquid_root_z=z_liquid,
            vapor_root_z=z_vapor,
            root_gap=root_gap,
            gibbs_gap=gibbs_gap,
            average_reduced_pressure=p_reduced,
            bubble_pressure_hint_pa=bubble_pressure_hint_pa,
            dew_pressure_hint_pa=dew_pressure_hint_pa,
            bubble_boundary_reason=bubble_boundary_reason,
            dew_boundary_reason=dew_boundary_reason,
        )

    if root_gap > 1.0e-4 and gibbs_gap >= 1.0e-2:
        return _provenance(
            hint=("single_phase_liquid_like" if g_liquid < g_vapor else "single_phase_vapor_like"),
            basis="direct_root_split",
            confidence="high",
        )

    bubble_pressure = None
    dew_pressure = None
    bubble_reason = None
    dew_reason = None

    if not pure_component_supercritical:
        try:
            bubble = calculate_bubble_point(
                temperature=temperature_k,
                composition=composition,
                components=eos.components,
                eos=eos,
                binary_interaction=binary_interaction,
            )
            bubble_pressure = float(bubble.pressure)
        except PhaseError as exc:
            bubble_reason = getattr(exc, "details", {}).get("reason")
        except Exception:
            bubble_reason = "error"

        try:
            dew = calculate_dew_point(
                temperature=temperature_k,
                composition=composition,
                components=eos.components,
                eos=eos,
                binary_interaction=binary_interaction,
            )
            dew_pressure = float(dew.pressure)
        except PhaseError as exc:
            dew_reason = getattr(exc, "details", {}).get("reason")
        except Exception:
            dew_reason = "error"

    pressure_rel_tol = 1.0e-3
    if bubble_pressure is not None and pressure_pa > bubble_pressure * (1.0 + pressure_rel_tol):
        return _provenance(
            hint="single_phase_liquid_like",
            basis="saturation_window",
            confidence="high",
            bubble_pressure_hint_pa=bubble_pressure,
            dew_pressure_hint_pa=dew_pressure,
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )
    if dew_pressure is not None and pressure_pa < dew_pressure * (1.0 - pressure_rel_tol):
        return _provenance(
            hint="single_phase_vapor_like",
            basis="saturation_window",
            confidence="high",
            bubble_pressure_hint_pa=bubble_pressure,
            dew_pressure_hint_pa=dew_pressure,
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )
    if bubble_pressure is not None and dew_pressure is not None:
        return _provenance(
            hint="single_phase_ambiguous",
            basis="saturation_window",
            confidence="medium",
            bubble_pressure_hint_pa=bubble_pressure,
            dew_pressure_hint_pa=dew_pressure,
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )

    z_single = float(max(roots, key=abs))

    if bubble_reason in {"degenerate_trivial_boundary", "no_saturation"} and dew_reason in {
        "degenerate_trivial_boundary",
        "no_saturation",
    }:
        if z_single >= 0.95 and p_reduced <= 0.75:
            return _provenance(
                hint="single_phase_vapor_like",
                basis=("supercritical_guard" if pure_component_supercritical else "no_boundary_guard"),
                confidence="medium",
                bubble_boundary_reason=bubble_reason,
                dew_boundary_reason=dew_reason,
            )
        return _provenance(
            hint="single_phase_ambiguous",
            basis=("supercritical_guard" if pure_component_supercritical else "no_boundary_guard"),
            confidence="low",
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )

    if z_single <= 0.30:
        return _provenance(
            hint="single_phase_liquid_like",
            basis="heuristic_fallback",
            confidence="medium",
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )
    if z_single >= 0.90:
        return _provenance(
            hint="single_phase_vapor_like",
            basis=("supercritical_guard" if pure_component_supercritical else "heuristic_fallback"),
            confidence=("medium" if pure_component_supercritical else "medium"),
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )
    if p_reduced >= 2.0 and z_single <= 0.80:
        return _provenance(
            hint="single_phase_liquid_like",
            basis="heuristic_fallback",
            confidence="low",
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )
    if p_reduced <= 0.50 and z_single >= 0.70:
        return _provenance(
            hint="single_phase_vapor_like",
            basis=("supercritical_guard" if pure_component_supercritical else "heuristic_fallback"),
            confidence=("medium" if pure_component_supercritical else "low"),
            bubble_boundary_reason=bubble_reason,
            dew_boundary_reason=dew_reason,
        )

    return _provenance(
        hint="single_phase_ambiguous",
        basis=("supercritical_guard" if pure_component_supercritical else "heuristic_fallback"),
        confidence="low",
        bubble_boundary_reason=bubble_reason,
        dew_boundary_reason=dew_reason,
    )


def _build_stability_seed_result(seed_result, component_ids: list[str]) -> StabilitySeedResultData:
    """Convert a pvtcore stability seed result to the app/runtime schema."""
    return StabilitySeedResultData(
        kind=str(seed_result.kind),
        trial_phase=str(seed_result.trial_phase),
        seed_index=int(seed_result.seed_index),
        seed_label=str(seed_result.seed_label),
        initial_composition={
            component_id: float(seed_result.initial_w[index])
            for index, component_id in enumerate(component_ids)
        },
        composition={
            component_id: float(seed_result.w[index])
            for index, component_id in enumerate(component_ids)
        },
        tpd=float(seed_result.tpd),
        iterations=int(seed_result.iterations),
        converged=bool(seed_result.converged),
        early_exit_unstable=bool(seed_result.early_exit_unstable),
        n_phi_calls=int(seed_result.n_phi_calls),
        n_eos_failures=int(seed_result.n_eos_failures),
        message=None if seed_result.message is None else str(seed_result.message),
    )


def _build_stability_trial_result(trial_result, component_ids: list[str]) -> StabilityTrialResultData:
    """Convert a pvtcore aggregated stability trial to the app/runtime schema."""
    return StabilityTrialResultData(
        kind=str(trial_result.kind),
        trial_phase=str(trial_result.trial_phase),
        composition={
            component_id: float(trial_result.w[index])
            for index, component_id in enumerate(component_ids)
        },
        tpd=float(trial_result.tpd),
        iterations=int(trial_result.iterations),
        total_iterations=int(trial_result.total_iterations),
        converged=bool(trial_result.converged),
        early_exit_unstable=bool(trial_result.early_exit_unstable),
        n_phi_calls=int(trial_result.n_phi_calls),
        n_eos_failures=int(trial_result.n_eos_failures),
        message=None if trial_result.message is None else str(trial_result.message),
        best_seed_index=int(trial_result.best_seed_index),
        candidate_seed_labels=[str(label) for label in trial_result.candidate_seed_labels],
        diagnostic_messages=[str(message) for message in trial_result.diagnostic_messages],
        seed_results=[
            _build_stability_seed_result(seed_result, component_ids)
            for seed_result in trial_result.seed_results
        ],
    )


def execute_pt_flash(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> PTFlashResult:
    """Execute a PT flash calculation.

    Args:
        config: Run configuration (must have pt_flash_config set)
        callback: Optional progress callback

    Returns:
        PTFlashResult with calculation results

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If pvtcore raises an error
    """
    from pvtcore.flash import pt_flash

    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    if callback:
        callback.on_progress(config.run_id or '', 0.3, "Running flash calculation...")

    # Execute flash
    flash_config = config.pt_flash_config
    result = pt_flash(
        pressure=flash_config.pressure_pa,
        temperature=flash_config.temperature_k,
        composition=z,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
        tolerance=config.solver_settings.tolerance,
        max_iterations=config.solver_settings.max_iterations,
    )

    if callback:
        callback.on_progress(config.run_id or '', 0.9, "Processing results...")

    # Convert to result schema
    diagnostics = _build_solver_diagnostics(result)
    certificate = _build_solver_certificate(result)

    # Build composition dicts
    liquid_comp = {cid: float(result.liquid_composition[i]) for i, cid in enumerate(component_ids)}
    vapor_comp = {cid: float(result.vapor_composition[i]) for i, cid in enumerate(component_ids)}
    k_values = {cid: float(result.K_values[i]) for i, cid in enumerate(component_ids)}
    liquid_fug = {cid: float(result.liquid_fugacity[i]) for i, cid in enumerate(component_ids)}
    vapor_fug = {cid: float(result.vapor_fugacity[i]) for i, cid in enumerate(component_ids)}
    phase_properties = _compute_pt_flash_phase_properties(
        pressure_pa=flash_config.pressure_pa,
        temperature_k=flash_config.temperature_k,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
        phase=result.phase,
        liquid_composition=result.liquid_composition,
        vapor_composition=result.vapor_composition,
    )
    reported_outcome = _resolve_reported_pt_flash_surface(
        config=config,
        prepared_fluid=prepared,
        flash_result=result,
    )
    reported = reported_outcome.surface

    return PTFlashResult(
        converged=result.converged,
        phase=result.phase,
        vapor_fraction=float(result.vapor_fraction),
        liquid_composition=liquid_comp,
        vapor_composition=vapor_comp,
        K_values=k_values,
        liquid_fugacity=liquid_fug,
        vapor_fugacity=vapor_fug,
        reported_surface_status=reported_outcome.status,
        reported_surface_reason=reported_outcome.reason,
        reported_component_basis=(
            None if reported is None else reported.component_basis
        ),
        reported_liquid_composition=(
            None if reported is None else reported.liquid_composition
        ),
        reported_vapor_composition=(
            None if reported is None else reported.vapor_composition
        ),
        reported_k_values=(
            None if reported is None else reported.k_values
        ),
        reported_liquid_fugacity=(
            None if reported is None else reported.liquid_fugacity
        ),
        reported_vapor_fugacity=(
            None if reported is None else reported.vapor_fugacity
        ),
        liquid_density_kg_per_m3=phase_properties["liquid_density_kg_per_m3"],
        vapor_density_kg_per_m3=phase_properties["vapor_density_kg_per_m3"],
        liquid_viscosity_pa_s=phase_properties["liquid_viscosity_pa_s"],
        vapor_viscosity_pa_s=phase_properties["vapor_viscosity_pa_s"],
        interfacial_tension_n_per_m=phase_properties["interfacial_tension_n_per_m"],
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_stability_analysis(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> StabilityAnalysisResult:
    """Execute standalone Michelsen / TPD stability analysis."""
    from pvtcore.stability import StabilityOptions, stability_analyze

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    stability_config = config.stability_analysis_config
    if stability_config is None:
        raise ValueError("stability_analysis_config is required for STABILITY_ANALYSIS calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running stability analysis...")

    options = StabilityOptions(
        tol_ln_w=float(config.solver_settings.tolerance),
        max_iter=int(config.solver_settings.max_iterations),
        use_gdem=bool(stability_config.use_gdem),
        n_random_trials=int(stability_config.n_random_trials),
        random_seed=(
            None if stability_config.random_seed is None else int(stability_config.random_seed)
        ),
        max_eos_failures_per_trial=int(stability_config.max_eos_failures_per_trial),
    )
    result = stability_analyze(
        z,
        float(stability_config.pressure_pa),
        float(stability_config.temperature_k),
        eos,
        feed_phase=stability_config.feed_phase.value,
        binary_interaction=binary_interaction,
        options=options,
    )
    hint_provenance = _infer_stability_physical_state_hint(
        stable=bool(result.stable),
        pressure_pa=float(stability_config.pressure_pa),
        temperature_k=float(stability_config.temperature_k),
        composition=z,
        eos=eos,
        binary_interaction=binary_interaction,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    return StabilityAnalysisResult(
        stable=bool(result.stable),
        tpd_min=float(result.tpd_min),
        pressure_pa=float(stability_config.pressure_pa),
        temperature_k=float(stability_config.temperature_k),
        requested_feed_phase=stability_config.feed_phase,
        resolved_feed_phase=str(result.feed_phase),
        reference_root_used=_resolve_stability_reference_root_used(str(result.feed_phase)),
        phase_regime=_classify_stability_phase_regime(bool(result.stable)),
        physical_state_hint=hint_provenance.hint,
        physical_state_hint_basis=hint_provenance.basis,
        physical_state_hint_confidence=hint_provenance.confidence,
        liquid_root_z=hint_provenance.liquid_root_z,
        vapor_root_z=hint_provenance.vapor_root_z,
        root_gap=hint_provenance.root_gap,
        gibbs_gap=hint_provenance.gibbs_gap,
        average_reduced_pressure=hint_provenance.average_reduced_pressure,
        bubble_pressure_hint_pa=hint_provenance.bubble_pressure_hint_pa,
        dew_pressure_hint_pa=hint_provenance.dew_pressure_hint_pa,
        bubble_boundary_reason=hint_provenance.bubble_boundary_reason,
        dew_boundary_reason=hint_provenance.dew_boundary_reason,
        feed_composition={
            component_id: float(z[index])
            for index, component_id in enumerate(component_ids)
        },
        best_unstable_trial_kind=(
            None if result.best_unstable_trial is None else str(result.best_unstable_trial.kind)
        ),
        vapor_like_trial=(
            None
            if result.vapor_like is None
            else _build_stability_trial_result(result.vapor_like, component_ids)
        ),
        liquid_like_trial=(
            None
            if result.liquid_like is None
            else _build_stability_trial_result(result.liquid_like, component_ids)
        ),
    )


def execute_phase_envelope(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> PhaseEnvelopeResult:
    """Execute a phase envelope calculation.

    **Fixed grid** (default): ``trace_phase_envelope`` walks a temperature mesh and
    solves bubble + dew at each node with pressure warm-started from the previous
    node — the usual interactive cost model (O(n) saturation solves).

    **Continuation**: ``trace_envelope_continuation`` adaptively follows certified
    branch roots with critical junction handling — intended for multi-root or
    pathological fluids; much heavier than fixed grid.

    For library-internal **Michelsen-style** Newton marching on fugacity equality
    without the continuation wrapper, see ``pvtcore.envelope.fast_envelope``.

    Args:
        config: Run configuration (must have phase_envelope_config set)
        callback: Optional progress callback

    Returns:
        PhaseEnvelopeResult with envelope points

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If pvtcore raises an error
    """
    config = _resolve_config_characterization(config)

    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    env_config = config.phase_envelope_config
    tracing_method = env_config.tracing_method
    cancel_check = (lambda: _raise_if_cancelled(callback)) if callback is not None else None

    if callback:
        if tracing_method is PhaseEnvelopeTracingMethod.FIXED_GRID:
            callback.on_progress(config.run_id or '', 0.3, "Tracing phase envelope...")
        else:
            callback.on_progress(config.run_id or '', 0.3, "Tracing phase envelope (continuation)...")

    if tracing_method is not PhaseEnvelopeTracingMethod.FIXED_GRID:
        # Route continuation/adaptive tracing through the fast Newton tracer
        # (``calculate_phase_envelope_fast``) directly, so cancellation from the
        # callback propagates out as ``CalculationCancelledError`` without being
        # swallowed by the envelope wrapper's broad fallback try/except. The
        # fast tracer marches along the saturation locus by Michelsen-style
        # Newton on fugacity equality with warm-started K-values and pairs with
        # the Heidemann-Khalil critical-point solver.
        from pvtcore.envelope.fast_envelope import calculate_phase_envelope_fast

        envelope = calculate_phase_envelope_fast(
            composition=np.asarray(z, dtype=float),
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            T_start=float(env_config.temperature_min_k),
            T_step_initial=max(
                (float(env_config.temperature_max_k) - float(env_config.temperature_min_k))
                / max(int(env_config.n_points), 1),
                1.0,
            ),
            max_points=max(int(env_config.n_points) * 4, 200),
            detect_critical=True,
            cancel_check=cancel_check,
        )
        if cancel_check is not None:
            cancel_check()

        if len(envelope.bubble_T) == 0 and len(envelope.dew_T) == 0:
            raise RuntimeError(
                "Phase envelope failed: no saturation points found in the requested temperature range. "
                "Suggestions: widen the temperature range; lower temperature_min_k; verify inputs are in K/Pa; "
                "confirm composition sums to 1.0 and components are valid."
            )

        bubble_points = [
            PhaseEnvelopePoint(
                temperature_k=float(T),
                pressure_pa=float(P),
                point_type='bubble',
            )
            for T, P in zip(envelope.bubble_T, envelope.bubble_P)
        ]
        dew_points = [
            PhaseEnvelopePoint(
                temperature_k=float(T),
                pressure_pa=float(P),
                point_type='dew',
            )
            for T, P in zip(envelope.dew_T, envelope.dew_P)
        ]

        if len(bubble_points) == 0 or len(dew_points) == 0:
            raise RuntimeError(
                "Phase envelope failed: could not trace both bubble and dew branches in the requested range. "
                "Suggestions: widen the temperature range; adjust the mixture to include both light/heavy components; "
                "verify EOS and binary interaction parameters."
            )

        critical = None
        critical_source = None
        if envelope.critical_T is not None and envelope.critical_P is not None:
            critical = PhaseEnvelopePoint(
                temperature_k=float(envelope.critical_T),
                pressure_pa=float(envelope.critical_P),
                point_type='critical',
            )
            critical_source = "heidemann_khalil"

        all_points = bubble_points + dew_points + ([critical] if critical is not None else [])
        cricondenbar = None
        cricondentherm = None
        if all_points:
            max_pressure_point = max(all_points, key=lambda point: point.pressure_pa)
            cricondenbar = PhaseEnvelopePoint(
                temperature_k=float(max_pressure_point.temperature_k),
                pressure_pa=float(max_pressure_point.pressure_pa),
                point_type='cricondenbar',
            )
            max_temperature_point = max(all_points, key=lambda point: point.temperature_k)
            cricondentherm = PhaseEnvelopePoint(
                temperature_k=float(max_temperature_point.temperature_k),
                pressure_pa=float(max_temperature_point.pressure_pa),
                point_type='cricondentherm',
            )

        return PhaseEnvelopeResult(
            bubble_curve=bubble_points,
            dew_curve=dew_points,
            critical_point=critical,
            cricondenbar=cricondenbar,
            cricondentherm=cricondentherm,
            tracing_method=tracing_method,
            continuation_switched=None,
            critical_source=critical_source,
            bubble_termination_reason=None,
            bubble_termination_temperature_k=None,
            dew_termination_reason=None,
            dew_termination_temperature_k=None,
        )

    from pvtcore.envelope import trace_phase_envelope

    envelope = trace_phase_envelope(
        composition=z,
        components=components,
        eos=eos,
        T_min=env_config.temperature_min_k,
        T_max=env_config.temperature_max_k,
        n_points=env_config.n_points,
        binary_interaction=binary_interaction,
        cancel_check=cancel_check,
    )

    if callback:
        callback.on_progress(config.run_id or '', 0.9, "Processing results...")

    # Convert to result schema
    bubble_points = [
        PhaseEnvelopePoint(
            temperature_k=float(T),
            pressure_pa=float(P),
            point_type='bubble'
        )
        for T, P in zip(envelope.bubble_T, envelope.bubble_P)
    ]

    dew_points = [
        PhaseEnvelopePoint(
            temperature_k=float(T),
            pressure_pa=float(P),
            point_type='dew'
        )
        for T, P in zip(envelope.dew_T, envelope.dew_P)
    ]

    critical = None
    if envelope.critical_point is not None:
        critical = PhaseEnvelopePoint(
            temperature_k=float(envelope.critical_point[0]),
            pressure_pa=float(envelope.critical_point[1]),
            point_type='critical'
        )

    cricondenbar = None
    if envelope.cricondenbar is not None:
        cricondenbar = PhaseEnvelopePoint(
            temperature_k=float(envelope.cricondenbar[0]),
            pressure_pa=float(envelope.cricondenbar[1]),
            point_type='cricondenbar'
        )

    cricondentherm = None
    if envelope.cricondentherm is not None:
        cricondentherm = PhaseEnvelopePoint(
            temperature_k=float(envelope.cricondentherm[0]),
            pressure_pa=float(envelope.cricondentherm[1]),
            point_type='cricondentherm'
        )

    return PhaseEnvelopeResult(
        bubble_curve=bubble_points,
        dew_curve=dew_points,
        critical_point=critical,
        cricondenbar=cricondenbar,
        cricondentherm=cricondentherm,
        tracing_method=tracing_method,
    )


def _finite_or_none(value: float) -> Optional[float]:
    """Return float(value) when finite, otherwise None."""
    if value is None:
        return None
    try:
        as_float = float(value)
    except (TypeError, ValueError):
        return None
    return as_float if np.isfinite(as_float) else None


def _composition_array_to_dict(
    component_ids: list[str], composition: np.ndarray | None
) -> Optional[dict[str, float]]:
    """Zip a per-component composition array into a {component_id: mole_fraction} dict.

    Returns None when the array is missing, empty, wrong-length, or sums to zero
    (e.g. the 'absent phase' placeholder used by single-phase steps).
    """
    if composition is None:
        return None
    arr = np.asarray(composition, dtype=float)
    if arr.size == 0 or arr.size != len(component_ids):
        return None
    if not np.isfinite(arr).all() or float(arr.sum()) <= 0.0:
        return None
    return {cid: float(val) for cid, val in zip(component_ids, arr)}


def _compute_pt_flash_phase_properties(
    pressure_pa: float,
    temperature_k: float,
    components,
    eos,
    binary_interaction,
    phase: str,
    liquid_composition: np.ndarray,
    vapor_composition: np.ndarray,
) -> Dict[str, Optional[float]]:
    """Compute phase densities, viscosities, and IFT for a PT-flash result."""
    from pvtcore.properties.ift_parachor import interfacial_tension_parachor_after_flash

    def _phase_properties(phase_name: str, composition: np.ndarray) -> tuple[Optional[float], Optional[float]]:
        return _compute_phase_density_and_viscosity(
            pressure_pa,
            temperature_k,
            components,
            eos,
            binary_interaction,
            phase_name,
            composition,
        )

    liquid_density = None
    liquid_viscosity = None
    vapor_density = None
    vapor_viscosity = None
    interfacial_tension = None

    if phase in {"liquid", "two-phase"}:
        liquid_density, liquid_viscosity = _phase_properties("liquid", liquid_composition)
    if phase in {"vapor", "two-phase"}:
        vapor_density, vapor_viscosity = _phase_properties("vapor", vapor_composition)
    if phase == "two-phase":
        try:
            ift_result = interfacial_tension_parachor_after_flash(
                SimpleNamespace(
                    phase=phase,
                    pressure=pressure_pa,
                    temperature=temperature_k,
                    liquid_composition=liquid_composition,
                    vapor_composition=vapor_composition,
                ),
                eos,
                components,
                binary_interaction=binary_interaction,
            )
        except Exception:
            interfacial_tension = None
        else:
            interfacial_tension = _finite_or_none(ift_result.sigma_N_per_m)

    return {
        "liquid_density_kg_per_m3": liquid_density,
        "vapor_density_kg_per_m3": vapor_density,
        "liquid_viscosity_pa_s": liquid_viscosity,
        "vapor_viscosity_pa_s": vapor_viscosity,
        "interfacial_tension_n_per_m": interfacial_tension,
    }


def _compute_phase_density_and_viscosity(
    pressure_pa: float,
    temperature_k: float,
    components,
    eos,
    binary_interaction,
    phase_name: str,
    composition: np.ndarray,
) -> tuple[Optional[float], Optional[float]]:
    """Compute density and LBC viscosity for a single phase composition."""
    from pvtcore.properties.density import calculate_density
    from pvtcore.properties.viscosity_lbc import calculate_viscosity_lbc

    if composition.size == 0 or float(np.sum(composition)) <= 0.0:
        return None, None

    try:
        density_result = calculate_density(
            pressure_pa,
            temperature_k,
            composition,
            components,
            eos,
            phase=phase_name,
            binary_interaction=binary_interaction,
        )
    except Exception:
        return None, None

    density = _finite_or_none(density_result.mass_density)

    try:
        viscosity_result = calculate_viscosity_lbc(
            density_result.molar_density,
            temperature_k,
            composition,
            components,
            MW_mix=density_result.MW_mix,
        )
    except Exception:
        return density, None

    return density, _finite_or_none(viscosity_result.viscosity)


def _compute_phase_viscosity(
    pressure_pa: float,
    temperature_k: float,
    components,
    eos,
    binary_interaction,
    phase_name: str,
    composition: np.ndarray,
) -> Optional[float]:
    """Compute only the phase viscosity for reuse across step-based experiments."""
    _, viscosity = _compute_phase_density_and_viscosity(
        pressure_pa,
        temperature_k,
        components,
        eos,
        binary_interaction,
        phase_name,
        composition,
    )
    return viscosity


_INLINE_COMPONENT_ZC = 0.27
_ATMOSPHERIC_PRESSURE_PA = 101325.0


def _inverse_edmister_tb(
    critical_temperature_k: float,
    critical_pressure_pa: float,
    omega: float,
) -> float:
    """Recover Tb from Tc, Pc, and omega for an inline pseudo-component."""
    a = (3.0 / 7.0) * np.log10(float(critical_pressure_pa) / _ATMOSPHERIC_PRESSURE_PA)
    denominator = 1.0 + a / (float(omega) + 1.0)
    if denominator <= 1.0:
        raise ValueError("Cannot derive Tb from the supplied Tc/Pc/omega triple.")
    tb = float(critical_temperature_k) / denominator
    if tb <= 0.0 or tb >= float(critical_temperature_k):
        raise ValueError("Derived Tb is not physically valid for the supplied Tc/Pc/omega triple.")
    return tb


def _estimate_vc_from_tc_pc(
    critical_temperature_k: float,
    critical_pressure_pa: float,
    *,
    zc: float = _INLINE_COMPONENT_ZC,
) -> float:
    """Estimate Vc from Tc and Pc using a nominal critical compressibility."""
    from pvtcore.core.constants import R

    return float(zc) * R.Pa_m3_per_mol_K * float(critical_temperature_k) / float(critical_pressure_pa)


def _build_inline_component(spec):
    """Construct a runtime Component from an explicit inline pseudo-component spec."""
    from pvtcore.models import Component

    tb_k = _inverse_edmister_tb(
        critical_temperature_k=spec.critical_temperature_k,
        critical_pressure_pa=spec.critical_pressure_pa,
        omega=spec.omega,
    )
    vc_m3_per_mol = _estimate_vc_from_tc_pc(
        critical_temperature_k=spec.critical_temperature_k,
        critical_pressure_pa=spec.critical_pressure_pa,
    )

    return Component(
        name=spec.name,
        formula=spec.formula or spec.name,
        Tc=spec.critical_temperature_k,
        Pc=spec.critical_pressure_pa,
        Vc=vc_m3_per_mol,
        omega=spec.omega,
        MW=spec.molecular_weight_g_per_mol,
        Tb=tb_k,
        note=(
            "Inline pseudo-component. Tb back-calculated from Tc/Pc/omega using inverse "
            "Edmister; Vc estimated with Zc=0.27."
        ),
        id=spec.component_id,
        aliases=[spec.name, spec.component_id],
        is_pseudo=True,
    )


def _resolve_config_characterization(config: RunConfig) -> RunConfig:
    """Resolve plus-fraction characterization policy into concrete runtime settings."""
    if config.composition is None:
        return config
    plus_fraction = config.composition.plus_fraction
    if plus_fraction is None:
        return config

    resolved_plus = resolve_plus_fraction_entry(
        config.composition.components,
        plus_fraction,
        config.calculation_type,
    )
    if resolved_plus == plus_fraction:
        return config

    resolved_composition = config.composition.model_copy(update={"plus_fraction": resolved_plus})
    return config.model_copy(update={"composition": resolved_composition})


def _coerce_runtime_tbp_cut_row(cut) -> dict[str, float | int | str | None]:
    """Normalize a TBP cut object/model into a single mapping shape."""
    mole_fraction = getattr(cut, "mole_fraction", None)
    if mole_fraction is None:
        mole_fraction = getattr(cut, "z")
    molecular_weight = getattr(cut, "molecular_weight_g_per_mol", None)
    if molecular_weight is None:
        molecular_weight = getattr(cut, "mw")
    return {
        "name": str(cut.name),
        "carbon_number": int(cut.carbon_number),
        "carbon_number_end": int(cut.carbon_number_end),
        "mole_fraction": float(mole_fraction),
        "molecular_weight_g_per_mol": float(molecular_weight),
        "boiling_point_k": getattr(cut, "boiling_point_k", getattr(cut, "tb_k", None)),
    }


def _pedersen_tbp_constraints_from_rows(
    rows: list[dict[str, float | int | str | None]],
    *,
    z_plus: float,
):
    """Build normalized Pedersen TBP constraints from observed assay cuts."""
    from pvtcore.characterization import PedersenTBPCutConstraint

    return tuple(
        PedersenTBPCutConstraint(
            name=str(row["name"]),
            carbon_number=int(row["carbon_number"]),
            carbon_number_end=int(row["carbon_number_end"]),
            z=float(row["mole_fraction"]) / float(z_plus),
            mw=float(row["molecular_weight_g_per_mol"]),
            tb_k=(
                None
                if row["boiling_point_k"] is None
                else float(row["boiling_point_k"])
            ),
        )
        for row in rows
    )


def _resolve_runtime_plus_fraction_characterization_inputs(config: RunConfig):
    """Resolve the canonical plus-fraction characterization request from a run config."""
    from pvtcore.characterization import (
        BinaryInteractionOverride,
        CharacterizationConfig,
        PlusFractionSpec,
    )
    from pvtcore.experiments.tbp import simulate_tbp
    from pvtcore.models import load_components, resolve_component_id

    config = _resolve_config_characterization(config)
    if config.composition is None or config.composition.plus_fraction is None:
        return None

    all_components = load_components()
    inline_components = {
        spec.component_id: spec
        for spec in config.composition.inline_components
    }
    if inline_components:
        raise ValueError("plus_fraction and inline_components cannot be used together in the current runtime path")

    raw_component_ids = [entry.component_id for entry in config.composition.components]
    mole_fractions = [entry.mole_fraction for entry in config.composition.components]

    component_ids: list[str] = []
    missing: list[str] = []
    for cid in raw_component_ids:
        try:
            component_ids.append(resolve_component_id(cid, all_components))
        except KeyError:
            missing.append(cid)

    if missing:
        raise ValueError(
            f"Unknown component(s): {missing}. "
            f"Available: {sorted(all_components.keys())}"
        )

    duplicate_sources: Dict[str, List[str]] = {}
    for raw_id, canonical_id in zip(raw_component_ids, component_ids):
        duplicate_sources.setdefault(canonical_id, []).append(raw_id)
    duplicates = {
        canonical_id: raw_ids
        for canonical_id, raw_ids in duplicate_sources.items()
        if len(raw_ids) > 1
    }
    if duplicates:
        raise ValueError(f"Duplicate component IDs after alias resolution: {duplicates}")

    resolved_feed = [
        (canonical_id, z)
        for canonical_id, z in zip(component_ids, mole_fractions)
    ]

    override_entries = None
    if config.binary_interaction:
        for pair_key in config.binary_interaction:
            if pair_key.count("-") != 1:
                raise ValueError(f"Invalid BIP pair key: {pair_key}. Expected 'comp1-comp2'")
        override_entries = tuple(
            BinaryInteractionOverride(
                component_i=pair_key.split("-")[0],
                component_j=pair_key.split("-")[1],
                kij=float(kij),
            )
            for pair_key, kij in config.binary_interaction.items()
        )

    plus_fraction = config.composition.plus_fraction
    observed_tbp_rows: list[dict[str, float | int | str | None]] | None = None
    pedersen_tbp_cuts = None
    if plus_fraction.tbp_cuts:
        tbp_payload = [cut.model_dump(mode="python", exclude_none=True) for cut in plus_fraction.tbp_cuts]
        tbp_summary = simulate_tbp(tbp_payload, cut_start=plus_fraction.cut_start)
        if abs(float(tbp_summary.z_plus) - float(plus_fraction.z_plus)) > PLUS_FRACTION_TBP_Z_ABS_TOLERANCE:
            raise ValueError(
                "plus_fraction.z_plus does not match the value derived from plus_fraction.tbp_cuts"
            )
        if (
            abs(float(tbp_summary.mw_plus_g_per_mol) - float(plus_fraction.mw_plus_g_per_mol))
            > PLUS_FRACTION_TBP_MW_ABS_TOLERANCE
        ):
            raise ValueError(
                "plus_fraction.mw_plus_g_per_mol does not match the value derived from plus_fraction.tbp_cuts"
            )
        observed_tbp_rows = [_coerce_runtime_tbp_cut_row(cut) for cut in tbp_summary.cuts]
        pedersen_tbp_cuts = _pedersen_tbp_constraints_from_rows(
            observed_tbp_rows,
            z_plus=float(plus_fraction.z_plus),
        )

    plus_spec = PlusFractionSpec(
        z_plus=plus_fraction.z_plus,
        mw_plus=plus_fraction.mw_plus_g_per_mol,
        sg_plus=plus_fraction.sg_plus_60f,
        label=plus_fraction.label,
        n_start=plus_fraction.cut_start,
    )
    characterization_config = CharacterizationConfig(
        n_end=plus_fraction.max_carbon_number,
        split_method=plus_fraction.split_method,
        split_mw_model=plus_fraction.split_mw_model,
        pedersen_solve_ab_from=plus_fraction.pedersen_solve_ab_from,
        pedersen_tbp_cuts=pedersen_tbp_cuts,
        kij_default=0.0,
        kij_overrides=override_entries,
        lumping_enabled=plus_fraction.lumping_enabled,
        lumping_n_groups=plus_fraction.lumping_n_groups,
        lumping_method=plus_fraction.lumping_method,
    )
    return resolved_feed, plus_spec, characterization_config, observed_tbp_rows


def _build_runtime_cut_mappings(
    *,
    split,
    z_plus: float,
    observed_tbp_rows: list[dict[str, float | int | str | None]] | None,
) -> list[TBPCharacterizationCutMapping]:
    """Compare observed TBP cuts against the derived SCN allocation."""
    if not observed_tbp_rows:
        return []

    cut_mappings: list[TBPCharacterizationCutMapping] = []
    for row in observed_tbp_rows:
        carbon_number = int(row["carbon_number"])
        carbon_number_end = int(row["carbon_number_end"])
        mask = (split.n >= carbon_number) & (split.n <= carbon_number_end)
        characterized_feed = float(split.z[mask].sum())
        characterized_normalized = characterized_feed / float(z_plus)
        characterized_avg_mw = None
        if characterized_feed > 0.0:
            characterized_avg_mw = float((split.z[mask] * split.MW[mask]).sum() / characterized_feed)

        observed_feed = float(row["mole_fraction"])
        observed_normalized = observed_feed / float(z_plus)
        cut_mappings.append(
            TBPCharacterizationCutMapping(
                cut_name=str(row["name"]),
                carbon_number=carbon_number,
                carbon_number_end=carbon_number_end,
                observed_mole_fraction=observed_feed,
                observed_normalized_mole_fraction=observed_normalized,
                characterized_mole_fraction=characterized_feed,
                characterized_normalized_mole_fraction=characterized_normalized,
                characterized_average_molecular_weight_g_per_mol=characterized_avg_mw,
                normalized_relative_error=(
                    None
                    if observed_normalized <= 0.0
                    else (characterized_normalized - observed_normalized) / observed_normalized
                ),
                scn_members=[int(value) for value in split.n[mask]],
            )
        )
    return cut_mappings


def _build_runtime_reconstruction_component_entries(
    *,
    detailed_component_ids: list[str],
    detailed_components: list[object],
    detailed_composition: np.ndarray,
    scn_distribution: list[RuntimeCharacterizationSCNEntry],
) -> list[RuntimeReconstructionComponentEntry]:
    """Serialize the detailed component basis preserved for reconstruction."""
    scn_by_id = {entry.component_id: entry for entry in scn_distribution}
    entries: list[RuntimeReconstructionComponentEntry] = []

    for component_id, component, z_value in zip(detailed_component_ids, detailed_components, detailed_composition):
        scn_entry = scn_by_id.get(component_id)
        if scn_entry is not None:
            entries.append(
                RuntimeReconstructionComponentEntry(
                    component_id=component_id,
                    source="characterized_scn",
                    feed_mole_fraction=float(z_value),
                    molecular_weight_g_per_mol=scn_entry.molecular_weight_g_per_mol,
                    critical_temperature_k=scn_entry.critical_temperature_k,
                    critical_pressure_pa=scn_entry.critical_pressure_pa,
                    critical_volume_m3_per_mol=scn_entry.critical_volume_m3_per_mol,
                    omega=scn_entry.omega,
                    boiling_point_k=scn_entry.boiling_point_k,
                    specific_gravity_60f=scn_entry.specific_gravity_60f,
                )
            )
            continue

        boiling_point = getattr(component, "Tb", None)
        entries.append(
            RuntimeReconstructionComponentEntry(
                component_id=component_id,
                source="resolved_feed_component",
                feed_mole_fraction=float(z_value),
                molecular_weight_g_per_mol=float(component.MW),
                critical_temperature_k=float(component.Tc),
                critical_pressure_pa=float(component.Pc),
                critical_volume_m3_per_mol=float(component.Vc),
                omega=float(component.omega),
                boiling_point_k=(
                    None
                    if boiling_point is None or float(boiling_point) <= 0.0
                    else float(boiling_point)
                ),
                specific_gravity_60f=None,
            )
        )

    return entries


def _build_runtime_detailed_reconstruction_context(
    *,
    characterized,
    characterization_config,
    scn_distribution: list[RuntimeCharacterizationSCNEntry],
) -> tuple[RuntimeDetailedReconstructionContext | None, str | None]:
    """Preserve the detailed basis required for a second EOS pass."""
    plus_fraction = characterized.plus_fraction
    split = characterized.split_result
    scn_props = characterized.scn_properties
    if plus_fraction is None or split is None or scn_props is None:
        return None, "Detailed reconstruction requires a preserved plus-fraction SCN basis."

    if not scn_distribution:
        return None, "Detailed reconstruction requires SCN distribution metadata from the originating characterization run."

    if characterized.lumping is None:
        detailed_component_ids = list(characterized.component_ids)
        detailed_components = list(characterized.components)
        detailed_composition = np.asarray(characterized.composition, dtype=np.float64)
        detailed_binary_interaction = np.asarray(characterized.binary_interaction, dtype=np.float64)
        component_basis: str = "scn_only" if len(detailed_component_ids) == len(scn_distribution) else "light_ends_plus_scn"
        reconstruction_note = (
            "Detailed reconstruction uses the same unrumped runtime component basis and stored BIP matrix because the heavy end was not lumped."
        )
    else:
        from pvtcore.characterization.pipeline import _build_kij_matrix

        lumping = characterized.lumping
        light_count = len(characterized.component_ids) - len(lumping.lump_component_ids)
        if light_count < 0:
            return None, "Runtime lump metadata is inconsistent with the preserved characterization basis."

        detailed_component_ids = list(characterized.component_ids[:light_count]) + list(lumping.scn_component_ids)
        detailed_components = list(characterized.components[:light_count]) + list(lumping.scn_components)
        detailed_composition = np.concatenate(
            [
                np.asarray(characterized.composition[:light_count], dtype=np.float64),
                np.asarray(lumping.scn_z, dtype=np.float64),
            ]
        )
        detailed_binary_interaction = np.asarray(
            _build_kij_matrix(
                component_ids=detailed_component_ids,
                overrides=characterization_config.kij_overrides,
                default_kij=float(characterization_config.kij_default),
                plus_fraction=plus_fraction,
                pseudo_component_ids=list(lumping.scn_component_ids),
            ),
            dtype=np.float64,
        )
        component_basis = "scn_only" if light_count == 0 else "light_ends_plus_scn"
        reconstruction_note = (
            "Detailed reconstruction rebuilds the BIP matrix on the full SCN basis from the same static characterization kij policy used during runtime preparation."
        )

    if detailed_binary_interaction.shape != (len(detailed_component_ids), len(detailed_component_ids)):
        return None, "Detailed reconstruction BIP matrix shape does not align with the preserved detailed component order."

    override_pairs = []
    if characterization_config.kij_overrides is not None:
        override_pairs = [
            f"{override.component_i}-{override.component_j}"
            for override in characterization_config.kij_overrides
        ]

    component_entries = _build_runtime_reconstruction_component_entries(
        detailed_component_ids=detailed_component_ids,
        detailed_components=detailed_components,
        detailed_composition=detailed_composition,
        scn_distribution=scn_distribution,
    )

    return (
        RuntimeDetailedReconstructionContext(
            component_basis=component_basis,
            components=component_entries,
            binary_interaction_matrix=detailed_binary_interaction.tolist(),
            bip_provenance=RuntimeReconstructionBIPProvenance(
                default_kij=float(characterization_config.kij_default),
                override_pairs=override_pairs,
                notes=[
                    "The preserved detailed matrix is static within the current runtime path; no temperature-dependent BIP rebuild policy is applied here.",
                ],
            ),
            notes=[reconstruction_note],
        ),
        None,
    )


def _build_runtime_characterization_result(
    *,
    source: str,
    characterized,
    characterization_config,
    split_method: str,
    split_mw_model: str | None,
    lumping_method: str | None,
    cut_end: int,
    sg_plus_60f: float | None,
    observed_tbp_rows: list[dict[str, float | int | str | None]] | None = None,
    notes: list[str] | None = None,
) -> RuntimeCharacterizationResult:
    """Serialize the heavy-end runtime characterization that the canonical path used."""
    from pvtcore.characterization.pseudo_correlations import RiaziDaubertCorrelation

    plus_fraction = characterized.plus_fraction
    split = characterized.split_result
    scn_props = characterized.scn_properties
    if plus_fraction is None or split is None or scn_props is None:
        raise RuntimeError("Runtime characterization requested without a resolved plus-fraction split")

    z_plus = float(plus_fraction.z_plus)
    mw_plus = float(plus_fraction.mw_plus)
    total_plus_mass_basis = z_plus * mw_plus
    scn_raw_mass = np.asarray(split.z * split.MW, dtype=np.float64)
    if total_plus_mass_basis > 0.0:
        scn_mass_fraction = scn_raw_mass / total_plus_mass_basis
    else:
        scn_mass_fraction = np.zeros_like(scn_raw_mass)

    pseudo_props = RiaziDaubertCorrelation(prefer_tb_form=True).estimate(scn_props)
    scn_component_ids = [f"SCN{int(value)}" for value in split.n]
    scn_distribution = [
        RuntimeCharacterizationSCNEntry(
            component_id=scn_component_ids[index],
            carbon_number=int(split.n[index]),
            feed_mole_fraction=float(split.z[index]),
            normalized_plus_mole_fraction=float(split.z[index]) / z_plus,
            normalized_plus_mass_fraction=float(scn_mass_fraction[index]),
            molecular_weight_g_per_mol=float(split.MW[index]),
            specific_gravity_60f=float(scn_props.sg_6060[index]),
            boiling_point_k=float(scn_props.tb_k[index]),
            critical_temperature_k=float(pseudo_props.Tc[index]),
            critical_pressure_pa=float(pseudo_props.Pc[index]),
            critical_volume_m3_per_mol=float(pseudo_props.Vc[index]),
            omega=float(pseudo_props.omega[index]),
        )
        for index in range(len(split.n))
    ]

    pedersen_fit = None
    if split_method == "pedersen":
        pedersen_fit = TBPCharacterizationPedersenFit(
            solve_ab_from=split.solve_ab_from,
            A=float(split.A),
            B=float(split.B),
            tbp_cut_rms_relative_error=(
                None
                if split.tbp_cut_rms_relative_error is None
                else float(split.tbp_cut_rms_relative_error)
            ),
        )

    lump_distribution: list[RuntimeCharacterizationLumpEntry] = []
    delumping_basis = None
    runtime_component_basis = "scn_unlumped"
    if characterized.lumping is not None:
        runtime_component_basis = "lumped"
        delumping_basis = "feed_scn_distribution"
        for group_index, members in enumerate(characterized.lumping.lump_members):
            member_entries = [
                RuntimeCharacterizationLumpMember(
                    component_id=characterized.lumping.scn_component_ids[scn_index],
                    carbon_number=int(characterized.lumping.scn_props.n[scn_index]),
                    feed_mole_fraction=float(characterized.lumping.scn_z[scn_index]),
                    normalized_plus_mole_fraction=float(characterized.lumping.scn_z[scn_index]) / z_plus,
                    delumping_weight=float(characterized.lumping.lump_weights[group_index][member_offset]),
                )
                for member_offset, scn_index in enumerate(members)
            ]
            lump_distribution.append(
                RuntimeCharacterizationLumpEntry(
                    component_id=characterized.lumping.lump_component_ids[group_index],
                    carbon_number_start=int(characterized.lumping.scn_props.n[members][0]),
                    carbon_number_end=int(characterized.lumping.scn_props.n[members][-1]),
                    feed_mole_fraction=float(characterized.lumping.lump_z[group_index]),
                    normalized_plus_mole_fraction=float(characterized.lumping.lump_z[group_index]) / z_plus,
                    molecular_weight_g_per_mol=float(characterized.lumping.lump_components[group_index].MW),
                    member_count=len(member_entries),
                    members=member_entries,
                )
            )

    runtime_notes = list(notes or [])
    if source == "tbp_assay":
        runtime_notes.append(
            "Standalone TBP now preserves the same SCN characterization package used by the canonical runtime path."
        )
    else:
        runtime_notes.append(
            "This run preserves the heavy-end characterization package used to prepare the runtime EOS inputs."
        )
    if delumping_basis is not None:
        runtime_notes.append(
            "Lumped runs preserve SCN member weights so the original heavy-end feed basis can be delumped later."
        )

    detailed_reconstruction, detailed_reconstruction_unavailable_reason = _build_runtime_detailed_reconstruction_context(
        characterized=characterized,
        characterization_config=characterization_config,
        scn_distribution=scn_distribution,
    )
    if detailed_reconstruction is not None:
        runtime_notes.append(
            "The runtime package also preserves a detailed SCN reconstruction basis and stored BIP matrix for second-pass thermodynamic reconstruction."
        )
    elif detailed_reconstruction_unavailable_reason is not None:
        runtime_notes.append(
            f"Detailed reconstruction payload unavailable: {detailed_reconstruction_unavailable_reason}"
        )

    return RuntimeCharacterizationResult(
        source=source,
        plus_fraction_label=plus_fraction.label,
        cut_start=int(plus_fraction.n_start),
        cut_end=int(cut_end),
        z_plus=z_plus,
        mw_plus_g_per_mol=mw_plus,
        sg_plus_60f=None if sg_plus_60f is None else float(sg_plus_60f),
        split_method=split_method,
        split_mw_model=split_mw_model,
        pseudo_property_correlation="riazi_daubert",
        lumping_method=(
            None
            if characterized.lumping is None or lumping_method is None
            else lumping_method.strip().lower()
        ),
        runtime_component_basis=runtime_component_basis,
        runtime_component_ids=list(characterized.component_ids),
        pedersen_fit=pedersen_fit,
        cut_mappings=_build_runtime_cut_mappings(
            split=split,
            z_plus=z_plus,
            observed_tbp_rows=observed_tbp_rows,
        ),
        scn_distribution=scn_distribution,
        lump_distribution=lump_distribution,
        delumping_basis=delumping_basis,
        detailed_reconstruction=detailed_reconstruction,
        detailed_reconstruction_unavailable_reason=detailed_reconstruction_unavailable_reason,
        notes=runtime_notes,
    )


def _build_runtime_characterization_from_tbp(kernel_result) -> RuntimeCharacterizationResult:
    """Build the canonical runtime characterization package for a standalone TBP assay."""
    from pvtcore.characterization import (
        CharacterizationConfig,
        PlusFractionSpec,
        characterize_fluid,
    )

    observed_tbp_rows = [_coerce_runtime_tbp_cut_row(cut) for cut in kernel_result.cuts]
    characterization_config = CharacterizationConfig(
        n_end=int(kernel_result.cut_end),
        split_method="pedersen",
        split_mw_model="table",
        correlation="riazi_daubert",
        pedersen_solve_ab_from="fit_to_tbp",
        pedersen_tbp_cuts=_pedersen_tbp_constraints_from_rows(
            observed_tbp_rows,
            z_plus=float(kernel_result.z_plus),
        ),
        lumping_enabled=False,
    )
    characterized = characterize_fluid(
        [],
        plus_fraction=PlusFractionSpec(
            z_plus=float(kernel_result.z_plus),
            mw_plus=float(kernel_result.mw_plus_g_per_mol),
            label=f"C{kernel_result.cut_start}+",
            n_start=int(kernel_result.cut_start),
        ),
        config=characterization_config,
    )
    return _build_runtime_characterization_result(
        source="tbp_assay",
        characterized=characterized,
        characterization_config=characterization_config,
        split_method="pedersen",
        split_mw_model="table",
        lumping_method=None,
        cut_end=int(kernel_result.cut_end),
        sg_plus_60f=None,
        observed_tbp_rows=observed_tbp_rows,
        notes=[
            (
                "This standalone assay still stops short of TBP-specific EOS/BIP selection, "
                "but it no longer discards the derived runtime characterization state."
            )
        ],
    )


def _build_runtime_characterization_from_prepared_plus_fraction(
    *,
    characterized,
    characterization_config,
    plus_spec,
    observed_tbp_rows: list[dict[str, float | int | str | None]] | None,
) -> RuntimeCharacterizationResult:
    """Promote the characterized heavy-end result into the runtime package used by the app."""
    return _build_runtime_characterization_result(
        source="plus_fraction_runtime",
        characterized=characterized,
        characterization_config=characterization_config,
        split_method=characterization_config.split_method,
        split_mw_model=characterization_config.split_mw_model,
        lumping_method=(
            characterization_config.lumping_method
            if characterization_config.lumping_enabled
            else None
        ),
        cut_end=int(characterization_config.n_end),
        sg_plus_60f=plus_spec.sg_plus,
        observed_tbp_rows=observed_tbp_rows,
        notes=[
            (
                "The preserved package mirrors the exact plus-fraction split and runtime basis "
                "used to prepare the EOS inputs for this run."
            )
        ],
    )


def _build_runtime_characterization_from_config(
    config: RunConfig,
) -> RuntimeCharacterizationResult | None:
    """Build the preserved heavy-end characterization package for a runtime config."""
    prepared = _prepare_fluid_inputs(config)
    return prepared.runtime_characterization


def _resolve_explicit_component_feed(
    feed,
    *,
    label: str,
    all_components: dict[str, object],
) -> tuple[list[str], np.ndarray]:
    """Resolve one explicit-feed composition onto canonical component IDs."""
    from pvtcore.models import resolve_component_id

    if feed.plus_fraction is not None:
        raise ValueError(
            f"{label} must not define plus_fraction in the current first-draft swelling runtime surface"
        )
    if feed.inline_components:
        raise ValueError(
            f"{label} must not define inline_components in the current first-draft swelling runtime surface"
        )

    raw_component_ids = [entry.component_id for entry in feed.components]
    mole_fractions = np.asarray(
        [float(entry.mole_fraction) for entry in feed.components],
        dtype=np.float64,
    )

    component_ids: list[str] = []
    missing: list[str] = []
    for cid in raw_component_ids:
        try:
            component_ids.append(resolve_component_id(cid, all_components))
        except KeyError:
            missing.append(cid)

    if missing:
        raise ValueError(
            f"Unknown component(s) in {label}: {missing}. Available: {sorted(all_components.keys())}"
        )

    duplicate_sources: dict[str, list[str]] = {}
    for raw_id, canonical_id in zip(raw_component_ids, component_ids, strict=True):
        duplicate_sources.setdefault(canonical_id, []).append(raw_id)
    duplicates = {
        canonical_id: raw_ids
        for canonical_id, raw_ids in duplicate_sources.items()
        if len(raw_ids) > 1
    }
    if duplicates:
        raise ValueError(
            f"Duplicate component IDs after alias resolution in {label}: {duplicates}"
        )

    return component_ids, mole_fractions


def _prepare_swelling_inputs(config: RunConfig) -> PreparedSwellingContext:
    """Build the bounded two-feed runtime package for swelling-test execution."""
    from pvtcore.models import load_components

    swelling_config = config.swelling_test_config
    if swelling_config is None:
        raise ValueError("swelling_test_config is required for SWELLING_TEST calculation")
    if config.composition is None:
        raise ValueError("composition is required for SWELLING_TEST calculation")

    all_components = load_components()
    oil_component_ids, oil_composition = _resolve_explicit_component_feed(
        config.composition,
        label="composition",
        all_components=all_components,
    )
    gas_component_ids, injection_gas_composition = _resolve_explicit_component_feed(
        swelling_config.injection_gas_composition,
        label="swelling_test_config.injection_gas_composition",
        all_components=all_components,
    )

    union_component_ids = list(oil_component_ids)
    for component_id in gas_component_ids:
        if component_id not in union_component_ids:
            union_component_ids.append(component_id)

    component_positions = {
        component_id: index for index, component_id in enumerate(union_component_ids)
    }
    aligned_oil = np.zeros(len(union_component_ids), dtype=np.float64)
    aligned_gas = np.zeros(len(union_component_ids), dtype=np.float64)

    for component_id, fraction in zip(oil_component_ids, oil_composition, strict=True):
        aligned_oil[component_positions[component_id]] = float(fraction)
    for component_id, fraction in zip(gas_component_ids, injection_gas_composition, strict=True):
        aligned_gas[component_positions[component_id]] = float(fraction)

    components = [all_components[component_id] for component_id in union_component_ids]
    eos = _build_runtime_eos(config, components)
    binary_interaction = _build_binary_interaction_matrix(
        union_component_ids,
        components,
        config,
    )

    return PreparedSwellingContext(
        component_ids=union_component_ids,
        components=components,
        oil_composition=aligned_oil,
        injection_gas_composition=aligned_gas,
        eos=eos,
        binary_interaction=binary_interaction,
    )


def _prepare_fluid_inputs(config: RunConfig) -> PreparedFluidContext:
    """Build the first-class runtime fluid package used by all non-TBP workflows."""
    from pvtcore.characterization import characterize_fluid
    from pvtcore.models import load_components, resolve_component_id

    config = _resolve_config_characterization(config)

    all_components = load_components()
    inline_components = {
        spec.component_id: spec
        for spec in config.composition.inline_components
    }
    if config.composition.plus_fraction is not None and inline_components:
        raise ValueError("plus_fraction and inline_components cannot be used together in the current runtime path")

    if inline_components:
        for inline_id in inline_components:
            try:
                resolve_component_id(inline_id, all_components)
            except KeyError:
                continue
            raise ValueError(
                f"Inline pseudo component ID '{inline_id}' conflicts with a database component or alias"
            )

    raw_component_ids = [entry.component_id for entry in config.composition.components]
    mole_fractions = [entry.mole_fraction for entry in config.composition.components]

    component_ids = []
    missing = []
    for cid in raw_component_ids:
        if cid in inline_components:
            component_ids.append(cid)
            continue
        try:
            component_ids.append(resolve_component_id(cid, all_components))
        except KeyError:
            missing.append(cid)

    if missing:
        raise ValueError(
            f"Unknown component(s): {missing}. "
            f"Available: {sorted(all_components.keys())}"
        )

    duplicate_sources: Dict[str, List[str]] = {}
    for raw_id, canonical_id in zip(raw_component_ids, component_ids):
        duplicate_sources.setdefault(canonical_id, []).append(raw_id)
    duplicates = {
        canonical_id: raw_ids
        for canonical_id, raw_ids in duplicate_sources.items()
        if len(raw_ids) > 1
    }
    if duplicates:
        raise ValueError(
            f"Duplicate component IDs after alias resolution: {duplicates}"
        )

    if config.composition.plus_fraction is not None:
        runtime_inputs = _resolve_runtime_plus_fraction_characterization_inputs(config)
        if runtime_inputs is None:
            raise RuntimeError("plus_fraction runtime inputs could not be resolved")
        resolved_feed, plus_spec, characterization_config, _observed_tbp_rows = runtime_inputs
        characterized = characterize_fluid(
            resolved_feed,
            plus_fraction=plus_spec,
            config=characterization_config,
        )
        components = list(characterized.components)
        component_ids = list(characterized.component_ids)
        composition = np.asarray(characterized.composition, dtype=np.float64)
        precomputed_binary_interaction = np.asarray(characterized.binary_interaction, dtype=np.float64)
        eos = _build_runtime_eos(config, components)
        runtime_characterization = _build_runtime_characterization_from_prepared_plus_fraction(
            characterized=characterized,
            characterization_config=characterization_config,
            plus_spec=plus_spec,
            observed_tbp_rows=_observed_tbp_rows,
        )
        return PreparedFluidContext(
            component_ids=component_ids,
            components=components,
            composition=composition,
            eos=eos,
            binary_interaction=precomputed_binary_interaction,
            characterization_result=characterized,
            runtime_characterization=runtime_characterization,
            detailed_reconstruction=runtime_characterization.detailed_reconstruction,
            detailed_reconstruction_unavailable_reason=(
                runtime_characterization.detailed_reconstruction_unavailable_reason
            ),
        )

    components = [
        _build_inline_component(inline_components[cid]) if cid in inline_components else all_components[cid]
        for cid in component_ids
    ]
    composition = np.array(mole_fractions, dtype=np.float64)
    eos = _build_runtime_eos(config, components)
    binary_interaction = _build_binary_interaction_matrix(component_ids, components, config)
    return PreparedFluidContext(
        component_ids=component_ids,
        components=components,
        composition=composition,
        eos=eos,
        binary_interaction=binary_interaction,
    )


def _build_delumped_saturation_reporting(
    *,
    prepared_fluid: PreparedFluidContext,
    liquid_composition: np.ndarray,
    vapor_composition: np.ndarray,
    k_values: np.ndarray,
) -> ReportedEquilibriumCompositions | None:
    """Recover SCN-detail saturation reporting from a lumped runtime solve."""
    delumped = _build_delumped_runtime_equilibrium_surface(
        prepared_fluid=prepared_fluid,
        liquid_composition=liquid_composition,
        vapor_composition=vapor_composition,
        k_values=k_values,
    )
    if delumped is None:
        return None

    return ReportedEquilibriumCompositions(
        component_basis="delumped_scn",
        liquid_composition={
            component_id: float(delumped.liquid_composition[index])
            for index, component_id in enumerate(delumped.component_ids)
        },
        vapor_composition={
            component_id: float(delumped.vapor_composition[index])
            for index, component_id in enumerate(delumped.component_ids)
        },
        k_values={
            component_id: float(delumped.k_values[index])
            for index, component_id in enumerate(delumped.component_ids)
        },
    )


def _build_delumped_runtime_equilibrium_surface(
    *,
    prepared_fluid: PreparedFluidContext,
    liquid_composition: np.ndarray,
    vapor_composition: np.ndarray,
    k_values: np.ndarray,
) -> DelumpedRuntimeEquilibriumSurface | None:
    """Expand a lumped runtime equilibrium surface back onto the detailed SCN basis."""
    from pvtcore.characterization.delumping import delump_kvalue_interpolation

    characterized = prepared_fluid.characterization_result
    runtime = prepared_fluid.runtime_characterization
    if (
        characterized is None
        or getattr(characterized, "lumping", None) is None
        or runtime is None
        or runtime.runtime_component_basis != "lumped"
    ):
        return None

    lumping = characterized.lumping
    n_runtime_components = len(prepared_fluid.component_ids)
    n_lumps = len(lumping.lump_component_ids)
    light_count = n_runtime_components - n_lumps
    if light_count < 0:
        raise RuntimeError("Runtime lump metadata is inconsistent with the prepared fluid component list")

    liquid_runtime = np.asarray(liquid_composition, dtype=np.float64)
    vapor_runtime = np.asarray(vapor_composition, dtype=np.float64)
    k_runtime = np.asarray(k_values, dtype=np.float64)
    if (
        liquid_runtime.size != n_runtime_components
        or vapor_runtime.size != n_runtime_components
        or k_runtime.size != n_runtime_components
    ):
        raise RuntimeError("Saturation result arrays do not align with the prepared runtime component basis")

    light_component_ids = list(prepared_fluid.component_ids[:light_count])
    detailed_component_ids = light_component_ids + list(lumping.scn_component_ids)
    z_detailed = np.concatenate(
        [
            np.asarray(prepared_fluid.composition[:light_count], dtype=np.float64),
            np.asarray(lumping.scn_z, dtype=np.float64),
        ]
    )
    mw_runtime = np.asarray([float(component.MW) for component in prepared_fluid.components], dtype=np.float64)
    mw_detailed = np.concatenate(
        [
            np.asarray(
                [float(component.MW) for component in prepared_fluid.components[:light_count]],
                dtype=np.float64,
            ),
            np.asarray(lumping.scn_props.mw, dtype=np.float64),
        ]
    )
    lump_mapping = [[index] for index in range(light_count)]
    lump_mapping.extend(
        [[light_count + int(member) for member in members] for members in lumping.lump_members]
    )

    delumped = delump_kvalue_interpolation(
        K_lumped=k_runtime,
        x_lumped=liquid_runtime,
        y_lumped=vapor_runtime,
        MW_lumped=mw_runtime,
        z_detailed=z_detailed,
        MW_detailed=mw_detailed,
        lump_mapping=lump_mapping,
    )

    return DelumpedRuntimeEquilibriumSurface(
        component_ids=detailed_component_ids,
        liquid_composition=np.asarray(delumped.x, dtype=np.float64),
        vapor_composition=np.asarray(delumped.y, dtype=np.float64),
        k_values=np.asarray(delumped.K, dtype=np.float64),
    )


def _build_preserved_detailed_runtime_fluid(
    config: RunConfig,
    prepared_fluid: PreparedFluidContext,
) -> tuple[list[str], list[object], np.ndarray, object, np.ndarray] | None:
    """Rebuild the preserved detailed SCN fluid basis stored in the runtime package."""
    from pvtcore.models import load_components, resolve_component_id
    from pvtcore.models.component import Component, PseudoType

    reconstruction = prepared_fluid.detailed_reconstruction
    if reconstruction is None:
        return None

    all_components = load_components()
    component_ids = [entry.component_id for entry in reconstruction.components]
    if not component_ids:
        raise RuntimeError("Detailed reconstruction component basis is empty")
    components: list[object] = []
    for entry in reconstruction.components:
        if entry.source == "resolved_feed_component":
            try:
                canonical_id = resolve_component_id(entry.component_id, all_components)
            except KeyError:
                canonical_id = None
            if canonical_id is not None and canonical_id in all_components:
                components.append(all_components[canonical_id])
                continue

        is_scn = entry.source == "characterized_scn"
        scn_index = None
        if is_scn and entry.component_id.startswith("SCN"):
            try:
                scn_index = int(entry.component_id[3:])
            except ValueError as exc:
                raise RuntimeError(
                    f"Detailed reconstruction SCN component id is malformed: {entry.component_id}"
                ) from exc
        components.append(
            Component(
                name=entry.component_id,
                formula=entry.component_id,
                id=entry.component_id,
                Tc=float(entry.critical_temperature_k),
                Pc=float(entry.critical_pressure_pa),
                Vc=float(entry.critical_volume_m3_per_mol),
                omega=float(entry.omega),
                MW=float(entry.molecular_weight_g_per_mol),
                Tb=(
                    float(entry.boiling_point_k)
                    if entry.boiling_point_k is not None
                    else 1.0
                ),
                note="Preserved detailed runtime reconstruction component",
                is_pseudo=is_scn,
                pseudo_type=PseudoType.SCN if is_scn else None,
                scn_index=scn_index,
            )
        )

    composition = np.asarray(
        [float(entry.feed_mole_fraction) for entry in reconstruction.components],
        dtype=np.float64,
    )
    if not np.all(np.isfinite(composition)):
        raise RuntimeError("Detailed reconstruction composition contains non-finite values")
    total = float(np.sum(composition))
    if total <= 0.0:
        raise RuntimeError("Detailed reconstruction composition is empty")
    composition = composition / total

    binary_interaction = np.asarray(reconstruction.binary_interaction_matrix, dtype=np.float64)
    if binary_interaction.shape != (len(component_ids), len(component_ids)):
        raise RuntimeError(
            "Detailed reconstruction BIP matrix shape does not align with the preserved component order"
        )
    if not np.all(np.isfinite(binary_interaction)):
        raise RuntimeError("Detailed reconstruction BIP matrix contains non-finite values")

    eos = _build_runtime_eos(config, components)
    return component_ids, components, composition, eos, binary_interaction


def _build_reconstructed_pt_flash_reporting(
    *,
    config: RunConfig,
    prepared_fluid: PreparedFluidContext,
    flash_result,
) -> ReportedPTFlashThermodynamicSurface | None:
    """Reconstruct a detailed SCN thermodynamic surface from a preserved SCN flash."""
    if flash_result.phase != "two-phase":
        return None

    from pvtcore.flash import pt_flash

    detailed_fluid = _build_preserved_detailed_runtime_fluid(config, prepared_fluid)
    if detailed_fluid is None:
        return None

    (
        detailed_component_ids,
        detailed_components,
        detailed_feed_composition,
        detailed_eos,
        detailed_binary_interaction,
    ) = detailed_fluid

    detailed_result = pt_flash(
        pressure=float(flash_result.pressure),
        temperature=float(flash_result.temperature),
        composition=np.asarray(detailed_feed_composition, dtype=np.float64),
        components=detailed_components,
        eos=detailed_eos,
        binary_interaction=detailed_binary_interaction,
        tolerance=config.solver_settings.tolerance,
        max_iterations=config.solver_settings.max_iterations,
    )
    if not detailed_result.converged or detailed_result.phase != "two-phase":
        return None

    return ReportedPTFlashThermodynamicSurface(
        component_basis="reconstructed_scn",
        liquid_composition={
            component_id: float(detailed_result.liquid_composition[index])
            for index, component_id in enumerate(detailed_component_ids)
        },
        vapor_composition={
            component_id: float(detailed_result.vapor_composition[index])
            for index, component_id in enumerate(detailed_component_ids)
        },
        k_values={
            component_id: float(detailed_result.K_values[index])
            for index, component_id in enumerate(detailed_component_ids)
        },
        liquid_fugacity={
            component_id: float(detailed_result.liquid_fugacity[index])
            for index, component_id in enumerate(detailed_component_ids)
        },
        vapor_fugacity={
            component_id: float(detailed_result.vapor_fugacity[index])
            for index, component_id in enumerate(detailed_component_ids)
        },
    )


def _resolve_reported_pt_flash_surface(
    *,
    config: RunConfig,
    prepared_fluid: PreparedFluidContext,
    flash_result,
) -> ReportedPTFlashSurfaceOutcome:
    """Resolve the optional reported PT-flash surface plus explicit absence diagnostics."""
    if flash_result.phase != "two-phase":
        if prepared_fluid.runtime_characterization is None:
            return ReportedPTFlashSurfaceOutcome(surface=None)
        return ReportedPTFlashSurfaceOutcome(
            surface=None,
            status="withheld_single_phase_runtime",
            reason=(
                "Reported SCN thermodynamics are only emitted when the runtime PT flash is two-phase."
            ),
        )

    if prepared_fluid.detailed_reconstruction is None:
        if prepared_fluid.runtime_characterization is None:
            return ReportedPTFlashSurfaceOutcome(surface=None)
        return ReportedPTFlashSurfaceOutcome(
            surface=None,
            status="unavailable_no_detailed_reconstruction",
            reason=(
                prepared_fluid.detailed_reconstruction_unavailable_reason
                or "No detailed reconstruction payload was preserved for this runtime package."
            ),
        )

    try:
        surface = _build_reconstructed_pt_flash_reporting(
            config=config,
            prepared_fluid=prepared_fluid,
            flash_result=flash_result,
        )
    except Exception as exc:
        return ReportedPTFlashSurfaceOutcome(
            surface=None,
            status="failed_reconstruction",
            reason=f"Detailed SCN thermodynamic reconstruction failed: {exc}",
        )

    if surface is None:
        return ReportedPTFlashSurfaceOutcome(
            surface=None,
            status="failed_reconstruction",
            reason=(
                "Detailed SCN thermodynamic reconstruction did not produce a two-phase reported surface."
            ),
        )

    return ReportedPTFlashSurfaceOutcome(
        surface=surface,
        status="available",
    )


def _build_runtime_eos(config: RunConfig, components):
    """Build the runtime EOS instance declared by the run config."""
    from pvtcore.eos import PR78EOS, PengRobinsonEOS, SRKEOS

    if config.eos_type == EOSType.PENG_ROBINSON:
        return PengRobinsonEOS(components)
    if config.eos_type == EOSType.SRK:
        return SRKEOS(components)
    if config.eos_type == EOSType.PR78:
        return PR78EOS(components)

    if config.eos_type in RUNTIME_UNSUPPORTED_EOS_MESSAGES:
        raise ValueError(RUNTIME_UNSUPPORTED_EOS_MESSAGES[config.eos_type])

    raise ValueError(f"Unsupported EOS type: {config.eos_type}")


def _build_binary_interaction_matrix(
    component_ids: List[str],
    components,
    config: RunConfig,
):
    """Build the symmetric binary interaction matrix if one was supplied."""
    from pvtcore.models import load_components, resolve_component_id

    binary_interaction = None
    if config.binary_interaction:
        all_components = load_components()
        component_positions = {component_id: i for i, component_id in enumerate(component_ids)}
        n = len(components)
        binary_interaction = np.zeros((n, n))
        for pair_key, kij in config.binary_interaction.items():
            parts = pair_key.split("-")
            if len(parts) != 2:
                raise ValueError(f"Invalid BIP pair key: {pair_key}. Expected 'comp1-comp2'")
            try:
                resolved_parts = []
                for part in parts:
                    if part in component_positions:
                        resolved_parts.append(part)
                    else:
                        resolved_parts.append(resolve_component_id(part, all_components))
                i = component_positions[resolved_parts[0]]
                j = component_positions[resolved_parts[1]]
            except KeyError:
                raise ValueError(f"BIP pair key contains unknown component: {pair_key}")
            binary_interaction[i, j] = kij
            binary_interaction[j, i] = kij
    return binary_interaction


def validate_runtime_config(config: RunConfig) -> None:
    """Validate runtime prerequisites without executing a calculation."""
    if config.calculation_type == CalculationType.TBP:
        execute_tbp(config)
        return
    if config.calculation_type == CalculationType.SWELLING_TEST:
        _prepare_swelling_inputs(config)
        return
    config = _resolve_config_characterization(config)
    _prepare_fluid_inputs(config)


def _build_tbp_characterization_context(kernel_result) -> TBPCharacterizationContext:
    """Build the bounded standalone TBP characterization bridge context."""
    runtime_characterization = _build_runtime_characterization_from_tbp(kernel_result)

    notes = [
        (
            "Standalone TBP assay artifacts now preserve the canonical runtime characterization "
            "package rather than only aggregate C<n>+ bridge values."
        ),
        (
            "SCN distributions are recorded on both assay basis and plus-fraction-normalized "
            "basis so the standalone assay does not discard the original heavy-end scale."
        ),
        (
            "No lumping or TBP-aware BIP/EOS selection is applied yet; this bridge preserves "
            "the derived SCN property table and fit metadata only."
        ),
    ]
    if any(cut.specific_gravity is not None for cut in kernel_result.cuts):
        notes.append(
            "Cut-level specific gravities are preserved on the assay input, but SG+ is still not auto-derived."
        )

    return TBPCharacterizationContext(
        source="tbp_assay",
        bridge_status="characterized_scn",
        plus_fraction_label=runtime_characterization.plus_fraction_label,
        cut_start=runtime_characterization.cut_start,
        cut_end=runtime_characterization.cut_end,
        cut_count=len(kernel_result.cuts),
        z_plus=runtime_characterization.z_plus,
        mw_plus_g_per_mol=runtime_characterization.mw_plus_g_per_mol,
        sg_plus_60f=runtime_characterization.sg_plus_60f,
        characterization_method=(
            "pedersen_fit_to_tbp"
            if runtime_characterization.pedersen_fit is not None
            and runtime_characterization.pedersen_fit.solve_ab_from == "fit_to_tbp"
            else runtime_characterization.split_method
        ),
        split_mw_model=runtime_characterization.split_mw_model,
        pseudo_property_correlation=runtime_characterization.pseudo_property_correlation,
        runtime_component_basis=runtime_characterization.runtime_component_basis,
        pedersen_fit=runtime_characterization.pedersen_fit,
        cut_mappings=runtime_characterization.cut_mappings,
        scn_distribution=[
            TBPCharacterizationSCNEntry(
                component_id=entry.component_id,
                carbon_number=entry.carbon_number,
                assay_mole_fraction=entry.feed_mole_fraction,
                normalized_mole_fraction=entry.normalized_plus_mole_fraction,
                normalized_mass_fraction=entry.normalized_plus_mass_fraction,
                molecular_weight_g_per_mol=entry.molecular_weight_g_per_mol,
                specific_gravity_60f=entry.specific_gravity_60f,
                boiling_point_k=entry.boiling_point_k,
                critical_temperature_k=entry.critical_temperature_k,
                critical_pressure_pa=entry.critical_pressure_pa,
                critical_volume_m3_per_mol=entry.critical_volume_m3_per_mol,
                omega=entry.omega,
            )
            for entry in runtime_characterization.scn_distribution
        ],
        notes=notes,
    )


def execute_tbp(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> TBPExperimentResult:
    """Execute the bounded standalone TBP assay runtime."""
    from pvtcore.experiments.tbp import simulate_tbp

    tbp_config = config.tbp_config
    if tbp_config is None:
        raise ValueError("tbp_config is required for TBP calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.2, "Validating TBP assay cuts...")
    _raise_if_cancelled(callback)

    kernel_result = simulate_tbp(
        [cut.model_dump(mode="python", exclude_none=True) for cut in tbp_config.cuts],
        cut_start=tbp_config.cut_start,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.65, "Deriving standalone TBP characterization context...")
    _raise_if_cancelled(callback)

    characterization_context = _build_tbp_characterization_context(kernel_result)

    if callback:
        callback.on_progress(config.run_id or "", 0.85, "Processing TBP assay summary...")
    _raise_if_cancelled(callback)

    return TBPExperimentResult(
        cut_start=kernel_result.cut_start,
        cut_end=kernel_result.cut_end,
        z_plus=float(kernel_result.z_plus),
        mw_plus_g_per_mol=float(kernel_result.mw_plus_g_per_mol),
        cuts=[
            TBPExperimentCutResult(
                name=cut.name,
                carbon_number=cut.carbon_number,
                carbon_number_end=cut.carbon_number_end,
                mole_fraction=float(cut.mole_fraction),
                normalized_mole_fraction=float(cut.normalized_mole_fraction),
                cumulative_mole_fraction=float(cut.cumulative_mole_fraction),
                molecular_weight_g_per_mol=float(cut.molecular_weight_g_per_mol),
                normalized_mass_fraction=float(cut.normalized_mass_fraction),
                cumulative_mass_fraction=float(cut.cumulative_mass_fraction),
                specific_gravity=None if cut.specific_gravity is None else float(cut.specific_gravity),
                boiling_point_k=None if cut.boiling_point_k is None else float(cut.boiling_point_k),
                boiling_point_source=cut.boiling_point_source,
            )
            for cut in kernel_result.cuts
        ],
        characterization_context=characterization_context,
    )


def execute_cce(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> CCEResult:
    """Execute a CCE calculation."""
    from pvtcore.experiments.cce import simulate_cce

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or "", 0.2, "Setting up EOS...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    cce_config = config.cce_config
    if cce_config is None:
        raise ValueError("cce_config is required for CCE calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running CCE calculation...")

    cce_pressure_steps = None
    if cce_config.pressure_points_pa is not None:
        cce_pressure_steps = np.asarray(cce_config.pressure_points_pa, dtype=np.float64)

    result = simulate_cce(
        composition=z,
        temperature=cce_config.temperature_k,
        components=components,
        eos=eos,
        pressure_start=cce_config.pressure_start_pa,
        pressure_end=cce_config.pressure_end_pa,
        n_steps=cce_config.n_steps,
        pressure_steps=cce_pressure_steps,
        binary_interaction=binary_interaction,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    steps: list[CCEStepResult] = []
    for step in result.steps:
        steps.append(
            CCEStepResult(
                pressure_pa=float(step.pressure),
                relative_volume=float(step.relative_volume),
                liquid_fraction=_finite_or_none(step.liquid_volume_fraction),
                vapor_fraction=_finite_or_none(step.vapor_fraction),
                z_factor=_finite_or_none(step.compressibility_Z),
                liquid_density_kg_per_m3=_finite_or_none(step.liquid_density),
                vapor_density_kg_per_m3=_finite_or_none(step.vapor_density),
                liquid_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "liquid",
                    step.liquid_composition,
                ),
                vapor_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "vapor",
                    step.vapor_composition,
                ),
                liquid_composition=_composition_array_to_dict(
                    component_ids, step.liquid_composition
                ),
                vapor_composition=_composition_array_to_dict(
                    component_ids, step.vapor_composition
                ),
            )
        )

    return CCEResult(
        temperature_k=float(result.temperature),
        saturation_pressure_pa=_finite_or_none(result.saturation_pressure),
        steps=steps,
    )


def execute_bubble_point(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> BubblePointResult:
    """Execute a bubble-point pressure calculation."""
    from pvtcore.flash import calculate_bubble_point

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    bubble_config = config.bubble_point_config
    if bubble_config is None:
        raise ValueError("bubble_point_config is required for BUBBLE_POINT calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running bubble-point calculation...")

    result = calculate_bubble_point(
        temperature=bubble_config.temperature_k,
        composition=z,
        components=components,
        eos=eos,
        pressure_initial=bubble_config.pressure_initial_pa,
        binary_interaction=binary_interaction,
        tolerance=config.solver_settings.tolerance,
        max_iterations=config.solver_settings.max_iterations,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    diagnostics = _build_solver_diagnostics(result)
    certificate = _build_solver_certificate(result)
    reported = _build_delumped_saturation_reporting(
        prepared_fluid=prepared,
        liquid_composition=result.liquid_composition,
        vapor_composition=result.vapor_composition,
        k_values=result.K_values,
    )

    return BubblePointResult(
        converged=bool(result.converged),
        pressure_pa=float(result.pressure),
        temperature_k=float(result.temperature),
        iterations=int(result.iterations),
        residual=float(result.residual),
        stable_liquid=bool(result.stable_liquid),
        liquid_composition={cid: float(result.liquid_composition[i]) for i, cid in enumerate(component_ids)},
        vapor_composition={cid: float(result.vapor_composition[i]) for i, cid in enumerate(component_ids)},
        k_values={cid: float(result.K_values[i]) for i, cid in enumerate(component_ids)},
        reported_component_basis=(
            None if reported is None else reported.component_basis
        ),
        reported_liquid_composition=(
            None if reported is None else reported.liquid_composition
        ),
        reported_vapor_composition=(
            None if reported is None else reported.vapor_composition
        ),
        reported_k_values=None if reported is None else reported.k_values,
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_dew_point(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> DewPointResult:
    """Execute a dew-point pressure calculation."""
    from pvtcore.flash import calculate_dew_point

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    dew_config = config.dew_point_config
    if dew_config is None:
        raise ValueError("dew_point_config is required for DEW_POINT calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running dew-point calculation...")

    result = calculate_dew_point(
        temperature=dew_config.temperature_k,
        composition=z,
        components=components,
        eos=eos,
        pressure_initial=dew_config.pressure_initial_pa,
        binary_interaction=binary_interaction,
        tolerance=config.solver_settings.tolerance,
        max_iterations=config.solver_settings.max_iterations,
        prefer_canonical_branch=True,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    diagnostics = _build_solver_diagnostics(result)
    certificate = _build_solver_certificate(result)
    reported = _build_delumped_saturation_reporting(
        prepared_fluid=prepared,
        liquid_composition=result.liquid_composition,
        vapor_composition=result.vapor_composition,
        k_values=result.K_values,
    )

    return DewPointResult(
        converged=bool(result.converged),
        pressure_pa=float(result.pressure),
        temperature_k=float(result.temperature),
        iterations=int(result.iterations),
        residual=float(result.residual),
        stable_vapor=bool(result.stable_vapor),
        liquid_composition={cid: float(result.liquid_composition[i]) for i, cid in enumerate(component_ids)},
        vapor_composition={cid: float(result.vapor_composition[i]) for i, cid in enumerate(component_ids)},
        k_values={cid: float(result.K_values[i]) for i, cid in enumerate(component_ids)},
        reported_component_basis=(
            None if reported is None else reported.component_basis
        ),
        reported_liquid_composition=(
            None if reported is None else reported.liquid_composition
        ),
        reported_vapor_composition=(
            None if reported is None else reported.vapor_composition
        ),
        reported_k_values=None if reported is None else reported.k_values,
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_dl(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> DLResult:
    """Execute a Differential Liberation calculation."""
    from pvtcore.experiments import simulate_dl

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    dl_config = config.dl_config
    if dl_config is None:
        raise ValueError("dl_config is required for DL calculation")

    if dl_config.pressure_points_pa is not None:
        pressure_steps = np.asarray(dl_config.pressure_points_pa, dtype=np.float64)
    else:
        pressure_steps = np.linspace(
            dl_config.bubble_pressure_pa,
            dl_config.pressure_end_pa,
            dl_config.n_steps,
            dtype=np.float64,
        )

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running DL calculation...")

    result = simulate_dl(
        composition=z,
        temperature=dl_config.temperature_k,
        components=components,
        eos=eos,
        bubble_pressure=dl_config.bubble_pressure_pa,
        pressure_steps=pressure_steps,
        binary_interaction=binary_interaction,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    steps: list[DLStepResult] = []
    for step in result.steps:
        steps.append(
            DLStepResult(
                pressure_pa=float(step.pressure),
                rs=float(step.Rs),
                rs_scf_stb=float(step.Rs_scf_stb),
                bg=_finite_or_none(step.Bg),
                bg_rb_per_scf=_finite_or_none(step.Bg_rb_per_scf),
                bo=float(step.Bo),
                bt=float(step.Bt),
                vapor_fraction=float(step.vapor_fraction),
                oil_density_kg_per_m3=_finite_or_none(step.oil_density),
                oil_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "liquid",
                    step.liquid_composition,
                ),
                gas_gravity=_finite_or_none(step.gas_gravity),
                gas_z_factor=_finite_or_none(step.gas_Z),
                gas_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "vapor",
                    step.gas_composition,
                ),
                cumulative_gas_produced=_finite_or_none(step.cumulative_gas),
                cumulative_gas_produced_scf_stb=_finite_or_none(step.cumulative_gas_scf_stb),
                liquid_moles_remaining=_finite_or_none(step.liquid_moles_remaining),
                liquid_composition=_composition_array_to_dict(
                    component_ids, step.liquid_composition
                ),
                gas_composition=_composition_array_to_dict(
                    component_ids, step.gas_composition
                ),
            )
        )

    return DLResult(
        temperature_k=float(result.temperature),
        bubble_pressure_pa=float(result.bubble_pressure),
        rsi=float(result.Rsi),
        rsi_scf_stb=float(result.Rsi_scf_stb),
        boi=float(result.Boi),
        residual_oil_density_kg_per_m3=_finite_or_none(result.residual_oil_density),
        converged=bool(result.converged),
        steps=steps,
    )


def execute_cvd(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> CVDResult:
    """Execute a Constant Volume Depletion calculation."""
    from pvtcore.experiments import simulate_cvd

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    cvd_config = config.cvd_config
    if cvd_config is None:
        raise ValueError("cvd_config is required for CVD calculation")

    pressure_steps = np.linspace(
        cvd_config.dew_pressure_pa,
        cvd_config.pressure_end_pa,
        cvd_config.n_steps,
        dtype=np.float64,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running CVD calculation...")

    result = simulate_cvd(
        composition=z,
        temperature=cvd_config.temperature_k,
        components=components,
        eos=eos,
        dew_pressure=cvd_config.dew_pressure_pa,
        pressure_steps=pressure_steps,
        binary_interaction=binary_interaction,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    steps: list[CVDStepResult] = []
    for step in result.steps:
        steps.append(
            CVDStepResult(
                pressure_pa=float(step.pressure),
                liquid_dropout=float(step.liquid_dropout),
                gas_produced=_finite_or_none(step.gas_produced),
                cumulative_gas_produced=float(step.cumulative_gas_produced),
                moles_remaining=_finite_or_none(step.moles_remaining),
                z_two_phase=_finite_or_none(step.Z_two_phase),
                liquid_density_kg_per_m3=_finite_or_none(step.liquid_density),
                vapor_density_kg_per_m3=_finite_or_none(step.vapor_density),
                liquid_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "liquid",
                    step.liquid_composition,
                ),
                vapor_viscosity_pa_s=_compute_phase_viscosity(
                    float(step.pressure),
                    float(step.temperature),
                    components,
                    eos,
                    binary_interaction,
                    "vapor",
                    step.vapor_composition,
                ),
            )
        )

    return CVDResult(
        temperature_k=float(result.temperature),
        dew_pressure_pa=float(result.dew_pressure),
        initial_z=float(result.initial_Z),
        converged=bool(result.converged),
        steps=steps,
    )


def execute_swelling_test(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_swelling: Optional[PreparedSwellingContext] = None,
) -> SwellingTestResult:
    """Execute the first-slice swelling-test calculation."""
    from pvtcore.experiments import simulate_swelling

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Validating swelling inputs...")

    prepared = prepared_swelling or _prepare_swelling_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction

    swelling_config = config.swelling_test_config
    if swelling_config is None:
        raise ValueError("swelling_test_config is required for SWELLING_TEST calculation")

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Building union fluid basis...")

    if callback:
        callback.on_progress(config.run_id or "", 0.6, "Running swelling test...")

    kernel_result = simulate_swelling(
        oil_composition=prepared.oil_composition,
        injection_gas_composition=prepared.injection_gas_composition,
        temperature=swelling_config.temperature_k,
        components=components,
        eos=eos,
        enrichment_steps=swelling_config.enrichment_steps_mol_per_mol_oil,
        binary_interaction=binary_interaction,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Packaging swelling results...")

    steps: list[SwellingStepResultData] = []
    for step in kernel_result.steps:
        vapor_vector = np.asarray(step.incipient_vapor_composition, dtype=np.float64)
        k_vector = np.asarray(step.k_values, dtype=np.float64)
        incipient_vapor = (
            None
            if not np.all(np.isfinite(vapor_vector))
            else {
                component_id: float(vapor_vector[index])
                for index, component_id in enumerate(component_ids)
            }
        )
        k_values = (
            None
            if not np.all(np.isfinite(k_vector))
            else {
                component_id: float(k_vector[index])
                for index, component_id in enumerate(component_ids)
            }
        )
        steps.append(
            SwellingStepResultData(
                step_index=int(step.step_index),
                added_gas_moles_per_mole_oil=float(step.added_gas_moles_per_mole_oil),
                total_mixture_moles_per_mole_oil=float(step.total_mixture_moles_per_mole_oil),
                bubble_pressure_pa=_finite_or_none(step.bubble_pressure),
                swelling_factor=_finite_or_none(step.swelling_factor),
                saturated_liquid_molar_volume_m3_per_mol=_finite_or_none(
                    step.saturated_liquid_molar_volume
                ),
                saturated_liquid_density_kg_per_m3=_finite_or_none(
                    step.saturated_liquid_density
                ),
                enriched_feed_composition={
                    component_id: float(step.enriched_feed_composition[index])
                    for index, component_id in enumerate(component_ids)
                },
                incipient_vapor_composition=incipient_vapor,
                k_values=k_values,
                status=str(step.status),
                message=step.message,
            )
        )

    return SwellingTestResult(
        temperature_k=float(kernel_result.temperature),
        baseline_bubble_pressure_pa=_finite_or_none(kernel_result.baseline_bubble_pressure),
        baseline_saturated_liquid_molar_volume_m3_per_mol=_finite_or_none(
            kernel_result.baseline_saturated_liquid_molar_volume
        ),
        enrichment_steps_mol_per_mol_oil=[
            float(value) for value in np.asarray(kernel_result.enrichment_steps, dtype=np.float64)
        ],
        steps=steps,
        bubble_pressures_pa=[
            _finite_or_none(value)
            for value in np.asarray(kernel_result.bubble_pressures, dtype=np.float64)
        ],
        swelling_factors=[
            _finite_or_none(value)
            for value in np.asarray(kernel_result.swelling_factors, dtype=np.float64)
        ],
        fully_certified=bool(kernel_result.fully_certified),
        overall_status=str(kernel_result.overall_status),
    )


def execute_separator(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
    prepared_fluid: Optional[PreparedFluidContext] = None,
) -> SeparatorResult:
    """Execute a multi-stage separator-train calculation."""
    from pvtcore.experiments import SeparatorConditions, calculate_separator_train

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    prepared = prepared_fluid or _prepare_fluid_inputs(config)
    component_ids = prepared.component_ids
    components = prepared.components
    z = prepared.composition
    eos = prepared.eos
    binary_interaction = prepared.binary_interaction
    _ = component_ids  # component IDs not needed in separator schema output

    separator_config = config.separator_config
    if separator_config is None:
        raise ValueError("separator_config is required for SEPARATOR calculation")

    separator_stages = [
        SeparatorConditions(
            pressure=stage.pressure_pa,
            temperature=stage.temperature_k,
            name=stage.name or f"Stage {idx + 1}",
        )
        for idx, stage in enumerate(separator_config.separator_stages)
    ]

    if callback:
        callback.on_progress(config.run_id or "", 0.3, "Running separator calculation...")

    result = calculate_separator_train(
        composition=z,
        components=components,
        eos=eos,
        separator_stages=separator_stages,
        reservoir_pressure=separator_config.reservoir_pressure_pa,
        reservoir_temperature=separator_config.reservoir_temperature_k,
        binary_interaction=binary_interaction,
        include_stock_tank=separator_config.include_stock_tank,
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    return SeparatorResult(
        bo=float(result.Bo),
        rs=float(result.Rs),
        rs_scf_stb=float(result.Rs_scf_stb),
        bg=float(result.Bg),
        api_gravity=float(result.API_gravity),
        stock_tank_oil_density=float(result.stock_tank_oil_density),
        stock_tank_oil_mw_g_per_mol=_finite_or_none(result.stock_tank_oil_MW),
        stock_tank_oil_specific_gravity=_finite_or_none(result.stock_tank_oil_SG),
        total_gas_moles=_finite_or_none(result.total_gas_moles),
        shrinkage=_finite_or_none(result.shrinkage),
        converged=bool(result.converged),
        stages=[
            SeparatorStageResult(
                stage_number=int(stage.stage_number),
                stage_name=str(stage.conditions.name or f"Stage {stage.stage_number + 1}"),
                pressure_pa=float(stage.conditions.pressure),
                temperature_k=float(stage.conditions.temperature),
                vapor_fraction=_finite_or_none(stage.vapor_fraction),
                liquid_moles=_finite_or_none(stage.liquid_moles),
                vapor_moles=_finite_or_none(stage.vapor_moles),
                liquid_density_kg_per_m3=_finite_or_none(stage.liquid_density),
                vapor_density_kg_per_m3=_finite_or_none(stage.vapor_density),
                liquid_z_factor=_finite_or_none(stage.Z_liquid),
                vapor_z_factor=_finite_or_none(stage.Z_vapor),
                converged=bool(stage.converged),
            )
            for stage in result.stages
        ],
    )


# ==============================================================================
# Main Job Runner
# ==============================================================================

def run_calculation(
    config: RunConfig,
    output_dir: Optional[Path] = None,
    callback: Optional[ProgressCallback] = None,
    write_artifacts: bool = True,
) -> RunResult:
    """Execute a PVT calculation and write artifacts.

    This is the main entry point for running calculations. It:
    1. Validates the configuration (hard failure on invalid input)
    2. Creates a run directory
    3. Writes config artifact
    4. Executes the calculation
    5. Writes results and manifest artifacts
    6. Returns the complete result

    Args:
        config: Validated RunConfig object
        output_dir: Directory for run artifacts (default: auto-generated)
        callback: Optional progress callback for GUI integration
        write_artifacts: Whether to write artifact files (default: True)

    Returns:
        RunResult with complete calculation results

    Raises:
        ValueError: If configuration is invalid (hard failure)
        RuntimeError: If calculation fails unexpectedly
    """
    config = _resolve_config_characterization(config)

    # Generate run ID if not provided
    run_id = config.run_id or str(uuid4())[:8]
    started_at = datetime.now()

    if callback:
        callback.on_started(run_id, config.calculation_type.value)

    # Create run directory
    run_dir = None
    if write_artifacts:
        run_dir = create_run_directory(run_id, output_dir)
        write_config_artifact(config, run_dir)

    try:
        _raise_if_cancelled(callback)

        # Execute based on calculation type
        pt_flash_result = None
        stability_analysis_result = None
        bubble_point_result = None
        dew_point_result = None
        phase_envelope_result = None
        tbp_result = None
        cce_result = None
        dl_result = None
        cvd_result = None
        swelling_test_result = None
        separator_result = None
        runtime_characterization = None
        prepared_fluid = None
        prepared_swelling = None

        if config.calculation_type == CalculationType.SWELLING_TEST:
            prepared_swelling = _prepare_swelling_inputs(config)
        elif config.calculation_type != CalculationType.TBP:
            prepared_fluid = _prepare_fluid_inputs(config)

        if config.calculation_type == CalculationType.PT_FLASH:
            pt_flash_result = execute_pt_flash(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.STABILITY_ANALYSIS:
            stability_analysis_result = execute_stability_analysis(
                config,
                callback,
                prepared_fluid=prepared_fluid,
            )

        elif config.calculation_type == CalculationType.BUBBLE_POINT:
            bubble_point_result = execute_bubble_point(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.DEW_POINT:
            dew_point_result = execute_dew_point(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.PHASE_ENVELOPE:
            phase_envelope_result = execute_phase_envelope(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.TBP:
            tbp_result = execute_tbp(config, callback)

        elif config.calculation_type == CalculationType.CCE:
            cce_result = execute_cce(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.DL:
            dl_result = execute_dl(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.CVD:
            cvd_result = execute_cvd(config, callback, prepared_fluid=prepared_fluid)

        elif config.calculation_type == CalculationType.SWELLING_TEST:
            swelling_test_result = execute_swelling_test(
                config,
                callback,
                prepared_swelling=prepared_swelling,
            )

        elif config.calculation_type == CalculationType.SEPARATOR:
            separator_result = execute_separator(config, callback, prepared_fluid=prepared_fluid)

        else:
            raise ValueError(f"Unsupported calculation type: {config.calculation_type}")

        _raise_if_cancelled(callback)

        if config.calculation_type == CalculationType.TBP and tbp_result is not None:
            runtime_characterization = _build_runtime_characterization_from_tbp(tbp_result)
        else:
            runtime_characterization = None if prepared_fluid is None else prepared_fluid.runtime_characterization

        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        result = RunResult(
            run_id=run_id,
            run_name=config.run_name,
            status=RunStatus.COMPLETED,
            error_message=None,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            config=config,
            pt_flash_result=pt_flash_result,
            stability_analysis_result=stability_analysis_result,
            bubble_point_result=bubble_point_result,
            dew_point_result=dew_point_result,
            phase_envelope_result=phase_envelope_result,
            tbp_result=tbp_result,
            cce_result=cce_result,
            dl_result=dl_result,
            cvd_result=cvd_result,
            swelling_test_result=swelling_test_result,
            separator_result=separator_result,
            runtime_characterization=runtime_characterization,
        )

        # Write artifacts
        if write_artifacts and run_dir:
            results_path = write_results_artifact(result, run_dir)

            # Write solver stats if available
            solver_diagnostics = None
            if pt_flash_result and pt_flash_result.diagnostics:
                solver_diagnostics = pt_flash_result.diagnostics
            elif bubble_point_result and bubble_point_result.diagnostics:
                solver_diagnostics = bubble_point_result.diagnostics
            elif dew_point_result and dew_point_result.diagnostics:
                solver_diagnostics = dew_point_result.diagnostics

            if solver_diagnostics is not None:
                write_solver_stats_artifact(solver_diagnostics, run_dir)

            # Create and write manifest
            config_path = run_dir / 'config.json'
            manifest = RunManifest(
                run_id=run_id,
                run_name=config.run_name,
                created_at=started_at,
                completed_at=completed_at,
                pvt_simulator_version=__version__,
                config_sha256=compute_file_sha256(config_path),
                results_sha256=compute_file_sha256(results_path),
                status=RunStatus.COMPLETED,
            )
            write_manifest_artifact(manifest, run_dir)

        if callback:
            callback.on_completed(run_id, result)

        return result

    except CalculationCancelledError as e:
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        cancelled_msg = str(e)
        result = RunResult(
            run_id=run_id,
            run_name=config.run_name,
            status=RunStatus.CANCELLED,
            error_message=cancelled_msg,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            config=config,
        )

        if write_artifacts and run_dir:
            results_path = write_results_artifact(result, run_dir)

            config_path = run_dir / 'config.json'
            manifest = RunManifest(
                run_id=run_id,
                run_name=config.run_name,
                created_at=started_at,
                completed_at=completed_at,
                pvt_simulator_version=__version__,
                config_sha256=compute_file_sha256(config_path) if config_path.exists() else None,
                results_sha256=compute_file_sha256(results_path) if results_path.exists() else None,
                status=RunStatus.CANCELLED,
                error_message=cancelled_msg,
            )
            write_manifest_artifact(manifest, run_dir)

        if callback:
            callback.on_cancelled(run_id)

        return result

    except Exception as e:
        completed_at = datetime.now()
        duration = (completed_at - started_at).total_seconds()

        error_msg = str(e)
        result = RunResult(
            run_id=run_id,
            run_name=config.run_name,
            status=RunStatus.FAILED,
            error_message=error_msg,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            config=config,
        )

        # Write failure artifacts
        if write_artifacts and run_dir:
            write_results_artifact(result, run_dir)

            config_path = run_dir / 'config.json'
            manifest = RunManifest(
                run_id=run_id,
                run_name=config.run_name,
                created_at=started_at,
                completed_at=completed_at,
                pvt_simulator_version=__version__,
                config_sha256=compute_file_sha256(config_path) if config_path.exists() else None,
                status=RunStatus.FAILED,
                error_message=error_msg,
            )
            write_manifest_artifact(manifest, run_dir)

        if callback:
            callback.on_failed(run_id, error_msg)

        return result


# ==============================================================================
# Run History Management
# ==============================================================================

def list_runs(base_dir: Optional[Path] = None, limit: int = 100) -> List[Dict]:
    """List recent runs from the run history.

    Args:
        base_dir: Base directory for runs (default: get_default_runs_directory())
        limit: Maximum number of runs to return

    Returns:
        List of run summaries (dicts with run_id, status, timestamp, etc.)
    """
    if base_dir is None:
        base_dir = get_default_runs_directory()

    runs = []
    if not base_dir.exists():
        return runs

    # Get all run directories, sorted by name (which includes timestamp)
    run_dirs = sorted(base_dir.iterdir(), reverse=True)

    for run_dir in run_dirs[:limit]:
        if not run_dir.is_dir():
            continue

        manifest_path = run_dir / 'manifest.json'
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            runs.append({
                'run_id': manifest.get('run_id'),
                'run_name': manifest.get('run_name'),
                'status': manifest.get('status'),
                'created_at': manifest.get('created_at'),
                'completed_at': manifest.get('completed_at'),
                'path': str(run_dir),
            })
        except (json.JSONDecodeError, KeyError):
            continue

    return runs


def load_run_result(run_dir: Path) -> Optional[RunResult]:
    """Load a RunResult from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        RunResult if found and valid, None otherwise
    """
    results_path = run_dir / 'results.json'
    if not results_path.exists():
        return None

    try:
        with open(results_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return RunResult.model_validate(data)
    except Exception:
        return None


def load_run_config(run_dir: Path) -> Optional[RunConfig]:
    """Load a persisted RunConfig from a run directory.

    Args:
        run_dir: Path to run directory

    Returns:
        RunConfig if found and valid, None otherwise
    """
    config_path = run_dir / 'config.json'
    if not config_path.exists():
        return None

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return RunConfig.model_validate(data)
    except Exception:
        return None


def build_rerun_config(
    config: RunConfig,
    *,
    run_name: Optional[str] = None,
) -> RunConfig:
    """Return a replay-safe config derived from a stored run configuration.

    A rerun should preserve the computational inputs while clearing the prior
    run identity so the next execution receives a fresh run id.
    """
    updates: Dict[str, Optional[str]] = {"run_id": None}
    if run_name is not None:
        updates["run_name"] = run_name
    return config.model_copy(update=updates)


def rerun_saved_run(
    run_dir: Path,
    *,
    output_dir: Optional[Path] = None,
    callback: Optional[ProgressCallback] = None,
    write_artifacts: bool = True,
    run_name: Optional[str] = None,
) -> RunResult:
    """Replay a prior run from its persisted config artifact."""
    config = load_run_config(run_dir)
    if config is None:
        raise ValueError(f"Could not load a valid config.json from run directory: {run_dir}")

    rerun_config = build_rerun_config(config, run_name=run_name)
    return run_calculation(
        config=rerun_config,
        output_dir=output_dir,
        callback=callback,
        write_artifacts=write_artifacts,
    )
