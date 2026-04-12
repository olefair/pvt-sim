"""Desktop contract regressions for the supported pvtapp workflows."""

from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication, QMessageBox
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QSettings = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QMessageBox = None  # type: ignore[assignment]

from pvtapp.schemas import (
    CCEResult,
    CCEStepResult,
    BubblePointResult,
    ConvergenceStatusEnum,
    CVDResult,
    CVDStepResult,
    DLResult,
    DLStepResult,
    DewPointResult,
    PhaseEnvelopePoint,
    PhaseEnvelopeResult,
    PTFlashResult,
    RunConfig,
    RunResult,
    RunStatus,
    SeparatorResult,
    SeparatorStageResult,
    SolverDiagnostics,
)
from pvtapp.style import DEFAULT_UI_SCALE, UI_SCALE_STEP

try:
    from pvtapp.main import PVTSimulatorWindow
    from pvtapp.widgets.results_view import ResultsPlotWidget, ResultsTableWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    PVTSimulatorWindow = None  # type: ignore[assignment]
    ResultsPlotWidget = None  # type: ignore[assignment]
    ResultsTableWidget = None  # type: ignore[assignment]
    TextOutputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if (
        QSettings is None
        or
        QApplication is None
        or PVTSimulatorWindow is None
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
    return tmp_path / "pvtapp-test-settings.ini"


@pytest.fixture()
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch, settings_path: Path) -> PVTSimulatorWindow:
    def _create_settings(_self) -> QSettings:
        return QSettings(str(settings_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(PVTSimulatorWindow, "_create_settings", _create_settings)
    instance = PVTSimulatorWindow()
    yield instance
    instance.close()


def _run_config(data: dict) -> RunConfig:
    return RunConfig.model_validate(data)


def _started_at() -> datetime:
    return datetime(2026, 4, 11, 9, 0, 0)


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


def _pt_flash_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.55},
                    {"component_id": "C10", "mole_fraction": 0.45},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 8.0e6,
                "temperature_k": 350.0,
            },
        }
    )


def _bubble_point_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.50},
                    {"component_id": "C10", "mole_fraction": 0.50},
                ]
            },
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 350.0,
                "pressure_initial_pa": 1.25e7,
            },
        }
    )


def _dew_point_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.85},
                    {"component_id": "C3", "mole_fraction": 0.10},
                    {"component_id": "C7", "mole_fraction": 0.05},
                ]
            },
            "calculation_type": "dew_point",
            "eos_type": "peng_robinson",
            "dew_point_config": {
                "temperature_k": 380.0,
                "pressure_initial_pa": 2.10e7,
            },
        }
    )


def _phase_envelope_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.60},
                    {"component_id": "C4", "mole_fraction": 0.25},
                    {"component_id": "C10", "mole_fraction": 0.15},
                ]
            },
            "calculation_type": "phase_envelope",
            "eos_type": "peng_robinson",
            "phase_envelope_config": {
                "temperature_min_k": 250.0,
                "temperature_max_k": 420.0,
                "n_points": 24,
            },
        }
    )


def _cce_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.70},
                    {"component_id": "C4", "mole_fraction": 0.20},
                    {"component_id": "C10", "mole_fraction": 0.10},
                ]
            },
            "calculation_type": "cce",
            "eos_type": "peng_robinson",
            "cce_config": {
                "temperature_k": 360.0,
                "pressure_start_pa": 2.0e7,
                "pressure_end_pa": 2.0e6,
                "n_steps": 6,
            },
        }
    )


def _dl_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.40},
                    {"component_id": "C3", "mole_fraction": 0.30},
                    {"component_id": "C10", "mole_fraction": 0.30},
                ]
            },
            "calculation_type": "differential_liberation",
            "eos_type": "peng_robinson",
            "dl_config": {
                "temperature_k": 350.0,
                "bubble_pressure_pa": 1.5e7,
                "pressure_end_pa": 1.0e6,
                "n_steps": 8,
            },
        }
    )


def _cvd_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.85},
                    {"component_id": "C3", "mole_fraction": 0.10},
                    {"component_id": "C7", "mole_fraction": 0.05},
                ]
            },
            "calculation_type": "cvd",
            "eos_type": "peng_robinson",
            "cvd_config": {
                "temperature_k": 380.0,
                "dew_pressure_pa": 5.652e6,
                "pressure_end_pa": 5.0e6,
                "n_steps": 5,
            },
        }
    )


def _separator_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.40},
                    {"component_id": "C4", "mole_fraction": 0.35},
                    {"component_id": "C10", "mole_fraction": 0.25},
                ]
            },
            "calculation_type": "separator",
            "eos_type": "peng_robinson",
            "separator_config": {
                "reservoir_pressure_pa": 3.0e7,
                "reservoir_temperature_k": 380.0,
                "include_stock_tank": True,
                "separator_stages": [
                    {"pressure_pa": 3.0e6, "temperature_k": 320.0, "name": "HP"},
                    {"pressure_pa": 5.0e5, "temperature_k": 300.0, "name": "LP"},
                ],
            },
        }
    )


DESKTOP_CONFIG_BUILDERS: tuple[Callable[[], RunConfig], ...] = (
    _pt_flash_config,
    _bubble_point_config,
    _dew_point_config,
    _phase_envelope_config,
    _cce_config,
    _dl_config,
    _cvd_config,
    _separator_config,
)

DESKTOP_CONFIG_IDS: tuple[str, ...] = tuple(
    builder().calculation_type.value for builder in DESKTOP_CONFIG_BUILDERS
)


def _pt_flash_result() -> RunResult:
    config = _pt_flash_config()
    return _completed_run_result(
        config,
        pt_flash_result=PTFlashResult(
            converged=True,
            phase="two-phase",
            vapor_fraction=0.35,
            liquid_composition={"C1": 0.25, "C10": 0.75},
            vapor_composition={"C1": 0.92, "C10": 0.08},
            K_values={"C1": 3.68, "C10": 0.11},
            liquid_fugacity={"C1": 1.0, "C10": 1.0},
            vapor_fugacity={"C1": 1.0, "C10": 1.0},
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=4,
                final_residual=1.0e-12,
            ),
        ),
    )


def _bubble_point_result() -> RunResult:
    config = _bubble_point_config()
    return _completed_run_result(
        config,
        bubble_point_result=BubblePointResult(
            converged=True,
            pressure_pa=1.20e7,
            temperature_k=350.0,
            iterations=5,
            residual=1.0e-10,
            stable_liquid=True,
            liquid_composition={"C1": 0.50, "C10": 0.50},
            vapor_composition={"C1": 0.88, "C10": 0.12},
            k_values={"C1": 1.76, "C10": 0.24},
        ),
    )


def _dew_point_result() -> RunResult:
    config = _dew_point_config()
    return _completed_run_result(
        config,
        dew_point_result=DewPointResult(
            converged=True,
            pressure_pa=1.95e7,
            temperature_k=380.0,
            iterations=6,
            residual=8.0e-11,
            stable_vapor=True,
            liquid_composition={"C1": 0.52, "C3": 0.28, "C7": 0.20},
            vapor_composition={"C1": 0.85, "C3": 0.10, "C7": 0.05},
            k_values={"C1": 1.63, "C3": 0.82, "C7": 0.21},
        ),
    )


def _phase_envelope_result() -> RunResult:
    config = _phase_envelope_config()
    return _completed_run_result(
        config,
        phase_envelope_result=PhaseEnvelopeResult(
            bubble_curve=[
                PhaseEnvelopePoint(temperature_k=300.0, pressure_pa=8.0e6, point_type="bubble"),
                PhaseEnvelopePoint(temperature_k=320.0, pressure_pa=7.0e6, point_type="bubble"),
            ],
            dew_curve=[
                PhaseEnvelopePoint(temperature_k=340.0, pressure_pa=6.5e6, point_type="dew"),
                PhaseEnvelopePoint(temperature_k=360.0, pressure_pa=5.5e6, point_type="dew"),
            ],
            critical_point=PhaseEnvelopePoint(temperature_k=330.0, pressure_pa=7.2e6, point_type="critical"),
        ),
    )


def _cce_result() -> RunResult:
    config = _cce_config()
    return _completed_run_result(
        config,
        cce_result=CCEResult(
            temperature_k=360.0,
            saturation_pressure_pa=1.55e7,
            steps=[
                CCEStepResult(
                    pressure_pa=2.0e7,
                    relative_volume=1.00,
                    liquid_fraction=1.0,
                    vapor_fraction=0.0,
                    z_factor=0.82,
                ),
                CCEStepResult(
                    pressure_pa=1.2e7,
                    relative_volume=1.15,
                    liquid_fraction=0.72,
                    vapor_fraction=0.28,
                    z_factor=0.91,
                ),
            ],
        ),
    )


def _dl_result() -> RunResult:
    config = _dl_config()
    return _completed_run_result(
        config,
        dl_result=DLResult(
            temperature_k=350.0,
            bubble_pressure_pa=1.5e7,
            rsi=620.0,
            boi=1.48,
            converged=True,
            steps=[
                DLStepResult(
                    pressure_pa=1.5e7,
                    rs=620.0,
                    bo=1.48,
                    bt=1.48,
                    vapor_fraction=0.0,
                    liquid_moles_remaining=1.0,
                ),
                DLStepResult(
                    pressure_pa=5.0e6,
                    rs=210.0,
                    bo=1.18,
                    bt=1.23,
                    vapor_fraction=0.28,
                    liquid_moles_remaining=0.72,
                ),
            ],
        ),
    )


def _cvd_result() -> RunResult:
    config = _cvd_config()
    return _completed_run_result(
        config,
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
                    pressure_pa=5.0e6,
                    liquid_dropout=0.07,
                    cumulative_gas_produced=0.20,
                    moles_remaining=0.80,
                    z_two_phase=0.86,
                ),
            ],
        ),
    )


def _separator_result() -> RunResult:
    config = _separator_config()
    return _completed_run_result(
        config,
        separator_result=SeparatorResult(
            bo=1.21,
            rs=145.0,
            rs_scf_stb=815.0,
            bg=0.0042,
            api_gravity=39.5,
            stock_tank_oil_density=790.0,
            converged=True,
            stages=[
                SeparatorStageResult(
                    stage_number=1,
                    stage_name="HP",
                    pressure_pa=3.0e6,
                    temperature_k=320.0,
                    vapor_fraction=0.35,
                    liquid_moles=0.65,
                    vapor_moles=0.35,
                    converged=True,
                ),
                SeparatorStageResult(
                    stage_number=2,
                    stage_name="LP",
                    pressure_pa=5.0e5,
                    temperature_k=300.0,
                    vapor_fraction=0.18,
                    liquid_moles=0.53,
                    vapor_moles=0.12,
                    converged=True,
                ),
            ],
        ),
    )


def _cancelled_result() -> RunResult:
    config = _pt_flash_config()
    return RunResult(
        run_id="cancelled-result",
        run_name="cancelled-result",
        status=RunStatus.CANCELLED,
        error_message="Calculation was cancelled by user",
        started_at=_started_at(),
        completed_at=_started_at(),
        duration_seconds=0.5,
        config=config,
    )


RESULT_BUILDERS: tuple[tuple[str, Callable[[], RunResult], str, str], ...] = (
    ("pt_flash", _pt_flash_result, "Component", "Pt Flash"),
    ("bubble_point", _bubble_point_result, "Component", "Bubble point"),
    ("dew_point", _dew_point_result, "Component", "Dew point"),
    ("phase_envelope", _phase_envelope_result, "Type", "Phase envelope"),
    ("cce", _cce_result, "Pressure (bar)", "CCE"),
    ("dl", _dl_result, "Pressure (bar)", "Differential liberation"),
    ("cvd", _cvd_result, "Pressure (bar)", "CVD"),
    ("separator", _separator_result, "Stage", "Separator train"),
)


def _assert_configs_equivalent(actual: RunConfig, expected: RunConfig) -> None:
    assert actual.calculation_type == expected.calculation_type
    assert actual.eos_type == expected.eos_type
    assert actual.composition.model_dump(mode="json") == expected.composition.model_dump(mode="json")
    assert actual.solver_settings.model_dump(mode="json") == expected.solver_settings.model_dump(mode="json")

    if expected.pt_flash_config is not None:
        assert actual.pt_flash_config is not None
        assert actual.pt_flash_config.pressure_pa == pytest.approx(expected.pt_flash_config.pressure_pa)
        assert actual.pt_flash_config.temperature_k == pytest.approx(expected.pt_flash_config.temperature_k)
    elif expected.bubble_point_config is not None:
        assert actual.bubble_point_config is not None
        assert actual.bubble_point_config.temperature_k == pytest.approx(expected.bubble_point_config.temperature_k)
        assert actual.bubble_point_config.pressure_initial_pa == pytest.approx(
            expected.bubble_point_config.pressure_initial_pa
        )
    elif expected.dew_point_config is not None:
        assert actual.dew_point_config is not None
        assert actual.dew_point_config.temperature_k == pytest.approx(expected.dew_point_config.temperature_k)
        assert actual.dew_point_config.pressure_initial_pa == pytest.approx(
            expected.dew_point_config.pressure_initial_pa
        )
    elif expected.phase_envelope_config is not None:
        assert actual.phase_envelope_config is not None
        assert actual.phase_envelope_config.temperature_min_k == pytest.approx(
            expected.phase_envelope_config.temperature_min_k
        )
        assert actual.phase_envelope_config.temperature_max_k == pytest.approx(
            expected.phase_envelope_config.temperature_max_k
        )
        assert actual.phase_envelope_config.n_points == expected.phase_envelope_config.n_points
    elif expected.cce_config is not None:
        assert actual.cce_config is not None
        assert actual.cce_config.temperature_k == pytest.approx(expected.cce_config.temperature_k)
        assert actual.cce_config.pressure_start_pa == pytest.approx(expected.cce_config.pressure_start_pa)
        assert actual.cce_config.pressure_end_pa == pytest.approx(expected.cce_config.pressure_end_pa)
        assert actual.cce_config.n_steps == expected.cce_config.n_steps
    elif expected.dl_config is not None:
        assert actual.dl_config is not None
        assert actual.dl_config.temperature_k == pytest.approx(expected.dl_config.temperature_k)
        assert actual.dl_config.bubble_pressure_pa == pytest.approx(expected.dl_config.bubble_pressure_pa)
        assert actual.dl_config.pressure_end_pa == pytest.approx(expected.dl_config.pressure_end_pa)
        assert actual.dl_config.n_steps == expected.dl_config.n_steps
    elif expected.cvd_config is not None:
        assert actual.cvd_config is not None
        assert actual.cvd_config.temperature_k == pytest.approx(expected.cvd_config.temperature_k)
        assert actual.cvd_config.dew_pressure_pa == pytest.approx(expected.cvd_config.dew_pressure_pa)
        assert actual.cvd_config.pressure_end_pa == pytest.approx(expected.cvd_config.pressure_end_pa)
        assert actual.cvd_config.n_steps == expected.cvd_config.n_steps
    elif expected.separator_config is not None:
        assert actual.separator_config is not None
        assert actual.separator_config.reservoir_pressure_pa == pytest.approx(
            expected.separator_config.reservoir_pressure_pa
        )
        assert actual.separator_config.reservoir_temperature_k == pytest.approx(
            expected.separator_config.reservoir_temperature_k
        )
        assert actual.separator_config.include_stock_tank == expected.separator_config.include_stock_tank
        assert len(actual.separator_config.separator_stages) == len(expected.separator_config.separator_stages)
        for actual_stage, expected_stage in zip(
            actual.separator_config.separator_stages,
            expected.separator_config.separator_stages,
            strict=True,
        ):
            assert actual_stage.name == expected_stage.name
            assert actual_stage.pressure_pa == pytest.approx(expected_stage.pressure_pa)
            assert actual_stage.temperature_k == pytest.approx(expected_stage.temperature_k)
    else:
        raise AssertionError("Expected config did not include a calculation-specific payload")


@pytest.mark.parametrize(
    "builder",
    DESKTOP_CONFIG_BUILDERS,
    ids=DESKTOP_CONFIG_IDS,
)
def test_main_window_builds_all_supported_desktop_configs(
    window: PVTSimulatorWindow,
    builder: Callable[[], RunConfig],
) -> None:
    config = builder()

    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    rebuilt = window._build_config()

    assert rebuilt is not None
    _assert_configs_equivalent(rebuilt, config)


@pytest.mark.parametrize(
    ("name", "builder", "expected_header", "expected_text"),
    RESULT_BUILDERS,
)
def test_desktop_result_widgets_render_supported_results(
    app: QApplication,
    name: str,
    builder: Callable[[], RunResult],
    expected_header: str,
    expected_text: str,
) -> None:
    result = builder()

    table = ResultsTableWidget()
    table.display_result(result)
    assert table.summary_table.rowCount() > 0
    assert table.composition_table.rowCount() > 0
    assert table.composition_table.horizontalHeaderItem(0).text() == expected_header

    plot = ResultsPlotWidget()
    if not getattr(plot, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")
    plot.display_result(result)
    assert len(plot.figure.axes) >= 1

    text = TextOutputWidget()
    text.display_result(result)
    assert expected_text in text.text.toPlainText()


@pytest.mark.parametrize(
    ("name", "builder", "expected_header", "expected_cell"),
    (
        ("pt_flash", _pt_flash_result, "Component", "C1"),
        ("bubble_point", _bubble_point_result, "Component", "C1"),
        ("dew_point", _dew_point_result, "Component", "C1"),
        ("phase_envelope", _phase_envelope_result, "Type", "bubble"),
        ("cce", _cce_result, "Pressure_bar", "200.0"),
        ("dl", _dl_result, "Pressure_bar", "150.0"),
        ("cvd", _cvd_result, "Pressure_bar", "56.52"),
        ("separator", _separator_result, "Stage", "HP"),
    ),
)
def test_main_window_exports_csv_for_supported_results(
    window: PVTSimulatorWindow,
    tmp_path: Path,
    name: str,
    builder: Callable[[], RunResult],
    expected_header: str,
    expected_cell: str,
) -> None:
    result = builder()
    filename = tmp_path / f"{name}.csv"

    window._export_csv(result, str(filename))

    assert filename.exists()
    with filename.open("r", newline="") as handle:
        rows = list(csv.reader(handle))

    assert rows[0][0] == expected_header
    assert any(expected_cell in cell for row in rows[1:] for cell in row)


def test_main_window_rejects_csv_export_for_cancelled_results(
    window: PVTSimulatorWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    filename = tmp_path / "cancelled.csv"
    warnings: list[tuple[str, str]] = []

    def fake_warning(_parent, title: str, message: str):
        warnings.append((title, message))
        return QMessageBox.StandardButton.Ok

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)

    window._export_csv(_cancelled_result(), str(filename))

    assert warnings == [("Export Error", "CSV export is only available for completed calculations")]
    assert not filename.exists()


def test_main_window_zoom_controls_rescale_shell(window: PVTSimulatorWindow) -> None:
    initial_scale = window.ui_scale
    initial_progress_width = window.progress_bar.maximumWidth()
    initial_fixed_min_width = window.workspace.fixed_pane.minimumWidth()

    window._zoom_in()

    assert window.ui_scale == pytest.approx(DEFAULT_UI_SCALE + UI_SCALE_STEP)
    assert window.progress_bar.maximumWidth() > initial_progress_width
    assert window.workspace.fixed_pane.minimumWidth() > initial_fixed_min_width
    assert window.status_label.text() == "Zoom: 120%"

    window._reset_zoom()

    assert window.ui_scale == pytest.approx(initial_scale)
    assert window.progress_bar.maximumWidth() == initial_progress_width
    assert window.workspace.fixed_pane.minimumWidth() == initial_fixed_min_width


def test_main_window_restores_persisted_zoom_between_sessions(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    settings_path: Path,
) -> None:
    def _create_settings(_self) -> QSettings:
        return QSettings(str(settings_path), QSettings.Format.IniFormat)

    monkeypatch.setattr(PVTSimulatorWindow, "_create_settings", _create_settings)

    first = PVTSimulatorWindow()
    try:
        first._zoom_in()
        first._zoom_in()
        assert first.ui_scale == pytest.approx(DEFAULT_UI_SCALE + (2 * UI_SCALE_STEP))
    finally:
        first.close()

    second = PVTSimulatorWindow()
    try:
        assert second.ui_scale == pytest.approx(DEFAULT_UI_SCALE + (2 * UI_SCALE_STEP))
    finally:
        second.close()
