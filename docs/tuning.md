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

Dedicated TBP experiment workflows are not implemented in this repo. The empty `src/pvtcore/experiments/tbp.py` stub was removed rather than kept as a phantom feature.

Phase-1 support does exist in the schema-driven `pvtcore` fluid-definition path: `fluid.plus_fraction.tbp_data.cuts` can be consumed by `load_fluid_definition(...)` plus `characterize_from_schema(...)` to derive aggregate plus-fraction inputs for the existing characterization workflow. That support does not extend `pvtcore.tuning`, `pvtcore.experiments`, or `pvtapp` with a standalone TBP calculation mode.

## Example

Regression inputs are built from `ExperimentalDataSet` and `ExperimentalPoint` objects. Use the supported `DataType` values above, then attach the dataset to `EOSRegressor` and call `fit()`.
