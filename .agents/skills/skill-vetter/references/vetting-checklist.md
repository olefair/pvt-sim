# Skill Vetting Checklist

Use this checklist to keep the review evidence complete and the verdict
defensible.

## Minimum Evidence

- identify the review surface: folder, `.skill`, `.zip`, or both
- list every file in scope before reaching a verdict
- record the top-level layout and total file count
- read `SKILL.md`, `agents/openai.yaml`, all reference docs, and every script,
  hook, asset, or hidden file that can affect behavior
- capture an archive SHA-256 when an archive is present and tooling permits
- compare folder source and packaged archive when both are available
- record any unreadable binary, generated blob, encrypted archive, minified
  payload, or missing file that limits review confidence
- for large archives or assets, still inventory every file and fully read every
  behavior-bearing text file rather than using size as a skip condition

## Permission Inventory

Capture the smallest honest scope for each category:

- filesystem reads
- filesystem writes
- network destinations
- commands or subprocesses
- hooks, startup behavior, or implicit/background invocation
- access to secrets, identity files, browser state, SSH material, or cloud
  credentials

If the skill asks for broad access, say why that scope is or is not justified by
the stated purpose.

## Finding Format

Every finding should be written with:

- `file`
- `evidence`
- `impact`
- `why it matters`

Do not write vague findings like "this seems risky" without tying them to a file
and an observable behavior.

## Packaging Sanity Checks

- archive root is flat and contains `SKILL.md`, `references/`, and
  `agents/openai.yaml`
- `SKILL.md` frontmatter uses only `name` and `description`
- `agents/openai.yaml` points at the correct skill name and matches the stated
  purpose
- reference docs exist for any non-obvious workflow
- folder source and packaged archive agree on the live contents
- extra files are explained; stale marketplace metadata or stray build output is
  treated as an operational risk

## Compatibility Pass

Use `references/compatibility-checks.md` to verify:

- environment assumptions are realistic
- referenced files and relative paths exist
- tool names are real for the target host
- output paths are explicit and sane
- prompt, metadata, and reference docs do not contradict each other

## Verdict Calibration

- `SAFE TO INSTALL`: no blockers, minimal permission scope, good packaging, low
  uncertainty
- `INSTALL WITH CAUTION`: no hard blocker, but broad scope, weak provenance, or
  meaningful unknowns remain
- `DO NOT INSTALL`: red flags, unexplained secret or system access, unreadable
  critical files, or source/package drift that prevents trust

## Unknowns

If you cannot verify a material fact, mark it as `unknown`. Do not replace
missing evidence with optimism. If the unknown sits on the critical behavior
path, treat it as a blocker candidate rather than a footnote.
