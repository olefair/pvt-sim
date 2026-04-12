"""Composition input widget with validation and normalization.

Provides a spreadsheet-like interface for entering fluid compositions
with strict validation ensuring mole fractions sum to 1.0.
"""

import json
from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QComboBox,
    QLabel,
    QMessageBox,
    QGroupBox,
    QSizePolicy,
    QInputDialog,
    QLineEdit,
    QStyledItemDelegate,
    QSpinBox,
    QStackedWidget,
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
    pressure_to_pa,
    temperature_to_k,
)
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtcore.models import resolve_component_id

COMPONENT_DROPDOWN_BUTTON_WIDTH = 34
COMPONENT_COLUMN_SIDE_MARGIN = 6
COMPONENT_COLUMN_MIN_WIDTH = 96
COMPONENT_COLUMN_MAX_WIDTH = 140
MOLE_FRACTION_COLUMN_MIN_WIDTH = 108
HEAVY_MODE_NONE = "none"
HEAVY_MODE_PLUS = "plus_fraction"
HEAVY_MODE_INLINE = "inline_pseudo"
SAVED_COMPOSITIONS_SETTINGS_KEY = "feeds/saved_compositions"
SETTINGS_ORGANIZATION = "PVT-SIM"


class ClickSelectComboBox(QComboBox):
    """Combo box that ignores mouse-wheel changes.

    This prevents accidental component changes when the cursor happens to be
    hovering over an already selected component while the user is trying to
    scroll the surrounding inputs panel.
    """

    def __init__(self, parent: Optional[QWidget] = None, *, ui_scale: float = DEFAULT_UI_SCALE) -> None:
        super().__init__(parent)
        self.apply_ui_scale(ui_scale)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Update the drop-down affordance to match the active UI scale."""
        dropdown_width = scale_metric(
            COMPONENT_DROPDOWN_BUTTON_WIDTH,
            ui_scale,
            reference_scale=DEFAULT_UI_SCALE,
        )
        self.setStyleSheet(
            f"QComboBox {{ padding-right: {dropdown_width + 4}px; }}"
            f"QComboBox::drop-down {{ width: {dropdown_width}px; border: none; }}"
        )

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()


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

        font_height = max(editor.fontMetrics().height(), option.fontMetrics.height())
        horizontal_padding = self._horizontal_padding_for_font_height(font_height)
        editor.setStyleSheet(
            f"padding: 0px {horizontal_padding}px;"
            "margin: 0px;"
            "border: none;"
            "border-radius: 0px;"
            "background: transparent;"
        )
        return editor

    def updateEditorGeometry(self, editor, option, index) -> None:
        rect = option.rect.adjusted(1, 0, -1, 0)
        editor.setGeometry(rect)


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

        saved_row = QHBoxLayout()
        saved_row.addWidget(QLabel("Saved Feed:"))
        self.saved_compositions_combo = QComboBox()
        self.saved_compositions_combo.addItem("Current Feed", None)
        saved_row.addWidget(self.saved_compositions_combo, 1)
        self.save_feed_btn = QPushButton("Save Current")
        self.delete_feed_btn = QPushButton("Delete Saved")
        self.delete_feed_btn.setEnabled(False)
        saved_row.addWidget(self.save_feed_btn)
        saved_row.addWidget(self.delete_feed_btn)
        group_layout.addLayout(saved_row)

        # Component table
        self.table = QTableWidget()
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

        # Button row
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Component")
        self.remove_btn = QPushButton("Remove Selected")
        self.normalize_btn = QPushButton("Normalize Feed")
        self.clear_btn = QPushButton("Clear All")

        button_layout.addWidget(self.add_btn)
        button_layout.addWidget(self.remove_btn)
        button_layout.addWidget(self.normalize_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()

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

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Mode:"))
        self.heavy_mode = QComboBox()
        self.heavy_mode.addItem("None", HEAVY_MODE_NONE)
        self.heavy_mode.addItem("Plus Fraction", HEAVY_MODE_PLUS)
        self.heavy_mode.addItem("Inline Pseudo", HEAVY_MODE_INLINE)
        mode_layout.addWidget(self.heavy_mode)
        mode_layout.addStretch()
        heavy_layout.addLayout(mode_layout)

        self.heavy_stack = QStackedWidget()
        self.heavy_stack.addWidget(QWidget())

        plus_page = QWidget()
        plus_form = QFormLayout(plus_page)
        plus_form.setContentsMargins(0, 0, 0, 0)
        self.plus_label_edit = QLineEdit("C7+")
        self.plus_cut_start_spin = QSpinBox()
        self.plus_cut_start_spin.setRange(1, 200)
        self.plus_cut_start_spin.setValue(7)
        self.plus_z_edit = self._create_float_edit()
        self.plus_mw_edit = self._create_float_edit()
        self.plus_sg_edit = self._create_float_edit()
        self.plus_characterization_preset = QComboBox()
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
        self.plus_end_spin = QSpinBox()
        self.plus_end_spin.setRange(1, 200)
        self.plus_end_spin.setValue(45)
        self.plus_split_mw_model = QComboBox()
        self.plus_split_mw_model.addItems(["paraffin", "table"])
        self.plus_split_mw_model.setCurrentText("paraffin")
        self.plus_lumping_enabled = QCheckBox("Enable lumping")
        self.plus_lumping_groups_spin = QSpinBox()
        self.plus_lumping_groups_spin.setRange(1, 200)
        self.plus_lumping_groups_spin.setValue(8)
        plus_form.addRow("Label", self.plus_label_edit)
        plus_form.addRow("Cut Start", self.plus_cut_start_spin)
        plus_form.addRow("z+", self.plus_z_edit)
        plus_form.addRow("MW+ (g/mol)", self.plus_mw_edit)
        plus_form.addRow("SG+ @60F", self.plus_sg_edit)
        plus_form.addRow("Characterization", self.plus_characterization_preset)
        plus_form.addRow("Resolved", self.plus_characterization_summary)
        plus_form.addRow("Split To", self.plus_end_spin)
        plus_form.addRow("Split MW Model", self.plus_split_mw_model)
        plus_form.addRow("Lumping", self.plus_lumping_enabled)
        plus_form.addRow("Lumping Groups", self.plus_lumping_groups_spin)
        self.heavy_stack.addWidget(plus_page)

        inline_page = QWidget()
        inline_form = QFormLayout(inline_page)
        inline_form.setContentsMargins(0, 0, 0, 0)
        self.inline_component_id_edit = QLineEdit("PSEUDO_PLUS")
        self.inline_name_edit = QLineEdit("PSEUDO+")
        self.inline_formula_edit = QLineEdit("PSEUDO+")
        self.inline_z_edit = self._create_float_edit()
        self.inline_mw_edit = self._create_float_edit()
        self.inline_tc_edit = self._create_float_edit()
        self.inline_tc_unit = QComboBox()
        self.inline_tc_unit.addItems([unit.value for unit in TemperatureUnit])
        self.inline_tc_unit.setCurrentText(TemperatureUnit.K.value)
        self.inline_pc_edit = self._create_float_edit()
        self.inline_pc_unit = QComboBox()
        self.inline_pc_unit.addItems([unit.value for unit in PressureUnit])
        self.inline_pc_unit.setCurrentText(PressureUnit.PA.value)
        self.inline_omega_edit = self._create_float_edit()

        inline_tc_row = QHBoxLayout()
        inline_tc_row.setContentsMargins(0, 0, 0, 0)
        inline_tc_row.addWidget(self.inline_tc_edit)
        inline_tc_row.addWidget(self.inline_tc_unit)

        inline_pc_row = QHBoxLayout()
        inline_pc_row.setContentsMargins(0, 0, 0, 0)
        inline_pc_row.addWidget(self.inline_pc_edit)
        inline_pc_row.addWidget(self.inline_pc_unit)

        inline_form.addRow("Component ID", self.inline_component_id_edit)
        inline_form.addRow("Name", self.inline_name_edit)
        inline_form.addRow("Formula", self.inline_formula_edit)
        inline_form.addRow("Mole Fraction", self.inline_z_edit)
        inline_form.addRow("MW (g/mol)", self.inline_mw_edit)
        inline_form.addRow("Tc", inline_tc_row)
        inline_form.addRow("Pc", inline_pc_row)
        inline_form.addRow("Omega", self.inline_omega_edit)
        self.heavy_stack.addWidget(inline_page)

        heavy_layout.addWidget(self.heavy_stack)
        layout.addWidget(heavy_group)

        self._on_heavy_mode_changed()
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()

    def _create_float_edit(self) -> QLineEdit:
        """Create a numeric line edit used by the heavy-end controls."""
        edit = QLineEdit()
        validator = QDoubleValidator(edit)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        edit.setValidator(validator)
        return edit

    def _get_heavy_mode(self) -> str:
        return str(self.heavy_mode.currentData())

    def _on_heavy_mode_changed(self, *_args) -> None:
        """Switch the visible heavy-end editor and refresh validation state."""
        mode = self._get_heavy_mode()
        if mode == HEAVY_MODE_PLUS:
            self.heavy_stack.setCurrentIndex(1)
        elif mode == HEAVY_MODE_INLINE:
            self.heavy_stack.setCurrentIndex(2)
        else:
            self.heavy_stack.setCurrentIndex(0)
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()
        self._update_sum()
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

    def _current_plus_characterization_preset(self) -> PlusFractionCharacterizationPreset:
        return PlusFractionCharacterizationPreset(self.plus_characterization_preset.currentData())

    def set_calculation_type_context(self, calc_type: CalculationType) -> None:
        """Provide the current workflow so auto characterization can resolve honestly."""
        self._calculation_type_context = calc_type
        self._refresh_plus_characterization_preview()

    def _set_plus_controls_from_resolved_entry(self, plus_fraction: PlusFractionEntry) -> None:
        self.plus_end_spin.blockSignals(True)
        self.plus_split_mw_model.blockSignals(True)
        self.plus_lumping_enabled.blockSignals(True)
        self.plus_lumping_groups_spin.blockSignals(True)
        try:
            self.plus_end_spin.setValue(plus_fraction.max_carbon_number)
            self.plus_split_mw_model.setCurrentText(plus_fraction.split_mw_model)
            self.plus_lumping_enabled.setChecked(plus_fraction.lumping_enabled)
            self.plus_lumping_groups_spin.setValue(plus_fraction.lumping_n_groups)
        finally:
            self.plus_end_spin.blockSignals(False)
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
                return None, "Auto: enter z+, MW+, and the light-end feed to resolve a validated profile."
            if preset is PlusFractionCharacterizationPreset.MANUAL:
                return None, "Manual: edit split/lumping settings directly."
            settings = PLUS_FRACTION_PRESET_SETTINGS[preset]
            return None, (
                f"{PLUS_FRACTION_PRESET_LABELS[preset]}; split MW model {settings.split_mw_model}, "
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
            self.plus_split_mw_model.blockSignals(True)
            self.plus_lumping_enabled.blockSignals(True)
            self.plus_lumping_groups_spin.blockSignals(True)
            try:
                self.plus_end_spin.setValue(settings.max_carbon_number)
                self.plus_split_mw_model.setCurrentText(settings.split_mw_model)
                self.plus_lumping_enabled.setChecked(settings.lumping_enabled)
                self.plus_lumping_groups_spin.setValue(settings.lumping_n_groups)
            finally:
                self.plus_end_spin.blockSignals(False)
                self.plus_split_mw_model.blockSignals(False)
                self.plus_lumping_enabled.blockSignals(False)
                self.plus_lumping_groups_spin.blockSignals(False)

        self.plus_end_spin.setEnabled(manual)
        self.plus_split_mw_model.setEnabled(manual)
        self.plus_lumping_enabled.setEnabled(manual)
        self._sync_plus_lumping_state()

    def _scaled_metric(self, value: int) -> int:
        """Scale metrics relative to the current default desktop baseline."""
        return scale_metric(value, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale non-QSS geometry to follow the app zoom level."""
        self._ui_scale = ui_scale
        for row in range(self.table.rowCount()):
            combo = self.table.cellWidget(row, 0)
            if isinstance(combo, ClickSelectComboBox):
                combo.apply_ui_scale(ui_scale)
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

        for widget in [
            self.plus_label_edit,
            self.plus_z_edit,
            self.plus_mw_edit,
            self.plus_sg_edit,
            self.inline_component_id_edit,
            self.inline_name_edit,
            self.inline_formula_edit,
            self.inline_z_edit,
            self.inline_mw_edit,
            self.inline_tc_edit,
            self.inline_pc_edit,
            self.inline_omega_edit,
        ]:
            widget.textChanged.connect(self._on_cell_changed)

        for combo in [self.inline_tc_unit, self.inline_pc_unit]:
            combo.currentTextChanged.connect(self._on_cell_changed)
        self.plus_characterization_preset.currentIndexChanged.connect(self._on_cell_changed)
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

    def _add_component_row(self, comp_id: str, fraction: float) -> None:
        """Add a component row with values."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Component selector (combobox)
        combo = ClickSelectComboBox(ui_scale=self._ui_scale)
        combo.setEditable(True)
        combo.addItems(STANDARD_COMPONENTS)
        if comp_id:
            idx = combo.findText(comp_id)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentText(comp_id)
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
        for item in self.table.selectedItems():
            rows.add(item.row())

        # Also check for selected widgets (comboboxes)
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget and widget.hasFocus():
                rows.add(row)

        # Remove rows in reverse order to preserve indices
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)

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
        self.plus_label_edit.setText("C7+")
        self.plus_cut_start_spin.setValue(7)
        self.plus_z_edit.clear()
        self.plus_mw_edit.clear()
        self.plus_sg_edit.clear()
        self.plus_characterization_preset.setCurrentIndex(0)
        self.plus_end_spin.setValue(45)
        self.plus_split_mw_model.setCurrentText("paraffin")
        self.plus_lumping_enabled.setChecked(False)
        self.plus_lumping_groups_spin.setValue(8)
        self._refresh_plus_characterization_preview()
        self._sync_plus_lumping_state()

        self.inline_component_id_edit.setText("PSEUDO_PLUS")
        self.inline_name_edit.setText("PSEUDO+")
        self.inline_formula_edit.setText("PSEUDO+")
        self.inline_z_edit.clear()
        self.inline_mw_edit.clear()
        self.inline_tc_edit.clear()
        self.inline_tc_unit.setCurrentText(TemperatureUnit.K.value)
        self.inline_pc_edit.clear()
        self.inline_pc_unit.setCurrentText(PressureUnit.PA.value)
        self.inline_omega_edit.clear()

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

        label = self.plus_label_edit.text().strip() or "C7+"
        z_plus, error = self._parse_float(self.plus_z_edit.text(), "Plus-fraction z+")
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

        component_id = self.inline_component_id_edit.text().strip()
        name = self.inline_name_edit.text().strip()
        formula = self.inline_formula_edit.text().strip() or name
        z_inline, error = self._parse_float(self.inline_z_edit.text(), "Inline pseudo mole fraction")
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
            spec = InlineComponentSpec(
                component_id=component_id,
                name=name,
                formula=formula,
                molecular_weight_g_per_mol=float(mw),
                critical_temperature_k=temperature_to_k(
                    float(tc_raw),
                    TemperatureUnit(self.inline_tc_unit.currentText()),
                ),
                critical_pressure_pa=pressure_to_pa(
                    float(pc_raw),
                    PressureUnit(self.inline_pc_unit.currentText()),
                ),
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
            z_plus, error = self._parse_float(self.plus_z_edit.text(), "Plus-fraction z+")
            if error is None and z_plus is not None:
                self.plus_z_edit.setText(f"{float(z_plus) / total:.6f}")
        elif self._get_heavy_mode() == HEAVY_MODE_INLINE:
            z_inline, error = self._parse_float(self.inline_z_edit.text(), "Inline pseudo mole fraction")
            if error is None and z_inline is not None:
                self.inline_z_edit.setText(f"{float(z_inline) / total:.6f}")

    def _on_cell_changed(self, *args) -> None:
        """Handle cell value changes."""
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

    def _sync_column_widths(self) -> None:
        """Keep the component column readable while letting mole fractions breathe."""
        viewport_width = self.table.viewport().width()
        if viewport_width <= 0:
            viewport_width = self.table.sizeHint().width()
        if viewport_width <= 0:
            return

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

        mole_fraction_min_width = self._scaled_metric(MOLE_FRACTION_COLUMN_MIN_WIDTH)
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

        plus_fraction, _ = self._get_plus_fraction_entry()
        if plus_fraction is not None:
            total += plus_fraction.z_plus

        inline_spec, inline_z, _ = self._get_inline_component_spec()
        if inline_spec is not None and inline_z is not None:
            total += inline_z
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
            # Get component ID from combobox
            widget = self.table.cellWidget(row, 0)
            if widget:
                comp_id = widget.currentText().strip()
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
            self.heavy_mode.setCurrentIndex(self.heavy_mode.findData(HEAVY_MODE_PLUS))
            self.plus_label_edit.setText(composition.plus_fraction.label)
            self.plus_cut_start_spin.setValue(composition.plus_fraction.cut_start)
            self.plus_z_edit.setText(f"{composition.plus_fraction.z_plus:.6f}")
            self.plus_mw_edit.setText(f"{composition.plus_fraction.mw_plus_g_per_mol:.6f}")
            self.plus_sg_edit.setText(
                "" if composition.plus_fraction.sg_plus_60f is None else f"{composition.plus_fraction.sg_plus_60f:.6f}"
            )
            preset_index = self.plus_characterization_preset.findData(
                composition.plus_fraction.characterization_preset
            )
            if preset_index >= 0:
                self.plus_characterization_preset.setCurrentIndex(preset_index)
            self.plus_end_spin.setValue(composition.plus_fraction.max_carbon_number)
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
            self.heavy_mode.setCurrentIndex(self.heavy_mode.findData(HEAVY_MODE_INLINE))
            self.inline_component_id_edit.setText(spec.component_id)
            self.inline_name_edit.setText(spec.name)
            self.inline_formula_edit.setText(spec.formula)
            if inline_fraction is not None:
                self.inline_z_edit.setText(f"{inline_fraction:.6f}")
            self.inline_mw_edit.setText(f"{spec.molecular_weight_g_per_mol:.6f}")
            self.inline_tc_unit.setCurrentText(TemperatureUnit.K.value)
            self.inline_tc_edit.setText(f"{spec.critical_temperature_k:.6f}")
            self.inline_pc_unit.setCurrentText(PressureUnit.PA.value)
            self.inline_pc_edit.setText(f"{spec.critical_pressure_pa:.6f}")
            self.inline_omega_edit.setText(f"{spec.omega:.6f}")

        self._sync_table_height()
        self._update_sum()
        self.composition_edited.emit()
