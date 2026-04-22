# Input Schema (Canonical)

This document defines the canonical **fluid input contract** for PVT-SIM.

**Goal:** Make inputs unambiguous, reproducible, and stable across modules (characterization → EOS → stability/flash → envelope → properties → confinement).

> This is a *schema spec* (data contract), not an implementation spec. Mathematical details live in:
> - `docs/technical_notes.md` (equations / model definitions)
> - `docs/numerical_methods.md` (solvers / convergence / damping / bracketing)
> - the course lecture material and assignment handouts (primary scope reference)

---

## 0. Design principles

### 0.1 Single source of truth
A “fluid” is defined once and then transformed through explicit steps:
1. **Normalize & validate feed** (mass balance, missing props)
2. **Characterize / pseudoize** (incl. plus fraction splitting & lumping)
3. **Build EOS-ready component set** (Tc, Pc, ω, MW, kij, volume shifts)
4. **Run thermo** (stability, flash, saturation, envelope)
5. **Compute properties** (μ, IFT, density)
6. **Optional confinement loop** (Pc coupled via IFT/density outputs)

### 0.2 Explicit options, no hidden physics
All correlation and model choices must be explicit in input (or explicitly defaulted in `docs/technical_notes.md`).

### 0.3 Units are mandatory
All dimensional quantities must declare units (or be in canonical SI where required).

### 0.4 Component naming must be explicit
Hydrocarbon isomer labels must be written explicitly anywhere ambiguity is
possible.

Preferred explicit notation in user-facing docs, validation artifacts, and
external simulator exchanges:

- `iC4` = isobutane
- `nC4` = normal butane
- `iC5` = isopentane
- `nC5` = normal pentane
- `neoC5` = neopentane

Current runtime / database compatibility note:

- the repo's historical internal IDs still use `C4` for `nC4`
- the repo's historical internal IDs still use `C5` for `nC5`
- alias resolution supports both forms where implemented

Documentation and validation guidance:

- prefer `nC4` / `nC5` over bare `C4` / `C5` in new docs and external
  reference captures
- only use bare `C4` / `C5` when referring to the legacy internal component IDs
  explicitly

---

## 1. Canonical top-level object

### 1.1 YAML/JSON structure (conceptual)

```yaml
fluid:
  name: "Example Fluid"
  basis: "mole"                       # currently supported: mole
  components:
    - id: "C1"                        # known pure component ID (from DB)
      z: 0.70
    - id: "C10"
      z: 0.30

  plus_fraction:                      # OPTIONAL (present if a plus cut exists)
    label: "C7+"
    z_plus: 0.0392
    cut_start: 7                      # carbon number start (e.g., 7 for C7+)
    mw_plus_g_per_mol: 165.0
    sg_plus_60F: 0.815                # specific gravity at 60°F/60°F convention
    tbp_data:                         # OPTIONAL (if TBP cut data exists)
      cuts:
        - name: "C7-C9"
          z: 0.010
          mw: 103.0
          sg: 0.72
          tb_k: 385.0
        - name: "C12"
          z: 0.009
          mw: 170.0
          sg: 0.74
        - name: "C15-C18"
          z: 0.0202
          mw: 235.0
          sg: 0.81
    splitting:                        # controls how C7+ is expanded
      method: "pedersen"              # pedersen | katz | lohrenz
      target_end: "C20+"              # e.g., "C20+", "C30+", "C45+"
      max_carbon_number: 45           # only used for methods that need explicit N
      pedersen:
        form: "ln_z = A + B*MW"       # slide + plan-aligned canonical form
        mw_model: "MWn = 14n - 4"     # Danesh-style approximation if needed
        solve_AB_from: "balances"     # balances | fit_to_tbp
      katz:
        zn_formula: "zn = 1.38205*z7plus*exp(-0.25903*n)"
      lohrenz:
        requires_partial_molar_fit: true
    lumping:
      enabled: false
      n_groups: 8
      method: "whitson"
      mixing: "lee"                   # how Tc/Pc/omega mix for lumps

  eos:
    model: "PR"                       # PR | SRK (future)
    mixing_rule: "vdW1"               # van der Waals one-fluid
    kij:                              # optional explicit overrides (tuning-ready)
      default_policy: "generalized"   # "generalized" uses documented kij ranges
      overrides:
        - pair: ["CO2", "C7+"]
          kij: 0.12
    volume_translation:
      enabled: false
      method: "peneloux"              # planned

  correlations:
    tb: "soreide_1989"
    critical_props: "riazi_daubert_1987"    # or kesler_lee_1976 | cavett_1962
    acentric: "edmister_1958"               # or kesler_lee_1976
    parachor: "weinaug_katz_1943"           # mixture parachor workflow

  simulation_controls:
    allow_negative_flash: false       # true enables nv outside [0,1]
    stability_before_flash: true      # Michelsen TPD gate before PT flash

confinement:                          # OPTIONAL: only for nano-confined runs
  enabled: false
  pore_radius_nm: 5.0
  contact_angle_deg: 0.0              # fully wetting default (cosθ=1)
  couple_pc:
    enabled: true
    max_iters: 50
    tol_pc_pa: 1.0
    ift_method: "parachor"            # depends on densities + compositions
