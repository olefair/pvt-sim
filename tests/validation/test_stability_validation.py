"""Standalone stability-analysis validation.

Consolidated from:
- test_stability_runtime_matrix.py (broad runtime matrix + replay)
- test_stability_fixture_validation.py (fixture phase-regime anchors)
- test_stability_external_pure_component_regimes.py (off-saturation regime checks)
- test_stability_physical_state_hints.py (supercritical / dense hints)
- test_stability_saturation_regime_windows.py (multicomponent saturation windows)

Three test functions:
1. test_stability_runtime_matrix — runtime matrix + replay invariants
2. test_stability_fixture_and_external_anchors — fixture phase regimes + NIST off-saturation
3. test_stability_physical_hints_and_saturation_windows — hint edge cases + window consistency
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

from pvtapp.job_runner import load_run_config, load_run_result, rerun_saved_run, run_calculation
from pvtapp.schemas import RunConfig, RunStatus
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.flash.bubble_point import calculate_bubble_point
from pvtcore.flash.dew_point import calculate_dew_point
from pvtcore.models.component import load_components
from pvtcore.stability.analysis import StabilityOptions
from pvtcore.validation import PureComponentSaturationAnchor, load_external_anchor_case


FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
FLUIDS_DIR = FIXTURES_DIR / "fluids"
EXPECTED_DIR = FIXTURES_DIR / "expected"
_NIST_CASES_DIR = Path(__file__).resolve().parent / "external_data" / "cases"


# ===================================================================
# Shared helpers
# ===================================================================

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _fixture_payload(fluid_id: str) -> dict:
    payload = _load_json(FLUIDS_DIR / f"{fluid_id}.json")
    return {"components": payload["components"]}


def _fixture_components(fluid_id: str) -> list[dict]:
    payload = _load_json(FLUIDS_DIR / f"{fluid_id}.json")
    return payload["components"]


def _run_stability(*, name: str, components: list[dict], pressure_pa: float, temperature_k: float):
    result = run_calculation(
        config=RunConfig.model_validate({
            "run_name": name,
            "composition": {"components": components},
            "calculation_type": "stability_analysis",
            "eos_type": "peng_robinson",
            "stability_analysis_config": {
                "pressure_pa": pressure_pa,
                "temperature_k": temperature_k,
                "feed_phase": "auto",
            },
        }),
        write_artifacts=False,
    )
    assert result.status == RunStatus.COMPLETED
    assert result.stability_analysis_result is not None
    return result.stability_analysis_result


def _plus_gas_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0060},
            {"component_id": "CO2", "mole_fraction": 0.0250},
            {"component_id": "C1", "mole_fraction": 0.6400},
            {"component_id": "C2", "mole_fraction": 0.1100},
            {"component_id": "C3", "mole_fraction": 0.0750},
            {"component_id": "iC4", "mole_fraction": 0.0250},
            {"component_id": "C4", "mole_fraction": 0.0250},
            {"component_id": "iC5", "mole_fraction": 0.0180},
            {"component_id": "C5", "mole_fraction": 0.0160},
            {"component_id": "C6", "mole_fraction": 0.0140},
        ],
        "plus_fraction": {
            "label": "C7+", "cut_start": 7,
            "z_plus": 0.0460,
            "mw_plus_g_per_mol": 128.25512173913043,
            "sg_plus_60f": 0.7571304347826087,
            "characterization_preset": "manual",
            "max_carbon_number": 18,
            "split_method": "pedersen",
            "split_mw_model": "paraffin",
            "lumping_enabled": True,
            "lumping_n_groups": 2,
        },
    }


def _plus_oil_payload() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0021},
            {"component_id": "CO2", "mole_fraction": 0.0187},
            {"component_id": "C1", "mole_fraction": 0.3478},
            {"component_id": "C2", "mole_fraction": 0.0712},
            {"component_id": "C3", "mole_fraction": 0.0934},
            {"component_id": "iC4", "mole_fraction": 0.0302},
            {"component_id": "nC4", "mole_fraction": 0.0431},
            {"component_id": "iC5", "mole_fraction": 0.0276},
            {"component_id": "nC5", "mole_fraction": 0.0418},
            {"component_id": "C6", "mole_fraction": 0.0574},
        ],
        "plus_fraction": {
            "label": "C7+", "cut_start": 7,
            "z_plus": 0.2667,
            "mw_plus_g_per_mol": 119.78759868766404,
            "sg_plus_60f": 0.82,
            "characterization_preset": "auto",
            "max_carbon_number": 20,
            "split_method": "pedersen",
            "split_mw_model": "table",
            "lumping_enabled": True,
            "lumping_n_groups": 6,
        },
    }


def _inline_pseudo_payload() -> dict:
    return {
        "components": [
            {"component_id": "C1", "mole_fraction": 0.55},
            {"component_id": "PSEUDO_PLUS", "mole_fraction": 0.45},
        ],
        "inline_components": [
            {
                "component_id": "PSEUDO_PLUS",
                "name": "Pseudo+",
                "formula": "Pseudo+",
                "molecular_weight_g_per_mol": 110.0,
                "critical_temperature_k": 650.0,
                "critical_pressure_pa": 2.2e6,
                "omega": 0.55,
            }
        ],
    }


# ===================================================================
# 1) Runtime matrix + replay
# ===================================================================

@dataclass(frozen=True)
class StabilityMatrixCase:
    case_id: str
    composition_payload: dict
    pressure_pa: float
    temperature_k: float
    eos_type: str
    feed_phase: str


def _build_config(case: StabilityMatrixCase) -> RunConfig:
    return RunConfig.model_validate({
        "run_name": case.case_id,
        "composition": case.composition_payload,
        "calculation_type": "stability_analysis",
        "eos_type": case.eos_type,
        "stability_analysis_config": {
            "pressure_pa": case.pressure_pa,
            "temperature_k": case.temperature_k,
            "feed_phase": case.feed_phase,
            "use_gdem": True,
            "n_random_trials": 1,
            "random_seed": 7,
            "max_eos_failures_per_trial": 4,
        },
    })


def _matrix_cases() -> list[StabilityMatrixCase]:
    cases: list[StabilityMatrixCase] = []
    fixture_points = {
        "dry_gas": [
            {"pressure_pa": 1.0e5, "temperature_k": 200.0, "label": "vapor_low_p"},
            {"pressure_pa": 5.0e5, "temperature_k": 200.0, "label": "two_phase_low_t"},
        ],
        "co2_rich_gas": [
            {"pressure_pa": 1.0e5, "temperature_k": 300.0, "label": "vapor_low_p"},
            {"pressure_pa": 5.0e6, "temperature_k": 300.0, "label": "two_phase_mid_p"},
        ],
        "black_oil": [
            {"pressure_pa": 1.0e5, "temperature_k": 300.0, "label": "two_phase_low_p"},
            {"pressure_pa": 1.0e6, "temperature_k": 300.0, "label": "two_phase_mid_p"},
        ],
    }
    for fluid_id, points in fixture_points.items():
        payload = _fixture_payload(fluid_id)
        for point in points:
            for eos_type in ("peng_robinson", "pr78", "srk"):
                for feed_phase in ("auto", "liquid", "vapor"):
                    cases.append(StabilityMatrixCase(
                        case_id=f"{fluid_id}-{point['label']}-{eos_type}-{feed_phase}",
                        composition_payload=payload,
                        pressure_pa=point["pressure_pa"],
                        temperature_k=point["temperature_k"],
                        eos_type=eos_type, feed_phase=feed_phase,
                    ))
    extra = {
        "gas_condensate_plus": (_plus_gas_payload(), 3.0e6, 320.0),
        "volatile_oil_plus": (_plus_oil_payload(), 8.0e6, 360.0),
        "inline_pseudo": (_inline_pseudo_payload(), 5.0e6, 350.0),
    }
    for fluid_id, (payload, p, t) in extra.items():
        for eos_type in ("peng_robinson", "pr78", "srk"):
            for feed_phase in ("auto", "liquid", "vapor"):
                cases.append(StabilityMatrixCase(
                    case_id=f"{fluid_id}-matrix-{eos_type}-{feed_phase}",
                    composition_payload=payload,
                    pressure_pa=p, temperature_k=t,
                    eos_type=eos_type, feed_phase=feed_phase,
                ))
    return cases


_REPLAY_CASES = [
    StabilityMatrixCase("dry_gas-replay", _fixture_payload("dry_gas"), 5.0e5, 200.0, "srk", "auto"),
    StabilityMatrixCase("black_oil-replay", _fixture_payload("black_oil"), 1.0e6, 300.0, "pr78", "liquid"),
    StabilityMatrixCase("gas_condensate_plus-replay", _plus_gas_payload(), 3.0e6, 320.0, "peng_robinson", "vapor"),
    StabilityMatrixCase("inline_pseudo-replay", _inline_pseudo_payload(), 5.0e6, 350.0, "peng_robinson", "auto"),
]


@pytest.mark.parametrize("case", _matrix_cases(), ids=lambda c: c.case_id)
def test_stability_runtime_matrix(case: StabilityMatrixCase) -> None:
    """Runtime matrix: completes, surface invariants hold, replay preserves state."""
    config = _build_config(case)
    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.COMPLETED
    assert result.error_message is None
    assert result.stability_analysis_result is not None

    s = result.stability_analysis_result
    assert math.isfinite(s.tpd_min)
    assert sum(s.feed_composition.values()) == pytest.approx(1.0, abs=1e-9)
    assert s.reference_root_used in {"liquid", "vapor"}
    assert s.phase_regime in {"single_phase", "two_phase"}
    assert s.physical_state_hint in {
        "two_phase", "single_phase_vapor_like",
        "single_phase_liquid_like", "single_phase_ambiguous",
    }
    assert s.physical_state_hint_basis in {
        "two_phase_regime", "direct_root_split", "saturation_window",
        "supercritical_guard", "no_boundary_guard", "heuristic_fallback",
    }
    assert s.physical_state_hint_confidence in {"high", "medium", "low"}
    assert s.vapor_like_trial is not None
    assert s.liquid_like_trial is not None
    assert s.tpd_min == pytest.approx(
        min(s.vapor_like_trial.tpd, s.liquid_like_trial.tpd), abs=1e-12,
    )

    if case.feed_phase == "auto":
        assert s.resolved_feed_phase.endswith(s.reference_root_used)
    else:
        assert s.resolved_feed_phase == case.feed_phase
        assert s.reference_root_used == case.feed_phase

    if s.stable:
        assert s.phase_regime == "single_phase"
        assert s.physical_state_hint.startswith("single_phase_")
        assert s.best_unstable_trial_kind is None
    else:
        assert s.phase_regime == "two_phase"
        assert s.physical_state_hint == "two_phase"
        assert s.physical_state_hint_basis == "two_phase_regime"
        assert s.physical_state_hint_confidence == "high"
        assert s.best_unstable_trial_kind in {"vapor_like", "liquid_like"}

    for trial in (s.vapor_like_trial, s.liquid_like_trial):
        assert math.isfinite(trial.tpd)
        assert trial.seed_attempts >= 1
        assert trial.candidate_seed_count >= trial.seed_attempts
        assert 0 <= trial.best_seed_index < len(trial.seed_results)
        assert trial.best_seed.seed_label in trial.candidate_seed_labels
        assert trial.best_seed.tpd == pytest.approx(trial.tpd, abs=1e-12)
        assert trial.n_phi_calls == sum(seed.n_phi_calls for seed in trial.seed_results)
        assert trial.n_eos_failures == sum(seed.n_eos_failures for seed in trial.seed_results)
        assert trial.total_iterations == sum(seed.iterations for seed in trial.seed_results)
        assert all(seed.kind == trial.kind for seed in trial.seed_results)
        assert all(seed.trial_phase == trial.trial_phase for seed in trial.seed_results)


@pytest.mark.parametrize("case", _REPLAY_CASES, ids=lambda c: c.case_id)
def test_stability_saved_run_replay(tmp_path: Path, case: StabilityMatrixCase) -> None:
    """Saved stability runs reload and rerun cleanly."""
    output_dir = tmp_path / case.case_id
    config = _build_config(case)
    result = run_calculation(config=config, output_dir=output_dir, write_artifacts=True)
    assert result.status == RunStatus.COMPLETED
    run_dirs = sorted(p for p in output_dir.iterdir() if p.is_dir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    loaded_result = load_run_result(run_dir)
    loaded_config = load_run_config(run_dir)
    assert loaded_result is not None and loaded_config is not None
    assert loaded_result.status == RunStatus.COMPLETED
    assert loaded_config.calculation_type.value == "stability_analysis"
    assert loaded_config.stability_analysis_config.feed_phase.value == case.feed_phase
    assert loaded_result.stability_analysis_result.tpd_min == pytest.approx(
        result.stability_analysis_result.tpd_min, abs=1e-12,
    )

    replayed = rerun_saved_run(
        run_dir, output_dir=tmp_path / f"{case.case_id}-rerun",
        write_artifacts=True, run_name=f"{case.case_id}-rerun",
    )
    assert replayed.status == RunStatus.COMPLETED
    assert replayed.run_id != result.run_id
    assert replayed.stability_analysis_result is not None
    assert math.isfinite(replayed.stability_analysis_result.tpd_min)


# ===================================================================
# 2) Fixture phase-regime anchors + NIST off-saturation regimes
# ===================================================================

def _load_pure_component_cases() -> list[PureComponentSaturationAnchor]:
    cases: list[PureComponentSaturationAnchor] = []
    for path in sorted(_NIST_CASES_DIR.glob("*.json")):
        case = load_external_anchor_case(path)
        if isinstance(case, PureComponentSaturationAnchor):
            cases.append(case)
    return cases


@pytest.mark.parametrize("fluid_id", ["dry_gas", "co2_rich_gas", "black_oil"])
def test_stability_fixture_and_external_anchors(fluid_id: str) -> None:
    """Standalone stability matches fixture phase anchors."""
    fluid = _load_json(FLUIDS_DIR / f"{fluid_id}.json")
    expected = _load_json(EXPECTED_DIR / f"{fluid_id}_pt_flash.json")
    tol = StabilityOptions().tpd_negative_tol
    composition_payload = {"components": fluid["components"]}

    for point, exp in zip(fluid["pt_points"], expected["points"], strict=True):
        pressure_pa = float(point["pressure_pa"])
        temperature_k = float(point["temperature_k"])
        expected_phase = exp["phase"]

        stability_config = RunConfig.model_validate({
            "run_name": f"{fluid_id}-stability-{point['label']}",
            "composition": composition_payload,
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
        })
        s_result = run_calculation(config=stability_config, write_artifacts=False)
        assert s_result.status == RunStatus.COMPLETED
        s = s_result.stability_analysis_result

        if expected_phase == "two-phase":
            assert s.stable is False
            assert s.phase_regime == "two_phase"
            assert s.physical_state_hint == "two_phase"
            assert s.tpd_min < -tol
        else:
            assert s.stable is True
            assert s.phase_regime == "single_phase"
            assert s.physical_state_hint.startswith("single_phase_")
            assert s.tpd_min >= -tol

        assert s.vapor_like_trial is not None
        assert s.liquid_like_trial is not None
        assert s.tpd_min == pytest.approx(
            min(s.vapor_like_trial.tpd, s.liquid_like_trial.tpd), abs=1e-12,
        )


@pytest.mark.parametrize("case", _load_pure_component_cases(), ids=lambda c: c.case_id)
def test_stability_nist_off_saturation_regimes(case: PureComponentSaturationAnchor) -> None:
    """Below Psat → stable vapor; above Psat → stable liquid."""
    tol = StabilityOptions().tpd_negative_tol

    def _stability_config(*, component_id, temperature_k, pressure_pa):
        return RunConfig.model_validate({
            "run_name": f"Stability {component_id} @ {temperature_k:.2f} K",
            "composition": {"components": [{"component_id": component_id, "mole_fraction": 1.0}]},
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
        })

    for point in case.points:
        temperature_k = float(point.temperature.value)
        sat_p = float(point.pressure.value) * 1.0e5

        below = run_calculation(
            config=_stability_config(component_id=case.component_id, temperature_k=temperature_k, pressure_pa=sat_p * 0.90),
            write_artifacts=False,
        )
        above = run_calculation(
            config=_stability_config(component_id=case.component_id, temperature_k=temperature_k, pressure_pa=sat_p * 1.10),
            write_artifacts=False,
        )

        assert below.status == RunStatus.COMPLETED
        assert above.status == RunStatus.COMPLETED
        b = below.stability_analysis_result
        a = above.stability_analysis_result

        assert b.stable is True and b.phase_regime == "single_phase"
        assert b.physical_state_hint == "single_phase_vapor_like"
        assert b.tpd_min >= -tol

        assert a.stable is True and a.phase_regime == "single_phase"
        assert a.physical_state_hint == "single_phase_liquid_like"
        assert a.tpd_min >= -tol


# ===================================================================
# 3) Physical hints edge cases + multicomponent saturation windows
# ===================================================================

def test_stability_physical_hints_and_saturation_windows() -> None:
    """Supercritical, dense, and multicomponent saturation-window regime checks."""
    tol = StabilityOptions().tpd_negative_tol

    # Supercritical methane
    methane = [{"component_id": "C1", "mole_fraction": 1.0}]
    low_p = _run_stability(name="methane-sc-low-p", components=methane, pressure_pa=2.0e6, temperature_k=320.0)
    high_p = _run_stability(name="methane-sc-high-p", components=methane, pressure_pa=1.0e7, temperature_k=320.0)
    assert low_p.stable and low_p.physical_state_hint == "single_phase_vapor_like"
    assert low_p.physical_state_hint_basis == "supercritical_guard"
    assert high_p.stable and high_p.physical_state_hint == "single_phase_ambiguous"
    assert high_p.physical_state_hint_basis == "supercritical_guard"

    # CO2-rich dense subcritical vs critical
    co2_gas = _fixture_components("co2_rich_gas")
    sub = _run_stability(name="co2-rich-dense-sub", components=co2_gas, pressure_pa=8.0e6, temperature_k=280.0)
    crit = _run_stability(name="co2-rich-crit", components=co2_gas, pressure_pa=8.0e6, temperature_k=320.0)
    assert sub.stable and sub.physical_state_hint == "single_phase_liquid_like"
    assert sub.physical_state_hint_basis == "saturation_window"
    assert sub.bubble_pressure_hint_pa is not None
    assert crit.stable and crit.physical_state_hint == "single_phase_ambiguous"
    assert crit.physical_state_hint_basis == "no_boundary_guard"

    # Multicomponent saturation windows
    components = load_components()
    window_cases = [
        (("C1", "C4"), (0.8, 0.2), 250.0),
        (("C1", "C4"), (0.5, 0.5), 250.0),
        (("C1", "C4"), (0.2, 0.8), 250.0),
        (("C2", "C3"), (0.5, 0.5), 270.0),
    ]
    for comp_ids, composition, temp_k in window_cases:
        mixture = [components[cid] for cid in comp_ids]
        z = np.asarray(composition, dtype=float)
        eos = PengRobinsonEOS(mixture)

        bubble = calculate_bubble_point(temp_k, z, mixture, eos)
        dew = calculate_dew_point(temp_k, z, mixture, eos)
        assert bubble.converged and dew.converged
        assert dew.pressure < bubble.pressure

        def _stability_cfg(pressure_pa):
            return RunConfig.model_validate({
                "run_name": f"window-{comp_ids}-{pressure_pa:.0f}",
                "composition": {"components": [
                    {"component_id": cid, "mole_fraction": mf}
                    for cid, mf in zip(comp_ids, composition, strict=True)
                ]},
                "calculation_type": "stability_analysis",
                "eos_type": "peng_robinson",
                "stability_analysis_config": {
                    "pressure_pa": pressure_pa,
                    "temperature_k": temp_k,
                    "feed_phase": "auto",
                    "use_gdem": True,
                    "n_random_trials": 1,
                    "random_seed": 7,
                    "max_eos_failures_per_trial": 4,
                },
            })

        above = run_calculation(config=_stability_cfg(float(bubble.pressure) * 1.05), write_artifacts=False)
        within = run_calculation(
            config=_stability_cfg(0.5 * (float(bubble.pressure) + float(dew.pressure))),
            write_artifacts=False,
        )
        below = run_calculation(config=_stability_cfg(float(dew.pressure) * 0.95), write_artifacts=False)

        assert above.stability_analysis_result.stable is True
        assert above.stability_analysis_result.physical_state_hint == "single_phase_liquid_like"
        assert within.stability_analysis_result.stable is False
        assert within.stability_analysis_result.physical_state_hint == "two_phase"
        assert below.stability_analysis_result.stable is True
        assert below.stability_analysis_result.physical_state_hint == "single_phase_vapor_like"
