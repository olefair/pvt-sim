"""PVT Simulator main application window.

Provides the main GUI interface with dockable panels for composition
input, conditions, results, and diagnostics.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QMenuBar,
    QMenu,
    QToolBar,
    QStatusBar,
    QProgressBar,
    QLabel,
    QMessageBox,
    QFileDialog,
    QPushButton,
)

from pvtapp import __version__, __app_name__
from pvtapp.schemas import (
    RunConfig,
    RunResult,
    RunStatus,
    FluidComposition,
    ComponentEntry,
    CalculationType,
)
from pvtapp.widgets import (
    CompositionInputWidget,
    ConditionsInputWidget,
    ResultsTableWidget,
    ResultsPlotWidget,
    DiagnosticsWidget,
    InputsPanel,
    CriticalPropsWidget,
    InteractionParamsWidget,
    TextOutputWidget,
    RunLogWidget,
    TwoPaneWorkspace,
    ViewSpec,
)
from pvtapp.workers import CalculationThread

from pvtcore.models import load_components


class PVTSimulatorWindow(QMainWindow):
    """Main application window for PVT Simulator."""

    def __init__(self):
        super().__init__()
        self._current_thread: Optional[CalculationThread] = None
        self._run_history: list[RunResult] = []

        # Component DB (for critical props / BIPs views)
        self._components_db = load_components()

        self._setup_window()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._connect_signals()

    def _setup_window(self) -> None:
        """Configure main window properties."""
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        # Upscaled default footprint (still resizable)
        self.setMinimumSize(1400, 900)

    def _setup_menus(self) -> None:
        """Create menu bar and menus."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        new_action = QAction("&New Session", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._new_session)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Config...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._open_config)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Config...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._save_config)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("&Export Results")
        export_csv = QAction("As CSV...", self)
        export_csv.triggered.connect(lambda: self._export_results("csv"))
        export_menu.addAction(export_csv)
        export_json = QAction("As JSON...", self)
        export_json.triggered.connect(lambda: self._export_results("json"))
        export_menu.addAction(export_json)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        clear_action = QAction("Clear &Composition", self)
        clear_action.triggered.connect(self._clear_composition)
        edit_menu.addAction(clear_action)

        normalize_action = QAction("&Normalize Composition", self)
        normalize_action.triggered.connect(self._normalize_composition)
        edit_menu.addAction(normalize_action)

        # Run menu
        run_menu = menubar.addMenu("&Run")

        self.run_action = QAction("&Run Calculation", self)
        self.run_action.setShortcut(QKeySequence("F5"))
        self.run_action.triggered.connect(self._run_calculation)
        run_menu.addAction(self.run_action)

        self.cancel_action = QAction("&Cancel", self)
        self.cancel_action.setShortcut(QKeySequence("Escape"))
        self.cancel_action.triggered.connect(self._cancel_calculation)
        self.cancel_action.setEnabled(False)
        run_menu.addAction(self.cancel_action)

        run_menu.addSeparator()

        validate_action = QAction("&Validate Input", self)
        validate_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        validate_action.triggered.connect(self._validate_input)
        run_menu.addAction(validate_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        # Dock widget toggles will be added when docks are created

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        self._view_menu = view_menu

    def _setup_toolbar(self) -> None:
        """Create main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Run button
        self.run_btn = QPushButton("Run")
        self.run_btn.setObjectName("RunButton")
        self.run_btn.clicked.connect(self._run_calculation)
        toolbar.addWidget(self.run_btn)

        # Cancel button
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setObjectName("CancelButton")
        self.cancel_btn.clicked.connect(self._cancel_calculation)
        toolbar.addWidget(self.cancel_btn)

        toolbar.addSeparator()

        # Validate button
        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self._validate_input)
        toolbar.addWidget(validate_btn)

    def _setup_central_widget(self) -> None:
        """Create central widget with two configurable panes."""

        # Primary inputs (single shared instance, movable between panes)
        self.composition_widget = CompositionInputWidget()
        self.conditions_widget = ConditionsInputWidget()
        self.inputs_panel = InputsPanel(self.composition_widget, self.conditions_widget)

        # Outputs / tools (single shared instances)
        self.results_table = ResultsTableWidget()
        self.results_plot = ResultsPlotWidget()
        self.diagnostics_widget = DiagnosticsWidget()
        self.text_output_widget = TextOutputWidget()

        # MI-PVT-like tabs as views
        self.critical_props_widget = CriticalPropsWidget(self._components_db)
        self.interaction_params_widget = InteractionParamsWidget(self._components_db)
        self.run_log_widget = RunLogWidget()

        vapor_placeholder = QLabel("Vapor saturation view is not implemented yet.")
        vapor_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vapor_placeholder.setStyleSheet("color: #9ca3af;")
        self.vapor_saturation_widget = vapor_placeholder

        view_specs = [
            ViewSpec("inputs", "Feeds / Inputs"),
            ViewSpec("critical_props", "Critical prop."),
            ViewSpec("interaction_params", "Interaction para."),
            ViewSpec("log", "Log"),
            ViewSpec("text_output", "Text output"),
            ViewSpec("results_table", "Results table"),
            ViewSpec("phase_envelope", "Phase Envelope"),
            ViewSpec("diagnostics", "Diagnostics"),
            ViewSpec("vapor_saturation", "Vapor saturation"),
        ]

        view_widgets = {
            "inputs": self.inputs_panel,
            "critical_props": self.critical_props_widget,
            "interaction_params": self.interaction_params_widget,
            "log": self.run_log_widget,
            "text_output": self.text_output_widget,
            "results_table": self.results_table,
            "phase_envelope": self.results_plot,
            "diagnostics": self.diagnostics_widget,
            "vapor_saturation": self.vapor_saturation_widget,
        }

        self.workspace = TwoPaneWorkspace(
            view_specs=view_specs,
            view_widgets=view_widgets,
            left_default="inputs",
            right_default="phase_envelope",
        )
        self.setCentralWidget(self.workspace)

        # Seed composition-dependent views
        self._update_component_dependent_views()

    def _setup_dock_widgets(self) -> None:
        """Deprecated: previous dock-based layout removed."""
        return

    def _setup_statusbar(self) -> None:
        """Create status bar with progress indicator."""
        statusbar = self.statusBar()

        # Status label
        self.status_label = QLabel("Ready")
        statusbar.addWidget(self.status_label, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximumWidth(200)
        self.progress_bar.setVisible(False)
        statusbar.addPermanentWidget(self.progress_bar)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        # Validation errors
        self.composition_widget.validation_error.connect(self._show_validation_error)
        self.conditions_widget.validation_error.connect(self._show_validation_error)

        # Composition edits drive derived views
        self.composition_widget.composition_edited.connect(self._update_component_dependent_views)

        # Export requests
        self.results_table.export_requested.connect(self._export_results)

    @Slot()
    def _update_component_dependent_views(self) -> None:
        """Update component-dependent panels (critical props / BIPs)."""
        try:
            component_ids = [cid for cid, _frac in self.composition_widget.get_components() if cid]
        except Exception:
            component_ids = []

        if hasattr(self, "critical_props_widget"):
            self.critical_props_widget.update_components(component_ids)
        if hasattr(self, "interaction_params_widget"):
            self.interaction_params_widget.update_components(component_ids)

    def _build_config(self) -> Optional[RunConfig]:
        """Build RunConfig from current input state.

        Returns:
            RunConfig if valid, None otherwise
        """
        # Get and validate composition
        composition = self.composition_widget.get_composition()
        if composition is None:
            return None

        # Get calculation type and settings
        calc_type = self.conditions_widget.get_calculation_type()
        eos_type = self.conditions_widget.get_eos_type()
        solver_settings = self.conditions_widget.get_solver_settings()

        # Build config based on calculation type
        config_kwargs = {
            "run_id": str(uuid.uuid4())[:8],
            "run_name": f"{calc_type.value}_{datetime.now().strftime('%H%M%S')}",
            "composition": composition,
            "calculation_type": calc_type,
            "eos_type": eos_type,
            "solver_settings": solver_settings,
        }

        # Add calculation-specific config
        if calc_type == CalculationType.PT_FLASH:
            pt_config = self.conditions_widget.get_pt_flash_config()
            if pt_config is None:
                return None
            config_kwargs["pt_flash_config"] = pt_config

        elif calc_type == CalculationType.PHASE_ENVELOPE:
            env_config = self.conditions_widget.get_phase_envelope_config()
            if env_config is None:
                return None
            config_kwargs["phase_envelope_config"] = env_config

        elif calc_type == CalculationType.CCE:
            cce_config = self.conditions_widget.get_cce_config()
            if cce_config is None:
                return None
            config_kwargs["cce_config"] = cce_config

        else:
            self._show_validation_error(
                f"Calculation type '{calc_type.value}' not yet implemented"
            )
            return None

        try:
            return RunConfig(**config_kwargs)
        except Exception as e:
            self._show_validation_error(str(e))
            return None

    # =========================================================================
    # Action handlers
    # =========================================================================

    @Slot()
    def _new_session(self) -> None:
        """Start a new session, clearing all inputs."""
        reply = QMessageBox.question(
            self,
            "New Session",
            "Clear all inputs and results?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.composition_widget.table.setRowCount(0)
            # Keep the sum/status in sync and refresh dependent panels
            if hasattr(self.composition_widget, "_update_sum"):
                self.composition_widget._update_sum()
            if hasattr(self.composition_widget, "composition_edited"):
                self.composition_widget.composition_edited.emit()
            self.results_table.clear()
            self.results_plot.clear()
            self.diagnostics_widget.clear()
            self.text_output_widget.clear()
            self.status_label.setText("Ready")

    @Slot()
    def _open_config(self) -> None:
        """Load configuration from JSON file."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Configuration",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if filename:
            try:
                import json
                with open(filename, 'r') as f:
                    data = json.load(f)

                config = RunConfig.model_validate(data)

                # Load composition
                self.composition_widget.set_composition(config.composition)
                self.conditions_widget.load_from_run_config(config)
                self._update_component_dependent_views()

                self.status_label.setText(f"Loaded: {Path(filename).name}")

            except Exception as e:
                QMessageBox.critical(
                    self, "Load Error",
                    f"Failed to load configuration: {e}"
                )

    @Slot()
    def _save_config(self) -> None:
        """Save current configuration to JSON file."""
        config = self._build_config()
        if config is None:
            QMessageBox.warning(
                self, "Validation Error",
                "Cannot save: current configuration is invalid"
            )
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Configuration",
            "",
            "JSON Files (*.json)",
        )
        if filename:
            try:
                import json
                with open(filename, 'w') as f:
                    json.dump(config.model_dump(mode='json'), f, indent=2, default=str)

                self.status_label.setText(f"Saved: {Path(filename).name}")

            except Exception as e:
                QMessageBox.critical(
                    self, "Save Error",
                    f"Failed to save configuration: {e}"
                )

    @Slot(str)
    def _export_results(self, format: str) -> None:
        """Export results to file."""
        if not self._run_history:
            QMessageBox.warning(
                self, "No Results",
                "No results available to export"
            )
            return

        result = self._run_history[-1]

        if format == "csv":
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export CSV", "", "CSV Files (*.csv)"
            )
            if filename:
                self._export_csv(result, filename)

        elif format == "json":
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export JSON", "", "JSON Files (*.json)"
            )
            if filename:
                self._export_json(result, filename)

    def _export_csv(self, result: RunResult, filename: str) -> None:
        """Export result to CSV file."""
        try:
            import csv

            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)

                if result.pt_flash_result:
                    res = result.pt_flash_result
                    writer.writerow(["Component", "Liquid", "Vapor", "K-value"])
                    for comp in sorted(res.liquid_composition.keys()):
                        writer.writerow([
                            comp,
                            res.liquid_composition.get(comp, 0),
                            res.vapor_composition.get(comp, 0),
                            res.K_values.get(comp, 0),
                        ])

            self.status_label.setText(f"Exported: {Path(filename).name}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _export_json(self, result: RunResult, filename: str) -> None:
        """Export result to JSON file."""
        try:
            import json
            with open(filename, 'w') as f:
                json.dump(result.model_dump(mode='json'), f, indent=2, default=str)

            self.status_label.setText(f"Exported: {Path(filename).name}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    @Slot()
    def _clear_composition(self) -> None:
        """Clear composition table."""
        self.composition_widget._clear_all()

    @Slot()
    def _normalize_composition(self) -> None:
        """Normalize composition to sum to 1.0."""
        self.composition_widget._normalize()

    @Slot()
    def _validate_input(self) -> None:
        """Validate all inputs and show result."""
        # Validate composition
        comp_valid, comp_error = self.composition_widget.validate()
        if not comp_valid:
            QMessageBox.warning(
                self, "Validation Failed",
                f"Composition error: {comp_error}"
            )
            return

        # Validate conditions
        cond_valid, cond_error = self.conditions_widget.validate()
        if not cond_valid:
            QMessageBox.warning(
                self, "Validation Failed",
                f"Conditions error: {cond_error}"
            )
            return

        # Try to build full config
        config = self._build_config()
        if config is None:
            QMessageBox.warning(
                self, "Validation Failed",
                "Configuration is incomplete"
            )
            return

        QMessageBox.information(
            self, "Validation Passed",
            "All inputs are valid. Ready to run calculation."
        )

    @Slot()
    def _run_calculation(self) -> None:
        """Start calculation in background thread."""
        # Build and validate config
        config = self._build_config()
        if config is None:
            return

        # Update UI state
        self._set_running_state(True)
        self.status_label.setText(f"Running {config.calculation_type.value}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Clear previous results
        self.results_table.clear()
        self.results_plot.clear()
        self.diagnostics_widget.clear()
        self.text_output_widget.clear()

        # Create and start worker thread
        self._current_thread = CalculationThread(config)
        self._current_thread.started.connect(self._on_calculation_started)
        self._current_thread.progress.connect(self._on_calculation_progress)
        self._current_thread.finished.connect(self._on_calculation_finished)
        self._current_thread.error.connect(self._on_calculation_error)
        self._current_thread.start()

    @Slot()
    def _cancel_calculation(self) -> None:
        """Cancel running calculation."""
        if self._current_thread:
            self._current_thread.cancel()
            self.status_label.setText("Cancelling...")

    @Slot(str, str)
    def _on_calculation_started(self, run_id: str, calc_type: str) -> None:
        """Handle calculation started signal."""
        self.status_label.setText(f"Running {calc_type}...")

    @Slot(str, int, str)
    def _on_calculation_progress(self, run_id: str, progress: int, message: str) -> None:
        """Handle progress update signal."""
        self.progress_bar.setValue(progress)
        self.status_label.setText(message)

    @Slot(object)
    def _on_calculation_finished(self, result: RunResult) -> None:
        """Handle calculation completion signal."""
        self._set_running_state(False)
        self.progress_bar.setVisible(False)

        # Store result
        self._run_history.append(result)

        # Display results
        self.results_table.display_result(result)
        self.results_plot.display_result(result)
        self.diagnostics_widget.display_result(result)
        self.text_output_widget.display_result(result)

        # Refresh log (run folders are persisted by the worker)
        try:
            self.run_log_widget.refresh()
        except Exception:
            pass

        # Update status
        if result.status == RunStatus.COMPLETED:
            self.status_label.setText(
                f"Completed in {result.duration_seconds:.2f}s"
            )
        elif result.status == RunStatus.CANCELLED:
            self.status_label.setText("Calculation cancelled")
        else:
            self.status_label.setText(f"Calculation failed: {result.error_message}")

    @Slot(str, str)
    def _on_calculation_error(self, run_id: str, error_message: str) -> None:
        """Handle calculation error signal."""
        self._set_running_state(False)
        self.progress_bar.setVisible(False)

        QMessageBox.critical(
            self, "Calculation Error",
            f"Calculation failed:\n\n{error_message}"
        )
        self.status_label.setText("Calculation failed")

    def _set_running_state(self, running: bool) -> None:
        """Update UI for running/idle state."""
        self.run_btn.setEnabled(not running)
        self.run_action.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.cancel_action.setEnabled(running)

    @Slot(str)
    def _show_validation_error(self, message: str) -> None:
        """Show validation error in status bar."""
        self.status_label.setText(f"Validation error: {message}")
        self.status_label.setStyleSheet("color: red;")

        # Reset style after 3 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self.status_label.setStyleSheet(""))

    @Slot()
    def _show_about(self) -> None:
        """Show about dialog."""
        QMessageBox.about(
            self,
            f"About {__app_name__}",
            f"<h3>{__app_name__}</h3>"
            f"<p>Version {__version__}</p>"
            "<p>A production-grade PVT simulator for reservoir fluid "
            "phase behavior analysis.</p>"
            "<p>Built with PySide6 (Qt) and pvtcore engine.</p>"
        )


def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setApplicationVersion(__version__)

    # Set application style
    app.setStyle("Fusion")

    # Apply Cato-like dark theme + slight upscale
    from pvtapp.style import build_cato_dark_stylesheet
    app.setStyleSheet(build_cato_dark_stylesheet(scale=1.10))

    window = PVTSimulatorWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
