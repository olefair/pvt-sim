"""Command-line interface for PVT Simulator.

Provides headless execution of PVT calculations from configuration files.
Useful for batch processing and scripting.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pvtapp import __version__, __app_name__
from pvtapp.schemas import RunConfig, RunResult, RunStatus
from pvtapp.job_runner import run_calculation, create_run_directory


def load_config(config_path: Path) -> RunConfig:
    """Load RunConfig from JSON file.

    Args:
        config_path: Path to JSON configuration file

    Returns:
        Validated RunConfig

    Raises:
        ValueError: If configuration is invalid
        FileNotFoundError: If file doesn't exist
    """
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        data = json.load(f)

    return RunConfig.model_validate(data)


def save_result(result: RunResult, output_path: Path) -> None:
    """Save RunResult to JSON file.

    Args:
        result: Calculation result
        output_path: Path for output JSON file
    """
    with open(output_path, 'w') as f:
        json.dump(result.model_dump(mode='json'), f, indent=2, default=str)


def print_result_summary(result: RunResult) -> None:
    """Print a summary of the result to stdout."""
    print(f"\n{'='*60}")
    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status.value}")

    if result.duration_seconds:
        print(f"Duration: {result.duration_seconds:.2f} seconds")

    if result.status == RunStatus.FAILED:
        print(f"Error: {result.error_message}")
        return

    if result.pt_flash_result:
        res = result.pt_flash_result
        print(f"\nPT Flash Results:")
        print(f"  Converged: {res.converged}")
        print(f"  Phase: {res.phase}")
        print(f"  Vapor Fraction: {res.vapor_fraction:.6f}")
        print(f"  Iterations: {res.diagnostics.iterations}")

        print(f"\n  {'Component':<10} {'Liquid':<12} {'Vapor':<12} {'K-value':<12}")
        print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
        for comp in sorted(res.liquid_composition.keys()):
            print(f"  {comp:<10} "
                  f"{res.liquid_composition.get(comp, 0):<12.6f} "
                  f"{res.vapor_composition.get(comp, 0):<12.6f} "
                  f"{res.K_values.get(comp, 0):<12.4f}")

    elif result.phase_envelope_result:
        res = result.phase_envelope_result
        print(f"\nPhase Envelope Results:")
        print(f"  Bubble Points: {len(res.bubble_curve)}")
        print(f"  Dew Points: {len(res.dew_curve)}")
        if res.critical_point:
            print(f"  Critical Point: "
                  f"{res.critical_point.temperature_k - 273.15:.2f} C, "
                  f"{res.critical_point.pressure_pa / 1e5:.2f} bar")

    elif result.cce_result:
        res = result.cce_result
        print(f"\nCCE Results:")
        print(f"  Temperature: {res.temperature_k - 273.15:.2f} C")
        print(f"  Steps: {len(res.steps)}")
        if res.saturation_pressure_pa:
            print(f"  Saturation Pressure: {res.saturation_pressure_pa / 1e5:.2f} bar")

    print(f"{'='*60}\n")


class ProgressPrinter:
    """Simple progress callback for CLI output."""

    def on_started(self, run_id: str, calculation_type: str) -> None:
        print(f"Starting {calculation_type}...")

    def on_progress(self, run_id: str, progress: float, message: str) -> None:
        pct = int(progress * 100)
        print(f"  [{pct:3d}%] {message}")

    def on_completed(self, run_id: str, result: RunResult) -> None:
        print("Calculation completed.")

    def on_failed(self, run_id: str, error: str) -> None:
        print(f"Calculation failed: {error}")

    def on_cancelled(self, run_id: str) -> None:
        print("Calculation cancelled.")


def main() -> int:
    """CLI entry point.

    Returns:
        Exit code (0 for success, non-zero for errors)
    """
    parser = argparse.ArgumentParser(
        prog="pvtsim-cli",
        description=f"{__app_name__} v{__version__} - Command Line Interface",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a calculation from config file")
    run_parser.add_argument(
        "config",
        type=Path,
        help="Path to JSON configuration file",
    )
    run_parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Path for output JSON file (default: stdout only)",
    )
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for run artifacts (default: auto-generated)",
    )
    run_parser.add_argument(
        "--no-artifacts",
        action="store_true",
        help="Don't write artifact files",
    )
    run_parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a configuration file without running"
    )
    validate_parser.add_argument(
        "config",
        type=Path,
        help="Path to JSON configuration file",
    )

    # Parse arguments
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "validate":
        return _cmd_validate(args)
    elif args.command == "run":
        return _cmd_run(args)

    return 0


def _cmd_validate(args) -> int:
    """Handle validate command."""
    try:
        config = load_config(args.config)
        print(f"Configuration valid: {args.config}")
        print(f"  Calculation type: {config.calculation_type.value}")
        print(f"  Components: {len(config.composition.components)}")
        print(f"  EOS: {config.eos_type.value}")
        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Validation failed: {e}", file=sys.stderr)
        return 1


def _cmd_run(args) -> int:
    """Handle run command."""
    try:
        # Load configuration
        config = load_config(args.config)

        # Set up progress callback
        callback = None if args.quiet else ProgressPrinter()

        # Run calculation
        result = run_calculation(
            config=config,
            output_dir=args.output_dir,
            callback=callback,
            write_artifacts=not args.no_artifacts,
        )

        # Print summary
        if not args.quiet:
            print_result_summary(result)

        # Save result if output path specified
        if args.output:
            save_result(result, args.output)
            if not args.quiet:
                print(f"Results saved to: {args.output}")

        # Return exit code based on result
        if result.status == RunStatus.COMPLETED:
            return 0
        else:
            return 1

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Calculation failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
