# Tuning

This document records the supported EOS regression surface in `pvtcore.tuning`.

## Supported Data Types

The regression engine currently implements these `DataType` values from [`src/pvtcore/tuning/objectives.py`](../src/pvtcore/tuning/objectives.py):

- `SATURATION_PRESSURE`
- `LIQUID_DENSITY`
- `VAPOR_DENSITY`
- `VAPOR_FRACTION`
- `Z_FACTOR`

These are the only data types accepted by `EOSRegressor._model_function` today.

## Unsupported Data Types

The following `DataType` values are defined in the enum but are not implemented yet in the regression model path:

- `LIQUID_COMPOSITION`
- `VAPOR_COMPOSITION`
- `RELATIVE_VOLUME`
- `LIQUID_DROPOUT`
- `GOR`
- `BO`

Requests using these types should fail explicitly with a message that names the unsupported type and lists the supported set.

## TBP

The repo now has a bounded standalone TBP assay kernel in `src/pvtcore/experiments/tbp.py`.

Bounded support now exists in two forms:

- `fluid.plus_fraction.tbp_data.cuts` can be consumed by `load_fluid_definition(...)` plus `characterize_from_schema(...)` to derive aggregate plus-fraction inputs for the existing characterization workflow.
- Pedersen plus-fraction splitting now also supports `solve_AB_from: fit_to_tbp`, allowing TBP cuts to constrain the actual heavy-end split used by the runtime characterization path.
- `pvtapp` exposes a standalone desktop-plus-runtime TBP run mode through `CalculationType.TBP`, `RunConfig(calculation_type="tbp", tbp_config={...})`, and `run_calculation(...)`, with saved artifact and result rendering support.
- `pvtapp` plus-fraction runtime configs now also admit optional `tbp_cuts` plus Pedersen `fit_to_tbp` selection for non-standalone thermo runs.
- TBP run artifacts now preserve a derived aggregate heavy-end bridge context so the runtime-visible `z+` / `MW+` intent remains auditable outside the standalone assay screen.
- `RunResult` artifacts now also preserve a reusable heavy-end runtime characterization package whenever plus-fraction preparation occurs. That package records the SCN split, Pedersen fit metadata, runtime component basis, and, for lumped runs, the explicit lumping method plus the lump membership and delumping weights that the runtime actually used.
- The current TBP slice now also admits interval/gapped cuts and optional/estimated boiling-point endpoints in the standalone assay workflow.

This does **not** yet mean full-spectrum TBP characterization maturity. The runtime-backed piece is still a bounded Pedersen `fit_to_tbp` path; the standalone TBP desktop support is still a cut-table assay workflow, but its result artifacts now preserve the reusable runtime characterization package instead of only aggregate `C<n>+` values. The default heavy-end runtime lumping path is now `Whitson`, while broader downstream TBP-specific characterization / validation work still remains.

## Example

Regression inputs are built from `ExperimentalDataSet` and `ExperimentalPoint` objects. Use the supported `DataType` values above, then attach the dataset to `EOSRegressor` and call `fit()`.
