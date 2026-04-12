---
name: pete-skill-library-auditor
description: >
  Run the repo-local Pete tools skill-library audit wrappers for deterministic
  verification of tools/SKILLS folder/package parity, packaging sanity,
  validator health, and regression status. Use when the user wants to audit the
  Pete workspace skill library, check tools/SKILLS, verify packaged skills, or
  run the wrapper-backed skill audit automation manually. Triggers: Pete skill
  library audit, tools skills audit, package parity audit, validate workspace
  skills, audit tools/SKILLS, check skill packaging. Do NOT trigger for
  third-party one-off skill vetting or for Codex skills outside Pete-workspace.
---

# Pete Skill Library Auditor

Run the approved Pete tools skill-library audit wrappers. This skill is for the
workspace skill library under `tools/SKILLS`, not for imported third-party
packages and not for `C:\Users\olefa\.codex\skills`.

---

## Output Location

- Default output is the wrapper's markdown report in chat.
- The full-library wrapper does not write a vault note by default. It prints a
  deterministic report built from validator, package-audit, regression, and
  test results.
- If the user explicitly asks for a persisted note, say so and route it as an
  audit only after the wrapper report is complete.

---

## Workflow

### Step 1: Read the local contract

Read these first:

- `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\README.md`
- `C:\Users\olefa\dev\pete-workspace\tools\SKILLS\SKILL_STANDARD.md`
- `C:\Users\olefa\dev\pete-workspace\docs\plans\workspace\plan_skill-governance-and-surface-hardening.md`

### Step 2: Choose full-library or single-skill mode

Use full-library mode by default:

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\run_pete_skill_library_audit.py
```

Use single-skill mode only when the user narrows scope to one skill:

```powershell
python C:\Users\olefa\dev\pete-workspace\tools\scripts\audit_skill_package.py --skill-dir C:\Users\olefa\dev\pete-workspace\tools\SKILLS\folders\<skill-name> --archive C:\Users\olefa\dev\pete-workspace\tools\SKILLS\packages\<skill-name>.skill
```

Run from `C:\Users\olefa\dev\pete-workspace\tools`.

### Step 3: Return the wrapper evidence

For the full-library wrapper, report:

- overall status
- counts
- check results
- top findings
- notes

If a command check fails, preserve the first failing summary exactly. Do not
replace it with a softer paraphrase.

### Step 4: Scope discipline

Do not use this skill for:

- `C:\Users\olefa\.codex\skills`
- generic skill creation
- third-party import vetting

For those surfaces, use the dedicated workflow instead.

---

## Reference Files

- [`references/checks-and-commands.md`](./references/checks-and-commands.md) -
  wrapper coverage, command entrypoints, and what each check means.

---

## Edge Cases

- **Command cannot start:** report the run as blocked with the first failing
  step.
- **Wrapper reports actionable findings:** do not hide them behind a summary;
  surface the worst findings first.
- **User wants Codex global skills audited:** this skill does not cover that
  library.
