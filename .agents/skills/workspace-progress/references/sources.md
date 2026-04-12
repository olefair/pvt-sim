# Workspace Progress — Data Sources Reference

Documents how to pull from each source, what to look for, and known quirks.

---

## Source 1: Todoist

**Tool:** `Todoist:find-tasks`
**Call pattern:**
```
responsibleUserFiltering: all
limit: 100
(no projectId filter — pull all projects)
```

**Known projects and IDs:**
| Project | ID | Scope |
|---|---|---|
| Claude Config | `6g7whR7hcHVH3jMm` | Infra, skills, MCP, tools |
| Pete | (look up) | Voice assistant dev |
| PVT Simulator | (look up) | pvt-sim_canon dev |
| MCP Servers & Plugins | (look up) | Server builds |
| Inbox | `inbox` | Unsorted / catch-all |

**Labels to watch:**
- `blocker` — gates other work
- `accelerator` — high leverage, unblocks multiple items

**Priority mapping:**
- `p1` — Urgent
- `p2` — High
- `p3` — Medium
- `p4` — Low/deferred

**Known quirks:**
- Duplicate tasks exist (same content, different IDs). Flag these in the
  Duplicate/Cleanup section rather than silently deduplicating.
- Some tasks have stale descriptions referencing old approaches
  (e.g. VoiceMode MCP tasks that were superseded by the dictate stack).
  Flag these for closure.
- 403 errors from Todoist don't reliably indicate failure — if you get one,
  check whether results were actually returned before retrying.

---

## Source 2: Handoff Files

**Location:** `C:\Users\olefa\dev\pete-workspace\docs\handoffs\claude\` and `C:\Users\olefa\dev\pete-workspace\docs\handoffs\gpt\`
**Legacy fallback:** `C:\Users\olefa\dev\pete-workspace\docs\handoffs\` and `C:\Users\olefa\dev\pete-workspace\docs\handoffs\GPT\`
**Pattern:** `handoff_[slug]_YYYY-MM-DD.md`
**Tool:** `file-reader:read_files_matching` with glob `*.md`

**What to extract:**
Parse YAML frontmatter first and use it legally:
- `status`, `open_threads`, `carried_forward`, and `resolved_threads` are the canonical thread-state model
- `supersedes` and `superseded_by` determine which handoff is current
- `areas`, `subjects`, `project`, `projects`, and `repos` define grouping and scope
- `links`, `related`, and `files` provide context and file evidence

Only fall back to headings like `## Open Threads`, `## Pending`, `## Remaining`, `## Unresolved`, or `## Recommended Next Steps` when a legacy handoff has no valid frontmatter.

**Deduplication against Todoist:**
If an open thread from a handoff clearly matches a Todoist task (same
intent, even if worded differently), count it once. Use the Todoist entry
as canonical; note "also in handoff: [filename]" on that task.

**Orphan detection:**
If an open thread has NO match in Todoist, it is orphaned. Flag it in the
Orphaned Items section with the source filename and age in days.

**Supersession logic:**
If the same thread appears in multiple handoffs and the latest one marks
it resolved or superseded, don't surface it. Only flag items that are still
open in the most recent non-superseded handoff that mentions them.

**Age calculation:**
Parse the date from the filename. Today minus that date = age in days.
Items >14 days old with no Todoist entry should be highlighted.

---

## Source 3: Cowork Staging

**Location:** `C:\Users\olefa\dev\pete-workspace\docs\blueprints\cowork\`
**Tool:** `file-reader:directory_tree` then `file-reader:read_file` for
first line of each prompt file.

**What counts as queued:**
Any `.md` file at the ROOT of `cowork/` (not inside subdirectories or
`Output/`) that does NOT have a corresponding completion report in
`cowork/Output/`.

**Completion matching:**
A prompt `cowork-prompt_foo.md` is considered complete if `Output/`
contains a file with `foo` in the name, or a `DEPLOYMENT-STATUS.md`
that references it as done.

**Files to always exclude:**
- `desktop.ini`
- Anything inside `Output/`

**Naming convention for prompts:**
`cowork-prompt_[what-it-does].md`

---

## Prioritization Logic (for Recommended Next Ups)

Order strictly:
1. Blockers that gate an accelerator
2. Standalone blockers
3. Accelerators (P1 first, then P2)
4. P1 tasks (non-blocker, non-accelerator)
5. Orphaned handoff items older than 14 days
6. P2 tasks open the longest (estimate from earliest handoff they appear in)

Cap at 5 items. If fewer than 5 qualify from the top tiers, fill from
the next tier down.
