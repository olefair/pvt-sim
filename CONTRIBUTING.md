# Contributing to PVT-SIM

PVT-SIM is intentionally held to a higher bar than a typical course repo.

This repository is allowed to grow again, but not by accreting duplicate
paths, decorative comments, or unverified fallback layers.

Read these before changing code:

- [README.md](README.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/runtime_surface_standard.md](docs/runtime_surface_standard.md)
- [docs/development.md](docs/development.md)

## Contribution Rules

- Prefer the smallest coherent implementation that fully solves the task.
- Preserve existing behavior unless the change explicitly expands or changes it.
- Do not add side-path implementations that the runtime will not actually use.
- Do not leave "temporary" fallback logic behind without explicit docs and tests.
- Do not add broad refactors, renames, or formatting sweeps unless they are required.
- Keep the app/runtime path faithful to the actual kernel methods being restored.

## Code Style Expectations

- Write direct, readable code with clear control flow.
- Comments should explain invariants, numerical choices, or non-obvious reasoning.
- Do not add comments that merely narrate the next line of code.
- Do not put usage examples, tutorial walkthroughs, or long reference lists in runtime code.
- Remove dead code instead of commenting it out.
- Keep method and model choices explicit and auditable.
- Avoid "just in case" branches unless there is a concrete failure mode they address.
- Keep docstrings short and contractual; move theory and exposition to `docs/`.

## Restoring Removed Functionality

Restoring submission-trimmed functionality is allowed, but each restored slice must:

- be wired into the canonical runtime path, not only added to a library side path
- be documented accurately
- have targeted verification appropriate to the touched surface
- state what is now supported, experimental, or still intentionally excluded

If a feature is not runtime-wired yet, mark it explicitly as experimental or not supported. Do not imply app support ahead of the runtime.

## Pull Requests

Every PR should state:

- what changed
- why it changed
- what verification was run
- what remains intentionally out of scope
- any residual risk or follow-up work

Use the PR template. If a change cannot be explained concisely, the scope is
probably too wide.
