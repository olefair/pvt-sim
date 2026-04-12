# Bubble Point Validation Matrix

This document is the working signoff matrix for the bubble-point module.

Validation is split into three layers:

- authoritative equation-based benchmarks: independent reference solves of the PR fugacity equations
- external data anchors: published vapor-pressure, VLE, or lab data where available
- MI-PVT cross-checks: envelope and graphical comparisons only, never the scalar truth baseline for bubble pressure

## Signoff Criteria

Do not treat the bubble-point module as complete until all of the following are true:

- the production bubble solver matches an independent equation-based reference solve across volatile-oil, black-oil, sour-oil, and multicomponent control regimes
- the same bubble boundary is recovered from low, default, and high pressure guesses for each authoritative reservoir-style case
- the `C1`-`C6` + `C7+` characterization path preserves the bubble boundary through splitting and lumping
- each authoritative bubble case checks both bubble pressure and incipient vapor composition
- at least one negative-path case demonstrates that the solver correctly rejects a non-physical or trivial bubble boundary
- pure-component bubble pressure collapses to the same saturation pressure as dew-point vapor pressure
- heavier-mixture coverage beyond explicit single-carbon-number components is either externally validated or fenced until pseudo-component support exists

## Authoritative Now

The current authoritative layer lives in `tests/validation/test_saturation_equation_benchmarks.py`.

The current characterization-preservation layer lives in `tests/validation/test_plus_fraction_bubble_characterization.py`.

| Case ID | Regime | Authority | What is checked |
| --- | --- | --- | --- |
| `synthetic_c1_c4_bubble_equation` | Internal control binary | Independent equation solve | Bubble pressure and incipient vapor `y` |
| `literature_c1_c3_sage_lacey_bubble_equation` | Literature binary tie-line | Independent equation solve at literature state | Bubble pressure and incipient vapor `y` |
| `reservoir_volatile_oil_a_bubble_equation` | Volatile oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `reservoir_volatile_oil_b_bubble_equation` | Volatile oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `reservoir_black_oil_a_bubble_equation` | Black oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `reservoir_black_oil_b_bubble_equation` | Black oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `reservoir_sour_oil_a_bubble_equation` | Sour oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `reservoir_sour_oil_b_bubble_equation` | Sour oil | Independent equation solve plus guess-robustness check | Bubble pressure and incipient vapor `y` |
| `plus_volatile_oil_characterized_bubble` | Volatile oil with `C7+` | Characterization path preservation check | Split/lump/delump balances plus bubble pressure agreement between unlumped and lumped models |
| `plus_black_oil_characterized_bubble` | Black oil with `C7+` | Characterization path preservation check | Split/lump/delump balances plus bubble pressure agreement between unlumped and lumped models |
| `plus_sour_oil_a_characterized_bubble` | Sour oil with `C7+` | Characterization path preservation check | Split/lump/delump balances plus bubble pressure agreement between unlumped and lumped models |
| `plus_sour_oil_b_characterized_bubble` | Sour oil with `C7+` | Characterization path preservation check | Split/lump/delump balances plus bubble pressure agreement between unlumped and lumped models |
| `co2_rich_high_temperature_no_nontrivial_bubble` | Negative path | Independent equation scan plus production error check | No non-trivial bubble boundary should be certified |
| Pure-component `C1`, `C3`, `C6` at `Tr = 0.7` | Pure-component consistency | Saturation identity | `Pbubble == Pdew` |

These are authoritative for solver correctness because they validate the production bubble solver against the governing equilibrium equations with an independent root-finding path, not against MI-PVT output.

## Default Reservoir-Style Composition Roster

For manual desktop validation and routine workflow signoff, the default bubble-point roster should start with characterized lab-style feeds rather than fully resolved `C7`-`C16` tails. The fully resolved oil cases remain in `tests/validation/test_saturation_equation_benchmarks.py` to isolate solver behavior from characterization, but first-line GUI and end-to-end checks should use the following `C1`-`C6` + `C7+` feeds from `tests/validation/test_plus_fraction_bubble_characterization.py`.

The preferred default list is intentionally majority `C7+`:

1. `plus_volatile_oil_characterized_bubble`
   `T = 360.0 K`, expected lumped `Pb = 114.66643 bar`
   Resolved feed: `N2 0.0021, CO2 0.0187, C1 0.3478, C2 0.0712, C3 0.0934, iC4 0.0302, C4 0.0431, iC5 0.0276, C5 0.0418, C6 0.0574`
   Plus fraction: `C7+ z = 0.2667, MW+ = 119.7876 g/mol, SG+ = 0.82`
2. `plus_black_oil_characterized_bubble`
   `T = 380.0 K`, expected lumped `Pb = 64.24213 bar`
   Resolved feed: `N2 0.0010, CO2 0.0100, H2S 0.0040, C1 0.1800, C2 0.0550, C3 0.0700, iC4 0.0400, C4 0.0500, iC5 0.0420, C5 0.0500, C6 0.0700`
   Plus fraction: `C7+ z = 0.4280, MW+ = 140.1515 g/mol, SG+ = 0.85`
3. `plus_sour_oil_a_characterized_bubble`
   `T = 340.0 K`, expected lumped `Pb = 68.38842 bar`
   Resolved feed: `N2 0.0010, CO2 0.0500, H2S 0.0700, C1 0.2200, C2 0.0600, C3 0.0700, iC4 0.0300, C4 0.0400, iC5 0.0300, C5 0.0400, C6 0.0600`
   Plus fraction: `C7+ z = 0.3990, MW+ = 141.1734 g/mol, SG+ = 0.86`
4. `plus_sour_oil_b_characterized_bubble`
   `T = 330.0 K`, expected lumped `Pb = 52.93491 bar`
   Resolved feed: `N2 0.0010, CO2 0.0350, H2S 0.0900, C1 0.1800, C2 0.0550, C3 0.0650, iC4 0.0300, C4 0.0400, iC5 0.0300, C5 0.0400, C6 0.0650`
   Plus fraction: `C7+ z = 0.4340, MW+ = 142.6216 g/mol, SG+ = 0.87`

When a shorter control set is needed, keep one explicit heavy-end case such as `reservoir_volatile_oil_a_bubble_equation` or `reservoir_black_oil_a_bubble_equation` alongside these `C7+` feeds so solver-only regressions stay distinguishable from characterization regressions.

The desktop/runtime `C7+` auto-characterization path should resolve oil-like bubble feeds onto these validated family defaults rather than falling back to one generic split. The current intended family presets are:

- volatile oil: `split_mw_model = table`, `split_to = C20`, `lumping_groups = 6`
- black oil: `split_mw_model = table`, `split_to = C20`, `lumping_groups = 6`
- sour oil: `split_mw_model = table`, `split_to = C20`, `lumping_groups = 6`

## External Data Still Needed

Equation-based agreement proves the solver is implementing the chosen EOS consistently. It does not prove the EOS or component data are accurate enough for field fluids.

Still needed for full signoff:

- experimental or trusted literature bubble-point anchors for multicomponent volatile oils and black oils
- at least one measured sour-oil bubble-point dataset with component detail sufficient to reproduce the feed
- experimental anchors for `C7+`-characterized oils after splitting/lumping choices are frozen

The structured intake surface for those anchors now lives in:

- `tests/validation/external_data/acquisition_manifest.json`
- `tests/validation/external_data/cases/`
- `tests/validation/external_data/templates/`
- `src/pvtcore/validation/external_corpus.py`

The current executed pure-component external lane lives in:

- `tests/validation/test_external_pure_component_saturation.py`
- `tests/validation/external_data/cases/nist_c1_saturation_batch.json`
- `tests/validation/external_data/cases/nist_c2_saturation_batch.json`
- `tests/validation/external_data/cases/nist_c3_saturation_batch.json`
- `tests/validation/external_data/cases/nist_c4_saturation_batch.json`
- `tests/validation/external_data/cases/nist_c5_saturation_batch.json`
- `tests/validation/external_data/cases/nist_c6_saturation_batch.json`
- `tests/validation/external_data/cases/nist_co2_saturation_batch.json`

The first executed literature tie-line lane now lives in:

- `tests/validation/test_external_literature_vle.py`
- `tests/validation/external_data/cases/thermoml_2015_ch4_c3_tieline_24361k_xch4_04857.json`

## MI-PVT Role

MI-PVT should remain a secondary cross-check for:

- phase-envelope shape
- graphical overlays
- qualitative location of key envelope features

MI-PVT should not be used as the authoritative scalar baseline for:

- bubble-point pressure
- dew-point pressure
- incipient phase composition at saturation

## Next Actions

1. Add external bubble-point anchors for at least one volatile-oil and one black-oil regime.
2. Add external `C7+` bubble anchors so the characterization-preservation cases are tied to lab data, not just internal consistency.
3. Keep the CO2-rich negative-path case in sync with the desktop trace workflow so GUI regressions remain visible.
4. Promote the remaining literature and lab entries from `tests/validation/external_data/acquisition_manifest.json` into ready case files under `tests/validation/external_data/cases/`.
