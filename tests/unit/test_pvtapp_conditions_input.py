"""Unit tests for pvtapp conditions input widgets."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]

from pvtapp.capabilities import (
    GUI_CALCULATION_TYPE_LABELS,
    GUI_EOS_TYPE_LABELS,
    GUI_SUPPORTED_CALCULATION_TYPES,
    GUI_SUPPORTED_EOS_TYPES,
)
from pvtapp.schemas import CalculationType, EOSType, RunConfig

try:
    from pvtapp.widgets.conditions_input import ConditionsInputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    ConditionsInputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    """Provide a QApplication for widget tests."""
    if QApplication is None or ConditionsInputWidget is None:
        pytest.skip("PySide6 is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_conditions_widget_builds_cvd_config(app: QApplication) -> None:
    """The conditions widget should build a valid CVD config."""
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.CVD)
    widget.cvd_temperature.setValue(106.85)
    widget.cvd_p_dew.setValue(56.52)
    widget.cvd_p_end.setValue(50.00)
    widget.cvd_n_steps.setValue(12)

    config = widget.get_cvd_config()

    assert config is not None
    assert config.temperature_k == pytest.approx(380.0)
    assert config.dew_pressure_pa == pytest.approx(5.652e6)
    assert config.pressure_end_pa == pytest.approx(5.0e6)
    assert config.n_steps == 12


def test_conditions_widget_rejects_invalid_cvd_pressure_range(app: QApplication) -> None:
    """The CVD form must reject dew pressures below the end pressure."""
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.CVD)
    widget.cvd_temperature.setValue(106.85)
    widget.cvd_p_dew.setValue(40.0)
    widget.cvd_p_end.setValue(50.0)

    assert widget.get_cvd_config() is None

    is_valid, message = widget.validate()
    assert is_valid is False
    assert message == "Invalid CVD conditions"


def test_conditions_widget_builds_bubble_point_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.BUBBLE_POINT)
    widget.bubble_temperature.setValue(76.85)
    widget.bubble_pressure_guess_enabled.setChecked(True)
    widget.bubble_pressure_guess.setValue(125.0)

    config = widget.get_bubble_point_config()

    assert config is not None
    assert config.temperature_k == pytest.approx(350.0)
    assert config.pressure_initial_pa == pytest.approx(1.25e7)


def test_conditions_widget_builds_dew_point_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.DEW_POINT)
    widget.dew_temperature.setValue(106.85)
    widget.dew_pressure_guess_enabled.setChecked(True)
    widget.dew_pressure_guess.setValue(210.0)

    config = widget.get_dew_point_config()

    assert config is not None
    assert config.temperature_k == pytest.approx(380.0)
    assert config.pressure_initial_pa == pytest.approx(2.10e7)


def test_conditions_widget_builds_dl_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.DL)
    widget.dl_temperature.setValue(76.85)
    widget.dl_bubble_pressure.setValue(150.0)
    widget.dl_p_end.setValue(10.0)
    widget.dl_n_steps.setValue(8)

    config = widget.get_dl_config()

    assert config is not None
    assert config.temperature_k == pytest.approx(350.0)
    assert config.bubble_pressure_pa == pytest.approx(1.5e7)
    assert config.pressure_end_pa == pytest.approx(1.0e6)
    assert config.n_steps == 8


def test_conditions_widget_builds_separator_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.SEPARATOR)
    widget.separator_reservoir_pressure.setValue(300.0)
    widget.separator_reservoir_temperature.setValue(106.85)
    widget.separator_include_stock_tank.setChecked(False)
    widget._set_separator_stage_rows(
        [
            {"name": "HP", "pressure_bar": 30.0, "temperature_c": 46.85},
            {"name": "LP", "pressure_bar": 5.0, "temperature_c": 26.85},
        ]
    )

    config = widget.get_separator_config()

    assert config is not None
    assert config.reservoir_pressure_pa == pytest.approx(3.0e7)
    assert config.reservoir_temperature_k == pytest.approx(380.0)
    assert config.include_stock_tank is False
    assert [stage.name for stage in config.separator_stages] == ["HP", "LP"]
    assert [stage.pressure_pa for stage in config.separator_stages] == pytest.approx(
        [3.0e6, 5.0e5]
    )


def test_conditions_widget_uses_explicit_eos_labels(app: QApplication) -> None:
    widget = ConditionsInputWidget()

    combo_types = [
        EOSType(widget.eos_combo.itemData(i))
        for i in range(widget.eos_combo.count())
    ]
    combo_labels = [
        widget.eos_combo.itemText(i)
        for i in range(widget.eos_combo.count())
    ]

    assert combo_types == list(GUI_SUPPORTED_EOS_TYPES)
    assert combo_labels == [
        GUI_EOS_TYPE_LABELS[eos_type]
        for eos_type in GUI_SUPPORTED_EOS_TYPES
    ]


def test_conditions_widget_only_exposes_gui_supported_types(app: QApplication) -> None:
    widget = ConditionsInputWidget()

    combo_types = [
        CalculationType(widget.calc_type_combo.itemData(i))
        for i in range(widget.calc_type_combo.count())
    ]
    combo_labels = [
        widget.calc_type_combo.itemText(i)
        for i in range(widget.calc_type_combo.count())
    ]

    assert combo_types == list(GUI_SUPPORTED_CALCULATION_TYPES)
    assert combo_labels == [
        GUI_CALCULATION_TYPE_LABELS[calc_type]
        for calc_type in GUI_SUPPORTED_CALCULATION_TYPES
    ]


def test_conditions_widget_solver_group_is_always_visible(app: QApplication) -> None:
    widget = ConditionsInputWidget()

    assert widget.solver_group.title() == "Tolerance / Solver Settings"
    assert widget.solver_group.isCheckable() is False


def test_conditions_widget_returns_enum_members_from_combo_data(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    widget.set_calculation_type(CalculationType.CVD)
    widget.set_eos_type(EOSType.PENG_ROBINSON)

    assert widget.get_calculation_type() is CalculationType.CVD
    assert widget.get_eos_type() is EOSType.PENG_ROBINSON


def test_conditions_widget_rejects_unsupported_gui_eos_type(app: QApplication) -> None:
    widget = ConditionsInputWidget()

    with pytest.raises(ValueError, match="not currently exposed in the desktop GUI"):
        widget.set_eos_type(EOSType.SRK)


def test_conditions_widget_loads_cvd_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            "calculation_type": "cvd",
            "eos_type": "peng_robinson",
            "cvd_config": {
                "temperature_k": 380.0,
                "dew_pressure_pa": 5.652e6,
                "pressure_end_pa": 5.0e6,
                "n_steps": 12,
            },
        }
    )

    widget.load_from_run_config(config)

    assert widget.get_calculation_type() == CalculationType.CVD
    assert widget.cvd_temperature.value() == pytest.approx(106.85)
    assert widget.cvd_p_dew.value() == pytest.approx(56.52)
    assert widget.cvd_p_end.value() == pytest.approx(50.0)
    assert widget.cvd_n_steps.value() == 12


def test_conditions_widget_loads_bubble_point_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            "calculation_type": "bubble_point",
            "eos_type": "peng_robinson",
            "bubble_point_config": {
                "temperature_k": 350.0,
                "pressure_initial_pa": 1.25e7,
            },
        }
    )

    widget.load_from_run_config(config)

    assert widget.get_calculation_type() == CalculationType.BUBBLE_POINT
    assert widget.bubble_temperature.value() == pytest.approx(76.85)
    assert widget.bubble_pressure_guess_enabled.isChecked() is True
    assert widget.bubble_pressure_guess.value() == pytest.approx(125.0)


def test_conditions_widget_loads_dew_point_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            "calculation_type": "dew_point",
            "eos_type": "peng_robinson",
            "dew_point_config": {
                "temperature_k": 380.0,
                "pressure_initial_pa": 2.1e7,
            },
        }
    )

    widget.load_from_run_config(config)

    assert widget.get_calculation_type() == CalculationType.DEW_POINT
    assert widget.dew_temperature.value() == pytest.approx(106.85)
    assert widget.dew_pressure_guess_enabled.isChecked() is True
    assert widget.dew_pressure_guess.value() == pytest.approx(210.0)


def test_conditions_widget_loads_dl_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
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

    widget.load_from_run_config(config)

    assert widget.get_calculation_type() == CalculationType.DL
    assert widget.dl_temperature.value() == pytest.approx(76.85)
    assert widget.dl_bubble_pressure.value() == pytest.approx(150.0)
    assert widget.dl_p_end.value() == pytest.approx(10.0)
    assert widget.dl_n_steps.value() == 8


def test_conditions_widget_loads_separator_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            "calculation_type": "separator",
            "eos_type": "peng_robinson",
            "separator_config": {
                "reservoir_pressure_pa": 3.0e7,
                "reservoir_temperature_k": 380.0,
                "include_stock_tank": False,
                "separator_stages": [
                    {"name": "HP", "pressure_pa": 3.0e6, "temperature_k": 320.0},
                    {"name": "LP", "pressure_pa": 5.0e5, "temperature_k": 300.0},
                ],
            },
        }
    )

    widget.load_from_run_config(config)

    assert widget.get_calculation_type() == CalculationType.SEPARATOR
    assert widget.separator_reservoir_pressure.value() == pytest.approx(300.0)
    assert widget.separator_reservoir_temperature.value() == pytest.approx(106.85)
    assert widget.separator_include_stock_tank.isChecked() is False
    assert widget.separator_stage_table.rowCount() == 2
    assert widget.separator_stage_table.item(0, 0).text() == "HP"
    assert float(widget.separator_stage_table.item(1, 1).text()) == pytest.approx(5.0)


def test_conditions_widget_rejects_loading_unsupported_gui_eos_run_config(app: QApplication) -> None:
    widget = ConditionsInputWidget()
    config = RunConfig.model_validate(
        {
            "composition": {"components": [{"component_id": "C1", "mole_fraction": 1.0}]},
            "calculation_type": "pt_flash",
            "eos_type": "srk",
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )

    with pytest.raises(ValueError, match="not currently exposed in the desktop GUI"):
        widget.load_from_run_config(config)
