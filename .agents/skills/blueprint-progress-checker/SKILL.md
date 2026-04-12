---
name: blueprint-progress-checker
description: >
  Blueprint fidelity audit engine. Given implementation specs/blueprints in the
  repo, reads every spec requirement side-by-side with the actual code and
  produces an honest status report — not "does the file exist?" but "does the
  implementation actually match what the spec asked for?"

  Invoke with `/audit` or `/reality-check`.

  Use when the user wants to check blueprint progress, audit implementation
  fidelity, find what's left to build, see what's done vs remaining, prioritize
  remaining work, or get a status report on a feature. Trigger phrases: "how
  far along is this", "what's left", "check progress", "what's implemented",
  "status check", "what should I work on next", "prioritize remaining tasks",
  "reality check", "audit".
---

# Blueprint Progress Checker — Fidelity Audit Mode

You are a progress audit engine. Your job is to take implementation blueprints
and specs, compare them **requirement-by-requirement** against the actual code,
and produce an honest status report.

**Invoke with:** `/audit` or `/reality-check`

## The Lesson That Built This Skill

> A structural scan once reported 83% complete. The real number was 59%.
> "File exists" is not "spec implemented." "Keyword found in codebase" is not
> "requirement met." The only way to know if something is done is to read the
> spec and the code side-by-side.

## MCP-Free Execution Rule

This skill must not depend on any MCP server. If later sections or linked
references mention legacy `repo_*` helper names, treat them as shorthand for
the equivalent local workflow using direct file reads, `rg`, directory
listings, `git diff` or `git log` when available, ordinary edit tools, and the
project's real test commands. Never stop or fail merely because a repo MCP
server is unavailable.

---

## Workspace Docs Vault

When this skill reads from or writes to `docs/`, treat that directory as the
shared Obsidian vault rooted at `C:\Users\olefa\dev\pete-workspace\docs`, not
as a repo-local `docs/` folder inside an individual project repo or uploaded
snapshot. Treat YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body
linking as part of the operating contract, not optional formatting.

---

## Vault Output Contract

Full fidelity progress checks are evaluative artifacts. When persisted as
durable notes in the Pete docs vault, default to the audit family.

- Repo-scoped default: `docs/audits/code-reviews/audit_<repo>-blueprint-fidelity_<YYYY-MM-DD>.md`
- Cross-repo/workspace default: `docs/audits/workspace/audit_<slug>_<YYYY-MM-DD>.md`
- Template family: `docs/templates/template_audit-canonical_v1_2026-03-17.md`
- `audit_kind: quality-audit`
- `review_state: pending-review`
- `production_mode: generated`
- `produced_by: blueprint-progress-checker`
- `agent_surface`: use the actual Codex surface when the audit is machine-generated
- Required canonical audit fields still apply, including `repo` and `subject` for repo-scoped audits
- `subject` should identify both the blueprint and the implementation target being audited
- Put the governing blueprint note in `links:` and adjacent implementation notes or prior progress notes in `related:`

If the user explicitly wants a lightweight non-judgment status artifact
instead of a fidelity audit, a canonical report under
`docs/reports/progress/report_<slug>_<YYYY-MM-DD>.md` with
`report_kind: progress-report` is acceptable. Do not blur the two modes.

When the current workspace uses the Pete docs vault, also read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
audit-specific routing rules above are deltas, not substitutes.

---

## Core Principles

1. **Fidelity over existence.** Don't check if a file exists — read it and
   check if it does what the spec says it should do.

2. **Every "done" claim needs line-number evidence.** Not "function exists"
   but "function at line 234 implements X with Y and Z per the spec."

3. **Every gap must be specific.** Not "partially implemented" but "spec
   requires 6 config vars, 4 exist, `PETE_SPOKEN_MODEL` and
   `PETE_RESEARCH_MAX_PAGES` are completely absent."

4. **Structural scan is a first pass, not the answer.** Start with a quick
   manual inventory of file existence, obvious stubs, and keyword matches,
   then immediately deep-verify everything that scan suggests is "done."

5. **Tests that reference nonexistent features are broken, not passing.**
   A test file that exists but tests the wrong API is worse than no test.

---

## Workflow

### Step 0: Find the Blueprints

Look for spec/blueprint documents in these locations (in priority order):
- `docs/specs/*.md` — Feature specification documents
- `data/knowledge/PHASE*_ROADMAP.md` — Phase roadmaps
- `data/knowledge/PROGRESS.md` — Progress tracker
- Any file the user explicitly provides

Read ALL of them. Each spec becomes one or more milestones.

### Step 1: Parse Milestones from Specs

For each spec document, extract structured milestones:

- Parse canonical blueprint frontmatter first, when present, and treat it as
  binding operational context rather than decorative metadata:
  - `links` and `external_links` are governing context to preload before
    judging implementation fidelity
  - `related` is adjacent context to consult when a requirement or design
    choice refers to broader surrounding work
  - `blocked_by` defines gating dependencies; if the blueprint is blocked,
    report that constraint instead of overstating implementation readiness
  - `supersedes` and `superseded_by` define lineage; if the provided
    blueprint is superseded and a successor is available, prefer auditing the
    successor unless the user explicitly asked for historical state
  - `status` is a claim to verify, not proof that the implementation is
    actually complete or current
  - `project`, `repo`, `target`, `category`, `parent_plan`, and
    `strategic_role` define the implementation scope and how the resulting
    audit should be routed in the vault
  - `completed` is historical metadata only; never treat it as substitute
    evidence that the code satisfies the blueprint
- **Milestones**: Ordered list with IDs (M1, M2, etc.)
- **Per milestone:**
  - `new_files`: Files that should be created (path + description)
  - `modified_files`: Files that should be modified (path + expected functions)
  - `test_files`: Test files that should exist and pass
  - `requirements`: Every individual requirement from the spec (numbered)
  - `success_criteria`: Human-readable criteria for completion

> **Reference:** [blueprint-parsing.md](references/blueprint-parsing.md)

### Step 2: Structural Scan (Quick First Pass)

Run a quick manual structural scan against the parsed milestones. This gives you:
- Which files exist vs. don't
- Keyword-level heuristic matching
- A rough % per milestone

**CRITICAL: Treat this as a ceiling, not a score.** The structural scan
will almost always overestimate progress because:
- It counts "file exists" as progress even if the file is a stub
- It does keyword matching that doesn't verify actual behavior
- It can't tell if an implementation deviates from the spec's design

### Step 3: Fidelity Audit (THE CORE STEP)

This is where the real work happens. For EVERY milestone — not just the
ones marked "partial" — do a side-by-side comparison:

**Launch parallel subagents** (one per spec document) that each:

1. Read the spec document
2. Read each implementation file the spec references
3. For EVERY requirement in the spec, report:
   - The exact requirement text
   - Status: **YES** / **PARTIAL** / **NO** / **STUB**
   - Evidence: function name + file + line number (or "not found")
   - If PARTIAL: what specifically is present vs. missing
   - If there's a design deviation from the spec, describe it

4. Check for:
   - TODO/FIXME/pass/NotImplementedError in implementation files
   - Config variables mentioned in spec but absent from code
   - Test files that reference features that don't exist (broken tests)
   - Functions that exist but have different signatures than spec
   - Architectural deviations (spec says X pattern, code does Y)

5. Produce a **fidelity score** for the milestone:
   - Count requirements with YES / PARTIAL / NO / STUB
   - Fidelity % = (YES + 0.5*PARTIAL) / total requirements

**The fidelity score replaces the structural scan score.** If the
structural scan said 80% but fidelity audit says 45%, report 45%.

### Step 4: Prioritize Remaining Work

Prioritize the remaining items from Step 3 manually using a balanced ranking:
- dependency order first
- user-visible leverage second
- risk reduction third

State why each top item is ranked where it is.

### Step 5: Impact Analysis

For the top 5 highest-leverage remaining tasks, verify the leverage score by
tracing real usage with `rg`, import and registration reads, nearby tests, and
recent change history. Confirm the work actually touches live code rather than
dead helpers or stale references.

### Step 5.5: Regression Check & Health Audit (if implementation is in progress)

**Fast path:** If the repo includes a recent implementation report, milestone
checklist, or comparable progress artifact, compare it against the current code
and test state for a combined verdict.

**Manual path:** If a baseline snapshot exists:
1. Compare baseline and current test results for regressions
2. Review `git status`, `git diff --stat`, touched files, and obvious
   complexity growth for a manual health verdict

### Step 6: Present the Report

```
## Blueprint Fidelity Audit

**Specs Audited:** [list of spec docs]
**Overall Fidelity:** X% (structural scan claimed Y%)
**Milestones:** N complete / M partial / K not started
**Test Suite:** passing / failing / not run

### Completed (fidelity-verified)
- [M1] milestone name — all N requirements verified YES with evidence

### In Progress (with specific gaps)
- [M3] milestone name — fidelity: 65% (structural scan: 90%)
  Verified YES (N items):
    - [requirement]: [evidence with file:line]
  Gaps (M items):
    - [requirement]: [what's missing + effort estimate]
    - [requirement]: [design deviation description]

### Not Started
- [M5] milestone name — 0%
  Blocked by: [M3] (dependency)

### Recommended Next Steps (by leverage)
1. [task] — leverage: X — unblocks: [downstream tasks]
   Files: [paths]
   Effort: [estimate]
2. ...

### Corrections from Structural Scan
Items the structural scan marked as "done" that fidelity audit found
are actually incomplete:
- [item]: structural said DONE, fidelity found [gap]
```

---

## Usage Patterns

### `/audit` — Full fidelity audit
Full workflow — Steps 0 through 6.
This is the default and most useful mode.

### "What should I work on next?"
Steps 0-3 (find specs + parse + fidelity audit), then Step 4 (prioritize).
Present just the ranked remaining tasks.

### "Is milestone M3 done?"
Steps 0-3 focused on a single milestone.
Full fidelity audit on just that milestone.

### "What's blocking progress?"
Steps 0-3, then check which `not_started` milestones have dependencies
on `partial` milestones. Those partial items are the blockers.

---

## Effort Estimation Heuristics

| Situation | Estimate |
|-----------|----------|
| File missing entirely | Medium-Large: needs design + implementation |
| File exists, empty/stub | Medium: structure done, needs logic |
| File exists, some functions missing | Small-Medium: add specific functions |
| File exists, functions present but wrong behavior | Small-Medium: fix logic |
| File exists, all functions present but tests fail | Small: fix bugs |
| Spec requires config var, completely absent | Small: add to normalize.py |
| Test file missing | Small-Medium: write tests for existing code |
| Test file exists but tests wrong API | Medium: rewrite tests |
| Config/wiring missing | Small: add imports, register routes |
| Design deviation from spec | Medium: decide if refactor needed or spec should update |

"Small" = < 50 lines. "Medium" = 50-200 lines. "Large" = 200+ lines.

---

## Anti-Patterns to Avoid

1. **Never report structural scan percentages as the final answer.**
   Always run fidelity audit. Always.

2. **Never mark a milestone "complete" without reading the code.**
   File existence + keyword grep is not verification.

3. **Never skip milestones that the structural scan says are "complete."**
   Those are the most dangerous — false confidence.

4. **Never count broken tests as "test file exists."**
   If the test references features that don't exist in the implementation,
   the test is broken regardless of whether pytest collects it.

5. **Never average structural and fidelity scores.**
   Fidelity score wins. Period.
