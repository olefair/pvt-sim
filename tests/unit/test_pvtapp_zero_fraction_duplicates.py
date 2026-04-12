"""Regression tests for zero-fraction duplicate rows in the composition widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLineEdit, QStyleOptionViewItem
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]
    QLineEdit = None  # type: ignore[assignment]
    QStyleOptionViewItem = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]

from pvtapp.schemas import FluidComposition

try:
    from pvtapp.widgets.composition_input import (
        COMPONENT_DROPDOWN_BUTTON_WIDTH,
        MOLE_FRACTION_COLUMN_MIN_WIDTH,
        CompositionInputWidget,
    )
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    COMPONENT_DROPDOWN_BUTTON_WIDTH = None  # type: ignore[assignment]
    MOLE_FRACTION_COLUMN_MIN_WIDTH = None  # type: ignore[assignment]
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


def test_component_table_grows_to_show_new_rows_without_internal_scroll(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._sync_table_height()

    for comp_id in ["C1", "C2", "C3", "nC4", "nC5"]:
        widget._add_component_row(comp_id, 0.0)

    widget.show()
    app.processEvents()

    initial_height = widget.table.height()

    widget._add_component_row("C6", 0.0)
    app.processEvents()

    assert widget.table.rowCount() == 6
    assert widget.table.verticalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert widget.table.height() > initial_height
    assert widget.table.verticalScrollBar().maximum() == 0

    last_item = widget.table.item(widget.table.rowCount() - 1, 1)
    assert last_item is not None
    last_rect = widget.table.visualItemRect(last_item)
    assert last_rect.isValid()
    assert last_rect.bottom() <= widget.table.viewport().height()


def test_component_selector_ignores_mouse_wheel_changes(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 1.0)

    combo = widget.table.cellWidget(0, 0)
    assert combo is not None
    assert combo.currentText() == "C1"

    class DummyWheelEvent:
        def __init__(self) -> None:
            self.ignored = False

        def ignore(self) -> None:
            self.ignored = True

    event = DummyWheelEvent()
    combo.wheelEvent(event)

    assert event.ignored is True
    assert combo.currentText() == "C1"


def test_mole_fraction_cells_are_left_aligned_like_component_names(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.123456)

    item = widget.table.item(0, 1)
    assert item is not None

    alignment = item.textAlignment()
    assert alignment & Qt.AlignmentFlag.AlignLeft
    assert alignment & Qt.AlignmentFlag.AlignVCenter


def test_mole_fraction_editor_uses_compact_visible_line_edit(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.123456)

    delegate = widget.table.itemDelegateForColumn(1)
    index = widget.table.model().index(0, 1)
    option = QStyleOptionViewItem()
    option.font = widget.table.font()
    editor = delegate.createEditor(widget.table.viewport(), option, index)

    assert isinstance(editor, QLineEdit)
    assert editor.alignment() & Qt.AlignmentFlag.AlignLeft
    assert editor.alignment() & Qt.AlignmentFlag.AlignVCenter
    assert "padding: 0px" in editor.styleSheet()
    assert "border: none" in editor.styleSheet()


def test_mole_fraction_rows_scale_with_table_font(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    scaled_font = widget.table.font()
    scaled_font.setPointSizeF(max(14.0, scaled_font.pointSizeF() + 4.0))
    widget.table.setFont(scaled_font)
    widget._add_component_row("C1", 0.123456)
    widget._sync_table_height()

    row_height = widget.table.rowHeight(0)
    assert row_height >= widget.table.fontMetrics().height() + 6


def test_column_width_policy_keeps_component_readable_and_shows_full_mole_fraction_header(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.resize(360, 600)
    widget.table.setRowCount(0)
    widget._add_component_row("nC5", 0.123456)
    widget.show()
    app.processEvents()
    widget._sync_column_widths()

    header_metrics = widget.table.horizontalHeader().fontMetrics()
    mole_header_width = header_metrics.horizontalAdvance("Mole Fraction") + 16

    assert 96 <= widget.table.columnWidth(0) <= 140
    assert widget.table.columnWidth(1) >= max(MOLE_FRACTION_COLUMN_MIN_WIDTH, mole_header_width)
    assert widget.table.columnWidth(0) + widget.table.columnWidth(1) >= widget.table.viewport().width() - 2


def test_component_dropdown_button_is_wider_without_expanding_column_excessively(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.5)

    combo = widget.table.cellWidget(0, 0)
    assert combo is not None
    assert f"width: {COMPONENT_DROPDOWN_BUTTON_WIDTH}px" in combo.styleSheet()
