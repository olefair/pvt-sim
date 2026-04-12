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
from pvtcore.eos import PengRobinsonEOS
from pvtcore.experiments import simulate_cce, simulate_dl
from pvtcore.flash import calculate_bubble_point
from pvtcore.models import Component, get_components_cached, resolve_component_id


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


def _serialize_cce_result(result: Any) -> dict[str, Any]:
    steps = []
    for step in result.steps:
        steps.append(
            {
                "pressure_pa": float(step.pressure),
                "pressure_psia": pa_to_psia(step.pressure),
                "relative_volume": float(step.relative_volume),
                "liquid_fraction": _safe_float(step.liquid_volume_fraction),
                "vapor_fraction": _safe_float(step.vapor_fraction),
                "z_factor": _safe_float(step.compressibility_Z),
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


def _gas_volume_at_standard_conditions(
    gas_composition: np.ndarray,
    n_moles: float,
    components: list[Component],
    eos: PengRobinsonEOS,
    binary_interaction: np.ndarray,
) -> float:
    z_std = eos.compressibility(
        SC_IMPERIAL.P,
        SC_IMPERIAL.T,
        gas_composition,
        phase="vapor",
        binary_interaction=binary_interaction,
    )
    if isinstance(z_std, (list, tuple, np.ndarray)):
        z_std = z_std[-1]
    return float(n_moles) * float(z_std) * R.Pa_m3_per_mol_K * SC_IMPERIAL.T / SC_IMPERIAL.P


def _serialize_dl_result(
    result: Any,
    *,
    components: list[Component],
    eos: PengRobinsonEOS,
    binary_interaction: np.ndarray,
) -> dict[str, Any]:
    steps = []
    previous_liquid_moles = 1.0

    for index, step in enumerate(result.steps):
        if index == 0:
            previous_liquid_moles = float(step.liquid_moles_remaining)
            continue

        bg = None
        if step.vapor_fraction > 0.0 and np.isfinite(step.gas_Z):
            n_gas = float(previous_liquid_moles) * float(step.vapor_fraction)
            v_gas_at_reservoir = (
                n_gas
                * float(step.gas_Z)
                * R.Pa_m3_per_mol_K
                * float(step.temperature)
                / float(step.pressure)
            )
            v_gas_at_standard = _gas_volume_at_standard_conditions(
                step.gas_composition,
                n_gas,
                components,
                eos,
                binary_interaction,
            )
            if v_gas_at_standard > 0.0:
                bg = v_gas_at_reservoir / v_gas_at_standard

        steps.append(
            {
                "pressure_pa": float(step.pressure),
                "pressure_psia": pa_to_psia(step.pressure),
                "rsd_sm3_sm3": float(step.Rs),
                "rsd_scf_stb": float(step.Rs) * SCF_PER_STB_PER_SM3_PER_SM3,
                "rsdb_sm3_sm3": float(result.Rsi),
                "rsdb_scf_stb": float(result.Rsi) * SCF_PER_STB_PER_SM3_PER_SM3,
                "bo": float(step.Bo),
                "bg": _safe_float(bg),
                "btd": float(step.Bt),
                "vapor_fraction": float(step.vapor_fraction),
                "gas_z": _safe_float(step.gas_Z),
                "gas_gravity": _safe_float(step.gas_gravity),
                "cumulative_gas_sm3_sm3": float(step.cumulative_gas),
            }
        )
        previous_liquid_moles = float(step.liquid_moles_remaining)

    return {
        "temperature_k": float(result.temperature),
        "temperature_f": kelvin_to_fahrenheit(result.temperature),
        "bubble_pressure_pa": float(result.bubble_pressure),
        "bubble_pressure_psia": pa_to_psia(result.bubble_pressure),
        "rsi_sm3_sm3": float(result.Rsi),
        "rsi_scf_stb": float(result.Rsi) * SCF_PER_STB_PER_SM3_PER_SM3,
        "boi": float(result.Boi),
        "converged": bool(result.converged),
        "steps": steps,
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
    eos = PengRobinsonEOS(components)
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

    dl_result = simulate_dl(
        composition=composition,
        temperature=selected_temperature_k,
        components=components,
        eos=eos,
        bubble_pressure=float(bubble_result.pressure),
        pressure_steps=np.asarray(
            [psia_to_pa(value) for value in case.dl_pressures_psia],
            dtype=np.float64,
        ),
        binary_interaction=binary_interaction,
    )

    return {
        "assignment": case.name,
        "source_document": case.source_document,
        "selected_initials": selected_initials,
        "selected_temperature_f": selected_temperature_f,
        "selected_temperature_k": selected_temperature_k,
        "assumptions": [
            "Runtime EOS is the current Peng-Robinson implementation in pvtcore.",
            "Binary interaction parameters are forced to zero for the assignment baseline.",
            "PSEUDO_PLUS Tb is back-calculated from Tc/Pc/omega using inverse Edmister only to satisfy the current Component contract.",
            "PSEUDO_PLUS Vc is estimated with Zc = 0.27 only to satisfy the current Component contract."
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
        "dl": _serialize_dl_result(
            dl_result,
            components=components,
            eos=eos,
            binary_interaction=binary_interaction,
        ),
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
    return parser


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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
