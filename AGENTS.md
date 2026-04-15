# AGENTS.md - PVT-SIM Canon Repo

This repo is the canonical implementation surface for PVT-SIM.

This file is a repo-local execution adapter for coding agents. It is not the
canonical home for simulator architecture, equations, units, workflows, or
coding standards.

## Precedence

- Direct user instructions for the current task take priority over this file,
  unless they conflict with higher-level safety constraints.
- Durable simulator and development context lives in `README.md` and `docs/`.
  Do not treat agent-orientation files as the software source of truth.
- Verified code, config, and runtime behavior take precedence over stale docs.
  If drift is found, update the docs.

## Startup

Before non-trivial repo work here:
1. Read this file.
2. Use the repo docs as the canonical software reference, as needed:
   - `docs/architecture.md`
   - `docs/development.md`
   - `docs/runtime_surface_standard.md`
   - `docs/technical_notes.md`
   - `docs/numerical_methods.md`
   - `docs/input_schema.md`
   - `docs/units.md`
   - `docs/validation_plan.md`
3. If you are creating, managing, or auditing delegated/concurrent work, read
   `PVTSIM_DEPENDENCY_MAP.md`.

## Temporary Codex Orchestration Contract

This contract governs Codex behavior in this repository until the current
assignment phase is complete or this document is explicitly replaced.

### Purpose

The goal is to preserve the richest correct codebase with the least
coordination overhead.

Git is used here for auditability, rollback, synchronization, and controlled
integration. Elegant history is not the priority. Stable forward progress is.

### Core terms

- `main` is the canonical integration branch.
- `integration root` is the dedicated clean worktree attached to `main`.
- `lane` is a scoped implementation stream such as `gui`, `thermo`,
  `validation`, or `scratch`.
- `lane worktree` is a worker checkout used for implementation within one lane.

### Lane roster

- `gui`
- `thermo`
- `validation`
- `scratch`

### Operating model

This repo uses a controller-and-worker model.

- One controller thread acts as the command center.
- One clean integration root is reserved for `main` integration work.
- Worker lanes may use their own branch and worktree when isolation is
  warranted.
- No feature implementation occurs in the integration root.
- All accepted progress flows through `main`.

### Codex desktop branch rule

When operating in the Codex desktop app, default to one normal branch in the
current checkout.

- Do not create extra Git worktrees or occupy multiple lane branches from this
  repo unless the user explicitly asks for concurrent isolated work and accepts
  that plain branch switching in the current checkout will stop working while
  those worktrees exist.
- If the user wants one continuous implementation stream that spans thermo,
  runtime-surface, and GUI exposure work, keep that work on one branch instead
  of splitting it across lane worktrees.

### Integration-root rule

All branch-state operations involving `main` must be rooted through the
integration root.

The integration root is the only surface allowed to:
- reconcile with `main`
- absorb lane work into `main`
- run final publish verification for `main`
- push updates to `main`
- perform merge, rebase, cherry-pick, revert, or similar operations that
  affect `main`

There are no exceptions to this rule.

### Publish path

All accepted progress flows as follows:

`lane worktree -> integration root -> main`

No lane may merge directly into another lane. No lane may publish directly to
`main`. Other lanes refresh only from `main`.

### Roles

Controller thread:
- classifies work
- starts and directs workers
- prevents overlap
- decides when a lane has reached a checkpoint-ready slice
- routes refresh, absorb, and push operations through the integration root

Worker subagents:
- implement only within assigned scope
- do not broaden scope on their own
- do not make Git strategy decisions
- produce narrow, auditable deltas

Integrator:
- operates only through the integration root
- performs refresh, absorb, verification, and push operations affecting `main`
- never performs feature implementation

## Concurrency rule

Default posture:
- maximize safe parallelism
- do not allow cross-contamination across touched repo surfaces
- do not run overlapping concurrent work on the same repo surface unless a
  controller explicitly documents the coordination rule
- do not perform any `main`-affecting Git operation outside the integration
  root

Parallel work is allowed only when repo-touch overlap is low enough to be
safe.

If overlap is discovered after work begins, stop the later task and escalate
to the controller.

## Dependency-map rule

`PVTSIM_DEPENDENCY_MAP.md` is the controller-owned operational map for:
- active work partitions
- touched repo surfaces
- lane ownership and touched surfaces
- active lane branch / worktree state
- behind-`main` status and last absorbed commit
- dependency edges
- blocked edges
- serial-only/shared surfaces

If delegated or concurrent work changes scope, touched files, or dependency
ordering, update the dependency map before spawning more work or declaring the
map current.

## Shared / Serial-only Surfaces

These are controller-only unless explicitly reassigned:

- `AGENTS.md`
- `PVTSIM_DEPENDENCY_MAP.md`
- `.github/`
- `pyproject.toml`
- `requirements*.txt`
- repo-wide workflow documentation
- branch and worktree lifecycle operations
- merge, rebase, cherry-pick, revert, and push operations
- broad refactors spanning multiple lanes

## Checkpoint Cadence

Workers must not accumulate large unpublished deltas.

When a lane reaches a coherent, verified slice, absorbing that slice into
`main` should be treated as the default next step rather than postponed
cleanup.

A coherent slice includes:
- a completed bug fix
- a user-visible improvement
- a completed small feature slice
- a verified refactor step
- any test-backed state worth preserving

### Pragmatic Verification Rule

Do not block checkpointing or integration on a pristine working tree or a
fully green full-suite run.

- Prefer the smallest relevant verification for the touched surface.
- Known failures or incomplete slices are acceptable if they are called out
  explicitly.
- Preserve forward progress first; tighten correctness iteratively instead of
  turning every checkpoint into a full cleanup pass.

## Worker Boundaries

Workers may:
- implement scoped changes
- create lane-local commits
- run the smallest relevant verification for their assigned work

Workers may not:
- touch shared or serial-only surfaces unless explicitly told to
- merge into `main`
- push to `main`
- reconcile branch state involving `main`
- merge lane-to-lane
- choose branch or worktree strategy on their own

## Escalation

Stop and escalate to the controller when:
- scope expands beyond the assigned lane
- overlap with another active lane is discovered
- shared or serial-only surfaces are required
- another lane must be touched
- a Git decision affecting `main` is needed
- verification suggests cross-lane impact

## Output Contract

Worker closeout must contain only:
- changed files
- what changed
- verification run
- blocker or residual risk

## Documentation boundary

- Keep repo execution rules in `AGENTS.md`.
- Keep software-facing technical documentation in `README.md` and `docs/`.
- Keep cross-session coordination artifacts in the shared docs vault, not in
  this repo.

## Runtime Surface Rule

For app/runtime work, enforce `docs/runtime_surface_standard.md`.

Do not leave domain-level simulator features stranded in side-library paths
while the desktop runtime executes a narrower or materially different method
without explicit documentation and user-facing disclosure.

## Cursor Cloud specific instructions

### Environment

- Python 3.12, venv at `.venv`.
- Install surface for development: `pip install -e '.[gui,dev]'`.
- PySide6 (Qt) requires system libraries for xcb: `libegl1 libgl1 libopengl0
  libxkbcommon0 libxkbcommon-x11-0 libdbus-1-3 libfontconfig1 libxcb-xinerama0
  libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0
  libxcb-render-util0 libxcb-shape0 libxcb-xfixes0`. These are pre-installed
  in the snapshot.
- GUI and GUI-dependent tests require a display. Use `xvfb-run -a` or start
  `Xvfb :99` and export `DISPLAY=:99`.

### Running tests

- `pytest` runs the default ~1100-test suite (unit + contracts + validation).
  Expect ~13 min wall time — phase envelope tests dominate (~500 s total due
  to repeated `calculate_phase_envelope` calls without fixture caching in
  `tests/unit/test_envelope.py`).
- For fast iteration, target specific test files or directories:
  `pytest tests/unit/test_flash.py` (< 1 s).
- GUI contract tests are opt-in: `pytest --run-gui-contracts`.
- 9 pre-existing test failures on `main` as of 2026-04-15 (dew
  characterization, thermopack envelope, stability robustness, flash fixture
  invariants, MI PVT bubble point). These are known; do not block on them.

### Running the application

- CLI: `pvtsim run examples/pt_flash_config.json` or `pvtsim validate <config>`.
  See `README.md` for entry points.
- GUI: `DISPLAY=:99 pvtsim-gui` (after starting Xvfb).

### Linting

- `black --check src/ tests/` — formatting (many files currently unformatted).
- `flake8 src/ --max-line-length=120` — style.
- `mypy` and `pylint` are installed but not routinely run clean on the full
  codebase.

## Bottom line

Read `AGENTS.md` for execution boundaries.
Read `docs/` for simulator reality.
Use `PVTSIM_DEPENDENCY_MAP.md` only for safe parallelization work.
