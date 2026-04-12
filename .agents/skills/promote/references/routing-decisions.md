# Promote Routing Decisions

Use this table when deciding what a Task should become next.

## Promote to Blueprint

Choose **Blueprint** when the next missing thing is a specification.

Signals:
- design boundaries need to be defined
- interfaces or structures are still mushy
- implementation would thrash without a clearer target
- the task implies one coherent build/design artifact

## Promote to Plan

Choose **Plan** when the next missing thing is sequencing or coordination.

Signals:
- multi-step rollout
- staged decomposition matters
- multiple child artifacts or execution slices are likely
- the work is more roadmap than spec

## Direct execution / config route

Choose this when the task is too small or obvious to deserve heavy planning.

Signals:
- bounded one-off config or implementation tweak
- low ambiguity
- little or no specification work needed
- creating a Blueprint or Plan would be overhead theater

Do not treat this as permission to silently do risky work inside Promote.

## Remain a Task

Leave it as a Task when:
- it is still fuzzy
- it is low-value backlog
- it needs Resolve first
- there is not enough signal to justify a structured artifact yet

## Merge rule

Merge Tasks when they are clearly fragments of the same underlying idea and one combined artifact will stay coherent.

Do not merge unrelated tasks just to reduce note count.
