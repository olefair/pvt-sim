# PVT-SIM Architecture

Simulator architecture belongs in this docs set, not in repo-root
orientation files.

## Canonical Companion Docs

- `docs/runtime_surface_standard.md` for the canonical app/runtime parity rule
- `docs/technical_notes.md` for equations and thermo dependency ordering
- `docs/numerical_methods.md` for solver policy and convergence rules
- `docs/input_schema.md` for fluid/config contracts
- `docs/units.md` for canonical internal units

## System Overview

PVT-SIM is a modular phase behavior simulator designed for both standalone use and integration into larger systems. The architecture separates concerns into distinct layers:

```
┌─────────────────────────────────────────────────────────────┐
│                    External Systems                         │
│              (Voice Assistant, Scripts, API)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      pvtapp Layer                           │
│         (UI, Plotting, Interactive Sessions)                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     pvtcore Layer                           │
│              (All Computational Logic)                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐            │
│  │ charac- │ │   eos   │ │  flash  │ │ proper- │            │
│  │tertic.  │ │         │ │         │ │  ties   │            │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘            │
│       │          │          │          │                    │
│       └──────────┴─────┬────┴──────────┘                    │
│                        │                                    │
│               ┌────────▼────────┐                           │
│               │     models      │                           │
│               │  (data structs) │                           │
│               └────────┬────────┘                           │
│                        │                                    │
│               ┌────────▼────────┐                           │
│               │      core       │                           │
│               │ (units, consts) │                           │
│               └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      data Layer                             │
│        (Component DB, Correlation Coefficients)             │
└─────────────────────────────────────────────────────────────┘
```

---

## Module Specifications

### core/

Foundation module with no dependencies on other pvtcore modules.

| File | Purpose |
|------|---------|
| `constants.py` | Physical constants (R, standard conditions, etc.) |
| `units.py` | Unit conversion functions, unit registry |
| `typing.py` | Type aliases, Protocol classes |
| `errors.py` | Custom exception hierarchy |
| `numerics/brent.py` | Brent's method for root finding |
| `numerics/newton.py` | Newton-Raphson with damping |
| `numerics/convergence.py` | Convergence criteria, iteration tracking |

### models/

Data structures representing physical entities. Immutable where possible.

| File | Purpose |
|------|---------|
| `component.py` | `Component` dataclass with Tc, Pc, ω, MW, etc. |
| `mixture.py` | `Mixture` class holding composition + component list |
| `eos_params.py` | EOS-specific parameters (a, b, BIPs) |
| `phase.py` | `Phase` with composition, Z-factor, density |
| `results.py` | Result containers for flash, envelope, experiments |

### characterization/

Fluid characterization from laboratory data.

| File | Purpose |
|------|---------|
| `plus_splitting/pedersen.py` | Exponential distribution: ln(zₙ) = A + B·MWₙ |
| `plus_splitting/katz.py` | Katz correlation: zₙ = 1.38205·z₇₊·exp(-0.25903n) |
| `plus_splitting/lohrenz.py` | Quadratic exponential |
| `plus_splitting/whitson_gamma.py` | Gamma distribution (optional) |
| `scn_properties.py` | Generalized SCN tables (Katz-Firoozabadi) |
| `lumping.py` | Whitson lumping with Lee mixing rules |
| `delumping.py` | K-value interpolation for full composition recovery |

### correlations/

Property estimation correlations for pseudo-components.

| File | Purpose |
|------|---------|
| `tb.py` | Boiling point: Soreide (1989) |
| `critical_props/riazi_daubert.py` | Tc, Pc, Vc from Tb, γ |
| `critical_props/kesler_lee.py` | Tc, Pc, ω from Tb, γ |
| `critical_props/cavett.py` | Alternative correlation |
| `acentric.py` | Edmister, Kesler-Lee methods |
| `parachor.py` | Fanchi correlation from MW |

### eos/

Equation of state implementations.

| File | Purpose |
|------|---------|
| `base.py` | Abstract `CubicEOS` protocol |
| `peng_robinson.py` | PR (1976) implementation |
| `pr78.py` | PR (1978) implementation (runtime-wired) |
| `srk.py` | SRK (1972) implementation |
| `ppr78.py` | Predictive PR78 group-contribution k_ij(T) model (Jaubert & Mutelet 2004). **Kernel-present, not runtime-wired** — treated as experimental until validated and exposed through `pvtapp`. |
| `groups/` | PPR78 group definitions and component decomposition |

Shared helpers for cubic roots, mixing rules, and volume translation live
alongside these files (`base.py`, SRK, PR modules). The runtime EOS surface
exposed through `src/pvtapp/capabilities.py` is Peng-Robinson (1976),
Peng-Robinson (1978), and SRK.

### stability/

Phase stability analysis.

| File | Purpose |
|------|---------|
| `wilson.py` | Wilson K-value correlation for initialization |
| `tpd.py` | Michelsen tangent plane distance method |

### flash/

Phase equilibrium calculations.

| File | Purpose |
|------|---------|
| `rachford_rice.py` | RR equation solver (Brent's method) |
| `pt_flash.py` | Isothermal flash at specified P, T |
| `saturation.py` | Bubble point, dew point calculations |
| `acceleration/gdem.py` | General dominant eigenvalue method |

### envelope/

Phase envelope construction.

| File | Purpose |
|------|---------|
| `trace.py` | Envelope tracing algorithm |
| `critical_point.py` | Critical point location |
| `quality_lines.py` | Iso-volume fraction curves |

### properties/

Transport and interfacial properties.

| File | Purpose |
|------|---------|
| `density.py` | From Z-factor with volume translation |
| `viscosity_lbc.py` | Lohrenz-Bray-Clark correlation |
| `ift_parachor.py` | Parachor method (Weinaug-Katz) |

### experiments/

Laboratory test simulations.

| File | Purpose |
|------|---------|
| `cce.py` | Constant Composition Expansion |
| `dl.py` | Differential Liberation |
| `cvd.py` | Constant Volume Depletion |
| `swelling.py` | Fixed-temperature single-contact swelling test |
| `separators.py` | Multi-stage separator optimization |

### confinement/

Nano-confinement extensions.

| File | Purpose |
|------|---------|
| `capillary.py` | Capillary pressure from IFT and pore radius |
| `confined_flash.py` | Flash with Pⱽ = Pᴸ + Pc iteration |
| `confined_envelope.py` | Shifted phase envelope generation |

### tuning/

EOS parameter regression.

| File | Purpose |
|------|---------|
| `parameters.py` | Tunable parameter definitions, bounds |
| `objectives.py` | Objective function construction |
| `datasets.py` | Experimental data containers |
| `regression.py` | Levenberg-Marquardt optimizer |

### io/

Data import/export inside `pvtcore`.

| File | Purpose |
|------|---------|
| `import_csv.py` | Parse CSV composition files |
| `import_excel.py` | Parse Excel PVT reports |
| `export_csv.py` | Write results to CSV |
| `report_templates/` | Standard PVT report formats |

Application-facing export lives in `pvtapp`:

| File | Purpose |
|------|---------|
| `src/pvtapp/excel_export.py` | Multi-sheet `.xlsx` export of a completed `RunResult`. Uses `openpyxl` Tables (`TableStyleMedium2`) with per-calc sections (e.g. CCE → Expansion / Phase Densities / Phase Viscosities / Per-Step Liquid / Per-Step Vapor). All values are written in US-petroleum display units (psia, °F, ...) to match the GUI and text output. Public entry point: `export_result_to_excel`. |

---

## Data Flow: Flash Calculation

```
Input: composition z[], pressure P, temperature T
                    │
                    ▼
        ┌───────────────────────┐
        │  Stability Analysis   │
        │    (Michelsen TPD)    │
        └───────────┬───────────┘
                    │
          ┌─────────┴─────────┐
          │                   │
     TPD ≥ 0             TPD < 0
     (stable)           (unstable)
          │                   │
          ▼                   ▼
    Return single      ┌─────────────┐
    phase (z, Z)       │  PT Flash   │
                       └──────┬──────┘
                              │
                    ┌─────────┴─────────┐
                    │                   │
                    ▼                   ▼
            ┌──────────────┐    ┌──────────────┐
            │ Liquid Phase │    │ Vapor Phase  │
            │   x[], Zᴸ    │    │   y[], Zⱽ    │
            └──────┬───────┘    └──────┬───────┘
                   │                   │
                   └─────────┬─────────┘
                             │
                             ▼
                   ┌───────────────────┐
                   │    Properties     │
                   │  ρ, μ, σ for each │
                   └───────────────────┘
                             │
                             ▼
                      FlashResult
```

---

## Data Flow: Nano-Confined Flash

```
Input: composition z[], liquid pressure Pᴸ, temperature T, pore radius r
                    │
                    ▼
        ┌───────────────────────┐
        │   Bulk Flash (Pc=0)   │
        │     Get x, y, ρ       │
        └───────────┬───────────┘
                    │
                    ▼
        ┌───────────────────────┐
        │   Calculate IFT (σ)   │◄─────────┐
        │   from x, y, ρᴸ, ρⱽ   │          │
        └───────────┬───────────┘          │
                    │                      │
                    ▼                      │
        ┌───────────────────────┐          │
        │   Pc = 2σ/r           │          │
        └───────────┬───────────┘          │
                    │                      │
                    ▼                      │
        ┌───────────────────────┐          │
        │  Re-flash with        │          │
        │  Pⱽ = Pᴸ + Pc         │          │
        └───────────┬───────────┘          │
                    │                      │
                    ▼                      │
              |Pc_new - Pc_old|            │
                < tolerance?               │
                    │                      │
          ┌─────────┴─────────┐            │
          No                  Yes          │
          │                   │            │
          └───────────────────┘────────────┘
                              │
                              ▼
                    ConfinedFlashResult
```

---

## Interface Design

### Callable Module Pattern

For voice assistant and external system integration:

```python
from pvtcore import Fluid, FlashEngine

# Load fluid from composition
fluid = Fluid.from_composition({
    "N2": 0.005, "CO2": 0.012, "C1": 0.45, "C2": 0.08,
    "C3": 0.055, "C7+": {"z": 0.25, "MW": 215, "gamma": 0.85}
})

# Configure and run flash
engine = FlashEngine(eos="PR", splitting="pedersen")
result = engine.flash(fluid, P=2000e5, T=373.15)

# Access results
print(result.vapor_fraction)      # 0.342
print(result.liquid.density)      # 650.2 kg/m³
print(result.phases["vapor"].composition)  # NDArray
```

### Result Objects

All results are serializable dataclasses:

```python
@dataclass(frozen=True)
class FlashResult:
    converged: bool
    iterations: int
    vapor_fraction: float
    liquid: Phase
    vapor: Phase
    stability_info: StabilityResult
    
    def to_dict(self) -> dict: ...
    def to_json(self) -> str: ...
```

---

## Extensibility Points

1. **New EOS:** Implement `CubicEOS` protocol, register in factory
2. **New Correlations:** Add module to `correlations/`, register in dispatcher
3. **New Splitting Methods:** Add to `plus_splitting/`, implement `SplittingMethod` protocol
4. **New Lab Tests:** Add to `experiments/`, follow CCE/DL pattern
5. **Alternative Optimizers:** Swap in `tuning/regression.py`

---

## Performance Considerations

1. **Vectorization:** Use NumPy arrays for composition vectors; avoid Python loops over components
2. **Caching:** EOS parameters (a, b) don't change during flash iteration—compute once
3. **Lazy Evaluation:** Don't compute viscosity/IFT unless requested
4. **Profiling Points:** Flash inner loop, cubic solver, fugacity coefficient calculation

---

## Desktop Runtime Surface (pvtapp)

The desktop app layers three persistence surfaces on top of the kernel:

### Run persistence

Every completed run is written to a timestamped directory by the worker
thread in `src/pvtapp/job_runner.py`:

- Windows: `%LOCALAPPDATA%/PVTSimulator/runs/<YYYYMMDD_HHMMSS>_<run_id>/`
- Other platforms: `~/.pvtsimulator/runs/<YYYYMMDD_HHMMSS>_<run_id>/`

The directory is created by `get_default_runs_directory()` /
`create_run_directory()`. Saved runs are reloaded via:

- `pvtapp.job_runner.load_run_config(run_dir)` → `RunConfig | None`
- `pvtapp.job_runner.load_run_result(run_dir)` → `RunResult | None`
- `pvtapp.job_runner.list_runs(limit=...)` → status-annotated recent runs

### Auto-restore on open

`PVTSimulatorWindow._restore_last_completed_run` runs once on startup via a
queued `QTimer.singleShot(0, ...)` hook. It picks the most recent
`completed` entry from `list_runs(limit=10)`, loads its config back into the
inputs panel, and replays its result into the right-rail, text output,
diagnostics, and plot surfaces. Cancelled and failed runs are skipped.
Failures at any stage are silent — a first launch with no saved runs is a
normal case and leaves the UI empty.

### Excel export

`pvtapp.excel_export.export_result_to_excel(result, path)` writes a
multi-sheet `.xlsx` workbook using `openpyxl`. The workbook contains:

- a `Summary` sheet with run metadata and per-calc highlights
- one data sheet per logical section per calc type (e.g. for CCE:
  `Expansion`, `Phase Densities`, `Phase Viscosities`, `Per-Step Liquid`,
  `Per-Step Vapor`)

Each data sheet uses `Table` with `TableStyleMedium2`, frozen header panes,
and unit-labelled column headers (`P (psia)`, `Liquid Density (kg/m³)`,
...). Every pressure / temperature / density / viscosity / GOR / FVF value
is rendered in US-petroleum display units to match the GUI and text output.

---

## Known Architectural Limitations

These are architectural, not numerical, and the ones that affect runtime
shape.

- **Phase envelope plotter does not inject the critical point.** Per the
  comment in `src/pvtapp/widgets/results_view.py._plot_phase_envelope._curve_xy`,
  the detected critical point is deliberately not stitched into the bubble
  and dew polylines because the CP generally does not lie on the discrete
  traced locus and sorting by T would fabricate spikes. The test
  `test_phase_envelope_plot_connects_curves_through_critical_point` is kept
  `xfail` (strict=False) as the reminder.
- **BIP panel is diagnostic, not runtime.** `src/pvtapp/main.py` does not
  feed the GUI BIP selection into `RunConfig`. Runtime default is zero-BIP
  unless supplied through config data. This violates the runtime-surface
  standard (`docs/runtime_surface_standard.md` §4) and is tracked as an
  explicit upgrade.
- **PPR78 is kernel-only.** `src/pvtcore/eos/ppr78.py` implements Jaubert &
  Mutelet (2004) with the group interaction table, but no `pvtapp` module
  imports it. Treated as experimental until the numerical output is
  validated against Jaubert literature cases.
- **CVD pressure schedule is step-based.** `CVDConfig.n_steps` still
  requires `>= 5`. CCE and DL now accept explicit descending
  `pressure_points_pa` lists; CVD does not.
- **Flash SS fallback is unaccelerated.** When Michelsen-Newton fails,
  `_ss_flash_loop` runs pure successive substitution. On non-pathological
  failures (contractive SS operator), GDEM acceleration would reduce the
  iteration count 3–5×.
