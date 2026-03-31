# Phase 1: Full Repository Inspection Protocol

Exhaustive inspection and gap analysis against an uploaded blueprint.

**Philosophy:** You cannot implement what you do not understand, and you cannot understand what you have not read. Every shortcut in this phase creates a bug in Phase 2.

---

## Step 1: Structural Inventory

Build the structural inventory directly from the repo.

- **1.1 Language breakdown** — Use `rg --files`, extension counts, and representative reads to note languages and proportion.
- **1.2 Directory structure** — Walk the tree with directory listings. Map: app/, tests/, config/, scripts/, docs/, gui/.
- **1.3 Test inventory** — Identify which modules have tests, which have none, and the naming convention (test_*.py, *_test.py).
- **1.4 Config inventory** — Read config files and startup paths to learn how the app is configured, what dependencies matter, and where execution starts.

---

## Step 2: Deep File Reading

Do not skip.

- **2.1 Blueprint-referenced files** — For every path in the blueprint, read the entire file directly (or full content in chunks if it is very large). Note: functions or classes, imports, exports, and role.
- **2.2 Neighboring files** — For each dir with a blueprint-referenced file, read ALL files in that directory (integration points and conventions).
- **2.3 Test files** — Every test that covers blueprint modules, is in scope, or the blueprint says to create/modify.
- **2.4 Integration points** — API routers, main entry (imports), plugin registries, config loaders.
- **2.5 Discipline** — After each file state: "I've read [path]. It contains: [N] functions/classes [names], imports from [key deps], role: [summary]." If you haven't read a file you're about to reference, say so.

---

## Step 3: Architecture Mapping

- **3.1 Request flow** — Trace: request → router → handler → tools → response (file/function at each step).
- **3.2 Dependency graph** — Per module in scope: imports, importers, circular dependency risks.
- **3.3 Conventions** — Naming, error handling, test patterns, config. New code must follow these.

---

## Step 4: Blueprint Parsing

- **4.1 Structure** — See [blueprint-format.md](blueprint-format.md). Parse: title/scope, repo anchors, milestones, per-milestone (new files, file changes, success criteria, test plan), definition of done.
- **4.2 Anchor verification** — For each anchor, verify it with direct file reads, `rg`, router or registry reads, and test discovery. If it is not found, flag a discrepancy.

---

## Step 5: Gap Analysis Production

Per milestone classify:

- **COMPLETE** — Behavior exists and works; file + line evidence.
- **PARTIAL** — Some behavior, incomplete or wrong; note what's there and missing.
- **NOT STARTED** — Nothing matching.
- **DISCREPANCY** — Blueprint claims something that doesn't exist, or repo contradicts blueprint.

**Ordering:** No dependencies first; then dependents; within level: models → logic → API → tests; respect blueprint order unless dependencies override.

**Test gaps:** Per success criterion — COVERED (test exists), NEEDS UPDATE (test exists but wrong), NEEDS CREATION (no test).

---

## Step 6: Transition to Phase 2

Output gap analysis as structured report and start Phase 2 immediately. Gap analysis is the implementation plan; no approval gate.
