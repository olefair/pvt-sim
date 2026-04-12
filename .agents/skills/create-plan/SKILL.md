---
name: create-plan
description: >
  Use this skill whenever the user wants a durable strategic plan note rather
  than a conversational plan. It writes canonical plan-family markdown that
  governs broad, layered work under a parent plan and decomposes that scope
  into bounded child blueprints or one shallow layer of child plans. Trigger
  for "write a plan", "create a parent plan", "roadmap this work", "decompose
  this into child blueprints", "turn this into a plan document", "make the
  orchestration note", or any request for a canonical plan artifact under
  docs/plans/<project_name>/plan_<slug>.md. Do NOT trigger for single bounded implementation
  units that should stay blueprints (use blueprint-architect), migration-only
  transformations (use migration-planner), refactor-only prescriptions (use
  refactor-advisor), or the conversational style-plan mode.
---

# Create Plan

Produce a canonical plan note that governs multiple bounded execution units
without collapsing into one oversized implementation prompt.

## MCP-Free Execution Rule

This skill must not depend on any MCP server. Use direct file reads, `rg`,
directory listings, and the real workspace docs as the source of truth.

## Workspace Vault Contract

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
- `docs/templates/specs/template_plan-canonical_v3_2026-03-17.md`

Use the shared intake and backlink workflow from the fourth note for `links`,
`related`, lineage fields, reciprocal decomposition links, body wikilinks, and
backlink fallback search. The plan-specific rules below are deltas, not
substitutes.

When consuming existing vault notes, parse frontmatter before interpreting the
body, read every note in `links` before acting, inspect `related` whenever the
active task touches adjacent context, use `external_links` only when they
materially affect the plan, and follow `superseded_by` to the current note
unless the user explicitly wants historical context.

## Output Contract

- Canonical path: `docs/plans/<project_name>/plan_<slug>.md`
- Workspace path: `docs/plans/workspace/plan_<slug>.md`
- The project directory is the only routing subfolder under `docs/plans/`
- `plan_` is the canonical filename prefix for all plan notes
- `<slug>` is the filename stem for the plan note, not a subdirectory name
- If revising an existing plan, preserve the current filename unless there is a
  real canonicalization reason to rename it
- Do not put dates in active plan filenames
- `project_name` must match the canonical plan enum; use `workspace` only for
  true cross-project coordination
- `<slug>` is the durable umbrella identifier for that plan scope
- Required frontmatter: `project`, `repos`, `status`, `category`, `created`,
  `updated`, `links`, `related`, `external_links`, `child_plans`, and
  `child_blueprints`
- Optional when materially true: `projects`, `completed`, `agent_surface`,
  `produced_by`, `parent_plan`, `supersedes`, `superseded_by`
- For vault-native links, use Obsidian wikilinks in `links`, `related`,
  `parent_plan`, `child_plans`, `child_blueprints`, `supersedes`, and
  `superseded_by`
- If this skill authored the note, prefer `produced_by: create-plan` and the
  actual execution surface in `agent_surface`
- A plan exists only when the scope truly requires multiple child blueprints,
  or a short-lived provisional state before those children are finished
- If there are no child notes yet, the body must explicitly say
  **provisional decomposition pending**
- If the scope can be executed cleanly as one bounded implementation unit, do
  not write a faux plan; route to blueprint-architect instead

## Workflow

### Phase 1: Prove This Should Be a Plan

1. Identify the governing outcome, repos, workstreams, and acceptance surfaces.
2. Decide whether the scope is orchestration or implementation:
   - If one bounded unit can own the whole result, it is a blueprint.
   - If the work needs multiple bounded execution units, sequencing gates, or
     cross-workstream coordination, it is a plan.
3. Choose the canonical `project_name`, plan slug, and
   `category` before drafting.

### Phase 2: Build the Governing Context

1. Read the frontmatter first, then the body, of the governing spec,
   blueprint, audit, brief, handoff, or prior plan.
2. Follow the vault intake order:
   - read `links`
   - read materially required `external_links`
   - read `related`
   - inspect lineage and dependency fields, including `superseded_by`
   - inspect body wikilinks
   - run a backlink fallback search when needed
3. Record the minimum context the plan must carry forward: objective, scope,
   constraints, blockers, repo list, and decision points that children must not
   re-litigate.

### Phase 3: Decompose the Scope

Read `references/plan-decomposition-rubric.md` before drafting the child map.

Partition the work by one or more of these hard boundaries:

- dominant responsibility or ownership surface
- coupled write surface
- dominant verification or acceptance surface
- gating dependency that must land before other work
- repo or project boundary when coordination crosses workspaces

Prefer direct child blueprints. Introduce child plans only when one parent plan
would otherwise become an unreadable pile of siblings or when coordination
needs a project-level split before implementation. Do not go deeper than:

`parent plan -> child plan -> child blueprint`

### Phase 4: Sanctify Child Tasks Before Admission

Every child blueprint or child plan must earn its slot under the parent plan.
Admit it only when all of the following are true:

- it has one primary outcome that fits in a single sentence
- it has one coherent write surface or tightly coupled cluster
- it has explicit in-scope and out-of-scope boundaries
- it has named validation or exit criteria
- it has named blockers or states that no blockers exist
- an implementer can hold the relevant context without dragging in the full
  parent initiative on every pass

Split the child if it bundles unrelated write surfaces, unrelated validation
modes, or multiple decisions that should be resolved independently. Merge or
drop the child if it cannot be validated independently and only exists as a
trivial sub-step inside another bounded unit.

### Phase 5: Render the Plan Note

Write the canonical plan note with the template body structure:

- `# Plan: <Human Readable Title>`
- `## Objective`
- `## Context`
- `## Scope`
- `## Decomposition Strategy`
- `## Child Plan / Blueprint Map`
- `## Sequencing / Gates`
- `## Validation / Exit Criteria`
- `## Risks / Open Questions`
- `## Notes`

In the child map, state for each child:

- the responsibility boundary
- what the child must not absorb from siblings
- the gating relationship to other children
- the acceptance boundary that makes it independently executable

If the task also includes authoring or updating child blueprints, enforce the
reciprocal decomposition contract:

- the parent plan lists the child in `child_blueprints` or `child_plans`
- each child carries `parent_plan`
- the governing plan appears in the child's `links` when it is required reading

### Phase 6: Sanity Check the Note

Before finalizing, verify all of the following:

- the note is genuinely orchestration, not implementation detail in disguise
- `child_plans` and `child_blueprints` are not both empty unless the note says
  **provisional decomposition pending**
- the child set covers the full scope without overlap or orphaned work
- no child boundary is defined only by chronology; each one has a real
  responsibility and validation surface
- the plan does not smuggle scope creep with catch-all children like
  "cleanup", "misc hardening", or "follow-up tasks"

## Usage Patterns

- **"Write a plan for this initiative"**: run the full workflow and emit the
  canonical plan note.
- **"Should this be a plan or a blueprint?"**: do Phase 1 only, explain the
  decision, and route accordingly.
- **"Turn these blueprints into a parent plan"**: ingest the existing children,
  derive the decomposition strategy, and write the governing plan note.
- **"We need an umbrella over several repos or projects"**: use a workspace or
  higher-level project plan and introduce one shallow child-plan layer only if
  the sibling set would otherwise become unmanageable.

## References

- Read `references/plan-decomposition-rubric.md` whenever the split between
  parent plan, child plan, and child blueprint is not obvious.

## Edge Cases

- If the scope can be executed as one bounded implementation unit, do not force
  a plan; route to `blueprint-architect`.
- If the correct plan `project_name` is ambiguous, prefer the concrete project
  over `workspace`; use `workspace` only for true cross-project coordination.
- If an older plan already exists with a noncanonical filename, preserve it
  while revising unless there is a real canonicalization reason to rename it.
