# Common Root Causes by Symptom Type

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

Diagnostic shortcuts: when you see symptom X, check for cause Y first.
These are heuristics, not guarantees — always verify with evidence.

---

## "It returns the wrong value"

### Check first: Data transformation errors
- Wrong unit conversion (psi vs Pa, °F vs °R)
- Off-by-one in indexing (0-based vs 1-based)
- Integer division where float was intended (`5/2 = 2` in Python 2, not 2.5)
- Stale variable (computed once, used after state changed)
- Wrong variable name (copy-paste: used `temperature` where `pressure` was needed)

### Diagnostic shortcut
Trace the data backwards from where the wrong value appears. At each step,
ask: "Is this value correct at this point?" The bug is at the first step
where the answer is no.

---

## "It crashes / raises an unexpected exception"

### Check first: Missing input validation
- None/null passed where a value was expected
- Empty collection accessed by index (`items[0]` when items is empty)
- String where number expected (or vice versa)
- File/path doesn't exist
- Network endpoint unreachable

### Diagnostic shortcut
Read the stack trace bottom-up. The crash site is the symptom. The cause is
usually 2-5 frames up — where bad data was created or where a check should
have been.

---

## "It worked before and now it doesn't"

### Check first: Recent changes
1. Run `repo_hotspot_history` — what files changed recently?
2. For each recently-changed file on the code path: what specifically changed?
3. Cross-reference: does the change affect the failing behavior?

### Common causes
- New code path introduced a side effect (global state mutation, file write)
- Dependency update changed behavior (check requirements.txt changes)
- Config change (new env var, changed default, different environment)
- Data shape changed (new field, missing field, different type)

### Diagnostic shortcut
If you can identify the last-known-good state (git commit, timestamp), diff
everything that changed since then. The cause is in the diff.

---

## "It only happens sometimes" (intermittent)

### Check first: Concurrency and external state
- Race condition on shared mutable state (see worked example)
- External service flakiness (API timeout, rate limit, DNS resolution)
- Time-dependent logic (time zones, DST transitions, midnight boundary)
- Order-dependent initialization (import order, startup sequence)
- Resource exhaustion under load (file handles, connections, memory)

### Diagnostic shortcut
Ask: "What varies between the working and failing cases?" If the code is
identical each time, the variable must be external: timing, load, network,
or accumulated state.

### Key questions
- Does it happen more under load? → concurrency or resource exhaustion
- Does it happen at specific times? → time-dependent logic
- Does it happen after the service runs for a while? → memory leak or state accumulation
- Is it truly random? → uninitialized variable or hash ordering

---

## "It's slow"

### Check first: Algorithmic and I/O issues
- N+1 queries (loop making one database/API call per item)
- O(n²) algorithm on growing data (nested loops, repeated search)
- Blocking I/O in async context (sync HTTP call in async handler)
- Missing index (database full table scan)
- Repeated computation (same expensive call in a loop without caching)
- Logging at debug level writing to disk on every request

### Diagnostic shortcut
Add timing to each step of the code path. The step with the most time is
where to focus. Don't optimize the fast parts.

---

## "It hangs / never completes"

### Check first: Deadlocks and infinite loops
- Deadlock: two locks acquired in different order by different threads
- Infinite loop: loop condition that can never become false
- Blocking read: waiting for input/data that never arrives (missing timeout)
- Circular dependency at startup: module A imports B which imports A

### Diagnostic shortcut
If the process is still running: what's it doing? Check CPU usage:
- CPU at 100% → infinite loop (tight loop, no I/O)
- CPU at 0% → blocked on I/O or lock (waiting for something)

---

## "It works locally but not in production/CI"

### Check first: Environment differences
- Different Python/Node/runtime version
- Missing environment variable or different default
- Different OS (path separators, case sensitivity, line endings)
- Missing dependency (not in requirements, or different version)
- Different filesystem permissions
- Different timezone setting
- Docker vs bare metal (filesystem, networking, resource limits)

### Diagnostic shortcut
Compare environments systematically: runtime version, env vars, installed
packages, OS. The first difference you find that touches the code path is
the likely cause.

---

## "The error message doesn't match the actual problem"

### Check first: Exception handling that swallows context
- Bare `except:` or `except Exception:` that re-raises a generic error
- Error handling that catches the real error and raises a different one
- Logging that captures the wrong variable (`logger.error(f"Failed: {result}")` when `result` is the wrong thing to log)
- Error message written for a different failure mode (copy-pasted handler)

### Diagnostic shortcut
Ignore the error message. Read the code at the crash site. The code tells
you what actually happened; the message tells you what someone thought
might happen.
