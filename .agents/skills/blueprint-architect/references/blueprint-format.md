# Blueprint Format Reference

How to parse (and structure) implementation blueprint documents. Blueprints are Markdown with a consistent structure.

---

## Expected Blueprint Structure

### Section 0: Repo Anchors (Current State)
**Look for:** "Where the repo is today", "Current repo state", "Verified anchors", "Existing substrate."

Extract: file paths, function/class names with location, API endpoints, config references. Each anchor is a claim — re-verify against repo.

### Section 1: Target Capabilities (Definition of Done)
**Look for:** "Target capabilities", "Definition of done", "Target behavior", "What we're building."

Extract: each capability, required behavior, hard constraints ("must", "must not", "non-negotiable").

### Section 2: Architecture Overview
**Look for:** "Architecture", "Proposed architecture", "How it fits", "System design."

Extract: new modules/dirs, integration points, data flow.

### Section 3: Detailed File Guidance
**Look for:** "File-level guidance", "New files to add", "Existing files to change."

Extract: file creation list (path → purpose → key contents), modification list (path → what changes → why), code snippets/pseudo-code.

### Section 4: Milestones
**Look for:** "Implementation plan", "Milestones", "Phases", "Step-by-step plan."

Extract: milestone ID/name, objective, ordered steps, success criteria, dependencies.

### Section 5: Success Criteria
**Look for:** "Success criteria", "Acceptance criteria", "Definition of done", "PASS/FAIL criteria."

Extract: each criterion; classify (functional, safety, quality, regression); map to milestone and verifying test.

### Section 6: Test Plan
**Look for:** "Test plan", "Testing", "Verification", "Test files to create."

Extract: test file paths, what each verifies, categories (unit, integration, API, regression).

---

## Blueprint Variants

- **Full:** All sections — fully autonomous implementation.
- **Minimal:** Infer file locations from architecture/conventions; generate test plan from success criteria; note inferred parts.
- **Spec-only:** No milestones/file targets/success criteria — derive from spec and Phase 1; flag plan as inferred.

---

## Key Patterns

- **Checklist:** `- [ ]` = TODO, `- [x]` = done (verify in repo).
- **Paths:** Backtick paths like `app/policy/models.py` — check against repo.
- **Code blocks:** Guidance only; may not match repo conventions.
- **Constraints:** "must"/"MUST" → hard, test; "should" → soft; "may" → optional; "must not" → negative, test NOT possible.
- **Success criteria:** `✅ [criterion]` or `PASS: ... / FAIL: ...` — both testable.
