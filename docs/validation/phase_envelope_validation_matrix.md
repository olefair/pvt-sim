# Phase Envelope Validation Matrix

This document is the working signoff matrix for the phase-envelope module and
the continuation tracer that is intended to replace the current fixed-grid
desktop path.

The key rule is simple:

- accepted error depends on the validation authority
- same-equation classroom/workbook reproductions are expected to match at the
  rounding level
- experimental and literature data are judged against measurement-quality
  tolerances
- MI PVT remains a secondary graphical cross-check for envelopes, not the
  scalar truth source for bubble or dew pressures

## Signoff Criteria

Do not treat the continuation-based phase-envelope path as release-ready until
all of the following are true:

- the traced envelope is deterministic for repeated identical runs
- the bubble branch stays on one local root family instead of teleporting
  between branches
- the dew branch restarts only when the critical handoff is locally continuous
- the result contains no fake flat tails caused by trivial `x ~= y ~= z`,
  `K ~= 1` states being accepted as ordinary saturation points
- the critical marker is tied to branch collapse behavior, not merely to curve
  intersection after two unrelated scans
- standalone bubble-point and dew-point solves agree with same-equation
  reference solves at the appropriate scalar tolerances
- MI PVT overlays match key envelope features within the stated graphical
  tolerances once identical fluid definition and EOS settings are locked

## Validation Classes

| Validation class | Authority | Example anchors | Accepted error / gate | What it proves |
| --- | --- | --- | --- | --- |
| Same-equation scalar reproduction | Highest for lecture/workbook cases | March 3 VLE worksheet, March 17 PR EOS workbook | Pressure error <= 0.1% or <= 1 psia, whichever is larger; composition error <= 5e-4 absolute | The implemented equations and units match the reference solve |
| Independent equation benchmark | Highest for repo saturation solvers | `tests/validation/test_saturation_equation_benchmarks.py` | Case-specific numerical tolerance from the reference solve; no branch ambiguity accepted | The production bubble/dew solvers satisfy the governing fugacity equations |
| Literature / experimental VLE | Highest for physical fidelity where available | NIST vapor pressure, literature tie-line cases | Pressure typically within 2-3%; composition within 0.01 absolute mole fraction unless the dataset justifies tighter bounds | The EOS plus component data are physically credible for that regime |
| Continuation topology gate | Highest for envelope tracer structure | `tests/validation/test_phase_envelope_release_gates.py` | Deterministic repeated runs, continuous branch tracking, controlled switch, no flat tails, no branch teleportation | The continuation tracer is numerically stable enough to trust structurally |
| MI PVT envelope cross-check | Secondary graphical authority | Homework envelope composition, MI PVT overlays | Cricondenbar and critical pressure within 1%; cricondentherm within 1 deg F; overall branch shape qualitatively consistent | The resulting envelope looks right against a trusted commercial surface |
| MI PVT DL / workflow cross-check | Secondary workflow authority | March 31, 2026 MI PVT oil DL exercise | Trend agreement required; scalar targets are secondary unless the exact MI settings and fluid characterization are frozen | The flash-driven workflow reproduces the intended classroom process chain |

## Course-Derived Anchors

The following course artifacts were re-checked on 2026-04-12 from the uploaded
lecture bundle supplied outside the repo:

- `VLE class exercise March 3, 2026.docx`
- `VLE CALCULATION CLASS NOTES IN EXCEL MARCH 3, 2026.xlsx`
- `Pb and Pd calculation class exercise_PR EOS_March 17, 2026.xlsx`
- `Use the MI PVT oil and simulate the DL_CALCULATIONS_March 31, 2026.docx`

### 1. March 3, 2026 VLE class exercise

Authority class:

- same-equation classroom reference for bubble pressure, dew pressure, and
  flash state consistency

Verified scalar anchors from the workbook:

- feed at `160 deg F`:
  - propane `z = 0.4653949824`
  - n-butane `z = 0.2118349575`
  - n-pentane `z = 0.2275264358`
  - n-hexane `z = 0.0952436243`
- ideal-solution bubble pressure: `215.4740919 psia`
- Wilson bubble pressure: `217.8643414 psia`
- ideal-solution dew pressure: `69.7313593 psia`
- Wilson flash reference at `150 psia`:
  - vapor fraction `0.4539352551`
  - liquid `x = [0.2700188753, 0.2321913923, 0.3375891528, 0.1602005701]`
  - vapor `y = [0.7004241036, 0.1873470350, 0.0951256831, 0.0171031898]`

What this implies for release:

- if this repo reproduces the same Wilson or ideal-solution formulas, the
  acceptable error is rounding-level, not a broad engineering tolerance
- if this repo uses a different EOS path for the same fluid, this exercise is
  still useful as a sanity anchor but no longer an exact scalar truth source

### 2. March 17, 2026 PR EOS bubble/dew workbook

Authority class:

- same-equation PR-EOS reference with explicit `kij`

Verified scalar anchors from the workbook:

- methane / n-pentane feed:
  - methane `z = 0.7384764711`
  - n-pentane `z = 0.2615235289`
  - `kij = 0.020641`
- bubble-point sheet:
  - `T = 100 deg F`
  - `Pb = 200 psia`
  - incipient vapor `y = [0.8593456901, 0.1406551813]`
- dew-point sheet:
  - `T = 220 deg F`
  - `Pd = 15 psia`
  - incipient liquid `x = [0.5290784294, 0.4709217299]`

What this implies for release:

- this is an exact PR-EOS solver-verification case, so the correct target is
  essentially exact reproduction of pressure and incipient phase composition
- for these same-equation workbook cases, "< 0.1%" is a ceiling, not a goal

### 3. March 31, 2026 MI PVT oil / DL exercise

Authority class:

- secondary workflow cross-check

Verified workflow anchors from the note:

- reported saturation pressure at `200 deg F`: `2970.31 psia`
- DL-style flash checkpoints:
  - `2900 psia`
  - `1000 psia`
  - standard conditions
- derived classroom values include:
  - `RsDb = 696.8 scf/stb`
  - `Bo(2900 psia) = 1.33 rb/stb`
  - `Bo(1000 psia) = 1.15 rb/stb`
  - `RsD(2900 psia) = 677 scf/stb`
  - `RsD(1000 psia) = 230 scf/stb`

What this implies for release:

- this note is a good process-chain check for flash to DL post-processing
- it is not the primary authority for envelope topology or standalone bubble /
  dew saturation pressure validation
- if this repo is configured to mirror the same MI PVT fluid and settings,
  these numbers should be close, but they should still be treated as secondary
  to same-equation and literature-backed scalar validation

## Continuation Release Gate

The continuation tracer should only replace the fixed-grid desktop tracer when
all of these gates are passing:

1. Scalar consistency

- bubble and dew points used by the continuation path remain consistent with
  the authoritative saturation benchmarks in
  `tests/validation/test_saturation_equation_benchmarks.py`

2. Structural topology

- repeated identical runs produce the same branch states
- bubble branch temperatures are monotone and remain on one local family
- dew restart occurs at most once
- the critical handoff is supported by branch collapse, not a spurious jump
- no flat constant-pressure tails appear after the true boundary disappears

3. MI PVT graphical agreement

- bubble and dew branches overlay the MI PVT envelope qualitatively
- cricondenbar pressure error is below 1%
- critical pressure error is below 1%
- cricondentherm temperature error is below 1 deg F

4. Runtime agreement

- the desktop runtime path and the kernel continuation path agree when given
  the same fluid, EOS, and settings

## Current Executable Mapping

Current repo surfaces that implement parts of this matrix:

- `tests/validation/test_saturation_equation_benchmarks.py`
  - authoritative scalar bubble/dew equation checks
- `tests/validation/test_external_pure_component_saturation.py`
  - external NIST pure-component saturation anchors for scalar physical-fidelity checks
- `tests/validation/test_external_literature_vle.py`
  - external literature tie-line checks for scalar bubble-point pressure and incipient vapor agreement
- `tests/validation/test_vle_benchmarks.py`
  - internal flash/VLE consistency checks, not literature-backed external anchors
- `tests/validation/test_phase_envelope_runtime_matrix.py`
  - runtime fixed-grid envelope checks on the minimum practical field-fluid
    roster, including `C7+` entry surfaces, against the standalone saturation
    workflows already validated by the saturation benchmark lane
- `tests/validation/test_vs_mi_pvt.py`
  - secondary MI PVT cross-check harness
- `tests/validation/test_phase_envelope_release_gates.py`
  - continuation topology and determinism gates

Recommended MI PVT envelope-generation roster:

- `docs/validation/mi_pvt_phase_envelope_roster.md`

## Remaining Gaps

Still needed before the continuation tracer can be treated as fully signed off:

- MI PVT phase-envelope exports for the current homework/default fluid with
  key points filled into the repo harness
- at least one richer multicomponent envelope benchmark with an external
  literature or commercial reference, not just a classroom workbook
- one characterized heavy-end case that exercises the continuation path after
  the runtime heavy-end surface is finalized
