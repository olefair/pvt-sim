# PVT-SIM Test Suite Consolidation Plan

## Current state

| Directory | Files | Tests | Lines | Wall time |
|-----------|------:|------:|------:|-----------|
| `tests/unit/` | 59 | 840 | ~18 000 | ~700 s |
| `tests/validation/` | 22 | 276 | ~5 000 | ~350 s |
| `tests/contracts/` | 2 | 52 | ~750 | ~15 s |
| **Total** | **79** | **1 168** | **~26 000** | **~13 min** |

Target: **≤ 250 tests, < 2 min wall time**, zero redundant computation, every
test adds signal.

---

## Principles

1. **One computation, many assertions.** Never call `calculate_phase_envelope`,
   `pt_flash`, `run_calculation`, or any EOS-backed solver more than once for
   the same `(mixture, P, T, eos)` inputs across the entire suite.
2. **Parametrize, don't copy-paste.** When the same assertion shape applies to
   N components, N fluids, or N calculation types, use one
   `@pytest.mark.parametrize` test.
3. **Module/session fixtures for expensive objects.** `load_components()`, EOS
   construction, phase envelopes, flash results — these are deterministic and
   must be cached at the widest safe scope.
4. **GUI tests cover contracts, not pixels.** Needed: does the GUI agree with
   the backend? Do widgets fit in their parents? Do results render without
   error? Not needed: 70 separate tests for individual widget field values.
5. **Validation tests earn their cost.** Each validation test must compare
   against an external or independent reference. Internal consistency checks
   belong in unit tests.
6. **Viable subsets by marker.** Tests must be selectable per module so that a
   lane merge touching `pvtcore.flash` can run only the flash-relevant tests.

---

## Shared fixtures layer (`tests/conftest.py`)

Create a centralized fixture layer:

```python
import pytest
from pvtcore.models.component import load_components
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.eos.srk import SRKEOS
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.saturation.bubble_point import calculate_bubble_point
from pvtcore.saturation.dew_point import calculate_dew_point
from pvtcore.envelope.phase_envelope import calculate_phase_envelope

@pytest.fixture(scope="session")
def components():
    return load_components()

@pytest.fixture(scope="session")
def c1_c10_pr(components):
    return PengRobinsonEOS([components["C1"], components["C10"]])

@pytest.fixture(scope="session")
def c1_c4_pr(components):
    return PengRobinsonEOS([components["C1"], components["C4"]])

@pytest.fixture(scope="session")
def c2_c3_pr(components):
    return PengRobinsonEOS([components["C2"], components["C3"]])

@pytest.fixture(scope="session")
def c1_c10_envelope(components, c1_c10_pr):
    """Single phase envelope computation reused by all envelope tests."""
    import numpy as np
    z = np.array([0.5, 0.5])
    return calculate_phase_envelope(z, [components["C1"], components["C10"]], c1_c10_pr)

@pytest.fixture(scope="session")
def c1_c10_flash(components, c1_c10_pr):
    """Single PT flash reused by all flash-property tests."""
    import numpy as np
    z = np.array([0.5, 0.5])
    return pt_flash(5e6, 350.0, z, [components["C1"], components["C10"]], c1_c10_pr)

# Add more as needed per the consolidation below.
```

---

## File-by-file plan

### A. Component database — `test_components.py`

**Current:** 71 tests, 508 lines. Each test asserts one property of one
component against a NIST reference value.

**Plan:** Replace with one parametrized test over a reference table.

```python
NIST_REFERENCE = [
    ("N2",  "Tc", 126.19, 0.001),
    ("N2",  "Pc_MPa", 3.3978, 0.001),
    ("N2",  "MW", 28.0134, 0.0001),
    ("N2",  "Tb", 77.34, 0.001),
    ("N2",  "omega", 0.039, 0.002),
    ("CO2", "Tc", 304.18, 0.001),
    # ... all species/properties
]

@pytest.mark.parametrize("comp_id,attr,expected,tol", NIST_REFERENCE)
def test_component_property_vs_nist(components, comp_id, attr, expected, tol):
    assert getattr(components[comp_id], attr) == pytest.approx(expected, abs=tol)
```

Plus 3-4 structural tests (DB loads, all expected IDs present, dataclass
shape, alias index).

**Result:** 71 → ~5 test functions (~75 parametrized cases).

---

### B. Phase envelope — `test_envelope.py`

**Current:** 69 tests, 1 274 lines. Every test calls
`calculate_phase_envelope()` independently (~7.5 s each).

**Plan:** Use session-scoped `c1_c10_envelope` fixture. Collapse into:

1. `test_envelope_structure` — result fields, types, lengths, convergence.
2. `test_envelope_physics` — T/P positive, bubble left of dew, pressure
   increases with temperature, adaptive step density near critical.
3. `test_critical_point` — detected, positive, between pure Tc, on envelope.
4. `test_cricondentherm_cricondenbar` — estimates from shared envelope.
5. `test_envelope_reproducibility` — two calls give same result (only test
   that computes a second envelope).
6. `test_composition_variation` — parametrize over `(z, eos_fixture)` for
   C1-rich, C10-rich, C2-C3.
7. `test_input_validation` — bad composition sum, length mismatch (cheap).
8. `test_iso_lines` — IsoLineMode enum, compute from shared envelope,
   alpha/beta close to target, physical constraints. One envelope computation,
   many assertions.
9. `test_ternary_diagram` — grid geometry (pure math, cheap), then one
   `compute_ternary_diagram` call with assertions on classification, mass
   balance, tie-lines.

**Result:** 69 → ~12 test functions. Envelope computation: 3-4 times total
(one per mixture) instead of ~60 times. **Time: ~500 s → ~30 s.**

---

### C. Flash — `test_flash.py`

**Current:** 37 tests, 605 lines. Repeated `pt_flash` and Rachford-Rice
across classes.

**Plan:**

1. `test_wilson_k_values` — parametrize over components (cheap, no EOS).
2. `test_rachford_rice_solver` — parametrize over (K, z, expected β).
3. `test_pt_flash_converges` — one flash result from session fixture; assert
   convergence, material balance, fugacity equality, K-values, phase.
4. `test_flash_special_cases` — BIP, initial K-values (parametrize).
5. `test_flash_edge_cases` — single-phase, near-critical (parametrize P/T).

**Result:** 37 → ~6 test functions.

---

### D. Saturation — `test_saturation.py`

**Current:** 36 tests, 634 lines. Many repeated bubble/dew solves.

**Plan:** Session fixture for canonical bubble and dew results. Collapse into:

1. `test_bubble_point` — convergence, pressure physical, composition shift.
2. `test_dew_point` — same pattern.
3. `test_composition_variation` — parametrize over z.
4. `test_convergence_options` — max_iter, tolerance effects.
5. `test_edge_cases` — near-critical, pure-component.

**Result:** 36 → ~6 test functions.

---

### E. Stability — merge 4 files into 1

**Current:** `test_stability.py` (23), `test_stability_analysis.py` (6),
`test_stability_analysis_api.py` (2), `test_stability_analysis_robustness.py`
(4) = 35 tests across 4 files. `test_stability_analysis_api.py` is a
duplicate of the first two tests in `test_stability_analysis.py`.

**Plan:** Single `test_stability.py`:

1. `test_tpd_and_stability` — session fixture for PR EOS, parametrize
   (P, T, z, expected_stable).
2. `test_stability_analyze_api` — output structure, diagnostics.
3. `test_gdem_acceleration` — faster convergence.
4. `test_eos_failure_recovery` — flaky EOS wrapper.
5. `test_legacy_wrapper_parity` — Michelsen wrapper agrees with new API.

Delete `test_stability_analysis_api.py` entirely.

**Result:** 35 → ~6 test functions, 1 file.

---

### F. EOS — `test_peng_robinson.py` + `test_ppr78.py` + `test_pr78.py` + `test_srk.py`

**Current:** 39 + 33 + 4 + 4 = 80 tests.

**Plan:** `test_eos.py`:

1. `test_eos_parametrized` — parametrize `(EOS_class, component, expected_Z,
   expected_fugacity)` over PR76, PR78, SRK × {C1, C2, ..., C10}.
2. `test_mixing_rules` — one binary test per EOS.
3. `test_ppr78_group_decomposition` — parametrize species → expected groups.
4. `test_ppr78_kij` — one binary kij check.
5. `test_pr78_vs_pr76_heavy` — C12 κ divergence.

**Result:** 80 → ~8 test functions.

---

### G. Experiments — `test_experiments.py` + `test_cvd_dl_retained_basis.py` + `test_cvd_volume_closure.py`

**Current:** 31 + 2 + 2 = 35 tests.

**Plan:** Single `test_experiments.py`:

1. `test_cce` — one simulation, multiple assertions.
2. `test_differential_liberation` — same.
3. `test_cvd` — same, including volume closure and retained basis.
4. `test_separator` — parametrize stage count.
5. `test_experiment_edge_cases` — invalid inputs (parametrize).

**Result:** 35 → ~6 test functions.

---

### H. Properties — `test_properties.py` + `test_density.py` + `test_ift_parachor.py`

**Current:** 31 + 3 + 4 = 38 tests.

**Plan:** Merge into `test_properties.py`. Use session flash fixture; one
flash gives liquid/vapor compositions and volumes for all property tests.

1. `test_density_from_flash` — liquid, vapor, mixing rule.
2. `test_viscosity_from_flash` — LBC, Lohrenz.
3. `test_ift_parachor` — from same flash, scaling.
4. `test_property_edge_cases` — single-phase, near-critical.

**Result:** 38 → ~5 test functions.

---

### I. Characterization — `test_characterization_pipeline.py` + `test_plus_fraction_splitting.py` + `test_lumping_delumping.py`

**Current:** 33 + 3 + 3 = 39 tests.

**Plan:**

1. `test_pedersen_split` — parametrize C7+ inputs.
2. `test_katz_faskhi_split` — same shape.
3. `test_lumping_delumping_roundtrip` — one split, lump, delump, assert
   closure.
4. `test_bip_matrix` — from split output.
5. `test_scn_properties` — table lookup (keep, cheap).

**Result:** 39 → ~6 test functions.

---

### J. Correlations — `test_correlations.py` + `test_riazi_daubert.py`

**Current:** 29 + 2 = 31 tests.

**Plan:** Parametrize all correlation families:

```python
CORRELATION_CASES = [
    ("kesler_lee_Tc", {"Tb": 477.6, "sg": 0.862}, 693.3, 0.01),
    ("riazi_daubert_Tc_Tb_sg", {"Tb": 477.6, "sg": 0.862}, ..., 0.01),
    # ...
]

@pytest.mark.parametrize("func,inputs,expected,tol", CORRELATION_CASES)
def test_correlation(func, inputs, expected, tol):
    ...
```

**Result:** 31 → ~2 test functions.

---

### K. Cubic solver — `test_cubic_solver.py`

**Current:** 33 tests.

**Plan:** Parametrize `(coefficients, expected_roots)`.

**Result:** 33 → ~3 test functions (real roots, complex, edge cases).

---

### L. IO — `test_io.py` + `test_fluid_definition_parser.py`

**Current:** 34 + 15 = 49 tests.

**Plan:**

1. `test_import_export_roundtrip` — parametrize format.
2. `test_unit_conversions` — parametrize (quantity, from, to, expected).
3. `test_fluid_definition_parser` — parametrize (valid/invalid JSON, expected
   outcome).
4. `test_report_generation` — one run, assert structure.

**Result:** 49 → ~5 test functions.

---

### M. Tuning — `test_tuning.py` + `test_tuning_unsupported_datatype.py`

**Current:** 34 + 1 = 35 tests.

**Plan:**

1. `test_objective_functions` — parametrize type over reference scalar.
2. `test_parameter_bounds` — parametrize parameter type.
3. `test_regressor_converges` — one regression run, assert improvement.
4. `test_unsupported_datatype_error` — keep.

**Result:** 35 → ~4 test functions.

---

### N. Convergence status — `test_convergence_status.py`

**Current:** 21 tests.

**Plan:** Parametrize enum cases; one flash for status behavior.

**Result:** 21 → ~3 test functions.

---

### O. Confinement — `test_confinement.py`

**Current:** 26 tests.

**Plan:** Module-scoped EOS; parametrize pore size/pressure.

**Result:** 26 → ~5 test functions.

---

### P. GUI tests — consolidate 16 files into 3

**Current:** 16 `test_pvtapp_*` files, 219 tests, ~8 600 lines.

The 3 615-line `test_pvtapp_desktop_contract.py` alone has 70 tests that
overlap with nearly every other pvtapp test file.

**Plan:** Three focused files:

#### `test_gui_contracts.py` (~8 tests)

Replaces: `test_pvtapp_desktop_contract.py`,
`test_pvtapp_workspace_layout.py`,
`test_pvtapp_phase_envelope_widget_style.py`,
`test_pvtapp_stability_desktop.py`,
`test_pvtapp_conditions_input.py`,
`test_pvtapp_zero_fraction_duplicates.py`,
`test_pvtapp_cvd_result_views.py`,
`test_pvtapp_tbp_result_views.py`,
`test_pvtapp_pt_flash_viscosity.py`.

Tests:

1. `test_main_window_opens_and_closes` — PVTSimulatorWindow instantiates,
   shows all expected top-level widgets.
2. `test_config_roundtrip_all_calc_types` — parametrize over all
   `CalculationType` values: build config → load → re-extract → equal.
3. `test_results_render_all_calc_types` — parametrize over synthetic
   `RunResult` per type: table + plot + text render without error.
4. `test_composition_widget_validation` — duplicate rows, normalization,
   plus-fraction modes (parametrize mode).
5. `test_gui_agrees_with_backend` — run one PT flash via `run_calculation`,
   feed result to results widgets, assert displayed values match
   `PTFlashResult` fields.
6. `test_zoom_and_scaling` — apply UI scale, assert no widget exceeds parent
   bounds, text fits.
7. `test_dark_theme_palette` — plot colors match expected palette.
8. `test_run_log_lifecycle` — add runs, sort, select, delete, export.

#### `test_runtime_contract.py` (~10 tests)

Replaces: `test_pvtapp_runtime_contract.py`,
`test_pvtapp_cce_workflow.py`,
`test_pvtapp_remaining_workflows.py`,
`test_pvtapp_phase_envelope_workflow.py`,
`test_pvtapp_stability_runtime.py`,
`test_pvtapp_run_history.py`,
`test_pvtapp_assignment_case.py`,
`test_pvtapp_pt_flash_viscosity.py` (runtime half).

Tests:

1. `test_validate_runtime_config` — parametrize valid/invalid configs.
2. `test_run_calculation_all_workflows` — parametrize over all calculation
   types with representative configs. One run each.
3. `test_plus_fraction_auto_characterization` — one plus-fraction run.
4. `test_phase_envelope_tracers` — parametrize continuation vs fixed_grid.
5. `test_stability_analysis_runtime` — one run, assert trial diagnostics.
6. `test_rerun_saved_run` — one save + reload + rerun roundtrip.
7. `test_cancel_calculation` — thread cancel behavior.
8. `test_progress_callback` — callback fires.
9. `test_assignment_preset` — preset builder.
10. `test_cli_validate` — parametrize valid/invalid config files.

#### `test_pvtapp_schemas.py` (~3 tests)

1. `test_run_config_validation` — parametrize valid/invalid payloads.
2. `test_run_result_serialization` — roundtrip.
3. `test_recommendation_policy` — parametrize fluid kind.

**Result:** 219 GUI/app tests → ~21 test functions. 16 files → 3 files.

---

### Q. Contracts — `tests/contracts/`

**Current:** `test_invariants.py` (17) + `test_robustness.py` (34) = 52
tests.

**Overlap:** `test_invariants.py` duplicates `tests/unit/test_invariants.py`
and `tests/validation/test_vle_benchmarks.py`. `test_robustness.py` tests
invalid-input paths already covered by unit tests.

**Plan:** Merge into unit tests:
- Physics invariants → `test_flash.py` assertions (already there).
- Invalid-input robustness → parametrize in relevant unit test files.
- Delete `tests/contracts/` directory.

**Result:** 52 → 0 (absorbed into unit tests).

---

### R. Validation — consolidate and deduplicate

**Current:** 22 files, 276 tests.

Many validation tests overlap each other and unit tests. Keep only tests that
compare against an **external** reference.

#### Keep (with consolidation):

1. `test_nist_validation.py` — merge `test_nist_vapor_pressure.py` +
   `test_external_pure_component_saturation.py`. Parametrize over NIST
   JSON. ~2 test functions.
2. `test_external_literature.py` — merge `test_external_literature_vle.py` +
   `test_external_corpus_schema.py`. ~2 test functions.
3. `test_mi_pvt_validation.py` — keep `test_vs_mi_pvt.py`, deduplicate curve
   helpers. ~1 test function.
4. `test_thermopack_validation.py` — keep `test_thermopack_phase_envelope.py`.
   ~1 test function.
5. `test_plus_fraction_validation.py` — merge
   `test_plus_fraction_bubble_characterization.py` +
   `test_plus_fraction_dew_characterization.py`. ~2 test functions.
6. `test_stability_validation.py` — merge `test_stability_runtime_matrix.py` +
   `test_stability_fixture_validation.py` +
   `test_stability_external_pure_component_regimes.py` +
   `test_stability_physical_state_hints.py` +
   `test_stability_saturation_regime_windows.py`. Share one EOS setup. ~3 test
   functions.
7. `test_phase_envelope_validation.py` — merge
   `test_phase_envelope_runtime_matrix.py` +
   `test_phase_envelope_release_gates.py` +
   `test_phase_envelope_breadth_roster.py`. ~2 test functions.
8. `test_fluid_validation_matrix.py` — keep, consolidate. ~2 test functions.

#### Delete (absorbed into unit tests):

- `test_vle_benchmarks.py` — internal consistency, not external reference.
  Assertions already in `test_flash.py`.
- `test_saturation_equation_benchmarks.py` — internal cross-check. Move
  independent-reference cases to `test_nist_validation.py`.
- `test_flash_fixture_invariants.py` — fixture regression, not external ref.
  Move to `test_flash.py`.
- `test_heavy_end_pt_flash_runtime_matrix.py` — runtime policy checks. Move
  to `test_runtime_contract.py`.
- `test_units_validation.py` — script runner test. Move to unit tests.

**Result:** 22 files, 276 tests → 8 files, ~15 test functions.

---

### S. Remaining small files — absorb or keep

| File | Tests | Action |
|------|------:|--------|
| `test_invariants.py` (unit) | 9 | Absorb into `test_flash.py` |
| `test_validation_invariants.py` | 6 | Absorb into `test_flash.py` |
| `test_validation_backend_registry.py` | 4 | Keep (cheap, distinct) |
| `test_stability_wrappers.py` | 2 | Absorb into `test_stability.py` |
| `test_prode_bridge.py` | 2 | Keep (isolated mock) |
| `test_thermopack_bridge.py` | 2 | Keep (isolated mock) |
| `test_pete665_assignment.py` | 7 | Absorb into `test_runtime_contract.py` |
| `test_scn_properties.py` | 3 | Keep (cheap) |
| `test_tbp_module.py` | 8 | Collapse to ~2 (parametrize cuts) |
| `test_tbp_policy.py` | 5 | Absorb into `test_runtime_contract.py` |

---

## Consolidated test inventory

| File | Tests | Replaces |
|------|------:|----------|
| `tests/conftest.py` | — | Shared fixtures |
| **Unit** | | |
| `test_components.py` | ~5 | 71 → 5 |
| `test_eos.py` | ~8 | 80 → 8 |
| `test_flash.py` | ~6 | 37 + 9 + 6 → 6 |
| `test_stability.py` | ~6 | 35 → 6 |
| `test_saturation.py` | ~6 | 36 → 6 |
| `test_envelope.py` | ~12 | 69 → 12 |
| `test_experiments.py` | ~6 | 35 → 6 |
| `test_properties.py` | ~5 | 38 → 5 |
| `test_characterization.py` | ~6 | 39 → 6 |
| `test_correlations.py` | ~2 | 31 → 2 |
| `test_cubic_solver.py` | ~3 | 33 → 3 |
| `test_io.py` | ~5 | 49 → 5 |
| `test_tuning.py` | ~4 | 35 → 4 |
| `test_convergence.py` | ~3 | 21 → 3 |
| `test_confinement.py` | ~5 | 26 → 5 |
| `test_scn_properties.py` | 3 | keep |
| `test_prode_bridge.py` | 2 | keep |
| `test_thermopack_bridge.py` | 2 | keep |
| `test_validation_backend_registry.py` | 4 | keep |
| `test_tbp.py` | ~2 | 13 → 2 |
| **App** | | |
| `test_gui_contracts.py` | ~8 | 219 → 8 |
| `test_runtime_contract.py` | ~10 | (see above) |
| `test_pvtapp_schemas.py` | ~3 | (see above) |
| **Validation** | | |
| `test_nist_validation.py` | ~2 | (see above) |
| `test_external_literature.py` | ~2 | (see above) |
| `test_mi_pvt_validation.py` | ~1 | (see above) |
| `test_thermopack_validation.py` | ~1 | (see above) |
| `test_plus_fraction_validation.py` | ~2 | (see above) |
| `test_stability_validation.py` | ~3 | (see above) |
| `test_phase_envelope_validation.py` | ~2 | (see above) |
| `test_fluid_validation_matrix.py` | ~2 | (see above) |
| **Total** | **~135** | **1 168 → ~135** |

---

## Pytest markers for lane-scoped runs

```ini
[tool.pytest.ini_options]
markers = [
    "eos: equation of state tests",
    "flash: PT flash tests",
    "stability: stability analysis tests",
    "saturation: bubble/dew point tests",
    "envelope: phase envelope tests",
    "experiments: CCE/DL/CVD/separator tests",
    "properties: density/viscosity/IFT tests",
    "characterization: plus fraction / SCN tests",
    "gui: desktop GUI contract tests",
    "runtime: pvtapp runtime/schema tests",
    "validation: external reference validation",
    "slow: tests expected to take > 5 s",
]
```

Lane merge example:
```bash
pytest -m flash          # touched pvtcore.flash
pytest -m "gui"          # touched pvtapp widgets
pytest -m "not slow"     # fast feedback loop
```

---

## Execution order

This is ordered by impact (time saved × risk reduced):

### Phase 1 — Shared fixtures + envelope fix

1. Build `tests/conftest.py` shared fixture layer.
2. Rewrite `test_envelope.py` to use session-scoped fixtures.

**Impact:** ~500 s → ~30 s. Single biggest win.

### Phase 2 — Parametrize data-table tests

3. `test_components.py` → parametrized reference table.
4. `test_correlations.py` → parametrized.
5. `test_cubic_solver.py` → parametrized.
6. `test_peng_robinson.py` + `test_ppr78.py` + `test_pr78.py` +
   `test_srk.py` → `test_eos.py`.

**Impact:** ~170 tests → ~18 test functions.

### Phase 3 — Merge stability files + flash + saturation

7. Merge stability files, deduplicate API tests.
8. Consolidate `test_flash.py` + invariant files.
9. Consolidate `test_saturation.py`.

**Impact:** ~100 tests → ~18 test functions. Shared EOS eliminates repeated
setup.

### Phase 4 — GUI consolidation

10. Merge all 16 pvtapp test files into 3.
11. Delete `tests/contracts/` (absorb into unit tests).

**Impact:** 219 + 52 → ~21 test functions. Eliminates the 3 615-line file.

### Phase 5 — Validation consolidation

12. Merge validation files by reference source.
13. Delete internal-consistency files (absorb into unit tests).

**Impact:** 276 → ~15 test functions. Eliminates duplicate cross-checks.

### Phase 6 — Remaining cleanup

14. Absorb small files into their parent modules.
15. Add pytest markers.
16. Verify full suite < 2 min.
