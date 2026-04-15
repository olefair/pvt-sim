# Validation Plan

## Philosophy

Every numerical result must be traceable to one of:
1. A published experimental dataset,
2. An independent reference solve of the governing equations, or
3. A secondary commercial-software cross-check for graphical surfaces such as phase envelopes

"It runs without crashing" is not validation. "It matches experiment, or it matches an independent equation-based reference where that is the correct authority, and any remaining commercial cross-checks are clearly secondary" is validation.

---

## Validation Levels

### Level 1: Unit Tests
Verify individual functions produce correct output for known inputs.

**Scope:** Every public function in `pvtcore`
**Frequency:** Run on every commit (CI/CD)
**Pass Criteria:** Exact match (within floating-point tolerance)

### Level 2: Integration Tests
Verify module interactions work correctly.

**Scope:** Complete workflows (e.g., characterization → flash → properties)
**Frequency:** Run on every PR
**Pass Criteria:** Results within expected numerical tolerance

### Level 3: Regression Tests
Verify results match validated reference calculations.

**Scope:** Full simulations against published data or independent reference solves
**Frequency:** Run before releases
**Pass Criteria:** Match external data within measurement uncertainty, or match independent reference equations within numerical tolerance

---

## Module-Specific Validation

### 1. Pure Component Database

**Validation Source:** NIST Chemistry WebBook

| Component | Property | NIST Value | Tolerance |
|-----------|----------|------------|-----------|
| Methane | Tc | 190.564 K | ±0.01 K |
| Methane | Pc | 4.5992 MPa | ±0.001 MPa |
| Methane | ω | 0.0115 | ±0.001 |
| n-Decane | Tc | 617.7 K | ±0.1 K |
| n-Decane | Pc | 2.103 MPa | ±0.001 MPa |

**Test:** Load each component, verify properties match NIST to specified tolerance.

---

### 2. Cubic Solver

**Validation:** Analytical verification

| Test Case | c₂ | c₁ | c₀ | Expected Roots |
|-----------|-----|-----|-----|----------------|
| Three real | -6 | 11 | -6 | 1, 2, 3 |
| One real | 0 | 0 | -8 | 2 |
| Repeated | -3 | 3 | -1 | 1, 1, 1 |
| PR typical | -0.8 | 0.12 | -0.004 | (compute analytically) |

**Test:** Verify solver returns correct roots for each case.

---

### 3. Peng-Robinson EOS

**Validation Source:** Original PR paper (1976), Table 1

Pure component vapor pressures at various temperatures:

| Component | T (K) | P_exp (bar) | P_calc (bar) | Error |
|-----------|-------|-------------|--------------|-------|
| Methane | 150 | 8.86 | TBD | < 2% |
| n-Butane | 350 | 9.35 | TBD | < 2% |
| n-Decane | 500 | 5.12 | TBD | < 3% |

**Test:** Calculate vapor pressure via bubble point, compare to experimental.

---

### 4. Flash Calculation

**Validation Source:** Experiment C₁-nC₄ VLE data (from professor's reading list)

Binary system at specified conditions:

| T (°F) | P (psia) | x_C1 (exp) | y_C1 (exp) | x_C1 (calc) | y_C1 (calc) |
|--------|----------|------------|------------|-------------|-------------|
| 100 | 500 | TBD | TBD | | |
| 100 | 1000 | TBD | TBD | | |
| 160 | 500 | TBD | TBD | | |

**Test:** Run PT flash, compare compositions to experimental values.
**Tolerance:** |x_calc - x_exp| < 0.01 (1 mol% absolute)

---

### 5. Phase Envelope

**Primary Validation Source:** equation-authority saturation checks plus honest
external or commercial multicomponent envelope references

**Secondary Only:** MI PVT proxy output for MI-compatible compositions, used as
an optional visual sanity check

Primary signoff fluid: one honest reference-backed multicomponent case,
preferably a characterized heavy-end or `C1-C6 + C7+` gas-condensate /
volatile-oil feed

| Point | T (°F) | P (psia) | Reference | PVT-SIM | Error |
|-------|--------|----------|-----------|---------|-------|
| Cricondenbar | TBD | TBD | | | < 1% |
| Cricondentherm | TBD | TBD | | | < 1°F |
| Critical | TBD | TBD | | | < 1% |

**Test:** Generate phase envelope, compare key points and overall graphical
behavior against the reference-backed case; use MI PVT only as supplemental
context when the feed can be represented honestly.
**Boundary:** Do not use MI PVT as the authoritative scalar baseline for
bubble-point or dew-point pressures, and do not treat MI-only proxy cases as
signoff for `C7+`, `H2S`, sour, or pseudo-component envelope behavior.
**Detailed signoff matrix:** `docs/validation/phase_envelope_validation_matrix.md`
**Optional MI PVT proxy roster:** `docs/validation/mi_pvt_phase_envelope_roster.md`
**Optional automated ThermoPack lane:** `tests/validation/thermopack/`
**External backend policy:** `docs/validation/external_validation_engine.md`

Course-derived interpretation for this repo:

- `VLE class exercise March 3, 2026`: same-equation scalar bubble/dew checks. Agreement should be at the rounding level, not "within a few percent."
- `Pb and Pd calculation class exercise_PR EOS_March 17, 2026.xlsx`: same-equation PR-EOS checks with explicit `kij`. Agreement should again be at the rounding level.
- `Use the MI PVT oil and simulate the DL_CALCULATIONS_March 31, 2026`: workflow-level MI PVT cross-check for DL-style flash outputs, not an authoritative scalar baseline for saturation or envelope pressures.

Commercial/software cross-check policy:

- MI PVT remains an optional manual proxy surface for course-compatible cases;
  it is not a release gate for fluid families it cannot represent honestly.
- The active automated external engine is limited to permissive backends under
  `docs/validation/external_validation_engine.md`.
- ThermoPack is the primary external EOS/VLE comparison lane under
  `tests/validation/thermopack/`.
- These external lanes do not replace the repo's equation-based solver
  correctness tests.

---

### 6. Plus-Fraction Splitting

**Validation:** Material balance closure

| Test | z_C7+ | MW_C7+ | γ_C7+ | Σzₙ | Σzₙ·MWₙ | Σ(zₙ·MWₙ/ρₙ) |
|------|-------|--------|-------|-----|---------|---------------|
| Heavy oil | 0.25 | 215 | 0.85 | = z_C7+ | = z_C7+·MW_C7+ | = z_C7+·MW_C7+/ρ_C7+ |

**Test:** Split plus fraction, verify all material balance constraints satisfied to 10⁻¹⁰.

---

### 7. Critical Property Correlations

**Validation Source:** Generalized SCN tables (Katz-Firoozabadi)

| SCN | MW | γ | Tc_table (K) | Tc_RD (K) | Error |
|-----|-----|-----|--------------|-----------|-------|
| C7 | 96 | 0.722 | 548.9 | TBD | < 2% |
| C10 | 134 | 0.778 | 622.2 | TBD | < 2% |
| C15 | 206 | 0.836 | 708.9 | TBD | < 2% |

**Test:** Compare correlation output to tabulated values.

---

### 8. Viscosity (LBC)

**Validation Source:** Published crude oil viscosity measurements

| Fluid | T (°F) | P (psia) | μ_exp (cp) | μ_calc (cp) | Error |
|-------|--------|----------|------------|-------------|-------|
| Light oil | 200 | 3000 | TBD | TBD | < 10% |
| Heavy oil | 150 | 2000 | TBD | TBD | < 15% |

**Note:** Viscosity correlations have inherently higher uncertainty (~10-20%).

---

### 9. IFT (Parachor)

**Validation Source:** Published IFT measurements

| System | T | P | σ_exp (mN/m) | σ_calc (mN/m) | Error |
|--------|---|---|--------------|---------------|-------|
| C1-nC10 | TBD | TBD | TBD | TBD | < 15% |

**Note:** IFT has measurement uncertainty of ~5-10%.

---

### 10. Lab Test Simulations (CCE, DL, CVD)

**Validation Source:** Published PVT reports from literature

CCE Test:
| P (psia) | V_rel (exp) | V_rel (calc) | Error |
|----------|-------------|--------------|-------|
| Above Pb | 1.0 | 1.0 | exact |
| Pb | TBD | TBD | |
| Below Pb | TBD | TBD | < 2% |

DL Test:
| P (psia) | Rs (exp) | Bo (exp) | Rs (calc) | Bo (calc) |
|----------|----------|----------|-----------|-----------|
| TBD | TBD | TBD | | |

---

### 11. Nano-Confinement

**Validation Source:** Nojabaei, Johns & Chu (2013), SPE-159258

C₁-nC₄ system in nanopores:

| Pore radius (nm) | ΔPb (exp) | ΔPb (calc) | Error |
|------------------|-----------|------------|-------|
| 10 | TBD | TBD | < 5% |
| 5 | TBD | TBD | < 10% |

**Test:** Calculate bubble point suppression, compare to published results.

---

## Test Data Management

### Directory Structure
```
tests/
├── unit/
│   ├── test_cubic_solver.py
│   ├── test_rachford_rice.py
│   └── ...
├── validation/
│   ├── test_saturation_equation_benchmarks.py
│   ├── test_external_corpus_schema.py
│   ├── test_vs_mi_pvt.py
│   ├── external_data/
│   │   ├── acquisition_manifest.json
│   │   ├── cases/
│   │   └── templates/
│   ├── mi_pvt/
│   │   └── cases/
│   └── ...
```

### Data Format

External physical-accuracy anchors now have a repo-local JSON intake surface:

- schema/loader: `src/pvtcore/validation/external_corpus.py`
- planned acquisition backlog: `tests/validation/external_data/acquisition_manifest.json`
- ready-case templates: `tests/validation/external_data/templates/`

Use one of the supported JSON shapes instead of ad hoc CSV or one-off test data:

- `pure_component_saturation`
- `literature_vle_tieline`
- `lab_c7plus_saturation`

This keeps the equation-authority lane, external physical-accuracy lane, and
MI-PVT cross-check lane separated cleanly.

---

## Continuous Integration

### Pre-commit Hooks
- Type checking (mypy)
- Linting (ruff)
- Unit tests (fast subset)

### PR Checks
- Full unit test suite
- Integration tests
- Coverage report (target: >90%)

### Release Validation
- Full regression suite
- Performance benchmarks
- Documentation build

---

## Reporting

Each validation run produces a report:

```
PVT-SIM Validation Report
=========================
Date: 2026-01-31
Version: 0.1.0
Git SHA: abc123

Module: Flash Calculation
  Test: C1-nC4 binary VLE
  Source: Experiment (1985)
  Points: 15
  Max Error: 0.8 mol%
  Mean Error: 0.3 mol%
  Status: PASS

Module: Phase Envelope
  Test: Homework fluid
  Source: MI PVT v2023
  Cricondenbar Error: 0.4%
  Critical Point Error: 0.6%
  Status: PASS

Overall: 47/48 tests passed (1 pending data)
```
