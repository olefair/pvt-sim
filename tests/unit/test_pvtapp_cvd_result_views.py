"""Regression tests for CVD result presentation widgets."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]

from pvtapp.schemas import (
    CalculationType,
    CVDResult,
    CVDStepResult,
    RunConfig,
    RunResult,
    RunStatus,
    SolverSettings,
)

try:
    from pvtapp.widgets.results_view import ResultsPlotWidget, ResultsTableWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    ResultsPlotWidget = None  # type: ignore[assignment]
    ResultsTableWidget = None  # type: ignore[assignment]
    TextOutputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if (
        QApplication is None
        or ResultsPlotWidget is None
        or ResultsTableWidget is None
        or TextOutputWidget is None
    ):
        pytest.skip("PySide6/matplotlib is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def _build_cvd_run_result() -> RunResult:
    return RunResult(
        run_id="cvd-view-test",
        run_name="cvd-view-test",
        status=RunStatus.COMPLETED,
        started_at=datetime(2026, 4, 9, 8, 0, 0),
        completed_at=datetime(2026, 4, 9, 8, 0, 5),
        duration_seconds=5.0,
        config=RunConfig(
            calculation_type=CalculationType.CVD,
            eos_type="peng_robinson",
            composition={"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            solver_settings=SolverSettings(),
            cvd_config={
                "temperature_k": 380.0,
                "dew_pressure_pa": 5.652e6,
                "pressure_end_pa": 5.0e6,
                "n_steps": 5,
            },
        ),
        cvd_result=CVDResult(
            temperature_k=380.0,
            dew_pressure_pa=5.652e6,
            initial_z=0.92,
            converged=True,
            steps=[
                CVDStepResult(
                    pressure_pa=5.652e6,
                    liquid_dropout=0.00,
                    cumulative_gas_produced=0.00,
                    moles_remaining=1.0,
                    z_two_phase=0.92,
                ),
                CVDStepResult(
                    pressure_pa=5.30e6,
                    liquid_dropout=0.04,
                    cumulative_gas_produced=0.12,
                    moles_remaining=0.88,
                    z_two_phase=0.89,
                ),
                CVDStepResult(
                    pressure_pa=5.0e6,
                    liquid_dropout=0.07,
                    cumulative_gas_produced=0.20,
                    moles_remaining=0.80,
                    z_two_phase=0.86,
                ),
            ],
        ),
    )


def test_cvd_results_table_displays_summary_instead_of_error(app: QApplication) -> None:
    widget = ResultsTableWidget()
    widget.display_result(_build_cvd_run_result())

    assert widget.summary_table.item(0, 0).text() == "Temperature"
    assert widget.summary_table.item(1, 0).text() == "Dew Pressure"
    assert widget.composition_table.rowCount() == 3


def test_cvd_plot_widget_renders_a_plot(app: QApplication) -> None:
    widget = ResultsPlotWidget()
    if not getattr(widget, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")

    widget.display_result(_build_cvd_run_result())

    assert len(widget.figure.axes) >= 1
    assert "CVD" in widget.figure.axes[0].get_title()


def test_cvd_text_output_reports_dropout(app: QApplication) -> None:
    widget = TextOutputWidget()
    widget.display_result(_build_cvd_run_result())

    text = widget.text.toPlainText()
    assert "CVD" in text
    assert "Liquid Dropout" in text
    assert "Cum. Gas" in text
