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
  owner / lane: Ole + Codex on `feat/stability-analysis-api`
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
- 2026-04-11: Promoted the validated desktop-contract slice to the canonical baseline on `feat/stability-analysis-api`.
