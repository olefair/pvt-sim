# Runtime Surface Consolidation Blueprint

## Objective

Bring the desktop app/runtime into parity with the simulator capabilities that
the repo already claims and the PETE 665 course flow expects, with special
focus on heavy-end characterization, runtime method selection, Whitson
lumping, delumping, and real runtime control of BIPs and related methods.

This blueprint is driven by the standard in
`docs/runtime_surface_standard.md`.

---

## Problem Statement

The current desktop runtime is not a faithful orchestration layer over the full
simulator surface.

Verified issues:

1. The app uses a narrowed characterization path in
   `src/pvtcore/characterization/pipeline.py`, while other supported methods
   remain in separate side paths such as `src/pvtcore/characterization/fluid.py`.
2. The active runtime path hard-limits split/lumping behavior to
   `Pedersen + contiguous`, which does not match the intended method surface.
3. Characterization context is discarded by `pvtapp.job_runner`, preventing
   delumping and transparent heavy-end reporting.
4. The GUI does not expose method selection for retained characterization
   methods.
5. The GUI shows BIP controls that are not currently the canonical runtime
   control path.
6. Several domain features exist in `pvtcore` but are not yet surfaced through
   the desktop runtime.

This violates the runtime-surface standard and creates a mismatch between:

- the course methodology
- the architecture/docs
- the library surface
- the actual app behavior

---

## Non-Negotiable Standards

The implementation must satisfy all of the following:

- one canonical runtime preparation path
- multiple user-selectable characterization methods on that path
- Whitson heavy-end lumping as the canonical runtime lumping method
- preserved characterization context through execution and reporting
- delumped heavy-end reporting where the user expects detailed compositions
- no display-only runtime controls
- no orphaned domain features left implied as supported

---

## Verified Current Gaps

### A. Characterization / Heavy-End Runtime

- `pvtapp.job_runner` currently uses `pvtcore.characterization.pipeline` for
  plus-fraction handling.
- The active `pipeline` path supports only `Pedersen` splitting and
  `contiguous` lumping.
- `pvtcore.characterization.fluid` contains additional split methods and
  Whitson lumping but is not the canonical app runtime path.

### B. Lumping / Delumping

- Whitson lumping exists in `src/pvtcore/characterization/lumping.py`.
- Delumping exists in `src/pvtcore/characterization/delumping.py` and
  `SCNLumpingResult`.
- The app/runtime does not currently preserve and use that context through
  result reporting.

### C. Runtime Method Surface

- The heavy-end GUI does not expose characterization method selection.
- The heavy-end GUI does not expose runtime lumping method selection.
- The BIP pane is not yet a faithful runtime control path.

### D. Broader Orphaned or Partial Runtime Surfaces

The following are present in `pvtcore` but not yet on the desktop runtime
surface as first-class supported features:

- predictive PPR78 BIPs
- viscosity / IFT runtime surfaces
- confinement workflows
- ternary / iso-line envelope tooling
- wider tuning/regression surface
- slimtube / MMP workflows

Some of these may remain future milestones, but they must not remain implied as
app-supported if they are not wired.

Current bounded state: the desktop/runtime surface now includes a first-slice
single-contact swelling test. Slimtube, MMP, and broader miscibility workflows
remain out of scope and must stay labeled as absent until separately wired.

---

## Target End State

### 1. Canonical Prepared Fluid Context

Replace tuple-style fluid preparation with a structured runtime object, for
example `PreparedFluidContext`, carrying at least:

- input component IDs
- resolved runtime component IDs
- runtime component models
- runtime composition
- EOS instance
- runtime BIP matrix / BIP source
- characterization method
- split result
- SCN properties
- lumping result
- delumping basis
- feed-to-runtime mapping

The canonical runtime path must operate on this context.

### 2. Canonical Characterization Runtime API

Unify the runtime-facing characterization surface so the app uses one
preparation path with pluggable methods instead of multiple competing side
paths.

That path must support, at minimum:

- `Pedersen`
- `Katz`
- `Lohrenz`

If additional methods are retained as supported in the repo, they must either
be added here or explicitly demoted from supported status.

### 3. Canonical Runtime Lumping / Delumping

- Canonical runtime lumping method: `Whitson`
- Canonical reporting path: preserve and use delumping/retrieval for detailed
  output

The runtime may solve on a lumped representation for speed, but result
presentation/export must remain auditable and transparent.

### 4. Honest Runtime Controls

The GUI must expose actual runtime options, including:

- characterization split method
- split MW model where applicable
- lumping enabled/disabled
- lumping method
- number of lumped groups
- BIP method / override mode

If a control does not affect runtime behavior, it must not appear as a normal
input.

---

## Work Packages

## WP1. Runtime Context Refactor

### Goal

Stop discarding characterization state at the app/runtime boundary.

### Primary Surfaces

- `src/pvtapp/job_runner.py`
- `src/pvtapp/schemas.py`

### Changes

- Introduce `PreparedFluidContext`
- Change `_prepare_fluid_inputs()` to return that context
- Update all `execute_*` functions to consume it
- Persist runtime method metadata into run artifacts

### Acceptance

- No run path relies on anonymous tuple unpacking for fluid state
- Run artifacts show the actual characterization/lumping/BIP choices

---

## WP2. Characterization Method Consolidation

### Goal

Make retained characterization methods runtime-selectable on one canonical app
path.

### Primary Surfaces

- `src/pvtcore/characterization/pipeline.py`
- `src/pvtcore/characterization/fluid.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/widgets/composition_input.py`

### Changes

- Consolidate split-method support into the canonical runtime API
- Expose method selection in the GUI
- Remove or explicitly demote duplicate competing paths that are not part of
  the canonical runtime

### Acceptance

- User can choose `Pedersen`, `Katz`, or `Lohrenz` in the GUI
- Selected method is visible in run artifacts
- Runtime actually executes the chosen method

---

## WP3. Replace Contiguous Lumping With Whitson

### Goal

Move canonical runtime heavy-end lumping to the Whitson method.

### Primary Surfaces

- `src/pvtcore/characterization/pipeline.py`
- `src/pvtcore/characterization/lumping.py`
- `src/pvtcore/io/fluid_definition.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/widgets/composition_input.py`

### Changes

- Remove `contiguous` as the canonical runtime lumping method
- Call Whitson lumping from the active runtime path
- Expose runtime lumping controls in the GUI
- Keep any legacy contiguous code only if clearly marked non-canonical

### Acceptance

- A heavy-end run with runtime lumping enabled uses Whitson, not contiguous
- The selected lumping method is visible in artifacts
- Heavy-end multi-step workflows run through the same canonical lumped context

---

## WP4. Delumping / Composition Retrieval

### Goal

Reconstruct detailed heavy-end output for reporting/export when the runtime
solves on lumped groups.

### Primary Surfaces

- `src/pvtcore/characterization/delumping.py`
- `src/pvtcore/characterization/pipeline.py`
- `src/pvtapp/job_runner.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/widgets/results_view.py`
- `src/pvtapp/widgets/text_output_view.py`

### Changes

- Preserve lump mapping in runtime context
- Delump PT-flash compositions and K-values
- Extend the same pattern to:
  - bubble point
  - dew point
  - phase envelope compositions where available
  - CCE
  - DL
  - CVD
  - separator workflows where phase-composition reporting exists
- Label whether outputs are lumped or delumped

### Acceptance

- Detailed heavy-end reporting is available after a lumped run
- Exports remain auditable and consistent with the solved lumped state

---

## WP5. Real BIP Runtime Surface

### Goal

Make BIP choices and overrides actual runtime inputs.

### Primary Surfaces

- `src/pvtapp/main.py`
- `src/pvtapp/widgets/interaction_params_view.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/job_runner.py`
- `src/pvtcore/characterization/bip.py`
- `src/pvtcore/eos/ppr78.py`

### Changes

- Promote the BIP pane from diagnostic display to true config input
- Record BIP source as one of:
  - zero
  - default correlation
  - PPR78
  - explicit override matrix
- Ensure the runtime matrix used by EOS matches the GUI selection exactly

### Acceptance

- GUI BIP choices change the actual runtime matrix
- Run artifacts record the BIP source and overrides
- No displayed BIP mode is merely cosmetic

---

## WP6. Broader Runtime Surface Reconciliation

### Goal

Resolve other major `pvtcore` domain features that are present but not yet
properly surfaced.

### Candidate Areas

- viscosity / IFT
- confinement
- ternary / iso-lines
- tuning / regression
- slimtube / MMP / miscibility workflows

### Rule

For each area, decide one of:

- wire into app/runtime
- explicitly label as future / experimental / non-runtime
- remove from claimed support surfaces

---

## Documentation Updates Required

The implementation work must keep these docs aligned:

- `README.md`
- `docs/development.md`
- `docs/architecture.md`
- `docs/input_schema.md`
- `docs/technical_notes.md`
- `docs/runtime_surface_standard.md`

If a feature is not yet wired, canonical docs must say so plainly.

---

## Completion Criteria

This blueprint is complete only when all of the following are true:

- there is one canonical runtime preparation path
- retained characterization methods are runtime-selectable
- Whitson is the canonical runtime lumping method
- delumping is wired into user-facing reporting where expected
- the BIP surface is real runtime control, not diagnostic theater
- no domain-level simulator feature remains orphaned while still implied as
  supported

