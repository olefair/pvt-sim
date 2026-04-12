---
name: multi-agent-feature-planner
description: Run the planning-first multi-agent feature workflow for a feature request, short spec, or repo-scoped implementation idea. Use when the goal is to produce a routed, repo-grounded planning package and controlling blueprint files for later builder work, not to execute the build itself.
---

# Multi-Agent Feature Planner

Use this as the top-level planning workflow entrypoint.

## Core stance

- Stay planning-first.
- Write planning artifacts to files before summarizing in chat.
- Do not execute builder implementation from this skill.
- Reuse or extend an existing controlling blueprint when one already covers the work.
- Stop and ask for clarification when the repo/workspace path or scope is too ambiguous for grounded planning.

## Required reads at start

Before planning, read these canonical vault notes:
- `docs/plans/workspace/plan_multi-agent-feature-planning-workflow.md`
- `docs/reference/workspace/reference_multi-agent-feature-planning-artifact-schema.md`

Use workspace-root-relative paths in any written content unless an absolute path is genuinely required for runtime configuration.

Also confirm the currently available helper skills you may delegate to:
- `blueprint-router`
- `read-repo`
- `blueprint-architect`
- `test-strategist`
- `blueprint-progress-checker`

When spawning or emulating workers, also read these role references as needed:
- `references/worker-foundation.md`
- `references/style-stage-integration.md`
- `references/worker-security-adversarial.md`
- `references/worker-implementation-engineering.md`
- `references/worker-continuity-integration.md`
- `references/worker-capability-leverage.md`
- `references/worker-operations-runtime.md`

## Trigger fit

This skill fits requests like:
- "Run the multi-agent feature planning workflow for..."
- "Plan this feature before coding it"
- "Turn this feature request/spec into a planning package"
- "Create the blueprint/handoff package for this repo change"

Minimum required inputs:
- `feature_name`
- `goal`
- `repo_or_workspace_path`

Strongly recommended inputs:
- `problem_statement`
- `constraints`
- `non_goals`
- `attached_spec_paths`
- `deadline_or_priority`
- `checkpoint_mode`

Normalization defaults:
- missing `checkpoint_mode` => `mandatory`
- missing `constraints` => `none supplied by requester`
- missing `non_goals` => `not yet specified`
- missing spec attachment => derive a short inferred intake summary and label it inferred
- ambiguous `repo_or_workspace_path` => stop and request clarification

## Workflow

1. **Load governing docs**
   - Read the two canonical vault notes above.
   - Treat the plan note as the stage/decision authority and the reference note as the run-artifact contract.

2. **Normalize intake**
   - Convert the request into a compact run brief.
   - Record any inferred fields explicitly.

3. **Route first**
   - Use `blueprint-router` posture to determine whether a controlling blueprint already exists.
   - Classify as `reuse-existing`, `extend-existing`, `new-blueprint-needed`, or `insufficient-context`.
   - If context is insufficient, stop.

4. **Ground in the repo**
   - Use `read-repo` posture plus targeted reads/searches.
   - Separate observed facts from inferred architecture.
   - If the real surface is still vague, stop and ask for scope narrowing.

5. **Explore and converge**
   - If subagent orchestration is available, follow the staged workflow in the canonical plan note.
   - If subagent orchestration is not available, emulate the same stages sequentially and say that the workflow was run in single-agent fallback mode.
   - Preserve the stage boundaries: intake/route, grounding, generation, review, debate, arbiter-if-needed, plan synthesis, show-working, handoff.
   - Treat generation as Explore-derived, review as Reflect-derived, and debate as a Reflect + Show Working hybrid.
   - Do not let workers debate before the review stage is complete.

6. **Produce the planning package**
   - Write the run artifacts required by the canonical artifact-schema note.
   - Produce or identify the controlling blueprint.
   - Use `blueprint-architect` for blueprint authoring or refinement.
   - Use `test-strategist` when verification planning needs its own explicit pass.

7. **Checkpoint before handoff**
   - Do not start builder execution.
   - Summarize the package, controlling blueprint, open questions, and recommended next actor.
   - If the run is blocked on human input, say so plainly.

## Output contract

At minimum, produce:
- a routing decision
- repo-grounding notes backed by observed files
- a controlling blueprint path or explicit reuse/extend result
- the run package files required by the canonical artifact schema
- a concise final summary naming risks, unknowns, and next step

## Guardrails

- No code changes outside planning docs/skill scaffolding for this workflow.
- Do not quietly skip file writes and rely on chat history as the record.
- Do not reopen explore after show-working; return only to plan refinement when needed.
- Do not widen scope from planning into implementation.
- If a material information gap appears, escalate to the human instead of improvising.

## Notes

- Prefer exact canonical paths and Obsidian wikilinks when writing vault documents.
- If the workflow evolves, keep this skill aligned with the two canonical vault notes rather than duplicating long contracts here.
