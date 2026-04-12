#!/usr/bin/env python3
"""
Master validation script for PVT-SIM.

Runs all validation checks in sequence:
1. Component schema validation (groups, structure)
2. Component integration tests (loading, PPR78)
3. Units contract validation (canonical units, range checks)

Run from repo root:
    python scripts/validate_modules.py

Exit codes:
    0 - All validations passed
    1 - One or more validations failed
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


class ValidationStep:
    """Represents a single validation step."""

    def __init__(self, name: str, script: str, description: str):
        self.name = name
        self.script = script
        self.description = description
        self.passed = False
        self.exit_code = None


def run_validation(step: ValidationStep, repo_root: Path) -> bool:
    """
    Run a validation script and capture results.

    Returns
    -------
    success : bool
        True if validation passed
    """
    script_path = repo_root / "scripts" / step.script

    if not script_path.exists():
        print(f"⚠️  WARNING: Validation script not found: {step.script}")
        return False

    print(f"\n{'=' * 70}")
    print(f"Running: {step.name}")
    print(f"{step.description}")
    print(f"{'=' * 70}\n")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=repo_root,
            capture_output=False,  # Show output in real-time
            text=True,
        )
        step.exit_code = result.returncode
        step.passed = result.returncode == 0
        return step.passed

    except Exception as e:
        print(f"❌ ERROR: Failed to run {step.script}: {e}")
        step.exit_code = 1
        step.passed = False
        return False


def print_summary(steps: List[ValidationStep]) -> None:
    """Print validation summary."""
    print("\n" + "=" * 70)
    print("Validation Summary")
    print("=" * 70)

    for step in steps:
        if step.passed:
            status = "[PASSED]"
        elif step.exit_code is None:
            status = "[SKIPPED]"
        else:
            status = f"[FAILED] (exit code {step.exit_code})"

        print(f"  {status:25} {step.name}")

    print("=" * 70)


def main() -> None:
    """Run all validation steps."""
    repo_root = Path(__file__).resolve().parent.parent

    # Define validation pipeline
    steps = [
        ValidationStep(
            name="Component Schema Validation",
            script="validate_components_schema.py",
            description="Validates component database schema, groups, and basic thermo sanity",
        ),
        ValidationStep(
            name="Component Alias Contract Audit",
            script="audit_component_aliases.py",
            description="Checks alias uniqueness and app picker/runtime component contract alignment",
        ),
        ValidationStep(
            name="Component Integration Tests",
            script="validate_components.py",
            description="Tests component loading, PPR78 decomposition, and k_ij calculation",
        ),
        ValidationStep(
            name="Units Contract Validation",
            script="validate_units.py",
            description="Enforces canonical units and detects unit scale errors",
        ),
    ]

    print("=" * 70)
    print("PVT-SIM Validation Suite")
    print("=" * 70)
    print(f"Repository: {repo_root}")
    print(f"Running {len(steps)} validation step(s)...")

    # Run all validations
    all_passed = True
    for step in steps:
        passed = run_validation(step, repo_root)
        if not passed:
            all_passed = False

    # Print summary
    print_summary(steps)

    # Exit with appropriate code
    if all_passed:
        print("\n[SUCCESS] All validations passed!")
        sys.exit(0)
    else:
        print("\n[FAILED] One or more validations failed")
        print("Fix errors before committing or running solver code.")
        sys.exit(1)


if __name__ == "__main__":
    main()
