#!/usr/bin/env python3
"""
Validate units contract across the repository.

This script enforces canonical internal units and detects common unit scale errors
(e.g., kPa accidentally stored as Pa, Celsius as Kelvin).

Run from repo root:
    python scripts/validate_units.py

Exit codes:
    0 - All validations passed
    1 - Errors found (unit contract violations)
    2 - Warnings only (suspicious but not fatal)
"""

from __future__ import annotations

import argparse
import json
import math
import numbers
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# ==============================================================================
# Canonical Units Contract
# ==============================================================================

CANONICAL_UNITS = {
    "Tc": "K",
    "Pc": "Pa",
    "Vc": "m3/mol",
    "MW": "g/mol",
    "Tb": "K",
    "omega": None,  # dimensionless, no unit field expected
}

ALLOWED_PRESSURE_UNITS = {"Pa", "kPa", "MPa", "bar", "atm", "psia"}
ALLOWED_TEMPERATURE_UNITS = {"K", "C", "F", "R"}
ALLOWED_VOLUME_UNITS = {"m3/mol", "cm3/mol", "L/mol"}
ALLOWED_MW_UNITS = {"g/mol", "kg/kmol"}

# ==============================================================================
# Range Checks for Sanity (Detect Unit Scale Errors)
# ==============================================================================

# Property: (min_error, max_error, min_warn, max_warn, typical_issue)
RANGE_CHECKS = {
    "Tc": {
        "error_min": 2.0,  # Allow cryogenic gases like He (Tc ~5K), H2 (Tc ~33K)
        "error_max": 2000.0,
        "typical_issue": "Celsius input not converted to Kelvin",
    },
    "Pc": {
        "error_min": 0.0,  # Must be positive
        "warn_min": 1e5,  # 0.1 MPa
        "warn_max": 2e8,  # 200 MPa
        "typical_issue": "Looks like kPa; multiply by 1000 to convert to Pa",
    },
    "Vc": {
        "error_min": 1e-6,
        "error_max": 1e-2,
        "typical_issue": "cm³/mol not converted; multiply by 1e-6 for m³/mol",
    },
    "MW": {
        "error_min": 1.0,
        "error_max": 2000.0,
        "typical_issue": "Invalid molecular weight",
    },
    "Tb": {
        "error_min": 2.0,  # Allow cryogenic gases like He (Tb ~4K), H2 (Tb ~20K)
        "error_max": 2500.0,
        "typical_issue": "Celsius input not converted to Kelvin",
    },
    "omega": {
        "warn_min": -0.5,
        "typical_issue": "Unusual acentric factor",
    },
}


# ==============================================================================
# Utility Functions
# ==============================================================================


def is_numeric(val: Any) -> bool:
    """Check if value is a finite numeric type."""
    return isinstance(val, numbers.Real) and math.isfinite(float(val))


def check_range(
    prop_name: str,
    value: float,
    component_id: str,
) -> Tuple[List[str], List[str]]:
    """
    Check if property value is within expected range.

    Returns
    -------
    errors : List[str]
        Hard errors (unit scale problems)
    warnings : List[str]
        Soft warnings (suspicious but plausible values)
    """
    errors = []
    warnings = []

    if prop_name not in RANGE_CHECKS:
        return errors, warnings

    checks = RANGE_CHECKS[prop_name]
    val = float(value)

    # Check for non-finite
    if not math.isfinite(val):
        errors.append(
            f"[{component_id}] {prop_name} must be finite; got {value!r}"
        )
        return errors, warnings

    # Error range checks
    if "error_min" in checks and val < checks["error_min"]:
        typical = checks.get("typical_issue", "")
        errors.append(
            f"[{component_id}] {prop_name} = {val:.6g} is below minimum "
            f"{checks['error_min']:.6g}. {typical}"
        )

    if "error_max" in checks and val > checks["error_max"]:
        typical = checks.get("typical_issue", "")
        errors.append(
            f"[{component_id}] {prop_name} = {val:.6g} exceeds maximum "
            f"{checks['error_max']:.6g}. {typical}"
        )

    # Check for exactly zero (Pc, Vc, MW, Tc, Tb should never be zero)
    if prop_name in ("Pc", "Vc", "MW", "Tc", "Tb") and val == 0.0:
        errors.append(
            f"[{component_id}] {prop_name} cannot be zero"
        )

    # Warning range checks
    if "warn_min" in checks and val < checks["warn_min"]:
        typical = checks.get("typical_issue", "")
        warnings.append(
            f"[{component_id}] {prop_name} = {val:.6g} is below typical minimum "
            f"{checks['warn_min']:.6g}. {typical}"
        )

    if "warn_max" in checks and val > checks["warn_max"]:
        typical = checks.get("typical_issue", "")
        warnings.append(
            f"[{component_id}] {prop_name} = {val:.6g} exceeds typical maximum "
            f"{checks['warn_max']:.6g}. {typical}"
        )

    return errors, warnings


def check_unit_metadata(
    prop_name: str,
    unit_field: str,
    unit_value: Any,
    component_id: str,
) -> List[str]:
    """
    Validate that explicit unit metadata matches canonical units.

    Returns
    -------
    errors : List[str]
        Unit metadata violations
    """
    errors = []

    canonical = CANONICAL_UNITS.get(prop_name)
    if canonical is None:
        # No canonical unit defined (e.g., omega is dimensionless)
        return errors

    if not isinstance(unit_value, str):
        errors.append(
            f"[{component_id}] {unit_field} must be a string; got {type(unit_value).__name__}"
        )
        return errors

    # Exact match required (case-sensitive)
    if unit_value != canonical:
        errors.append(
            f"[{component_id}] {unit_field} = '{unit_value}' must be '{canonical}' (canonical unit)"
        )

    return errors


# ==============================================================================
# Component Database Validation
# ==============================================================================


def validate_component_db(db_path: Path) -> Tuple[int, int]:
    """
    Validate component database units contract.

    Returns
    -------
    errors : int
        Number of unit contract violations
    warnings : int
        Number of suspicious values
    """
    if not db_path.exists():
        print(f"ERROR: Component database not found: {db_path}")
        return 1, 0

    try:
        data = json.loads(db_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Failed to parse {db_path}: {e}")
        return 1, 0

    components = data.get("components", {})
    if not isinstance(components, dict):
        print(f"ERROR: 'components' field must be a dict in {db_path}")
        return 1, 0

    errors = 0
    warnings = 0

    print(f"\nValidating component database: {db_path}")
    print(f"  Found {len(components)} components")

    for comp_id, comp_data in components.items():
        if not isinstance(comp_data, dict):
            errors += 1
            print(f"ERROR: [{comp_id}] component data must be a dict")
            continue

        # Check each property with canonical units
        for prop_name, canonical_unit in CANONICAL_UNITS.items():
            prop_value = comp_data.get(prop_name)
            unit_field = f"{prop_name}_unit"
            unit_value = comp_data.get(unit_field)

            # If property exists, validate it
            if prop_value is not None:
                # Check numeric validity
                if not is_numeric(prop_value):
                    errors += 1
                    print(
                        f"ERROR: [{comp_id}] {prop_name} must be numeric; got {type(prop_value).__name__}"
                    )
                    continue

                # Check range
                prop_errors, prop_warnings = check_range(
                    prop_name, float(prop_value), comp_id
                )
                errors += len(prop_errors)
                warnings += len(prop_warnings)
                for err in prop_errors:
                    print(f"ERROR: {err}")
                for warn in prop_warnings:
                    print(f"WARNING: {warn}")

            # If unit metadata exists, validate it
            if unit_value is not None:
                unit_errors = check_unit_metadata(
                    prop_name, unit_field, unit_value, comp_id
                )
                errors += len(unit_errors)
                for err in unit_errors:
                    print(f"ERROR: {err}")

    return errors, warnings


# ==============================================================================
# Scan for Other Data Files
# ==============================================================================


def scan_data_files(repo_root: Path) -> List[Path]:
    """
    Find all JSON/YAML files in data/ directory.

    Returns
    -------
    paths : List[Path]
        Potential input files to validate
    """
    data_dir = repo_root / "data"
    if not data_dir.exists():
        return []

    files = []
    for pattern in ("**/*.json", "**/*.yaml", "**/*.yml"):
        files.extend(data_dir.glob(pattern))

    return files


def validate_data_file(file_path: Path) -> Tuple[int, int]:
    """
    Validate units in arbitrary data files (best-effort).

    This is a heuristic scan for common property names with unit issues.

    Returns
    -------
    errors : int
    warnings : int
    """
    errors = 0
    warnings = 0

    try:
        if file_path.suffix == ".json":
            data = json.loads(file_path.read_text(encoding="utf-8"))
        else:
            # YAML support would require PyYAML
            return 0, 0
    except Exception as e:
        print(f"WARNING: Could not parse {file_path}: {e}")
        return 0, 1

    # Recursively search for property names
    def search_dict(d: Any, path: str = "") -> None:
        nonlocal errors, warnings

        if not isinstance(d, dict):
            return

        for key, value in d.items():
            current_path = f"{path}.{key}" if path else key

            # Check if this looks like a thermodynamic property
            if key in CANONICAL_UNITS and is_numeric(value):
                prop_errors, prop_warnings = check_range(
                    key, float(value), f"{file_path.name}::{current_path}"
                )
                errors += len(prop_errors)
                warnings += len(prop_warnings)
                for err in prop_errors:
                    print(f"ERROR: {err}")
                for warn in prop_warnings:
                    print(f"WARNING: {warn}")

            # Check unit metadata
            if key.endswith("_unit"):
                prop_name = key[:-5]  # Remove '_unit' suffix
                unit_errors = check_unit_metadata(
                    prop_name,
                    key,
                    value,
                    f"{file_path.name}::{current_path}",
                )
                errors += len(unit_errors)
                for err in unit_errors:
                    print(f"ERROR: {err}")

            # Recurse into nested structures
            if isinstance(value, dict):
                search_dict(value, current_path)
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        search_dict(item, f"{current_path}[{idx}]")

    search_dict(data)
    return errors, warnings


# ==============================================================================
# Main Entry Point
# ==============================================================================


def main() -> None:
    """Run units validation suite."""
    parser = argparse.ArgumentParser(
        description="Validate units contract across PVT-SIM repository"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--component-db",
        type=Path,
        default=None,
        help="Path to components.json (default: data/pure_components/components.json)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )
    args = parser.parse_args()

    repo_root: Path = args.repo_root
    if not repo_root.exists():
        print(f"ERROR: Repository root not found: {repo_root}")
        sys.exit(1)

    print("=" * 70)
    print("Units Contract Validation")
    print("=" * 70)

    total_errors = 0
    total_warnings = 0

    # 1. Validate component database
    if args.component_db:
        db_path = args.component_db
    else:
        db_path = repo_root / "data" / "pure_components" / "components.json"

    if db_path.exists():
        errors, warnings = validate_component_db(db_path)
        total_errors += errors
        total_warnings += warnings
    else:
        print(f"\nWARNING: Component database not found at {db_path}")
        total_warnings += 1

    # 2. Scan for other data files
    print("\nScanning for other data files...")
    data_files = scan_data_files(repo_root)

    # Exclude the main components.json
    data_files = [f for f in data_files if f != db_path]

    if data_files:
        print(f"  Found {len(data_files)} additional data file(s)")
        for data_file in data_files:
            errors, warnings = validate_data_file(data_file)
            total_errors += errors
            total_warnings += warnings
    else:
        print("  No additional data files found")

    # 3. Summary
    print("\n" + "=" * 70)
    print(f"Validation Complete: {total_errors} errors, {total_warnings} warnings")
    print("=" * 70)

    if total_errors > 0:
        print("\n[FAILED] Unit contract violations detected")
        print("Fix errors before committing or running solver code.")
        sys.exit(1)
    elif total_warnings > 0:
        if args.strict:
            print("\n[FAILED] Warnings treated as errors (--strict mode)")
            sys.exit(1)
        else:
            print("\n[WARNING] PASSED with warnings: Review suspicious values")
            sys.exit(2)
    else:
        print("\n[PASSED] All units validated successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
