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
    CalculationType, EOSType, PhaseEnvelopeTracingMethod,
    PTFlashResult, PhaseEnvelopeResult, PhaseEnvelopePoint,
    CCEResult, CCEStepResult,
    BubblePointResult, DewPointResult,
    DLResult, DLStepResult,
    CVDResult, CVDStepResult,
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
    from pvtcore.flash import pt_flash

    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)

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
    if callback:
        callback.on_progress(config.run_id or '', 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or '', 0.2, "Setting up EOS...")

    _component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)

    env_config = config.phase_envelope_config
    tracing_method = env_config.tracing_method

    if callback:
        if tracing_method is PhaseEnvelopeTracingMethod.FIXED_GRID:
            callback.on_progress(config.run_id or '', 0.3, "Tracing phase envelope...")
        else:
            callback.on_progress(config.run_id or '', 0.3, "Tracing phase envelope (continuation)...")

    if tracing_method is not PhaseEnvelopeTracingMethod.FIXED_GRID:
        from pvtcore.envelope import trace_envelope_continuation

        temperatures = np.linspace(
            env_config.temperature_min_k,
            env_config.temperature_max_k,
            env_config.n_points,
            dtype=float,
        ).tolist()
        envelope = trace_envelope_continuation(
            temperatures=temperatures,
            composition=z,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
            # Keep the continuation pressure scan above the coarse-grid regime
            # that can misclassify upper-branch local roots near the critical region.
            n_pressure_points=max(160, env_config.n_points * 4),
        )
        if not envelope.converged:
            raise RuntimeError(
                "Phase envelope failed: no saturation points found in the requested temperature range. "
                "Suggestions: widen the temperature range; lower temperature_min_k; verify inputs are in K/Pa; "
                "confirm composition sums to 1.0 and components are valid."
            )

        bubble_points = [
            PhaseEnvelopePoint(
                temperature_k=float(state.temperature),
                pressure_pa=float(state.pressure),
                point_type='bubble',
            )
            for state in envelope.bubble_states
        ]
        dew_points = [
            PhaseEnvelopePoint(
                temperature_k=float(state.temperature),
                pressure_pa=float(state.pressure),
                point_type='dew',
            )
            for state in envelope.dew_states
        ]

        if len(bubble_points) == 0 or len(dew_points) == 0:
            raise RuntimeError(
                "Phase envelope failed: could not trace both bubble and dew branches in the requested range. "
                "Suggestions: widen the temperature range; adjust the mixture to include both light/heavy components; "
                "verify EOS and binary interaction parameters."
            )

        critical = None
        if envelope.critical_state is not None:
            critical = PhaseEnvelopePoint(
                temperature_k=float(envelope.critical_state.temperature),
                pressure_pa=float(envelope.critical_state.pressure),
                point_type='critical',
            )

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
            continuation_switched=bool(envelope.switched),
            critical_source=envelope.critical_state.source if envelope.critical_state is not None else None,
            bubble_termination_reason=envelope.bubble_termination_reason,
            dew_termination_reason=envelope.dew_termination_reason,
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
    as_float = float(value)
    return as_float if np.isfinite(as_float) else None


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


def _load_component_inputs(config: RunConfig):
    """Load component IDs, component models, and feed composition."""
    from pvtcore.characterization import (
        BinaryInteractionOverride,
        CharacterizationConfig,
        PlusFractionSpec,
        characterize_fluid,
    )
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
        resolved_feed = [
            (canonical_id, z)
            for raw_id, canonical_id, z in zip(raw_component_ids, component_ids, mole_fractions)
            if raw_id not in inline_components
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
        characterized = characterize_fluid(
            resolved_feed,
            plus_fraction=PlusFractionSpec(
                z_plus=plus_fraction.z_plus,
                mw_plus=plus_fraction.mw_plus_g_per_mol,
                sg_plus=plus_fraction.sg_plus_60f,
                label=plus_fraction.label,
                n_start=plus_fraction.cut_start,
            ),
            config=CharacterizationConfig(
                n_end=plus_fraction.max_carbon_number,
                split_mw_model=plus_fraction.split_mw_model,
                kij_default=0.0,
                kij_overrides=override_entries,
                lumping_enabled=plus_fraction.lumping_enabled,
                lumping_n_groups=plus_fraction.lumping_n_groups,
            ),
        )
        return (
            characterized.component_ids,
            characterized.components,
            np.asarray(characterized.composition, dtype=np.float64),
            np.asarray(characterized.binary_interaction, dtype=np.float64),
        )

    components = [
        _build_inline_component(inline_components[cid]) if cid in inline_components else all_components[cid]
        for cid in component_ids
    ]
    z = np.array(mole_fractions, dtype=np.float64)
    return component_ids, components, z, None


def _build_runtime_eos(config: RunConfig, components):
    """Build the runtime EOS instance declared by the run config."""
    from pvtcore.eos import PengRobinsonEOS

    if config.eos_type == EOSType.PENG_ROBINSON:
        return PengRobinsonEOS(components)

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


def _prepare_fluid_inputs(config: RunConfig):
    """Build component IDs, objects, composition, EOS, and optional BIP matrix."""
    component_ids, components, z, precomputed_binary_interaction = _load_component_inputs(config)
    eos = _build_runtime_eos(config, components)
    binary_interaction = (
        precomputed_binary_interaction
        if precomputed_binary_interaction is not None
        else _build_binary_interaction_matrix(component_ids, components, config)
    )
    return component_ids, components, z, eos, binary_interaction


def validate_runtime_config(config: RunConfig) -> None:
    """Validate runtime prerequisites without executing a calculation."""
    config = _resolve_config_characterization(config)
    _prepare_fluid_inputs(config)


def execute_cce(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> CCEResult:
    """Execute a CCE calculation."""
    from pvtcore.experiments.cce import simulate_cce

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    if callback:
        callback.on_progress(config.run_id or "", 0.2, "Setting up EOS...")

    _component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)

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

    steps = [
        CCEStepResult(
            pressure_pa=float(step.pressure),
            relative_volume=float(step.relative_volume),
            liquid_fraction=_finite_or_none(step.liquid_volume_fraction),
            vapor_fraction=_finite_or_none(step.vapor_fraction),
            z_factor=_finite_or_none(step.compressibility_Z),
        )
        for step in result.steps
    ]

    return CCEResult(
        temperature_k=float(result.temperature),
        saturation_pressure_pa=_finite_or_none(result.saturation_pressure),
        steps=steps,
    )


def execute_bubble_point(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> BubblePointResult:
    """Execute a bubble-point pressure calculation."""
    from pvtcore.flash import calculate_bubble_point

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)

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
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_dew_point(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> DewPointResult:
    """Execute a dew-point pressure calculation."""
    from pvtcore.flash import calculate_dew_point

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)

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
    )

    if callback:
        callback.on_progress(config.run_id or "", 0.9, "Processing results...")

    diagnostics = _build_solver_diagnostics(result)
    certificate = _build_solver_certificate(result)

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
        diagnostics=diagnostics,
        certificate=certificate,
    )


def execute_dl(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> DLResult:
    """Execute a Differential Liberation calculation."""
    from pvtcore.experiments import simulate_dl

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)
    _ = component_ids  # component IDs not needed in DL schema output

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

    return DLResult(
        temperature_k=float(result.temperature),
        bubble_pressure_pa=float(result.bubble_pressure),
        rsi=float(result.Rsi),
        boi=float(result.Boi),
        converged=bool(result.converged),
        steps=[
            DLStepResult(
                pressure_pa=float(step.pressure),
                rs=float(step.Rs),
                bo=float(step.Bo),
                bt=float(step.Bt),
                vapor_fraction=float(step.vapor_fraction),
                liquid_moles_remaining=_finite_or_none(step.liquid_moles_remaining),
            )
            for step in result.steps
        ],
    )


def execute_cvd(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> CVDResult:
    """Execute a Constant Volume Depletion calculation."""
    from pvtcore.experiments import simulate_cvd

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)
    _ = component_ids  # component IDs not needed in CVD schema output

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

    return CVDResult(
        temperature_k=float(result.temperature),
        dew_pressure_pa=float(result.dew_pressure),
        initial_z=float(result.initial_Z),
        converged=bool(result.converged),
        steps=[
            CVDStepResult(
                pressure_pa=float(step.pressure),
                liquid_dropout=float(step.liquid_dropout),
                cumulative_gas_produced=float(step.cumulative_gas_produced),
                moles_remaining=_finite_or_none(step.moles_remaining),
                z_two_phase=_finite_or_none(step.Z_two_phase),
            )
            for step in result.steps
        ],
    )


def execute_separator(
    config: RunConfig,
    callback: Optional[ProgressCallback] = None,
) -> SeparatorResult:
    """Execute a multi-stage separator-train calculation."""
    from pvtcore.experiments import SeparatorConditions, calculate_separator_train

    if callback:
        callback.on_progress(config.run_id or "", 0.1, "Loading components...")

    component_ids, components, z, eos, binary_interaction = _prepare_fluid_inputs(config)
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
        bubble_point_result = None
        dew_point_result = None
        phase_envelope_result = None
        cce_result = None
        dl_result = None
        cvd_result = None
        separator_result = None

        if config.calculation_type == CalculationType.PT_FLASH:
            pt_flash_result = execute_pt_flash(config, callback)

        elif config.calculation_type == CalculationType.BUBBLE_POINT:
            bubble_point_result = execute_bubble_point(config, callback)

        elif config.calculation_type == CalculationType.DEW_POINT:
            dew_point_result = execute_dew_point(config, callback)

        elif config.calculation_type == CalculationType.PHASE_ENVELOPE:
            phase_envelope_result = execute_phase_envelope(config, callback)

        elif config.calculation_type == CalculationType.CCE:
            cce_result = execute_cce(config, callback)

        elif config.calculation_type == CalculationType.DL:
            dl_result = execute_dl(config, callback)

        elif config.calculation_type == CalculationType.CVD:
            cvd_result = execute_cvd(config, callback)

        elif config.calculation_type == CalculationType.SEPARATOR:
            separator_result = execute_separator(config, callback)

        else:
            raise ValueError(f"Unsupported calculation type: {config.calculation_type}")

        _raise_if_cancelled(callback)

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
            bubble_point_result=bubble_point_result,
            dew_point_result=dew_point_result,
            phase_envelope_result=phase_envelope_result,
            cce_result=cce_result,
            dl_result=dl_result,
            cvd_result=cvd_result,
            separator_result=separator_result,
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
    """Load a RunConfig from a run directory.

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


def build_rerun_config(config: RunConfig, run_name: Optional[str] = None) -> RunConfig:
    """Return a replay-safe copy of a saved run configuration.

    The rerun keeps the original calculation inputs but clears the old run ID so the
    next execution gets a fresh artifact identity.
    """
    updates: Dict[str, Optional[str]] = {"run_id": None}
    if run_name is not None:
        updates["run_name"] = run_name
    return config.model_copy(update=updates)


def rerun_saved_run(
    run_dir: Path,
    output_dir: Optional[Path] = None,
    callback: Optional[ProgressCallback] = None,
    write_artifacts: bool = True,
    run_name: Optional[str] = None,
) -> RunResult:
    """Reload a saved config.json and execute it again through the normal job runner."""
    config = load_run_config(run_dir)
    if config is None:
        raise ValueError(f"No valid config.json found in saved run: {run_dir}")

    rerun_config = build_rerun_config(config, run_name=run_name)
    return run_calculation(
        config=rerun_config,
        output_dir=output_dir,
        callback=callback,
        write_artifacts=write_artifacts,
    )
