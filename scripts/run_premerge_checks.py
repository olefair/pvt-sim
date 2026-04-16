#!/usr/bin/env python3
"""Run the fast pre-merge verification surface.

This script is the intended lane/worktree gate before absorbing work back into
the integration root. It always runs a small, fixed baseline and then adds
focused test bundles based on files changed since the selected base ref.

Use ``scripts/run_full_validation.py`` for the longer validation surface.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


REPO_ROOT = Path(__file__).resolve().parent.parent
PYTHON = sys.executable

# Merge-gate / `--baseline-only` pytest targets: high-signal path for integration-root absorb and conflict resolution.
# - Kernel: full `test_flash.py` (RR, Wilson, PT flash, special cases) — firm on thermo/flash regressions.
# - App: phase envelope + CCE workflow tests (runtime/GUI wiring vs `job_runner`).
# - Boundaries: CLI validate + cross-cutting invariants.
# Routine `pytest` still runs the full headless suite in CI after this baseline; together they back “no regressions” over “clean git theater.”
BASELINE_MERGE_GATE_PYTEST_ITEMS: tuple[str, ...] = (
    "tests/unit/test_flash.py",
    "tests/unit/test_cli_validate.py",
    "tests/unit/test_pvtapp_phase_envelope_workflow.py",
    "tests/unit/test_pvtapp_cce_workflow.py",
    "tests/contracts/test_invariants.py",
)
BASELINE_SMOKE_TESTS = frozenset(
    Path(item.split("::", 1)[0]).as_posix().lstrip("./") for item in BASELINE_MERGE_GATE_PYTEST_ITEMS
)


@dataclass(frozen=True)
class CheckStep:
    """A single executable verification step."""

    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CheckGroup:
    """A domain-specific fast test bundle."""

    name: str
    path_prefixes: tuple[str, ...]
    steps: tuple[CheckStep, ...]


BASELINE_STEPS = (
    CheckStep(
        "validate-modules",
        (PYTHON, "scripts/validate_modules.py"),
    ),
    CheckStep(
        "baseline-smoke-tests",
        (PYTHON, "-m", "pytest", *BASELINE_MERGE_GATE_PYTEST_ITEMS, "-q"),
    ),
    CheckStep(
        "validate-phase-envelope-example",
        (
            PYTHON,
            "-m",
            "pvtapp.cli",
            "validate",
            "examples/phase_envelope_config.json",
        ),
    ),
    CheckStep(
        "run-phase-envelope-example",
        (
            PYTHON,
            "-m",
            "pvtapp.cli",
            "run",
            "--no-artifacts",
            "examples/phase_envelope_config.json",
        ),
    ),
    CheckStep(
        "validate-pt-flash-example",
        (
            PYTHON,
            "-m",
            "pvtapp.cli",
            "validate",
            "examples/pt_flash_config.json",
        ),
    ),
    CheckStep(
        "run-pt-flash-example",
        (
            PYTHON,
            "-m",
            "pvtapp.cli",
            "run",
            "--no-artifacts",
            "examples/pt_flash_config.json",
        ),
    ),
)


FAST_GROUPS = (
    CheckGroup(
        name="components-and-characterization",
        path_prefixes=(
            "src/pvtcore/characterization/",
            "src/pvtcore/models/",
            "src/pvtcore/correlations/",
            "data/pure_components/",
            "scripts/validate_components.py",
            "scripts/validate_components_schema.py",
            "scripts/audit_component_aliases.py",
        ),
        steps=(
            CheckStep(
                "characterization-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_characterization_pipeline.py",
                    "tests/unit/test_plus_fraction_splitting.py",
                    "tests/unit/test_lumping_delumping.py",
                    "tests/unit/test_scn_properties.py",
                    "tests/unit/test_tbp_module.py",
                    "tests/unit/test_tbp_policy.py",
                    "tests/unit/test_fluid_definition_parser.py",
                    "tests/unit/test_components.py",
                    "tests/unit/test_correlations.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="flash-eos-and-properties",
        path_prefixes=(
            "src/pvtcore/flash/",
            "src/pvtcore/eos/",
            "src/pvtcore/properties/",
            "src/pvtcore/core/",
            "src/pvtcore/confinement/",
        ),
        steps=(
            CheckStep(
                "flash-eos-property-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_saturation.py",
                    "tests/unit/test_peng_robinson.py",
                    "tests/unit/test_pr78.py",
                    "tests/unit/test_ppr78.py",
                    "tests/unit/test_srk.py",
                    "tests/unit/test_density.py",
                    "tests/unit/test_properties.py",
                    "tests/unit/test_ift_parachor.py",
                    "tests/unit/test_confinement.py",
                    "tests/unit/test_cubic_solver.py",
                    "tests/unit/test_convergence_status.py",
                    "tests/unit/test_invariants.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="stability",
        path_prefixes=(
            "src/pvtcore/stability/",
            "src/pvtcore/core/errors.py",
        ),
        steps=(
            CheckStep(
                "stability-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_stability.py",
                    "tests/unit/test_stability_analysis.py",
                    "tests/unit/test_stability_analysis_api.py",
                    "tests/unit/test_stability_wrappers.py",
                    "tests/unit/test_stability_analysis_robustness.py",
                    "tests/unit/test_pvtapp_stability_runtime.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="envelope",
        path_prefixes=(
            "src/pvtcore/envelope/",
            "scripts/run_phase_envelope_validation.py",
            "scripts/validate_envelope.py",
        ),
        steps=(
            CheckStep(
                "envelope-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_envelope.py",
                    "tests/unit/test_envelope_continuation.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="runtime-surface",
        path_prefixes=(
            "src/pvtapp/",
            "src/pvtcore/io/",
            "src/pvtcore/experiments/",
        ),
        steps=(
            CheckStep(
                "runtime-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_pvtapp_runtime_contract.py",
                    "tests/unit/test_pvtapp_remaining_workflows.py",
                    "tests/unit/test_pvtapp_assignment_case.py",
                    "tests/unit/test_pvtapp_run_history.py",
                    "tests/unit/test_experiments.py",
                    "tests/unit/test_cvd_dl_retained_basis.py",
                    "tests/unit/test_pvtapp_cvd_result_views.py",
                    "tests/unit/test_pvtapp_tbp_result_views.py",
                    "tests/unit/test_pvtapp_pt_flash_viscosity.py",
                    "tests/unit/test_pvtapp_stability_runtime.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="validation-backends",
        path_prefixes=(
            "src/pvtcore/validation/",
            "tests/validation/external_data/",
            "scripts/run_pete665_assignment.py",
        ),
        steps=(
            CheckStep(
                "validation-backend-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_validation_backend_registry.py",
                    "tests/unit/test_validation_invariants.py",
                    "tests/unit/test_prode_bridge.py",
                    "tests/unit/test_thermopack_bridge.py",
                    "tests/unit/test_pete665_assignment.py",
                    "tests/validation/test_external_corpus_schema.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="tuning",
        path_prefixes=("src/pvtcore/tuning/",),
        steps=(
            CheckStep(
                "tuning-tests",
                (
                    PYTHON,
                    "-m",
                    "pytest",
                    "tests/unit/test_tuning.py",
                    "tests/unit/test_tuning_unsupported_datatype.py",
                    "-q",
                ),
            ),
        ),
    ),
    CheckGroup(
        name="packaging",
        path_prefixes=(
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "packaging/",
            "tools/",
        ),
        steps=(
            CheckStep(
                "build-distributions",
                (PYTHON, "-m", "build"),
            ),
        ),
    ),
)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(REPO_ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src_path if not existing else src_path + os.pathsep + existing
    env.setdefault("PYTHONUTF8", "1")
    return env


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def _resolve_base_ref(requested: str) -> str:
    candidates = [requested]
    if requested == "main":
        candidates.extend(["origin/main", "refs/heads/main"])

    for candidate in candidates:
        completed = _run_git("rev-parse", "--verify", f"{candidate}^{{commit}}")
        if completed.returncode == 0:
            return candidate

    raise SystemExit(
        f"Could not resolve base ref '{requested}'. "
        "Pass --base <ref> explicitly, for example --base origin/main."
    )


def _git_lines(*args: str) -> list[str]:
    completed = _run_git(*args)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return [_normalize_path(line) for line in completed.stdout.splitlines() if line.strip()]


def _changed_files_from_git(base_ref: str) -> list[str]:
    resolved_base = _resolve_base_ref(base_ref)
    merge_base = _git_lines("merge-base", "HEAD", resolved_base)
    if len(merge_base) != 1:
        raise SystemExit(f"Expected one merge-base for HEAD and {resolved_base}, got {merge_base!r}")

    committed = _git_lines("diff", "--name-only", f"{merge_base[0]}..HEAD")
    staged = _git_lines("diff", "--name-only", "--cached")
    unstaged = _git_lines("diff", "--name-only")
    untracked = _git_lines("ls-files", "--others", "--exclude-standard")
    return sorted(set(committed + staged + unstaged + untracked))


def _matches_prefix(path: str, prefix: str) -> bool:
    normalized_prefix = _normalize_path(prefix)
    if normalized_prefix.endswith("/"):
        return path.startswith(normalized_prefix)
    return path == normalized_prefix


def _triggered_groups(changed_files: list[str], *, all_fast: bool) -> list[CheckGroup]:
    if all_fast:
        return list(FAST_GROUPS)

    selected: list[CheckGroup] = []
    for group in FAST_GROUPS:
        if any(
            _matches_prefix(path, prefix)
            for path in changed_files
            for prefix in group.path_prefixes
        ):
            selected.append(group)
    return selected


def _changed_fast_tests(changed_files: list[str]) -> list[str]:
    paths = {
        path
        for path in changed_files
        if path.endswith(".py")
        and (
            path.startswith("tests/unit/")
            or path == "tests/contracts/test_invariants.py"
        )
    }
    return sorted(paths.difference(BASELINE_SMOKE_TESTS))


def _selected_steps(changed_files: list[str], *, all_fast: bool) -> list[CheckStep]:
    steps: list[CheckStep] = list(BASELINE_STEPS)

    changed_test_paths = _changed_fast_tests(changed_files)
    if changed_test_paths:
        steps.append(
            CheckStep(
                "changed-fast-tests",
                (PYTHON, "-m", "pytest", *changed_test_paths, "-q"),
            )
        )

    for group in _triggered_groups(changed_files, all_fast=all_fast):
        steps.extend(group.steps)
    return steps


def _print_plan(
    changed_files: list[str],
    steps: list[CheckStep],
    *,
    base_ref: str,
    all_fast: bool,
    baseline_only: bool = False,
) -> None:
    if baseline_only:
        mode = "baseline only (fixed CI fast gate)"
    elif all_fast:
        mode = "all fast groups"
    else:
        mode = f"changed since {base_ref}"
    print(f"Pre-merge verification plan ({mode})")
    print("=" * 72)
    if baseline_only:
        print("Git-based routing skipped (--baseline-only).")
    elif changed_files:
        print("Changed files:")
        for path in changed_files:
            print(f"- {path}")
    else:
        print("Changed files: none detected beyond the fixed baseline")
    print("")
    print("Selected steps:")
    for step in steps:
        print(f"- {step.name}: {' '.join(step.command)}")


def _run_steps(steps: list[CheckStep]) -> int:
    env = _command_env()
    for step in steps:
        print(f"\n== {step.name} ==")
        completed = subprocess.run(step.command, cwd=REPO_ROOT, env=env)
        if completed.returncode != 0:
            print(f"\nPre-merge verification failed in step: {step.name}")
            return completed.returncode
    print("\nPre-merge verification surface completed successfully.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the fast lane/worktree verification surface. "
            "This is the intended pre-merge gate before integration-root absorb."
        )
    )
    parser.add_argument(
        "--base",
        default="main",
        help="Git ref used to compute changed files (default: main)",
    )
    parser.add_argument(
        "--all-fast",
        action="store_true",
        help="Run every fast domain group instead of routing from changed files",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        help="Explicit file list to route instead of using git diff",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Print the selected plan without executing it",
    )
    parser.add_argument(
        "--baseline-only",
        "--integration-root",
        dest="baseline_only",
        action="store_true",
        help=(
            "Run only the fixed baseline (validate_modules, curated smoke tests, "
            "canonical CLI examples). Skips git diff routing and domain bundles. "
            "Use before absorbing a lane worktree into the integration root; same as "
            "CI fast gate (--integration-root is an alias)."
        ),
    )
    args = parser.parse_args()

    if args.baseline_only:
        changed_files: list[str] = []
        steps = list(BASELINE_STEPS)
    else:
        changed_files = (
            sorted({_normalize_path(path) for path in args.files})
            if args.files
            else _changed_files_from_git(args.base)
        )
        steps = _selected_steps(changed_files, all_fast=args.all_fast)

    if args.list:
        _print_plan(
            changed_files,
            steps,
            base_ref=args.base,
            all_fast=args.all_fast,
            baseline_only=args.baseline_only,
        )
        return 0

    return _run_steps(steps)


if __name__ == "__main__":
    raise SystemExit(main())
