---
name: blueprint-implementer
description: >
  Three-phase autonomous feature implementation engine. Phase 1 exhaustively
  inspects every relevant file in the repository, builds a complete inventory and
  architecture map, then compares repo state to an uploaded implementation
  blueprint. Phase 2 iteratively edits the codebase using disciplined local
  inspection, editing, and verification loops, fixing failures until every
  success criterion passes and the full test suite is green. Phase 3 requires an
  independent audit, remediation from the persisted audit artifact, and repeated
  re-audit until the implementation genuinely passes. Use when the user wants to
  implement a feature from a blueprint or spec, do a gap analysis between repo and
  plan, autonomously build to spec, run implement-test-fix loops, or compare repo
  state to a design doc. Also trigger for phrases like "implement this blueprint",
  "build this spec", "what's missing from my repo vs this plan", or "make this
  pass all tests".

---

# Blueprint Implementer

Autonomous implementation engine: take an uploaded implementation blueprint (features, milestones, success criteria, file targets, test plan) and implement it in the codebase — methodically, verifiably, and with a mandatory external audit gate.

**Phase 1**: See clearly before touching anything (inspection + gap analysis).
**Phase 2**: Build correctly through disciplined edit-test-fix iteration.
**Phase 3**: Hand off to the auditor, remediate from the written audit artifact, and do not call the blueprint complete until audit PASS.

**Pete vault rule:** When the current workspace uses the Pete docs vault, read and follow `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`, `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`, `docs/reference/workspace/reference_workspace-conventions.md`, and `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`. Use the shared intake and backlink workflow from the last note for `links`, `related`, lineage fields, body wikilinks, and backlink fallback search when preloading blueprint context or emitting vault-native audit artifacts. The blueprint-specific rules below are deltas, not substitutes.

## MCP-Free Execution Rule

This skill must not depend on any MCP server. If later sections or linked
references mention legacy `repo_*` helper names, treat them as shorthand for
the equivalent local workflow using direct file reads, `rg`, directory
listings, `git diff` or `git log` when available, ordinary edit tools, and the
project's real test and syntax commands. Never stop or fail merely because a
repo MCP server is unavailable.

---

## Prerequisites

Confirm normal local repo access: you must be able to read files, search text,
edit files, run shell commands, and execute the project's real test or syntax
checks. Richer analysis tools are optional acceleration only; they are never a
gate.

## Working State

1. Record the blueprint path, repo root, current branch or status, baseline
   test command, and touched-file list before editing.
2. Refresh that working baseline after each milestone or when the scope shifts.
3. If helper analyzers exist, use them only as optional acceleration.

---

## Phase 1: Full Repository Inspection + Blueprint Gap Analysis

> **Detailed protocol:** [phase1-inspection.md](references/phase1-inspection.md)

### Why

Blueprints reference specific files, functions, and patterns. Guessing causes wrong edits and regressions. Phase 1 ensures you know exactly what exists before changing anything.

### High-level steps

1. **Full inventory** — Build a file manifest with `rg --files`, directory
   listings, and targeted reads of entrypoints, config, tests, and blueprint
   targets.
2. **Read every file that matters** — Every blueprint-referenced file, every related test file, every config file, and all files in the same directories as blueprint targets. Do not skip. State after each: "I've read [file]. Current behavior: [summary]."
3. **Map architecture** — Dependency graph, golden paths (e.g. request flow), integration points (routers, middleware, registries), test coverage.
4. **Parse blueprint** — Extract milestones, file targets, success criteria, test plan, repo anchors, and canonical frontmatter. See [blueprint-format.md](references/blueprint-format.md).
   - Treat canonical blueprint frontmatter as binding operational context, not decorative metadata
   - `links` and `external_links` are required preload; read them before editing code
   - `related` is adjacent context, not a substitute for `links`
   - `blocked_by` is gating dependency context; if the blueprint is `status: blocked`, surface the blockers and stop unless the user explicitly wants workaround work
   - `supersedes` and `superseded_by` are lineage fields; if the blueprint is superseded or archived and points at a successor, prefer the successor unless the user explicitly asked for historical execution
   - `project`, `implementer`, `repo`, `target`, `category`, and optional `parent_plan` define routing and scope and must shape the implementation plan
   - `completed` is historical metadata only; it is not proof that the current repo still satisfies the blueprint
5. **Verify anchors** — For each "anchor" the blueprint claims exists, verify
   it with direct file reads and `rg`. Flag discrepancies.
6. **Gap analysis** — For each milestone: what exists (with file:line), what's partial, what's missing, tests needed. Use this structure:

```
## Gap Analysis: [Blueprint Title]

### Milestone: [Name]
Status: NOT STARTED | PARTIAL | COMPLETE

#### Exists (verified):
- [file:line] — [what it does]

#### Missing:
- [what to create/modify]
- Depends on: [other milestones or code]

#### Tests needed:
- [test description] → [target test file]
```

7. **Proceed** — Output the gap analysis, compute implementation order (respecting dependencies), then go straight to Phase 2. No approval gate; the blueprint is the contract.

---

## Phase 2: Iterative Implementation Loop

> **Detailed protocol:** [phase2-implementation.md](references/phase2-implementation.md)

### Loop (per milestone, in dependency order)

For each gap item:

1. **PLAN** — Describe what and why.
2. **PRE-EDIT CHECK** — Read the target file, nearby wiring points, relevant
   tests, and local conventions before editing.
3. **READ** target file (current state).
4. **EDIT** — Surgical, minimal, using the normal local editing tools.
5. **POST-EDIT VERIFY** — syntax check → targeted tests → broader regression
   review using the project's real commands.
6. If pass → next gap item. If fail → analyze, fix, repeat from 4.

After all gaps in milestone:

8. **MILESTONE COMPLETE** — run the full relevant suite, review regressions,
   and sanity-check complexity and scope before declaring the milestone done.
9. If PASS → milestone complete. If FAIL → debug and re-verify.

### Rules

- **One change at a time** — One edit, then test. No batching edits then testing.
- **Read before every edit** — Re-read the file before each edit; state may have changed.
- **Syntax before test** — Don't run full suite if the file doesn't parse.
- **Targeted tests first** — Run tests for the edited module, then full suite.
- **Never ignore failing tests** — Regressions must be fixed before moving on.

### When stuck (e.g. test fails 3 times)

1. Re-read the failing test and the code path it exercises.
2. Check mental model vs actual code.
3. If still stuck: report to user — what you tried, what the test expects, what the code does, hypothesis.

### Done

- **Milestone complete**: All gap items done, new and pre-existing tests pass, syntax clean on all modified files.
- **Implementation complete**: All milestones done, full suite green, every "definition of done" criterion satisfied, and ready for audit.
- **Blueprint complete**: Implementation complete AND Phase 3 reaches audit PASS.

---

## Phase 3: Mandatory Audit + Remediation Loop

> **Detailed protocol:** [phase3-audit-loop.md](references/phase3-audit-loop.md)

When the code appears complete, stop self-grading. The blueprint is not done yet.

### Audit loop

1. Call `/audit-blueprint` with the blueprint path.
2. If the audit verdict is **FAIL**, read the persisted audit artifact under `docs/audits/blueprint-audits/` using the returned `latest` path.
3. Convert every item in `### Required fixes` into the next implementation queue.
4. Address the fixes in order using the same read-edit-verify discipline from Phase 2.
5. Re-run targeted tests, full suite, and regression checks.
6. Call `/audit-blueprint` again.
7. Repeat until the audit verdict is **PASS**.

### Rules

- Do **not** mark the blueprint complete, closed, or pending review before the audit passes.
- `### Required fixes` in the audit artifact are binding. `### Recommendations` are not.
- If the audit finds blueprint mismatches and independent quality gaps, address both. The second pass is not limited to the blueprint checklist.
- Do not claim a fix is addressed without changing the repo state the auditor called out.
- Closure is owned by the auditor decision gate, not by the implementer.

### Final report format

```  
## Implementation Report: [Blueprint Title]

### Milestones completed: [N/N]
### Audit iterations: [N]
### Latest audit doc: [path]
### Closure status: [AUTO-CLOSED | PENDING REVIEW]
### Files created: [list]
### Files modified: [list]
### Tests added: [list]

### Success criteria verification:
- [criterion 1]: PASS — [evidence]
- [criterion 2]: PASS — [evidence]

### Full test suite: PASS ([N] passed, [N] skipped)
### Notes: [anything the user should know]
```

---

## Edge Cases

- **Stale blueprint** — If referenced files/functions don't exist: "This blueprint appears to be for a different repo version. What doesn't match: [list]. Should I adapt to current state?"
- **Circular milestone dependencies** — Identify minimal subset of A to unblock B; implement that first.
- **No test plan in blueprint** — Propose tests from success criteria; every criterion should have at least one verifying test.
- **No existing tests** — Set up test infrastructure first (e.g. pytest for Python), then implement features.
- **Audit FAIL after code-complete** — Read the latest audit artifact, turn every required fix into queue items, and resume Phase 2 work from that queue.
