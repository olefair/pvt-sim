---
name: blueprint-presence-checker
description: Check the Obsidian docs vault for an existing implementation blueprint before starting feature work. Use when Codex needs to answer questions like "do we already have a blueprint for this?", search `docs/blueprints` for a proposed implementation, decide whether an existing blueprint is complete enough to reuse, route directly into `$blueprint-implementer` when a matching blueprint exists, or draft a ChatGPT Pro desktop prompt to create a blueprint when none exists.
---

# Blueprint Presence Checker

Before implementing or designing from scratch, prove whether the docs vault already contains a usable blueprint. Reuse existing specs when possible; only ask for a new blueprint when the vault truly does not cover the work.

## Workflow

1. Resolve the vault root.
2. Search `docs/blueprints` with the bundled script.
3. Read the best candidate notes yourself before claiming a match.
4. Classify the result as `EXISTS`, `PARTIAL / OVERLAP`, or `MISSING`.
5. Route the next step:
   - `EXISTS`: point to the note and use `$blueprint-implementer` if the current request includes implementation work.
   - `PARTIAL / OVERLAP`: identify the overlapping notes and explain the uncovered gap.
   - `MISSING`: stop implementation and draft a ChatGPT Pro desktop prompt for a new blueprint.

## Resolve The Vault

Prefer the configured vault root from:

- `MCP-servers/obsidian-vault-mcp/obsidian_vault_config.yaml`
- or the known workspace path when that file is available.

In this workspace, the configured root is `C:\Users\olefa\dev\pete-workspace\docs`.
That `docs/` tree is the shared Obsidian vault at the workspace root, not a
repo-local `docs/` folder inside an individual project repo or uploaded
snapshot. Treat YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body
linking as part of the operating contract whenever reading or proposing notes
there.

## Vault Document Intake Rules

When evaluating a blueprint note, follow the workspace vault contract in:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Execution rules:

- parse frontmatter before interpreting the body
- read `links` first when present
- read materially necessary `external_links` when the request depends on them
- inspect `related` and body `[[wikilinks]]` for adjacent blueprint context
- if there is no backlinks tool, run a fallback vault search on the note basename and key slug phrases to approximate backlinks before declaring the note isolated
- when proposing a new blueprint path or frontmatter seed, keep `links`, `related`, and `external_links` semantically correct rather than treating them as decoration

## Search The Blueprints Tree

Use the bundled script:

```bash
python scripts/find_blueprints.py --config C:\Users\olefa\dev\pete-workspace\tools\MCP-servers\obsidian-vault-mcp\obsidian_vault_config.yaml --query "add minimal CI smoke workflow for pete" --project pete --implementer codex --repo pete --json
```

Guidance:

- Search the whole `docs/blueprints` tree, not a single folder.
- Prefer active notes over `_archive`.
- Prefer repo- and project-specific hits over generic workspace notes.
- Add `--project`, `--implementer`, and `--repo` whenever those are clear from the request.
- Read [vault-blueprint-layout.md](references/vault-blueprint-layout.md) if you need the observed folder conventions and placement rules.

## Verify Candidates Manually

Do not trust filename similarity alone. Read enough of each top candidate to verify:

- title
- frontmatter fields such as `repo`, `project`, `target`, and `status`
- `Objective`
- `Scope`
- `Implementation Plan`
- `Validation / Acceptance Criteria`

Treat a blueprint as reusable only when its target surface and acceptance intent materially match the requested implementation.

## Classify The Result

### `EXISTS`

Use this only when one note clearly covers the requested work.

Respond with:

- the blueprint path
- one sentence on why it matches
- the next action

If the user also wants implementation work in the same request, transition immediately into `$blueprint-implementer` using that blueprint path.

### `PARTIAL / OVERLAP`

Use this when related blueprints exist but do not fully cover the request.

Respond with:

- overlapping blueprint paths
- the gap between those notes and the requested work
- whether extending an existing blueprint or writing a new one is the cleaner move

Do not hand off to `$blueprint-implementer` until a concrete blueprint actually covers the requested scope.

### `MISSING`

Use this when the search finds no blueprint that materially covers the request.

Do not invent a blueprint inside this skill. Instead, draft a ChatGPT Pro desktop prompt that asks for:

- one Markdown blueprint, not implementation code
- the repo and project
- the target subsystem or files
- the constraints and non-goals
- validation / acceptance criteria
- canonical YAML frontmatter matching the vault blueprint template
- the canonical save path in the vault

After the blueprint exists in `docs/blueprints`, hand off to `$blueprint-implementer`.

## Response Shape

Use this response shape when reporting results:

```text
Blueprint Check
Status: EXISTS | PARTIAL / OVERLAP | MISSING

Matches:
- <path> — <why it matches or why it only partially matches>

Next step:
- <implement with $blueprint-implementer | extend an existing blueprint | ask ChatGPT Pro desktop to draft one>
```

## New Blueprint Placement

When suggesting where a newly drafted blueprint should be saved:

- Always use the canonical vault blueprint path `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`.
- Use lowercase canonical implementer and project enums.
- Treat legacy mixed-case or legacy project folders as search-only history, not as destinations for new blueprints, unless the user explicitly tells you to preserve legacy placement.

## Resources

- [find_blueprints.py](scripts/find_blueprints.py) searches the vault and ranks likely blueprint matches.
- [vault-blueprint-layout.md](references/vault-blueprint-layout.md) explains the mixed live layout and where new blueprints should go.
