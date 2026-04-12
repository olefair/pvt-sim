# Dew Point Validation Matrix

This document is the working signoff matrix for the dew-point module.

Validation is split into three layers:

- authoritative equation-based benchmarks: independent reference solves of the PR fugacity equations
- external data anchors: published vapor-pressure, VLE, or lab data where available
- MI-PVT cross-checks: envelope and graphical comparisons only, never the scalar truth baseline for dew pressure

## Signoff Criteria

Do not treat the dew-point module as complete until all of the following are true:

- the production dew solver matches an independent equation-based reference solve across lean, dry-gas, gas-condensate, CO2-rich, and multicomponent regimes
- the same dew boundary is recovered from low, default, and high pressure guesses for each authoritative reservoir-style case
- the `C1`-`C6` + `C7+` characterization path preserves the dew boundary when the declared split range, MW model, and lumping groups are held fixed
- each authoritative dew case checks both dew pressure and incipient liquid composition
- at least one negative-path case demonstrates that the solver correctly rejects a non-physical or trivial dew boundary
- pure-component dew pressure collapses to the same saturation pressure as bubble-point vapor pressure
- richer condensate cases are validated against external data or explicitly fenced out of scope until heavy-component support exists

## Authoritative Now

The current authoritative layer lives in `tests/validation/test_saturation_equation_benchmarks.py`.

The current characterization-preservation layer lives in `tests/validation/test_plus_fraction_dew_characterization.py`.

| Case ID | Regime | Authority | What is checked |
| --- | --- | --- | --- |
| `synthetic_c1_c4_dew_equation` | Internal control binary | Independent equation solve | Dew pressure and incipient liquid `x` |
| `literature_c1_c3_sage_lacey_dew_equation` | Lean hydrocarbon gas | Independent equation solve at literature tie-line state | Dew pressure and incipient liquid `x` |
| `literature_co2_c3_reamer_sage_dew_equation` | CO2-rich binary gas | Independent equation solve at literature tie-line state | Dew pressure and incipient liquid `x` |
| `multicomponent_co2_rich_dew_equation` | Multicomponent CO2-rich gas | Independent equation solve | Dew pressure and incipient liquid `x` |
| `reservoir_dry_gas_a_dew_equation` | Dry gas | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `reservoir_dry_gas_b_dew_equation` | Dry gas with acid gas | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `reservoir_gas_condensate_a_dew_equation` | Gas condensate | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `reservoir_gas_condensate_b_dew_equation` | Sour gas condensate | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `reservoir_co2_rich_gas_a_dew_equation` | CO2-rich gas | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `reservoir_co2_rich_gas_b_dew_equation` | CO2-rich sour gas | Independent equation solve plus guess-robustness check | Dew pressure and incipient liquid `x` |
| `plus_dry_gas_a_characterized_dew` | Dry gas with `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `plus_dry_gas_b_characterized_dew` | Dry gas with acid gas and `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `plus_gas_condensate_a_characterized_dew` | Gas condensate with `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `plus_gas_condensate_b_characterized_dew` | Sour gas condensate with `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `plus_co2_rich_gas_a_characterized_dew` | CO2-rich gas with `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `plus_co2_rich_gas_b_characterized_dew` | CO2-rich sour gas with `C7+` | Characterization path preservation check | Split/lump/delump balances plus lumped dew pressure and incipient liquid agreement versus the explicit dew reference |
| `c1_c4_high_temperature_no_nontrivial_dew` | Negative path | Independent equation scan plus production error check | No non-trivial dew boundary should be certified |
| Pure-component `C1`, `C3`, `C6` at `Tr = 0.7` | Pure-component consistency | Saturation identity | `Pdew == Pbubble` |

These are authoritative for solver correctness because they validate the production dew solver against the governing equilibrium equations with an independent root-finding path, not against MI-PVT output.

## Default Reservoir-Style Composition Roster

For manual desktop validation and routine workflow signoff, the default dew-point roster should include characterized lab-style gas feeds rather than only fully resolved heavy tails. The fully resolved gas cases remain in `tests/validation/test_saturation_equation_benchmarks.py` to isolate solver behavior from characterization. First-line GUI and end-to-end checks should include the following `C1`-`C6` + `C7+` feeds from `tests/validation/test_plus_fraction_dew_characterization.py`.

These settings are part of the validated input, not cosmetic options. `max_carbon_number`, `split_mw_model`, and `lumping_n_groups` materially affect the dew boundary for light plus fractions.

1. `plus_dry_gas_a_characterized_dew`
   `T = 260.0 K`, `split_mw_model = table`, `split_to = C11`, `lumping_groups = 4`, expected lumped `Pdew = 0.04606 bar`
   Resolved feed: `N2 0.010000, CO2 0.015000, C1 0.820000, C2 0.070000, C3 0.035000, iC4 0.012000, C4 0.010000, iC5 0.008000, C5 0.007000, C6 0.005000`
   Plus fraction: `C7+ z = 0.008000, MW+ = 115.981825 g/mol, SG+ = 0.744625`
2. `plus_dry_gas_b_characterized_dew`
   `T = 280.0 K`, `split_mw_model = table`, `split_to = C11`, `lumping_groups = 4`, expected lumped `Pdew = 0.17075 bar`
   Resolved feed: `N2 0.012000, CO2 0.045000, H2S 0.003000, C1 0.760000, C2 0.080000, C3 0.045000, iC4 0.012000, C4 0.012000, iC5 0.008000, C5 0.007000, C6 0.006000`
   Plus fraction: `C7+ z = 0.010000, MW+ = 117.033820 g/mol, SG+ = 0.745700`
3. `plus_gas_condensate_a_characterized_dew`
   `T = 320.0 K`, `split_mw_model = paraffin`, `split_to = C18`, `lumping_groups = 2`, expected lumped `Pdew = 0.03906 bar`
   Resolved feed: `N2 0.006000, CO2 0.025000, C1 0.640000, C2 0.110000, C3 0.075000, iC4 0.025000, C4 0.025000, iC5 0.018000, C5 0.016000, C6 0.014000`
   Plus fraction: `C7+ z = 0.046000, MW+ = 128.255122 g/mol, SG+ = 0.757130`
4. `plus_gas_condensate_b_characterized_dew`
   `T = 330.0 K`, `split_mw_model = table`, `split_to = C17`, `lumping_groups = 2`, expected lumped `Pdew = 0.05152 bar`
   Resolved feed: `N2 0.004000, CO2 0.018000, H2S 0.008000, C1 0.580000, C2 0.120000, C3 0.085000, iC4 0.030000, C4 0.028000, iC5 0.020000, C5 0.019000, C6 0.018000`
   Plus fraction: `C7+ z = 0.070000, MW+ = 130.659681 g/mol, SG+ = 0.760300`
5. `plus_co2_rich_gas_a_characterized_dew`
   `T = 290.0 K`, `split_mw_model = paraffin`, `split_to = C11`, `lumping_groups = 4`, expected lumped `Pdew = 0.16367 bar`
   Resolved feed: `N2 0.008163, CO2 0.469388, H2S 0.010204, C1 0.295918, C2 0.071429, C3 0.045918, iC4 0.020408, C4 0.018367, iC5 0.012245, C5 0.012245, C6 0.011224`
   Plus fraction: `C7+ z = 0.024490, MW+ = 115.397383 g/mol, SG+ = 0.743667`
6. `plus_co2_rich_gas_b_characterized_dew`
   `T = 300.0 K`, `split_mw_model = paraffin`, `split_to = C11`, `lumping_groups = 3`, expected lumped `Pdew = 0.56669 bar`
   Resolved feed: `N2 0.010000, CO2 0.360000, H2S 0.030000, C1 0.370000, C2 0.080000, C3 0.055000, iC4 0.020000, C4 0.020000, iC5 0.013000, C5 0.013000, C6 0.011000`
   Plus fraction: `C7+ z = 0.018000, MW+ = 111.890733 g/mol, SG+ = 0.739000`

The desktop/runtime `C7+` auto-characterization path should resolve gas-like dew feeds onto these validated family defaults rather than falling back to one generic split. The current intended family presets are:

- dry gas: `split_mw_model = table`, `split_to = C11`, `lumping_groups = 4`
- CO2-rich / acid gas: `split_mw_model = paraffin`, `split_to = C11`, `lumping_groups = 4`
- gas condensate: `split_mw_model = paraffin`, `split_to = C18`, `lumping_groups = 2`

## External Data Still Needed

Equation-based agreement proves the solver is implementing the chosen EOS consistently. It does not prove the EOS or component data are accurate enough for real fluids.

Still needed for full signoff:

- richer condensate dew references with experimental or trusted literature data
- at least one external no-dew or near-critical case with enough detail to distinguish `no_saturation` from a trivial critical-locus collapse
- external lab anchors for the characterized `C1`-`C6` + `C7+` dew roster so the selected split/lump settings are tied to measured data

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

The first promoted literature tie-line anchor is now available under:

- `tests/validation/external_data/cases/thermoml_2015_ch4_c3_tieline_24361k_xch4_04857.json`

## MI-PVT Role

MI-PVT should remain a secondary cross-check for:

- phase-envelope shape
- graphical overlays
- qualitative location of key envelope features

MI-PVT should not be used as the authoritative scalar baseline for:

- dew-point pressure
- bubble-point pressure
- incipient phase composition at saturation

## Next Actions

1. Add external experimental or literature dew anchors for at least one richer condensate regime.
2. Add external lab or literature anchors for the current characterized `C1`-`C6` + `C7+` dew roster, especially the gas-condensate and CO2-rich settings.
3. Add at least one measured near-critical dew dataset to separate EOS error from boundary-detection error.
4. Promote the remaining literature and lab entries from `tests/validation/external_data/acquisition_manifest.json` into ready case files under `tests/validation/external_data/cases/`.
