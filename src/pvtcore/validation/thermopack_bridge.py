"""Optional ThermoPack validation bridge.

This bridge is validation-facing only. It provides a normalized adapter over
the ThermoPack Python wrapper so the repo can compare its own solver outputs
against ThermoPack without introducing ThermoPack as a required runtime
dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib
import importlib.util
import os
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

import numpy as np

from .prode_bridge import EnvelopePoint, NormalizedEnvelopeResult, NormalizedFlashResult, NormalizedSaturationResult


_THERMOPACK_BRIDGE_ENV = "PVTSIM_THERMOPACK_BRIDGE"
_COMMON_FACTORY_NAMES = (
    "get_pvtsim_thermopack_backend",
    "get_backend",
    "build_backend",
    "create_backend",
)
_EOS_ALIASES = {
    "pr": "PR",
    "peng-robinson": "PR",
    "peng robinson": "PR",
    "peng-robinson 1976": "PR",
    "peng_robinson": "PR",
    "srk": "SRK",
    "soave-redlich-kwong": "SRK",
    "soave redlich kwong": "SRK",
}
_THERMOPACK_COMPONENT_IDS = {
    "N2": "N2",
    "CO2": "CO2",
    "H2S": "H2S",
    "C1": "C1",
    "C2": "C2",
    "C3": "C3",
    "C4": "NC4",
    "nC4": "NC4",
    "iC4": "IC4",
    "C5": "NC5",
    "nC5": "NC5",
    "iC5": "IC5",
    "C6": "NC6",
    "C7": "NC7",
    "C8": "NC8",
    "C9": "NC9",
    "C10": "NC10",
    "C11": "NC11",
    "C12": "NC12",
    "C13": "NC13",
    "C14": "NC14",
    "C15": "NC15",
    "C16": "NC16",
    "C17": "NC17",
    "C18": "NC18",
    "C19": "NC19",
    "C20": "NC20",
    "C21": "NC21",
    "C22": "NC22",
    "C23": "NC23",
    "C24": "NC24",
    "C25": "NC25",
}


@runtime_checkable
class ThermoPackValidationBackend(Protocol):
    """Protocol for normalized ThermoPack validation backends."""

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
class ThermoPackBridgeAvailability:
    """Availability report for the optional ThermoPack bridge."""

    available: bool
    backend_name: Optional[str]
    reason: str


class ThermoPackBridgeError(RuntimeError):
    """Raised when the ThermoPack bridge cannot be loaded or normalized."""


def _resolve_bridge_target(spec: str) -> tuple[str, Optional[str]]:
    value = str(spec).strip()
    if not value:
        raise ThermoPackBridgeError(f"{_THERMOPACK_BRIDGE_ENV} was set but empty")
    if ":" not in value:
        return value, None
    module_name, object_name = value.split(":", 1)
    module_name = module_name.strip()
    object_name = object_name.strip()
    if not module_name:
        raise ThermoPackBridgeError(f"{_THERMOPACK_BRIDGE_ENV} must declare a module path before ':'")
    if not object_name:
        raise ThermoPackBridgeError(f"{_THERMOPACK_BRIDGE_ENV} must declare an object name after ':'")
    return module_name, object_name


def _normalize_component_id(component_id: str) -> str:
    stripped = str(component_id).strip()
    if stripped in _THERMOPACK_COMPONENT_IDS:
        return _THERMOPACK_COMPONENT_IDS[stripped]

    if stripped.startswith("nC") and stripped[2:].isdigit():
        return f"NC{int(stripped[2:])}"
    if stripped.startswith("iC") and stripped[2:].isdigit():
        return f"IC{int(stripped[2:])}"
    if stripped.startswith("C") and stripped[1:].isdigit():
        carbon = int(stripped[1:])
        if carbon <= 3:
            return f"C{carbon}"
        return f"NC{carbon}"

    raise ThermoPackBridgeError(f"Component {component_id!r} cannot be mapped to a ThermoPack identifier")


def _normalize_eos_name(eos_name: str) -> str:
    normalized = _EOS_ALIASES.get(str(eos_name).strip().lower())
    if normalized is None:
        raise ThermoPackBridgeError(f"Unsupported ThermoPack EOS request: {eos_name!r}")
    return normalized


def _phase_name(backend: Any, phase_flag: int, beta_v: Optional[float], beta_l: Optional[float]) -> Optional[str]:
    if phase_flag == getattr(backend, "TWOPH", object()):
        return "two-phase"
    if phase_flag == getattr(backend, "LIQPH", object()):
        return "liquid"
    if phase_flag == getattr(backend, "VAPPH", object()):
        return "vapor"

    if beta_v is not None and beta_l is not None:
        if beta_v > 0.0 and beta_l > 0.0:
            return "two-phase"
        if beta_v >= 1.0 - 1e-12:
            return "vapor"
        if beta_l >= 1.0 - 1e-12:
            return "liquid"
    return None


def _coerce_backend(candidate: Any, *, source: str) -> ThermoPackValidationBackend:
    backend = candidate() if callable(candidate) else candidate
    if not isinstance(backend, ThermoPackValidationBackend):
        raise ThermoPackBridgeError(
            f"Object loaded from {source} does not implement ThermoPackValidationBackend"
        )
    return backend


def _load_backend_from_module(module_name: str, *, object_name: Optional[str] = None) -> ThermoPackValidationBackend:
    module = importlib.import_module(module_name)

    if object_name is not None:
        if not hasattr(module, object_name):
            raise ThermoPackBridgeError(f"Module {module_name!r} does not expose {object_name!r}")
        return _coerce_backend(getattr(module, object_name), source=f"{module_name}:{object_name}")

    for factory_name in _COMMON_FACTORY_NAMES:
        if hasattr(module, factory_name):
            return _coerce_backend(getattr(module, factory_name), source=f"{module_name}:{factory_name}")

    if hasattr(module, "backend"):
        return _coerce_backend(getattr(module, "backend"), source=f"{module_name}:backend")

    raise ThermoPackBridgeError(
        f"Module {module_name!r} was found, but no known backend factory was exposed. "
        f"Set {_THERMOPACK_BRIDGE_ENV}=package.module:callable to point at an explicit bridge."
    )


class NativeThermoPackBackend:
    """Normalized adapter over ThermoPack's native Python API."""

    name = "thermopack-native"

    def __init__(self) -> None:
        from thermopack.cubic import PengRobinson, SoaveRedlichKwong

        self._peng_robinson = PengRobinson
        self._srk = SoaveRedlichKwong

    def _build_eos(
        self,
        *,
        component_ids: Sequence[str],
        eos_name: str,
        binary_interaction: Optional[Sequence[Sequence[float]]] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> Any:
        options = dict(options or {})
        mapped_ids = [_normalize_component_id(component_id) for component_id in component_ids]
        joined = ",".join(mapped_ids)
        normalized_eos = _normalize_eos_name(eos_name)

        if normalized_eos == "PR":
            eos = self._peng_robinson(
                joined,
                mixing=str(options.get("mixing", "vdW")),
                alpha=str(options.get("alpha", "Classic")),
                parameter_reference=str(options.get("parameter_reference", "Default")),
                volume_shift=bool(options.get("volume_shift", False)),
            )
        elif normalized_eos == "SRK":
            eos = self._srk(
                joined,
                mixing=str(options.get("mixing", "vdW")),
                parameter_reference=str(options.get("parameter_reference", "Default")),
                volume_shift=bool(options.get("volume_shift", False)),
            )
        else:  # pragma: no cover - guarded by _normalize_eos_name
            raise ThermoPackBridgeError(f"Unsupported ThermoPack EOS request: {eos_name!r}")

        if binary_interaction is not None:
            kij = np.asarray(binary_interaction, dtype=float)
            if kij.ndim != 2 or kij.shape[0] != kij.shape[1] or kij.shape[0] != len(component_ids):
                raise ThermoPackBridgeError("binary_interaction must be a square matrix matching the component count")
            for i in range(len(component_ids)):
                for j in range(i + 1, len(component_ids)):
                    eos.set_kij(i + 1, j + 1, float(kij[i, j]))

        return eos

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
        eos = self._build_eos(
            component_ids=component_ids,
            eos_name=eos_name,
            binary_interaction=binary_interaction,
            options=options,
        )
        flash = eos.two_phase_tpflash(float(temperature_k), float(pressure_pa), composition)
        beta_v = None if getattr(flash, "betaV", None) is None else float(flash.betaV)
        beta_l = None if getattr(flash, "betaL", None) is None else float(flash.betaL)
        return NormalizedFlashResult(
            phase=_phase_name(eos, int(getattr(flash, "phase", -1)), beta_v, beta_l),
            vapor_fraction=beta_v,
            liquid_composition=None if getattr(flash, "x", None) is None else tuple(np.array(flash.x, dtype=float)),
            vapor_composition=None if getattr(flash, "y", None) is None else tuple(np.array(flash.y, dtype=float)),
        )

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
        eos = self._build_eos(
            component_ids=component_ids,
            eos_name=eos_name,
            binary_interaction=binary_interaction,
            options=options,
        )
        pressure, incipient = eos.bubble_pressure(float(temperature_k), composition)
        return NormalizedSaturationResult(
            pressure_pa=float(pressure),
            vapor_composition=tuple(np.array(incipient, dtype=float)),
        )

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
        eos = self._build_eos(
            component_ids=component_ids,
            eos_name=eos_name,
            binary_interaction=binary_interaction,
            options=options,
        )
        pressure, incipient = eos.dew_pressure(float(temperature_k), composition)
        return NormalizedSaturationResult(
            pressure_pa=float(pressure),
            liquid_composition=tuple(np.array(incipient, dtype=float)),
        )

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
        options = dict(options or {})
        eos = self._build_eos(
            component_ids=component_ids,
            eos_name=eos_name,
            binary_interaction=binary_interaction,
            options=options,
        )

        initial_pressure_pa = float(options.get("initial_pressure_pa", 1.0e5))
        maximum_pressure_pa = float(
            options.get(
                "maximum_pressure_pa",
                max(1.5e7, initial_pressure_pa * 20.0),
            )
        )
        step_size_factor = float(options.get("step_size_factor", 1.0))
        step_size = options.get("step_size")
        initial_temperature_k = options.get("initial_temperature_k")
        calc_v = bool(options.get("calc_v", False))

        if initial_temperature_k is not None:
            initial_temperature_k = float(initial_temperature_k)
        if step_size is not None:
            step_size = float(step_size)

        envelope = eos.get_envelope_twophase(
            initial_pressure_pa,
            composition,
            maximum_pressure=maximum_pressure_pa,
            minimum_temperature=temperature_min_k,
            step_size_factor=step_size_factor,
            step_size=step_size,
            calc_v=calc_v,
            initial_temperature=initial_temperature_k,
            calc_criconden=True,
        )

        temperatures = np.array(envelope[0], dtype=float)
        pressures = np.array(envelope[1], dtype=float)
        if temperatures.size == 0 or pressures.size == 0:
            raise ThermoPackBridgeError("ThermoPack returned an empty phase envelope")

        order = np.argsort(temperatures)
        temperatures_sorted = temperatures[order]
        pressures_sorted = pressures[order]
        if temperature_max_k is not None:
            mask = temperatures_sorted <= float(temperature_max_k) + 1e-12
            temperatures_sorted = temperatures_sorted[mask]
            pressures_sorted = pressures_sorted[mask]

        idx_pmax = int(np.argmax(pressures))
        dew = [
            EnvelopePoint(float(t), float(p))
            for t, p in sorted(
                zip(temperatures[: idx_pmax + 1], pressures[: idx_pmax + 1], strict=False),
                key=lambda pair: pair[0],
            )
        ]
        bubble = [
            EnvelopePoint(float(t), float(p))
            for t, p in sorted(
                zip(temperatures[idx_pmax + 1 :], pressures[idx_pmax + 1 :], strict=False),
                key=lambda pair: pair[0],
            )
        ]

        criconden = envelope[-1] if len(envelope) >= (4 if calc_v else 3) else None
        cricondenbar = None
        cricondentherm = None
        if criconden is not None:
            criconden = np.array(criconden, dtype=float).reshape(-1)
            if criconden.size >= 4:
                cricondenbar = EnvelopePoint(float(criconden[0]), float(criconden[1]))
                cricondentherm = EnvelopePoint(float(criconden[2]), float(criconden[3]))

        critical_point = None
        try:
            critical_temperature, _critical_volume, critical_pressure = eos.critical(composition)
            critical_point = EnvelopePoint(float(critical_temperature), float(critical_pressure))
        except Exception:
            critical_point = None

        return NormalizedEnvelopeResult(
            bubble_curve=tuple(bubble),
            dew_curve=tuple(dew),
            critical_point=critical_point,
            cricondenbar=cricondenbar,
            cricondentherm=cricondentherm,
        )


def load_thermopack_validation_backend() -> ThermoPackValidationBackend:
    """Load the configured ThermoPack validation backend."""

    explicit = os.environ.get(_THERMOPACK_BRIDGE_ENV)
    if explicit:
        module_name, object_name = _resolve_bridge_target(explicit)
        return _load_backend_from_module(module_name, object_name=object_name)

    if importlib.util.find_spec("thermopack") is None:
        raise ModuleNotFoundError(
            "No ThermoPack install was found. Install `thermopack` or set "
            f"{_THERMOPACK_BRIDGE_ENV}=package.module:callable."
        )

    return NativeThermoPackBackend()


def detect_thermopack_validation_backend() -> ThermoPackBridgeAvailability:
    """Return a non-raising availability report for the ThermoPack bridge."""

    try:
        backend = load_thermopack_validation_backend()
    except ModuleNotFoundError as exc:
        return ThermoPackBridgeAvailability(available=False, backend_name=None, reason=str(exc))
    except ThermoPackBridgeError as exc:
        return ThermoPackBridgeAvailability(available=False, backend_name=None, reason=str(exc))
    except Exception as exc:  # pragma: no cover - defensive guard for vendor bridge failures
        return ThermoPackBridgeAvailability(
            available=False,
            backend_name=None,
            reason=f"Unexpected ThermoPack bridge failure: {exc}",
        )

    return ThermoPackBridgeAvailability(
        available=True,
        backend_name=getattr(backend, "name", backend.__class__.__name__),
        reason="loaded",
    )
