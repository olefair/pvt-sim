# ThermoPack Live Validation Cases

This folder contains optional live comparison cases for a ThermoPack-backed
validation bridge.

Boundary:

- This lane is validation-only and never participates in the desktop or CLI
  runtime solver path.
- It is skipped unless both conditions are true:
  - at least one case file exists under `tests/validation/thermopack/cases/`
  - a bridge implementing `pvtcore.validation.thermopack_bridge.ThermoPackValidationBackend`
    can be loaded

## Enablement

Either:

- install `thermopack` into the current Python environment, or
- set `PVTSIM_THERMOPACK_BRIDGE=package.module:callable`

The callable must return an object implementing the normalized bridge protocol
defined in:

`src/pvtcore/validation/thermopack_bridge.py`

If `PVTSIM_THERMOPACK_BRIDGE` is not set, the loader will try the native
ThermoPack Python API.

## Case Schema

Create JSON files under:

`tests/validation/thermopack/cases/<case_id>.json`

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
- `thermopack_options`
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
shared by the validation layer:

- `NormalizedFlashResult`
- `NormalizedSaturationResult`
- `NormalizedEnvelopeResult`

That keeps ThermoPack-specific logic isolated from the repo test logic.
