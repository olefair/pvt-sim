# Workspace Skill Template

Use this template when a proven learning graduates into a reusable workspace
skill. It follows the Pete workspace standard rather than the original
upstream/ClawdHub layout.

## Required Files

Every installable workspace skill should contain:

- `SKILL.md`
- `references/` with at least one reference document
- `agents/openai.yaml`

Optional:

- `scripts/`
- `assets/`

## `SKILL.md`

```markdown
---
name: skill-name-here
description: >
  State what the skill does, when to use it, and its trigger surface.
---

# Skill Name

One-sentence purpose.

## Output Location

[If the skill writes files, state the exact path, naming rule, and format.
If it does not write files, say so plainly.]

## Workflow

1. Step one
2. Step two
3. Verification or handoff

## References

- `references/output-template.md` - say when to read it

## Failure Modes

- main guardrail
- main edge case
```

## `references/output-template.md`

```markdown
# Output Template

[Put the durable schema, routing rules, template, or decision table here.]
```

## `agents/openai.yaml`

```yaml
interface:
  display_name: "Skill Name"
  short_description: "Short UI description."
  default_prompt: "Use $skill-name-here for [default invocation guidance]."

policy:
  allow_implicit_invocation: false
```

## Extraction Checklist

Before promoting a learning into a skill:

- [ ] The solution is tested and real
- [ ] The content is broadly reusable, not a one-off repo note
- [ ] The skill name follows lowercase-hyphen format
- [ ] The trigger surface is explicit in `description`
- [ ] The scaffold includes `references/` and `agents/openai.yaml`
- [ ] Any scripts are necessary and documented
- [ ] Packaging will happen from `tools/SKILLS/folders/<skill-name>/`

## Packaging Reminder

Package from:

- `tools/SKILLS/folders/<skill-name>/`

Into:

- `tools/SKILLS/packages/<skill-name>.skill`

The archive root must stay flat:

- `SKILL.md`
- `references/...`
- `agents/openai.yaml`
