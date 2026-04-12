---
name: advise
description: >
  Decision assistance for project work. Reads project context (CLAUDE.md, TASKS.md,
  memory/, git state) and provides structured advice on next steps, tradeoffs, or
  priorities. Trigger on: /advise, "what should I do next", "help me decide",
  "advise me", "what's the best move here", "what would you recommend", "I'm stuck",
  "priorities?", "what should I work on", or any request for guidance on next steps
  or tradeoffs in current project work. Also trigger when the user seems blocked or
  indecisive about sequencing multiple tasks. Do NOT trigger for general knowledge
  questions or technical how-to requests.
---

# Advise

Decision assistance skill. Reads project context and delivers structured advice.

## Modes

- **`/advise quick`** — Brief recommendation from context files only.
- **`/advise full`** or **`/advise`** — Structured deliberation including git state.
- **Natural language** — Any phrasing that asks for guidance on next steps runs full mode.

## Step 1: Gather Context

Use available read tools (`file-reader`, `repo-engineer`, `nexus-docs`) to read:

**Always read (both modes):**
- `CLAUDE.md` in the relevant workspace root (project instructions, active work)
- `TASKS.md` if it exists (current task list and commitments)
- `memory/` directory contents if they exist (project state, preferences)

**Full mode only** (skip for quick):
- `git status` — uncommitted changes
- `git log --oneline -10` — recent commit history
- `git diff --stat` — what's been modified

For git commands, use `terminal` or `repo-engineer` tools if available. If unavailable, note the gap and work with what you have.

**Which workspace?** If the user specifies a project, use that. Otherwise, infer from recent conversation context. If ambiguous, ask.

## Step 2: Identify the Decision Point

From the gathered context, determine what the user most likely needs advice on. Look for:

- Items marked "pending", "next", or "TODO" in TASKS.md or CLAUDE.md
- Active work sections describing unfinished tasks
- Unresolved questions or noted uncertainties
- Uncommitted changes suggesting work-in-progress (full mode only)
- Competing priorities or deadline pressure

**If the decision point isn't obvious, state what you see and ask.** Do not guess.

## Step 3: Advise

### Quick mode

```
**Situation:** [1 sentence — what you're working on and where you are]
**Recommendation:** [1-2 sentences — what to do next and why]
```

No preamble, no hedging. Under 4 sentences total.

### Full mode

```
## Situation
[2-3 sentences: current project state, active work, what's at stake]

## Options
1. **[Option A]** — [what this means concretely]
2. **[Option B]** — [what this means concretely]
3. **[Option C]** — [if applicable]

## Tradeoffs
| | Effort | Risk | Payoff |
|---|--------|------|--------|
| Option A | ... | ... | ... |
| Option B | ... | ... | ... |

## Recommendation
[Which option and why. Be direct. State the reasoning, not just the conclusion.]

## What I'm uncertain about
[Anything you couldn't determine from the context. "I don't know" is valid.]
```

Keep full mode under 300 words.

## Rules

- **Never fabricate context.** Only reference what you actually read.
- **If a file doesn't exist, say so** and work with what you have.
- **State uncertainty explicitly** — don't paper over gaps.
- **Don't expand scope.** Advise on what's in front of the user, not hypothetical future work.
- **Use KNOW / THINK / UNKNOWN** for any claims about project state.