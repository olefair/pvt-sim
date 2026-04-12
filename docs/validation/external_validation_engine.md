# External Validation Engine

This document defines the allowed role of external tools in the repo's
validation stack.

The governing rule is:

- align the simulator first with the methods used in the course and workbook
  materials
- keep the active external validation engine limited to permissive,
  redistributable packages with no strong-copyleft or proprietary obligations
- do not let an external tool quietly replace the repo's own solver authority

## Approved Backends

Only these backends are part of the active validation engine.

### ThermoPack

Primary role:

- external EOS / VLE reference backend

Use it for:

- PT flash
- bubble point
- dew point
- phase envelope
- critical-point and envelope-structure cross-checks

Repo policy:

- Apache-2.0
- approved for active validation use
- acceptable source for selective implementation borrowing when needed

### thermo

Primary role:

- pure-component and general thermodynamic property/data support

Use it for:

- large pure-component property coverage
- light-component/property sanity checks
- supplementary property/bootstrap work

Repo policy:

- MIT
- approved for active validation use
- acceptable source for selective implementation borrowing when needed

## Explicitly Excluded from the Active Engine

These tools may be technically useful, but they are not part of the supported
validation engine under the repo's current licensing policy.

### Prode Properties

- proprietary/commercial
- excluded from the active engine
- do not copy implementation from it into the repo

### DWSIM

- GPL-3.0
- excluded from the active engine
- do not copy implementation from it into the repo

### PyReservoir

- license terms need explicit review before adoption
- excluded from the active engine until the license position is unambiguous

## Coursework-First Order

When deciding what to implement next, use this order:

1. equation-based and workbook-derived checks already inside the repo
2. ThermoPack for external EOS/VLE comparison
3. `thermo` for broader property-data support

This keeps the repo aligned with class methods first, and only then expands
the external validation surface using permissive tools only.
