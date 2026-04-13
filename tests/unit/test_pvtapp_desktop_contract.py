"""Desktop contract regressions for the supported pvtapp workflows."""

from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Callable

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtCore import QSettings, Qt
    from PySide6.QtWidgets import QApplication, QMessageBox
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QSettings = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QMessageBox = None  # type: ignore[assignment]

from pvtapp.assignment_case import build_assignment_desktop_preset
from pvtapp.schemas import (
    CalculationType,
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
    IterationRecord,
    RunConfig,
    RunResult,
    RunStatus,
    SeparatorResult,
    SeparatorStageResult,
    SolverDiagnostics,
)
from pvtapp.style import DEFAULT_UI_SCALE, UI_SCALE_STEP, build_cato_stylesheet, scale_metric

try:
    from pvtapp.main import PVTSimulatorWindow
    from pvtapp.widgets.diagnostics_view import DiagnosticsWidget
    from pvtapp.widgets.results_view import ResultsPlotWidget, ResultsTableWidget
    from pvtapp.widgets.run_log_view import RunLogWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    PVTSimulatorWindow = None  # type: ignore[assignment]
    DiagnosticsWidget = None  # type: ignore[assignment]
    ResultsPlotWidget = None  # type: ignore[assignment]
    ResultsTableWidget = None  # type: ignore[assignment]
    RunLogWidget = None  # type: ignore[assignment]
    TextOutputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if (
        QSettings is None
        or
        QApplication is None
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


def _bubble_point_plus_fraction_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "N2", "mole_fraction": 0.0021},
                    {"component_id": "CO2", "mole_fraction": 0.0187},
                    {"component_id": "C1", "mole_fraction": 0.3478},
                    {"component_id": "C2", "mole_fraction": 0.0712},
                    {"component_id": "C3", "mole_fraction": 0.0934},
                    {"component_id": "iC4", "mole_fraction": 0.0302},
                    {"component_id": "nC4", "mole_fraction": 0.0431},
                    {"component_id": "iC5", "mole_fraction": 0.0276},
                    {"component_id": "nC5", "mole_fraction": 0.0418},
                    {"component_id": "C6", "mole_fraction": 0.0574},
                ],
                "plus_fraction": {
                    "label": "C7+",
                    "cut_start": 7,
                    "z_plus": 0.2667,
                    "mw_plus_g_per_mol": 119.787599,
                    "sg_plus_60f": 0.82,
                    "characterization_preset": "manual",
                    "max_carbon_number": 20,
                    "split_mw_model": "table",
                    "lumping_enabled": True,
                    "lumping_n_groups": 6,
                },
            },
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 360.0,
                "pressure_initial_pa": 1.0e5,
                "pressure_unit": "bar",
                "temperature_unit": "C",
            },
        }
    )


def _inline_pseudo_bubble_point_config() -> RunConfig:
    return _run_config(
        {
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.199620},
                    {"component_id": "C2", "mole_fraction": 0.100100},
                    {"component_id": "C3", "mole_fraction": 0.185790},
                    {"component_id": "nC4", "mole_fraction": 0.090360},
                    {"component_id": "nC5", "mole_fraction": 0.188510},
                    {"component_id": "PSEUDO_PLUS", "mole_fraction": 0.235630},
                ],
                "inline_components": [
                    {
                        "component_id": "PSEUDO_PLUS",
                        "name": "Pseudo+",
                        "formula": "Pseudo+",
                        "molecular_weight_g_per_mol": 86.177000,
                        "critical_temperature_k": 507.400000,
                        "critical_pressure_pa": 3008134.215801,
                        "omega": 0.296000,
                    }
                ],
            },
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 326.76111111111106,
                "pressure_initial_pa": 1.0e7,
                "pressure_unit": "bar",
                "temperature_unit": "F",
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


def _plus_fraction_oil_composition() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0021},
            {"component_id": "CO2", "mole_fraction": 0.0187},
            {"component_id": "C1", "mole_fraction": 0.3478},
            {"component_id": "C2", "mole_fraction": 0.0712},
            {"component_id": "C3", "mole_fraction": 0.0934},
            {"component_id": "iC4", "mole_fraction": 0.0302},
            {"component_id": "nC4", "mole_fraction": 0.0431},
            {"component_id": "iC5", "mole_fraction": 0.0276},
            {"component_id": "nC5", "mole_fraction": 0.0418},
            {"component_id": "C6", "mole_fraction": 0.0574},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.2667,
            "mw_plus_g_per_mol": 119.787599,
            "sg_plus_60f": 0.82,
            "characterization_preset": "auto",
            "resolved_characterization_preset": "volatile_oil",
            "max_carbon_number": 20,
            "split_mw_model": "table",
            "lumping_enabled": True,
            "lumping_n_groups": 6,
        },
    }


def _plus_fraction_gas_composition() -> dict:
    return {
        "components": [
            {"component_id": "N2", "mole_fraction": 0.0060},
            {"component_id": "CO2", "mole_fraction": 0.0250},
            {"component_id": "C1", "mole_fraction": 0.6400},
            {"component_id": "C2", "mole_fraction": 0.1100},
            {"component_id": "C3", "mole_fraction": 0.0750},
            {"component_id": "iC4", "mole_fraction": 0.0250},
            {"component_id": "C4", "mole_fraction": 0.0250},
            {"component_id": "iC5", "mole_fraction": 0.0180},
            {"component_id": "C5", "mole_fraction": 0.0160},
            {"component_id": "C6", "mole_fraction": 0.0140},
        ],
        "plus_fraction": {
            "label": "C7+",
            "cut_start": 7,
            "z_plus": 0.0460,
            "mw_plus_g_per_mol": 128.255122,
            "sg_plus_60f": 0.757130,
            "characterization_preset": "auto",
            "resolved_characterization_preset": "gas_condensate",
            "max_carbon_number": 18,
            "split_mw_model": "paraffin",
            "lumping_enabled": True,
            "lumping_n_groups": 2,
        },
    }


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
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=5,
                final_residual=1.0e-10,
            ),
        ),
    )


def _inline_pseudo_bubble_point_result() -> RunResult:
    config = _inline_pseudo_bubble_point_config()
    return _completed_run_result(
        config,
        bubble_point_result=BubblePointResult(
            converged=True,
            pressure_pa=5.236495885582632e6,
            temperature_k=326.76111111111106,
            iterations=12,
            residual=6.16e-16,
            stable_liquid=True,
            liquid_composition={
                "C1": 0.199618,
                "C2": 0.100099,
                "C3": 0.185788,
                "nC4": 0.090359,
                "nC5": 0.188508,
                "PSEUDO_PLUS": 0.235628,
            },
            vapor_composition={
                "C1": 0.724185,
                "C2": 0.120726,
                "C3": 0.099516,
                "nC4": 0.021807,
                "nC5": 0.021056,
                "PSEUDO_PLUS": 0.012711,
            },
            k_values={
                "C1": 3.627854,
                "C2": 1.206062,
                "C3": 0.535642,
                "nC4": 0.241339,
                "nC5": 0.111696,
                "PSEUDO_PLUS": 0.053944,
            },
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=12,
                final_residual=6.16e-16,
            ),
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
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=6,
                final_residual=8.0e-11,
            ),
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
        assert actual.pt_flash_config.pressure_unit == expected.pt_flash_config.pressure_unit
        assert actual.pt_flash_config.temperature_unit == expected.pt_flash_config.temperature_unit
    elif expected.bubble_point_config is not None:
        assert actual.bubble_point_config is not None
        assert actual.bubble_point_config.temperature_k == pytest.approx(expected.bubble_point_config.temperature_k)
        assert actual.bubble_point_config.pressure_initial_pa == pytest.approx(
            expected.bubble_point_config.pressure_initial_pa
        )
        assert actual.bubble_point_config.pressure_unit == expected.bubble_point_config.pressure_unit
        assert actual.bubble_point_config.temperature_unit == expected.bubble_point_config.temperature_unit
    elif expected.dew_point_config is not None:
        assert actual.dew_point_config is not None
        assert actual.dew_point_config.temperature_k == pytest.approx(expected.dew_point_config.temperature_k)
        assert actual.dew_point_config.pressure_initial_pa == pytest.approx(
            expected.dew_point_config.pressure_initial_pa
        )
        assert actual.dew_point_config.pressure_unit == expected.dew_point_config.pressure_unit
        assert actual.dew_point_config.temperature_unit == expected.dew_point_config.temperature_unit
    elif expected.phase_envelope_config is not None:
        assert actual.phase_envelope_config is not None
        assert actual.phase_envelope_config.temperature_min_k == pytest.approx(
            expected.phase_envelope_config.temperature_min_k
        )
        assert actual.phase_envelope_config.temperature_max_k == pytest.approx(
            expected.phase_envelope_config.temperature_max_k
        )
        assert actual.phase_envelope_config.n_points == expected.phase_envelope_config.n_points
        assert actual.phase_envelope_config.tracing_method == expected.phase_envelope_config.tracing_method
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


def test_main_window_round_trips_plus_fraction_bubble_config(window: PVTSimulatorWindow) -> None:
    config = _bubble_point_plus_fraction_config()

    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    rebuilt = window._build_config()

    assert rebuilt is not None
    _assert_configs_equivalent(rebuilt, config)


def test_main_window_loads_saved_run_inputs_from_artifact(
    window: PVTSimulatorWindow,
    tmp_path: Path,
) -> None:
    config = _bubble_point_plus_fraction_config()
    run_dir = tmp_path / "saved-bubble"
    run_dir.mkdir()
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(config.model_dump(mode="json"), handle, indent=2)

    window._load_saved_run_inputs(str(run_dir))

    rebuilt = window._build_config()

    assert rebuilt is not None
    _assert_configs_equivalent(rebuilt, config)
    assert window.status_label.text() == "Loaded inputs: saved-bubble"


def test_main_window_loading_saved_run_inputs_does_not_start_calculation(
    window: PVTSimulatorWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved_config = _pt_flash_config().model_copy(update={"run_id": "saved001", "run_name": "Saved PT Flash"})
    run_dir = tmp_path / "saved-pt-flash"
    run_dir.mkdir()
    with (run_dir / "config.json").open("w", encoding="utf-8") as handle:
        json.dump(saved_config.model_dump(mode="json"), handle, indent=2)

    observed: dict[str, RunConfig] = {}

    def fake_start(config: RunConfig) -> None:
        observed["config"] = config

    monkeypatch.setattr(window, "_start_calculation", fake_start)

    window._load_saved_run_inputs(str(run_dir))

    rebuilt = window._build_config()

    assert rebuilt is not None
    _assert_configs_equivalent(rebuilt, saved_config)
    assert "config" not in observed
    assert window.status_label.text() == "Loaded inputs: Saved PT Flash"


def test_main_window_round_trips_exact_cce_schedule(window: PVTSimulatorWindow) -> None:
    config = _run_config(
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
                "pressure_points_pa": [2.0e7, 1.3e7, 2.0e6],
            },
        }
    )

    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    rebuilt = window._build_config()

    assert rebuilt is not None
    assert rebuilt.cce_config is not None
    assert rebuilt.cce_config.pressure_points_pa == pytest.approx([2.0e7, 1.3e7, 2.0e6])
    assert rebuilt.cce_config.n_steps == 3


def test_main_window_round_trips_exact_dl_schedule(window: PVTSimulatorWindow) -> None:
    config = _run_config(
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
                "pressure_points_pa": [5.0e6, 3.0e6, 1.0e6],
            },
        }
    )

    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    rebuilt = window._build_config()

    assert rebuilt is not None
    assert rebuilt.dl_config is not None
    assert rebuilt.dl_config.pressure_points_pa == pytest.approx([5.0e6, 3.0e6, 1.0e6])
    assert rebuilt.dl_config.n_steps == 4


def test_main_window_loads_assignment_case_via_generic_inputs(window: PVTSimulatorWindow) -> None:
    preset = build_assignment_desktop_preset(initials="TANS")
    config = _run_config(
        {
            "composition": preset.composition.model_dump(mode="json"),
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": preset.bubble_point_config.model_dump(mode="json"),
        }
    )

    assert hasattr(window, "_apply_assignment_case_preset") is False
    assert hasattr(window, "assignment_initials_combo") is False

    window.composition_widget.set_composition(config.composition)
    window.conditions_widget.load_from_run_config(config)

    composition = window.composition_widget.get_composition()
    assert composition is not None
    assert sum(entry.mole_fraction for entry in composition.components) == pytest.approx(1.00001)
    assert window.conditions_widget.get_calculation_type() is CalculationType.BUBBLE_POINT
    assert window.status_label.text() == "Ready"

    rebuilt = window._build_config()

    assert rebuilt is not None
    assert rebuilt.bubble_point_config is not None
    assert rebuilt.bubble_point_config.temperature_k == pytest.approx(preset.temperature_k)
    assert rebuilt.bubble_point_config.pressure_initial_pa == pytest.approx(preset.bubble_pressure_pa)


def test_main_window_round_trips_assignment_exact_schedules_via_generic_workflows(
    window: PVTSimulatorWindow,
) -> None:
    preset = build_assignment_desktop_preset(initials="TANS")
    cce_config = _run_config(
        {
            "composition": preset.composition.model_dump(mode="json"),
            "calculation_type": "cce",
            "eos_type": "peng_robinson",
            "cce_config": preset.cce_config.model_dump(mode="json"),
        }
    )

    window.composition_widget.set_composition(cce_config.composition)
    window.conditions_widget.load_from_run_config(cce_config)

    rebuilt_cce = window._build_config()

    assert rebuilt_cce is not None
    assert rebuilt_cce.cce_config is not None
    assert rebuilt_cce.cce_config.pressure_points_pa == pytest.approx(preset.cce_config.pressure_points_pa)
    assert rebuilt_cce.cce_config.n_steps == len(preset.cce_config.pressure_points_pa)
    assert window.conditions_widget.get_calculation_type() is CalculationType.CCE

    dl_config = _run_config(
        {
            "composition": preset.composition.model_dump(mode="json"),
            "calculation_type": "differential_liberation",
            "eos_type": "peng_robinson",
            "dl_config": preset.dl_config.model_dump(mode="json"),
        }
    )

    window.composition_widget.set_composition(dl_config.composition)
    window.conditions_widget.load_from_run_config(dl_config)

    rebuilt_dl = window._build_config()

    assert rebuilt_dl is not None
    assert rebuilt_dl.dl_config is not None
    assert rebuilt_dl.dl_config.pressure_points_pa == pytest.approx(preset.dl_config.pressure_points_pa)
    assert rebuilt_dl.dl_config.n_steps == len(preset.dl_config.pressure_points_pa) + 1
    assert rebuilt_dl.dl_config.bubble_pressure_pa > max(rebuilt_dl.dl_config.pressure_points_pa)
    assert window.conditions_widget.get_calculation_type() is CalculationType.DL


def test_main_window_offers_feed_normalization_instead_of_hard_failure(
    window: PVTSimulatorWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    window.conditions_widget.load_from_run_config(_pt_flash_config())
    window.composition_widget.table.setRowCount(0)
    window.composition_widget._add_component_row("C1", 0.55)
    window.composition_widget._add_component_row("C10", 0.40)

    monkeypatch.setattr(
        "pvtapp.main.QMessageBox.question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    rebuilt = window._build_config()

    assert rebuilt is not None
    assert sum(entry.mole_fraction for entry in rebuilt.composition.components) == pytest.approx(1.0)
    assert window.composition_widget.sum_label.text() == "1.000000"


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


def test_phase_envelope_plot_connects_curves_through_critical_point(app: QApplication) -> None:
    result = _phase_envelope_result()

    plot = ResultsPlotWidget()
    if not getattr(plot, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")

    plot.display_result(result)
    ax = plot.figure.axes[0]

    bubble_line = next(line for line in ax.lines if line.get_label() == "Bubble Point")
    dew_line = next(line for line in ax.lines if line.get_label() == "Dew Point")

    critical = result.phase_envelope_result.critical_point
    assert critical is not None
    crit_t = critical.temperature_k - 273.15
    crit_p = critical.pressure_pa / 1e5

    assert bubble_line.get_xdata()[-1] == pytest.approx(crit_t)
    assert bubble_line.get_ydata()[-1] == pytest.approx(crit_p)
    assert dew_line.get_xdata()[0] == pytest.approx(crit_t)
    assert dew_line.get_ydata()[0] == pytest.approx(crit_p)


def _summary_values(widget: ResultsTableWidget) -> dict[str, str]:
    return {
        widget.summary_table.item(row, 0).text(): widget.summary_table.item(row, 1).text()
        for row in range(widget.summary_table.rowCount())
    }


def test_results_table_scales_summary_columns_with_ui_zoom_without_shrinking_composition_data(
    app: QApplication,
) -> None:
    table = ResultsTableWidget()
    table.resize(340, 900)
    table.display_result(_bubble_point_result())
    table.show()
    app.processEvents()

    initial_summary_width = table.summary_table.columnWidth(0)
    initial_composition_width = table.composition_table.columnWidth(1)

    table.apply_ui_scale(DEFAULT_UI_SCALE + UI_SCALE_STEP)
    app.processEvents()

    assert table.summary_table.columnWidth(0) > initial_summary_width
    assert table.composition_table.columnWidth(1) >= initial_composition_width


def test_results_table_gives_composition_data_columns_more_room(app: QApplication) -> None:
    table = ResultsTableWidget()
    table.resize(340, 900)
    table.display_result(_inline_pseudo_bubble_point_result())
    table.show()
    app.processEvents()

    assert table.composition_table.columnWidth(0) < table.composition_table.columnWidth(1)
    assert table.composition_table.columnWidth(2) >= table.composition_table.columnWidth(1) - 4


def test_stylesheet_keeps_labels_transparent_and_combo_drop_downs_rounded() -> None:
    stylesheet = build_cato_stylesheet(scale=DEFAULT_UI_SCALE)

    assert "QLabel" in stylesheet
    assert "background: transparent;" in stylesheet
    assert "QComboBox::drop-down" in stylesheet
    assert "border-top-right-radius" in stylesheet
    assert "border-bottom-right-radius" in stylesheet
    assert "QGroupBox" in stylesheet
    assert "border: none;" in stylesheet
    assert "QTabWidget#HeavyFractionTabs::pane" in stylesheet


def test_results_tables_align_to_shared_right_edge(app: QApplication) -> None:
    table = ResultsTableWidget()
    table.resize(340, 900)
    table.display_result(_bubble_point_result())
    table.show()
    app.processEvents()
    table.apply_ui_scale(DEFAULT_UI_SCALE)
    app.processEvents()

    def _column_span(widget: ResultsTableWidget, attr: str) -> int:
        grid = getattr(widget, attr)
        return sum(grid.columnWidth(column) for column in range(grid.columnCount()))

    summary_span = _column_span(table, "summary_table")
    composition_span = _column_span(table, "composition_table")
    details_span = _column_span(table, "details_table")

    assert abs(summary_span - composition_span) <= 2
    assert abs(details_span - composition_span) <= 2


def test_pt_flash_result_widgets_honor_selected_display_units(app: QApplication) -> None:
    config = _run_config(
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
                "pressure_unit": "MPa",
                "temperature_unit": "F",
            },
        }
    )
    result = _completed_run_result(
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

    table = ResultsTableWidget()
    table.display_result(result)
    summary = _summary_values(table)

    assert summary["Pressure"] == "8.00 MPa"
    assert summary["Temperature"] == "170.33 °F"

    text = TextOutputWidget()
    text.display_result(result)
    report = text.text.toPlainText()

    assert "T = 170.330 °F" in report
    assert "P = 8.00000 MPa" in report


def test_saturation_result_widgets_honor_selected_display_units(app: QApplication) -> None:
    config = _run_config(
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
                "pressure_unit": "MPa",
                "temperature_unit": "F",
            },
        }
    )
    result = _completed_run_result(
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
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=5,
                final_residual=1.0e-10,
            ),
        ),
    )

    table = ResultsTableWidget()
    table.display_result(result)
    summary = _summary_values(table)

    assert summary["Bubble Pressure"] == "12.00 MPa"
    assert summary["Temperature"] == "170.33 °F"
    assert "Solver Status" not in summary
    assert "Final Residual" not in summary
    assert table.summary_table.item(0, 0).text() == "Bubble Pressure"

    plot = ResultsPlotWidget()
    if not getattr(plot, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")
    plot.display_result(result)
    assert plot.figure.axes[0].get_title() == "Bubble Point at 12.00 MPa"

    text = TextOutputWidget()
    text.display_result(result)
    report = text.text.toPlainText()

    assert "T = 170.330 °F" in report
    assert "Pb = 12.00000 MPa" in report


def test_saturation_result_widgets_render_plus_fraction_lump_names(app: QApplication) -> None:
    config = _bubble_point_plus_fraction_config()
    result = _completed_run_result(
        config,
        bubble_point_result=BubblePointResult(
            converged=True,
            pressure_pa=11466642.931388617,
            temperature_k=360.0,
            iterations=24,
            residual=1.0e-8,
            stable_liquid=True,
            liquid_composition={
                "N2": 0.0021,
                "CO2": 0.0187,
                "C1": 0.3478,
                "C2": 0.0712,
                "C3": 0.0934,
                "iC4": 0.0302,
                "C4": 0.0431,
                "iC5": 0.0276,
                "C5": 0.0418,
                "C6": 0.0574,
                "LUMP1_C7_C9": 0.2196,
                "LUMP2_C10_C12": 0.0351,
                "LUMP3_C13_C14": 0.0089,
                "LUMP4_C15_C16": 0.0022,
                "LUMP5_C17_C18": 0.0007,
                "LUMP6_C19_C20": 0.0002,
            },
            vapor_composition={
                "N2": 0.0073866627,
                "CO2": 0.0229572188,
                "C1": 0.7619977163,
                "C2": 0.0759257797,
                "C3": 0.0594793635,
                "iC4": 0.0135354779,
                "C4": 0.0165468784,
                "iC5": 0.0073006676,
                "C5": 0.0099363061,
                "C6": 0.0086462764,
                "LUMP1_C7_C9": 0.0147698929,
                "LUMP2_C10_C12": 0.0013765479,
                "LUMP3_C13_C14": 0.0001250000,
                "LUMP4_C15_C16": 0.0000120000,
                "LUMP5_C17_C18": 0.0000040000,
                "LUMP6_C19_C20": 0.0000012114,
            },
            k_values={
                "N2": 3.517458,
                "CO2": 1.227659,
                "C1": 2.190332,
                "C2": 1.066372,
                "C3": 0.636824,
                "iC4": 0.448194,
                "C4": 0.383918,
                "iC5": 0.264517,
                "C5": 0.237710,
                "C6": 0.150632,
                "LUMP1_C7_C9": 0.067258,
                "LUMP2_C10_C12": 0.039218,
                "LUMP3_C13_C14": 0.014045,
                "LUMP4_C15_C16": 0.005455,
                "LUMP5_C17_C18": 0.002857,
                "LUMP6_C19_C20": 0.001513,
            },
            diagnostics=SolverDiagnostics(
                status=ConvergenceStatusEnum.CONVERGED,
                iterations=24,
                final_residual=1.0e-8,
            ),
        ),
    )

    table = ResultsTableWidget()
    table.display_result(result)
    components = {
        table.composition_table.item(row, 0).text()
        for row in range(table.composition_table.rowCount())
    }

    assert "LUMP1_C7_C9" in components
    assert "LUMP2_C10_C12" in components

    text = TextOutputWidget()
    text.display_result(result)
    report = text.text.toPlainText()

    assert "C7+ characterization" in report
    assert "Manual; split MW model table, split to C20, lumping on (6 groups)" in report
    assert "LUMP1_C7_C9" in report
    assert "LUMP2_C10_C12" in report


def test_saturation_result_widgets_render_inline_pseudo_display_label(app: QApplication) -> None:
    result = _inline_pseudo_bubble_point_result()

    table = ResultsTableWidget()
    table.display_result(result)

    composition_labels = [
        table.composition_table.item(row, 0).text()
        for row in range(table.composition_table.rowCount())
    ]
    detail_labels = [
        table.details_table.item(row, 0).text()
        for row in range(table.details_table.rowCount())
    ]

    assert "Pseudo+" in composition_labels
    assert "Pseudo+" in detail_labels
    assert "PSEUDO_PLUS" not in composition_labels
    assert "PSEUDO_PLUS" not in detail_labels

    plot = ResultsPlotWidget()
    if not getattr(plot, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")
    plot.display_result(result)

    tick_labels = [tick.get_text() for tick in plot.figure.axes[0].get_xticklabels()]
    assert "Pseudo+" in tick_labels
    assert "PSEUDO_PLUS" not in tick_labels
    assert plot.figure.subplotpars.bottom <= 0.22


@pytest.mark.parametrize(
    ("config", "result", "expected_policy"),
    (
        (
            _run_config(
                {
                    "composition": _plus_fraction_gas_composition(),
                    "calculation_type": "phase_envelope",
                    "eos_type": "peng_robinson",
                    "phase_envelope_config": {
                        "temperature_min_k": 250.0,
                        "temperature_max_k": 420.0,
                        "n_points": 12,
                    },
                }
            ),
            PhaseEnvelopeResult(
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
            "Auto -> Gas Condensate",
        ),
        (
            _run_config(
                {
                    "composition": _plus_fraction_oil_composition(),
                    "calculation_type": "cce",
                    "eos_type": "peng_robinson",
                    "cce_config": {
                        "temperature_k": 360.0,
                        "pressure_start_pa": 2.0e7,
                        "pressure_end_pa": 2.0e6,
                        "n_steps": 6,
                    },
                }
            ),
            CCEResult(
                temperature_k=360.0,
                saturation_pressure_pa=1.1466642931388617e7,
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
            "Auto -> Volatile Oil",
        ),
        (
            _run_config(
                {
                    "composition": _plus_fraction_oil_composition(),
                    "calculation_type": "differential_liberation",
                    "eos_type": "peng_robinson",
                    "dl_config": {
                        "temperature_k": 360.0,
                        "bubble_pressure_pa": 1.1466642931388617e7,
                        "pressure_end_pa": 1.0e6,
                        "n_steps": 6,
                    },
                }
            ),
            DLResult(
                temperature_k=360.0,
                bubble_pressure_pa=1.1466642931388617e7,
                rsi=620.0,
                boi=1.48,
                converged=True,
                steps=[
                    DLStepResult(
                        pressure_pa=1.1466642931388617e7,
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
            "Auto -> Volatile Oil",
        ),
        (
            _run_config(
                {
                    "composition": _plus_fraction_gas_composition(),
                    "calculation_type": "cvd",
                    "eos_type": "peng_robinson",
                    "cvd_config": {
                        "temperature_k": 320.0,
                        "dew_pressure_pa": 3906.418983182879,
                        "pressure_end_pa": 1500.0,
                        "n_steps": 5,
                    },
                }
            ),
            CVDResult(
                temperature_k=320.0,
                dew_pressure_pa=3906.418983182879,
                initial_z=0.92,
                converged=True,
                steps=[
                    CVDStepResult(
                        pressure_pa=3906.418983182879,
                        liquid_dropout=0.00,
                        cumulative_gas_produced=0.00,
                        moles_remaining=1.0,
                        z_two_phase=0.92,
                    ),
                    CVDStepResult(
                        pressure_pa=1800.0,
                        liquid_dropout=0.07,
                        cumulative_gas_produced=0.20,
                        moles_remaining=0.80,
                        z_two_phase=0.86,
                    ),
                ],
            ),
            "Auto -> Gas Condensate",
        ),
        (
            _run_config(
                {
                    "composition": _plus_fraction_oil_composition(),
                    "calculation_type": "separator",
                    "eos_type": "peng_robinson",
                    "separator_config": {
                        "reservoir_pressure_pa": 2.0e7,
                        "reservoir_temperature_k": 360.0,
                        "include_stock_tank": False,
                        "separator_stages": [
                            {"pressure_pa": 3.0e6, "temperature_k": 320.0, "name": "HP"},
                            {"pressure_pa": 5.0e5, "temperature_k": 300.0, "name": "LP"},
                        ],
                    },
                }
            ),
            SeparatorResult(
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
            "Auto -> Volatile Oil",
        ),
    ),
)
def test_non_saturation_result_widgets_render_plus_fraction_policy(
    app: QApplication,
    config: RunConfig,
    result,
    expected_policy: str,
) -> None:
    payload_key = {
        "phase_envelope": "phase_envelope_result",
        "cce": "cce_result",
        "differential_liberation": "dl_result",
        "cvd": "cvd_result",
        "separator": "separator_result",
    }[config.calculation_type.value]
    run_result = _completed_run_result(config, **{payload_key: result})

    table = ResultsTableWidget()
    table.display_result(run_result)
    summary = _summary_values(table)

    assert summary["C7+ Policy"].startswith(expected_policy)

    text = TextOutputWidget()
    text.display_result(run_result)
    report = text.text.toPlainText()

    assert "C7+ characterization" in report
    assert expected_policy in report


def test_diagnostics_widget_displays_dew_point_solver_status(app: QApplication) -> None:
    result = _dew_point_result()

    widget = DiagnosticsWidget()
    widget.display_result(result)

    assert widget.status_label.text() == "CONVERGED"
    assert "No solver diagnostics available" not in widget.log_text.toPlainText()


def test_diagnostics_widget_convergence_plot_uses_integer_iteration_ticks(
    app: QApplication,
) -> None:
    result = _bubble_point_result()
    diagnostics = result.bubble_point_result.diagnostics.model_copy(
        update={
            "iteration_history": [
                IterationRecord(iteration=1, residual=1.0e-1, step_norm=0.0, damping=1.0, elapsed_ms=1.0),
                IterationRecord(iteration=2, residual=4.0e-2, step_norm=0.0, damping=1.0, elapsed_ms=2.0),
                IterationRecord(iteration=3, residual=1.0e-2, step_norm=0.0, damping=1.0, elapsed_ms=3.0),
                IterationRecord(iteration=4, residual=1.0e-12, step_norm=0.0, damping=1.0, elapsed_ms=4.0),
            ]
        }
    )
    result = result.model_copy(
        update={
            "bubble_point_result": result.bubble_point_result.model_copy(
                update={"diagnostics": diagnostics}
            )
        }
    )

    widget = DiagnosticsWidget()
    widget.display_result(result)

    ax = widget.figure.axes[0]
    visible_ticks = [tick for tick in ax.get_xticks() if 1 <= tick <= 4]
    assert visible_ticks
    assert all(float(tick).is_integer() for tick in visible_ticks)


def test_main_window_phase_envelope_view_rejects_non_envelope_plots(
    window: PVTSimulatorWindow,
) -> None:
    result = _bubble_point_result()

    assert window.results_plot._view_mode == "phase_envelope_only"
    window.results_plot.display_result(result)

    assert len(window.results_plot.figure.axes) == 1
    ax = window.results_plot.figure.axes[0]
    assert ax.get_title() == "Phase Envelope"
    assert len(ax.texts) == 1
    assert "only populated by phase-envelope runs" in ax.texts[0].get_text()


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
    initial_results_min_width = window.workspace.results_pane.minimumWidth()
    initial_text_font_size = window.text_output_widget.text.font().pointSizeF()

    window._zoom_in()

    zoomed_scale = DEFAULT_UI_SCALE + UI_SCALE_STEP
    assert window.ui_scale == pytest.approx(DEFAULT_UI_SCALE + UI_SCALE_STEP)
    assert window.progress_bar.maximumWidth() > initial_progress_width
    assert window.workspace.fixed_pane.minimumWidth() == scale_metric(
        initial_fixed_min_width,
        zoomed_scale,
        reference_scale=DEFAULT_UI_SCALE,
    )
    assert window.workspace.results_pane.minimumWidth() == scale_metric(
        initial_results_min_width,
        zoomed_scale,
        reference_scale=DEFAULT_UI_SCALE,
    )
    assert window.text_output_widget.text.font().pointSizeF() > initial_text_font_size
    assert window.status_label.text() == "Zoom: 120%"

    window._reset_zoom()

    assert window.ui_scale == pytest.approx(initial_scale)
    assert window.progress_bar.maximumWidth() == initial_progress_width
    assert window.workspace.fixed_pane.minimumWidth() == initial_fixed_min_width
    assert window.workspace.results_pane.minimumWidth() == initial_results_min_width
    assert window.text_output_widget.text.font().pointSizeF() == initial_text_font_size


def test_main_window_results_pane_title_tracks_active_calculation(
    window: PVTSimulatorWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _bubble_point_result()
    monkeypatch.setattr(window.run_log_widget, "refresh", lambda: None)

    window._on_calculation_finished(result)

    assert window.workspace.results_pane is not None
    assert window.workspace.results_pane._title_label.text() == "Bubble Point Results"
    assert window.results_table.run_id_label.text() == result.run_name
    assert window.results_report_widget.text.toPlainText().startswith("Bubble Point")


def test_main_window_logged_run_selection_populates_cached_results_sidebar(
    window: PVTSimulatorWindow,
) -> None:
    result = _inline_pseudo_bubble_point_result()

    window._on_logged_run_selected(result)

    assert window.workspace.results_pane is not None
    assert window.workspace.results_pane._title_label.text() == "Bubble Point Results"
    assert window.results_table.run_id_label.text() == result.run_name
    assert window.results_table.status_label.text() == "Cached"
    assert window.results_table.display_is_cached is True
    assert "Bubble Point" in window.results_report_widget.text.toPlainText()


def test_run_log_widget_collapses_empty_preview_until_selection(app: QApplication) -> None:
    widget = RunLogWidget()
    widget.resize(900, 700)
    widget.show()
    app.processEvents()

    widget._set_preview(None, None)
    app.processEvents()
    empty_tree_height = widget.tree.height()

    widget.preview_plot.display_result = lambda _result: None  # type: ignore[method-assign]
    widget._set_preview(Path("C:/tmp/run"), _pt_flash_result())
    app.processEvents()
    selected_tree_height = widget.tree.height()

    assert widget._preview_panel.isVisible() is True
    assert empty_tree_height > selected_tree_height
    assert "Pt Flash" in widget.preview_title.text()


def test_run_log_widget_emits_selected_result_signal(app: QApplication) -> None:
    widget = RunLogWidget()
    seen: list[object] = []
    widget.result_selected.connect(seen.append)

    widget.preview_plot.display_result = lambda _result: None  # type: ignore[method-assign]
    result = _pt_flash_result()
    widget._set_preview(Path("C:/tmp/run"), result)
    widget._set_preview(None, None)

    assert seen[0] == result
    assert seen[-1] is None


def test_run_log_widget_sorts_flat_run_list_by_clicked_header(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_a = str(Path("C:/tmp/run-a"))
    run_b = str(Path("C:/tmp/run-b"))
    run_c = str(Path("C:/tmp/run-c"))
    run_results = {
        run_a: _completed_run_result(
            _pt_flash_config().model_copy(update={"run_name": "alpha"}),
            pt_flash_result=_pt_flash_result().pt_flash_result,
        ).model_copy(update={"run_name": "alpha"}),
        run_c: _completed_run_result(
            _pt_flash_config().model_copy(update={"run_name": "charlie"}),
            pt_flash_result=_pt_flash_result().pt_flash_result,
        ).model_copy(update={"run_name": "charlie"}),
        run_b: _completed_run_result(
            _pt_flash_config().model_copy(update={"run_name": "bravo"}),
            pt_flash_result=_pt_flash_result().pt_flash_result,
        ).model_copy(update={"run_name": "bravo"}),
    }
    runs = [
        {"path": run_a},
        {"path": run_c},
        {"path": run_b},
    ]

    monkeypatch.setattr("pvtapp.widgets.run_log_view.list_runs", lambda limit=200: runs[:limit])
    monkeypatch.setattr(
        "pvtapp.widgets.run_log_view.load_run_result",
        lambda run_dir: run_results.get(str(run_dir)),
    )

    widget = RunLogWidget()
    widget.show()
    app.processEvents()

    assert widget.tree.isSortingEnabled() is False
    assert widget.tree.topLevelItemCount() == 3
    assert widget.tree.header().sortIndicatorSection() == 2
    assert widget.tree.header().sortIndicatorOrder() == Qt.SortOrder.DescendingOrder

    widget._on_header_clicked(0)
    app.processEvents()

    ordered_names = [
        widget.tree.topLevelItem(index).text(0)
        for index in range(widget.tree.topLevelItemCount())
    ]
    assert ordered_names == ["alpha", "bravo", "charlie"]


def test_run_log_widget_groups_by_test_type_and_keeps_child_sorting(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_a = str(Path("C:/tmp/run-a"))
    run_b = str(Path("C:/tmp/run-b"))
    run_c = str(Path("C:/tmp/run-c"))
    run_results = {
        run_a: _completed_run_result(
            _bubble_point_config().model_copy(update={"run_name": "charlie"}),
            bubble_point_result=_bubble_point_result().bubble_point_result,
        ).model_copy(update={"run_name": "charlie"}),
        run_b: _completed_run_result(
            _bubble_point_config().model_copy(update={"run_name": "alpha"}),
            bubble_point_result=_bubble_point_result().bubble_point_result,
        ).model_copy(update={"run_name": "alpha"}),
        run_c: _completed_run_result(
            _pt_flash_config().model_copy(update={"run_name": "bravo"}),
            pt_flash_result=_pt_flash_result().pt_flash_result,
        ).model_copy(update={"run_name": "bravo"}),
    }
    runs = [{"path": run_a}, {"path": run_b}, {"path": run_c}]

    monkeypatch.setattr("pvtapp.widgets.run_log_view.list_runs", lambda limit=200: runs[:limit])
    monkeypatch.setattr(
        "pvtapp.widgets.run_log_view.load_run_result",
        lambda run_dir: run_results.get(str(run_dir)),
    )

    widget = RunLogWidget()
    widget.show()
    app.processEvents()

    widget.group_by_combo.setCurrentText("Test Type")
    widget._on_header_clicked(0)
    app.processEvents()

    assert widget.tree.topLevelItemCount() == 2
    bubble_group = widget.tree.topLevelItem(0)
    assert bubble_group.text(0) == "Bubble Point"
    assert bubble_group.childCount() == 2
    assert bubble_group.child(0).text(0) == "alpha"
    assert bubble_group.child(1).text(0) == "charlie"


def test_main_window_disables_log_replay_actions_while_running(window: PVTSimulatorWindow) -> None:
    window.run_log_widget._set_preview(Path("C:/tmp/saved-run"), _pt_flash_result())

    assert window.run_log_widget.load_inputs_btn.isEnabled() is True

    window._set_running_state(True)

    assert window.run_log_widget.load_inputs_btn.isEnabled() is False

    window._set_running_state(False)

    assert window.run_log_widget.load_inputs_btn.isEnabled() is True


def test_main_window_log_item_click_populates_cached_results_sidebar(
    window: PVTSimulatorWindow,
    monkeypatch: pytest.MonkeyPatch,
    app: QApplication,
) -> None:
    run_dir = "C:/tmp/run-a"
    expected_run_dir = str(Path(run_dir))
    result = _inline_pseudo_bubble_point_result()

    monkeypatch.setattr("pvtapp.widgets.run_log_view.list_runs", lambda limit=200: [{"path": run_dir}])
    monkeypatch.setattr(
        "pvtapp.widgets.run_log_view.load_run_result",
        lambda run_path: result if str(run_path) == expected_run_dir else None,
    )

    window.run_log_widget.refresh()
    app.processEvents()

    assert window.run_log_widget.tree.topLevelItemCount() == 1
    item = window.run_log_widget.tree.topLevelItem(0)
    window.run_log_widget._on_item_clicked(item, 0)
    app.processEvents()

    assert window.results_table.status_label.text() == "Cached"
    assert "Bubble Point" in window.results_report_widget.text.toPlainText()


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
