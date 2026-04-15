"""Regression tests for phase-envelope plot widget styling."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytestmark = pytest.mark.gui_contract

try:
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]
    QColor = None  # type: ignore[assignment]

from pvtapp.schemas import (
    CalculationType,
    PhaseEnvelopePoint,
    PhaseEnvelopeResult,
    RunConfig,
    RunResult,
    RunStatus,
    SolverSettings,
)

try:
    from pvtapp.widgets.results_view import (
        PLOT_CANVAS_COLOR,
        PLOT_SURFACE_COLOR,
        ResultsPlotWidget,
    )
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    ResultsPlotWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if QApplication is None or ResultsPlotWidget is None:
        pytest.skip("PySide6/matplotlib is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def _build_phase_envelope_run_result() -> RunResult:
    phase_envelope = PhaseEnvelopeResult(
        bubble_curve=[
            PhaseEnvelopePoint(temperature_k=300.0, pressure_pa=8.0e6, point_type="bubble"),
            PhaseEnvelopePoint(temperature_k=320.0, pressure_pa=7.0e6, point_type="bubble"),
        ],
        dew_curve=[
            PhaseEnvelopePoint(temperature_k=340.0, pressure_pa=6.5e6, point_type="dew"),
            PhaseEnvelopePoint(temperature_k=360.0, pressure_pa=5.5e6, point_type="dew"),
        ],
        critical_point=PhaseEnvelopePoint(temperature_k=330.0, pressure_pa=7.2e6, point_type="critical"),
        cricondenbar=None,
        cricondentherm=None,
    )

    return RunResult(
        run_id="style-test",
        run_name="style-test",
        calculation_type=CalculationType.PHASE_ENVELOPE,
        status=RunStatus.COMPLETED,
        started_at=datetime(2026, 4, 8, 8, 0, 0),
        config=RunConfig(
            calculation_type=CalculationType.PHASE_ENVELOPE,
            eos_type="peng_robinson",
            composition={"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            solver_settings=SolverSettings(),
            phase_envelope_config={"temperature_min_k": 250.0, "temperature_max_k": 400.0, "n_points": 20},
        ),
        phase_envelope_result=phase_envelope,
    )


def test_plot_widget_uses_dark_surface_before_render(app: QApplication) -> None:
    widget = ResultsPlotWidget()
    if not getattr(widget, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")

    assert widget.palette().color(widget.backgroundRole()).name().lower() == QColor(PLOT_SURFACE_COLOR).name().lower()
    assert widget.canvas.palette().color(widget.canvas.backgroundRole()).name().lower() == QColor(PLOT_SURFACE_COLOR).name().lower()


def test_phase_envelope_plot_keeps_dark_canvas_after_render(app: QApplication) -> None:
    widget = ResultsPlotWidget()
    if not getattr(widget, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")

    widget.display_result(_build_phase_envelope_run_result())

    assert QColor(PLOT_CANVAS_COLOR).name().lower() == QColor(PLOT_SURFACE_COLOR).name().lower()
    assert widget.figure.get_facecolor()[:3] == pytest.approx(QColor(PLOT_CANVAS_COLOR).getRgbF()[:3], abs=1e-3)
    ax = widget.figure.axes[0]
    assert ax.get_facecolor()[:3] == pytest.approx(QColor(PLOT_CANVAS_COLOR).getRgbF()[:3], abs=1e-3)
