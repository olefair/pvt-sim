# Blueprint Format Reference

How to parse implementation blueprint documents. Blueprints are Markdown files with a specific structure.

---

## Expected Blueprint Structure

### Section 0: Repo Anchors (Current State)
**Look for**: "Where the repo is today", "Current repo state", "Verified anchors", "Existing substrate."

- Extract every file path, function/class with location, API endpoint, config reference.
- Each anchor is a claim — re-verify against the actual repo.

### Section 1: Target Capabilities (Definition of Done)
**Look for**: "Target capabilities", "Definition of done", "Target behavior", "What we're building."

- Extract each capability; identify required behavior; note hard constraints ("must", "must not", "non-negotiable").

### Section 2: Architecture Overview
**Look for**: "Architecture", "Proposed architecture", "How it fits", "System design."

- Extract new modules/dirs, integration points (existing files that change), data flow.

### Section 3: Detailed File Guidance
**Look for**: "File-level guidance", "Detailed blueprints", "New files to add", "Existing files to change."

- File creation list: path → purpose → key contents.
- File modification list: path → what changes → why.
- Extract code snippets or pseudo-code.

### Section 4: Milestones
**Look for**: "Implementation plan", "Milestones", "Phases", "Step-by-step plan."

- Extract: milestone ID/name, objective, ordered steps, success criteria, dependencies.

### Section 5: Success Criteria
**Look for**: "Success criteria", "Acceptance criteria", "Definition of done", "PASS/FAIL criteria."

- Extract each criterion; classify (functional, safety, quality, regression); map to milestone and verifying test.

### Section 6: Test Plan
**Look for**: "Test plan", "Testing", "Verification", "Test files to create."

- Extract test file paths, what each test verifies, categories (unit, integration, API, regression).

---

## Blueprint Variants

- **Full blueprint**: All sections — implementation can be fully autonomous.
- **Minimal**: Missing file guidance or test plan — infer from architecture and conventions; generate test plan from success criteria; note what was inferred.
- **Spec-only**: No milestones/file targets/success criteria — treat as spec; derive milestones, file targets, and success criteria from spec and Phase 1; flag that the implementation plan was inferred.

---

## Key Patterns to Extract

- **Checklist**: `- [ ]` = TODO, `- [x]` = done (verify in repo).
- **Paths**: Backtick-quoted paths like `app/policy/models.py` — check against repo.
- **Code blocks**: Use as guidance, not copy-paste (may not match repo conventions).
- **Constraints**: "must" / "MUST" → hard, must test; "should" → soft; "may" → optional; "must not" → negative constraint, test that it's NOT possible.
- **Success criteria**: Often `✅ [criterion]` or `PASS: ... / FAIL: ...` — both are testable.
