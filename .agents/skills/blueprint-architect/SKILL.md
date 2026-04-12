---
name: blueprint-architect
description: >
  Deep repository analysis and blueprint generation. Uses direct repository
  inspection, code reading, search, git history, and test discovery to build a
  complete picture of a codebase: file inventory, dependency shape, coupling
  and risk analysis, hotspot history, and dead-code candidates. Compares repo
  state against an uploaded spec or blueprint to produce a verified,
  implementation-ready blueprint document. Use when the user wants to analyze
  repository architecture, understand how code connects, find high-risk areas,
  assess change impact, generate an implementation blueprint from a spec, audit
  before changes, find dead code, or map what needs to happen before
  implementing a feature. Trigger for "analyze this repo", "map the
  architecture", "what would break if I change X", "generate a blueprint",
  "find the riskiest files", "show me how things connect", or "what's dead
  code in here".
---

# Blueprint Architect

Repository analysis and blueprint generation engine: deeply understand a codebase — connections, risks, dead ends — and produce verified, actionable implementation blueprints that blueprint-implementer can execute.

**Principle:** You cannot design what you do not understand, and you cannot understand what you have not measured. Every claim must be backed by tool output; every risk must have data; every blueprint section must trace to something you read.

**Workspace docs vault:** In this workspace, `docs/` means the shared
Obsidian vault rooted at `C:\Users\olefa\dev\pete-workspace\docs`, not a
repo-local `docs/` folder inside an individual project repo or uploaded
snapshot. Treat YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body
linking as part of the operating contract whenever reading or writing notes
there.

**Pete vault rule:** When the current workspace uses the Pete docs vault, read and follow `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`, `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`, `docs/reference/workspace/reference_workspace-conventions.md`, and `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`. Use the shared intake and backlink workflow from the last note for `links`, `related`, lineage fields, body wikilinks, and backlink fallback search when reading or emitting blueprint notes. The blueprint-specific rules below are deltas, not substitutes.

## MCP-Free Execution Rule

This skill must not depend on any MCP server. If later sections or linked
references mention legacy `repo_*` helper names, treat them as shorthand for
the equivalent local workflow using direct file reads, `rg`, directory
listings, `git diff` or `git log` when available, ordinary edit tools, and the
project's real test commands. Never stop or fail merely because a repo MCP
server is unavailable.

---

## Working State

1. Record the repo root, current branch or status, relevant test commands, and
   the blueprint or spec path before starting.
2. Update that working baseline whenever scope changes or you discover a new
   risk cluster or dependency.
3. If richer analysis tooling exists, treat it as optional acceleration only.

### Fast-path

For "analyze this repo", start with a shell-first sweep: `rg --files`,
top-level directory listing, targeted reads of likely entrypoints, and a quick
recent-history pass from git when available. Deepen from there only where the
evidence points.

---

## Analysis Workflow

Follow phases in order. Each phase builds on the previous.

### Phase 1: Structural Inventory

> **Detailed protocol:** [structural-analysis.md](structural-analysis.md)

**Goal:** Know what exists — every file, directory, language.

1. Build a file manifest with `rg --files`, directory listings, and quick file
   counts by area or language.
2. Walk the directory structure directly to identify app, tests, config,
   scripts, docs, and registration surfaces.
3. Infer conventions by reading representative source files, test files, config
   files, and entrypoints. New code in blueprints MUST match those conventions.
4. Note language distribution (import parsers, test frameworks).
5. Flag large files (> 500 lines) — high-risk candidates.

**Output:** Inventory summary + conventions report. Conventions become a mandatory constraint for Phase 5.

### Phase 2: Dependency & Impact Mapping

> **Detailed protocol:** [dependency-analysis.md](dependency-analysis.md)

**Goal:** How code connects — file-level and symbol-level.

1. Trace file-level imports and registrations by reading imports, exports, app
   setup, routers, plugin registries, and config loaders directly.
2. Trace symbol-level blast radius with `rg` callsite searches plus targeted
   code reading for the functions and classes the user cares about.
3. Estimate coupling from fan-in, fan-out, shared utilities, and repeated
   co-location in critical flows; explicitly call out uncertainty where it is
   manual rather than computed.
4. Use `git log --stat`, recent diffs, or file timestamps when available to
   identify hotspots and recent change concentration.
5. Flag dead-code candidates only after searching for callsites, registrations,
   dynamic references, and tests.

**Output:** Risk-ranked map: hub files, fragile files, clusters, hotspots, dead code.

### Phase 2.5: Test Landscape

1. Inspect the test tree, coverage config, test naming conventions, and nearby
   test files to understand framework and coverage shape.
2. Use that map for the blueprint: new code touching uncovered files should add
   coverage; new tests must follow detected framework and fixture patterns.

**Output:** Test landscape report for Phase 5 milestone planning.

### Phase 3: Deep File Reading

**Goal:** Read high-importance files, not just metadata.

From Phase 2 results: read every high-risk/hub/god file, every file that would be touched by planned changes, relevant test files, config files. State what you read; don't assume. Note signatures, class hierarchies, decorators, config, error handling.

**Output:** Deep understanding; you can make evidence-based claims.

### Phase 4: Blueprint Gap Analysis (if spec/blueprint provided)

**Goal:** Compare spec vs repo.

1. Parse document for anchors (paths, function names, endpoints, config). See [blueprint-format.md](blueprint-format.md).
2. Verify anchors manually with direct file reads and `rg` searches for the
   referenced paths, symbols, endpoints, configs, and tests.
3. Per anchor: **verified** = exists as claimed; **missing** = blueprint stale or feature to create; **drifted** = file exists but contents don't match.
4. Cross-reference missing/drifted with impact graph for ripple effects.

**Output:** Verified gap analysis — what's real, stale, new.

### Phase 5: Blueprint Generation (Dynamic Ordering)

**Goal:** Complete, verified blueprint with milestones ordered by dependency topology and impact leverage, then emit it as a canonical vault blueprint note. See [canonical-blueprint-template.md](references/canonical-blueprint-template.md).

**Step 5a — Draft milestones:** Group into milestones: new_files, modified_files, test_files, success_criteria. Heuristics: tightly-coupled files (from Phase 2) in same milestone; each milestone independently testable; no milestone that can only be verified after later ones.

**Step 5b — Order dynamically:** Order milestones manually by dependency
topology, wiring risk, and verification leverage. Work leaf modules before
shared hubs where possible, and explicitly note any cycles or uncertainty.

**Step 5c — Canonicalize metadata:** Before rendering, determine the full vault metadata contract:

- `project` — canonical workspace enum
- `implementer` — canonical agent lane
- `repo` — actual repo name
- `target` — concrete implementation surface
- `category` — canonical category enum
- optional `strategic_role`
- optional `parent_plan`
- `links`, `related`, `external_links`, `blocked_by`, `supersedes`, `superseded_by`
- `context`, `in_scope`, `out_of_scope`, `constraints`, `risks_and_dependencies`

Do not leave naming or placement implicit. New blueprints must use canonical lowercase enums and must not use dated filenames.

**Step 5d — Render canonical blueprint:** Write the canonical blueprint note
manually using the required metadata above plus title, goal, repo anchors, and
ordered milestones. Use the derived vault path
`docs/blueprints/<implementer>/<project>/blueprint_<slug>.md` when writing to
the Pete docs vault. Do not invent alternate blueprint directories, filenames,
or frontmatter shapes.

**Output:** Canonical implementation blueprint note, ready for blueprint-implementer.

### Phase 6: Snapshot for Baseline

Capture a baseline before implementation using `git status`, `git diff`,
relevant test output, and a written list of in-scope files. The implementer can
compare against that baseline after the build.

---

## Usage Patterns

- **"Analyze this repo"** — Phases 1–3. Present risk map, hub files, coupling, dead code.
- **"What would break if I change X?"** — Phase 2 with `target_symbols=["X"]` on impact graph; cross-reference coupling and hotspot history.
- **"Generate a blueprint for this spec"** — All 6 phases; spec drives Phase 4–5.
- **"Find the riskiest files"** — Phase 2 (coupling_analysis + hotspot_history); high-coupling + high-churn.
- **"Map the architecture"** — Phases 1–2; dependency and impact graphs; hub symbols and god files as backbone.

---

## Handoff to Blueprint Implementer

1. Architect produces a canonical vault blueprint note (Phase 5) and baseline snapshot (Phase 6).
2. Implementer reads blueprint, re-verifies anchors, executes.
3. After implementation, diff snapshot to verify changes.

Architect does not edit source code. The only file it should write is the blueprint artifact itself.
