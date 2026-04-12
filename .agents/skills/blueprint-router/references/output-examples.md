# Output Examples

## Example A: Exact match

~~~markdown
## Blueprint routing result

**Verdict:** existing blueprint found

### Best match
- `docs/blueprints/codex/workspace/blueprint_llm-chat-endpoint-benchmark.md` - matches the same benchmark target and optional local-server constraint; canonical path/frontmatter verified.

### Other possible matches
- `docs/blueprints/codex/workspace/blueprint_cli-json-scaffold-benchmark.md` - related benchmark scaffold, but different implementation target.

### Recommended next step
Use the best match as the controlling blueprint and compare its success criteria to the current repo state.

### Suggested prompt
Use `docs/blueprints/codex/workspace/blueprint_llm-chat-endpoint-benchmark.md` as the controlling blueprint for the implementation currently under discussion. Summarize its success criteria, identify any mismatch with the current repo state, and propose the next small reversible implementation step.
~~~

## Example B: Related but noncanonical match

~~~markdown
## Blueprint routing result

**Verdict:** related blueprint found, but not exact

### Best match
- `docs/blueprints/Codex/automation/blueprint-router.md` - related routing workflow precedent, but it is legacy/noncanonical and does not exactly match the current scope.

### Recommended next step
Use this document as supporting context only. If the current work still needs its own controlling blueprint, create a new one at a canonical path.

### Suggested prompt
Use `docs/blueprints/Codex/automation/blueprint-router.md` as supporting context only. Draft a new controlling blueprint for the current implementation using the canonical blueprint path and frontmatter contract.
~~~

## Example C: No strong match

~~~markdown
## Blueprint intake brief

### Working title
Blueprint router for existing-vs-missing blueprint detection

### Suggested canonical path
`docs/blueprints/codex/workspace/blueprint_blueprint-router.md`

### Canonical frontmatter seed
```yaml
---
project: workspace
implementer: codex
repo: tools
target: blueprint-router
status: draft
category: workflow
created: 2026-03-19
updated: 2026-03-19
links: []
related: []
external_links: []
blocked_by: []
supersedes: []
superseded_by: []
---
```

### Implementation summary
Create a lightweight workflow that checks whether the implementation currently being discussed already has a blueprint under `docs/blueprints`. If a match exists, return the best file path and a short explanation. If no strong match exists, generate a compact intake brief that can be handed to desktop ChatGPT to author the full blueprint.

### Problem to solve
- implementation discussions can duplicate blueprint work because existing blueprints are easy to miss

### Goal
- route current work to an existing blueprint when one exists
- otherwise generate a high-signal intake brief instead of a full blueprint

### Affected areas
- docs/blueprints
- blueprint naming and routing workflow
- downstream desktop blueprint-authoring flow

### Constraints
- do not write the full blueprint automatically
- keep output concise and paste-ready
- avoid false positives on weak keyword overlap

### Non-goals
- autonomous implementation
- repo-wide refactoring beyond the routing workflow

### Success criteria
- returns exact file path when a strong blueprint match exists
- distinguishes exact matches from merely related ones
- emits a usable intake brief when no strong match exists

### Suggested prompt
Turn the intake brief below into a concrete implementation blueprint. Write the output to the suggested canonical path unless the user has explicitly requested a different location. Preserve the canonical frontmatter contract, required body sections, and existing verified repo details. Do not invent repo details that are not stated.
~~~
