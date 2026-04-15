# TBP Status

A bounded standalone TBP kernel now exists in `pvtcore` at `pvtcore.experiments.tbp`.

Current supported surface:

- `pvtcore.experiments.tbp.simulate_tbp(...)` accepts phase-1 TBP cuts (`C<number>` names with `z` and `mw`, plus optional `sg`) and returns a standalone cut-resolved assay summary.
- The standalone result includes derived `z_plus` / `mw_plus_g_per_mol` plus cumulative mole- and mass-yield curves across the ordered cuts.
- Ordered single cuts, interval cuts such as `C7-C9`, and gapped but non-overlapping sequences are now accepted.
- Optional cut boiling points can be entered explicitly as `tb_k`; when `sg` is present and `tb_k` is omitted, the runtime preserves an estimated boiling-point curve for reporting.
- `fluid.plus_fraction.tbp_data.cuts` remains supported in the schema-driven `load_fluid_definition(...)` + `characterize_from_schema(...)` path.
- Pedersen heavy-end characterization now supports `solve_AB_from: fit_to_tbp` when TBP cuts are provided, so TBP data can drive the actual plus-fraction split used by downstream runtime workflows.
- The desktop plus-fraction editor now carries optional TBP cuts and the Pedersen `fit_to_tbp` solve mode through `RunConfig` for non-standalone runtime calculations.
- `pvtapp` now supports a bounded standalone TBP workflow end to end: desktop calculation selection, cut-table input, runtime/config execution via `RunConfig(calculation_type="tbp", tbp_config={...})`, and saved run artifacts/results rendering.
- TBP run results now preserve an explicit bounded heavy-end characterization context in the result artifact and reporting surfaces, including the derived `C<n>+` bridge, Pedersen `fit_to_tbp` metadata, cut-to-SCN mapping, and the SCN property table used by the standalone bridge.
- Runtime-backed plus-fraction calculations now also preserve the actual heavy-end characterization package used to prepare EOS inputs: SCN distribution, runtime basis (`scn_unlumped` or `lumped`), lump membership, and the delumping weights needed to reconstruct the original heavy-end feed basis later.
- Standalone TBP now emits that same reusable runtime characterization package alongside the narrower TBP-specific bridge/reporting context, so the assay path no longer discards the deterministic SCN characterization state immediately after rendering it.

Current limitations:

- The first TBP cut must still start at `fluid.plus_fraction.cut_start`.
- The current `fit_to_tbp` implementation is a bounded Pedersen A/B fit. It does not yet drive broader TBP-specific property correlation fitting, BIP fitting, or a richer distillation-characterization workflow.
- The desktop GUI admission is still intentionally narrow: a standalone TBP assay screen plus optional TBP cuts inside the plus-fraction editor for Pedersen `fit_to_tbp`. It is not yet a full boiling-point / distillation / characterization workflow.
- The standalone TBP assay bridge is now richer than aggregate-only: it preserves a bounded unlumped SCN characterization derived from Pedersen `fit_to_tbp` plus Riazi-Daubert pseudo properties. This still does **not** yet imply broader TBP-driven lumping, BIP, or EOS selection logic.
- The preserved runtime package records the current lumping basis, explicit lumping method, and delumping weights when the canonical runtime solves on lumped heavy-end groups.
- The canonical runtime default now promotes lumped heavy-end runs to `Whitson` grouping, but this still does **not** yet imply broader TBP-aware BIP policy or a direct "run PT flash from a standalone TBP assay" workflow.
