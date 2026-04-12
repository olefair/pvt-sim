---
name: read-repo
description: Read and orient within a code repository before deeper work. Use when asked to understand a repo, map architecture, locate entrypoints, find likely touchpoints for a bug or feature, summarize a codebase area, or do a pre-investigation/pre-implementation scan. Prefer this as the first step before debug, code review, migration planning, or refactoring when repo context is incomplete.
---

# Read Repo

Build a grounded picture of the repository without modifying it.

## Core behavior

- Start with the smallest useful scan, not a full-repo dump.
- Read real files, not just filenames.
- Prefer targeted search and selective reads over exhaustive ingestion.
- Treat this as a read-only orientation pass unless the user explicitly asks for edits.

## Workflow

1. Confirm scope.
   - Use the current working directory unless the user specifies a subdirectory or repository path.
   - If the task names a bug, feature, file, error string, route, API, or module, use that as the search seed.

2. Inventory the repo shape.
   - Use `exec` to inspect the top-level structure.
   - Prefer a fast file manifest when possible.
   - Use this search fallback pattern when needed:

```bash
if [ -x /usr/bin/rg ]; then
  RG=/usr/bin/rg
elif command -v rg >/dev/null 2>&1; then
  RG=$(command -v rg)
else
  RG=
fi
```

   - If `RG` is available, use it for file listing and content search.
   - If not, fall back to `find`, `grep`, and targeted `ls`.

3. Read high-signal files first.
   - Typical examples: `README*`, `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, `Dockerfile`, CI config, test config, top-level app entrypoints.
   - Read only the minimum needed to establish architecture and workflow.

4. Search by concept.
   - Search for user-provided terms, function/class/module names, error strings, route names, config keys, and likely related components.
   - Read only the files and sections surfaced by the search.

5. Produce a structured orientation.
   - Summarize likely entrypoints, relevant files, observed structure, likely touchpoints, and unknowns.
   - Do not claim full understanding if only partial inspection was done.

## Output format

Use this stable structure:

```md
## Repo Readout
- Scope: <repo or subdir>
- Task focus: <bug/feature/question>

### Likely entrypoints
- <file>: <why it matters>

### Relevant files
- <file>: <role>

### Observed structure
- Runtime/build: <summary>
- Tests: <summary>
- Data/config: <summary>

### Likely touchpoints
1. ...
2. ...

### Unknowns / next best reads
- ...
```

## Evidence discipline

Distinguish clearly between:
- **Observed** — directly verified from files or command output
- **Inferred** — a strong interpretation from observed evidence
- **Unknown** — not yet verified

## Boundaries

- Do not modify code or files unless explicitly asked.
- Do not pretend repo understanding from filenames alone.
- Do not silently expand into debugging, implementation, or review unless the user asks or the parent skill explicitly requires it.
