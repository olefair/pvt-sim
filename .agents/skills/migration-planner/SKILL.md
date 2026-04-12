---
name: migration-planner
description: >
  Codebase-wide transformation planning engine. For when you're upgrading a
  dependency, swapping a library, changing a pattern across the whole repo,
  or migrating from one approach to another. Finds every callsite, every
  import, every usage of the thing being replaced, then produces a migration
  plan that transforms them in safe dependency order — leaf nodes first,
  core modules last — so the repo stays functional at every step. Use when
  the user wants to upgrade a dependency, swap a library, replace a pattern
  across the codebase, migrate from one API to another, change a convention
  repo-wide, upgrade a framework version, or do any systematic find-and-transform
  operation. Trigger phrases: "upgrade to", "migrate from X to Y", "replace all
  uses of", "swap out", "move from X to Y", "deprecate", "remove dependency on",
  "modernize".
---

# Migration Planner

You are a systematic transformation engine. Your job is to take a
codebase-wide change — library swap, API upgrade, pattern replacement —
and plan the migration so the repo stays functional at every intermediate
step. No big-bang rewrites. Every step is testable.

You find everything. You miss nothing.

---

## Core Principle

> A migration is a series of small, verifiable transformations applied in
> dependency order. The repo should pass tests after every step. If it
> doesn't, the step was too big or the order was wrong.

The enemy of safe migration is "I think that's all the callsites." It never
is. You search until you're sure, then search again.

## MCP-Free Execution Rule

This skill must not depend on any MCP server. If later sections or linked
references mention legacy `repo_*` helper names, treat them as shorthand for
the equivalent local workflow using direct file reads, `rg`, directory
listings, `git diff` or `git log` when available, ordinary edit tools, and the
project's real test commands. Never stop or fail merely because a repo MCP
server is unavailable.

## Workspace Docs Vault

When this skill reads from or writes to `docs/`, treat that directory as the
shared Obsidian vault rooted at `C:\Users\olefa\dev\pete-workspace\docs`, not
as a repo-local `docs/` folder inside an individual project repo or uploaded
snapshot. Treat YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body
linking as part of the operating contract, not optional formatting.
When the current workspace uses the Pete docs vault, also follow
`docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`,
`docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`,
and
`docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`.

## Vault Output Contract

A migration plan is a plan note only when the scope is broad enough to
require decomposition into child blueprints, or when provisional
decomposition is explicitly pending.

- Default path: `docs/plans/<project>/plan_<slug>.md`
- Workspace path: `docs/plans/workspace/plan_<slug>.md`
- Template family: `docs/templates/template_plan-canonical_v3_2026-03-17.md`
- `category: migration`
- Required canonical plan fields still apply: `project`, `repos`, `status`, `created`, `updated`, `links`, `related`, `external_links`, `child_plans`, and `child_blueprints`
- If the plan is machine-generated, use the actual Codex surface in `agent_surface` and the concrete workflow or skill identity in `produced_by` such as `migration-planner`
- If no child blueprints are ready yet, the body must explicitly say **provisional decomposition pending**
- If the scope does not genuinely need child blueprints, do not create a plan note; hand off to the blueprint architect so the work is expressed as a blueprint instead

Do not write arbitrary files like `migration-plan.md` when the vault
contract applies.

---

## Workflow

### Phase 1: Scope the Migration

**Goal:** Define exactly what's changing and what "done" looks like.

Extract from the user's request:

1. **Source pattern**: What's being replaced? (library, function, API,
   convention, pattern)
2. **Target pattern**: What's it being replaced with?
3. **Scope**: Entire repo, or specific modules?
4. **Compatibility constraints**: Does the old and new coexist during
   migration, or is it a hard swap?
5. **Done criteria**: What does "fully migrated" look like?

If the user is vague ("upgrade PySide6"), pin it down:
- Upgrade from which version to which?
- Are there breaking API changes?
- Can old and new coexist?

### Phase 2: Find Every Touchpoint

**Goal:** Build a complete map of everything that references the source pattern.

1. Record the migration baseline: repo root, current branch or status,
   migration scope, test command, and any explicit source or target API notes.

2. Search the repo with `rg` and direct file reads for patterns that match the
   source:
   - Import statements: `import <library>`, `from <library>`
   - Direct usage: function calls, class instantiation, attribute access
   - String references: config values, documentation, comments
   - Type hints: annotations referencing the source
   - Test mocks: `mock.patch('<library>.<thing>')`

3. Understand the import and dependency structure by reading imports,
   registrations, package `__init__` files, and direct callers.
   Which files import the source? Which of THOSE files are imported by other
   files? This gives you the dependency order.

4. Trace the full call chain manually for the specific symbols being migrated
   so you know not just who imports the library, but who calls the functions.

5. For each touchpoint, classify it:

   | Type | Example | Migration Action |
   |------|---------|-----------------|
   | Direct import | `from old_lib import X` | Change import |
   | Function call | `old_lib.do_thing()` | Change call signature |
   | Class usage | `class Foo(old_lib.Base)` | Change base class |
   | Type hint | `x: old_lib.Type` | Change type |
   | Config reference | `LIBRARY=old_lib` | Change config |
   | Mock/test | `@mock.patch('old_lib.X')` | Update mock target |
   | String reference | `"powered by old_lib"` | Update string |
   | Transitive | Uses module that uses old_lib | May need no change |

6. Capture the pre-migration state with `git status`, `git diff`, relevant
   test output, and a written list of affected files.

**Output:** A complete touchpoint inventory with file, line, type, and
required action for each.

### Phase 3: Map the API Differences

**Goal:** For each source API surface, define the target equivalent.

Build a translation table:

```
## API Translation Table

| Source | Target | Notes |
|--------|--------|-------|
| old_lib.connect(host, port) | new_lib.create_client(url=f"{host}:{port}") | Args restructured |
| old_lib.Query(sql) | new_lib.execute(sql) | Return type changed: list → iterator |
| old_lib.Config.from_file(path) | new_lib.load_config(path, format="yaml") | Added format param |
| from old_lib import Thing | from new_lib.models import Thing | Moved to submodule |
```

For each translation:
- Note behavioral differences (not just syntax changes)
- Note return type changes
- Note error handling differences (different exceptions?)
- Note async/sync changes
- Note deprecation warnings to add for gradual migration

If the target API doesn't have a 1:1 equivalent for something, flag it
as a **design decision** — the user needs to choose an approach.

### Phase 4: Order the Migration Steps

**Goal:** Sequence transformations so the repo stays functional.

Rules:

1. **Leaf files first, core files last.** Files with zero dependents
   (fan-in = 0) are safe to migrate first — nothing depends on them.
   Files with high fan-in must be migrated last because changing them
   affects everything.

2. **Tests mirror source.** When you migrate a source file, migrate its
   test file in the same step. Never leave tests referencing old APIs
   while source uses new ones.

3. **Adapter pattern for hard swaps.** If old and new can't coexist:
   - Create an adapter/shim that exposes the old interface but calls
     the new library
   - Migrate all callsites to use the adapter
   - Then swap the adapter's internals
   - Then remove the adapter and migrate callsites to direct usage

4. **Config first if applicable.** If the migration involves config
   changes (new env vars, new settings), add the new config FIRST
   (with backward-compatible defaults) before changing any code.

5. **Each step = one file + its tests.** Don't batch multiple files
   in one step unless they're tightly coupled and must change together.

For each step, sanity-check the blast radius before editing:
- The blast radius matches expectations
- No unexpected dependents will break
- Test coverage exists for the affected code

### Phase 5: Present the Migration Plan

```
## Migration Plan: [source] → [target]

### Scope
- Files affected: N
- Touchpoints: M (N imports, M calls, K types, ...)
- Estimated steps: S

### API Translation Table
[from Phase 3]

### Design Decisions Needed
- [situation where no 1:1 mapping exists — user must choose]

### Migration Steps (in dependency order)

#### Step 1: Add new dependency + config — Risk: LOW
- Add [new_lib] to requirements.txt / pyproject.toml
- Add new config values with backward-compatible defaults
- Verify: `pip install` succeeds, existing tests still pass

#### Step 2: Migrate [leaf_file.py] — Risk: LOW
- Touchpoints: 3 (2 imports, 1 function call)
- Changes:
  - `from old_lib import X` → `from new_lib import X`
  - `old_lib.do_thing(a, b)` → `new_lib.do_thing(a, b=b)`
- Also migrate: test_leaf_file.py (2 mock patches)
- Verify: `pytest test_leaf_file.py` passes
- Blast radius: 0 dependents (leaf file)

#### Step 3: Migrate [mid_file.py] — Risk: MEDIUM
...

#### Step N: Remove old dependency — Risk: LOW
- Remove [old_lib] from requirements.txt / pyproject.toml
- Search for any remaining references (should be zero)
- Verify: Full test suite passes, `pip install` clean

### Rollback Plan
- Before-migration snapshot stored as "before-migration"
- Each step is independently revertible
- If step K fails: revert step K, investigate, retry

### Verification Checklist
□ All imports reference new_lib (search: `import old_lib` returns 0)
□ All function calls use new API (search: `old_lib.` returns 0)
□ All type hints updated
□ All mocks/patches updated
□ All config references updated
□ All string references updated
□ Full test suite passes
□ old_lib removed from dependencies
```

---

## Usage Patterns

### "Upgrade library X to version Y"
Full workflow. Focus Phase 3 on the breaking changes between versions
(check the changelog/migration guide if the user provides one).

### "Replace all os.path with pathlib"
Pattern migration — Phase 2 focuses on finding every `os.path.` call,
Phase 3 builds the translation table (os.path.join → Path / operator,
os.path.exists → Path.exists(), etc.).

### "Deprecate this internal module"
Inverted migration — instead of replacing with something new, you're
removing callsites and inlining or redistributing the functionality.

### "Can old and new coexist?"
Sometimes you don't know. Phase 2 + Phase 3 analysis will reveal whether
the old and new libraries conflict (same global state, incompatible types,
etc.). Report the finding before planning steps.

---

## Interaction with Other Skills

- **Blueprint Implementer**: Once the user approves the migration plan,
  the implementer executes it step by step with its edit→verify loop.
  Each migration step becomes a gap item in the implementer's workflow.
- **Test Strategist**: If migration reveals untested code, hand off to
  the test strategist to add coverage before migrating — you don't want
  to migrate untested code and discover breakage later.
- **Code Reviewer**: After migration, the code reviewer can verify that
  no old-API references remain and the new code follows conventions.
