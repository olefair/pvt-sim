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
The current desktop `pvtapp` GUI surface includes:
- PT flash
- bubble point
- dew point
- phase envelope
- CCE
- differential liberation
- CVD
- swelling test
- separator

For additional packaging details and non-Windows launch routes, see `docs/packaging.md`.

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

Run tests:

```bash
pytest
```

## Install (runtime only)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
```

> Long-term intent: publish wheels to an internal/public index once the thermo kernel stabilizes.
