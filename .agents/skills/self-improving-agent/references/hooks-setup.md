# Hook Setup Guide

Optional reminder-hook setup for environments that support command hooks.

These scripts are not used automatically by Codex Desktop just because the
skill is installed. They matter only when a CLI agent explicitly references
them from its hook configuration.

## Pick The Correct Skill Root

Adjust paths to match where the skill actually lives:

- Repo-local source tree in this workspace:
  - `./tools/SKILLS/folders/self-improving-agent`
- Codex global install:
  - `~/.codex/skills/self-improving-agent`
- Claude Code global install:
  - `~/.claude/skills/self-improving-agent`

In the examples below, replace `<skill-root>` with the correct path.

## Runtime Guard

The reminder scripts stay silent unless one of these is true:

- the current working directory contains `.learnings/`
- `SELF_IMPROVING_AGENT_FORCE=1` is set intentionally

That guard keeps global hook setups from spamming repos that have not adopted
the `.learnings/` workflow.

The optional OpenClaw bootstrap hook should be treated the same way: keep it
quiet unless the active workspace already uses `.learnings/`, or you forced it
on deliberately for testing.

## Claude Code

Project-level example using a repo-local skill path:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "./tools/SKILLS/folders/self-improving-agent/scripts/activator.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "./tools/SKILLS/folders/self-improving-agent/scripts/error-detector.sh"
          }
        ]
      }
    ]
  }
}
```

Global example if the skill is installed under `~/.claude/skills/`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/skills/self-improving-agent/scripts/activator.sh"
          }
        ]
      }
    ]
  }
}
```

## Codex CLI

Example:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "<skill-root>/scripts/activator.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "<skill-root>/scripts/error-detector.sh"
          }
        ]
      }
    ]
  }
}
```

Use the repo-local path if you are running from this workspace, or the
`~/.codex/skills/self-improving-agent` path if you installed it globally.

## GitHub Copilot

Copilot does not support shell hooks directly. Use a manual prompt reminder in
`.github/copilot-instructions.md` instead.

Suggested block:

```markdown
## Self-Improving Agent

After resolving a non-obvious issue, recurring failure, or repo-specific
workflow gotcha, consider logging it to `.learnings/`.
```

## Verification

### Activator

1. Ensure `.learnings/` exists in the repo, or set `SELF_IMPROVING_AGENT_FORCE=1`.
2. Start a fresh CLI session.
3. Submit any prompt.
4. Confirm the context includes `<self-improving-agent-reminder>`.

### Error Detector

1. Ensure `.learnings/` exists in the repo, or set `SELF_IMPROVING_AGENT_FORCE=1`.
2. Trigger a failing command.
3. Confirm the context includes `<self-improving-agent-error-detected>`.

### Extraction Helper

```bash
<skill-root>/scripts/extract-skill.sh example-skill --dry-run
```

The dry run should report a workspace-compliant scaffold with:

- `SKILL.md`
- `references/output-template.md`
- `agents/openai.yaml`

## Troubleshooting

- If nothing fires, confirm the hook path is correct for the environment.
- If the scripts report `Permission denied`, mark them executable where needed.
- If reminders fire in unwanted repos, remove the global hook or rely on the
  `.learnings/` guard instead of forcing activation.
- If you want reminders in a repo before creating `.learnings/`, set
  `SELF_IMPROVING_AGENT_FORCE=1` explicitly for that environment.
