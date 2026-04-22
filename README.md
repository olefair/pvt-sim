# PVT Simulator (pvt-simulator)

Core thermodynamics + PVT workflows:

- Plus-fraction characterization (starting with Pedersen-style split)
- PR EOS (with mixing rules) + fugacity
- Michelsen-style stability (TPD)
- PT flash (Rachford–Rice + successive substitution)

This repo uses a **src-layout** Python package: `pvtcore`.

## Canonical Documentation

Durable simulator and developer context lives in normal repo docs:

- `docs/architecture.md`
- `docs/development.md`
- `docs/runtime_surface_standard.md`
- `docs/technical_notes.md`
- `docs/numerical_methods.md`
- `docs/input_schema.md`
- `docs/units.md`
- `docs/validation_plan.md`

## Windows quick start

This simulator is intended to run natively on Windows. If you are launching it locally, use the PowerShell route first.

### Install (PowerShell)
```powershell
python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python.exe -m pip install -U pip
python.exe -m pip install -e .[full]
```

`.[full]` is the intended Windows desktop install surface: GUI runtime + SciPy-backed features. If you only want the lighter GUI-only stack, use `python.exe -m pip install -e .[gui]`.

### Launch
```powershell
pvtsim-gui
```

### CLI sanity check
```powershell
pvtsim validate examples\pt_flash_config.json
pvtsim validate examples\swelling_test_config.json
```

### Entry points
- `pvtsim-gui` -> desktop GUI
- `pvtsim` -> CLI entrypoint
- `pvtsim-cli` -> CLI entrypoint

### Current workflow surface

The current desktop `pvtapp` GUI surface exposes the calculations below. Each
one names the method + equation actually wired in the kernel; deeper math
lives in `docs/technical_notes.md` and `docs/numerical_methods.md`.

**PT flash** — two-phase isothermal-isobaric flash. Rachford-Rice for vapor
fraction β via Brent (bracketed so it can't jump the asymptotes a Newton
solver would). Outer successive-substitution loop on K-values, with GDEM
acceleration (General Dominant Eigenvalue Method, Michelsen 1982) kicking in
near the critical point where plain SS slows to linear. Damping engages on
oscillation. Fugacity equality is the convergence criterion.

**Stability analysis** — Michelsen tangent-plane-distance minimization. Seeds
from Wilson K-values (vapor-like and liquid-like trials). Runs before every
flash to prevent convergence to the trivial K = 1 solution when a real phase
split exists (the classical near-critical failure mode).

**Bubble point / dew point** — saturation pressure at fixed T. Solved as the
root of TPD(P) = 0 via Brent, using the stability metric directly rather than
the classical `∑zᵢKᵢ = 1` equation (which can return non-physical roots when
the incipient-phase composition isn't self-consistently iterated). Initial
pressure guess from Wilson-K correlation.

**Phase envelope** — natural-parameter continuation in (P, T, K) space,
alternating bubble and dew solves with adaptive step control based on local
curvature. Critical-point detection monitors `|∑(xᵢ - yᵢ)²| → 0`. *Staged —
continuity through the critical point is currently unreliable;* see the
known-limitations section below.

**CCE (constant composition expansion)** — feed composition and total moles
fixed, cell volume varies with pressure. Runs a flash at each pressure step,
records relative volume V/V_sat, Z-factor, phase fractions, liquid dropout.

**Differential liberation** — below-bubble-point depletion sequence. At each
step: flash the current oil, remove all liberated gas from the cell, update
the feed to the remaining liquid for the next step. Tracks Bo, Bg, RsD,
RsDb, BtD, cumulative gas produced, residual oil density, and per-step
oil/gas compositions. Reference state for the formation volume factors is
the final residual oil flashed to stock-tank conditions (14.65 psia, 60°F).

**CVD (constant volume depletion)** — retrograde condensate analog to DL. At
each step, remove only enough gas to restore the cell to its initial volume
(rather than all gas). Solves an extra coupled constraint for the gas
removal fraction per step.

**Swelling test** — fixed temperature, fixed injection-gas composition. Each
enrichment step re-solves bubble pressure on the swollen mixture, tracking
swelling factor and saturated liquid density vs enrichment ratio. Current
runtime slice is single-contact enrichment only (not slimtube / MMP /
multi-contact miscibility).

**Separator (multistage train)** — sequential PT flashes at user-specified
stage conditions, cascading mass balance stage-to-stage, final stock-tank
flash giving GOR, API gravity, and shrinkage.

**TBP characterization** — plus-fraction splitting and pseudo-component
property assignment. Default split is Pedersen exponential (`ln zₙ = A + B·MWₙ`
solved via 2D Newton enforcing mass + MW balance); Katz exponential,
Lohrenz quadratic-exponential, and Whitson gamma are also available.
Critical properties (Tc, Pc, Vc) from Riazi-Daubert (1987) or Kesler-Lee
(1976); acentric factor from Edmister or Kesler-Lee; normal boiling point
from Soreide (1989); parachor from Fanchi.

#### EOS / mixing rules

Three cubic EOS options: **Peng-Robinson 1976** (classical quadratic
kappa-correlation), **Peng-Robinson 1978** (heavy-end extended cubic kappa,
matches the GPA reservoir-engineering program), and **Soave-Redlich-Kwong**.
All three use **van der Waals one-fluid mixing** with binary interaction
parameters `kᵢⱼ` (default zero unless supplied). The cubic Z-equation is
solved **analytically via Cardano's formula** (depressed-cubic substitution
+ trigonometric or cube-root branch depending on discriminant) rather than
iteratively — O(1) and machine-precision with no convergence pathologies
near the critical point. Fugacity coefficients are computed from the standard
PR mixture expression; domain guards (`Z > B`, `Z + (1−√2)B > 0`) are
enforced to prevent non-physical states.

See `src/pvtapp/capabilities.py` for the authoritative wired lists and
`src/pvtcore/eos/README.md` for full EOS-level detail.

#### Post-flash properties

- **Density** — from the EOS Z-factor: ρ = P / (Z R T) in mol/m³, then
  multiplied by phase MW for kg/m³. Optional Peneloux-style volume
  translation available but not default-on.
- **Viscosity** — Lohrenz-Bray-Clark (1964). Density-based correlation so
  it's smooth through the two-phase region and uses reduced density
  ρ_r = ρ/ρ_c. Dilute-gas viscosity from Stiel-Thodos corresponding-states
  for the low-density limit.
- **Interfacial tension** — Weinaug-Katz parachor form. Only meaningful for
  two-phase states; used by the nano-confinement capillary-pressure
  coupling if that path is exercised.

#### Numerical-methods summary

| Solver | Method | Used for |
|---|---|---|
| Cubic Z | Cardano's formula (analytical) | EOS root at any (P, T, composition) |
| Rachford-Rice | Brent (bracketed root-finder) | Vapor fraction β given K-values |
| Flash outer loop | Successive substitution + GDEM acceleration | K-value update to fugacity equality |
| Stability | Michelsen TPD SS, Wilson-K trials | Single-phase vs split detection |
| Saturation pressure | Brent on TPD(P) = 0 | Bubble / dew points |
| Plus-fraction fit | 2D Newton with overflow guards | Pedersen `(A, B)` constants |
| General root-find | Newton-Raphson with Armijo line search | Saturation, envelope continuation, tuning |

Convergence tolerances live in `docs/numerical_methods.md` (summary table at
the end of that doc).

### Outputs and run history
- Every completed run is persisted by the worker to
  `%LOCALAPPDATA%/PVTSimulator/runs/<timestamp>_<id>/` on Windows (or
  `~/.pvtsimulator/runs/<timestamp>_<id>/` elsewhere). Config and result are
  loadable via `pvtapp.job_runner.load_run_config` /
  `pvtapp.job_runner.load_run_result`.
- On reopen, `pvtsim-gui` auto-restores the most recent *completed* run into
  the inputs + right-rail + text output + plot surfaces. Cancelled and failed
  runs are skipped. A first launch with no saved runs is a normal case.
- The run log sidebar exposes the persisted history for re-display and
  input-restore without re-running.
- Results can be exported to a multi-sheet `.xlsx` workbook via
  `pvtapp.excel_export.export_result_to_excel`. Every sheet is written in
  US-petroleum display units (psia, °F) so the workbook matches what the
  user sees in the GUI and in the text / CSV exports.

### I/O default units
GUI, text output, and Excel export default to US-petroleum display units
(psia, °F, bbl). The kernel continues to operate on canonical internal SI
(Pa, K, mol) — conversions happen only at I/O boundaries. See `docs/units.md`
for the full contract.

For additional packaging details and non-Windows launch routes, see `docs/packaging.md`.

## Known limitations

- **Phase envelope at the critical point.** The current plotter intentionally
  does not inject the detected critical point into the bubble/dew polylines
  (see the comment in `results_view.py._plot_phase_envelope._curve_xy`).
  `test_phase_envelope_plot_connects_curves_through_critical_point` is kept
  `xfail` until the envelope-accuracy/continuity redesign lands.
- **Pre-existing headless test failures.** 9 tests are known-failing on
  `main` as of 2026-04-15 — see `docs/development.md` for the enumerated
  list. These do not block new work; do not silently reframe a new failure
  as pre-existing without checking the baseline.
- **CVD schedule.** `CVDConfig.n_steps` currently requires `>= 5`; explicit
  pressure lists are not yet supported at that surface (CCE and DL now do
  support explicit descending `pressure_points_pa` lists).
- **BIP GUI panel.** The current desktop BIP panel is diagnostic and does not
  feed into `RunConfig`. Runtime default is zero-BIP unless supplied via
  config data. See `docs/runtime_surface_standard.md` for the standing rule.
- **PPR78 kernel path.** `src/pvtcore/eos/ppr78.py` implements the Jaubert
  group-contribution temperature-dependent BIP model but is not imported by
  the `pvtapp` runtime. Treat it as experimental until validation and GUI
  wiring land.
- **CI workflows.** `.github/workflows/*.yml` are present on disk but
  gitignored while the repo is in a focused execution phase. The active
  merge gate is `python scripts/run_premerge_checks.py --baseline-only`
  run locally. See `docs/development.md`.

## Roadmap

Near-term upgrades with scoped blueprints or explicit acknowledgment in the
docs set:

- **Fast phase envelope solver** — direct Michelsen-style Newton replacing
  the current TPD-plus-Brent inner loop. Target: <0.5 s for a binary PR
  envelope, <5 s for a 15-component characterized fluid, no public API
  changes. See `docs/blueprints/fast_phase_envelope.md`.
- **Selective GDEM acceleration of the flash SS fallback** — classify why
  Newton failed and route non-pathological failures through GDEM-accelerated
  SS (Michelsen 1982) for a 3–5× speedup, keeping pure SS for pathological
  regimes. No public API changes. See
  `docs/blueprints/selective_gdem_flash_ss_fallback.md`.
- **Phase envelope critical-point redesign** — resolve the parked
  connectivity xfail with a redesign that either injects the detected
  critical point cleanly into the polylines or documents the traced-locus
  behavior as intended.
- **BIP matrix UI** — promote the diagnostic BIP panel into a real runtime
  control that feeds `RunConfig`, or explicitly demote/remove per
  `docs/runtime_surface_standard.md` §4.
- **PPR78 runtime wiring + validation** — exercise the kernel PPR78 module
  against Jaubert literature cases, then wire into the runtime EOS surface.
- **Recommendation panel persistence** — persist GUI recommendation /
  advisory state across sessions alongside the restored last run.
- **Assignment-aware desktop path** — close the remaining PETE 665 baseline
  gaps (assignment-case loader, initials-based temperature picker,
  CVD explicit pressure schedule). See
  `docs/validation/pete665_assignment_baseline.md`.

## Install (development)

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[dev]'
```

This `dev` extra includes the headless developer tooling plus the approved
permissive validation backends (`thermo`, `thermopack`). If you also want to
launch the desktop app or run GUI/widget tests, install:

```bash
python -m pip install -e '.[gui,dev]'
```

For a full local validation surface on Windows, the intended reset/install
command is:

```powershell
python.exe -m pip install -e .[full,dev]
```

Verification entrypoints (details in `docs/development.md`):

| Surface | Command |
|--------|---------|
| Routine headless | `pytest` |
| CI / integration-root gate (`--baseline-only`, `--integration-root`) | `python scripts/run_premerge_checks.py --baseline-only` — strong regression signal, then routine `pytest` for full headless suite (see `docs/development.md`) |
| Lane pre-merge (baseline + touched-surface) | `python scripts/run_premerge_checks.py` |
| Full validation | `python scripts/run_full_validation.py` |

## Install (runtime only)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

> Long-term intent: publish wheels to an internal/public index once the thermo kernel stabilizes.
