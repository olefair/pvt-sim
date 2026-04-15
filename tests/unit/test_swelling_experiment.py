"""Focused unit coverage for the swelling-test kernel."""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.core.errors import PhaseError, ValidationError
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.experiments import simulate_swelling
from pvtcore.models.component import get_component, load_components


@pytest.fixture
def swelling_components():
    components = load_components()
    return [
        components["C1"],
        get_component("nC4", components),
        components["C10"],
        components["CO2"],
    ]


@pytest.fixture
def swelling_eos(swelling_components):
    return PengRobinsonEOS(swelling_components)


def _oil_feed() -> np.ndarray:
    return np.asarray([0.40, 0.30, 0.30, 0.0], dtype=np.float64)


def _gas_feed() -> np.ndarray:
    return np.asarray([0.85, 0.0, 0.0, 0.15], dtype=np.float64)


def _enrichment_schedule() -> list[float]:
    return [0.05, 0.10, 0.20, 0.35]


def test_swelling_happy_path_certifies_all_steps(swelling_components, swelling_eos) -> None:
    result = simulate_swelling(
        oil_composition=_oil_feed(),
        injection_gas_composition=_gas_feed(),
        temperature=350.0,
        components=swelling_components,
        eos=swelling_eos,
        enrichment_steps=_enrichment_schedule(),
    )

    assert len(result.steps) == 5
    assert result.enrichment_steps.tolist() == pytest.approx([0.0, 0.05, 0.10, 0.20, 0.35])
    assert result.fully_certified is True
    assert result.overall_status == "complete"
    assert result.baseline_bubble_pressure is not None
    assert result.baseline_saturated_liquid_molar_volume is not None
    assert np.isfinite(result.bubble_pressures).all()
    assert np.isfinite(result.swelling_factors).all()
    assert result.swelling_factors[0] == pytest.approx(1.0)
    assert all(step.status == "certified" for step in result.steps)
    assert all(step.enriched_feed_composition.shape == (4,) for step in result.steps)


@pytest.mark.parametrize(
    "schedule",
    (
        [-0.05, 0.10],
        [0.10, 0.10],
        [0.20, 0.10],
    ),
)
def test_swelling_rejects_invalid_enrichment_schedule(
    schedule,
    swelling_components,
    swelling_eos,
) -> None:
    with pytest.raises(ValidationError):
        simulate_swelling(
            oil_composition=_oil_feed(),
            injection_gas_composition=_gas_feed(),
            temperature=350.0,
            components=swelling_components,
            eos=swelling_eos,
            enrichment_steps=schedule,
        )


def test_swelling_rejects_mismatched_component_basis(swelling_components, swelling_eos) -> None:
    with pytest.raises(ValidationError):
        simulate_swelling(
            oil_composition=np.asarray([0.4, 0.3, 0.3], dtype=np.float64),
            injection_gas_composition=_gas_feed(),
            temperature=350.0,
            components=swelling_components,
            eos=swelling_eos,
            enrichment_steps=_enrichment_schedule(),
        )


def test_swelling_auto_inserts_zero_baseline(swelling_components, swelling_eos) -> None:
    result = simulate_swelling(
        oil_composition=_oil_feed(),
        injection_gas_composition=_gas_feed(),
        temperature=350.0,
        components=swelling_components,
        eos=swelling_eos,
        enrichment_steps=[0.10, 0.20],
    )

    assert result.enrichment_steps.tolist() == pytest.approx([0.0, 0.10, 0.20])
    assert result.steps[0].added_gas_moles_per_mole_oil == pytest.approx(0.0)


def test_swelling_surfaces_partial_failure_without_dropping_rows(
    swelling_components,
    swelling_eos,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pvtcore.experiments.swelling as swelling_module

    original = swelling_module.calculate_bubble_point
    call_count = 0

    def wrapped(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise PhaseError("No boundary for injected step", reason="no_saturation")
        return original(*args, **kwargs)

    monkeypatch.setattr(swelling_module, "calculate_bubble_point", wrapped)

    result = simulate_swelling(
        oil_composition=_oil_feed(),
        injection_gas_composition=_gas_feed(),
        temperature=350.0,
        components=swelling_components,
        eos=swelling_eos,
        enrichment_steps=[0.05, 0.10],
    )

    assert len(result.steps) == 3
    assert result.overall_status == "partial"
    assert result.fully_certified is False
    assert result.steps[1].status == "failed_no_boundary"
    assert result.steps[1].bubble_pressure is None
    assert np.isnan(result.steps[1].incipient_vapor_composition).all()
    assert np.isnan(result.steps[1].k_values).all()
    assert result.steps[2].status == "certified"


def test_swelling_repeat_runs_are_reproducible(swelling_components, swelling_eos) -> None:
    result_a = simulate_swelling(
        oil_composition=_oil_feed(),
        injection_gas_composition=_gas_feed(),
        temperature=350.0,
        components=swelling_components,
        eos=swelling_eos,
        enrichment_steps=_enrichment_schedule(),
    )
    result_b = simulate_swelling(
        oil_composition=_oil_feed(),
        injection_gas_composition=_gas_feed(),
        temperature=350.0,
        components=swelling_components,
        eos=swelling_eos,
        enrichment_steps=_enrichment_schedule(),
    )

    assert result_a.overall_status == result_b.overall_status
    assert result_a.enrichment_steps.tolist() == pytest.approx(result_b.enrichment_steps.tolist())
    assert result_a.bubble_pressures.tolist() == pytest.approx(result_b.bubble_pressures.tolist())
    assert result_a.swelling_factors.tolist() == pytest.approx(result_b.swelling_factors.tolist())
