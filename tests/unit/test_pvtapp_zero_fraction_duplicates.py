"""Regression tests for zero-fraction duplicate rows in the composition widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]

from pvtapp.schemas import FluidComposition

try:
    from pvtapp.widgets.composition_input import CompositionInputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    CompositionInputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if QApplication is None or CompositionInputWidget is None:
        pytest.skip("PySide6 is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def _set_row(widget: CompositionInputWidget, row: int, component_id: str, mole_fraction: float) -> None:
    combo = widget.table.cellWidget(row, 0)
    combo.setCurrentText(component_id)
    widget.table.item(row, 1).setText(f"{mole_fraction:.6f}")


def test_zero_fraction_duplicate_placeholder_rows_are_ignored_in_runtime_validation(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    widget._add_component_row("C1", 0.7)
    widget._add_component_row("C7+", 0.3)
    widget._add_component_row("C1", 0.0)

    is_valid, message = widget.validate()
    assert is_valid is True
    assert message == ""

    composition = widget.get_composition()
    assert isinstance(composition, FluidComposition)
    assert [entry.component_id for entry in composition.components] == ["C1", "C7+"]
    assert [entry.mole_fraction for entry in composition.components] == pytest.approx([0.7, 0.3])


def test_positive_fraction_duplicates_still_fail_validation(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    widget._add_component_row("C1", 0.5)
    widget._add_component_row("C1", 0.5)

    is_valid, message = widget.validate()
    assert is_valid is False
    assert "Duplicate component IDs" in message
