# Vault Blueprint Layout

Use this note when you need the observed blueprint search surface or when you need to suggest where a new blueprint should live.

## Vault Root

In this workspace, `MCP-servers/obsidian-vault-mcp/obsidian_vault_config.yaml` points to:

- `C:\Users\olefa\dev\pete-workspace\docs`

Search under:

- `C:\Users\olefa\dev\pete-workspace\docs\blueprints`

## Live Layout

This vault currently uses a mixed layout. Do not assume a single folder convention.

Important distinction:

- mixed legacy folders are part of the **search surface**
- they are **not** the canonical destination for new blueprint creation
- new blueprints should always be saved to the canonical lowercase path
  `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`

Observed active patterns:

- `docs/blueprints/Codex/<project>/...`
- `docs/blueprints/cowork/<project>/...`
- legacy project folders such as `docs/blueprints/pete/`, `docs/blueprints/pvt-sim/`, and `docs/blueprints/FaultTensor/`
- root-level shared notes such as index files, blueprint packs, and migration notes

Historical material may also appear under `_archive`.

## Search Order

Prefer this search order when judging whether a blueprint already exists:

1. Active implementer/project folders that match the current work.
2. Legacy project folders for the same repo or subsystem.
3. Shared workspace blueprints and root-level blueprint packs.
4. `_archive` only as historical context, not as the default implementation source.

## Match Standard

Treat a blueprint as a real match only if all of the following are materially aligned:

- repo or subsystem
- implementation target
- scope
- validation intent

Similar filenames alone are not enough.

## Placement For New Blueprints

If the user wants a new blueprint drafted outside Codex and then saved into the vault:

- Always target the canonical lowercase path:
  - `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`
- Do not route newly-created blueprints into `docs/blueprints/Codex/...`, uppercase project folders, or legacy project-root folders unless the user explicitly requests legacy placement.

That canonical path comes from:

- `MCP-servers/obsidian-vault-mcp/src/obsidian_vault_mcp/tools/canonical.py`

## Handoff Rule

- Existing blueprint found: point to the file and use `$blueprint-implementer`.
- No blueprint found: draft a ChatGPT Pro desktop prompt that asks for a single Markdown blueprint to be saved into the vault before implementation begins.
