"""Consolidated unit tests for the tuning/regression module.

Covers:
- Residual & objective-metric calculations
- ExperimentalPoint / ExperimentalDataSet
- TunableParameter / ParameterSet creation, validation, extraction
- EOSRegressor setup, dataset management, fitting
- Unsupported data-type error messaging
- Integration: simple regression + standalone objective function
"""

from __future__ import annotations

import numpy as np
import pytest

from pvtcore.tuning import (
    DataType,
    ExperimentalPoint,
    ExperimentalDataSet,
    ObjectiveResult,
    ObjectiveFunction,
    calculate_residual,
    calculate_objective_sse,
    calculate_objective_aad,
    create_saturation_objective,
    create_density_objective,
    ParameterType,
    TunableParameter,
    ParameterSet,
    create_kij_parameters,
    create_volume_shift_parameters,
    create_critical_multipliers,
    merge_parameter_sets,
    RegressionResult,
    EOSRegressor,
    tune_binary_interactions,
    sensitivity_analysis,
)
from pvtcore.eos.peng_robinson import PengRobinsonEOS
from pvtcore.core.errors import ValidationError


# ---------------------------------------------------------------------------
# Objective functions & data structures
# ---------------------------------------------------------------------------

def test_objectives_and_datasets(components):
    """Residuals, SSE/AAD metrics, ExperimentalPoint, ExperimentalDataSet."""
    # --- residuals ---
    assert calculate_residual(105.0, 100.0, relative=True) == pytest.approx(0.05)
    assert calculate_residual(105.0, 100.0, relative=False) == pytest.approx(5.0)
    assert calculate_residual(5.0, 0.0, relative=True) == 5.0
    assert calculate_residual(0.0, 0.0, relative=True) == 0.0

    # --- SSE / AAD ---
    residuals = np.array([0.1, -0.2, 0.15])
    assert calculate_objective_sse(residuals) == pytest.approx(0.1**2 + 0.2**2 + 0.15**2)
    aad = calculate_objective_aad(np.array([0.1, -0.2, 0.1]))
    assert aad == pytest.approx(np.mean([0.1, 0.2, 0.1]) * 100)

    # --- ExperimentalPoint ---
    pt = ExperimentalPoint(data_type=DataType.SATURATION_PRESSURE, temperature=300.0, pressure=None, value=5e6)
    assert pt.data_type == DataType.SATURATION_PRESSURE
    assert pt.weight == 1.0
    pt2 = ExperimentalPoint(data_type=DataType.LIQUID_DENSITY, temperature=300.0, pressure=5e6, value=500.0, uncertainty=5.0)
    assert pt2.uncertainty == 5.0

    # --- ExperimentalDataSet ---
    z = np.array([0.5, 0.5])
    points = [
        ExperimentalPoint(DataType.SATURATION_PRESSURE, 300.0, None, 5e6),
        ExperimentalPoint(DataType.SATURATION_PRESSURE, 320.0, None, 7e6),
    ]
    ds = ExperimentalDataSet("test", z, points)
    assert ds.n_points == 2
    assert len(ds.data_types) == 1

    # normalization
    ds2 = ExperimentalDataSet("test2", np.array([1.0, 1.0]), [ExperimentalPoint(DataType.SATURATION_PRESSURE, 300.0, None, 5e6)])
    assert abs(ds2.composition.sum() - 1.0) < 1e-10

    # empty points
    with pytest.raises(ValidationError):
        ExperimentalDataSet("empty", z, [])

    # filter by type
    mixed = ExperimentalDataSet("mixed", z, [
        ExperimentalPoint(DataType.SATURATION_PRESSURE, 300.0, None, 5e6),
        ExperimentalPoint(DataType.LIQUID_DENSITY, 300.0, 5e6, 500.0),
    ])
    assert len(mixed.get_points_by_type(DataType.SATURATION_PRESSURE)) == 1

    # --- creation helpers ---
    sat_ds = create_saturation_objective(np.array([300.0, 320.0, 340.0]), np.array([5e6, 7e6, 9e6]), z, "bubble")
    assert sat_ds.n_points == 3
    assert sat_ds.name == "bubble_pressure"

    den_ds = create_density_objective(np.array([300.0, 320.0]), np.array([5e6, 10e6]), np.array([500.0, 550.0]), z, "liquid")
    assert den_ds.n_points == 2
    assert den_ds.name == "liquid_density"


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------

def test_parameters(components):
    """TunableParameter, ParameterSet, creation helpers, extraction."""
    # --- basic parameter ---
    p = TunableParameter(name="kij_C1_C3", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.0, lower_bound=-0.1, upper_bound=0.1)
    assert p.bounds == (-0.1, 0.1)
    assert p.active is True

    # --- bounds validation ---
    with pytest.raises(ValidationError):
        TunableParameter(name="bad", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.0, lower_bound=0.1, upper_bound=-0.1)
    with pytest.raises(ValidationError):
        TunableParameter(name="bad", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.5, lower_bound=-0.1, upper_bound=0.1)

    # --- ParameterSet ---
    ps = ParameterSet(n_components=2)
    ps.add_parameter(TunableParameter(name="p1", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.05, lower_bound=-0.1, upper_bound=0.1))
    ps.add_parameter(TunableParameter(name="p2", param_type=ParameterType.BINARY_INTERACTION, initial_value=-0.02, lower_bound=-0.1, upper_bound=0.1))
    assert len(ps.parameters) == 2
    x0 = ps.get_initial_vector()
    assert x0[0] == 0.05 and x0[1] == -0.02

    params_d = ps.vector_to_dict(np.array([0.03, -0.01]))
    assert params_d["p1"] == 0.03

    # duplicate
    with pytest.raises(ValidationError):
        ps.add_parameter(TunableParameter(name="p1", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.0, lower_bound=-0.1, upper_bound=0.1))

    # --- creation helpers ---
    kij_p = create_kij_parameters(3, ["C1", "C3", "C7"])
    assert kij_p.n_active == 3
    assert kij_p.n_components == 3

    kij_active = create_kij_parameters(3, ["C1", "C3", "C7"], active_pairs=[(0, 2)])
    assert kij_active.n_active == 1

    vs_p = create_volume_shift_parameters(3, ["C1", "C3", "C7"])
    assert vs_p.n_active == 3

    merged = merge_parameter_sets(create_kij_parameters(2, ["C1", "C3"]), create_volume_shift_parameters(2, ["C1", "C3"]))
    assert len(merged.parameters) == 3

    # --- extraction ---
    kij3 = create_kij_parameters(3, ["C1", "C3", "C7"])
    kij_mat = kij3.extract_kij_matrix({"kij_C1_C3": 0.01, "kij_C1_C7": 0.02, "kij_C3_C7": 0.005})
    assert kij_mat[0, 1] == 0.01 and kij_mat[1, 0] == 0.01
    assert kij_mat[0, 2] == 0.02
    assert kij_mat[1, 2] == 0.005

    vs2 = create_volume_shift_parameters(2, ["C1", "C3"])
    shifts = vs2.extract_volume_shifts({"c_C1": 0.001, "c_C3": -0.002})
    assert shifts[0] == 0.001 and shifts[1] == -0.002


# ---------------------------------------------------------------------------
# Regression engine + unsupported data type
# ---------------------------------------------------------------------------

def test_regression(components):
    """EOSRegressor: init, dataset management, fitting, result structure, unsupported DataType."""
    c1, c3 = components["C1"], components["C3"]
    comps = [c1, c3]
    eos = PengRobinsonEOS(comps)
    params = create_kij_parameters(2, ["C1", "C3"])
    regressor = EOSRegressor(comps, eos, params)

    assert regressor.components == comps
    assert len(regressor.datasets) == 0

    z = np.array([0.5, 0.5])
    data = create_saturation_objective(np.array([300.0]), np.array([5e6]), z, "bubble")
    regressor.add_dataset(data)
    assert len(regressor.datasets) == 1

    # fit without datasets
    empty_reg = EOSRegressor(comps, eos, create_kij_parameters(2, ["C1", "C3"]))
    with pytest.raises(ValidationError):
        empty_reg.fit()

    # fit without active params
    no_active = EOSRegressor(comps, eos, create_kij_parameters(2, ["C1", "C3"], active_pairs=[]))
    no_active.add_dataset(data)
    with pytest.raises(ValidationError):
        no_active.fit()

    # --- simple regression (synthetic) ---
    T_exp = np.array([280.0, 300.0, 320.0])
    P_exp = np.array([2.5e6, 4.0e6, 5.5e6])
    data2 = create_saturation_objective(T_exp, P_exp, z, "bubble")

    reg2 = EOSRegressor(comps, eos, create_kij_parameters(2, ["C1", "C3"]))
    reg2.add_dataset(data2)
    result = reg2.fit(method="Nelder-Mead", maxiter=5)

    assert isinstance(result, RegressionResult)
    assert "kij_C1_C3" in result.optimal_params
    assert result.n_evaluations > 0

    # --- RegressionResult structure ---
    rr = RegressionResult(
        success=True, optimal_params={"kij": 0.01}, initial_objective=1.0, final_objective=0.1,
        improvement=90.0, n_iterations=10, n_evaluations=50, elapsed_time=1.5,
        convergence_message="Converged", parameter_set=ParameterSet(),
    )
    assert rr.success and rr.improvement == 90.0

    # --- standalone ObjectiveFunction ---
    points = [ExperimentalPoint(data_type=DataType.VAPOR_FRACTION, temperature=300.0, pressure=3e6, value=0.5)]
    ds = ExperimentalDataSet("test", z, points)
    obj = ObjectiveFunction([ds], lambda pt, p: 0.55, metric="sse")
    assert obj({}) > 0

    # --- unsupported DataType error message ---
    params_us = create_kij_parameters(2, ["C1", "C3"])
    reg_us = EOSRegressor(comps, eos, params_us)
    point = ExperimentalPoint(data_type=DataType.GOR, temperature=300.0, pressure=5_000_000.0, value=1.0, composition=np.array([0.5, 0.5]))
    with pytest.raises(NotImplementedError) as excinfo:
        reg_us._model_function(point, {})
    msg = str(excinfo.value)
    assert "Unsupported DataType=GOR" in msg
    assert "Supported:" in msg
    assert "SATURATION_PRESSURE" in msg
    assert "Filter the dataset" in msg


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_tuning_edge_cases():
    """Tuning edge cases: bounds validation, empty datasets."""
    # Already covered inline above; this function kept for explicit parametrized extension.
    with pytest.raises(ValidationError):
        TunableParameter(name="x", param_type=ParameterType.BINARY_INTERACTION, initial_value=0.0, lower_bound=1.0, upper_bound=-1.0)
