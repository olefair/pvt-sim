# Engineering Test Cases Reference

Domain-specific edge cases and validation strategies for PVT, thermodynamic,
and petroleum engineering code. Use this catalog when generating tests for
physics/engineering modules.

---

## PVT Property Calculations

### Bubble Point Pressure

**Happy path:**
- Light oil at moderate temperature (100-200°F), known Pb from lab data
- Compare against Standing, Vasquez-Beggs, or Al-Marhoun correlations
  with published example values

**Edge cases:**
- Pure methane (no heavy components) — should reduce to vapor pressure
- Dead oil (no dissolved gas, Rs = 0) — Pb should approach atmospheric
- Very heavy oil (API < 10) — many correlations invalid here
- Temperature at or near critical — correlations break down
- Gas-oil ratio = 0 — must return atmospheric, not crash
- Negative GOR input — must reject, not compute

**Physical invariants:**
- Pb must increase with temperature (for a given composition)
- Pb must increase with GOR (more gas = higher pressure to keep it dissolved)
- Pb must be > 0

### Solution Gas-Oil Ratio (Rs)

**Happy path:**
- Known Rs at various pressures from differential liberation test
- Below bubble point: Rs should decrease with decreasing pressure
- At and above bubble point: Rs should be constant (= Rsb)

**Edge cases:**
- Pressure = 0 — Rs must be 0 (no gas dissolved at vacuum)
- Pressure > Pb — Rs must equal Rsb (flat, not extrapolating)
- Temperature = 60°F (standard conditions) — Rs should be 0 by definition
- Very high GOR (gas condensate behavior) — correlations may not apply
- Separator conditions vs reservoir conditions — different Rs values

**Physical invariants:**
- Rs ≥ 0 always
- Rs is monotonically non-decreasing with pressure (below Pb)
- Rs at Pb equals Rsb (continuity at bubble point)

### Oil Formation Volume Factor (Bo)

**Happy path:**
- Bo > 1.0 always (oil expands from stock tank to reservoir)
- Bo at Pb should be maximum (below Pb, gas comes out, oil shrinks)
- Compare against Standing or Vasquez-Beggs with published values

**Edge cases:**
- Pressure = atmospheric → Bo should approach 1.0
- Pressure >> Pb → Bo should decrease slightly due to compression
- Dead oil (Rs = 0) → Bo should be close to 1.0, slightly above
- Undersaturated oil (P > Pb) — Bo decreases with increasing pressure
  (compressibility effect, different formula than below Pb)
- Temperature = standard conditions → Bo = 1.0 by definition

**Physical invariants:**
- Bo > 1.0 always (for live oil at reservoir conditions)
- Bo is continuous at Pb (no discontinuity at bubble point)
- dBo/dP changes sign at Pb (increases below, decreases above)

### Oil Viscosity

**Happy path:**
- Dead oil viscosity from Beggs-Robinson or similar
- Live oil viscosity reduction from dissolved gas
- Undersaturated viscosity increase from pressure

**Edge cases:**
- Dead oil at very low temperature — viscosity can be extremely high
- Dead oil at very high temperature — must remain > 0
- Rs = 0 — live oil viscosity should equal dead oil viscosity
- Very high pressure — viscosity increases but should remain physical
- API gravity near 10 (water-equivalent density) — correlation boundaries
- Pure gas component — oil viscosity correlation is meaningless

**Physical invariants:**
- Viscosity > 0 always
- Dead oil viscosity decreases with temperature
- Live oil viscosity decreases with increasing Rs (gas thins oil)
- Viscosity is continuous at bubble point

---

## Phase Equilibrium

### Flash Calculations

**Happy path:**
- Two-component system with known K-values at P, T
- Multi-component system with converged vapor fraction

**Edge cases:**
- Single component feed — flash reduces to vapor pressure check
- Feed at exactly the bubble point — vapor fraction should be 0 (or ε)
- Feed at exactly the dew point — vapor fraction should be 1 (or 1-ε)
- Feed well above bubble point — should report single-phase liquid
- Feed well below dew point — should report single-phase vapor
- Component with Ki = 1.0 exactly — appears in both phases equally
- Trace component (zi < 1e-10) — should not cause numerical issues
- Near-critical conditions — K-values approach 1, convergence is hard
- Three-phase region — standard two-phase flash is invalid

**Physical invariants:**
- Sum of xi = 1.0 (liquid mole fractions)
- Sum of yi = 1.0 (vapor mole fractions)
- zi = xi·(1-V) + yi·V (component material balance)
- 0 ≤ V ≤ 1 (vapor fraction physical bounds)
- 0 ≤ xi ≤ 1 and 0 ≤ yi ≤ 1 for all components

### Equation of State

**Happy path:**
- Pure component at known P, T — compare Z-factor against NIST data
- Binary mixture — compare against published binary interaction data

**Edge cases:**
- At critical point — multiple solutions coalesce, cubic EOS is singular
- Very low pressure — should approach ideal gas (Z → 1)
- Very high pressure — compressibility effects dominate
- Negative discriminant in cubic solution — only one real root
- Two real roots but need to pick correct one (liquid vs vapor)
- Temperature below triple point — EOS may give liquid-like Z but
  the phase is actually solid
- Hydrogen/helium — special treatment needed in many mixing rules

**Physical invariants:**
- Z > 0 always
- Z → 1 as P → 0 (ideal gas limit)
- For cubic EOS: exactly 1 or 3 real roots (never 2)

---

## Fluid Flow & Pressure Drop

### Pipe Flow (Beggs-Brill, Hagedorn-Brown, etc.)

**Happy path:**
- Single-phase liquid flow at moderate velocity
- Known pressure drop from published correlations

**Edge cases:**
- Zero flow rate — pressure drop should be hydrostatic only
- Very low velocity — must not produce negative friction
- Near-zero pipe diameter — must reject, not divide by zero
- Horizontal pipe — hydrostatic component is zero
- Vertical upflow vs downflow — sign conventions matter
- Gas-liquid two-phase — flow pattern transition boundaries
- Slug flow regime — correlations have discontinuities
- Very high velocity — choked flow / sonic velocity limit
- Pipe roughness = 0 — smooth pipe limit, must not cause log(0)

**Physical invariants:**
- Friction pressure drop ≥ 0 (friction always dissipates energy)
- Total pressure drop in uphill flow > hydrostatic component
- Flow velocity = volumetric rate / area (mass balance)
- Reynolds number > 0 for any nonzero flow

### Choke / Valve Flow

**Edge cases:**
- Choke fully open — should reduce to pipe flow
- Choke fully closed — flow rate = 0, must not divide by zero
- Critical flow (sonic velocity at throat) — downstream pressure
  doesn't matter, must be detected
- Very small choke size — numerical precision of Cv/area matters
- Flashing across choke — two-phase choke model needed

---

## Numerical Method Edge Cases

### Newton-Raphson Solver

**Edge cases:**
- Initial guess far from solution — may diverge or find wrong root
- Derivative = 0 at some iterate — division by zero
- Multiple solutions — which root does it find?
- Function is flat near solution — slow convergence, may timeout
- Oscillation between two values — needs dampening or bisection fallback
- Maximum iterations reached — must report non-convergence, not return
  the last iterate as if it's the answer

**Tests to write:**
- Known-solution problems with exact answers
- Pathological functions (flat regions, multiple roots, discontinuities)
- Convergence tolerance verification: does it actually stop within tolerance?
- Max iteration limit: does it respect the limit and report failure?

### Bisection Method

**Edge cases:**
- f(a) and f(b) have same sign — no root guaranteed, must reject
- Root is exactly at a or b — should find it in 1 step
- Multiple roots in interval — finds one, but which one?
- Function is discontinuous — may "find" a root at the discontinuity
  that isn't actually a zero

---

## General Patterns for Engineering Tests

### Reference Data Sources

When writing tests for engineering calculations, the expected values should
come from a verifiable source. In order of preference:

1. **Published textbook examples** — worked problems with known answers
   (McCain, Ahmed, Whitson, etc.)
2. **NIST/DIPPR databases** — pure component properties at specific conditions
3. **Published papers** — correlation validation data from the original paper
4. **Commercial software output** — values verified against HYSYS, PVTsim,
   PIPESIM, etc. (note the software version)
5. **Hand calculations** — manually verified with a calculator (last resort,
   document the calculation)

Never use "I ran the code and it gave me this value" as the reference —
that's a tautological test.

### Tolerance Guidance

| Property | Typical Tolerance | Reasoning |
|----------|------------------|-----------|
| Pressure (psi) | ±1% or ±1 psi (whichever is larger) | Correlations typically ±5-10% |
| Temperature (°F) | ±0.1°F | Usually exact or near-exact |
| Volume factor (Bo, Bg) | ±0.5% | Correlations ±2-5% |
| Viscosity | ±5% | Viscosity correlations are notoriously imprecise |
| Z-factor | ±0.001 | EOS solutions should be numerically precise |
| Mole fractions | ±1e-6 | Should sum to 1 within numerical precision |
| Flow rate | ±1% | Depends on correlation used |

### Test Organization

For each engineering module, organize tests as:

```python
class TestModuleName:
    """Tests for [module], validated against [source]."""

    class TestHappyPath:
        """Standard operating conditions."""
        def test_known_example_from_mccain(self): ...
        def test_another_published_value(self): ...

    class TestEdgeCases:
        """Boundary conditions and limiting cases."""
        def test_pure_component(self): ...
        def test_zero_gor(self): ...
        def test_at_bubble_point(self): ...

    class TestPhysicalInvariants:
        """Properties that must always hold."""
        def test_always_positive(self): ...
        def test_monotonicity(self): ...
        def test_continuity_at_phase_boundary(self): ...

    class TestInputValidation:
        """Bad inputs should be caught, not computed."""
        def test_negative_pressure_raises(self): ...
        def test_composition_not_summing_to_one(self): ...

    class TestNumericalStability:
        """Near-singular conditions."""
        def test_near_critical_point(self): ...
        def test_trace_component(self): ...
```
