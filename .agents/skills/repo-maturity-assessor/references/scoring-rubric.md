# Scoring Rubric — Code Maturity Dimensions

Concrete code examples for each score level on each dimension. Use these
to calibrate your assessments so a "3" means the same thing every time.

---

## 1. Input Validation & Defensive Programming

### Score 1 — No Validation
```python
def bubble_point(T, Rs, gamma_g, gamma_o):
    # Just compute. Whatever happens, happens.
    A = 0.0125 * gamma_o - 0.00091 * T
    Pb = 18.2 * (A - 1.4)
    return Pb
```
No checks. Negative temperature? NaN gamma? Computes garbage silently.

### Score 2 — Basic Type Checks Only
```python
def bubble_point(T, Rs, gamma_g, gamma_o):
    if not isinstance(T, (int, float)):
        raise TypeError("T must be numeric")
    A = 0.0125 * gamma_o - 0.00091 * T
    Pb = 18.2 * (A - 1.4)
    return Pb
```
Catches wrong types but doesn't check physical validity.

### Score 3 — Some Validation, Inconsistent
```python
def bubble_point(T, Rs, gamma_g, gamma_o):
    if T < 0:
        raise ValueError("Temperature must be positive")
    # But doesn't check Rs, gamma_g, gamma_o...
    A = 0.0125 * gamma_o - 0.00091 * T
    Pb = 18.2 * (A - 1.4)
    return Pb
```
Validates some inputs on some functions. Other functions in the same
module have no validation at all.

### Score 4 — Systematic Validation
```python
def bubble_point(T, Rs, gamma_g, gamma_o):
    """Standing correlation for bubble point pressure.

    Args:
        T: Temperature (°F), must be > 0
        Rs: Solution GOR (scf/STB), must be ≥ 0
        gamma_g: Gas specific gravity (air=1), must be > 0
        gamma_o: Oil specific gravity (water=1), must be > 0
    """
    if T <= 0:
        raise ValueError(f"Temperature must be > 0, got {T}")
    if Rs < 0:
        raise ValueError(f"GOR must be ≥ 0, got {Rs}")
    if gamma_g <= 0:
        raise ValueError(f"Gas gravity must be > 0, got {gamma_g}")
    if gamma_o <= 0:
        raise ValueError(f"Oil gravity must be > 0, got {gamma_o}")

    A = 0.0125 * gamma_o - 0.00091 * T
    Pb = 18.2 * (A - 1.4)
    return Pb
```
All inputs checked with clear error messages including the bad value.

### Score 5 — Comprehensive with Physical Bounds
```python
def bubble_point(T, Rs, gamma_g, gamma_o):
    """Standing correlation for bubble point pressure.

    Valid ranges (Standing, 1947):
        T:       100-258°F
        Rs:      20-1425 scf/STB
        gamma_g: 0.59-0.95
        gamma_o: 0.72-0.93 (16-44 API)

    Args:
        T: Temperature (°F)
        Rs: Solution GOR (scf/STB)
        gamma_g: Gas specific gravity (air=1)
        gamma_o: Oil specific gravity (water=1)

    Raises:
        ValueError: If inputs are physically impossible
        CorrelationRangeWarning: If inputs outside valid range
    """
    # Physical validity (hard errors)
    if T <= -459.67:
        raise ValueError(f"Temperature below absolute zero: {T}°F")
    if Rs < 0:
        raise ValueError(f"GOR cannot be negative: {Rs}")
    if gamma_g <= 0:
        raise ValueError(f"Gas gravity must be positive: {gamma_g}")
    if gamma_o <= 0:
        raise ValueError(f"Oil gravity must be positive: {gamma_o}")

    # Correlation validity (warnings)
    if not (100 <= T <= 258):
        warnings.warn(
            f"T={T}°F outside Standing correlation range (100-258°F)",
            CorrelationRangeWarning
        )
    if not (20 <= Rs <= 1425):
        warnings.warn(
            f"Rs={Rs} outside Standing correlation range (20-1425 scf/STB)",
            CorrelationRangeWarning
        )
    # ... similar for gamma_g, gamma_o

    A = 0.0125 * gamma_o - 0.00091 * T
    Pb = 18.2 * (A - 1.4)
    return Pb
```
Physical impossibility = hard error. Correlation range violation = warning.
Both include the actual value and the expected range.

---

## 2. Numerical Robustness

### Score 1 — Unprotected Math
```python
def gas_fvf(P, T, z):
    return 0.02829 * z * T / P  # Blows up when P = 0
```

### Score 2 — Some Guards, Ad Hoc
```python
def gas_fvf(P, T, z):
    if P == 0:  # Exact float comparison — fragile
        return float('inf')
    return 0.02829 * z * T / P
```

### Score 3 — Better Guards, Not Systematic
```python
def gas_fvf(P, T, z):
    if P < 1e-10:
        return float('inf')  # But what should the caller DO with inf?
    return 0.02829 * z * T / P
```

### Score 4 — Systematic Numerical Safety
```python
def gas_fvf(P, T, z):
    """Gas formation volume factor (Bg).

    Returns Bg in RB/scf. Returns None if pressure too low for
    meaningful calculation (caller should handle).
    """
    MIN_PRESSURE = 1e-6  # psia — below this, Bg is meaningless
    if P < MIN_PRESSURE:
        raise PhysicalBoundsError(
            f"Pressure {P} psia too low for Bg calculation"
        )
    return 0.02829 * z * T / P
```

### Score 5 — Robust Throughout
```python
def gas_fvf(P, T, z):
    """Gas formation volume factor (Bg).

    Bg = 0.02829 * z * T / P  (Eq. 2.44, McCain 5th ed.)

    For pressures below 14.696 psia, Bg grows rapidly and may not
    be physically meaningful for reservoir calculations. This function
    clamps at atmospheric and warns.
    """
    if P < 0:
        raise PhysicalBoundsError(f"Negative pressure: {P}")
    if P < 14.696:
        warnings.warn(
            f"P={P} below atmospheric. Bg clamped at P=14.696 psia.",
            NumericalWarning
        )
        P = 14.696
    if not (0 < z < 5):
        raise PhysicalBoundsError(
            f"Z-factor {z} outside physical range (0, 5)"
        )
    return 0.02829 * z * (T + 459.67) / P  # Note: T in °R
```
Guards, physical reasoning behind the guards, reference to source
equation, and correct unit handling (°F → °R).

---

## 3. Correlation & Model Validity Ranges

### Score 1 — No Awareness
```python
def standing_Pb(T, Rs, gamma_g, gamma_o):
    # Standing correlation — works for everything right?
    a = 0.00091 * T - 0.0125 * gamma_o
    return 18.2 * ((Rs / gamma_g) ** 0.83 * 10**a - 1.4)
```

### Score 3 — Documented but Not Enforced
```python
def standing_Pb(T, Rs, gamma_g, gamma_o):
    """Standing bubble point correlation.

    Note: Valid for T=100-258°F, Rs=20-1425 scf/STB.
    May be inaccurate outside these ranges.
    """
    a = 0.00091 * T - 0.0125 * gamma_o
    return 18.2 * ((Rs / gamma_g) ** 0.83 * 10**a - 1.4)
```
The comment is helpful but the code doesn't act on it.

### Score 5 — Source, Range, Uncertainty, Enforcement
```python
# Correlation registry pattern
STANDING_PB = Correlation(
    name="Standing bubble point",
    source="Standing, M.B. (1947). 'A Pressure-Volume-Temperature '
           'Correlation for Mixtures of California Oils and Gases.' "
           "Drilling and Production Practice, API.",
    valid_ranges={
        "T": (100, 258, "°F"),
        "Rs": (20, 1425, "scf/STB"),
        "gamma_g": (0.59, 0.95, "air=1"),
        "gamma_o": (0.72, 0.93, "water=1"),
    },
    reported_accuracy="±4.8% average absolute error",
    notes="Developed from California crude oils. May be less accurate "
          "for volatile oils or heavy crudes outside the dataset."
)

def standing_Pb(T, Rs, gamma_g, gamma_o, on_extrapolation="warn"):
    """Bubble point pressure via Standing (1947).

    Args:
        on_extrapolation: "warn" (default), "raise", or "ignore"
    """
    STANDING_PB.validate(T=T, Rs=Rs, gamma_g=gamma_g, gamma_o=gamma_o,
                         on_extrapolation=on_extrapolation)
    a = 0.00091 * T - 0.0125 * gamma_o
    return 18.2 * ((Rs / gamma_g) ** 0.83 * 10**a - 1.4)
```

---

## 4. Unit Handling & Consistency

### Score 1 — Implicit, Undocumented
```python
def pressure_drop(q, d, L, rho, mu):
    f = 0.316 / (rho * q * d / mu) ** 0.25  # What units? Who knows.
    return f * L * rho * q**2 / (2 * d)
```

### Score 3 — Documented Convention
```python
# All internal calculations use SI units:
# Pressure: Pa, Temperature: K, Length: m, Mass: kg
# Conversion happens at module boundaries.

def pressure_drop(q_m3s, d_m, L_m, rho_kgm3, mu_Pas):
    """Pressure drop (Pa) for turbulent pipe flow.

    All inputs in SI units. Use convert_to_si() at boundaries.
    """
    Re = rho_kgm3 * q_m3s * d_m / mu_Pas
    f = 0.316 / Re ** 0.25
    return f * L_m * rho_kgm3 * q_m3s**2 / (2 * d_m)
```
Convention exists and is documented. Variable names encode units.
Still possible to pass wrong units, but much harder.

### Score 5 — Enforced Unit System
```python
from units import Pressure, Temperature, Length, FlowRate, Density, Viscosity

def pressure_drop(
    q: FlowRate,
    d: Length,
    L: Length,
    rho: Density,
    mu: Viscosity
) -> Pressure:
    """Darcy-Weisbach pressure drop for turbulent flow."""
    Re = (rho * q * d / mu).dimensionless()
    f = 0.316 / Re ** 0.25
    dp = f * L * rho * q**2 / (2 * d)
    return dp.to(Pressure)
```
Type system prevents unit mismatches at the boundary.

---

## 5. Determinism & Reproducibility

### Score 1 — Hidden State
```python
_last_result = None  # Module-level mutable state

def compute_properties(T, P):
    global _last_result
    if _last_result and T == _last_result['T']:
        return _last_result  # Stale cache, no P check!
    result = _expensive_calculation(T, P)
    _last_result = result
    return result
```

### Score 5 — Pure Functions, Explicit State
```python
def compute_properties(T, P):
    """Pure function — no side effects, no cached state.

    Same inputs always produce the same outputs.
    """
    z = solve_eos(T, P)  # Also pure
    rho = density_from_z(T, P, z)  # Also pure
    return {"z": z, "rho": rho, "T": T, "P": P}
```

---

## 6. Error Handling & Failure Modes

### Score 1 — Silent Failure
```python
def solve_flash(z, K):
    try:
        V = newton_solve(rachford_rice, z, K)
    except:
        V = 0.5  # "Good enough" default — WRONG
    return V
```

### Score 3 — Logs but Doesn't Propagate
```python
def solve_flash(z, K):
    try:
        V = newton_solve(rachford_rice, z, K, max_iter=50)
    except ConvergenceError:
        logger.warning("Flash did not converge, using last iterate")
        V = newton_solve.last_iterate  # Might be garbage
    return V
```

### Score 5 — Informative Failure
```python
def solve_flash(z, K, max_iter=50, tol=1e-8):
    """Rachford-Rice flash calculation.

    Raises:
        ConvergenceError: If solver doesn't converge within max_iter.
            The error includes the last iterate, residual, and iteration
            history so the caller can diagnose or try alternative methods.
        SinglePhaseError: If the feed is entirely liquid or vapor
            (no two-phase solution exists at these conditions).
    """
    # Check for trivial (single-phase) solution first
    if all(ki > 1 for ki in K):
        raise SinglePhaseError("All K > 1: feed is single-phase vapor")
    if all(ki < 1 for ki in K):
        raise SinglePhaseError("All K < 1: feed is single-phase liquid")

    V, converged, history = newton_solve(
        rachford_rice, z, K, max_iter=max_iter, tol=tol
    )
    if not converged:
        raise ConvergenceError(
            f"Flash did not converge after {max_iter} iterations. "
            f"Last V={V:.6f}, residual={history[-1]['residual']:.2e}. "
            f"Try adjusting initial guess or increasing max_iter.",
            last_value=V,
            history=history
        )
    return V
```

---

## 7. Test Quality

### Score 1 — Tests That Don't Test
```python
def test_bubble_point():
    result = bubble_point(180, 500, 0.75, 0.85)
    assert result is not None  # So it returned SOMETHING. Great.
```

### Score 3 — Hardcoded Values, No Source
```python
def test_bubble_point():
    result = bubble_point(180, 500, 0.75, 0.85)
    assert abs(result - 2345.6) < 1.0  # Where does 2345.6 come from?
```

### Score 5 — Referenced, Edge-Cased, Invariant-Checked
```python
class TestStandingBubblePoint:
    """Validated against McCain, 5th ed., Example 2.3, p. 89."""

    @pytest.mark.parametrize("T,Rs,gg,go,expected_Pb", [
        (180, 500, 0.75, 0.85, 2345.6),  # McCain Example 2.3
        (200, 800, 0.80, 0.82, 3890.2),  # Standing (1947) Table 3
    ])
    def test_against_published_values(self, T, Rs, gg, go, expected_Pb):
        Pb = standing_Pb(T, Rs, gg, go)
        assert abs(Pb - expected_Pb) / expected_Pb < 0.05  # 5% tolerance

    def test_zero_gor_returns_atmospheric(self):
        Pb = standing_Pb(180, 0, 0.75, 0.85)
        assert Pb == pytest.approx(14.696, abs=1.0)

    def test_Pb_increases_with_temperature(self):
        """Physical invariant: Pb increases with T for fixed composition."""
        Pb_low = standing_Pb(100, 500, 0.75, 0.85)
        Pb_high = standing_Pb(200, 500, 0.75, 0.85)
        assert Pb_high > Pb_low

    def test_negative_gor_raises(self):
        with pytest.raises(ValueError, match="GOR"):
            standing_Pb(180, -100, 0.75, 0.85)

    def test_warns_outside_correlation_range(self):
        with pytest.warns(CorrelationRangeWarning):
            standing_Pb(400, 500, 0.75, 0.85)  # T > 258°F
```

---

## 8. Documentation & Assumptions

### Score 1 — Cryptic
```python
def calc(a, b, c, d):
    x = 0.0125 * d - 0.00091 * a
    return 18.2 * ((b/c)**0.83 * 10**x - 1.4)
```

### Score 3 — Reasonable Docstring
```python
def standing_Pb(T, Rs, gamma_g, gamma_o):
    """Calculate bubble point pressure using Standing correlation.

    Args:
        T: Temperature (°F)
        Rs: Solution GOR (scf/STB)
        gamma_g: Gas gravity
        gamma_o: Oil gravity

    Returns:
        Bubble point pressure (psia)
    """
```

### Score 5 — Publication Quality
```python
def standing_Pb(T, Rs, gamma_g, gamma_o):
    """Bubble point pressure via Standing (1947) correlation.

    Implements Eq. 2.7 from McCain, "Properties of Petroleum Fluids,"
    5th edition, p. 82:

        Pb = 18.2 * [(Rs/γg)^0.83 · 10^a - 1.4]

    where:
        a = 0.00091·T - 0.0125·γo

    Assumptions:
        - Black oil system (not volatile oil or gas condensate)
        - Separator gas gravity ≈ reservoir gas gravity
        - Oil gravity measured at 60°F standard conditions

    Valid ranges (from Standing's original dataset):
        T:       100-258 °F
        Rs:      20-1425 scf/STB
        γg:      0.59-0.95 (air=1)
        γo:      0.72-0.93 (water=1), equivalent to 16-44 °API

    Reported accuracy: ±4.8% average absolute error over the
    original dataset. Higher errors expected for:
        - Heavy oils (API < 20)
        - Volatile oils (Rs > 1000)
        - High-temperature systems (T > 250°F)

    Args:
        T: Temperature in °F
        Rs: Solution gas-oil ratio in scf/STB
        gamma_g: Gas specific gravity (air = 1.0)
        gamma_o: Oil specific gravity (water = 1.0)

    Returns:
        Bubble point pressure in psia

    Raises:
        ValueError: If inputs are physically impossible
        CorrelationRangeWarning: If inputs outside valid range
    """
```
