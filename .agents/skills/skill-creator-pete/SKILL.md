---
name: skill-creator-pete
description: >
  Creates, updates, and packages Claude Desktop skills following Ole's workspace conventions. Use this skill — NOT the built-in skill-creator — whenever building or modifying a skill for this workspace. Triggers: create/build/update/package a skill, add a new capability via the skills system.
---

# Skill Creator — Pete Workspace

This skill enforces the correct workflow for creating and packaging Claude
Desktop skills in this workspace. Follow every step in order. No shortcuts.

---

## Chat Access Restriction

Chat is read-only — it cannot write to the local filesystem. Chat's role in
skill creation is to **author the content** (SKILL.md and reference docs) and
deliver them via the container for download. Packaging and placement on disk
are either done by Cowork or by the user manually.

---

## Conventions (Non-Negotiable)

| Convention | Value |
|---|---|
| Working folders | `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\` |
| Package directory | `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\packages\` |
| Final output | `tools\SKILLS\packages\[skill-name].skill` |
| Codex mirror | `C:\Users\olefa\.codex\skills\[skill-name]\` |
| Package format | ZIP with `.skill` extension, flat root (no wrapping folder) |
| Required contents | `SKILL.md` + `references\` folder (at least one ref doc) + `agents\openai.yaml` |

---

## Workflow

### Step 1: Read Existing Skills for Pattern Reference

Before writing anything, read at least one existing skill to calibrate
format and quality. Pick one relevant to the new skill's domain:

```
file-reader: read C:\Users\olefa\dev\pete-workspace\tools\SKILLS\packages\[relevant].skill
```

### Step 2: Design the Skill

Before writing any files, confirm with Ole:
1. What should this skill enable Claude to do?
2. What are the trigger phrases? (Be specific — undertriggering is the main failure mode)
3. What tools does it require?
4. What reference docs are needed in `references\`?
5. What is the output, and where does it get written?

Do not skip this step for non-trivial skills.

### Step 3: Write SKILL.md

Write `SKILL.md` content and create it in the container at
`/mnt/user-data/outputs/[skill-name]/SKILL.md` using the built-in `create_file`
tool (NOT `file-writer:create_file`).

SKILL.md must contain:
- YAML frontmatter: `name`, `description` (triggers go HERE, not in the body),
  and optionally `compatibility`
- Clear workflow steps
- Explicit output location if the skill produces files
- For any skill that reads or writes workspace docs, an explicit vault clause
  stating that `docs/` is the shared Obsidian vault rooted at
  `C:\Users\olefa\dev\pete-workspace\docs` and that YAML frontmatter,
  `[[wikilinks]]`, and backlink-oriented body linking are operational
  requirements, with the canonical contract note
  `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
  cited directly in the skill body
- References to files in `references\` with guidance on when to read them

See `references\skill-md-template.md` for the full template.

### Step 4: Write Reference Docs

Every skill must have at least one reference doc. Create each in the container at
`/mnt/user-data/outputs/[skill-name]/references/[doc-name].md` using the built-in
`create_file` tool.

Common reference doc types:
- `output-template.md` — if the skill produces a document
- `sources.md` — if the skill pulls from multiple data sources
- `decision-table.md` — if the skill makes branching decisions
- `conventions.md` — if the skill enforces naming/structural rules

### Step 5: Present Files for Download

Use `present_files` to deliver the skill folder contents for user download.

State the packaging and placement instructions in chat:

"Skill files written to container — download all files. To package:
1. Place `SKILL.md`, `references\`, and optional `agents\` in `tools\SKILLS\folders\[skill-name]\`
2. Package as zip:
   ```powershell
   Compress-Archive `
     -Path 'C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\[skill-name]\SKILL.md', `
             'C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\[skill-name]\references', `
             'C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\[skill-name]\agents' `
     -DestinationPath 'C:\Users\olefa\dev\pete-workspace\tools\SKILLS\packages\[skill-name].skill'
   ```
3. Verify flat structure (no wrapping folder at root)
4. Keep the standardized working folder in place under `tools\SKILLS\folders\[skill-name]\`
5. Mirror the finalized skill folder into `C:\Users\olefa\.codex\skills\[skill-name]\` so Codex keeps the same skill surface.
6. Upload: Settings → Project Knowledge → upload `.skill` file

Or delegate packaging to Cowork."

Chat does not write to the local filesystem or run terminal commands directly.

### Step 6: Confirm

Report:
- Skill name and intended location: `tools\SKILLS\packages\[skill-name].skill`
- Files produced: SKILL.md + references list
- Packaging status: files delivered for download (packaging pending)

---

## Updating an Existing Skill

Existing `.skill` files are read-only zips. To update:

1. Read the current `.skill` file contents using file-reader.
2. Draft the updated `SKILL.md` and/or reference docs.
3. Create updated files in the container at `/mnt/user-data/outputs/[skill-name]/`.
4. Present via `present_files` for download.
5. State the repackaging instructions (same as Step 5 above, with `-Force` flag).
6. Mirror the updated skill folder into `C:\Users\olefa\.codex\skills\[skill-name]\` so the Codex skill repo stays in sync with the Pete workspace copy.

---

## Common Failure Modes

| Failure | Cause | Fix |
|---|---|---|
| Wrong zip structure (folder-wrapped) | Zipped the folder itself instead of its contents | Zip `folder\SKILL.md` and `folder\references`, not `folder\` |
| .zip instead of .skill | Wrong extension | Change `-DestinationPath` to end in `.skill` |
| No references folder | Skipped Step 4 | Every skill needs at least one reference doc |
| Missing `agents\openai.yaml` | Skipped UI metadata generation | Add an `agents\openai.yaml` file before packaging |
