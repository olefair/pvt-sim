# PETE 665 Assignment Baseline

This document maps the current repo against the course project described in
`TERM_PROJECT_ASSIGNMENT.md`.

This is a runtime-surface baseline, not a promise that the desktop app is
already assignment-complete.

---

## Verification Basis

This baseline was re-verified against the current repo on 2026-04-12 using:

- `TERM_PROJECT_ASSIGNMENT.md`
- `examples/pete665_assignment_case.json`
- `src/pvtcore/validation/pete665_assignment.py`
- `src/pvtapp/schemas.py`
- `src/pvtapp/job_runner.py`
- `src/pvtapp/main.py`
- `src/pvtapp/widgets/composition_input.py`
- `src/pvtapp/widgets/results_view.py`
- `src/pvtapp/widgets/text_output_view.py`

The earlier version of this note overstated some GUI blockers. This version is
the corrected baseline.

---

## Current Desktop Surface

The current desktop GUI exposes these calculation types:

- `PT Flash`
- `Bubble Point`
- `Dew Point`
- `Phase Envelope`
- `CCE`
- `Differential Liberation`
- `CVD`
- `Separator`

The current desktop GUI exposes one runtime EOS:

- `Peng-Robinson (1976)`

The dedicated assignment reference path lives outside the GUI in:

- `examples/pete665_assignment_case.json`
- `src/pvtcore/validation/pete665_assignment.py`
- `scripts/run_pete665_assignment.py`

---

## Assignment Requirements Extracted

From `TERM_PROJECT_ASSIGNMENT.md`, the repo must support at least:

- the listed black-oil mixture with an explicit heavy pseudo row
- an assigned temperature by initials
- a PR-based EOS baseline
- zero-BIP runs as an allowed baseline
- saturation pressure
- CCE at `1000`, `1250`, and `1500 psia`
- DL at `500`, `300`, and `100 psia`
- CCE outputs: relative volume plus oil/gas trends versus pressure
- DL outputs: `Bg`, `Bo`, `RsD`, `RsDb`, `BtD`

---

## Current Repo Status Against Assignment

### 1. Assignment Fluid Entry

Status: `PARTIAL`

What is now true:

- The app-facing schema does support explicit inline pseudo-components through
  `FluidComposition.inline_components` in `src/pvtapp/schemas.py`.
- The GUI composition widget does support that same inline pseudo-component
  path in `src/pvtapp/widgets/composition_input.py`.
- `pvtapp.job_runner` does construct runtime `Component` objects from those
  inline pseudo rows.

What is still blocked:

- The published assignment mole fractions sum to `1.00001`.
- `RunConfig` currently rejects that raw published total because the
  app-facing composition tolerance is tighter than the rounded assignment
  table.
- The dedicated assignment runner accepts the published case, but the general
  GUI / `RunConfig` path does not accept the raw document values unchanged.

Implication:

- The desktop app can represent the assignment fluid structurally.
- The current GUI path is still not assignment-ready as an exact
  document-to-runtime entry surface.

### 2. Assigned Temperature by Initials

Status: `PARTIAL`

What exists:

- The assignment reference case stores the initials table in
  `examples/pete665_assignment_case.json`.
- The assignment runner accepts either `--initials` or an explicit
  `--temperature-f`.
- The GUI can accept the temperature numerically.

What is missing on the desktop path:

- There is no assignment-case loader in the GUI.
- There is no initials picker in the GUI.

Implication:

- The repo supports the temperature mapping on the assignment reference path.
- The desktop app still depends on manual temperature entry.

### 3. EOS and BIP Baseline

Status: `PARTIAL`

What exists:

- The runtime implements the standard Peng-Robinson EOS.
- The assignment runner uses that kernel path directly.
- Zero-BIP execution is supported.

Important limitation:

- The GUI BIP panel is not the runtime control path.
- `src/pvtapp/main.py` does not feed the selected BIP method into
  `RunConfig`.
- The current desktop truth is effectively "no explicit BIP override unless
  provided through config data."

Working interpretation:

- The assignment's `PR EOS (1978)` wording is currently treated as the repo's
  present Peng-Robinson kernel baseline, not a wired PPR78 workflow.

Implication:

- The kernel baseline is usable for the assignment reference run.
- The desktop BIP control surface is still misleading.

### 4. Saturation Pressure

Status: `PARTIAL`

What exists:

- Bubble-point calculation is implemented and exposed.
- Dew-point calculation is implemented and exposed.
- The dedicated assignment runner computes saturation pressure via the
  bubble-point path.
- Existing assignment tests verify the kernel saturation path remains robust to
  poor initial guesses.

Desktop limitation:

- The desktop path is still gated by the raw-fluid-entry issue above if the
  user enters the assignment table exactly as published.

Implication:

- The saturation workflow itself is present.
- The desktop assignment path is still not fully frictionless.

### 5. CCE at 1000 / 1250 / 1500 psia

Status: `PARTIAL`

What exists:

- The kernel assignment runner does hit the exact required CCE points.
- `CCEResult` carries:
  - pressure
  - relative volume
  - liquid fraction
  - vapor fraction
  - Z-factor
- CSV export from the desktop path already includes vapor fraction.

What is still blocked on the app-facing path:

- `CCEConfig.n_steps` currently requires `>= 5`, so the desktop app cannot
  express the exact 3-point assignment schedule through `RunConfig`.
- The main GUI CCE table omits vapor fraction.
- The text output omits both liquid and vapor fractions.
- The CCE plot only shows relative volume versus pressure.

Implication:

- The kernel can satisfy the assignment CCE requirement.
- The desktop app still cannot run the exact assignment schedule or present the
  full assignment output surface honestly.

### 6. DL at 500 / 300 / 100 psia

Status: `BLOCKED` on the general desktop path, `SUPPORTED` on the dedicated
assignment runner

What exists in the kernel assignment path:

- exact DL pressure points
- `Bg`
- `Bo`
- `RsD`
- `RsDb`
- `BtD`

What exists in the current app-facing path:

- `DLConfig` supports only:
  - `bubble_pressure_pa`
  - `pressure_end_pa`
  - `n_steps`
- `execute_dl(...)` builds a linear grid from bubble pressure down to the end
  pressure.
- `DLResult` exposes only:
  - pressure
  - `Rs`
  - `Bo`
  - `Bt`
  - vapor fraction
  - liquid moles remaining

Implication:

- The desktop app cannot express the exact assignment DL schedule.
- The desktop app does not expose the full assignment DL output set.

---

## GUI Reconciliation Matrix

| Assignment Item | Desktop Status | Main Gap |
|---|---|---|
| Exact assignment fluid entry | Partial | Inline pseudo row is supported, but the raw published composition total is rejected by `RunConfig` |
| Assignment temperature by initials | Partial | No initials picker or assignment-case loader in the GUI |
| PR baseline | Partial | Only `Peng-Robinson (1976)` is exposed; interpretation remains documented rather than explicit in-app |
| Zero-BIP baseline | Partial | Runtime behavior is zero-BIP by default, but the BIP pane is diagnostic theater |
| Saturation pressure | Partial | Workflow exists, but raw assignment entry remains frictionful |
| CCE exact pressure schedule | No | `CCEConfig.n_steps >= 5` blocks the exact 3-point assignment schedule |
| CCE output: relative volume | Yes | Already present |
| CCE output: oil/gas trends | Partial | Data exists, but the primary table/text/plot surface is incomplete |
| DL exact pressure schedule | No | Only bubble-to-end linear spacing is supported in the app-facing config |
| DL output: `Bg` | No | Missing from app result schema and GUI |
| DL output: `Bo` | Yes | Already present |
| DL output: `RsD` | Partial | Present as `Rs`, but not mapped as assignment output in the desktop surface |
| DL output: `RsDb` | No | Missing from app result schema and GUI |
| DL output: `BtD` | Partial | Present as `Bt`, but not mapped as assignment output in the desktop surface |

---

## Acceptance Rule

The repo should only be considered assignment-satisfying when all of the
following are true:

- The published assignment fluid can be entered on an official desktop path
  without manual workaround or hidden normalization steps.
- The assignment temperature can be selected from the initials table or
  entered directly in an explicit assignment workflow.
- The selected EOS interpretation is documented and reflected honestly in the
  desktop runtime.
- Saturation pressure can be run from the desktop app for the assignment case.
- CCE can run exactly at `1000`, `1250`, and `1500 psia` from the desktop app.
- DL can run exactly at `500`, `300`, and `100 psia` from the desktop app.
- The desktop app exposes the assignment-required CCE and DL outputs clearly.
- The assignment runner and the desktop runtime agree when configured to the
  same physical case.

---

## Immediate Work Required

Priority 1:

- Decide how the desktop path should accept the rounded published assignment
  composition without falsifying the input.

Priority 2:

- Add an assignment-aware input path:
  - assignment case loader
  - initials-based temperature selection

Priority 3:

- Make CCE and DL schedules explicit pressure lists on the app-facing path
  instead of forcing minimum-length linear grids.

Priority 4:

- Promote or remove misleading runtime surfaces:
  - BIP method selection
  - assignment output naming for DL
  - assignment-complete CCE presentation

---

## Practical Next Step

For the desktop milestone, the highest-leverage next step is:

1. treat `pvtcore.validation.pete665_assignment` as the kernel reference
2. make the desktop path capable of expressing that same case without manual
   massaging
3. close the schedule/output gaps for CCE and DL

That turns the assignment from a kernel-side reference artifact into a real
desktop runtime capability.
