# PVT-SIM PETE 665 Submission

Compact course-scope PVT simulator centered on the methods covered in
`LECTURE_SLIDES_MERGED.md`.

## Included scope

- Cubic EOS: Peng-Robinson 1976, Peng-Robinson 1978, SRK
- Phase-equilibrium workflows: stability, PT flash, bubble point, dew point, phase envelope
- Lab workflows: CCE, differential liberation, CVD, separator, swelling
- Heavy-end workflows: Pedersen, Katz, Lohrenz splitting; Whitson lumping
- Post-flash properties: density, viscosity (LBC), interfacial tension (parachor)

## Repo layout

- `src/pvtcore/`: thermodynamic kernel
- `src/pvtapp/`: GUI and CLI surface
- `examples/`: minimal sample inputs
- `scripts/run_pete665_assignment.py`: assignment runner

## Install

```powershell
python.exe -m venv .venv
.\.venv\Scripts\Activate.ps1
python.exe -m pip install -U pip
python.exe -m pip install -e .[full]
```

Use `.[gui]` instead of `.[full]` if you do not need SciPy-backed features.

## Run

```powershell
python scripts\run_pete665_assignment.py --initials TANS
pvtsim validate examples\pt_flash_config.json
pvtsim-gui
```

Entry points:

- `pvtsim`
- `pvtsim-cli`
- `pvtsim-gui`

## Verification

```powershell
pytest -q
```

## Notes

- The desktop app now opens on `Bubble Point` with `PR78` selected so the first visible workflow matches the PETE 665 submission path.
- Heavy-end lumping is restricted to `whitson`.
- External comparison harnesses and validation backends are intentionally excluded from the submission surface.
- Core equations, solver details, and units live in `docs/technical_notes.md`, `docs/numerical_methods.md`, `docs/input_schema.md`, and `docs/units.md`.
