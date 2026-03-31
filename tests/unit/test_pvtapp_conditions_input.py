"""Unit tests for pvtapp conditions input widgets."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]

from pvtapp.schemas import CalculationType

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
