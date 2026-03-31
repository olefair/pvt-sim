# Structural Analysis Protocol

Phase 1: Structural Inventory — detailed steps.

---

## Step 1: Full Inventory

Build the full inventory directly from the repo. Use `rg --files`, extension
counts, directory listings, and representative file reads.

**Look for:** Dominant language (test framework, import parsing, naming); directory patterns (app/, src/, lib/, tests/, scripts/, config/); unexpected languages (e.g. stray .js in a Python repo).

## Step 2: Directory Tree

Walk the directory tree directly.

**Look for:** Depth (deep nesting >4 levels); naming (app/api/, app/models/ → layered; features/auth/ → domain-driven); test organization (co-located vs tests/); config locations (.env, config/, settings/).

## Step 3: Large Files

Files > 500 lines or > 20KB: may be god files, high impact, harder to reason about. Record for Phase 2 risk assessment.

## Step 4: Entry Points

Where execution starts: Python (`if __name__ == "__main__"`, uvicorn.run(), FastAPI()); PowerShell (pete.ps1, param() scripts); JavaScript (package.json main/scripts, index.js). These are dependency roots.

## Step 5: Inventory Summary

Format:

```
Inventory Summary:
- Total files: N
- Languages: Python (X files, Y KB), ...
- Structure: [layered|domain-driven|flat|monolith]
- Test strategy: [co-located|separated|mixed]
- Entry points: [list]
- Large files (>500 lines): [list]
- Config locations: [list]
```

This feeds every subsequent phase.
