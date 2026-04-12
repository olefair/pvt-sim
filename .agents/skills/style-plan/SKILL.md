---
name: style-plan
description: "Stage 3 of the cognitive style chain: strategic planning. Takes the synthesized briefing produced by Reflect and translates it into structured, actionable strategy — goals, phases, deliverables, dependencies, and risks — without descending into implementation details. Trigger on: 'plan mode', 'plan this', 'make a plan', 'lay out the strategy', 'what are the phases', 'structure this', 'roadmap', 'give me a plan', or any request to convert understanding into organized strategic action. Also trigger after a Reflect phase when the user is ready to move from synthesis to structure."
---

# Style: Plan

## Role in the Style Chain

**Position:** Stage 3 — the bridge between understanding and implementation.

Plan takes the organized synthesis from Reflect (or, less ideally, raw input) and translates it into strategic structure: goals, phases, deliverables, dependencies, and risks. It operates at the architectural level — what needs to happen, in what order, with what dependencies — without specifying how each piece gets built. Plan is the last purely strategic stage before work becomes concrete. Its output is the blueprint that Show Working and Build execute against.

**Input state:** An organized briefing — key themes identified, tensions flagged, open questions resolved or consciously deferred. Typically the output of Reflect. If a Reflect summary or prior exploration exists, Plan must reference it explicitly as its starting point.
**Output state:** A structured plan document: goals, phases, deliverables, dependencies, risks, and success criteria. Must be specific enough that Build can execute against it without re-deriving the strategy.
**Precedes:** Show Working (detailed reasoning and methodology), Build (implementation)
**Follows:** Reflect (convergent synthesis), or occasionally Explore if the problem is well-enough understood to skip synthesis

## Cognitive Mode

Strategic structuring. The goal is to impose actionable order on synthesized understanding. Plan thinks in phases, dependencies, and risks — not in code, algorithms, or implementation steps. It asks "what needs to happen and in what order?" rather than "how does this get built?" The discipline of Plan is staying at the right altitude: high enough to see the full scope, low enough to produce specific deliverables and dependencies rather than vague aspirations.

## When to Use

- After Reflect has produced a synthesis, and the user is ready to structure action
- When the user says "plan", "strategy", "roadmap", "phases", "what's the order of operations"
- When a project or task needs decomposition into organized, sequenced work
- Before Build — to ensure implementation has a coherent strategy behind it

## Application Instructions

Read `references/original-style-prompt.md` and apply its instructions to all subsequent responses until told otherwise. Key behavioral shifts:

- **Each reply is either a Document or Thinking/Collaboration — never mixed.** Documents go in code blocks with appropriate formatting (`txt`, `md`). Thinking/collaboration uses headings with paragraphs or short sentence lists.
- Operate at the **strategic level**: goals, phases, deliverables, dependencies, risks
- If a Reflect summary or prior exploration exists, **reference it explicitly** as the starting point
- **Do not produce code or implementation details** — that belongs to Show Working and Build
- Be full and comprehensive — a plan that's vague is worse than no plan because it creates false confidence

## Anti-Patterns

These prohibitions exist because Plan's value depends on maintaining strategic altitude without collapsing into premature implementation:

- **Producing code or implementation details** — Plan that includes code has left the strategic level and is doing Build's job. The resulting plan becomes an awkward hybrid where some parts are strategic and others are concrete, making it hard to use as a coherent blueprint
- **Mixing document and thinking modes** — the output format discipline exists because plans are reference documents. A reply that's half-plan, half-discussion is neither a clean document nor a productive conversation. Keeping them separate means each output type serves its purpose cleanly
- **Ignoring prior Reflect output** — Plan that starts from scratch when a Reflect summary exists is throwing away synthesized understanding and re-deriving from raw memory, which is both slower and less reliable
- **Vague deliverables** — "handle authentication" is not a deliverable. "Design auth flow with OAuth2 + refresh token rotation, documented as an architecture decision record" is. Vagueness in Plan means ambiguity in Build.

## Deactivation

Stop applying this style when the user says "normal mode", "drop the style", "reset style", switches to another style skill, or signals readiness to implement (e.g., "let's start building" — at which point Show Working or Build is the natural next stage).

## Chain Awareness Note

Plan without Reflect tends to over-index on whatever the planner remembers most vividly from the exploration, producing a plan that covers 60% of the problem space thoroughly and ignores the rest. Plan without Explore produces a plan for the problem as initially framed, which may not be the right problem. The full chain — Explore → Reflect → Plan — ensures the plan addresses the actual problem space rather than a convenient subset of it. If either upstream stage was skipped, Plan should flag that explicitly rather than proceeding as if the foundation is solid.
