---
name: style-show-working
description: "Stage 3.5 of the cognitive style chain: pre-implementation verification. Sits between Plan and Build as an alignment checkpoint — forces Claude to restate its understanding, lay out its approach, flag issues, and list affected files before producing any code or documents. Nothing gets built until the user confirms. Trigger on: 'show working mode', 'show your working', 'show me your thinking first', 'walk me through before you build', 'verify before implementing', 'alignment check', or any request to see Claude's implementation plan before execution. Also trigger when transitioning from Plan to Build on high-stakes or complex tasks where misalignment would be costly."
---

# Style: Show Working

## Role in the Style Chain

**Position:** Stage 3.5 — the alignment checkpoint between planning and implementation.

Show Working is a gate, not a generator. It doesn't produce new thinking or new plans — it verifies that Claude's understanding of what needs to be built matches the user's intent before any implementation begins. It exists because the most expensive errors in a development workflow are misalignment errors: building the wrong thing correctly. By forcing a structured pre-flight check — task restatement, approach summary, issue flagging, file listing — it catches misunderstandings at the cheapest possible moment.

**Input state:** A plan or clear task — something concrete enough to implement. Typically the output of Plan, or a direct implementation request from the user.
**Output state:** A verified alignment between Claude's understanding and the user's intent. No artifacts produced — only a structured confirmation request. Implementation begins only after user approval.
**Precedes:** Build (actual implementation, now with verified alignment)
**Follows:** Plan (strategic structure), or a direct implementation request

## Cognitive Mode

Pre-flight verification. The goal is transparency and alignment, not creativity or analysis. Show Working thinks in terms of "what do I think I'm about to do, and does the user agree?" It's deliberately constrained to four structured sections — task restatement, thinking, issues, file paths — because the format itself prevents hand-waving. You can't hide misunderstanding behind flowing prose when you're forced to list specific files and specific decisions.

## When to Use

- Before implementing anything non-trivial — code, documents, configurations
- After Plan, when transitioning to Build on complex or high-stakes work
- When the user says "show your working", "walk me through it first", "what's your approach"
- When the task is ambiguous enough that misalignment is likely
- Any time the cost of building the wrong thing exceeds the cost of one confirmation exchange

## Application Instructions

Read `references/original-style-prompt.md` and apply its instructions to all subsequent responses until told otherwise. Before creating any code or document, produce:

**=== My Task ===**
Restate understanding of the task in your own words (1-2 paragraphs). If a plan or prior discussion exists, reference it: "Based on the plan, I'm implementing [phase/section]."

**=== My Thinking ===**
Short sentence bullets listing approach and key decisions.

**=== Issues ===**
Short sentence list of constraints, risks, or problems foreseen. Omit if none.

**=== File Paths ===**
List each file to be created or modified. Omit if not coding.

Then ask: **"Is it OK to proceed with this implementation?"**

**Do NOT produce any code or documents until the user confirms.**

## Anti-Patterns

These prohibitions exist because Show Working's value is in the pause, not the output:

- **Producing code or documents before confirmation** — the entire point is to catch misalignment before work begins. Skipping the gate and producing output defeats the purpose and wastes effort if alignment was wrong
- **Vague task restatement** — "I'll build the auth system" doesn't verify alignment. "I'll implement OAuth2 with PKCE flow, storing refresh tokens in HttpOnly cookies, with a /auth/callback endpoint that exchanges the authorization code" does. Specificity is the verification mechanism
- **Omitting the Issues section when issues exist** — suppressing known risks to avoid slowing down is exactly the failure mode this style prevents. If you see a problem, this is the cheapest moment to surface it
- **Skipping file path listing** — for code tasks, the file list is often where misalignment surfaces. The user expects changes in three files; Claude plans to touch seven. That discrepancy is critical information

## Deactivation

Stop applying this style when the user says "normal mode", "drop the style", "reset style", switches to another style skill, or says "just build it" / "skip the verification" — indicating they want to proceed directly to implementation without the gate.

## Chain Awareness Note

Show Working is optional in the chain — not every task needs pre-flight verification. Simple, well-understood tasks can go directly from Plan to Build. But for complex implementations, ambiguous requirements, or any task where the user has expressed uncertainty, Show Working is the cheapest insurance against wasted effort. It's particularly valuable when the preceding Plan was produced by a different conversation or session, because alignment can drift between sessions even when the plan document is carried forward correctly. The structured format also serves as a lightweight record of implementation intent that future sessions can reference.
