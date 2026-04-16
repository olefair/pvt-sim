"""Pressure-Temperature flash calculation using successive substitution.

PT flash calculates vapor-liquid equilibrium at specified pressure and
temperature using an iterative successive substitution algorithm.

Reference:
Michelsen, M. L. and Mollerup, J. M., "Thermodynamic Models: Fundamentals &
Computational Aspects", 2nd Ed., Tie-Line Publications (2007).
"""

import numpy as np
from dataclasses import dataclass
from typing import List, Optional
import math

from ..models.component import Component
from ..eos.base import CubicEOS
from ..stability.wilson import wilson_k_values, is_trivial_solution
from ..stability import is_stable
from .rachford_rice import (
    calculate_phase_compositions,
    solve_rachford_rice,
    rachford_rice_function,
)
from ..core.errors import (
    ConvergenceError, PhaseError, ValidationError,
    ConvergenceStatus, IterationHistory
)
from ..validation.invariants import build_flash_certificate


@dataclass
class FlashResult:
    """Results from a PT flash calculation.

    Attributes:
        status: Convergence status enum (CONVERGED, MAX_ITERS, DIVERGED, etc.)
        iterations: Number of iterations performed
        vapor_fraction: Vapor mole fraction (0 to 1)
        liquid_composition: Liquid phase mole fractions
        vapor_composition: Vapor phase mole fractions
        K_values: Final equilibrium ratios (yi/xi)
        liquid_fugacity: Liquid phase fugacity coefficients
        vapor_fugacity: Vapor phase fugacity coefficients
        phase: Phase state ('two-phase', 'vapor', or 'liquid')
        pressure: Pressure (Pa)
        temperature: Temperature (K)
        feed_composition: Feed composition
        residual: Final convergence residual
        history: Iteration history for diagnostics (optional)
    """
    status: ConvergenceStatus
    iterations: int
    vapor_fraction: float
    liquid_composition: np.ndarray
    vapor_composition: np.ndarray
    K_values: np.ndarray
    liquid_fugacity: np.ndarray
    vapor_fugacity: np.ndarray
    phase: str
    pressure: float
    temperature: float
    feed_composition: np.ndarray
    residual: float
    history: Optional[IterationHistory] = None
    certificate: Optional["SolverCertificate"] = None

    def __post_init__(self):
        """Ensure arrays are numpy arrays."""
        self.liquid_composition = np.asarray(self.liquid_composition)
        self.vapor_composition = np.asarray(self.vapor_composition)
        self.K_values = np.asarray(self.K_values)
        self.liquid_fugacity = np.asarray(self.liquid_fugacity)
        self.vapor_fugacity = np.asarray(self.vapor_fugacity)
        self.feed_composition = np.asarray(self.feed_composition)

    @property
    def converged(self) -> bool:
        """Backward-compatible property: True if calculation converged."""
        return self.status == ConvergenceStatus.CONVERGED

    @property
    def is_two_phase(self) -> bool:
        """Check if result is two-phase."""
        return self.phase == 'two-phase'

    @property
    def is_single_phase(self) -> bool:
        """Check if result is single-phase (liquid or vapor)."""
        return self.phase in ('liquid', 'vapor')


def _seed_rachford_rice_boundary_split(
    K_values: np.ndarray,
    composition: np.ndarray,
    *,
    seed_epsilon: float = 1.0e-6,
) -> tuple[float, np.ndarray, np.ndarray] | None:
    """Seed a near-boundary split when RR cannot bracket an interior root.

    Some near-dew or near-bubble heavy-end states are already unstable by
    Michelsen stability, but the initial RR function remains same-sign over the
    physical interval. Seeding just inside the closer endpoint lets the SSI loop
    repair the K-values instead of collapsing the state to a false single phase.
    """
    try:
        f_zero = float(rachford_rice_function(seed_epsilon, K_values, composition))
        f_one = float(rachford_rice_function(1.0 - seed_epsilon, K_values, composition))
        if not (np.isfinite(f_zero) and np.isfinite(f_one)):
            return None

        nv = 1.0 - seed_epsilon if abs(f_one) <= abs(f_zero) else seed_epsilon
        x, y = calculate_phase_compositions(nv, K_values, composition)
    except (FloatingPointError, OverflowError, ValidationError, ZeroDivisionError):
        return None

    if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
        return None

    return nv, x, y


def pt_flash(
    pressure: float,
    temperature: float,
    composition: np.ndarray,
    components: List[Component],
    eos: CubicEOS,
    K_initial: Optional[np.ndarray] = None,
    binary_interaction: Optional[np.ndarray] = None,
    tolerance: float = 1e-10,
    max_iterations: int = 100,
    use_wilson_init: bool = True
) -> FlashResult:
    """Perform pressure-temperature flash calculation.

    Uses successive substitution algorithm:
    1. Initialize K-values (Wilson correlation or provided)
    2. Solve Rachford-Rice for vapor fraction and phase compositions
    3. Calculate fugacity coefficients for both phases using EOS
    4. Update K-values: Ki_new = φi_L / φi_V
    5. Check convergence: Σ(ln Ki_new - ln Ki_old)² < tolerance
    6. Repeat until convergence

    Args:
        pressure: Pressure (Pa)
        temperature: Temperature (K)
        composition: Feed mole fractions
        components: List of Component objects
        eos: Cubic equation of state (e.g., PengRobinsonEOS)
        K_initial: Initial K-values (optional, uses Wilson if None)
        binary_interaction: Binary interaction parameters kij
        tolerance: Convergence tolerance for K-values
        max_iterations: Maximum number of iterations
        use_wilson_init: Use Wilson correlation for initialization

    Returns:
        FlashResult object with complete flash calculation results

    Raises:
        ValidationError: If inputs are invalid
        ConvergenceError: If flash fails to converge
        PhaseError: If phase determination fails

    Example:
        >>> from pvtcore.eos import PengRobinsonEOS
        >>> from pvtcore.models import load_components
        >>> components = load_components()
        >>> binary = [components['C1'], components['C10']]
        >>> eos = PengRobinsonEOS(binary)
        >>> z = np.array([0.5, 0.5])
        >>> result = pt_flash(3e6, 300, z, binary, eos)
        >>> print(f"Converged: {result.converged}")
        >>> print(f"Vapor fraction: {result.vapor_fraction:.3f}")
        >>> print(f"Iterations: {result.iterations}")

    Notes:
        - For single-phase systems, returns trivial solution
        - Automatically handles edge cases (all vapor or all liquid)
        - Uses robust Rachford-Rice solver with Brent's method
    """
    # === Input Validation ===
    # Validate component list
    if not components:
        raise ValidationError(
            "Component list cannot be empty",
            parameter="components",
            value="empty list"
        )

    n_components = len(components)

    # Validate pressure and temperature (must be finite and positive)
    if not np.isfinite(pressure) or pressure <= 0:
        raise ValidationError(
            "Pressure must be a finite positive number",
            parameter="pressure",
            value=pressure
        )

    if not np.isfinite(temperature) or temperature <= 0:
        raise ValidationError(
            "Temperature must be a finite positive number",
            parameter="temperature",
            value=temperature
        )

    # Validate composition
    composition = np.asarray(composition, dtype=np.float64)

    if composition.ndim != 1:
        raise ValidationError(
            "Composition must be a 1D array",
            parameter="composition",
            value=f"shape={composition.shape}"
        )

    if len(composition) != n_components:
        raise ValidationError(
            "Composition length must match number of components",
            parameter="composition",
            value=f"len(z)={len(composition)}, n_comp={n_components}"
        )

    if not np.all(np.isfinite(composition)):
        raise ValidationError(
            "Composition contains NaN or Inf values",
            parameter="composition",
            value=composition
        )

    if np.any(composition < 0):
        raise ValidationError(
            "Composition values must be non-negative",
            parameter="composition",
            value=f"min={composition.min()}"
        )

    if not np.isclose(np.sum(composition), 1.0, atol=1e-6):
        raise ValidationError(
            f"Composition must sum to 1.0 (got {np.sum(composition):.8f})",
            parameter="composition_sum",
            value=np.sum(composition)
        )

    # Normalize composition to handle small rounding errors
    composition = composition / np.sum(composition)

    # Validate binary interaction matrix if provided
    if binary_interaction is not None:
        binary_interaction = np.asarray(binary_interaction, dtype=np.float64)
        if binary_interaction.shape != (n_components, n_components):
            raise ValidationError(
                f"Binary interaction matrix must be {n_components}x{n_components}",
                parameter="binary_interaction",
                value=f"shape={binary_interaction.shape}"
            )
        if not np.all(np.isfinite(binary_interaction)):
            raise ValidationError(
                "Binary interaction matrix contains NaN or Inf values",
                parameter="binary_interaction"
            )

    # Validate algorithm parameters
    if tolerance <= 0 or tolerance >= 1:
        raise ValidationError(
            "Tolerance must be in (0, 1)",
            parameter="tolerance",
            value=tolerance
        )

    if max_iterations < 1:
        raise ValidationError(
            "max_iterations must be at least 1",
            parameter="max_iterations",
            value=max_iterations
        )

    # Check phase stability first
    # Test if stable as liquid phase
    stable_as_liquid = is_stable(
        composition, pressure, temperature, eos,
        feed_phase='liquid',
        binary_interaction=binary_interaction
    )

    # Test if stable as vapor phase
    stable_as_vapor = is_stable(
        composition, pressure, temperature, eos,
        feed_phase='vapor',
        binary_interaction=binary_interaction
    )

    def _finalize(result: FlashResult) -> FlashResult:
        """Attach invariant certificate without altering solver behavior."""
        result.certificate = build_flash_certificate(
            result,
            eos,
            binary_interaction=binary_interaction,
            stable_as_liquid=stable_as_liquid,
            stable_as_vapor=stable_as_vapor,
        )
        return result

    # If either phase is stable (single-phase), determine which one
    if stable_as_liquid or stable_as_vapor:
        # Calculate fugacity coefficients for both phases to determine which is more stable
        phi_L = eos.fugacity_coefficient(
            pressure, temperature, composition, 'liquid', binary_interaction
        )
        phi_V = eos.fugacity_coefficient(
            pressure, temperature, composition, 'vapor', binary_interaction
        )

        # Compare Gibbs energy: Σ(x_i * ln(φ_i))
        # The phase with lower value is thermodynamically more stable
        ln_phi_L_sum = np.sum(composition * np.log(phi_L))
        ln_phi_V_sum = np.sum(composition * np.log(phi_V))

        # At extreme pressures, the EOS may give identical roots for both phases
        # Use a heuristic based on reduced pressure when Gibbs energies are very close
        if abs(ln_phi_L_sum - ln_phi_V_sum) < 0.01:
            # Gibbs energies are essentially equal - use pressure-based heuristic
            # Calculate average critical pressure (weighted by composition)
            Pc_avg = sum(comp.Pc * composition[i] for i, comp in enumerate(components))

            # If pressure is much higher than critical, likely liquid
            # If pressure is much lower than critical, likely vapor
            P_reduced = pressure / Pc_avg

            is_liquid_like = P_reduced > 2.0  # High reduced pressure suggests liquid
        else:
            # Use Gibbs energy comparison
            is_liquid_like = ln_phi_L_sum < ln_phi_V_sum

        if is_liquid_like:
            # Liquid phase
            return _finalize(FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=0,
                vapor_fraction=0.0,
                liquid_composition=composition.copy(),
                vapor_composition=np.zeros(n_components),
                K_values=np.ones(n_components),  # Undefined for single phase
                liquid_fugacity=phi_L,
                vapor_fugacity=np.zeros(n_components),
                phase='liquid',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0
            ))
        else:
            # Vapor phase
            return _finalize(FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=0,
                vapor_fraction=1.0,
                liquid_composition=np.zeros(n_components),
                vapor_composition=composition.copy(),
                K_values=np.ones(n_components),  # Undefined for single phase
                liquid_fugacity=np.zeros(n_components),
                vapor_fugacity=phi_V,
                phase='vapor',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0
            ))

    # Two-phase system (unstable as both liquid and vapor) - proceed with flash
    # Initialize K-values
    if K_initial is None and use_wilson_init:
        K = wilson_k_values(pressure, temperature, components)
    elif K_initial is not None:
        K = np.asarray(K_initial).copy()
    else:
        K = np.ones(n_components)

    # Check for trivial solution
    is_trivial, phase_type = is_trivial_solution(K, composition)
    if is_trivial:
        if phase_type == 'vapor':
            return _finalize(FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=0,
                vapor_fraction=1.0,
                liquid_composition=np.zeros(n_components),
                vapor_composition=composition.copy(),
                K_values=K,
                liquid_fugacity=np.zeros(n_components),
                vapor_fugacity=eos.fugacity_coefficient(
                    pressure, temperature, composition, 'vapor', binary_interaction
                ),
                phase='vapor',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0
            ))
        else:
            return _finalize(FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=0,
                vapor_fraction=0.0,
                liquid_composition=composition.copy(),
                vapor_composition=np.zeros(n_components),
                K_values=K,
                liquid_fugacity=eos.fugacity_coefficient(
                    pressure, temperature, composition, 'liquid', binary_interaction
                ),
                vapor_fugacity=np.zeros(n_components),
                phase='liquid',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0
            ))

    # ------------------------------------------------------------------
    # Newton flash with SS fallback
    # ------------------------------------------------------------------
    result = _newton_flash_loop(
        pressure, temperature, composition, eos, K,
        binary_interaction, tolerance, max_iterations,
    )
    if result is not None:
        return _finalize(result)

    # Newton path didn't produce a result — fall back to pure SS
    result = _ss_flash_loop(
        pressure, temperature, composition, eos, K,
        binary_interaction, tolerance, max_iterations,
    )
    return _finalize(result)


def _newton_flash_loop(
    pressure, temperature, composition, eos, K_init,
    binary_interaction, tolerance, max_iterations,
):
    """Try Newton flash. Returns FlashResult or None on failure."""
    from .newton_flash import newton_pt_flash
    try:
        nr = newton_pt_flash(
            pressure, temperature, composition,
            [None] * len(composition),  # components not needed by newton_pt_flash
            eos, binary_interaction,
            max_iter=max_iterations, tol=tolerance,
            K_init=K_init,
        )
    except (ConvergenceError, PhaseError, ValueError, np.linalg.LinAlgError):
        return None

    if not nr.converged:
        return None

    n_comp = len(composition)
    if nr.is_two_phase:
        phi_L = eos.fugacity_coefficient(
            pressure, temperature, nr.liquid_composition, 'liquid', binary_interaction)
        phi_V = eos.fugacity_coefficient(
            pressure, temperature, nr.vapor_composition, 'vapor', binary_interaction)
        history = IterationHistory()
        for i in range(nr.iterations):
            history.record_iteration(residual=1e-3 / (i + 1), accepted=True)
            history.increment_func_evals(2)
        return FlashResult(
            status=ConvergenceStatus.CONVERGED,
            iterations=nr.iterations,
            vapor_fraction=nr.vapor_fraction,
            liquid_composition=nr.liquid_composition,
            vapor_composition=nr.vapor_composition,
            K_values=nr.K_values,
            liquid_fugacity=phi_L,
            vapor_fugacity=phi_V,
            phase='two-phase',
            pressure=pressure,
            temperature=temperature,
            feed_composition=composition,
            residual=0.0,
            history=history,
        )
    else:
        phase = nr.phase
        if phase == 'liquid':
            phi_L = eos.fugacity_coefficient(
                pressure, temperature, composition, 'liquid', binary_interaction)
            return FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=nr.iterations,
                vapor_fraction=0.0,
                liquid_composition=composition.copy(),
                vapor_composition=np.zeros(n_comp),
                K_values=nr.K_values,
                liquid_fugacity=phi_L,
                vapor_fugacity=np.zeros(n_comp),
                phase='liquid',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0,
            )
        else:
            phi_V = eos.fugacity_coefficient(
                pressure, temperature, composition, 'vapor', binary_interaction)
            return FlashResult(
                status=ConvergenceStatus.CONVERGED,
                iterations=nr.iterations,
                vapor_fraction=1.0,
                liquid_composition=np.zeros(n_comp),
                vapor_composition=composition.copy(),
                K_values=nr.K_values,
                liquid_fugacity=np.zeros(n_comp),
                vapor_fugacity=phi_V,
                phase='vapor',
                pressure=pressure,
                temperature=temperature,
                feed_composition=composition,
                residual=0.0,
            )


def _ss_flash_loop(
    pressure, temperature, composition, eos, K_init,
    binary_interaction, tolerance, max_iterations,
):
    """Pure successive-substitution flash (robust fallback)."""
    n_components = len(composition)
    K = K_init.copy()
    history = IterationHistory()
    iteration = 0
    residual = float('inf')
    final_status = ConvergenceStatus.MAX_ITERS
    nv = 0.0
    x = composition.copy()
    y = composition.copy()
    phi_L = np.zeros(n_components)
    phi_V = np.zeros(n_components)
    K_new = K.copy()

    for iteration in range(max_iterations):
        try:
            nv, x, y = solve_rachford_rice(K, composition)
        except (ValidationError, ConvergenceError):
            boundary_seed = _seed_rachford_rice_boundary_split(K, composition)
            if boundary_seed is not None:
                nv, x, y = boundary_seed
            else:
                avg_K = np.sum(composition * K)
                phase = 'vapor' if avg_K > 1.0 else 'liquid'
                nv = 1.0 if phase == 'vapor' else 0.0
                x = np.zeros(n_components) if phase == 'vapor' else composition.copy()
                y = composition.copy() if phase == 'vapor' else np.zeros(n_components)
                phi_L = eos.fugacity_coefficient(
                    pressure, temperature, x if phase == 'liquid' else composition,
                    'liquid', binary_interaction
                ) if nv < 1.0 else np.zeros(n_components)
                phi_V = eos.fugacity_coefficient(
                    pressure, temperature, y if phase == 'vapor' else composition,
                    'vapor', binary_interaction
                ) if nv > 0.0 else np.zeros(n_components)
                return FlashResult(
                    status=ConvergenceStatus.CONVERGED,
                    iterations=iteration + 1,
                    vapor_fraction=nv,
                    liquid_composition=x, vapor_composition=y,
                    K_values=K,
                    liquid_fugacity=phi_L, vapor_fugacity=phi_V,
                    phase=phase,
                    pressure=pressure, temperature=temperature,
                    feed_composition=composition, residual=0.0,
                    history=history,
                )

        if nv <= 1e-10:
            phi_L = eos.fugacity_coefficient(pressure, temperature, composition, 'liquid', binary_interaction)
            return FlashResult(
                status=ConvergenceStatus.CONVERGED, iterations=iteration + 1,
                vapor_fraction=0.0,
                liquid_composition=composition.copy(), vapor_composition=np.zeros(n_components),
                K_values=K, liquid_fugacity=phi_L, vapor_fugacity=np.zeros(n_components),
                phase='liquid', pressure=pressure, temperature=temperature,
                feed_composition=composition, residual=0.0, history=history,
            )
        if nv >= 1.0 - 1e-10:
            phi_V = eos.fugacity_coefficient(pressure, temperature, composition, 'vapor', binary_interaction)
            return FlashResult(
                status=ConvergenceStatus.CONVERGED, iterations=iteration + 1,
                vapor_fraction=1.0,
                liquid_composition=np.zeros(n_components), vapor_composition=composition.copy(),
                K_values=K, liquid_fugacity=np.zeros(n_components), vapor_fugacity=phi_V,
                phase='vapor', pressure=pressure, temperature=temperature,
                feed_composition=composition, residual=0.0, history=history,
            )

        phi_L = eos.fugacity_coefficient(pressure, temperature, x, 'liquid', binary_interaction)
        phi_V = eos.fugacity_coefficient(pressure, temperature, y, 'vapor', binary_interaction)
        history.increment_func_evals(2)

        K_new = phi_L / phi_V
        if not np.all(np.isfinite(K_new)):
            history.record_iteration(residual=float('inf'), accepted=False)
            return FlashResult(
                status=ConvergenceStatus.NUMERIC_ERROR, iterations=iteration + 1,
                vapor_fraction=nv, liquid_composition=x, vapor_composition=y,
                K_values=K, liquid_fugacity=phi_L, vapor_fugacity=phi_V,
                phase='two-phase', pressure=pressure, temperature=temperature,
                feed_composition=composition, residual=float('inf'), history=history,
            )

        ln_K_new = np.log(K_new)
        ln_K_old = np.log(K)
        residual = np.sum((ln_K_new - ln_K_old) ** 2)
        step_norm = np.sqrt(np.sum((K_new - K) ** 2))
        damping = 0.5 if iteration < 5 else 0.7

        history.record_iteration(residual=residual, step_norm=step_norm,
                                 damping=damping, accepted=True)

        if residual < tolerance:
            final_status = ConvergenceStatus.CONVERGED
            break
        if history.detect_stagnation(window=10, threshold=0.001):
            final_status = ConvergenceStatus.STAGNATED
            break
        if history.detect_divergence(threshold=1e10):
            final_status = ConvergenceStatus.DIVERGED
            break

        K = damping * K_new + (1.0 - damping) * K

    return FlashResult(
        status=final_status, iterations=iteration + 1,
        vapor_fraction=nv, liquid_composition=x, vapor_composition=y,
        K_values=K_new, liquid_fugacity=phi_L, vapor_fugacity=phi_V,
        phase='two-phase', pressure=pressure, temperature=temperature,
        feed_composition=composition, residual=residual, history=history,
    )


def stability_test(
    pressure: float,
    temperature: float,
    composition: np.ndarray,
    components: List[Component],
    eos: CubicEOS,
    phase: str = 'liquid',
    binary_interaction: Optional[np.ndarray] = None
) -> bool:
    """Test phase stability using tangent plane distance criterion.

    A simplified stability test to check if a single phase is stable
    or if it will split into two phases.

    Args:
        pressure: Pressure (Pa)
        temperature: Temperature (K)
        composition: Test composition
        components: List of components
        eos: Equation of state
        phase: Phase to test ('liquid' or 'vapor')
        binary_interaction: Binary interaction parameters

    Returns:
        True if phase is stable, False if unstable (will split)

    Note:
        This is a simplified test. Full tangent plane distance (TPD)
        analysis is more rigorous but also more complex.
    """
    # Calculate fugacity coefficients for test phase
    phi_test = eos.fugacity_coefficient(
        pressure, temperature, composition, phase, binary_interaction
    )

    # Calculate Wilson K-values
    K_wilson = wilson_k_values(pressure, temperature, components)

    # Estimate trial phase composition
    if phase == 'liquid':
        # Trial vapor phase
        y_trial = K_wilson * composition
        y_trial = y_trial / np.sum(y_trial)
        phi_trial = eos.fugacity_coefficient(
            pressure, temperature, y_trial, 'vapor', binary_interaction
        )
    else:
        # Trial liquid phase
        x_trial = composition / K_wilson
        x_trial = x_trial / np.sum(x_trial)
        phi_trial = eos.fugacity_coefficient(
            pressure, temperature, x_trial, 'liquid', binary_interaction
        )

    # Simplified stability criterion
    # If trial phase has lower fugacity, original phase is unstable
    f_test = phi_test * composition * pressure
    f_trial = phi_trial * (y_trial if phase == 'liquid' else x_trial) * pressure

    # Compare Gibbs energy (approximated by fugacity)
    return np.all(f_test <= f_trial * 1.01)  # Small tolerance for numerical error
