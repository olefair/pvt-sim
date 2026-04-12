---
name: docs-contract-workflow
description: >
  Run the Pete workspace docs contract interpreter and custodian workflows
  through the repo-local wrapper script. Use when the user wants deterministic
  verification or contract-driven reconciliation of docs routing, frontmatter,
  blueprint lifecycle, or root-doc family placement. Triggers: docs contract
  audit, schema drift, docs family audit, blueprint lifecycle audit, legacy
  blueprint classification, docs metadata custodian, blueprint metadata
  custodian, relationship reciprocity, generated report authority, minimum
  linkage, vault contract workflow. Do NOT trigger for general documentation
  writing, ad hoc doc cleanup, or free-form documentation review.
---

# Docs Contract Workflow

Run the approved docs contract workflows from
`tools/scripts/run_docs_contract_workflow.py`. This skill is for deterministic
repo-specific verification, not free-form document critique.

It operates on the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not on repo-local `docs/` folders
inside individual project repos or uploaded snapshots. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or mutating notes there.

---

## Output Location

- Interpreter workflows write report notes to
  `C:\Users\olefa\dev\pete-workspace\docs\reports\progress\` and proposed
  contract artifacts to
  `C:\Users\olefa\dev\pete-workspace\tools\contracts\docs\proposed\`.
- Custodian workflows write a report note to
  `C:\Users\olefa\dev\pete-workspace\docs\reports\progress\` and may update
  frontmatter in `C:\Users\olefa\dev\pete-workspace\docs\`.
- Do not write anywhere else. Report the exact paths returned by the wrapper.

---

## Workflow

### Step 1: Read the governing sources

Read these before choosing a workflow:

- `C:\Users\olefa\dev\pete-workspace\tools\contracts\docs\README.md`
- `C:\Users\olefa\dev\pete-workspace\docs\VAULT_SCHEMA.md`
- `C:\Users\olefa\dev\pete-workspace\docs\reference\workspace\reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `C:\Users\olefa\dev\pete-workspace\docs\reference\workspace\reference_generated-document-routing_v1_2026-03-17.md`
- `C:\Users\olefa\dev\pete-workspace\docs\reference\workspace\reference_workspace-conventions.md`
- `C:\Users\olefa\dev\pete-workspace\docs\reference\workspace\reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`
- `C:\Users\olefa\dev\pete-workspace\docs\reference\workspace\reference_document-change-propagation-contract_v1_2026-03-22.md`

Use the shared intake and backlink workflow from the last note when reading
existing vault notes: inspect `links`, then `external_links` when needed, then
`related`, then lineage fields, then body wikilinks, then run a backlink
fallback search when no dedicated backlinks tool exists.

### Step 2: Choose the exact workflow

Map the request to one of these exact wrapper workflows:

- `schema-drift`
- `blueprint-lifecycle`
- `legacy-blueprint-classification`
- `docs-family`
- `repo-doc-boundary`
- `doc-change-propagation`
- `relationship-reciprocity`
- `generated-report-authority`
- `minimum-linkage`
- `blueprint-custodian`
- `docs-custodian`

Use these defaults:

- general root-doc or family routing audit -> `docs-family`
- contract freshness or schema mismatch check -> `schema-drift`
- blueprint path/status audit -> `blueprint-lifecycle`
- ambiguous legacy blueprint classification -> `legacy-blueprint-classification`
- repo-vs-workspace documentation boundary audit -> `repo-doc-boundary`
- authority-note dependency and change-propagation audit -> `doc-change-propagation`
- plan/blueprint reciprocity audit -> `relationship-reciprocity`
- generated report authority-link audit -> `generated-report-authority`
- minimum structured note-link audit for operational families -> `minimum-linkage`
- apply approved blueprint metadata reconciliation -> `blueprint-custodian`
- apply approved non-blueprint docs metadata reconciliation -> `docs-custodian`

Do not invent new workflow names.

### Step 3: Run the wrapper

Run the exact command from the workspace root:

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\run_docs_contract_workflow.py --workflow <workflow-name>
```

### Step 4: Report the wrapper result

Return:

- wrapper name
- status
- summary
- report path
- artifact paths

If the wrapper reports `blocked`, reproduce the first blocker exactly and do
not improvise manual fixes.

### Step 5: Mutation guard

Do not run `blueprint-custodian` or `docs-custodian` unless the user explicitly
requests a custodian pass or the current automation is already named for that
custodian workflow. The wrapper itself is allowed to refuse mutation when newer
proposals exist in `tools/contracts/docs/proposed/`; treat that refusal as the
correct outcome.

---

## Reference Files

- [`references/workflow-map.md`](./references/workflow-map.md) - workflow
  selection, output paths, and mutation guard summary for the wrapper.

---

## Edge Cases

- **Command cannot start:** Report the run as blocked with the first failing
  step. Do not switch to free-form auditing.
- **Wrapper returns success but expected files are missing:** Report the exact
  missing report or artifact path as wrapper drift.
- **User wants free-form doc critique:** do not use this skill; use the
  appropriate documentation or audit workflow instead.
