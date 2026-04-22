# Technical Notes (Equation-Level Contract + Execution Ordering)

This document is the **equation-level “source of truth”** for the simulator’s thermodynamic stack and the **ordering constraints** that make it a coherent system (not a grab-bag of correlations).

**Read alongside:**
- `docs/architecture.md` (module ownership + file locations)
- `docs/numerical_methods.md` (solver rules, tolerances, damping, failure modes)
- the course lecture material and assignment handouts (primary sources)

If code and this document disagree, **update one or both** so they match. Do not “fix” behavior by silently swapping equations/correlations.

---

## 0. Global conventions

### 0.1 Units (internal)
Internal SI is the default contract unless explicitly stated otherwise:
- Pressure `P` in **Pa**
- Temperature `T` in **K**
- Amount in **mol**
- Gas constant `R = 8.314462618… J/(mol·K)` (`Pa·m³/(mol·K)`)

Any “petroleum output” (psia, scf/STB, °F) is a **presentation layer** conversion only.

### 0.2 Notation
- Components indexed `i, j = 1..Nc`
- Feed composition: `z_i`, liquid: `x_i`, vapor: `y_i`
- Phase fraction: vapor `β` (aka `n_v` in some notes), liquid `1-β`
- Fugacity coefficient in phase `α ∈ {L,V}`: `φ_i^α`
- EOS mixture parameters: `a_mix`, `b_mix`; pure parameters `a_i(T)`, `b_i`
- Binary interaction parameters: `k_ij` (BIPs)
- Compressibility factor: `Z`

### 0.3 Hard invariants (enforced everywhere)
- `∑ z_i = 1`, `∑ x_i = 1`, `∑ y_i = 1` (within tolerance)
- `0 ≤ x_i, y_i, z_i ≤ 1` (after normalization)
- Physical EOS state checks (e.g., for PR `Z > B` and `Z + δ2 B > 0`) must be guarded.

---

## 1. The simulator “ecosystem” (ordering + dependencies)

**Core question:** given `(P, T, z)` ⇒ determine **phase state**, phase compositions `(x,y)`, phase fraction `β`, and properties (ρ, μ, IFT, etc.).

**Dependency chain (must not be broken):**

1) **Fluid characterization (once per fluid definition)**
   - plus fraction splitting → pseudo-components (SCN)
   - property estimation → `Tc, Pc, ω, MW, …`
   - EOS parameter tables and BIPs are created here

2) **Stability analysis (before *every* flash / saturation solve)**
   - prevents converging to trivial `x=y=z` when a split exists
   - provides phase existence logic and good initial guesses

3) **PT flash (only if unstable / two-phase)**
   - solves `β`, `x`, `y` via Rachford–Rice + fugacity equality
   - depends on EOS fugacity coefficients and robust Z-root selection

4) **Property calculations (post-flash)**
   - densities depend on EOS Z and phase MW
   - viscosity depends on density (often reduced density)
   - IFT depends on phase compositions + densities (parachor form)

5) **Nano-confinement coupling (optional)**
   - capillary pressure depends on IFT
   - phase equilibrium depends on capillary pressure (different phase pressures)
   - therefore confinement is an **outer coupling loop** around flash + IFT

6) **Higher-level “experiments” (CCE/DL/CVD/separators)**
   - are controlled sequences of flashes + bookkeeping
   - *state updates* (removing gas, holding volume, etc.) feed back into flash

This ordering is explicit in `simulator-workflow.docx` and is treated as contract.  

---

## 2. Fluid characterization

### 2.1 Inputs
Typical lab input includes:
- Light ends and resolved components (N₂, CO₂, H₂S, C1–C6, …)
- A plus fraction `C7+` (or `Cn+`) with:
  - plus fraction mole fraction `z_+`
  - plus fraction MW `MW_+`
  - optionally specific gravity `γ_+` and/or normal boiling point `Tb_+`

### 2.2 Plus-fraction splitting (Pedersen-style exponential)
Goal: split `z_+` into SCNs `n = n_start..n_end` (often 7..45).

A common Pedersen form is:
- `ln(z_n) = A + B·MW_n`
with constraints enforcing material balance:
- `∑_{n} z_n = z_+`
- `∑_{n} z_n·MW_n = z_+·MW_+`

**SCN molecular weights** are often approximated by:
- `MW_n = 14 n - 4`  (paraffin baseline; used for initial SCN MWs)

**Solve for (A,B)**:
- treat `z_n(A,B) = exp(A + B·MW_n)`
- enforce both constraints (2 unknowns) via a 2D solve (Newton / bracketed hybrid)
- normalize carefully; guard overflow for large `MW_n`

Notes:
- This is the *initial distribution*. Later lumping may reduce Nc, but delumping must preserve results.

### 2.3 Alternative splitting (optional selectable methods)
If implemented, each must be selectable and documented:
- Katz exponential SCN distribution
- Lohrenz-type forms
- Whitson gamma distribution (if adopted)

### 2.4 Pseudo-component critical properties and ω
Each SCN/pseudo-component requires at minimum:
- `Tc, Pc, ω, MW`
Optionally:
- `Vc`, parachor, volume shift coefficient, etc.

**Correlation selection is part of the user-facing configuration**:
- `Tc, Pc, Vc`: Riazi–Daubert (1987) options
- `Tc, Pc`: Kesler–Lee (1976) options
- `ω`: Edmister and/or Kesler–Lee options

**Contract rule:** do not “mix-and-match” silently. A fluid record should capture *which correlation family was used* for each property.

### 2.5 Binary interaction parameters (BIPs)
For PR/SRK-type EOS, mixture `a_mix` depends on `k_ij`:
- default `k_ij = 0` only when no correlation table is configured
- otherwise, build a full symmetric matrix with:
  - special handling for non-hydrocarbons (CO₂, N₂, H₂S)
  - optional “heavy pseudo” interactions (C7+ with light ends)

BIPs are a major tuning knob; they must remain traceable and overrideable.

### 2.6 Lumping + delumping (speed vs fidelity)
- Lumping reduces Nc for speed (esp. repeated flashes in envelopes/tests).
- Delumping reconstructs SCN-level compositions for reporting and for correlations that require full resolution.

**Key constraint:** any lumping scheme must preserve:
- total moles
- component MW balance
- EOS-consistent phase splits as closely as feasible

---

## 3. Cubic EOS: Peng–Robinson (1976) as primary

### 3.1 EOS form (PR)
PR EOS in molar volume form:
- `P = RT/(V - b) - a(T)/(V² + 2bV - b²)`

Temperature dependence:
- `a_i(T) = a_i(Tc) · α_i(T)`
- `b_i = b_i(Tc)` (PR treats b as T-independent)

Critical-point parameters (pure):
- `a_i(Tc) = 0.45724 * R² * Tc_i² / Pc_i`
- `b_i      = 0.07780 * R  * Tc_i   / Pc_i`

Alpha function:
- `α_i(T) = [1 + κ_i (1 - sqrt(T/Tc_i))]²`
- `κ_i = 0.37464 + 1.54226 ω_i - 0.26992 ω_i²`  (classic PR; heavy-end extensions optional)

### 3.2 Mixing rules (van der Waals one-fluid)
For mixture composition `x` (or `y`):
- `b_mix = ∑ x_i b_i`
- `a_mix = ∑∑ x_i x_j a_ij`
- `a_ij = sqrt(a_i a_j) · (1 - k_ij)`

### 3.3 Dimensionless parameters and Z-cubic
Define:
- `A = a_mix P / (R² T²)`
- `B = b_mix P / (R T)`

PR Z-cubic:
- `Z³ - (1 - B) Z² + (A - 2B - 3B²) Z - (A B - B² - B³) = 0`

**Root selection**
- If 3 real roots: smallest positive root ⇒ liquid-like Z; largest ⇒ vapor-like Z
- If 1 real root: single-phase or supercritical; use that root consistently

### 3.4 Fugacity coefficients (mixture)
For PR, the standard mixture fugacity coefficient form for component `i`:
- `ln φ_i = (b_i/b_mix)(Z - 1) - ln(Z - B)`
  ` - (A/(2√2 B)) * ( 2 * (∑_j x_j a_ij)/a_mix - b_i/b_mix )`
  ` * ln( (Z + (1+√2)B) / (Z + (1-√2)B) )`

This equation is the basis for:
- stability analysis (TPD)
- flash equilibrium (φ-ratio K updates)
- departure functions if implemented

**Domain guards** (must be enforced):
- `Z > B`
- `Z + (1-√2)B > 0`

### 3.5 Fugacity equality (equilibrium condition)
At VLE equilibrium (bulk):
- `f_i^L = f_i^V`
- `x_i φ_i^L P = y_i φ_i^V P`
So:
- `K_i ≡ y_i/x_i = φ_i^L / φ_i^V`

---

## 4. Stability analysis (Michelsen TPD)

### 4.1 Why stability is not optional
Flash iterations can converge to:
- trivial `x = y = z`, `K = 1` even when two phases exist,
especially near critical points or with poor initialization.

Therefore, **run stability before flash and before saturation solvers**.

### 4.2 Tangent Plane Distance function
Given feed `z` and a trial composition `w`, define:
- `d_i = ln z_i + ln φ_i(z)`  (evaluated at feed in a nominated feed-phase)
- `TPD(w) = ∑ w_i [ ln w_i + ln φ_i(w) - d_i ]`

**Decision rule**
- if `min_w TPD(w) < 0` ⇒ unstable ⇒ split occurs
- if `min_w TPD(w) ≥ 0` ⇒ stable ⇒ single-phase

### 4.3 Successive substitution iteration (Michelsen)
For a given trial phase, iterate:
- `w_i^{new} = exp( d_i - ln φ_i(w) )`
then normalize `w`.

Convergence metric:
- `max_i | ln(w_i^{new}/w_i^{old}) | < tol_stab`

### 4.4 Trial initializations (Wilson-based)
Generate at least two trial seeds:
- vapor-like: `w ∝ z * K^Wilson`
- liquid-like: `w ∝ z / K^Wilson`

Wilson K (used for initialization):
- `K_i^Wilson = (Pc_i/P) * exp[ 5.373 (1 + ω_i) (1 - Tc_i/T) ]`

---

## 5. PT flash (isothermal-isobaric, two-phase)

### 5.1 Governing equations
Unknowns: `β`, `x`, `y`.

Definitions:
- `y_i = K_i x_i`
- Material balance:
  - `z_i = (1-β) x_i + β y_i`
  - ⇒ `x_i = z_i / (1 + β (K_i - 1))`
  - ⇒ `y_i = K_i x_i`

Rachford–Rice equation for `β`:
- `F(β) = ∑ z_i (K_i - 1) / (1 + β (K_i - 1)) = 0`

### 5.2 Successive substitution loop (φ-ratio)
Loop until convergence:
1) Initialize `K` (Wilson or provided)
2) Solve Rachford–Rice for `β` (robust bracketing method preferred)
3) Compute `x`, `y` from `β` and `K`
4) Compute `φ^L(x)` and `φ^V(y)` from EOS (with proper Z roots)
5) Update `K_new = φ^L / φ^V`
6) Convergence check (typical):
   - `∑ (ln K_new - ln K_old)² < tol_flash`
   - or `max_i |ln(K_new/K_old)| < tol_flash`

### 5.3 Trivial / single-phase return path
If stability indicates single-phase, return:
- `phase = liquid` with `β=0` and `x=z`
or
- `phase = vapor` with `β=1` and `y=z`

### 5.4 Near-critical behavior
Expect:
- slow convergence (K → 1)
- numerical sensitivity in Z-root selection
Use documented damping/acceleration (see `docs/numerical_methods.md`) rather than changing physics.

---

## 6. Saturation pressures

### 6.1 Bubble point at fixed T (given z as liquid feed)
At bubble point:
- incipient vapor forms; liquid composition ~ feed: `x = z`
- condition (K-form):
  - `∑ z_i K_i(P,T) = 1`

Algorithm pattern:
- iterate on P
- at each P:
  - compute `K` from EOS φ-ratio with `x=z` and vapor composition from `y_i ∝ K_i z_i`
  - enforce `∑ y_i = 1`
- solve `g(P) = ∑ z_i K_i - 1 = 0` (Newton with bracket fallback)

### 6.2 Dew point at fixed T (given z as vapor feed)
At dew point:
- incipient liquid forms; vapor composition ~ feed: `y = z`
- condition:
  - `∑ z_i / K_i(P,T) = 1`

Analogous solver on P with robust bracketing.

### 6.3 “Negative flash”
For lab workflows, you may intentionally allow computed `β < 0` or `β > 1` to represent conditions outside the two-phase envelope.
This must be an explicit mode (not silent behavior), and downstream properties must interpret it consistently.

---

## 7. Phase envelope construction (bulk)

Envelope construction is a controlled continuation of saturation conditions across T (or P), producing:
- bubble curve
- dew curve
- critical region behavior and cricondentherm/cricondenbar

**Contract points:**
- Each envelope point is a saturation solve (bubble or dew), not a generic flash.
- Stability analysis is used to validate phase boundary points and detect critical proximity.
- Step control must be adaptive (smaller steps near the critical region).

(Implementation details and continuation numerics belong in `docs/numerical_methods.md` and the envelope module.)

---

## 8. Post-flash properties

### 8.1 Phase molecular weights
- `MW^L = ∑ x_i MW_i`
- `MW^V = ∑ y_i MW_i`

### 8.2 Densities (EOS-based)
Using compressibility `Z^α`:
- `ρ^α (mol/m³) = P / (Z^α R T)`
- `ρ^α (kg/m³)  = ρ^α(mol/m³) * MW^α(kg/mol)`

If volume translation is enabled, it modifies the molar volume:
- `V_corr = V_eos + ∑ x_i c_i`  (Peneloux-style form; coefficients must be traceable)

### 8.3 Viscosity (Lohrenz–Bray–Clark, 1964)
LBC is density-based and depends on:
- dilute-gas viscosity `μ*` (often from Stiel–Thodos / corresponding states)
- mixture critical properties (for reduced density)
- reduced density `ρ_r = ρ / ρ_c`

**Key interdependency:** viscosity requires **density**, which requires **EOS Z**, which requires a converged **phase equilibrium** state.

Implement LBC strictly from the chosen course reference set, with all coefficients and mixture rules documented in code or local notes.

### 8.4 Interfacial tension (parachor / Weinaug–Katz)
Common parachor mixing form:
- `σ^(1/4) = ∑ P_i ( x_i ρ^L/MW^L - y_i ρ^V/MW^V )`
⇒ `σ = [ … ]^4`

**Key interdependency:** IFT depends on:
- phase compositions (x,y)
- phase densities (ρ^L, ρ^V)
Therefore it is evaluated **after** flash.

---

## 9. Nano-confinement coupling (capillary pressure + VLE)

### 9.1 Capillary pressure
For a pore radius `r` and contact angle `θ`:
- `P_c = 2 σ cosθ / r`

Often assume complete wetting as a default:
- `θ = 0` ⇒ `cosθ = 1` ⇒ `P_c = 2σ/r`

### 9.2 Modified equilibrium condition (different phase pressures)
In confinement:
- liquid pressure `P^L`
- vapor pressure `P^V = P^L + P_c`

Equilibrium becomes:
- `x_i φ_i^L(P^L) P^L = y_i φ_i^V(P^V) P^V`

So the modified K-value is:
- `K_i = (φ_i^L / φ_i^V) * (P^L / P^V)`

### 9.3 Outer coupling loop (Pc ↔ flash ↔ IFT)
Because `P_c` depends on `σ`, and `σ` depends on `(x,y,ρ^L,ρ^V)`:

1) Start with bulk flash at `P^L = P^V = P`
2) Compute `σ` from parachor correlation
3) Compute `P_c = 2σ/r` (and `P^V = P^L + P_c`)
4) Re-run flash with split pressures and modified K update
5) Repeat until `|P_c^{new} - P_c^{old}| < tol_pc`

This coupling is **the** key reason the project is an ecosystem: confinement adds an outer fixed-point loop around the classical flash.

---

## 10. Laboratory “experiments” (structured flash sequences)

These are deterministic workflows composed of:
- repeated flashes
- explicit mass/volume bookkeeping between steps

### 10.1 CCE (constant composition expansion)
- z fixed, total moles fixed
- step pressure down (or up), run equilibrium each step
- record relative volume, Z, phase fractions, dropout, etc.

### 10.2 DL (differential liberation)
At each pressure step:
- flash current feed
- remove produced gas completely
- new feed for next step is remaining liquid (`z_next = x_current`)
Requires strict mass conservation tracking.

### 10.3 CVD (constant volume depletion)
At each step:
- flash
- remove only enough gas to restore cell volume to a target
- update overall composition accordingly
This is coupled because “remove enough gas” is an additional constraint.

### 10.4 Swelling test
- fixed temperature, explicit oil feed, explicit injection-gas feed
- enrichment schedule is expressed as gas added per initial oil mole
- each enrichment step recomputes bubble pressure on the enriched mixture
- reported first-slice outputs are bubble pressure, saturated-liquid density /
  molar volume, and swelling factor on the initial-oil basis
- the current admitted runtime slice is single-contact enrichment only; this is
  not slimtube, MMP, or multi-contact miscibility

### 10.5 Multistage separator train
- sequential flashes at separator conditions
- final stock-tank flash
- compute GOR, API, shrinkage, etc.

---

## 11. EOS tuning / regression (future but must remain traceable)

Tuning targets may include:
- saturation pressures
- liquid density
- CCE relative volumes
- CVD dropout

Parameters (priority order per plan):
- heavy-end `Ω_a, Ω_b` or heavy-end criticals within uncertainty
- volume translation coefficients
- selected BIPs (especially CO₂–heavy, C1–heavy)

**Contract rules:**
- tuning never changes the EOS form; it only adjusts documented parameters
- every tuned parameter must be:
  - bounded physically
  - recorded in an audit trail
  - validated against withheld checks

---

## 12. Recommended documentation additions (to persist knowledge)

If you want newcomers to onboard fast and avoid “tribal knowledge,” add:

1) `docs/units.md`
   - explicit unit policy (SI internal), conversion conventions, standard conditions

2) `docs/input_schema.md`
   - canonical JSON/YAML schema for fluid definition (including plus-fraction fields, correlation selections)

3) `docs/validation_cases.md`
   - a small suite of named cases (binary, ternary, real fluid) with expected invariants and reference values
   - include “smoke tests” and “regression” checks

4) `docs/literature/` (folder)
   - store the primary PDFs with stable filenames
   - keep filenames stable for offline, reproducible sourcing

5) `docs/known_failure_modes.md`
   - critical region behavior, near-spinodal failures, “Z-root flips,” convergence traps
   - and the prescribed mitigations (damping, bracketing, step control), referencing `docs/numerical_methods.md`

---

## 13. Quick glossary (common petroleum outputs)
(Compute from SI state; present as petroleum units)

- `R_s` solution GOR
- `B_o`, `B_g`, `B_t` formation volume factors
- API gravity
- shrinkage factors
- separator GOR and stock-tank oil density

(Exact definitions belong in the lab-test modules once implemented; keep them consistent with standard PVT reporting.)
