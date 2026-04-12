"""Registry of optional external validation backends.

This module is intentionally validation-facing. It records what each external
tool is good for, whether it is currently detectable in the local environment,
and whether it is allowed inside the repo's active validation engine.

The governing rule for this repo is:

- coursework and equation-based alignment come first
- external tools are secondary validation and bootstrap surfaces
- only permissive, readily redistributable backends are approved for the active
  validation engine
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import importlib.util
from typing import Callable, Optional

from .prode_bridge import detect_prode_validation_backend
from .thermopack_bridge import detect_thermopack_validation_backend


class ValidationBackendRole(str, Enum):
    """Primary role a backend serves in the validation stack."""

    EOS_REFERENCE = "eos_reference"
    PROPERTY_DATA = "property_data"
    PROCESS_SIMULATOR = "process_simulator"
    LAB_PVT_POSTPROCESSOR = "lab_pvt_postprocessor"


class CodeReusePolicy(str, Enum):
    """Repo policy for implementation reuse from a given backend."""

    PERMISSIVE_REUSE = "permissive_reuse"
    VALIDATION_ONLY = "validation_only"
    HOLD_FOR_REVIEW = "hold_for_review"


class ValidationBackendAdoptionStatus(str, Enum):
    """Whether the backend is part of the repo's active validation engine."""

    APPROVED = "approved"
    EXCLUDED_BY_LICENSE_POLICY = "excluded_by_license_policy"
    PENDING_LICENSE_REVIEW = "pending_license_review"


@dataclass(frozen=True)
class ValidationBackendSpec:
    """Metadata describing one external validation backend."""

    backend_id: str
    display_name: str
    role: ValidationBackendRole
    license_name: str
    code_reuse_policy: CodeReusePolicy
    adoption_status: ValidationBackendAdoptionStatus
    coursework_priority: int
    rationale: str
    detection_probe: Optional[Callable[[], bool]] = None

    def is_available(self) -> bool:
        """Return whether the backend appears usable in the current environment."""

        if self.detection_probe is None:
            return False
        try:
            return bool(self.detection_probe())
        except Exception:
            return False


def _has_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _detect_prode() -> bool:
    return detect_prode_validation_backend().available


def _detect_thermopack() -> bool:
    return detect_thermopack_validation_backend().available


_BACKENDS: tuple[ValidationBackendSpec, ...] = (
    ValidationBackendSpec(
        backend_id="thermopack",
        display_name="ThermoPack",
        role=ValidationBackendRole.EOS_REFERENCE,
        license_name="Apache-2.0",
        code_reuse_policy=CodeReusePolicy.PERMISSIVE_REUSE,
        adoption_status=ValidationBackendAdoptionStatus.APPROVED,
        coursework_priority=1,
        rationale=(
            "Best open external EOS/VLE comparison backend for flash, bubble/dew, "
            "critical-point, and phase-envelope structure."
        ),
        detection_probe=_detect_thermopack,
    ),
    ValidationBackendSpec(
        backend_id="thermo",
        display_name="thermo",
        role=ValidationBackendRole.PROPERTY_DATA,
        license_name="MIT",
        code_reuse_policy=CodeReusePolicy.PERMISSIVE_REUSE,
        adoption_status=ValidationBackendAdoptionStatus.APPROVED,
        coursework_priority=2,
        rationale=(
            "Strong pure-component/property-data and general thermodynamics support; "
            "useful for constants, light-mixture checks, and implementation bootstrap."
        ),
        detection_probe=lambda: _has_module("thermo"),
    ),
    ValidationBackendSpec(
        backend_id="prode",
        display_name="Prode Properties",
        role=ValidationBackendRole.EOS_REFERENCE,
        license_name="Proprietary / commercial with limited personal edition",
        code_reuse_policy=CodeReusePolicy.VALIDATION_ONLY,
        adoption_status=ValidationBackendAdoptionStatus.EXCLUDED_BY_LICENSE_POLICY,
        coursework_priority=3,
        rationale=(
            "Technically useful as an external comparison surface, but excluded "
            "from the active engine under the repo's permissive-only policy."
        ),
        detection_probe=_detect_prode,
    ),
    ValidationBackendSpec(
        backend_id="dwsim",
        display_name="DWSIM",
        role=ValidationBackendRole.PROCESS_SIMULATOR,
        license_name="GPL-3.0",
        code_reuse_policy=CodeReusePolicy.VALIDATION_ONLY,
        adoption_status=ValidationBackendAdoptionStatus.EXCLUDED_BY_LICENSE_POLICY,
        coursework_priority=4,
        rationale=(
            "Useful simulator cross-check, but excluded from the active engine "
            "under the repo's permissive-only policy."
        ),
        detection_probe=lambda: _has_module("dwsim"),
    ),
    ValidationBackendSpec(
        backend_id="pyreservoir",
        display_name="PyReservoir",
        role=ValidationBackendRole.LAB_PVT_POSTPROCESSOR,
        license_name="License needs explicit review before code reuse",
        code_reuse_policy=CodeReusePolicy.HOLD_FOR_REVIEW,
        adoption_status=ValidationBackendAdoptionStatus.PENDING_LICENSE_REVIEW,
        coursework_priority=5,
        rationale=(
            "Potentially useful for Bo, Rs, DL, CCE, CVD, and liquid-dropout style "
            "coursework comparisons, but excluded from the active engine until "
            "license terms are unambiguous."
        ),
        detection_probe=lambda: _has_module("pyreservoir"),
    ),
)


def iter_validation_backends() -> tuple[ValidationBackendSpec, ...]:
    """Return all configured external validation backend specifications."""

    return _BACKENDS


def get_validation_backend(backend_id: str) -> ValidationBackendSpec:
    """Return the specification for a named backend."""

    wanted = str(backend_id).strip().lower()
    for spec in _BACKENDS:
        if spec.backend_id == wanted:
            return spec
    raise KeyError(f"Unknown validation backend: {backend_id!r}")


def approved_validation_backends() -> tuple[ValidationBackendSpec, ...]:
    """Return only the backends approved for the active repo validation engine."""

    return tuple(
        sorted(
            (
                spec
                for spec in _BACKENDS
                if spec.adoption_status == ValidationBackendAdoptionStatus.APPROVED
            ),
            key=lambda spec: spec.coursework_priority,
        )
    )


def recommended_coursework_backends() -> tuple[ValidationBackendSpec, ...]:
    """Return approved backends in the recommended coursework-alignment order."""

    return approved_validation_backends()
