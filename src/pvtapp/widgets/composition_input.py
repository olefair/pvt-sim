"""Composition input widget with validation and normalization.

Provides a spreadsheet-like interface for entering fluid compositions
with strict validation ensuring mole fractions sum to 1.0.
"""

from typing import Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QDoubleValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QComboBox,
    QLabel,
    QMessageBox,
    QGroupBox,
    QSizePolicy,
    QLineEdit,
    QStyledItemDelegate,
)

from pvtapp.schemas import ComponentEntry, FluidComposition, COMPOSITION_SUM_TOLERANCE
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric


# Standard components available for selection
STANDARD_COMPONENTS = [
    "N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "nC4",
    "iC5", "nC5", "C6", "C7+",
]

COMPONENT_DROPDOWN_BUTTON_WIDTH = 34
COMPONENT_COLUMN_SIDE_MARGIN = 6
COMPONENT_COLUMN_MIN_WIDTH = 96
COMPONENT_COLUMN_MAX_WIDTH = 140
MOLE_FRACTION_COLUMN_MIN_WIDTH = 108


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

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ui_scale = DEFAULT_UI_SCALE
        self._setup_ui()
        self._connect_signals()

        # Add default components
        self._add_default_components()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Group box for composition
        group = QGroupBox("Fluid Composition")
        group_layout = QVBoxLayout(group)

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
        self.normalize_btn = QPushButton("Normalize to 1.0")
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
        self.table.cellChanged.connect(self._on_cell_changed)

    def _add_default_components(self) -> None:
        """Add common gas/oil components as starting point."""
        defaults = [
            ("C1", 0.50),
            ("C2", 0.10),
            ("C3", 0.10),
            ("nC4", 0.10),
            ("nC5", 0.10),
            ("C6", 0.10),
        ]

        self.table.blockSignals(True)
        for comp_id, fraction in defaults:
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
        if self.table.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                "Clear Composition",
                "Are you sure you want to clear all components?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.table.setRowCount(0)
                self._sync_table_height()
                self._update_sum()
                self.composition_edited.emit()

    def _normalize(self) -> None:
        """Normalize all mole fractions to sum to 1.0."""
        total = self._get_sum()
        if total <= 0:
            QMessageBox.warning(
                self,
                "Cannot Normalize",
                "Total must be greater than zero to normalize.",
            )
            return

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

        self._sync_table_height()
        self._update_sum()
        self.composition_edited.emit()

    def _on_cell_changed(self, *args) -> None:
        """Handle cell value changes."""
        self._update_sum()
        self.composition_edited.emit()

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
            self.sum_status.setText("(Close - click Normalize)")
            self.sum_status.setStyleSheet("color: orange; font-weight: bold;")
            self.sum_label.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.sum_status.setText("(Must sum to 1.0)")
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

    def validate(self) -> Tuple[bool, str]:
        """Validate the current composition.

        Returns:
            Tuple of (is_valid, error_message)
        """
        components = self._get_runtime_components()

        if not components:
            return False, "At least one component is required"

        # Check for duplicate IDs
        ids = [c[0] for c in components]
        if len(ids) != len(set(ids)):
            duplicates = [id_ for id_ in ids if ids.count(id_) > 1]
            return False, f"Duplicate component IDs: {set(duplicates)}"

        # Check for negative fractions
        for comp_id, fraction in components:
            if fraction < 0:
                return False, f"Negative mole fraction for {comp_id}"
            if fraction > 1:
                return False, f"Mole fraction > 1 for {comp_id}"

        # Check sum
        total = sum(f for _, f in components)
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

        components = self._get_runtime_components()
        entries = [
            ComponentEntry(component_id=cid, mole_fraction=frac)
            for cid, frac in components
        ]

        try:
            composition = FluidComposition(components=entries)
            self.composition_changed.emit(composition)
            return composition
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def set_composition(self, composition: FluidComposition) -> None:
        """Load a composition into the widget."""
        self.table.blockSignals(True)
        self.table.setRowCount(0)

        for entry in composition.components:
            self._add_component_row(entry.component_id, entry.mole_fraction)

        self.table.blockSignals(False)
        self._sync_table_height()
        self._update_sum()
        self.composition_edited.emit()
