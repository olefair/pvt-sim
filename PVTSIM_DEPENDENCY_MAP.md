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
- directive / task name: gui runtime follow-on lane
  owner / lane: Ole + Codex on planned `codex/gui`
  touched repo surfaces:
  - `src/pvtapp/`
  - `tests/unit/test_pvtapp_*`
  - `tests/unit/test_cli_validate.py`
  - `README.md`
  - `docs/development.md`
  - `docs/runtime_surface_standard.md`
  - `examples/pete665_assignment_case.json`
  - `scripts/run_pete665_assignment.py`
  - `scripts/validate_modules.py`
  upstream dependencies:
  - starts from the 2026-04-12 merged mainline baseline prepared from `codex/handoff-external-validation`
  - phase-envelope solver work must be consumed through the stable runtime contract, not by parallel edits inside `src/pvtcore/envelope/`
  blocked_by / blockers:
  - none currently recorded
  status:
  - declared for immediate dedicated worktree creation from updated `main`
  coordination rule:
  - keep this lane out of `src/pvtcore/envelope/`, `tests/validation/test_phase_envelope_*`, and `tests/validation/test_vs_*` unless a controller records an explicit shared-surface serialization rule
  last structural update:
  - 2026-04-12

- directive / task name: phase-envelope continuation correction + external comparison lane
  owner / lane: Ole + Codex on `codex/phase-envelope`
  touched repo surfaces:
  - `src/pvtcore/envelope/`
  - `tests/unit/test_envelope_*`
  - `tests/unit/test_pvtapp_phase_envelope_workflow.py`
  - `tests/validation/test_phase_envelope_*`
  - `tests/validation/test_vs_mi_pvt.py`
  - `tests/validation/test_vs_prode.py`
  - `tests/validation/test_vs_thermopack.py`
  - `tests/validation/mi_pvt/`
  - `tests/validation/prode/`
  - `tests/validation/thermopack/`
  - `scripts/debug_phase_envelope_roots.py`
  - `docs/validation/phase_envelope_validation_matrix.md`
  - `docs/validation/mi_pvt_phase_envelope_roster.md`
  upstream dependencies:
  - starts from the same 2026-04-12 merged mainline baseline
  - owns the carried local continuation checkpoint preserved on `codex/phase-envelope`
  - saturation authority and external-corpus ingestion remain upstream references, but critical-point alignment and release-gate/runtime-matrix certification are owned here
  blocked_by / blockers:
  - the continuation/ThermoPack critical-point mismatch remains unresolved
  - release-gate and runtime-matrix certification still need a fresh pass after follow-on solver changes
  status:
  - active on dedicated branch; worktree creation pending
  coordination rule:
  - do not run overlapping GUI edits in `src/pvtapp/` while this lane changes runtime-exposed solver semantics unless the controller records file-level serialization first
  - if solver semantics require GUI/runtime disclosure changes, land them back through `main` after both lanes agree on the contract
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
- 2026-04-12: Retired the mixed cleanup slice after preserving the local continuation checkpoint on `codex/phase-envelope` and declaring dedicated `gui` and `phase-envelope` follow-on lanes.
