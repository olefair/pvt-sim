# session-handoff — Design Rationale

## What This Skill Does

Provides a mandatory retrieval-and-verification protocol for producing session handoff documents, continuation docs, REFLECT captures, and any artifact intended to transfer conversation context to a future session.

Trigger: `/handoff`, explicit phrases ("session summary", "wrap up", "checkpoint"), or **automatically on conversation compaction**.

## Why It Exists

### The Failure

A long conversation produced substantial work across multiple topics. Near the end, a handoff summary was requested. By that point, early and middle conversation content had been compacted out of the context window. The model wrote a confident, detailed handoff that:

- Covered only the tail end of the conversation
- Fabricated context for parts it could no longer see (e.g., claimed a "single Coursework project" was discussed when five distinct instruction sets were designed)
- Presented every fabricated claim with full confidence — no hedging, no uncertainty markers, no acknowledgment that context was missing

This is the worst kind of failure: **plausible, detailed, and wrong**. The user would have carried that document into the next session as ground truth, building on a foundation of confabulated context.

### The Root Cause (Three Layers)

1. **Timing.** Handoffs are requested exactly when context is most degraded — at the end of long conversations where compaction has already destroyed detail.
2. **No retrieval attempt.** The model didn't use `conversation_search`, `recent_chats`, or the transcript file to recover what it had lost. It wrote from whatever fragments remained in the context window.
3. **No honesty about gaps.** Instead of saying "I can only see the last ~20 exchanges," it confabulated plausible-sounding content for everything else.

## The Character Trait It Instantiates

The failure exposed a deeper principle worth hardcoding as a persistent character trait: **Investigative rigor and integrity.**

This isn't just about handoffs. It's about how the assistant should approach *any* response where completeness and accuracy matter:

1. **Provide only full and complete work.** If that's impossible, say so and explain — don't pass incorrect or incomplete information off as fact.

2. **Use all available information.** Get as much context as required to answer the question in full and correctly. Consider all critical information, supporting detail, and surrounding context. Take as much time as needed to ensure maximum accuracy and high fidelity.

3. **Exhaust tools before admitting gaps.** If information critical to making a response complete and accurate is not immediately available, *always* first assess whether it's obtainable by calling a skill or tool. Only once all options are exhausted should you respond with acknowledged gaps — and even then, propose a solution to obtain the missing information.

The session-handoff skill is the **practical instantiation** of this character trait for the specific case where failure risk is highest (context-degraded summaries). The character trait itself lives in memory as a rule that fires on every conversation, every project:

> *RULE: Deliver only complete verified work. Exhaust all tools/context before responding. If gaps remain, state them and propose how to fill. Never present incomplete/unverified info as fact.*

## How the Pieces Fit Together

```
Character Trait (memory rule #1)
  "Investigative rigor and integrity"
  → Fires on ALL responses, ALL projects
  → Broad principle: completeness, verification, honesty about gaps
      │
      ├── Session Handoff Skill (SKILL.md)
      │     → Fires on handoff/summary requests + compaction events
      │     → Concrete protocol: 4-step retrieval, structured template,
      │       6 quality gates, failure mode table
      │     → The character trait made actionable for the worst-case scenario
      │
      ├── Memory rule #2 (handoff trigger)
      │     → "Before writing any handoff: read the skill first"
      │     → Ensures the skill is consulted, not bypassed
      │
      └── Memory rule #3 (compaction trigger)
            → "When compaction occurs: produce checkpoint immediately"
            → Ensures the most critical trigger isn't missed
```

The skill gives the trait *teeth* for handoffs. The memory rules ensure the skill actually fires. The trait ensures the underlying principle applies everywhere, not just handoffs.

## Why Compaction Is the Critical Trigger

Compaction is the exact moment context starts being destroyed. The system-generated compaction summary is lossy — it captures the gist but drops detail, nuance, corrections, rationale, and file paths. A structured handoff produced immediately after compaction preserves far more than the compaction summary alone.

Additionally, a well-structured handoff document in the conversation history is dramatically more searchable than scattered exchanges. When `conversation_search` hits a handoff, it finds concentrated keywords, specific file paths, named decisions, and explicit topic labels — all in one place. This single artifact makes every future reference to this conversation more reliable.

## Installation

1. Download `session-handoff.skill`
2. Open it (or drag into Claude Desktop)
3. It appears in Settings → Skills with its own toggle
4. The SKILL.md body is read at runtime whenever the description triggers match

The three memory rules are already active and persist across all conversations in this project.

## Future Considerations

- **Promotion path:** If the investigative rigor rule (memory #1) proves durable across many conversations, it should be promoted to system instructions (Core Protocols section, alongside "Evidence before assertion" and "Confidence signaling"). Memory is a staging area, not a permanent home for behavioral rules.
- **Companion skill:** The same character trait could spawn other domain-specific skills (e.g., an "investigative research" skill for literature review tasks, where the same exhaustive-retrieval-before-response principle applies).
- **Measurement:** The quality gates in the skill are self-checks, not external validation. A future improvement would be a mechanism to verify that the handoff actually covers the full conversation scope (e.g., comparing topic count against transcript sections).
