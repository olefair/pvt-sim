"""EOS parameter regression using optimization.

This module provides the main regression functionality for tuning
EOS parameters against experimental PVT data. It wraps scipy.optimize
with PVT-specific handling for:
- Binary interaction parameters (kij)
- Volume shift parameters
- Critical property adjustments

The regression workflow:
1. Define experimental data (ExperimentalDataSet)
2. Define parameters to tune (ParameterSet)
3. Create model evaluation function
4. Run optimization
5. Extract optimal parameters and statistics

Supported optimization methods:
- L-BFGS-B (gradient-based, bounded)
- SLSQP (gradient-based, bounded/constrained)
- differential_evolution (global, gradient-free)
- Nelder-Mead (local, gradient-free)

Units Convention:
- All units consistent with pvtcore conventions
- Pressure: Pa, Temperature: K, Density: kg/m³

References
----------
[1] Pedersen et al. (2015). Phase Behavior of Petroleum Reservoir Fluids.
[2] Numerical Optimization (Nocedal & Wright).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable, Tuple, Union
import time
import warnings

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, ValidationError
from ..eos.base import CubicEOS
from ..models.component import Component
from ..flash.pt_flash import pt_flash
from ..flash.bubble_point import calculate_bubble_point
from ..flash.dew_point import calculate_dew_point
from ..properties.density import calculate_density

from .objectives import (
    ObjectiveFunction,
    ObjectiveResult,
    ExperimentalDataSet,
    ExperimentalPoint,
    DataType,
)
from .parameters import ParameterSet, ParameterType


SUPPORTED_DATA_TYPES = (
    DataType.SATURATION_PRESSURE,
    DataType.LIQUID_DENSITY,
    DataType.VAPOR_DENSITY,
    DataType.VAPOR_FRACTION,
    DataType.Z_FACTOR,
)


def _unsupported_data_type_error(data_type: DataType) -> NotImplementedError:
    supported = ", ".join(dt.name for dt in SUPPORTED_DATA_TYPES)
    guidance = "Filter the dataset to supported types or extend EOSRegressor._model_function."
    return NotImplementedError(
        f"Unsupported DataType={data_type.name}. Supported: {supported}. {guidance}"
    )


def _require_scipy_optimize():
    try:
        from scipy import optimize
    except Exception as exc:
        raise RuntimeError(
            "SciPy is required for regression. Install with: pip install -e '.[full]'"
        ) from exc
    return optimize


@dataclass
class RegressionResult:
    """Results from EOS parameter regression.

    Attributes:
        success: True if optimization converged
        optimal_params: Optimized parameter values
        initial_objective: Objective before optimization
        final_objective: Objective after optimization
        improvement: Relative improvement (%)
        n_iterations: Number of optimizer iterations
        n_evaluations: Number of objective evaluations
        elapsed_time: Wall-clock time (seconds)
        convergence_message: Message from optimizer
        parameter_set: ParameterSet with updated initial values
        objective_details: Detailed breakdown of final objective
        optimization_history: History of objective values (if tracked)
    """
    success: bool
    optimal_params: Dict[str, float]
    initial_objective: float
    final_objective: float
    improvement: float
    n_iterations: int
    n_evaluations: int
    elapsed_time: float
    convergence_message: str
    parameter_set: ParameterSet
    objective_details: Optional[ObjectiveResult] = None
    optimization_history: List[float] = field(default_factory=list)


class EOSRegressor:
    """EOS parameter regression engine.

    This class manages the regression of EOS parameters against
    experimental PVT data.

    Parameters
    ----------
    components : list of Component
        Component objects for the mixture.
    eos : CubicEOS
        Equation of state to tune.
    parameter_set : ParameterSet
        Parameters to optimize.

    Examples
    --------
    >>> from pvtcore.tuning import EOSRegressor, create_kij_parameters
    >>> from pvtcore.tuning import create_saturation_objective
    >>> # Setup
    >>> params = create_kij_parameters(2, ['C1', 'C10'])
    >>> regressor = EOSRegressor(components, eos, params)
    >>> # Add experimental data
    >>> data = create_saturation_objective(T_exp, P_exp, z, 'bubble')
    >>> regressor.add_dataset(data)
    >>> # Run regression
    >>> result = regressor.fit()
    >>> print(f"Optimal kij: {result.optimal_params}")
    """

    def __init__(
        self,
        components: List[Component],
        eos: CubicEOS,
        parameter_set: ParameterSet,
    ):
        self.components = components
        self.eos = eos
        self.parameter_set = parameter_set
        self.datasets: List[ExperimentalDataSet] = []

        # Evaluation counter
        self._n_evals = 0
        self._history: List[float] = []

    def add_dataset(self, dataset: ExperimentalDataSet) -> None:
        """Add experimental dataset for regression.

        Parameters
        ----------
        dataset : ExperimentalDataSet
            Experimental data to match.
        """
        self.datasets.append(dataset)

    def clear_datasets(self) -> None:
        """Remove all datasets."""
        self.datasets.clear()

    def _model_function(
        self,
        point: ExperimentalPoint,
        params: Dict[str, float],
    ) -> float:
        """Evaluate model at an experimental point.

        Parameters
        ----------
        point : ExperimentalPoint
            Point to evaluate.
        params : dict
            Current parameter values.

        Returns
        -------
        float
            Model-calculated value.
        """
        # Extract kij matrix from parameters
        kij = self.parameter_set.extract_kij_matrix(params)

        # Get composition
        comp = point.composition
        if comp is None:
            # Find matching dataset
            for ds in self.datasets:
                if point in ds.points:
                    comp = ds.composition
                    break
        if comp is None:
            raise ValueError("No composition available for point")

        T = point.temperature
        P = point.pressure

        if point.data_type == DataType.SATURATION_PRESSURE:
            # Calculate saturation pressure
            sat_type = point.metadata.get('saturation_type', 'bubble')
            if sat_type == 'bubble':
                result = calculate_bubble_point(T, comp, self.components, self.eos, binary_interaction=kij)
                return result.pressure
            else:
                result = calculate_dew_point(T, comp, self.components, self.eos, binary_interaction=kij)
                return result.pressure

        elif point.data_type in (DataType.LIQUID_DENSITY, DataType.VAPOR_DENSITY):
            phase = 'liquid' if point.data_type == DataType.LIQUID_DENSITY else 'vapor'
            result = calculate_density(P, T, comp, self.components, self.eos, phase, kij)
            return result.mass_density

        elif point.data_type == DataType.VAPOR_FRACTION:
            flash = pt_flash(P, T, comp, self.components, self.eos, binary_interaction=kij)
            return flash.vapor_fraction

        elif point.data_type == DataType.Z_FACTOR:
            phase = point.metadata.get('phase', 'vapor')
            Z = self.eos.compressibility(P, T, comp, phase=phase, binary_interaction=kij)
            if isinstance(Z, list):
                Z = Z[-1] if phase == 'vapor' else Z[0]
            return Z

        else:
            raise _unsupported_data_type_error(point.data_type)

    def _objective(self, x: NDArray[np.float64]) -> float:
        """Objective function for optimizer.

        Parameters
        ----------
        x : ndarray
            Parameter vector.

        Returns
        -------
        float
            Objective value (to minimize).
        """
        self._n_evals += 1

        # Convert to dictionary
        params = self.parameter_set.vector_to_dict(x)

        # Evaluate objective
        obj_func = ObjectiveFunction(
            datasets=self.datasets,
            model_function=self._model_function,
            metric='sse',
        )

        try:
            obj_value = obj_func(params)
        except Exception:
            obj_value = 1e10  # Large penalty for failures

        self._history.append(obj_value)
        return obj_value

    def fit(
        self,
        method: str = 'L-BFGS-B',
        maxiter: int = 100,
        tol: float = 1e-6,
        verbose: bool = False,
        **kwargs,
    ) -> RegressionResult:
        """Run parameter regression.

        Parameters
        ----------
        method : str
            Optimization method: 'L-BFGS-B', 'SLSQP', 'Nelder-Mead',
            'differential_evolution'.
        maxiter : int
            Maximum iterations.
        tol : float
            Convergence tolerance.
        verbose : bool
            Print progress information.
        **kwargs
            Additional arguments for optimizer.

        Returns
        -------
        RegressionResult
            Regression results including optimal parameters.
        """
        if not self.datasets:
            raise ValidationError("No datasets added for regression", parameter="datasets")

        if self.parameter_set.n_active == 0:
            raise ValidationError("No active parameters to tune", parameter="parameter_set")

        # Reset counters
        self._n_evals = 0
        self._history = []

        # Get initial state
        x0 = self.parameter_set.get_initial_vector()
        bounds = self.parameter_set.get_bounds_list()

        # Calculate initial objective
        initial_params = self.parameter_set.vector_to_dict(x0)
        obj_func = ObjectiveFunction(
            datasets=self.datasets,
            model_function=self._model_function,
            metric='sse',
        )
        initial_objective = obj_func(initial_params)

        if verbose:
            print(f"Starting regression with {self.parameter_set.n_active} parameters")
            print(f"Initial objective: {initial_objective:.6e}")

        start_time = time.time()

        optimize = _require_scipy_optimize()

        # Run optimization
        if method.lower() == 'differential_evolution':
            result = optimize.differential_evolution(
                self._objective,
                bounds=bounds,
                maxiter=maxiter,
                tol=tol,
                **kwargs,
            )
        else:
            result = optimize.minimize(
                self._objective,
                x0,
                method=method,
                bounds=bounds,
                options={'maxiter': maxiter, 'disp': verbose},
                tol=tol,
                **kwargs,
            )

        elapsed_time = time.time() - start_time

        # Extract results
        optimal_x = result.x
        optimal_params = self.parameter_set.vector_to_dict(optimal_x)
        final_objective = result.fun

        # Calculate improvement
        if initial_objective > 0:
            improvement = (initial_objective - final_objective) / initial_objective * 100
        else:
            improvement = 0.0

        # Get detailed objective breakdown
        objective_details = obj_func.evaluate(optimal_params, return_details=True)

        # Update parameter set with optimal values
        updated_param_set = ParameterSet(n_components=self.parameter_set.n_components)
        for param in self.parameter_set.parameters:
            new_param = TunableParameter(
                name=param.name,
                param_type=param.param_type,
                initial_value=optimal_params.get(param.name, param.initial_value),
                lower_bound=param.lower_bound,
                upper_bound=param.upper_bound,
                active=param.active,
                component_i=param.component_i,
                component_j=param.component_j,
                component=param.component,
                description=param.description,
            )
            updated_param_set.parameters.append(new_param)

        if verbose:
            print(f"Final objective: {final_objective:.6e}")
            print(f"Improvement: {improvement:.1f}%")
            print(f"Evaluations: {self._n_evals}")

        return RegressionResult(
            success=result.success,
            optimal_params=optimal_params,
            initial_objective=initial_objective,
            final_objective=final_objective,
            improvement=improvement,
            n_iterations=getattr(result, 'nit', 0),
            n_evaluations=self._n_evals,
            elapsed_time=elapsed_time,
            convergence_message=result.message if hasattr(result, 'message') else str(result),
            parameter_set=updated_param_set,
            objective_details=objective_details,
            optimization_history=self._history.copy(),
        )


# Import TunableParameter for the fit method
from .parameters import TunableParameter


def tune_binary_interactions(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    experimental_data: List[ExperimentalDataSet],
    initial_kij: Optional[NDArray[np.float64]] = None,
    kij_bounds: Tuple[float, float] = (-0.15, 0.15),
    method: str = 'L-BFGS-B',
    maxiter: int = 100,
    verbose: bool = False,
) -> Tuple[NDArray[np.float64], RegressionResult]:
    """Convenience function to tune binary interaction parameters.

    Parameters
    ----------
    composition : ndarray
        Reference composition (mole fractions).
    components : list of Component
        Component objects.
    eos : CubicEOS
        Equation of state.
    experimental_data : list of ExperimentalDataSet
        Experimental data to match.
    initial_kij : ndarray, optional
        Initial kij matrix. Default is zeros.
    kij_bounds : tuple
        (lower, upper) bounds for kij values.
    method : str
        Optimization method.
    maxiter : int
        Maximum iterations.
    verbose : bool
        Print progress.

    Returns
    -------
    tuple
        (optimal_kij_matrix, regression_result)

    Examples
    --------
    >>> # Create experimental data
    >>> from pvtcore.tuning import create_saturation_objective
    >>> T_exp = np.array([300, 320, 340])  # K
    >>> P_exp = np.array([5e6, 7e6, 9e6])  # Pa
    >>> data = create_saturation_objective(T_exp, P_exp, z, 'bubble')
    >>> # Tune kij
    >>> kij, result = tune_binary_interactions(z, components, eos, [data])
    >>> print(f"Optimal kij matrix:\\n{kij}")
    """
    from .parameters import create_kij_parameters

    nc = len(components)
    component_names = [c.name for c in components]

    if initial_kij is None:
        initial_kij = np.zeros((nc, nc))

    # Create parameter set
    param_set = create_kij_parameters(
        nc,
        component_names=component_names,
        initial_values=initial_kij,
        bounds=kij_bounds,
    )

    # Create regressor
    regressor = EOSRegressor(components, eos, param_set)
    for data in experimental_data:
        regressor.add_dataset(data)

    # Run regression
    result = regressor.fit(method=method, maxiter=maxiter, verbose=verbose)

    # Extract optimal kij matrix
    optimal_kij = param_set.extract_kij_matrix(result.optimal_params)

    return optimal_kij, result


def tune_volume_shifts(
    composition: NDArray[np.float64],
    components: List[Component],
    eos: CubicEOS,
    experimental_data: List[ExperimentalDataSet],
    active_components: Optional[List[int]] = None,
    shift_bounds: Tuple[float, float] = (-0.01, 0.01),
    method: str = 'L-BFGS-B',
    maxiter: int = 100,
    verbose: bool = False,
) -> Tuple[NDArray[np.float64], RegressionResult]:
    """Convenience function to tune volume shift parameters.

    Parameters
    ----------
    composition : ndarray
        Reference composition.
    components : list of Component
        Component objects.
    eos : CubicEOS
        Equation of state.
    experimental_data : list of ExperimentalDataSet
        Experimental data (typically density).
    active_components : list of int, optional
        Which components to tune (default all).
    shift_bounds : tuple
        (lower, upper) bounds for shifts.
    method : str
        Optimization method.
    maxiter : int
        Maximum iterations.
    verbose : bool
        Print progress.

    Returns
    -------
    tuple
        (optimal_shifts, regression_result)
    """
    from .parameters import create_volume_shift_parameters

    nc = len(components)
    component_names = [c.name for c in components]

    param_set = create_volume_shift_parameters(
        nc,
        component_names=component_names,
        active_components=active_components,
        bounds=shift_bounds,
    )

    regressor = EOSRegressor(components, eos, param_set)
    for data in experimental_data:
        regressor.add_dataset(data)

    result = regressor.fit(method=method, maxiter=maxiter, verbose=verbose)

    optimal_shifts = param_set.extract_volume_shifts(result.optimal_params)

    return optimal_shifts, result


def sensitivity_analysis(
    regressor: EOSRegressor,
    optimal_params: Dict[str, float],
    perturbation: float = 0.01,
) -> Dict[str, float]:
    """Perform sensitivity analysis on optimal parameters.

    Calculates how much the objective changes when each parameter
    is perturbed by a small amount.

    Parameters
    ----------
    regressor : EOSRegressor
        Configured regressor.
    optimal_params : dict
        Optimal parameter values.
    perturbation : float
        Relative perturbation (fraction).

    Returns
    -------
    dict
        Sensitivity values for each parameter.
        Higher values indicate more sensitive parameters.
    """
    obj_func = ObjectiveFunction(
        datasets=regressor.datasets,
        model_function=regressor._model_function,
        metric='sse',
    )

    base_objective = obj_func(optimal_params)
    sensitivities = {}

    for param in regressor.parameter_set.active_parameters:
        # Perturb parameter
        perturbed = optimal_params.copy()
        delta = abs(param.initial_value * perturbation)
        if delta < 1e-10:
            delta = perturbation  # Use absolute for near-zero values

        perturbed[param.name] = optimal_params[param.name] + delta

        # Evaluate perturbed objective
        try:
            perturbed_obj = obj_func(perturbed)
            sensitivity = abs(perturbed_obj - base_objective) / delta
        except Exception:
            sensitivity = np.nan

        sensitivities[param.name] = sensitivity

    return sensitivities
