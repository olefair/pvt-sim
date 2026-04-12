# Runtime Surface Standard

This document defines the minimum acceptable runtime-surface standard for
PVT-SIM. It is intended to be durable across chats, agents, and platforms.

This is a repo contract, not a suggestion.

---

## Purpose

PVT-SIM is a simulator product, not a loose collection of thermodynamic
libraries. Domain-level simulator capabilities that exist in `pvtcore` must
not be left stranded in side paths while the desktop app and runtime execute a
different, narrower, or less rigorous path.

If a user-facing simulator feature exists in this repo, the app runtime must
either:

- expose it and execute it correctly, or
- mark it explicitly as non-runtime / experimental / not yet supported, and
  avoid implying otherwise.

Anything else is an orphaned feature and is not acceptable.

---

## Definitions

### Domain Feature

A simulator-facing feature, method, or workflow, such as:

- a calculation workflow (`PT Flash`, `Bubble Point`, `CCE`, `CVD`, etc.)
- an EOS option
- a characterization method (`Pedersen`, `Katz`, `Lohrenz`, etc.)
- a lumping or delumping method
- a BIP strategy (`zero`, default correlations, `PPR78`, explicit overrides)
- a property model (`LBC` viscosity, parachor IFT)
- a confinement workflow
- a tuning / regression workflow

### Canonical Runtime Path

The single app-facing execution path that takes user input, preserves all
relevant method selections and context, calls the actual computational kernel,
and returns auditable results and artifacts.

There may be many selectable methods, but there must be one canonical runtime
path.

### Orphaned Feature

A domain feature that is present in code and/or canonical docs but is not
actually reachable through the app runtime for the workflows where it is
supposed to matter, or is represented in the GUI without affecting the actual
runtime calculation.

### Internal Helper

A low-level utility, correlation, solver helper, or adapter that exists to
support a canonical runtime path. Internal helpers do not need separate GUI
controls as long as they are actually used by the runtime where intended.

---

## Core Rules

### 1. No Orphaned Domain Features

No domain-level simulator feature may remain in a library side path without a
clear runtime status.

Every such feature must be one of:

- `runtime-wired`
- `explicitly experimental / not app-supported`
- `removed`

“Present in code but not wired” is not an acceptable steady state.

### 2. One Runtime Path, Many Methods

The repo may support multiple characterization or modeling methods. That is
expected.

What is not acceptable is multiple competing runtime preparation paths where
the app uses a narrower or lower-fidelity path than the rest of the repo.

The runtime must have:

- one canonical orchestration path
- method selection carried as explicit input
- faithful dispatch into the chosen kernel method

### 3. GUI Controls Must Be Real Runtime Controls

If the GUI presents a selectable method, parameter matrix, or workflow option,
that selection must affect the actual runtime calculation.

Display-only controls that imply runtime behavior are not acceptable.

### 4. Method Choices Must Be Preserved In Artifacts

Run artifacts must record the actual methods and options used at runtime,
including at least:

- characterization method
- plus-fraction split method
- lumping method
- BIP method / overrides
- EOS selection
- whether outputs are lumped, delumped, or both

### 5. Characterization Context Must Not Be Discarded

If the runtime characterizes, splits, lumps, or otherwise transforms the feed,
the resulting context must remain available through the run.

This includes:

- original feed intent
- split SCN distribution
- lump mapping
- delumping basis
- precomputed BIPs, where applicable

The app must not collapse that context into only `(components, z, kij)` if
later workflows or reporting need the richer state.

### 6. Canonical Docs Must Match Runtime Reality

Canonical docs in `README.md` and `docs/` must not describe simulator support
that the app/runtime does not actually provide, unless the limitation is
spelled out explicitly.

### 7. New Feature Admission Gate

A new domain-level feature should not be treated as “implemented” merely
because there is library code for it.

A feature is only considered implemented when:

- it is reachable through the canonical runtime path for its intended use
- it is surfaced appropriately in the GUI and/or runtime config
- it is documented accurately
- it has verification coverage appropriate to its scope

---

## Mandatory Current Standards

These are explicit standards for the current repo, not future nice-to-haves.

### Characterization Method Surface

If `Pedersen`, `Katz`, and `Lohrenz` are retained as supported
characterization/splitting methods in `pvtcore`, they must be runtime-selectable
and GUI-exposed for the relevant heavy-end workflows.

### Heavy-End Lumping Standard

The canonical runtime heavy-end lumping method is `Whitson`.

`Contiguous` grouping is not acceptable as the steady-state runtime lumping
method for the simulator product. It may remain only as legacy or test code
until removed or demoted explicitly.

### Delumping / Composition Retrieval Standard

If the runtime solves on lumped heavy-end groups, delumping / composition
retrieval is required for user-facing reporting and export wherever detailed
heavy-end output is expected.

### BIP Surface Standard

The runtime BIP strategy must be explicit and auditable.

If the GUI presents BIP controls or methods, those controls must drive the
actual runtime matrix. Otherwise they must be hidden or clearly marked as
non-runtime diagnostics.

---

## Enforcement Guidance

When making runtime, GUI, or architecture changes in this repo:

- do not add a new side-path implementation if the app will not use it
- do not leave a previously implemented domain feature stranded off-runtime
- do not imply app support for a method that is only available via tests, a
  notebook, or a library-only API
- when consolidating duplicate paths, prefer the more rigorous and documented
  method, then retire or explicitly demote the weaker path

