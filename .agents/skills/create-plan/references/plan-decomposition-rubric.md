# Plan Decomposition and Task Sanctification Rubric

Read this before Phase 3 or Phase 4 of `create-plan`, and again whenever a
candidate child feels either too large or too tiny.

## Parent Plan Umbrella

The parent plan owns:

- the coordination outcome
- shared context that all children inherit
- sequencing and gating rules
- cross-child risks and open questions
- the canonical map of child plans and child blueprints
- the canonical parent note located at `docs/plans/<project_name>/<plan_stub>.md`

The parent plan does **not** own:

- line-by-line implementation steps
- file-level edit prescriptions for every child
- verification details that belong entirely inside one child blueprint
- catch-all "everything else" work

If the parent note starts reading like an execution prompt, it has absorbed too
much from its children.

## Direct Child Blueprints vs Child Plans

Prefer direct child blueprints when most of these are true:

- the scope stays within one project or one tight repo cluster
- the number of child units is still readable as one flat set
- each child has a clear execution boundary
- cross-child gating is simple enough to express in one sequencing section

Introduce one shallow child-plan layer when most of these are true:

- the initiative spans multiple projects or clearly separate domains
- one flat child set would be noisy or hard to navigate
- each domain has its own local sequencing logic before implementation
- the parent plan would otherwise become a second blueprint architect pass for
  every child

Never create a deep hierarchy. Stop at:

`parent plan -> child plan -> child blueprint`

## Task Sanctification Checklist

A child task is sanctified only when it passes every gate below.

### 1. Outcome Gate

Pass:
- one primary outcome, stated in one sentence

Split:
- "and", "plus", or "while also" is carrying separate deliverables

Reject:
- the child is just a vague intent like "improve reliability"

### 2. Write-Surface Gate

Pass:
- one dominant write cluster or tightly coupled file family

Split:
- the child spans unrelated modules, repos, or document families that do not
  need to move together

Reject:
- the child is only a tiny edit that cannot stand as its own execution unit

### 3. Validation Gate

Pass:
- one coherent acceptance bundle can prove the child complete

Split:
- success requires unrelated test suites, review modes, or acceptance surfaces

Reject:
- completion can only be inferred after several other siblings land

### 4. Boundary Gate

Pass:
- explicit in-scope and out-of-scope statements

Split:
- the child starts inheriting neighboring cleanup or speculative hardening

Reject:
- the child depends on ad hoc judgment during implementation to decide what
  else to absorb

### 5. Context-Load Gate

Pass:
- an implementer can reopen the relevant files and notes and keep the active
  problem in working memory without carrying the entire initiative

Split:
- the child requires constant switching across several independent problem
  spaces

Reject:
- the child is so tiny that an implementer would need the parent and sibling
  context just to understand why the task exists

## Anti-Patterns

Do not decompose by:

- chronology alone
- arbitrary file counts
- team politics without technical boundaries
- one giant child called "final cleanup"
- one giant child called "hardening"
- one parent plan with no real children

Do not sanctify a task that depends on unresolved architecture questions. Solve
the decision first, or make the decision itself a bounded child.

## Scope Creep Controls

Use these rules when implementation pressure starts to blur boundaries:

- New work that fits an existing child boundary may extend that child.
- New work that crosses two child boundaries should trigger a parent-plan
  revision or a new child note, not silent expansion.
- If a child can no longer be described without referencing multiple sibling
  acceptance criteria, the decomposition is drifting and needs repair.
- Every child map entry should name at least one thing it must not absorb.

## Reciprocal Linking Contract

For every governed child:

- the parent plan lists it in `child_blueprints` or `child_plans`
- the child stores the parent in `parent_plan`
- if the plan is required reading, the child includes the plan in `links`

These are operational links, not decorative backlinks.

## Mini Example

Good split:

1. Shared contract blueprint
   - establishes the schema or contract every other child depends on
2. Validation pipeline blueprint
   - adds or updates the checks that enforce the contract
3. Surface hardening blueprint
   - updates the concrete skill or product surfaces to comply

Why this works:

- each child has a distinct write surface
- each child has a distinct acceptance boundary
- sequencing is explicit without making any child trivial
- implementation agents can stay inside one local context at a time
