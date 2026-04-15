"""Michelsen TPD stability analysis (new API).

This module provides an *additive* stability-analysis interface built around
Michelsen-style tangent plane distance (TPD) minimization using successive
substitution in log-space, with optional GDEM acceleration.

It is designed to coexist with the legacy API in `pvtcore.stability.michelsen`
without changing any existing behavior.

Notes
-----
- The mixture is considered *unstable* if any trial produces TPD < 0 (within
  tolerance).
- The default trial set includes both vapor-like and liquid-like initializations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import CharacterizationError, ValidationError
from ..eos.base import CubicEOS
from .wilson import wilson_k_values


def _logsumexp(x: NDArray[np.float64]) -> float:
    m = float(np.max(x))
    return m + float(np.log(np.sum(np.exp(x - m))))


def _normalize_logw(logw: NDArray[np.float64]) -> NDArray[np.float64]:
    """Return normalized log(w) such that sum(w)=1."""
    return logw - _logsumexp(logw)


def _safe_log(x: NDArray[np.float64], eps: float) -> NDArray[np.float64]:
    return np.log(np.maximum(x, eps))


def _phase_gibbs_proxy(z: NDArray[np.float64], ln_phi: NDArray[np.float64]) -> float:
    """Cheap proxy used to pick a feed reference phase when `feed_phase='auto'`."""
    return float(np.sum(z * ln_phi))


def _select_feed_phase_auto(
    z: NDArray[np.float64],
    pressure: float,
    temperature: float,
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    *,
    tie_break_tol: float = 0.01,
) -> str:
    """Select 'liquid' or 'vapor' reference phase for feed based on a Gibbs proxy.

    Returns a label that preserves the fact that the phase was auto-selected.
    """
    ln_phi_l: NDArray[np.float64] | None = None
    ln_phi_v: NDArray[np.float64] | None = None

    try:
        phi_l = eos.fugacity_coefficient(pressure, temperature, z, "liquid", binary_interaction)
        ln_phi_l = np.log(phi_l)
    except Exception:
        ln_phi_l = None

    try:
        phi_v = eos.fugacity_coefficient(pressure, temperature, z, "vapor", binary_interaction)
        ln_phi_v = np.log(phi_v)
    except Exception:
        ln_phi_v = None

    if ln_phi_l is None and ln_phi_v is None:
        raise ValidationError(
            "EOS failed to evaluate feed fugacity coefficients in both liquid and vapor roots.",
            parameter="feed_phase",
            value="auto",
        )

    if ln_phi_l is None:
        return "auto_selected:vapor"
    if ln_phi_v is None:
        return "auto_selected:liquid"

    g_l = _phase_gibbs_proxy(z, ln_phi_l)
    g_v = _phase_gibbs_proxy(z, ln_phi_v)

    # Near-tie: use a reduced-pressure heuristic for determinism.
    if abs(g_l - g_v) < tie_break_tol:
        Pc_avg = float(np.sum(z * np.array([c.Pc for c in eos.components], dtype=float)))
        P_reduced = pressure / Pc_avg if Pc_avg > 0.0 else 1.0
        return "auto_selected:liquid" if P_reduced > 2.0 else "auto_selected:vapor"

    return "auto_selected:liquid" if g_l < g_v else "auto_selected:vapor"


def _feed_phase_label_to_phase(feed_phase: str) -> Literal["liquid", "vapor"]:
    if feed_phase == "liquid":
        return "liquid"
    if feed_phase == "vapor":
        return "vapor"
    if feed_phase == "auto_selected:liquid":
        return "liquid"
    if feed_phase == "auto_selected:vapor":
        return "vapor"
    raise ValidationError("Invalid feed_phase.", parameter="feed_phase", value=feed_phase)


@dataclass(frozen=True)
class StabilityOptions:
    """Configuration for the log-space successive-substitution stability driver."""

    tol_ln_w: float = 1e-10
    tpd_negative_tol: float = 1e-8
    max_iter: int = 200
    epsilon: float = 1e-300

    # Damping (relaxation) for fixed-point iteration in log-space.
    damping_initial: float = 1.0
    damping_min: float = 0.2
    damping_shrink: float = 0.5

    # Optional GDEM acceleration.
    use_gdem: bool = True
    gdem_start_iter: int = 6
    gdem_lambda_trigger: float = 0.9
    gdem_accept: str = "tpd"  # currently only "tpd" supported

    # Optional extra seeds.
    n_random_trials: int = 0
    random_seed: int | None = 0
    warm_start: dict[str, list[NDArray[np.float64]]] | None = None

    # Robustness: tolerate limited EOS evaluation failures and attempt recovery.
    max_eos_failures_per_trial: int = 5


@dataclass(frozen=True)
class StabilitySeedResult:
    """Result of one concrete seed attempt within a trial kind."""

    kind: str
    trial_phase: str
    seed_index: int
    seed_label: str
    initial_w: NDArray[np.float64]
    w: NDArray[np.float64]
    tpd: float
    iterations: int
    converged: bool
    early_exit_unstable: bool
    n_phi_calls: int
    n_eos_failures: int
    message: str | None


@dataclass(frozen=True)
class StabilityTrialResult:
    """Aggregated result of a trial kind over one or more concrete seeds."""

    kind: str
    trial_phase: str
    w: NDArray[np.float64]
    tpd: float
    iterations: int
    converged: bool
    early_exit_unstable: bool
    n_phi_calls: int
    n_eos_failures: int
    message: str | None
    best_seed_index: int
    candidate_seed_labels: tuple[str, ...]
    seed_results: tuple[StabilitySeedResult, ...]

    @property
    def best_seed(self) -> StabilitySeedResult:
        return self.seed_results[self.best_seed_index]

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
    def unattempted_seed_labels(self) -> tuple[str, ...]:
        return self.candidate_seed_labels[self.seed_attempts :]

    @property
    def total_iterations(self) -> int:
        return int(sum(seed.iterations for seed in self.seed_results))

    @property
    def diagnostic_messages(self) -> tuple[str, ...]:
        return tuple(
            f"{seed.seed_label}: {seed.message}"
            for seed in self.seed_results
            if seed.message is not None
        )


@dataclass(frozen=True)
class StabilityAnalysisResult:
    """Overall stability analysis result."""

    stable: bool
    tpd_min: float
    feed_phase: str
    trials: list[StabilityTrialResult]
    best_unstable_trial: StabilityTrialResult | None
    vapor_like: StabilityTrialResult | None
    liquid_like: StabilityTrialResult | None


@dataclass(frozen=True)
class _StabilitySeedSpec:
    label: str
    w0: NDArray[np.float64]


def _build_seed_specs(
    *,
    kind: str,
    z: NDArray[np.float64],
    K_wilson: NDArray[np.float64],
    options: StabilityOptions,
) -> list[_StabilitySeedSpec]:
    eps = options.epsilon
    specs: list[_StabilitySeedSpec] = []

    if kind == "vapor_like":
        w0 = np.maximum(z, eps) * np.maximum(K_wilson, eps)
        w0 = w0 / float(np.sum(w0))
        specs.append(_StabilitySeedSpec(label="wilson", w0=w0))

        # Extreme seed: pure lightest component by Wilson K.
        j = int(np.argmax(K_wilson))
        e = np.zeros_like(z)
        e[j] = 1.0
        specs.append(_StabilitySeedSpec(label="extreme_lightest", w0=e))

    elif kind == "liquid_like":
        w0 = np.maximum(z, eps) / np.maximum(K_wilson, eps)
        w0 = w0 / float(np.sum(w0))
        specs.append(_StabilitySeedSpec(label="wilson", w0=w0))

        # Extreme seed: pure heaviest component by Wilson K.
        j = int(np.argmin(K_wilson))
        e = np.zeros_like(z)
        e[j] = 1.0
        specs.append(_StabilitySeedSpec(label="extreme_heaviest", w0=e))

    else:
        raise ValidationError("Unknown trial kind.", parameter="trial_kind", value=kind)

    # Warm starts
    if options.warm_start is not None and kind in options.warm_start:
        for idx, w in enumerate(options.warm_start[kind], start=1):
            w = np.asarray(w, dtype=np.float64)
            if w.shape != z.shape:
                continue
            s = float(np.sum(w))
            if s <= 0.0:
                continue
            w = np.maximum(w / s, eps)
            w = w / float(np.sum(w))
            specs.append(_StabilitySeedSpec(label=f"warm_start_{idx}", w0=w))

    # Random perturbations (optional)
    if options.n_random_trials > 0:
        rng = np.random.default_rng(options.random_seed)
        sigma = 0.3
        for idx in range(1, int(options.n_random_trials) + 1):
            noise = rng.standard_normal(z.shape)
            w = np.maximum(z, eps) * np.exp(sigma * noise)
            w = w / float(np.sum(w))
            specs.append(_StabilitySeedSpec(label=f"random_{idx}", w0=w))

    return specs


def _build_seed_list(
    *,
    kind: str,
    z: NDArray[np.float64],
    K_wilson: NDArray[np.float64],
    options: StabilityOptions,
) -> list[NDArray[np.float64]]:
    return [
        np.asarray(spec.w0, dtype=np.float64).copy()
        for spec in _build_seed_specs(kind=kind, z=z, K_wilson=K_wilson, options=options)
    ]


def _tpd_value(
    *,
    w: NDArray[np.float64],
    logw: NDArray[np.float64],
    ln_phi_w: NDArray[np.float64],
    d_terms: NDArray[np.float64],
) -> float:
    # TPD(w) = Σ w_i [ ln w_i + ln φ_i(w) - d_i ]
    return float(np.sum(w * (logw + ln_phi_w - d_terms)))


def _run_single_seed(
    *,
    kind: str,
    trial_phase: Literal["liquid", "vapor"],
    seed_w: NDArray[np.float64],
    z: NDArray[np.float64],
    d_terms: NDArray[np.float64],
    eos: CubicEOS,
    pressure: float,
    temperature: float,
    binary_interaction: Optional[NDArray[np.float64]],
    options: StabilityOptions,
    seed_index: int = 0,
    seed_label: str = "seed",
) -> StabilitySeedResult:
    eps = options.epsilon
    initial_w = np.asarray(seed_w, dtype=np.float64).copy()
    logW = _safe_log(initial_w, eps)

    n_phi_calls = 0
    n_eos_failures = 0
    converged = False
    early_exit = False
    message: str | None = None

    alpha = float(options.damping_initial)
    if not (0.0 < alpha <= 1.0):
        alpha = 1.0

    # For GDEM: keep the last 3 normalized log(w) states (the SS sequence).
    logw_hist: list[NDArray[np.float64]] = []

    pending_gdem = False
    gdem_backup_logW: NDArray[np.float64] | None = None
    gdem_ref_tpd: float | None = None

    tpd_last = float("inf")
    w_last = initial_w.copy()
    tpd_prev: float | None = None

    for it in range(1, int(options.max_iter) + 1):
        logw = _normalize_logw(logW)
        w = np.exp(logw)
        w_last = w

        # EOS fugacity for current w
        try:
            phi = eos.fugacity_coefficient(pressure, temperature, w, trial_phase, binary_interaction)
            n_phi_calls += 1
        except Exception as e:
            # If this was a GDEM candidate step, reject immediately to backup
            if pending_gdem and gdem_backup_logW is not None:
                logW = gdem_backup_logW
                pending_gdem = False
                gdem_backup_logW = None
                gdem_ref_tpd = None
                alpha = max(options.damping_min, options.damping_shrink * alpha)
                continue

            n_eos_failures += 1
            if n_eos_failures > options.max_eos_failures_per_trial:
                message = f"EOS fugacity failed too many times: {type(e).__name__}: {e}"
                break

            # Recovery: blend toward the feed composition and dampen.
            w_blend = 0.9 * w + 0.1 * z
            w_blend = np.maximum(w_blend, eps)
            w_blend = w_blend / float(np.sum(w_blend))
            logW = _safe_log(w_blend, eps)
            alpha = max(options.damping_min, options.damping_shrink * alpha)
            continue

        ln_phi = np.log(phi)
        tpd = _tpd_value(w=w, logw=logw, ln_phi_w=ln_phi, d_terms=d_terms)

        # If we just took a GDEM candidate step, accept/reject based on TPD.
        if pending_gdem and gdem_ref_tpd is not None:
            if options.gdem_accept == "tpd" and tpd > gdem_ref_tpd:
                # Reject by reverting and retrying from backup next iteration.
                if gdem_backup_logW is not None:
                    logW = gdem_backup_logW
                pending_gdem = False
                gdem_backup_logW = None
                gdem_ref_tpd = None
                alpha = max(options.damping_min, options.damping_shrink * alpha)
                continue
            pending_gdem = False
            gdem_backup_logW = None
            gdem_ref_tpd = None

        tpd_last = float(tpd)

        # Proof of instability for this trial.
        if tpd < -options.tpd_negative_tol:
            early_exit = True
            break

        # Fixed-point update in log-space: logW_target = d - lnphi(w)
        logW_target = d_terms - ln_phi
        logW_new = (1.0 - alpha) * logW + alpha * logW_target

        logw_new = _normalize_logw(logW_new)
        max_change = float(np.max(np.abs(logw_new - logw)))

        if max_change < options.tol_ln_w:
            logW = logW_new
            converged = True
            break

        # GDEM (optional): propose extrapolated next iterate.
        if options.use_gdem and it >= options.gdem_start_iter:
            if not logw_hist:
                logw_hist.append(logw.copy())
            logw_hist.append(logw_new.copy())
            if len(logw_hist) >= 3:
                a = logw_hist[-3]
                b = logw_hist[-2]
                c = logw_hist[-1]
                d1 = b - a
                d2 = c - b
                denom = float(np.dot(d1, d2))
                if denom != 0.0:
                    lam = float(np.dot(d2, d2) / denom)
                    if 0.0 < lam < 1.0 and abs(lam) > options.gdem_lambda_trigger:
                        logw_ex = c + d2 / (1.0 - lam)
                        gdem_backup_logW = logW_new.copy()
                        gdem_ref_tpd = tpd_last
                        pending_gdem = True
                        logW = logw_ex
                        continue

            if len(logw_hist) > 4:
                logw_hist = logw_hist[-3:]

        logW = logW_new
        if tpd_prev is not None and tpd > tpd_prev:
            alpha = max(options.damping_min, options.damping_shrink * alpha)
        tpd_prev = tpd

    # If we converged (fixed-point), recompute TPD at the final iterate for accuracy.
    if converged:
        logw = _normalize_logw(logW)
        w = np.exp(logw)
        w_last = w
        try:
            phi = eos.fugacity_coefficient(pressure, temperature, w, trial_phase, binary_interaction)
            n_phi_calls += 1
            ln_phi = np.log(phi)
            tpd_last = _tpd_value(w=w, logw=logw, ln_phi_w=ln_phi, d_terms=d_terms)
        except Exception as e:
            n_eos_failures += 1
            message = message or f"EOS failed evaluating final converged iterate: {type(e).__name__}: {e}"

    return StabilitySeedResult(
        kind=kind,
        trial_phase=str(trial_phase),
        seed_index=int(seed_index),
        seed_label=str(seed_label),
        initial_w=initial_w,
        w=np.asarray(w_last, dtype=np.float64),
        tpd=float(tpd_last),
        iterations=int(it if "it" in locals() else 0),
        converged=bool(converged),
        early_exit_unstable=bool(early_exit),
        n_phi_calls=int(n_phi_calls),
        n_eos_failures=int(n_eos_failures),
        message=message,
    )


def _run_trial_kind(
    *,
    kind: Literal["vapor_like", "liquid_like"],
    z: NDArray[np.float64],
    d_terms: NDArray[np.float64],
    eos: CubicEOS,
    pressure: float,
    temperature: float,
    binary_interaction: Optional[NDArray[np.float64]],
    options: StabilityOptions,
) -> StabilityTrialResult:
    K_w = wilson_k_values(pressure, temperature, eos.components)
    seed_specs = _build_seed_specs(kind=kind, z=z, K_wilson=K_w, options=options)

    trial_phase: Literal["liquid", "vapor"] = "vapor" if kind == "vapor_like" else "liquid"

    best: StabilitySeedResult | None = None
    best_seed_index = -1
    seed_results: list[StabilitySeedResult] = []
    total_phi_calls = 0
    total_eos_failures = 0
    for idx, spec in enumerate(seed_specs):
        res = _run_single_seed(
            kind=kind,
            trial_phase=trial_phase,
            seed_w=spec.w0,
            z=z,
            d_terms=d_terms,
            eos=eos,
            pressure=float(pressure),
            temperature=float(temperature),
            binary_interaction=binary_interaction,
            options=options,
            seed_index=idx,
            seed_label=spec.label,
        )
        seed_results.append(res)
        total_phi_calls += res.n_phi_calls
        total_eos_failures += res.n_eos_failures
        if best is None or res.tpd < best.tpd:
            best = res
            best_seed_index = idx
        # Proof of instability; no need to search more seeds for this kind.
        if res.early_exit_unstable:
            best = res
            best_seed_index = idx
            break

    if best is None:
        raise CharacterizationError("No stability trial seeds were generated.")
    trial_message = best.message
    if total_eos_failures > 0:
        recovery_summary = (
            f"Recovered from {total_eos_failures} EOS evaluation failure(s) "
            f"across {len(seed_results)} seed attempt(s)."
        )
        trial_message = recovery_summary if trial_message is None else f"{recovery_summary} {trial_message}"
    elif trial_message is None and not best.converged and not best.early_exit_unstable:
        trial_message = "No seed converged within the iteration budget."

    return StabilityTrialResult(
        kind=best.kind,
        trial_phase=best.trial_phase,
        w=np.asarray(best.w, dtype=np.float64),
        tpd=float(best.tpd),
        iterations=int(best.iterations),
        converged=bool(best.converged),
        early_exit_unstable=bool(best.early_exit_unstable),
        n_phi_calls=int(total_phi_calls),
        n_eos_failures=int(total_eos_failures),
        message=trial_message,
        best_seed_index=int(best_seed_index),
        candidate_seed_labels=tuple(spec.label for spec in seed_specs),
        seed_results=tuple(seed_results),
    )


def tpd_single_trial(
    composition: NDArray[np.float64],
    pressure: float,
    temperature: float,
    eos: CubicEOS,
    *,
    feed_phase: Literal["liquid", "vapor"],
    trial_kind: Literal["vapor_like", "liquid_like"],
    binary_interaction: Optional[NDArray[np.float64]] = None,
    options: StabilityOptions | None = None,
) -> StabilityTrialResult:
    """Run a single Michelsen TPD minimization trial (vapor-like or liquid-like)."""
    z = np.asarray(composition, dtype=np.float64)
    if z.ndim != 1:
        raise ValidationError("Composition must be 1D.", parameter="composition")
    if len(z) != eos.n_components:
        raise ValidationError(
            "Composition length must match number of components in EOS",
            parameter="composition",
            value={"got": len(z), "expected": eos.n_components},
        )
    if not np.isclose(float(z.sum()), 1.0, atol=1e-6):
        raise ValidationError("Composition must sum to 1.0", parameter="composition_sum", value=float(z.sum()))
    if np.any(z < -1e-16):
        raise ValidationError("Composition must be non-negative", parameter="composition")

    if pressure <= 0.0:
        raise ValidationError("Pressure must be positive", parameter="pressure", value=pressure)
    if temperature <= 0.0:
        raise ValidationError("Temperature must be positive", parameter="temperature", value=temperature)

    opts = options or StabilityOptions()
    ref_phase = feed_phase

    phi_feed = eos.fugacity_coefficient(pressure, temperature, z, ref_phase, binary_interaction)
    ln_phi_feed = np.log(phi_feed)
    d_terms = _safe_log(z, opts.epsilon) + ln_phi_feed

    return _run_trial_kind(
        kind=trial_kind,
        z=z,
        d_terms=d_terms,
        eos=eos,
        pressure=float(pressure),
        temperature=float(temperature),
        binary_interaction=binary_interaction,
        options=opts,
    )


def stability_analyze(
    composition: NDArray[np.float64],
    pressure: float,
    temperature: float,
    eos: CubicEOS,
    *,
    feed_phase: Literal["liquid", "vapor", "auto"] = "auto",
    binary_interaction: Optional[NDArray[np.float64]] = None,
    options: StabilityOptions | None = None,
) -> StabilityAnalysisResult:
    """Perform Michelsen TPD-based stability analysis (VLE-only).

    This is an additive, higher-level API. It does not replace or modify the
    legacy Michelsen implementation.
    """
    z = np.asarray(composition, dtype=np.float64)
    if z.ndim != 1:
        raise ValidationError("Composition must be 1D.", parameter="composition")
    if len(z) != eos.n_components:
        raise ValidationError(
            "Composition length must match number of components in EOS",
            parameter="composition",
            value={"got": len(z), "expected": eos.n_components},
        )
    if not np.isclose(float(z.sum()), 1.0, atol=1e-6):
        raise ValidationError("Composition must sum to 1.0", parameter="composition_sum", value=float(z.sum()))
    if np.any(z < -1e-16):
        raise ValidationError("Composition must be non-negative", parameter="composition")

    if pressure <= 0.0:
        raise ValidationError("Pressure must be positive", parameter="pressure", value=pressure)
    if temperature <= 0.0:
        raise ValidationError("Temperature must be positive", parameter="temperature", value=temperature)

    opts = options or StabilityOptions()

    if feed_phase == "auto":
        feed_phase_label = _select_feed_phase_auto(z, pressure, temperature, eos, binary_interaction)
    else:
        feed_phase_label = str(feed_phase)

    ref_phase = _feed_phase_label_to_phase(feed_phase_label)

    phi_feed = eos.fugacity_coefficient(pressure, temperature, z, ref_phase, binary_interaction)
    ln_phi_feed = np.log(phi_feed)
    d_terms = _safe_log(z, opts.epsilon) + ln_phi_feed

    vapor_like = _run_trial_kind(
        kind="vapor_like",
        z=z,
        d_terms=d_terms,
        eos=eos,
        pressure=float(pressure),
        temperature=float(temperature),
        binary_interaction=binary_interaction,
        options=opts,
    )
    liquid_like = _run_trial_kind(
        kind="liquid_like",
        z=z,
        d_terms=d_terms,
        eos=eos,
        pressure=float(pressure),
        temperature=float(temperature),
        binary_interaction=binary_interaction,
        options=opts,
    )

    trials = [vapor_like, liquid_like]
    tpd_min = float(min(t.tpd for t in trials))
    stable = bool(tpd_min >= -opts.tpd_negative_tol)
    best_unstable = None if stable else min(trials, key=lambda t: t.tpd)

    return StabilityAnalysisResult(
        stable=stable,
        tpd_min=tpd_min,
        feed_phase=str(feed_phase_label),
        trials=trials,
        best_unstable_trial=best_unstable,
        vapor_like=vapor_like,
        liquid_like=liquid_like,
    )
