"""Results display widgets with tables and plots.

Provides tabular and graphical display of calculation results
with export capabilities.
"""

import csv
import json
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QFrame,
    QGroupBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
)

from pvtapp.plus_fraction_policy import describe_plus_fraction_policy
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.text_output_view import TextOutputWidget
from pvtapp.schemas import (
    RunResult,
    RunStatus,
    PTFlashResult,
    PTFlashConfig,
    BubblePointResult,
    DewPointResult,
    PhaseEnvelopeResult,
    CCEResult,
    DLResult,
    CVDResult,
    SeparatorResult,
    SaturationPointConfig,
    PressureUnit,
    TemperatureUnit,
    pressure_from_pa,
    temperature_from_k,
)


PLOT_SURFACE_COLOR = "#0f1a2b"
PLOT_CANVAS_COLOR = PLOT_SURFACE_COLOR
PLOT_TEXT_COLOR = "#e5e7eb"
PLOT_GRID_COLOR = "#223044"
PLOT_LEGEND_FACE_COLOR = "#121f34"
INLINE_PSEUDO_TOKEN = "PSEUDO_PLUS"
INLINE_PSEUDO_FALLBACK_LABEL = "Pseudo+"


def _display_component_label(
    component_id: str,
    current_result: Optional[RunResult],
) -> str:
    """Map runtime component tokens to compact user-facing labels."""
    normalized = component_id.strip()
    if current_result is not None:
        plus_fraction = current_result.config.composition.plus_fraction
        if plus_fraction is not None and normalized == plus_fraction.label.strip():
            return plus_fraction.label.strip()
        for spec in current_result.config.composition.inline_components:
            if spec.component_id.strip() == normalized:
                display_label = spec.name.strip() or spec.formula.strip()
                if display_label.upper() in {"PSEUDO+", "PSEUDO_PLUS"}:
                    return INLINE_PSEUDO_FALLBACK_LABEL
                return display_label or INLINE_PSEUDO_FALLBACK_LABEL
    if normalized == INLINE_PSEUDO_TOKEN:
        return INLINE_PSEUDO_FALLBACK_LABEL
    return normalized


def _format_temperature_unit(unit: TemperatureUnit) -> str:
    """Render compact temperature units with a visible degree marker."""
    return f"\N{DEGREE SIGN}{unit.value}"


def _format_pressure(value_pa: float, unit: PressureUnit, *, precision: int = 2) -> str:
    """Format a pressure in the requested display unit."""
    return f"{pressure_from_pa(value_pa, unit):.{precision}f} {unit.value}"


def _format_temperature(value_k: float, unit: TemperatureUnit, *, precision: int = 2) -> str:
    """Format a temperature in the requested display unit."""
    return f"{temperature_from_k(value_k, unit):.{precision}f} {_format_temperature_unit(unit)}"


def _format_calculation_type_label(calculation_type) -> str:
    """Render calculation-type labels for user-facing tables."""
    value = calculation_type.value
    labels = {
        "pt_flash": "PT Flash",
        "bubble_point": "Bubble Point",
        "dew_point": "Dew Point",
        "phase_envelope": "Phase Envelope",
        "cce": "CCE",
        "differential_liberation": "DL",
        "cvd": "CVD",
        "separator": "Separator",
    }
    return labels.get(value, value.replace("_", " ").title())


class ResultsTableWidget(QWidget):
    """Widget for displaying calculation results in tabular form.

    Signals:
        export_requested: Emitted when user requests export (format)
    """

    export_requested = Signal(str)
    CAPTURE_BASE_COLUMNS = ("Run ID", "Run", "Calculation", "Status", "Captured At")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_result: Optional[RunResult] = None
        self._captured_rows: list[dict[str, str]] = []
        self._captured_columns: list[str] = list(self.CAPTURE_BASE_COLUMNS)
        self._display_is_cached = False
        self._ui_scale = DEFAULT_UI_SCALE
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

        # Header with run info
        self._header_layout = QVBoxLayout()
        self._header_layout.setContentsMargins(0, 0, 0, 0)
        self._header_layout.setSpacing(4)

        self._header_meta_row = QHBoxLayout()
        self._header_meta_row.setContentsMargins(0, 0, 0, 0)
        self._header_meta_row.setSpacing(8)
        self.run_id_label = QLabel("No results")
        self.run_id_label.setStyleSheet("font-weight: bold;")
        self.run_id_label.setWordWrap(False)
        self.run_id_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._header_meta_row.addWidget(self.run_id_label, 1)
        self._header_layout.addLayout(self._header_meta_row)

        self._header_actions_row = QHBoxLayout()
        self._header_actions_row.setContentsMargins(0, 0, 0, 0)
        self._header_actions_row.setSpacing(8)
        self.status_label = QLabel("")
        self._header_actions_row.addWidget(self.status_label)
        self._header_actions_row.addStretch()

        self.capture_summary_btn = QPushButton("Capture Summary")
        self.capture_summary_btn.clicked.connect(self.capture_current_summary)
        self._header_actions_row.addWidget(self.capture_summary_btn)

        # Export buttons
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit("json"))
        self._header_actions_row.addWidget(self.export_csv_btn)
        self._header_actions_row.addWidget(self.export_json_btn)
        self._header_layout.addLayout(self._header_actions_row)

        self._layout.addLayout(self._header_layout)

        # Public tables remain stable for existing desktop/widget tests.
        self.summary_table = self._create_section_table()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Property", "Value"])

        self.composition_table = self._create_section_table()
        self.details_table = self._create_section_table()

        self.summary_section = self._build_table_section("Summary", self.summary_table)
        self.composition_section = self._build_table_section("Compositions", self.composition_table)
        self.details_section = self._build_table_section("Details", self.details_table)
        self.captured_section = QGroupBox("Captured")
        self.captured_section.setObjectName("ResultsSection")
        captured_layout = QVBoxLayout(self.captured_section)
        captured_layout.setContentsMargins(0, scale_metric(8, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE), 0, 0)
        captured_layout.setSpacing(scale_metric(8, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE))

        captured_header = QHBoxLayout()
        captured_header.setContentsMargins(0, 0, 0, 0)
        captured_header.setSpacing(scale_metric(8, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE))
        self.captured_status_label = QLabel("Captured rows: 0")
        self.captured_status_label.setStyleSheet("color: #9ca3af;")
        captured_header.addWidget(self.captured_status_label)
        captured_header.addStretch()

        self.export_captured_csv_btn = QPushButton("Export Captured CSV")
        self.export_captured_csv_btn.clicked.connect(self._prompt_export_captured_csv)
        captured_header.addWidget(self.export_captured_csv_btn)

        self.export_captured_json_btn = QPushButton("Export Captured JSON")
        self.export_captured_json_btn.clicked.connect(self._prompt_export_captured_json)
        captured_header.addWidget(self.export_captured_json_btn)

        self.export_captured_excel_btn = QPushButton("Export Captured Excel")
        self.export_captured_excel_btn.clicked.connect(self._prompt_export_captured_xlsx)
        captured_header.addWidget(self.export_captured_excel_btn)

        self.clear_captured_btn = QPushButton("Clear Captured")
        self.clear_captured_btn.clicked.connect(self.clear_captured)
        captured_header.addWidget(self.clear_captured_btn)
        captured_layout.addLayout(captured_header)

        self.captured_table = self._create_section_table()
        self.captured_table.setAlternatingRowColors(True)
        captured_layout.addWidget(self.captured_table)
        self._sections = (
            self.summary_section,
            self.composition_section,
            self.details_section,
            self.captured_section,
        )

        self.sections_scroll = QScrollArea()
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._sections_host = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_host)
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(10)
        self._sections_layout.addWidget(self.summary_section)
        self._sections_layout.addWidget(self.composition_section)
        self._sections_layout.addWidget(self.details_section)
        self._sections_layout.addWidget(self.captured_section)
        self._sections_layout.addStretch(1)

        self.sections_scroll.setWidget(self._sections_host)
        self._layout.addWidget(self.sections_scroll, 1)
        self._refresh_captured_table()

        # Deprecated legacy attribute kept as a sentinel for compatibility.
        self.tabs = None

    @property
    def current_result(self) -> Optional[RunResult]:
        """Return the result currently rendered in the fixed right rail."""
        return self._current_result

    @property
    def display_is_cached(self) -> bool:
        """Whether the current right-rail result came from saved run artifacts."""
        return self._display_is_cached

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Refresh column sizing after global zoom changes."""
        self._ui_scale = ui_scale
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._header_layout.setSpacing(scale_metric(4, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._header_meta_row.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._header_actions_row.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._sections_layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        for section in self._sections:
            layout = section.layout()
            if layout is not None:
                inset = scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE)
                layout.setContentsMargins(0, inset, 0, 0)
        self._finalize_section_tables()

    def _component_display_label(self, component_id: str) -> str:
        """Map runtime component tokens to compact user-facing labels."""
        return _display_component_label(component_id, self._current_result)

    @staticmethod
    def _create_section_table() -> QTableWidget:
        """Create a compact read-only table for the fixed right rail."""
        table = QTableWidget()
        table.setObjectName("ResultsSectionTable")
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.horizontalHeader().setStretchLastSection(False)
        return table

    @staticmethod
    def _build_table_section(title: str, table: QTableWidget) -> QGroupBox:
        """Wrap a results table in a standalone titled section."""
        section = QGroupBox(title)
        section.setObjectName("ResultsSection")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, scale_metric(8, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE), 0, 0)
        section_layout.setSpacing(0)
        section_layout.addWidget(table)
        return section

    def _compact_summary_columns(self) -> None:
        """Keep the always-on summary table compact in the fixed right rail."""
        self.summary_table.resizeColumnsToContents()
        if self.summary_table.columnCount() < 2:
            return
        for column in range(self.summary_table.columnCount()):
            self.summary_table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
        padding = scale_metric(10, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
        property_width = max(
            scale_metric(120, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
            min(
                scale_metric(168, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
                self.summary_table.columnWidth(0) + padding,
            ),
        )
        value_width = max(
            scale_metric(88, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
            min(
                scale_metric(132, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
                self.summary_table.columnWidth(1) + padding,
            ),
        )
        self.summary_table.setColumnWidth(0, property_width)
        self.summary_table.setColumnWidth(1, value_width)

    def _column_width_bounds(
        self,
        table: QTableWidget,
        column_name: str,
        column_index: int,
    ) -> tuple[int, int]:
        """Return pragmatic min/max widths for right-rail result tables."""
        label = column_name.lower()
        if table is self.composition_table:
            if column_index == 0 and "component" in label:
                return 66, 96
            if any(token in label for token in ("liquid", "vapor")):
                return 84, 120
        if column_index == 0:
            if any(token in label for token in ("component", "property", "stage")):
                return 78, 116
            if "type" in label:
                return 64, 88
            return 56, 96
        if "value" in label:
            return 84, 132
        if "fugacity" in label:
            return 88, 112
        if any(token in label for token in ("temperature", "pressure", "moles")):
            return 80, 104
        if any(token in label for token in ("liquid", "vapor", "feed", "k-value", "z-factor")):
            return 74, 92
        if any(token in label for token in ("dropout", "converged", "frac")):
            return 72, 92
        return 68, 96

    def _compact_data_columns(self, table: QTableWidget) -> None:
        """Size non-summary tables to content rather than stretching the rail."""
        if table.columnCount() == 0:
            return
        table.resizeColumnsToContents()
        for column in range(table.columnCount()):
            header = table.horizontalHeaderItem(column)
            header_label = header.text() if header is not None else ""
            minimum, maximum = self._column_width_bounds(table, header_label, column)
            minimum = scale_metric(minimum, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
            maximum = scale_metric(maximum, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
            table.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            width = max(
                minimum,
                min(
                    maximum,
                    table.columnWidth(column) + scale_metric(10, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
                ),
            )
            table.setColumnWidth(column, width)

    def _expand_columns_to_fill(self, table: QTableWidget) -> None:
        """Distribute unused table width so stacked sections share the same right edge."""
        column_count = table.columnCount()
        if column_count == 0:
            return

        available_width = table.viewport().width()
        if available_width <= 0:
            available_width = (
                table.width()
                - table.verticalHeader().width()
                - (2 * table.frameWidth())
            )
        if available_width <= 0:
            return

        occupied_width = sum(table.columnWidth(column) for column in range(column_count))
        slack = available_width - occupied_width
        if slack <= 0:
            return

        weights: list[float] = []
        for column in range(column_count):
            header = table.horizontalHeaderItem(column)
            label = header.text().lower() if header is not None else ""
            weight = 1.0
            if table is self.composition_table:
                if column == 0 and "component" in label:
                    weight = 0.72
                elif "liquid" in label:
                    weight = 1.08
                elif "vapor" in label:
                    weight = 1.20
            elif table is self.details_table:
                if column == 0 and "component" in label:
                    weight = 0.82
                elif "k-value" in label:
                    weight = 1.18
            weights.append(weight)

        total_weight = sum(weights) or float(column_count)
        distributed = 0
        for column in range(column_count):
            growth = int(round((slack * weights[column]) / total_weight))
            if growth > 0:
                table.setColumnWidth(column, table.columnWidth(column) + growth)
                distributed += growth
        remainder = slack - distributed
        for column in range(column_count):
            if remainder <= 0:
                break
            table.setColumnWidth(column, table.columnWidth(column) + 1)
            remainder -= 1

    def _sync_table_height(self, table: QTableWidget) -> None:
        """Let the outer scroll area own scrolling instead of nested table scrollbars."""
        table.resizeRowsToContents()
        header_height = table.horizontalHeader().height() if table.horizontalHeader().isVisible() else 0
        body_height = sum(table.rowHeight(row) for row in range(table.rowCount()))
        height = max(
            scale_metric(68, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
            header_height
            + body_height
            + (2 * table.frameWidth())
            + scale_metric(2, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
        )
        table.setMinimumHeight(height)
        table.setMaximumHeight(height)

    @staticmethod
    def _section_has_content(table: QTableWidget) -> bool:
        return table.columnCount() > 0 and table.rowCount() > 0

    def _finalize_section_tables(self) -> None:
        """Apply compact widths, fixed heights, and section visibility."""
        self._compact_summary_columns()
        self._compact_data_columns(self.composition_table)
        self._compact_data_columns(self.details_table)
        self._compact_data_columns(self.captured_table)
        for table in (self.summary_table, self.composition_table, self.details_table, self.captured_table):
            self._expand_columns_to_fill(table)

        for table in (self.summary_table, self.composition_table, self.details_table, self.captured_table):
            self._sync_table_height(table)

        self.summary_section.setVisible(True)
        self.composition_section.setVisible(self._section_has_content(self.composition_table))
        self.details_section.setVisible(self._section_has_content(self.details_table))
        self.captured_section.setVisible(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._finalize_section_tables()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._finalize_section_tables()

    def clear(self, *, clear_captured: bool = False) -> None:
        """Clear all result displays."""
        self._current_result = None
        self._display_is_cached = False
        self.run_id_label.setText("No results")
        self.run_id_label.setToolTip("")
        self.status_label.setText("")
        self.status_label.setToolTip("")
        self.summary_table.setRowCount(0)
        self.composition_table.setRowCount(0)
        self.details_table.setRowCount(0)
        if clear_captured:
            self.clear_captured()
        self._finalize_section_tables()

    def display_result(self, result: RunResult, *, cached: bool = False) -> None:
        """Display a calculation result.

        Args:
            result: RunResult to display
        """
        self._current_result = result
        self._display_is_cached = cached
        self.run_id_label.setText(result.run_name or result.run_id or "Run")
        self.run_id_label.setToolTip(result.run_name or result.run_id or "")

        # Set status with color
        status = result.status
        color_map = {
            RunStatus.COMPLETED: "green",
            RunStatus.FAILED: "red",
            RunStatus.CANCELLED: "orange",
            RunStatus.RUNNING: "blue",
            RunStatus.PENDING: "gray",
        }
        color = "#60a5fa" if cached else color_map.get(status, "black")
        status_text = "Cached" if cached else status.value.replace("_", " ").title()
        self.status_label.setText(status_text)
        self.status_label.setToolTip(
            f"Saved run artifact ({status.value.replace('_', ' ').title()})"
            if cached
            else ""
        )
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Display appropriate result type
        if result.pt_flash_result:
            self._display_pt_flash(result.pt_flash_result)
        elif result.bubble_point_result:
            self._display_bubble_point(result.bubble_point_result)
        elif result.dew_point_result:
            self._display_dew_point(result.dew_point_result)
        elif result.phase_envelope_result:
            self._display_phase_envelope(result.phase_envelope_result)
        elif result.cce_result:
            self._display_cce(result.cce_result)
        elif result.dl_result:
            self._display_dl(result.dl_result)
        elif result.cvd_result:
            self._display_cvd(result.cvd_result)
        elif result.separator_result:
            self._display_separator(result.separator_result)
        else:
            self._display_error(result)
        self._finalize_section_tables()

    def capture_current_summary(self) -> None:
        """Append or refresh the compact summary row for the current result."""
        if self._current_result is None:
            QMessageBox.warning(self, "No Results", "No result is loaded to capture.")
            return
        if self._current_result.status != RunStatus.COMPLETED:
            QMessageBox.warning(
                self,
                "Capture Error",
                "Only completed calculations can be captured into the compact summary table.",
            )
            return

        row = self._current_summary_capture_row()
        if row is None:
            QMessageBox.warning(self, "Capture Error", "The current result has no summary values to capture.")
            return

        run_id = row["Run ID"]
        for index, existing in enumerate(self._captured_rows):
            if existing.get("Run ID") == run_id:
                self._captured_rows[index] = row
                break
        else:
            self._captured_rows.append(row)

        for column in row:
            if column not in self._captured_columns:
                self._captured_columns.append(column)

        self._refresh_captured_table()
        self.sections_scroll.ensureWidgetVisible(self.captured_section)

    def clear_captured(self) -> None:
        """Remove all captured compact summary rows."""
        self._captured_rows = []
        self._captured_columns = list(self.CAPTURE_BASE_COLUMNS)
        self._refresh_captured_table()

    def _current_summary_capture_row(self) -> Optional[dict[str, str]]:
        if self._current_result is None:
            return None

        row: dict[str, str] = {
            "Run ID": self._current_result.run_id,
            "Run": self._current_result.run_name or self._current_result.run_id,
            "Calculation": _format_calculation_type_label(self._current_result.config.calculation_type),
            "Status": self._current_result.status.value,
            "Captured At": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        for summary_row in range(self.summary_table.rowCount()):
            prop_item = self.summary_table.item(summary_row, 0)
            value_item = self.summary_table.item(summary_row, 1)
            if prop_item is None or value_item is None:
                continue
            property_name = prop_item.text().strip()
            if not property_name:
                continue
            row[property_name] = value_item.text().strip()

        return row

    def _refresh_captured_table(self) -> None:
        self.captured_table.setColumnCount(len(self._captured_columns))
        self.captured_table.setHorizontalHeaderLabels(self._captured_columns)
        self.captured_table.setRowCount(len(self._captured_rows))

        for row_index, row_data in enumerate(self._captured_rows):
            for column_index, column_name in enumerate(self._captured_columns):
                self.captured_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(row_data.get(column_name, "")),
                )

        self.captured_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        if self._captured_columns:
            last_column = len(self._captured_columns) - 1
            self.captured_table.horizontalHeader().setSectionResizeMode(last_column, QHeaderView.ResizeMode.Stretch)
        self.captured_status_label.setText(f"Captured rows: {len(self._captured_rows)}")
        self._finalize_section_tables()

    def _prompt_export_captured_csv(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Export Captured CSV", "", "CSV Files (*.csv)")
        if filename:
            self._export_captured_csv(filename)

    def _prompt_export_captured_json(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Export Captured JSON", "", "JSON Files (*.json)")
        if filename:
            self._export_captured_json(filename)

    def _prompt_export_captured_xlsx(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(self, "Export Captured Excel", "", "Excel Files (*.xlsx)")
        if filename:
            self._export_captured_xlsx(filename)

    def _ensure_captured_rows(self) -> bool:
        if self._captured_rows:
            return True
        QMessageBox.warning(self, "No Captured Rows", "Capture at least one summary row before exporting.")
        return False

    def _export_captured_csv(self, filename: str) -> None:
        if not self._ensure_captured_rows():
            return
        try:
            with open(filename, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=self._captured_columns)
                writer.writeheader()
                writer.writerows(self._captured_rows)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export captured CSV: {exc}")

    def _export_captured_json(self, filename: str) -> None:
        if not self._ensure_captured_rows():
            return
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                json.dump(self._captured_rows, handle, indent=2)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export captured JSON: {exc}")

    def _export_captured_xlsx(self, filename: str) -> None:
        if not self._ensure_captured_rows():
            return
        try:
            from openpyxl import Workbook
        except ImportError as exc:
            QMessageBox.critical(self, "Export Error", f"openpyxl is required for Excel export: {exc}")
            return

        try:
            workbook = Workbook()
            worksheet = workbook.active
            worksheet.title = "Captured Results"
            worksheet.append(list(self._captured_columns))
            for row in self._captured_rows:
                worksheet.append([row.get(column, "") for column in self._captured_columns])
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            workbook.save(filename)
        except Exception as exc:
            QMessageBox.critical(self, "Export Error", f"Failed to export captured Excel: {exc}")

    def _pt_flash_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred PT flash display units."""
        config: Optional[PTFlashConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.pt_flash_config
        if config is None:
            return PressureUnit.BAR, TemperatureUnit.C
        return config.pressure_unit, config.temperature_unit

    def _saturation_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred saturation display units."""
        config: Optional[SaturationPointConfig] = None
        if self._current_result is not None:
            config = (
                self._current_result.config.bubble_point_config
                or self._current_result.config.dew_point_config
            )
        if config is None:
            return PressureUnit.BAR, TemperatureUnit.C
        return config.pressure_unit, config.temperature_unit

    def _plus_fraction_summary_rows(self) -> list[tuple[str, str]]:
        if self._current_result is None or self._current_result.config.composition.plus_fraction is None:
            return []
        plus_fraction = self._current_result.config.composition.plus_fraction
        return [
            ("C7+ Policy", describe_plus_fraction_policy(plus_fraction)),
            ("C7+ MW+", f"{plus_fraction.mw_plus_g_per_mol:.3f} g/mol"),
            ("C7+ SG+", "-" if plus_fraction.sg_plus_60f is None else f"{plus_fraction.sg_plus_60f:.3f}"),
        ]

    @staticmethod
    def _solver_summary_rows(
        *,
        converged: bool,
        iterations: Optional[int] = None,
        final_residual: Optional[float] = None,
        solver_status: Optional[str] = None,
        invariant_check: Optional[str] = None,
    ) -> list[tuple[str, str]]:
        """Keep low-signal solver bookkeeping below the headline results."""
        rows: list[tuple[str, str]] = []
        rows.append(("Converged", "Yes" if converged else "No"))
        if solver_status is not None:
            normalized_status = solver_status.replace("_", " ").title()
            if not (converged and normalized_status == "Converged"):
                rows.append(("Solver Status", normalized_status))
        if iterations is not None:
            rows.append(("Iterations", str(iterations)))
        if final_residual is not None and not converged:
            rows.append(("Final Residual", f"{final_residual:.2e}"))
        if invariant_check is not None:
            rows.append(("Invariant Check", invariant_check))
        return rows

    def _display_pt_flash(self, result: PTFlashResult) -> None:
        """Display PT flash results."""
        pressure_unit, temperature_unit = self._pt_flash_display_units()
        config = self._current_result.config.pt_flash_config if self._current_result else None

        # Summary table
        summary_data = [
            ("Phase State", result.phase.title()),
        ]

        if config is not None:
            summary_data.extend([
                ("Pressure", _format_pressure(config.pressure_pa, pressure_unit)),
                ("Temperature", _format_temperature(config.temperature_k, temperature_unit)),
            ])

        summary_data.extend([
            ("Vapor Fraction", f"{result.vapor_fraction:.6f}"),
            ("Liquid Fraction", f"{1 - result.vapor_fraction:.6f}"),
        ])
        summary_data.extend(self._plus_fraction_summary_rows())
        summary_data.extend(
            self._solver_summary_rows(
                converged=result.converged,
                iterations=result.diagnostics.iterations,
                final_residual=result.diagnostics.final_residual,
                solver_status=result.diagnostics.status.value,
            )
        )

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # Composition table
        components = sorted(result.liquid_composition.keys())
        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels([
            "Component", "Feed (z)", "Liquid (x)", "Vapor (y)"
        ])
        self.composition_table.setRowCount(len(components))

        for row, comp in enumerate(components):
            self.composition_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))

            # Calculate feed from material balance (approximate)
            x = result.liquid_composition.get(comp, 0)
            y = result.vapor_composition.get(comp, 0)
            nv = result.vapor_fraction
            z = (1 - nv) * x + nv * y

            self.composition_table.setItem(row, 1, QTableWidgetItem(f"{z:.6f}"))
            self.composition_table.setItem(row, 2, QTableWidgetItem(f"{x:.6f}"))
            self.composition_table.setItem(row, 3, QTableWidgetItem(f"{y:.6f}"))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        # Details table (K-values and fugacities)
        self.details_table.setColumnCount(4)
        self.details_table.setHorizontalHeaderLabels([
            "Component", "K-value", "Liquid Fugacity", "Vapor Fugacity"
        ])
        self.details_table.setRowCount(len(components))

        for row, comp in enumerate(components):
            self.details_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))
            self.details_table.setItem(
                row, 1, QTableWidgetItem(f"{result.K_values.get(comp, 0):.6f}")
            )
            self.details_table.setItem(
                row, 2, QTableWidgetItem(f"{result.liquid_fugacity.get(comp, 0):.6e}")
            )
            self.details_table.setItem(
                row, 3, QTableWidgetItem(f"{result.vapor_fugacity.get(comp, 0):.6e}")
            )

        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_phase_envelope(self, result: PhaseEnvelopeResult) -> None:
        """Display phase envelope results."""
        self.details_table.setRowCount(0)

        # Summary
        summary_data = [
            ("Bubble Points", str(len(result.bubble_curve))),
            ("Dew Points", str(len(result.dew_curve))),
        ]

        if result.critical_point:
            summary_data.append((
                "Critical Point",
                f"{result.critical_point.temperature_k - 273.15:.2f} C, "
                f"{result.critical_point.pressure_pa / 1e5:.2f} bar"
            ))

        if result.cricondenbar:
            summary_data.append((
                "Cricondenbar",
                f"{result.cricondenbar.temperature_k - 273.15:.2f} C, "
                f"{result.cricondenbar.pressure_pa / 1e5:.2f} bar"
            ))

        if result.cricondentherm:
            summary_data.append((
                "Cricondentherm",
                f"{result.cricondentherm.temperature_k - 273.15:.2f} C, "
                f"{result.cricondentherm.pressure_pa / 1e5:.2f} bar"
            ))
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # Envelope points in composition table
        all_points = (
            [(p, "Bubble") for p in result.bubble_curve] +
            [(p, "Dew") for p in result.dew_curve]
        )

        self.composition_table.setColumnCount(3)
        self.composition_table.setHorizontalHeaderLabels([
            "Type", "Temperature (C)", "Pressure (bar)"
        ])
        self.composition_table.setRowCount(len(all_points))

        for row, (point, ptype) in enumerate(all_points):
            self.composition_table.setItem(row, 0, QTableWidgetItem(ptype))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{point.temperature_k - 273.15:.2f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{point.pressure_pa / 1e5:.2f}")
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_saturation_result(
        self,
        result: BubblePointResult | DewPointResult,
        *,
        pressure_label: str,
        stability_label: str,
        stability_value: bool,
    ) -> None:
        """Display bubble-point or dew-point results."""
        pressure_unit, temperature_unit = self._saturation_display_units()
        summary_data = [
            (pressure_label, _format_pressure(result.pressure_pa, pressure_unit)),
            ("Temperature", _format_temperature(result.temperature_k, temperature_unit)),
            (stability_label, "Yes" if stability_value else "No"),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())
        summary_data.extend(
            self._solver_summary_rows(
                converged=result.converged,
                iterations=result.iterations,
                final_residual=result.residual,
                solver_status=None if result.diagnostics is None else result.diagnostics.status.value,
                invariant_check=None if result.certificate is None else ("Pass" if result.certificate.passed else "Fail"),
            )
        )

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        components = sorted(
            set(result.liquid_composition)
            | set(result.vapor_composition)
            | set(result.k_values)
        )

        self.composition_table.setColumnCount(3)
        self.composition_table.setHorizontalHeaderLabels(
            ["Component", "Liquid (x)", "Vapor (y)"]
        )
        self.composition_table.setRowCount(len(components))

        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Component", "K-value"])
        self.details_table.setRowCount(len(components))

        for row, comp in enumerate(components):
            self.composition_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{result.liquid_composition.get(comp, 0.0):.6f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{result.vapor_composition.get(comp, 0.0):.6f}")
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))
            self.details_table.setItem(
                row, 1, QTableWidgetItem(f"{result.k_values.get(comp, 0.0):.6f}")
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_bubble_point(self, result: BubblePointResult) -> None:
        """Display bubble-point results."""
        self._display_saturation_result(
            result,
            pressure_label="Bubble Pressure",
            stability_label="Stable Liquid",
            stability_value=result.stable_liquid,
        )

    def _display_dew_point(self, result: DewPointResult) -> None:
        """Display dew-point results."""
        self._display_saturation_result(
            result,
            pressure_label="Dew Pressure",
            stability_label="Stable Vapor",
            stability_value=result.stable_vapor,
        )

    def _display_cce(self, result: CCEResult) -> None:
        """Display CCE results."""
        self.details_table.setRowCount(0)

        # Summary
        summary_data = [
            ("Temperature", f"{result.temperature_k - 273.15:.2f} {_format_temperature_unit(TemperatureUnit.C)}"),
            ("Steps", str(len(result.steps))),
        ]

        if result.saturation_pressure_pa:
            summary_data.append((
                "Saturation Pressure",
                f"{result.saturation_pressure_pa / 1e5:.2f} bar"
            ))
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # Steps in composition table
        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels([
            "Pressure (bar)", "Rel. Volume", "Liquid Frac.", "Z-factor"
        ])
        self.composition_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row, 0, QTableWidgetItem(f"{step.pressure_pa / 1e5:.2f}")
            )
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{step.relative_volume:.4f}")
            )
            lf = step.liquid_fraction if step.liquid_fraction else ""
            self.composition_table.setItem(row, 2, QTableWidgetItem(
                f"{lf:.4f}" if lf else "-"
            ))
            zf = step.z_factor if step.z_factor else ""
            self.composition_table.setItem(row, 3, QTableWidgetItem(
                f"{zf:.4f}" if zf else "-"
            ))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_dl(self, result: DLResult) -> None:
        """Display DL results."""
        summary_data = [
            ("Temperature", f"{result.temperature_k - 273.15:.2f} {_format_temperature_unit(TemperatureUnit.C)}"),
            ("Bubble Pressure", f"{result.bubble_pressure_pa / 1e5:.2f} bar"),
            ("Initial Rs", f"{result.rsi:.4f}"),
            ("Initial Bo", f"{result.boi:.4f}"),
            ("Converged", "Yes" if result.converged else "No"),
            ("Steps", str(len(result.steps))),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        self.composition_table.setColumnCount(5)
        self.composition_table.setHorizontalHeaderLabels(
            ["Pressure (bar)", "Rs", "Bo", "Bt", "Vapor Frac."]
        )
        self.composition_table.setRowCount(len(result.steps))

        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Step", "Liquid Moles Remaining"])
        self.details_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row, 0, QTableWidgetItem(f"{step.pressure_pa / 1e5:.2f}")
            )
            self.composition_table.setItem(row, 1, QTableWidgetItem(f"{step.rs:.4f}"))
            self.composition_table.setItem(row, 2, QTableWidgetItem(f"{step.bo:.4f}"))
            self.composition_table.setItem(row, 3, QTableWidgetItem(f"{step.bt:.4f}"))
            self.composition_table.setItem(
                row, 4, QTableWidgetItem(f"{step.vapor_fraction:.4f}")
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            liquid_moles = (
                "-"
                if step.liquid_moles_remaining is None
                else f"{step.liquid_moles_remaining:.6f}"
            )
            self.details_table.setItem(row, 1, QTableWidgetItem(liquid_moles))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_cvd(self, result: CVDResult) -> None:
        """Display CVD results."""
        summary_data = [
            ("Temperature", f"{result.temperature_k - 273.15:.2f} {_format_temperature_unit(TemperatureUnit.C)}"),
            ("Dew Pressure", f"{result.dew_pressure_pa / 1e5:.2f} bar"),
            ("Initial Z", f"{result.initial_z:.4f}"),
            ("Steps", str(len(result.steps))),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels([
            "Pressure (bar)", "Liquid Dropout", "Cum. Gas", "Z (2-phase)"
        ])
        self.composition_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row, 0, QTableWidgetItem(f"{step.pressure_pa / 1e5:.2f}")
            )
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{step.liquid_dropout:.4f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{step.cumulative_gas_produced:.4f}")
            )
            z_two_phase = "-" if step.z_two_phase is None else f"{step.z_two_phase:.4f}"
            self.composition_table.setItem(row, 3, QTableWidgetItem(z_two_phase))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Step", "Moles Remaining"])
        self.details_table.setRowCount(len(result.steps))
        for row, step in enumerate(result.steps):
            self.details_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            moles_remaining = "-" if step.moles_remaining is None else f"{step.moles_remaining:.6f}"
            self.details_table.setItem(row, 1, QTableWidgetItem(moles_remaining))

        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_separator(self, result: SeparatorResult) -> None:
        """Display separator-train results."""
        summary_data = [
            ("Converged", "Yes" if result.converged else "No"),
            ("Bo", f"{result.bo:.4f}"),
            ("Rs", f"{result.rs:.4f}"),
            ("Rs (scf/STB)", f"{result.rs_scf_stb:.4f}"),
            ("Bg", f"{result.bg:.4f}"),
            ("API Gravity", f"{result.api_gravity:.2f}"),
            ("Oil Density", f"{result.stock_tank_oil_density:.4f}"),
            ("Stages", str(len(result.stages))),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels(
            ["Stage", "Pressure (bar)", "Temperature (C)", "Vapor Frac."]
        )
        self.composition_table.setRowCount(len(result.stages))

        self.details_table.setColumnCount(4)
        self.details_table.setHorizontalHeaderLabels(
            ["Stage", "Liquid Moles", "Vapor Moles", "Converged"]
        )
        self.details_table.setRowCount(len(result.stages))

        for row, stage in enumerate(result.stages):
            stage_label = stage.stage_name or f"Stage {stage.stage_number}"
            self.composition_table.setItem(row, 0, QTableWidgetItem(stage_label))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{stage.pressure_pa / 1e5:.2f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{stage.temperature_k - 273.15:.2f}")
            )
            vapor_fraction = "-" if stage.vapor_fraction is None else f"{stage.vapor_fraction:.4f}"
            self.composition_table.setItem(row, 3, QTableWidgetItem(vapor_fraction))

            self.details_table.setItem(row, 0, QTableWidgetItem(stage_label))
            liquid_moles = "-" if stage.liquid_moles is None else f"{stage.liquid_moles:.6f}"
            vapor_moles = "-" if stage.vapor_moles is None else f"{stage.vapor_moles:.6f}"
            self.details_table.setItem(row, 1, QTableWidgetItem(liquid_moles))
            self.details_table.setItem(row, 2, QTableWidgetItem(vapor_moles))
            self.details_table.setItem(
                row, 3, QTableWidgetItem("Yes" if stage.converged else "No")
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_error(self, result: RunResult) -> None:
        """Display error result."""
        self.summary_table.setRowCount(1)
        self.summary_table.setItem(0, 0, QTableWidgetItem("Error"))
        self.summary_table.setItem(0, 1, QTableWidgetItem(
            result.error_message or "Unknown error"
        ))

        self.composition_table.setRowCount(0)
        self.details_table.setRowCount(0)


class ResultsSidebarWidget(QWidget):
    """Fixed right-rail surface: summary tables on top, text report below."""

    def __init__(
        self,
        table_widget: Optional[ResultsTableWidget] = None,
        report_widget: Optional[TextOutputWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.table_widget = table_widget or ResultsTableWidget()
        self.report_widget = report_widget or TextOutputWidget()

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(scale_metric(4, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE))
        self._splitter.addWidget(self.table_widget)
        self._splitter.addWidget(self.report_widget)
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 2)
        self._splitter.setSizes([420, 260])

        self._layout.addWidget(self._splitter, 1)

    @property
    def current_result(self) -> Optional[RunResult]:
        return self.table_widget.current_result

    def apply_ui_scale(self, ui_scale: float) -> None:
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._splitter.setHandleWidth(scale_metric(4, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.table_widget.apply_ui_scale(ui_scale)
        if hasattr(self.report_widget, "apply_ui_scale"):
            self.report_widget.apply_ui_scale(ui_scale)

    def clear(self) -> None:
        self.table_widget.clear()
        self.report_widget.clear()

    def display_result(self, result: RunResult) -> None:
        self.table_widget.display_result(result)
        self.report_widget.display_result(result)

    def display_cached_result(self, result: RunResult) -> None:
        self.table_widget.display_result(result, cached=True)
        self.report_widget.display_result(result)


class ResultsPlotWidget(QWidget):
    """Widget for plotting calculation results.

    Uses matplotlib for high-quality publication-ready plots.
    """

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        view_mode: str = "generic",
    ):
        super().__init__(parent)
        if view_mode not in {"generic", "phase_envelope_only"}:
            raise ValueError(f"Unsupported ResultsPlotWidget view_mode: {view_mode}")
        self._current_result: Optional[RunResult] = None
        self._view_mode = view_mode
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._apply_background_color(self, PLOT_SURFACE_COLOR)

        # Import matplotlib with Qt backend
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self.figure = Figure(figsize=(8, 6), dpi=100)
            self._apply_figure_theme()
            self.canvas = FigureCanvasQTAgg(self.figure)
            self._apply_background_color(self.canvas, PLOT_SURFACE_COLOR)
            layout.addWidget(self.canvas)

            self._matplotlib_available = True

        except ImportError:
            # Fallback if matplotlib not available
            self._matplotlib_available = False
            placeholder = QLabel(
                "Matplotlib not available.\n"
                "Install with: pip install matplotlib"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(placeholder)

        # Export button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.export_btn = QPushButton("Export Plot")
        self.export_btn.clicked.connect(self._export_plot)
        btn_layout.addWidget(self.export_btn)
        layout.addLayout(btn_layout)

    @staticmethod
    def _apply_background_color(widget: QWidget, color: str) -> None:
        """Apply a solid Qt background color to a widget palette."""
        widget.setAutoFillBackground(True)
        palette = widget.palette()
        palette.setColor(widget.backgroundRole(), QColor(color))
        widget.setPalette(palette)

    def _apply_figure_theme(self) -> None:
        """Keep the matplotlib figure on the same dark surface as the UI."""
        self.figure.set_facecolor(PLOT_CANVAS_COLOR)

    def _apply_axes_theme(self, ax) -> None:
        """Apply dark-theme styling to a matplotlib axes object."""
        ax.set_facecolor(PLOT_CANVAS_COLOR)
        ax.xaxis.label.set_color(PLOT_TEXT_COLOR)
        ax.yaxis.label.set_color(PLOT_TEXT_COLOR)
        ax.title.set_color(PLOT_TEXT_COLOR)
        ax.tick_params(colors=PLOT_TEXT_COLOR)

        for spine in ax.spines.values():
            spine.set_color(PLOT_GRID_COLOR)

        ax.grid(True, color=PLOT_GRID_COLOR, alpha=0.6)

        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(PLOT_LEGEND_FACE_COLOR)
            legend.get_frame().set_edgecolor(PLOT_GRID_COLOR)
            for text in legend.get_texts():
                text.set_color(PLOT_TEXT_COLOR)
            if legend.get_title() is not None:
                legend.get_title().set_color(PLOT_TEXT_COLOR)

    def _component_display_label(self, component_id: str) -> str:
        """Use the same compact component labels in plots as in the results tables."""
        return _display_component_label(component_id, self._current_result)

    def _tighten_composition_plot_layout(self) -> None:
        """Keep bar-chart composition plots from wasting vertical space below the x-axis."""
        self.figure.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.20)

    def clear(self) -> None:
        """Clear the plot."""
        self._current_result = None
        if self._matplotlib_available:
            self.figure.clear()
            self._apply_figure_theme()
            self.canvas.draw()

    def display_result(self, result: RunResult) -> None:
        """Display a calculation result as a plot.

        Args:
            result: RunResult to plot
        """
        if not self._matplotlib_available:
            return

        self._current_result = result
        self.figure.clear()
        self._apply_figure_theme()

        if self._view_mode == "phase_envelope_only":
            if result.phase_envelope_result:
                self._plot_phase_envelope(result.phase_envelope_result)
            else:
                calc_label = result.config.calculation_type.value.replace("_", " ").title()
                self._plot_placeholder(
                    "Phase envelope view is only populated by phase-envelope runs.\n"
                    f"Latest result type: {calc_label}."
                )
        elif result.pt_flash_result:
            self._plot_pt_flash(result.pt_flash_result)
        elif result.bubble_point_result:
            self._plot_bubble_point(result.bubble_point_result)
        elif result.dew_point_result:
            self._plot_dew_point(result.dew_point_result)
        elif result.phase_envelope_result:
            self._plot_phase_envelope(result.phase_envelope_result)
        elif result.cce_result:
            self._plot_cce(result.cce_result)
        elif result.dl_result:
            self._plot_dl(result.dl_result)
        elif result.cvd_result:
            self._plot_cvd(result.cvd_result)
        elif result.separator_result:
            self._plot_separator(result.separator_result)

        self.canvas.draw()

    def _saturation_pressure_unit(self) -> PressureUnit:
        """Return the preferred saturation pressure unit."""
        config: Optional[SaturationPointConfig] = None
        if self._current_result is not None:
            config = (
                self._current_result.config.bubble_point_config
                or self._current_result.config.dew_point_config
            )
        if config is None:
            return PressureUnit.BAR
        return config.pressure_unit

    def _plot_placeholder(self, message: str) -> None:
        """Render a neutral placeholder instead of a misleading plot."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.grid(False)
        ax.text(
            0.5,
            0.5,
            message,
            color=PLOT_TEXT_COLOR,
            ha="center",
            va="center",
            wrap=True,
            transform=ax.transAxes,
        )
        ax.set_title("Phase Envelope")
        self._apply_axes_theme(ax)
        self.figure.tight_layout()

    def _plot_pt_flash(self, result: PTFlashResult) -> None:
        """Plot PT flash results (composition bar chart)."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        components = sorted(result.liquid_composition.keys())
        display_labels = [self._component_display_label(component) for component in components]
        x = list(range(len(components)))
        width = 0.35

        liquid_vals = [result.liquid_composition.get(c, 0) for c in components]
        vapor_vals = [result.vapor_composition.get(c, 0) for c in components]

        ax.bar([i - width/2 for i in x], liquid_vals, width, label='Liquid', color='blue', alpha=0.7)
        ax.bar([i + width/2 for i in x], vapor_vals, width, label='Vapor', color='red', alpha=0.7)

        ax.set_xlabel('Component')
        ax.set_ylabel('Mole Fraction')
        ax.set_title(f'PT Flash Results ({result.phase.title()})')
        ax.set_xticks(x)
        ax.set_xticklabels(display_labels, rotation=35, ha='right', rotation_mode='anchor')
        ax.legend()
        self._apply_axes_theme(ax)

        self._tighten_composition_plot_layout()

    def _plot_phase_envelope(self, result: PhaseEnvelopeResult) -> None:
        """Plot phase envelope."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        critical_xy: tuple[float, float] | None = None
        if result.critical_point:
            critical_xy = (
                result.critical_point.temperature_k - 273.15,
                result.critical_point.pressure_pa / 1e5,
            )

        def _curve_xy(points) -> tuple[list[float], list[float]]:
            xy = [
                (p.temperature_k - 273.15, p.pressure_pa / 1e5)
                for p in points
            ]
            if critical_xy is not None:
                crit_t, crit_p = critical_xy
                is_duplicate = any(
                    abs(t - crit_t) <= 1e-9 and abs(p - crit_p) <= 1e-9
                    for t, p in xy
                )
                if not is_duplicate:
                    xy.append(critical_xy)
                    xy.sort(key=lambda item: item[0])
            temps = [t for t, _ in xy]
            pressures = [p for _, p in xy]
            return temps, pressures

        # Bubble curve
        if result.bubble_curve:
            temps, pressures = _curve_xy(result.bubble_curve)
            ax.plot(temps, pressures, 'b-', linewidth=2, label='Bubble Point')

        # Dew curve
        if result.dew_curve:
            temps, pressures = _curve_xy(result.dew_curve)
            ax.plot(temps, pressures, 'r-', linewidth=2, label='Dew Point')

        # Critical point
        if critical_xy is not None:
            ax.plot(
                critical_xy[0],
                critical_xy[1],
                'ko', markersize=10, label='Critical Point'
            )

        ax.set_xlabel('Temperature (C)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title('Phase Envelope')
        ax.legend()
        self._apply_axes_theme(ax)

        self.figure.tight_layout()

    def _plot_saturation_result(
        self,
        result: BubblePointResult | DewPointResult,
        *,
        title: str,
    ) -> None:
        """Plot saturation-point liquid/vapor compositions."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        components = sorted(
            set(result.liquid_composition)
            | set(result.vapor_composition)
        )
        display_labels = [self._component_display_label(component) for component in components]
        x = list(range(len(components)))
        width = 0.35

        liquid_vals = [result.liquid_composition.get(c, 0.0) for c in components]
        vapor_vals = [result.vapor_composition.get(c, 0.0) for c in components]

        ax.bar(
            [i - width / 2 for i in x],
            liquid_vals,
            width,
            label="Liquid",
            color="blue",
            alpha=0.7,
        )
        ax.bar(
            [i + width / 2 for i in x],
            vapor_vals,
            width,
            label="Vapor",
            color="red",
            alpha=0.7,
        )

        ax.set_xlabel("Component")
        ax.set_ylabel("Mole Fraction")
        pressure_unit = self._saturation_pressure_unit()
        ax.set_title(f"{title} at {_format_pressure(result.pressure_pa, pressure_unit)}")
        ax.set_xticks(x)
        ax.set_xticklabels(display_labels, rotation=35, ha="right", rotation_mode="anchor")
        ax.legend()
        self._apply_axes_theme(ax)

        self._tighten_composition_plot_layout()

    def _plot_bubble_point(self, result: BubblePointResult) -> None:
        """Plot bubble-point results."""
        self._plot_saturation_result(result, title="Bubble Point")

    def _plot_dew_point(self, result: DewPointResult) -> None:
        """Plot dew-point results."""
        self._plot_saturation_result(result, title="Dew Point")

    def _plot_cce(self, result: CCEResult) -> None:
        """Plot CCE results."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        pressures = [s.pressure_pa / 1e5 for s in result.steps]
        rel_volumes = [s.relative_volume for s in result.steps]

        ax.plot(pressures, rel_volumes, 'b-o', linewidth=2, markersize=4)

        # Mark saturation pressure
        if result.saturation_pressure_pa:
            ax.axvline(
                result.saturation_pressure_pa / 1e5,
                color='r', linestyle='--', linewidth=1.5,
                label=f'Psat = {result.saturation_pressure_pa / 1e5:.2f} bar'
            )
            ax.legend()

        ax.set_xlabel('Pressure (bar)')
        ax.set_ylabel('Relative Volume')
        ax.set_title(f'CCE at {result.temperature_k - 273.15:.1f} C')
        ax.invert_xaxis()  # Pressure decreases during CCE
        self._apply_axes_theme(ax)

        self.figure.tight_layout()

    def _plot_dl(self, result: DLResult) -> None:
        """Plot DL pressure trends."""
        ax_rs = self.figure.add_subplot(211)
        ax_fvf = self.figure.add_subplot(212)
        ax_rs.set_facecolor(PLOT_CANVAS_COLOR)
        ax_fvf.set_facecolor(PLOT_CANVAS_COLOR)

        pressures = [s.pressure_pa / 1e5 for s in result.steps]
        rs = [s.rs for s in result.steps]
        bo = [s.bo for s in result.steps]
        bt = [s.bt for s in result.steps]

        ax_rs.plot(pressures, rs, "g-o", linewidth=2, markersize=4, label="Rs")
        ax_rs.set_xlabel("Pressure (bar)")
        ax_rs.set_ylabel("Rs")
        ax_rs.set_title(f"Differential Liberation at {result.temperature_k - 273.15:.1f} C")
        ax_rs.invert_xaxis()
        ax_rs.legend()
        self._apply_axes_theme(ax_rs)

        ax_fvf.plot(pressures, bo, "y-o", linewidth=2, markersize=4, label="Bo")
        ax_fvf.plot(pressures, bt, "m--o", linewidth=1.5, markersize=3, label="Bt")
        ax_fvf.set_xlabel("Pressure (bar)")
        ax_fvf.set_ylabel("Formation Volume Factor")
        ax_fvf.invert_xaxis()
        ax_fvf.legend()
        self._apply_axes_theme(ax_fvf)

        self.figure.tight_layout()

    def _plot_cvd(self, result: CVDResult) -> None:
        """Plot CVD liquid dropout versus pressure."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        pressures = [s.pressure_pa / 1e5 for s in result.steps]
        liquid_dropout = [s.liquid_dropout for s in result.steps]

        ax.plot(pressures, liquid_dropout, 'c-o', linewidth=2, markersize=4, label='Liquid Dropout')
        ax.set_xlabel('Pressure (bar)')
        ax.set_ylabel('Liquid Dropout')
        ax.set_title(f'CVD at {result.temperature_k - 273.15:.1f} C')
        ax.invert_xaxis()
        ax.legend()
        self._apply_axes_theme(ax)

        self.figure.tight_layout()

    def _plot_separator(self, result: SeparatorResult) -> None:
        """Plot separator stage pressure and vapor fraction."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)
        ax2 = ax.twinx()
        ax2.set_facecolor(PLOT_CANVAS_COLOR)

        labels = [
            stage.stage_name or f"Stage {stage.stage_number}"
            for stage in result.stages
        ]
        x = list(range(len(result.stages)))
        pressures = [stage.pressure_pa / 1e5 for stage in result.stages]

        ax.plot(x, pressures, "b-o", linewidth=2, markersize=4, label="Pressure (bar)")
        ax.set_xlabel("Stage")
        ax.set_ylabel("Pressure (bar)")
        ax.set_title("Separator Train")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=30, ha="right")

        vapor_fraction = [
            0.0 if stage.vapor_fraction is None else stage.vapor_fraction
            for stage in result.stages
        ]
        if any(stage.vapor_fraction is not None for stage in result.stages):
            ax2.bar(x, vapor_fraction, alpha=0.35, color="orange", label="Vapor Fraction")
            ax2.set_ylabel("Vapor Fraction")
        else:
            ax2.set_ylabel("")

        self._apply_axes_theme(ax)
        self._apply_axes_theme(ax2)
        ax2.grid(False)

        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        if handles1 or handles2:
            legend = ax.legend(handles1 + handles2, labels1 + labels2, loc="best")
            legend.get_frame().set_facecolor(PLOT_LEGEND_FACE_COLOR)
            legend.get_frame().set_edgecolor(PLOT_GRID_COLOR)
            for text in legend.get_texts():
                text.set_color(PLOT_TEXT_COLOR)

        self.figure.tight_layout()

    def _export_plot(self) -> None:
        """Export current plot to file."""
        if not self._matplotlib_available or not self._current_result:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Plot",
            "",
            "PNG Files (*.png);;PDF Files (*.pdf);;SVG Files (*.svg)"
        )

        if filename:
            try:
                self.figure.savefig(filename, dpi=300, bbox_inches='tight')
                QMessageBox.information(
                    self, "Export Complete",
                    f"Plot saved to {filename}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed",
                    f"Failed to save plot: {e}"
                )
