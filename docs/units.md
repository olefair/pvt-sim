# Units Convention and Contract

## Overview

This document defines the **canonical internal units** used throughout the PVT-SIM codebase. All thermodynamic computations must use these units internally. Input files and user interfaces may accept other units, but conversions must occur at I/O boundaries before data enters solver code.

**Golden Rule:** No EOS, flash, or envelope function should ever receive non-canonical units.

### Two layers, one contract

The units contract is split into two layers that must not be confused:

- **Internal (kernel) layer** — canonical SI: Pa, K, g/mol, m³/mol, kg/m³,
  Pa·s, N/m. Everything under `src/pvtcore/` operates on these units.
  This is the canonical internal side of the contract and is non-negotiable.
- **I/O boundary layer** — the `pvtapp` runtime *defaults to* US-petroleum
  display units for user-facing surfaces: **pressure in psia, temperature
  in °F, volumes in bbl** where appropriate. The GUI widgets, the Excel
  export (`src/pvtapp/excel_export.py`), the text output, and the CSV
  export all render these units by default. Input parsing accepts the
  full allowed-input set documented below; conversion into canonical SI
  happens at the schema / config-intake boundary through helpers such as
  `pvtapp.schemas.pressure_from_pa` and `temperature_from_k` (and their
  inverses).

Nothing in `pvtcore` has changed — the kernel still sees Pa and K only.
The US-petroleum default lives entirely in the boundary translation layer
and in the presentation widgets.

---

## Canonical Internal Units

All core modules (`pvtcore/*`) must use these units:

| Quantity | Unit | Symbol | Notes |
|----------|------|--------|-------|
| **Temperature** | Kelvin | K | Absolute temperature scale |
| **Pressure** | Pascal | Pa | SI base unit (1 Pa = 1 N/m²) |
| **Molecular Weight** | grams per mole | g/mol | Current component DB standard |
| **Critical Volume** | cubic meters per mole | m³/mol | Molar volume |
| **Density** | kilograms per cubic meter | kg/m³ | Mass density |
| **Viscosity** | Pascal-second | Pa·s | Dynamic viscosity |
| **Interfacial Tension** | Newtons per meter | N/m | Surface tension |
| **Specific Gravity** | dimensionless | - | Relative to water at 60°F |
| **Boiling Temperature** | Kelvin | K | Normal boiling point at 1 atm |
| **Critical Temperature** | Kelvin | K | - |
| **Critical Pressure** | Pascal | Pa | - |
| **Acentric Factor** | dimensionless | ω | Pitzer's acentric factor |

---

## Unit Metadata in Component Database

The component database (`data/pure_components/components.json`) includes explicit unit metadata for all physical properties:

```json
{
  "Tc": 304.18,
  "Tc_unit": "K",
  "Pc": 7380000,
  "Pc_unit": "Pa",
  "Vc": 9.19e-05,
  "Vc_unit": "m3/mol",
  "MW": 44.0095,
  "MW_unit": "g/mol",
  "Tb": 194.7,
  "Tb_unit": "K"
}
```

**Requirement:** All unit metadata fields (`*_unit`) must specify canonical units. The validation system enforces this.

---

## Allowed Units for Input Parsing

When implementing input parsers or UI layers, the following units may be accepted and converted to canonical form:

### Temperature
- `K` (Kelvin) - canonical, no conversion
- `C` (Celsius) - convert: K = C + 273.15
- `F` (Fahrenheit) - convert: K = (F - 32) × 5/9 + 273.15
- `R` (Rankine) - convert: K = R × 5/9

### Pressure
- `Pa` (Pascal) - canonical, no conversion
- `kPa` (kiloPascal) - convert: Pa = kPa × 1000
- `MPa` (megaPascal) - convert: Pa = MPa × 1e6
- `bar` (bar) - convert: Pa = bar × 1e5
- `atm` (atmosphere) - convert: Pa = atm × 101325
- `psia` (pounds per square inch absolute) - convert: Pa = psia × 6894.76

### Molecular Weight
- `g/mol` - canonical, no conversion
- `kg/kmol` - numerically identical to g/mol

### Volume
- `m3/mol` or `m^3/mol` - canonical, no conversion
- `cm3/mol` or `cc/mol` - convert: m³/mol = cm³/mol × 1e-6
- `L/mol` - convert: m³/mol = L/mol × 1e-3

### Density
- `kg/m3` or `kg/m^3` - canonical, no conversion
- `g/cm3` or `g/cc` - convert: kg/m³ = g/cm³ × 1000

---

## Conversion Policy

### Where Conversions Must Occur

1. **Input Boundaries:**
   - File parsers (JSON, CSV, Excel)
   - API endpoints
   - CLI argument parsing
   - UI input forms

2. **Output Boundaries:**
   - Report generation
   - Plot labels
   - API responses
   - UI display

### Where Conversions Must NOT Occur

- Inside EOS implementations (`pvtcore/eos/`)
- Inside flash algorithms (`pvtcore/flash/`)
- Inside stability analysis (`pvtcore/stability/`)
- Inside property calculations (`pvtcore/properties/`)
- Anywhere in `pvtcore/models/` data structures

**Centralization:** If unit conversions are needed, implement them in a dedicated `pvtcore/core/units.py` module. Do not scatter conversion logic throughout solver code.

---

## Validation System

The units validation system (`scripts/validate_units.py`) enforces this contract:

### Range Checks (Detect Unit Scale Errors)

These checks catch common errors like storing kPa as Pa:

| Property | Error Range | Warning Range | Typical Issue |
|----------|-------------|---------------|---------------|
| `Tc` (K) | < 50 or > 2000 | - | Celsius input not converted |
| `Pc` (Pa) | ≤ 0 or non-finite | < 1e5 or > 2e8 | kPa stored as Pa |
| `Vc` (m³/mol) | < 1e-6 or > 1e-2 | - | cm³/mol not converted |
| `MW` (g/mol) | < 1 or > 2000 | - | Invalid molecular weight |
| `Tb` (K) | < 50 or > 2500 | - | Celsius input not converted |
| `omega` | non-finite | < -0.5 | Unusual acentric factor |

### Unit Metadata Validation

For properties with explicit `*_unit` fields:
- Must match canonical unit exactly
- No abbreviation variations allowed (e.g., "pascal" vs "Pa")
- Case-sensitive matching

---

## Daily Workflow

After any edits to component database or input files:

```powershell
python .\scripts\validate_modules.py
```

This runs all validators including:
- Component schema validation
- Group consistency checks
- **Units contract validation** (new)
- Integration tests

**Fail Fast:** Fix unit errors before running tests or solver code.

---

## Common Pitfalls

### 1. kPa Landmine
```python
# WRONG: User provides kPa, stored directly
component["Pc"] = 4600  # Actually 4600 kPa = 4.6 MPa

# CORRECT: Convert at input boundary
component["Pc"] = 4600 * 1000  # Now 4,600,000 Pa
```

### 2. Celsius/Kelvin Confusion
```python
# WRONG: Temperature from user in Celsius
Tc = 31.1  # Propane Tc in °C

# CORRECT: Convert immediately
Tc = 31.1 + 273.15  # 304.25 K
```

### 3. Volume Units
```python
# WRONG: Critical volume from correlation in cm³/mol
Vc = 200  # cm³/mol

# CORRECT: Convert to m³/mol
Vc = 200 * 1e-6  # 2e-4 m³/mol
```

### 4. Mixed Units in Calculations
```python
# WRONG: Mixing pressure units in equation
R = 8.314  # J/(mol·K)
P_bar = 100
T_K = 400
V = R * T_K / P_bar  # WRONG! Dimensionally inconsistent

# CORRECT: Use canonical units throughout
P_Pa = 100 * 1e5  # Convert bar to Pa
V = R * T_K / P_Pa  # m³/mol
```

---

## Type Hints for Physical Quantities

When writing function signatures, document units in the docstring:

```python
def peng_robinson_eos(
    T: float,
    P: float,
    components: List[Component],
) -> CubicEOSResult:
    """
    Solve Peng-Robinson equation of state.

    Parameters
    ----------
    T : float
        Temperature [K] - MUST BE IN KELVIN
    P : float
        Pressure [Pa] - MUST BE IN PASCAL
    components : List[Component]
        Components with properties in canonical units

    Returns
    -------
    CubicEOSResult
        Z-factor and molar volume [m³/mol]
    """
```

---

## Enforcement

1. **Validation Scripts:** Run before every commit
2. **CI Integration:** Automated checks on all PRs
3. **Type Checking:** Use `mypy` to catch dimension errors where possible
4. **Code Review:** Reviewers must verify units at I/O boundaries
5. **Documentation:** Every physical quantity must document its units

---

## References

- **NIST Reference Fluid Thermodynamic and Transport Properties Database (REFPROP)**
- **International System of Units (SI)** - BIPM
- **Whitson & Brulé (2000)** - Phase Behavior, Appendix A: Units and Conversions

---

## Revision History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-03 | 1.0 | Initial canonical units contract |
