"""Unit tests for the optional Prode validation bridge loader."""

from __future__ import annotations

from textwrap import dedent

from pvtcore.validation.prode_bridge import (
    detect_prode_validation_backend,
    load_prode_validation_backend,
)


def test_detect_prode_validation_backend_reports_missing_installation(monkeypatch) -> None:
    monkeypatch.delenv("PVTSIM_PRODE_BRIDGE", raising=False)

    availability = detect_prode_validation_backend()

    assert availability.available is False
    assert availability.backend_name is None
    assert "PVTSIM_PRODE_BRIDGE" in availability.reason


def test_load_prode_validation_backend_from_explicit_bridge(monkeypatch, tmp_path) -> None:
    bridge_module = tmp_path / "fake_prode_bridge.py"
    bridge_module.write_text(
        dedent(
            """
            from pvtcore.validation.prode_bridge import (
                EnvelopePoint,
                NormalizedEnvelopeResult,
                NormalizedFlashResult,
                NormalizedSaturationResult,
            )

            class FakeBackend:
                name = "fake-prode"

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
    monkeypatch.setenv("PVTSIM_PRODE_BRIDGE", "fake_prode_bridge:get_backend")

    backend = load_prode_validation_backend()
    availability = detect_prode_validation_backend()

    assert backend.name == "fake-prode"
    assert availability.available is True
    assert availability.backend_name == "fake-prode"
