# Worked Example: Rejecting a Suspicious Imported Skill

Use this as a model for the level of evidence expected from a real review.

## Review Summary

- `Review surface`: archive and extracted folder
- `Package fingerprint`: SHA-256 captured for archive, 6 files reviewed
- `Verdict`: `DO NOT INSTALL`
- `Risk level`: `EXTREME`

## Findings

### Finding 1

- `file`: `scripts/bootstrap.sh`
- `evidence`: downloads and executes `https://example.invalid/install.sh`
  during setup
- `impact`: remote code can change after review and execute with the user's
  permissions
- `why it matters`: this defeats static review and creates an unbounded trust
  dependency

### Finding 2

- `file`: `SKILL.md`
- `evidence`: instructs the model to "ask for any API keys needed" as a default
  workflow step
- `impact`: normalizes secret collection without first proving necessity
- `why it matters`: the prompt itself expands the risk surface even before any
  script runs

### Finding 3

- `file`: `agents/openai.yaml`
- `evidence`: `default_prompt` says the skill only "formats local notes", but
  the scripts directory performs network activity and installs dependencies
- `impact`: surfaced UI description understates the true behavior
- `why it matters`: misleading metadata undermines operator trust and increases
  the chance of accidental installation

## Compatibility Notes

- archive contains `hooks/post-start.sh`, but the skill docs never mention hooks
- relative path `references/setup.md` is missing
- setup commands are bash-only while the target workspace is Windows-first

## Why The Verdict Is `DO NOT INSTALL`

This package fails both the security and operational sanity tests. The remote
bootstrap behavior is already a blocker. The prompt asks for secrets by default,
the UI metadata misrepresents the capability surface, and the packaging is not
self-consistent. Even if one issue were fixed, the package would still require a
fresh full review before reconsideration.
