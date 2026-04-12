---
name: self-improving-agent
description: "Injects a self-improving-agent reminder during agent bootstrap"
metadata: {"openclaw":{"emoji":"🧠","events":["agent:bootstrap"]}}
---

# Self-Improving Agent Hook

Injects a reminder to evaluate learnings during agent bootstrap.

## What It Does

- Fires on `agent:bootstrap` (before workspace files are injected)
- Adds a reminder block to check `.learnings/` for relevant entries
- Prompts the agent to log corrections, errors, and discoveries
- Stays quiet unless the active workspace already has `.learnings/` or
  `SELF_IMPROVING_AGENT_FORCE=1` is set intentionally

## Configuration

Enable with:

```bash
openclaw hooks enable self-improving-agent
```
