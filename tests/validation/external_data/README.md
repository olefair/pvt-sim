# External Saturation Validation Corpus

This folder is the canonical intake surface for external physical-accuracy
anchors used by bubble-point and dew-point validation.

Boundary:

- `tests/validation/test_saturation_equation_benchmarks.py` remains the
  authoritative solver-correctness lane.
- `tests/validation/mi_pvt/` remains the secondary MI-PVT cross-check lane.
- `tests/validation/external_data/` is where measured, critically evaluated,
  or literature-derived physical-accuracy anchors belong.

Do not drop new external reference JSON files directly into arbitrary test
modules. Add them here and validate them through
`pvtcore.validation.external_corpus`.

## Layout

```text
tests/validation/external_data/
├── acquisition_manifest.json
├── cases/
│   ├── nist_c1_saturation_batch.json
│   ├── nist_c2_saturation_batch.json
│   ├── nist_c3_saturation_batch.json
│   ├── nist_c4_saturation_batch.json
│   ├── nist_c5_saturation_batch.json
│   ├── nist_c6_saturation_batch.json
│   ├── nist_co2_saturation_batch.json
│   └── thermoml_2015_ch4_c3_tieline_24361k_xch4_04857.json
└── templates/
    ├── pure_component_saturation_template.json
    ├── literature_vle_tieline_template.json
    └── lab_c7plus_saturation_template.json
```

- `acquisition_manifest.json`
  Tracks the current planned external-anchor backlog before the actual numbers
  have been collected.
- `cases/`
  Holds ready-to-validate external anchor JSON files. The current repo already
  includes NIST pure-component saturation anchors for `C1`-`C6` and `CO2`,
  plus the first promoted ThermoML literature tie-line anchor.
- `templates/`
  Example JSON shapes for each supported anchor type. The values in the
  templates are illustrative only.

## Supported Anchor Types

1. `pure_component_saturation`
   Use for NIST or ThermoML saturation-pressure tables of pure components.

2. `literature_vle_tieline`
   Use for literature coexistence states with explicit liquid and vapor
   compositions at a reported `T, P`.

3. `lab_c7plus_saturation`
   Use for lab-style `C1-C6 + C7+` bubble-point or dew-point anchors. These
   cases must declare the exact characterization knobs needed to reproduce the
   reported result, not just the bulk `C7+` properties.

## Contract

- Every actual case file must validate against
  `src/pvtcore/validation/external_corpus.py`.
- Every planned source collection item must appear in
  `acquisition_manifest.json` until the case file exists.
- Bubble/dew docs should reference this folder when they call out missing
  external anchors.
- Promoted case files should be removed from `acquisition_manifest.json` once
  they exist under `cases/`.
