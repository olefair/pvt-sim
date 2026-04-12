# Advise Decision Framework

## Modes

- **Quick mode**: use only context files and return one direct recommendation.
- **Full mode**: include git state when available and compare concrete options with effort, risk, and payoff.

## Context Sources

Read these first when they exist:

- `CLAUDE.md` for project instructions and active work
- `TASKS.md` for commitments and pending tasks
- `memory/` for prior state, preferences, and known constraints
- git status, recent history, and diff summary for active-work signals in full mode

## Decision Heuristics

Prioritize advice around unfinished work, blockers, active edits already in flight, and competing priorities with real tradeoffs.

## Output Rules

- never fabricate project state
- state uncertainty explicitly
- advise on the current decision rather than expanding scope
- prefer a direct recommendation over a long exploration
