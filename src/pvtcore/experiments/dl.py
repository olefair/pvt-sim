"""DL."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash
from ..helper_functions import (
    P_sc,
    SCF_PER_STB_PER_SM3_SM3,
    T_sc_petroleum,
    _Bo,
    _Bt,
    _Rs,
    _V,
    _flash_sc,
    _gas_V,
    _scf_stb,
)
from ..models.component import Component
from ..properties.density import calculate_density, mixture_molecular_weight


####################
# DL
####################
@dataclass
class DLStepResult:
    """One DL step."""

    pressure: float
    temperature: float
    Rs: float
    Rs_scf_stb: float
    Bo: float
    oil_density: float
    gas_gravity: float
    gas_Z: float
    Bt: float
    Bg: Optional[float]
    Bg_rb_per_scf: Optional[float]
    liquid_composition: NDArray[np.float64]
    gas_composition: NDArray[np.float64]
    vapor_fraction: float
    cumulative_gas: float
    cumulative_gas_scf_stb: float
    liquid_moles_remaining: float


@dataclass
class DLResult:
    """Full DL result."""

    temperature: float
    bubble_pressure: float
    steps: list[DLStepResult]
    pressures: NDArray[np.float64]
    Rs_values: NDArray[np.float64]
    Bo_values: NDArray[np.float64]
    oil_densities: NDArray[np.float64]
    Bt_values: NDArray[np.float64]
    Rsi: float
    Rsi_scf_stb: float
    Boi: float
    residual_oil_density: float
    feed_composition: NDArray[np.float64]
    converged: bool


####################
# HELPER FUNCTIONS
####################
def _validate_dl_inputs(
    z: NDArray[np.float64],
    T: float,
    Pb: float,
    Ps: NDArray[np.float64],
    cs: list[Component],
) -> None:
    if T <= 0.0:
        raise ValidationError("Temperature must be positive", parameter="temperature")
    if Pb <= 0.0:
        raise ValidationError("Bubble pressure must be positive", parameter="bubble_pressure")
    if len(z) != len(cs):
        raise ValidationError("Composition length must match number of components", parameter="composition")
    if np.any(Ps <= 0.0):
        raise ValidationError("All pressure steps must be positive", parameter="pressure_steps")


def _dl_step(
    P: float,
    T: float,
    z: NDArray[np.float64],
    n: float,
    Gp: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
    Vo_st: float,
    Psc: float,
    Tsc: float,
) -> tuple[DLStepResult, NDArray[np.float64], float, float]:
    fl = pt_flash(P, T, z, cs, eos, binary_interaction=kij)

    if fl.phase == "liquid":
        rhoL = calculate_density(P, T, z, cs, eos, "liquid", kij)
        Vo = float(n) * rhoL.molar_volume
        st = _flash_sc(z, n, cs, eos, kij, Psc, Tsc)
        Rs = _Rs(float(st["Vg_sc"]), Vo_st)
        Bo = _Bo(Vo, Vo_st)
        Bt = _Bt(Vo, 0.0, Vo_st)
        Zg = float(st["Zg_sc"])
        if not np.isfinite(Zg):
            Zg = 1.0
        return (
            DLStepResult(
                pressure=P,
                temperature=T,
                Rs=Rs,
                Rs_scf_stb=_scf_stb(Rs),
                Bo=Bo,
                oil_density=rhoL.mass_density,
                gas_gravity=np.nan,
                gas_Z=Zg,
                Bt=Bt,
                Bg=None,
                Bg_rb_per_scf=None,
                liquid_composition=z.copy(),
                gas_composition=np.zeros_like(z),
                vapor_fraction=0.0,
                cumulative_gas=Gp,
                cumulative_gas_scf_stb=_scf_stb(Gp),
                liquid_moles_remaining=n,
            ),
            z.copy(),
            n,
            Gp,
        )

    nV = float(fl.vapor_fraction) * float(n)
    nL = (1.0 - float(fl.vapor_fraction)) * float(n)
    x = fl.liquid_composition
    y = fl.vapor_composition

    Vg_sc, _ = _gas_V(y, nV, Psc, Tsc, cs, eos, kij)
    Gp += _Rs(Vg_sc, Vo_st)

    rhoL = calculate_density(P, T, x, cs, eos, "liquid", kij)
    rhoV = calculate_density(P, T, y, cs, eos, "vapor", kij)
    Vo = nL * rhoL.molar_volume

    MWg = mixture_molecular_weight(y, cs)
    gg = MWg / 28.97

    ZV = eos.compressibility(P, T, y, phase="vapor", binary_interaction=kij)
    if isinstance(ZV, list):
        ZV = ZV[-1]

    st = _flash_sc(x, nL, cs, eos, kij, Psc, Tsc)
    Rs = _Rs(float(st["Vg_sc"]), Vo_st)
    Bo = _Bo(Vo, Vo_st)
    Vg = _V(nV, float(ZV), T, P)
    Bt = _Bt(Vo, Vg, Vo_st)
    Bg = Vg / Vg_sc if Vg_sc > 0.0 else None

    return (
        DLStepResult(
            pressure=P,
            temperature=T,
            Rs=Rs,
            Rs_scf_stb=_scf_stb(Rs),
            Bo=Bo,
            oil_density=rhoL.mass_density,
            gas_gravity=gg,
            gas_Z=float(ZV),
            Bt=Bt,
            Bg=Bg,
            Bg_rb_per_scf=(Bg / SCF_PER_STB_PER_SM3_SM3) if Bg is not None else None,
            liquid_composition=x.copy(),
            gas_composition=y.copy(),
            vapor_fraction=float(fl.vapor_fraction),
            cumulative_gas=Gp,
            cumulative_gas_scf_stb=_scf_stb(Gp),
            liquid_moles_remaining=nL,
        ),
        x.copy(),
        nL,
        Gp,
    )


def simulate_dl(
    composition: NDArray[np.float64],
    temperature: float,
    components: list[Component],
    eos: CubicEOS,
    bubble_pressure: float,
    pressure_steps: NDArray[np.float64],
    binary_interaction: Optional[NDArray[np.float64]] = None,
    standard_temperature: float = T_sc_petroleum,
    standard_pressure: float = P_sc,
) -> DLResult:
    """Run DL."""

    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    T = float(temperature)
    Pb = float(bubble_pressure)
    Psc = float(standard_pressure)
    Tsc = float(standard_temperature)

    _validate_dl_inputs(z, T, Pb, pressure_steps, components)

    st = _flash_sc(z, 1.0, components, eos, binary_interaction, Psc, Tsc)
    rho_o_sc = float(st["rho_o"])
    Vo_st = float(st["Vo_st"])
    Zg_sc = float(st["Zg_sc"])
    if not np.isfinite(Zg_sc):
        Zg_sc = 1.0

    rhoL0 = calculate_density(Pb, T, z, components, eos, "liquid", binary_interaction)
    Boi = _Bo(rhoL0.molar_volume, Vo_st)
    Rsi = _Rs(float(st["Vg_sc"]), Vo_st)

    steps = [
        DLStepResult(
            pressure=Pb,
            temperature=T,
            Rs=Rsi,
            Rs_scf_stb=_scf_stb(Rsi),
            Bo=Boi,
            oil_density=rhoL0.mass_density,
            gas_gravity=np.nan,
            gas_Z=Zg_sc,
            Bt=Boi,
            Bg=None,
            Bg_rb_per_scf=None,
            liquid_composition=z.copy(),
            gas_composition=np.zeros_like(z),
            vapor_fraction=0.0,
            cumulative_gas=0.0,
            cumulative_gas_scf_stb=0.0,
            liquid_moles_remaining=1.0,
        )
    ]

    x = z.copy()
    n = 1.0
    Gp = 0.0
    ok = True

    for P in pressure_steps:
        if P >= Pb:
            continue
        try:
            step, x, n, Gp = _dl_step(
                float(P),
                T,
                x,
                n,
                Gp,
                components,
                eos,
                binary_interaction,
                Vo_st,
                Psc,
                Tsc,
            )
            steps.append(step)
        except (ConvergenceError, PhaseError):
            ok = False
            steps.append(
                DLStepResult(
                    pressure=float(P),
                    temperature=T,
                    Rs=np.nan,
                    Rs_scf_stb=np.nan,
                    Bo=np.nan,
                    oil_density=np.nan,
                    gas_gravity=np.nan,
                    gas_Z=np.nan,
                    Bt=np.nan,
                    Bg=None,
                    Bg_rb_per_scf=None,
                    liquid_composition=x.copy(),
                    gas_composition=np.zeros_like(z),
                    vapor_fraction=np.nan,
                    cumulative_gas=Gp,
                    cumulative_gas_scf_stb=_scf_stb(Gp),
                    liquid_moles_remaining=n,
                )
            )

    return DLResult(
        temperature=T,
        bubble_pressure=Pb,
        steps=steps,
        pressures=np.array([s.pressure for s in steps]),
        Rs_values=np.array([s.Rs for s in steps]),
        Bo_values=np.array([s.Bo for s in steps]),
        oil_densities=np.array([s.oil_density for s in steps]),
        Bt_values=np.array([s.Bt for s in steps]),
        Rsi=Rsi,
        Rsi_scf_stb=_scf_stb(Rsi),
        Boi=Boi,
        residual_oil_density=rho_o_sc,
        feed_composition=z,
        converged=ok,
    )
