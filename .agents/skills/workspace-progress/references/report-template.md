# Workspace Progress Report — Canonical Output Template

This is the canonical template for
`report_workspace-progress_YYYY-MM-DD.md`.
Fill every section. Never skip a section — write "None" if empty so the
reader knows it was checked.

---

```markdown
---
project: workspace
repos:
  - pete-workspace
subject: workspace open-work synthesis
status: published
report_kind: progress-report
production_mode: generated
produced_by: workspace-progress
agent_surface: [active surface enum]
created: YYYY-MM-DD
updated: YYYY-MM-DD
links: []
related: []
external_links: []
supersedes: []
superseded_by: []
---

# Report: Workspace Progress Snapshot

## Report Type
State that this is a generated `progress-report`.

## Scope
Define the workspace scope and time window being summarized.

## Basis / Inputs
- Todoist ({N} open tasks across {P} projects)
- Handoffs ({N} files scanned; prefer canonical frontmatter over body heuristics)
- Cowork staging ({N} prompts)

## Findings / Observations

### 🔴 Blockers
- **[Task name]** — [Project] — [Why it's blocking / what it gates]
  `Todoist: {id}`

### ⚡ Accelerators
- **[Task name]** — [Project] — [What it accelerates]
  `Todoist: {id}`

### Priority Buckets
#### P1 — Urgent
- **[Task name]** — [Project]
  `Todoist: {id}`

#### P2 — High Priority
- **[Task name]** — [Project]
  `Todoist: {id}`

#### P3 — Medium
- **[Task name]** — [Project]
  `Todoist: {id}`

#### P4 — Low / Deferred
- **[Task name]** — [Project]
  `Todoist: {id}`

### 🚧 Cowork Queue
- `[filename]` — [prompt title / first line of file]

### ⚠️ Orphaned Items
- **[Item summary]** — from `[handoff_slug_YYYY-MM-DD.md]` ([N] days ago)
  > [Exact text or close paraphrase of the open item]

### 🔁 Duplicate / Cleanup Flags
- **[Task A]** (`{id}`) and **[Task B]** (`{id}`) appear to be duplicates — [reason]
- **[Task]** (`{id}`) — appears obsolete because [reason]; recommend closing

## Interpretation
Summarize the current workspace bottlenecks, stale queues, and what is actually gating movement.

## Implications / Suggested Follow-up

### 📋 Recommended Next Ups
1. **[Task]** — [Project]
   _Why: [blocker / accelerator / longest outstanding / orphaned / etc.]_

2. **[Task]** — [Project]
   _Why: [reason]_

3. **[Task]** — [Project]
   _Why: [reason]_

4. **[Task]** — [Project]
   _Why: [reason]_

5. **[Task]** — [Project]
   _Why: [reason]_

## Change Notes
- New baseline or notable changes since the prior progress report
```
