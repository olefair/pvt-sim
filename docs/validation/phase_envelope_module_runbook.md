# Phase Envelope Module Runbook

This runbook is the shortest path to a reproducible, auditable
phase-envelope validation pass.

Use it when you want the module to be:

- deterministic
- numerically self-consistent
- signed off against the repo's current validation policy

## What Counts As Real Signoff

The repo's active signoff surface is still:

1. same-equation scalar benchmarks
2. external pure-component and literature scalar anchors
3. runtime-agreement checks
4. continuation release gates
5. optional ThermoPack-backed full-envelope comparison when available

DWSIM is **not** part of the active validation engine. It is useful for local
batch spot-checking and triage, but it does not replace the repo's approved
signoff authorities.

See also:

- [phase_envelope_validation_matrix.md](/Users/olefa/.codex/worktrees/606a/pvt-sim_canon/docs/validation/phase_envelope_validation_matrix.md)
- [external_validation_engine.md](/Users/olefa/.codex/worktrees/606a/pvt-sim_canon/docs/validation/external_validation_engine.md)

## Canonical Breadth Roster

The explicit-component breadth roster now lives in:

- [phase_envelope_breadth_roster.json](/Users/olefa/.codex/worktrees/606a/pvt-sim_canon/scripts/data/phase_envelope_breadth_roster.json)

It contains the canonical 17-case family / topology surface:

1. `co2_rich_regression_gas`
2. `dry_gas_A`
3. `dry_gas_B_sour`
4. `gas_condensate_A`
5. `gas_condensate_B_sour`
6. `co2_rich_gas_A`
7. `co2_rich_gas_B`
8. `volatile_oil_A`
9. `volatile_oil_B`
10. `black_oil_A`
11. `black_oil_B`
12. `sour_oil_A`
13. `sour_oil_B`
14. `c2_c3_equal_molar`
15. `c1_c10_equal_molar`
16. `simple_dry_gas`
17. `co2_c3_binary`

That file is the source of truth for any future manual entry, local DWSIM
batch, or derived validation helper.

## Repo Signoff Command

Run the repo's canonical validation stack:

```powershell
python scripts/run_phase_envelope_validation.py --with-slow
```

Optional extra lanes:

```powershell
python scripts/run_phase_envelope_validation.py --with-slow --with-thermopack
python scripts/run_phase_envelope_validation.py --with-slow --with-thermopack --with-mi-proxy
```

To inspect the exact lane order without running it:

```powershell
python scripts/run_phase_envelope_validation.py --list
```

To target one expensive lane without rerunning the whole stack:

```powershell
python scripts/run_phase_envelope_validation.py --only release-gates --with-slow
```

## Local DWSIM Batch Helper

The local DWSIM DLL helper lives at:

- [dwsim_batch_phase_envelopes.py](/Users/olefa/.codex/worktrees/606a/pvt-sim_canon/scripts/dwsim_batch_phase_envelopes.py)

This helper can:

- populate numbered material streams from the canonical roster
- save a populated `.dwxmz`
- export one phase-envelope CSV per stream
- write summary and failure CSVs

### Preconditions

1. DWSIM installed locally, with DLLs under `%LOCALAPPDATA%\\DWSIM`
2. `pythonnet` installed in the Python you will use to run the script
3. a template flowsheet with:
   - the required compounds loaded
   - a `Peng-Robinson (PR)` package
   - numbered material streams matching the roster tags (`1` through `17`)

### Populate a Template Flowsheet

```powershell
python scripts/dwsim_batch_phase_envelopes.py ^
  --flowsheet C:\path\to\template.dwxmz ^
  --write-streams ^
  --populate-only ^
  --save-flowsheet C:\path\to\phase_envelope_breadth_populated.dwxmz
```

### Populate and Export in One Pass

```powershell
python scripts/dwsim_batch_phase_envelopes.py ^
  --flowsheet C:\path\to\template.dwxmz ^
  --write-streams ^
  --save-flowsheet C:\path\to\phase_envelope_breadth_populated.dwxmz ^
  --out C:\path\to\dwsim_phase_envelope_batch
```

### Export From an Already Populated Flowsheet

```powershell
python scripts/dwsim_batch_phase_envelopes.py ^
  --flowsheet C:\path\to\phase_envelope_breadth_populated.dwxmz ^
  --out C:\path\to\dwsim_phase_envelope_batch
```

### Run a Subset Only

```powershell
python scripts/dwsim_batch_phase_envelopes.py ^
  --flowsheet C:\path\to\phase_envelope_breadth_populated.dwxmz ^
  --out C:\path\to\dwsim_phase_envelope_batch ^
  --tags 2 4 11
```

## What Still Needs Human Input For Full Physical-Fidelity Signoff

The scripts now cover deterministic execution and repeatable validation
orchestration. What they do **not** solve on their own is the remaining
reference-authority gap for full-family physical fidelity.

To call the module truly signed off across the broad field-fluid families, we
still need at least one of the following:

- acceptance that ThermoPack-backed heavy / sour family cases are sufficient
  external signoff authority for those families
- or authoritative heavy-end and sour / acid-gas reference cases with frozen
  characterization knobs that can enter the repo's approved external corpus

Without that, the repo can still be deterministic and structurally correct,
but full-family physical-accuracy signoff remains partially open.
