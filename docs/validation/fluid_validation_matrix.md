# Two-Fluid Cross-Module Validation Matrix

This document defines the narrow cross-module validation lane for the current
canon branch.

The goal is not to validate "everything everywhere" at once. The goal is to
take two anchor fluids that already exist in the repo, run them through the
relevant runtime surfaces, and make the agreements and gaps explicit.

This note is intentionally narrower than the full repo validation plan.

---

## Verification Basis

This matrix was grounded against the current repo on 2026-04-12 using:

- `examples/pete665_assignment_case.json`
- `src/pvtcore/validation/pete665_assignment.py`
- `tests/unit/test_pete665_assignment.py`
- `tests/unit/test_pvtapp_runtime_contract.py`
- `tests/validation/test_heavy_end_pt_flash_runtime_matrix.py`
- `tests/validation/test_phase_envelope_runtime_matrix.py`
- `docs/validation/pete665_assignment_baseline.md`
- `docs/validation/phase_envelope_validation_matrix.md`

---

## Anchor Fluids

### Fluid A: PETE 665 assignment baseline

Canonical repo source:

- `examples/pete665_assignment_case.json`

Canonical kernel reference path:

- `src/pvtcore/validation/pete665_assignment.py`

Why this fluid is in scope:

- it is the current term-project anchor
- it includes the inline pseudo-component path (`PSEUDO_PLUS`)
- it already has dedicated bubble / CCE / DL reference handling in-repo

### Fluid B: provisional default gas / gas-condensate stand-in

Current repo-local source:

- the gas-plus-fraction runtime payload in
  `tests/unit/test_pvtapp_runtime_contract.py`
  (`_gas_plus_fraction_composition_payload()`)

Why this fluid is in scope:

- it exercises the `C1-C6 + C7+` characterization surface
- it is already used in runtime contract tests for dew / CVD / envelope-facing
  paths
- it is the closest checked-in stand-in for the "default MRPVT gas"
  description until an exact GUI-saved feed is exported into repo-local form

Important note:

- this second anchor is a provisional stand-in, not a claim that the exact GUI
  saved MRPVT default gas is already checked into this repo
- once the exact GUI-saved feed is exported or copied into a repo-local JSON
  artifact, it should replace this stand-in as Fluid B

---

## Scope Boundary

### In scope for this matrix

- config / schema acceptance
- component alias and feed normalization behavior
- inline pseudo or plus-fraction preservation through runtime preparation
- standalone saturation workflows
- experiment workflow execution where physically appropriate
- run-artifact persistence and replay surfaces

### Explicitly out of scope for the first checkpoint

- GUI layout and control placement
- broad EOS admission work
- broad BIP admission work
- external-corpus acquisition
- phase-envelope signoff as a release gate

Phase envelope is intentionally held out of the first checkpoint because there
is already an active envelope-specific lane and its topology/cancellation work
should not be conflated with this two-fluid cross-module matrix.

---

## Status Key

- `P0`: first-checkpoint required
- `P1`: useful follow-on after P0
- `Hold`: intentionally deferred or owned by another lane
- `Out`: not a meaningful target for this fluid/workflow pair

---

## Cross-Module Matrix

| Runtime surface | Fluid A: assignment baseline | Fluid B: gas-condensate stand-in | Status | Authority / comparison basis |
| --- | --- | --- | --- | --- |
| Raw feed acceptance | exact assignment JSON accepted on dedicated path; desktop/general path tolerance differences noted | runtime config accepted through general app path | `P0` | `examples/pete665_assignment_case.json`, `RunConfig`, runtime contract tests |
| Feed identity / alias preservation | inline `PSEUDO_PLUS` must survive load -> build -> runtime artifacts | `C7+` policy and resolved preset must survive load -> build -> runtime artifacts | `P0` | `pete665_assignment.py`, `plus_fraction_policy.py`, runtime contract tests |
| Runtime component build | DB components plus inline pseudo must build deterministically | characterized `C7+` path must build deterministically | `P0` | `_prepare_fluid_inputs`, assignment tests, runtime contract tests |
| PT flash | secondary structural check only | useful structural check; representative heavy-end runtime matrix now exists for dry-gas, gas-condensate, CO2-rich-gas, volatile-oil, black-oil, and sour-oil families, plus saved-run replay on representative gas/oil anchors | `P1` | same runtime path, no external authority required for first matrix |
| Bubble point | primary assignment scalar workflow | secondary check only | `P0` | assignment runner and standalone bubble workflow |
| Dew point | secondary structural check | primary gas scalar workflow | `P0` | standalone dew workflow and runtime contract expectations |
| CCE | primary assignment experiment workflow | secondary check only | `P0` | assignment runner exact schedule vs general runtime behavior |
| DL | primary assignment experiment workflow | `Out` for first checkpoint | `P0` | assignment runner exact schedule vs general runtime behavior |
| CVD | `Out` for first checkpoint | primary gas-condensate experiment workflow | `P0` | runtime contract workflow coverage |
| Separator | secondary assignment workflow check | `Out` for first checkpoint | `P1` | runtime execution only; no separate external authority in first pass |
| Phase envelope | `Hold` | `Hold` | `Hold` | covered by the separate envelope lane and `docs/validation/phase_envelope_validation_matrix.md` |
| Run artifacts / replay | stored config must replay cleanly | stored config must replay cleanly | `P0` | `config.json`, `results.json`, `manifest.json`, run-history helpers |

---

## First-Checkpoint Target Runs

### Fluid A: assignment baseline

Run these first:

1. dedicated assignment bubble-point baseline
2. general-runtime bubble-point configuration built from the same fluid intent
3. dedicated assignment CCE exact schedule
4. dedicated assignment DL exact schedule
5. artifact-backed replay of a saved assignment-style run

What this checkpoint should prove:

- the assignment fluid is not stranded in a one-off kernel path
- the inline pseudo-component survives the app/runtime boundary honestly
- the exact assignment experiment schedules remain executable on the reference
  path even where the generic desktop path is still partial

### Fluid B: gas-condensate stand-in

Run these first:

1. standalone dew-point run
2. standalone bubble-point run as a secondary structural check
3. CVD run
4. heavy-end PT-flash matrix across representative gas and oil families
5. artifact-backed replay of a saved gas run

What this checkpoint should prove:

- the `C7+` characterization path remains preserved through runtime dispatch
- gas-like heavy-end feeds do not silently collapse to a narrower component-only
  representation
- at least one gas-condensate experiment workflow stays aligned with the same
  fluid definition used for saturation

---

## Acceptance Gates

### Gate 1: same fluid intent survives across surfaces

For each anchor fluid, confirm that:

- the stored feed and heavy-end intent can be reconstructed from runtime
  artifacts
- the runtime-selected characterization context remains visible in the result
  config/artifacts
- replaying the stored `config.json` reproduces the same calculation type and
  fluid definition with a fresh run identity

### Gate 2: saturation and experiment surfaces agree locally

For each applicable fluid:

- the saturation workflow used as the anchor for that fluid must complete
- the corresponding experiment workflow must complete on the same fluid intent
- any first-step or boundary relationship that is supposed to match locally
  must be checked explicitly in tests, not assumed

Examples:

- assignment fluid: bubble pressure and assignment experiment schedule operate
  on the same pseudo-inclusive feed definition
- gas-condensate fluid: dew-point path and CVD path operate on the same
  characterized gas feed definition

### Gate 3: no phase-envelope signoff leakage

This matrix should not be used to declare the continuation tracer "done."

If a fluid is run through phase-envelope code as a secondary check, that does
not replace the separate envelope validation gates already tracked elsewhere.

---

## Immediate Gaps

These are the current known gaps in this matrix:

1. The exact GUI-saved "default MRPVT gas" feed is not yet represented in a
   repo-local artifact. Fluid B is therefore a provisional stand-in.
2. The generic desktop path is still not fully assignment-complete for exact
   assignment schedules and raw published composition entry.
3. Phase-envelope validation remains intentionally partitioned into its own
   lane.

---

## Recommended Next Step

Build the first executable matrix around these two concrete anchors:

- Fluid A: `examples/pete665_assignment_case.json`
- Fluid B: the gas-condensate plus-fraction payload currently exercised in
  `tests/unit/test_pvtapp_runtime_contract.py`

Then replace Fluid B with the exact GUI-saved MRPVT gas feed as soon as that
feed is exported into a stable repo-local JSON or test fixture.
