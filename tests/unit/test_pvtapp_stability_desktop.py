"""GUI-contract coverage for standalone stability analysis."""

from __future__ import annotations

import gc
import os
from datetime import datetime
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytestmark = pytest.mark.gui_contract

try:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QCoreApplication = None  # type: ignore[assignment]
    QEvent = None  # type: ignore[assignment]
    QSettings = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]

from pvtapp.schemas import (
    RunConfig,
    RunResult,
    RunStatus,
    PressureUnit,
    TemperatureUnit,
    StabilityAnalysisResult,
    StabilitySeedResultData,
    StabilityTrialResultData,
    pressure_from_pa,
    temperature_from_k,
)

try:
    from pvtapp.main import PVTSimulatorWindow
    from pvtapp.widgets.diagnostics_view import DiagnosticsWidget
    from pvtapp.widgets.results_view import ResultsPlotWidget, ResultsTableWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    PVTSimulatorWindow = None  # type: ignore[assignment]
    DiagnosticsWidget = None  # type: ignore[assignment]
    ResultsPlotWidget = None  # type: ignore[assignment]
    ResultsTableWidget = None  # type: ignore[assignment]
    TextOutputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if (
        QApplication is None
        or QSettings is None
        or PVTSimulatorWindow is None
        or DiagnosticsWidget is None
        or ResultsPlotWidget is None
        or ResultsTableWidget is None
        or TextOutputWidget is None
    ):
        pytest.skip("PySide6/matplotlib is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


@pytest.fixture()
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "pvtapp-stability-test-settings.ini"


@pytest.fixture()
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch, settings_path: Path) -> PVTSimulatorWindow:
    def _create_settings(_self) -> QSettings:
        return QSettings(str(settings_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(PVTSimulatorWindow, "_create_settings", _create_settings)
    instance = PVTSimulatorWindow()
    yield instance
    instance.close()
    instance.deleteLater()
    app.processEvents()
    if QCoreApplication is not None and QEvent is not None:
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)
        app.processEvents()
    gc.collect()


def _run_config(data: dict) -> RunConfig:
    return RunConfig.model_validate(data)


def _started_at() -> datetime:
    return datetime(2026, 4, 15, 9, 0, 0)


def _completed_run_result(config: RunConfig, **payload) -> RunResult:
    return RunResult(
        run_id=f"{config.calculation_type.value}-result",
        run_name=f"{config.calculation_type.value}-result",
        status=RunStatus.COMPLETED,
        started_at=_started_at(),
        completed_at=_started_at(),
        duration_seconds=1.0,
        config=config,
        **payload,
    )


def _stability_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "stability_analysis",
            "eos_type": "peng_robinson",
            "stability_analysis_config": {
                "pressure_pa": 10342135.5,
                "temperature_k": 326.76111111111106,
                "feed_phase": "liquid",
                "use_gdem": True,
                "n_random_trials": 2,
                "random_seed": 123,
                "max_eos_failures_per_trial": 4,
                "pressure_unit": "psia",
                "temperature_unit": "F",
            },
        }
    )


def _stability_result() -> RunResult:
    config = _stability_config()
    vapor_trial = StabilityTrialResultData(
        kind="vapor_like",
        trial_phase="vapor",
        composition={"C1": 0.96, "C10": 0.04},
        tpd=-2.5e-2,
        iterations=6,
        total_iterations=10,
        converged=True,
        early_exit_unstable=True,
        n_phi_calls=18,
        n_eos_failures=1,
        message="negative tpd located",
        best_seed_index=0,
        candidate_seed_labels=["wilson", "extreme_lightest"],
        diagnostic_messages=["transient eos failure recovered"],
        seed_results=[
            StabilitySeedResultData(
                kind="vapor_like",
                trial_phase="vapor",
                seed_index=0,
                seed_label="wilson",
                initial_composition={"C1": 0.90, "C10": 0.10},
                composition={"C1": 0.96, "C10": 0.04},
                tpd=-2.5e-2,
                iterations=6,
                converged=True,
                early_exit_unstable=True,
                n_phi_calls=12,
                n_eos_failures=1,
                message="best seed",
            ),
            StabilitySeedResultData(
                kind="vapor_like",
                trial_phase="vapor",
                seed_index=1,
                seed_label="extreme_lightest",
                initial_composition={"C1": 0.97, "C10": 0.03},
                composition={"C1": 0.98, "C10": 0.02},
                tpd=-2.0e-2,
                iterations=4,
                converged=True,
                early_exit_unstable=False,
                n_phi_calls=6,
                n_eos_failures=0,
                message="alternate stationary point",
            ),
        ],
    )
    liquid_trial = StabilityTrialResultData(
        kind="liquid_like",
        trial_phase="liquid",
        composition={"C1": 0.22, "C10": 0.78},
        tpd=-8.0e-3,
        iterations=5,
        total_iterations=5,
        converged=True,
        early_exit_unstable=False,
        n_phi_calls=9,
        n_eos_failures=0,
        message=None,
        best_seed_index=0,
        candidate_seed_labels=["wilson"],
        diagnostic_messages=[],
        seed_results=[
            StabilitySeedResultData(
                kind="liquid_like",
                trial_phase="liquid",
                seed_index=0,
                seed_label="wilson",
                initial_composition={"C1": 0.30, "C10": 0.70},
                composition={"C1": 0.22, "C10": 0.78},
                tpd=-8.0e-3,
                iterations=5,
                converged=True,
                early_exit_unstable=False,
                n_phi_calls=9,
                n_eos_failures=0,
                message=None,
            )
        ],
    )
    return _completed_run_result(
        config,
        stability_analysis_result=StabilityAnalysisResult(
            stable=False,
            tpd_min=-2.5e-2,
            pressure_pa=config.stability_analysis_config.pressure_pa,
            temperature_k=config.stability_analysis_config.temperature_k,
            requested_feed_phase=config.stability_analysis_config.feed_phase,
            resolved_feed_phase="liquid",
            reference_root_used="liquid",
            phase_regime="two_phase",
            physical_state_hint="two_phase",
            physical_state_hint_basis="two_phase_regime",
            physical_state_hint_confidence="high",
            liquid_root_z=0.120000,
            vapor_root_z=0.910000,
            root_gap=7.900000e-01,
            gibbs_gap=2.500000e-01,
            average_reduced_pressure=1.230000,
            feed_composition={"C1": 0.5, "C10": 0.5},
            best_unstable_trial_kind="vapor_like",
            vapor_like_trial=vapor_trial,
            liquid_like_trial=liquid_trial,
        ),
    )


def _summary_values(widget: ResultsTableWidget) -> dict[str, str]:
    return {
        widget.summary_table.item(row, 0).text(): widget.summary_table.item(row, 1).text()
        for row in range(widget.summary_table.rowCount())
    }


def test_main_window_round_trips_stability_analysis_units(window: PVTSimulatorWindow) -> None:
    config = _stability_config()
    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    rebuilt = window._build_config()

    assert rebuilt is not None
    assert rebuilt.stability_analysis_config is not None
    assert rebuilt.stability_analysis_config.pressure_pa == pytest.approx(
        config.stability_analysis_config.pressure_pa
    )
    assert rebuilt.stability_analysis_config.temperature_k == pytest.approx(
        config.stability_analysis_config.temperature_k
    )
    assert rebuilt.stability_analysis_config.feed_phase == config.stability_analysis_config.feed_phase
    assert rebuilt.stability_analysis_config.use_gdem == config.stability_analysis_config.use_gdem
    assert rebuilt.stability_analysis_config.n_random_trials == config.stability_analysis_config.n_random_trials
    assert rebuilt.stability_analysis_config.random_seed == config.stability_analysis_config.random_seed
    assert (
        rebuilt.stability_analysis_config.max_eos_failures_per_trial
        == config.stability_analysis_config.max_eos_failures_per_trial
    )
    assert rebuilt.stability_analysis_config.pressure_unit == config.stability_analysis_config.pressure_unit
    assert rebuilt.stability_analysis_config.temperature_unit == config.stability_analysis_config.temperature_unit
    assert window.conditions_widget.stability_pressure_edit.text() == (
        f"{pressure_from_pa(config.stability_analysis_config.pressure_pa, PressureUnit.PSIA):.6g}"
    )
    assert window.conditions_widget.stability_temperature_edit.text() == (
        f"{temperature_from_k(config.stability_analysis_config.temperature_k, TemperatureUnit.F):.6g}"
    )


def test_stability_analysis_result_widgets_surface_trial_diagnostics(app: QApplication) -> None:
    result = _stability_result()

    table = ResultsTableWidget()
    table.display_result(result)
    summary = _summary_values(table)

    assert table.composition_section.title() == "Trial Compositions"
    assert table.details_section.title() == "Trial Diagnostics"
    assert summary["Stable"] == "No"
    assert summary["Minimum TPD"] == "-2.500000e-02"
    assert summary["Phase Regime"] == "Two Phase"
    assert summary["Physical State Hint"] == "Two Phase"
    assert summary["Reference Root Used"] == "Liquid"
    assert table.composition_table.horizontalHeaderItem(1).text() == "Feed (z)"
    assert table.composition_table.horizontalHeaderItem(2).text() == "Vapor-like"
    assert table.composition_table.horizontalHeaderItem(3).text() == "Liquid-like"
    details = {
        table.details_table.item(row, 0).text(): table.details_table.item(row, 1).text()
        for row in range(table.details_table.rowCount())
    }
    assert details["Interpretation Basis"] == "Two Phase Regime"
    assert details["Hint Confidence"] == "High"
    assert details["Liquid Root Z"] == "0.120000"
    assert details["Vapor Root Z"] == "0.910000"
    assert details["Vapor-like Trial Best Seed"] == "wilson"

    text = TextOutputWidget()
    text.display_result(result)
    report = text.text.toPlainText()
    assert "Stability analysis" in report
    assert "Minimum TPD = -2.500000e-02" in report
    assert "Phase regime = two_phase" in report
    assert "Physical state hint = two_phase" in report
    assert "Hint basis = two_phase_regime" in report
    assert "Hint confidence = high" in report
    assert "Interpretation provenance" in report
    assert "Reference root used = liquid" in report
    assert "Vapor-like trial" in report
    assert "Liquid-like trial" in report
    assert "wilson" in report
    assert "transient eos failure recovered" in report

    widget = DiagnosticsWidget()
    widget.display_result(result)
    assert widget.status_label.text() == "UNSTABLE"
    assert widget.iterations_label.text() == "15"
    assert widget.residual_label.text() == "-2.50e-02"
    assert "No solver diagnostics available" not in widget.log_text.toPlainText()
    assert "Minimum TPD: -2.500000e-02" in widget.log_text.toPlainText()
    assert "Phase regime: two_phase" in widget.log_text.toPlainText()
    assert "Physical state hint: two_phase" in widget.log_text.toPlainText()
    assert "Hint basis: two_phase_regime" in widget.log_text.toPlainText()
    assert "Hint confidence: high" in widget.log_text.toPlainText()
    assert "Reference root used: liquid" in widget.log_text.toPlainText()

    plot = ResultsPlotWidget()
    if not getattr(plot, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")
    plot.display_result(result)
    assert plot.series_controls.isHidden() is True
    assert len(plot.figure.axes) == 1
    ax = plot.figure.axes[0]
    assert ax.get_ylabel() == "TPD"
    assert "Stability Analysis at" in ax.get_title()
