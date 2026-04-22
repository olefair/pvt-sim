"""Course helper functions."""

from __future__ import annotations

from typing import Literal, Optional

import numpy as np
from numpy.typing import NDArray

from .core.errors import PhaseError
from .eos.base import CubicEOS
from .flash.pt_flash import pt_flash
from .models.component import Component
from .properties.density import DensityResult, calculate_density


####################
# NOTATION
####################
# z = overall composition
# x = liquid composition
# y = vapor composition
# Cn = carbon number
# Zn = SCN mole fraction
# zP = plus-fraction mole fraction
# MWP = plus-fraction molecular weight
# A, B = Pedersen coefficients
# Z = compressibility factor
# ZL, ZV = liquid/vapor Z
# n = total moles
# nL, nV = liquid/vapor moles
# VL, VV = liquid/vapor volumes
# Vo_st, Vo_res = stock-tank/reservoir oil volume
# Vg_sc, Vg_res = standard/reservoir gas volume
# rhoL, rhoV = liquid/vapor molar density
# Rs, Bo, Bg, Bt = standard PVT outputs

R = 8.31446261815324
P_sc = 101325.0
T_sc_metric = 288.15
T_sc_petroleum = (60.0 - 32.0) * 5.0 / 9.0 + 273.15
SCF_PER_STB_PER_SM3_SM3 = 35.3146667 / 6.28981077


####################
# HELPER FUNCTIONS
####################
def _z_root(
    Z: float | list[float] | tuple[float, ...] | NDArray[np.float64],
    ph: Literal["liquid", "vapor"],
) -> float:
    if isinstance(Z, (list, tuple, np.ndarray)):
        return float(Z[0] if ph == "liquid" else Z[-1])
    return float(Z)


def _V(n: float, Z: float, T: float, P: float) -> float:
    return float(n) * float(Z) * R * float(T) / float(P)


def _v(Z: float, T: float, P: float) -> float:
    return _V(1.0, Z, T, P)


def _Z(V: float, n: float, T: float, P: float) -> float:
    if n <= 0.0:
        raise ValueError("Total moles must be positive.")
    return float(P) * float(V) / (float(n) * R * float(T))


def _VL(nL: float, rhoL: float) -> float:
    if rhoL <= 0.0:
        raise ValueError("Liquid molar density must be positive.")
    return float(nL) / float(rhoL)


def _Rs(Vg_sc: float, Vo_st: float) -> float:
    if Vg_sc <= 0.0:
        return 0.0
    if Vo_st <= 0.0:
        raise ValueError("Stock-tank oil volume must be positive.")
    return float(Vg_sc) / float(Vo_st)


def _Bo(Vo_res: float, Vo_st: float) -> float:
    if Vo_st <= 0.0:
        raise ValueError("Stock-tank oil volume must be positive.")
    return float(Vo_res) / float(Vo_st)


def _Bg(Vg_res: float, Vg_sc: float) -> float:
    if Vg_sc <= 0.0:
        return float("nan")
    return float(Vg_res) / float(Vg_sc)


def _Bt(Vo_res: float, Vg_res: float, Vo_st: float) -> float:
    if Vo_st <= 0.0:
        raise ValueError("Stock-tank oil volume must be positive.")
    return (float(Vo_res) + float(Vg_res)) / float(Vo_st)


def _scf_stb(Rs: float) -> float:
    return float(Rs) * SCF_PER_STB_PER_SM3_SM3


def _gas_V(
    y: NDArray[np.float64],
    nV: float,
    P: float,
    T: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
) -> tuple[float, float]:
    if nV <= 0.0:
        return 0.0, float("nan")
    ZV = _z_root(
        eos.compressibility(P, T, y, phase="vapor", binary_interaction=kij),
        "vapor",
    )
    return _V(nV, ZV, T, P), ZV


def _liq_V(
    x: NDArray[np.float64],
    nL: float,
    P: float,
    T: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
) -> tuple[float, DensityResult]:
    rho = calculate_density(P, T, x, cs, eos, "liquid", kij)
    return _VL(nL, rho.molar_density), rho


def _flash_sc(
    z: NDArray[np.float64],
    n: float,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
    Psc: float = P_sc,
    Tsc: float = T_sc_metric,
) -> dict[str, object]:
    fl = pt_flash(Psc, Tsc, z, cs, eos, binary_interaction=kij)
    if fl.phase == "vapor":
        raise PhaseError(
            "Standard-state flash produced no stock-tank oil.",
            phase="vapor",
            pressure=Psc,
            temperature=Tsc,
        )

    if fl.phase == "liquid":
        x = z.copy()
        y = np.zeros_like(z)
        nL = float(n)
        nV = 0.0
    else:
        x = fl.liquid_composition
        y = fl.vapor_composition
        nV = float(fl.vapor_fraction) * float(n)
        nL = (1.0 - float(fl.vapor_fraction)) * float(n)

    if nL <= 0.0:
        raise PhaseError(
            "Standard-state flash produced non-positive stock-tank oil moles.",
            phase=fl.phase,
            pressure=Psc,
            temperature=Tsc,
        )

    Vo_st, rhoL = _liq_V(x, nL, Psc, Tsc, cs, eos, kij)
    Vg_sc, Zg_sc = _gas_V(y, nV, Psc, Tsc, cs, eos, kij)
    return {
        "x": x.copy(),
        "y": y.copy(),
        "nL": nL,
        "nV": nV,
        "Vo_st": Vo_st,
        "Vg_sc": Vg_sc,
        "rho_o": float(rhoL.mass_density),
        "Zg_sc": Zg_sc,
    }


####################
# COMPATIBILITY
####################
def _select_z_factor(
    Z: float | list[float] | tuple[float, ...] | NDArray[np.float64],
    phase: Literal["liquid", "vapor"],
) -> float:
    return _z_root(Z, phase)


def _calculate_volume_from_z(n: float, Z: float, T: float, P: float) -> float:
    return _V(n, Z, T, P)


def _calculate_molar_volume(Z: float, T: float, P: float) -> float:
    return _v(Z, T, P)


def _calculate_overall_z(V: float, n: float, T: float, P: float) -> float:
    return _Z(V, n, T, P)


def _calculate_liquid_volume(nL: float, rhoL_molar: float) -> float:
    return _VL(nL, rhoL_molar)


def _calculate_solution_gor(Vg_sc: float, Vo_st: float) -> float:
    return _Rs(Vg_sc, Vo_st)


def _calculate_oil_fvf(Vo_res: float, Vo_st: float) -> float:
    return _Bo(Vo_res, Vo_st)


def _calculate_gas_fvf(Vg_res: float, Vg_sc: float) -> float:
    return _Bg(Vg_res, Vg_sc)


def _calculate_total_fvf(Vo_res: float, Vg_res: float, Vo_st: float) -> float:
    return _Bt(Vo_res, Vg_res, Vo_st)


def _scf_stb_from_sm3_sm3(Rs: float) -> float:
    return _scf_stb(Rs)


def _calculate_gas_volume_from_eos(
    y: NDArray[np.float64],
    nV: float,
    P: float,
    T: float,
    components: list[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> tuple[float, float]:
    return _gas_V(y, nV, P, T, components, eos, binary_interaction)


def _calculate_oil_volume_from_density(
    x: NDArray[np.float64],
    nL: float,
    P: float,
    T: float,
    components: list[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
) -> tuple[float, DensityResult]:
    return _liq_V(x, nL, P, T, components, eos, binary_interaction)


def _flash_to_standard_state(
    z: NDArray[np.float64],
    n: float,
    components: list[Component],
    eos: CubicEOS,
    binary_interaction: Optional[NDArray[np.float64]],
    P_std: float = P_sc,
    T_std: float = T_sc_metric,
) -> dict[str, object]:
    return _flash_sc(z, n, components, eos, binary_interaction, P_std, T_std)
