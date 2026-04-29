# your-project-name

Short project description.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

## Run

```powershell
python -m your_package_name
your-project --help
```

## Test

```powershell
pytest
```

## Environment

Safe tracked defaults live in `.env.defaults`.
Machine-local overrides belong in `.env`, which stays ignored.
