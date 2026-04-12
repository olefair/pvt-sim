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

## Concurrency rule

Default posture:
- maximize safe parallelism
- do not allow cross-contamination across touched repo surfaces
- do not run overlapping concurrent work on the same repo surface unless a
  controller explicitly documents the coordination rule

## Dependency-map rule

`PVTSIM_DEPENDENCY_MAP.md` is the controller-owned operational map for:
- active work partitions
- touched repo surfaces
- dependency edges
- blocked edges
- serial-only/shared surfaces

If delegated or concurrent work changes scope, touched files, or dependency
ordering, update the dependency map before spawning more work or declaring the
map current.

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

## Bottom line

Read `AGENTS.md` for execution boundaries.
Read `docs/` for simulator reality.
Use `PVTSIM_DEPENDENCY_MAP.md` only for safe parallelization work.

