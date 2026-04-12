# Routing Rules

## Match Thresholds

Use these thresholds consistently.

### Existing blueprint found

Use this when the candidate matches the current work on scope and intent.

Signals:

- same repo or subsystem
- same type of task
- same primary success criterion
- same implementation direction

### Related blueprint found, but not exact

Use this when the candidate is adjacent, supportive, or partially overlapping.

Signals:

- same repo, different deliverable
- same deliverable type, different subsystem
- useful precedent or scaffold, but not the controlling document

### No strong match

Use this when the overlap is mostly keyword-level or the candidate would clearly
mislead implementation.

## Search Heuristics

Prefer these clues in order:

1. explicit repo name or project name
2. canonical path candidates under `docs/blueprints/<implementer>/<project>/blueprint_<slug>.md`
3. feature name, task label, or blueprint id
4. stable technical nouns (`workflow`, `latency`, `benchmark`, `smoke`, `router`, `prompt`, `regression`)
5. exact file or folder names
6. distinctive constraints (`no external deps`, `optional local server`, `in-process isolates`)

## Canonicality Rules

- Prefer canonical blueprint files when relevance is otherwise equal.
- If a noncanonical file is the best scope match, return it and label it
  `legacy/noncanonical`.
- If the path looks canonical but you cannot read the file, say that frontmatter
  is unverified.
- When producing intake for a new blueprint, always emit a canonical path and
  frontmatter seed.

## Output Discipline

- Return no more than 3 candidates unless the user asks for more.
- Always provide exact relative paths.
- Always state the verdict explicitly.
- Keep reasons short and evidence-based.
- Never collapse `related` into `existing`.
- Always include a downstream paste-ready prompt.
