"""Unit tests for the optional ThermoPack validation bridge loader."""

from __future__ import annotations

import importlib.util
from textwrap import dedent

from pvtcore.validation.thermopack_bridge import (
    detect_thermopack_validation_backend,
    load_thermopack_validation_backend,
)


def test_detect_thermopack_validation_backend_reports_missing_installation(monkeypatch) -> None:
    monkeypatch.delenv("PVTSIM_THERMOPACK_BRIDGE", raising=False)
    original_find_spec = importlib.util.find_spec
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: None if name == "thermopack" else original_find_spec(name),
    )

    availability = detect_thermopack_validation_backend()

    assert availability.available is False
    assert availability.backend_name is None
    assert "PVTSIM_THERMOPACK_BRIDGE" in availability.reason or "thermopack" in availability.reason.lower()


def test_load_thermopack_validation_backend_from_explicit_bridge(monkeypatch, tmp_path) -> None:
    bridge_module = tmp_path / "fake_thermopack_bridge.py"
    bridge_module.write_text(
        dedent(
            """
            from pvtcore.validation.thermopack_bridge import (
                EnvelopePoint,
                NormalizedEnvelopeResult,
                NormalizedFlashResult,
                NormalizedSaturationResult,
            )

            class FakeBackend:
                name = "fake-thermopack"

                def pt_flash(self, **_kwargs):
                    return NormalizedFlashResult(
                        phase="two-phase",
                        vapor_fraction=0.25,
                        liquid_composition=(0.5, 0.5),
                        vapor_composition=(0.7, 0.3),
                    )

                def bubble_point(self, **_kwargs):
                    return NormalizedSaturationResult(pressure_pa=1.23e6)

                def dew_point(self, **_kwargs):
                    return NormalizedSaturationResult(pressure_pa=9.87e5)

                def phase_envelope(self, **_kwargs):
                    point = EnvelopePoint(temperature_k=300.0, pressure_pa=1.0e6)
                    return NormalizedEnvelopeResult(
                        bubble_curve=(point,),
                        dew_curve=(point,),
                        critical_point=point,
                        cricondenbar=point,
                        cricondentherm=point,
                    )

            def get_backend():
                return FakeBackend()
            """
        ),
        encoding="utf-8",
    )

    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv("PVTSIM_THERMOPACK_BRIDGE", "fake_thermopack_bridge:get_backend")

    backend = load_thermopack_validation_backend()
    availability = detect_thermopack_validation_backend()

    assert backend.name == "fake-thermopack"
    assert availability.available is True
    assert availability.backend_name == "fake-thermopack"
