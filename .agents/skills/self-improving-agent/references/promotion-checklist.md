# Promotion Checklist

Promote a learning out of `.learnings/` only when all of the following are true:

- the pattern is verified, not speculative
- the rule is concise enough to fit cleanly in a steering file
- the lesson matters beyond the single incident that produced it
- the destination file is the correct home for the rule
- any sensitive details have already been removed or redacted

## Destination Guide

- `AGENTS.md` for durable workflow and tool-use rules
- `.github/copilot-instructions.md` for repo guidance when that file exists
- `CLAUDE.md` only when the repo actually uses it
- OpenClaw `SOUL.md` or `TOOLS.md` only in a real OpenClaw workspace

## Do Not Promote

- one-off debugging notes
- unstable workarounds
- repo-specific details that would confuse global steering files
- anything that still needs a human decision before it becomes policy
