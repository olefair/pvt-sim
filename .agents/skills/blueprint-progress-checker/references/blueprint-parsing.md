# Blueprint Parsing Reference

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

How to extract structured milestone data from uploaded blueprint documents.

---

## Expected Blueprint Structure

Blueprints come in different formats but share common patterns. Your job is
to normalize any format into the structured milestone format that the
blueprint progress workflow expects.

## Recognizing Milestones

Look for these patterns (in priority order):

1. **Explicit milestone headers**: `## M1: ...`, `### Milestone 1: ...`,
   `## Phase 1: ...`
2. **Numbered sections with checklists**: `## 1) Feature Name` followed
   by `- [ ]` items
3. **Task groups under headings**: Any `##` or `###` heading followed by
   file paths, function names, or test references
4. **Flat checklists**: A single `- [ ]` list without grouping — treat
   each logical group of related items as one milestone

## Extracting Per-Milestone Data

For each milestone, extract:

### new_files
Look for:
- `Create \`path/to/file.py\``
- `- [ ] Create \`path/to/file.py\``
- `New file: path/to/file.py`
- Paths mentioned under "New files" or "Files to create" headings
- Any path in backticks that doesn't currently exist in the repo

Format: `{"path": "relative/path.py", "description": "what this file does"}`

### modified_files
Look for:
- `Modify \`path/to/file.py\`` or `Update \`path/to/file.py\``
- `Add \`function_name()\` to \`path/to/file.py\``
- `- [ ] Modify \`path/to/file.py\``
- Function names in backticks near file paths
- Patterns like "add X to Y", "extend Y with X", "update Y to support X"

Format: `{"path": "relative/path.py", "functions": ["fn1", "fn2"], "description": "..."}`

### test_files
Look for:
- Paths containing `test_` or in `tests/` directories
- `- [ ] Add test \`tests/test_foo.py\``
- `Verify: ...` followed by test file references
- Success criteria that mention specific test files

Format: `{"path": "tests/test_foo.py", "verifies": "what this test checks"}`

### success_criteria
Look for:
- `- [ ] Verify: ...` patterns
- Text under "Success Criteria" headings
- Sentences starting with "must", "should", "shall"
- Items in "Definition of Done" sections
- Acceptance criteria patterns

Format: Plain string list.

## Handling Ambiguous Blueprints

If the blueprint is loose (no explicit milestones), create synthetic milestones:

1. Group related items by the files they touch
2. Order by dependency (infrastructure first, integration last)
3. Name them M1, M2, etc. with descriptive names
4. Flag to the user: "I've organized this into N milestones based on
   file grouping — adjust if this doesn't match your intent"

## Handling Blueprint Variants

### Full blueprint (has milestones, files, criteria)
Parse directly — all fields should map cleanly.

### Spec-only (describes what to build, no file guidance)
Infer file paths from the repo's existing structure:
- If the repo has `app/plugins/`, new features probably go there
- If tests are in `tests/`, new tests go there
- Match naming conventions from existing files

### Checklist-only (flat list of - [ ] items)
Group by theme. Each group becomes a milestone.
Items that reference the same file go in the same milestone.

## Validation

After parsing, verify:
- Every `path` uses forward slashes and is relative to repo root
- No duplicate file paths across milestones (a file should only appear once)
- Every milestone has at least one concrete item (file or criterion)
- Dependencies between milestones are acyclic
