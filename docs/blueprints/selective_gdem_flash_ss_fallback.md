# Blueprint: Selective GDEM Acceleration in Flash SS Fallback

## Status: proposed

## Problem

`pt_flash()` (and by extension `bubble_point`, `dew_point`) use a two-tier
solver:

1. **Primary path** — `_newton_flash_loop` runs Michelsen's Newton-on-fugacity
   (with a 3-iteration SS warmup, then full Newton via
   `newton_pt_flash`). Typical cost: 5–15 iterations, quadratic convergence.
2. **Fallback** — if Newton returns `None` (converged=False or raised an
   exception), `_ss_flash_loop` runs pure successive substitution in
   K-space. Typical cost: 50–200 iterations, linear convergence with
   dominant eigenvalue of the SS operator `λ ∈ (0, 1)`.

The fallback is **unaccelerated**. When Newton fails, we pay the full SS
price regardless of why Newton failed. Two sub-cases matter:

- **Pathological failure** — near critical points, across phase boundaries,
  or when the SS operator itself is non-contractive (`λ → 1`). In this regime
  SS converges slowly *and* acceleration tricks like GDEM are unreliable:
  GDEM's eigenvalue estimate breaks down when the iteration is not
  contractive, and extrapolation overshoots. The current "just run pure SS
  to convergence" behavior is correct here — slow but safe.
- **Non-pathological failure** — Newton failed for reasons unrelated to
  numerical pathology (poor Wilson initial K-values in unusual mixtures,
  transient Jacobian condition number spikes, single iteration that hit
  a bad `β` from Rachford-Rice and triggered a `PhaseError`). In this
  regime SS converges normally (contractive, `λ < 0.9`) and GDEM
  acceleration would cut iteration count by roughly 3–5× (Michelsen
  1982). The current "pure SS" path leaves this speedup on the table.

Empirically the SS fallback rarely fires for the demo-priority calc types
(PT flash, bubble point, DL, CCE) on well-characterized fluids. But it
does fire for validation runs on hard fluids (near-critical condensates,
CO2-rich mixtures, TBP-characterized heavy oils with aggressive
lumping), and for any case where Wilson seeding is a poor initial guess.

## Goal

Make the SS fallback **classify** the reason Newton failed and route to
either:

- **Pure SS** (current behavior) when Newton failed from numerical
  pathology → GDEM would be unreliable here too.
- **GDEM-accelerated SS** (new path) when Newton failed for non-pathological
  reasons → plain SS converges, GDEM speeds it up 3–5×.

No change to the public `pt_flash()` / `bubble_point()` / `dew_point()`
API or return contract. The result is at worst no slower than today
(pure SS still runs for the hard cases), and in the non-pathological
sub-case roughly 3–5× faster.

## Background: how to distinguish Newton failure modes

Newton's iteration history carries enough signal to classify the
failure with high confidence. The four things to inspect:

1. **Exception type**, if any:
   - `np.linalg.LinAlgError` → Jacobian is singular (near-critical or
     degenerate phase split). Pathological.
   - `PhaseError` from the EOS root-finder (two real roots too close,
     compressibility negative) → ill-conditioned EOS region. Pathological.
   - `ConvergenceError` (Newton ran to max_iter without converging) →
     examine residual history.
2. **Residual history monotonicity**:
   - Monotonically decreasing residual that just didn't hit the
     tolerance threshold → healthy iteration, Newton is slow because the
     initial guess is far from the solution. **Non-pathological**.
   - Non-monotonic residual (bouncing up and down) → iteration is
     unstable, likely in a non-contractive region or crossing a phase
     boundary mid-solve. **Pathological**.
3. **Vapor-fraction trajectory**:
   - `β` converging smoothly toward a value in `(0, 1)` → two-phase
     region, healthy.
   - `β` oscillating near 0 or 1 with alternating sign on updates →
     near a phase boundary, the solver is toggling between single-phase
     and two-phase reads. **Pathological**.
4. **Jacobian condition number** (optional, more expensive to compute):
   - `cond(J) < 10⁶` → well-conditioned, probably just a poor initial
     guess.
   - `cond(J) > 10⁹` → near-critical, pathological.

The first two signals (exception type + residual monotonicity) are
cheap to expose — Newton's inner loop already has them — and together
classify ~95% of failures correctly. The vapor-fraction and condition
number checks are refinements worth adding only if empirical testing
shows the simple classifier misrouting cases.

## Background: what GDEM does inside SS

The General Dominant Eigenvalue Method (Michelsen 1982, *SPE J.*
22:617–630) accelerates successive substitution by estimating the
dominant eigenvalue of the SS fixed-point operator `T` from the last
three iterates `x_{n-2}, x_{n-1}, x_n`:

```
λ_est = ‖x_n − x_{n-1}‖ / ‖x_{n-1} − x_{n-2}‖
```

If `λ_est ∈ (λ_trigger, 1)` (i.e. the iteration is slowly contractive,
typically `λ_trigger = 0.9`), GDEM proposes the extrapolated step:

```
x_accel = x_{n-1} + (x_n − x_{n-1}) / (1 − λ_est)
```

This is a geometric-series acceleration assuming SS behaves locally
like `x_{n+1} = λ · x_n + c`. When the assumption holds, GDEM gets
quadratic-like speedup; when it doesn't (non-contractive or non-linear
operator), the extrapolation can overshoot badly.

The standard safety net is **backup-and-reject**:

1. Save the non-accelerated next iterate `x_n+1` as a backup.
2. Propose the GDEM step.
3. Compute the objective (in flash: `Σ(ln K_new - ln K_old)²`,
   or equivalently the fugacity-equality residual, or the mixture
   Gibbs energy).
4. If the objective did **not** decrease, reject the GDEM step and
   restore the backup.

This is exactly the pattern already used in
`src/pvtcore/stability/analysis.py` (lines 345–443) for the TPD solver.
Porting it to flash requires the same data-structures but with a
different acceptance criterion (phase-split residual descent instead
of TPD descent).

## Detailed design

### Change 1: `NewtonFailureReason` enum

New enum in `src/pvtcore/flash/newton_flash.py`:

```python
class NewtonFailureReason(Enum):
    SINGULAR_JACOBIAN = "singular_jacobian"      # np.linalg.LinAlgError
    PHASE_ERROR = "phase_error"                   # EOS root-finder blew up
    OSCILLATING_RESIDUAL = "oscillating"          # non-monotonic history
    SLOW_MONOTONIC = "slow_monotonic"             # healthy but didn't hit tol
    STUCK_AT_MAX_ITERS = "stuck"                  # residual flat for last N
    SUCCEEDED = "succeeded"                       # Newton converged
```

### Change 2: `NewtonFlashResult` extension

Add two fields to `NewtonFlashResult` (defined in `newton_flash.py`):

```python
failure_reason: NewtonFailureReason = NewtonFailureReason.SUCCEEDED
residual_history: tuple[float, ...] = ()
```

`residual_history` is the per-iteration `np.max(np.abs(residual))`
that Newton already computes. Exposing it costs nothing; it's just
returned rather than thrown away.

### Change 3: `_newton_flash_loop` returns a *reason* on failure

Currently:

```python
def _newton_flash_loop(...) -> Optional[FlashResult]:
    try:
        nr = newton_pt_flash(...)
    except (ConvergenceError, PhaseError, ValueError, np.linalg.LinAlgError):
        return None
    if not nr.converged:
        return None
    ...
```

Proposed:

```python
def _newton_flash_loop(...) -> tuple[Optional[FlashResult], NewtonFailureReason, tuple[float, ...]]:
    try:
        nr = newton_pt_flash(...)
    except np.linalg.LinAlgError:
        return None, NewtonFailureReason.SINGULAR_JACOBIAN, ()
    except PhaseError:
        return None, NewtonFailureReason.PHASE_ERROR, ()
    except (ConvergenceError, ValueError):
        return None, NewtonFailureReason.OSCILLATING_RESIDUAL, ()  # refine below

    if not nr.converged:
        reason = _classify_newton_failure(nr.residual_history)
        return None, reason, nr.residual_history
    ...
    return flash_result, NewtonFailureReason.SUCCEEDED, nr.residual_history
```

Where `_classify_newton_failure` inspects the residual history:

```python
def _classify_newton_failure(history: tuple[float, ...]) -> NewtonFailureReason:
    if len(history) < 3:
        return NewtonFailureReason.STUCK_AT_MAX_ITERS
    # Monotonicity check: count "went up" steps in the last 6.
    tail = history[-6:]
    ups = sum(1 for i in range(1, len(tail)) if tail[i] > tail[i - 1])
    if ups >= 2:
        return NewtonFailureReason.OSCILLATING_RESIDUAL
    # Stall check: last 4 residuals all within 1% of each other.
    if len(history) >= 4:
        recent = history[-4:]
        if max(recent) / min(recent) < 1.01:
            return NewtonFailureReason.STUCK_AT_MAX_ITERS
    return NewtonFailureReason.SLOW_MONOTONIC
```

### Change 4: `_ss_flash_loop` gains an `accelerate` parameter

Current signature:

```python
def _ss_flash_loop(
    pressure, temperature, composition, eos, K,
    binary_interaction, tolerance, max_iterations,
) -> Optional[FlashResult]:
```

Proposed:

```python
def _ss_flash_loop(
    pressure, temperature, composition, eos, K,
    binary_interaction, tolerance, max_iterations,
    *, accelerate: bool = False,
) -> Optional[FlashResult]:
```

When `accelerate=True`, the loop tracks the last three `ln(K)` iterates
and attempts a GDEM step whenever:

- `iteration >= gdem_start_iter` (default 6, same as stability module)
- Three monotonic SS iterates are available
- `λ_est ∈ (gdem_lambda_trigger, 1.0)` (default trigger 0.9)

Each GDEM proposal saves the non-accelerated backup, runs one SS step
from the extrapolated iterate, and accepts if the phase-split residual
`Σ(ln K_new − ln K_prev)²` decreased; otherwise rolls back to the
backup and resumes plain SS from there.

The accept criterion MUST be the phase-split residual (same thing SS
drives to zero), NOT mixture Gibbs energy. Gibbs is a better physical
criterion but requires recomputing compositions and fugacity
coefficients on the candidate state — roughly the cost of a full SS
iteration — which negates the speedup. The phase-split residual is
free (already computed to check convergence) and practically
equivalent as a descent test.

### Change 5: Dispatch in `pt_flash()`

Current:

```python
newton_result = _newton_flash_loop(...)
if newton_result is not None:
    return _finalize(newton_result)
# fall back
result = _ss_flash_loop(...)
```

Proposed:

```python
newton_result, failure_reason, _history = _newton_flash_loop(...)
if newton_result is not None:
    return _finalize(newton_result)

# Route fallback based on why Newton failed.
healthy_failures = {
    NewtonFailureReason.SLOW_MONOTONIC,
}
accelerate = failure_reason in healthy_failures
result = _ss_flash_loop(
    pressure, temperature, composition, eos, K,
    binary_interaction, tolerance, max_iterations,
    accelerate=accelerate,
)
return _finalize(result)
```

`OSCILLATING_RESIDUAL`, `SINGULAR_JACOBIAN`, `PHASE_ERROR`, and
`STUCK_AT_MAX_ITERS` all route to pure SS (the conservative default).
Only `SLOW_MONOTONIC` opts into GDEM.

### Change 6: Parallel treatment for bubble / dew point

`bubble_point.py` and `dew_point.py` use the same Newton-primary +
SS-fallback structure. Applying the same classification + dispatch
there is mechanical: same `NewtonFailureReason` enum, same
`_classify_newton_failure`, same `accelerate` kwarg on the SS
fallback. Scope multiplier ~1.2× (saturation-point solver has one
extra unknown beyond flash K's, but the convergence story is
identical).

## Testing plan

Three test layers:

1. **Unit tests** (`tests/unit/test_flash.py`, `tests/unit/test_newton_flash.py`):
   - A synthetic well-behaved fluid where Newton succeeds → check
     `failure_reason == SUCCEEDED` and the new path is byte-for-byte
     identical to the current behavior.
   - A synthetic fluid where Newton fails with slow-monotonic descent
     → mock or hand-craft a case that forces Newton past max_iter
     while the residual is still decreasing monotonically. Assert
     the SS fallback runs with `accelerate=True` and converges in
     fewer iterations than `accelerate=False`.
   - A synthetic near-critical fluid where Newton hits `LinAlgError`
     → assert SS fallback runs with `accelerate=False`.

2. **Classification tests** (`tests/unit/test_newton_failure_classifier.py`, new):
   - Monotonic history `[10, 5, 2, 1, 0.5, 0.1]` (decreasing but didn't
     hit tol) → `SLOW_MONOTONIC`.
   - Oscillating history `[1, 5, 1, 5, 1]` → `OSCILLATING_RESIDUAL`.
   - Stuck history `[0.1, 0.099, 0.1, 0.1]` → `STUCK_AT_MAX_ITERS`.
   - Short history `[5]` → `STUCK_AT_MAX_ITERS` (conservative).

3. **Performance regression** (`tests/performance/test_ss_fallback_speedup.py`, new):
   - Fluid from the `mi_pvt_phase_envelope_roster.md` validation set
     where Newton is known to fail cleanly. Compare iteration counts
     for `accelerate=False` vs `accelerate=True`. Target: ≥2× speedup
     without loss of accuracy vs a reference pure-SS run to tight
     tolerance.

## Risk analysis

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Classifier mis-routes a pathological case to GDEM | Medium | GDEM overshoots, SS accepts a worse iterate | Backup-and-reject guard inside SS already catches this; worst case is +1 wasted iteration per misroute |
| `residual_history` exposure breaks downstream callers of `NewtonFlashResult` | Low | Test failures | New fields default to empty — existing callers unaffected |
| GDEM inside flash uses a different accept criterion than stability and the copy-paste introduces a subtle bug | Medium | Silent wrong answers in the accelerated path | Write the flash GDEM as a new function, NOT a copy of the stability one; unit-test independently |
| Bubble/dew implementation drifts from flash | Medium | Inconsistent acceleration behavior across calc types | Ship all three in the same PR; share `_classify_newton_failure` via a common module |
| Performance test is flaky because SS iteration counts depend on floating-point noise | Low | CI churn | Test asserts a ratio (`ss_pure_iters / ss_accel_iters >= 2.0`), not absolute counts |

## Non-goals

- **Do NOT** add GDEM to the Newton primary path itself — Newton is
  already quadratic and GDEM has nothing to offer there.
- **Do NOT** change the stability-analysis GDEM implementation — it
  works, it's tested, and its accept criterion (TPD descent) is
  different from the flash one.
- **Do NOT** expose the accelerate toggle to the GUI — it's a solver
  internal, auto-routed by failure classification.

## Milestone ordering

Recommended slice-by-slice:

1. **M1 — Classifier + residual-history exposure** (no behavior change).
   - Add `NewtonFailureReason` enum and `_classify_newton_failure`.
   - Expose `residual_history` on `NewtonFlashResult`.
   - Change `_newton_flash_loop` to return the tuple; update `pt_flash`
     caller to destructure but still dispatch to pure SS.
   - Ship with classification unit tests. No accelerated path yet.
2. **M2 — GDEM-accelerated `_ss_flash_loop` (opt-in, default off)**.
   - Implement the accelerate path with backup-and-reject.
   - Unit-test on a hand-crafted slow-monotonic case.
   - Still not wired to the dispatch; caller always passes
     `accelerate=False`.
3. **M3 — Dispatch wire-up**.
   - Flip the dispatch in `pt_flash` to route `SLOW_MONOTONIC` failures
     to `accelerate=True`.
   - Run the performance regression test.
4. **M4 — Replicate for bubble_point / dew_point**.
   - Same classifier, same acceleration, same dispatch.
5. **M5 — Post-ship audit**.
   - Run the full validation suite; confirm no regressions on the
     fluids known to stress the SS fallback.
   - Graph iteration-count distributions before/after.

Each milestone is independently mergeable; M1 alone is a net-positive
change (better diagnostics) even if M2+ never land.

## References

- Michelsen, M.L. (1982) *The isothermal flash problem. Part II. Phase-split
  calculation.* SPE Journal 22: 617–630.
- Michelsen, M.L. & Mollerup, J. (2007) *Thermodynamic Models:
  Fundamentals and Computational Aspects*, Ch. 10 (Flash calculations),
  §10.4 (General Dominant Eigenvalue Method).
- Existing implementation: `src/pvtcore/stability/analysis.py` lines
  345–443 (GDEM in the log-space TPD solver — pattern to adapt, not
  copy verbatim).
