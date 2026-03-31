# Code Review Anti-Patterns

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

Common mistakes that make reviews less useful. Check yourself against these
before finalizing a review.

---

## 1. Style Nitpicking While Missing Bugs

**The trap:** You produce 12 findings about naming, whitespace, and import
ordering, but miss the off-by-one error on line 47.

**Why it happens:** Style issues are easy to find. Bugs require understanding
what the code actually does.

**Fix:** Read for correctness FIRST (trace the logic, check edge cases).
Then check conventions. If you found zero bugs, re-read more carefully
before concluding the code is correct.

---

## 2. Reviewing the Diff Without Understanding the Context

**The trap:** You review the 20 changed lines without reading the 200
surrounding lines. You miss that the change breaks an implicit contract
with a function 50 lines above.

**Why it happens:** Diffs feel complete. They're not — they show what
changed, not what the change interacts with.

**Fix:** Always read the full file, not just the diff. Use `repo_impact_graph`
to understand what depends on the changed code.

---

## 3. Suggesting a Complete Rewrite

**The trap:** "I would have done this completely differently." Then you
describe an alternative architecture. The author can't use this — they'd
have to throw away their work and start over.

**Why it happens:** It's easier to imagine a clean solution than to improve
an existing one.

**Fix:** Work within the author's approach. If the approach is fundamentally
flawed, say so clearly and explain WHY (not just that you'd do it differently).
But in most cases, the approach is fine — focus on making it correct and clean.

---

## 4. "LGTM" Without Actually Reading

**The trap:** Rubber-stamp approval because the author is senior, the change
is small, or you're busy.

**Why it happens:** Social pressure, time pressure, assumption that small
changes are safe.

**Fix:** Small changes can have large impact. A one-line change to a function
with 20 callers affects more code than a 200-line new file with zero callers.
Check the impact graph, not just the diff size.

---

## 5. False Positive Bug Reports

**The trap:** You report a "bug" that isn't one because you misunderstood
the code. The author has to spend time explaining why it's correct. Trust
erodes.

**Why it happens:** You read the code too quickly and formed an incorrect
mental model.

**Fix:** Before reporting a bug, trace the exact execution path that produces
the wrong behavior. If you can't construct a specific scenario where it fails,
downgrade to QUESTION: "I'm not sure this handles the case where X — can you
verify?"

---

## 6. Reviewing Tests as an Afterthought

**The trap:** You review the implementation thoroughly but barely glance at
the tests. "Tests look fine." But the tests are tautological — they assert
that the function returns what the function returns.

**Why it happens:** Tests are boring. Implementation is interesting.

**Fix:** Read tests FIRST. The tests tell you what the code is supposed to do.
Then read the implementation to verify it actually does that. If the tests
are weak, the implementation review is less valuable because you can't verify
correctness against anything.

---

## 7. Ignoring the Blast Radius

**The trap:** You review a utility function change and approve it because
the function itself looks correct. But 30 other files import this function,
and the behavior change breaks 5 of them.

**Why it happens:** You reviewed the change in isolation.

**Fix:** Always check fan-in. A change to a function with fan_in > 5 needs
extra scrutiny: did the semantics change? Did the return type change? Did
error behavior change? Are callers prepared for the new behavior?

---

## 8. Conflating "I Wouldn't Do It This Way" with "This Is Wrong"

**The trap:** You report 8 SUGGESTION findings that are really personal
preferences. "I'd use a list comprehension here." "I prefer explicit imports."
These dilute the signal.

**Why it happens:** Reviewers confuse their preferences with objective quality.

**Fix:** Ask: "Would this cause a bug, performance issue, or maintenance
problem?" If not, it's a preference. Limit to 1-2 suggestions per review.
Save them for cases where the alternative is clearly better, not just different.

---

## 9. Not Checking What Happens When It Fails

**The trap:** You verify the happy path works but don't check error handling.
The function works perfectly when the API returns 200 — but crashes when it
returns 500.

**Why it happens:** Happy paths are intuitive. Failure modes require
imagination.

**Fix:** For every external call, ask: "What happens when this fails?"
For every branch: "What if this condition is false?" For every loop:
"What if the collection is empty?" These are where bugs live.

---

## 10. Reviewing a Feature Without Reading the Spec

**The trap:** You review the code for technical correctness but don't check
if it actually implements what was requested. The code is clean, well-tested,
and does the wrong thing.

**Why it happens:** Specs are separate from code. Reviewers focus on code.

**Fix:** If a blueprint or spec exists, read it before reviewing. Check that
every success criterion has corresponding code and tests.
