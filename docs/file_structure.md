# Planned File Structure

This is the target file structure for the complete PVT-SIM project. Files and folders should be created incrementally as modules are implemented—do not create empty placeholders.

```
pvt-sim/
├── README.md                          # Project overview, quick start
├── AGENTS.md                          # Repo-local execution notes for coding agents
├── LICENSE                            # MIT or similar
├── pyproject.toml                     # Project config, dependencies
├── .gitignore                         # Python, IDE, OS ignores
├── .pre-commit-config.yaml            # Linting, type checking hooks
│
├── docs/
│   ├── architecture.md                # System design, data flow
│   ├── development.md                 # Stack, coding standards, verification contract
│   ├── numerical_methods.md           # Algorithm specifications
│   ├── validation_plan.md             # Testing strategy
│   ├── references.md                  # Primary literature sources
│   └── file_structure.md              # This file
│
├── data/
│   ├── pure_components/
│   │   ├── components.json            # N₂, CO₂, H₂S, C₁-C₁₀, isomers
│   │   └── sources.md                 # Data provenance (NIST, DIPPR)
│   ├── correlation_coeffs/            # Correlation constants
│   ├── parachor/                      # Parachor values
│   └── bip_defaults/                  # Default BIP matrices
│
├── src/
│   ├── pvtcore/
│   │   ├── __init__.py
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── constants.py           # R, standard conditions
│   │   │   ├── units.py               # Conversion functions
│   │   │   ├── typing.py              # Type aliases, Protocols
│   │   │   ├── errors.py              # Custom exceptions
│   │   │   └── numerics/
│   │   │       ├── __init__.py
│   │   │       ├── brent.py           # Bracketed root finding
│   │   │       ├── newton.py          # Newton-Raphson
│   │   │       ├── damping.py         # Step damping strategies
│   │   │       └── convergence.py     # Convergence criteria
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── component.py           # Component dataclass
│   │   │   ├── mixture.py             # Mixture class
│   │   │   ├── eos_params.py          # EOS parameter containers
│   │   │   ├── phase.py               # Phase dataclass
│   │   │   └── results.py             # Result containers
│   │   │
│   │   ├── characterization/
│   │   │   ├── __init__.py
│   │   │   ├── plus_splitting/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── pedersen.py        # Exponential: ln(zₙ) = A + B·MWₙ
│   │   │   │   ├── katz.py            # Katz correlation
│   │   │   │   ├── lohrenz.py         # Quadratic exponential
│   │   │   │   └── whitson_gamma.py   # Gamma distribution
│   │   │   ├── scn_properties.py      # Generalized SCN tables
│   │   │   ├── lumping.py             # Whitson lumping
│   │   │   └── delumping.py           # K-value interpolation
│   │   │
│   │   ├── correlations/
│   │   │   ├── __init__.py
│   │   │   ├── tb.py                  # Soreide (1989)
│   │   │   ├── critical_props/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── base.py            # Protocol definition
│   │   │   │   ├── riazi_daubert.py   # Tc, Pc, Vc
│   │   │   │   ├── kesler_lee.py      # Tc, Pc, ω
│   │   │   │   └── cavett.py          # Alternative
│   │   │   ├── acentric.py            # Edmister, Kesler-Lee
│   │   │   └── parachor.py            # Fanchi from MW
│   │   │
│   │   ├── eos/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # CubicEOS Protocol
│   │   │   ├── mixing_rules.py        # van der Waals, BIPs
│   │   │   ├── cubic_solver.py        # Cardano's formula
│   │   │   ├── peng_robinson.py       # PR (1976)
│   │   │   ├── srk.py                 # SRK (1972)
│   │   │   └── volume_translation.py  # Peneloux correction
│   │   │
│   │   ├── stability/
│   │   │   ├── __init__.py
│   │   │   ├── wilson.py              # Wilson K-value correlation
│   │   │   └── tpd.py                 # Michelsen TPD
│   │   │
│   │   ├── flash/
│   │   │   ├── __init__.py
│   │   │   ├── rachford_rice.py       # RR solver (Brent)
│   │   │   ├── pt_flash.py            # Isothermal flash
│   │   │   ├── saturation.py          # Bubble/dew point
│   │   │   └── acceleration/
│   │   │       ├── __init__.py
│   │   │       └── gdem.py            # Dominant eigenvalue
│   │   │
│   │   ├── envelope/
│   │   │   ├── __init__.py
│   │   │   ├── trace.py               # Envelope tracing
│   │   │   ├── critical_point.py      # Critical point location
│   │   │   └── quality_lines.py       # Iso-volume curves
│   │   │
│   │   ├── properties/
│   │   │   ├── __init__.py
│   │   │   ├── density.py             # From Z with vol. trans.
│   │   │   ├── viscosity_lbc.py       # LBC correlation
│   │   │   └── ift_parachor.py        # Parachor method
│   │   │
│   │   ├── experiments/
│   │   │   ├── __init__.py
│   │   │   ├── cce.py                 # Constant Composition Expansion
│   │   │   ├── dl.py                  # Differential Liberation
│   │   │   ├── cvd.py                 # Constant Volume Depletion
│   │   │   └── separators.py          # Multi-stage separator
│   │   │
│   │   ├── confinement/
│   │   │   ├── __init__.py
│   │   │   ├── capillary.py           # Pc = 2σ/r
│   │   │   ├── confined_flash.py      # Flash with Pⱽ = Pᴸ + Pc
│   │   │   └── confined_envelope.py   # Shifted envelope
│   │   │
│   │   ├── tuning/
│   │   │   ├── __init__.py
│   │   │   ├── parameters.py          # Tunable params, bounds
│   │   │   ├── objectives.py          # Objective function
│   │   │   ├── datasets.py            # Experimental data containers
│   │   │   └── regression.py          # Levenberg-Marquardt
│   │   │
│   │   └── io/
│   │       ├── __init__.py
│   │       ├── import_csv.py          # CSV parsing
│   │       ├── import_excel.py        # Excel parsing
│   │       ├── export_csv.py          # CSV export
│   │       └── report_templates/      # PVT report formats
│   │
│   └── pvtapp/
│       ├── __init__.py
│       ├── main.py                    # Application entry point
│       ├── ui/                        # User interface
│       ├── viewmodels/                # UI state management
│       ├── plotting/                  # Matplotlib wrappers
│       └── resources/                 # Assets, templates
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # pytest fixtures
│   ├── unit/
│   │   ├── test_cubic_solver.py
│   │   ├── test_rachford_rice.py
│   │   ├── test_fugacity.py
│   │   └── ...
│   ├── integration/
│   │   ├── test_flash_workflow.py
│   │   ├── test_characterization.py
│   │   └── ...
│   ├── regression/
│   │   ├── test_vs_mi_pvt.py
│   │   ├── test_vs_experiment.py
│   │   └── ...
│   └── data/
│       ├── experimental/              # VLE data, PVT reports
│       ├── mi_pvt_reference/          # MI PVT output for comparison
│       └── nist/                      # Pure component validation
│
├── examples/
│   ├── notebooks/
│   │   ├── 01_basic_flash.ipynb
│   │   ├── 02_phase_envelope.ipynb
│   │   └── 03_confinement.ipynb
│   └── sample_fluids/
│       ├── black_oil.json
│       ├── volatile_oil.json
│       └── gas_condensate.json
│
└── scripts/
    ├── run_phase_envelope.py          # CLI for envelope generation
    ├── run_cce.py                     # CLI for CCE simulation
    └── benchmark_flash.py             # Performance testing
```

## Implementation Order

### Phase 1: Foundation (Weeks 1-4)
- `core/` (all files)
- `models/` (all files)
- `data/pure_components/`
- `eos/cubic_solver.py`, `eos/peng_robinson.py`
- Basic tests

### Phase 2: Characterization (Weeks 5-8)
- `characterization/` (all files)
- `correlations/` (all files)
- `data/correlation_coeffs/`, `data/bip_defaults/`

### Phase 3: Flash & Stability (Weeks 9-12)
- `stability/` (all files)
- `flash/` (all files)
- `envelope/` (all files)

### Phase 4: Properties & Experiments (Weeks 13-16)
- `properties/` (all files)
- `experiments/` (all files)
- `data/parachor/`

### Phase 5: Confinement & Tuning (Weeks 17-20)
- `confinement/` (all files)
- `tuning/` (all files)

### Phase 6: Application Layer (Weeks 21+)
- `pvtapp/` (all files)
- `io/` (all files)
- `examples/`, `scripts/`
