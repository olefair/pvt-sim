"""Declared capability surfaces for the pvtapp package."""

from __future__ import annotations

from pvtapp.schemas import CalculationType, EOSType


GUI_SUPPORTED_CALCULATION_TYPES: tuple[CalculationType, ...] = (
    CalculationType.PT_FLASH,
    CalculationType.BUBBLE_POINT,
    CalculationType.DEW_POINT,
    CalculationType.PHASE_ENVELOPE,
    CalculationType.CCE,
    CalculationType.DL,
    CalculationType.CVD,
    CalculationType.SEPARATOR,
)

GUI_CALCULATION_TYPE_LABELS: dict[CalculationType, str] = {
    CalculationType.PT_FLASH: "PT Flash",
    CalculationType.BUBBLE_POINT: "Bubble Point",
    CalculationType.DEW_POINT: "Dew Point",
    CalculationType.PHASE_ENVELOPE: "Phase Envelope",
    CalculationType.CCE: "CCE",
    CalculationType.DL: "Differential Liberation",
    CalculationType.CVD: "CVD",
    CalculationType.SEPARATOR: "Separator",
}

RUNTIME_SUPPORTED_EOS_TYPES: tuple[EOSType, ...] = (
    EOSType.PENG_ROBINSON,
)

RUNTIME_UNSUPPORTED_EOS_MESSAGES: dict[EOSType, str] = {
    EOSType.SRK: "EOS 'srk' is declared in the schema but is not implemented in pvtcore/eos",
    EOSType.PR78: (
        "EOS 'pr78' is not a standalone runtime EOS in the current codebase; "
        "predictive PPR78 BIP wiring is not implemented"
    ),
}

GUI_SUPPORTED_EOS_TYPES: tuple[EOSType, ...] = RUNTIME_SUPPORTED_EOS_TYPES

GUI_EOS_TYPE_LABELS: dict[EOSType, str] = {
    EOSType.PENG_ROBINSON: "Peng-Robinson (1976)",
}


def is_gui_supported_calculation_type(calc_type: CalculationType) -> bool:
    """Return whether a calculation type is currently exposed in the desktop GUI."""
    return calc_type in GUI_SUPPORTED_CALCULATION_TYPES


def is_gui_supported_eos_type(eos_type: EOSType) -> bool:
    """Return whether an EOS is currently exposed in the desktop GUI."""
    return eos_type in GUI_SUPPORTED_EOS_TYPES
