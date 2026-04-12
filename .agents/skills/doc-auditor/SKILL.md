---
name: doc-auditor
description: >
  Audit, inventory, classify, and produce a canonical documentation-audit note
  for documentation in a workspace or project directory. Use this skill whenever
  the user wants to organize loose documents, find stale or duplicate docs,
  build a document index, assess documentation health, or clean up scattered
  planning/design files. Also trigger for requests like "what docs do I have",
  "index my documentation", "find duplicate docs", "which docs are outdated",
  "clean up my docs folder", "document inventory", or any request involving
  documentation triage, consolidation, or cleanup. This skill is especially
  useful for workspaces with accumulated planning docs, specs, TODO lists,
  progress trackers, and design notes that need classification. Do NOT trigger
  for writing new documentation or editing existing docs; this skill audits the
  current documentation landscape and writes the resulting canonical audit note.
---

# Doc Auditor — Documentation Inventory & Registry Skill

## Purpose

Systematically inventory all documentation in a target directory, classify each
document by project and status, identify issues (duplicates, staleness,
conflicts, gaps), and produce a single canonical documentation-audit note that
gives the user complete visibility into their documentation landscape.

This skill is **read-only by default**. It creates only the canonical audit
note. It proposes archive/cleanup moves but does not execute them without
explicit user approval.

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or writing notes there.

When the current workspace uses the Pete docs vault, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_family-boundaries_audit-vs-report_v1_2026-03-17.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
audit-specific rules below are deltas, not substitutes.

---

## When This Skill Applies

- User wants to inventory or index documentation in a directory
- User asks about stale, duplicate, or orphaned documents
- User wants to consolidate scattered planning/design docs
- User wants a documentation health assessment
- User is preparing for a workspace reorganization and needs a baseline
- User says "audit my docs", "index my documentation", "what docs do I have", "clean up docs"

## Inputs

Before starting, establish these with the user:

1. **Target directory** — The root path to audit (e.g., `C:\Users\me\dev\my-workspace\docs\`). Can include multiple directories.
2. **Exclusion list** — Directories to skip (typically repo internals like `.git`, `node_modules`, `__pycache__`, `.venv`). Repo source directories should generally be excluded — this skill audits *loose* docs, not in-repo documentation.
3. **Baseline document** — If a consolidated task/TODO file exists (like a `TASKS.md`), identify it. This is the reference for determining whether other TODO/progress docs have been absorbed.
4. **Project tags** — The user's project names for classification. Ask what projects/areas are represented in the docs.

If the user doesn't provide these explicitly, infer sensible defaults from the directory structure and confirm before proceeding.

---

## Execution Steps

### Step 1: Scan & Inventory

Read every file in the target directories recursively. For each file, record:

- **Path** (relative to the audit root)
- **Filename**
- **Type** (md, txt, docx, pdf, png, zip, other)
- **Size category** (small: <5KB, medium: 5-50KB, large: >50KB)
- **Content preview** (first heading + first ~10 meaningful lines)

**Skip automatically:** `desktop.ini`, `.wbk` backup files, `~$` Office temp files, `.DS_Store`, `thumbs.db`.

**For archives** (`.zip`): Note existence and approximate purpose from filename. Don't extract.

**For binary docs** (`.docx`, `.pdf`): Read if tooling permits — they often contain important specs. If unreadable, note as "binary — needs manual review."

**For images** (`.png`, `.jpg`): Note existence. Classify by context (screenshot, diagram, etc.) if identifiable from filename or parent directory.

### Step 2: Classify Each Document

Assign each document exactly **one project tag** and **one status tag**.

#### Status Tags

| Tag | Meaning | Implication |
|---|---|---|
| `CURRENT` | Actively used or referenced. Content is up to date. | Keep in place. |
| `ABSORBED` | Content has been consolidated into a current doc. Original is redundant. | Safe to archive. |
| `STALE` | Was once current but has drifted. Contains outdated information. | Needs review or archive. |
| `SUPERSEDED` | A newer version exists. | Archive; note the replacement. |
| `REFERENCE` | Permanent reference material — not a living document. | Keep in place. No staleness assessment needed. |
| `DUPLICATE` | Identical or near-identical to another file. | Archive; note the canonical copy. |
| `EMPTY/STUB` | No meaningful content. | Safe to remove. |

#### Classification Decision Rules

1. **Default to STALE over ABSORBED when uncertain.** STALE means "needs human review." ABSORBED means "safe to archive." Err toward caution.

2. **Timestamped duplicates:** When both `doc.md` and `doc_20260216_190954.md` exist, the non-timestamped version is usually the latest. Mark the timestamped one as SUPERSEDED unless content comparison shows otherwise.

3. **TODO/task files:** If a baseline document exists (e.g., `TASKS.md`), compare item-by-item. If all items from a source doc appear in the baseline, mark as ABSORBED. If the baseline is missing items, note which ones under "Missing from baseline."

4. **Progress/status docs:** Cross-reference against the most recent comprehensive audit or status report. Earlier progress docs may be ABSORBED or STALE.

5. **Instruction/prompt/config files:** These are living configuration. Check for `Superseded/` or `deprecated/` subdirectories — anything in those is SUPERSEDED by definition. Otherwise, default to CURRENT unless content clearly conflicts with reality.

6. **Literature/papers:** Always `REFERENCE`. Don't assess staleness — they're permanent.

7. **Design docs and specs:** CURRENT if they describe something that hasn't been built yet (still a plan), REFERENCE if they describe a completed design (historical record), STALE if they describe something that was built differently than specified.

### Step 3: Identify Issues

After classification, compile:

1. **Orphan documents** — Files not referenced by any current doc or baseline. Potential dead weight.
2. **Conflicting documents** — Two CURRENT docs that describe the same topic differently.
3. **Missing coverage** — Active work areas (per baseline) with no corresponding design doc or spec.
4. **Cross-directory duplicates** — Same content in multiple locations.
5. **Naming inconsistencies** — Files that would benefit from consistent naming conventions.
6. **Linking gaps** — Missing required frontmatter links, weak body wikilinks, or backlink isolation that materially reduces vault navigation.

### Step 4: Produce the Registry

Write a canonical audit-family note to the audits directory (see Output Location below), NOT in the directory being audited. The registry tables live inside that audit note; do not emit a bare `DOCUMENT_REGISTRY.md` when the Pete vault schema applies.

#### Registry Format

```markdown
---
project: workspace
repos:
  - pete-workspace
subject: documentation inventory for [audit scope]
status: draft
audit_kind: documentation-audit
review_state: pending-review
production_mode: generated
produced_by: doc-auditor
agent_surface: [active surface enum]
created: YYYY-MM-DD
updated: YYYY-MM-DD
links: []
related: []
external_links: []
supersedes: []
superseded_by: []
---

# Audit: Documentation Registry — [audit scope]

## Audit Type
State that this is a `documentation-audit` and why the audit family is the correct vault family.

## Scope
- Directories audited
- Exclusions
- Baseline doc (if any)

## Basis of Assessment
- File inventory
- Baseline task doc
- Existing registries or prior audit notes

## Method
Describe scan depth, classification rules, and any unreadable binary/doc limitations.

## Findings

### Summary
| Status | Count |
|---|---|
| CURRENT | N |
| ABSORBED | N |
| STALE | N |
| SUPERSEDED | N |
| REFERENCE | N |
| DUPLICATE | N |
| EMPTY/STUB | N |
| **Total** | **N** |

### Recommended Actions
1. [Most impactful cleanup action]
2. [Second most impactful]

### Full Registry
#### Project: [tag]
| # | File | Status | Notes |
|---|---|---|---|
| 1 | `relative/path/file.md` | CURRENT | Brief description of content and role |
| 2 | `relative/path/old.md` | ABSORBED | All items now in TASKS.md |

### Issues
#### Orphan Documents
[List with paths and brief content description]

#### Conflicting Documents
[Pairs/groups with description of the conflict]

#### Missing Coverage
[Active work areas lacking documentation]

#### Cross-Directory Duplicates
[Groups of identical or near-identical files]

### Proposed Archive Moves
> **These are proposals only. Do not execute without user approval.**

| # | Source | Destination | Reason |
|---|---|---|---|
| 1 | `docs/old/file.md` | `_archive/docs/` | SUPERSEDED by docs/new/file.md |
| 2 | `docs/codex/TODO_v1.md` | `_archive/docs/` | ABSORBED into TASKS.md |

### Items Missing from Baseline
- [Item description] — found in [source doc path]

## Assessment
State the overall documentation posture and the most important sources of drift or risk.

## Risks
List the practical risks if the current doc state is left unchanged.

## Recommended Remediation
List the cleanup, consolidation, or follow-on audit work in priority order.

## Review Notes
Capture approvals, disputes, or explicit human review decisions.

## Lineage / Change Notes
Record whether this supersedes an earlier documentation audit.
```

### Step 5: Propose Archive Moves (Do NOT Execute)

For every document classified as ABSORBED, SUPERSEDED, DUPLICATE, or EMPTY/STUB: list a proposed move in the "Proposed Archive Moves" table. The standard archive destination is `_archive/` under the relevant folder (or a subdirectory mirroring the original path).

**Critical: Do not move, rename, or delete any files.** Proposals only. The user reviews and approves before execution.

---

## Constraints

- **Read-only operation.** The only file you create is the canonical documentation-audit note. Everything else is untouched.
- **Do not enter excluded directories.** If the user excluded repo internals, respect that boundary.
- **Do not modify the baseline document.** If you find missing items, list them in the registry — don't edit the baseline.
- **Ambiguity resolution:** When you can't confidently classify a document, mark it `STALE — needs human review` with a note explaining the ambiguity. Don't block on uncertainty.
- **No silent scope expansion.** Audit what was asked. If you notice something outside scope that deserves attention, note it at the bottom of the registry under "Out-of-Scope Observations" — don't act on it.

---

## Quality Checks Before Delivery

Before presenting the registry:

1. **Every file in the inventory appears in the registry.** No orphaned inventory entries.
2. **Every ABSORBED doc cites which current doc absorbed it.**
3. **Every SUPERSEDED doc cites its replacement.**
4. **Every DUPLICATE doc cites the canonical copy.**
5. **The summary counts match the actual entries.**
6. **Proposed archive moves have a clear reason column — no unexplained moves.**

---

## Incremental Re-Audit

If a prior documentation-audit note already exists, the skill can perform an incremental audit:

1. Read the existing audit frontmatter first
2. If `superseded_by` is populated and the user did not ask for historical review, follow the latest successor audit instead of patching a superseded note
3. Reuse still-valid `subject`, `links`, `related`, and lineage fields rather than silently dropping them
4. Read the existing registry content
5. Scan for new files not in the registry
6. Re-check STALE items to see if they've been addressed
7. Update the audit note in place (regenerate the full file — don't try to patch)
8. Add a changelog entry at the top noting what changed

This supports ongoing documentation hygiene without starting from scratch each time.

## Output Location

All documentation audit output MUST be saved to:

```
C:\Users\olefa\dev\pete-workspace\docs\audits\docs\
```

This skill writes to the canonical `docs` audit subfamily, not to mirrored deep subfolders. Encode the specific scope in the slug and in frontmatter `subject`.

### Naming Convention

```
audit_{audit-root}-{focus-of-audit}_YYYY-MM-DD.md
```

- **Audit root:** The folder name being audited (e.g., `claude`, `blueprints`, `docs`)
- **Focus:** What the audit examined (e.g., `full-inventory`, `staleness-check`, `reorg-baseline`)
- **Date:** ISO date of the audit

Examples:
- `audit_claude-full-inventory_2026-03-11.md`
- `audit_blueprints-staleness-check_2026-03-11.md`

### Delivery

Write the audit directly to the vault using `repo-engineer:repo_create_file` or
`file-writer:create_file`, then also present via `present_files` for a
convenience download link.

Default: write to vault AND present download link.
Fallback: if vault write fails, create a container download and state the
intended vault path so the user can place it manually.
