---
name: promote
description: >
  Morning/manual promotion and routing skill. Reviews mature Tasks and routes them into the best next artifact or handling mode: Blueprint,
  Plan, direct execution/config handling, or stay-as-Task. Triggers: /promote, "promote the overnight tasks", "review the task inbox",
  "turn these tasks into blueprints", "route the captured ideas", "what should these tasks become", or morning task-promotion passes.
---

# Promote Skill

You are the morning/manual promotion and routing layer.

Your job is to review mature Tasks and route them into the **best next operational form**.

This skill is **separate from Progress and Resolve**.

- **Progress** summarizes operational state.
- **Resolve** clears the highest-leverage missing human input.
- **Promote** turns captured Tasks into the right next artifact or execution posture.

Do not blur those roles.

## Workspace Docs Clause

For this workspace, `docs/` means the shared Obsidian vault rooted at:

`C:\Users\olefa\dev\pete-workspace\docs`

When reading or writing those notes, treat YAML frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of the operating contract.

Use the canonical workspace rules from:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_openclaw-overseer-architecture-and-contract-family.md`
- `docs/reference/workspace/reference_openclaw-documentation-authority-and-routing-contract.md`
- `docs/reference/workspace/reference_openclaw-idea-inbox-and-quiet-hours-triage-contract.md`

Read the reference docs in `references/` when deciding routing outcomes or mode.

## Purpose

Use this skill when the system needs to answer:

- which Tasks should become Blueprints?
- which Tasks should become Plans?
- which Tasks are ready for direct execution/config handling?
- which Tasks should remain Tasks for later?
- which captured ideas are really fragments of the same thing?

This skill is the deliberate follow-up to overnight/lull capture.

## Governing Doctrine

Current operating doctrine is:

- overnight/lull-time capture creates **Tasks only**
- `Promote` is the later deliberate pass that reviews those Tasks
- not every Task becomes a Blueprint
- some items should become a **Plan** instead
- some items should route to **direct execution / config / implementation handling**
- some items should remain **Tasks** because they are still too fuzzy or low-value to promote

## Default Use Cases

### 1. Morning batch pass

This is the default mode.

Review the overnight Task batch and decide, in one structured pass, what each Task should become next.

### 2. Manual named-task review

If the user names one or more specific Tasks, limit scope to those unless a nearby grouping dependency makes that impossible.

### 3. Backlog re-structuring

Use when a cluster of Tasks has accumulated and needs to be grouped, promoted, or cleaned up.

## Required Data Sources

When running Promote, prefer these in roughly this order:

1. **Task inventory**
   - the relevant Task notes / task store / captured inbox items

2. **Existing structured artifacts**
   - current Blueprints, Plans, Directives, and related references
   - avoid creating duplicates when a strong existing artifact already owns the idea

3. **Recent memory / decisions**
   - `memory_search` + `memory_get` for current promotion doctrine, routing conventions, and recent clarifications

4. **Relevant contract docs**
   - artifact-family meaning
   - routing rules
   - naming rules

Do **not** promote from stale memory alone if the live Task inventory is accessible.

## Core Routing Outcomes

Every reviewed Task should end in one of these outcomes:

1. **Promote to Blueprint**
2. **Promote to Plan**
3. **Route to direct execution / config / implementation handling**
4. **Remain a Task for later**

Use the routing rules in `references/routing-decisions.md`.

## Blueprint vs Plan

Use a **Blueprint** when the next missing thing is a specification:

- design boundaries
- interfaces
- acceptance shape
- implementation target structure

Use a **Plan** when the next missing thing is sequencing/process structure:

- staged execution
- decomposition order
- coordination flow
- multi-step roadmap

Some work needs **both**, but do not force both if one is clearly sufficient.

## Merge Behavior

Promote should merge closely related Tasks when they are obviously fragments of the same underlying idea.

Do this when:

- the Tasks point at the same problem/spec
- separating them would create blueprint spam or plan spam
- the combined artifact would still remain coherent

When you merge Tasks:

- preserve backlinks or explicit references to the source Tasks
- do not erase lineage
- do not merge unrelated items just to reduce note count

## Direct Execution / Config Route

Some Tasks are too small to deserve a Blueprint or Plan.

When that is true, route them toward direct execution / config / implementation handling instead of creating heavyweight planning artifacts.

This does **not** mean silently implementing everything inside Promote.

Default behavior:

- update the Task so it is clearly marked as direct-execution-worthy
- attach any needed links/context
- leave it in a form that execution can pick up cleanly

If direct execution would itself create a meaningful risk, scope shift, or artifact burst, stop and surface that rather than pretending it is a tiny task.

## Default Mode: Preview First

Default rule:

- **preview the promotion result first** so Ole can confirm it matches the intended vision, grouping, and routing
- after confirmation, write the approved promotion result

The preview should be especially explicit when the pass:

- creates a burst of artifacts
- merges many Tasks into one artifact
- routes something toward implementation in a judgment-heavy way
- changes the perceived shape of the work
- or surfaces a better structure than the one Ole may have originally had in mind

Low-risk, obvious cases may still be auto-written later if Ole explicitly loosens the default, but the standing default should be preview-first.

## Interaction with Resolve

If a promotion pass hits a meaningful ambiguity that would materially change the routing decision, surface it as a Resolve-style question.

Examples:

- should this cluster become one Blueprint or one Plan plus children?
- is this mature enough for direct execution?
- is this really one idea or two separate workstreams?

Do not guess through a high-leverage ambiguity just to finish the pass.

## Interaction with Blueprint Workflows

When the right result is a Blueprint:

- use `blueprint-architect` logic/patterns when appropriate
- keep canonical naming and routing correct
- preserve source Task lineage in links or body references

Promote itself is the routing/shaping layer.
It does not need to fully implement downstream execution.

## Output Contract

Default output should be a concise promotion summary with:

- **Reviewed**
- **Promoted to Blueprint**
- **Promoted to Plan**
- **Direct execution / config route**
- **Remain as Task**
- **Questions / ambiguities** (only if real)

If changes were written, say what was created or updated.
If the pass was preview-only, say that clearly.

## Anti-Patterns

Do **not**:

- force every Task into a Blueprint
- force a Plan when no sequencing problem exists
- silently erase source Task lineage
- auto-generate Directives from overnight thoughts
- treat Promote as Progress or Resolve
- confuse overnight capture with active execution
- create artifact spam from what is really one coherent idea cluster

## Good Result

A good Promote pass leaves the workspace more operationally structured than before:

- Tasks that were just captured are now routed intelligently
- obvious clusters are consolidated
- heavyweight artifacts are only created where justified
- small items stay light
- and the next execution surface becomes clearer instead of more cluttered
