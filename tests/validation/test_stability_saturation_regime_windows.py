"""Stability regime consistency derived from computed multicomponent saturation windows.

This validation layer checks that the standalone stability runtime surface
behaves correctly relative to computed bubble/dew boundaries for representative
multicomponent mixtures:

- above bubble pressure: stable single phase
- between bubble and dew: unstable (inside the two-phase window)
- below dew pressure: stable single phase

The goal is to lock down physically coherent regime classification for the
standalone stability workflow using the same EOS and saturation routines that
define the envelope boundaries in the repo.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components
from pvtcore.stability.analysis import StabilityOptions


@dataclass(frozen=True)
class SaturationWindowCase:
    case_id: str
    component_ids: tuple[str, ...]
    composition: tuple[float, ...]
    temperature_k: float


def _cases() -> list[SaturationWindowCase]:
    return [
        SaturationWindowCase(
            case_id="c1_c4_light_250k",
            component_ids=("C1", "C4"),
            composition=(0.8, 0.2),
            temperature_k=250.0,
        ),
        SaturationWindowCase(
            case_id="c1_c4_mid_250k",
            component_ids=("C1", "C4"),
            composition=(0.5, 0.5),
            temperature_k=250.0,
        ),
        SaturationWindowCase(
            case_id="c1_c4_heavy_250k",
            component_ids=("C1", "C4"),
            composition=(0.2, 0.8),
            temperature_k=250.0,
        ),
        SaturationWindowCase(
            case_id="c2_c3_mid_270k",
            component_ids=("C2", "C3"),
            composition=(0.5, 0.5),
            temperature_k=270.0,
        ),
    ]


def _stability_config(case: SaturationWindowCase, *, pressure_pa: float) -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": f"Stability saturation window {case.case_id}",
            "composition": {
                "components": [
                    {
                        "component_id": component_id,
                        "mole_fraction": mole_fraction,
                    }
                    for component_id, mole_fraction in zip(
                        case.component_ids,
                        case.composition,
                        strict=True,
                    )
                ]
            },
            "calculation_type": "stability_analysis",
            "eos_type": "peng_robinson",
            "stability_analysis_config": {
                "pressure_pa": pressure_pa,
                "temperature_k": case.temperature_k,
                "feed_phase": "auto",
                "use_gdem": True,
                "n_random_trials": 1,
                "random_seed": 7,
                "max_eos_failures_per_trial": 4,
            },
        }
    )


@pytest.mark.parametrize("case", _cases(), ids=lambda case: case.case_id)
def test_standalone_stability_tracks_multicomponent_saturation_window(
    case: SaturationWindowCase,
) -> None:
    """Standalone stability should agree with bubble/dew-defined regime windows."""
    components = load_components()
    mixture = [components[component_id] for component_id in case.component_ids]
    z = np.asarray(case.composition, dtype=float)
    eos = PengRobinsonEOS(mixture)
    tol = StabilityOptions().tpd_negative_tol

    bubble = calculate_bubble_point(case.temperature_k, z, mixture, eos)
    dew = calculate_dew_point(case.temperature_k, z, mixture, eos)

    assert bubble.converged is True
    assert dew.converged is True
    assert dew.pressure < bubble.pressure

    above = run_calculation(
        config=_stability_config(case, pressure_pa=float(bubble.pressure) * 1.05),
        write_artifacts=False,
    )
    within = run_calculation(
        config=_stability_config(case, pressure_pa=0.5 * (float(bubble.pressure) + float(dew.pressure))),
        write_artifacts=False,
    )
    below = run_calculation(
        config=_stability_config(case, pressure_pa=float(dew.pressure) * 0.95),
        write_artifacts=False,
    )

    assert above.status == RunStatus.COMPLETED
    assert within.status == RunStatus.COMPLETED
    assert below.status == RunStatus.COMPLETED
    assert above.stability_analysis_result is not None
    assert within.stability_analysis_result is not None
    assert below.stability_analysis_result is not None

    above_result = above.stability_analysis_result
    within_result = within.stability_analysis_result
    below_result = below.stability_analysis_result

    assert above_result.stable is True
    assert above_result.tpd_min >= -tol
    assert above_result.best_unstable_trial_kind is None
    assert above_result.physical_state_hint == "single_phase_liquid_like"
    assert above_result.physical_state_hint_basis in {"saturation_window", "direct_root_split"}
    assert above_result.physical_state_hint_confidence == "high"

    assert within_result.stable is False
    assert within_result.tpd_min < -tol
    assert within_result.best_unstable_trial_kind in {"vapor_like", "liquid_like"}
    assert within_result.physical_state_hint == "two_phase"
    assert within_result.physical_state_hint_basis == "two_phase_regime"
    assert within_result.physical_state_hint_confidence == "high"

    assert below_result.stable is True
    assert below_result.tpd_min >= -tol
    assert below_result.best_unstable_trial_kind is None
    assert below_result.physical_state_hint == "single_phase_vapor_like"
    assert below_result.physical_state_hint_basis in {"saturation_window", "direct_root_split"}
    assert below_result.physical_state_hint_confidence == "high"
