---
name: blueprint-router
description: >
  Check whether the implementation work under discussion already has a
  controlling blueprint and route the user to the right next step. Searches
  `docs/blueprints` for existing blueprint documents, distinguishes exact
  matches from merely related ones, and when no strong match exists produces a
  compact intake brief plus a downstream prompt for blueprint authoring. Use
  when the user wants to know whether a blueprint already exists, avoid
  duplicate blueprint authoring, route implementation work to the right
  blueprint, or prepare intake for a new blueprint without writing the full
  blueprint directly.
---

# Blueprint Router

Use this skill to decide whether the current implementation work already has a
blueprint and to route the user to the right next step.

This skill does **not** write the full blueprint unless the user explicitly asks
for that. Its job is to:

1. search for an existing blueprint in the available `docs/blueprints` corpus
2. return the best matching file path(s) with a grounded explanation
3. note whether the best match follows the canonical blueprint path/frontmatter contract
4. produce a compact intake brief when no strong match exists
5. draft a prompt the user can paste into desktop ChatGPT or another agent to create the real blueprint

## Workspace Docs Vault

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or proposing notes there.

## Canonical Blueprint Contract

When this skill evaluates existing blueprints or prepares intake for a new one,
use the workspace's canonical blueprint naming, placement, and frontmatter
contract. Read and follow
`docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
and
`docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`
for canonical frontmatter semantics, `links` / `related` meaning, body
`[[wikilinks]]`, and backlink fallback expectations. See
`references/canonical-blueprint-template.md`.

- Preferred path: `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`
- `implementer` must be one of `claude`, `codex`, `cowork`, `human`
- `project` must use the canonical workspace enum
- filename must be `blueprint_<slug>.md`
- do not use dated filenames for blueprint notes
- required frontmatter fields:
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

If the best existing match is useful but noncanonical, still route to it, but
say that plainly instead of silently normalizing it.

## Workflow

### Step 1: Define the implementation target

Extract the implementation target from the current conversation.

Capture the smallest useful summary:

- repo or project name, if known
- feature / fix / refactor / automation / benchmark / CI task
- affected files, modules, commands, or workflows mentioned by the user
- constraints and success criteria already stated

If the target is still unclear after reading the current conversation, ask for
the minimum missing detail needed to search well.

### Step 2: Search for existing blueprints

Search the available blueprint corpus first. Prefer the user's actual
`docs/blueprints` tree when it is available through repo files, uploaded files,
or connected sources.

Search in this order:

1. likely exact filename or title matches
2. likely canonical-path matches under `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`
3. folder-specific matches
4. concept matches from the body text

Build queries from:

- repo / project names
- task nouns (`ci`, `benchmark`, `latency`, `workflow`, `smoke`, `router`, `prompt`, `automation`)
- important verbs (`add`, `check`, `route`, `implement`, `scaffold`, `validate`)
- distinctive file or command names, if present

When searching, prefer precision over breadth once you have 1-3 plausible
candidates.

### Step 3: Validate canonicality

For each strong candidate, verify as much of the canonical contract as the
available context allows.

- If you can read the file, verify whether the frontmatter contains the required fields.
- If you only have a file list or search results, judge by path and filename and
  say that frontmatter is unverified.
- Mark the candidate as one of:
  - `canonical`
  - `legacy/noncanonical`
  - `path looks canonical, frontmatter unverified`

Canonicality does not override relevance. A noncanonical blueprint can still be
the best controlling document if it is the closest scope match.

### Step 4: Classify the result

Use exactly one of these verdicts:

- **existing blueprint found**
- **related blueprint found, but not exact**
- **no strong match**

Only use **existing blueprint found** when the overlap is real in scope, not
just a shared keyword.

A strong match usually shares most of these:

- same implementation goal
- same repo or subsystem
- same main constraint or success criterion
- same type of work (feature, refactor, benchmark, CI, automation, migration)

If results are only adjacent or partial, mark them as **related blueprint found,
but not exact**.

Never pretend a weak match is exact just to avoid creating intake.

### Step 5: Respond in one of two modes

#### Mode A: Existing or related blueprint found

Return a concise routing result using this structure:

```markdown
## Blueprint routing result

**Verdict:** existing blueprint found

### Best match
- `relative/path/to/file.md` - one-line reason, including canonical status

### Other possible matches
- `relative/path/to/file.md` - one-line reason
- `relative/path/to/file.md` - one-line reason

### Recommended next step
[one sentence telling the user whether to open the best match, reuse it directly, or spawn a blueprint/implementation sub-agent around it]
```

Also include a short reusable prompt:

```markdown
### Suggested prompt
Use `docs/blueprints/.../file.md` as the controlling blueprint for the implementation currently under discussion. Summarize its success criteria, identify any mismatch with the current repo state, and propose the next small reversible implementation step.
```

If the best match is not canonical, say so in the reason line or recommended
next step.

#### Mode B: No strong match

Do **not** write the full blueprint. Instead, produce a compact Markdown intake
brief using the template in `references/intake-template.md`.

The intake brief must be specific enough that desktop ChatGPT or another agent
can turn it into a real blueprint without re-asking obvious questions.

Always include:

- a suggested canonical blueprint path
- a canonical frontmatter seed for the downstream authoring model
- a ready-to-paste prompt block that tells the downstream model to convert the
  intake brief into a canonical blueprint

## Reliability Rules

- Treat the user's existing folder structure as authoritative context, but new
  blueprint documents should use the canonical contract unless the user
  explicitly asks otherwise.
- Prefer exact file paths over vague references like "there's already a doc for
  that."
- Keep the answer compact. The output is a routing decision, not a research
  report.
- If search access to the blueprint corpus is unavailable, say so plainly and
  ask for the `docs/blueprints` directory, a file list, or a zip.
- If multiple blueprints overlap, choose the best controlling document and label
  the others as supporting context.
- If the user explicitly wants the blueprint created, hand off cleanly by
  producing the intake brief and a downstream prompt instead of expanding into
  blueprint authoring yourself.
- Do not invent alternate blueprint directories, filenames, or frontmatter
  shapes for new blueprint notes.

## Resources

- For the intake brief template, see `references/intake-template.md`.
- For match thresholds and search heuristics, see `references/routing-rules.md`.
- For canonical blueprint naming, placement, and frontmatter, see `references/canonical-blueprint-template.md`.
- For output examples, see `references/output-examples.md`.
