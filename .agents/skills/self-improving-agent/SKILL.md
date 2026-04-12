---
name: self-improving-agent
description: >
  Capture non-obvious failures, corrections, knowledge gaps, and recurring
  workflow improvements into repo-local `.learnings/` logs so future sessions
  do not repeat them. Use when a command fails in a non-trivial way, the user
  corrects the agent, a missing capability is discovered, a better recurring
  approach is found, or before major work when reviewing prior learnings. Do
  not use for trivial typos, routine expected errors, or one-off noise.
---

# Self-Improving Agent

Repo-local learning capture and promotion workflow, adapted for the Pete
workspace. This skill keeps durable notes in `.learnings/` and promotes only
proven, recurring patterns into repo steering files when they are stable enough
to deserve permanent guidance.

Imported from an upstream ClawdHub/OpenClaw skill and normalized here for
workspace standards, Codex use, and safer operational behavior.

## Output Location

This skill writes plain Markdown logs under the current repo root:

- `.learnings/LEARNINGS.md` - corrections, knowledge gaps, and best practices
- `.learnings/ERRORS.md` - unexpected command, tool, runtime, or integration failures
- `.learnings/FEATURE_REQUESTS.md` - user-requested capabilities or missing automation

Rules:

- Keep these filenames fixed. Do not create dated variants or extra ad hoc log files.
- These are repo-local logs, not vault notes. Do not add YAML frontmatter.
- Keep `.learnings/` at the active repo or workspace root only. Do not create it in the installed skill folder, user home directory, or another unrelated global path.
- If `.learnings/` is missing and the repo wants this workflow, create it and seed the files from:
  - `assets/LEARNINGS.md`
  - `assets/ERRORS.md`
  - `assets/FEATURE_REQUESTS.md`
- If the repo intentionally does not use `.learnings/`, keep the note in chat unless the user asks to adopt the logging system.
- Do not route this skill into the workspace report, audit, or blueprint note families. Those belong to the dedicated report, audit, and blueprint skills.

## Sensitive Data Hygiene

Before writing any entry, remove or redact:

- secrets, tokens, API keys, cookies, session identifiers, or credentials
- personal data that is not needed to explain the issue
- long raw stack traces when a shorter excerpt is enough
- proprietary prompt text or private conversation excerpts that are not required
  for future prevention

Prefer concise evidence over verbatim dumps. Use placeholders like
`<redacted-token>` when the shape matters but the value must not be stored.

## When To Log

Log only when the information is likely to prevent future mistakes.

- A command or operation failed in a non-obvious way
- The user corrected an incorrect assumption or outdated claim
- A repo-specific convention or workflow had to be discovered instead of already being known
- A recurring pattern or better approach emerged from real investigation
- The user requested a capability the current setup does not support

Do not log:

- trivial typos
- obvious expected failures
- generic knowledge with no repo or workflow value
- unresolved speculation without a concrete action or rule

## Workflow

### Step 0: Review Existing Learnings Before Major Work

If the user asks for a pre-flight review, or you are about to start major work
in a repo that already uses `.learnings/`, scan the existing logs first and
surface only the entries that are materially relevant to the task at hand.

Do not create a new entry just because you performed this review.

### Step 1: Decide Whether The Event Is Worth Logging

Ask:

- Is this non-obvious?
- Is it likely to recur?
- Would another session benefit from seeing it?
- Can I describe the prevention rule clearly?

If the answer is no, do not create noise in `.learnings/`.

### Step 2: Search Existing Entries Before Writing

Before creating a new entry, search `.learnings/` for related errors, patterns,
or feature gaps.

Use `rg` when available, for example:

```bash
rg -n "pnpm|timeout|Pattern-Key:" .learnings
```

If a related entry already exists:

- update that entry instead of duplicating it
- add `See Also` links when separate entries still make sense
- bump priority or recurrence metadata when the issue is clearly recurring

### Step 3: Route To The Correct Log

- `LEARNINGS.md` for corrections, knowledge gaps, and best practices
- `ERRORS.md` for failures and breakages that required diagnosis
- `FEATURE_REQUESTS.md` for missing capability or automation requests

### Step 4: Write A Canonical Entry

Use the examples in `references/examples.md` and the seed headers in `assets/`
when creating or normalizing entries. Apply `references/data-hygiene.md`
before saving anything.

Minimum required fields by log:

- Learning entry:
  - ID
  - `Logged`
  - `Priority`
  - `Status`
  - `Area`
  - `Summary`
  - `Details`
  - `Suggested Action`
  - `Metadata`
- Error entry:
  - ID
  - `Logged`
  - `Priority`
  - `Status`
  - `Area`
  - `Summary`
  - `Error`
  - `Context`
  - `Suggested Fix`
  - `Metadata`
- Feature request entry:
  - ID
  - `Logged`
  - `Priority`
  - `Status`
  - `Area`
  - `Requested Capability`
  - `User Context`
  - `Complexity Estimate`
  - `Suggested Implementation`
  - `Metadata`

Use these ID prefixes:

- `LRN-YYYYMMDD-XXX`
- `ERR-YYYYMMDD-XXX`
- `FEAT-YYYYMMDD-XXX`

### Step 5: Resolve Or Evolve Existing Entries

When an issue is fixed or absorbed into repo guidance:

- update `Status`
- add a `Resolution` block when relevant
- preserve links to the originating context
- record where it was promoted if it became permanent steering

Do not silently leave stale `pending` entries behind once the repo state has changed.

## Promotion Rules

Promotion is deliberate, not automatic.

Promote only when the learning is:

- verified in practice
- concise enough to become a prevention rule
- broad enough to matter outside the original incident
- likely to recur if left only in `.learnings/`

Preferred promotion targets in this workspace:

- `AGENTS.md` for durable workflow or tool-use rules
- `.github/copilot-instructions.md` when the repo uses Copilot context files
- `CLAUDE.md` only if the repo actually maintains that file
- OpenClaw-specific `SOUL.md` and `TOOLS.md` only when explicitly operating inside an OpenClaw workspace that already uses them

Do not "promote aggressively." Promote only after repeated evidence, clear user direction, or a truly durable repo rule.

Use `references/promotion-checklist.md` before promoting any entry out of
`.learnings/`.

## Skill Extraction Rules

When a learning deserves its own reusable skill:

1. Confirm the solution is real, tested, and broadly reusable.
2. Use `scripts/extract-skill.sh` as a scaffold generator only.
3. Finish the extracted skill against the Pete workspace standard before treating it as installable.
4. Repackage from `tools/SKILLS/folders/<skill-name>/` into `tools/SKILLS/packages/<skill-name>.skill`.

For extracted skills in this workspace, follow `SKILLS/SKILL_STANDARD.md` and
the `skill-creator-pete` workflow. Do not rely on upstream generic skill
layouts.

## Hooks And Automation

Hook scripts under `scripts/` are optional helpers for CLI agents that support
command hooks. They are not executed just because this skill is installed in
Codex Desktop.

- Read `references/hooks-setup.md` only when wiring CLI hook reminders.
- Read `references/openclaw-integration.md` only when explicitly operating in OpenClaw.
- The reminder scripts and the optional OpenClaw hook are designed to be inert
  unless `.learnings/` exists at the active repo or workspace root, unless you
  override that behavior intentionally with `SELF_IMPROVING_AGENT_FORCE=1`.

## Failure Modes

- Do not spam `.learnings/` with one-off trivia.
- Do not promote unresolved speculation into steering files.
- Do not store secrets, raw auth material, or oversized sensitive error dumps in
  `.learnings/`.
- Do not create `.learnings/` in the installed skill directory or another global
  location just to make hooks fire.
- Do not assume OpenClaw-only tools such as `sessions_list` or `sessions_send` exist in Codex.
- Do not scaffold new workspace skills with a bare `SKILL.md` only; the workspace standard requires `references/` and `agents/openai.yaml`.
- Do not treat this skill as a replacement for the dedicated artifact, audit, blueprint, or handoff skills.

## References

- `references/examples.md` - concrete entry examples and promotion examples
- `references/data-hygiene.md` - what to redact before writing repo-local learnings
- `references/hooks-setup.md` - optional hook setup for CLI agents
- `references/openclaw-integration.md` - OpenClaw-specific installation and routing notes
- `references/promotion-checklist.md` - when a learning is mature enough to promote
- `assets/LEARNINGS.md`, `assets/ERRORS.md`, `assets/FEATURE_REQUESTS.md` - seed templates for a new `.learnings/` directory
- `assets/SKILL-TEMPLATE.md` - workspace-compliant skill scaffold template for promoted learnings
