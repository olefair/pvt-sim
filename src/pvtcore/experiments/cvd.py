"""CVD."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash
from ..helper_functions import _V, _Z, _v, _z_root
from ..models.component import Component
from ..properties.density import calculate_density


CVD_VOLUME_RELATIVE_TOLERANCE = 1e-10
CVD_VOLUME_ABSOLUTE_TOLERANCE = 1e-15


####################
# CVD
####################
@dataclass
class CVDStepResult:
    """One CVD step."""

    pressure: float
    temperature: float
    liquid_dropout: float
    gas_produced: float
    cumulative_gas_produced: float
    Z_two_phase: float
    liquid_density: float
    vapor_density: float
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    cell_composition: NDArray[np.float64]
    moles_remaining: float


@dataclass
class CVDResult:
    """Full CVD result."""

    temperature: float
    dew_pressure: float
    initial_Z: float
    steps: list[CVDStepResult]
    pressures: NDArray[np.float64]
    liquid_dropouts: NDArray[np.float64]
    cumulative_gas: NDArray[np.float64]
    Z_values: NDArray[np.float64]
    feed_composition: NDArray[np.float64]
    converged: bool


####################
# HELPER FUNCTIONS
####################
def _volume_matches_target(V: float, Vt: float) -> bool:
    return bool(
        np.isclose(
            V,
            Vt,
            rtol=CVD_VOLUME_RELATIVE_TOLERANCE,
            atol=CVD_VOLUME_ABSOLUTE_TOLERANCE,
        )
    )


def _validate_cvd_inputs(
    z: NDArray[np.float64],
    T: float,
    Pd: float,
    Ps: NDArray[np.float64],
    cs: list[Component],
) -> None:
    if T <= 0.0:
        raise ValidationError("Temperature must be positive", parameter="temperature")
    if Pd <= 0.0:
        raise ValidationError("Dew pressure must be positive", parameter="dew_pressure")
    if len(z) != len(cs):
        raise ValidationError("Composition length must match number of components", parameter="composition")
    if np.any(Ps <= 0.0):
        raise ValidationError("All pressure steps must be positive", parameter="pressure_steps")


def _cvd_step(
    pressure: float,
    temperature: float,
    cell_composition: NDArray[np.float64],
    n_total: float,
    cumulative_gas: float,
    V_cell: float,
    components: list[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> tuple[CVDStepResult, NDArray[np.float64], float, float]:
    """Run one CVD step."""

    P = float(pressure)
    T = float(temperature)
    z = cell_composition
    fl = pt_flash(P, T, z, components, eos, binary_interaction=binary_interaction)

    if fl.phase in {"vapor", "liquid"}:
        ph = fl.phase
        Z = _z_root(eos.compressibility(P, T, z, phase=ph, binary_interaction=binary_interaction), ph)
        v = _v(Z, T, P)
        V = n_total * v
        if V < V_cell and not _volume_matches_target(V, V_cell):
            raise PhaseError(
                "Single-phase CVD step cannot satisfy target cell volume by depletion",
                phase=ph,
                pressure=P,
                temperature=T,
                current_volume=V,
                target_volume=V_cell,
            )

        n1 = V_cell / v
        if n1 > n_total and _volume_matches_target(V, V_cell):
            n1 = n_total
        npd = max(0.0, n_total - n1)
        if npd < CVD_VOLUME_ABSOLUTE_TOLERANCE:
            npd = 0.0
        cumulative_gas += npd
        rho = calculate_density(P, T, z, components, eos, ph, binary_interaction)
        return (
            CVDStepResult(
                pressure=P,
                temperature=T,
                liquid_dropout=1.0 if ph == "liquid" else 0.0,
                gas_produced=npd,
                cumulative_gas_produced=cumulative_gas,
                Z_two_phase=Z,
                liquid_density=rho.mass_density if ph == "liquid" else 0.0,
                vapor_density=rho.mass_density if ph == "vapor" else 0.0,
                liquid_composition=z.copy() if ph == "liquid" else np.zeros_like(z),
                vapor_composition=z.copy() if ph == "vapor" else np.zeros_like(z),
                cell_composition=z.copy(),
                moles_remaining=n_total - npd,
            ),
            z.copy(),
            n_total - npd,
            cumulative_gas,
        )

    nV = float(fl.vapor_fraction) * float(n_total)
    nL = (1.0 - float(fl.vapor_fraction)) * float(n_total)
    x = fl.liquid_composition
    y = fl.vapor_composition
    ZL = _z_root(eos.compressibility(P, T, x, phase="liquid", binary_interaction=binary_interaction), "liquid")
    ZV = _z_root(eos.compressibility(P, T, y, phase="vapor", binary_interaction=binary_interaction), "vapor")
    VL = _V(nL, ZL, T, P)
    VV = _V(nV, ZV, T, P)
    Vt = VL + VV
    Zt = _Z(Vt, n_total, T, P)

    if VV > 0.0:
        npd = max(0.0, min((Vt - V_cell) / _v(ZV, T, P), nV))
    else:
        npd = 0.0
    cumulative_gas += npd

    nVr = nV - npd
    n1 = nL + nVr
    if n1 > 0.0:
        z1 = (nL * x + nVr * y) / n1
        z1 = z1 / z1.sum()
    else:
        z1 = x.copy()

    rhoL = calculate_density(P, T, x, components, eos, "liquid", binary_interaction)
    rhoV = calculate_density(P, T, y, components, eos, "vapor", binary_interaction)
    return (
        CVDStepResult(
            pressure=P,
            temperature=T,
            liquid_dropout=VL / V_cell,
            gas_produced=npd,
            cumulative_gas_produced=cumulative_gas,
            Z_two_phase=Zt,
            liquid_density=rhoL.mass_density,
            vapor_density=rhoV.mass_density,
            liquid_composition=x.copy(),
            vapor_composition=y.copy(),
            cell_composition=z1,
            moles_remaining=n1,
        ),
        z1,
        n1,
        cumulative_gas,
    )


def simulate_cvd(
    composition: NDArray[np.float64],
    temperature: float,
    components: list[Component],
    eos: CubicEOS,
    dew_pressure: float,
    pressure_steps: NDArray[np.float64],
    binary_interaction: Optional[NDArray[np.float64]] = None,
) -> CVDResult:
    """Run CVD."""

    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    T = float(temperature)
    Pd = float(dew_pressure)
    _validate_cvd_inputs(z, T, Pd, pressure_steps, components)

    Zd = _z_root(eos.compressibility(Pd, T, z, phase="vapor", binary_interaction=binary_interaction), "vapor")
    Vcell = _v(Zd, T, Pd)

    rhoVd = calculate_density(Pd, T, z, components, eos, "vapor", binary_interaction)
    steps = [
        CVDStepResult(
            pressure=Pd,
            temperature=T,
            liquid_dropout=0.0,
            gas_produced=0.0,
            cumulative_gas_produced=0.0,
            Z_two_phase=Zd,
            liquid_density=0.0,
            vapor_density=rhoVd.mass_density,
            liquid_composition=np.zeros_like(z),
            vapor_composition=z.copy(),
            cell_composition=z.copy(),
            moles_remaining=1.0,
        )
    ]

    z1 = z.copy()
    n1 = 1.0
    Gp = 0.0
    ok = True
    for P in pressure_steps:
        if P >= Pd:
            continue
        try:
            step, z1, n1, Gp = _cvd_step(
                float(P),
                T,
                z1,
                n1,
                Gp,
                Vcell,
                components,
                eos,
                binary_interaction,
            )
            steps.append(step)
        except (ConvergenceError, PhaseError):
            ok = False
            steps.append(
                CVDStepResult(
                    pressure=float(P),
                    temperature=T,
                    liquid_dropout=np.nan,
                    gas_produced=np.nan,
                    cumulative_gas_produced=Gp,
                    Z_two_phase=np.nan,
                    liquid_density=np.nan,
                    vapor_density=np.nan,
                    liquid_composition=z1.copy(),
                    vapor_composition=np.zeros_like(z),
                    cell_composition=z1.copy(),
                    moles_remaining=n1,
                )
            )

    return CVDResult(
        temperature=T,
        dew_pressure=Pd,
        initial_Z=Zd,
        steps=steps,
        pressures=np.array([s.pressure for s in steps]),
        liquid_dropouts=np.array([s.liquid_dropout for s in steps]),
        cumulative_gas=np.array([s.cumulative_gas_produced for s in steps]),
        Z_values=np.array([s.Z_two_phase for s in steps]),
        feed_composition=z,
        converged=ok,
    )
