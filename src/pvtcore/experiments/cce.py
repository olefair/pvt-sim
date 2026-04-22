"""CCE."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash
from ..helper_functions import _V, _Z, _v, _z_root
from ..models.component import Component
from ..properties.density import calculate_density


####################
# CCE
####################
@dataclass
class CCEStepResult:
    """One CCE step."""

    pressure: float
    temperature: float
    relative_volume: float
    compressibility_Z: float
    liquid_volume_fraction: float
    vapor_fraction: float
    liquid_density: float
    vapor_density: float
    liquid_compressibility: float
    vapor_compressibility: float
    phase: str
    liquid_composition: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    vapor_composition: NDArray[np.float64] = field(default_factory=lambda: np.array([], dtype=np.float64))
    Y_function: Optional[float] = None


@dataclass
class CCEResult:
    """Full CCE result."""

    temperature: float
    saturation_pressure: float
    saturation_type: str
    steps: list[CCEStepResult]
    pressures: NDArray[np.float64]
    relative_volumes: NDArray[np.float64]
    liquid_dropouts: NDArray[np.float64]
    compressibility_above_sat: float
    feed_composition: NDArray[np.float64]
    converged: bool


####################
# HELPER FUNCTIONS
####################
def _validate_cce_inputs(
    z: NDArray[np.float64],
    T: float,
    Ps: NDArray[np.float64],
    cs: list[Component],
) -> None:
    if T <= 0.0:
        raise ValidationError("Temperature must be positive", parameter="temperature")
    if len(Ps) < 2:
        raise ValidationError("CCE requires at least two pressure points", parameter="pressure_steps")
    if np.any(Ps <= 0.0):
        raise ValidationError("Pressures must be positive", parameter="pressure")
    if np.any(Ps[:-1] <= Ps[1:]):
        raise ValidationError("CCE pressure schedule must be strictly descending", parameter="pressure")
    if len(z) != len(cs):
        raise ValidationError("Composition length must match number of components", parameter="composition")


def _build_cce_pressure_schedule(
    *,
    pressure_start: float,
    pressure_end: float,
    n_steps: int,
    pressure_steps: Optional[NDArray[np.float64]],
) -> NDArray[np.float64]:
    if pressure_steps is not None:
        Ps = np.asarray(pressure_steps, dtype=np.float64)
        if Ps.ndim != 1:
            raise ValidationError("pressure_steps must be a one-dimensional array", parameter="pressure_steps")
        return Ps
    return np.linspace(pressure_start, pressure_end, n_steps, dtype=np.float64)


def _sat_kind(
    z: NDArray[np.float64],
    T: float,
    Psat: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
) -> str:
    fl = pt_flash(Psat * 0.95, T, z, cs, eos, binary_interaction=kij)
    if fl.phase == "two-phase":
        return "bubble" if float(fl.vapor_fraction) < 0.5 else "dew"
    return "bubble" if fl.phase == "liquid" else "dew"


def _find_sat(
    z: NDArray[np.float64],
    T: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
    Ph: float,
    Pl: float,
) -> tuple[float, str]:
    from ..flash.bubble_point import calculate_bubble_point
    from ..flash.dew_point import calculate_dew_point

    cand: list[tuple[float, str]] = []
    try:
        r = calculate_bubble_point(T, z, cs, eos, binary_interaction=kij)
        cand.append((float(r.pressure), "bubble"))
    except (ConvergenceError, PhaseError):
        pass
    try:
        r = calculate_dew_point(T, z, cs, eos, binary_interaction=kij)
        cand.append((float(r.pressure), "dew"))
    except (ConvergenceError, PhaseError):
        pass

    if cand:
        in_grid = [(P, kind) for P, kind in cand if Pl < P < Ph]
        if in_grid:
            cand = in_grid
        if len(cand) == 1:
            return cand[0]
        MWm = sum(float(z[i]) * comp.MW for i, comp in enumerate(cs))
        pref = "bubble" if MWm > 50.0 else "dew"
        for P, kind in cand:
            if kind == pref:
                return P, kind
        return cand[0]

    P = 0.5 * (Ph + Pl)
    for _ in range(20):
        fl = pt_flash(P, T, z, cs, eos, binary_interaction=kij)
        if fl.phase == "liquid":
            Ph = P
        elif fl.phase == "vapor":
            Pl = P
        else:
            break
        P = 0.5 * (Ph + Pl)

    MWm = sum(float(z[i]) * comp.MW for i, comp in enumerate(cs))
    return P, ("bubble" if MWm > 50.0 else "dew")


def _state_v(
    P: float,
    T: float,
    z: NDArray[np.float64],
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
    ph: str,
) -> float:
    Z = _z_root(eos.compressibility(P, T, z, phase=ph, binary_interaction=kij), "liquid" if ph == "liquid" else "vapor")
    return _v(Z, T, P)


def _cce_step(
    P: float,
    T: float,
    z: NDArray[np.float64],
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
    Psat: float,
    Vsat: float,
    sat_type: str,
) -> CCEStepResult:
    if P > Psat:
        ph = "liquid" if sat_type == "bubble" else "vapor"
        Z = _z_root(eos.compressibility(P, T, z, phase=ph, binary_interaction=kij), ph)
        v = _v(Z, T, P)
        rho = calculate_density(P, T, z, cs, eos, ph, kij)
        return CCEStepResult(
            pressure=P,
            temperature=T,
            relative_volume=v / Vsat,
            compressibility_Z=Z,
            liquid_volume_fraction=1.0 if ph == "liquid" else 0.0,
            vapor_fraction=0.0 if ph == "liquid" else 1.0,
            liquid_density=rho.mass_density if ph == "liquid" else 0.0,
            vapor_density=rho.mass_density if ph == "vapor" else 0.0,
            liquid_compressibility=Z if ph == "liquid" else 0.0,
            vapor_compressibility=Z if ph == "vapor" else 0.0,
            phase=ph,
            liquid_composition=z.copy() if ph == "liquid" else np.zeros_like(z),
            vapor_composition=z.copy() if ph == "vapor" else np.zeros_like(z),
        )

    fl = pt_flash(P, T, z, cs, eos, binary_interaction=kij)
    if fl.phase in {"liquid", "vapor"}:
        ph = fl.phase
        Z = _z_root(eos.compressibility(P, T, z, phase=ph, binary_interaction=kij), ph)
        v = _v(Z, T, P)
        rho = calculate_density(P, T, z, cs, eos, ph, kij)
        return CCEStepResult(
            pressure=P,
            temperature=T,
            relative_volume=v / Vsat,
            compressibility_Z=Z,
            liquid_volume_fraction=1.0 if ph == "liquid" else 0.0,
            vapor_fraction=float(fl.vapor_fraction),
            liquid_density=rho.mass_density if ph == "liquid" else 0.0,
            vapor_density=rho.mass_density if ph == "vapor" else 0.0,
            liquid_compressibility=Z if ph == "liquid" else 0.0,
            vapor_compressibility=Z if ph == "vapor" else 0.0,
            phase=ph,
            liquid_composition=z.copy() if ph == "liquid" else np.zeros_like(z),
            vapor_composition=z.copy() if ph == "vapor" else np.zeros_like(z),
        )

    nV = float(fl.vapor_fraction)
    nL = 1.0 - nV
    x = fl.liquid_composition
    y = fl.vapor_composition
    ZL = _z_root(eos.compressibility(P, T, x, phase="liquid", binary_interaction=kij), "liquid")
    ZV = _z_root(eos.compressibility(P, T, y, phase="vapor", binary_interaction=kij), "vapor")
    VL = _V(nL, ZL, T, P)
    VV = _V(nV, ZV, T, P)
    Vt = VL + VV
    VLf = VL / Vt if Vt > 0.0 else 0.0
    rhoL = calculate_density(P, T, x, cs, eos, "liquid", kij)
    rhoV = calculate_density(P, T, y, cs, eos, "vapor", kij)
    Yf = None
    if sat_type == "dew" and VLf > 0.0:
        Vr = Vt / Vsat
        if Vr > 1.001:
            Yf = (Psat - P) / (P * (Vr - 1.0))
    return CCEStepResult(
        pressure=P,
        temperature=T,
        relative_volume=Vt / Vsat,
        compressibility_Z=_Z(Vt, 1.0, T, P),
        liquid_volume_fraction=VLf,
        vapor_fraction=nV,
        liquid_density=rhoL.mass_density,
        vapor_density=rhoV.mass_density,
        liquid_compressibility=ZL,
        vapor_compressibility=ZV,
        phase="two-phase",
        liquid_composition=x.copy(),
        vapor_composition=y.copy(),
        Y_function=Yf,
    )


def simulate_cce(
    composition: NDArray[np.float64],
    temperature: float,
    components: list[Component],
    eos: CubicEOS,
    pressure_start: float,
    pressure_end: float,
    n_steps: int = 20,
    pressure_steps: Optional[NDArray[np.float64]] = None,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    saturation_pressure: Optional[float] = None,
) -> CCEResult:
    """Run CCE."""

    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    T = float(temperature)
    Ps = _build_cce_pressure_schedule(
        pressure_start=pressure_start,
        pressure_end=pressure_end,
        n_steps=n_steps,
        pressure_steps=pressure_steps,
    )
    _validate_cce_inputs(z, T, Ps, components)

    Ph = float(Ps[0])
    Pl = float(Ps[-1])
    if saturation_pressure is None:
        Psat, sat_type = _find_sat(z, T, components, eos, binary_interaction, Ph, Pl)
    else:
        Psat = float(saturation_pressure)
        sat_type = _sat_kind(z, T, Psat, components, eos, binary_interaction)

    Vsat = _state_v(
        Psat,
        T,
        z,
        components,
        eos,
        binary_interaction,
        "liquid" if sat_type == "bubble" else "vapor",
    )

    steps: list[CCEStepResult] = []
    ok = True
    for P in Ps:
        try:
            steps.append(_cce_step(float(P), T, z, components, eos, binary_interaction, Psat, Vsat, sat_type))
        except (ConvergenceError, PhaseError):
            ok = False
            steps.append(
                CCEStepResult(
                    pressure=float(P),
                    temperature=T,
                    relative_volume=np.nan,
                    compressibility_Z=np.nan,
                    liquid_volume_fraction=np.nan,
                    vapor_fraction=np.nan,
                    liquid_density=np.nan,
                    vapor_density=np.nan,
                    liquid_compressibility=np.nan,
                    vapor_compressibility=np.nan,
                    phase="unknown",
                    liquid_composition=np.zeros_like(z),
                    vapor_composition=np.zeros_like(z),
                )
            )

    Vr = np.array([s.relative_volume for s in steps])
    VLf = np.array([s.liquid_volume_fraction for s in steps])
    Z_above = np.mean([s.compressibility_Z for s in steps if s.pressure > Psat and s.phase != "unknown"]) if any(
        s.pressure > Psat and s.phase != "unknown" for s in steps
    ) else np.nan
    return CCEResult(
        temperature=T,
        saturation_pressure=Psat,
        saturation_type=sat_type,
        steps=steps,
        pressures=Ps,
        relative_volumes=Vr,
        liquid_dropouts=VLf,
        compressibility_above_sat=Z_above,
        feed_composition=z,
        converged=ok,
    )
