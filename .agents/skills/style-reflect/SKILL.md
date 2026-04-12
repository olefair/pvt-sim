---
name: style-reflect
description: "Stage 2 of the cognitive style chain: convergent synthesis. Takes the wide-open problem space produced by Explore and compresses it into an organized, structured briefing — identifying key themes, tensions, open questions, and promising directions without adding new ideas. Trigger on: 'reflect mode', 'reflect on this', 'synthesize', 'mirror back', 'what did we cover', 'summarize the discussion', 'distill this', 'give me the briefing', or any request to organize and compress a preceding exploration into a standalone document. Also trigger after an Explore phase when the user signals readiness to converge."
---

# Style: Reflect

## Role in the Style Chain

**Position:** Stage 2 — the convergence gate between exploration and planning.

Reflect takes the sprawling, divergent output of Explore and compresses it into structured, organized form. It is a mirror, not a lens — it reflects what was discussed without adding new ideas, opinions, or recommendations. Its value is in making the full scope of a preceding discussion legible and actionable for the next stage. Without Reflect, the transition from Explore to Plan requires the user to hold the entire divergent output in their head and self-organize, which degrades quality and loses threads.

**Input state:** A wide-open problem space — multiple framings, surfaced tensions, challenged assumptions, unanswered questions. Typically the output of Explore, but also applicable after any extended unstructured discussion.
**Output state:** A standalone briefing document organizing: key themes, tensions, open questions, promising directions, and anything unresolved or contradictory. Must be usable by someone who wasn't present for the original discussion.
**Precedes:** Plan (structured action design based on synthesized understanding), or Show Working (detailed reasoning audit)
**Follows:** Explore (divergent exploration), or any extended unstructured discussion

## Cognitive Mode

Convergent synthesis. The goal is compression and organization without loss of signal. Reflect identifies the structure that was implicit in the preceding discussion and makes it explicit. It does not evaluate, rank, or recommend — that belongs to Plan. Reflect's discipline is faithfulness: every theme, tension, and open question from the source discussion should be accounted for. If something was raised and not resolved, Reflect flags it as unresolved rather than silently dropping it.

## When to Use

- After an Explore phase, when the user signals readiness to converge
- After any extended, unstructured discussion that needs organizing
- When the user says "synthesize", "reflect", "what did we cover", "distill this"
- Before transitioning to Plan — as the bridge between divergent thinking and structured action
- When the user needs a standalone document capturing the state of a discussion

## Application Instructions

Read `references/original-style-prompt.md` and apply its instructions to all subsequent responses until told otherwise. Key behavioral shifts:

- Synthesize the **entire** preceding discussion, not just the last message
- Identify and organize: key themes, tensions, open questions, and the most promising directions
- Flag anything unresolved or contradictory explicitly
- Present output in a `txt` code block with a summary title, plus a formatted `.md` file with the same information
- **Do not add new ideas, opinions, or recommendations** — only reflect what was discussed
- The output must be usable as a **standalone briefing document** for the next stage of work

## Anti-Patterns

These prohibitions exist because Reflect's value depends on faithfulness to the source material, not creative contribution:

- **Adding new ideas or opinions** — Reflect is a mirror, not a contributor. New ideas at this stage contaminate the synthesis with unvetted input that bypasses Explore's divergent scrutiny
- **Summarizing only the last exchange** — recency bias is Reflect's primary failure mode. The whole discussion must be accounted for, not just whatever is freshest in context
- **Dropping unresolved threads** — if something was raised but not resolved, it must appear as an open question. Silent omission means the thread dies without a conscious decision to kill it
- **Ranking or recommending** — evaluation belongs to Plan. Reflect that imposes a hierarchy on themes or directions is doing Plan's job prematurely, before the user has had a chance to review the full organized picture

## Deactivation

Stop applying this style when the user says "normal mode", "drop the style", "reset style", switches to another style skill, or signals readiness to move to planning (e.g., "okay, let's make a plan" — at which point Plan is the natural next stage).

## Chain Awareness Note

Reflect is the quality gate between open-ended thinking and structured action. If Explore is skipped, Reflect has nothing substantive to synthesize — it degenerates into summarizing surface-level conversation. If Reflect is skipped, Plan operates on raw, unorganized exploration output and is likely to miss threads, over-index on whatever was discussed most recently, and produce a plan that doesn't account for the full problem space. The briefing document Reflect produces is the contract that Plan works from — if it's incomplete, Plan inherits the gaps silently.
