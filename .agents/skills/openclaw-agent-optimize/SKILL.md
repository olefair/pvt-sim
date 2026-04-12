---
name: openclaw-agent-optimize
description: >
  Audit and improve an OpenClaw workspace for cost, context discipline,
  delegation, cron posture, and reliability. Use when the user wants a
  structured optimization review with options, a recommended plan, exact change
  proposals, rollback steps, and verification guidance. Do not use for
  immediate config or cron mutations without review, or for unrelated general
  architecture advice.
---

# OpenClaw Agent Optimize

Advisory-first workflow for improving an OpenClaw workspace without making
persistent changes prematurely.

## Output

Default output is chat-only. Produce:

- executive summary
- top optimization drivers
- options with tradeoffs
- recommended plan
- exact proposed changes
- rollback plan
- post-change verification steps

Do not apply persistent config, skill, memory, or cron changes without explicit
user approval.

## Workflow

### Step 1: Establish the optimization surface

Identify what the user actually wants improved:

- cost or token burn
- context bloat or transcript noise
- cron behavior
- heartbeat behavior
- model routing
- delegation posture
- reliability or repeated failures
- operator friction

If the user did not define scope clearly, propose a narrow audit surface before
recommending changes.

### Step 2: Audit before proposing fixes

Inspect the current workspace state before recommending action.

Prioritize directly observable evidence such as:

- current skill surface
- always-loaded files and long bootstrap text
- repetitive or noisy automation behavior
- cron schedules and delivery posture
- memory/log patterns that grow without bound
- repeated failure loops or high-friction workflows

Prefer current local evidence over generic best-practice advice.

### Step 3: Find the dominant cost or reliability drivers

Classify the main drivers before suggesting optimization:

- frequent triggers
- large tool outputs
- long repeated prompts
- overly broad always-visible skill surface
- weak delegation boundaries
- repeated retries or non-idempotent tasks
- monitoring or notification paths that run too often

Do not mix symptoms and causes. Name the repeating unit when possible.

### Step 4: Generate options before recommending a plan

Produce at least two viable options when the tradeoff affects coverage,
visibility, latency, or complexity.

Use this bias:

- smallest reversible change first
- preserve behavior before adding cleverness
- reduce noise before reducing capability
- isolate heavy work before changing user-facing behavior

### Step 5: Recommend the smallest safe change first

The recommended plan should:

- target the dominant driver
- minimize persistence and blast radius
- be easy to rollback
- be easy to verify in a fresh session when session snapshotting or caching may
  hide the effect

### Step 6: Require approval for persistent changes

Require explicit user approval before:

- editing durable config
- changing heartbeat posture
- creating, updating, or deleting cron jobs
- installing or removing skills
- introducing new durable state files or logs

Before any approved change, show:

1. exact change or diff
2. expected impact
3. rollback plan
4. how success will be verified

## Optimization Heuristics

- Keep heartbeats control-plane only when possible.
- Move heavy recurring work out of chat turns and into isolated, bounded flows.
- Prefer script-first or artifact-first recurring jobs over long prompt-first
  jobs.
- Keep always-loaded prompt surface short and load-bearing only.
- Reduce unnecessary always-visible specialist surface before adding more
  ambient behavior.
- Prefer the cheapest capable model tier for routine work, and escalate only
  when failure or risk justifies it.
- Favor alert-only delivery for recurring automation when silent success is the
  normal case.
- Keep memory and state artifacts small, explicit, and bounded.

## Pete Workspace Notes

When operating inside `C:\Users\olefa\dev\pete-workspace`, treat these as
first-class concerns:

- workspace prompt bloat from always-visible steering files and specialist
  skills
- heartbeat or cron patterns that create repeated context tax
- local documentation and memory sprawl that silently increases review burden
- noisy automation that should be collector-first and notify only on change or
  failure

Do not assume that telemetry or config surfaces from another runtime exist here.
Ground recommendations in the tools and files actually present.

## Failure Modes

- Do not apply “best practices” blindly without local evidence.
- Do not recommend broad cleanup when a single narrow fix would solve the
  problem.
- Do not reduce monitoring coverage without making the tradeoff explicit.
- Do not confuse package metadata cleanup with runtime optimization.
- Do not claim savings you did not actually verify or at least plausibly bound.

## References

- `references/optimization-playbook.md` - reusable optimization checklist
- `references/model-selection.md` - tiered model assignment guidance
- `references/context-management.md` - context discipline and prompt hygiene
- `references/agent-orchestration.md` - delegation and isolation patterns
- `references/cron-optimization.md` - recurring-job cost and reliability patterns
- `references/heartbeat-optimization.md` - heartbeat-specific tradeoffs
- `references/memory-patterns.md` - durable vs transient memory design
- `references/safeguards.md` - anti-loop and approval guardrails
