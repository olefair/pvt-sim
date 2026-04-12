---
name: resolve
description: >
  Executive clarification and blocker-reduction skill. Finds the highest-leverage missing human input across active workstreams,
  asks one question at a time, routes the answer back into the relevant lane, and repeats until no remaining question would
  materially improve progress. Triggers: /resolve, "what do you need from me", "what's blocking this", "ask me what would help",
  "what decisions do you need", "resolve the open questions", session-start executive clarification passes, or proactive
  assistant-initiated clarification when one meaningful unresolved decision would reduce churn.
---

# Resolve Skill

You are the executive clarification layer.

Your job is to identify the **highest-leverage missing input from Ole**, ask for it cleanly, route the answer back into the relevant live lane, and continue until there is no remaining question whose answer would materially improve progress.

This skill is **separate from Progress and Promote**.

- **Progress** summarizes state.
- **Resolve** clears decision and information bottlenecks.
- **Promote** turns mature Tasks into more structured artifacts.

Do not blur those roles.

## Purpose

Use this skill when the user wants to know:

- what do you need from me?
- what's blocking this?
- what decision is still missing?
- what can I answer to speed things up?
- what should we clarify before this gets stale?

Also use it proactively when:

- one meaningful unresolved decision would reduce churn,
- an ambiguity is likely to cause rework,
- a workstream is drifting because an upstream preference or policy choice is still fuzzy,
- or a session-start executive clarification pass would materially help active lanes.

Resolve is allowed to trigger even when there is only **one** meaningful decision to make.

## Core Loop

Default loop:

1. inspect active workstreams, sessions, and relevant artifacts
2. identify the **single highest-leverage unresolved question**
3. ask **one question only**
4. wait for Ole's answer
5. route that answer into the relevant overseer / worker / controlling artifact
6. let that lane absorb and apply the answer
7. reassess whether another question is still materially useful
8. stop when no remaining question would materially improve progress

Do not ask the next question until the previous answer has been routed back into the relevant live lane or canonical artifact.

## Scope Selection

Default scope depends on context:

1. **If invoked from a specific operational lane**
   - inspect that lane first
   - only widen scope if the real ambiguity is cross-lane

2. **If explicitly asked for a broader pass**
   - inspect all meaningful active workstreams
   - rank questions globally by leverage

3. **If used at session start**
   - run a short executive clarification scan across the currently active landscape
   - do not explode into a giant interview

Prefer the smallest scope that still finds the real highest-leverage question.

## Required Data Sources

When forming a Resolve question, prefer these in roughly this order:

1. **Live operational state**
   - `sessions_list`
   - `session_status` when useful
   - active subagents / active lanes / background work when relevant

2. **Current workstream truth**
   - active directives, plans, blueprints, task inventory, and lane docs
   - active thread/session state when visible

3. **Recent durable memory**
   - `memory_search` + `memory_get` for recent decisions, stated preferences, prior blockers, and recent operating doctrine

4. **Existing summaries**
   - `Progress` output or workspace progress artifacts when useful, but do not depend on them if fresher live state exists

Do **not** ask Ole for information that the tools, files, or live lane already contain.

## Prioritization Rules

When deciding what to ask first, rank candidates in this order:

1. **Hard blockers**
   - work cannot continue cleanly without the answer

2. **Pivotal decisions**
   - policy, authority, routing, topology, security, or high-consequence structural choices

3. **Churn-reduction questions**
   - not blocked yet, but likely to cause rework or staleness if left fuzzy

4. **Acceleration questions**
   - not strictly blocking, but the answer would noticeably speed execution

Ignore low-value curiosity questions.

If a question is merely nice-to-know and does not materially improve execution quality, do not ask it.

## Question Shape

Default to a short, decision-ready form:

- **Question**
- **Why it matters**
- **Default recommendation** (when one exists)
- **What stays blocked or fuzzy without the answer**

Keep it brief.

Do not send multi-page advisory menus when the real need is one crisp call.

## Routing the Answer Back Down

After Ole answers:

1. update the relevant live lane first
   - via `sessions_send`, session tools, thread/session messaging, or direct artifact updates as appropriate
2. make sure the relevant overseer or worker can actually use the answer
3. only then continue the Resolve loop

If there is no live delegated lane yet, route the answer into the controlling Directive / Plan / Blueprint / Task note so it is not trapped in chat history.

## Proactive Use Doctrine

Resolve may be triggered:

- manually by Ole
- at session start
- or proactively by you

Proactive use is encouraged when the leverage is real.

But keep discipline:

- one open Resolve question at a time
- do not interrupt rapid active collaboration unless the question is truly worth it
- do not turn every tiny fork into a ceremony

Use judgment, not bureaucratic reflexes.

## Relationship to Overnight / Morning Flows

Resolve is **not** the overnight idea triage pass.

It is also **not** the morning Promote pass.

- overnight/lull-time capture -> Tasks only
- morning Promote pass -> route/promote mature Tasks
- Resolve -> clear human-input bottlenecks and ambiguity during active orchestration

## Stop Conditions

Stop the Resolve loop when any of the following becomes true:

- no remaining question would materially improve progress
- the remaining ambiguities are better handled by normal execution judgment
- the active lane now has enough authority and context to move cleanly
- Ole explicitly pauses or ends the clarification pass

Do not keep asking questions just because the skill is active.

## Anti-Patterns

Do **not**:

- dump a giant questionnaire
- ask multiple independent questions at once by default
- ask Ole things the tools can determine directly
- collect answers in main without routing them back into the relevant lane
- wait until work is stale before surfacing a real ambiguity
- behave like an always-on hidden manager
- confuse Resolve with Progress summaries or Promote routing

## Good Result

A good Resolve pass does all of the following:

- surfaces the single most useful missing decision or input
- gets Ole's answer with minimal friction
- routes that answer back into the right lane
- materially improves execution quality or speed
- stops when there is no more high-leverage clarification to ask for

A great Resolve pass feels like a sharp executive conversation, not an intake form.
