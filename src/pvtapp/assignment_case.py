"""Desktop-app assignment preset helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pvtapp.schemas import (
    CCEConfig,
    DLConfig,
    ComponentEntry,
    EOSType,
    FluidComposition,
    InlineComponentSpec as AppInlineComponentSpec,
    SaturationPointConfig,
)
from pvtcore.eos import PR78EOS
from pvtcore.flash import calculate_bubble_point
from pvtcore.validation.pete665_assignment import (
    AssignmentCase,
    build_assignment_fluid,
    fahrenheit_to_kelvin,
    load_assignment_case,
    psia_to_pa,
    resolve_assignment_temperature_f,
)


@dataclass(frozen=True)
class AssignmentDesktopPreset:
    """Resolved desktop preset for the PETE 665 assignment case."""

    case: AssignmentCase
    eos_type: EOSType
    selected_initials: str | None
    temperature_f: float
    temperature_k: float
    composition: FluidComposition
    bubble_point_config: SaturationPointConfig
    dew_point_config: SaturationPointConfig
    cce_config: CCEConfig
    dl_config: DLConfig
    bubble_pressure_pa: float


def build_assignment_desktop_preset(
    *,
    case_path: str | Path | None = None,
    initials: str | None = None,
    temperature_f: float | None = None,
) -> AssignmentDesktopPreset:
    """Build a desktop-app preset from the repo-local assignment case."""
    case = load_assignment_case(case_path)
    selected_temperature_f, selected_initials = resolve_assignment_temperature_f(
        case,
        initials=initials,
        temperature_f=temperature_f,
    )
    selected_temperature_k = fahrenheit_to_kelvin(selected_temperature_f)

    composition = FluidComposition(
        components=[
            ComponentEntry(component_id=component_id, mole_fraction=mole_fraction)
            for component_id, mole_fraction in case.composition_rows
        ],
        inline_components=[
            AppInlineComponentSpec(
                component_id=spec.component_id,
                name=spec.name,
                formula=spec.formula,
                molecular_weight_g_per_mol=spec.molecular_weight_g_per_mol,
                critical_temperature_k=spec.critical_temperature_k,
                critical_pressure_pa=spec.critical_pressure_pa,
                omega=spec.omega,
            )
            for spec in case.inline_components.values()
        ],
    )

    _component_ids, components, composition_array = build_assignment_fluid(case)
    eos = PR78EOS(components)
    binary_interaction = np.zeros((len(components), len(components)), dtype=float)
    bubble_result = calculate_bubble_point(
        temperature=selected_temperature_k,
        composition=composition_array,
        components=components,
        eos=eos,
        binary_interaction=binary_interaction,
    )
    bubble_pressure_pa = float(bubble_result.pressure)

    return AssignmentDesktopPreset(
        case=case,
        eos_type=EOSType.PR78,
        selected_initials=selected_initials,
        temperature_f=selected_temperature_f,
        temperature_k=selected_temperature_k,
        composition=composition,
        bubble_point_config=SaturationPointConfig(
            temperature_k=selected_temperature_k,
            pressure_initial_pa=bubble_pressure_pa,
        ),
        dew_point_config=SaturationPointConfig(
            temperature_k=selected_temperature_k,
        ),
        cce_config=CCEConfig(
            temperature_k=selected_temperature_k,
            pressure_points_pa=[psia_to_pa(value) for value in case.cce_pressures_psia],
        ),
        dl_config=DLConfig(
            temperature_k=selected_temperature_k,
            bubble_pressure_pa=bubble_pressure_pa,
            pressure_points_pa=[psia_to_pa(value) for value in case.dl_pressures_psia],
        ),
        bubble_pressure_pa=bubble_pressure_pa,
    )
