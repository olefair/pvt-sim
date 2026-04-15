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


def test_validate_accepts_shipped_swelling_example(capsys) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "examples" / "swelling_test_config.json"

    exit_code = _cmd_validate(Namespace(config=config_path))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration valid" in captured.out
    assert "swelling_test" in captured.out


def test_validate_rejects_swelling_injection_gas_plus_fraction(tmp_path, capsys) -> None:
    config_path = _write_config(
        tmp_path,
        {
            "run_name": "Bad Swelling Config",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.40},
                    {"component_id": "C4", "mole_fraction": 0.30},
                    {"component_id": "C10", "mole_fraction": 0.30},
                ]
            },
            "calculation_type": "swelling_test",
            "eos_type": "peng_robinson",
            "swelling_test_config": {
                "temperature_k": 350.0,
                "enrichment_steps_mol_per_mol_oil": [0.05, 0.10],
                "injection_gas_composition": {
                    "components": [
                        {"component_id": "C1", "mole_fraction": 0.85},
                    ],
                    "plus_fraction": {
                        "label": "C7+",
                        "cut_start": 7,
                        "z_plus": 0.15,
                        "mw_plus_g_per_mol": 130.0,
                        "sg_plus_60f": 0.78,
                    },
                },
            },
        },
    )

    exit_code = _cmd_validate(Namespace(config=config_path))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "must not define plus_fraction" in captured.err
