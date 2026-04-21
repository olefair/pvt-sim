"""Resolution helpers for plus-fraction characterization policy.

This module centralizes the app/runtime policy for lab-style ``C1-C6 + C7+``
feeds. The goal is to avoid silent generic defaults by resolving every
plus-fraction input into an explicit, auditable characterization profile before
the thermo runtime executes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from pvtcore.models import resolve_component_id

from pvtapp.schemas import (
    CalculationType,
    ComponentEntry,
    PlusFractionCharacterizationPreset,
    PlusFractionEntry,
)


@dataclass(frozen=True)
class PlusFractionPresetSettings:
    """Concrete characterization settings for a validated family preset."""

    split_method: str
    split_mw_model: str
    max_carbon_number: int
    lumping_enabled: bool
    lumping_n_groups: int
    lumping_method: str


PLUS_FRACTION_PRESET_LABELS: Mapping[PlusFractionCharacterizationPreset, str] = {
    PlusFractionCharacterizationPreset.AUTO: "Auto",
    PlusFractionCharacterizationPreset.MANUAL: "Manual",
    PlusFractionCharacterizationPreset.DRY_GAS: "Dry Gas",
    PlusFractionCharacterizationPreset.CO2_RICH_GAS: "CO2-Rich / Acid Gas",
    PlusFractionCharacterizationPreset.GAS_CONDENSATE: "Gas Condensate",
    PlusFractionCharacterizationPreset.VOLATILE_OIL: "Volatile Oil",
    PlusFractionCharacterizationPreset.BLACK_OIL: "Black Oil",
    PlusFractionCharacterizationPreset.SOUR_OIL: "Sour Oil",
}


PLUS_FRACTION_PRESET_SETTINGS: Mapping[
    PlusFractionCharacterizationPreset,
    PlusFractionPresetSettings,
] = {
    PlusFractionCharacterizationPreset.DRY_GAS: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=11,
        lumping_enabled=True,
        lumping_n_groups=4,
        lumping_method="contiguous",
    ),
    PlusFractionCharacterizationPreset.CO2_RICH_GAS: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="paraffin",
        max_carbon_number=11,
        lumping_enabled=True,
        lumping_n_groups=4,
        lumping_method="contiguous",
    ),
    PlusFractionCharacterizationPreset.GAS_CONDENSATE: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="paraffin",
        max_carbon_number=18,
        lumping_enabled=True,
        lumping_n_groups=2,
        lumping_method="contiguous",
    ),
    PlusFractionCharacterizationPreset.VOLATILE_OIL: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_enabled=True,
        lumping_n_groups=6,
        lumping_method="contiguous",
    ),
    PlusFractionCharacterizationPreset.BLACK_OIL: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_enabled=True,
        lumping_n_groups=6,
        lumping_method="contiguous",
    ),
    PlusFractionCharacterizationPreset.SOUR_OIL: PlusFractionPresetSettings(
        split_method="pedersen",
        split_mw_model="table",
        max_carbon_number=20,
        lumping_enabled=True,
        lumping_n_groups=6,
        lumping_method="contiguous",
    ),
}


_C2_TO_C6_IDS = ("C2", "C3", "IC4", "C4", "IC5", "C5", "C6")
_GAS_FAMILY_CALC_TYPES = {
    CalculationType.DEW_POINT,
    CalculationType.CVD,
}
_OIL_FAMILY_CALC_TYPES = {
    CalculationType.BUBBLE_POINT,
    CalculationType.CCE,
    CalculationType.DL,
}


def _canonical_component_fractions(
    components: Sequence[ComponentEntry] | Iterable[tuple[str, float]],
) -> dict[str, float]:
    """Resolve raw component IDs into canonical IDs and accumulate fractions."""

    fractions: dict[str, float] = {}
    for item in components:
        if isinstance(item, ComponentEntry):
            raw_id = item.component_id
            z = item.mole_fraction
        else:
            raw_id, z = item
        canonical_id = resolve_component_id(raw_id).upper()
        fractions[canonical_id] = fractions.get(canonical_id, 0.0) + float(z)
    return fractions


def _is_gas_like_feed(
    *,
    calculation_type: CalculationType,
    methane: float,
    acid_gas: float,
    plus_fraction_z: float,
) -> bool:
    """Classify the feed broadly as gas-like or oil-like for auto inference."""

    if calculation_type in _GAS_FAMILY_CALC_TYPES:
        return True
    if calculation_type in _OIL_FAMILY_CALC_TYPES:
        return False

    if plus_fraction_z > 0.12:
        return False
    return methane >= 0.55 or (methane + acid_gas) >= 0.70


def infer_plus_fraction_preset(
    components: Sequence[ComponentEntry] | Iterable[tuple[str, float]],
    plus_fraction: PlusFractionEntry,
    calculation_type: CalculationType,
) -> PlusFractionCharacterizationPreset:
    """Infer a validated family preset from the feed and workflow."""

    fractions = _canonical_component_fractions(components)
    methane = fractions.get("C1", 0.0)
    co2 = fractions.get("CO2", 0.0)
    h2s = fractions.get("H2S", 0.0)
    acid = co2 + h2s
    c2_to_c6 = sum(fractions.get(component_id, 0.0) for component_id in _C2_TO_C6_IDS)
    plus_z = float(plus_fraction.z_plus)

    if _is_gas_like_feed(
        calculation_type=calculation_type,
        methane=methane,
        acid_gas=acid,
        plus_fraction_z=plus_z,
    ):
        if acid >= 0.20:
            return PlusFractionCharacterizationPreset.CO2_RICH_GAS
        if plus_z >= 0.035 or c2_to_c6 >= 0.20:
            return PlusFractionCharacterizationPreset.GAS_CONDENSATE
        return PlusFractionCharacterizationPreset.DRY_GAS

    if h2s >= 0.05 or acid >= 0.10:
        return PlusFractionCharacterizationPreset.SOUR_OIL
    if methane >= 0.25:
        return PlusFractionCharacterizationPreset.VOLATILE_OIL
    return PlusFractionCharacterizationPreset.BLACK_OIL


def resolve_plus_fraction_entry(
    components: Sequence[ComponentEntry] | Iterable[tuple[str, float]],
    plus_fraction: PlusFractionEntry,
    calculation_type: CalculationType,
) -> PlusFractionEntry:
    """Resolve a plus-fraction entry into concrete characterization settings."""

    requested = plus_fraction.characterization_preset
    if requested is PlusFractionCharacterizationPreset.MANUAL:
        payload = plus_fraction.model_dump(mode="python")
        payload["resolved_characterization_preset"] = None
        return PlusFractionEntry.model_validate(payload)

    resolved_preset = (
        infer_plus_fraction_preset(components, plus_fraction, calculation_type)
        if requested is PlusFractionCharacterizationPreset.AUTO
        else requested
    )
    settings = PLUS_FRACTION_PRESET_SETTINGS[resolved_preset]
    payload = plus_fraction.model_dump(mode="python")
    payload.update(
        {
            "split_method": settings.split_method,
            "split_mw_model": settings.split_mw_model,
            "max_carbon_number": settings.max_carbon_number,
            "lumping_enabled": settings.lumping_enabled,
            "lumping_n_groups": settings.lumping_n_groups,
            "lumping_method": settings.lumping_method,
            "resolved_characterization_preset": resolved_preset,
        }
    )
    return PlusFractionEntry.model_validate(payload)


def describe_plus_fraction_policy(
    plus_fraction: PlusFractionEntry,
) -> str:
    """Return a compact human-readable description of the resolved policy."""

    requested = PLUS_FRACTION_PRESET_LABELS[plus_fraction.characterization_preset]
    resolved = plus_fraction.resolved_characterization_preset
    if plus_fraction.characterization_preset is PlusFractionCharacterizationPreset.MANUAL:
        prefix = "Manual"
    elif resolved is None:
        prefix = requested
    elif resolved is plus_fraction.characterization_preset:
        prefix = requested
    else:
        prefix = f"{requested} -> {PLUS_FRACTION_PRESET_LABELS[resolved]}"

    lumping_txt = "off"
    if plus_fraction.lumping_enabled:
        lumping_txt = f"on ({plus_fraction.lumping_n_groups} groups)"

    description = (
        f"{prefix}; split method {plus_fraction.split_method}, "
        f"split MW model {plus_fraction.split_mw_model}, "
        f"split to C{plus_fraction.max_carbon_number}, lumping {lumping_txt}"
    )
    if plus_fraction.lumping_enabled:
        description += f", lumping method {plus_fraction.lumping_method}"
    if plus_fraction.split_method == "pedersen":
        description += f", Pedersen A/B from {plus_fraction.pedersen_solve_ab_from}"
        if plus_fraction.tbp_cuts:
            description += f" using {len(plus_fraction.tbp_cuts)} TBP cuts"
    return description
