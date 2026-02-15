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
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import numpy as np

from pvtapp.schemas import (
    RunConfig, RunResult, RunManifest, RunStatus,
    CalculationType, EOSType,
    PTFlashResult, PhaseEnvelopeResult, PhaseEnvelopePoint,
    CCEResult, CCEStepResult,
    SolverDiagnostics, IterationRecord, ConvergenceStatusEnum,
    InvariantCheck, SolverCertificate,
)
from pvtapp import __version__


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


def _build_solver_diagnostics(flash_result) -> SolverDiagnostics:
    """Build SolverDiagnostics from flash result."""
    history_records = []
    if flash_result.history is not None:
        for i, residual in enumerate(flash_result.history.residuals):
            record = IterationRecord(
                iteration=i + 1,
                residual=residual,
                step_norm=flash_result.history.step_norms[i] if i < len(flash_result.history.step_norms) else None,
                damping=flash_result.history.damping_factors[i] if i < len(flash_result.history.damping_factors) else None,
                accepted=flash_result.history.accepted[i] if i < len(flash_result.history.accepted) else True,
                timing_ms=flash_result.history.timings_ms[i] if i < len(flash_result.history.timings_ms) else None,
            )
            history_records.append(record)

    return SolverDiagnostics(
        status=_convert_convergence_status(flash_result.status),
        iterations=flash_result.iterations,
        final_residual=flash_result.residual,
        initial_residual=flash_result.history.initial_residual if flash_result.history else None,
        n_func_evals=flash_result.history.n_func_evals if flash_result.history else 0,
        n_jac_evals=flash_result.history.n_jac_evals if flash_result.history else 0,
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


def execute_pt_flash(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
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
    from pvtcore.models import load_components, Component
    from pvtcore.eos import PengRobinsonEOS
    from pvtcore.flash import pt_flash

    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    # Load component database
    all_components = load_components()

    # Build component list and composition array
    component_ids = [entry.component_id for entry in config.composition.components]
    mole_fractions = [entry.mole_fraction for entry in config.composition.components]

    # Validate all components exist
    missing = [cid for cid in component_ids if cid not in all_components]
    if missing:
        raise ValueError(
            f"Unknown component(s): {missing}. "
            f"Available: {sorted(all_components.keys())}"
        )

    components = [all_components[cid] for cid in component_ids]
    z = np.array(mole_fractions, dtype=np.float64)

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    # Create EOS instance
    eos = PengRobinsonEOS(components)

    # Build binary interaction matrix if provided
    binary_interaction = None
    if config.binary_interaction:
        n = len(components)
        binary_interaction = np.zeros((n, n))
        for pair_key, kij in config.binary_interaction.items():
            parts = pair_key.split('-')
            if len(parts) != 2:
                raise ValueError(f"Invalid BIP pair key: {pair_key}. Expected 'comp1-comp2'")
            try:
                i = component_ids.index(parts[0])
                j = component_ids.index(parts[1])
                binary_interaction[i, j] = kij
                binary_interaction[j, i] = kij
            except ValueError:
                raise ValueError(f"BIP pair key contains unknown component: {pair_key}")

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

    return PTFlashResult(
        converged=result.converged,
        phase=result.phase,
        vapor_fraction=float(result.vapor_fraction),
        liquid_composition=liquid_comp,
        vapor_composition=vapor_comp,
        K_values=k_values,
        liquid_fugacity=liquid_fug,
        vapor_fugacity=vapor_fug,
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_phase_envelope(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> PhaseEnvelopeResult:
    """Execute a phase envelope calculation.

    Args:
        config: Run configuration (must have phase_envelope_config set)
        callback: Optional progress callback

    Returns:
        PhaseEnvelopeResult with envelope points

    Raises:
        ValueError: If configuration is invalid
        RuntimeError: If pvtcore raises an error
    """
    from pvtcore.models import load_components
    from pvtcore.eos import PengRobinsonEOS
    from pvtcore.envelope import trace_phase_envelope

    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    # Load components
    all_components = load_components()
    component_ids = [entry.component_id for entry in config.composition.components]
    mole_fractions = [entry.mole_fraction for entry in config.composition.components]

    missing = [cid for cid in component_ids if cid not in all_components]
    if missing:
        raise ValueError(f"Unknown component(s): {missing}")

    components = [all_components[cid] for cid in component_ids]
    z = np.array(mole_fractions, dtype=np.float64)

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    eos = PengRobinsonEOS(components)

    if callback:
        callback.on_progress(config.run_id or '', 0.3, "Tracing phase envelope...")

    env_config = config.phase_envelope_config
    envelope = trace_phase_envelope(
        composition=z,
        components=components,
        eos=eos,
        T_min=env_config.temperature_min_k,
        T_max=env_config.temperature_max_k,
        n_points=env_config.n_points,
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
        # Execute based on calculation type
        pt_flash_result = None
        phase_envelope_result = None
        cce_result = None

        if config.calculation_type == CalculationType.PT_FLASH:
            pt_flash_result = execute_pt_flash(config, callback)

        elif config.calculation_type == CalculationType.PHASE_ENVELOPE:
            phase_envelope_result = execute_phase_envelope(config, callback)

        elif config.calculation_type == CalculationType.CCE:
            # TODO: Implement CCE execution
            raise NotImplementedError("CCE calculation not yet implemented")

        else:
            raise ValueError(f"Unsupported calculation type: {config.calculation_type}")

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
            phase_envelope_result=phase_envelope_result,
            cce_result=cce_result,
        )

        # Write artifacts
        if write_artifacts and run_dir:
            results_path = write_results_artifact(result, run_dir)

            # Write solver stats if available
            if pt_flash_result and pt_flash_result.diagnostics:
                write_solver_stats_artifact(pt_flash_result.diagnostics, run_dir)

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
