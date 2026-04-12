# Skill Compatibility Checks

Use this pass to decide whether the skill is operationally sane in the target
environment even if it appears safe at first glance.

## Environment Fit

- commands match the host OS and shell
- any PowerShell, bash, Python, or node usage is plausible for the target
  environment
- tool names are real and available for the intended host
- the skill does not assume Claude/OpenClaw/Codex-specific capabilities that do
  not exist on the target platform

## File and Path Sanity

- every referenced script, hook, asset, and document actually exists
- relative links in `SKILL.md` resolve to real files
- output paths are explicit, writable, and inside the expected workspace unless
  there is a strong reason otherwise
- hidden directories or generated files have an explained purpose

## Metadata Alignment

- `SKILL.md` description, `agents/openai.yaml`, and reference docs all describe
  the same workflow
- `default_prompt` does not widen the skill beyond the written instructions
- display metadata is not leaking frontmatter, stale descriptions, or the wrong
  skill name

## Pete Workspace Pass

If the skill lives under `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\`:

- read `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\SKILL_STANDARD.md`
- compare against at least two neighboring curated skills in the same source
  tree
- run `python C:\Users\olefa\dev\pete-workspace\tools\scripts\validate_skills.py`
- run `python C:\Users\olefa\dev\pete-workspace\tools\scripts\sync_skill_openai_yaml.py`
  without `--write`
- if a packaged `.skill` exists, compare its contents against the folder source

Fail this pass when the skill could not actually run as advertised, or when the
packaged surface materially differs from the reviewed source surface.
