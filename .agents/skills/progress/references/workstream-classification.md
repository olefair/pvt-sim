# Progress Workstream Classification

Use these rules when deciding where a lane belongs in a Progress summary.

## Active

Put a lane under **Active** when:

- meaningful work is currently in motion
- the lane still has real remaining scope
- the governing Directive / Plan / active execution state still points to live work

A lane is not automatically active just because a thread, note, or session still exists.

## Blocked / waiting

Put a lane under **Blocked / waiting** when:

- it is still genuinely active
- but cannot proceed cleanly because of an external dependency, missing artifact, runtime issue, or unresolved prerequisite

## Waiting on Ole

Put something under **Waiting on Ole** when:

- a human decision, preference, approval, or pivotal branch is the real bottleneck
- Ole's answer would materially change execution quality, speed, or correctness

## Next up

Use **Next up** for the highest-leverage near-term moves that are not already blocked on Ole.

## Can be closed

Put a lane under **Can be closed** when:

- its main goal is functionally done
- any needed durable output already exists
- remaining follow-up is minor, optional, or moved elsewhere
- keeping it listed as active would be misleading

Checkpoint-back-to-main is the default closure mode. Do not require a heavyweight closure artifact unless the work type actually justifies it.

## Parked / deferred

Use this for intentionally inactive items, low-priority backlog, or things explicitly paused for later.

## Coherent concurrency check

Do not judge health by a rigid lane count alone.

Instead ask:

- are the active lanes cleanly isolated?
- are they fighting over the same shared surfaces?
- are they waiting on the same unresolved policy fork?
- does the coordination load still look sane?

A larger number of narrow, isolated lanes may be healthier than a small number of broad, entangled ones.
