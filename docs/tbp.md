# TBP Status

Dedicated TBP workflows are not implemented in this repo today.

Current status:

- Phase 1 support exists in the schema-driven `pvtcore` fluid-definition path only.
- `fluid.plus_fraction.tbp_data.cuts` can be used by `load_fluid_definition(...)` + `characterize_from_schema(...)` to derive aggregate plus-fraction inputs (`z_plus` and `mw_plus_g_per_mol`) for the existing characterization pipeline.
- There is no supported `pvtcore.experiments.tbp` module.
- There is no supported `pvtapp` calculation type for TBP runs.
- The supported laboratory workflows are CCE, DL, CVD, and multi-stage separator calculations.

Phase-1 limitations:

- TBP cut data is input-side characterization support, not a standalone TBP experiment product.
- `solve_AB_from: fit_to_tbp` remains unsupported.
- Phase 1 accepts only contiguous one-carbon cuts starting at `fluid.plus_fraction.cut_start`.
- Gapped assays, interval cuts, and temperature-endpoint fitting remain out of scope.

Use TBP data today only as a way to derive aggregate plus-fraction inputs inside `pvtcore`. Do not assume GUI, CLI, or dedicated lab-workflow support for TBP runs.
