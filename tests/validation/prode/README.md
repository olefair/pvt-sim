# Prode Live Validation Cases

This folder contains optional live comparison cases for a Prode-backed
validation bridge.

Boundary:

- This lane is **validation-only** and never participates in the desktop or
  CLI runtime solver path.
- It is skipped unless both conditions are true:
  - at least one case file exists under `tests/validation/prode/cases/`
  - a bridge implementing `pvtcore.validation.prode_bridge.ProdeValidationBackend`
    can be loaded

## Enablement

Set the environment variable:

`PVTSIM_PRODE_BRIDGE=package.module:callable`

The callable must return an object implementing the normalized bridge protocol
defined in:

`src/pvtcore/validation/prode_bridge.py`

If `PVTSIM_PRODE_BRIDGE` is not set, the loader will try a few common Prode
module names, but the explicit bridge path is the recommended path because the
vendor Python surface is installation-specific.

## Case Schema

Create JSON files under:

`tests/validation/prode/cases/<case_id>.json`

Minimal fields:

- `case_id`
- `task`: `"pt_flash" | "bubble_point" | "dew_point" | "phase_envelope"`
- `temperature`
- `pressure` for `pt_flash`
- `composition`: list of `{"id": "<component id>", "z": <float>}`

Optional fields:

- `trace` for phase-envelope comparisons
  - `method`: `"fixed_grid"` or `"continuation"`
  - `temperature_min`
  - `temperature_max`
  - `n_points`
- `prode_options`
  - freeform options passed through to the bridge
- `tolerances`
  - `pressure_pa_atol`
  - `composition_atol`
  - `key_pressure_pa_atol`
  - `key_temperature_k_atol`
  - `curve_pressure_pa_atol`
  - `curve_point_fraction_min`

## What the bridge should normalize

The bridge should convert vendor-specific outputs into the normalized dataclasses
from `src/pvtcore/validation/prode_bridge.py`:

- `NormalizedFlashResult`
- `NormalizedSaturationResult`
- `NormalizedEnvelopeResult`

That keeps the vendor-specific logic isolated from the repo test logic.
