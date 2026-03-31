# Engineering Code Pitfalls Catalog

Common numerical, physical, and computational pitfalls in petroleum
engineering and scientific code. Use this as a checklist when assessing
code maturity — if the code doesn't handle these, it's fragile.

---

## Numerical Pitfalls

### 1. Division by Zero at Phase Boundaries

**Where it happens:** Any property that depends on phase fraction.
- Gas FVF: Bg = f(P) — when P → 0
- Liquid fraction: 1/(1-Vf) — when vapor fraction → 1
- Gas-oil ratio calculations at zero pressure
- Relative permeability: kr/(1-Swc-Sor) — at residual saturations

**The trap:** It works fine for 99% of inputs. Then someone runs a
depletion curve down to abandonment pressure and it blows up.

**What good code does:** Guards the denominator with a physically
meaningful minimum, not just `if x != 0`.

### 2. Log of Zero or Negative Numbers

**Where it happens:**
- Acentric factor correlations: log10(Pvp/Pc)
- Rachford-Rice: ln(Ki) in stability analysis
- Any correlation involving log of pressure ratio
- Friction factor correlations: log(Re) or log(ε/D)

**The trap:** Pressure can be zero at surface conditions. Ki can be
zero for non-volatile components. Pipe roughness can be zero (smooth).

**What good code does:** Validates inputs before taking logarithms.
For physical quantities that must be positive, catches the ≤ 0 case
with a clear error, not a math domain exception.

### 3. Floating Point Comparison

**Where it happens:**
- Composition sum check: `sum(z) == 1.0` (NEVER true for floats)
- Phase boundary detection: `if Pb == P` (almost never exactly equal)
- Convergence checks: `if residual == 0` (should be `< tolerance`)
- Temperature/pressure equality in lookup tables

**The trap:** `0.1 + 0.2 != 0.3` in IEEE 754. Code that uses `==` for
floats will have intermittent, unreproducible failures.

**What good code does:** Always uses tolerance-based comparison:
`abs(a - b) < tol` or relative: `abs(a - b) / max(abs(a), abs(b)) < tol`

### 4. Overflow in Exponentials

**Where it happens:**
- Arrhenius equation: exp(-Ea/RT) — at very low T, exponent is huge negative
- Peng-Robinson α function: exp at extreme temperatures
- Boltzmann factors in molecular simulations
- Any exp() where the argument isn't bounded

**The trap:** `exp(710)` overflows to inf in float64. `exp(-710)` underflows
to 0. Both are silent — no exception raised.

**What good code does:** Clamps the exponent argument or uses log-space
arithmetic for very large/small values.

### 5. Iterative Solver Non-Convergence

**Where it happens:**
- Flash calculations near critical point
- Equation of state root finding
- Pressure-temperature flash (PT flash) at phase boundaries
- Flow assurance calculations (wax, hydrate equilibrium)

**The trap:** The solver reaches max iterations and returns whatever value
it has. The caller treats this as a valid answer. Everything downstream
is based on garbage.

**What good code does:** Returns a convergence flag alongside the result.
Better: raises a specific exception. Best: returns the result, the flag,
AND the iteration history for diagnostics.

### 6. Loss of Significance in Subtraction

**Where it happens:**
- Compressibility: (V2 - V1) / V1 when V2 ≈ V1
- Numerical derivatives: (f(x+h) - f(x)) / h when h is small
- Density differences in buoyancy calculations
- ΔP calculations where P1 ≈ P2

**The trap:** Subtracting two nearly-equal numbers cancels significant
digits. 1.000001 - 1.000000 = 0.000001, but if each input had 6 digits
of precision, the result has 1 digit.

**What good code does:** Reformulates the math to avoid catastrophic
cancellation, or uses higher precision for intermediate calculations.

---

## Physical / Domain Pitfalls

### 7. Unit System Mixing

**Where it happens:** Any code that interfaces between:
- SI (Pa, K, m³) and field units (psi, °F, bbl)
- Molar (mol/s) and mass (kg/s) flow rates
- Gauge and absolute pressure
- Celsius, Fahrenheit, Kelvin, Rankine

**The trap:** A function expects pressure in Pa but gets psi. The
calculation "works" — no errors — but the answer is wrong by a factor
of 6894.76. The Mars Climate Orbiter crashed because of this exact bug.

**Common hiding spots:**
- Gas constant R: 8.314 J/(mol·K) vs 10.73 psia·ft³/(lbmol·°R)
- Conversion factors hardcoded inside functions instead of centralized
- Temperature offsets: °F to °R requires +459.67, °C to K requires +273.15
- Pressure: gauge vs absolute (forgot to add atmospheric?)

### 8. Composition Normalization

**Where it happens:** Any multi-component calculation.

**The trap:** User inputs mole fractions that sum to 0.9998 instead of
1.0 (rounding errors, or they forgot a trace component). The code either:
- Silently computes with non-normalized composition (wrong)
- Crashes because some correlation assumes sum = 1.0

**What good code does:** Checks the sum. If close to 1.0 (within
tolerance), normalizes. If close to 100 (mole percent), divides by 100.
If neither, raises an error explaining the problem.

### 9. Correlation Extrapolation

**Where it happens:** Every empirical correlation has a valid range.
Standing's bubble point, Beggs-Robinson viscosity, Hall-Yarborough
Z-factor — all developed from specific datasets.

**The trap:** The correlation "works" outside its range. It returns a
number. That number is meaningless. A Standing bubble point calculated
at 500°F will give you a value, but Standing never measured anything
near 500°F — the correlation is extrapolating into fantasy.

**Worse trap:** Some correlations go negative outside their range.
A negative bubble point, negative viscosity, or Bo < 1.0 are physically
impossible but mathematically possible from a polynomial correlation
being evaluated too far from its fitted range.

### 10. Phase Boundary Discontinuities

**Where it happens:** Properties that change formula at phase boundaries.

**The trap:** Many PVT property models use different equations above
and below the bubble point:
- Below Pb: Bo = f1(P, T, Rs)
- Above Pb: Bo = f2(P, T, co)

If f1(Pb) ≠ f2(Pb), there's a discontinuity in Bo at the bubble point.
This causes:
- Jumps in simulation results at phase transitions
- Oscillation in iterative solvers near the boundary
- Incorrect derivatives (dBo/dP is infinite at the discontinuity)

**What good code does:** Verifies continuity at the boundary. Both
formulas must give the same value at Pb. Some implementations use a
blending function in a small region around Pb to smooth the transition.

### 11. Temperature Convention Ambiguity

**Where it happens:** Any thermodynamic calculation.

**The trap:**
- Is T in °F, °C, K, or °R?
- Correlations from American literature use °F or °R
- EOS calculations typically use K or °R (absolute scale required)
- If you pass °F to a function expecting °R, you get wrong answers
  (not errors — just wrong answers, because °F values are still positive)

**Specific danger:** The gas constant R must match the temperature unit:
- R = 8.314 J/(mol·K) — T must be in Kelvin
- R = 10.73 psia·ft³/(lbmol·°R) — T must be in Rankine
- R = 1.987 cal/(mol·K) — T must be in Kelvin
Using R = 10.73 with T in °F gives wrong answers that are within
plausible-looking range — the hardest bug to catch.

### 12. Standard Conditions Ambiguity

**Where it happens:** Volumetric flow rates, GOR, formation volume factors.

**The trap:** "Standard conditions" vary:
- API standard: 14.696 psia, 60°F
- SI standard: 101.325 kPa, 15°C
- Some older references: 14.65 psia, 60°F
- Some Canadian references: 14.696 psia, 59°F

If the code doesn't document which standard conditions it uses, and
two modules use different standards, volume-based calculations will
be inconsistent.

---

## Computational Pitfalls

### 13. Caching with Stale State

**Where it happens:** Performance optimization of expensive calculations.

**The trap:** An LRU cache on a method that depends on instance state:
```python
class Fluid:
    @lru_cache(maxsize=128)
    def z_factor(self, T, P):
        return solve_eos(self.composition, T, P)
```
If `self.composition` changes, the cached results are stale but still
returned. The cache key is (self, T, P) but `self` is hashed by
identity, not by composition content.

### 14. Mutable Default Arguments

**Where it happens:** Python functions with list/dict defaults.

**The trap:**
```python
def flash(z, K, options={}):
    options.setdefault('max_iter', 50)
    # ... modifies options ...
```
The default `{}` is shared across all calls. After the first call,
`options` already has `max_iter` set. This causes mysterious behavior
where the function works differently on the second call.

### 15. Global State in Module Imports

**Where it happens:** Configuration that runs at import time.

**The trap:**
```python
# config.py
UNITS = os.environ.get("UNITS", "field")  # Read once at import

# pvt.py
from config import UNITS
def bubble_point(T, Rs, ...):
    if UNITS == "SI":
        T = T * 9/5 + 32  # Convert to °F
```
If the environment variable changes after import, the code doesn't know.
Worse: import order determines which modules get which config.

### 16. Silent NaN Propagation

**Where it happens:** Any calculation that can produce NaN.

**The trap:** `float('nan')` propagates silently through all arithmetic:
- `nan + 5 = nan`
- `nan > 0 = False`
- `nan == nan = False`
- `nan < 0 = False`

A single NaN in a composition array will silently corrupt every
downstream calculation. No exception, no warning — just wrong answers
that happen to be NaN if you think to check.

**What good code does:** Checks for NaN/Inf at critical checkpoints:
```python
if np.any(np.isnan(result)) or np.any(np.isinf(result)):
    raise NumericalError(f"NaN/Inf detected in {function_name}")
```

---

## Assessment Priority

When auditing engineering code, check for these pitfalls in this order:

1. **Silent wrong answers** (items 7, 9, 10, 11, 12, 16) — highest
   priority because they produce plausible-looking but incorrect results
2. **Crashes at edge cases** (items 1, 2, 4) — high priority but at
   least they fail visibly
3. **Numerical fragility** (items 3, 5, 6) — medium priority, causes
   intermittent failures
4. **State bugs** (items 13, 14, 15) — medium priority, causes
   hard-to-reproduce issues
5. **Missing validation** (item 8) — lower priority but easy to fix
