# TBP Status

A bounded standalone TBP kernel now exists in `pvtcore` at `pvtcore.experiments.tbp`.

Current supported surface:

- `pvtcore.experiments.tbp.simulate_tbp(...)` accepts phase-1 TBP cuts (`C<number>` names with `z` and `mw`, plus optional `sg`) and returns a standalone cut-resolved assay summary.
- The standalone result includes derived `z_plus` / `mw_plus_g_per_mol` plus cumulative mole- and mass-yield curves across the ordered cuts.
- `fluid.plus_fraction.tbp_data.cuts` remains supported in the schema-driven `load_fluid_definition(...)` + `characterize_from_schema(...)` path.
- There is still no supported `pvtapp` calculation type for TBP runs.

Current limitations:

- The repo-local TBP contract does not yet carry boiling-point or temperature-endpoint data, so the standalone module does not generate temperature-based distillation curves or fit boiling-point correlations.
- Phase 1 still accepts only contiguous one-carbon cuts starting at `fluid.plus_fraction.cut_start`.
- Gapped assays, interval cuts, and `solve_AB_from: fit_to_tbp` remain unsupported.
- TBP remains kernel-only: no GUI or CLI workflow or dedicated `pvtapp` lab-test runner is exposed.