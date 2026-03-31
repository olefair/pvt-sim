# Migration Pitfalls

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

Common ways migrations fail, even when the plan looks correct.

---

## 1. "I Think That's All the Callsites"

**What happens:** You search for `old_lib.function()` and find 15 callsites.
You migrate all 15. You missed 3 more that use `from old_lib import function`
and then call `function()` without the module prefix.

**Why it's dangerous:** The migration appears complete. Tests pass because
the 3 missed callsites are in error paths that aren't tested. In production,
those error paths fire and call a function that no longer exists.

**Prevention:** Search for EVERY import pattern:
- `import old_lib`
- `from old_lib import X`
- `from old_lib import X as Y` (aliased — easy to miss)
- `old_lib.X` (direct usage)
- `X` (after `from old_lib import X` — hardest to find)
- String references: `"old_lib"` in configs, mock patches, dynamic imports

After migration, search for any remaining reference to the old name. Zero
matches is the only acceptable result.

---

## 2. Behavior Change Disguised as API Change

**What happens:** The new library's function has the same name and similar
signature, but subtly different behavior. You swap the import, tests pass,
but production behavior changes.

**Examples:**
- Old function returns `None` on failure; new one raises an exception
- Old function returns a list; new one returns an iterator (breaks `len()`, indexing)
- Old function is synchronous; new one is async (returns a coroutine object)
- Old function accepts `**kwargs` and ignores unknowns; new one raises on unknown args
- Old function sorts results; new one doesn't (or sorts differently)

**Prevention:** For each function in the translation table, document not just
the signature change but the behavioral change. Write a test that exercises
the specific behavioral difference before migrating.

---

## 3. Mock Patches That Reference Old Paths

**What happens:** You migrate `app/utils/old_client.py` to
`app/utils/new_client.py`. All imports updated. But tests use:
```python
@mock.patch("app.utils.old_client.send_request")
```
This mock now patches a module that doesn't exist. The test passes because
the mock silently does nothing — the real function runs instead.

**Prevention:** Search for all `mock.patch` and `mock.patch.object` calls.
Every path string is a migration target.

---

## 4. Migrating Core Before Leaves

**What happens:** You migrate the most-imported utility module first because
it's the most important. Now 30 files that import it are broken simultaneously.
You have to fix all 30 before you can run tests.

**Prevention:** Always migrate leaf files first (fan_in = 0). Each leaf
migration is independently testable. Core modules (high fan_in) go last,
when all their callers have already been updated.

---

## 5. Type System Mismatches

**What happens:** The old library returns `str` everywhere. The new library
returns `Path` objects (or `bytes`, or custom types). Code that did
`result + "/suffix"` now breaks because you can't concatenate `Path + str`.

**Prevention:** Check the return type of every migrated function. If it
changed, trace every usage of the return value downstream.

---

## 6. Transitive Dependencies You Didn't Know About

**What happens:** Module A imports old_lib. Module B doesn't import old_lib
but gets a return value from A that's an old_lib type. After migrating A,
B receives a new_lib type. B's code that expected old_lib's type breaks.

**Prevention:** Run `repo_impact_graph` to trace not just who imports old_lib,
but who uses values that originated from old_lib. The migration boundary
extends beyond direct importers.

---

## 7. Config and String References

**What happens:** You migrate all code references but miss:
- `.env` files: `DATABASE_CLIENT=old_lib.PostgresClient`
- YAML configs: `driver: old_lib`
- JSON schemas: `{"type": "old_lib.Model"}`
- Log messages: `logger.info("Using old_lib for...")`
- Documentation: `README.md` still says "We use old_lib"
- Docker files: `pip install old_lib`

**Prevention:** Search for the old library name as a plain string across
ALL file types, not just `.py` files:
```
repo_search_content(pattern="old_lib")  # No file type filter
```

---

## 8. Removing the Old Dependency Too Early

**What happens:** After migrating all callsites, you remove old_lib from
requirements.txt. But a plugin or test fixture still imports it dynamically.
The test suite passes locally (old_lib is still in your venv) but fails
in CI (clean install).

**Prevention:** Remove the dependency as the LAST step. After removal, do
a clean install and full test run.

---

## 9. Async/Sync Mismatch

**What happens:** The old library is synchronous. The new one is async. You
swap the import and add `await`. But one of the callers is a sync function
that can't use `await`. Or the function is called in a list comprehension
where `await` doesn't work.

**Prevention:** Check every caller's context. Is it async? Can it be made
async without cascading changes? If not, you need an async-to-sync wrapper
or a different migration strategy for that callsite.

---

## 10. "It Works in Tests" But Tests Mock the Migrated Code

**What happens:** Tests mock the function being migrated. The mock returns
a hardcoded value. The test passes — but it's not testing the new library
at all. The mock is covering up integration issues.

**Prevention:** After migration, audit every mock that touches the migrated
code path. Ensure at least one integration test exercises the real new library
(not mocked).
