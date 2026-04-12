# AGENTS.md - PVT-SIM Canon Repo

This repo is the canonical implementation surface for PVT-SIM.

This file complements `CLAUDE.md`; it does not replace it.

## Startup

Before doing repo work here:
1. Read `CLAUDE.md`
2. If you are creating, managing, or auditing delegated/concurrent work, read `PVTSIM_DEPENDENCY_MAP.md`

## Concurrency rule

Default posture:
- maximize safe parallelism
- do not allow cross-contamination across touched repo surfaces
- do not run overlapping concurrent work on the same repo surface unless a controller explicitly documents the coordination rule

## Dependency-map rule

`PVTSIM_DEPENDENCY_MAP.md` is the controller-owned operational map for:
- active work partitions
- touched repo surfaces
- dependency edges
- blocked edges
- serial-only/shared surfaces

If delegated or concurrent work changes scope, touched files, or dependency ordering, update the dependency map before spawning more work or declaring the map current.

## Documentation boundary

Use repo-local docs for software-facing technical documentation.
Use the shared docs vault for cross-session coordination artifacts such as Directives, Plans, Blueprints, Audits, Handoffs, and shared Reports.

## Bottom line

Read `CLAUDE.md` first.
Use `PVTSIM_DEPENDENCY_MAP.md` for safe parallelization.
Keep concurrent work isolated by repo surface and dependency state.
