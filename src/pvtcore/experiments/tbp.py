"""Standalone true boiling point (TBP) assay kernel.

This phase-1 module accepts cut-resolved TBP data and produces a standalone
assay summary. The kernel intentionally stays inside the repo's current
verified contract: contiguous one-carbon cuts with `name`, `z`, and `mw`.
It does not invent temperature-endpoint fitting or GUI exposure.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ValidationError


@dataclass(frozen=True)
class TBPAssayCut:
    """Single TBP cut accepted by the standalone assay kernel."""

    name: str
    carbon_number: int
    mole_fraction: float
    molecular_weight_g_per_mol: float
    specific_gravity: float | None = None


@dataclass(frozen=True)
class TBPCutResult:
    """Derived cut-level result on both mole and mass assay bases."""

    name: str
    carbon_number: int
    mole_fraction: float
    normalized_mole_fraction: float
    cumulative_mole_fraction: float
    molecular_weight_g_per_mol: float
    normalized_mass_fraction: float
    cumulative_mass_fraction: float
    specific_gravity: float | None = None


@dataclass(frozen=True)
class TBPResult:
    """Standalone TBP assay summary."""

    cut_start: int
    cut_end: int
    cuts: tuple[TBPCutResult, ...]
    z_plus: float
    mw_plus_g_per_mol: float
    carbon_numbers: NDArray[np.int64]
    normalized_mole_fractions: NDArray[np.float64]
    cumulative_mole_fractions: NDArray[np.float64]
    normalized_mass_fractions: NDArray[np.float64]
    cumulative_mass_fractions: NDArray[np.float64]

    @property
    def cut_names(self) -> tuple[str, ...]:
        return tuple(cut.name for cut in self.cuts)

    @property
    def cumulative_mole_percent(self) -> NDArray[np.float64]:
        return self.cumulative_mole_fractions * 100.0

    @property
    def cumulative_mass_percent(self) -> NDArray[np.float64]:
        return self.cumulative_mass_fractions * 100.0


def simulate_tbp(
    cuts: Sequence[object],
    *,
    cut_start: int | None = None,
) -> TBPResult:
    """Build a standalone TBP assay summary from cut-resolved input.

    Parameters
    ----------
    cuts : sequence
        Ordered TBP cuts. Each item may be a mapping with `name`, `z`, and
        `mw` keys or an object exposing equivalent attributes. Optional cut
        specific gravity may be provided as `sg` or `specific_gravity`.
    cut_start : int, optional
        Expected first carbon number in the sequence. When omitted, the first
        cut defines the assay start.

    Returns
    -------
    TBPResult
        Cut-resolved cumulative mole- and mass-yield curves plus derived
        `z_plus` and `mw_plus_g_per_mol`.

    Notes
    -----
    The repo's current TBP contract does not include boiling-point or
    temperature-endpoint fields. This function therefore returns a cut-based
    assay summary rather than a temperature-based distillation curve.
    """
    if isinstance(cuts, (str, bytes, bytearray)):
        raise ValidationError(
            "TBP cuts must be provided as a sequence of cut definitions.",
            parameter="cuts",
            value=type(cuts).__name__,
        )

    cut_items = tuple(cuts)
    if len(cut_items) == 0:
        raise ValidationError(
            "TBP cuts must be a non-empty list.",
            parameter="cuts",
        )

    assay_cuts = tuple(_coerce_cut(cut_obj, index=index) for index, cut_obj in enumerate(cut_items))
    expected_cut_start = assay_cuts[0].carbon_number if cut_start is None else _as_positive_int(cut_start, "cut_start")
    _validate_cut_sequence(assay_cuts, cut_start=expected_cut_start)

    z_plus = float(sum(cut.mole_fraction for cut in assay_cuts))
    mole_fractions = np.asarray([cut.mole_fraction for cut in assay_cuts], dtype=np.float64)
    normalized_mole_fractions = mole_fractions / z_plus
    cumulative_mole_fractions = np.cumsum(normalized_mole_fractions)

    raw_mass_basis = np.asarray(
        [cut.mole_fraction * cut.molecular_weight_g_per_mol for cut in assay_cuts],
        dtype=np.float64,
    )
    total_mass_basis = float(raw_mass_basis.sum())
    if not isfinite(total_mass_basis) or total_mass_basis <= 0.0:
        raise ValidationError(
            "TBP cuts must sum to a positive assay mass basis.",
            parameter="cuts",
            value=total_mass_basis,
        )
    normalized_mass_fractions = raw_mass_basis / total_mass_basis
    cumulative_mass_fractions = np.cumsum(normalized_mass_fractions)

    cut_results = tuple(
        TBPCutResult(
            name=cut.name,
            carbon_number=cut.carbon_number,
            mole_fraction=cut.mole_fraction,
            normalized_mole_fraction=float(normalized_mole_fractions[index]),
            cumulative_mole_fraction=float(cumulative_mole_fractions[index]),
            molecular_weight_g_per_mol=cut.molecular_weight_g_per_mol,
            normalized_mass_fraction=float(normalized_mass_fractions[index]),
            cumulative_mass_fraction=float(cumulative_mass_fractions[index]),
            specific_gravity=cut.specific_gravity,
        )
        for index, cut in enumerate(assay_cuts)
    )

    return TBPResult(
        cut_start=expected_cut_start,
        cut_end=assay_cuts[-1].carbon_number,
        cuts=cut_results,
        z_plus=z_plus,
        mw_plus_g_per_mol=float(total_mass_basis / z_plus),
        carbon_numbers=np.asarray([cut.carbon_number for cut in assay_cuts], dtype=np.int64),
        normalized_mole_fractions=normalized_mole_fractions,
        cumulative_mole_fractions=cumulative_mole_fractions,
        normalized_mass_fractions=normalized_mass_fractions,
        cumulative_mass_fractions=cumulative_mass_fractions,
    )


def _coerce_cut(cut_obj: object, *, index: int) -> TBPAssayCut:
    prefix = f"cuts[{index}]"

    if isinstance(cut_obj, Mapping):
        name = _as_non_empty_str(_get_required_mapping_value(cut_obj, "name", prefix), f"{prefix}.name")
        carbon_number_value = cut_obj.get("carbon_number")
        mole_fraction_value, mole_fraction_parameter = _get_required_alias(
            cut_obj,
            prefix,
            aliases=(("z", f"{prefix}.z"), ("mole_fraction", f"{prefix}.mole_fraction")),
        )
        molecular_weight_value, molecular_weight_parameter = _get_required_alias(
            cut_obj,
            prefix,
            aliases=(("mw", f"{prefix}.mw"), ("molecular_weight_g_per_mol", f"{prefix}.molecular_weight_g_per_mol")),
        )
        specific_gravity_value = _get_optional_alias(cut_obj, "sg", "specific_gravity")
    else:
        name = _as_non_empty_str(_get_required_object_attr(cut_obj, "name", prefix), f"{prefix}.name")
        carbon_number_value = _get_optional_object_attr(cut_obj, "carbon_number")
        mole_fraction_value, mole_fraction_parameter = _get_required_object_alias(
            cut_obj,
            prefix,
            aliases=(("z", f"{prefix}.z"), ("mole_fraction", f"{prefix}.mole_fraction")),
        )
        molecular_weight_value, molecular_weight_parameter = _get_required_object_alias(
            cut_obj,
            prefix,
            aliases=(("mw", f"{prefix}.mw"), ("molecular_weight_g_per_mol", f"{prefix}.molecular_weight_g_per_mol")),
        )
        specific_gravity_value = _get_optional_object_attr(cut_obj, "sg", "specific_gravity")

    parsed_carbon_number = _parse_tbp_cut_name(name, f"{prefix}.name")
    if carbon_number_value is None:
        carbon_number = parsed_carbon_number
    else:
        carbon_number = _as_positive_int(carbon_number_value, f"{prefix}.carbon_number")
        if carbon_number != parsed_carbon_number:
            raise ValidationError(
                "TBP cut carbon_number must match the numeric suffix in name.",
                parameter=f"{prefix}.carbon_number",
                value=carbon_number,
            )

    mole_fraction = _as_positive_float(
        mole_fraction_value,
        mole_fraction_parameter,
        "TBP cut mole fraction must be positive.",
    )
    molecular_weight = _as_positive_float(
        molecular_weight_value,
        molecular_weight_parameter,
        "TBP cut molecular weight must be positive.",
    )

    specific_gravity: float | None = None
    if specific_gravity_value is not None:
        specific_gravity = _as_positive_float(
            specific_gravity_value,
            f"{prefix}.specific_gravity",
            "TBP cut specific gravity must be positive when provided.",
        )

    return TBPAssayCut(
        name=name,
        carbon_number=carbon_number,
        mole_fraction=mole_fraction,
        molecular_weight_g_per_mol=molecular_weight,
        specific_gravity=specific_gravity,
    )


def _validate_cut_sequence(cuts: Sequence[TBPAssayCut], *, cut_start: int) -> None:
    seen_names: set[str] = set()
    previous_carbon_number: int | None = None

    for index, cut in enumerate(cuts):
        parameter = f"cuts[{index}].name"
        if cut.name in seen_names:
            raise ValidationError(
                "TBP cut names must be unique.",
                parameter=parameter,
                value=cut.name,
            )
        if cut.carbon_number < cut_start:
            raise ValidationError(
                "TBP cuts must not start below cut_start.",
                parameter=parameter,
                value=cut.name,
                cut_start=cut_start,
            )
        if previous_carbon_number is None:
            if cut.carbon_number != cut_start:
                raise ValidationError(
                    "The first TBP cut must start at cut_start.",
                    parameter=parameter,
                    value=cut.name,
                    cut_start=cut_start,
                )
        elif cut.carbon_number != previous_carbon_number + 1:
            raise ValidationError(
                "TBP cuts must be contiguous one-carbon cuts in phase 1.",
                parameter=parameter,
                value=cut.name,
            )
        seen_names.add(cut.name)
        previous_carbon_number = cut.carbon_number


def _parse_tbp_cut_name(name: str, parameter: str) -> int:
    normalized = name.strip()
    if len(normalized) < 2 or not normalized.startswith("C") or not normalized[1:].isdigit():
        raise ValidationError(
            "TBP cut name must look like 'C7' in phase 1.",
            parameter=parameter,
            value=name,
        )
    return int(normalized[1:])


def _get_required_mapping_value(mapping: Mapping[str, Any], key: str, prefix: str) -> Any:
    if key not in mapping:
        raise ValidationError(
            f"Missing required TBP field '{prefix}.{key}'.",
            parameter=f"{prefix}.{key}",
        )
    return mapping[key]


def _get_required_alias(
    mapping: Mapping[str, Any],
    prefix: str,
    *,
    aliases: Sequence[tuple[str, str]],
) -> tuple[Any, str]:
    for key, parameter in aliases:
        if key in mapping:
            return mapping[key], parameter
    alias_names = ", ".join(key for key, _ in aliases)
    raise ValidationError(
        f"Missing required TBP field at '{prefix}' (expected one of: {alias_names}).",
        parameter=prefix,
    )


def _get_optional_alias(mapping: Mapping[str, Any], *keys: str) -> Any | None:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _get_required_object_attr(obj: object, attr: str, prefix: str) -> Any:
    if not hasattr(obj, attr):
        raise ValidationError(
            f"TBP cut objects must expose '{attr}' at '{prefix}'.",
            parameter=f"{prefix}.{attr}",
            value=type(obj).__name__,
        )
    return getattr(obj, attr)


def _get_required_object_alias(
    obj: object,
    prefix: str,
    *,
    aliases: Sequence[tuple[str, str]],
) -> tuple[Any, str]:
    for attr, parameter in aliases:
        if hasattr(obj, attr):
            return getattr(obj, attr), parameter
    alias_names = ", ".join(attr for attr, _ in aliases)
    raise ValidationError(
        f"TBP cut objects at '{prefix}' must expose one of: {alias_names}.",
        parameter=prefix,
        value=type(obj).__name__,
    )


def _get_optional_object_attr(obj: object, *attrs: str) -> Any | None:
    for attr in attrs:
        if hasattr(obj, attr):
            return getattr(obj, attr)
    return None


def _as_non_empty_str(value: Any, parameter: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(
            f"Expected string at '{parameter}'.",
            parameter=parameter,
            value=value,
        )
    normalized = value.strip()
    if not normalized:
        raise ValidationError(
            "TBP cut names must be non-empty strings.",
            parameter=parameter,
            value=value,
        )
    return normalized


def _as_positive_int(value: Any, parameter: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(
            f"Expected integer at '{parameter}'.",
            parameter=parameter,
            value=value,
        )
    try:
        converted = int(value)
    except (TypeError, ValueError):
        raise ValidationError(
            f"Expected integer at '{parameter}'.",
            parameter=parameter,
            value=value,
        )
    if converted <= 0:
        raise ValidationError(
            "TBP cut carbon numbers must be positive integers.",
            parameter=parameter,
            value=converted,
        )
    return converted


def _as_positive_float(value: Any, parameter: str, message: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(message, parameter=parameter, value=value)
    try:
        converted = float(value)
    except (TypeError, ValueError):
        raise ValidationError(message, parameter=parameter, value=value)
    if not isfinite(converted) or converted <= 0.0:
        raise ValidationError(message, parameter=parameter, value=converted)
    return converted


__all__ = [
    "TBPAssayCut",
    "TBPCutResult",
    "TBPResult",
    "simulate_tbp",
]