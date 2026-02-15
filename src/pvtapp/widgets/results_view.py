"""Results display widgets with tables and plots.

Provides tabular and graphical display of calculation results
with export capabilities.
"""

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
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
    PhaseEnvelopeResult,
    CCEResult,
    pressure_from_pa,
    temperature_from_k,
    PressureUnit,
    TemperatureUnit,
)


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
        elif result.phase_envelope_result:
            self._display_phase_envelope(result.phase_envelope_result)
        elif result.cce_result:
            self._display_cce(result.cce_result)
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

    def _display_cce(self, result: CCEResult) -> None:
        """Display CCE results."""
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

        # Import matplotlib with Qt backend
        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self.figure = Figure(figsize=(8, 6), dpi=100)
            self.canvas = FigureCanvasQTAgg(self.figure)
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

    def clear(self) -> None:
        """Clear the plot."""
        self._current_result = None
        if self._matplotlib_available:
            self.figure.clear()
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

        if result.pt_flash_result:
            self._plot_pt_flash(result.pt_flash_result)
        elif result.phase_envelope_result:
            self._plot_phase_envelope(result.phase_envelope_result)
        elif result.cce_result:
            self._plot_cce(result.cce_result)

        self.canvas.draw()

    def _plot_pt_flash(self, result: PTFlashResult) -> None:
        """Plot PT flash results (composition bar chart)."""
        ax = self.figure.add_subplot(111)

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
        ax.grid(True, alpha=0.3)

        self.figure.tight_layout()

    def _plot_phase_envelope(self, result: PhaseEnvelopeResult) -> None:
        """Plot phase envelope."""
        ax = self.figure.add_subplot(111)

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
        ax.grid(True, alpha=0.3)

        self.figure.tight_layout()

    def _plot_cce(self, result: CCEResult) -> None:
        """Plot CCE results."""
        ax = self.figure.add_subplot(111)

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
        ax.grid(True, alpha=0.3)
        ax.invert_xaxis()  # Pressure decreases during CCE

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
