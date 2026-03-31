# Phase 2: Iterative Implementation Protocol

Turn the Phase 1 gap analysis into working, tested code.

**Principle:** Small changes, verified constantly. Every edit gets a syntax check; every syntax-clean edit gets tests; every failure gets fixed before moving on.

---

## Implementation Queue

Convert gap analysis (MISSING, PARTIAL, DISCREPANCY) into an ordered queue:

1. **Infrastructure first** — Test framework, __init__.py, config scaffolding.
2. **Models and types** — Data structures, schemas, type definitions.
3. **Core logic** — Business logic, algorithms.
4. **Integration points** — Routers, registries, entry points.
5. **Tests** — New and updated tests.
6. **Config/data** — YAML, JSON, etc.

Within each, respect dependency order from gap analysis.

---

## Edit-Test-Fix Cycle (per queue item)

### Step 1: Announce intent
State: Implementing [item], target file [path], strategy (create | edit | add), reason.

### Step 2: Read and preview
- Re-read the target file directly because it may have changed. For new files, read the directory and neighboring files for conventions.
- **Pre-edit:** identify the symbols to add, modify, remove, or call; estimate blast radius from imports, callsites, registrations, and nearby tests. If the change is high risk, tighten the plan before editing.
- **Wiring:** Find registration points by reading routes, plugins, imports, startup code, and config. Don't guess.

### Step 3: Edit
- **New file:** create it with full imports, local conventions, and real implementation (no TODO placeholders).
- **Existing:** make surgical edits that preserve surrounding style and only change what the milestone requires.
- **Multiple edits to one file:** One edit at a time → syntax check → next edit → … → then tests.

### Step 4: Syntax check
Run the project's real syntax, lint, or type check for the touched file. If it fails: read the error, read the file, fix it, and re-check until clean. Watch for missing imports, indentation, unclosed brackets, and signature drift.

### Step 5: Targeted tests
Run the project's real targeted tests for the edited module and blueprint tests. Then run the broader suite or the relevant verification command for the repo.

### Step 5.5: Regression check
After the broader test pass, compare against the baseline from session start. If any regressions appear in tests, behavior, or touched-file scope, stop and fix them before the next item.

### Step 6: Handle results
- **All pass, no regressions** → Next item.
- **New test fails** → Read test and error; fix implementation or test; re-check syntax and tests.
- **Pre-existing test fails (regression)** → Find where edit broke behavior; fix without undoing intent; if conflict, report to user.
- **Infrastructure error** — Imports, __init__.py, fixtures; fix and re-run.

---

## Debug (test fails 3+ times)

1. Read full test (setup, fixtures, teardown).
2. Trace code path step by step.
3. Check imports, types, side effects (mocks, DB).
4. Search for similar passing tests; copy pattern.
5. After ~5 attempts: report to user (test, implementation, error, attempts, hypothesis).

---

## Milestone Completion

When all queue items for a milestone are done:

1. Run the broader test command and syntax check every created or modified file.
2. For each success criterion: which test(s) verify it; confirm they pass; if no test, flag.
3. Output: "Milestone [name]: COMPLETE — Files created/modified, tests passing, success criteria N/N."
4. Proceed to next milestone.

---

## Full Implementation Completion (Pre-Audit)

1. Run full suite; syntax check all touched files.
2. Walk every "definition of done" criterion with evidence (test name, path, behavior).
3. Hand off to `/audit-blueprint`. The blueprint is not complete until the audit phase returns PASS.
4. If the audit FAILS, read the latest persisted audit doc in `docs/audits/blueprint-audits/`, convert `### Required fixes` into the next queue, and resume the edit-test-fix loop.

**Pre-audit implementation report:**
```
## Implementation Report: [Blueprint Title]
### Status: CODE COMPLETE (AWAITING AUDIT)
### Milestones: [N/N]
### Files created: [path — purpose]
### Files modified: [path — what changed]
### Tests: New [N] in [N] files; Modified [N]; Full suite N passed, N skipped, 0 failed
### Success criteria: [criterion]: PASS — [evidence] ...
### Regressions: None
### Notes: [notable]
```

---

## Constraints

- **pytest:** Assumed for Python (`python -m pytest -v --tb=short`). Other languages: use available syntax check (e.g. PowerShell, JSON, YAML).
- **Surgical edits:** Change only what's needed; don't rewrite whole files.
- **Conventions:** Match import style, naming, docstrings, error handling, test structure. If repo uses `from app.tools.policy import ToolPolicyResolver`, use same style.
- **PowerShell:** If editing .ps1, never assign to $PID, $Args, $Error, $PSScriptRoot, $PSCommandPath, $MyInvocation, $PSBoundParameters, $HOME; use local names ($procId, $scriptArgs, etc.).
