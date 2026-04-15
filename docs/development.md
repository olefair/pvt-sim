# PVT-SIM Development Contract

This document is the canonical home for the repo's current development-facing
context: stack, package surface, coding conventions, error-handling
expectations, and verification habits.

Durable simulator information belongs here and in the rest of `docs/`, not in
repo-root agent orientation files.

---

## Canonical Doc Map

Use the docs set as a whole:

- `README.md` for install and launch surfaces
- `docs/architecture.md` for system/module layout and data flow
- `docs/runtime_surface_standard.md` for the app/runtime parity contract
- `docs/technical_notes.md` for thermodynamic equations and dependency ordering
- `docs/numerical_methods.md` for solver policy and convergence rules
- `docs/input_schema.md` for fluid/config data contracts
- `docs/units.md` for internal units and conversion policy
- `docs/validation_plan.md` for validation strategy and reference targets

---

## Current Repo Surface

The live package surface is split into two layers:

- `src/pvtcore/`: computational kernel with no GUI dependencies
- `src/pvtapp/`: desktop GUI, CLI entrypoints, schemas, run orchestration, and
  result presentation

Current `pvtcore` module groups present in the repo:

- `characterization`
- `confinement`
- `core`
- `correlations`
- `envelope`
- `eos`
- `experiments`
- `flash`
- `io`
- `models`
- `properties`
- `stability`
- `tuning`
- `validation`

Current `pvtapp` surface present in the repo:

- desktop GUI widgets in `src/pvtapp/widgets/`
- CLI entrypoints in `src/pvtapp/cli.py`
- runtime schemas and orchestration in `src/pvtapp/schemas.py` and
  `src/pvtapp/job_runner.py`

Current workflow surface exposed in the GUI/runtime, verified from
`src/pvtapp/capabilities.py`:

- `PT Flash`
- `Stability Analysis`
- `Bubble Point`
- `Dew Point`
- `Phase Envelope`
- `CCE`
- `Differential Liberation`
- `CVD`
- `Separator`

Current runtime EOS surface:

- implemented and exposed: `Peng-Robinson (1976)`, `Peng-Robinson (1978)`, `SRK`

---

## Runtime Surface Parity

The canonical runtime-surface contract lives in
`docs/runtime_surface_standard.md`.

Short version:

- Domain-level simulator features must not remain orphaned in side-library
  paths while the app/runtime uses a narrower or different method.
- The desktop app should orchestrate the actual supported simulator methods,
  not shadow them with reduced alternatives.
- If a feature or method is retained as supported in `pvtcore`, it must either
  be wired into the canonical runtime path or be documented explicitly as
  experimental / not app-supported.

---

## Technical Stack

Verified from `pyproject.toml`:

- Python `>=3.10`
- packaging/build: `setuptools`, `wheel`
- core runtime dependencies: `numpy`, `pydantic`
- GUI/runtime extras: `PySide6`, `matplotlib`, `pyqtgraph`
- extended numerical/runtime extra: `scipy`
- developer tooling: `pytest`, `pytest-cov`, `black`, `flake8`, `mypy`,
  `pylint`, `build`, `wheel`
- approved permissive validation backends in the dev surface: `thermo`,
  `thermopack`
- docs extra: `sphinx`, `sphinx-rtd-theme`

Install surfaces currently defined:

- base: `pip install -e .`
- GUI-only: `pip install -e .[gui]`
- full desktop/runtime: `pip install -e .[full]`
- development: `pip install -e .[dev]`
- full desktop + developer/validation surface: `pip install -e .[full,dev]`
- docs: `pip install -e .[docs]`

---

## Coding Conventions

These conventions are grounded in the current repo and should be preserved:

- Use 4-space indentation.
- Keep `pvtcore` free of GUI dependencies.
- Add type hints on public functions, dataclasses, and schema-facing APIs.
- Prefer `from __future__ import annotations` in new Python modules to match the
  active codebase.
- Keep units explicit in docstrings and APIs for physical quantities.
- Keep unit conversions at I/O boundaries; solver code should operate on
  canonical internal units from `docs/units.md`.
- Use concise, informative docstrings for public behavior and non-obvious
  numerical logic. The current repo is mixed, but active modules already rely
  heavily on function/class docstrings.
- Prefer small, auditable edits over broad refactors unless a larger change is
  required for correctness.

Formatting and static checks are part of the intended developer surface because
`black`, `flake8`, `mypy`, and `pylint` are already wired as dev dependencies.

---

## Error Handling Contract

The repo currently uses a two-layer error model:

- `pvtcore` raises domain-specific exceptions from `pvtcore.core.errors`, such
  as `ConvergenceError`, `ValidationError`, `PhaseError`, `EOSError`,
  `PropertyError`, and related `PVTError` subclasses.
- `pvtapp` and schema-validation boundaries commonly raise `ValueError`,
  `FileNotFoundError`, or Pydantic validation errors when user/config input is
  incomplete or invalid before computation begins.

Guidelines:

- Use `pvtcore` custom exceptions for thermodynamic, numerical, and data-domain
  failures inside the kernel.
- Use boundary-validation errors for malformed UI/CLI/config input before it
  enters the kernel.
- Do not silently coerce physically invalid inputs into a run.
- Surface enough context in error messages for the failed variable, phase,
  component, or configuration key to be identifiable.

---

## Verification Expectations

Validation has two different roles in this repo and they should not be
confused:

- automated tests protect behavior and catch regressions
- thermodynamic validation requires external references, literature, commercial
  comparisons, and physically credible manual case review

Current verification surfaces:

- `python .\scripts\validate_modules.py`
- `pytest` for the default high-signal kernel/runtime surface
- `pytest --run-gui-contracts` for optional desktop layout/style contract checks
- `pvtsim validate <config>`
- manual CLI/GUI validation against literature data, MI PVT, lab reports, and
  physical invariants

`pytest` is necessary but not sufficient proof of thermodynamic correctness. Use
the validation plan and external reference cases when judging whether the
simulator is actually right.

The default `pytest` path intentionally deselects tests marked `gui_contract`.
Those checks cover desktop layout, styling, zoom, and other presentation
contracts that are useful when changing the GUI shell but are lower signal than
kernel correctness and runtime-surface wiring for routine verification.
