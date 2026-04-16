# Blueprint: Fast Phase Envelope Solver

## Status: proposed

## Problem

`calculate_phase_envelope` takes ~7.5 s for a 2-component PR binary that
should complete in <0.5 s. The full test suite spends ~6 of its 8.4 minutes
on phase envelope computations. The runtime `run_calculation` envelope path
(which goes through `continuation.py`) takes ~90 s per envelope.

The root cause is algorithmic: the current implementation uses TPD-based
stability boundaries with Brent root-finding, where each Brent iteration runs
a full stability analysis (200 SS iterations × 2 seeds). This produces
~10³–10⁴ fugacity evaluations per envelope point instead of ~5.

## Goal

Replace the inner solver of `calculate_phase_envelope` with a direct
Michelsen-style Newton method. Target: <0.5 s for a binary PR envelope, <5 s
for a 15-component characterized fluid. No change to the public API or
`EnvelopeResult` contract.

## Background: what an efficient envelope solver does

The standard method (Michelsen 1980, Michelsen & Mollerup 2007 Ch. 12) solves
the **saturation point equations directly** rather than searching for TPD sign
changes:

For a bubble point at temperature T, find pressure P and vapor composition y
such that:

```
f_i(P, y) = ln(K_i) + ln(φ_i^V(P, T, y)) - ln(φ_i^L(P, T, z)) = 0
             for i = 1..n_c

g(P, y)   = Σ(z_i · K_i) - 1 = 0    (Rachford-Rice at β=0)
```

This is n_c + 1 equations in n_c + 1 unknowns (P, y_1..y_nc). Newton
converges in 3-5 iterations from a warm-started initial guess (previous
envelope point). Each Newton iteration requires:

1. One φ^L evaluation (n_c values)
2. One φ^V evaluation (n_c values)
3. Jacobian: ∂ln(φ)/∂P and ∂ln(φ)/∂y (analytically available for cubic EOS)

Total: **~2 φ evaluations + 1 Jacobian per Newton iteration**, ~10-15 φ
evaluations per envelope point. Compare to current ~10³–10⁴.

For continuation along the envelope (especially near the critical point where
natural parameter continuation in T fails), use **arclength continuation**:
parametrize by arc length s instead of T, adding the normalization equation:

```
(dT/ds)² + (dP/ds)² + Σ(dln(K_i)/ds)² = 1
```

This lets the solver smoothly traverse the critical point without switching
between bubble and dew branches.

## Detailed design

### New module: `src/pvtcore/envelope/fast_envelope.py`

Keep `phase_envelope.py` as the existing robust fallback. The new module
provides `calculate_phase_envelope_fast()` with the same signature and return
type.

### Required EOS additions: `src/pvtcore/eos/base.py` + implementations

Add to `CubicEOS` base class:

```python
def ln_fugacity_coefficient(
    self, pressure, temperature, composition, phase, binary_interaction=None
) -> NDArray[np.float64]:
    """Return ln(φ_i) for all components. Default: log of fugacity_coefficient."""
    return np.log(self.fugacity_coefficient(
        pressure, temperature, composition, phase, binary_interaction
    ))

def d_ln_phi_dP(
    self, pressure, temperature, composition, phase, binary_interaction=None
) -> NDArray[np.float64]:
    """∂ln(φ_i)/∂P at constant T, x. Analytical for cubic EOS."""
    raise NotImplementedError

def d_ln_phi_dx(
    self, pressure, temperature, composition, phase, binary_interaction=None
) -> NDArray[np.float64]:
    """∂ln(φ_i)/∂x_j matrix (n_c × n_c). Analytical for cubic EOS."""
    raise NotImplementedError
```

For PR EOS, these have closed-form expressions derivable from the standard
cubic mixing rules. The key identities:

```
∂ln(φ_i)/∂P = (V̄_i - RT/P) / RT

where V̄_i is the partial molar volume from:
V̄_i = RT/(P - b_mix/V²) · (1 + b_i·P/(RT·Z) + ...)
```

The full expressions are in Michelsen & Mollerup (2007) Appendix A and
Thermodynamics and Its Applications (Tester & Modell) for cubic EOS.

### Solver structure

```
calculate_phase_envelope_fast(z, components, eos, ...)
│
├── _initialize_envelope(z, components, eos)
│   │   Wilson K-values at low T → first bubble point via Newton
│   └── returns (T₀, P₀, K₀, y₀)
│
├── _trace_branch(z, eos, T₀, P₀, K₀, branch="bubble", ...)
│   │   Natural parameter continuation in T (while dP/dT > threshold)
│   │   Switch to arclength continuation near critical
│   │   Each step: Newton solve of saturation equations
│   │   Warm-start from previous (P, K, y)
│   └── returns [(T, P, K, y, certificate), ...]
│
├── _detect_critical_region(bubble_points, dew_points)
│   │   K → 1 criterion or pressure convergence
│   └── returns (T_crit, P_crit)
│
└── returns EnvelopeResult (same structure as current)
```

### Newton solver for one saturation point

```python
def _newton_saturation_point(
    T: float,
    P_init: float,
    K_init: NDArray,
    z: NDArray,
    eos: CubicEOS,
    branch: str,  # "bubble" or "dew"
    binary_interaction=None,
    max_iter: int = 15,
    tol: float = 1e-10,
) -> Tuple[float, NDArray, NDArray]:
    """
    Solve saturation equations by Newton's method.

    Returns (P, y, K) at convergence.
    """
    P = P_init
    K = K_init.copy()
    nc = len(z)

    for iteration in range(max_iter):
        if branch == "bubble":
            y = z * K / np.sum(z * K)
            x = z
        else:  # dew
            x = z / K / np.sum(z / K)
            y = z

        ln_phi_L = eos.ln_fugacity_coefficient(P, T, x, "liquid", binary_interaction)
        ln_phi_V = eos.ln_fugacity_coefficient(P, T, y, "vapor", binary_interaction)

        # Residual: ln(K_i) + ln(φ_i^V) - ln(φ_i^L) = 0
        ln_K = np.log(K)
        F = ln_K + ln_phi_V - ln_phi_L
        # Plus summation equation
        if branch == "bubble":
            g = np.sum(z * K) - 1.0
        else:
            g = 1.0 - np.sum(z / K)

        residual = np.append(F, g)
        if np.max(np.abs(residual)) < tol:
            return P, y if branch == "bubble" else x, K

        # Build Jacobian (nc+1 × nc+1)
        # Variables: [ln(K_1), ..., ln(K_nc), ln(P)]
        d_phi_V_dx = eos.d_ln_phi_dx(P, T, y, "vapor", binary_interaction)
        d_phi_V_dP = eos.d_ln_phi_dP(P, T, y, "vapor", binary_interaction)
        d_phi_L_dP = eos.d_ln_phi_dP(P, T, x, "liquid", binary_interaction)

        J = np.zeros((nc + 1, nc + 1))
        # ∂F_i/∂ln(K_j) = δ_ij + ∂ln(φ_i^V)/∂y_j · ∂y_j/∂ln(K_j)
        # For bubble: y_j = z_j·K_j / Σ(z·K), chain rule applies
        J[:nc, :nc] = np.eye(nc) + d_phi_V_dx  # simplified; full chain rule needed
        # ∂F_i/∂ln(P) = P · (∂ln(φ_i^V)/∂P - ∂ln(φ_i^L)/∂P)
        J[:nc, nc] = P * (d_phi_V_dP - d_phi_L_dP)
        # ∂g/∂ln(K_j) and ∂g/∂ln(P)
        if branch == "bubble":
            J[nc, :nc] = z * K
        else:
            J[nc, :nc] = z / K

        delta = np.linalg.solve(J, -residual)
        ln_K += delta[:nc]
        P *= np.exp(delta[nc])
        K = np.exp(ln_K)

    raise ConvergenceError("Saturation Newton did not converge", iterations=max_iter)
```

### Arclength continuation

When |dP/dT| becomes large (near cricondenbar) or K → 1 (near critical),
switch to arclength parametrization. The extended system adds one equation:

```
Σ (Δln(K_i))² + (ΔlnP)² + (ΔT/T_scale)² = Δs²
```

The specification variable (the one "freed" to vary) is chosen as the variable
with the largest tangent component. This is standard Michelsen (1980).

### Warm-starting

The key to efficiency: each envelope point uses (P, K, y) from the previous
point as the initial guess. For well-spaced points, Newton converges in 2-3
iterations instead of the 10-15 needed from Wilson K-values.

### Certificate generation (optional, deferred)

The current code builds a `SolverCertificate` at every point (fugacity check,
sanity, Z/V). This adds ~6 EOS calls per point. Make it optional:

```python
def calculate_phase_envelope_fast(
    ...,
    compute_certificates: bool = False,  # skip by default for speed
):
```

Tests that need certificates can opt in. The default path skips them.

## Analytical derivatives for PR EOS

The derivatives ∂ln(φ_i)/∂P and ∂ln(φ_i)/∂x_j for Peng-Robinson are
well-known. Key expressions (all from the standard cubic formulation):

### ∂ln(φ_i)/∂P

From the relation V̄_i = RT · ∂ln(f_i)/∂P:

```
∂ln(φ_i)/∂P = (b_i / b_mix) · (Z - 1) / P
             - 1/P
             + a_mix/(√8 · b_mix · RT) · [2·Σ_j(x_j·a_ij)/(a_mix) - b_i/b_mix]
               · ∂Z/∂P / (Z + (1+√2)·B) / (Z + (1-√2)·B)
```

More practically, differentiate the explicit ln(φ_i) expression w.r.t. P,
using ∂Z/∂P from implicit differentiation of the cubic:

```
∂Z/∂P = -(∂cubic/∂P) / (∂cubic/∂Z)
```

where the cubic is Z³ - (1-B)Z² + (A-3B²-2B)Z - (AB-B²-B³) = 0.

### ∂ln(φ_i)/∂x_j

Differentiate the standard PR ln(φ_i) expression:

```
ln(φ_i) = (b_i/b_mix)(Z-1) - ln(Z-B)
         - A/(2√2·B) · [2·Σ_j(x_j·a_ij)/a_mix - b_i/b_mix]
           · ln[(Z+(1+√2)B)/(Z+(1-√2)B)]
```

w.r.t. x_j, accounting for:
- ∂a_mix/∂x_j = 2·Σ_k(x_k·a_jk)
- ∂b_mix/∂x_j = b_j
- ∂A/∂x_j and ∂B/∂x_j
- ∂Z/∂x_j from implicit differentiation of the cubic

This is algebraically tedious but straightforward. Reference: Michelsen &
Mollerup (2007) Appendix A, or derive directly from the PR formulation.

## Implementation phases

### Phase 1: EOS derivatives (~2-3 hours of focused work)

1. Add `ln_fugacity_coefficient` to base class (trivial default).
2. Implement `d_ln_phi_dP` for PR EOS with analytical expression.
3. Implement `d_ln_phi_dx` for PR EOS with analytical expression.
4. Add derivative tests: finite-difference validation for each.
5. Mirror for SRK (same structure, different constants).

### Phase 2: Newton saturation solver (~2-3 hours)

1. Implement `_newton_saturation_point` for bubble and dew.
2. Test against existing `calculate_bubble_point` / `calculate_dew_point`
   results for agreement.
3. Verify 3-5 iteration convergence from warm start.

### Phase 3: Fast envelope tracer (~3-4 hours)

1. Implement `calculate_phase_envelope_fast` with natural parameter
   continuation.
2. Add arclength switching near critical.
3. Implement warm-starting between points.
4. Test against existing envelope results for agreement (bubble/dew arrays
   should match within tolerance).

### Phase 4: Integration (~1-2 hours)

1. Wire `calculate_phase_envelope_fast` as the default in
   `calculate_phase_envelope` (with fallback flag).
2. Update `continuation.py` to use Newton solver internally.
3. Run full test suite — should drop from ~8 min to ~2-3 min.
4. Optional: deferred certificate generation.

## Scope: cubic EOS with quadratic mixing rules only

The analytical derivatives ∂ln(φ)/∂P and ∂ln(φ)/∂x_j have clean closed-form
expressions **only** for cubic EOS (PR, SRK, PR78) with the standard van der
Waals one-fluid quadratic mixing rules currently in the codebase:

```
a_mix = ΣΣ x_i x_j a_ij
b_mix = Σ x_i b_i
```

This does NOT generalize for free to:

- **Non-classical mixing rules** (Wong-Sandler, MHV2, Huron-Vidal): the
  composition dependence of `a_mix` routes through an activity coefficient
  model (NRTL, UNIQUAC, etc.), making ∂a_mix/∂x_j implicit and
  model-dependent. The derivatives are still obtainable but require
  chain-ruling through the activity coefficient layer.
- **SAFT-type EOS** (PC-SAFT, CPA): fugacity expressions are not cubic;
  derivatives exist but are structurally different and much more involved.
- **Association terms** (CPA for water/glycol systems): the monomer fraction
  X_A must be converged iteratively before φ can be evaluated, and
  differentiating through that implicit solve requires either the implicit
  function theorem or automatic differentiation.

**Design implication:** the `d_ln_phi_dP` and `d_ln_phi_dx` methods belong on
`CubicEOS` (the existing base class), not on a hypothetical `EOS` superclass.
The base class should provide a finite-difference fallback so that any future
non-cubic EOS can still use Newton at reduced efficiency:

```python
class CubicEOS:
    def d_ln_phi_dP(self, P, T, x, phase, kij=None):
        """Analytical for cubic EOS. Override in subclasses."""
        raise NotImplementedError

    def d_ln_phi_dP_numerical(self, P, T, x, phase, kij=None, dP=1e2):
        """Central finite-difference fallback for any EOS."""
        ln_phi_plus = self.ln_fugacity_coefficient(P + dP, T, x, phase, kij)
        ln_phi_minus = self.ln_fugacity_coefficient(P - dP, T, x, phase, kij)
        return (ln_phi_plus - ln_phi_minus) / (2.0 * dP)
```

The Newton envelope solver should call the analytical version when available
and fall back to the numerical version otherwise. This keeps the fast path
fast for cubic EOS while remaining correct for future EOS types.

For the current codebase (PR76, PR78, SRK only), the analytical path covers
100% of use cases.

## Risk and fallback

The existing TPD-based solver is **more robust** for pathological fluids
(near-critical multicomponent mixtures with multiple phase splits). The Newton
solver can fail to converge if:

- The initial K-values are far from the solution (mitigate: fall back to
  Wilson + SS for the first point only, then warm-start)
- Near the critical point where the Jacobian becomes singular (mitigate:
  arclength continuation)
- Phase identification is ambiguous (mitigate: use existing phase selection
  logic from cubic root)

Fallback strategy: if Newton fails for a point, call the existing TPD solver
for that point and resume Newton from the next point. This preserves
robustness while keeping the fast path for >95% of points.

## Expected performance

| Scenario | Current | After | Speedup |
|----------|---------|-------|---------|
| C1/C10 binary envelope | 7.5 s | <0.3 s | ~25× |
| 6-component flash config | ~5 s | <1 s | ~5× |
| 15-component characterized | ~90 s | <5 s | ~18× |
| Full test suite | 8.4 min | ~2 min | ~4× |

## References

1. Michelsen, M. L. (1980). "Calculation of phase envelopes and critical
   points for multicomponent mixtures." Fluid Phase Equilibria, 4(1-2), 1-10.
2. Michelsen, M. L. & Mollerup, J. M. (2007). Thermodynamic Models:
   Fundamentals and Computational Aspects. 2nd ed. Tie-Line Publications.
   Ch. 12 (Phase Envelopes), Appendix A (Derivatives).
3. Nichita, D. V. (2008). "Phase envelope construction for mixtures with many
   components." Energy & Fuels, 22(1), 488-495.
4. Hoteit, H. & Firoozabadi, A. (2006). "Simple phase stability-testing
   algorithm in the reduction method." AIChE Journal, 52(8), 2884-2897.
