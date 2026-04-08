# PVT Simulator (pvt-simulator)

Core thermodynamics + PVT workflows:

- Plus-fraction characterization (starting with Pedersen-style split)
- PR EOS (with mixing rules) + fugacity
- Michelsen-style stability (TPD)
- PT flash (Rachford–Rice + successive substitution)

This repo uses a **src-layout** Python package: `pvtcore`.

## Windows quick start

This simulator is intended to run natively on Windows. If you are launching it locally, use the PowerShell route first.

### Install (PowerShell)
```powershell
python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python.exe -m pip install -U pip
python.exe -m pip install -e .[full]
```

### Launch
```powershell
pvtsim-gui
```

### CLI sanity check
```powershell
pvtsim validate examples\pt_flash_config.json
```

### Entry points
- `pvtsim-gui` -> desktop GUI
- `pvtsim` -> CLI entrypoint
- `pvtsim-cli` -> CLI entrypoint

### Current workflow surface
The current `pvtapp` workflow surface includes:
- PT flash
- bubble point
- dew point
- phase envelope
- CCE
- differential liberation
- CVD
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
