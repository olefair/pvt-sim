"""Optional Prode Properties validation bridge.

This module is validation-facing only. It does not participate in the runtime
solver path. Its purpose is to normalize an external Prode-backed comparison
surface behind a small protocol so pytest-based validation can compare this
repo's results against Prode when Prode is installed and licensed.

The bridge is loaded dynamically to avoid a hard dependency on Prode. A user-
provided bridge factory can be supplied via ``PVTSIM_PRODE_BRIDGE`` using the
form ``package.module:callable``. The callable must return an object
implementing :class:`ProdeValidationBackend`.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import os
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable


_PRODE_BRIDGE_ENV = "PVTSIM_PRODE_BRIDGE"
_COMMON_PRODE_MODULES = (
    "prode",
    "prode_properties",
    "ppp",
    "ProdeProperties",
)
_COMMON_FACTORY_NAMES = (
    "get_pvtsim_prode_backend",
    "get_backend",
    "build_backend",
    "create_backend",
)


@dataclass(frozen=True)
class EnvelopePoint:
    """Normalized temperature/pressure point."""

    temperature_k: float
    pressure_pa: float


@dataclass(frozen=True)
class NormalizedFlashResult:
    """Normalized PT-flash result returned by a Prode validation backend."""

    phase: Optional[str]
    vapor_fraction: Optional[float]
    liquid_composition: Optional[tuple[float, ...]]
    vapor_composition: Optional[tuple[float, ...]]


@dataclass(frozen=True)
class NormalizedSaturationResult:
    """Normalized bubble/dew-point result returned by a Prode validation backend."""

    pressure_pa: float
    liquid_composition: Optional[tuple[float, ...]] = None
    vapor_composition: Optional[tuple[float, ...]] = None


@dataclass(frozen=True)
class NormalizedEnvelopeResult:
    """Normalized phase-envelope result returned by a Prode validation backend."""

    bubble_curve: tuple[EnvelopePoint, ...]
    dew_curve: tuple[EnvelopePoint, ...]
    critical_point: Optional[EnvelopePoint] = None
    cricondenbar: Optional[EnvelopePoint] = None
    cricondentherm: Optional[EnvelopePoint] = None


@runtime_checkable
class ProdeValidationBackend(Protocol):
    """Protocol that a dynamically loaded Prode bridge must satisfy."""

    name: str

    def pt_flash(
        self,
        *,
        temperature_k: float,
        pressure_pa: float,
        component_ids: Sequence[str],
        composition: Sequence[float],
        eos_name: str,
        binary_interaction: Optional[Sequence[Sequence[float]]] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> NormalizedFlashResult:
        """Return a normalized PT-flash result."""

    def bubble_point(
        self,
        *,
        temperature_k: float,
        component_ids: Sequence[str],
        composition: Sequence[float],
        eos_name: str,
        binary_interaction: Optional[Sequence[Sequence[float]]] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> NormalizedSaturationResult:
        """Return a normalized bubble-point result."""

    def dew_point(
        self,
        *,
        temperature_k: float,
        component_ids: Sequence[str],
        composition: Sequence[float],
        eos_name: str,
        binary_interaction: Optional[Sequence[Sequence[float]]] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> NormalizedSaturationResult:
        """Return a normalized dew-point result."""

    def phase_envelope(
        self,
        *,
        component_ids: Sequence[str],
        composition: Sequence[float],
        eos_name: str,
        binary_interaction: Optional[Sequence[Sequence[float]]] = None,
        temperature_min_k: Optional[float] = None,
        temperature_max_k: Optional[float] = None,
        n_points: Optional[int] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> NormalizedEnvelopeResult:
        """Return a normalized phase-envelope result."""


@dataclass(frozen=True)
class ProdeBridgeAvailability:
    """Availability report for the optional Prode validation backend."""

    available: bool
    backend_name: Optional[str]
    reason: str


class ProdeBridgeError(RuntimeError):
    """Raised when a requested Prode validation bridge is malformed."""


def _resolve_bridge_target(spec: str) -> tuple[str, Optional[str]]:
    value = str(spec).strip()
    if not value:
        raise ProdeBridgeError(f"{_PRODE_BRIDGE_ENV} was set but empty")

    if ":" not in value:
        return value, None

    module_name, object_name = value.split(":", 1)
    module_name = module_name.strip()
    object_name = object_name.strip()
    if not module_name:
        raise ProdeBridgeError(f"{_PRODE_BRIDGE_ENV} must declare a module path before ':'")
    if not object_name:
        raise ProdeBridgeError(f"{_PRODE_BRIDGE_ENV} must declare an object name after ':'")
    return module_name, object_name


def _coerce_backend(candidate: Any, *, source: str) -> ProdeValidationBackend:
    backend = candidate() if callable(candidate) else candidate
    if not isinstance(backend, ProdeValidationBackend):
        raise ProdeBridgeError(
            f"Object loaded from {source} does not implement ProdeValidationBackend"
        )
    return backend


def _load_backend_from_module(
    module_name: str,
    *,
    object_name: Optional[str] = None,
) -> ProdeValidationBackend:
    module = importlib.import_module(module_name)

    if object_name is not None:
        if not hasattr(module, object_name):
            raise ProdeBridgeError(f"Module {module_name!r} does not expose {object_name!r}")
        return _coerce_backend(getattr(module, object_name), source=f"{module_name}:{object_name}")

    for factory_name in _COMMON_FACTORY_NAMES:
        if hasattr(module, factory_name):
            return _coerce_backend(getattr(module, factory_name), source=f"{module_name}:{factory_name}")

    if hasattr(module, "backend"):
        return _coerce_backend(getattr(module, "backend"), source=f"{module_name}:backend")

    raise ProdeBridgeError(
        f"Module {module_name!r} was found, but no known backend factory was exposed. "
        f"Set {_PRODE_BRIDGE_ENV}=package.module:callable to point at an explicit bridge."
    )


def load_prode_validation_backend() -> ProdeValidationBackend:
    """Load the configured Prode validation backend.

    Raises:
        ProdeBridgeError: if a configured bridge cannot be imported or does not
            implement the required protocol.
        ModuleNotFoundError: if an explicitly requested module cannot be found.
    """

    explicit = os.environ.get(_PRODE_BRIDGE_ENV)
    if explicit:
        module_name, object_name = _resolve_bridge_target(explicit)
        return _load_backend_from_module(module_name, object_name=object_name)

    for module_name in _COMMON_PRODE_MODULES:
        if importlib.util.find_spec(module_name) is None:
            continue
        return _load_backend_from_module(module_name)

    raise ModuleNotFoundError(
        "No Prode bridge could be located. Set "
        f"{_PRODE_BRIDGE_ENV}=package.module:callable to enable Prode validation."
    )


def detect_prode_validation_backend() -> ProdeBridgeAvailability:
    """Return a non-raising availability report for the Prode bridge."""

    try:
        backend = load_prode_validation_backend()
    except ModuleNotFoundError as exc:
        return ProdeBridgeAvailability(available=False, backend_name=None, reason=str(exc))
    except ProdeBridgeError as exc:
        return ProdeBridgeAvailability(available=False, backend_name=None, reason=str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard for vendor bridge failures
        return ProdeBridgeAvailability(
            available=False,
            backend_name=None,
            reason=f"Unexpected Prode bridge failure: {exc}",
        )

    return ProdeBridgeAvailability(
        available=True,
        backend_name=getattr(backend, "name", backend.__class__.__name__),
        reason="loaded",
    )

