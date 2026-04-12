"""Schemas and loaders for external saturation-validation corpus files.

This module is intentionally validation-facing, not runtime-facing. It defines
the durable JSON shapes used to collect and validate external physical-accuracy
anchors for saturation work:

- pure-component saturation tables
- literature VLE tie-line points
- lab-style ``C1-C6 + C7+`` saturation anchors

It also defines a separate acquisition manifest schema so planned source
collection can be tracked in structured JSON before the measured values are
entered.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, model_validator


class PressureUnit(str, Enum):
    """Supported pressure units for external corpus files."""

    PA = "Pa"
    KPA = "kPa"
    MPA = "MPa"
    BAR = "bar"
    PSI = "psi"
    PSIA = "psia"
    ATM = "atm"


class TemperatureUnit(str, Enum):
    """Supported temperature units for external corpus files."""

    K = "K"
    C = "C"
    F = "F"
    R = "R"


class ExternalAnchorType(str, Enum):
    """Top-level case kinds supported by the external corpus."""

    PURE_COMPONENT_SATURATION = "pure_component_saturation"
    LITERATURE_VLE_TIELINE = "literature_vle_tieline"
    LAB_C7PLUS_SATURATION = "lab_c7plus_saturation"


class SourceKind(str, Enum):
    """External source types tracked by the corpus."""

    NIST_WEBBOOK = "nist_webbook"
    THERMOML = "thermoml"
    JOURNAL = "journal"
    LAB_REPORT = "lab_report"
    COMMERCIAL_REPORT = "commercial_report"


class AcquisitionPriority(str, Enum):
    """Relative priority for planned external anchor collection."""

    NOW = "now"
    NEXT = "next"
    LATER = "later"


class SourceReference(BaseModel):
    """Citation metadata for an external case or planned acquisition."""

    kind: SourceKind
    citation: str = Field(..., min_length=1)
    url: str | None = None
    notes: list[str] = Field(default_factory=list)


class TemperatureSpec(BaseModel):
    """Scalar temperature with explicit unit."""

    value: float = Field(..., gt=0.0)
    unit: TemperatureUnit


class PressureSpec(BaseModel):
    """Scalar pressure with explicit unit."""

    value: float = Field(..., gt=0.0)
    unit: PressureUnit


class CompositionEntry(BaseModel):
    """Single component mole-fraction entry."""

    component_id: str = Field(..., min_length=1)
    mole_fraction: float = Field(..., gt=0.0, le=1.0)


def _validate_composition_sum(entries: list[CompositionEntry], *, label: str, atol: float = 1e-6) -> None:
    total = float(sum(entry.mole_fraction for entry in entries))
    if abs(total - 1.0) > atol:
        raise ValueError(f"{label} mole fractions must sum to 1.0; got {total:.10f}")


def _component_ids(entries: list[CompositionEntry]) -> tuple[str, ...]:
    return tuple(entry.component_id for entry in entries)


class PureComponentSaturationPoint(BaseModel):
    """Single measured pure-component saturation point."""

    temperature: TemperatureSpec
    pressure: PressureSpec


class PureComponentSaturationAnchor(BaseModel):
    """Reference-quality pure-component saturation data."""

    anchor_type: Literal["pure_component_saturation"]
    case_id: str = Field(..., min_length=1)
    component_id: str = Field(..., min_length=1)
    source: SourceReference
    points: list[PureComponentSaturationPoint] = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)


class LiteratureVLETieLineAnchor(BaseModel):
    """Literature VLE tie-line or coexistence-state anchor."""

    anchor_type: Literal["literature_vle_tieline"]
    case_id: str = Field(..., min_length=1)
    source: SourceReference
    temperature: TemperatureSpec
    pressure: PressureSpec
    liquid_composition: list[CompositionEntry] = Field(..., min_length=2)
    vapor_composition: list[CompositionEntry] = Field(..., min_length=2)
    feed_composition: list[CompositionEntry] | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_phase_compositions(self) -> "LiteratureVLETieLineAnchor":
        _validate_composition_sum(self.liquid_composition, label="liquid_composition")
        _validate_composition_sum(self.vapor_composition, label="vapor_composition")

        liquid_ids = _component_ids(self.liquid_composition)
        vapor_ids = _component_ids(self.vapor_composition)
        if liquid_ids != vapor_ids:
            raise ValueError(
                "liquid_composition and vapor_composition must list the same component IDs in the same order"
            )

        if self.feed_composition is not None:
            _validate_composition_sum(self.feed_composition, label="feed_composition")
            feed_ids = _component_ids(self.feed_composition)
            if feed_ids != liquid_ids:
                raise ValueError(
                    "feed_composition must list the same component IDs as the tie-line phase compositions"
                )
        return self


class PlusFractionCharacterizationSpec(BaseModel):
    """Explicit runtime characterization choices required to reproduce a lab case."""

    split_mw_model: Literal["paraffin", "table"]
    max_carbon_number: int = Field(..., ge=7, le=60)
    lumping_enabled: bool = True
    lumping_n_groups: int = Field(..., ge=1, le=20)


class PlusFractionInputSpec(BaseModel):
    """Lab-reported plus-fraction descriptor."""

    label: str = Field(..., min_length=1)
    cut_start: int = Field(default=7, ge=7, le=30)
    z_plus: float = Field(..., gt=0.0, le=1.0)
    mw_plus_g_per_mol: float = Field(..., gt=0.0)
    sg_plus_60f: float = Field(..., gt=0.0, lt=2.0)
    characterization: PlusFractionCharacterizationSpec


class LabC7PlusSaturationAnchor(BaseModel):
    """Lab-style ``C1-C6 + C7+`` bubble/dew anchor."""

    anchor_type: Literal["lab_c7plus_saturation"]
    case_id: str = Field(..., min_length=1)
    workflow: Literal["bubble_point", "dew_point"]
    fluid_family: str = Field(..., min_length=1)
    source: SourceReference
    temperature: TemperatureSpec
    expected_pressure: PressureSpec
    light_components: list[CompositionEntry] = Field(..., min_length=2)
    plus_fraction: PlusFractionInputSpec
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_feed_balance(self) -> "LabC7PlusSaturationAnchor":
        total = float(sum(entry.mole_fraction for entry in self.light_components) + self.plus_fraction.z_plus)
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"light_components plus z_plus must sum to 1.0; got {total:.10f}")
        return self


ExternalAnchorCase = Annotated[
    PureComponentSaturationAnchor | LiteratureVLETieLineAnchor | LabC7PlusSaturationAnchor,
    Field(discriminator="anchor_type"),
]


class PlannedExternalAnchor(BaseModel):
    """Structured backlog entry for an external anchor that still needs to be collected."""

    planned_case_id: str = Field(..., min_length=1)
    anchor_type: ExternalAnchorType
    priority: AcquisitionPriority
    source: SourceReference
    target_regime: str = Field(..., min_length=1)
    target_components: list[str] = Field(default_factory=list)
    target_temperatures_k: list[float] = Field(default_factory=list)
    expected_workflow: Literal["bubble_point", "dew_point"] | None = None
    requested_observables: list[str] = Field(..., min_length=1)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_targeting(self) -> "PlannedExternalAnchor":
        if self.anchor_type == ExternalAnchorType.PURE_COMPONENT_SATURATION:
            if len(self.target_components) != 1:
                raise ValueError("pure_component_saturation planned entries must list exactly one target component")
            if not self.target_temperatures_k:
                raise ValueError("pure_component_saturation planned entries must include target_temperatures_k")

        if self.anchor_type == ExternalAnchorType.LAB_C7PLUS_SATURATION and self.expected_workflow is None:
            raise ValueError("lab_c7plus_saturation planned entries must declare expected_workflow")

        return self


class ExternalAcquisitionManifest(BaseModel):
    """Structured acquisition backlog for external saturation anchors."""

    schema_version: int = Field(default=1, ge=1)
    notes: list[str] = Field(default_factory=list)
    entries: list[PlannedExternalAnchor] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_unique_ids(self) -> "ExternalAcquisitionManifest":
        ids = [entry.planned_case_id for entry in self.entries]
        if len(ids) != len(set(ids)):
            raise ValueError("planned_case_id values in the acquisition manifest must be unique")
        return self


_EXTERNAL_CASE_ADAPTER = TypeAdapter(ExternalAnchorCase)


def _load_json(path: str | Path) -> object:
    case_path = Path(path)
    return json.loads(case_path.read_text(encoding="utf-8"))


def load_external_anchor_case(path: str | Path) -> ExternalAnchorCase:
    """Load and validate a ready/template external anchor case file."""

    return _EXTERNAL_CASE_ADAPTER.validate_python(_load_json(path))


def load_external_acquisition_manifest(path: str | Path) -> ExternalAcquisitionManifest:
    """Load and validate the planned external-anchor acquisition manifest."""

    return ExternalAcquisitionManifest.model_validate(_load_json(path))
