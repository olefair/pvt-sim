# Worked Migration Example: os.path → pathlib

Legacy note: if this example mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

A complete library swap walked through step by step, showing how to
find every touchpoint, order the migration, and verify completeness.

---

## Scope

**Source:** `os.path` for all filesystem operations
**Target:** `pathlib.Path`
**Scope:** Entire repo (25 files use `os.path`)
**Coexistence:** Old and new can coexist — no hard swap needed

---

## Phase 1: Find Every Touchpoint

### Search strategy

Don't just search for `import os.path`. Search for every way `os.path`
gets used:

```
repo_search_content(pattern="import os\b")        → 18 files
repo_search_content(pattern="from os.path import") → 3 files
repo_search_content(pattern="from os import path")  → 1 file
repo_search_content(pattern="os\.path\.")          → 47 callsites
repo_search_content(pattern="os\.getcwd")          → 2 callsites
repo_search_content(pattern="os\.listdir")         → 5 callsites
repo_search_content(pattern="os\.makedirs")        → 3 callsites
repo_search_content(pattern="os\.remove")          → 1 callsite
```

**Critical:** Also search for patterns that use `os` but aren't `os.path`:
```
repo_search_content(pattern="os\.environ")         → 12 files (NOT migrating these)
repo_search_content(pattern="os\.getpid")          → 1 file (NOT migrating)
```

These files import `os` for non-path reasons. After migration, they still
need `import os` — don't remove it.

### Classify touchpoints

| Pattern | Count | Migration |
|---------|-------|-----------|
| `os.path.join(a, b)` | 19 | `Path(a) / b` |
| `os.path.exists(p)` | 8 | `Path(p).exists()` |
| `os.path.dirname(p)` | 5 | `Path(p).parent` |
| `os.path.basename(p)` | 4 | `Path(p).name` |
| `os.path.splitext(p)` | 3 | `Path(p).suffix` and `Path(p).stem` |
| `os.path.isfile(p)` | 2 | `Path(p).is_file()` |
| `os.path.isdir(p)` | 2 | `Path(p).is_dir()` |
| `os.path.abspath(p)` | 2 | `Path(p).resolve()` |
| `os.path.expanduser(p)` | 1 | `Path(p).expanduser()` |
| `os.getcwd()` | 2 | `Path.cwd()` |
| `os.listdir(d)` | 5 | `Path(d).iterdir()` or `.glob("*")` |
| `os.makedirs(d, exist_ok=True)` | 3 | `Path(d).mkdir(parents=True, exist_ok=True)` |

---

## Phase 2: API Translation Traps

### Trap 1: os.listdir returns strings, Path.iterdir returns Path objects
```python
# BEFORE — works because items are strings:
for f in os.listdir(directory):
    if f.endswith(".json"):
        data = json.load(open(os.path.join(directory, f)))

# AFTER — wrong if you forget .name:
for f in Path(directory).iterdir():
    if f.suffix == ".json":           # OK — Path has .suffix
        data = json.load(open(f))     # OK — open() accepts Path
```

But if downstream code does `some_dict[f]`, the key is now a Path object
instead of a string. Check every usage of the loop variable.

### Trap 2: os.path.join accepts strings, / operator needs Path on left
```python
# BEFORE:
os.path.join(base, "config", "settings.json")

# AFTER — correct:
Path(base) / "config" / "settings.json"

# AFTER — WRONG (if base is already a Path):
base / "config" / "settings.json"  # Works
"config" / base / "settings.json"  # TypeError: str doesn't support /
```

### Trap 3: os.path.splitext returns a tuple, Path has separate properties
```python
# BEFORE:
name, ext = os.path.splitext(filename)
new_name = name + "_processed" + ext

# AFTER:
p = Path(filename)
new_name = p.stem + "_processed" + p.suffix
# But this returns a string, not a Path!
# If you need a Path: p.with_name(p.stem + "_processed" + p.suffix)
```

### Trap 4: String concatenation with paths
```python
# BEFORE — works because os.path.join returns a string:
log_path = os.path.join(log_dir, "app.log")
rotated = log_path + ".1"  # String concatenation — fine

# AFTER — breaks:
log_path = Path(log_dir) / "app.log"
rotated = log_path + ".1"  # TypeError: can't add str to Path
# Fix: str(log_path) + ".1" or log_path.with_suffix(".log.1")
```

---

## Phase 3: Migration Order

### Dependency analysis

```
repo_dependency_graph() → sort by fan_in:

Fan-in 0 (leaf files — migrate first):
  scripts/cleanup.py
  scripts/export.py
  tests/conftest.py

Fan-in 1-3 (mid-level):
  app/config/loader.py        (fan_in=2)
  app/plugins/manager.py      (fan_in=3)
  app/memory/store.py         (fan_in=2)

Fan-in 5+ (core — migrate last):
  app/utils/paths.py          (fan_in=12)  ← utility module, everyone imports it
```

### Recommended step sequence

1. **Step 0:** Add `from pathlib import Path` to `app/utils/paths.py` — don't
   change any functions yet. Just make Path available for when callers migrate.

2. **Steps 1-6:** Migrate leaf files (scripts, tests). Each file + its test
   in one step. Run tests after each.

3. **Steps 7-12:** Migrate mid-level files. Check for callers that pass string
   paths to these functions — they'll still work because Path accepts strings.

4. **Step 13:** Migrate `app/utils/paths.py` last. This is the highest-impact
   change. Update all path utility functions to return Path objects.

5. **Step 14:** Search for any remaining `os.path` references. Should be zero
   for path operations (some `os.environ` usage will remain — that's fine).

---

## Phase 4: Verification

After all steps complete:

```
# Must return 0 matches (path operations fully migrated):
repo_search_content(pattern="os\.path\.")

# These are fine — os is still needed for non-path operations:
repo_search_content(pattern="os\.environ")  → expected: 12 files
repo_search_content(pattern="os\.getpid")   → expected: 1 file

# Full test suite must pass:
repo_run_tests()
```
