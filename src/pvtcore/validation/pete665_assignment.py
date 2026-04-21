"""PETE 665 assignment baseline runner.

This module provides a narrow, reproducible run path for the course-assignment
case added to the repository. It intentionally operates at the kernel layer so
the baseline can be satisfied without first widening the desktop app schema.
"""

from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from pvtcore.core.constants import R, SC_IMPERIAL
from pvtcore.eos.pr78 import PR78EOS
from pvtcore.envelope.phase_envelope import calculate_phase_envelope
from pvtcore.experiments import simulate_cce
from pvtcore.flash import calculate_bubble_point
from pvtcore.flash.pt_flash import pt_flash
from pvtcore.models import Component, get_components_cached, resolve_component_id
from pvtcore.properties.density import calculate_density, mixture_molecular_weight


PA_PER_PSIA = 6894.757293168361
ATMOSPHERIC_PRESSURE_PA = 101325.0
SCF_PER_STB_PER_SM3_PER_SM3 = 35.3146667 / 6.28981077
DEFAULT_ZC_FOR_INLINE_COMPONENTS = 0.27


@dataclass(frozen=True)
class InlineComponentSpec:
    """Explicit component properties supplied outside the DB."""

    component_id: str
    name: str
    formula: str
    molecular_weight_g_per_mol: float
    critical_temperature_k: float
    critical_pressure_pa: float
    omega: float


@dataclass(frozen=True)
class AssignmentCase:
    """Structured PETE 665 assignment case definition."""

    name: str
    source_document: str
    notes: tuple[str, ...]
    temperature_by_initials_f: dict[str, float]
    composition_rows: tuple[tuple[str, float], ...]
    inline_components: dict[str, InlineComponentSpec]
    cce_pressures_psia: tuple[float, ...]
    dl_pressures_psia: tuple[float, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def default_assignment_case_path() -> Path:
    """Return the default repo-local assignment case file."""
    return _repo_root() / "examples" / "pete665_assignment_case.json"


def fahrenheit_to_kelvin(value_f: float) -> float:
    """Convert Fahrenheit to Kelvin."""
    return (float(value_f) - 32.0) * 5.0 / 9.0 + 273.15


def kelvin_to_fahrenheit(value_k: float) -> float:
    """Convert Kelvin to Fahrenheit."""
    return (float(value_k) - 273.15) * 9.0 / 5.0 + 32.0


def psia_to_pa(value_psia: float) -> float:
    """Convert psia to Pa."""
    return float(value_psia) * PA_PER_PSIA


def pa_to_psia(value_pa: float) -> float:
    """Convert Pa to psia."""
    return float(value_pa) / PA_PER_PSIA


def _normalize_temperature_unit(unit: str) -> str:
    return unit.strip().lower()


def _convert_temperature_to_kelvin(value: float, unit: str) -> float:
    unit_n = _normalize_temperature_unit(unit)
    if unit_n == "k":
        return float(value)
    if unit_n in {"f", "degf", "fahrenheit"}:
        return fahrenheit_to_kelvin(value)
    if unit_n in {"c", "degc", "celsius"}:
        return float(value) + 273.15
    raise ValueError(f"Unsupported temperature unit: {unit}")


def _normalize_pressure_unit(unit: str) -> str:
    return unit.strip().lower()


def _convert_pressure_to_pa(value: float, unit: str) -> float:
    unit_n = _normalize_pressure_unit(unit)
    if unit_n == "pa":
        return float(value)
    if unit_n in {"psia", "psi"}:
        return psia_to_pa(value)
    if unit_n == "bar":
        return float(value) * 1e5
    raise ValueError(f"Unsupported pressure unit: {unit}")


def _inverse_edmister_tb(critical_temperature_k: float, critical_pressure_pa: float, omega: float) -> float:
    """Recover Tb from Tc, Pc, and omega using the Edmister relation."""
    a = (3.0 / 7.0) * np.log10(critical_pressure_pa / ATMOSPHERIC_PRESSURE_PA)
    denominator = 1.0 + a / (float(omega) + 1.0)
    if denominator <= 1.0:
        raise ValueError("Cannot derive Tb from the supplied Tc/Pc/omega triple.")
    tb = float(critical_temperature_k) / denominator
    if tb <= 0.0 or tb >= critical_temperature_k:
        raise ValueError("Derived Tb is not physically valid for the supplied Tc/Pc/omega triple.")
    return tb


def _estimate_vc_from_tc_pc(
    critical_temperature_k: float,
    critical_pressure_pa: float,
    *,
    zc: float = DEFAULT_ZC_FOR_INLINE_COMPONENTS,
) -> float:
    """Estimate Vc from Tc and Pc using a nominal critical compressibility."""
    return float(zc) * R.Pa_m3_per_mol_K * float(critical_temperature_k) / float(critical_pressure_pa)


def load_assignment_case(path: str | Path | None = None) -> AssignmentCase:
    """Load and parse the PETE 665 assignment case JSON."""
    case_path = Path(path) if path is not None else default_assignment_case_path()
    raw = json.loads(case_path.read_text(encoding="utf-8"))

    temperatures = {
        initials.strip().upper(): float(value)
        for initials, value in raw["temperature_by_initials_f"].items()
    }
    composition_rows = tuple(
        (str(item["id"]).strip(), float(item["z"]))
        for item in raw["fluid"]["components"]
    )

    inline_components: dict[str, InlineComponentSpec] = {}
    for component_id, component_data in raw["fluid"].get("inline_components", {}).items():
        inline_components[str(component_id).strip()] = InlineComponentSpec(
            component_id=str(component_id).strip(),
            name=str(component_data["name"]).strip(),
            formula=str(component_data.get("formula", component_id)).strip(),
            molecular_weight_g_per_mol=float(component_data["mw_g_per_mol"]),
            critical_temperature_k=_convert_temperature_to_kelvin(
                component_data["tc_value"],
                component_data["tc_unit"],
            ),
            critical_pressure_pa=_convert_pressure_to_pa(
                component_data["pc_value"],
                component_data["pc_unit"],
            ),
            omega=float(component_data["omega"]),
        )

    return AssignmentCase(
        name=str(raw["name"]),
        source_document=str(raw["source_document"]),
        notes=tuple(str(note) for note in raw.get("notes", [])),
        temperature_by_initials_f=temperatures,
        composition_rows=composition_rows,
        inline_components=inline_components,
        cce_pressures_psia=tuple(float(value) for value in raw["targets"]["cce_pressures"]["values"]),
        dl_pressures_psia=tuple(float(value) for value in raw["targets"]["dl_pressures"]["values"]),
    )


def resolve_assignment_temperature_f(
    case: AssignmentCase,
    *,
    initials: str | None = None,
    temperature_f: float | None = None,
) -> tuple[float, str | None]:
    """Resolve the assignment temperature from initials or explicit override."""
    if initials and temperature_f is not None:
        raise ValueError("Provide either initials or temperature_f, not both.")
    if temperature_f is not None:
        return float(temperature_f), None
    if not initials:
        raise ValueError("Temperature is required. Provide initials or an explicit temperature.")

    normalized = initials.strip().upper()
    try:
        return float(case.temperature_by_initials_f[normalized]), normalized
    except KeyError as exc:
        raise ValueError(
            f"Unknown initials '{initials}'. Available: {sorted(case.temperature_by_initials_f)}"
        ) from exc


def build_inline_component(spec: InlineComponentSpec) -> Component:
    """Build a runtime Component from an inline assignment pseudo row."""
    tb_k = _inverse_edmister_tb(
        critical_temperature_k=spec.critical_temperature_k,
        critical_pressure_pa=spec.critical_pressure_pa,
        omega=spec.omega,
    )
    vc_m3_per_mol = _estimate_vc_from_tc_pc(
        critical_temperature_k=spec.critical_temperature_k,
        critical_pressure_pa=spec.critical_pressure_pa,
    )

    return Component(
        name=spec.name,
        formula=spec.formula,
        Tc=spec.critical_temperature_k,
        Pc=spec.critical_pressure_pa,
        Vc=vc_m3_per_mol,
        omega=spec.omega,
        MW=spec.molecular_weight_g_per_mol,
        Tb=tb_k,
        note=(
            "Inline assignment pseudo-component. Tb back-calculated from Tc/Pc/omega "
            "using inverse Edmister; Vc estimated with Zc=0.27."
        ),
        id=spec.component_id,
        aliases=[spec.name, spec.component_id],
        is_pseudo=True,
    )


def build_assignment_fluid(case: AssignmentCase) -> tuple[list[str], list[Component], np.ndarray]:
    """Build the assignment fluid from DB components plus the inline pseudo row."""
    component_db = get_components_cached()
    component_ids: list[str] = []
    components: list[Component] = []
    mole_fractions: list[float] = []
    duplicate_sources: dict[str, list[str]] = {}

    for raw_id, z in case.composition_rows:
        mole_fractions.append(float(z))

        if raw_id in case.inline_components:
            spec = case.inline_components[raw_id]
            component_ids.append(spec.component_id)
            components.append(build_inline_component(spec))
            duplicate_sources.setdefault(spec.component_id, []).append(raw_id)
            continue

        canonical_id = resolve_component_id(raw_id, component_db)
        component_ids.append(canonical_id)
        components.append(component_db[canonical_id])
        duplicate_sources.setdefault(canonical_id, []).append(raw_id)

    duplicates = {
        canonical_id: raw_ids
        for canonical_id, raw_ids in duplicate_sources.items()
        if len(raw_ids) > 1
    }
    if duplicates:
        raise ValueError(f"Duplicate component IDs after alias resolution: {duplicates}")

    composition = np.asarray(mole_fractions, dtype=np.float64)
    total = float(composition.sum())
    if not np.isclose(total, 1.0, atol=1e-9):
        raise ValueError(f"Assignment composition must sum to 1.0, got {total:.10f}")

    return component_ids, components, composition


def _require_linear_pressure_grid(values_psia: tuple[float, ...], label: str) -> tuple[float, float, int]:
    if len(values_psia) < 2:
        raise ValueError(f"{label} pressure list must contain at least two points.")
    expected = np.linspace(values_psia[0], values_psia[-1], len(values_psia))
    if not np.allclose(np.asarray(values_psia, dtype=float), expected, atol=1e-9):
        raise ValueError(
            f"{label} pressure list must be linearly spaced for the current kernel path: {values_psia}"
        )
    return float(values_psia[0]), float(values_psia[-1]), int(len(values_psia))


def _serialize_bubble_result(component_ids: list[str], bubble_result: Any) -> dict[str, Any]:
    return {
        "converged": bool(bubble_result.converged),
        "pressure_pa": float(bubble_result.pressure),
        "pressure_psia": pa_to_psia(bubble_result.pressure),
        "iterations": int(bubble_result.iterations),
        "residual": float(bubble_result.residual),
        "stable_liquid": bool(bubble_result.stable_liquid),
        "liquid_composition": {
            component_ids[i]: float(value)
            for i, value in enumerate(bubble_result.liquid_composition)
        },
        "vapor_composition": {
            component_ids[i]: float(value)
            for i, value in enumerate(bubble_result.vapor_composition)
        },
        "k_values": {
            component_ids[i]: float(value)
            for i, value in enumerate(bubble_result.K_values)
        },
    }


def _safe_float(value: float | None) -> float | None:
    return None if value is None or not np.isfinite(value) else float(value)


KG_PER_M3_TO_LB_PER_FT3 = 0.0624279605761446


def _serialize_cce_result(result: Any) -> dict[str, Any]:
    steps = []
    for step in result.steps:
        oil_density = _safe_float(step.liquid_density)
        gas_density = _safe_float(step.vapor_density)
        steps.append(
            {
                "pressure_pa": float(step.pressure),
                "pressure_psia": pa_to_psia(step.pressure),
                "relative_volume": float(step.relative_volume),
                "liquid_fraction": _safe_float(step.liquid_volume_fraction),
                "vapor_fraction": _safe_float(step.vapor_fraction),
                "z_factor": _safe_float(step.compressibility_Z),
                "oil_density_kg_m3": oil_density,
                "oil_density_lb_ft3": (
                    oil_density * KG_PER_M3_TO_LB_PER_FT3
                    if oil_density is not None
                    else None
                ),
                "gas_density_kg_m3": gas_density,
                "gas_density_lb_ft3": (
                    gas_density * KG_PER_M3_TO_LB_PER_FT3
                    if gas_density is not None
                    else None
                ),
                "phase": str(step.phase),
            }
        )

    return {
        "temperature_k": float(result.temperature),
        "temperature_f": kelvin_to_fahrenheit(result.temperature),
        "saturation_pressure_pa": float(result.saturation_pressure),
        "saturation_pressure_psia": pa_to_psia(result.saturation_pressure),
        "saturation_type": str(result.saturation_type),
        "converged": bool(result.converged),
        "steps": steps,
    }


AIR_MOLECULAR_WEIGHT_G_PER_MOL = 28.9647


def _compressibility_root(
    eos: PR78EOS,
    pressure: float,
    temperature: float,
    composition: np.ndarray,
    phase: str,
    binary_interaction: np.ndarray,
) -> float:
    """Return a single Z-factor value for the requested phase root."""
    z = eos.compressibility(
        pressure,
        temperature,
        composition,
        phase=phase,
        binary_interaction=binary_interaction,
    )
    if isinstance(z, (list, tuple, np.ndarray)):
        arr = np.asarray(z, dtype=float)
        return float(arr.min() if phase == "liquid" else arr.max())
    return float(z)


def _run_assignment_differential_liberation(
    *,
    composition: np.ndarray,
    reservoir_temperature_k: float,
    bubble_pressure_pa: float,
    reporting_pressures_pa: tuple[float, ...],
    components: list[Component],
    eos: PR78EOS,
    binary_interaction: np.ndarray,
) -> dict[str, Any]:
    """Simulate a proper differential-liberation test with stock-tank reference.

    Pressure schedule: [Pb, P1, P2, ..., P_N, P_std].
    All reporting pressures are run at reservoir temperature; the final
    stock-tank flash uses SC_IMPERIAL (60 F, 14.696 psia). The residual oil
    volume V_or from that last step defines Bo(P_i) = V_oil(P_i, T_res) / V_or
    and RsD(P_i) = cumulative standard gas below P_i / V_or.
    """
    P_std = float(SC_IMPERIAL.P)
    T_std = float(SC_IMPERIAL.T)
    R_gas = R.Pa_m3_per_mol_K

    descending = sorted(
        (float(p) for p in reporting_pressures_pa if float(p) < bubble_pressure_pa),
        reverse=True,
    )
    if not descending:
        raise ValueError("Reporting pressures must lie strictly below Pb.")

    # Step record per flash step (index 0 is the bubble-point reference; the last
    # index is the stock-tank flash).
    step_records: list[dict[str, Any]] = []

    # Initial state: saturated liquid at Pb, T_res.
    rho_pb = calculate_density(
        bubble_pressure_pa,
        reservoir_temperature_k,
        composition,
        components,
        eos,
        "liquid",
        binary_interaction,
    )
    v_oil_pb = 1.0 / rho_pb.molar_density  # m3 per mole of feed

    step_records.append(
        {
            "phase": "bubble",
            "pressure_pa": float(bubble_pressure_pa),
            "temperature_k": float(reservoir_temperature_k),
            "v_oil_res_per_mole_feed": float(v_oil_pb),
            "oil_density_kg_m3": float(rho_pb.mass_density),
            "liquid_moles_fraction": 1.0,
            "gas_moles_fraction_this_step": 0.0,
            "v_gas_res_per_mole_feed": 0.0,
            "v_gas_std_per_mole_feed": 0.0,
            "z_gas_at_step": None,
            "gas_gravity": None,
            "gas_composition": None,
            "liquid_composition": composition.copy(),
            "vapor_fraction_in_step": 0.0,
        }
    )

    # Walk the descending schedule at reservoir T.
    liquid_x = composition.copy()
    n_liquid_cumulative = 1.0  # moles of remaining liquid per mole of original feed

    for pressure_pa in descending:
        flash = pt_flash(
            pressure_pa,
            reservoir_temperature_k,
            liquid_x,
            components,
            eos,
            binary_interaction=binary_interaction,
        )
        if flash.phase == "two-phase":
            nv = float(flash.vapor_fraction)
            x_new = np.asarray(flash.liquid_composition, dtype=np.float64)
            y_step = np.asarray(flash.vapor_composition, dtype=np.float64)
        elif flash.phase == "liquid":
            nv = 0.0
            x_new = liquid_x.copy()
            y_step = np.zeros_like(liquid_x)
        else:
            # All-vapor below bubble point would be unphysical; treat defensively
            # as "no remaining liquid" so the walk can surface the issue.
            nv = 1.0
            x_new = np.zeros_like(liquid_x)
            y_step = liquid_x.copy()

        n_gas_step_moles = n_liquid_cumulative * nv
        n_liquid_cumulative_new = n_liquid_cumulative * (1.0 - nv)

        if n_gas_step_moles > 0.0:
            z_gas_res = _compressibility_root(
                eos, pressure_pa, reservoir_temperature_k, y_step, "vapor",
                binary_interaction,
            )
            z_gas_std = _compressibility_root(
                eos, P_std, T_std, y_step, "vapor", binary_interaction,
            )
            v_gas_res = n_gas_step_moles * z_gas_res * R_gas * reservoir_temperature_k / pressure_pa
            v_gas_std = n_gas_step_moles * z_gas_std * R_gas * T_std / P_std
            mw_gas = mixture_molecular_weight(y_step, components)
            gas_gravity = mw_gas / AIR_MOLECULAR_WEIGHT_G_PER_MOL
        else:
            z_gas_res = None
            v_gas_res = 0.0
            v_gas_std = 0.0
            gas_gravity = None

        if n_liquid_cumulative_new > 0.0:
            rho_L = calculate_density(
                pressure_pa,
                reservoir_temperature_k,
                x_new,
                components,
                eos,
                "liquid",
                binary_interaction,
            )
            v_oil_step = n_liquid_cumulative_new / rho_L.molar_density
            oil_density = float(rho_L.mass_density)
        else:
            v_oil_step = 0.0
            oil_density = float("nan")

        step_records.append(
            {
                "phase": "reservoir",
                "pressure_pa": float(pressure_pa),
                "temperature_k": float(reservoir_temperature_k),
                "v_oil_res_per_mole_feed": float(v_oil_step),
                "oil_density_kg_m3": oil_density,
                "liquid_moles_fraction": float(n_liquid_cumulative_new),
                "gas_moles_fraction_this_step": float(n_gas_step_moles),
                "v_gas_res_per_mole_feed": float(v_gas_res),
                "v_gas_std_per_mole_feed": float(v_gas_std),
                "z_gas_at_step": _safe_float(z_gas_res),
                "gas_gravity": _safe_float(gas_gravity),
                "gas_composition": y_step.copy() if n_gas_step_moles > 0 else None,
                "liquid_composition": x_new.copy(),
                "vapor_fraction_in_step": nv,
            }
        )

        liquid_x = x_new
        n_liquid_cumulative = n_liquid_cumulative_new

    # Stock-tank flash at SC_IMPERIAL.
    stock_flash = pt_flash(
        P_std,
        T_std,
        liquid_x,
        components,
        eos,
        binary_interaction=binary_interaction,
    )
    if stock_flash.phase == "two-phase":
        nv_s = float(stock_flash.vapor_fraction)
        x_stock = np.asarray(stock_flash.liquid_composition, dtype=np.float64)
        y_stock = np.asarray(stock_flash.vapor_composition, dtype=np.float64)
    elif stock_flash.phase == "liquid":
        nv_s = 0.0
        x_stock = liquid_x.copy()
        y_stock = np.zeros_like(liquid_x)
    else:
        nv_s = 1.0
        x_stock = np.zeros_like(liquid_x)
        y_stock = liquid_x.copy()

    n_gas_stock_moles = n_liquid_cumulative * nv_s
    n_liquid_stock_moles = n_liquid_cumulative * (1.0 - nv_s)

    if n_gas_stock_moles > 0.0:
        z_gas_stock = _compressibility_root(
            eos, P_std, T_std, y_stock, "vapor", binary_interaction,
        )
        v_gas_stock_std = n_gas_stock_moles * z_gas_stock * R_gas * T_std / P_std
        mw_gas_stock = mixture_molecular_weight(y_stock, components)
        stock_gas_gravity = mw_gas_stock / AIR_MOLECULAR_WEIGHT_G_PER_MOL
    else:
        z_gas_stock = None
        v_gas_stock_std = 0.0
        stock_gas_gravity = None

    if n_liquid_stock_moles > 0.0:
        rho_stock = calculate_density(
            P_std, T_std, x_stock, components, eos, "liquid", binary_interaction,
        )
        v_or = n_liquid_stock_moles / rho_stock.molar_density
        residual_density = float(rho_stock.mass_density)
    else:
        v_or = float("nan")
        residual_density = float("nan")

    step_records.append(
        {
            "phase": "stock_tank",
            "pressure_pa": P_std,
            "temperature_k": T_std,
            "v_oil_res_per_mole_feed": float(v_or),
            "oil_density_kg_m3": residual_density,
            "liquid_moles_fraction": float(n_liquid_stock_moles),
            "gas_moles_fraction_this_step": float(n_gas_stock_moles),
            "v_gas_res_per_mole_feed": float(v_gas_stock_std),
            "v_gas_std_per_mole_feed": float(v_gas_stock_std),
            "z_gas_at_step": _safe_float(z_gas_stock),
            "gas_gravity": _safe_float(stock_gas_gravity),
            "gas_composition": y_stock.copy() if n_gas_stock_moles > 0 else None,
            "liquid_composition": x_stock.copy(),
            "vapor_fraction_in_step": nv_s,
        }
    )

    # Aggregate into DL outputs.
    v_gas_std_by_step = [rec["v_gas_std_per_mole_feed"] for rec in step_records]
    g_total_std = sum(v_gas_std_by_step[1:])  # below Pb down through stock
    if not np.isfinite(v_or) or v_or <= 0.0:
        raise ValueError("Residual oil volume at stock conditions is non-positive.")

    steps_out: list[dict[str, Any]] = []
    bubble_bo = step_records[0]["v_oil_res_per_mole_feed"] / v_or
    rsi = g_total_std / v_or

    # Build cumulative gas_std flowing from Pb downward. cum_std[i] = std gas
    # liberated in steps 1..i (inclusive). RsD at step_i = (G_total - cum_std[i-1]) / V_or
    # for reservoir steps because it represents gas still in solution at P_i which
    # would be released on the path P_i -> stock.
    running_cum = 0.0
    for i, rec in enumerate(step_records):
        v_oil_i = rec["v_oil_res_per_mole_feed"]
        bo = v_oil_i / v_or if v_or > 0 else float("nan")

        if i == 0:
            # Bubble point reference row
            rs = rsi
            bg = None
            btd = bo
            cumulative_released = 0.0
        else:
            # Gas liberated at this step adds to cumulative released from Pb
            running_cum += rec["v_gas_std_per_mole_feed"]
            cumulative_released = running_cum
            # Gas still in solution = total - released_up_to_and_including_this_step
            remaining_std = g_total_std - cumulative_released
            rs = remaining_std / v_or

            # Bg at this step: ratio of gas volume at (P, T_res) to gas volume at std
            # for the same moles of vapor liberated this step. If no gas this step,
            # fall back to None.
            if rec["v_gas_std_per_mole_feed"] > 0.0 and rec["phase"] == "reservoir":
                bg = rec["v_gas_res_per_mole_feed"] / rec["v_gas_std_per_mole_feed"]
            else:
                bg = None

            # BtD = Bo + Bg * (Rsi - RsD)
            if bg is not None and np.isfinite(bg):
                btd = bo + bg * (rsi - rs)
            else:
                btd = bo

        steps_out.append(
            {
                "phase": rec["phase"],
                "pressure_pa": float(rec["pressure_pa"]),
                "pressure_psia": pa_to_psia(rec["pressure_pa"]),
                "temperature_k": float(rec["temperature_k"]),
                "temperature_f": kelvin_to_fahrenheit(rec["temperature_k"]),
                "bo": float(bo),
                "rsd_sm3_sm3": float(rs),
                "rsd_scf_stb": float(rs) * SCF_PER_STB_PER_SM3_PER_SM3,
                "bg": _safe_float(bg),
                "btd": float(btd),
                "vapor_fraction_in_step": float(rec["vapor_fraction_in_step"]),
                "gas_z": rec["z_gas_at_step"],
                "gas_gravity": rec["gas_gravity"],
                "oil_density_kg_m3": _safe_float(rec["oil_density_kg_m3"]),
                "cumulative_gas_std_sm3_per_sm3_residual": float(cumulative_released / v_or),
            }
        )

    # Soft-check validations
    stock_bo = steps_out[-1]["bo"]
    stock_rs = steps_out[-1]["rsd_sm3_sm3"]
    validations = {
        "stock_bo_close_to_one": {
            "value": stock_bo,
            "tolerance": 1e-6,
            "ok": bool(abs(stock_bo - 1.0) <= 1e-6),
        },
        "stock_rs_close_to_zero": {
            "value": stock_rs,
            "tolerance": 1e-6,
            "ok": bool(abs(stock_rs) <= 1e-6),
        },
    }

    return {
        "temperature_k": float(reservoir_temperature_k),
        "temperature_f": kelvin_to_fahrenheit(reservoir_temperature_k),
        "bubble_pressure_pa": float(bubble_pressure_pa),
        "bubble_pressure_psia": pa_to_psia(bubble_pressure_pa),
        "rsdb_sm3_sm3": float(rsi),
        "rsdb_scf_stb": float(rsi) * SCF_PER_STB_PER_SM3_PER_SM3,
        "rsi_sm3_sm3": float(rsi),
        "rsi_scf_stb": float(rsi) * SCF_PER_STB_PER_SM3_PER_SM3,
        "boi": float(bubble_bo),
        "residual_oil_density_kg_m3": residual_density,
        "residual_oil_density_lb_ft3": (
            residual_density * KG_PER_M3_TO_LB_PER_FT3
            if np.isfinite(residual_density)
            else None
        ),
        "converged": True,
        "steps": steps_out,
        "validations": validations,
    }


def _serialize_envelope(envelope: Any, assignment_T_k: float) -> dict[str, Any]:
    bub_T = np.asarray(envelope.bubble_T, dtype=float)
    bub_P = np.asarray(envelope.bubble_P, dtype=float)
    dew_T = np.asarray(envelope.dew_T, dtype=float)
    dew_P = np.asarray(envelope.dew_P, dtype=float)

    def _rows(Ts: np.ndarray, Ps: np.ndarray) -> list[dict[str, float]]:
        return [
            {
                "temperature_k": float(T),
                "temperature_f": kelvin_to_fahrenheit(float(T)),
                "pressure_pa": float(P),
                "pressure_psia": pa_to_psia(float(P)),
            }
            for T, P in zip(Ts, Ps)
        ]

    pb_from_env_psia: float | None = None
    if bub_T.size >= 2:
        order = np.argsort(bub_T)
        Ts_sorted = bub_T[order]
        Ps_sorted = bub_P[order]
        if Ts_sorted[0] <= assignment_T_k <= Ts_sorted[-1]:
            pb_from_env_psia = pa_to_psia(
                float(np.interp(assignment_T_k, Ts_sorted, Ps_sorted))
            )

    crit = None
    if envelope.critical_T is not None and envelope.critical_P is not None:
        crit = {
            "temperature_k": float(envelope.critical_T),
            "temperature_f": kelvin_to_fahrenheit(float(envelope.critical_T)),
            "pressure_pa": float(envelope.critical_P),
            "pressure_psia": pa_to_psia(float(envelope.critical_P)),
        }

    return {
        "available": True,
        "converged": bool(envelope.converged),
        "critical_point": crit,
        "bubble_points": _rows(bub_T, bub_P),
        "dew_points": _rows(dew_T, dew_P),
        "bubble_pressure_at_assignment_T_psia": pb_from_env_psia,
    }
def run_assignment_case(
    *,
    case_path: str | Path | None = None,
    initials: str | None = None,
    temperature_f: float | None = None,
) -> dict[str, Any]:
    """Run the PETE 665 assignment baseline at the selected temperature."""
    case = load_assignment_case(case_path)
    selected_temperature_f, selected_initials = resolve_assignment_temperature_f(
        case,
        initials=initials,
        temperature_f=temperature_f,
    )
    selected_temperature_k = fahrenheit_to_kelvin(selected_temperature_f)

    component_ids, components, composition = build_assignment_fluid(case)
    eos = PR78EOS(components)
    binary_interaction = np.zeros((len(components), len(components)), dtype=float)

    bubble_result = calculate_bubble_point(
        temperature=selected_temperature_k,
        composition=composition,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
    )

    cce_start_psia, cce_end_psia, cce_n_steps = _require_linear_pressure_grid(
        case.cce_pressures_psia,
        "CCE",
    )
    cce_result = simulate_cce(
        composition=composition,
        temperature=selected_temperature_k,
        components=components,
        eos=eos,
        pressure_start=psia_to_pa(cce_start_psia),
        pressure_end=psia_to_pa(cce_end_psia),
        n_steps=cce_n_steps,
        binary_interaction=binary_interaction,
        saturation_pressure=float(bubble_result.pressure),
    )

    dl_payload = _run_assignment_differential_liberation(
        composition=composition,
        reservoir_temperature_k=selected_temperature_k,
        bubble_pressure_pa=float(bubble_result.pressure),
        reporting_pressures_pa=tuple(
            psia_to_pa(value) for value in case.dl_pressures_psia
        ),
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
    )

    envelope_payload: dict[str, Any]
    try:
        envelope = calculate_phase_envelope(
            composition,
            components,
            eos,
            binary_interaction=binary_interaction,
            T_start=200.0,
            max_points=200,
        )
        envelope_payload = _serialize_envelope(envelope, selected_temperature_k)
    except Exception as exc:  # noqa: BLE001 — envelope must never break the run
        envelope_payload = {"available": False, "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "assignment": case.name,
        "source_document": case.source_document,
        "selected_initials": selected_initials,
        "selected_temperature_f": selected_temperature_f,
        "selected_temperature_k": selected_temperature_k,
        "assumptions": [
            "Runtime EOS is Peng-Robinson (1978) via pvtcore.eos.pr78.PR78EOS.",
            "Binary interaction parameters are forced to zero for the assignment baseline.",
            "PSEUDO_PLUS Tb is back-calculated from Tc/Pc/omega using inverse Edmister only to satisfy the current Component contract.",
            "PSEUDO_PLUS Vc is estimated with Zc = 0.27 only to satisfy the current Component contract.",
            "Differential liberation uses a proper DL-to-stock-tank schedule; Bo and RsD reference the residual oil volume at 60 F, 14.696 psia.",
        ],
        "fluid": {
            "component_ids": component_ids,
            "composition": {
                component_id: float(composition[i])
                for i, component_id in enumerate(component_ids)
            }
        },
        "saturation_pressure": _serialize_bubble_result(component_ids, bubble_result),
        "cce": _serialize_cce_result(cce_result),
        "dl": dl_payload,
        "envelope": envelope_payload,
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the PETE 665 assignment baseline case.",
    )
    parser.add_argument(
        "--case",
        type=Path,
        default=default_assignment_case_path(),
        help="Path to the assignment case JSON file.",
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument(
        "--initials",
        help="Initials key from the assignment document temperature list.",
    )
    selector.add_argument(
        "--temperature-f",
        type=float,
        help="Explicit assignment temperature in Fahrenheit.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path for a JSON result artifact.",
    )
    parser.add_argument(
        "--plot-dir",
        type=Path,
        help="Optional directory for PNG plots (CCE, DL, envelope).",
    )
    return parser


def _plot_prefix(result: dict[str, Any]) -> str:
    initials = result.get("selected_initials")
    return f"{initials.lower()}_" if initials else "pete665_"


def _write_assignment_plots(result: dict[str, Any], plot_dir: Path) -> list[Path]:
    """Render the assignment plots to ``plot_dir`` and return the written paths."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as exc:  # noqa: BLE001 — matplotlib is optional at runtime
        print(f"warning: matplotlib unavailable, skipping plots ({exc})")
        return []

    plot_dir.mkdir(parents=True, exist_ok=True)
    prefix = _plot_prefix(result)
    written: list[Path] = []

    def _save(fig, name: str) -> None:
        path = plot_dir / f"{prefix}{name}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        written.append(path)

    title_T = (
        f"{result['selected_temperature_f']:.1f} F"
        if result.get("selected_temperature_f") is not None
        else ""
    )

    # CCE plots
    cce_steps = result.get("cce", {}).get("steps", [])
    if cce_steps:
        psat = result["cce"].get("saturation_pressure_psia")
        P = [s["pressure_psia"] for s in cce_steps]
        V = [s["relative_volume"] for s in cce_steps]
        rho = [s.get("oil_density_kg_m3") for s in cce_steps]
        Z = [s.get("z_factor") for s in cce_steps]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, V, "o-")
        if psat is not None:
            ax.axvline(psat, linestyle="--", color="grey", alpha=0.7, label=f"Psat ≈ {psat:.0f} psia")
            ax.legend()
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("Relative volume V/Vsat")
        ax.set_title(f"CCE relative volume — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "cce_relative_volume")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, rho, "o-", color="tab:red")
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("Oil density ρo (kg/m³)")
        ax.set_title(f"CCE oil density — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "cce_oil_density")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, Z, "o-", color="tab:green")
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("Z factor")
        ax.set_title(f"CCE Z-factor — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "cce_z_factor")

    # DL plots — exclude the stock-tank step from curves (reference-only row)
    dl_steps = result.get("dl", {}).get("steps", [])
    dl_curve = [s for s in dl_steps if s.get("phase") != "stock_tank"]
    if dl_curve:
        P = [s["pressure_psia"] for s in dl_curve]
        Bo = [s["bo"] for s in dl_curve]
        Rs = [s["rsd_scf_stb"] for s in dl_curve]
        Bg = [s.get("bg") for s in dl_curve]
        Bt = [s["btd"] for s in dl_curve]
        pb = result["dl"].get("bubble_pressure_psia")
        rsi_scf = result["dl"].get("rsdb_scf_stb")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, Bo, "o-", color="tab:blue")
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("Bo (res bbl / STB)")
        ax.set_title(f"DL oil FVF — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "dl_bo")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, Rs, "o-", color="tab:orange")
        if rsi_scf is not None:
            ax.axhline(rsi_scf, linestyle="--", color="grey", alpha=0.7, label=f"RsDb = {rsi_scf:.0f} scf/STB")
            ax.legend()
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("RsD (scf/STB)")
        ax.set_title(f"DL solution GOR — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "dl_rs")

        if any(b is not None for b in Bg):
            fig, ax = plt.subplots(figsize=(6, 4))
            P_bg = [p for p, b in zip(P, Bg) if b is not None]
            Bg_plot = [b for b in Bg if b is not None]
            ax.plot(P_bg, Bg_plot, "o-", color="tab:purple")
            ax.set_xlabel("Pressure (psia)")
            ax.set_ylabel("Bg (res ft³ / scf)")
            ax.set_title(f"DL gas FVF — {title_T}")
            ax.grid(True, alpha=0.3)
            _save(fig, "dl_bg")

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(P, Bt, "o-", color="tab:green")
        if pb is not None:
            ax.axvline(pb, linestyle="--", color="grey", alpha=0.7, label=f"Pb ≈ {pb:.0f} psia")
            ax.legend()
        ax.set_xlabel("Pressure (psia)")
        ax.set_ylabel("BtD (res bbl / STB)")
        ax.set_title(f"DL total FVF — {title_T}")
        ax.grid(True, alpha=0.3)
        _save(fig, "dl_bt")

    # Phase envelope
    env = result.get("envelope", {})
    if env.get("available") and (env.get("bubble_points") or env.get("dew_points")):
        fig, ax = plt.subplots(figsize=(7, 5))
        bub = env.get("bubble_points", [])
        dew = env.get("dew_points", [])
        if bub:
            ax.plot([p["temperature_f"] for p in bub], [p["pressure_psia"] for p in bub],
                    "-", color="tab:blue", label="Bubble")
        if dew:
            ax.plot([p["temperature_f"] for p in dew], [p["pressure_psia"] for p in dew],
                    "-", color="tab:red", label="Dew")
        crit = env.get("critical_point")
        if crit:
            ax.plot(crit["temperature_f"], crit["pressure_psia"], "k*", markersize=12,
                    label="Critical")
        T_assign = result.get("selected_temperature_f")
        Pb_assign = result.get("saturation_pressure", {}).get("pressure_psia")
        if T_assign is not None and Pb_assign is not None:
            ax.plot(T_assign, Pb_assign, "go", markersize=9,
                    label=f"Assignment (T={T_assign:.1f} F, Pb={Pb_assign:.0f} psia)")
        ax.set_xlabel("Temperature (F)")
        ax.set_ylabel("Pressure (psia)")
        ax.set_title("Phase envelope — PR78, BIP=0")
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
        _save(fig, "envelope")

    return written


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the PETE 665 assignment runner."""
    parser = _build_argument_parser()
    args = parser.parse_args(argv)

    result = run_assignment_case(
        case_path=args.case,
        initials=args.initials,
        temperature_f=args.temperature_f,
    )

    rendered = json.dumps(result, indent=2, sort_keys=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote assignment results to {args.output}")
    else:
        print(rendered)

    if args.plot_dir is not None:
        written = _write_assignment_plots(result, args.plot_dir)
        for path in written:
            print(f"Wrote plot {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
