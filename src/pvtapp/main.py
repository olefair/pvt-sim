"""PVT Simulator main application window.

Provides the main GUI interface with dockable panels for composition
input, conditions, results, and diagnostics.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import uuid

from PySide6.QtCore import QSettings, Qt, QTimer, Slot
from PySide6.QtGui import QAction, QKeySequence
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
    QSizePolicy,
)

from pvtapp import __version__, __app_name__
from pvtapp.capabilities import GUI_CALCULATION_TYPE_LABELS, is_gui_supported_calculation_type
from pvtapp.plus_fraction_policy import resolve_plus_fraction_entry
from pvtapp.recommendation_policy import format_run_recommendation, recommend_run_setup
from pvtapp.schemas import (
    COMPOSITION_SUM_TOLERANCE,
    RunConfig,
    RunResult,
    RunStatus,
    FluidComposition,
    ComponentEntry,
    CalculationType,
    EOSType,
    PressureUnit,
    SaturationPointConfig,
    TemperatureUnit,
    pressure_from_pa,
    temperature_from_k,
)
from pvtapp.widgets import (
    CompositionInputWidget,
    ConditionsInputWidget,
    ResultsTableWidget,
    ResultsSidebarWidget,
    UnitConverterWidget,
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
from pvtapp.widgets.two_pane_workspace import PANE_MODE_DOUBLE
from pvtapp.workers import CalculationThread
from pvtapp.job_runner import (
    execute_bubble_point,
    list_runs,
    load_run_config,
    load_run_result,
)
from pvtapp.style import (
    DEFAULT_THEME,
    DEFAULT_UI_SCALE,
    THEME_DARK,
    THEME_SLATE,
    UI_SCALE_STEP,
    build_cato_stylesheet,
    clamp_ui_scale,
    scale_metric,
)

from pvtcore.models import load_components

SETTINGS_ORGANIZATION = "PVT-SIM"
UI_SCALE_SETTINGS_KEY = "ui/scale"
UI_THEME_SETTINGS_KEY = "ui/theme"


class PVTSimulatorWindow(QMainWindow):
    """Main application window for PVT Simulator."""

    def __init__(self):
        super().__init__()
        self._current_thread: Optional[CalculationThread] = None
        self._run_history: list[RunResult] = []
        self._ui_scale = DEFAULT_UI_SCALE
        self._theme_mode = DEFAULT_THEME
        self._ui_scale_initialized = False
        self._base_min_window_size = (1400, 900)
        self._base_progress_width = 200
        self._settings = self._create_settings()

        # Component DB (for critical props / BIPs views)
        self._components_db = load_components()

        self._setup_window()
        self._setup_menus()
        self._setup_toolbar()
        self._setup_central_widget()
        self._setup_statusbar()
        self._connect_signals()
        self._ui_scale = self._load_persisted_ui_scale()
        self._theme_mode = self._load_persisted_theme_mode()
        self.workspace.set_theme_mode(self._theme_mode, emit_signal=False)
        self._apply_ui_scale(self._ui_scale, announce=False)

        # Auto-restore the most recent completed run so reopening the app
        # picks up where the user left off. Deferred one event-loop tick
        # so the widgets finish their initial layout pass first (otherwise
        # column-width / row-height math in ResultsTableWidget runs against
        # stale geometry).
        QTimer.singleShot(0, self._restore_last_completed_run)

    def _setup_window(self) -> None:
        """Configure main window properties."""
        self.setWindowTitle(f"{__app_name__} v{__version__}")

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

        self.clear_action = QAction("Clear &Composition", self)
        self.clear_action.triggered.connect(self._clear_composition)
        edit_menu.addAction(self.clear_action)

        self.normalize_action = QAction("&Normalize Feed", self)
        self.normalize_action.triggered.connect(self._normalize_composition)
        edit_menu.addAction(self.normalize_action)

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

        self.recommend_action = QAction("&Recommend Setup", self)
        self.recommend_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self.recommend_action.triggered.connect(self._recommend_setup)
        run_menu.addAction(self.recommend_action)

        self.validate_action = QAction("&Validate Input", self)
        self.validate_action.setShortcut(QKeySequence("Ctrl+Shift+V"))
        self.validate_action.triggered.connect(self._validate_input)
        run_menu.addAction(self.validate_action)

        # View menu
        view_menu = menubar.addMenu("&View")
        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcuts(self._build_zoom_in_shortcuts())
        self.zoom_in_action.triggered.connect(self._zoom_in)
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcuts(self._build_zoom_out_shortcuts())
        self.zoom_out_action.triggered.connect(self._zoom_out)
        view_menu.addAction(self.zoom_out_action)

        self.reset_zoom_action = QAction("&Actual Size", self)
        self.reset_zoom_action.setShortcut(QKeySequence("Ctrl+0"))
        self.reset_zoom_action.triggered.connect(self._reset_zoom)
        view_menu.addAction(self.reset_zoom_action)

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

        self.recommend_btn = QPushButton("Recommend")
        self.recommend_btn.clicked.connect(self._recommend_setup)
        toolbar.addWidget(self.recommend_btn)

        # Validate button
        validate_btn = QPushButton("Validate")
        validate_btn.clicked.connect(self._validate_input)
        toolbar.addWidget(validate_btn)

        toolbar.addSeparator()
        self._toolbar_spacer = QWidget()
        self._toolbar_spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(self._toolbar_spacer)

        self.unit_converter_widget = UnitConverterWidget()
        toolbar.addWidget(self.unit_converter_widget)

    def _setup_central_widget(self) -> None:
        """Create central widget with fixed sidebars and configurable center panes."""

        # Primary inputs (single shared instance, movable between panes)
        self.composition_widget = CompositionInputWidget()
        self.conditions_widget = ConditionsInputWidget()
        self.inputs_panel = InputsPanel(self.composition_widget, self.conditions_widget)

        # Outputs / tools (single shared instances)
        self.results_table = ResultsTableWidget()
        self.results_sidebar = ResultsSidebarWidget(self.results_table)
        self.results_plot = ResultsPlotWidget(view_mode="generic")
        self.diagnostics_widget = DiagnosticsWidget()
        self.text_output_widget = TextOutputWidget()

        # MI-PVT-like tabs as views
        self.critical_props_widget = CriticalPropsWidget(self._components_db)
        self.interaction_params_widget = InteractionParamsWidget(self._components_db)
        self.run_log_widget = RunLogWidget()

        view_specs = [
            ViewSpec("critical_props", "Critical properties"),
            ViewSpec("interaction_params", "Interaction parameters"),
            ViewSpec("log", "Log"),
            ViewSpec("text_output", "Text output"),
            ViewSpec("phase_envelope", "Plot"),
            ViewSpec("diagnostics", "Diagnostics"),
        ]

        view_widgets = {
            "critical_props": self.critical_props_widget,
            "interaction_params": self.interaction_params_widget,
            "log": self.run_log_widget,
            "text_output": self.text_output_widget,
            "phase_envelope": self.results_plot,
            "diagnostics": self.diagnostics_widget,
        }

        self.workspace = TwoPaneWorkspace(
            view_specs=view_specs,
            view_widgets=view_widgets,
            left_default="text_output",
            right_default="phase_envelope",
            fixed_widget=self.inputs_panel,
            fixed_title="Run Inputs",
            fixed_width=360,
            fixed_right_widget=self.results_sidebar,
            fixed_right_title="Results",
            fixed_right_width=420,
            default_pane_mode="single",
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
        self.progress_bar.setMaximumWidth(self._base_progress_width)
        self.progress_bar.setVisible(False)
        statusbar.addPermanentWidget(self.progress_bar)

        self._status_style_reset_timer = QTimer(self)
        self._status_style_reset_timer.setSingleShot(True)
        self._status_style_reset_timer.timeout.connect(
            lambda: self.status_label.setStyleSheet("")
        )
        self._dl_bubble_preview_timer = QTimer(self)
        self._dl_bubble_preview_timer.setSingleShot(True)
        self._dl_bubble_preview_timer.timeout.connect(self._refresh_dl_bubble_pressure_preview)

    def _set_status_message(
        self,
        message: str,
        *,
        color: Optional[str] = None,
        timeout_ms: int = 0,
    ) -> None:
        """Update the bottom status strip with optional transient emphasis."""
        self._status_style_reset_timer.stop()
        self.status_label.setText(message)
        self.status_label.setStyleSheet("" if color is None else f"color: {color};")
        if color is not None and timeout_ms > 0:
            self._status_style_reset_timer.start(timeout_ms)

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        # Validation errors
        self.composition_widget.validation_error.connect(self._show_validation_error)
        self.conditions_widget.validation_error.connect(self._show_validation_error)
        self.conditions_widget.status_hint.connect(self._show_status_hint)
        self.conditions_widget.status_warning.connect(self._show_status_warning)

        # Composition edits drive derived views
        self.composition_widget.composition_edited.connect(self._on_composition_edited)
        self.conditions_widget.conditions_changed.connect(self._sync_characterization_context)
        self._sync_characterization_context()

        # Flipping the bubble/dew pressure-unit combo in the inputs panel
        # re-renders any active saturation result in the newly selected
        # unit without requiring a re-run of the solver.
        self.conditions_widget.saturation_display_unit_changed.connect(
            self.results_table.apply_saturation_display_unit
        )

        # Export requests
        self.results_table.export_requested.connect(self._export_results)
        self.workspace.theme_mode_changed.connect(self._set_theme_mode)
        self.run_log_widget.load_inputs_requested.connect(self._load_saved_run_inputs)
        self.run_log_widget.result_activated.connect(self._on_logged_run_selected)

    @Slot()
    def _on_composition_edited(self) -> None:
        """Invalidate composition-derived previews before refreshing dependent views."""
        self.conditions_widget.clear_dl_bubble_pressure()
        self._update_component_dependent_views()
        self._schedule_dl_bubble_pressure_preview()

    @Slot()
    def _sync_characterization_context(self) -> None:
        """Keep plus-fraction auto-characterization aligned with the active workflow."""
        calc_type = self.conditions_widget.get_calculation_type()
        self.composition_widget.set_calculation_type_context(calc_type)
        self._sync_input_mode_for_calculation_type(calc_type)
        self._schedule_dl_bubble_pressure_preview()

    @staticmethod
    def _calculation_requires_composition(calc_type: CalculationType) -> bool:
        """Return whether the desktop workflow requires the normal feed editor."""
        return calc_type != CalculationType.TBP

    def _sync_input_mode_for_calculation_type(self, calc_type: CalculationType) -> None:
        """Keep the desktop input shell honest for standalone TBP runs."""
        needs_composition = self._calculation_requires_composition(calc_type)
        self.composition_widget.setVisible(needs_composition)
        self.clear_action.setEnabled(needs_composition)
        self.normalize_action.setEnabled(needs_composition)
        self.recommend_action.setEnabled(needs_composition)
        self.recommend_btn.setEnabled(needs_composition)
        self._update_component_dependent_views()

    @property
    def ui_scale(self) -> float:
        """Return the active app UI scale."""
        return self._ui_scale

    def _create_settings(self) -> QSettings:
        """Return the persistent settings store for desktop app preferences."""
        return QSettings(SETTINGS_ORGANIZATION, __app_name__)

    def _load_persisted_ui_scale(self) -> float:
        """Load the saved UI scale, falling back to the desktop default."""
        raw_value = self._settings.value(UI_SCALE_SETTINGS_KEY, DEFAULT_UI_SCALE)
        try:
            return clamp_ui_scale(float(raw_value))
        except (TypeError, ValueError):
            return DEFAULT_UI_SCALE

    def _load_persisted_theme_mode(self) -> str:
        """Load the saved theme mode, defaulting to the canonical dark palette."""
        raw_value = self._settings.value(UI_THEME_SETTINGS_KEY, DEFAULT_THEME)
        return str(raw_value) if raw_value in {THEME_DARK, THEME_SLATE} else DEFAULT_THEME

    def _persist_ui_scale(self) -> None:
        """Persist the current UI scale for the next app launch."""
        self._settings.setValue(UI_SCALE_SETTINGS_KEY, self._ui_scale)
        self._settings.sync()

    def _persist_theme_mode(self) -> None:
        """Persist the current palette selection."""
        self._settings.setValue(UI_THEME_SETTINGS_KEY, self._theme_mode)
        self._settings.sync()

    def _scaled_metric(self, value: int) -> int:
        """Scale window-level fixed metrics relative to the default shell."""
        return scale_metric(value, self._ui_scale, reference_scale=DEFAULT_UI_SCALE)

    @staticmethod
    def _build_zoom_in_shortcuts() -> list[QKeySequence]:
        shortcuts = list(QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomIn))
        for extra in (QKeySequence("Ctrl+="), QKeySequence("Ctrl++")):
            if extra not in shortcuts:
                shortcuts.append(extra)
        return shortcuts

    @staticmethod
    def _build_zoom_out_shortcuts() -> list[QKeySequence]:
        shortcuts = list(QKeySequence.keyBindings(QKeySequence.StandardKey.ZoomOut))
        extra = QKeySequence("Ctrl+-")
        if extra not in shortcuts:
            shortcuts.append(extra)
        return shortcuts

    def _apply_ui_scale(self, scale: float, *, announce: bool) -> None:
        """Apply global UI zoom and refresh fixed-size shell geometry."""
        clamped_scale = clamp_ui_scale(scale)
        previous_scale = self._ui_scale
        self._ui_scale = clamped_scale

        QApplication.instance().setStyleSheet(
            build_cato_stylesheet(scale=clamped_scale, theme=self._theme_mode)
        )

        min_width, min_height = self._base_min_window_size
        self.setMinimumSize(self._scaled_metric(min_width), self._scaled_metric(min_height))
        self.progress_bar.setMaximumWidth(self._scaled_metric(self._base_progress_width))
        self.workspace.apply_ui_scale(clamped_scale, previous_scale=previous_scale)
        self.composition_widget.apply_ui_scale(clamped_scale)
        self.results_sidebar.apply_ui_scale(clamped_scale)
        self.unit_converter_widget.apply_ui_scale(clamped_scale)
        self.diagnostics_widget.apply_ui_scale(clamped_scale)
        if hasattr(self.text_output_widget, "apply_ui_scale"):
            self.text_output_widget.apply_ui_scale(clamped_scale)
        if hasattr(self.run_log_widget, "apply_ui_scale"):
            self.run_log_widget.apply_ui_scale(clamped_scale)
        self.updateGeometry()
        self._persist_ui_scale()
        self._ui_scale_initialized = True

        if announce:
            self._set_status_message(f"Zoom: {int(round(clamped_scale * 100))}%")

    @Slot(str)
    def _set_theme_mode(self, theme: str) -> None:
        """Apply a named palette variant without changing the zoom level."""
        if theme not in {THEME_DARK, THEME_SLATE}:
            return
        self._theme_mode = theme
        QApplication.instance().setStyleSheet(
            build_cato_stylesheet(scale=self._ui_scale, theme=self._theme_mode)
        )
        self._persist_theme_mode()
        self._set_status_message(f"Palette: {'Slate' if theme == THEME_SLATE else 'Dark'}")

    @Slot()
    def _zoom_in(self) -> None:
        """Increase the app UI zoom."""
        self._apply_ui_scale(self._ui_scale + UI_SCALE_STEP, announce=True)

    @Slot()
    def _zoom_out(self) -> None:
        """Decrease the app UI zoom."""
        self._apply_ui_scale(self._ui_scale - UI_SCALE_STEP, announce=True)

    @Slot()
    def _reset_zoom(self) -> None:
        """Restore the app UI zoom to the default baseline."""
        self._apply_ui_scale(DEFAULT_UI_SCALE, announce=True)

    @Slot()
    def _update_component_dependent_views(self) -> None:
        """Update component-dependent panels (critical props / BIPs)."""
        calc_type = self.conditions_widget.get_calculation_type()
        if not self._calculation_requires_composition(calc_type):
            component_ids = []
        else:
            try:
                component_ids = [cid for cid, _frac in self.composition_widget._get_runtime_components() if cid]
            except Exception:
                component_ids = []

        if hasattr(self, "critical_props_widget"):
            self.critical_props_widget.update_components(component_ids)
        if hasattr(self, "interaction_params_widget"):
            self.interaction_params_widget.update_components(component_ids)

    def _build_preview_composition(self) -> Optional[FluidComposition]:
        """Return the current feed when it is valid enough for a silent preview calculation."""
        is_valid, _error = self.composition_widget.validate()
        if not is_valid:
            return None

        components, error = self.composition_widget._resolve_runtime_components()
        if error is not None:
            return None

        entries = [
            ComponentEntry(component_id=raw_id, mole_fraction=frac)
            for raw_id, _canonical_id, frac in components
        ]

        plus_fraction, plus_error = self.composition_widget._get_plus_fraction_entry()
        if plus_error is not None:
            return None

        inline_components = []
        inline_spec, inline_z, inline_error = self.composition_widget._get_inline_component_spec()
        if inline_error is not None:
            return None
        if inline_spec is not None and inline_z is not None:
            entries.append(ComponentEntry(component_id=inline_spec.component_id, mole_fraction=inline_z))
            inline_components.append(inline_spec)

        try:
            return FluidComposition(
                components=entries,
                plus_fraction=plus_fraction,
                inline_components=inline_components,
            )
        except Exception:
            return None

    def _schedule_dl_bubble_pressure_preview(self) -> None:
        """Debounce the DL bubble-pressure preview so the field fills after inputs settle."""
        if self.conditions_widget.get_calculation_type() != CalculationType.DL:
            self._dl_bubble_preview_timer.stop()
            return
        if self.conditions_widget.get_dl_bubble_pressure_pa() is not None:
            self._dl_bubble_preview_timer.stop()
            return
        if self._build_preview_composition() is None:
            self._dl_bubble_preview_timer.stop()
            return
        self._dl_bubble_preview_timer.start(250)

    @Slot()
    def _refresh_dl_bubble_pressure_preview(self) -> None:
        """Fill the DL bubble-pressure field from the active feed/temperature when possible."""
        if self.conditions_widget.get_calculation_type() != CalculationType.DL:
            return
        if self.conditions_widget.get_dl_bubble_pressure_pa() is not None:
            return

        composition = self._build_preview_composition()
        if composition is None:
            return

        try:
            bubble_pressure_pa = self._derive_dl_bubble_pressure_pa(
                composition,
                self.conditions_widget.get_eos_type(),
                self.conditions_widget.get_solver_settings(),
            )
        except Exception:
            return

        if (
            self.conditions_widget.get_calculation_type() == CalculationType.DL
            and self.conditions_widget.get_dl_bubble_pressure_pa() is None
        ):
            self.conditions_widget.set_dl_bubble_pressure_pa(bubble_pressure_pa)

    def _derive_dl_bubble_pressure_pa(
        self,
        composition: FluidComposition,
        eos_type: EOSType,
        solver_settings,
    ) -> float:
        """Calculate the DL bubble pressure from the active feed and DL temperature."""
        runtime_composition = composition
        plus_fraction = composition.plus_fraction
        if plus_fraction is not None:
            resolved_plus = resolve_plus_fraction_entry(
                composition.components,
                plus_fraction,
                CalculationType.DL,
            )
            if resolved_plus != plus_fraction:
                runtime_composition = composition.model_copy(update={"plus_fraction": resolved_plus})

        preview_config = RunConfig(
            run_id="dl-autopb",
            run_name="dl_auto_bubble",
            calculation_type=CalculationType.BUBBLE_POINT,
            eos_type=eos_type,
            composition=runtime_composition,
            bubble_point_config=SaturationPointConfig(
                temperature_k=self.conditions_widget.get_dl_temperature_k(),
            ),
            solver_settings=solver_settings,
        )
        return float(execute_bubble_point(preview_config).pressure_pa)

    def _reset_composition_inputs_silently(self) -> None:
        """Clear the composition editor without prompting when a non-feed workflow is loaded."""
        self.composition_widget.table.setRowCount(0)
        if hasattr(self.composition_widget, "_reset_heavy_inputs"):
            self.composition_widget._reset_heavy_inputs()
        if hasattr(self.composition_widget, "_sync_table_height"):
            self.composition_widget._sync_table_height()
        if hasattr(self.composition_widget, "_update_sum"):
            self.composition_widget._update_sum()
        if hasattr(self.composition_widget, "composition_edited"):
            self.composition_widget.composition_edited.emit()

    def _offer_feed_normalization_if_needed(self) -> bool:
        """Offer to normalize the entered feed instead of failing immediately."""
        if not self._calculation_requires_composition(self.conditions_widget.get_calculation_type()):
            return True
        total = self.composition_widget._get_sum()
        if total <= 0.0 or abs(total - 1.0) <= COMPOSITION_SUM_TOLERANCE:
            return True

        reply = QMessageBox.question(
            self,
            "Normalize Feed",
            (
                f"The current feed totals {total:.8f}, not 1.0.\n\n"
                "Normalize the feed in the GUI and continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return False

        self.composition_widget._normalize()
        return True

    def _build_config(self) -> Optional[RunConfig]:
        """Build RunConfig from current input state.

        Returns:
            RunConfig if valid, None otherwise
        """
        # Get calculation type and settings
        calc_type = self.conditions_widget.get_calculation_type()
        eos_type = self.conditions_widget.get_eos_type()
        solver_settings = self.conditions_widget.get_solver_settings()

        # Build config based on calculation type
        config_kwargs = {
            "run_id": str(uuid.uuid4())[:8],
            "run_name": f"{calc_type.value}_{datetime.now().strftime('%H%M%S')}",
            "calculation_type": calc_type,
            "eos_type": eos_type,
            "solver_settings": solver_settings,
        }

        if self._calculation_requires_composition(calc_type):
            if not self._offer_feed_normalization_if_needed():
                return None

            composition = self.composition_widget.get_composition()
            if composition is None:
                return None
            config_kwargs["composition"] = composition

        # Add calculation-specific config
        if calc_type == CalculationType.PT_FLASH:
            pt_config = self.conditions_widget.get_pt_flash_config()
            if pt_config is None:
                return None
            config_kwargs["pt_flash_config"] = pt_config

        elif calc_type == CalculationType.STABILITY_ANALYSIS:
            stability_config = self.conditions_widget.get_stability_analysis_config()
            if stability_config is None:
                return None
            config_kwargs["stability_analysis_config"] = stability_config

        elif calc_type == CalculationType.BUBBLE_POINT:
            bubble_config = self.conditions_widget.get_bubble_point_config()
            if bubble_config is None:
                return None
            config_kwargs["bubble_point_config"] = bubble_config

        elif calc_type == CalculationType.DEW_POINT:
            dew_config = self.conditions_widget.get_dew_point_config()
            if dew_config is None:
                return None
            config_kwargs["dew_point_config"] = dew_config

        elif calc_type == CalculationType.PHASE_ENVELOPE:
            env_config = self.conditions_widget.get_phase_envelope_config()
            if env_config is None:
                return None
            config_kwargs["phase_envelope_config"] = env_config

        elif calc_type == CalculationType.TBP:
            tbp_config = self.conditions_widget.get_tbp_config()
            if tbp_config is None:
                return None
            config_kwargs["tbp_config"] = tbp_config

        elif calc_type == CalculationType.CCE:
            cce_config = self.conditions_widget.get_cce_config()
            if cce_config is None:
                return None
            config_kwargs["cce_config"] = cce_config

        elif calc_type == CalculationType.DL:
            assert composition is not None
            bubble_pressure_pa = self.conditions_widget.get_dl_bubble_pressure_pa()
            if bubble_pressure_pa is None:
                try:
                    bubble_pressure_pa = self._derive_dl_bubble_pressure_pa(
                        composition,
                        eos_type,
                        solver_settings,
                    )
                except Exception as e:
                    self._show_validation_error(str(e))
                    return None
                self.conditions_widget.set_dl_bubble_pressure_pa(bubble_pressure_pa)
            dl_config = self.conditions_widget.get_dl_config()
            if dl_config is None:
                return None
            config_kwargs["dl_config"] = dl_config

        elif calc_type == CalculationType.CVD:
            cvd_config = self.conditions_widget.get_cvd_config()
            if cvd_config is None:
                return None
            config_kwargs["cvd_config"] = cvd_config

        elif calc_type == CalculationType.SWELLING_TEST:
            swelling_config = self.conditions_widget.get_swelling_test_config()
            if swelling_config is None:
                return None
            config_kwargs["swelling_test_config"] = swelling_config

        elif calc_type == CalculationType.SEPARATOR:
            separator_config = self.conditions_widget.get_separator_config()
            if separator_config is None:
                return None
            config_kwargs["separator_config"] = separator_config

        else:
            self._show_validation_error(
                f"Calculation type '{calc_type.value}' is not currently exposed in the desktop GUI"
            )
            return None

        try:
            config = RunConfig(**config_kwargs)
            if config.composition is None:
                return config

            plus_fraction = config.composition.plus_fraction
            if plus_fraction is None:
                return config

            resolved_plus = resolve_plus_fraction_entry(
                config.composition.components,
                plus_fraction,
                config.calculation_type,
            )
            if resolved_plus == plus_fraction:
                return config

            resolved_composition = config.composition.model_copy(update={"plus_fraction": resolved_plus})
            return config.model_copy(update={"composition": resolved_composition})
        except Exception as e:
            self._show_validation_error(str(e))
            return None

    def _load_run_config_into_inputs(
        self,
        config: RunConfig,
        *,
        status_message: Optional[str] = None,
    ) -> None:
        """Populate GUI inputs from a validated run configuration."""
        if not is_gui_supported_calculation_type(config.calculation_type):
            raise ValueError(
                f"Calculation type '{config.calculation_type.value}' is supported in the runtime/artifact layer "
                "but is not currently editable from the desktop input panels."
            )
        if config.composition is None:
            self._reset_composition_inputs_silently()
        else:
            self.composition_widget.set_composition(config.composition)
        self.conditions_widget.load_from_run_config(config)
        self._sync_characterization_context()
        if status_message is not None:
            self._set_status_message(status_message)

    def _set_results_pane_title(self, title: str) -> None:
        """Update the fixed results-pane title."""
        if self.workspace.results_pane is not None:
            self.workspace.results_pane.set_title(title)

    @staticmethod
    def _results_title_for_config(config: RunConfig) -> str:
        """Return a concise title for the active result surface."""
        calc_title = GUI_CALCULATION_TYPE_LABELS.get(
            config.calculation_type,
            config.calculation_type.value.replace("_", " ").title(),
        )
        return f"{calc_title} Results"

    def _start_calculation(self, config: RunConfig) -> None:
        """Start a calculation thread from an already-built configuration."""
        self._set_running_state(True)
        self._set_results_pane_title(self._results_title_for_config(config))
        self._set_status_message(f"Running {config.calculation_type.value}...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Clear previous results
        self.results_sidebar.clear()
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
            if hasattr(self.composition_widget, "_reset_heavy_inputs"):
                self.composition_widget._reset_heavy_inputs()
            # Keep the sum/status in sync and refresh dependent panels
            if hasattr(self.composition_widget, "_update_sum"):
                self.composition_widget._update_sum()
            if hasattr(self.composition_widget, "composition_edited"):
                self.composition_widget.composition_edited.emit()
            self.results_sidebar.clear()
            self.results_table.clear(clear_captured=True)
            self.results_plot.clear()
            self.diagnostics_widget.clear()
            self.text_output_widget.clear()
            self._set_results_pane_title("Results")
            self._set_status_message("Ready")

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
                self._load_run_config_into_inputs(config, status_message=f"Loaded: {Path(filename).name}")

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

                self._set_status_message(f"Saved: {Path(filename).name}")

            except Exception as e:
                QMessageBox.critical(
                    self, "Save Error",
                    f"Failed to save configuration: {e}"
                )

    @Slot(str)
    def _export_results(self, format: str) -> None:
        """Export results to file."""
        if not self._run_history:
            current_result = self.results_table.current_result
            if current_result is None:
                QMessageBox.warning(
                    self, "No Results",
                    "No results available to export"
                )
                return
            result = current_result
        else:
            result = self.results_table.current_result or self._run_history[-1]

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

        elif format == "excel":
            filename, _ = QFileDialog.getSaveFileName(
                self, "Export Excel", "", "Excel Workbook (*.xlsx)"
            )
            if filename:
                self._export_excel(result, filename)

    def _export_csv(self, result: RunResult, filename: str) -> None:
        """Export result to CSV file."""
        if result.status != RunStatus.COMPLETED:
            QMessageBox.warning(
                self,
                "Export Error",
                "CSV export is only available for completed calculations",
            )
            return

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
                elif result.stability_analysis_result:
                    res = result.stability_analysis_result
                    writer.writerow(["Metric", "Value"])
                    writer.writerow(["Stable", res.stable])
                    writer.writerow(["MinimumTPD", res.tpd_min])
                    writer.writerow(["PhaseRegime", res.phase_regime])
                    writer.writerow(["PhysicalStateHint", res.physical_state_hint])
                    writer.writerow(["PhysicalStateHintBasis", res.physical_state_hint_basis])
                    writer.writerow(["PhysicalStateHintConfidence", res.physical_state_hint_confidence])
                    writer.writerow(["RequestedFeedPhase", res.requested_feed_phase.value])
                    writer.writerow(["ResolvedFeedPhase", res.resolved_feed_phase])
                    writer.writerow(["ReferenceRootUsed", res.reference_root_used])
                    writer.writerow(["LiquidRootZ", res.liquid_root_z])
                    writer.writerow(["VaporRootZ", res.vapor_root_z])
                    writer.writerow(["RootGap", res.root_gap])
                    writer.writerow(["GibbsGap", res.gibbs_gap])
                    writer.writerow(["AverageReducedPressure", res.average_reduced_pressure])
                    writer.writerow(["BubblePressureHintPa", res.bubble_pressure_hint_pa])
                    writer.writerow(["DewPressureHintPa", res.dew_pressure_hint_pa])
                    writer.writerow(["BubbleBoundaryReason", res.bubble_boundary_reason])
                    writer.writerow(["DewBoundaryReason", res.dew_boundary_reason])
                    writer.writerow(["BestUnstableTrial", res.best_unstable_trial_kind])
                    writer.writerow([])

                    components = sorted(
                        set(res.feed_composition)
                        | (
                            set()
                            if res.vapor_like_trial is None
                            else set(res.vapor_like_trial.composition)
                        )
                        | (
                            set()
                            if res.liquid_like_trial is None
                            else set(res.liquid_like_trial.composition)
                        )
                    )
                    writer.writerow(["Component", "Feed_z", "VaporLike", "LiquidLike"])
                    for comp in components:
                        writer.writerow([
                            comp,
                            res.feed_composition.get(comp, 0.0),
                            None if res.vapor_like_trial is None else res.vapor_like_trial.composition.get(comp, 0.0),
                            None if res.liquid_like_trial is None else res.liquid_like_trial.composition.get(comp, 0.0),
                        ])

                    writer.writerow([])
                    writer.writerow(
                        [
                            "Trial",
                            "TPD",
                            "Converged",
                            "EarlyExitUnstable",
                            "Iterations",
                            "TotalIterations",
                            "PhiCalls",
                            "EOSFailures",
                            "BestSeed",
                        ]
                    )
                    for trial_name, trial in (
                        ("vapor_like", res.vapor_like_trial),
                        ("liquid_like", res.liquid_like_trial),
                    ):
                        if trial is None:
                            continue
                        writer.writerow(
                            [
                                trial_name,
                                trial.tpd,
                                trial.converged,
                                trial.early_exit_unstable,
                                trial.iterations,
                                trial.total_iterations,
                                trial.n_phi_calls,
                                trial.n_eos_failures,
                                trial.best_seed.seed_label,
                            ]
                        )
                elif result.bubble_point_result:
                    res = result.bubble_point_result
                    writer.writerow(["Component", "Liquid", "Vapor", "K-value"])
                    for comp in sorted(res.liquid_composition.keys()):
                        writer.writerow([
                            comp,
                            res.liquid_composition.get(comp, 0),
                            res.vapor_composition.get(comp, 0),
                            res.k_values.get(comp, 0),
                        ])
                elif result.dew_point_result:
                    res = result.dew_point_result
                    writer.writerow(["Component", "Liquid", "Vapor", "K-value"])
                    for comp in sorted(res.liquid_composition.keys()):
                        writer.writerow([
                            comp,
                            res.liquid_composition.get(comp, 0),
                            res.vapor_composition.get(comp, 0),
                            res.k_values.get(comp, 0),
                        ])
                # CSV export uses the repo-wide US-petroleum defaults
                # (psia, °F) for every pressure/temperature column, so the
                # file the user gets out of "Export CSV" matches what they
                # see in the results table and the text-output panel.
                elif result.phase_envelope_result:
                    writer.writerow(["Type", "Temperature_F", "Pressure_psia"])
                    for point in result.phase_envelope_result.continuous_curve_points():
                        writer.writerow([
                            point.point_type,
                            temperature_from_k(point.temperature_k, TemperatureUnit.F),
                            pressure_from_pa(point.pressure_pa, PressureUnit.PSIA),
                        ])
                elif result.cce_result:
                    writer.writerow(["Pressure_psia", "RelativeVolume", "LiquidFraction", "VaporFraction", "ZFactor"])
                    for step in result.cce_result.steps:
                        writer.writerow([
                            pressure_from_pa(step.pressure_pa, PressureUnit.PSIA),
                            step.relative_volume,
                            step.liquid_fraction,
                            step.vapor_fraction,
                            step.z_factor,
                        ])
                elif result.dl_result:
                    writer.writerow(
                        [
                            "Pressure_psia",
                            "RsD_scf_STB",
                            "RsDb_scf_STB",
                            "Bo_rb_STB",
                            "Bg_rb_scf",
                            "BtD_rb_STB",
                            "VaporFraction",
                            "LiquidMolesRemaining",
                        ]
                    )
                    for step in result.dl_result.steps:
                        writer.writerow([
                            pressure_from_pa(step.pressure_pa, PressureUnit.PSIA),
                            step.rs_scf_stb,
                            result.dl_result.rsi_scf_stb,
                            step.bo,
                            step.bg_rb_per_scf,
                            step.bt,
                            step.vapor_fraction,
                            step.liquid_moles_remaining,
                        ])
                elif result.cvd_result:
                    writer.writerow(
                        [
                            "Pressure_psia",
                            "LiquidDropout",
                            "GasProduced",
                            "CumulativeGasProduced",
                            "MolesRemaining",
                            "ZTwoPhase",
                            "LiquidDensity_kg_m3",
                            "VaporDensity_kg_m3",
                        ]
                    )
                    for step in result.cvd_result.steps:
                        writer.writerow([
                            pressure_from_pa(step.pressure_pa, PressureUnit.PSIA),
                            step.liquid_dropout,
                            step.gas_produced,
                            step.cumulative_gas_produced,
                            step.moles_remaining,
                            step.z_two_phase,
                            step.liquid_density_kg_per_m3,
                            step.vapor_density_kg_per_m3,
                        ])
                elif result.swelling_test_result:
                    writer.writerow(
                        [
                            "AddedGas_mol_per_mol_oil",
                            "TotalMixture_mol_per_mol_oil",
                            "BubblePressure_psia",
                            "SwellingFactor",
                            "SaturatedLiquidMolarVolume_m3_per_mol",
                            "SaturatedLiquidDensity_kg_m3",
                            "Status",
                            "Message",
                        ]
                    )
                    for step in result.swelling_test_result.steps:
                        writer.writerow(
                            [
                                step.added_gas_moles_per_mole_oil,
                                step.total_mixture_moles_per_mole_oil,
                                None if step.bubble_pressure_pa is None
                                else pressure_from_pa(step.bubble_pressure_pa, PressureUnit.PSIA),
                                step.swelling_factor,
                                step.saturated_liquid_molar_volume_m3_per_mol,
                                step.saturated_liquid_density_kg_per_m3,
                                step.status,
                                step.message,
                            ]
                        )
                elif result.separator_result:
                    writer.writerow(
                        [
                            "Stage",
                            "Pressure_psia",
                            "Temperature_F",
                            "VaporFraction",
                            "LiquidMoles",
                            "VaporMoles",
                            "LiquidDensity_kg_m3",
                            "VaporDensity_kg_m3",
                            "LiquidZ",
                            "VaporZ",
                            "Converged",
                        ]
                    )
                    for stage in result.separator_result.stages:
                        writer.writerow([
                            stage.stage_name,
                            pressure_from_pa(stage.pressure_pa, PressureUnit.PSIA),
                            temperature_from_k(stage.temperature_k, TemperatureUnit.F),
                            stage.vapor_fraction,
                            stage.liquid_moles,
                            stage.vapor_moles,
                            stage.liquid_density_kg_per_m3,
                            stage.vapor_density_kg_per_m3,
                            stage.liquid_z_factor,
                            stage.vapor_z_factor,
                            stage.converged,
                        ])

            self._set_status_message(f"Exported: {Path(filename).name}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _export_json(self, result: RunResult, filename: str) -> None:
        """Export result to JSON file."""
        try:
            import json
            payload = result.model_dump(mode='json')
            if result.phase_envelope_result is not None:
                payload.setdefault("phase_envelope_result", {})
                payload["phase_envelope_result"]["continuous_curve"] = (
                    result.phase_envelope_result.continuous_curve_payload()
                )
            with open(filename, 'w') as f:
                json.dump(payload, f, indent=2, default=str)

            self._set_status_message(f"Exported: {Path(filename).name}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    def _export_excel(self, result: RunResult, filename: str) -> None:
        """Export result to a multi-sheet Excel (.xlsx) workbook.

        Delegates to :mod:`pvtapp.excel_export`, which builds a calc-type
        specific workbook: a "Summary" sheet with run metadata + result
        highlights, plus per-section data sheets (Expansion / Phase
        Densities / Phase Viscosities / Per-Step Compositions, etc.).
        Pressures / temperatures follow the repo-wide US-petroleum
        display units (psia, °F) so the workbook matches what the user
        sees in the GUI tables and the text-output panel.
        """
        if result.status != RunStatus.COMPLETED:
            QMessageBox.warning(
                self,
                "Export Error",
                "Excel export is only available for completed calculations",
            )
            return
        try:
            from pvtapp.excel_export import export_result_to_excel
            export_result_to_excel(result, filename)
            self._set_status_message(f"Exported: {Path(filename).name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export: {e}")

    @Slot()
    def _clear_composition(self) -> None:
        """Clear composition table."""
        if not self._calculation_requires_composition(self.conditions_widget.get_calculation_type()):
            return
        self.composition_widget._clear_all()

    @Slot()
    def _normalize_composition(self) -> None:
        """Normalize composition to sum to 1.0."""
        if not self._calculation_requires_composition(self.conditions_widget.get_calculation_type()):
            return
        self.composition_widget._normalize()

    @Slot()
    def _validate_input(self) -> None:
        """Validate all inputs and show result."""
        calc_type = self.conditions_widget.get_calculation_type()
        if self._calculation_requires_composition(calc_type):
            if not self._offer_feed_normalization_if_needed():
                return

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
    def _recommend_setup(self) -> None:
        """Analyze the current feed and surface advisory workflow/EOS guidance."""
        calc_type = self.conditions_widget.get_calculation_type()
        if not self._calculation_requires_composition(calc_type):
            QMessageBox.information(
                self,
                "Recommendation Unavailable",
                "TBP runs are standalone assay workflows. Feed/EOS setup recommendations apply only to EOS-backed fluid calculations.",
            )
            return

        if not self._offer_feed_normalization_if_needed():
            return

        comp_valid, comp_error = self.composition_widget.validate()
        if not comp_valid:
            QMessageBox.warning(
                self,
                "Recommendation Unavailable",
                f"Composition error: {comp_error}",
            )
            return

        composition = self.composition_widget.get_composition()
        if composition is None:
            QMessageBox.warning(
                self,
                "Recommendation Unavailable",
                "Finish entering the fluid composition before requesting a recommendation.",
            )
            return

        calculation_type = self.conditions_widget.get_calculation_type()
        current_eos = self.conditions_widget.get_eos_type()
        recommendation = recommend_run_setup(
            composition,
            calculation_type,
            current_eos=current_eos,
        )
        QMessageBox.information(
            self,
            "Setup Recommendation",
            format_run_recommendation(recommendation),
        )
        self._set_status_message("Recommendation ready")

    @Slot()
    def _run_calculation(self) -> None:
        """Start calculation in background thread."""
        # Build and validate config
        config = self._build_config()
        if config is None:
            return
        self._start_calculation(config)

    @Slot(str)
    def _load_saved_run_inputs(self, run_dir: str) -> None:
        """Hydrate GUI inputs from a persisted run directory."""
        config = load_run_config(Path(run_dir))
        if config is None:
            QMessageBox.warning(
                self,
                "Load Inputs Failed",
                f"Could not load config.json from saved run:\n\n{run_dir}",
            )
            return

        run_name = config.run_name or config.run_id or Path(run_dir).name
        self._load_run_config_into_inputs(config, status_message=f"Loaded inputs: {run_name}")

    def _restore_last_completed_run(self) -> None:
        """Auto-restore the most recent completed run on app startup.

        Every run is already persisted by the worker to
        ``%LOCALAPPDATA%/PVTSimulator/runs/<timestamp>_<id>/``. On reopen
        we pick the most recent *completed* run (cancelled / failed runs
        are skipped), load its config into the inputs panel, and render
        its result into the right-rail + text-output + plot surfaces so
        the user picks up exactly where they left off.
        Silent on any failure — a first-launch with no saved runs is a
        normal case, not an error.
        """
        try:
            recent = list_runs(limit=10)
        except Exception:
            return

        target = None
        for entry in recent:
            if entry.get("status") == "completed":
                target = entry
                break
        if target is None:
            return

        run_dir = Path(target["path"])
        try:
            config = load_run_config(run_dir)
            result = load_run_result(run_dir)
        except Exception:
            return

        if config is None or result is None:
            return

        try:
            self._load_run_config_into_inputs(
                config, status_message="Restored last run"
            )
        except Exception:
            pass

        try:
            self._set_results_pane_title(self._results_title_for_config(result.config))
            self.results_sidebar.display_cached_result(result)
            self.text_output_widget.display_result(result)
            self.diagnostics_widget.display_result(result)
            self.results_plot.display_result(result)
        except Exception:
            # Any rendering failure leaves the UI clean (inputs restored,
            # results empty) — the user can re-run to repopulate.
            pass

    @Slot(object)
    def _on_logged_run_selected(self, result: Optional[RunResult]) -> None:
        """Render an explicitly activated saved run into the fixed right-side results rail."""
        if result is None:
            self.results_sidebar.clear()
            self._set_results_pane_title("Results")
            return

        self.results_sidebar.display_cached_result(result)
        self._set_results_pane_title(self._results_title_for_config(result.config))

    @Slot()
    def _cancel_calculation(self) -> None:
        """Cancel running calculation."""
        if self._current_thread:
            self._current_thread.cancel()
            self._set_status_message("Cancelling...")

    @Slot(str, str)
    def _on_calculation_started(self, run_id: str, calc_type: str) -> None:
        """Handle calculation started signal."""
        self._set_status_message(f"Running {calc_type}...")

    @Slot(str, int, str)
    def _on_calculation_progress(self, run_id: str, progress: int, message: str) -> None:
        """Handle progress update signal."""
        self.progress_bar.setValue(progress)
        self._set_status_message(message)

    @Slot(object)
    def _on_calculation_finished(self, result: RunResult) -> None:
        """Handle calculation completion signal."""
        self._set_running_state(False)
        self.progress_bar.setVisible(False)
        self._set_results_pane_title(self._results_title_for_config(result.config))

        # Store result
        self._run_history.append(result)

        # Display results
        self.results_sidebar.display_result(result)
        self.results_plot.display_result(result)
        self.diagnostics_widget.display_result(result)
        self.text_output_widget.display_result(result)

        # Refresh log (run folders are persisted by the worker)
        try:
            self.run_log_widget.refresh()
        except Exception:
            pass

        # Phase envelope: show the Plot view (phase_envelope) on the primary center pane.
        if result.status == RunStatus.COMPLETED and result.phase_envelope_result is not None:
            self._show_phase_envelope_plot_pane()

        # Update status
        if result.status == RunStatus.COMPLETED:
            self._set_status_message(
                f"Completed in {result.duration_seconds:.2f}s"
            )
        elif result.status == RunStatus.CANCELLED:
            self._set_status_message("Calculation cancelled")
        else:
            self._set_status_message(f"Calculation failed: {result.error_message}")

    @Slot(str, str)
    def _on_calculation_error(self, run_id: str, error_message: str) -> None:
        """Handle calculation error signal."""
        self._set_running_state(False)
        self.progress_bar.setVisible(False)

        QMessageBox.critical(
            self, "Calculation Error",
            f"Calculation failed:\n\n{error_message}"
        )
        self._set_status_message("Calculation failed")

    def _show_phase_envelope_plot_pane(self) -> None:
        """Focus the primary center pane on Plot (phase envelope) after a completed run.

        Default layout is text on the primary pane and Plot on the secondary. In double
        pane mode, ``_sync_disabled_items`` hides Plot on the primary while the
        secondary shows it, so we must move the secondary off Plot before selecting Plot
        on the primary.
        """
        ws = self.workspace
        if ws.left_pane.current_view_id == "phase_envelope":
            return
        if ws.pane_mode == PANE_MODE_DOUBLE and ws.right_pane.current_view_id == "phase_envelope":
            ws.right_pane.set_current_view("text_output")
        ws.left_pane.set_current_view("phase_envelope")

    def _set_running_state(self, running: bool) -> None:
        """Update UI for running/idle state."""
        self.run_btn.setEnabled(not running)
        self.run_action.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.cancel_action.setEnabled(running)
        self.recommend_btn.setEnabled(not running)
        self.recommend_action.setEnabled(not running)
        self.run_log_widget.set_replay_actions_enabled(not running)

    @Slot(str)
    def _show_validation_error(self, message: str) -> None:
        """Show validation error in status bar."""
        self._set_status_message(
            f"Validation error: {message}",
            color="red",
            timeout_ms=3000,
        )

    @Slot(str)
    def _show_status_hint(self, message: str) -> None:
        """Show a transient non-error reminder in the status bar."""
        self._set_status_message(
            message,
            color="#93c5fd",
            timeout_ms=5000,
        )

    @Slot(str)
    def _show_status_warning(self, message: str) -> None:
        """Show a transient warning in the status bar."""
        self._set_status_message(
            message,
            color="#fbbf24",
            timeout_ms=5000,
        )

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

    window = PVTSimulatorWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
