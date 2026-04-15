"""Regression tests for zero-fraction duplicate rows in the composition widget."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtCore import Qt, QSettings
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QLineEdit, QStyle, QStyleOptionComboBox, QStyleOptionViewItem
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]
    QLineEdit = None  # type: ignore[assignment]
    QTest = None  # type: ignore[assignment]
    QStyle = None  # type: ignore[assignment]
    QStyleOptionComboBox = None  # type: ignore[assignment]
    QStyleOptionViewItem = None  # type: ignore[assignment]
    Qt = None  # type: ignore[assignment]
    QSettings = None  # type: ignore[assignment]

from pvtapp.schemas import CalculationType, FluidComposition, PlusFractionCharacterizationPreset

try:
    from pvtapp.component_catalog import STANDARD_COMPONENTS
    from pvtapp.widgets.composition_input import (
        COMPONENT_PICKER_OPTIONS,
        COMPONENT_DROPDOWN_BUTTON_WIDTH,
        HEAVY_MODE_INLINE,
        HEAVY_MODE_PLUS,
        MOLE_FRACTION_COLUMN_MIN_WIDTH,
        CompositionInputWidget,
    )
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    COMPONENT_PICKER_OPTIONS = None  # type: ignore[assignment]
    STANDARD_COMPONENTS = None  # type: ignore[assignment]
    COMPONENT_DROPDOWN_BUTTON_WIDTH = None  # type: ignore[assignment]
    HEAVY_MODE_INLINE = None  # type: ignore[assignment]
    HEAVY_MODE_PLUS = None  # type: ignore[assignment]
    MOLE_FRACTION_COLUMN_MIN_WIDTH = None  # type: ignore[assignment]
    CompositionInputWidget = None  # type: ignore[assignment]

from pvtcore.models import resolve_component_id


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
    widget._add_component_row("C7", 0.3)
    widget._add_component_row("C1", 0.0)

    is_valid, message = widget.validate()
    assert is_valid is True
    assert message == ""

    composition = widget.get_composition()
    assert isinstance(composition, FluidComposition)
    assert [entry.component_id for entry in composition.components] == ["C1", "C7"]
    assert [entry.mole_fraction for entry in composition.components] == pytest.approx([0.7, 0.3])


def test_positive_fraction_duplicates_still_fail_validation(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    widget._add_component_row("C1", 0.5)
    widget._add_component_row("C1", 0.5)

    is_valid, message = widget.validate()
    assert is_valid is False
    assert "Duplicate component IDs" in message


def test_alias_duplicates_fail_after_canonical_resolution(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    widget._add_component_row("C4", 0.5)
    widget._add_component_row("nC4", 0.5)

    is_valid, message = widget.validate()
    assert is_valid is False
    assert "Duplicate component IDs after alias resolution" in message
    assert "C4" in message
    assert "nC4" in message


def test_unknown_component_ids_fail_widget_validation(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)

    widget._add_component_row("NOT_A_COMPONENT", 1.0)

    is_valid, message = widget.validate()
    assert is_valid is False
    assert "not found in database" in message


def test_component_picker_surfaces_special_tokens_immediately_after_c7(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("", 0.0)

    combo = widget.table.cellWidget(0, 0)
    assert combo is not None
    options = [combo.itemText(index) for index in range(combo.count())]

    assert options == list(COMPONENT_PICKER_OPTIONS)
    assert options.index("C7+") == options.index("C7") + 1
    assert options.index("PSEUDO+") == options.index("C7+") + 1


def test_selecting_c7_plus_in_main_table_activates_plus_mode_and_updates_total(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.7)
    widget._add_component_row("", 0.3)

    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("C7+")
    widget.plus_mw_edit.setText("150.0")
    widget.plus_sg_edit.setText("0.82")

    assert widget.heavy_mode.currentData() == HEAVY_MODE_PLUS
    assert widget._find_special_row(HEAVY_MODE_PLUS) == 1
    assert widget._get_sum() == pytest.approx(1.0)
    assert widget.get_components() == [("C1", pytest.approx(0.7))]


def test_plus_fraction_mode_contributes_to_total_and_returns_plus_fraction_schema(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.7)
    widget.set_calculation_type_context(CalculationType.BUBBLE_POINT)
    widget.heavy_mode.setCurrentIndex(widget.heavy_mode.findData(HEAVY_MODE_PLUS))
    widget.plus_z_edit.setText("0.3")
    widget.plus_mw_edit.setText("150.0")
    widget.plus_sg_edit.setText("0.82")

    is_valid, message = widget.validate()
    assert is_valid is True
    assert message == ""

    composition = widget.get_composition()
    assert isinstance(composition, FluidComposition)
    assert composition.plus_fraction is not None
    assert composition.plus_fraction.z_plus == pytest.approx(0.3)
    assert composition.plus_fraction.mw_plus_g_per_mol == pytest.approx(150.0)
    assert composition.plus_fraction.sg_plus_60f == pytest.approx(0.82)
    assert composition.plus_fraction.characterization_preset.value == "auto"
    assert composition.plus_fraction.resolved_characterization_preset.value == "volatile_oil"
    assert composition.plus_fraction.split_method == "pedersen"
    assert composition.plus_fraction.split_mw_model == "table"
    assert composition.plus_fraction.max_carbon_number == 20
    assert composition.plus_fraction.lumping_enabled is True
    assert composition.plus_fraction.lumping_n_groups == 6


def test_saved_feed_round_trips_c7_plus_row_cleanly(
    app: QApplication,
    tmp_path,
) -> None:
    if QSettings is None:
        pytest.skip("PySide6 is not installed in this test environment")

    settings = QSettings(str(tmp_path / "saved_plus.ini"), QSettings.Format.IniFormat)

    widget = CompositionInputWidget(settings=settings)
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.7)
    widget._add_component_row("", 0.3)
    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("C7+")
    widget.plus_mw_edit.setText("150.0")
    widget.plus_sg_edit.setText("0.82")

    assert widget._save_composition_named("GUI feed") is True

    reloaded = CompositionInputWidget(settings=settings)
    saved_index = reloaded.saved_compositions_combo.findData("GUI feed")
    assert saved_index >= 0
    reloaded.saved_compositions_combo.setCurrentIndex(saved_index)

    assert reloaded.heavy_mode.currentData() == HEAVY_MODE_PLUS
    plus_row = reloaded._find_special_row(HEAVY_MODE_PLUS)
    assert plus_row is not None
    assert reloaded._read_row_fraction(plus_row) == pytest.approx(0.3)
    assert reloaded.plus_mw_edit.text() == "150.000000"


def test_plus_fraction_mode_round_trips_advanced_characterization_fields(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.7333)
    widget.heavy_mode.setCurrentIndex(widget.heavy_mode.findData(HEAVY_MODE_PLUS))
    widget.plus_characterization_preset.setCurrentIndex(
        widget.plus_characterization_preset.findData(PlusFractionCharacterizationPreset.MANUAL)
    )
    widget.plus_label_edit.setText("C7+")
    widget.plus_cut_start_spin.setValue(7)
    widget.plus_z_edit.setText("0.2667")
    widget.plus_mw_edit.setText("119.7876")
    widget.plus_sg_edit.setText("0.82")
    widget.plus_end_spin.setValue(20)
    widget.plus_split_method.setCurrentText("lohrenz")
    widget.plus_split_mw_model.setCurrentText("table")
    widget.plus_lumping_enabled.setChecked(True)
    widget.plus_lumping_groups_spin.setValue(6)

    composition = widget.get_composition()

    assert isinstance(composition, FluidComposition)
    assert composition.plus_fraction is not None
    assert composition.plus_fraction.characterization_preset.value == "manual"
    assert composition.plus_fraction.resolved_characterization_preset is None
    assert composition.plus_fraction.max_carbon_number == 20
    assert composition.plus_fraction.split_method == "lohrenz"
    assert composition.plus_fraction.split_mw_model == "table"
    assert composition.plus_fraction.lumping_enabled is True
    assert composition.plus_fraction.lumping_n_groups == 6

    reloaded = CompositionInputWidget()
    reloaded.set_composition(composition)

    assert reloaded.heavy_mode.currentData() == HEAVY_MODE_PLUS
    assert PlusFractionCharacterizationPreset(reloaded.plus_characterization_preset.currentData()).value == "manual"
    assert reloaded.plus_split_method.currentText() == "lohrenz"
    assert reloaded.plus_split_mw_model.currentText() == "table"
    assert reloaded.plus_lumping_enabled.isChecked() is True
    assert reloaded.plus_lumping_groups_spin.value() == 6
    assert reloaded.plus_lumping_groups_spin.isEnabled() is True


def test_plus_fraction_mode_round_trips_tbp_fit_controls(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.95)
    widget.heavy_mode.setCurrentIndex(widget.heavy_mode.findData(HEAVY_MODE_PLUS))
    widget.plus_characterization_preset.setCurrentIndex(
        widget.plus_characterization_preset.findData(PlusFractionCharacterizationPreset.MANUAL)
    )
    widget.plus_cut_start_spin.setValue(7)
    widget.plus_z_edit.setText("0.05")
    widget.plus_sg_edit.setText("0.82")
    widget.plus_split_method.setCurrentText("pedersen")
    fit_index = widget.plus_pedersen_solve_ab_from.findData("fit_to_tbp")
    widget.plus_pedersen_solve_ab_from.setCurrentIndex(fit_index)
    widget._set_plus_tbp_cut_rows(
        [
            {"name": "C7", "z": 0.020, "mw": 96.0},
            {"name": "C8", "z": 0.015, "mw": 110.0},
            {"name": "C9", "z": 0.015, "mw": 124.0, "tb_k": 425.0},
        ]
    )

    composition = widget.get_composition()

    assert composition is not None
    assert composition.plus_fraction is not None
    assert composition.plus_fraction.pedersen_solve_ab_from == "fit_to_tbp"
    assert composition.plus_fraction.mw_plus_g_per_mol == pytest.approx(108.6)
    assert composition.plus_fraction.tbp_cuts is not None
    assert len(composition.plus_fraction.tbp_cuts) == 3
    assert composition.plus_fraction.tbp_cuts[2].tb_k == pytest.approx(425.0)

    reloaded = CompositionInputWidget()
    reloaded.set_composition(composition)

    assert reloaded.heavy_mode.currentData() == HEAVY_MODE_PLUS
    assert str(reloaded.plus_pedersen_solve_ab_from.currentData()) == "fit_to_tbp"
    assert reloaded.plus_tbp_fit_widget.isHidden() is False
    assert reloaded.plus_tbp_cut_table.rowCount() == 3
    assert reloaded.plus_tbp_cut_table.item(2, 0).text() == "C9"
    assert reloaded.plus_tbp_cut_table.item(2, 4).text() == "425.000000"


def test_auto_plus_fraction_policy_tracks_workflow_context(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("N2", 0.0060)
    widget._add_component_row("CO2", 0.0250)
    widget._add_component_row("C1", 0.6400)
    widget._add_component_row("C2", 0.1100)
    widget._add_component_row("C3", 0.0750)
    widget._add_component_row("iC4", 0.0250)
    widget._add_component_row("C4", 0.0250)
    widget._add_component_row("iC5", 0.0180)
    widget._add_component_row("C5", 0.0160)
    widget._add_component_row("C6", 0.0140)
    widget.heavy_mode.setCurrentIndex(widget.heavy_mode.findData(HEAVY_MODE_PLUS))
    widget.plus_z_edit.setText("0.046")
    widget.plus_mw_edit.setText("128.25512173913043")
    widget.plus_sg_edit.setText("0.7571304347826087")

    widget.set_calculation_type_context(CalculationType.DEW_POINT)
    composition = widget.get_composition()

    assert composition is not None
    assert composition.plus_fraction is not None
    assert composition.plus_fraction.resolved_characterization_preset.value == "gas_condensate"
    assert composition.plus_fraction.split_method == "pedersen"
    assert composition.plus_fraction.split_mw_model == "paraffin"
    assert composition.plus_fraction.max_carbon_number == 18
    assert composition.plus_fraction.lumping_n_groups == 2


def test_inline_pseudo_mode_returns_inline_component_schema(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.6)
    widget._add_component_row("", 0.4)
    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("PSEUDO+")
    widget.inline_name_edit.setText("PSEUDO+")
    widget.inline_mw_edit.setText("150.0")
    widget.inline_tc_edit.setText("520.0")
    widget.inline_pc_edit.setText("3500000.0")
    widget.inline_omega_edit.setText("0.45")

    is_valid, message = widget.validate()
    assert is_valid is True
    assert message == ""

    composition = widget.get_composition()
    assert isinstance(composition, FluidComposition)
    assert [entry.component_id for entry in composition.components] == ["C1", "PSEUDO_PLUS"]
    assert [entry.mole_fraction for entry in composition.components] == pytest.approx([0.6, 0.4])
    assert len(composition.inline_components) == 1
    spec = composition.inline_components[0]
    assert spec.component_id == "PSEUDO_PLUS"
    assert spec.molecular_weight_g_per_mol == pytest.approx(150.0)
    assert spec.critical_temperature_k == pytest.approx(520.0)
    assert spec.critical_pressure_pa == pytest.approx(3.5e6)


def test_inline_pseudo_uses_fixed_special_token_even_if_lower_field_is_overridden(
    app: QApplication,
) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.6)
    widget._add_component_row("", 0.4)
    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("PSEUDO+")
    widget.inline_component_id_edit.setText("nC4")
    widget.inline_name_edit.setText("bad pseudo")
    widget.inline_mw_edit.setText("150.0")
    widget.inline_tc_edit.setText("520.0")
    widget.inline_pc_edit.setText("3500000.0")
    widget.inline_omega_edit.setText("0.45")

    composition = widget.get_composition()

    assert composition is not None
    assert [entry.component_id for entry in composition.components] == ["C1", "PSEUDO_PLUS"]
    assert len(composition.inline_components) == 1
    assert composition.inline_components[0].component_id == "PSEUDO_PLUS"


def test_normalize_feed_scales_inline_pseudo_fraction(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.7)
    widget._add_component_row("", 0.4)
    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("PSEUDO+")
    widget.inline_name_edit.setText("PSEUDO+")
    widget.inline_mw_edit.setText("150.0")
    widget.inline_tc_edit.setText("520.0")
    widget.inline_pc_edit.setText("3500000.0")
    widget.inline_omega_edit.setText("0.45")

    widget._normalize()

    composition = widget.get_composition()
    assert composition is not None
    assert [entry.component_id for entry in composition.components] == ["C1", "PSEUDO_PLUS"]
    assert [entry.mole_fraction for entry in composition.components] == pytest.approx(
        [0.636364, 0.363636],
        abs=1e-6,
    )


def test_inline_pseudo_editor_collapses_redundant_identifier_rows(app: QApplication) -> None:
    widget = CompositionInputWidget()

    assert widget.inline_form.rowCount() == 5
    first_label = widget.inline_form.itemAt(0, widget.inline_form.ItemRole.LabelRole).widget()
    assert first_label is not None
    assert first_label.text() == "Label"
    assert widget.inline_component_id_edit.text() == "PSEUDO+"
    assert widget.inline_formula_edit.text() == "PSEUDO+"


def test_normalize_feed_scales_plus_fraction(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.8)
    widget._add_component_row("", 0.4)
    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("C7+")
    widget.plus_mw_edit.setText("150.0")
    widget.plus_sg_edit.setText("0.82")

    widget._normalize()

    composition = widget.get_composition()
    assert composition is not None
    assert composition.components[0].mole_fraction == pytest.approx(0.666667, abs=1e-6)
    assert composition.plus_fraction is not None
    assert composition.plus_fraction.z_plus == pytest.approx(0.333333, abs=1e-6)


def test_standard_component_picker_only_lists_resolvable_components() -> None:
    assert STANDARD_COMPONENTS is not None
    for component_id in STANDARD_COMPONENTS:
        assert resolve_component_id(component_id)


@pytest.mark.gui_contract
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


@pytest.mark.gui_contract
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


@pytest.mark.gui_contract
def test_heavy_fraction_tabs_ignore_mouse_wheel_changes(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.heavy_tabs.setCurrentIndex(1)

    class DummyWheelEvent:
        def __init__(self) -> None:
            self.ignored = False

        def ignore(self) -> None:
            self.ignored = True

    event = DummyWheelEvent()
    widget.heavy_tabs.tabBar().wheelEvent(event)

    assert event.ignored is True
    assert widget.heavy_tabs.currentIndex() == 1


@pytest.mark.gui_contract
def test_heavy_fraction_tabs_fill_width_without_scroll_buttons(app: QApplication) -> None:
    widget = CompositionInputWidget()

    assert widget.heavy_tabs.usesScrollButtons() is False
    assert widget.heavy_tabs.tabBar().expanding() is True
    assert widget.heavy_tabs.tabBar().elideMode() == Qt.TextElideMode.ElideNone


@pytest.mark.gui_contract
def test_mole_fraction_cells_are_left_aligned_like_component_names(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.123456)

    item = widget.table.item(0, 1)
    assert item is not None

    alignment = item.textAlignment()
    assert alignment & Qt.AlignmentFlag.AlignLeft
    assert alignment & Qt.AlignmentFlag.AlignVCenter


@pytest.mark.gui_contract
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
    assert "background-color: palette(base)" in editor.styleSheet()
    assert "background: transparent" not in editor.styleSheet()


@pytest.mark.gui_contract
def test_pressing_enter_in_mole_fraction_editor_advances_to_next_fraction_row(
    app: QApplication,
) -> None:
    if QTest is None:
        pytest.skip("PySide6 QtTest is not installed in this test environment")

    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.1)
    widget._add_component_row("C2", 0.2)
    widget.show()

    first_item = widget.table.item(0, 1)
    assert first_item is not None
    widget.table.setCurrentItem(first_item)
    widget.table.editItem(first_item)
    app.processEvents()

    editor = widget.table.findChild(QLineEdit)
    assert editor is not None
    editor.setText("0.300000")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    app.processEvents()

    assert widget.table.item(0, 1).text() == "0.300000"
    assert widget.table.currentRow() == 1
    assert widget.table.currentColumn() == 1
    assert widget.table.currentItem() == widget.table.item(1, 1)


@pytest.mark.gui_contract
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


@pytest.mark.gui_contract
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
    combo = widget.table.cellWidget(0, 0)
    assert combo is not None

    assert widget.table.columnWidth(0) >= max(96, combo.minimumSizeHint().width())
    assert widget.table.columnWidth(1) >= max(MOLE_FRACTION_COLUMN_MIN_WIDTH, mole_header_width)
    assert widget.table.columnWidth(0) + widget.table.columnWidth(1) >= widget.table.viewport().width() - 2


@pytest.mark.gui_contract
def test_component_dropdown_button_is_wider_without_expanding_column_excessively(app: QApplication) -> None:
    widget = CompositionInputWidget()
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.5)

    combo = widget.table.cellWidget(0, 0)
    assert combo is not None
    assert combo.objectName() == "CompositionComponentCombo"
    assert f"width: {COMPONENT_DROPDOWN_BUTTON_WIDTH}px" in combo.styleSheet()
    assert "QComboBox#CompositionComponentCombo" in combo.styleSheet()
    assert "border-radius: 0px" in combo.styleSheet()
    assert "border-top-right-radius: 0px" in combo.styleSheet()
    assert "border-bottom-right-radius: 0px" in combo.styleSheet()


@pytest.mark.gui_contract
def test_inline_pseudo_component_label_remains_fully_visible_when_table_has_spare_width(
    app: QApplication,
) -> None:
    widget = CompositionInputWidget()
    widget.resize(420, 600)
    widget.table.setRowCount(0)
    widget._add_component_row("C1", 0.6)
    widget._add_component_row("", 0.4)

    combo = widget.table.cellWidget(1, 0)
    assert combo is not None
    combo.setCurrentText("PSEUDO+")

    widget.show()
    app.processEvents()
    widget._sync_column_widths()
    app.processEvents()

    row = widget._find_special_row(HEAVY_MODE_INLINE)
    assert row is not None
    combo = widget.table.cellWidget(row, 0)
    assert combo is not None

    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    content_rect = combo.style().subControlRect(
        QStyle.ComplexControl.CC_ComboBox,
        option,
        QStyle.SubControl.SC_ComboBoxEditField,
        combo,
    )

    assert content_rect.width() >= combo.fontMetrics().horizontalAdvance(combo.currentText())
