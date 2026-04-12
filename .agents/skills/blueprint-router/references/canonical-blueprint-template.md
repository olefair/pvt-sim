# Canonical Blueprint Template

Use this contract when emitting a new blueprint artifact.

## Canonical Path

`docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`

Rules:

- `implementer` must be one of `claude`, `codex`, `cowork`, `human`
- `project` must use the canonical workspace enum
- filename must be `blueprint_<slug>.md`
- do not put dates in blueprint filenames
- do not invent alternate blueprint folders when a canonical lane exists

## Canonical Enums

### `project`

- `pete`
- `pvt-sim`
- `fault-tensor`
- `claude-config`
- `gpt-config`
- `coursework`
- `workspace`

### `status`

- `draft`
- `active`
- `blocked`
- `completed`
- `superseded`
- `archived`

### `category`

- `feature`
- `refactor`
- `migration`
- `debug`
- `infrastructure`
- `research`
- `config`
- `workflow`

### `strategic_role`

Optional. When used, it must be one of:

- `blocker`
- `accelerator`

## Required Frontmatter

Required fields:

- `project`
- `implementer`
- `repo`
- `target`
- `status`
- `category`
- `created`
- `updated`
- `links`
- `related`
- `external_links`
- `blocked_by`
- `supersedes`
- `superseded_by`

Optional fields:

- `strategic_role`
- `completed`
- `parent_plan`

## Canonical Body Sections

Every emitted blueprint should contain these sections in order:

1. `# Blueprint: <Human Readable Title>`
2. `## Objective`
3. `## Context`
4. `## Scope`
5. `## Constraints`
6. `## Implementation Plan`
7. `## Validation / Acceptance Criteria`
8. `## Risks / Dependencies`
