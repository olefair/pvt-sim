"""Results display widgets with tables and plots.

Provides tabular and graphical display of calculation results
with export capabilities.
"""

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor
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
    QLineEdit,
    QMenu,
    QToolButton,
    QToolTip,
)

from pvtapp.plus_fraction_policy import describe_plus_fraction_policy
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.text_output_view import format_eos_label
from pvtapp.widgets.combo_box import NoWheelComboBox, NoWheelDoubleSpinBox
from pvtapp.schemas import (
    RunResult,
    RunStatus,
    PTFlashResult,
    PTFlashConfig,
    StabilityAnalysisResult,
    StabilityAnalysisConfig,
    BubblePointResult,
    DewPointResult,
    PhaseEnvelopeResult,
    TBPExperimentResult,
    CCEResult,
    DLResult,
    CVDResult,
    SwellingTestResult,
    SeparatorResult,
    SaturationPointConfig,
    CCEConfig,
    DLConfig,
    SwellingTestConfig,
    PressureUnit,
    TemperatureUnit,
    describe_pt_flash_reported_surface_status,
    describe_reported_component_basis,
    describe_runtime_component_basis,
    pressure_to_pa,
    pressure_from_pa,
    temperature_from_k,
    temperature_to_k,
)


PLOT_SURFACE_COLOR = "#0f1a2b"
PLOT_CANVAS_COLOR = PLOT_SURFACE_COLOR
PLOT_TEXT_COLOR = "#e5e7eb"
PLOT_GRID_COLOR = "#223044"

# Multi-step plot functions (CCE / DL / CVD / swelling) lock their x-axis
# ticks to the calculation's exact step values when there are few enough
# steps to read comfortably. Above this threshold matplotlib's auto-locator
# picks the tick density instead — explicitly pinning 20+ ticks across a
# 2x2 subplot grid produces an unreadable jumble. Tune if you want denser
# or sparser default tick behavior.
_EXPLICIT_XTICKS_MAX = 8
PLOT_LEGEND_FACE_COLOR = "#121f34"
INLINE_PSEUDO_TOKEN = "PSEUDO_PLUS"
INLINE_PSEUDO_FALLBACK_LABEL = "PSEUDO+"


class _TableWheelForwarder(QObject):
    """Pass wheel events from a result table to its enclosing scroll area.

    Without this, a ``QTableWidget`` in the right-rail results panel
    consumes wheel events internally and the user can end up nudging rows
    out of view within an individual section — losing sight of e.g. the
    last DL step. Forwarding the event to the parent lets the outer
    ``sections_scroll`` handle it instead, which is what the user expects.
    """

    _instance: Optional["_TableWheelForwarder"] = None

    @classmethod
    def instance(cls) -> "_TableWheelForwarder":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if event is not None and event.type() == QEvent.Type.Wheel:
            parent = watched.parent() if isinstance(watched, QWidget) else None
            # Walk up until we find a scrollable ancestor (QScrollArea).
            while parent is not None:
                if isinstance(parent, QScrollArea):
                    parent.verticalScrollBar().event(event)
                    return True
                parent = parent.parent()
            return True
        return False


class _ImmediateHeaderTooltipFilter(QObject):
    """Show header-cell tooltips with **zero delay** on hover.

    Qt's default tooltip has a ~700 ms wake-up delay, which makes
    header-cell tooltips effectively invisible — nobody discovers them
    by random hovering. This filter watches mouse-move events on a
    ``QHeaderView`` and calls ``QToolTip.showText()`` immediately when
    the cursor enters a column whose ``horizontalHeaderItem`` has a
    non-empty ``toolTip``. The tooltip then stays visible per Qt's
    default auto-hide timer (~10 s on most platforms) and follows the
    standard "replace on new selection, hide on Leave" behaviour.
    """

    def __init__(self, table: QTableWidget, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._table = table
        self._last_col: Optional[int] = None
        header = table.horizontalHeader()
        header.setMouseTracking(True)
        header.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        header = self._table.horizontalHeader()
        if obj is header:
            etype = event.type()
            if etype == QEvent.Type.MouseMove:
                pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                col = header.logicalIndexAt(pos)
                item = self._table.horizontalHeaderItem(col) if col >= 0 else None
                tip = item.toolTip() if item is not None else ""
                if tip:
                    if col != self._last_col:
                        QToolTip.showText(header.mapToGlobal(pos), tip, header)
                        self._last_col = col
                else:
                    if self._last_col is not None:
                        QToolTip.hideText()
                        self._last_col = None
            elif etype in (QEvent.Type.Leave, QEvent.Type.HoverLeave):
                if self._last_col is not None:
                    QToolTip.hideText()
                    self._last_col = None
        return False


def _display_component_label(
    component_id: str,
    current_result: Optional[RunResult],
) -> str:
    """Map runtime component tokens to compact user-facing labels."""
    normalized = component_id.strip()
    if current_result is not None:
        composition = current_result.config.composition
        if composition is not None:
            plus_fraction = composition.plus_fraction
            if plus_fraction is not None and normalized == plus_fraction.label.strip():
                return plus_fraction.label.strip()
            for spec in composition.inline_components:
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


def _format_optional_measurement(value: Optional[float], *, precision: int, unit: str) -> str:
    """Format an optional scalar measurement with units for summary tables."""
    if value is None or not math.isfinite(value):
        return "-"
    return f"{value:.{precision}f} {unit}"


def _format_calculation_type_label(calculation_type) -> str:
    """Render calculation-type labels for user-facing tables."""
    value = calculation_type.value
    labels = {
        "pt_flash": "PT Flash",
        "stability_analysis": "Stability Analysis",
        "bubble_point": "Bubble Point",
        "dew_point": "Dew Point",
        "phase_envelope": "Phase Envelope",
        "tbp": "TBP",
        "cce": "CCE",
        "differential_liberation": "DL",
        "cvd": "CVD",
        "swelling_test": "Swelling Test",
        "separator": "Separator",
    }
    return labels.get(value, value.replace("_", " ").title())


@dataclass(frozen=True)
class PlotSeriesSpec:
    """Metadata for a selectable result series plotted against pressure."""

    key: str
    label: str
    axis_group: str
    axis_label: str
    overlay_group: str
    values: list[Optional[float]]
    color: str
    default_selected: bool = False
    marker: str = "o"
    linestyle: str = "-"
    linewidth: float = 2.0
    markersize: float = 4.0
    force_overlay: bool = False
    preferred_ylim: Optional[tuple[float, float]] = None


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
        self._saturation_unit_override: Optional[PressureUnit] = None
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

        # Export buttons. Excel is the richest deliverable (multi-sheet
        # workbook with unit-labelled headers, numeric types, formatting)
        # and lives next to the more primitive CSV / JSON exports.
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit("json"))
        self.export_excel_btn = QPushButton("Export Excel")
        self.export_excel_btn.clicked.connect(lambda: self.export_requested.emit("excel"))
        self._header_actions_row.addWidget(self.export_csv_btn)
        self._header_actions_row.addWidget(self.export_json_btn)
        self._header_actions_row.addWidget(self.export_excel_btn)
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

        # Auxiliary table used by _display_cce to present viscosities in a
        # separate, un-cramped section beneath phase densities.
        self.viscosity_table = self._create_section_table()
        self.viscosity_section = self._build_table_section("Phase Viscosities", self.viscosity_table)

        # Zero-delay header tooltips on every result table. Any column
        # whose ``horizontalHeaderItem`` carries a non-empty tooltip
        # (e.g. the Rel. Vol. column on CCE) pops immediately on hover
        # instead of Qt's ~700 ms wake-up. Stored on self to prevent
        # garbage-collection of the installed event filters.
        self._composition_header_tooltip = _ImmediateHeaderTooltipFilter(
            self.composition_table, self
        )
        self._details_header_tooltip = _ImmediateHeaderTooltipFilter(
            self.details_table, self
        )

        # Saturation-point display unit is driven by the bubble/dew pressure
        # unit combo in the left inputs panel. The active result re-renders
        # in the new unit via apply_saturation_display_unit() when that
        # combo changes; no widget lives in the results pane itself.
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
            self.viscosity_section,
            self.captured_section,
        )

        self.sections_scroll = QScrollArea()
        self.sections_scroll.setWidgetResizable(True)
        self.sections_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.sections_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sections_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._sections_host = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_host)
        self._sections_layout.setContentsMargins(0, 0, 0, 0)
        self._sections_layout.setSpacing(10)
        self._sections_layout.addWidget(self.summary_section)
        self._sections_layout.addWidget(self.composition_section)
        self._sections_layout.addWidget(self.details_section)
        self._sections_layout.addWidget(self.viscosity_section)
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
        """Create a compact read-only table for the fixed right rail.

        Each results section is sized in ``_sync_table_height`` to show every
        row without the table itself scrolling. The outer ``sections_scroll``
        area owns all scrolling, so we disable the table's own scroll bars
        completely (including wheel-driven scrolling) — nested scroll
        surfaces make it easy to miss data in the last row.
        """
        table = QTableWidget()
        table.setObjectName("ResultsSectionTable")
        table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        table.verticalScrollBar().setEnabled(False)
        table.horizontalScrollBar().setEnabled(False)
        # Forward wheel events to the surrounding scroll area instead of
        # consuming them inside the table.
        table.viewport().installEventFilter(_TableWheelForwarder.instance())
        table.verticalHeader().setVisible(False)
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
        if table is self.summary_table:
            if column_index == 0:
                return 132, 220
            return 104, 176
        if table is self.composition_table:
            if column_index == 0 and "component" in label:
                return 84, 124
            if any(token in label for token in ("liquid", "vapor")):
                return 96, 140
            if "feed" in label:
                return 76, 112
        if table is self.details_table and table.columnCount() <= 2:
            if column_index == 0 and any(token in label for token in ("component", "property", "stage")):
                return 108, 196
            if any(token in label for token in ("k-value", "value", "temperature", "pressure", "moles", "fugacity")):
                return 116, 232
            if column_index == 0:
                return 96, 180
            return 108, 216
        if column_index == 0:
            if any(token in label for token in ("component", "property", "stage")):
                return 78, 112
            if "type" in label:
                return 64, 88
            return 56, 96
        if "value" in label:
            return 88, 136
        if "fugacity" in label:
            return 84, 108
        if any(token in label for token in ("temperature", "pressure", "moles")):
            return 76, 104
        if any(token in label for token in ("liquid", "vapor", "feed", "k-value", "z-factor")):
            return 72, 98
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
            header_minimum = table.horizontalHeader().fontMetrics().horizontalAdvance(header_label)
            minimum = max(minimum, header_minimum)
            maximum = max(maximum, minimum)
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
        """Fit table columns inside the right rail without hidden horizontal overflow."""
        column_count = table.columnCount()
        if column_count == 0:
            return

        candidate_widths = [
            width
            for width in (
                table.viewport().width(),
                self.sections_scroll.viewport().width() - (2 * table.frameWidth()),
            )
            if width > 0
        ]
        available_width = min(candidate_widths) if candidate_widths else 0
        if available_width <= 0:
            available_width = (
                table.width()
                - table.verticalHeader().width()
                - (2 * table.frameWidth())
            )
        if available_width <= 0:
            return

        widths: list[int] = []
        minimums: list[int] = []
        for column in range(column_count):
            header = table.horizontalHeaderItem(column)
            header_label = header.text() if header is not None else ""
            minimum, maximum = self._column_width_bounds(table, header_label, column)
            minimum = scale_metric(minimum, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
            maximum = scale_metric(maximum, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
            header_minimum = table.horizontalHeader().fontMetrics().horizontalAdvance(header_label)
            minimum = max(minimum, header_minimum)
            maximum = max(maximum, minimum)
            minimums.append(minimum)
            widths.append(max(minimum, min(maximum, table.columnWidth(column))))

        occupied_width = sum(widths)
        if occupied_width > available_width:
            overflow = occupied_width - available_width
            while overflow > 0:
                shrinkable = [max(0, widths[index] - minimums[index]) for index in range(column_count)]
                total_shrinkable = sum(shrinkable)
                if total_shrinkable <= 0:
                    break
                for column in range(column_count):
                    capacity = shrinkable[column]
                    if capacity <= 0 or overflow <= 0:
                        continue
                    shrink = min(
                        capacity,
                        max(1, int(round((overflow * capacity) / total_shrinkable))),
                    )
                    widths[column] -= shrink
                    overflow -= shrink
        else:
            slack = available_width - occupied_width
            if slack > 0:
                even_growth, remainder = divmod(slack, column_count)
                for column in range(column_count):
                    widths[column] += even_growth
                    if column < remainder:
                        widths[column] += 1

        for column, width in enumerate(widths):
            table.setColumnWidth(column, width)

    def _sync_table_height(self, table: QTableWidget) -> None:
        """Lock the table height to exactly fit its rows plus header.

        Because all results scrolling happens at the outer ``sections_scroll``
        layer, we want each table to be tall enough that none of its rows
        get clipped or forced into a nested scroll.

        Timing subtlety: Qt's row-height APIs (``rowHeight``, ``sizeHintForRow``,
        and even the vertical header's ``sectionSize``) don't reflect the
        row's ACTUALLY-RENDERED height until after the paint queue flushes.
        If we call this synchronously right after ``setRowCount`` +
        populating cells — which is exactly what ``_finalize_section_tables``
        does — every row APIs returns a small default (e.g. 20 px from
        ``sizeHintForRow`` or 30 px from ``defaultSectionSize``) even though
        the row will actually render at ~37 px once the stylesheet's
        padding and font-size apply. That used to clip the last row.

        Fix: compute an optimistic height on the first synchronous call
        using a generous per-row floor (``_row_height_estimate`` below),
        then schedule a deferred second pass via ``QTimer.singleShot(0)``
        that re-reads the row heights after Qt has painted the table and
        the sizing APIs have settled. The deferred pass calls
        ``setFixedHeight`` again so the table grows (or shrinks) to the
        real content height.
        """
        if table.columnCount() == 0:
            table.setMinimumHeight(0)
            table.setMaximumHeight(0)
            return
        table.resizeRowsToContents()
        self._apply_table_fixed_height(table)
        # Defer a second pass for the same table so the painted row heights
        # get picked up after Qt flushes layout. This is a no-op if the
        # initial pass already computed the right height.
        QTimer.singleShot(0, lambda t=table: self._apply_table_fixed_height(t))

    def _apply_table_fixed_height(self, table: QTableWidget) -> None:
        """Read current row/header heights and setFixedHeight on the table."""
        if table is None or table.columnCount() == 0:
            return
        header = table.horizontalHeader()
        header_height = max(header.sizeHint().height(), header.height())
        row_floor = self._row_height_estimate(table)
        body_height = 0
        for row in range(table.rowCount()):
            body_height += max(
                row_floor,
                table.verticalHeader().sectionSize(row),
                table.rowHeight(row),
            )
        pad = scale_metric(6, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)
        height = max(
            scale_metric(60, self._ui_scale, reference_scale=DEFAULT_UI_SCALE),
            header_height + body_height + (2 * table.frameWidth()) + pad,
        )
        if table.maximumHeight() != height or table.minimumHeight() != height:
            table.setFixedHeight(height)

    def _row_height_estimate(self, table: QTableWidget) -> int:
        """Conservative floor for a row's rendered height.

        Derived from font metrics + QSS cell padding; Qt's internal
        ``defaultSectionSize`` is too small for our themed rows (20-30 px
        vs the actual ~37 px).
        """
        metrics = table.fontMetrics()
        line = metrics.height()
        # Our QSS gives QTableWidget cells ~5 px vertical padding on each
        # side. A generous floor of line + 18 keeps rows from getting
        # clipped even when a theme bumps line height.
        return max(32, line + 18)

    @staticmethod
    def _section_has_content(table: QTableWidget) -> bool:
        return table.columnCount() > 0 and table.rowCount() > 0

    def _finalize_section_tables(self) -> None:
        """Apply compact widths, fixed heights, and section visibility."""
        self._compact_summary_columns()
        self._compact_data_columns(self.composition_table)
        self._compact_data_columns(self.details_table)
        self._compact_data_columns(self.viscosity_table)
        self._compact_data_columns(self.captured_table)
        for table in (
            self.summary_table,
            self.composition_table,
            self.details_table,
            self.viscosity_table,
            self.captured_table,
        ):
            self._expand_columns_to_fill(table)

        for table in (
            self.summary_table,
            self.composition_table,
            self.details_table,
            self.viscosity_table,
            self.captured_table,
        ):
            self._sync_table_height(table)

        self.summary_section.setVisible(True)
        self.composition_section.setVisible(self._section_has_content(self.composition_table))
        self.details_section.setVisible(self._section_has_content(self.details_table))
        self.viscosity_section.setVisible(self._section_has_content(self.viscosity_table))
        self.captured_section.setVisible(bool(self._captured_rows))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._finalize_section_tables()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._finalize_section_tables()
        # Qt hasn't finalised the panel's width on the first showEvent, so
        # column-expansion and row-height math both work against stale
        # geometry and the tables don't reach the right edge / the last
        # row gets clipped. Defer a second finalize pass for one event-loop
        # tick so it runs after Qt paints with the real sizes.
        QTimer.singleShot(0, self._finalize_section_tables)

    def clear(self, *, clear_captured: bool = False) -> None:
        """Clear all result displays."""
        self._current_result = None
        self._display_is_cached = False
        self.run_id_label.setText("No results")
        self.run_id_label.setToolTip("")
        self.status_label.setText("")
        self.status_label.setToolTip("")
        self.summary_section.setTitle("Summary")
        self.composition_section.setTitle("Compositions")
        self.details_section.setTitle("Details")
        self.viscosity_section.setTitle("Phase Viscosities")
        self.summary_table.setRowCount(0)
        self.composition_table.setRowCount(0)
        self.details_table.setRowCount(0)
        self.viscosity_table.setRowCount(0)
        self.viscosity_table.setColumnCount(0)
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
        self.summary_section.setTitle("Summary")
        self.composition_section.setTitle("Compositions")
        self.details_section.setTitle("Details")
        self.viscosity_section.setTitle("Phase Viscosities")
        # Reset the auxiliary viscosity table so non-CCE result types don't
        # carry over a stale section.
        self.viscosity_table.setRowCount(0)
        self.viscosity_table.setColumnCount(0)

        # Reset per-result view state (e.g. saturation display-unit override).
        self._saturation_unit_override = None

        # Display appropriate result type
        if result.pt_flash_result:
            self._display_pt_flash(result.pt_flash_result)
        elif result.stability_analysis_result:
            self._display_stability_analysis(result.stability_analysis_result)
        elif result.bubble_point_result:
            self._display_bubble_point(result.bubble_point_result)
        elif result.dew_point_result:
            self._display_dew_point(result.dew_point_result)
        elif result.phase_envelope_result:
            self._display_phase_envelope(result.phase_envelope_result)
        elif result.tbp_result:
            self._display_tbp(result.tbp_result)
        elif result.cce_result:
            self._display_cce(result.cce_result)
        elif result.dl_result:
            self._display_dl(result.dl_result)
        elif result.cvd_result:
            self._display_cvd(result.cvd_result)
        elif result.swelling_test_result:
            self._display_swelling(result.swelling_test_result)
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
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def apply_saturation_display_unit(self, unit: PressureUnit) -> None:
        """Re-render the current bubble/dew point result in the given unit.

        Called from the main window when the bubble/dew pressure-unit combo
        in the left inputs panel changes, so the user can flip the display
        unit (bar / psia / atm / ...) without re-running the solver.
        """
        if self._current_result is None:
            return
        if not isinstance(unit, PressureUnit):
            return
        if self._saturation_unit_override == unit:
            return
        result = self._current_result
        if (
            result.bubble_point_result is None
            and result.dew_point_result is None
        ):
            return
        self._saturation_unit_override = unit
        if result.bubble_point_result is not None:
            self._display_bubble_point(result.bubble_point_result)
        elif result.dew_point_result is not None:
            self._display_dew_point(result.dew_point_result)
        self._finalize_section_tables()

    def _saturation_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred saturation display units.

        When the user has picked a display-unit override via the results-pane
        combo, that wins; otherwise we fall back to the unit captured in the
        saturation config at run time (or PSIA / C when nothing is available).
        """
        config: Optional[SaturationPointConfig] = None
        if self._current_result is not None:
            config = (
                self._current_result.config.bubble_point_config
                or self._current_result.config.dew_point_config
            )
        native_pressure_unit = PressureUnit.PSIA if config is None else config.pressure_unit
        native_temperature_unit = TemperatureUnit.C if config is None else config.temperature_unit
        pressure_unit = self._saturation_unit_override or native_pressure_unit
        return pressure_unit, native_temperature_unit

    def _stability_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred standalone stability-analysis display units."""
        config: Optional[StabilityAnalysisConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.stability_analysis_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _cce_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred CCE display units."""
        config: Optional[CCEConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.cce_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _dl_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred DL display units."""
        config: Optional[DLConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.dl_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _swelling_display_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred swelling-test display units."""
        config: Optional[SwellingTestConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.swelling_test_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _plus_fraction_summary_rows(self) -> list[tuple[str, str]]:
        if (
            self._current_result is None
            or self._current_result.config.composition is None
            or self._current_result.config.composition.plus_fraction is None
        ):
            return []
        plus_fraction = self._current_result.config.composition.plus_fraction
        rows = [
            ("C7+ Policy", describe_plus_fraction_policy(plus_fraction)),
            ("C7+ MW+", f"{plus_fraction.mw_plus_g_per_mol:.3f} g/mol"),
            ("C7+ SG+", "-" if plus_fraction.sg_plus_60f is None else f"{plus_fraction.sg_plus_60f:.3f}"),
        ]
        rows.extend(self._runtime_characterization_summary_rows())
        return rows

    def _runtime_characterization_summary_rows(self) -> list[tuple[str, str]]:
        if self._current_result is None or self._current_result.runtime_characterization is None:
            return []

        runtime = self._current_result.runtime_characterization
        basis_label = describe_runtime_component_basis(runtime.runtime_component_basis)
        rows = [
            ("Runtime Basis", basis_label or runtime.runtime_component_basis),
            ("Runtime Split", runtime.split_method.replace("_", " ")),
            ("Runtime Components", str(len(runtime.runtime_component_ids))),
            ("SCNs", str(len(runtime.scn_distribution))),
        ]
        if runtime.lumping_method is not None:
            rows.append(("Runtime Lumping", runtime.lumping_method.title()))
        if runtime.lump_distribution:
            rows.append(("Lumps", str(len(runtime.lump_distribution))))
        if runtime.delumping_basis is not None:
            rows.append(("Delumping", runtime.delumping_basis.replace("_", " ")))
        if runtime.pedersen_fit is not None:
            rows.append(("Pedersen A/B", f"{runtime.pedersen_fit.A:.4f}, {runtime.pedersen_fit.B:.6f}"))
            if runtime.pedersen_fit.tbp_cut_rms_relative_error is not None:
                rows.append(("Cut Fit RMS", f"{runtime.pedersen_fit.tbp_cut_rms_relative_error:.4f}"))
        return rows

    def _tbp_characterization_summary_rows(self, result: TBPExperimentResult) -> list[tuple[str, str]]:
        context = result.characterization_context
        if context is None:
            return []
        status_label = {
            "aggregate_only": "Aggregate only",
            "characterized_scn": "Characterized SCN",
        }.get(context.bridge_status, context.bridge_status.replace("_", " ").title())
        rows = [
            ("Bridge Source", "TBP assay"),
            ("Bridge Status", status_label),
            ("Bridge Label", context.plus_fraction_label),
        ]
        if context.characterization_method is not None:
            rows.append(("Characterization", context.characterization_method.replace("_", " ")))
        if context.runtime_component_basis is not None:
            basis_label = describe_runtime_component_basis(context.runtime_component_basis)
            rows.append(("Runtime Basis", basis_label or context.runtime_component_basis))
        if context.scn_distribution:
            rows.append(("SCNs", str(len(context.scn_distribution))))
        if context.pedersen_fit is not None:
            rows.append(("Pedersen A/B", f"{context.pedersen_fit.A:.4f}, {context.pedersen_fit.B:.6f}"))
            if context.pedersen_fit.tbp_cut_rms_relative_error is not None:
                rows.append(("Cut Fit RMS", f"{context.pedersen_fit.tbp_cut_rms_relative_error:.4f}"))
        rows.append(("Bridge SG+", "-" if context.sg_plus_60f is None else f"{context.sg_plus_60f:.3f}"))
        return rows

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

        reported_surface_label = describe_pt_flash_reported_surface_status(
            result.reported_surface_status
        )
        reported_basis_label = describe_reported_component_basis(result.reported_component_basis)
        if reported_surface_label is not None:
            summary_data.append(("Reported Surface", reported_surface_label))
            if result.reported_surface_reason:
                summary_data.append(("Reported Surface Note", result.reported_surface_reason))
        if reported_basis_label is not None:
            summary_data.extend([
                ("Reported Basis", reported_basis_label),
                (
                    "Rendered Basis",
                    reported_basis_label
                    if result.has_reported_thermodynamic_surface
                    else "Runtime thermodynamic basis",
                ),
            ])
        elif reported_surface_label is not None:
            summary_data.append(("Rendered Basis", "Runtime thermodynamic basis"))

        summary_data.extend([
            ("Vapor Fraction", f"{result.vapor_fraction:.6f}"),
            ("Liquid Fraction", f"{1 - result.vapor_fraction:.6f}"),
            (
                "Liquid Density",
                _format_optional_measurement(
                    result.liquid_density_kg_per_m3,
                    precision=2,
                    unit="kg/m³",
                ),
            ),
            (
                "Vapor Density",
                _format_optional_measurement(
                    result.vapor_density_kg_per_m3,
                    precision=2,
                    unit="kg/m³",
                ),
            ),
            (
                "Liquid Viscosity",
                _format_optional_measurement(
                    result.liquid_viscosity_cp,
                    precision=4,
                    unit="cP",
                ),
            ),
            (
                "Vapor Viscosity",
                _format_optional_measurement(
                    result.vapor_viscosity_cp,
                    precision=4,
                    unit="cP",
                ),
            ),
            (
                "Interfacial Tension",
                _format_optional_measurement(
                    result.interfacial_tension_mn_per_m,
                    precision=4,
                    unit="mN/m",
                ),
            ),
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
        components = sorted(
            set(result.display_liquid_composition)
            | set(result.display_vapor_composition)
            | set(result.display_k_values)
            | set(result.display_liquid_fugacity)
            | set(result.display_vapor_fugacity)
        )
        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels([
            "Component", "Feed (z)", "Liquid (x)", "Vapor (y)"
        ])
        self.composition_table.setRowCount(len(components))

        for row, comp in enumerate(components):
            self.composition_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))

            # Calculate feed from material balance (approximate)
            x = result.display_liquid_composition.get(comp, 0.0)
            y = result.display_vapor_composition.get(comp, 0.0)
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
                row, 1, QTableWidgetItem(f"{result.display_k_values.get(comp, 0.0):.6f}")
            )
            self.details_table.setItem(
                row, 2, QTableWidgetItem(f"{result.display_liquid_fugacity.get(comp, 0.0):.6e}")
            )
            self.details_table.setItem(
                row, 3, QTableWidgetItem(f"{result.display_vapor_fugacity.get(comp, 0.0):.6e}")
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

        if result.continuation_switched is not None:
            summary_data.append(("Switched", "yes" if result.continuation_switched else "no"))

        if result.bubble_termination_reason:
            bubble_stop = result.bubble_termination_reason
            if result.bubble_termination_temperature_k is not None:
                bubble_stop = f"{bubble_stop} @ {result.bubble_termination_temperature_k - 273.15:.2f} C"
            summary_data.append(("Bubble Stop", bubble_stop))

        if result.dew_termination_reason:
            dew_stop = result.dew_termination_reason
            if result.dew_termination_temperature_k is not None:
                dew_stop = f"{dew_stop} @ {result.dew_termination_temperature_k - 273.15:.2f} C"
            summary_data.append(("Dew Stop", dew_stop))

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

        # Envelope points in composition table. Header + values use the
        # repo-wide default US-petroleum units (psia, °F) to match every
        # other calc-type display. PhaseEnvelopeConfig does not yet carry
        # its own unit-preference fields; if a follow-up adds them, wire
        # ``pressure_unit`` / ``temperature_unit`` through the same way
        # ``_cce_display_units`` does.
        envelope_pressure_unit = PressureUnit.PSIA
        envelope_temperature_unit = TemperatureUnit.F
        all_points = result.continuous_curve_points()

        self.composition_table.setColumnCount(3)
        self.composition_table.setHorizontalHeaderLabels([
            "Type",
            f"Temperature (\u00b0{envelope_temperature_unit.value})",
            f"Pressure ({envelope_pressure_unit.value})",
        ])
        self.composition_table.setRowCount(len(all_points))

        for row, point in enumerate(all_points):
            self.composition_table.setItem(row, 0, QTableWidgetItem(str(point.point_type).title()))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(
                    f"{temperature_from_k(point.temperature_k, envelope_temperature_unit):.2f}"
                )
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(
                    f"{pressure_from_pa(point.pressure_pa, envelope_pressure_unit):.2f}"
                )
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_tbp(self, result: TBPExperimentResult) -> None:
        """Display bounded standalone TBP assay results."""
        self.composition_section.setTitle("Cuts")
        self.details_section.setTitle("Curves")

        summary_data = [
            ("Cut Start", str(result.cut_start)),
            ("Cut End", str(result.cut_end)),
            ("Cuts", str(len(result.cuts))),
            ("z+", f"{result.z_plus:.6f}"),
            ("MW+", f"{result.mw_plus_g_per_mol:.3f} g/mol"),
            (
                "Tb Curve",
                "Available" if any(cut.boiling_point_k is not None for cut in result.cuts) else "Not available",
            ),
        ]
        summary_data.extend(self._tbp_characterization_summary_rows(result))
        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        self.composition_table.setColumnCount(7)
        self.composition_table.setHorizontalHeaderLabels(
            ["Cut", "Carbon Range", "z", "Norm. z", "MW (g/mol)", "SG", "Tb (K)"]
        )
        self.composition_table.setRowCount(len(result.cuts))
        for row, cut in enumerate(result.cuts):
            carbon_range = (
                str(cut.carbon_number)
                if cut.carbon_number_end == cut.carbon_number
                else f"{cut.carbon_number}-{cut.carbon_number_end}"
            )
            self.composition_table.setItem(row, 0, QTableWidgetItem(cut.name))
            self.composition_table.setItem(row, 1, QTableWidgetItem(carbon_range))
            self.composition_table.setItem(row, 2, QTableWidgetItem(f"{cut.mole_fraction:.6f}"))
            self.composition_table.setItem(row, 3, QTableWidgetItem(f"{cut.normalized_mole_fraction:.6f}"))
            self.composition_table.setItem(row, 4, QTableWidgetItem(f"{cut.molecular_weight_g_per_mol:.3f}"))
            self.composition_table.setItem(
                row,
                5,
                QTableWidgetItem("-" if cut.specific_gravity is None else f"{cut.specific_gravity:.4f}"),
            )
            self.composition_table.setItem(
                row,
                6,
                QTableWidgetItem("-" if cut.boiling_point_k is None else f"{cut.boiling_point_k:.2f}"),
            )

        self.details_table.setColumnCount(5)
        self.details_table.setHorizontalHeaderLabels(
            ["Cut", "Cum. Mole %", "Mass Frac.", "Cum. Mass %", "Cum. Mole Frac."]
        )
        self.details_table.setRowCount(len(result.cuts))
        for row, cut in enumerate(result.cuts):
            self.details_table.setItem(row, 0, QTableWidgetItem(cut.name))
            self.details_table.setItem(row, 1, QTableWidgetItem(f"{cut.cumulative_mole_fraction * 100.0:.2f}"))
            self.details_table.setItem(row, 2, QTableWidgetItem(f"{cut.normalized_mass_fraction:.6f}"))
            self.details_table.setItem(row, 3, QTableWidgetItem(f"{cut.cumulative_mass_fraction * 100.0:.2f}"))
            self.details_table.setItem(row, 4, QTableWidgetItem(f"{cut.cumulative_mole_fraction:.6f}"))

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
            ("EOS", format_eos_label(self._current_result.config.eos_type)),
            (stability_label, "Yes" if stability_value else "No"),
        ]
        reported_basis_label = describe_reported_component_basis(result.reported_component_basis)
        if reported_basis_label is not None:
            summary_data.extend([
                ("Reported Basis", reported_basis_label),
                (
                    "Rendered Basis",
                    reported_basis_label
                    if result.has_reported_surface
                    else "Runtime thermodynamic basis",
                ),
            ])
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
            set(result.display_liquid_composition)
            | set(result.display_vapor_composition)
            | set(result.display_k_values)
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
                row, 1, QTableWidgetItem(f"{result.display_liquid_composition.get(comp, 0.0):.6f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{result.display_vapor_composition.get(comp, 0.0):.6f}")
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(comp)))
            self.details_table.setItem(
                row, 1, QTableWidgetItem(f"{result.display_k_values.get(comp, 0.0):.6f}")
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_stability_analysis(self, result: StabilityAnalysisResult) -> None:
        """Display standalone Michelsen / TPD stability-analysis results."""
        self.composition_section.setTitle("Trial Compositions")
        self.details_section.setTitle("Trial Diagnostics")

        pressure_unit, temperature_unit = self._stability_display_units()
        summary_data = [
            ("Pressure", _format_pressure(result.pressure_pa, pressure_unit)),
            ("Temperature", _format_temperature(result.temperature_k, temperature_unit)),
            ("EOS", format_eos_label(self._current_result.config.eos_type)),
            ("Stable", "Yes" if result.stable else "No"),
            ("Minimum TPD", f"{result.tpd_min:.6e}"),
            ("Phase Regime", result.phase_regime.replace("_", " ").title()),
            ("Physical State Hint", result.physical_state_hint.replace("_", " ").title()),
            ("Requested Feed Phase", result.requested_feed_phase.value.replace("_", " ").title()),
            ("Resolved Feed Phase", result.resolved_feed_phase.replace("_", " ").title()),
            ("Reference Root Used", result.reference_root_used.replace("_", " ").title()),
            (
                "Best Unstable Trial",
                "-" if result.best_unstable_trial_kind is None else result.best_unstable_trial_kind.replace("_", " ").title(),
            ),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        vapor_comp = {} if result.vapor_like_trial is None else result.vapor_like_trial.composition
        liquid_comp = {} if result.liquid_like_trial is None else result.liquid_like_trial.composition
        components = sorted(set(result.feed_composition) | set(vapor_comp) | set(liquid_comp))

        self.composition_table.setColumnCount(4)
        self.composition_table.setHorizontalHeaderLabels(
            ["Component", "Feed (z)", "Vapor-like", "Liquid-like"]
        )
        self.composition_table.setRowCount(len(components))
        for row, component in enumerate(components):
            self.composition_table.setItem(row, 0, QTableWidgetItem(self._component_display_label(component)))
            self.composition_table.setItem(row, 1, QTableWidgetItem(f"{result.feed_composition.get(component, 0.0):.6f}"))
            self.composition_table.setItem(
                row,
                2,
                QTableWidgetItem("-" if component not in vapor_comp else f"{vapor_comp.get(component, 0.0):.6f}"),
            )
            self.composition_table.setItem(
                row,
                3,
                QTableWidgetItem("-" if component not in liquid_comp else f"{liquid_comp.get(component, 0.0):.6f}"),
            )

        detail_rows: list[tuple[str, str]] = [
            ("Interpretation Basis", result.physical_state_hint_basis.replace("_", " ").title()),
            ("Hint Confidence", result.physical_state_hint_confidence.title()),
        ]
        if result.liquid_root_z is not None:
            detail_rows.append(("Liquid Root Z", f"{result.liquid_root_z:.6f}"))
        if result.vapor_root_z is not None:
            detail_rows.append(("Vapor Root Z", f"{result.vapor_root_z:.6f}"))
        if result.root_gap is not None:
            detail_rows.append(("Root Gap", f"{result.root_gap:.6e}"))
        if result.gibbs_gap is not None:
            detail_rows.append(("Gibbs Gap", f"{result.gibbs_gap:.6e}"))
        if result.average_reduced_pressure is not None:
            detail_rows.append(("Average Reduced Pressure", f"{result.average_reduced_pressure:.6f}"))
        if result.bubble_pressure_hint_pa is not None:
            detail_rows.append(
                ("Bubble Pressure Hint", _format_pressure(result.bubble_pressure_hint_pa, pressure_unit))
            )
        if result.dew_pressure_hint_pa is not None:
            detail_rows.append(
                ("Dew Pressure Hint", _format_pressure(result.dew_pressure_hint_pa, pressure_unit))
            )
        if result.bubble_boundary_reason:
            detail_rows.append(("Bubble Boundary Reason", result.bubble_boundary_reason.replace("_", " ").title()))
        if result.dew_boundary_reason:
            detail_rows.append(("Dew Boundary Reason", result.dew_boundary_reason.replace("_", " ").title()))
        for trial_label, trial in (
            ("Vapor-like Trial", result.vapor_like_trial),
            ("Liquid-like Trial", result.liquid_like_trial),
        ):
            if trial is None:
                continue
            detail_rows.extend(
                [
                    (f"{trial_label} TPD", f"{trial.tpd:.6e}"),
                    (f"{trial_label} Converged", "Yes" if trial.converged else "No"),
                    (f"{trial_label} Early Exit", "Yes" if trial.early_exit_unstable else "No"),
                    (f"{trial_label} Iterations", str(trial.iterations)),
                    (f"{trial_label} Total Iterations", str(trial.total_iterations)),
                    (f"{trial_label} Phi Calls", str(trial.n_phi_calls)),
                    (f"{trial_label} EOS Failures", str(trial.n_eos_failures)),
                    (f"{trial_label} Best Seed", trial.best_seed.seed_label),
                    (
                        f"{trial_label} Seed Attempts",
                        f"{trial.seed_attempts}/{trial.candidate_seed_count}",
                    ),
                ]
            )
            if trial.message:
                detail_rows.append((f"{trial_label} Message", trial.message))
            if trial.diagnostic_messages:
                detail_rows.append(
                    (
                        f"{trial_label} Diagnostics",
                        "; ".join(message for message in trial.diagnostic_messages if message),
                    )
                )

        self.details_table.setColumnCount(2)
        self.details_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.details_table.setRowCount(len(detail_rows))
        for row, (prop, value) in enumerate(detail_rows):
            self.details_table.setItem(row, 0, QTableWidgetItem(prop))
            self.details_table.setItem(row, 1, QTableWidgetItem(value))

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
        self.composition_section.setTitle("Expansion")
        self.details_section.setTitle("Phase Densities")
        self.viscosity_section.setTitle("Phase Viscosities")
        pressure_unit, temperature_unit = self._cce_display_units()

        # Summary
        summary_data = [
            ("Temperature", _format_temperature(result.temperature_k, temperature_unit)),
            ("Steps", str(len(result.steps))),
        ]

        if result.saturation_pressure_pa:
            summary_data.append((
                "Saturation Pressure",
                _format_pressure(result.saturation_pressure_pa, pressure_unit)
            ))
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # Expansion table (kept compact so all 5 columns fit the right rail).
        # The "Rel. Vol." header stays short to avoid squeezing the other
        # four columns; the full "Relative Volume (V/Vsat)" name is exposed
        # on header hover instead.
        self.composition_table.setColumnCount(5)
        self.composition_table.setHorizontalHeaderLabels([
            f"P ({pressure_unit.value})",
            "Rel. Vol.",
            "Liquid Frac.",
            "Vapor Frac.",
            "Z-factor",
        ])
        rel_vol_header = self.composition_table.horizontalHeaderItem(1)
        if rel_vol_header is not None:
            # Tooltip shown with **zero delay** via
            # _ImmediateHeaderTooltipFilter installed on composition_table
            # in __init__. Text is deliberately tight (symbolic, no prose):
            # petroleum readers recognize V(P)/V(Psat) instantly, and if
            # the user catches only the first second of hover they still
            # get the definition.
            rel_vol_header.setToolTip("V(P) / V(Psat)")
        self.composition_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row,
                0,
                QTableWidgetItem(f"{pressure_from_pa(step.pressure_pa, pressure_unit):.2f}"),
            )
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{step.relative_volume:.4f}")
            )
            lf = step.liquid_fraction if step.liquid_fraction else ""
            self.composition_table.setItem(row, 2, QTableWidgetItem(
                f"{lf:.4f}" if lf else "-"
            ))
            vf = step.vapor_fraction if step.vapor_fraction else ""
            self.composition_table.setItem(row, 3, QTableWidgetItem(
                f"{vf:.4f}" if vf else "-"
            ))
            zf = step.z_factor if step.z_factor else ""
            self.composition_table.setItem(row, 4, QTableWidgetItem(
                f"{zf:.4f}" if zf else "-"
            ))

        # Phase Densities - smaller so column titles aren't clipped.
        self.details_table.setColumnCount(3)
        self.details_table.setHorizontalHeaderLabels([
            f"P ({pressure_unit.value})",
            "Liquid Density",
            "Vapor Density",
        ])
        self.details_table.setRowCount(len(result.steps))
        for row, step in enumerate(result.steps):
            self.details_table.setItem(
                row,
                0,
                QTableWidgetItem(f"{pressure_from_pa(step.pressure_pa, pressure_unit):.2f}"),
            )
            liquid_density = step.liquid_density_kg_per_m3
            vapor_density = step.vapor_density_kg_per_m3
            self.details_table.setItem(
                row, 1, QTableWidgetItem(
                    "-" if liquid_density is None or liquid_density <= 0 else f"{liquid_density:.2f}"
                )
            )
            self.details_table.setItem(
                row, 2, QTableWidgetItem(
                    "-" if vapor_density is None or vapor_density <= 0 else f"{vapor_density:.2f}"
                )
            )

        # Phase Viscosities - companion table beneath Phase Densities so
        # nothing gets cramped.
        self.viscosity_table.setColumnCount(3)
        self.viscosity_table.setHorizontalHeaderLabels([
            f"P ({pressure_unit.value})",
            "Liquid Viscosity",
            "Vapor Viscosity",
        ])
        self.viscosity_table.setRowCount(len(result.steps))
        for row, step in enumerate(result.steps):
            self.viscosity_table.setItem(
                row,
                0,
                QTableWidgetItem(f"{pressure_from_pa(step.pressure_pa, pressure_unit):.2f}"),
            )
            liquid_viscosity = step.liquid_viscosity_cp
            vapor_viscosity = step.vapor_viscosity_cp
            self.viscosity_table.setItem(
                row, 1, QTableWidgetItem(
                    "-" if liquid_viscosity is None or liquid_viscosity <= 0 else f"{liquid_viscosity:.4f}"
                )
            )
            self.viscosity_table.setItem(
                row, 2, QTableWidgetItem(
                    "-" if vapor_viscosity is None or vapor_viscosity <= 0 else f"{vapor_viscosity:.4f}"
                )
            )

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.viscosity_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_dl(self, result: DLResult) -> None:
        """Display DL results."""
        pressure_unit, temperature_unit = self._dl_display_units()
        summary_data = [
            ("Temperature", _format_temperature(result.temperature_k, temperature_unit)),
            ("Bubble Pressure", _format_pressure(result.bubble_pressure_pa, pressure_unit)),
            ("Initial Rs", f"{result.rsi:.4f}"),
            ("Initial Bo", f"{result.boi:.4f}"),
            (
                "Residual Oil Density",
                _format_optional_measurement(
                    result.residual_oil_density_kg_per_m3,
                    precision=2,
                    unit="kg/m³",
                ),
            ),
            ("Converged", "Yes" if result.converged else "No"),
            ("Steps", str(len(result.steps))),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # DL Compositions header compacted to match CCE's "P ({unit})"
        # short-form — "Pressure" was getting truncated to "ressure" in
        # the right-rail width, losing the leading P.
        self.composition_table.setColumnCount(7)
        self.composition_table.setHorizontalHeaderLabels(
            [f"P ({pressure_unit.value})", "RsD", "RsDb", "Bo", "Bg", "BtD", "Cum. Gas"]
        )
        self.composition_table.setRowCount(len(result.steps))

        # DL Details header uses standard petroleum-engineering symbols
        # (Greek letter + single-capital phase suffix, same plain-letter
        # style the CCE text output adopted for ρL / ρV / μL / μV). That
        # gives every column a 2–4 character header so all eight columns
        # fit the rail without truncation. Mapping:
        #   Oil Density       →  ρO   (rho  + O)
        #   Oil Viscosity     →  μO   (mu   + O)
        #   Gas Gravity       →  γg   (gamma + g)   — specific gravity
        #   Gas Z-factor      →  Zg
        #   Gas Viscosity     →  μG   (mu   + G)
        #   Liquid Moles Rem. →  n_L  — keep explicit; no standard symbol
        self.details_table.setColumnCount(8)
        self.details_table.setHorizontalHeaderLabels(
            [
                "Step",
                "\u03b2",                # β (vapor fraction)
                "\u03c1O",               # ρO
                "\u03bcO",               # μO
                "\u03b3g",               # γg
                "Zg",
                "\u03bcG",               # μG
                "n_L",
            ]
        )
        self.details_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row,
                0,
                QTableWidgetItem(f"{pressure_from_pa(step.pressure_pa, pressure_unit):.2f}"),
            )
            self.composition_table.setItem(row, 1, QTableWidgetItem(f"{step.rs:.4f}"))
            self.composition_table.setItem(row, 2, QTableWidgetItem(f"{result.rsi:.4f}"))
            self.composition_table.setItem(row, 3, QTableWidgetItem(f"{step.bo:.4f}"))
            self.composition_table.setItem(
                row,
                4,
                QTableWidgetItem("-" if step.bg is None else f"{step.bg:.4f}"),
            )
            self.composition_table.setItem(row, 5, QTableWidgetItem(f"{step.bt:.4f}"))
            self.composition_table.setItem(
                row,
                6,
                QTableWidgetItem(
                    "-" if step.cumulative_gas_produced is None else f"{step.cumulative_gas_produced:.4f}"
                ),
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            self.details_table.setItem(row, 1, QTableWidgetItem(f"{step.vapor_fraction:.4f}"))
            oil_density = (
                "-"
                if step.oil_density_kg_per_m3 is None or step.oil_density_kg_per_m3 <= 0
                else f"{step.oil_density_kg_per_m3:.2f}"
            )
            gas_gravity = "-" if step.gas_gravity is None else f"{step.gas_gravity:.4f}"
            gas_z = "-" if step.gas_z_factor is None else f"{step.gas_z_factor:.4f}"
            oil_viscosity = (
                "-"
                if step.oil_viscosity_cp is None or step.oil_viscosity_cp <= 0
                else f"{step.oil_viscosity_cp:.4f}"
            )
            gas_viscosity = (
                "-"
                if step.gas_viscosity_cp is None or step.gas_viscosity_cp <= 0
                else f"{step.gas_viscosity_cp:.4f}"
            )
            self.details_table.setItem(row, 2, QTableWidgetItem(oil_density))
            self.details_table.setItem(row, 3, QTableWidgetItem(oil_viscosity))
            self.details_table.setItem(row, 4, QTableWidgetItem(gas_gravity))
            self.details_table.setItem(row, 5, QTableWidgetItem(gas_z))
            self.details_table.setItem(row, 6, QTableWidgetItem(gas_viscosity))
            liquid_moles = (
                "-"
                if step.liquid_moles_remaining is None
                else f"{step.liquid_moles_remaining:.6f}"
            )
            self.details_table.setItem(row, 7, QTableWidgetItem(liquid_moles))

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

        # Header + values use the repo-wide default US-petroleum units
        # (psia). CVDConfig does not carry its own unit-preference field;
        # if a follow-up adds one, wire ``cvd_pressure_unit`` through the
        # same way ``_cce_display_units`` does.
        cvd_pressure_unit = PressureUnit.PSIA
        self.composition_table.setColumnCount(6)
        # Compact "P ({unit})" form to match CCE / DL — "Pressure (psia)"
        # gets truncated in the right-rail width.
        self.composition_table.setHorizontalHeaderLabels([
            f"P ({cvd_pressure_unit.value})",
            "Liquid Dropout",
            "Gas Produced",
            "Cum. Gas",
            "Moles Remaining",
            "Z (2-phase)",
        ])
        self.composition_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            self.composition_table.setItem(
                row, 0, QTableWidgetItem(
                    f"{pressure_from_pa(step.pressure_pa, cvd_pressure_unit):.2f}"
                )
            )
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{step.liquid_dropout:.4f}")
            )
            self.composition_table.setItem(
                row,
                2,
                QTableWidgetItem("-" if step.gas_produced is None else f"{step.gas_produced:.4f}"),
            )
            self.composition_table.setItem(
                row, 3, QTableWidgetItem(f"{step.cumulative_gas_produced:.4f}")
            )
            moles_remaining = "-" if step.moles_remaining is None else f"{step.moles_remaining:.6f}"
            self.composition_table.setItem(row, 4, QTableWidgetItem(moles_remaining))
            z_two_phase = "-" if step.z_two_phase is None else f"{step.z_two_phase:.4f}"
            self.composition_table.setItem(row, 5, QTableWidgetItem(z_two_phase))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.details_table.setColumnCount(5)
        self.details_table.setHorizontalHeaderLabels(
            ["Step", "Liquid Density", "Vapor Density", "Liquid Viscosity", "Vapor Viscosity"]
        )
        self.details_table.setRowCount(len(result.steps))
        for row, step in enumerate(result.steps):
            self.details_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
            liquid_density = (
                "-"
                if step.liquid_density_kg_per_m3 is None or step.liquid_density_kg_per_m3 <= 0
                else f"{step.liquid_density_kg_per_m3:.2f}"
            )
            vapor_density = (
                "-"
                if step.vapor_density_kg_per_m3 is None or step.vapor_density_kg_per_m3 <= 0
                else f"{step.vapor_density_kg_per_m3:.2f}"
            )
            self.details_table.setItem(row, 1, QTableWidgetItem(liquid_density))
            self.details_table.setItem(row, 2, QTableWidgetItem(vapor_density))
            liquid_viscosity = (
                "-"
                if step.liquid_viscosity_cp is None or step.liquid_viscosity_cp <= 0
                else f"{step.liquid_viscosity_cp:.4f}"
            )
            vapor_viscosity = (
                "-"
                if step.vapor_viscosity_cp is None or step.vapor_viscosity_cp <= 0
                else f"{step.vapor_viscosity_cp:.4f}"
            )
            self.details_table.setItem(row, 3, QTableWidgetItem(liquid_viscosity))
            self.details_table.setItem(row, 4, QTableWidgetItem(vapor_viscosity))

        self.details_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def _display_swelling(self, result: SwellingTestResult) -> None:
        """Display swelling-test results."""
        self.composition_section.setTitle("Step Summary")
        self.details_section.setTitle("Step Diagnostics")

        pressure_unit, temperature_unit = self._swelling_display_units()
        certified_steps = sum(step.status == "certified" for step in result.steps)
        summary_data = [
            ("Temperature", _format_temperature(result.temperature_k, temperature_unit)),
            (
                "Baseline Bubble Pressure",
                "-"
                if result.baseline_bubble_pressure_pa is None
                else _format_pressure(result.baseline_bubble_pressure_pa, pressure_unit),
            ),
            (
                "Baseline Sat. Liquid Vm",
                "-"
                if result.baseline_saturated_liquid_molar_volume_m3_per_mol is None
                else f"{result.baseline_saturated_liquid_molar_volume_m3_per_mol:.6e} m³/mol",
            ),
            ("Steps", str(len(result.steps))),
            ("Certified Steps", f"{certified_steps} / {len(result.steps)}"),
            ("Overall Status", result.overall_status.replace("_", " ").title()),
            ("Fully Certified", "Yes" if result.fully_certified else "No"),
        ]

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        self.composition_table.setColumnCount(6)
        self.composition_table.setHorizontalHeaderLabels(
            [
                "Step",
                "Added Gas (mol/mol oil)",
                f"Bubble Pressure ({pressure_unit.value})",
                "Swelling Factor",
                "Sat. Liquid Density (kg/m³)",
                "Status",
            ]
        )
        self.composition_table.setRowCount(len(result.steps))

        self.details_table.setColumnCount(4)
        self.details_table.setHorizontalHeaderLabels(
            [
                "Step",
                "Total Moles (mol/mol oil)",
                "Sat. Liquid Vm (m³/mol)",
                "Message",
            ]
        )
        self.details_table.setRowCount(len(result.steps))

        for row, step in enumerate(result.steps):
            bubble_pressure = (
                "-"
                if step.bubble_pressure_pa is None
                else f"{pressure_from_pa(step.bubble_pressure_pa, pressure_unit):.4f}"
            )
            swelling_factor = (
                "-"
                if step.swelling_factor is None
                else f"{step.swelling_factor:.6f}"
            )
            liquid_density = (
                "-"
                if step.saturated_liquid_density_kg_per_m3 is None
                else f"{step.saturated_liquid_density_kg_per_m3:.2f}"
            )
            molar_volume = (
                "-"
                if step.saturated_liquid_molar_volume_m3_per_mol is None
                else f"{step.saturated_liquid_molar_volume_m3_per_mol:.6e}"
            )

            self.composition_table.setItem(row, 0, QTableWidgetItem(str(step.step_index)))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{step.added_gas_moles_per_mole_oil:.6f}")
            )
            self.composition_table.setItem(row, 2, QTableWidgetItem(bubble_pressure))
            self.composition_table.setItem(row, 3, QTableWidgetItem(swelling_factor))
            self.composition_table.setItem(row, 4, QTableWidgetItem(liquid_density))
            self.composition_table.setItem(
                row,
                5,
                QTableWidgetItem(step.status.replace("_", " ").title()),
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(str(step.step_index)))
            self.details_table.setItem(
                row,
                1,
                QTableWidgetItem(f"{step.total_mixture_moles_per_mole_oil:.6f}"),
            )
            self.details_table.setItem(row, 2, QTableWidgetItem(molar_volume))
            self.details_table.setItem(row, 3, QTableWidgetItem(step.message or ""))

        self.composition_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
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
            (
                "Stock-tank MW",
                "-" if result.stock_tank_oil_mw_g_per_mol is None else f"{result.stock_tank_oil_mw_g_per_mol:.3f} g/mol",
            ),
            (
                "Stock-tank SG",
                "-" if result.stock_tank_oil_specific_gravity is None else f"{result.stock_tank_oil_specific_gravity:.4f}",
            ),
            (
                "Total Gas Moles",
                "-" if result.total_gas_moles is None else f"{result.total_gas_moles:.6f}",
            ),
            (
                "Shrinkage",
                "-" if result.shrinkage is None else f"{result.shrinkage:.4f}",
            ),
            ("Stages", str(len(result.stages))),
        ]
        summary_data.extend(self._plus_fraction_summary_rows())

        self.summary_table.setRowCount(len(summary_data))
        for row, (prop, value) in enumerate(summary_data):
            self.summary_table.setItem(row, 0, QTableWidgetItem(prop))
            self.summary_table.setItem(row, 1, QTableWidgetItem(value))

        # Header + values use the repo-wide default US-petroleum units
        # (psia, °F). SeparatorConfig does not yet carry its own
        # unit-preference fields; a follow-up can thread them through
        # identically to ``_cce_display_units``.
        sep_pressure_unit = PressureUnit.PSIA
        sep_temperature_unit = TemperatureUnit.F
        self.composition_table.setColumnCount(6)
        self.composition_table.setHorizontalHeaderLabels([
            "Stage",
            f"Pressure ({sep_pressure_unit.value})",
            f"Temperature (\u00b0{sep_temperature_unit.value})",
            "Vapor Frac.",
            "Liquid Moles",
            "Vapor Moles",
        ])
        self.composition_table.setRowCount(len(result.stages))

        self.details_table.setColumnCount(6)
        self.details_table.setHorizontalHeaderLabels(
            [
                "Stage",
                "Liquid Density",
                "Vapor Density",
                "ZL",
                "ZV",
                "Converged",
            ]
        )
        self.details_table.setRowCount(len(result.stages))

        for row, stage in enumerate(result.stages):
            stage_label = stage.stage_name or f"Stage {stage.stage_number}"
            self.composition_table.setItem(row, 0, QTableWidgetItem(stage_label))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(
                    f"{pressure_from_pa(stage.pressure_pa, sep_pressure_unit):.2f}"
                )
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(
                    f"{temperature_from_k(stage.temperature_k, sep_temperature_unit):.2f}"
                )
            )
            vapor_fraction = "-" if stage.vapor_fraction is None else f"{stage.vapor_fraction:.4f}"
            self.composition_table.setItem(row, 3, QTableWidgetItem(vapor_fraction))
            liquid_moles = "-" if stage.liquid_moles is None else f"{stage.liquid_moles:.6f}"
            vapor_moles = "-" if stage.vapor_moles is None else f"{stage.vapor_moles:.6f}"
            self.composition_table.setItem(row, 4, QTableWidgetItem(liquid_moles))
            self.composition_table.setItem(row, 5, QTableWidgetItem(vapor_moles))

            self.details_table.setItem(row, 0, QTableWidgetItem(stage_label))
            liquid_density = (
                "-"
                if stage.liquid_density_kg_per_m3 is None or stage.liquid_density_kg_per_m3 <= 0
                else f"{stage.liquid_density_kg_per_m3:.2f}"
            )
            vapor_density = (
                "-"
                if stage.vapor_density_kg_per_m3 is None or stage.vapor_density_kg_per_m3 <= 0
                else f"{stage.vapor_density_kg_per_m3:.2f}"
            )
            liquid_z = "-" if stage.liquid_z_factor is None else f"{stage.liquid_z_factor:.4f}"
            vapor_z = "-" if stage.vapor_z_factor is None else f"{stage.vapor_z_factor:.4f}"
            self.details_table.setItem(row, 1, QTableWidgetItem(liquid_density))
            self.details_table.setItem(row, 2, QTableWidgetItem(vapor_density))
            self.details_table.setItem(row, 3, QTableWidgetItem(liquid_z))
            self.details_table.setItem(row, 4, QTableWidgetItem(vapor_z))
            self.details_table.setItem(
                row, 5, QTableWidgetItem("Yes" if stage.converged else "No")
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
    """Fixed right-rail surface: compact results tables only."""

    def __init__(
        self,
        table_widget: Optional[ResultsTableWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.table_widget = table_widget or ResultsTableWidget()

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)
        self._layout.addWidget(self.table_widget, 1)

    @property
    def current_result(self) -> Optional[RunResult]:
        return self.table_widget.current_result

    def apply_ui_scale(self, ui_scale: float) -> None:
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.table_widget.apply_ui_scale(ui_scale)

    def clear(self) -> None:
        self.table_widget.clear()

    def display_result(self, result: RunResult) -> None:
        self.table_widget.display_result(result)

    def display_cached_result(self, result: RunResult) -> None:
        self.table_widget.display_result(result, cached=True)


class UnitConverterWidget(QWidget):
    """Compact toolbar converter for quick pressure and temperature checks."""

    _PRESSURE_LABEL = "Pressure"
    _TEMPERATURE_LABEL = "Temperature"

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ToolbarUnitConverter")
        self._ui_scale = DEFAULT_UI_SCALE
        self._setting_units = False
        self._setup_ui()
        self._on_quantity_changed()

    def _setup_ui(self) -> None:
        self._layout = QHBoxLayout(self)
        inset_x = scale_metric(6, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE)
        inset_y = scale_metric(3, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE)
        self._layout.setContentsMargins(inset_x, inset_y, inset_x, inset_y)
        self._layout.setSpacing(scale_metric(8, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE))

        self.heading_label = QLabel("Convert")
        self._layout.addWidget(self.heading_label)

        self.quantity_combo = NoWheelComboBox()
        self.quantity_combo.addItem(self._PRESSURE_LABEL, self._PRESSURE_LABEL)
        self.quantity_combo.addItem(self._TEMPERATURE_LABEL, self._TEMPERATURE_LABEL)
        self._layout.addWidget(self.quantity_combo)

        self.value_spin = NoWheelDoubleSpinBox()
        self.value_spin.setDecimals(6)
        self.value_spin.setRange(-1.0e12, 1.0e12)
        self.value_spin.setValue(1.0)
        self._layout.addWidget(self.value_spin)

        self.from_unit_combo = NoWheelComboBox()
        self.to_unit_combo = NoWheelComboBox()
        self._layout.addWidget(self.from_unit_combo)
        self.arrow_label = QLabel("→")
        self._layout.addWidget(self.arrow_label)
        self._layout.addWidget(self.to_unit_combo)

        self.result_value = QLineEdit()
        self.result_value.setReadOnly(True)
        self.equals_label = QLabel("=")
        self._layout.addWidget(self.equals_label)
        self._layout.addWidget(self.result_value)
        self._layout.addStretch(1)

        self._apply_widget_widths(DEFAULT_UI_SCALE)

        self.quantity_combo.currentIndexChanged.connect(self._on_quantity_changed)
        self.value_spin.valueChanged.connect(self._update_result)
        self.from_unit_combo.currentIndexChanged.connect(self._update_result)
        self.to_unit_combo.currentIndexChanged.connect(self._update_result)

    def apply_ui_scale(self, ui_scale: float) -> None:
        self._ui_scale = ui_scale
        inset_x = scale_metric(6, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        inset_y = scale_metric(3, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        self._layout.setContentsMargins(inset_x, inset_y, inset_x, inset_y)
        self._layout.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._apply_widget_widths(ui_scale)

    def _apply_widget_widths(self, ui_scale: float) -> None:
        self.quantity_combo.setMinimumWidth(scale_metric(96, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.value_spin.setMinimumWidth(scale_metric(96, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.from_unit_combo.setMinimumWidth(scale_metric(84, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.to_unit_combo.setMinimumWidth(scale_metric(84, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.result_value.setMinimumWidth(scale_metric(128, ui_scale, reference_scale=DEFAULT_UI_SCALE))

    def _populate_units(self, combo: NoWheelComboBox, units: list[object]) -> None:
        combo.blockSignals(True)
        combo.clear()
        for unit in units:
            combo.addItem(unit.value, unit)
        combo.blockSignals(False)

    @staticmethod
    def _coerce_unit(value, enum_type):
        """Normalize Qt combo payloads back into the expected enum type."""
        if isinstance(value, enum_type):
            return value
        return enum_type(value)

    def _on_quantity_changed(self, *_args) -> None:
        self._setting_units = True
        try:
            quantity = self.quantity_combo.currentData()
            if quantity == self._TEMPERATURE_LABEL:
                units = list(TemperatureUnit)
                self._populate_units(self.from_unit_combo, units)
                self._populate_units(self.to_unit_combo, units)
                self.from_unit_combo.setCurrentIndex(self.from_unit_combo.findData(TemperatureUnit.C))
                self.to_unit_combo.setCurrentIndex(self.to_unit_combo.findData(TemperatureUnit.F))
                self.value_spin.setRange(-459.67, 1000000.0)
                self.value_spin.setValue(100.0)
                self.value_spin.setDecimals(4)
            else:
                units = list(PressureUnit)
                self._populate_units(self.from_unit_combo, units)
                self._populate_units(self.to_unit_combo, units)
                self.from_unit_combo.setCurrentIndex(self.from_unit_combo.findData(PressureUnit.PSIA))
                # Default target = atm (more common in coursework than bar).
                self.to_unit_combo.setCurrentIndex(self.to_unit_combo.findData(PressureUnit.ATM))
                self.value_spin.setRange(0.0, 1000000000.0)
                self.value_spin.setValue(1.0)
                self.value_spin.setDecimals(6)
        finally:
            self._setting_units = False
        self._update_result()

    def _update_result(self, *_args) -> None:
        if self._setting_units:
            return
        quantity = self.quantity_combo.currentData()
        value = self.value_spin.value()
        if quantity == self._TEMPERATURE_LABEL:
            from_unit = self._coerce_unit(self.from_unit_combo.currentData(), TemperatureUnit)
            to_unit = self._coerce_unit(self.to_unit_combo.currentData(), TemperatureUnit)
            if from_unit is None or to_unit is None:
                self.result_value.clear()
                return
            kelvin = temperature_to_k(value, from_unit)
            converted = temperature_from_k(kelvin, to_unit)
            self.result_value.setText(f"{converted:.6g} {_format_temperature_unit(to_unit)}")
            return

        from_unit = self._coerce_unit(self.from_unit_combo.currentData(), PressureUnit)
        to_unit = self._coerce_unit(self.to_unit_combo.currentData(), PressureUnit)
        if from_unit is None or to_unit is None:
            self.result_value.clear()
            return
        pascal = pressure_to_pa(value, from_unit)
        converted = pressure_from_pa(pascal, to_unit)
        self.result_value.setText(f"{converted:.6g} {to_unit.value}")


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
        self._current_plot_kind: Optional[str] = None
        self._plot_series_specs: dict[str, PlotSeriesSpec] = {}
        self._selected_plot_series: dict[str, list[str]] = {}
        self._view_mode = view_mode
        # Holds the most recent mplcursors Cursor object so we can .remove()
        # it before attaching a new one on the next plot. Leaving a stale
        # cursor attached would leak hover callbacks onto axes that no
        # longer exist after a figure.clear().
        self._hover_cursor = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)
        self._apply_background_color(self, PLOT_SURFACE_COLOR)

        self.series_controls = QWidget(self)
        self._apply_background_color(self.series_controls, PLOT_SURFACE_COLOR)
        self.series_controls.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.series_controls.hide()
        self._controls_layout = QHBoxLayout(self.series_controls)
        self._controls_layout.setContentsMargins(0, 0, 0, 0)
        self._controls_layout.setSpacing(8)
        self.series_label = QLabel("Plot Series")
        self.series_button = QToolButton(self.series_controls)
        self.series_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.series_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.series_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.series_button.setText("Select series")
        self.series_menu = QMenu(self.series_button)
        self.series_button.setMenu(self.series_menu)
        self._controls_layout.addWidget(self.series_label)
        self._controls_layout.addWidget(self.series_button)
        self._controls_layout.addStretch()
        self._layout.addWidget(self.series_controls, 0, Qt.AlignmentFlag.AlignTop)

        # Import matplotlib with Qt backend
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self.figure = Figure(figsize=(8, 6), dpi=100)
            self._apply_figure_theme()
            self.canvas = FigureCanvasQTAgg(self.figure)
            self._apply_background_color(self.canvas, PLOT_SURFACE_COLOR)
            self.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.canvas.setMinimumSize(0, 0)
            self._layout.addWidget(self.canvas, 1)

            self._matplotlib_available = True

        except ImportError:
            # Fallback if matplotlib not available
            self._matplotlib_available = False
            placeholder = QLabel(
                "Matplotlib not available.\n"
                "Install with: pip install matplotlib"
            )
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._layout.addWidget(placeholder, 1)

        # Export button
        self._btn_layout = QHBoxLayout()
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_layout.setSpacing(8)
        self._btn_layout.addStretch()
        self.export_btn = QPushButton("Export Plot")
        self.export_btn.clicked.connect(self._export_plot)
        self._btn_layout.addWidget(self.export_btn)
        self._layout.addLayout(self._btn_layout)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Keep the plot surface spacing aligned with the app shell zoom."""
        self._layout.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._controls_layout.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._btn_layout.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        if self._matplotlib_available:
            self._sync_figure_size()
            if self._current_result is not None:
                self._refresh_plot()
            else:
                self.canvas.draw_idle()

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

    def _attach_hover_tooltips(
        self,
        data_lines: list,
        *,
        x_label: str,
        x_unit: str = "",
        x_precision: int = 2,
        y_precision: int = 4,
    ) -> None:
        """Attach mplcursors hover tooltips to the given data line artists.

        Shows ``{x_label} = {x_value} {x_unit}`` on one line and
        ``{series_label} = {y_value}`` on the next, styled to match the
        dark palette used by the rest of the plot. Any artist whose label
        starts with ``_`` (matplotlib's hide-from-legend convention) is
        silently skipped so reference-only axvline underscore labels don't
        produce bogus tooltips. The previously-attached cursor, if any, is
        removed first so hover callbacks do not accumulate across replots.
        """
        # Tear down the prior cursor so we don't leak handlers onto an
        # axes object that will be discarded on the next figure.clear().
        if self._hover_cursor is not None:
            try:
                self._hover_cursor.remove()
            except Exception:
                pass
            self._hover_cursor = None

        if not data_lines:
            return
        try:
            import mplcursors
        except ImportError:
            # mplcursors is an optional runtime dep; fall back to no
            # tooltips rather than breaking the plot altogether.
            return

        cursor = mplcursors.cursor(data_lines, hover=True)
        x_unit_suffix = f" {x_unit}" if x_unit else ""

        @cursor.connect("add")
        def _on_hover(sel):
            label = sel.artist.get_label() or "Value"
            if label.startswith("_"):
                sel.annotation.set_visible(False)
                return
            x_val, y_val = sel.target
            sel.annotation.set_text(
                f"{x_label} = {x_val:.{x_precision}f}{x_unit_suffix}\n"
                f"{label} = {y_val:.{y_precision}g}"
            )
            bbox = sel.annotation.get_bbox_patch()
            if bbox is not None:
                bbox.set_facecolor(PLOT_LEGEND_FACE_COLOR)
                bbox.set_edgecolor(PLOT_GRID_COLOR)
                bbox.set_alpha(0.95)
            sel.annotation.set_color(PLOT_TEXT_COLOR)

        self._hover_cursor = cursor

    @staticmethod
    def _cluster_title(cluster: list["PlotSeriesSpec"]) -> str:
        """Pick a short, descriptive title for a subplot.

        - Single-spec cluster → use the spec label verbatim (e.g. "Z-factor",
          "Relative Volume").
        - Multi-spec cluster with a common trailing word → use that word
          (e.g. "Liquid Density" + "Vapor Density" → "Density";
          "Liquid Viscosity" + "Vapor Viscosity" → "Viscosity").
        - Otherwise fall back to a joined label.
        """
        if not cluster:
            return ""
        if len(cluster) == 1:
            return cluster[0].label
        label_parts = [spec.label.split() for spec in cluster]
        common = set(label_parts[0])
        for parts in label_parts[1:]:
            common &= set(parts)
        if common:
            return " ".join(w for w in label_parts[0] if w in common)
        return " / ".join(spec.label for spec in cluster)

    def _apply_figure_suptitle(self, title: str) -> None:
        """Set a figure-level super-title styled for the dark theme.

        Used in place of per-axis titles on the first subplot so the main
        title sits cleanly above the whole grid rather than crowding the
        top-left panel.
        """
        if title:
            self.figure.suptitle(title, color=PLOT_TEXT_COLOR, fontsize=12)

    def _component_display_label(self, component_id: str) -> str:
        """Use the same compact component labels in plots as in the results tables."""
        return _display_component_label(component_id, self._current_result)

    def _tighten_composition_plot_layout(self) -> None:
        """Keep bar-chart composition plots from wasting vertical space below the x-axis."""
        self.figure.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.20)

    @staticmethod
    def _set_mole_fraction_axis(ax) -> None:
        """Keep composition bar charts on the physical 0..1 mole-fraction scale."""
        ax.set_ylim(0.0, 1.0)

    def clear(self) -> None:
        """Clear the plot."""
        self._current_result = None
        self._current_plot_kind = None
        self._plot_series_specs = {}
        self.series_controls.hide()
        if self._matplotlib_available:
            self.figure.clear()
            self._apply_figure_theme()
            self.canvas.draw()

    def _sync_figure_size(self) -> None:
        """Match the Matplotlib figure size to the live Qt canvas size."""
        if not self._matplotlib_available:
            return
        device_pixel_ratio = 1.0
        if hasattr(self.canvas, "devicePixelRatioF"):
            device_pixel_ratio = max(float(self.canvas.devicePixelRatioF()), 1.0)
        width = max(self.canvas.width() * device_pixel_ratio, 1.0)
        height = max(self.canvas.height() * device_pixel_ratio, 1.0)
        dpi = max(float(self.figure.get_dpi()), 1.0)
        self.figure.set_size_inches(width / dpi, height / dpi, forward=False)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._matplotlib_available:
            return
        self._sync_figure_size()
        if self._current_result is not None:
            self._refresh_plot()
        else:
            self.canvas.draw_idle()

    def display_result(self, result: RunResult) -> None:
        """Display a calculation result as a plot.

        Args:
            result: RunResult to plot
        """
        if not self._matplotlib_available:
            return

        self._current_result = result
        self._configure_plot_series_selector(result)
        self._refresh_plot()

    def _refresh_plot(self) -> None:
        """Redraw the plot for the current result and series selection."""
        if not self._matplotlib_available or self._current_result is None:
            return

        self._sync_figure_size()
        self.figure.clear()
        self._apply_figure_theme()
        result = self._current_result

        if self._view_mode == "phase_envelope_only":
            if result.phase_envelope_result:
                self._plot_phase_envelope(result.phase_envelope_result)
            else:
                calc_label = _format_calculation_type_label(result.config.calculation_type)
                self._plot_placeholder(
                    "Phase envelope view is only populated by phase-envelope runs.\n"
                    f"Latest result type: {calc_label}.",
                    title="Phase Envelope",
                )
        elif result.pt_flash_result:
            self._plot_pt_flash(result.pt_flash_result)
        elif result.stability_analysis_result:
            self._plot_stability_analysis(result.stability_analysis_result)
        elif result.bubble_point_result:
            self._plot_bubble_point(result.bubble_point_result)
        elif result.dew_point_result:
            self._plot_dew_point(result.dew_point_result)
        elif result.phase_envelope_result:
            self._plot_phase_envelope(result.phase_envelope_result)
        elif result.tbp_result:
            self._plot_tbp(result.tbp_result)
        elif result.cce_result:
            self._plot_cce(result.cce_result)
        elif result.dl_result:
            self._plot_dl(result.dl_result)
        elif result.cvd_result:
            self._plot_cvd(result.cvd_result)
        elif result.swelling_test_result:
            self._plot_swelling(result.swelling_test_result)
        elif result.separator_result:
            self._plot_separator(result.separator_result)

        self.canvas.draw()

    def _configure_plot_series_selector(self, result: RunResult) -> None:
        """Expose checkable plot-series options for pressure-driven experiment plots."""
        if self._view_mode == "phase_envelope_only":
            self._current_plot_kind = None
            self._plot_series_specs = {}
            self.series_menu.clear()
            self.series_button.setText("Select series")
            self.series_controls.hide()
            return

        if result.cce_result is not None:
            plot_kind = "cce"
            specs = self._cce_plot_series_specs(result.cce_result)
        elif result.dl_result is not None:
            plot_kind = "dl"
            specs = self._dl_plot_series_specs(result.dl_result)
        elif result.cvd_result is not None:
            plot_kind = "cvd"
            specs = self._cvd_plot_series_specs(result.cvd_result)
        elif result.swelling_test_result is not None:
            plot_kind = "swelling"
            specs = self._swelling_plot_series_specs(result.swelling_test_result)
        elif result.separator_result is not None:
            plot_kind = "separator"
            specs = self._separator_plot_series_specs(result.separator_result)
        else:
            self._current_plot_kind = None
            self._plot_series_specs = {}
            self.series_menu.clear()
            self.series_button.setText("Select series")
            self.series_controls.hide()
            return

        self._current_plot_kind = plot_kind
        self._plot_series_specs = specs
        self.series_menu.clear()

        selected = [
            key
            for key in self._selected_plot_series.get(plot_kind, [])
            if key in specs
        ]
        if not selected:
            selected = [
                key
                for key, spec in specs.items()
                if spec.default_selected
            ]
        if not selected and specs:
            selected = [next(iter(specs))]
        self._selected_plot_series[plot_kind] = selected

        for key, spec in specs.items():
            action = QAction(spec.label, self.series_menu)
            action.setCheckable(True)
            action.setChecked(key in selected)
            action.toggled.connect(
                lambda checked, *, series_key=key: self._on_plot_series_toggled(series_key, checked)
            )
            self.series_menu.addAction(action)

        self._update_plot_series_button_text()
        self.series_controls.show()

    def _on_plot_series_toggled(self, series_key: str, checked: bool) -> None:
        """Track plot-series selection and redraw the active plot."""
        if self._current_plot_kind is None:
            return
        selected = list(self._selected_plot_series.get(self._current_plot_kind, []))
        if checked:
            if series_key not in selected:
                selected.append(series_key)
        else:
            selected = [key for key in selected if key != series_key]
        self._selected_plot_series[self._current_plot_kind] = selected
        self._update_plot_series_button_text()
        self._refresh_plot()

    def _update_plot_series_button_text(self) -> None:
        """Keep the selector caption aligned with the active checked series."""
        if self._current_plot_kind is None:
            self.series_button.setText("Select series")
            return
        specs = self._plot_series_specs
        labels = [
            specs[key].label
            for key in self._selected_plot_series.get(self._current_plot_kind, [])
            if key in specs
        ]
        if not labels:
            self.series_button.setText("Select series")
        elif len(labels) <= 2:
            self.series_button.setText(", ".join(labels))
        else:
            self.series_button.setText(f"{len(labels)} selected")

    def _saturation_pressure_unit(self) -> PressureUnit:
        """Return the preferred saturation pressure unit."""
        config: Optional[SaturationPointConfig] = None
        if self._current_result is not None:
            config = (
                self._current_result.config.bubble_point_config
                or self._current_result.config.dew_point_config
            )
        if config is None:
            return PressureUnit.PSIA
        return config.pressure_unit

    def _stability_plot_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred standalone stability-analysis plot units."""
        config: Optional[StabilityAnalysisConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.stability_analysis_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _cce_plot_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred CCE plot units."""
        config: Optional[CCEConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.cce_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _dl_plot_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred DL plot units."""
        config: Optional[DLConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.dl_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _swelling_plot_units(self) -> tuple[PressureUnit, TemperatureUnit]:
        """Return the preferred swelling-test plot units."""
        config: Optional[SwellingTestConfig] = None
        if self._current_result is not None:
            config = self._current_result.config.swelling_test_config
        if config is None:
            return PressureUnit.PSIA, TemperatureUnit.F
        return config.pressure_unit, config.temperature_unit

    def _plot_placeholder(self, message: str, *, title: str = "Plot") -> None:
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
        ax.set_title(title)
        self._apply_axes_theme(ax)
        self.figure.tight_layout()

    def _current_series_specs(self) -> list[PlotSeriesSpec]:
        """Return the checked plot-series specs in stable definition order."""
        if self._current_plot_kind is None:
            return []
        selected = set(self._selected_plot_series.get(self._current_plot_kind, []))
        return [
            spec
            for key, spec in self._plot_series_specs.items()
            if key in selected
        ]

    @staticmethod
    def _series_value_range(values: list[Optional[float]]) -> Optional[tuple[float, float]]:
        finite_values = [
            float(value)
            for value in values
            if value is not None and math.isfinite(float(value))
        ]
        if not finite_values:
            return None
        return min(finite_values), max(finite_values)

    def _series_are_compatible_for_overlay(
        self,
        cluster: list[PlotSeriesSpec],
        candidate: PlotSeriesSpec,
    ) -> bool:
        """Return whether two pressure-series remain visually comparable on one axis."""
        if candidate.force_overlay or any(spec.force_overlay for spec in cluster):
            return True

        cluster_range = self._series_value_range(
            [value for spec in cluster for value in spec.values]
        )
        candidate_range = self._series_value_range(candidate.values)
        if cluster_range is None or candidate_range is None:
            return False

        cluster_min, cluster_max = cluster_range
        candidate_min, candidate_max = candidate_range
        cluster_span = cluster_max - cluster_min
        candidate_span = candidate_max - candidate_min
        cluster_scale = max(abs(cluster_min), abs(cluster_max), cluster_span)
        candidate_scale = max(abs(candidate_min), abs(candidate_max), candidate_span)
        tiny = 1.0e-12

        if cluster_scale <= tiny or candidate_scale <= tiny:
            return cluster_scale <= tiny and candidate_scale <= tiny

        magnitude_ratio = max(cluster_scale, candidate_scale) / max(
            min(cluster_scale, candidate_scale),
            tiny,
        )
        if magnitude_ratio > 8.0:
            return False

        if cluster_span <= tiny or candidate_span <= tiny:
            return True

        span_ratio = max(cluster_span, candidate_span) / max(
            min(cluster_span, candidate_span),
            tiny,
        )
        return span_ratio <= 12.0 or magnitude_ratio <= 3.0

    def _cluster_selected_series(self, specs: list[PlotSeriesSpec]) -> list[list[PlotSeriesSpec]]:
        """Partition checked series into visually compatible subplot clusters."""
        clusters: list[list[PlotSeriesSpec]] = []
        groups: dict[str, list[PlotSeriesSpec]] = {}
        group_order: list[str] = []

        for spec in specs:
            if spec.overlay_group not in groups:
                groups[spec.overlay_group] = []
                group_order.append(spec.overlay_group)
            groups[spec.overlay_group].append(spec)

        for group in group_order:
            for spec in groups[group]:
                placed = False
                for cluster in clusters:
                    if cluster[0].overlay_group != group:
                        continue
                    if self._series_are_compatible_for_overlay(cluster, spec):
                        cluster.append(spec)
                        placed = True
                        break
                if not placed:
                    clusters.append([spec])
        return clusters

    @staticmethod
    def _cluster_axis_label(cluster: list[PlotSeriesSpec]) -> str:
        if not cluster:
            return ""
        if len(cluster) == 1:
            return cluster[0].axis_label
        first_label = cluster[0].axis_label
        if all(spec.axis_label == first_label for spec in cluster):
            return first_label
        return cluster[0].axis_label

    @staticmethod
    def _finite_pressure_series(
        pressures: list[float],
        values: list[Optional[float]],
    ) -> tuple[list[float], list[float]]:
        """Filter a pressure series down to finite numeric values only."""
        return ResultsPlotWidget._finite_xy_series(pressures, values)

    @staticmethod
    def _finite_xy_series(
        xs_in: list[float],
        values: list[Optional[float]],
    ) -> tuple[list[float], list[float]]:
        """Filter any x/y series pair down to finite numeric values only."""
        xs: list[float] = []
        ys: list[float] = []
        for x_value, value in zip(xs_in, values, strict=True):
            if value is None:
                continue
            numeric = float(value)
            if not math.isfinite(numeric):
                continue
            xs.append(x_value)
            ys.append(numeric)
        return xs, ys

    def _cce_plot_series_specs(self, result: CCEResult) -> dict[str, PlotSeriesSpec]:
        """Return the available selectable CCE series."""
        return {
            "liquid_density": PlotSeriesSpec(
                key="liquid_density",
                label="Liquid Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[step.liquid_density_kg_per_m3 for step in result.steps],
                color="#2563eb",
                default_selected=True,
            ),
            "vapor_density": PlotSeriesSpec(
                key="vapor_density",
                label="Vapor Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[step.vapor_density_kg_per_m3 for step in result.steps],
                color="#dc2626",
                default_selected=True,
                marker="s",
            ),
            "relative_volume": PlotSeriesSpec(
                key="relative_volume",
                label="Relative Volume",
                # Dedicated axis group (not the generic "dimensionless" bucket)
                # so the y-axis label can carry the V/Vsat qualifier without
                # overriding sibling axes like liquid/vapor fraction. Mathtext
                # gives a real subscript on the "sat" qualifier.
                axis_group="relative_volume",
                axis_label=r"$V/V_{sat}$",
                overlay_group="relative_volume",
                values=[step.relative_volume for step in result.steps],
                color="#f59e0b",
                default_selected=True,
                linestyle="--",
            ),
            "liquid_fraction": PlotSeriesSpec(
                key="liquid_fraction",
                label="Liquid Fraction",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="fraction",
                values=[step.liquid_fraction for step in result.steps],
                color="#10b981",
                force_overlay=True,
                preferred_ylim=(0.0, 1.0),
            ),
            "vapor_fraction": PlotSeriesSpec(
                key="vapor_fraction",
                label="Vapor Fraction",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="fraction",
                values=[step.vapor_fraction for step in result.steps],
                color="#ef4444",
                force_overlay=True,
                preferred_ylim=(0.0, 1.0),
            ),
            "z_factor": PlotSeriesSpec(
                key="z_factor",
                label="Z-factor",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="z_factor",
                values=[step.z_factor for step in result.steps],
                color="#8b5cf6",
                marker="d",
                default_selected=True,
            ),
            "liquid_viscosity": PlotSeriesSpec(
                key="liquid_viscosity",
                label="Liquid Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.liquid_viscosity_cp for step in result.steps],
                color="#0f766e",
            ),
            "vapor_viscosity": PlotSeriesSpec(
                key="vapor_viscosity",
                label="Vapor Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.vapor_viscosity_cp for step in result.steps],
                color="#7c3aed",
                marker="^",
            ),
        }

    def _dl_plot_series_specs(self, result: DLResult) -> dict[str, PlotSeriesSpec]:
        """Return the available selectable DL series."""
        return {
            "rsd": PlotSeriesSpec(
                key="rsd",
                label="RsD",
                axis_group="gor",
                axis_label="Solution GOR",
                overlay_group="solution_gor",
                values=[step.rs for step in result.steps],
                color="#22c55e",
                default_selected=True,
            ),
            "rsdb": PlotSeriesSpec(
                key="rsdb",
                label="RsDb",
                axis_group="gor",
                axis_label="Solution GOR",
                overlay_group="solution_gor",
                values=[result.rsi for _ in result.steps],
                color="#86efac",
                linestyle=":",
            ),
            "bo": PlotSeriesSpec(
                key="bo",
                label="Bo",
                axis_group="fvf",
                axis_label="Formation Volume Factor",
                overlay_group="liquid_fvf",
                values=[step.bo for step in result.steps],
                color="#eab308",
                default_selected=True,
            ),
            "bg": PlotSeriesSpec(
                key="bg",
                label="Bg",
                axis_group="fvf",
                axis_label="Formation Volume Factor",
                overlay_group="gas_fvf",
                values=[step.bg for step in result.steps],
                color="#38bdf8",
                marker="s",
            ),
            "btd": PlotSeriesSpec(
                key="btd",
                label="BtD",
                axis_group="fvf",
                axis_label="Formation Volume Factor",
                overlay_group="liquid_fvf",
                values=[step.bt for step in result.steps],
                color="#f472b6",
                default_selected=True,
                linestyle="--",
            ),
            "oil_viscosity": PlotSeriesSpec(
                key="oil_viscosity",
                label="Oil Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.oil_viscosity_cp for step in result.steps],
                color="#0f766e",
            ),
            "gas_viscosity": PlotSeriesSpec(
                key="gas_viscosity",
                label="Gas Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.gas_viscosity_cp for step in result.steps],
                color="#7c3aed",
                marker="^",
            ),
        }

    def _cvd_plot_series_specs(self, result: CVDResult) -> dict[str, PlotSeriesSpec]:
        """Return the available selectable CVD series."""
        return {
            "liquid_dropout": PlotSeriesSpec(
                key="liquid_dropout",
                label="Liquid Dropout",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="liquid_dropout",
                values=[step.liquid_dropout for step in result.steps],
                color="#06b6d4",
                default_selected=True,
            ),
            "gas_produced": PlotSeriesSpec(
                key="gas_produced",
                label="Gas Produced",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="gas_release",
                values=[step.gas_produced for step in result.steps],
                color="#f97316",
            ),
            "cumulative_gas_produced": PlotSeriesSpec(
                key="cumulative_gas_produced",
                label="Cumulative Gas",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="gas_release",
                values=[step.cumulative_gas_produced for step in result.steps],
                color="#22c55e",
                default_selected=True,
                linestyle="--",
            ),
            "moles_remaining": PlotSeriesSpec(
                key="moles_remaining",
                label="Moles Remaining",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="inventory",
                values=[step.moles_remaining for step in result.steps],
                color="#a3e635",
            ),
            "z_two_phase": PlotSeriesSpec(
                key="z_two_phase",
                label="Z-factor",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="z_factor",
                values=[step.z_two_phase for step in result.steps],
                color="#8b5cf6",
                default_selected=True,
                marker="d",
            ),
            "liquid_density": PlotSeriesSpec(
                key="liquid_density",
                label="Liquid Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[step.liquid_density_kg_per_m3 for step in result.steps],
                color="#2563eb",
            ),
            "vapor_density": PlotSeriesSpec(
                key="vapor_density",
                label="Vapor Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[step.vapor_density_kg_per_m3 for step in result.steps],
                color="#dc2626",
                marker="s",
            ),
            "liquid_viscosity": PlotSeriesSpec(
                key="liquid_viscosity",
                label="Liquid Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.liquid_viscosity_cp for step in result.steps],
                color="#0f766e",
            ),
            "vapor_viscosity": PlotSeriesSpec(
                key="vapor_viscosity",
                label="Vapor Viscosity",
                axis_group="viscosity",
                axis_label="Viscosity (cP)",
                overlay_group="viscosity",
                values=[step.vapor_viscosity_cp for step in result.steps],
                color="#7c3aed",
                marker="^",
            ),
        }

    def _separator_plot_series_specs(self, result: SeparatorResult) -> dict[str, PlotSeriesSpec]:
        """Return the available selectable separator-trend series."""
        return {
            "vapor_fraction": PlotSeriesSpec(
                key="vapor_fraction",
                label="Vapor Fraction",
                axis_group="fraction",
                axis_label="Fraction",
                overlay_group="fraction",
                values=[stage.vapor_fraction for stage in result.stages],
                color="#f59e0b",
                default_selected=True,
                force_overlay=True,
                preferred_ylim=(0.0, 1.0),
            ),
            "liquid_moles": PlotSeriesSpec(
                key="liquid_moles",
                label="Liquid Moles",
                axis_group="moles",
                axis_label="Moles",
                overlay_group="moles",
                values=[stage.liquid_moles for stage in result.stages],
                color="#22c55e",
                default_selected=True,
            ),
            "vapor_moles": PlotSeriesSpec(
                key="vapor_moles",
                label="Vapor Moles",
                axis_group="moles",
                axis_label="Moles",
                overlay_group="moles",
                values=[stage.vapor_moles for stage in result.stages],
                color="#ef4444",
                default_selected=True,
                linestyle="--",
            ),
            "liquid_density": PlotSeriesSpec(
                key="liquid_density",
                label="Liquid Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[stage.liquid_density_kg_per_m3 for stage in result.stages],
                color="#2563eb",
            ),
            "vapor_density": PlotSeriesSpec(
                key="vapor_density",
                label="Vapor Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[stage.vapor_density_kg_per_m3 for stage in result.stages],
                color="#dc2626",
                marker="s",
            ),
            "liquid_z": PlotSeriesSpec(
                key="liquid_z",
                label="ZL",
                axis_group="z",
                axis_label="Z-factor",
                overlay_group="z_factor",
                values=[stage.liquid_z_factor for stage in result.stages],
                color="#0ea5e9",
                marker="d",
            ),
            "vapor_z": PlotSeriesSpec(
                key="vapor_z",
                label="ZV",
                axis_group="z",
                axis_label="Z-factor",
                overlay_group="z_factor",
                values=[stage.vapor_z_factor for stage in result.stages],
                color="#a855f7",
                marker="^",
            ),
        }

    def _swelling_plot_series_specs(self, result: SwellingTestResult) -> dict[str, PlotSeriesSpec]:
        """Return the available selectable swelling-test series."""
        pressure_unit, _temperature_unit = self._swelling_plot_units()
        return {
            "bubble_pressure": PlotSeriesSpec(
                key="bubble_pressure",
                label="Bubble Pressure",
                axis_group="pressure",
                axis_label=f"Pressure ({pressure_unit.value})",
                overlay_group="pressure",
                values=[
                    None
                    if step.bubble_pressure_pa is None
                    else pressure_from_pa(step.bubble_pressure_pa, pressure_unit)
                    for step in result.steps
                ],
                color="#2563eb",
                default_selected=True,
            ),
            "swelling_factor": PlotSeriesSpec(
                key="swelling_factor",
                label="Swelling Factor",
                axis_group="dimensionless",
                axis_label="Dimensionless",
                overlay_group="swelling_factor",
                values=[step.swelling_factor for step in result.steps],
                color="#f59e0b",
                default_selected=True,
                linestyle="--",
            ),
            "liquid_density": PlotSeriesSpec(
                key="liquid_density",
                label="Sat. Liquid Density",
                axis_group="density",
                axis_label="Density (kg/m³)",
                overlay_group="density",
                values=[step.saturated_liquid_density_kg_per_m3 for step in result.steps],
                color="#22c55e",
                default_selected=True,
                marker="s",
            ),
        }

    def _plot_selected_pressure_series(
        self,
        *,
        pressures: list[float],
        specs: list[PlotSeriesSpec],
        pressure_unit: PressureUnit,
        title: str,
        reference_pressure: Optional[float] = None,
        reference_label: Optional[str] = None,
    ) -> None:
        """Plot selected experiment series using separate subplots for incompatible scales."""
        if not specs:
            self._plot_placeholder("Select at least one series to display.", title=title)
            return

        clusters = self._cluster_selected_series(specs)
        # Pick a grid that keeps each panel reasonably square: with four or
        # more clusters we switch to a near-square (rows x cols) grid so
        # individual plots don't get vertically crushed. Stacked Nx1 is
        # fine for up to 3 clusters.
        n_clusters = len(clusters)
        if n_clusters >= 4:
            import math
            cols = math.ceil(math.sqrt(n_clusters))
            rows = math.ceil(n_clusters / cols)
        else:
            rows, cols = n_clusters, 1
        axes: list[object] = []
        for index in range(len(clusters)):
            share_axis = axes[0] if axes else None
            axis = self.figure.add_subplot(rows, cols, index + 1, sharex=share_axis)
            axis.set_facecolor(PLOT_CANVAS_COLOR)
            axes.append(axis)

        plotted_any = False
        data_lines: list = []
        for index, (axis, cluster) in enumerate(zip(axes, clusters, strict=True)):
            cluster_plotted = False
            for spec in cluster:
                xs, ys = self._finite_pressure_series(pressures, spec.values)
                if not xs:
                    continue
                line, = axis.plot(
                    xs,
                    ys,
                    color=spec.color,
                    marker=spec.marker,
                    linestyle=spec.linestyle,
                    linewidth=spec.linewidth,
                    markersize=spec.markersize,
                    label=spec.label,
                )
                data_lines.append(line)
                cluster_plotted = True
                plotted_any = True

            if reference_pressure is not None and reference_label:
                axis.axvline(
                    reference_pressure,
                    color="#ef4444",
                    linestyle="--",
                    linewidth=1.5,
                    label=reference_label if index == 0 else "_nolegend_",
                )

            if not cluster_plotted and reference_pressure is None:
                axis.text(
                    0.5,
                    0.5,
                    "No finite data is available for the selected series.",
                    color=PLOT_TEXT_COLOR,
                    ha="center",
                    va="center",
                    wrap=True,
                    transform=axis.transAxes,
                )

            preferred_ylim = next(
                (spec.preferred_ylim for spec in cluster if spec.preferred_ylim is not None),
                None,
            )
            if preferred_ylim is not None:
                axis.set_ylim(*preferred_ylim)
            axis.set_ylabel(self._cluster_axis_label(cluster))
            axis.set_xlabel(f"Pressure ({pressure_unit.value})")
            # Per-subplot title derived from the cluster's series so every
            # panel is self-labelled rather than relying on the top-left
            # one to double as the figure heading.
            subplot_title = self._cluster_title(cluster)
            if subplot_title:
                axis.set_title(subplot_title, color=PLOT_TEXT_COLOR, fontsize=10)
            # invert_xaxis() TOGGLES the axis direction, and with sharex all
            # subplots share the same underlying x-axis state. Calling it on
            # every axis flipped the direction even-vs-odd across the plot
            # count (2 clusters = upright, 3 = inverted, 4 = upright, etc.).
            # Apply once on the first axis; sharex propagates to the rest.
            if index == 0:
                axis.invert_xaxis()
            self._apply_axes_theme(axis)

            handles, labels = axis.get_legend_handles_labels()
            if handles:
                axis.legend(handles, labels, loc="best")
                self._apply_axes_theme(axis)

        if not plotted_any and reference_pressure is None:
            self.figure.clear()
            self._apply_figure_theme()
            self._plot_placeholder("No finite data is available for the selected series.", title=title)
            return

        # Figure-level main title above the whole grid (replaces the old
        # axis.set_title on axes[0] which crowded the first panel).
        self._apply_figure_suptitle(title)

        # Pin ticks to the calculation's actual pressure steps when there
        # are few enough to read. sharex propagates ticks from axes[0] to
        # every subplot in the grid, so setting them once is sufficient.
        if axes and 0 < len(pressures) <= _EXPLICIT_XTICKS_MAX:
            axes[0].set_xticks(list(pressures))

        # Hover tooltips: "P = <value> <unit>\n<series-label> = <value>"
        # on every data marker across every subplot.
        self._attach_hover_tooltips(
            data_lines,
            x_label="P",
            x_unit=pressure_unit.value,
        )

        if len(axes) > 1:
            if cols > 1:
                # Grid layout (e.g. 2x2): give extra horizontal breathing room
                # between columns so y-axis labels don't clash with the
                # preceding column's tick labels. Extra top margin for the
                # figure-level suptitle + per-axis titles.
                self.figure.subplots_adjust(
                    left=0.10, right=0.97, top=0.88, bottom=0.11, hspace=0.55, wspace=0.32
                )
            else:
                self.figure.subplots_adjust(
                    left=0.12, right=0.97, top=0.88, bottom=0.09, hspace=0.50
                )
        else:
            self.figure.tight_layout(rect=(0, 0, 1, 0.94))

    def _plot_selected_enrichment_series(
        self,
        *,
        enrichment_steps: list[float],
        specs: list[PlotSeriesSpec],
        title: str,
        x_label: str = "Added Gas (mol/mol initial oil)",
    ) -> None:
        """Plot selected swelling-test series against enrichment/contact ratio."""
        if not specs:
            self._plot_placeholder("Select at least one series to display.", title=title)
            return

        clusters = self._cluster_selected_series(specs)
        # Pick a grid that keeps each panel reasonably square: with four or
        # more clusters we switch to a near-square (rows x cols) grid so
        # individual plots don't get vertically crushed. Stacked Nx1 is
        # fine for up to 3 clusters.
        n_clusters = len(clusters)
        if n_clusters >= 4:
            import math
            cols = math.ceil(math.sqrt(n_clusters))
            rows = math.ceil(n_clusters / cols)
        else:
            rows, cols = n_clusters, 1
        axes: list[object] = []
        for index in range(len(clusters)):
            share_axis = axes[0] if axes else None
            axis = self.figure.add_subplot(rows, cols, index + 1, sharex=share_axis)
            axis.set_facecolor(PLOT_CANVAS_COLOR)
            axes.append(axis)

        plotted_any = False
        data_lines: list = []
        for index, (axis, cluster) in enumerate(zip(axes, clusters, strict=True)):
            cluster_plotted = False
            for spec in cluster:
                xs, ys = self._finite_xy_series(enrichment_steps, spec.values)
                if not xs:
                    continue
                line, = axis.plot(
                    xs,
                    ys,
                    color=spec.color,
                    marker=spec.marker,
                    linestyle=spec.linestyle,
                    linewidth=spec.linewidth,
                    markersize=spec.markersize,
                    label=spec.label,
                )
                data_lines.append(line)
                cluster_plotted = True
                plotted_any = True

            if not cluster_plotted:
                axis.text(
                    0.5,
                    0.5,
                    "No finite data is available for the selected series.",
                    color=PLOT_TEXT_COLOR,
                    ha="center",
                    va="center",
                    wrap=True,
                    transform=axis.transAxes,
                )

            preferred_ylim = next(
                (spec.preferred_ylim for spec in cluster if spec.preferred_ylim is not None),
                None,
            )
            if preferred_ylim is not None:
                axis.set_ylim(*preferred_ylim)
            axis.set_ylabel(self._cluster_axis_label(cluster))
            axis.set_xlabel(x_label)
            subplot_title = self._cluster_title(cluster)
            if subplot_title:
                axis.set_title(subplot_title, color=PLOT_TEXT_COLOR, fontsize=10)
            self._apply_axes_theme(axis)

            handles, labels = axis.get_legend_handles_labels()
            if handles:
                axis.legend(handles, labels, loc="best")
                self._apply_axes_theme(axis)

        if not plotted_any:
            self.figure.clear()
            self._apply_figure_theme()
            self._plot_placeholder("No finite data is available for the selected series.", title=title)
            return

        # Figure-level main title above the grid (same pattern as the
        # pressure-series plot).
        self._apply_figure_suptitle(title)

        # Same tick-threshold policy as the pressure-series plot: lock
        # ticks to the enrichment steps the user actually specified when
        # there are few of them; otherwise let matplotlib auto-locate.
        if axes and 0 < len(enrichment_steps) <= _EXPLICIT_XTICKS_MAX:
            axes[0].set_xticks(list(enrichment_steps))

        # Hover tooltips. The enrichment axis is dimensionless
        # (mol-added / mol-initial-oil), so no x_unit suffix.
        self._attach_hover_tooltips(
            data_lines,
            x_label="Added Gas",
            x_unit="",
            x_precision=3,
        )

        if len(axes) > 1:
            self.figure.subplots_adjust(left=0.12, right=0.97, top=0.88, bottom=0.10, hspace=0.50)
        else:
            self.figure.tight_layout(rect=(0, 0, 1, 0.94))

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
        self._set_mole_fraction_axis(ax)
        ax.set_xticks(x)
        ax.set_xticklabels(display_labels, rotation=35, ha='right', rotation_mode='anchor')
        ax.legend()
        self._apply_axes_theme(ax)

        self._tighten_composition_plot_layout()

    def _plot_stability_analysis(self, result: StabilityAnalysisResult) -> None:
        """Plot standalone stability-analysis TPD branch values."""
        pressure_unit, temperature_unit = self._stability_plot_units()
        series: list[tuple[str, float]] = []
        if result.vapor_like_trial is not None:
            series.append(("Vapor-like", result.vapor_like_trial.tpd))
        if result.liquid_like_trial is not None:
            series.append(("Liquid-like", result.liquid_like_trial.tpd))

        if not series:
            self._plot_placeholder("No trial branches are available for this stability result.", title="Stability Analysis")
            return

        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)
        labels = [label for label, _value in series]
        values = [value for _label, value in series]
        colors = ["#22c55e" if value >= 0.0 else "#ef4444" for value in values]
        x = list(range(len(series)))

        bars = ax.bar(x, values, color=colors, alpha=0.85)
        ax.axhline(0.0, color="#94a3b8", linestyle="--", linewidth=1.2)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("TPD")
        ax.set_title(
            "Stability Analysis at "
            f"{_format_pressure(result.pressure_pa, pressure_unit)} / "
            f"{_format_temperature(result.temperature_k, temperature_unit, precision=1)}"
        )
        self._apply_axes_theme(ax)

        for bar, value in zip(bars, values, strict=True):
            offset = 6 if value >= 0 else -14
            va = "bottom" if value >= 0 else "top"
            ax.annotate(
                f"{value:.3e}",
                xy=(bar.get_x() + bar.get_width() / 2.0, value),
                xytext=(0, offset),
                textcoords="offset points",
                ha="center",
                va=va,
                color=PLOT_TEXT_COLOR,
                fontsize=9,
            )

        self.figure.tight_layout()

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
            # Plot only traced saturation points. Do not inject the detected critical
            # point into these polylines: it generally does not lie on the discrete
            # bubble or dew locus, and sorting by T creates fake segments (spikes).
            xy = [
                (p.temperature_k - 273.15, p.pressure_pa / 1e5)
                for p in points
            ]
            temps = [t for t, _ in xy]
            pressures = [p for _, p in xy]
            return temps, pressures

        # Bubble / dew / critical-point artists are captured so we can
        # attach hover tooltips at the end of the function.
        data_lines: list = []

        # Bubble curve
        if result.bubble_curve:
            temps, pressures = _curve_xy(result.bubble_curve)
            line, = ax.plot(temps, pressures, 'b-', linewidth=2, label='Bubble Point')
            data_lines.append(line)

        # Dew curve
        if result.dew_curve:
            temps, pressures = _curve_xy(result.dew_curve)
            line, = ax.plot(temps, pressures, 'r-', linewidth=2, label='Dew Point')
            data_lines.append(line)

        # Critical point
        if critical_xy is not None:
            line, = ax.plot(
                critical_xy[0],
                critical_xy[1],
                'ko', markersize=10, label='Critical Point'
            )
            data_lines.append(line)

        ax.set_xlabel('Temperature (C)')
        ax.set_ylabel('Pressure (bar)')
        ax.set_title('Phase Envelope')
        ax.legend()
        self._apply_axes_theme(ax)

        # Hover tooltips on bubble, dew, and critical-point artists.
        self._attach_hover_tooltips(
            data_lines,
            x_label="T",
            x_unit="\u00b0C",
            x_precision=2,
        )

        self.figure.tight_layout()

    def _plot_tbp(self, result: TBPExperimentResult) -> None:
        """Plot cumulative TBP assay curves across the entered cut sequence."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        labels = [cut.name for cut in result.cuts]
        x = list(range(len(result.cuts)))
        cumulative_mole_percent = [cut.cumulative_mole_fraction * 100.0 for cut in result.cuts]
        cumulative_mass_percent = [cut.cumulative_mass_fraction * 100.0 for cut in result.cuts]

        ax.plot(x, cumulative_mole_percent, color="#2563eb", marker="o", linewidth=2, label="Cum. Mole %")
        ax.plot(x, cumulative_mass_percent, color="#dc2626", marker="s", linewidth=2, label="Cum. Mass %")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", rotation_mode="anchor")
        ax.set_xlabel("TBP Cut")
        ax.set_ylabel("Cumulative Yield (%)")
        ax.set_title("TBP Assay Summary")
        ax.set_ylim(0.0, 100.0)
        boiling_points_k = [cut.boiling_point_k for cut in result.cuts]
        if any(value is not None for value in boiling_points_k):
            tb_ax = ax.twinx()
            tb_ax.set_facecolor(PLOT_CANVAS_COLOR)
            tb_x = [idx for idx, value in enumerate(boiling_points_k) if value is not None]
            tb_y = [value for value in boiling_points_k if value is not None]
            tb_ax.plot(
                tb_x,
                tb_y,
                color="#f59e0b",
                marker="^",
                linewidth=1.8,
                linestyle="--",
                label="Tb (K)",
            )
            tb_ax.set_ylabel("Boiling Point (K)")
            tb_ax.tick_params(axis="y", colors=PLOT_TEXT_COLOR)
            tb_ax.yaxis.label.set_color(PLOT_TEXT_COLOR)
            handles, labels_text = ax.get_legend_handles_labels()
            tb_handles, tb_labels = tb_ax.get_legend_handles_labels()
            ax.legend(handles + tb_handles, labels_text + tb_labels)
        else:
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
            set(result.display_liquid_composition)
            | set(result.display_vapor_composition)
        )
        display_labels = [self._component_display_label(component) for component in components]
        x = list(range(len(components)))
        width = 0.35

        liquid_vals = [result.display_liquid_composition.get(c, 0.0) for c in components]
        vapor_vals = [result.display_vapor_composition.get(c, 0.0) for c in components]

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
        self._set_mole_fraction_axis(ax)
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
        """Plot the selected CCE pressure-series."""
        pressure_unit, temperature_unit = self._cce_plot_units()
        pressures = [pressure_from_pa(s.pressure_pa, pressure_unit) for s in result.steps]
        self._plot_selected_pressure_series(
            pressures=pressures,
            specs=self._current_series_specs(),
            pressure_unit=pressure_unit,
            title=f"CCE Trends at {_format_temperature(result.temperature_k, temperature_unit, precision=1)}",
            reference_pressure=(
                None
                if result.saturation_pressure_pa is None
                else pressure_from_pa(result.saturation_pressure_pa, pressure_unit)
            ),
            reference_label=(
                None
                if result.saturation_pressure_pa is None
                else f"Psat = {pressure_from_pa(result.saturation_pressure_pa, pressure_unit):.2f} {pressure_unit.value}"
            ),
        )

    def _plot_dl(self, result: DLResult) -> None:
        """Plot the selected DL pressure-series."""
        pressure_unit, temperature_unit = self._dl_plot_units()
        pressures = [pressure_from_pa(s.pressure_pa, pressure_unit) for s in result.steps]
        self._plot_selected_pressure_series(
            pressures=pressures,
            specs=self._current_series_specs(),
            pressure_unit=pressure_unit,
            title=(
                f"Differential Liberation at "
                f"{_format_temperature(result.temperature_k, temperature_unit, precision=1)}"
            ),
        )

    def _plot_cvd(self, result: CVDResult) -> None:
        """Plot the selected CVD pressure-series."""
        pressures = [s.pressure_pa / 1e5 for s in result.steps]
        self._plot_selected_pressure_series(
            pressures=pressures,
            specs=self._current_series_specs(),
            pressure_unit=PressureUnit.BAR,
            title=f"CVD Trends at {result.temperature_k - 273.15:.1f} {_format_temperature_unit(TemperatureUnit.C)}",
            reference_pressure=result.dew_pressure_pa / 1e5,
            reference_label=f"Pd = {result.dew_pressure_pa / 1e5:.2f} bar",
        )

    def _plot_swelling(self, result: SwellingTestResult) -> None:
        """Plot swelling-test trends against enrichment rather than pressure."""
        pressure_unit, temperature_unit = self._swelling_plot_units()
        _ = pressure_unit
        enrichment_steps = [step.added_gas_moles_per_mole_oil for step in result.steps]
        self._plot_selected_enrichment_series(
            enrichment_steps=enrichment_steps,
            specs=self._current_series_specs(),
            title=(
                "Swelling Test at "
                f"{_format_temperature(result.temperature_k, temperature_unit, precision=1)}"
            ),
        )

    def _plot_separator(self, result: SeparatorResult) -> None:
        """Plot the selected separator stage series against stage pressure."""
        pressures = [stage.pressure_pa / 1e5 for stage in result.stages]
        self._plot_selected_pressure_series(
            pressures=pressures,
            specs=self._current_series_specs(),
            pressure_unit=PressureUnit.BAR,
            title="Separator Trends",
        )

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
