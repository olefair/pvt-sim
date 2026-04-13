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

## Temporary Codex lane model

For the current assignment-phase Codex workflow, use the following operational
model:

- `main` is the canonical integration branch
- `integration root` is the only worktree allowed to perform branch-state
  operations affecting `main`
- accepted progress flows `lane worktree -> integration root -> main`
- lane worktrees refresh only from `main`
- lane-to-lane merges are not allowed

Default lane names:

- `gui`
- `thermo`
- `validation`
- `scratch`

Use these lane names when opening or updating active slices unless a controller
records an explicit exception.

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
- branch
- worktree
- touched repo surfaces
- forbidden / shared surfaces
- behind-main status
- last absorbed commit
- upstream dependencies
- blocked_by / blockers
- status
- last structural update

### Current active slices
- directive / task name: gui general UI fixes
  owner / lane: Ole + Codex on active `gui` lane
  branch:
  - planned `codex/gui`
  worktree:
  - pending dedicated `gui` worker bootstrap from current `main`
  touched repo surfaces:
  - `src/pvtapp/widgets/`
  - `src/pvtapp/style.py`
  - `src/pvtapp/main.py`
  - `tests/unit/test_pvtapp_*`
  forbidden / shared surfaces:
  - `AGENTS.md`
  - `PVTSIM_DEPENDENCY_MAP.md`
  - `.github/`
  - `pyproject.toml`
  - `requirements*.txt`
  - `src/pvtapp/assignment_case.py`
  - `src/pvtapp/component_catalog.py`
  - `src/pvtapp/job_runner.py`
  - `src/pvtapp/plus_fraction_policy.py`
  - `src/pvtapp/schemas.py`
  - `src/pvtcore/`
  - `tests/validation/`
  - `docs/validation/`
  behind-main status:
  - clean launch requested from current `main` controller baseline
  last absorbed commit:
  - none yet
  upstream dependencies:
  - starts from current `main`
  blocked_by / blockers:
  - none currently recorded
  status:
  - active and ready for worker spawn on general UI fixes
  coordination rule:
  - no other active lane conflicts are currently recorded
  - widen ownership only through an explicit controller update
  last structural update:
  - 2026-04-13

- directive / task name: phase-envelope kernel slice
  owner / lane: Codex background `thermo` lane
  branch:
  - planned `codex/phase-envelope`
  worktree:
  - `C:/Users/olefa/.codex/worktrees/phase-envelope-pvt-sim_canon`
  touched repo surfaces:
  - `src/pvtcore/envelope/`
  - `tests/unit/test_envelope.py`
  - `tests/unit/test_envelope_continuation.py`
  - `tests/validation/test_phase_envelope_release_gates.py`
  - `tests/validation/test_phase_envelope_runtime_matrix.py`
  forbidden / shared surfaces:
  - `AGENTS.md`
  - `PVTSIM_DEPENDENCY_MAP.md`
  - `.github/`
  - `pyproject.toml`
  - `requirements*.txt`
  - `src/pvtapp/`
  - `src/pvtcore/experiments/tbp.py`
  - `docs/tbp.md`
  behind-main status:
  - clean launch requested from current `main` controller baseline
  last absorbed commit:
  - none yet
  upstream dependencies:
  - starts from current `main`
  blocked_by / blockers:
  - none currently recorded
  status:
  - active background worker launch requested for one substantial envelope kernel slice
  coordination rule:
  - no overlap with the active `gui` surface
  - stop immediately if the slice needs `pvtapp` or shared surfaces
  last structural update:
  - 2026-04-13

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
- 2026-04-12: Reconciled the active mixed local lane onto `codex/validate-composition-across-modules` so fresh `phase-envelope` and `gui` follow-on branches can split cleanly from updated `main`.
- 2026-04-13: Refreshed the ledger to match the current operating model: `gui` is the active lane being launched from `main`, and no other active lane is currently recorded.
