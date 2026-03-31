# When NOT to Refactor

Knowing when to leave code alone is as important as knowing how to fix it.
These are situations where refactoring is wrong, premature, or counterproductive.

---

## 1. No Tests, No Refactor

If the code has zero test coverage, you cannot safely refactor it. Refactoring
is behavior-preserving transformation — without tests, you have no way to
verify behavior is preserved.

**What to do instead:** Write characterization tests first. These capture
what the code currently does (even if it's wrong). Then refactor with the
safety net of tests.

**Exception:** If the refactoring IS adding tests (e.g., extracting a function
to make it testable), proceed carefully and verify manually.

---

## 2. The Code Works and Nobody Touches It

A 400-line function from 2019 that hasn't been modified in 3 years and has
no open bugs is not a problem. It's ugly, but it's stable.

**Why leave it alone:** Refactoring introduces risk. If the code is never
modified, the risk has zero upside. You're trading known-stable code for
potentially-broken code in exchange for aesthetics.

**When it IS worth refactoring:** When you need to modify it for a new feature.
Then the refactoring is amortized into the feature work — you're cleaning
the room you need to work in.

---

## 3. Unfamiliar Codebase, Day One

Don't refactor code you don't understand yet. What looks like a mess might
be intentional. What looks like a god file might have been carefully designed
to keep related concerns together (and the alternative was worse).

**What to do instead:** Read the code, build the dependency graph, understand
the architecture. After a week, you'll know which messes are real and which
are deliberate.

---

## 4. "It Should Use [New Pattern]"

Refactoring to a newer pattern (dependency injection, decorators, dataclasses,
Protocol classes) is not justified by the pattern being newer. It's justified
by the old pattern causing actual problems.

**Questions to ask:**
- Is the current pattern causing bugs? (If no, leave it)
- Is the current pattern making changes harder? (If no, leave it)
- Will the new pattern require rewriting tests? (If yes, the cost is high)
- Does the team know the new pattern? (If no, you're creating a learning curve)

---

## 5. Pre-Optimization Refactoring

"Let me refactor this so it's ready for the feature we might add next quarter."

Don't refactor for hypothetical future requirements. The future requirement
might never come. Or it might come in a form you didn't predict, making your
refactoring useless or actively harmful.

**The exception:** If the blueprint explicitly plans for the future feature
and the refactoring is in the blueprint, then it's planned work, not speculation.

---

## 6. Cosmetic Consistency for Its Own Sake

Some files use `snake_case`, others use `camelCase`. Some functions have
docstrings, others don't. Some use `'single quotes'`, others `"double quotes"`.

If the inconsistency is within a single file, fix it. If it's across the
codebase and there's no active linting/formatting tool, don't embark on a
repo-wide rename. The diff will touch hundreds of lines, pollute git blame,
and risk merge conflicts with in-flight feature work.

**What to do instead:** Enforce the convention going forward (add a linter rule).
Clean up old code opportunistically when you're already modifying a file.

---

## 7. "This Is Too Coupled" (But the Coupling Is Inherent)

Sometimes high coupling between two modules is correct. A database model
and its repository are supposed to be tightly coupled — the repository's
job is to know everything about the model.

**Signs the coupling is inherent:**
- The two modules represent the same domain concept at different layers
- Changing one always requires changing the other (by design, not by accident)
- Decoupling would require creating an interface with exactly one implementation

**Signs the coupling is accidental:**
- Module A reaches into Module B's internals (accesses private attributes)
- The coupling is one-way (A depends on B, but B doesn't know about A) — and
  extracting an interface would allow swapping implementations

---

## 8. Right Before a Release

Refactoring right before a release introduces risk at the worst time. Even
"safe" refactoring can break things. The cost of a post-release bug vastly
outweighs the benefit of cleaner code.

**What to do instead:** Track the refactoring candidate. Schedule it for
right after the release, when there's time to test thoroughly.

---

## 9. The Code Is Scheduled for Deletion

If a module is being replaced or deprecated, don't refactor it. You're
spending effort on code that's about to disappear.

**Check:** Is there a migration plan or deprecation ticket? If so, leave
the old code alone and focus on the replacement.

---

## 10. Refactoring as Procrastination

Sometimes "I should clean this up first" is avoidance of the harder task
(implementing the feature, fixing the bug). If the refactoring isn't on the
critical path, do the hard thing first.

**Litmus test:** If you removed the refactoring from the plan, would the
feature still ship? If yes, the refactoring is optional and can be deferred.

---

## The Decision Framework

Before prescribing any refactoring, answer these four questions:

1. **Is there a concrete problem?** (bugs, blocked features, test failures)
   If no → don't refactor.

2. **Are there tests?** If no → write characterization tests first.

3. **Is this the right time?** (not pre-release, not pre-deletion, not
   day-one on the codebase) If no → defer.

4. **Is the cost proportional to the benefit?** If the refactoring touches
   20 files to make one file slightly cleaner → probably not worth it.

If all four answers are favorable, proceed with the refactoring. Otherwise,
document the smell and revisit when conditions change.
