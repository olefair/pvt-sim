# PVTSIM_DEPENDENCY_MAP.md

This is the canonical live dependency and concurrency map for PVT-SIM.

## Purpose

Use this file to keep delegated and concurrent PVTSim work:
- safely parallelized
- partitioned by touched repo surface
- explicit about dependency ordering
- resistant to cross-contamination
- reviewable from files instead of chat memory

## Canonical role

This file is the controller-owned operational source of truth for:
- active work partitions
- touched repo surfaces
- blocked or upstream dependency edges
- shared / serial-only surfaces
- concurrency-safe decomposition

If this file and any pointer note disagree, this file wins.

## Read this when

Read/update this file when:
- creating a new delegated overseer or worker
- deciding whether work can run concurrently
- changing task scope or touched repo surfaces
- discovering a new blocker or dependency edge
- pausing, completing, merging, or superseding active work

## Parallelization doctrine

Default to the **highest safe level of parallelism**.

Do **not** keep independent work serial by default just because it is easier to manage.

The limiting factors are:
- repo-touch overlap
- dependency coupling
- shared/serial-only surfaces
- checkpoint/audit burden

## Provisional parallel partitions

These are the initial high-level concurrency partitions for Phase 1. Refine them as the real work proves a better split.

### 1. Characterization / correlations
Primary surfaces:
- `src/pvtcore/characterization/`
- `src/pvtcore/correlations/`

### 2. Thermo / EOS / flash / envelope / properties
Primary surfaces:
- `src/pvtcore/eos/`
- `src/pvtcore/stability/`
- `src/pvtcore/flash/`
- `src/pvtcore/envelope/`
- `src/pvtcore/properties/`
- related tests that touch those systems

### 3. Units / core numerics / models
Primary surfaces:
- `src/pvtcore/core/`
- `src/pvtcore/models/`

### 4. Validation / experiments
Primary surfaces:
- `src/pvtcore/experiments/`
- validation-focused tests, fixtures, and evidence

### 5. Confinement / tuning
Primary surfaces:
- `src/pvtcore/confinement/`
- `src/pvtcore/tuning/`

### 6. App / UI / IO
Primary surfaces:
- `src/pvtapp/`
- `src/pvtcore/io/`

These are **not eternal doctrine**. They are the initial operational partitions to help delegation stay fast and safe.

## Shared / serial-only surfaces

Treat these as serial-only or explicitly coordinated unless a controller says otherwise:
- `pyproject.toml`
- `requirements.txt`
- `requirements-dev.txt`
- top-level packaging / install / environment files
- broad architectural docs that redefine repo-wide structure
- repo-wide import or typing changes that cut across multiple partitions
- any task that materially changes multiple partitions at once

## Active work ledger

Use this section to record real active delegated slices.

For each active slice, include:
- directive / task name
- owner / lane
- touched repo surfaces
- upstream dependencies
- blocked_by / blockers
- status
- last structural update

### Current active slices
- directive / task name: canonical pvtapp shell + desktop contract baseline
  owner / lane: Ole + Codex on `main`
  touched repo surfaces:
  - `.github/workflows/smoke.yml`
  - `.gitignore`
  - `src/pvtapp/capabilities.py`
  - `src/pvtapp/job_runner.py`
  - `src/pvtapp/main.py`
  - `src/pvtapp/style.py`
  - `src/pvtapp/workers.py`
  - `src/pvtapp/widgets/`
  - `tests/unit/test_pvtapp_*`
  - `tests/unit/test_cli_validate.py`
  - `README.md`
  - `docs/packaging.md`
  - `docs/tbp.md`
  - `docs/tuning.md`
  - `pyproject.toml`
  - `data/pure_components/components.json`
  - `AGENTS.md`
  - `PVTSIM_DEPENDENCY_MAP.md`
  upstream dependencies:
  - keep `src/pvtcore/` thermodynamics untouched while the app shell is still settling
  - align the desktop contract before promoting more calculation types or EOS choices into the GUI
  - shared-surface caution applies because `pyproject.toml` is already in flight in this slice
  blocked_by / blockers:
  - none currently recorded
  status:
  - validated checkpoint baseline on the canonical branch
  coordination rule:
  - do not spawn overlapping app-shell, desktop-contract, or packaging work until new issue-scoped follow-on slices are declared from this baseline
  last structural update:
  - 2026-04-11

- directive / task name: saturation validation lane unification
  owner / lane: Codex in current thermo-validation thread
  touched repo surfaces:
  - `src/pvtcore/flash/bubble_point.py`
  - `src/pvtcore/flash/dew_point.py`
  - `src/pvtcore/validation/external_corpus.py`
  - `tests/validation/test_saturation_equation_benchmarks.py`
  - `tests/validation/test_plus_fraction_dew_characterization.py`
  - `tests/validation/test_plus_fraction_bubble_characterization.py`
  - `tests/validation/test_phase_envelope_runtime_matrix.py`
  - `tests/validation/test_external_corpus_schema.py`
  - `tests/validation/test_vs_mi_pvt.py`
  - `tests/validation/mi_pvt/README.md`
  - `docs/validation/bubble_point_validation_matrix.md`
  - `docs/validation/dew_point_validation_matrix.md`
  - `docs/validation/phase_envelope_validation_matrix.md`
  - `docs/validation/mi_pvt_phase_envelope_roster.md`
  - `docs/validation_plan.md`
  - `src/pvtapp/job_runner.py`
  - `src/pvtapp/main.py`
  - `src/pvtapp/schemas.py`
  - `src/pvtapp/widgets/composition_input.py`
  - `src/pvtapp/widgets/conditions_input.py`
  - `src/pvtapp/widgets/results_view.py`
  - `src/pvtapp/widgets/text_output_view.py`
  - `src/pvtapp/widgets/diagnostics_view.py`
  - `tests/unit/test_pvtapp_conditions_input.py`
  - `tests/unit/test_pvtapp_desktop_contract.py`
  - `tests/unit/test_pvtapp_runtime_contract.py`
  - `tests/unit/test_pvtapp_remaining_workflows.py`
  - `tests/unit/test_pvtapp_zero_fraction_duplicates.py`
  - `tests/unit/test_saturation.py`
  upstream dependencies:
  - the 2026-04-11 desktop-contract baseline remains the upstream runtime shell baseline for any app-surface changes
  - bubble-point and dew-point authority, robustness, and GUI honesty are treated as one saturation lane because the solver methods and failure semantics are intentionally mirrored
  - external-data ingestion and corpus acquisition remain required before full physical-accuracy signoff
  blocked_by / blockers:
  - no measured external pure-component saturation anchors have been entered yet
  - no measured external rich-fluid `C1`-`C6` + `C7+` bubble/dew anchors have been entered yet
  - MI-PVT or literature envelope overlays for the current runtime matrix roster are still secondary/manual, not fully ingested
  status:
  - handoff-ready; internal solver/runtime and practical family coverage established, external-authority lane still open
  coordination rule:
  - do not split bubble and dew saturation validation into separate concurrent slices unless the controller records a file-level partition first
  - if app result surfaces are touched, keep the runtime semantics aligned with the same certificates and failure states exposed by the thermo layer
  last structural update:
  - 2026-04-12

- directive / task name: runtime surface consolidation + assignment validation expansion
  owner / lane: Ole + Codex on `codex/handoff-external-validation`
  touched repo surfaces:
  - `AGENTS.md`
  - `README.md`
  - `docs/development.md`
  - `docs/runtime_surface_standard.md`
  - `docs/runtime_surface_consolidation_blueprint.md`
  - `docs/validation/`
  - `examples/pete665_assignment_case.json`
  - `scripts/audit_component_aliases.py`
  - `scripts/debug_phase_envelope_roots.py`
  - `scripts/run_pete665_assignment.py`
  - `scripts/validate_modules.py`
  - `src/pvtapp/assignment_case.py`
  - `src/pvtapp/component_catalog.py`
  - `src/pvtapp/job_runner.py`
  - `src/pvtapp/main.py`
  - `src/pvtapp/plus_fraction_policy.py`
  - `src/pvtapp/schemas.py`
  - `src/pvtapp/widgets/`
  - `src/pvtcore/envelope/`
  - `src/pvtcore/experiments/cce.py`
  - `src/pvtcore/flash/bubble_point.py`
  - `src/pvtcore/flash/dew_point.py`
  - `src/pvtcore/io/data_io.py`
  - `src/pvtcore/models/component.py`
  - `src/pvtcore/validation/`
  - `tests/unit/test_envelope_*`
  - `tests/unit/test_pete665_assignment.py`
  - `tests/unit/test_pvtapp_*`
  - `tests/unit/test_saturation.py`
  - `tests/unit/test_validation_backend_registry.py`
  - `tests/validation/mi_pvt/`
  - `tests/validation/prode/`
  - `tests/validation/thermopack/`
  - `tests/validation/test_phase_envelope_release_gates.py`
  - `tests/validation/test_phase_envelope_runtime_matrix.py`
  - `tests/validation/test_plus_fraction_bubble_characterization.py`
  - `tests/validation/test_plus_fraction_dew_characterization.py`
  - `tests/validation/test_saturation_equation_benchmarks.py`
  - `tests/validation/test_vs_mi_pvt.py`
  - `tests/validation/test_vs_prode.py`
  - `tests/validation/test_vs_thermopack.py`
  upstream dependencies:
  - the 2026-04-11 desktop-contract baseline remains the app/runtime shell baseline
  - the 2026-04-12 saturation-validation lane remains upstream for bubble/dew authority and external-corpus intake
  - runtime-surface honesty must stay aligned with `docs/runtime_surface_standard.md`
  blocked_by / blockers:
  - a fresh targeted verification pass is still required before declaring the branch clean
  - full-suite status remains intentionally unknown unless explicitly requested
  status:
  - dirty-worktree cleanup in progress; preparing one coherent checkpoint commit
  coordination rule:
  - do not run overlapping edits across `src/pvtapp/`, `src/pvtcore/flash/`, `src/pvtcore/envelope/`, `src/pvtcore/validation/`, and validation docs until this cleanup checkpoint lands
  last structural update:
  - 2026-04-12

## Dependency refresh protocol

Refresh this file immediately when any of the following happens:
1. before spawning a new concurrent slice
2. after a task claims new touched repo surfaces
3. when a new blocker or dependency edge is discovered
4. when two slices merge or split
5. when a slice moves from active -> blocked / paused / complete
6. when shared or serial-only surfaces change

## Stale-map rule

This map is stale if any of the following is true:
- an active delegated slice is missing from the ledger
- touched repo surfaces no longer match current reality
- a blocker/dependency changed without an update here
- concurrent lane ownership changed without an update here
- the last structural update predates a material task split, merge, or handoff

If the map is stale, refresh it before creating more parallel branches where overlap risk is nontrivial.

## No-overlap rule

Do not run concurrent delegated work against the same repo surface unless the controller explicitly records:
- why the overlap is acceptable
- which files or subpaths each slice owns
- what serialization / coordination rule is in effect

## Change log

- 2026-04-08: Initial controller-owned dependency-map scaffold created.
- 2026-04-09: Recorded the active local pvtapp + packaging slice and flagged shared-surface coordination.
- 2026-04-11: Expanded the active local slice to include `job_runner.py`, `capabilities.py`, and desktop contract alignment work.
- 2026-04-11: Promoted the validated desktop-contract slice to the canonical baseline on `main`.
- 2026-04-12: Added the unified saturation-validation lane so bubble-point and dew-point authority, robustness, and GUI honesty stay in one controlled surface.
- 2026-04-12: Added the runtime-surface consolidation + assignment validation expansion slice to capture the current branch scope while the dirty worktree is being cleaned for commit.
