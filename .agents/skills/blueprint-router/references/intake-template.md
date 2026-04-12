# Blueprint Intake Brief Template

Use this template when no strong existing blueprint exists.

~~~markdown
## Blueprint intake brief

### Working title
[short, specific title for the likely blueprint]

### Suggested canonical path
`docs/blueprints/[implementer]/[project]/blueprint_[slug].md`

### Canonical frontmatter seed
```yaml
---
project: [canonical project enum]
implementer: [claude|codex|cowork|human]
repo: [repo-name]
target: [implementation surface]
status: draft
category: [feature|refactor|migration|debug|infrastructure|research|config|workflow]
created: [YYYY-MM-DD]
updated: [YYYY-MM-DD]
links: []
related: []
external_links: []
blocked_by: []
supersedes: []
superseded_by: []
---
```

Optional frontmatter when relevant:
- `strategic_role: blocker|accelerator`
- `parent_plan: [path or id]`
- `completed: [YYYY-MM-DD]`

### Implementation summary
[2-4 sentences describing the change in plain language]

### Problem to solve
- [current friction, missing capability, or failure mode]

### Goal
- [what the implementation should achieve]

### Affected areas
- [repo / project]
- [folders, files, modules, commands, workflows]

### Constraints
- [technical, operational, UX, dependency, or environment constraints]

### Non-goals
- [things this blueprint should explicitly avoid]

### Success criteria
- [observable result 1]
- [observable result 2]
- [observable result 3]

### Open questions
- [only include real unresolved questions that materially affect the blueprint]
~~~

## Downstream Prompt Template

Always append this after the intake brief so the user can hand it directly to
desktop ChatGPT or another agent.

```markdown
Turn the intake brief below into a concrete implementation blueprint. Write the output to the suggested canonical path unless the user has explicitly requested a different location. Preserve the canonical frontmatter contract, required body sections, and existing verified repo details. Do not invent repo details that are not stated.
```
