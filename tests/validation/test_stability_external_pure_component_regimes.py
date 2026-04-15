"""Standalone stability regime checks around external pure-component saturation anchors.

These are not duplicate saturation-pressure tests. The existing pure-component
validation already checks bubble/dew pressure accuracy against NIST anchors.
This module uses those same anchors to validate the standalone stability
runtime surface: slightly below saturation pressure the state should resolve as
stable vapor, and slightly above saturation pressure it should resolve as
stable liquid.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from pvtcore.stability.analysis import StabilityOptions
from pvtcore.validation import PureComponentSaturationAnchor, load_external_anchor_case


_CASES_DIR = Path(__file__).resolve().parent / "external_data" / "cases"
_BELOW_SATURATION_SCALE = 0.90
_ABOVE_SATURATION_SCALE = 1.10


def _load_pure_component_cases() -> list[PureComponentSaturationAnchor]:
    cases: list[PureComponentSaturationAnchor] = []
    for path in sorted(_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, PureComponentSaturationAnchor):
            cases.append(case)
    return cases


def _stability_config(*, component_id: str, temperature_k: float, pressure_pa: float) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": f"Stability {component_id} @ {temperature_k:.2f} K",
            "composition": {
                "components": [
                    {
                        "component_id": component_id,
                        "mole_fraction": 1.0,
                    }
                ]
            },
            "calculation_type": "stability_analysis",
            "eos_type": "peng_robinson",
            "stability_analysis_config": {
                "pressure_pa": pressure_pa,
                "temperature_k": temperature_k,
                "feed_phase": "auto",
                "use_gdem": True,
                "n_random_trials": 1,
                "random_seed": 7,
                "max_eos_failures_per_trial": 4,
            },
        }
    )


@pytest.mark.parametrize("case", _load_pure_component_cases(), ids=lambda case: case.case_id)
def test_standalone_stability_resolves_correct_off_saturation_phase(
    case: PureComponentSaturationAnchor,
) -> None:
    """Below Psat should be stable vapor; above Psat should be stable liquid."""
    tol = StabilityOptions().tpd_negative_tol

    for point in case.points:
        temperature_k = float(point.temperature.value)
        saturation_pressure_pa = float(point.pressure.value) * 1.0e5

        below = run_calculation(
            config=_stability_config(
                component_id=case.component_id,
                temperature_k=temperature_k,
                pressure_pa=saturation_pressure_pa * _BELOW_SATURATION_SCALE,
            ),
            write_artifacts=False,
        )
        above = run_calculation(
            config=_stability_config(
                component_id=case.component_id,
                temperature_k=temperature_k,
                pressure_pa=saturation_pressure_pa * _ABOVE_SATURATION_SCALE,
            ),
            write_artifacts=False,
        )

        assert below.status == RunStatus.COMPLETED
        assert above.status == RunStatus.COMPLETED
        assert below.stability_analysis_result is not None
        assert above.stability_analysis_result is not None

        below_result = below.stability_analysis_result
        above_result = above.stability_analysis_result

        assert below_result.stable is True
        assert below_result.phase_regime == "single_phase"
        assert below_result.physical_state_hint == "single_phase_vapor_like"
        assert below_result.physical_state_hint_basis in {"saturation_window", "direct_root_split"}
        assert below_result.physical_state_hint_confidence == "high"
        assert below_result.tpd_min >= -tol
        assert below_result.best_unstable_trial_kind is None
        assert below_result.reference_root_used == "vapor"

        assert above_result.stable is True
        assert above_result.phase_regime == "single_phase"
        assert above_result.physical_state_hint == "single_phase_liquid_like"
        assert above_result.physical_state_hint_basis in {"saturation_window", "direct_root_split"}
        assert above_result.physical_state_hint_confidence == "high"
        assert above_result.tpd_min >= -tol
        assert above_result.best_unstable_trial_kind is None
        assert above_result.reference_root_used == "liquid"

        assert below_result.vapor_like_trial is not None
        assert below_result.liquid_like_trial is not None
        assert above_result.vapor_like_trial is not None
        assert above_result.liquid_like_trial is not None
