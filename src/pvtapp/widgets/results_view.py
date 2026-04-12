"""Results display widgets with tables and plots.

Provides tabular and graphical display of calculation results
with export capabilities.
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QTabWidget,
    QLabel,
    QGroupBox,
    QPushButton,
    QFileDialog,
    QMessageBox,
)

from pvtapp.schemas import (
    RunResult,
    RunStatus,
    PTFlashResult,
    BubblePointResult,
    DewPointResult,
    PhaseEnvelopeResult,
    CCEResult,
    DLResult,
    CVDResult,
    SeparatorResult,
)


PLOT_SURFACE_COLOR = "#0f1a2b"
PLOT_CANVAS_COLOR = PLOT_SURFACE_COLOR
PLOT_TEXT_COLOR = "#e5e7eb"
PLOT_GRID_COLOR = "#223044"
PLOT_LEGEND_FACE_COLOR = "#121f34"


class ResultsTableWidget(QWidget):
    """Widget for displaying calculation results in tabular form.

    Signals:
        export_requested: Emitted when user requests export (format)
    """

    export_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_result: Optional[RunResult] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with run info
        header_layout = QHBoxLayout()
        self.run_id_label = QLabel("No results")
        self.run_id_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(self.run_id_label)

        self.status_label = QLabel("")
        header_layout.addWidget(self.status_label)
        header_layout.addStretch()

        # Export buttons
        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(lambda: self.export_requested.emit("csv"))
        self.export_json_btn = QPushButton("Export JSON")
        self.export_json_btn.clicked.connect(lambda: self.export_requested.emit("json"))
        header_layout.addWidget(self.export_csv_btn)
        header_layout.addWidget(self.export_json_btn)

        layout.addLayout(header_layout)

        # Tab widget for different result views
        self.tabs = QTabWidget()

        # Summary tab
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(2)
        self.summary_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.summary_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.summary_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        self.tabs.addTab(self.summary_table, "Summary")

        # Compositions tab
        self.composition_table = QTableWidget()
        self.tabs.addTab(self.composition_table, "Compositions")

        # Details tab
        self.details_table = QTableWidget()
        self.tabs.addTab(self.details_table, "Details")

        layout.addWidget(self.tabs)

    def clear(self) -> None:
        """Clear all result displays."""
        self._current_result = None
        self.run_id_label.setText("No results")
        self.status_label.setText("")
        self.summary_table.setRowCount(0)
        self.composition_table.setRowCount(0)
        self.details_table.setRowCount(0)

    def display_result(self, result: RunResult) -> None:
        """Display a calculation result.

        Args:
            result: RunResult to display
        """
        self._current_result = result
        self.run_id_label.setText(f"Run: {result.run_name or result.run_id}")

        # Set status with color
        status = result.status
        color_map = {
            RunStatus.COMPLETED: "green",
            RunStatus.FAILED: "red",
            RunStatus.CANCELLED: "orange",
            RunStatus.RUNNING: "blue",
            RunStatus.PENDING: "gray",
        }
        color = color_map.get(status, "black")
        self.status_label.setText(f"Status: {status.value}")
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

    def _display_pt_flash(self, result: PTFlashResult) -> None:
        """Display PT flash results."""
        # Summary table
        summary_data = [
            ("Converged", "Yes" if result.converged else "No"),
            ("Phase State", result.phase.title()),
            ("Vapor Fraction", f"{result.vapor_fraction:.6f}"),
            ("Liquid Fraction", f"{1 - result.vapor_fraction:.6f}"),
            ("Iterations", str(result.diagnostics.iterations)),
            ("Final Residual", f"{result.diagnostics.final_residual:.2e}"),
        ]

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
            self.composition_table.setItem(row, 0, QTableWidgetItem(comp))

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
            self.details_table.setItem(row, 0, QTableWidgetItem(comp))
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
        summary_data = [
            ("Converged", "Yes" if result.converged else "No"),
            (pressure_label, f"{result.pressure_pa / 1e5:.2f} bar"),
            ("Temperature", f"{result.temperature_k - 273.15:.2f} C"),
            (stability_label, "Yes" if stability_value else "No"),
            ("Iterations", str(result.iterations)),
            ("Final Residual", f"{result.residual:.2e}"),
        ]

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
            self.composition_table.setItem(row, 0, QTableWidgetItem(comp))
            self.composition_table.setItem(
                row, 1, QTableWidgetItem(f"{result.liquid_composition.get(comp, 0.0):.6f}")
            )
            self.composition_table.setItem(
                row, 2, QTableWidgetItem(f"{result.vapor_composition.get(comp, 0.0):.6f}")
            )

            self.details_table.setItem(row, 0, QTableWidgetItem(comp))
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
            ("Temperature", f"{result.temperature_k - 273.15:.2f} C"),
            ("Steps", str(len(result.steps))),
        ]

        if result.saturation_pressure_pa:
            summary_data.append((
                "Saturation Pressure",
                f"{result.saturation_pressure_pa / 1e5:.2f} bar"
            ))

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
            ("Temperature", f"{result.temperature_k - 273.15:.2f} C"),
            ("Bubble Pressure", f"{result.bubble_pressure_pa / 1e5:.2f} bar"),
            ("Initial Rs", f"{result.rsi:.4f}"),
            ("Initial Bo", f"{result.boi:.4f}"),
            ("Converged", "Yes" if result.converged else "No"),
            ("Steps", str(len(result.steps))),
        ]

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
            ("Temperature", f"{result.temperature_k - 273.15:.2f} C"),
            ("Dew Pressure", f"{result.dew_pressure_pa / 1e5:.2f} bar"),
            ("Initial Z", f"{result.initial_z:.4f}"),
            ("Steps", str(len(result.steps))),
        ]

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


class ResultsPlotWidget(QWidget):
    """Widget for plotting calculation results.

    Uses matplotlib for high-quality publication-ready plots.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._current_result: Optional[RunResult] = None
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

        if result.pt_flash_result:
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

    def _plot_pt_flash(self, result: PTFlashResult) -> None:
        """Plot PT flash results (composition bar chart)."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        components = sorted(result.liquid_composition.keys())
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
        ax.set_xticklabels(components, rotation=45, ha='right')
        ax.legend()
        self._apply_axes_theme(ax)

        self.figure.tight_layout()

    def _plot_phase_envelope(self, result: PhaseEnvelopeResult) -> None:
        """Plot phase envelope."""
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(PLOT_CANVAS_COLOR)

        # Bubble curve
        if result.bubble_curve:
            temps = [p.temperature_k - 273.15 for p in result.bubble_curve]
            pressures = [p.pressure_pa / 1e5 for p in result.bubble_curve]
            ax.plot(temps, pressures, 'b-', linewidth=2, label='Bubble Point')

        # Dew curve
        if result.dew_curve:
            temps = [p.temperature_k - 273.15 for p in result.dew_curve]
            pressures = [p.pressure_pa / 1e5 for p in result.dew_curve]
            ax.plot(temps, pressures, 'r-', linewidth=2, label='Dew Point')

        # Critical point
        if result.critical_point:
            ax.plot(
                result.critical_point.temperature_k - 273.15,
                result.critical_point.pressure_pa / 1e5,
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
        ax.set_title(f"{title} at {result.pressure_pa / 1e5:.2f} bar")
        ax.set_xticks(x)
        ax.set_xticklabels(components, rotation=45, ha="right")
        ax.legend()
        self._apply_axes_theme(ax)

        self.figure.tight_layout()

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
