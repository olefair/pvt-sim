# MI-PVT Cross-Check Cases

This folder contains MI-PVT exports used as secondary cross-checks.

Boundary for this repo:

- Use MI-PVT here for PT-flash and graphical or envelope-oriented comparisons.
- Do not use MI-PVT as the authoritative scalar baseline for bubble-point or
  dew-point validation. Saturation correctness is validated separately from the
  governing equations in `tests/validation/test_saturation_equation_benchmarks.py`.

## How to add a case

Create a JSON file under:

`tests/validation/mi_pvt/cases/<case_id>.json`

### Case schema (minimal)

- `case_id` (string)
- `task` (string): `"pt_flash" | "bubble_point" | "dew_point" | "phase_envelope"`
- `temperature` (number K, or {"value":..., "unit":"K"})
- `pressure` (required for pt_flash; optional for bubble/dew legacy artifacts)
  - either number (Pa), or {"value":..., "unit":"atm"|"bar"|"psi"|"Pa"}
- `composition`: the exact MI feed as entered in MI-PVT, list of {"id": "<MI label>", "z": <float>}
- optional `runtime_composition`: the feed the repo should actually execute, when it differs from the MI feed
- optional `runtime_supported`: `true` / `false`
- optional `runtime_skip_reason`: short note explaining why this case is archived-only for now

Important distinction:

- `composition` is allowed to reflect the MI UI exactly, including MI-only heavy bins such as `C7-C12`.
- The automated pytest harness can only execute a case when the repo has an equivalent runtime feed surface.
- If the case is capture-only for now, set:
  - `runtime_supported: false`
  - `runtime_skip_reason: "..."`

Supported runtime labels right now:
`N2`, `H2S`, `CO2`, `C1`, `C2`, `C3`, `iC4`, `nC4`, `iC5`, `nC5`, `C6`,
plus explicit `C7`, `C8`, `C10`, `C12`, `C14`, `C16`-style labels.

Still not executable in this harness without a separate runtime mapping:
- aggregate heavy-lump MI labels like `C7-C12`
- multi-bin MI heavy feeds such as `C13-C18`, `C19-C26`, `C27-C37`, `C38-C85`
- inline pseudo-components unless a future case schema adds explicit pseudo data

### Expected outputs

Put MI outputs in the `expected` object. Examples:

For pt_flash:
- `phase`: "vapor" | "liquid" | "two-phase"  (optional)
- `vapor_fraction`: float (optional)
- `x`: array of liquid composition aligned to input ordering (optional)
- `y`: array of vapor composition aligned to input ordering (optional)

Legacy note:
- Some historical case files may still contain `bubble_point` or `dew_point`
  tasks, but the pytest MI harness skips them on purpose.

For phase envelope:
- `envelope_points`: ordered MI text-table points, each like:
  - `{"temperature": {"value": 230.6659, "unit": "K"}, "pressure": {"value": 5.0, "unit": "atm"}, "marker": null}`
- optional `marker` values:
  - `tmax`
  - `pmax`
  - `crit`
- optional explicit key points:
  - `critical_point`
  - `cricondenbar`
  - `cricondentherm`
- optional explicit branch tables:
  - `bubble_curve`
  - `dew_curve`

If only `envelope_points` are provided, the harness assumes the standard MI
text-output ordering:
- dew branch up to `PMAX`
- then bubble branch back to low temperature

Optional `trace` object for phase-envelope cases:
- `method`: `"fixed_grid"` or `"continuation"` (default `fixed_grid`)
- `temperature_min`
- `temperature_max`
- `n_points`

If `temperature_min` / `temperature_max` are omitted, the harness derives them
from the MI envelope points.

### Tolerances

Optional `tolerances` object. Examples:
- `pressure_pa_atol`: absolute Pa tolerance (default 5e4 Pa ~ 0.5 bar)
- `composition_atol`: absolute mol fraction tolerance (default 1e-3)
- `vapor_fraction_atol`: absolute tolerance (default 1e-3)
- `key_pressure_pa_atol`: phase-envelope key-point pressure tolerance
- `key_temperature_k_atol`: phase-envelope key-point temperature tolerance
- `curve_pressure_pa_atol`: branch-to-branch pressure tolerance
- `curve_point_fraction_min`: minimum fraction of comparable MI branch points
  that must fall within `curve_pressure_pa_atol`

## Notes on MI settings

MI-PVT must be configured to match:
- EOS: Peng-Robinson 1976 (PR)
- Binary interaction parameters (kij): ideally all zero unless explicitly set

Record MI settings in the case file under `mi_settings` if you can.

If a case is only a backlog scaffold, omit `expected` entirely or leave it
empty. The pytest harness will skip it until the MI-PVT outputs are filled in.

If a case is an MI-native heavy-bin artifact that the current runtime cannot
represent honestly, keep the MI `composition`, add the `expected` outputs, and
set `runtime_supported: false`. The harness will archive it cleanly and skip
execution until the runtime feed surface catches up.
