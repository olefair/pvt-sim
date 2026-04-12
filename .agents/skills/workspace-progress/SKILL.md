---
name: workspace-progress
description: >
  Workspace-wide progress aggregator. Pulls open tasks from Todoist, scans handoff files for unresolved threads, checks for unexecuted Cowork prompts. Deduplicates across sources, writes prioritized progress report. Triggers: /progress, /status, "full status report", "where are we", "what should we tackle", "what's left to do", workspace-level overview of open work.
---

# Workspace Progress Skill

You are a workspace intelligence aggregator. Your job is to pull open work
from every task store, deduplicate, prioritize, and produce a single
authoritative progress snapshot.

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or writing notes there.

When the current workspace uses the Pete docs vault, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
progress-report rules below are deltas, not substitutes.

---

## Output Location

**Always write to:**
`C:\Users\olefa\dev\pete-workspace\docs\reports\progress\report_workspace-progress_YYYY-MM-DD.md`

Replace `YYYY-MM-DD` with today's date. If a file already exists for today,
overwrite it (use `overwrite: true`).

Use the canonical report contract from `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`, routing rules from `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`, and `docs/templates/template_report-canonical_v1_2026-03-17.md`:
- `report_kind: progress-report`
- `production_mode: generated`
- `produced_by: workspace-progress`
- `agent_surface` for the active surface
- required report fields: `project`, `status`, `created`, `updated`, `links`, `related`, `external_links`
- recommended: `repos`, `subject`, `supersedes`, `superseded_by`
- put governing notes and must-read source notes in `links`, adjacent notes in `related`, preserve lineage in `supersedes` / `superseded_by`, and use body wikilinks so the report remains discoverable through backlink navigation

**Also present as download** after writing, so the file is immediately accessible.

---

## Workflow

### Step 1: Pull Todoist — All Projects

Call `Todoist:find-tasks` with `responsibleUserFiltering: all` and no
project filter to get all open tasks across every project.

For each task, capture: `id`, `content`, `description`, `priority`,
`projectId`, `labels`, and any `dueString` or `deadlineDate`.

Group by project. Known projects:
- **Claude Config** (`6g7whR7hcHVH3jMm`) — infra, skills, MCP, tools
- **Pete** — voice assistant dev
- **PVT Simulator** — pvt-sim_canon dev
- **MCP Servers & Plugins** — server builds
- **Inbox** — unsorted

Note tasks labeled `blocker` or `accelerator` — these get special treatment
in the report.

### Step 2: Scan Handoff Files

Read all `.md` files in:
- `C:\Users\olefa\dev\pete-workspace\docs\handoffs\claude\`
- `C:\Users\olefa\dev\pete-workspace\docs\handoffs\gpt\`

Fallback only for legacy notes:
- `C:\Users\olefa\dev\pete-workspace\docs\handoffs\`
- `C:\Users\olefa\dev\pete-workspace\docs\handoffs\GPT\`

For each handoff, parse YAML frontmatter first and use it legally:
- `status`, `open_threads`, `carried_forward`, and `resolved_threads` define unresolved work
- `supersedes` and `superseded_by` define which handoff is current
- `areas`, `subjects`, `project`, `projects`, and `repos` define grouping and scope
- `links`, `related`, and `files` define governing context and produced-file evidence

Only fall back to body headings like "Open Items", "Pending", "Remaining", or "Unresolved" when a legacy handoff has no valid frontmatter.

Do not re-report threads that are clearly superseded by a later handoff
or already present verbatim in Todoist. Use judgment — if the same task
appears in both, it counts once (Todoist is the canonical record).

Flag any open thread older than 14 days that has no corresponding Todoist
task — these are at risk of being forgotten entirely.

### Step 3: Check Cowork Staging

List files in `C:\Users\olefa\dev\pete-workspace\docs\blueprints\cowork\`.

Exclude `desktop.ini` and the `Output/` subdirectory.

Each `.md` file in the root of `cowork/` is an unexecuted prompt. Cross-
reference against the `Output/` completion reports — if a prompt has a
corresponding completion report, it's done. Otherwise it's queued.

Capture: filename, and the first line of the file (usually the prompt title).

### Step 4: Deduplicate

Before writing the report, cross-reference all three sources:
- If a handoff open thread matches a Todoist task (by content similarity,
  not just exact string), keep the Todoist entry and note "also in handoff"
- If a Cowork prompt is already represented as a Todoist task, keep the
  Todoist entry and note "Cowork prompt queued"
- If an item appears in handoffs but not Todoist, flag it as **orphaned**

### Step 5: Write the Report

Use the template below. Fill in every section — do not skip sections
because they're empty (instead write "None" so the reader knows it was
checked).

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
State that this is a generated `progress-report` covering open work across Todoist, handoffs, and Cowork staging.

## Scope
Define the workspace scope and the date window being summarized.

## Basis / Inputs
- Todoist ({N} tasks across {P} projects)
- Handoffs ({N} files, canonical handoff frontmatter preferred over body heuristics)
- Cowork staging ({N} prompts)

## Findings / Observations

### 🔴 Blockers
- **[Task name]** — [project] — [brief description or why it's blocking]
  `Todoist: {id}`

### ⚡ Accelerators
- **[Task name]** — [project]

### Priority Buckets
#### P1 — Urgent
- **[Task name]** — [project]

#### P2 — High Priority
- **[Task name]** — [project]

#### P3 — Medium
- **[Task name]** — [project]

#### P4 — Low / Deferred
- **[Task name]** — [project]

### 🚧 Cowork Queue
- `[filename]` — [prompt title]

### ⚠️ Orphaned Items
- **[Item]** — from `[handoff filename]` ([date]) — [brief description]

## Interpretation
Explain the current workspace bottlenecks, stale queues, and the main coordination picture.

## Implications / Suggested Follow-up

### 📋 Recommended Next Ups
1. [Task] — [why: blocker / accelerator / longest outstanding / etc.]
2. ...

## Change Notes
- New baseline or notable changes since the prior progress report
```

---

## Prioritization Logic for "Recommended Next Ups"

Order of priority:
1. Blockers labeled as such AND blocking an identified accelerator
2. Standalone blockers
3. Accelerators (P1 before P2)
4. P1 non-blocker non-accelerator tasks
5. Orphaned handoff items older than 14 days
6. P2 tasks that have been open the longest (infer from handoff date if no
   Todoist created date is available)

Limit to 5 items. If the list is clean (no blockers, no orphans), pick the
5 highest-leverage items across all priorities.

---

## Reference Files

- [`references/sources.md`](./references/sources.md) — Data source details:
  Todoist project IDs, handoff parsing patterns, Cowork staging logic,
  known quirks. Read this if any source pull is ambiguous.
- [`references/report-template.md`](./references/report-template.md) — Full
  output template with all sections. Use this when writing the report.

---

## Edge Cases

- **Todoist unavailable:** Proceed with handoffs + Cowork only. Note in
  report header that Todoist was unavailable.
- **Handoffs directory empty:** Skip Step 2, note in report.
- **No cowork prompts queued:** Write "None" in Cowork Queue section.
- **Today's report already exists:** Overwrite with `overwrite: true`.
  This is intentional — run it as many times as needed in a session.
- **Duplicate Todoist tasks** (same content, different IDs): Note both IDs
  in the report and flag for cleanup. Do not silently drop either one.
