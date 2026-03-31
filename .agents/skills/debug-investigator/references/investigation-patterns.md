# Investigation Patterns

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

Common bug categories and their investigation strategies.

## "It crashes when..."

Start at the crash point (stack trace). Trace backwards through the call chain. The crash is the symptom, not the cause — the cause is usually 2-5 frames up the stack.

## "It gives the wrong value"

Trace the data flow. Find where the value is computed. Check every transformation along the path. The bug is where the computation diverges from intent.

## "It worked before and now it doesn't"

Check `repo_hotspot_history` for recent changes. Diff the changed files against the symptom. Recent changes to high-coupling files are the prime suspect.

## "It only happens sometimes"

Intermittent bugs are usually: race conditions, state-dependent logic, external service flakiness, or uninitialized variables. Focus on shared mutable state and external calls.

## "It's slow"

Not a logic bug but a performance bug. Trace the hot path. Look for: N+1 queries, unnecessary recomputation, blocking I/O in async contexts, missing caches, or O(n^2) algorithms on growing data.

## Root Cause Report Format

```
## Bug Investigation: [symptom summary]

### Root Cause
[1-3 sentences: what's wrong and why]

Location: [file:function:line range]
Trigger: [specific conditions that cause the bug]

### Evidence Chain
1. User action -> [entry point]
2. [entry point] calls -> [function A]
3. [function A] passes [data] to -> [function B]
4. [function B] assumes [X] but actually [Y] <- BUG IS HERE
5. This causes [downstream effect] -> [observed symptom]

### Hypotheses Evaluated
- H1: [description] — CONFIRMED <- root cause
- H2: [description] — ELIMINATED (because [reason])

### Suggested Fix Direction
- What to change: [specific function/logic]
- What to preserve: [behavior that must not change]
- What to test: [how to verify the fix works]
- Risk: [what could go wrong with the fix]
```
