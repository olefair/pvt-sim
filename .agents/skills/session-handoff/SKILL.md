---
name: session-handoff
description: "Trigger on /handoff, handoff, session summary, continuation doc, checkpoint, wrap up, capture what we did, summarize this session, REFLECT document, status capture, \"write this up for next time,\" or any request to preserve conversation context for a future session. AUTO-TRIGGER on conversation compaction — when a compaction marker appears, produce a checkpoint handoff BEFORE continuing. MUST read this skill before writing any handoff. Never produce a session summary from memory alone — follow the retrieval protocol. Common failure: confident summaries that omit major work or fabricate lost context."
---

# Session Handoff — Context Transfer Protocol

## Purpose

Produce a document that allows a future conversation (with no memory of this one) to resume work with full, accurate context. The reader has zero shared history. Every claim must be either verified from available evidence or explicitly marked as uncertain.

## Why This Skill Exists

Handoffs requested near the end of long conversations are the highest-risk output Claude produces. By that point, early and middle conversation content may have been compacted or lost from the context window. The model's default behavior is to confabulate plausible-sounding context for parts it can no longer see, producing summaries that are confidently wrong. This skill exists to prevent that failure mode through mandatory retrieval, structured coverage, and explicit honesty about visibility gaps.

## Workspace Vault Contract

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or writing notes there.

When the current workspace uses the Pete docs vault, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
handoff-specific field rules below are deltas, not substitutes.

## Pre-Writing Protocol (MANDATORY)

Do NOT begin drafting until all of these steps are complete. This is not optional.

### Step 1: Assess Context Visibility

Before anything else, determine how much of the conversation you can actually see.

- Count the approximate number of exchanges visible in your current context
- Check for compaction markers (e.g., `[NOTE: This conversation was successfully compacted...]`)
- If compaction occurred, note what the compaction summary covers and what it likely omits
- **Write a private assessment** (not shown to user yet): "I can see approximately X exchanges. The conversation appears to have covered [topics visible]. I may be missing [topics likely discussed earlier]."

### Step 2: Retrieve What You Cannot See

Use tools to recover context that may have fallen out of your window:

1. **`conversation_search`** — Search for key topics, decisions, deliverables, and file names mentioned in the conversation. Run at least 3 targeted searches using substantive keywords from the visible portion of the conversation. If the conversation involved multiple distinct topics, search for each one.

2. **`recent_chats`** — If the current conversation is the most recent, use this to confirm the conversation's scope and timeline.

3. **Transcript file** — If a compaction occurred and a transcript path is provided, READ IT. Use `view` or `bash` to read the transcript file. This is the single most valuable recovery step. Read it incrementally if it's large.

4. **Uploaded files / project files** — Check `/mnt/user-data/uploads/` and `/mnt/project/` for any files the user uploaded or referenced. These are evidence of what was discussed.

### Step 3: Build a Scope Inventory

Before writing prose, produce a structured list:

- **Topics discussed** (with confidence: VERIFIED from context/tools, INFERRED from partial evidence, UNKNOWN)
- **Decisions made** (what was decided, and what evidence you have for it)
- **Deliverables produced** (files created, code written, documents generated — with paths if known)
- **Open threads** (things discussed but not resolved)
- **Corrections made** (any time the user corrected the assistant — these are critical and often lost)

If any major section is marked UNKNOWN, say so in the handoff. Do not fill it in with plausible guesses.

### Step 4: Cross-Check Against User's Request

Re-read the user's handoff request. Does your scope inventory match what they asked for? If they said "summarize everything we did," but your inventory only covers the last topic discussed — that's a red flag. Go back to Step 2 and search harder.

## Handoff Document Structure

The handoff must include ALL of these sections. If a section has no content, include it with "None identified" rather than omitting it.

```markdown
---
origin: [claude|gpt|openclaw]
scope: [project|workspace|general]
status: [open|carried-forward|resolved]
created: YYYY-MM-DD
updated: YYYY-MM-DD
closed:
project:
projects: []
repos: []
areas:
  - [broad-stable-area-slug]
subjects:
  - [narrower-standardized-subject-slug]
links: []
related: []
files: []
open_threads: []
carried_forward: []
resolved_threads: []
supersedes: []
superseded_by: []
external_links: []
---

# Session Handoff: [Descriptive Title]

**Date:** [today's date]
**Source conversation:** [conversation title or description]
**Context coverage:** [honest assessment — e.g., "Full visibility" or "Partial — 
  early conversation lost to compaction, recovered via transcript/search" or 
  "Limited — only final ~20 exchanges visible, retrieval partially successful"]

## Scope
What this conversation set out to accomplish. One paragraph.

## What Was Accomplished
Concrete deliverables, decisions, and completed work. Each item should be 
specific enough that the next session can verify it exists.
- [Deliverable/decision 1 — with file path if applicable]
- [Deliverable/decision 2]
- ...

## Key Decisions and Rationale
Decisions made during the session and WHY they were made. The "why" is 
often the first thing lost. Include the user's stated reasoning, not just 
the outcome.

## Corrections and Course Changes
Any time the user corrected an error, changed direction, or clarified a 
misunderstanding. These are the most important context for future sessions 
because they represent hard-won constraints that should not be violated again.

## Open Threads
Work started but not finished. Questions raised but not answered. Topics 
that need follow-up. For each, include enough context that the next session 
can pick it up without re-deriving the problem.

## Files Produced or Modified
List every file created, modified, or referenced, with paths. The next 
session needs to know what exists and where.

## Recommended Next Steps
What should the next session start with? Be specific and actionable.

## Context Gaps (if any)
Anything you could not verify or recover. Be explicit: "The early portion 
of this conversation was not recoverable. The following topics may have been 
discussed but could not be confirmed: [list]."
```

Use the canonical handoff template at `docs/templates/template_handoff-canonical_v3_2026-03-14.md`.

Field semantics are binding:
- `origin` controls the folder lane and must be lowercase `claude`, `gpt`, or `openclaw`
- use `openclaw` when the runtime/session surface is OpenClaw (including OpenClaw webchat, control UI, or native OpenClaw sessions), regardless of which model is running underneath
- use `gpt` only for actual ChatGPT/OpenAI-native surfaces
- `scope`, `project`, `projects`, and `repos` define routing context; do not bury that information in prose alone
- `links` are must-read vault notes/files for the next session
- `related` is broader context, not mandatory preload
- `files` is the canonical inventory of key produced or referenced files; use wikilinks for vault-native files and plain repo paths only when a vault link is impossible
- `open_threads` is the canonical unresolved thread list; `carried_forward` and `resolved_threads` are thread-lifecycle metadata, not substitutes for `status`
- `supersedes` and `superseded_by` must be maintained when one handoff replaces another
- If a required array has no entries, use an empty array rather than omitting the field

Write-order rule for superseding handoffs:
- update the older handoff first when adding `superseded_by`, `carried_forward`, or status changes
- write or finalize the new handoff last so filesystem "Date modified" ordering still points at the newest handoff in Explorer/Finder views
- if a later correction forces touching both files again, finish by re-saving the new handoff last

## Quality Gates (Self-Check Before Delivering)

Run these checks before presenting the handoff to the user:

1. **Scope coverage:** Does the handoff account for the FULL conversation, not just the most recent topic? If compaction occurred, did you read the transcript?
2. **Factual verification:** Is every claim either (a) visible in your context, (b) recovered via tools, or (c) explicitly marked as uncertain?
3. **No confabulation:** Are you presenting anything as fact that you're actually inferring or guessing? If so, rewrite it with appropriate qualification.
4. **Corrections included:** Did the user correct you at any point? Is that correction reflected in the handoff?
5. **Actionability:** Could a fresh instance of Claude, reading only this document, resume the work effectively? What would it need to ask about?
6. **File inventory:** Are all produced files listed with their actual paths?

If any gate fails, fix the issue before delivering. If you cannot fix it (e.g., context is irrecoverable), state the gap explicitly in the "Context Gaps" section.

## Todoist Sync (MANDATORY)

After writing the handoff document, add all unfinished or unresolved items from the Open Threads section to Todoist as tasks in their logical corresponding project. This is not optional.

For each open thread:
1. Create a task with a clear, actionable title
2. Add a description with enough context to act on it without re-reading the full handoff
3. Include a [[backlink]] to the handoff document in the description
4. Place it in the correct Todoist project (Claude Config, Pete, PVT Simulator, MCP Servers & Plugins, Obsidian & Linear, UAF, etc.)
5. Set priority based on blocking status (p1 if it blocks other work, p2 for important, p3 for nice-to-have)

**Why:** Handoffs capture nuance and detail. Todoist captures the actionable queue. Without this step, open threads get buried in handoff documents that may never be re-read. With it, every unfinished item surfaces in the task system where it gets tracked to completion.

## Common Failure Modes

These are the specific ways handoffs go wrong. Check for each one:

| Failure | How It Manifests | Prevention |
|---------|-----------------|------------|
| **Recency bias** | Only the last topic discussed appears in the handoff | Step 2: search for earlier topics; Step 3: build full scope inventory |
| **Confident confabulation** | Plausible but fabricated details about early conversation content | Step 1: assess visibility honestly; never fill gaps with guesses |
| **Missing corrections** | User corrections are omitted, so future sessions repeat the same mistakes | Explicitly scan for correction patterns ("no, I said...", "that's wrong", "I specifically...") |
| **Vague deliverables** | "We discussed the architecture" instead of "Produced System-Instructions-Claude-Desktop.md at /path/to/file" | Always include file paths, specific names, concrete outputs |
| **Scope collapse** | A 2-hour session producing 5 deliverables gets summarized as if it only produced 1 | Cross-check file system for produced files; search for all topics |
| **Missing rationale** | Decisions recorded without the reasoning that led to them | For each decision, ask "why was this chosen over alternatives?" |

## When to Offer Proactive Handoffs

Don't wait to be asked. If a conversation involves substantial design or implementation work, offer a checkpoint summary after each major deliverable or decision. A mid-conversation checkpoint is worth more than an end-of-conversation handoff, because context is still fresh.

Suggested trigger points:
- After completing a significant deliverable (file, design, analysis)
- After a major decision that constrains future work
- After a correction that changes direction
- When the conversation has been going long enough that compaction is likely soon
- When switching between major topics within the same conversation

## Compaction Auto-Trigger Protocol

**This is the most important trigger in this skill.** When a conversation is compacted, context is actively being destroyed. The compaction summary is a lossy compression — it captures the gist but drops detail, nuance, corrections, rationale, and file paths. A structured handoff produced immediately after compaction preserves far more than the compaction summary alone.

### How to Detect Compaction

Look for this pattern in the conversation history:
```
[NOTE: This conversation was successfully compacted to free up space in the context window...]
[Transcript: /mnt/transcripts/...]
```

### What to Do When Compaction Is Detected

1. **Read this skill immediately** — before processing the user's next message.
2. **Read the transcript file** referenced in the compaction marker. This is your primary recovery source. Read it incrementally (it may be large).
3. **Produce a checkpoint handoff** following the full protocol in this skill.
4. **Present it to the user** before continuing with whatever they asked. Frame it as: "The conversation was just compacted. I've produced a checkpoint to preserve context. Here's what I've captured — let me know if anything is missing, then we can continue."
5. **Then** address the user's actual message.

### Why This Matters for Future Search

A well-structured handoff document in the conversation history is dramatically more searchable than scattered exchanges. When `conversation_search` hits a handoff, it finds concentrated keywords, specific file paths, named decisions, and explicit topic labels — all in one place. This single artifact makes every future reference to this conversation more reliable. Without it, searching for "what did we decide about X" returns fragments that may be misleading out of context.

### Timing Considerations

The handoff should be thorough but not bloated. At compaction time, the user is already bumping against context limits. Produce the handoff, present the file, and keep your surrounding chat message brief. The detail lives in the document, not in your response text.

## Output Format and Location

### Directory

All handoff files MUST be saved to:

```
C:\Users\olefa\dev\pete-workspace\docs\handoffs\<origin>\
```

Use the lowercase canonical origin lanes from the vault schema:
- `docs\handoffs\claude\`
- `docs\handoffs\gpt\`
- `docs\handoffs\openclaw\`

For sessions happening inside OpenClaw itself, write to `docs\handoffs\openclaw\`, not `gpt`, even if the underlying model is GPT-family.

Do not write new handoffs into the legacy root handoff directory or the older uppercase `GPT\` lane.

### Naming Convention

All handoff files MUST follow this naming pattern:

```
handoff_topic-slug_YYYY-MM-DD.md
```

Rules:
- **Prefix:** Always `handoff_` (not `session-handoff_`, not any other prefix)
- **Topic slug:** Lowercase, hyphen-separated, descriptive of the session's primary focus (e.g., `voice-stack`, `pete665-instructions-merge`, `post-midterms-inventory`). Keep it short but specific — 2-4 words is ideal.
- **Date:** ISO date of the session (`YYYY-MM-DD`)
- **Extension:** Always `.md`

Examples:
- `handoff_voice-stack_2026-03-10.md`
- `handoff_obsidian-vault-reorg_2026-03-09.md`
- `handoff_pete665-instructions-merge_2026-02-27.md`

### Delivery

Every handoff — regardless of length — MUST be written to the vault using
`repo-engineer:repo_create_file` (preferred) or `file-writer:create_file`. Disk write
is not optional. Do not deliver a handoff inline-only, even for short sessions.

Write the file directly to the canonical vault path, then also present via `present_files`
for convenient access.

Prefer writing directly to the vault over download-only delivery. Use the canonical
origin lane from the vault schema (e.g., `docs/handoffs/claude/handoff_topic-slug_YYYY-MM-DD.md`).

When a new handoff supersedes an older one, apply lineage edits to the older note first and
finish with the new handoff write so the latest handoff remains the most recently modified file.
