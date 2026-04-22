"""Separator train."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ConvergenceError, PhaseError, ValidationError
from ..eos.base import CubicEOS
from ..flash.pt_flash import pt_flash
from ..helper_functions import P_sc, T_sc_metric, _Bg, _Bo, _Rs, _flash_sc, _gas_V, _liq_V, _scf_stb, _z_root
from ..models.component import Component
from ..properties.density import calculate_density, mixture_molecular_weight


####################
# SEPARATOR
####################
@dataclass
class SeparatorConditions:
    """One separator stage."""

    pressure: float
    temperature: float
    name: str = ""


@dataclass
class SeparatorStageResult:
    """One separator step."""

    stage_number: int
    conditions: SeparatorConditions
    inlet_composition: NDArray[np.float64]
    inlet_moles: float
    vapor_fraction: float
    liquid_composition: NDArray[np.float64]
    vapor_composition: NDArray[np.float64]
    liquid_moles: float
    vapor_moles: float
    liquid_density: float
    vapor_density: float
    Z_liquid: float
    Z_vapor: float
    converged: bool


@dataclass
class SeparatorTrainResult:
    """Full separator result."""

    stages: list[SeparatorStageResult]
    stock_tank_oil_composition: NDArray[np.float64]
    stock_tank_oil_moles: float
    stock_tank_oil_density: float
    stock_tank_oil_MW: float
    stock_tank_oil_SG: float
    API_gravity: float
    total_gas_composition: NDArray[np.float64]
    total_gas_moles: float
    Bo: float
    Rs: float
    Rs_scf_stb: float
    Bg: float
    shrinkage: float
    converged: bool


####################
# HELPER FUNCTIONS
####################
def _validate_separator_inputs(
    z: NDArray[np.float64],
    cs: list[Component],
    stages: list[SeparatorConditions],
) -> None:
    if len(z) != len(cs):
        raise ValidationError("Composition length must match number of components", parameter="composition")
    if not stages:
        raise ValidationError("At least one separator stage required", parameter="separator_stages")
    for i, stage in enumerate(stages):
        if stage.pressure <= 0.0:
            raise ValidationError(f"Stage {i} pressure must be positive", parameter=f"separator_stages[{i}].pressure")
        if stage.temperature <= 0.0:
            raise ValidationError(
                f"Stage {i} temperature must be positive",
                parameter=f"separator_stages[{i}].temperature",
            )


def _separator_stage(
    z: NDArray[np.float64],
    n: float,
    cond: SeparatorConditions,
    i: int,
    cs: list[Component],
    eos: CubicEOS,
    kij: Optional[NDArray[np.float64]],
) -> SeparatorStageResult:
    P = float(cond.pressure)
    T = float(cond.temperature)
    fl = pt_flash(P, T, z, cs, eos, binary_interaction=kij)

    if fl.phase == "liquid":
        ZL = _z_root(eos.compressibility(P, T, z, phase="liquid", binary_interaction=kij), "liquid")
        rhoL = calculate_density(P, T, z, cs, eos, "liquid", kij)
        return SeparatorStageResult(
            stage_number=i,
            conditions=cond,
            inlet_composition=z.copy(),
            inlet_moles=n,
            vapor_fraction=0.0,
            liquid_composition=z.copy(),
            vapor_composition=np.zeros_like(z),
            liquid_moles=n,
            vapor_moles=0.0,
            liquid_density=rhoL.mass_density,
            vapor_density=0.0,
            Z_liquid=ZL,
            Z_vapor=0.0,
            converged=True,
        )

    if fl.phase == "vapor":
        ZV = _z_root(eos.compressibility(P, T, z, phase="vapor", binary_interaction=kij), "vapor")
        rhoV = calculate_density(P, T, z, cs, eos, "vapor", kij)
        return SeparatorStageResult(
            stage_number=i,
            conditions=cond,
            inlet_composition=z.copy(),
            inlet_moles=n,
            vapor_fraction=1.0,
            liquid_composition=np.zeros_like(z),
            vapor_composition=z.copy(),
            liquid_moles=0.0,
            vapor_moles=n,
            liquid_density=0.0,
            vapor_density=rhoV.mass_density,
            Z_liquid=0.0,
            Z_vapor=ZV,
            converged=True,
        )

    x = fl.liquid_composition
    y = fl.vapor_composition
    nV = float(fl.vapor_fraction) * float(n)
    nL = (1.0 - float(fl.vapor_fraction)) * float(n)
    ZL = _z_root(eos.compressibility(P, T, x, phase="liquid", binary_interaction=kij), "liquid")
    ZV = _z_root(eos.compressibility(P, T, y, phase="vapor", binary_interaction=kij), "vapor")
    rhoL = calculate_density(P, T, x, cs, eos, "liquid", kij)
    rhoV = calculate_density(P, T, y, cs, eos, "vapor", kij)
    return SeparatorStageResult(
        stage_number=i,
        conditions=cond,
        inlet_composition=z.copy(),
        inlet_moles=n,
        vapor_fraction=float(fl.vapor_fraction),
        liquid_composition=x.copy(),
        vapor_composition=y.copy(),
        liquid_moles=nL,
        vapor_moles=nV,
        liquid_density=rhoL.mass_density,
        vapor_density=rhoV.mass_density,
        Z_liquid=ZL,
        Z_vapor=ZV,
        converged=True,
    )


def _geometric_pressures(Ph: float, Pl: float, nst: int, ratio: float) -> list[float]:
    if nst == 1:
        return [float(np.sqrt(Ph * Pl))]
    dln = np.log(Pl / Ph) / nst
    return [Ph * np.exp(dln * (i + 1) * ratio * nst / (nst - 0.5)) for i in range(nst)]


def calculate_separator_train(
    composition: NDArray[np.float64],
    components: list[Component],
    eos: CubicEOS,
    separator_stages: list[SeparatorConditions],
    reservoir_pressure: float,
    reservoir_temperature: float,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    include_stock_tank: bool = True,
) -> SeparatorTrainResult:
    """Run a separator train."""

    z = np.asarray(composition, dtype=np.float64)
    z = z / z.sum()
    nc = len(z)
    _validate_separator_inputs(z, components, separator_stages)

    stages = list(separator_stages)
    if include_stock_tank:
        stages.append(SeparatorConditions(pressure=P_sc, temperature=T_sc_metric, name="Stock Tank"))

    rows: list[SeparatorStageResult] = []
    gas_rows: list[tuple[NDArray[np.float64], float]] = []
    x = z.copy()
    n = 1.0
    nG = 0.0
    ok = True

    for i, cond in enumerate(stages):
        try:
            row = _separator_stage(x, n, cond, i, components, eos, binary_interaction)
            rows.append(row)
            if row.converged:
                x = row.liquid_composition.copy()
                n = row.liquid_moles
                if row.vapor_moles > 0.0:
                    gas_rows.append((row.vapor_composition.copy(), row.vapor_moles))
                    nG += row.vapor_moles
            else:
                ok = False
        except (ConvergenceError, PhaseError):
            ok = False
            rows.append(
                SeparatorStageResult(
                    stage_number=i,
                    conditions=cond,
                    inlet_composition=x.copy(),
                    inlet_moles=n,
                    vapor_fraction=np.nan,
                    liquid_composition=x.copy(),
                    vapor_composition=np.zeros(nc),
                    liquid_moles=n,
                    vapor_moles=0.0,
                    liquid_density=np.nan,
                    vapor_density=np.nan,
                    Z_liquid=np.nan,
                    Z_vapor=np.nan,
                    converged=False,
                )
            )

    if include_stock_tank:
        x_st = x.copy()
        n_st = n
        Vo_st, rho_st = _liq_V(x_st, n_st, P_sc, T_sc_metric, components, eos, binary_interaction)
        rho_o = rho_st.mass_density
    else:
        st = _flash_sc(x, n, components, eos, binary_interaction, P_sc, T_sc_metric)
        x_st = np.asarray(st["x"], dtype=np.float64)
        n_st = float(st["nL"])
        Vo_st = float(st["Vo_st"])
        rho_o = float(st["rho_o"])
        if float(st["nV"]) > 0.0:
            gas_rows.append((np.asarray(st["y"], dtype=np.float64), float(st["nV"])))
            nG += float(st["nV"])

    MWo = mixture_molecular_weight(x_st, components)
    SGo = rho_o / 999.0
    API = 141.5 / SGo - 131.5

    if nG > 0.0 and gas_rows:
        yG = np.zeros(nc)
        for y, ng in gas_rows:
            yG += y * ng
        yG /= nG
    else:
        yG = np.zeros(nc)

    Vo_res, _ = _liq_V(
        z,
        1.0,
        float(reservoir_pressure),
        float(reservoir_temperature),
        components,
        eos,
        binary_interaction,
    )
    Bo = _Bo(Vo_res, Vo_st)
    Vg_sc, _ = _gas_V(yG, nG, P_sc, T_sc_metric, components, eos, binary_interaction)
    Rs = _Rs(Vg_sc, Vo_st)
    Vg_res, _ = _gas_V(
        yG,
        nG,
        float(reservoir_pressure),
        float(reservoir_temperature),
        components,
        eos,
        binary_interaction,
    )
    Bg = _Bg(Vg_res, Vg_sc)
    return SeparatorTrainResult(
        stages=rows,
        stock_tank_oil_composition=x_st,
        stock_tank_oil_moles=n_st,
        stock_tank_oil_density=rho_o,
        stock_tank_oil_MW=MWo,
        stock_tank_oil_SG=SGo,
        API_gravity=API,
        total_gas_composition=yG,
        total_gas_moles=nG,
        Bo=Bo,
        Rs=Rs,
        Rs_scf_stb=_scf_stb(Rs),
        Bg=Bg,
        shrinkage=1.0 / Bo if Bo > 0.0 else np.nan,
        converged=ok,
    )


def optimize_separator_pressures(
    composition: NDArray[np.float64],
    components: list[Component],
    eos: CubicEOS,
    reservoir_pressure: float,
    reservoir_temperature: float,
    n_stages: int = 2,
    binary_interaction: Optional[NDArray[np.float64]] = None,
    temperature: float = 300.0,
) -> tuple[list[SeparatorConditions], SeparatorTrainResult]:
    """Pick a simple geometric separator schedule."""

    if n_stages < 1:
        raise ValidationError("Need at least 1 separator stage", parameter="n_stages")

    Ph = min(float(reservoir_pressure) * 0.3, 10e6)
    Pl = 0.2e6
    best_stages: list[SeparatorConditions] | None = None
    best_result: SeparatorTrainResult | None = None
    best_Bo = 0.0

    for ratio in (0.3, 0.4, 0.5):
        Ps = _geometric_pressures(Ph, Pl, n_stages, ratio)
        stages = [
            SeparatorConditions(pressure=float(P), temperature=float(temperature), name=f"Stage {i + 1}")
            for i, P in enumerate(Ps)
        ]
        try:
            result = calculate_separator_train(
                composition,
                components,
                eos,
                stages,
                reservoir_pressure,
                reservoir_temperature,
                binary_interaction=binary_interaction,
            )
            if result.converged and result.Bo > best_Bo:
                best_stages = stages
                best_result = result
                best_Bo = result.Bo
        except Exception:
            continue

    if best_stages is None or best_result is None:
        Ps = _geometric_pressures(Ph, Pl, n_stages, 0.4)
        best_stages = [
            SeparatorConditions(pressure=float(P), temperature=float(temperature), name=f"Stage {i + 1}")
            for i, P in enumerate(Ps)
        ]
        best_result = calculate_separator_train(
            composition,
            components,
            eos,
            best_stages,
            reservoir_pressure,
            reservoir_temperature,
            binary_interaction=binary_interaction,
        )

    return best_stages, best_result
