# Refactoring Operations Catalog

Legacy note: if this reference mentions historical `repo_*` helper names,
treat them as shorthand for local file reads, `rg`, git history, and the
project's real test commands. They are not required tools.

## Extraction Operations

### Extract Function
Pull a block of code into a named function.
- **When:** A function does 3+ distinct things
- **Verify:** Call sites produce same results, tests still pass

### Extract Module
Move related functions into a new file.
- **When:** A file has 2+ distinct responsibilities
- **Verify:** All imports updated, no circular deps introduced

### Extract Interface
Create an abstract base/protocol.
- **When:** Multiple implementations share a pattern but aren't formalized
- **Verify:** Existing code works through the interface

## Consolidation Operations

### Merge Duplicates
Combine near-identical functions into one.
- **When:** Two functions differ by < 20% of their logic
- **Verify:** All former call sites use the merged version

### Consolidate Config
Unify scattered config access.
- **When:** Convention scan shows 3+ config patterns
- **Verify:** All config reads go through single path

## Simplification Operations

### Inline Dead Code
Remove unreferenced symbols.
- **When:** `repo_dead_code` flags them AND you've confirmed no dynamic usage
- **Verify:** Tests still pass, no import errors

### Break Circular Dependency
Introduce an intermediary or invert dependency.
- **When:** Dependency graph shows mutual imports
- **Verify:** Both modules import cleanly, no runtime errors

### Flatten Hierarchy
Remove unnecessary inheritance layers.
- **When:** A class hierarchy has single-child nodes
- **Verify:** All isinstance/issubclass checks still work

## Rename Operations

### Rename for Clarity
Change names to match conventions + intent.
- **When:** Convention scan shows inconsistency or names are misleading
- **Verify:** All references updated (search for old name returns 0 hits)

## Ordering Rules

1. Dead code removal first (lowest risk, reduces noise)
2. Renames second (behavior-preserving, improves clarity)
3. Extractions before consolidations (safer to split then merge)
4. Break circular deps before module moves
5. Test deserts get tests before refactoring

## Prescription Output Format

```
## Refactoring Prescription: [target area]

### Diagnosis
[2-3 sentence summary]

### Operations (in recommended order)

#### Step N: [operation name] — Risk: LOW/MEDIUM/HIGH
Target: [file:function/class]
What: [specific description]
Why: [which smell this addresses]
Verify: [how to confirm nothing broke]
Blast radius: [N files affected]
Test coverage: [covered / NOT covered]

### Estimated Effort
- Total operations: N
- Low risk: X | Medium risk: Y | High risk: Z
- Pre-requisite tests needed: N
```
