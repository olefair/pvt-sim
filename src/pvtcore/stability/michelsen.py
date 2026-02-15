"""Michelsen stability test for phase equilibrium analysis.

Implementation of the successive substitution algorithm for phase stability
testing as described in Michelsen (1982).

Reference:
Michelsen, M. L., "The Isothermal Flash Problem. Part I. Stability",
Fluid Phase Equilibria, 9(1), 1-19 (1982).
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from numpy.typing import NDArray

from ..eos.base import CubicEOS
from ..core.errors import ConvergenceError, ValidationError, ConvergenceStatus, IterationHistory
from .wilson import wilson_k_values
from .tpd import calculate_tpd, calculate_d_terms


# Numerical tolerances
STABILITY_TOLERANCE: float = 1e-10  # Convergence tolerance for ln(W_new/W_old)
MAX_STABILITY_ITERATIONS: int = 1000  # Maximum iterations for stability test
TPD_TOLERANCE: float = 1e-8  # Tolerance for considering TPD = 0


@dataclass
class StabilityResult:
    """Results from Michelsen stability analysis.

    Attributes:
        status: Convergence status enum (CONVERGED, MAX_ITERS, etc.)
        stable: True if mixture is stable (single phase)
        tpd_min: Minimum TPD value found
        trial_compositions: List of trial compositions tested
        tpd_values: TPD values for each trial composition
        iterations: Number of iterations for each trial
        feed_phase: Phase of the feed composition
        history: Optional iteration history for diagnostics
    """
    status: ConvergenceStatus
    stable: bool
    tpd_min: float
    trial_compositions: List[NDArray[np.float64]]
    tpd_values: List[float]
    iterations: List[int]
    feed_phase: str
    history: Optional[IterationHistory] = None

    @property
    def converged(self) -> bool:
        """Backward-compatible property: True if calculation converged."""
        return self.status == ConvergenceStatus.CONVERGED


def michelsen_stability_test(
    composition: NDArray[np.float64],
    pressure: float,
    temperature: float,
    eos: CubicEOS,
    feed_phase: str = 'liquid',
    binary_interaction: Optional[NDArray[np.float64]] = None,
    tolerance: float = STABILITY_TOLERANCE,
    max_iterations: int = MAX_STABILITY_ITERATIONS
) -> StabilityResult:
    """Perform Michelsen stability test using successive substitution.

    Tests whether a single-phase mixture is stable or will split into two phases.
    Initializes trial compositions from Wilson K-values and iterates until
    convergence or maximum iterations.

    The successive substitution iteration is:
        Wᵢ_new = exp(dᵢ - ln(φᵢ(W)))

    where dᵢ = ln(zᵢ) + ln(φᵢ(z)) are the feed fugacity terms.

    Parameters
    ----------
    composition : NDArray[np.float64]
        Feed composition (mole fractions)
    pressure : float
        System pressure (Pa)
    temperature : float
        System temperature (K)
    eos : CubicEOS
        Equation of state object
    feed_phase : str, optional
        Phase of feed ('liquid' or 'vapor'), default 'liquid'
    binary_interaction : NDArray[np.float64], optional
        Binary interaction parameters kᵢⱼ (n×n matrix)
    tolerance : float, optional
        Convergence tolerance for |ln(Wᵢ_new/Wᵢ_old)|
    max_iterations : int, optional
        Maximum number of iterations per trial

    Returns
    -------
    StabilityResult
        Result object with stability status and details

    Raises
    ------
    ValidationError
        If input parameters are invalid
    ConvergenceError
        If stability test fails to converge for critical trials

    Notes
    -----
    - Tests both vapor-like and liquid-like trial compositions
    - Vapor-like: W = K × z (light components enriched)
    - Liquid-like: W = z / K (heavy components enriched)
    - Mixture is stable if all TPD values are non-negative
    - Mixture is unstable if any TPD < 0

    Example
    -------
    >>> from pvtcore.eos import PengRobinsonEOS
    >>> from pvtcore.models import load_components
    >>> components = load_components()
    >>> eos = PengRobinsonEOS([components['C1'], components['C10']])
    >>> z = np.array([0.5, 0.5])
    >>> result = michelsen_stability_test(z, 5e6, 300, eos, feed_phase='liquid')
    >>> if not result.stable:
    ...     print("Mixture is unstable - two phases will form")
    """
    # Validate inputs
    composition = np.asarray(composition, dtype=np.float64)

    if len(composition) != eos.n_components:
        raise ValidationError(
            "Composition length must match number of components in EOS",
            parameter='composition',
            value={'got': len(composition), 'expected': eos.n_components}
        )

    if not np.isclose(composition.sum(), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0, got {composition.sum():.6f}",
            parameter='composition'
        )

    if pressure <= 0:
        raise ValidationError("Pressure must be positive", parameter='pressure', value=pressure)

    if temperature <= 0:
        raise ValidationError("Temperature must be positive", parameter='temperature', value=temperature)

    if feed_phase not in ['liquid', 'vapor']:
        raise ValidationError(
            "Feed phase must be 'liquid' or 'vapor'",
            parameter='feed_phase',
            value=feed_phase
        )

    # Calculate d terms for feed composition
    # d_terms = ln(z) + ln(φ(z))
    d_terms = calculate_d_terms(
        composition, eos, pressure, temperature, feed_phase, binary_interaction
    )

    # Also get ln(φ(z)) for TPD calculation
    phi_feed = eos.fugacity_coefficient(
        pressure, temperature, composition, feed_phase, binary_interaction
    )
    ln_phi_feed = np.log(phi_feed)

    # Initialize trial compositions from Wilson K-values
    K_wilson = wilson_k_values(pressure, temperature, eos.components)

    # Generate trial compositions
    # Trial 1: Vapor-like (W = K × z, enriched in light components)
    # Trial 2: Liquid-like (W = z / K, enriched in heavy components)
    trial_specs = []

    # Vapor-like trial (test if liquid feed wants to vaporize)
    W_vapor = K_wilson * composition
    W_vapor = W_vapor / W_vapor.sum()  # Normalize
    trial_specs.append(('vapor', W_vapor))

    # Liquid-like trial (test if vapor feed wants to condense)
    W_liquid = composition / K_wilson
    W_liquid = W_liquid / W_liquid.sum()  # Normalize
    trial_specs.append(('liquid', W_liquid))

    # Perform stability test for each trial
    results_list = []
    for trial_phase, W_init in trial_specs:
        result = _stability_test_single_trial(
            W_init, composition, d_terms, ln_phi_feed, eos, pressure, temperature,
            trial_phase, binary_interaction, tolerance, max_iterations
        )
        results_list.append(result)

    # Determine overall stability
    tpd_values = [r['tpd'] for r in results_list]
    tpd_min = min(tpd_values)

    # Stable if all TPD values are non-negative (within tolerance)
    # Convert to Python bool to avoid numpy bool issues
    stable = bool(tpd_min >= -TPD_TOLERANCE)

    # Check convergence and determine status
    all_converged = all(r['converged'] for r in results_list)

    # Build iteration history from all trials
    history = IterationHistory()
    total_func_evals = sum(r['iterations'] for r in results_list)
    history.n_func_evals = total_func_evals

    # Determine convergence status
    if all_converged:
        status = ConvergenceStatus.CONVERGED
    else:
        # Check if any trial hit max iterations
        status = ConvergenceStatus.MAX_ITERS

    return StabilityResult(
        status=status,
        stable=stable,
        tpd_min=tpd_min,
        trial_compositions=[r['composition'] for r in results_list],
        tpd_values=tpd_values,
        iterations=[r['iterations'] for r in results_list],
        feed_phase=feed_phase,
        history=history,
    )


def _stability_test_single_trial(
    W_init: NDArray[np.float64],
    feed_composition: NDArray[np.float64],
    d_terms: NDArray[np.float64],
    ln_phi_feed: NDArray[np.float64],
    eos: CubicEOS,
    pressure: float,
    temperature: float,
    trial_phase: str,
    binary_interaction: Optional[NDArray[np.float64]],
    tolerance: float,
    max_iterations: int
) -> dict:
    """Perform stability test for a single trial composition.

    Uses successive substitution to minimize TPD for given trial.

    Parameters
    ----------
    W_init : NDArray[np.float64]
        Initial trial composition
    feed_composition : NDArray[np.float64]
        Feed composition
    d_terms : NDArray[np.float64]
        Pre-calculated d terms for feed: d = ln(z) + ln(φ(z))
    ln_phi_feed : NDArray[np.float64]
        Natural log of feed fugacity coefficients
    eos : CubicEOS
        Equation of state
    pressure : float
        Pressure (Pa)
    temperature : float
        Temperature (K)
    trial_phase : str
        Phase of trial ('liquid' or 'vapor')
    binary_interaction : NDArray[np.float64], optional
        Binary interaction parameters
    tolerance : float
        Convergence tolerance
    max_iterations : int
        Maximum iterations

    Returns
    -------
    dict
        Dictionary with 'composition', 'tpd', 'iterations', 'converged'
    """
    W = W_init.copy()
    epsilon = 1e-100  # Avoid log(0)

    converged = False
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        # Calculate fugacity coefficients for current trial composition
        phi_W = eos.fugacity_coefficient(
            pressure, temperature, W, trial_phase, binary_interaction
        )
        ln_phi_W = np.log(phi_W)

        # Successive substitution: Wᵢ_new = exp(dᵢ - ln(φᵢ(W)))
        W_new = np.exp(d_terms - ln_phi_W)

        # Normalize
        W_new = W_new / W_new.sum()

        # Check convergence: |ln(Wᵢ_new/Wᵢ_old)| < tolerance for all i
        ln_ratio = np.log(np.maximum(W_new, epsilon)) - np.log(np.maximum(W, epsilon))
        max_change = np.max(np.abs(ln_ratio))

        if max_change < tolerance:
            converged = True
            W = W_new
            break

        # Update for next iteration
        W = W_new

    # Calculate final TPD value
    # ln_phi_feed is already passed in, calculated in the feed phase
    tpd = calculate_tpd(
        W, feed_composition, ln_phi_feed, eos,
        pressure, temperature, trial_phase, binary_interaction
    )

    return {
        'composition': W,
        'tpd': tpd,
        'iterations': iteration,
        'converged': converged
    }


def is_stable(
    composition: NDArray[np.float64],
    pressure: float,
    temperature: float,
    eos: CubicEOS,
    feed_phase: str = 'liquid',
    binary_interaction: Optional[NDArray[np.float64]] = None
) -> bool:
    """Simplified stability check returning only boolean result.

    Convenience function that returns only whether the mixture is stable.

    Parameters
    ----------
    composition : NDArray[np.float64]
        Feed composition (mole fractions)
    pressure : float
        System pressure (Pa)
    temperature : float
        System temperature (K)
    eos : CubicEOS
        Equation of state object
    feed_phase : str, optional
        Phase of feed ('liquid' or 'vapor')
    binary_interaction : NDArray[np.float64], optional
        Binary interaction parameters kᵢⱼ

    Returns
    -------
    bool
        True if mixture is stable (single phase), False if unstable (two phases)

    Example
    -------
    >>> if is_stable(z, P, T, eos):
    ...     print("Single phase")
    ... else:
    ...     print("Two phases - perform flash calculation")
    """
    result = michelsen_stability_test(
        composition, pressure, temperature, eos,
        feed_phase, binary_interaction
    )
    return result.stable
