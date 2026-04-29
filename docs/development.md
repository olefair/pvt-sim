# Development Standard

This document defines the engineering bar for PVT-SIM development.

It exists to keep the codebase from turning into comment-heavy, duplicated,
poorly-scoped code.

This is a repo standard, not a suggestion.

---

## 1. Purpose

PVT-SIM must not become:

- a dumping ground for half-wired feature branches
- a collection of mutually inconsistent fallback paths
- transcript-like narration of every line of code
- a broad refactor target every time one workflow changes

The goal is:

- explicit method choices
- a canonical runtime path
- auditable feature restoration
- targeted verification
- readable, compact implementation

---

## 2. Core Development Rules

### 2.1 Smallest Coherent Change

Implement the smallest change that fully solves the problem.

Do not widen scope just because related code is nearby.

### 2.2 No Duplicate Runtime Paths

If a method or workflow is restored, restore it through the canonical runtime
path.

Do not create a second competing path for the same user-facing behavior unless
there is an explicit architectural reason and the distinction is documented.

### 2.3 No Ghost Fallbacks

Fallbacks are allowed only when they handle a known, real failure mode.

A fallback must answer all of the following:

- What concrete failure does it handle?
- Why is the primary path still preferred?
- How is the fallback verified?
- How is it documented in code or docs?

If those answers are weak, do not add the fallback.

### 2.4 No Decorative Complexity

Do not add abstraction, indirection, helper layers, or configuration switches
unless they clearly reduce real complexity or preserve method fidelity.

### 2.5 Runtime Truth Over Library Presence

Library-only code does not count as simulator support.

A feature is only "implemented" when it is:

- reachable through the intended runtime path
- reflected accurately in docs and UI/runtime config
- covered by verification appropriate to its scope

This rule is strict for restored functionality.

---

## 3. Style Conventions

### 3.1 General Style

- Prefer straightforward control flow over clever compression.
- Keep functions focused and bounded.
- Make important method choices explicit rather than implicit.
- Use names that match the thermodynamic or runtime meaning of the value.
- Keep runtime modules compact.
- If a block needs a long explanation to be tolerable, simplify the block.

### 3.2 Comments

Comments should be rare and high value.

Good comments:

- explain a numerical invariant
- explain a non-obvious algorithmic choice
- explain why a branch exists
- note a method limitation or standard reference

Bad comments:

- repeat what the code already says
- narrate assignments or loops
- leave stale TODO prose without ownership or context
- explain code that should instead be simplified

Do not use comments as decoration.

### 3.3 No Tutorial Prose in Runtime Code

Runtime modules are not lecture notes.

Do not put the following inside solver, runtime, or kernel code unless there is
a narrow, concrete reason:

- example blocks
- tutorial walkthroughs
- numbered step-by-step algorithm essays
- long references sections
- prose that explains background theory better suited for `docs/`

If explanation is needed:

- put the method contract in the docstring
- put the theory and references in `docs/`
- put usage examples in tests or user docs

### 3.4 Docstrings

Docstrings should describe contract, intent, and important caveats.

They should be short by default.

Rules:

- module docstrings: brief purpose only
- public function docstrings: contract, key caveat, and units if needed
- private helper docstrings: only when the helper is genuinely non-obvious
- no `Example:` sections in runtime code
- no `References:` sections in routine runtime code
- no arg/return boilerplate when the signature and types already say it

If a function needs a long docstring to be understandable, the code shape is a
problem.

### 3.5 Error Handling

- Fail clearly on invalid states.
- Do not swallow errors just to keep a workflow moving.
- Prefer explicit exceptions over silent fallback behavior.
- Include enough context in errors to diagnose the actual failure.

### 3.6 Configuration and Flags

- New flags must correspond to real behavioral choices.
- Remove dead or misleading configuration instead of keeping it for appearance.
- If the GUI or runtime config exposes a method, that method must affect the calculation.

---

## 4. Feature Restoration Policy

The repo may regain functionality that was trimmed for submission. That work
must be deliberate.

### 4.1 Restore by Slice

Restore one coherent capability slice at a time, for example:

- one characterization method admission
- one runtime wiring gap
- one experiment workflow
- one reporting/export surface tied to a restored runtime method

Do not reopen broad surfaces all at once.

### 4.2 Preserve Method Fidelity

When restoring functionality:

- keep equations, units, and solver rules aligned with canonical docs
- preserve actual method selections through runtime artifacts
- avoid silently substituting a narrower method for a richer one

### 4.3 Experimental Features

If a restored feature is not yet ready for the normal runtime surface:

- label it explicitly as experimental or not app-supported
- document the limitation plainly
- do not imply parity with wired runtime features

### 4.4 Documentation Sync

Whenever capability scope changes, update docs that describe simulator support.

At minimum, review:

- `README.md`
- `docs/runtime_surface_standard.md`
- `docs/technical_notes.md`
- any workflow-specific doc affected by the change

---

## 5. Verification Rules

### 5.1 Targeted Verification First

Run the smallest relevant verification that demonstrates the touched behavior.

Examples:

- unit tests for a restored solver path
- runtime contract tests for a GUI/runtime wiring fix
- a narrow experiment regression for a restored lab workflow

### 5.2 Do Not Claim More Than Was Verified

If only a targeted subset was tested, say so plainly.

Do not imply full-surface validation from one passing narrow test.

### 5.3 Verification Is Part of the Change

A feature restoration is incomplete if the repo has no realistic way to check
that the restored path still works.

---

## 6. Review Expectations

Every substantive change should be reviewable in terms of:

- scope
- method fidelity
- runtime impact
- verification
- residual risk

Reviewers should push back on:

- comment bloat
- docstring bloat
- tutorial prose inside runtime code
- example blocks inside solver code
- references dumped into implementation files
- large unfocused rewrites
- duplicate paths
- speculative fallback ladders
- UI/runtime mismatches
- documentation drift

---

## 7. Practical Heuristics

Before opening or merging a change, ask:

1. Is this the smallest coherent implementation?
2. Did I add a real capability, or just more code?
3. Is the runtime path clearer, or more fragmented?
4. Are any comments pulling weight, or just occupying space?
5. If this were the pattern for the next ten changes, would the repo get better or worse?

If the answer to the last question is "worse," rework the change before landing it.

---

## 8. Where These Rules Live

Keep durable standards in durable files.

### 8.1 Permanent Repo Standards

Use these files for rules that should still be true a month from now:

- `AGENTS.md` for repo execution boundaries and controller/lane rules
- `CONTRIBUTING.md` for contributor-facing expectations
- `docs/development.md` for engineering and restoration standards
- `docs/runtime_surface_standard.md` for app/runtime parity rules
- `docs/technical_notes.md` and `docs/numerical_methods.md` for method truth

Do not let permanent standards live only in chat messages, PR comments, or
issue threads.

### 8.2 Temporary Lane Briefs

Use lane prompts for temporary scoped restoration work:

- place reusable lane prompts under `.agents/`
- record active lane ownership and touched surfaces in `PVTSIM_DEPENDENCY_MAP.md`
- keep lane prompts narrow and slice-specific

Lane prompts should tell a worker:

- exactly what capability slice it owns
- which repo surfaces it may and may not touch
- which docs define the method contract
- what verification is required before closeout

Do not bury repo-wide coding standards inside one lane prompt. Put the durable
rule in the durable doc, then have the prompt point back to it.
