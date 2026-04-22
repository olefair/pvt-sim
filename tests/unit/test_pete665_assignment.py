import numpy as np
import pytest

from pvtcore.eos import PR78EOS
from pvtcore.flash import calculate_bubble_point, calculate_dew_point
from pvtcore.validation.pete665_assignment import (
    build_assignment_fluid,
    default_assignment_case_path,
    fahrenheit_to_kelvin,
    load_assignment_case,
    resolve_assignment_temperature_f,
    run_assignment_case,
)


def test_assignment_case_file_exists() -> None:
    assert default_assignment_case_path().exists()


def test_assignment_case_loads_and_keeps_expected_pressures() -> None:
    case = load_assignment_case()

    assert case.cce_pressures_psia == pytest.approx((1500.0, 1250.0, 1000.0))
    assert case.dl_pressures_psia == pytest.approx((500.0, 300.0, 100.0))
    assert "TANS" in case.temperature_by_initials_f


def test_assignment_fluid_builds_with_inline_pseudo_component() -> None:
    case = load_assignment_case()
    component_ids, components, composition = build_assignment_fluid(case)

    assert np.isclose(float(composition.sum()), 1.0)
    assert component_ids[-1] == "PSEUDO_PLUS"
    assert components[-1].is_pseudo is True
    assert components[-1].Tb > 0.0
    assert components[-1].Vc > 0.0


def test_temperature_resolution_supports_initials_and_explicit_override() -> None:
    case = load_assignment_case()

    temperature_f, initials = resolve_assignment_temperature_f(case, initials="tans")
    assert temperature_f == pytest.approx(125.0)
    assert initials == "TANS"

    explicit_temperature_f, explicit_initials = resolve_assignment_temperature_f(case, temperature_f=130.0)
    assert explicit_temperature_f == pytest.approx(130.0)
    assert explicit_initials is None


def test_assignment_runner_smoke() -> None:
    result = run_assignment_case(temperature_f=125.0)

    assert result["selected_temperature_f"] == pytest.approx(125.0)
    assert result["saturation_pressure"]["converged"] is True
    assert [step["pressure_psia"] for step in result["cce"]["steps"]] == pytest.approx([1500.0, 1250.0, 1000.0])

    dl_steps = result["dl"]["steps"]
    schedule_pressures = [
        step["pressure_psia"]
        for step in dl_steps
        if step.get("phase") == "reservoir"
    ]
    assert schedule_pressures == pytest.approx([500.0, 300.0, 100.0])
    assert all("bg" in step for step in dl_steps)
    assert any(step.get("phase") == "bubble" for step in dl_steps)
    assert any(step.get("phase") == "stock_tank" for step in dl_steps)
    assert result["dl"]["validations"]["stock_bo_close_to_one"]["ok"] is True
    assert result["dl"]["validations"]["stock_rs_close_to_zero"]["ok"] is True


def test_assignment_bubble_point_is_robust_to_bad_initial_guesses() -> None:
    case = load_assignment_case()
    _component_ids, components, composition = build_assignment_fluid(case)
    eos = PR78EOS(components)
    temperature_k = fahrenheit_to_kelvin(125.0)

    reference = calculate_bubble_point(
        temperature_k,
        composition,
        components,
        eos,
    )

    for guess_psia in (100.0, 700.0, 1423.0, 1600.0):
        result = calculate_bubble_point(
            temperature_k,
            composition,
            components,
            eos,
            pressure_initial=guess_psia * 6894.757293168361,
        )
        assert result.converged is True
        assert result.pressure == pytest.approx(reference.pressure, abs=250.0)


def test_assignment_dew_point_is_robust_to_bad_initial_guesses() -> None:
    case = load_assignment_case()
    _component_ids, components, composition = build_assignment_fluid(case)
    eos = PR78EOS(components)
    temperature_k = fahrenheit_to_kelvin(125.0)

    reference = calculate_dew_point(
        temperature_k,
        composition,
        components,
        eos,
    )

    for guess_psia in (300.0, 500.0, 700.0, 1000.0, 1500.0):
        result = calculate_dew_point(
            temperature_k,
            composition,
            components,
            eos,
            pressure_initial=guess_psia * 6894.757293168361,
        )
        assert result.converged is True
        assert result.pressure == pytest.approx(reference.pressure, abs=250.0)
