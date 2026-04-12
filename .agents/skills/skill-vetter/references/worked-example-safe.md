# Worked Example: Accepting a Well-Scoped Skill

Use this as a model for what a defensible `SAFE TO INSTALL` review looks like.

## Review Summary

- `Review surface`: folder and packaged archive
- `Package fingerprint`: SHA-256 captured for archive, 7 files reviewed
- `Verdict`: `SAFE TO INSTALL`
- `Risk level`: `LOW`

## Findings

### Finding 1

- `file`: `SKILL.md`
- `evidence`: scope is limited to read-only analysis of local markdown files and chat-only output unless the user explicitly asks for a saved note
- `impact`: permission surface stays narrow and easy to reason about
- `why it matters`: small, explicit scope reduces the chance of surprise writes or hidden side effects

### Finding 2

- `file`: `agents/openai.yaml`
- `evidence`: surfaced description matches the skill purpose and does not widen behavior beyond the written instructions
- `impact`: the operator sees an accurate capability summary in the UI
- `why it matters`: aligned metadata improves trust and reduces accidental invocation under false assumptions

### Finding 3

- `file`: `references/checklist.md`
- `evidence`: reference material supports the stated workflow and introduces no extra command, network, or secret-handling behavior
- `impact`: the supporting docs strengthen execution quality without expanding risk
- `why it matters`: references should clarify the workflow, not smuggle in broader powers

## Compatibility Notes

- all referenced files exist
- package root is flat and contains the expected files
- no hooks, scripts, binaries, encrypted blobs, or generated artifacts were present
- folder and archive contents match

## Why The Verdict Is `SAFE TO INSTALL`

This package is narrowly scoped, fully readable, and self-consistent. It does not request secrets, enable automation, fetch remote code, or write outside the declared workflow. Packaging is sane, metadata matches behavior, and there are no meaningful unknowns on the critical path.
