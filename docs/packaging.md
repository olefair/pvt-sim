# Windows Packaging Guide

## Prereqs
- Windows 11
- PowerShell 7
- Python 3.10+ on PATH
- (Installer) Inno Setup 6

## Create Venv
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Install Dependencies
GUI-only desktop runtime:
```powershell
python -m pip install -e ".[gui]"
```

Full desktop runtime (GUI + SciPy-backed features):
```powershell
python -m pip install -e ".[full]"
```

Developer tooling with GUI:
```powershell
python -m pip install -e ".[gui,dev]"
```

## Run From Source
```powershell
pvtsim-gui
pvtsim validate examples\pt_flash_config.json
```

## Build (PyInstaller)
```powershell
.\tools\build_windows.ps1
```

Optional one-file build:
```powershell
.\tools\build_windows.ps1 -OneFile
```

Skip building the CLI executable:
```powershell
.\tools\build_windows.ps1 -SkipCli
```

## Build Installer (Inno Setup)
```powershell
.\tools\build_installer.ps1
```

Installer output: `dist_installer\`.

## Troubleshooting
- PySide6 plugin errors at runtime (missing Qt platform plugins): rebuild and ensure the PySide6 hooks are included, and confirm `dist\pvtsim\PySide6\plugins` exists after build.
- Matplotlib backend errors (e.g., QtAgg missing): ensure `matplotlib` is installed and rebuild; the spec includes `matplotlib.backends.backend_qtagg`.
- Missing SciPy: SciPy is optional in the base install; features that rely on SciPy will raise a clear import error if used. Install the full desktop/runtime surface with `pip install -e ".[full]"`.
- Logs: `build_logs\build_windows.log` and `build_logs\build_installer.log`.
