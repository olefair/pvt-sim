"""Validation tests for conservative physical-state hints on stability results.

These checks target the interpretation layer rather than the TPD solve itself.
The goal is to lock down the most failure-prone edge cases:

- dense subcritical mixtures where saturation boundaries exist and should drive
  a liquid-like or vapor-like hint
- supercritical pure-component states where a forced liquid/vapor label would
  be less defensible than an explicit ambiguity
"""

from __future__ import annotations

import json
from pathlib import Path

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus


_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


def _fixture_components(fluid_id: str) -> list[dict]:
    payload = json.loads((_FIXTURES_DIR / "fluids" / f"{fluid_id}.json").read_text(encoding="utf-8"))
    return payload["components"]


def _run_stability(*, name: str, components: list[dict], pressure_pa: float, temperature_k: float):
    result = run_calculation(
        config=RunConfig.model_validate(
            {
                "run_name": name,
                "composition": {"components": components},
                "calculation_type": "stability_analysis",
                "eos_type": "peng_robinson",
                "stability_analysis_config": {
                    "pressure_pa": pressure_pa,
                    "temperature_k": temperature_k,
                    "feed_phase": "auto",
                },
            }
        ),
        write_artifacts=False,
    )
    assert result.status == RunStatus.COMPLETED
    assert result.stability_analysis_result is not None
    return result.stability_analysis_result


def test_supercritical_pure_methane_stays_conservative_across_pressure() -> None:
    methane = [{"component_id": "C1", "mole_fraction": 1.0}]

    low_pressure = _run_stability(
        name="methane-supercritical-low-pressure",
        components=methane,
        pressure_pa=2.0e6,
        temperature_k=320.0,
    )
    high_pressure = _run_stability(
        name="methane-supercritical-high-pressure",
        components=methane,
        pressure_pa=1.0e7,
        temperature_k=320.0,
    )

    assert low_pressure.stable is True
    assert low_pressure.phase_regime == "single_phase"
    assert low_pressure.physical_state_hint == "single_phase_vapor_like"
    assert low_pressure.physical_state_hint_basis == "supercritical_guard"
    assert low_pressure.physical_state_hint_confidence == "medium"

    assert high_pressure.stable is True
    assert high_pressure.phase_regime == "single_phase"
    assert high_pressure.physical_state_hint == "single_phase_ambiguous"
    assert high_pressure.physical_state_hint_basis == "supercritical_guard"
    assert high_pressure.physical_state_hint_confidence == "low"


def test_co2_rich_single_phase_hint_uses_saturation_when_available_and_ambiguity_when_not() -> None:
    co2_rich_gas = _fixture_components("co2_rich_gas")

    subcritical_dense = _run_stability(
        name="co2-rich-dense-subcritical",
        components=co2_rich_gas,
        pressure_pa=8.0e6,
        temperature_k=280.0,
    )
    critical_region = _run_stability(
        name="co2-rich-critical-region",
        components=co2_rich_gas,
        pressure_pa=8.0e6,
        temperature_k=320.0,
    )

    assert subcritical_dense.stable is True
    assert subcritical_dense.phase_regime == "single_phase"
    assert subcritical_dense.physical_state_hint == "single_phase_liquid_like"
    assert subcritical_dense.physical_state_hint_basis == "saturation_window"
    assert subcritical_dense.physical_state_hint_confidence == "high"
    assert subcritical_dense.bubble_pressure_hint_pa is not None
    assert subcritical_dense.dew_pressure_hint_pa is not None

    assert critical_region.stable is True
    assert critical_region.phase_regime == "single_phase"
    assert critical_region.physical_state_hint == "single_phase_ambiguous"
    assert critical_region.physical_state_hint_basis == "no_boundary_guard"
    assert critical_region.physical_state_hint_confidence == "low"
    assert critical_region.bubble_boundary_reason == "degenerate_trivial_boundary"
    assert critical_region.dew_boundary_reason == "degenerate_trivial_boundary"
