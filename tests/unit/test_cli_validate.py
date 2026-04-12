"""CLI validation contract tests."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

from pvtapp.cli import _cmd_validate


def _write_config(tmp_path: Path, data: dict) -> Path:
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(data), encoding="utf-8")
    return config_path


def test_validate_accepts_component_alias_ids(tmp_path, capsys) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "run_name": "Alias PT Flash",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "nC4", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5_000_000,
                "temperature_k": 350.0,
            },
        },
    )

    exit_code = _cmd_validate(Namespace(config=config_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration valid" in captured.out


def test_validate_rejects_unknown_component_ids(tmp_path, capsys) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "run_name": "Bad PT Flash",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "NOT_A_REAL_COMPONENT", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5_000_000,
                "temperature_k": 350.0,
            },
        },
    )

    exit_code = _cmd_validate(Namespace(config=config_path))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Unknown component(s)" in captured.err
    assert "NOT_A_REAL_COMPONENT" in captured.err


def test_validate_accepts_shipped_phase_envelope_example(capsys) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "examples" / "phase_envelope_config.json"

    exit_code = _cmd_validate(Namespace(config=config_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration valid" in captured.out
