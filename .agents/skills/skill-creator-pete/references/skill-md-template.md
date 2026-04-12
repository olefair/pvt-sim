# SKILL.md Template

Copy this structure when writing a new skill.

---

```markdown
---
name: skill-name-kebab-case
description: >
  One paragraph. First sentence: what it does.
  Second sentence: what tools/sources it uses and what it produces.

  TRIGGER on: [explicit trigger phrases, slash commands, keywords].
  Also trigger when [natural language patterns that indicate this skill].

  Do NOT trigger for [anti-patterns — what looks similar but isn't this skill].

compatibility:
  required_tools:
    - tool-name (what it's used for)
---

# Skill Title

One sentence: what you are and what your job is.

---

## Output Location

[If the skill produces files, specify exactly where they go and the naming convention.]
[If the skill does not produce files, omit this section.]

## Workspace Docs Vault

[Required for skills that read or write workspace docs.]
[State explicitly that `docs/` is the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local docs folder inside
an individual project repo or uploaded snapshot.]
[State that YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body
links are part of the operating contract.]

---

## Workflow

### Step 1: [Action]
[Instructions. Be specific about which tool to call and with what parameters.]

### Step 2: [Action]
[Instructions.]

[... continue for all steps]

---

## Reference Files

- [`references/[doc].md`](./references/[doc].md) — [When to read it and what it contains]

---

## Edge Cases

- **[Scenario]:** [How to handle it]
```

---

## Description Writing Guide

The description is the ONLY triggering mechanism. Claude decides whether to
consult a skill based on name + description alone. Rules:

- **Be pushy.** Undertriggering is the main failure mode. Tell Claude to use
  this skill even when the user doesn't explicitly ask for it by name.
- **List trigger phrases explicitly.** Include both slash commands (`/progress`)
  and natural language patterns ('where are we', 'what should I work on').
- **Include anti-patterns.** Tell Claude what NOT to trigger on, to avoid
  stealing triggers from other skills.
- **Keep it under 150 words.** The description is always in context — it costs
  tokens every time. Tight descriptions outperform verbose ones.

## Reference Doc Guide

Every skill needs at least one reference doc. Reference docs are loaded on
demand — they don't cost tokens unless the skill is active. Use them for:

- Output templates (copy-paste the exact format)
- Decision tables (when to do X vs Y)
- Data source details (API quirks, field names, known issues)
- Conventions (naming rules, path patterns)

Keep SKILL.md under 500 lines. Push anything that makes it longer into a
reference doc with a clear pointer in SKILL.md.
