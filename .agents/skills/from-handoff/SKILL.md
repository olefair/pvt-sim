---
name: from-handoff
description: "Resume work from where a previous session left off. Reads the single most recent session handoff and presents a prioritized recap. Trigger on: /from-handoff, 'where did we leave off', 'continue from last session', 'pick up where we left off', 'what were we working on', 'resume', 'check the last handoff', or any reference to continuing prior work. Also trigger when the user's first message implies they want to continue something but doesn't specify what. Accepts an optional file upload to target a specific handoff instead of the most recent one."
---

# From Handoff — Session Resumption Protocol

## Purpose

Close the context restoration loop opened by the `session-handoff` skill. Read the single most recent handoff, extract what matters, and present a prioritized starting point.

## Critical: Token Economy

This skill runs at session start when the context window is nearly empty. Every byte it reads stays in context for the entire conversation and gets reprocessed on every subsequent message. **Minimize tool calls and data ingestion ruthlessly.**

The skill's job is orientation, not exhaustive verification. Read one file. Present the summary. Let the user choose what to work on. Verify claims only when the user picks a thread and is about to act on it.

## Execution Protocol

### Step 1: Locate and Read the Handoff (ONE tool call)

The handoff directory for this platform is:
```
C:\Users\olefa\dev\pete-workspace\docs\handoffs\claude\
```

This is Claude. Always use the `claude` lane. Do NOT search `gpt`, `openclaw`, or any other lane unless the user explicitly asks.

**Default (no argument, no upload):**

List the directory with `file-reader:list_directory_with_sizes` sorted by `modified`. Take the first entry (most recent). Read that single file with `file-reader:read_file`.

That is two tool calls total. Not three. Not five. Not fifteen.

**With file upload:** If the user uploads a handoff file alongside the `/from-handoff` command, read the uploaded file instead. Do not search the directory at all.

**With slug argument (e.g., `/from-handoff dictate`):** List the directory as above, find the filename containing the slug, read that one file. If multiple match, present filenames as options and ask — do NOT read all of them.

### Step 2: Parse the Handoff

Parse YAML frontmatter as authoritative metadata. Extract from body:
- **Open threads** — what's unfinished
- **Recommended next steps** — previous session's suggested priorities
- **Key decisions** — for context, not recitation

Do NOT recite the full handoff back. The user wrote it or can read it. Summarize the actionable state only.

### Step 3: Present the Recap

```
## Last Session: [Title]
[Date] — [1-2 sentence scope]

## Open Threads
**[n]. [Thread title]** [priority indicator]
[1-2 sentences: what's unfinished, what's needed next]

## Suggested Starting Point
[Which thread first and why — one sentence.]

---
Which thread would you like to pick up? Or is there something new?
```

**Formatting rules:**
- Priority indicators: 🔴 P1, 🟡 P2, 🔵 P3, ⚪ P4
- End with an explicit question. The user chooses.

### Step 4: Verify On Demand

Do NOT preemptively verify file paths, Todoist tasks, or tool status at session start. That verification happens when the user picks a thread and you're about to act on it. At that point, verify only what's relevant to that specific thread.

## What This Skill Does NOT Do

- **Does not read multiple handoffs.** One handoff. The most recent one.
- **Does not cross-check Todoist.** If the user wants task status, they'll ask.
- **Does not scan recent_chats.** If intervening work happened, the user knows.
- **Does not search across origin lanes.** This is Claude; read from `claude/`.
- **Does not write files.** Read-only, presentation-only.
- **Does not auto-pick a thread.** It suggests, then asks.

## Edge Cases

**No handoffs exist:** Say so. Offer `conversation_search` as fallback.

**Handoff is very old (>7 days):** Note the age. Flag that priorities may have shifted. Still don't do expensive verification — let the user guide what to check.

## Output Location

None — conversational output only.