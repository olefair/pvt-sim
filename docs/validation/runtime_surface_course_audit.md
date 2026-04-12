# Runtime Surface Course Audit

This note validates the current repo against:

- `TERM_PROJECT_ASSIGNMENT.md`
- `LECTURE_SLIDES_MERGED.md`
- `docs/runtime_surface_standard.md`

The focus is the canonical desktop runtime path: what the GUI and
`pvtapp.job_runner` actually execute, not just what exists somewhere in
`pvtcore`.

---

## Verification Basis

This audit was verified from the current repo on 2026-04-12 using:

- `src/pvtapp/capabilities.py`
- `src/pvtapp/main.py`
- `src/pvtapp/job_runner.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/widgets/composition_input.py`
- `src/pvtapp/widgets/interaction_params_view.py`
- `src/pvtapp/widgets/results_view.py`
- `src/pvtapp/widgets/text_output_view.py`
- `src/pvtcore/characterization/pipeline.py`
- `src/pvtcore/characterization/fluid.py`
- `src/pvtcore/characterization/lumping.py`
- `src/pvtcore/characterization/delumping.py`
- `src/pvtcore/characterization/bip.py`
- `src/pvtcore/eos/ppr78.py`
- `src/pvtcore/properties/`
- `src/pvtcore/confinement/`
- `src/pvtcore/envelope/`
- `src/pvtcore/tuning/`
- `src/pvtcore/validation/pete665_assignment.py`

---

## Verified Runtime-Wired Surface

The canonical desktop runtime currently wires these workflows through
`src/pvtapp/job_runner.py` and exposes the same set in
`src/pvtapp/capabilities.py`:

- `PT Flash`
- `Bubble Point`
- `Dew Point`
- `Phase Envelope`
- `CCE`
- `Differential Liberation`
- `CVD`
- `Separator`

The current runtime EOS surface is:

- `Peng-Robinson (1976)` only

The current heavy-end app path supports:

- explicit inline pseudo-components
- plus-fraction entry
- Pedersen-based plus splitting
- optional SCN lumping via the active `pipeline` path

What it does not yet preserve is the richer characterization context after
fluid preparation.

---

## Assignment-Critical Findings

### 1. The assignment fluid is structurally supported in the app, but not yet as a raw document-to-runtime path

- The GUI and `RunConfig` both support explicit inline pseudo-components.
- The raw published assignment mole fractions sum to `1.00001`.
- The app-facing composition validator currently rejects that rounded total.
- The dedicated assignment runner still accepts the published case.

### 2. The desktop app does not have an assignment-aware loader

- No assignment-case loader is present in the GUI.
- No initials picker is present in the GUI.
- The reference case and initials table live only in the dedicated assignment
  runner path.

### 3. The desktop CCE surface is not assignment-complete

- The kernel reference path can hit `1500`, `1250`, and `1000 psia` exactly.
- The app-facing `CCEConfig` requires `n_steps >= 5`, so the exact 3-point
  assignment schedule is not expressible through the desktop runtime config.
- `CCEResult` retains vapor fraction and CSV export includes it.
- The primary CCE table, text output, and plot still under-surface the oil/gas
  trends requested in the assignment.

### 4. The desktop DL surface is still assignment-blocked

- The kernel reference path supports explicit DL pressure lists and returns the
  full assignment-style outputs.
- The app-facing DL config only supports a linear bubble-to-end grid.
- The app-facing DL result contract omits `Bg` and `RsDb`.

### 5. The BIP pane is still display-only

- `src/pvtapp/widgets/interaction_params_view.py` computes and displays a
  matrix based on a selected method.
- `src/pvtapp/main.py` does not carry that selection into `RunConfig`.
- The BIP pane is therefore not the canonical runtime control path.

---

## Lecture-Derived Feature Matrix

| Course Topic | Kernel Status | Desktop Runtime Status | Notes |
|---|---|---|---|
| Saturation / flash / phase behavior basics | Present | Wired | Bubble, dew, PT flash, and envelope are real desktop workflows |
| CCE / DL / CVD / separator | Present | Wired, but partial | Core workflows run; assignment parity is incomplete |
| Pedersen characterization | Present | Wired | Active plus-fraction runtime path uses Pedersen |
| Katz characterization | Present | Not wired | Available in `plus_splitting` and `characterization.fluid`, not in the canonical desktop path |
| Lohrenz characterization | Present | Not wired | Same status as Katz |
| Whitson lumping | Present | Not wired | Exists in `characterization.lumping`, but active runtime path still uses `contiguous` |
| Delumping / composition retrieval | Present | Not wired | Exists in `characterization.delumping` and `SCNLumpingResult`, not preserved through app reporting |
| Wilson initialization | Present | Wired internally | Used by the kernel as an internal helper, not a user-facing mode |
| Whitson-Torp K-value workflow | Not found | Not wired | Mentioned in lecture notes but not present as a repo workflow |
| Predictive `PPR78` BIPs | Present | Not wired | Exists in `characterization.bip` and `eos.ppr78`, not in the desktop runtime |
| Viscosity (`LBC`) | Present | Not wired | Present in `pvtcore.properties` only |
| IFT (`parachor`) | Present | Not wired | Present in `pvtcore.properties` only |
| Confinement | Present | Not wired | Present in `pvtcore.confinement` only |
| Ternary / iso-line tools | Present | Not wired | Present in `pvtcore.envelope` only |
| Tuning / regression | Present | Not wired | Present in `pvtcore.tuning` only |
| Swelling / slimtube / MMP workflows | Not found as executable workflows | Not wired | Covered in lecture material but not present as first-class repo workflows |
| Standalone TBP experiment | Explicit stub only | Honest non-runtime | `pvtcore.experiments.tbp` raises `NotImplementedError` instead of pretending support |

---

## Runtime-Honesty Findings

The repo currently has three different classes of feature state:

### A. Runtime-wired

These are genuinely reachable from the desktop GUI and `job_runner`:

- flash / saturation / envelope core workflows
- CCE / DL / CVD / separator
- inline pseudo-component fluid entry
- Pedersen-based plus characterization on the active path

### B. Present in code but not on the canonical desktop path

These are the main orphan-risk surfaces:

- Katz / Lohrenz split methods
- Whitson lumping
- delumping
- predictive `PPR78`
- viscosity / IFT
- confinement
- ternary / iso-lines
- tuning / regression

### C. Explicitly non-runtime

These are currently honest boundaries rather than hidden orphaned features:

- standalone TBP execution

---

## Current Controller Conclusion

The current repo aligns with only part of the assignment and lecture-derived
surface.

The most important verified mismatches are:

1. the desktop app still narrows the kernel surface more than the course flow
   implies
2. the BIP pane is still diagnostic theater
3. the active heavy-end runtime path still hard-limits method selection
4. several kernel features remain stranded outside the canonical runtime path
5. the dedicated assignment runner is ahead of the desktop app in both
   scheduling flexibility and output completeness

---

## Priority Order for the Next Validation / Fix Pass

1. Make the assignment desktop path honest:
   - raw published fluid entry
   - initials/assignment loader
   - exact CCE/DL schedules
   - assignment-complete outputs

2. Make GUI controls real runtime controls:
   - BIP method
   - characterization method
   - lumping method

3. Consolidate characterization onto one canonical runtime path:
   - preserve characterization context
   - replace `contiguous` as the canonical lumping path
   - wire delumping into reporting

4. Decide the runtime status of broader kernel features:
   - wire them
   - demote them explicitly
   - or remove the implied support

That order matches both the term project pressure and the runtime-surface
standard already documented in this repo.
