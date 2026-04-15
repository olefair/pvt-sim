"""Composition input widget with validation and normalization.

Provides a spreadsheet-like interface for entering fluid compositions
with strict validation ensuring mole fractions sum to 1.0.
"""

import json
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSettings, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtWidgets import (
    QAbstractItemDelegate,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGridLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QMessageBox,
    QGroupBox,
    QSizePolicy,
    QInputDialog,
    QLineEdit,
    QStyledItemDelegate,
    QCheckBox,
)

from pvtapp import __app_name__
from pvtapp.component_catalog import DEFAULT_COMPONENT_ROWS, STANDARD_COMPONENTS
from pvtapp.plus_fraction_policy import (
    PLUS_FRACTION_PRESET_LABELS,
    PLUS_FRACTION_PRESET_SETTINGS,
    describe_plus_fraction_policy,
    resolve_plus_fraction_entry,
)
from pvtapp.schemas import (
    CalculationType,
    COMPOSITION_SUM_TOLERANCE,
    ComponentEntry,
    FluidComposition,
    InlineComponentSpec,
    PlusFractionEntry,
    PlusFractionCharacterizationPreset,
    PressureUnit,
    TemperatureUnit,
    pressure_from_pa,
    pressure_to_pa,
    temperature_from_k,
    temperature_to_k,
)
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.combo_box import NoWheelComboBox, NoWheelSpinBox, NoWheelTabWidget
from pvtcore.models import resolve_component_id

COMPONENT_DROPDOWN_BUTTON_WIDTH = 34
COMPONENT_COLUMN_SIDE_MARGIN = 6
COMPONENT_COLUMN_MIN_WIDTH = 96
COMPONENT_COLUMN_MAX_WIDTH = 140
MOLE_FRACTION_COLUMN_MIN_WIDTH = 108
PLUS_FRACTION_TOKEN = "C7+"
INLINE_PSEUDO_TOKEN = "PSEUDO_PLUS"
INLINE_PSEUDO_LABEL = "PSEUDO+"
HEAVY_MODE_NONE = "none"
HEAVY_MODE_PLUS = "plus_fraction"
HEAVY_MODE_INLINE = "inline_pseudo"
SAVED_COMPOSITIONS_SETTINGS_KEY = "feeds/saved_compositions"
SETTINGS_ORGANIZATION = "PVT-SIM"
SPECIAL_ROLE_BY_TOKEN = {
    PLUS_FRACTION_TOKEN: HEAVY_MODE_PLUS,
    INLINE_PSEUDO_TOKEN: HEAVY_MODE_INLINE,
}
SPECIAL_TOKEN_BY_ROLE = {
    HEAVY_MODE_PLUS: PLUS_FRACTION_TOKEN,
    HEAVY_MODE_INLINE: INLINE_PSEUDO_TOKEN,
}
SPECIAL_DISPLAY_BY_TOKEN = {
    PLUS_FRACTION_TOKEN: PLUS_FRACTION_TOKEN,
    INLINE_PSEUDO_TOKEN: INLINE_PSEUDO_LABEL,
}
SPECIAL_TOKEN_BY_DISPLAY = {
    PLUS_FRACTION_TOKEN: PLUS_FRACTION_TOKEN,
    INLINE_PSEUDO_LABEL: INLINE_PSEUDO_TOKEN,
}

_COMPONENT_PICKER_OPTIONS = list(STANDARD_COMPONENTS)
try:
    _c7_index = _COMPONENT_PICKER_OPTIONS.index("C7") + 1
except ValueError:
    _c7_index = len(_COMPONENT_PICKER_OPTIONS)
_COMPONENT_PICKER_OPTIONS.insert(_c7_index, PLUS_FRACTION_TOKEN)
_COMPONENT_PICKER_OPTIONS.insert(_c7_index + 1, INLINE_PSEUDO_LABEL)
COMPONENT_PICKER_OPTIONS = tuple(_COMPONENT_PICKER_OPTIONS)


class ClickSelectComboBox(NoWheelComboBox):
    """Combo box that ignores mouse-wheel changes.

    This prevents accidental component changes when the cursor happens to be
    hovering over an already selected component while the user is trying to
    scroll the surrounding inputs panel.
    """

    def __init__(self, parent: Optional[QWidget] = None, *, ui_scale: float = DEFAULT_UI_SCALE) -> None:
        super().__init__(parent)
        self.setObjectName("CompositionComponentCombo")
        self.apply_ui_scale(ui_scale)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Update the drop-down affordance to match the active UI scale."""
        dropdown_width = scale_metric(
            COMPONENT_DROPDOWN_BUTTON_WIDTH,
            ui_scale,
            reference_scale=DEFAULT_UI_SCALE,
        )
        self.setStyleSheet(
            "QComboBox#CompositionComponentCombo {"
            f" padding-right: {dropdown_width + 4}px;"
            " border-radius: 0px;"
            " border-top-left-radius: 0px;"
            " border-bottom-left-radius: 0px;"
            " border-top-right-radius: 0px;"
            " border-bottom-right-radius: 0px;"
            "}"
            f"QComboBox#CompositionComponentCombo::drop-down {{ "
            f"subcontrol-origin: padding; "
            f"subcontrol-position: top right; "
            f"width: {dropdown_width}px; "
            f"border: none; "
            f"background: transparent; "
            f"border-top-right-radius: 0px; "
            f"border-bottom-right-radius: 0px; "
            f"}}"
        )

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()


class CompactTabWidget(NoWheelTabWidget):
    """Tab widget that sizes itself to the currently visible tab page."""

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        current = self.currentWidget()
        if current is None:
            return base
        current_hint = current.sizeHint()
        tab_bar_hint = self.tabBar().sizeHint()
        height = tab_bar_hint.height() + current_hint.height() + scale_metric(8, DEFAULT_UI_SCALE)
        width = max(base.width(), current_hint.width(), tab_bar_hint.width())
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        base = super().minimumSizeHint()
        current = self.currentWidget()
        if current is None:
            return base
        current_hint = current.minimumSizeHint()
        tab_bar_hint = self.tabBar().minimumSizeHint()
        height = tab_bar_hint.height() + current_hint.height() + scale_metric(8, DEFAULT_UI_SCALE)
        width = max(base.width(), current_hint.width(), tab_bar_hint.width())
        return QSize(width, height)


class MoleFractionItemDelegate(QStyledItemDelegate):
    """Compact table-cell editor for mole fractions.

    Prevents the global rounded/padded QLineEdit style from clipping the text
    inside a table row when the user edits a mole-fraction value.
    """

    @staticmethod
    def _horizontal_padding_for_font_height(font_height: int) -> int:
        return max(2, int(round(font_height * 0.25)))

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setFrame(False)
        editor.setFont(option.font)
        editor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        editor.setAutoFillBackground(True)
        editor.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

        font_height = max(editor.fontMetrics().height(), option.fontMetrics.height())
        horizontal_padding = self._horizontal_padding_for_font_height(font_height)
        editor.setTextMargins(horizontal_padding + 2, 0, horizontal_padding, 0)
        editor.setStyleSheet(
            "padding: 0px;"
            "margin: 0px;"
            "border: none;"
            "border-radius: 0px;"
            "background-color: palette(base);"
            "color: palette(text);"
            "selection-background-color: palette(highlight);"
            "selection-color: palette(highlighted-text);"
        )
        editor.returnPressed.connect(lambda row=index.row(), column=index.column(), widget=editor: self._commit_and_move_down(widget, row, column))
        return editor

    def updateEditorGeometry(self, editor, option, index) -> None:
        rect = option.rect.adjusted(2, 1, -2, -1)
        editor.setGeometry(rect)

    def _commit_and_move_down(self, editor: QLineEdit, row: int, column: int) -> None:
        self.commitData.emit(editor)
        self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)

        if column != 1:
            return

        table = self.parent()
        if not isinstance(table, QTableWidget):
            return

        next_row = row + 1
        if next_row >= table.rowCount():
            return

        def activate_next_row() -> None:
            next_item = table.item(next_row, column)
            if next_item is None:
                return
            table.setCurrentCell(next_row, column)
            table.editItem(next_item)

        QTimer.singleShot(0, activate_next_row)


class CompositionInputWidget(QWidget):
    """Widget for entering and validating fluid composition.

    Signals:
        composition_changed: Emitted when valid composition is entered
        validation_error: Emitted with error message when validation fails
    """

    composition_changed = Signal(object)  # FluidComposition
    # Emitted whenever the table contents change (even if invalid).
    # Useful for updating derived views like critical props / BIPs.
    composition_edited = Signal()
    validation_error = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        settings: Optional[QSettings] = None,
    ):
        super().__init__(parent)
        self._ui_scale = DEFAULT_UI_SCALE
        self._calculation_type_context = CalculationType.PT_FLASH
        self._settings = settings or QSettings(SETTINGS_ORGANIZATION, __app_name__)
        self._saved_compositions: Dict[str, dict] = {}
        self._loading_saved_composition = False
        self._syncing_special_rows = False
        self._setup_ui()
        self._connect_signals()
        self._load_saved_compositions()

        # Add default components
        self._add_default_components()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box for composition
        group = QGroupBox("Fluid Composition")
        group_layout = QVBoxLayout(group)

        saved_feed_row = QHBoxLayout()
        saved_feed_row.addWidget(QLabel("Saved Feed:"))
        self.saved_compositions_combo = NoWheelComboBox()
        self.saved_compositions_combo.addItem("Current Feed", None)
        saved_feed_row.addWidget(self.saved_compositions_combo, 1)
        group_layout.addLayout(saved_feed_row)

        saved_actions_row = QHBoxLayout()
        self.save_feed_btn = QPushButton("Save Current")
        self.delete_feed_btn = QPushButton("Delete Saved")
        self.delete_feed_btn.setEnabled(False)
        saved_actions_row.addWidget(self.save_feed_btn)
        saved_actions_row.addWidget(self.delete_feed_btn)
        saved_actions_row.addStretch()
        group_layout.addLayout(saved_actions_row)

        # Component table
        self.table = QTableWidget()
        self.table.setObjectName("CompositionInputTable")
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Component", "Mole Fraction"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.table.setItemDelegateForColumn(1, MoleFractionItemDelegate(self.table))
        group_layout.addWidget(self.table)
        self._sync_column_widths()

        # Button grid
        self.add_btn = QPushButton("Add Component")
        self.remove_btn = QPushButton("Remove Selected")
        self.normalize_btn = QPushButton("Normalize Feed")
        self.clear_btn = QPushButton("Clear All")

        button_layout = QGridLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setHorizontalSpacing(8)
        button_layout.setVerticalSpacing(8)
        button_layout.addWidget(self.add_btn, 0, 0)
        button_layout.addWidget(self.remove_btn, 0, 1)
        button_layout.addWidget(self.normalize_btn, 1, 0)
        button_layout.addWidget(self.clear_btn, 1, 1)
        button_layout.setColumnStretch(0, 1)
        button_layout.setColumnStretch(1, 1)
        group_layout.addLayout(button_layout)

        # Sum display
        sum_layout = QHBoxLayout()
        sum_layout.addWidget(QLabel("Total:"))
        self.sum_label = QLabel("0.000000")
        self.sum_label.setStyleSheet("font-weight: bold;")
        sum_layout.addWidget(self.sum_label)
        self.sum_status = QLabel("")
        sum_layout.addWidget(self.sum_status)
        sum_layout.addStretch()

        group_layout.addLayout(sum_layout)

        layout.addWidget(group)

        heavy_group = QGroupBox("Heavy Fraction / Inline Pseudo")
        heavy_layout = QVBoxLayout(heavy_group)
        self.heavy_mode = NoWheelComboBox()
        self.heavy_mode.addItem("None", HEAVY_MODE_NONE)
        self.heavy_mode.addItem("Plus Fraction", HEAVY_MODE_PLUS)
        self.heavy_mode.addItem("Inline Pseudo", HEAVY_MODE_INLINE)
        self.heavy_tabs = CompactTabWidget()
        self.heavy_tabs.setObjectName("HeavyFractionTabs")
        self.heavy_tabs.setUsesScrollButtons(False)
        self.heavy_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.heavy_tabs.setDocumentMode(True)
        self.heavy_tabs.tabBar().setExpanding(True)
        self.heavy_tabs.tabBar().setElideMode(Qt.TextElideMode.ElideNone)
        self.heavy_tabs.tabBar().setObjectName("HeavyFractionTabBar")
        self.heavy_tabs.tabBar().setDrawBase(False)
        self.heavy_tabs.addTab(QWidget(), "None")

        plus_page = QWidget()
        plus_form = QFormLayout(plus_page)
        self.plus_form = plus_form
        self._configure_form_layout(plus_form)
        self.plus_label_edit = QLineEdit(PLUS_FRACTION_TOKEN)
        self.plus_cut_start_spin = NoWheelSpinBox()
        self.plus_cut_start_spin.setRange(1, 200)
        self.plus_cut_start_spin.setValue(7)
        self.plus_z_edit = self._create_float_edit()
        self.plus_mw_edit = self._create_float_edit()
        self.plus_sg_edit = self._create_float_edit()
        self.plus_characterization_preset = NoWheelComboBox()
        for preset in [
            PlusFractionCharacterizationPreset.AUTO,
            PlusFractionCharacterizationPreset.MANUAL,
            PlusFractionCharacterizationPreset.DRY_GAS,
            PlusFractionCharacterizationPreset.CO2_RICH_GAS,
            PlusFractionCharacterizationPreset.GAS_CONDENSATE,
            PlusFractionCharacterizationPreset.VOLATILE_OIL,
            PlusFractionCharacterizationPreset.BLACK_OIL,
            PlusFractionCharacterizationPreset.SOUR_OIL,
        ]:
            self.plus_characterization_preset.addItem(PLUS_FRACTION_PRESET_LABELS[preset], preset)
        self.plus_characterization_summary = QLabel()
        self.plus_characterization_summary.setWordWrap(True)
        self.plus_characterization_summary.setStyleSheet("color: #9ca3af;")
        self.plus_end_spin = NoWheelSpinBox()
        self.plus_end_spin.setRange(1, 200)
        self.plus_end_spin.setValue(45)
        self.plus_split_method = NoWheelComboBox()
        self.plus_split_method.addItems(["pedersen", "katz", "lohrenz"])
        self.plus_split_method.setCurrentText("pedersen")
        self.plus_split_mw_model = NoWheelComboBox()
        self.plus_split_mw_model.addItems(["paraffin", "table"])
        self.plus_split_mw_model.setCurrentText("paraffin")
        self.plus_lumping_enabled = QCheckBox("Enable lumping")
        self.plus_lumping_groups_spin = NoWheelSpinBox()
        self.plus_lumping_groups_spin.setRange(1, 200)
        self.plus_lumping_groups_spin.setValue(8)
        plus_form.addRow("Cut Start", self.plus_cut_start_spin)
        plus_form.addRow("MW+ (g/mol)", self.plus_mw_edit)
        plus_form.addRow("SG+ @60F", self.plus_sg_edit)
        plus_form.addRow("Characterization", self.plus_characterization_preset)
        plus_form.addRow("Resolved", self.plus_characterization_summary)
        plus_form.addRow("Split To", self.plus_end_spin)
        plus_form.addRow("Split Method", self.plus_split_method)
        plus_form.addRow("Split MW Model", self.plus_split_mw_model)
        plus_form.addRow("Lumping", self.plus_lumping_enabled)
        plus_form.addRow("Lumping Groups", self.plus_lumping_groups_spin)
        self.heavy_tabs.addTab(plus_page, "Plus Fraction")

        inline_page = QWidget()
        inline_form = QFormLayout(inline_page)
        self.inline_form = inline_form
        self._configure_form_layout(inline_form)
        self.inline_component_id_edit = QLineEdit(INLINE_PSEUDO_LABEL)
        self.inline_component_id_edit.setReadOnly(True)
        self.inline_name_edit = QLineEdit(INLINE_PSEUDO_LABEL)
        self.inline_formula_edit = QLineEdit(INLINE_PSEUDO_LABEL)
        self.inline_z_edit = self._create_float_edit()
        self.inline_mw_edit = self._create_float_edit()
        self.inline_tc_edit = self._create_float_edit()
        self.inline_tc_unit = NoWheelComboBox()
        self.inline_tc_unit.addItems([unit.value for unit in TemperatureUnit])
        self.inline_tc_unit.setCurrentText(TemperatureUnit.K.value)
        self.inline_pc_edit = self._create_float_edit()
        self.inline_pc_unit = NoWheelComboBox()
        self.inline_pc_unit.addItems([unit.value for unit in PressureUnit])
        self.inline_pc_unit.setCurrentText(PressureUnit.PA.value)
        self.inline_omega_edit = self._create_float_edit()

        inline_tc_row = QHBoxLayout()
        self._configure_unit_row(inline_tc_row, self.inline_tc_edit, self.inline_tc_unit)

        inline_pc_row = QHBoxLayout()
        self._configure_unit_row(inline_pc_row, self.inline_pc_edit, self.inline_pc_unit)

        inline_form.addRow("Label", self.inline_name_edit)
        inline_form.addRow("MW (g/mol)", self.inline_mw_edit)
        inline_form.addRow("Tc", inline_tc_row)
        inline_form.addRow("Pc", inline_pc_row)
        inline_form.addRow("Omega", self.inline_omega_edit)
        self.heavy_tabs.addTab(inline_page, "Inline Pseudo")

        heavy_layout.addWidget(self.heavy_tabs)
        layout.addWidget(heavy_group)

        self._sync_heavy_tab_spacing()
        self._on_heavy_mode_changed()
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()

    @staticmethod
    def _configure_form_layout(layout: QFormLayout) -> None:
        """Tune form rows for the stable-width inputs rail."""
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

    @staticmethod
    def _configure_unit_row(layout: QHBoxLayout, field: QWidget, unit_widget: QWidget) -> None:
        """Give inline unit rows stable proportions in the narrow sidebar."""
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        unit_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        unit_widget.setProperty("sidebar_unit_widget", True)
        if hasattr(unit_widget, "setMaximumWidth"):
            unit_widget.setMaximumWidth(96)
        layout.addWidget(field, 1)
        layout.addWidget(unit_widget, 0)

    def _create_float_edit(self) -> QLineEdit:
        """Create a numeric line edit used by the heavy-end controls."""
        edit = QLineEdit()
        validator = QDoubleValidator(edit)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        edit.setValidator(validator)
        return edit

    def _get_heavy_mode(self) -> str:
        return str(self.heavy_mode.currentData())

    def _on_heavy_tab_changed(self, index: int) -> None:
        """Mirror the visible heavy-end tab into the existing mode state."""
        mode_by_index = {
            0: HEAVY_MODE_NONE,
            1: HEAVY_MODE_PLUS,
            2: HEAVY_MODE_INLINE,
        }
        mode = mode_by_index.get(index, HEAVY_MODE_NONE)
        combo_index = self.heavy_mode.findData(mode)
        if combo_index >= 0 and combo_index != self.heavy_mode.currentIndex():
            self.heavy_mode.setCurrentIndex(combo_index)
        self.heavy_tabs.updateGeometry()
        self.updateGeometry()

    def _on_heavy_mode_changed(self, *_args) -> None:
        """Switch the visible heavy-end editor and refresh validation state."""
        previous_plus = self._find_special_row(HEAVY_MODE_PLUS)
        previous_inline = self._find_special_row(HEAVY_MODE_INLINE)
        mode = self._get_heavy_mode()
        target_index = {
            HEAVY_MODE_NONE: 0,
            HEAVY_MODE_PLUS: 1,
            HEAVY_MODE_INLINE: 2,
        }.get(mode, 0)
        if self.heavy_tabs.currentIndex() != target_index:
            self.heavy_tabs.blockSignals(True)
            self.heavy_tabs.setCurrentIndex(target_index)
            self.heavy_tabs.blockSignals(False)
        if mode == HEAVY_MODE_PLUS:
            self._ensure_plus_fraction_row()
            self._sync_plus_fraction_row_from_fields()
        elif previous_plus is not None:
            self._sync_plus_fraction_fields_from_row()
            self._remove_special_row(HEAVY_MODE_PLUS)
        if mode == HEAVY_MODE_INLINE:
            self._ensure_inline_pseudo_row()
            self._sync_inline_pseudo_row_from_fields()
        elif previous_inline is not None:
            self._sync_inline_fraction_fields_from_row()
            self._remove_special_row(HEAVY_MODE_INLINE)
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()
        self._update_sum()
        self.heavy_tabs.updateGeometry()
        self.updateGeometry()
        self.composition_edited.emit()

    def _sync_plus_lumping_state(self, *_args) -> None:
        """Enable the lump-group control only when plus-fraction lumping is active."""
        preset = self._current_plus_characterization_preset()
        enabled = (
            self._get_heavy_mode() == HEAVY_MODE_PLUS
            and preset is PlusFractionCharacterizationPreset.MANUAL
            and self.plus_lumping_enabled.isChecked()
        )
        self.plus_lumping_groups_spin.setEnabled(enabled)

    def _find_special_row(self, role: str) -> Optional[int]:
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget is not None and widget.property("special_role") == role:
                return row
        return None

    def _row_is_special(self, row: int, role: Optional[str] = None) -> bool:
        widget = self.table.cellWidget(row, 0)
        if widget is None:
            return False
        current_role = widget.property("special_role")
        if role is None:
            return current_role is not None
        return current_role == role

    def _read_row_fraction(self, row: int) -> float:
        item = self.table.item(row, 1)
        if item is None:
            return 0.0
        try:
            return float(item.text())
        except ValueError:
            return 0.0

    @staticmethod
    def _special_token_for_role(role: str) -> str:
        return SPECIAL_TOKEN_BY_ROLE[role]

    @staticmethod
    def _display_label_for_component(component_id: str) -> str:
        return SPECIAL_DISPLAY_BY_TOKEN.get(component_id.strip(), component_id.strip())

    @staticmethod
    def _component_token_from_label(component_id: str) -> str:
        normalized = component_id.strip()
        if normalized in SPECIAL_ROLE_BY_TOKEN:
            return normalized
        return SPECIAL_TOKEN_BY_DISPLAY.get(normalized, normalized)

    @staticmethod
    def _combo_component_token(combo: ClickSelectComboBox) -> str:
        current_data = combo.currentData()
        if isinstance(current_data, str) and current_data.strip():
            return current_data.strip()
        return CompositionInputWidget._component_token_from_label(combo.currentText())

    @staticmethod
    def _special_role_for_component(component_id: str) -> Optional[str]:
        return SPECIAL_ROLE_BY_TOKEN.get(
            CompositionInputWidget._component_token_from_label(component_id)
        )

    def _configure_component_combo(
        self,
        combo: ClickSelectComboBox,
        *,
        special_role: Optional[str],
        current_text: str,
    ) -> None:
        """Configure a row picker as a normal component row or a special feed row."""
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.setProperty("special_role", special_role)
            if special_role is None:
                combo.setEditable(True)
                combo.addItems(COMPONENT_PICKER_OPTIONS)
                display_text = self._display_label_for_component(current_text)
                if current_text:
                    if combo.findText(display_text) >= 0:
                        combo.setCurrentText(display_text)
                    else:
                        combo.setEditText(display_text)
            else:
                token = self._special_token_for_role(special_role)
                display_text = self._display_label_for_component(token)
                combo.setEditable(False)
                combo.addItem(display_text, token)
                combo.setCurrentIndex(0)
        finally:
            combo.blockSignals(False)

    def _set_row_fraction(self, row: int, fraction: float) -> None:
        item = self.table.item(row, 1)
        if item is not None:
            item.setText(f"{fraction:.6f}")

    def _row_for_combo(self, combo: ClickSelectComboBox) -> Optional[int]:
        for row in range(self.table.rowCount()):
            if self.table.cellWidget(row, 0) is combo:
                return row
        return None

    def _special_fraction_cache(self, role: str) -> float:
        edit = self.plus_z_edit if role == HEAVY_MODE_PLUS else self.inline_z_edit
        text = edit.text().strip()
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            return 0.0

    def _ensure_special_row(self, role: str) -> Optional[int]:
        if self._get_heavy_mode() != role:
            return None
        row = self._find_special_row(role)
        fraction = self._special_fraction_cache(role)
        if row is None:
            self._add_component_row(self._special_token_for_role(role), fraction, special_role=role)
            row = self._find_special_row(role)
        if row is None:
            return None
        combo = self.table.cellWidget(row, 0)
        if isinstance(combo, ClickSelectComboBox):
            self._configure_component_combo(
                combo,
                special_role=role,
                current_text=self._special_token_for_role(role),
            )
        self._set_row_fraction(row, fraction)
        return row

    def _ensure_plus_fraction_row(self) -> None:
        self._ensure_special_row(HEAVY_MODE_PLUS)

    def _ensure_inline_pseudo_row(self) -> None:
        self._ensure_special_row(HEAVY_MODE_INLINE)

    def _sync_plus_fraction_fields_from_row(self) -> None:
        row = self._find_special_row(HEAVY_MODE_PLUS)
        if row is None or self._syncing_special_rows:
            return
        combo = self.table.cellWidget(row, 0)
        label = combo.currentText().strip() if isinstance(combo, ClickSelectComboBox) else PLUS_FRACTION_TOKEN
        item = self.table.item(row, 1)
        value = "" if item is None else item.text().strip()
        self._syncing_special_rows = True
        try:
            self.plus_label_edit.setText(label or PLUS_FRACTION_TOKEN)
            self.plus_z_edit.setText(value)
        finally:
            self._syncing_special_rows = False

    def _sync_plus_fraction_row_from_fields(self) -> None:
        if self._syncing_special_rows or self._get_heavy_mode() != HEAVY_MODE_PLUS:
            return
        row = self._find_special_row(HEAVY_MODE_PLUS)
        if row is None:
            return
        item = self.table.item(row, 1)
        value = self.plus_z_edit.text().strip()
        self._syncing_special_rows = True
        try:
            self.plus_label_edit.setText(PLUS_FRACTION_TOKEN)
            if item is not None:
                if value:
                    try:
                        item.setText(f"{float(value):.6f}")
                    except ValueError:
                        item.setText(value)
                else:
                    item.setText("0.000000")
        finally:
            self._syncing_special_rows = False

    def _sync_inline_fraction_fields_from_row(self) -> None:
        row = self._find_special_row(HEAVY_MODE_INLINE)
        if row is None or self._syncing_special_rows:
            return
        item = self.table.item(row, 1)
        value = "" if item is None else item.text().strip()
        self._syncing_special_rows = True
        try:
            self.inline_component_id_edit.setText(INLINE_PSEUDO_LABEL)
            self.inline_z_edit.setText(value)
        finally:
            self._syncing_special_rows = False

    def _sync_inline_pseudo_row_from_fields(self) -> None:
        if self._syncing_special_rows or self._get_heavy_mode() != HEAVY_MODE_INLINE:
            return
        row = self._find_special_row(HEAVY_MODE_INLINE)
        if row is None:
            return
        item = self.table.item(row, 1)
        value = self.inline_z_edit.text().strip()
        self._syncing_special_rows = True
        try:
            self.inline_component_id_edit.setText(INLINE_PSEUDO_LABEL)
            if item is not None:
                if value:
                    try:
                        item.setText(f"{float(value):.6f}")
                    except ValueError:
                        item.setText(value)
                else:
                    item.setText("0.000000")
        finally:
            self._syncing_special_rows = False

    def _promote_row_to_special_role(self, row: int, role: str) -> None:
        """Convert a table row into the single special row for the requested role."""
        combo = self.table.cellWidget(row, 0)
        if not isinstance(combo, ClickSelectComboBox):
            return

        existing_row = self._find_special_row(role)
        if existing_row is not None and existing_row != row:
            self.table.removeRow(existing_row)
            if existing_row < row:
                row -= 1
            combo = self.table.cellWidget(row, 0)
            if not isinstance(combo, ClickSelectComboBox):
                return

        self._configure_component_combo(
            combo,
            special_role=role,
            current_text=self._special_token_for_role(role),
        )
        if role == HEAVY_MODE_PLUS:
            self._sync_plus_fraction_fields_from_row()
        elif role == HEAVY_MODE_INLINE:
            self._sync_inline_fraction_fields_from_row()

    def _handle_component_selection(self, sender: ClickSelectComboBox) -> None:
        """Promote explicit special tokens selected in the main table to special rows."""
        row = self._row_for_combo(sender)
        if row is None:
            return
        role = self._special_role_for_component(self._combo_component_token(sender))
        if role is None:
            return

        self._promote_row_to_special_role(row, role)
        target_index = self.heavy_mode.findData(role)
        if target_index >= 0 and target_index != self.heavy_mode.currentIndex():
            self.heavy_mode.setCurrentIndex(target_index)

    def _remove_special_row(self, role: str) -> None:
        row = self._find_special_row(role)
        if row is not None:
            self.table.removeRow(row)

    def _current_plus_characterization_preset(self) -> PlusFractionCharacterizationPreset:
        return PlusFractionCharacterizationPreset(self.plus_characterization_preset.currentData())

    def set_calculation_type_context(self, calc_type: CalculationType) -> None:
        """Provide the current workflow so auto characterization can resolve honestly."""
        self._calculation_type_context = calc_type
        self._refresh_plus_characterization_preview()

    def _set_plus_controls_from_resolved_entry(self, plus_fraction: PlusFractionEntry) -> None:
        self.plus_end_spin.blockSignals(True)
        self.plus_split_method.blockSignals(True)
        self.plus_split_mw_model.blockSignals(True)
        self.plus_lumping_enabled.blockSignals(True)
        self.plus_lumping_groups_spin.blockSignals(True)
        try:
            self.plus_end_spin.setValue(plus_fraction.max_carbon_number)
            self.plus_split_method.setCurrentText(plus_fraction.split_method)
            self.plus_split_mw_model.setCurrentText(plus_fraction.split_mw_model)
            self.plus_lumping_enabled.setChecked(plus_fraction.lumping_enabled)
            self.plus_lumping_groups_spin.setValue(plus_fraction.lumping_n_groups)
        finally:
            self.plus_end_spin.blockSignals(False)
            self.plus_split_method.blockSignals(False)
            self.plus_split_mw_model.blockSignals(False)
            self.plus_lumping_enabled.blockSignals(False)
            self.plus_lumping_groups_spin.blockSignals(False)

    def _resolved_plus_fraction_preview(self) -> Tuple[Optional[PlusFractionEntry], Optional[str]]:
        if self._get_heavy_mode() != HEAVY_MODE_PLUS:
            return None, None

        preset = self._current_plus_characterization_preset()
        base_entry, error = self._get_plus_fraction_entry(resolve_policy=False)
        if base_entry is None:
            if preset is PlusFractionCharacterizationPreset.AUTO:
                return None, "Auto: enter the plus-fraction table row, MW+, and the light-end feed to resolve a validated profile."
            if preset is PlusFractionCharacterizationPreset.MANUAL:
                return None, "Manual: edit split/lumping settings directly."
            settings = PLUS_FRACTION_PRESET_SETTINGS[preset]
            return None, (
                f"{PLUS_FRACTION_PRESET_LABELS[preset]}; split method {settings.split_method}, "
                f"split MW model {settings.split_mw_model}, "
                f"split to C{settings.max_carbon_number}, "
                f"lumping {'on' if settings.lumping_enabled else 'off'}"
                + (f" ({settings.lumping_n_groups} groups)" if settings.lumping_enabled else "")
            )
        if error is not None:
            return None, error
        try:
            resolved = resolve_plus_fraction_entry(
                [ComponentEntry(component_id=comp_id, mole_fraction=fraction) for comp_id, fraction in self._get_runtime_components()],
                base_entry,
                self._calculation_type_context,
            )
        except Exception as exc:
            return None, str(exc)
        return resolved, describe_plus_fraction_policy(resolved)

    def _refresh_plus_characterization_preview(self) -> None:
        if self._get_heavy_mode() != HEAVY_MODE_PLUS:
            self.plus_characterization_summary.setText("Not active")
            self.plus_end_spin.setEnabled(False)
            self.plus_split_method.setEnabled(False)
            self.plus_split_mw_model.setEnabled(False)
            self.plus_lumping_enabled.setEnabled(False)
            self.plus_lumping_groups_spin.setEnabled(False)
            return

        preset = self._current_plus_characterization_preset()
        resolved, summary = self._resolved_plus_fraction_preview()
        self.plus_characterization_summary.setText(summary or "")

        manual = preset is PlusFractionCharacterizationPreset.MANUAL
        if resolved is not None and not manual:
            self._set_plus_controls_from_resolved_entry(resolved)
        elif not manual and preset in PLUS_FRACTION_PRESET_SETTINGS:
            settings = PLUS_FRACTION_PRESET_SETTINGS[preset]
            self.plus_end_spin.blockSignals(True)
            self.plus_split_method.blockSignals(True)
            self.plus_split_mw_model.blockSignals(True)
            self.plus_lumping_enabled.blockSignals(True)
            self.plus_lumping_groups_spin.blockSignals(True)
            try:
                self.plus_end_spin.setValue(settings.max_carbon_number)
                self.plus_split_method.setCurrentText(settings.split_method)
                self.plus_split_mw_model.setCurrentText(settings.split_mw_model)
                self.plus_lumping_enabled.setChecked(settings.lumping_enabled)
                self.plus_lumping_groups_spin.setValue(settings.lumping_n_groups)
            finally:
                self.plus_end_spin.blockSignals(False)
                self.plus_split_method.blockSignals(False)
                self.plus_split_mw_model.blockSignals(False)
                self.plus_lumping_enabled.blockSignals(False)
                self.plus_lumping_groups_spin.blockSignals(False)

        self.plus_end_spin.setEnabled(manual)
        self.plus_split_method.setEnabled(manual)
        self.plus_split_mw_model.setEnabled(manual)
        self.plus_lumping_enabled.setEnabled(manual)
        self._sync_plus_lumping_state()

    def _scaled_metric(self, value: int) -> int:
        """Scale metrics relative to the current default desktop baseline."""
        return scale_metric(value, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)

    def _sync_heavy_tab_spacing(self) -> None:
        """Keep a small visual gap between the tab strip and the first form row."""
        top_margin = scale_metric(6, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
        for form_layout in (self.plus_form, self.inline_form):
            form_layout.setContentsMargins(0, top_margin, 0, 0)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale non-QSS geometry to follow the app zoom level."""
        self._ui_scale = ui_scale
        scaled_gap = scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        scaled_row_gap = scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        scaled_unit_width = scale_metric(96, ui_scale, reference_scale=DEFAULT_UI_SCALE)

        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setSpacing(scaled_gap)

        for form_layout in self.findChildren(QFormLayout):
            form_layout.setHorizontalSpacing(scaled_gap)
            form_layout.setVerticalSpacing(scaled_row_gap)

        for row_layout in self.findChildren(QHBoxLayout):
            row_layout.setSpacing(scaled_row_gap)

        for button_layout in self.findChildren(QGridLayout):
            button_layout.setHorizontalSpacing(scaled_row_gap)
            button_layout.setVerticalSpacing(scaled_row_gap)

        for unit_widget in self.findChildren(QWidget):
            if unit_widget.property("sidebar_unit_widget") and hasattr(unit_widget, "setMaximumWidth"):
                unit_widget.setMaximumWidth(scaled_unit_width)

        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, ClickSelectComboBox):
                combo.apply_ui_scale(ui_scale)
        self._sync_heavy_tab_spacing()
        self._sync_table_height()

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.add_btn.clicked.connect(self._add_row)
        self.remove_btn.clicked.connect(self._remove_selected)
        self.normalize_btn.clicked.connect(self._normalize)
        self.clear_btn.clicked.connect(self._clear_all)
        self.saved_compositions_combo.currentIndexChanged.connect(self._on_saved_composition_selected)
        self.save_feed_btn.clicked.connect(self._save_current_composition)
        self.delete_feed_btn.clicked.connect(self._delete_selected_saved_composition)
        self.table.cellChanged.connect(self._on_cell_changed)
        self.heavy_mode.currentIndexChanged.connect(self._on_heavy_mode_changed)
        self.heavy_tabs.currentChanged.connect(self._on_heavy_tab_changed)

        for widget in [
            self.plus_label_edit,
            self.plus_z_edit,
            self.plus_mw_edit,
            self.plus_sg_edit,
            self.inline_z_edit,
            self.inline_name_edit,
            self.inline_mw_edit,
            self.inline_tc_edit,
            self.inline_pc_edit,
            self.inline_omega_edit,
        ]:
            widget.textChanged.connect(self._on_cell_changed)
        self.inline_name_edit.textChanged.connect(self._sync_inline_label_fields)

        for combo in [self.inline_tc_unit, self.inline_pc_unit]:
            combo.currentTextChanged.connect(self._on_cell_changed)
        self.plus_characterization_preset.currentIndexChanged.connect(self._on_cell_changed)
        self.plus_split_method.currentTextChanged.connect(self._on_cell_changed)
        self.plus_split_mw_model.currentTextChanged.connect(self._on_cell_changed)
        self.plus_lumping_enabled.toggled.connect(self._sync_plus_lumping_state)
        self.plus_lumping_enabled.toggled.connect(self._on_cell_changed)

        for spin in [self.plus_cut_start_spin, self.plus_end_spin, self.plus_lumping_groups_spin]:
            spin.valueChanged.connect(self._on_cell_changed)

    def _add_default_components(self) -> None:
        """Add common gas/oil components as starting point."""
        self.table.blockSignals(True)
        for comp_id, fraction in DEFAULT_COMPONENT_ROWS:
            self._add_component_row(comp_id, fraction)
        self.table.blockSignals(False)

        self._sync_table_height()
        self._update_sum()

    def _add_row(self) -> None:
        """Add a new empty row to the table."""
        self._add_component_row("", 0.0)

    def _add_component_row(self, comp_id: str, fraction: float, *, special_role: Optional[str] = None) -> None:
        """Add a component row with values."""
        if special_role is None:
            special_role = self._special_role_for_component(comp_id)
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Component selector (combobox)
        combo = ClickSelectComboBox(ui_scale=self._ui_scale)
        self._configure_component_combo(combo, special_role=special_role, current_text=comp_id)
        combo.currentTextChanged.connect(self._on_cell_changed)
        self.table.setCellWidget(row, 0, combo)

        # Mole fraction
        item = QTableWidgetItem(f"{fraction:.6f}")
        item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row, 1, item)

        self._sync_table_height()

    def _remove_selected(self) -> None:
        """Remove selected rows from the table."""
        rows = set()
        removed_special_roles = set()
        for item in self.table.selectedItems():
            rows.add(item.row())

        # Also check for selected widgets (comboboxes)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget and widget.hasFocus():
                rows.add(row)

        # Remove rows in reverse order to preserve indices
        for row in sorted(rows, reverse=True):
            widget = self.table.cellWidget(row, 0)
            if widget is not None and widget.property("special_role") is not None:
                removed_special_roles.add(str(widget.property("special_role")))
            self.table.removeRow(row)

        if HEAVY_MODE_PLUS in removed_special_roles:
            self.plus_z_edit.clear()
            none_index = self.heavy_mode.findData(HEAVY_MODE_NONE)
            if none_index >= 0:
                self.heavy_mode.setCurrentIndex(none_index)
        elif HEAVY_MODE_INLINE in removed_special_roles:
            self.inline_z_edit.clear()
            none_index = self.heavy_mode.findData(HEAVY_MODE_NONE)
            if none_index >= 0:
                self.heavy_mode.setCurrentIndex(none_index)

        self._sync_table_height()
        self._update_sum()
        self.composition_edited.emit()

    def _clear_all(self) -> None:
        """Clear all rows after confirmation."""
        has_heavy_data = self._get_heavy_mode() != HEAVY_MODE_NONE
        if self.table.rowCount() > 0 or has_heavy_data:
            reply = QMessageBox.question(
                self,
                "Clear Composition",
                "Are you sure you want to clear all components?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.table.setRowCount(0)
                self._reset_heavy_inputs()
                self._sync_table_height()
                self._update_sum()
                self._mark_saved_selection_dirty()
                self.composition_edited.emit()

    def _reset_heavy_inputs(self) -> None:
        """Restore the heavy-end editor to its default empty state."""
        self.heavy_mode.setCurrentIndex(0)
        self.plus_label_edit.setText(PLUS_FRACTION_TOKEN)
        self.plus_cut_start_spin.setValue(7)
        self.plus_z_edit.clear()
        self.plus_mw_edit.clear()
        self.plus_sg_edit.clear()
        self.plus_characterization_preset.setCurrentIndex(0)
        self.plus_end_spin.setValue(45)
        self.plus_split_method.setCurrentText("pedersen")
        self.plus_split_mw_model.setCurrentText("paraffin")
        self.plus_lumping_enabled.setChecked(False)
        self.plus_lumping_groups_spin.setValue(8)
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()

        self.inline_component_id_edit.setText(INLINE_PSEUDO_LABEL)
        self.inline_name_edit.setText(INLINE_PSEUDO_LABEL)
        self.inline_formula_edit.setText(INLINE_PSEUDO_LABEL)
        self.inline_z_edit.clear()
        self.inline_mw_edit.clear()
        self.inline_tc_edit.clear()
        self.inline_tc_unit.setCurrentText(TemperatureUnit.K.value)
        self.inline_pc_edit.clear()
        self.inline_pc_unit.setCurrentText(PressureUnit.PA.value)
        self.inline_omega_edit.clear()

    def _sync_inline_label_fields(self, *_args) -> None:
        """Mirror the single visible inline label into the hidden derived fields."""
        label = self.inline_name_edit.text().strip() or INLINE_PSEUDO_LABEL
        self.inline_component_id_edit.blockSignals(True)
        self.inline_formula_edit.blockSignals(True)
        try:
            self.inline_component_id_edit.setText(label)
            self.inline_formula_edit.setText(label)
        finally:
            self.inline_component_id_edit.blockSignals(False)
            self.inline_formula_edit.blockSignals(False)

    @staticmethod
    def _parse_float(value: str, label: str) -> Tuple[Optional[float], Optional[str]]:
        text = value.strip()
        if not text:
            return None, f"{label} is required"
        try:
            return float(text), None
        except ValueError:
            return None, f"{label} must be a number"

    def _get_plus_fraction_entry(self, *, resolve_policy: bool = True) -> Tuple[Optional[PlusFractionEntry], Optional[str]]:
        if self._get_heavy_mode() != HEAVY_MODE_PLUS:
            return None, None

        row = self._find_special_row(HEAVY_MODE_PLUS)
        label = self.plus_label_edit.text().strip() or PLUS_FRACTION_TOKEN
        z_text = self.plus_z_edit.text()
        if row is not None:
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, ClickSelectComboBox):
                label = combo.currentText().strip() or label
            item = self.table.item(row, 1)
            z_text = "" if item is None else item.text()

        z_plus, error = self._parse_float(z_text, "Plus-fraction z+")
        if error is not None:
            return None, error
        mw_plus, error = self._parse_float(self.plus_mw_edit.text(), "Plus-fraction MW+")
        if error is not None:
            return None, error

        sg_text = self.plus_sg_edit.text().strip()
        sg_plus = None
        if sg_text:
            sg_plus, error = self._parse_float(sg_text, "Plus-fraction SG+")
            if error is not None:
                return None, error

        try:
            plus_fraction = PlusFractionEntry(
                label=label,
                cut_start=self.plus_cut_start_spin.value(),
                z_plus=float(z_plus),
                mw_plus_g_per_mol=float(mw_plus),
                sg_plus_60f=sg_plus,
                characterization_preset=self._current_plus_characterization_preset(),
                max_carbon_number=self.plus_end_spin.value(),
                split_method=self.plus_split_method.currentText(),
                split_mw_model=self.plus_split_mw_model.currentText(),
                lumping_enabled=self.plus_lumping_enabled.isChecked(),
                lumping_n_groups=self.plus_lumping_groups_spin.value(),
            )
            if not resolve_policy:
                return plus_fraction, None
            resolved = resolve_plus_fraction_entry(
                [ComponentEntry(component_id=comp_id, mole_fraction=fraction) for comp_id, fraction in self._get_runtime_components()],
                plus_fraction,
                self._calculation_type_context,
            )
            return resolved, None
        except Exception as exc:
            return None, str(exc)

    def _get_inline_component_spec(self) -> Tuple[Optional[InlineComponentSpec], Optional[float], Optional[str]]:
        if self._get_heavy_mode() != HEAVY_MODE_INLINE:
            return None, None, None

        row = self._find_special_row(HEAVY_MODE_INLINE)
        component_id = INLINE_PSEUDO_TOKEN
        name = self.inline_name_edit.text().strip() or INLINE_PSEUDO_LABEL
        formula = name
        z_text = self.inline_z_edit.text()
        if row is not None:
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, ClickSelectComboBox):
                component_id = self._combo_component_token(combo) or component_id
            item = self.table.item(row, 1)
            z_text = "" if item is None else item.text()
        z_inline, error = self._parse_float(z_text, "Inline pseudo mole fraction")
        if error is not None:
            return None, None, error
        mw, error = self._parse_float(self.inline_mw_edit.text(), "Inline pseudo MW")
        if error is not None:
            return None, None, error
        tc_raw, error = self._parse_float(self.inline_tc_edit.text(), "Inline pseudo Tc")
        if error is not None:
            return None, None, error
        pc_raw, error = self._parse_float(self.inline_pc_edit.text(), "Inline pseudo Pc")
        if error is not None:
            return None, None, error
        omega, error = self._parse_float(self.inline_omega_edit.text(), "Inline pseudo omega")
        if error is not None:
            return None, None, error

        try:
            tc_unit = TemperatureUnit(self.inline_tc_unit.currentText())
            pc_unit = PressureUnit(self.inline_pc_unit.currentText())
            spec = InlineComponentSpec(
                component_id=component_id,
                name=name,
                formula=formula,
                molecular_weight_g_per_mol=float(mw),
                critical_temperature_k=temperature_to_k(
                    float(tc_raw),
                    tc_unit,
                ),
                critical_pressure_pa=pressure_to_pa(
                    float(pc_raw),
                    pc_unit,
                ),
                critical_temperature_unit=tc_unit,
                critical_pressure_unit=pc_unit,
                omega=float(omega),
            )
            return spec, float(z_inline), None
        except Exception as exc:
            return None, None, str(exc)

    def _normalize(self) -> None:
        """Normalize all active feed fractions to sum to 1.0."""
        total = self._get_sum()
        if total <= 0:
            QMessageBox.warning(
                self,
                "Cannot Normalize",
                "Total must be greater than zero to normalize.",
            )
            return

        self._normalize_active_fractions(total)
        self._sync_table_height()
        self._update_sum()
        self._mark_saved_selection_dirty()
        self.composition_edited.emit()

    def _normalize_active_fractions(self, total: float) -> None:
        """Scale the table and active heavy-end editor so the full feed sums to 1.0."""
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item:
                try:
                    value = float(item.text())
                    normalized = value / total
                    item.setText(f"{normalized:.6f}")
                except ValueError:
                    pass
        self.table.blockSignals(False)

        if self._get_heavy_mode() == HEAVY_MODE_PLUS:
            self._sync_plus_fraction_fields_from_row()
        elif self._get_heavy_mode() == HEAVY_MODE_INLINE:
            self._sync_inline_fraction_fields_from_row()

    def _on_cell_changed(self, *args) -> None:
        """Handle cell value changes."""
        sender = self.sender()
        if isinstance(sender, ClickSelectComboBox):
            self._handle_component_selection(sender)
        if self._get_heavy_mode() == HEAVY_MODE_PLUS:
            if sender in {self.plus_label_edit, self.plus_z_edit}:
                self._sync_plus_fraction_row_from_fields()
            elif sender is self.table or (
                isinstance(sender, ClickSelectComboBox)
                and sender.property("special_role") == HEAVY_MODE_PLUS
            ):
                self._sync_plus_fraction_fields_from_row()
        if self._get_heavy_mode() == HEAVY_MODE_INLINE:
            if sender in {self.inline_name_edit, self.inline_z_edit}:
                self._sync_inline_pseudo_row_from_fields()
            elif sender is self.table or (
                isinstance(sender, ClickSelectComboBox)
                and sender.property("special_role") == HEAVY_MODE_INLINE
            ):
                self._sync_inline_fraction_fields_from_row()
        self._refresh_plus_characterization_preview()
        self._update_sum()
        self._mark_saved_selection_dirty()
        self.composition_edited.emit()

    def _load_saved_compositions(self) -> None:
        """Load persisted saved-feed payloads from QSettings."""
        raw_value = self._settings.value(SAVED_COMPOSITIONS_SETTINGS_KEY, "{}")
        try:
            data = json.loads(raw_value) if isinstance(raw_value, str) else {}
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict):
            self._saved_compositions = {str(name): payload for name, payload in data.items()}
        else:
            self._saved_compositions = {}
        self._refresh_saved_compositions_combo()

    def _persist_saved_compositions(self) -> None:
        """Persist saved-feed payloads into QSettings."""
        self._settings.setValue(
            SAVED_COMPOSITIONS_SETTINGS_KEY,
            json.dumps(self._saved_compositions, sort_keys=True),
        )
        self._settings.sync()

    def _refresh_saved_compositions_combo(self, *, selected_name: Optional[str] = None) -> None:
        """Refresh the saved-feed drop-down while preserving an optional selection."""
        self.saved_compositions_combo.blockSignals(True)
        try:
            self.saved_compositions_combo.clear()
            self.saved_compositions_combo.addItem("Current Feed", None)
            for name in sorted(self._saved_compositions):
                self.saved_compositions_combo.addItem(name, name)
            if selected_name is not None:
                index = self.saved_compositions_combo.findData(selected_name)
                if index >= 0:
                    self.saved_compositions_combo.setCurrentIndex(index)
        finally:
            self.saved_compositions_combo.blockSignals(False)
        self.delete_feed_btn.setEnabled(
            isinstance(self.saved_compositions_combo.currentData(), str)
        )

    def _mark_saved_selection_dirty(self) -> None:
        """Reset the saved-feed selector when the current feed diverges from a stored preset."""
        if self._loading_saved_composition:
            return
        if self.saved_compositions_combo.currentIndex() != 0:
            self.saved_compositions_combo.blockSignals(True)
            self.saved_compositions_combo.setCurrentIndex(0)
            self.saved_compositions_combo.blockSignals(False)
        self.delete_feed_btn.setEnabled(False)

    def _save_composition_named(self, name: str) -> bool:
        """Save the current validated composition under a user-defined name."""
        normalized_name = name.strip()
        if not normalized_name:
            QMessageBox.warning(self, "Save Feed", "A saved feed name is required.")
            return False

        composition = self.get_composition()
        if composition is None:
            QMessageBox.warning(
                self,
                "Save Feed",
                "The current feed is invalid. Normalize or correct it before saving.",
            )
            return False

        self._saved_compositions[normalized_name] = composition.model_dump(mode="json")
        self._persist_saved_compositions()
        self._refresh_saved_compositions_combo(selected_name=normalized_name)
        self.delete_feed_btn.setEnabled(True)
        return True

    def _save_current_composition(self) -> None:
        """Prompt for a saved-feed name and persist the current composition."""
        current_name = self.saved_compositions_combo.currentData()
        default_name = current_name if isinstance(current_name, str) else ""
        name, ok = QInputDialog.getText(
            self,
            "Save Feed",
            "Saved feed name:",
            text=default_name,
        )
        if not ok:
            return
        self._save_composition_named(name)

    def _delete_selected_saved_composition(self) -> None:
        """Delete the currently selected saved feed, if any."""
        current_name = self.saved_compositions_combo.currentData()
        if not isinstance(current_name, str):
            return
        reply = QMessageBox.question(
            self,
            "Delete Saved Feed",
            f"Delete saved feed '{current_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._saved_compositions.pop(current_name, None)
        self._persist_saved_compositions()
        self._refresh_saved_compositions_combo()
        self.delete_feed_btn.setEnabled(False)

    def _on_saved_composition_selected(self, _index: int) -> None:
        """Load a saved feed when the user selects it from the drop-down."""
        selected_name = self.saved_compositions_combo.currentData()
        self.delete_feed_btn.setEnabled(isinstance(selected_name, str))
        if not isinstance(selected_name, str):
            return
        payload = self._saved_compositions.get(selected_name)
        if payload is None:
            return
        try:
            composition = FluidComposition.model_validate(payload)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Load Saved Feed",
                f"Could not load saved feed '{selected_name}': {exc}",
            )
            return
        self._loading_saved_composition = True
        try:
            self.set_composition(composition)
            self._refresh_saved_compositions_combo(selected_name=selected_name)
            self.delete_feed_btn.setEnabled(True)
        finally:
            self._loading_saved_composition = False

    def _preferred_row_height(self) -> int:
        """Return a row height that tracks the current scaled UI font/widgets."""
        font_height = self.table.fontMetrics().height()
        combo_height = 0
        if self.table.rowCount() > 0:
            combo = self.table.cellWidget(0, 0)
            if combo is not None:
                combo_height = combo.sizeHint().height()

        editor_padding = MoleFractionItemDelegate._horizontal_padding_for_font_height(font_height)
        editor_height = font_height + max(4, editor_padding)
        return max(self.table.verticalHeader().minimumSectionSize(), font_height + 10, editor_height, combo_height)

    def _widest_component_selector_width(self) -> int:
        """Return the widest visible component picker width needed by the current rows."""
        width = 0
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, ClickSelectComboBox):
                width = max(width, combo.minimumSizeHint().width(), combo.sizeHint().width())
        return width

    def _sync_column_widths(self) -> None:
        """Keep the component column readable while letting mole fractions breathe."""
        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.table.sizeHint().width()
        if viewport_width <= 0:
            return

        mole_fraction_min_width = self._scaled_metric(MOLE_FRACTION_COLUMN_MIN_WIDTH)
        header_metrics = self.table.horizontalHeader().fontMetrics()
        header_width = header_metrics.horizontalAdvance("Component")
        component_width = max(
            self._scaled_metric(COMPONENT_COLUMN_MIN_WIDTH),
            min(
                self._scaled_metric(COMPONENT_COLUMN_MAX_WIDTH),
                max(
                    header_width
                    + self._scaled_metric(COMPONENT_DROPDOWN_BUTTON_WIDTH)
                    + self._scaled_metric(COMPONENT_COLUMN_SIDE_MARGIN),
                    int(round(viewport_width * 0.46)),
                ),
            ),
        )

        widest_selector_width = self._widest_component_selector_width()
        if widest_selector_width > 0:
            max_component_width = max(
                self._scaled_metric(COMPONENT_COLUMN_MIN_WIDTH),
                viewport_width - mole_fraction_min_width,
            )
            component_width = max(
                component_width,
                min(widest_selector_width, max_component_width),
            )

        available_for_fraction = max(mole_fraction_min_width, viewport_width - component_width)
        if viewport_width < component_width + mole_fraction_min_width:
            component_width = max(self._scaled_metric(COMPONENT_COLUMN_MIN_WIDTH), viewport_width - mole_fraction_min_width)
            available_for_fraction = max(mole_fraction_min_width, viewport_width - component_width)

        self.table.setColumnWidth(0, component_width)
        self.table.setColumnWidth(1, available_for_fraction)

    def _sync_table_height(self) -> None:
        """Resize the table to show all rows without internal scrolling."""
        preferred_row_height = self._preferred_row_height()
        self.table.verticalHeader().setDefaultSectionSize(preferred_row_height)
        self.table.verticalHeader().setMinimumSectionSize(preferred_row_height)

        for row in range(self.table.rowCount()):
            self.table.setRowHeight(row, preferred_row_height)

        self._sync_column_widths()

        header_height = self.table.horizontalHeader().sizeHint().height()
        frame_height = self.table.frameWidth() * 2
        row_heights = preferred_row_height * max(self.table.rowCount(), 1)

        table_height = frame_height + header_height + row_heights + 4
        self.table.setMinimumHeight(table_height)
        self.table.setMaximumHeight(table_height)
        self.table.updateGeometry()
        self.updateGeometry()

    def _get_sum(self) -> float:
        """Calculate sum of mole fractions."""
        total = 0.0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 1)
            if item:
                try:
                    total += float(item.text())
                except ValueError:
                    pass
        return total

    def _update_sum(self) -> None:
        """Update the sum display and status."""
        total = self._get_sum()
        self.sum_label.setText(f"{total:.6f}")

        diff = abs(total - 1.0)
        if diff < COMPOSITION_SUM_TOLERANCE:
            self.sum_status.setText("Valid")
            self.sum_status.setStyleSheet("color: green; font-weight: bold;")
            self.sum_label.setStyleSheet("color: green; font-weight: bold;")
        elif diff < 0.01:
            self.sum_status.setText("(Close - click Normalize Feed)")
            self.sum_status.setStyleSheet("color: orange; font-weight: bold;")
            self.sum_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.sum_status.setText("(Normalize Feed or enter 1.0 total)")
            self.sum_status.setStyleSheet("color: red; font-weight: bold;")
            self.sum_label.setStyleSheet("color: red; font-weight: bold;")

    def resizeEvent(self, event) -> None:
        """Keep column widths sensible when the fixed sidebar geometry changes."""
        super().resizeEvent(event)
        self._sync_column_widths()

    def get_components(self) -> List[Tuple[str, float]]:
        """Get list of (component_id, mole_fraction) tuples.

        Returns:
            List of tuples, may include invalid entries
        """
        components = []
        for row in range(self.table.rowCount()):
            if self._row_is_special(row):
                continue
            # Get component ID from combobox
            widget = self.table.cellWidget(row, 0)
            if widget:
                if isinstance(widget, ClickSelectComboBox):
                    comp_id = self._combo_component_token(widget)
                else:
                    comp_id = self._component_token_from_label(widget.currentText())
            else:
                comp_id = ""

            # Get mole fraction
            item = self.table.item(row, 1)
            try:
                fraction = float(item.text()) if item else 0.0
            except ValueError:
                fraction = 0.0

            if comp_id:  # Skip empty component IDs
                components.append((comp_id, fraction))

        return components

    def _get_runtime_components(self) -> List[Tuple[str, float]]:
        """Return components that should participate in runtime validation/execution.

        Zero-fraction rows are treated as placeholders and ignored at runtime.
        """
        return [
            (comp_id, fraction)
            for comp_id, fraction in self.get_components()
            if abs(fraction) > COMPOSITION_SUM_TOLERANCE
        ]

    def _resolve_runtime_components(self) -> Tuple[List[Tuple[str, str, float]], Optional[str]]:
        """Resolve user-entered component IDs to canonical database IDs."""
        resolved_components: List[Tuple[str, str, float]] = []

        for raw_id, fraction in self._get_runtime_components():
            try:
                canonical_id = resolve_component_id(raw_id)
            except KeyError as exc:
                return [], str(exc)
            resolved_components.append((raw_id, canonical_id, fraction))

        return resolved_components, None

    def validate(self) -> Tuple[bool, str]:
        """Validate the current composition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        components, error = self._resolve_runtime_components()
        if error is not None:
            return False, error

        if not components:
            return False, "At least one component is required"

        # Check for duplicate IDs after alias resolution
        duplicate_sources: Dict[str, List[str]] = {}
        for raw_id, canonical_id, _fraction in components:
            duplicate_sources.setdefault(canonical_id, []).append(raw_id)
        duplicates = {
            canonical_id: raw_ids
            for canonical_id, raw_ids in duplicate_sources.items()
            if len(raw_ids) > 1
        }
        if duplicates:
            return False, f"Duplicate component IDs after alias resolution: {duplicates}"

        # Check for negative fractions
        for raw_id, _canonical_id, fraction in components:
            if fraction < 0:
                return False, f"Negative mole fraction for {raw_id}"
            if fraction > 1:
                return False, f"Mole fraction > 1 for {raw_id}"

        plus_fraction, plus_error = self._get_plus_fraction_entry()
        inline_spec, inline_z, inline_error = self._get_inline_component_spec()
        if plus_error is not None:
            return False, plus_error
        if inline_error is not None:
            return False, inline_error

        if plus_fraction is not None and inline_spec is not None:
            return False, "Plus fraction and inline pseudo modes are mutually exclusive"

        if inline_spec is not None:
            try:
                resolve_component_id(inline_spec.component_id)
            except KeyError:
                pass
            else:
                return False, (
                    f"Inline pseudo component ID '{inline_spec.component_id}' conflicts with a database component or alias"
                )

            existing_ids = {canonical_id for _raw_id, canonical_id, _fraction in components}
            existing_ids.update(raw_id for raw_id, _canonical_id, _fraction in components)
            if inline_spec.component_id in existing_ids:
                return False, f"Duplicate component ID '{inline_spec.component_id}'"

        # Check sum
        total = sum(fraction for _, _, fraction in components)
        if plus_fraction is not None:
            total += plus_fraction.z_plus
        if inline_spec is not None and inline_z is not None:
            total += inline_z
        if abs(total - 1.0) > COMPOSITION_SUM_TOLERANCE:
            return False, f"Mole fractions must sum to 1.0 (got {total:.8f})"

        return True, ""

    def get_composition(self) -> Optional[FluidComposition]:
        """Get validated FluidComposition object.

        Returns:
            FluidComposition if valid, None otherwise
        """
        is_valid, error = self.validate()
        if not is_valid:
            self.validation_error.emit(error)
            return None

        components, error = self._resolve_runtime_components()
        if error is not None:
            self.validation_error.emit(error)
            return None
        entries = [
            ComponentEntry(component_id=raw_id, mole_fraction=frac)
            for raw_id, _canonical_id, frac in components
        ]

        plus_fraction, plus_error = self._get_plus_fraction_entry()
        if plus_error is not None:
            self.validation_error.emit(plus_error)
            return None

        inline_components: List[InlineComponentSpec] = []
        inline_spec, inline_z, inline_error = self._get_inline_component_spec()
        if inline_error is not None:
            self.validation_error.emit(inline_error)
            return None
        if inline_spec is not None and inline_z is not None:
            entries.append(ComponentEntry(component_id=inline_spec.component_id, mole_fraction=inline_z))
            inline_components.append(inline_spec)

        try:
            composition = FluidComposition(
                components=entries,
                plus_fraction=plus_fraction,
                inline_components=inline_components,
            )
            self.composition_changed.emit(composition)
            return composition
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def set_composition(self, composition: FluidComposition) -> None:
        """Load a composition into the widget."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        inline_ids = {spec.component_id for spec in composition.inline_components}
        for entry in composition.components:
            if entry.component_id in inline_ids:
                continue
            self._add_component_row(entry.component_id, entry.mole_fraction)

        self.table.blockSignals(False)

        self._reset_heavy_inputs()
        if composition.plus_fraction is not None:
            self.plus_label_edit.setText(composition.plus_fraction.label)
            self.plus_cut_start_spin.setValue(composition.plus_fraction.cut_start)
            self.plus_z_edit.setText(f"{composition.plus_fraction.z_plus:.6f}")
            self.plus_mw_edit.setText(f"{composition.plus_fraction.mw_plus_g_per_mol:.6f}")
            self.plus_sg_edit.setText(
                "" if composition.plus_fraction.sg_plus_60f is None else f"{composition.plus_fraction.sg_plus_60f:.6f}"
            )
            self.heavy_mode.setCurrentIndex(self.heavy_mode.findData(HEAVY_MODE_PLUS))
            preset_index = self.plus_characterization_preset.findData(
                composition.plus_fraction.characterization_preset
            )
            if preset_index >= 0:
                self.plus_characterization_preset.setCurrentIndex(preset_index)
            self.plus_end_spin.setValue(composition.plus_fraction.max_carbon_number)
            self.plus_split_method.setCurrentText(composition.plus_fraction.split_method)
            self.plus_split_mw_model.setCurrentText(composition.plus_fraction.split_mw_model)
            self.plus_lumping_enabled.setChecked(composition.plus_fraction.lumping_enabled)
            self.plus_lumping_groups_spin.setValue(composition.plus_fraction.lumping_n_groups)
            self._refresh_plus_characterization_preview()
            self._sync_plus_lumping_state()
        elif composition.inline_components:
            spec = composition.inline_components[0]
            inline_fraction = next(
                (entry.mole_fraction for entry in composition.components if entry.component_id == spec.component_id),
                None,
            )
            inline_label = spec.name or spec.formula or self._display_label_for_component(spec.component_id or INLINE_PSEUDO_TOKEN)
            self.inline_component_id_edit.setText(self._display_label_for_component(spec.component_id or INLINE_PSEUDO_TOKEN))
            self.inline_name_edit.setText(inline_label)
            self.inline_formula_edit.setText(inline_label)
            if inline_fraction is not None:
                self.inline_z_edit.setText(f"{inline_fraction:.6f}")
            self.heavy_mode.setCurrentIndex(self.heavy_mode.findData(HEAVY_MODE_INLINE))
            self.inline_mw_edit.setText(f"{spec.molecular_weight_g_per_mol:.6f}")
            self.inline_tc_unit.setCurrentText(spec.critical_temperature_unit.value)
            self.inline_tc_edit.setText(
                f"{temperature_from_k(spec.critical_temperature_k, spec.critical_temperature_unit):.6f}"
            )
            self.inline_pc_unit.setCurrentText(spec.critical_pressure_unit.value)
            self.inline_pc_edit.setText(
                f"{pressure_from_pa(spec.critical_pressure_pa, spec.critical_pressure_unit):.6f}"
            )
            self.inline_omega_edit.setText(f"{spec.omega:.6f}")

        self._sync_table_height()
        self._update_sum()
        self.composition_edited.emit()
