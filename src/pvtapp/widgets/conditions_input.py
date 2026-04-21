"""Conditions input widget with units-aware validated fields.

Provides input fields for pressure, temperature, and calculation type
with explicit unit handling and strict validation.
"""

import re
from typing import Optional, Tuple

import numpy as np
from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
    QGroupBox,
    QStackedWidget,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QSizePolicy,
    QToolTip,
)

from pvtapp.schemas import (
    CalculationType,
    EOSType,
    COMPOSITION_SUM_TOLERANCE,
    PhaseEnvelopeTracingMethod,
    PressureUnit,
    TemperatureUnit,
    StabilityFeedPhase,
    RunConfig,
    FluidComposition,
    ComponentEntry,
    PTFlashConfig,
    StabilityAnalysisConfig,
    PhaseEnvelopeConfig,
    TBPConfig,
    CCEConfig,
    SaturationPointConfig,
    DLConfig,
    CVDConfig,
    SwellingTestConfig,
    SeparatorConfig,
    SolverSettings,
    pressure_from_pa,
    temperature_from_k,
    pressure_to_pa,
    temperature_to_k,
    PRESSURE_MIN_PA,
    PRESSURE_MAX_PA,
    TEMPERATURE_MIN_K,
    TEMPERATURE_MAX_K,
)
from pvtapp.capabilities import (
    GUI_CALCULATION_TYPE_LABELS,
    GUI_SUPPORTED_CALCULATION_TYPES,
    GUI_EOS_TYPE_LABELS,
    GUI_SUPPORTED_EOS_TYPES,
    is_gui_supported_calculation_type,
    is_gui_supported_eos_type,
)
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.combo_box import (
    NoWheelComboBox,
    NoWheelDoubleSpinBox,
    NoWheelSpinBox,
)
from pvtcore.models import load_components, resolve_component_id


class ValidatedLineEdit(QLineEdit):
    """Line edit with validation state display."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._valid = True
        self._update_style()

    def set_valid(self, valid: bool) -> None:
        """Set validation state and update style."""
        self._valid = valid
        self._update_style()

    def _update_style(self) -> None:
        """Update border color based on validation state."""
        if self._valid:
            self.setStyleSheet("")
        else:
            self.setStyleSheet("border: 2px solid red;")


class CompactStackedWidget(QStackedWidget):
    """A stacked widget that sizes itself to the currently visible page.

    The default QStackedWidget reports ``heightForWidth`` / ``sizeHint`` as
    the max over *all* children (so the parent layout reserves room for
    the tallest hidden page). For a sidebar that switches between a short
    Phase-Envelope panel and a tall Separator panel, that leaves a 120+
    px band of dead space above the Tolerance/Solver section when a short
    calc is active. PySide does not honour a Python-side override of
    ``heightForWidth`` from QWidgetItem's internal path, so we pin the
    widget's ``maximumHeight`` explicitly from the outside whenever the
    current page changes (see ``ConditionsInputWidget._shrink_config_stack_to_current``).
    """

    def sizeHint(self) -> QSize:
        base = super().sizeHint()
        current = self.currentWidget()
        if current is None:
            return base
        current_hint = current.sizeHint()
        return QSize(max(base.width(), current_hint.width()), current_hint.height())

    def minimumSizeHint(self) -> QSize:
        base = super().minimumSizeHint()
        current = self.currentWidget()
        if current is None:
            return base
        current_hint = current.minimumSizeHint()
        return QSize(max(base.width(), current_hint.width()), current_hint.height())


class ConditionsInputWidget(QWidget):
    """Widget for entering calculation conditions with unit selection.

    Signals:
        conditions_changed: Emitted when valid conditions are entered
        validation_error: Emitted with error message when validation fails
    """

    conditions_changed = Signal()
    validation_error = Signal(str)
    status_hint = Signal(str)
    status_warning = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._components_db = load_components()
        self._focus_tooltip_text_by_widget: dict[QWidget, str] = {}
        self._updating_cce_pressure_points = False
        self._cce_pressure_points_is_auto = True
        self._cce_schedule_hint = (
            "CCE exact pressures are shown high-to-low because constant composition "
            "expansion runs from high pressure to low pressure."
        )
        self._setup_ui()
        self._cce_temperature_unit_value = self._coerce_combo_enum(
            self.cce_temperature_unit.currentData(),
            TemperatureUnit,
        )
        self._cce_pressure_unit_value = self._coerce_combo_enum(
            self.cce_pressure_unit.currentData(),
            PressureUnit,
        )
        self._dl_temperature_unit_value = self._coerce_combo_enum(
            self.dl_temperature_unit.currentData(),
            TemperatureUnit,
        )
        self._dl_pressure_unit_value = self._coerce_combo_enum(
            self.dl_pressure_unit.currentData(),
            PressureUnit,
        )
        self._sync_cce_pressure_affordances()
        self._sync_dl_pressure_affordances()
        self._sync_cce_generated_pressure_points(force=True)
        self._connect_signals()
        self._on_calc_type_changed()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(1)

        # Calculation type selection
        calc_group = QGroupBox("Calculation Type")
        calc_layout = QFormLayout(calc_group)
        self._configure_form_layout(calc_layout)

        self.calc_type_combo = NoWheelComboBox()
        for calc_type in GUI_SUPPORTED_CALCULATION_TYPES:
            self.calc_type_combo.addItem(GUI_CALCULATION_TYPE_LABELS[calc_type], calc_type)
        calc_layout.addRow("Type:", self.calc_type_combo)

        self.eos_combo = NoWheelComboBox()
        for eos in GUI_SUPPORTED_EOS_TYPES:
            self.eos_combo.addItem(GUI_EOS_TYPE_LABELS[eos], eos)
        calc_layout.addRow("EOS:", self.eos_combo)

        layout.addWidget(calc_group)

        # Stacked widget for calculation-specific inputs
        self.config_stack = CompactStackedWidget()
        self.config_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        # PT Flash config
        self.pt_flash_widget = self._create_pt_flash_widget()
        self.config_stack.addWidget(self.pt_flash_widget)

        # Stability-analysis config
        self.stability_widget = self._create_stability_analysis_widget()
        self.config_stack.addWidget(self.stability_widget)

        # Phase Envelope config
        self.phase_env_widget = self._create_phase_envelope_widget()
        self.config_stack.addWidget(self.phase_env_widget)

        # TBP config
        self.tbp_widget = self._create_tbp_widget()
        self.config_stack.addWidget(self.tbp_widget)

        # Bubble-point config
        self.bubble_widget = self._create_bubble_point_widget()
        self.config_stack.addWidget(self.bubble_widget)

        # Dew-point config
        self.dew_widget = self._create_dew_point_widget()
        self.config_stack.addWidget(self.dew_widget)

        # CCE config
        self.cce_widget = self._create_cce_widget()
        self.config_stack.addWidget(self.cce_widget)

        # DL config
        self.dl_widget = self._create_dl_widget()
        self.config_stack.addWidget(self.dl_widget)

        # CVD config
        self.cvd_widget = self._create_cvd_widget()
        self.config_stack.addWidget(self.cvd_widget)

        # Swelling config
        self.swelling_widget = self._create_swelling_widget()
        self.config_stack.addWidget(self.swelling_widget)

        # Separator config
        self.separator_widget = self._create_separator_widget()
        self.config_stack.addWidget(self.separator_widget)

        # Placeholder for other calculation types
        self.placeholder_widget = QLabel("Configuration for this calculation type\ncoming soon...")
        self.placeholder_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_stack.addWidget(self.placeholder_widget)

        layout.addWidget(self.config_stack)

        # Solver settings (always visible in the fixed inputs sidebar)
        self.solver_group = QGroupBox("Tolerance / Solver Settings")
        solver_layout = QFormLayout(self.solver_group)
        self._configure_form_layout(solver_layout)

        self.tolerance_edit = QLineEdit("1e-10")
        self.tolerance_edit.setValidator(QDoubleValidator(1e-15, 1e-1, 15))
        solver_layout.addRow("Tolerance:", self.tolerance_edit)

        self.max_iters_spin = NoWheelSpinBox()
        self.max_iters_spin.setRange(1, 10000)
        self.max_iters_spin.setValue(100)
        solver_layout.addRow("Max Iterations:", self.max_iters_spin)

        layout.addWidget(self.solver_group)

        layout.addStretch()

    @staticmethod
    def _configure_form_layout(layout: QFormLayout) -> None:
        """Tune form rows so they fit the fixed-width sidebar cleanly."""
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(4)

    @staticmethod
    def _configure_unit_row(layout: QHBoxLayout, field: QWidget, unit_widget: QWidget) -> None:
        """Give input/unit rows predictable proportions inside narrow forms."""
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        unit_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        unit_widget.setProperty("sidebar_unit_widget", True)
        if hasattr(unit_widget, "setMaximumWidth"):
            unit_widget.setMaximumWidth(96)
        layout.addWidget(field, 1)
        layout.addWidget(unit_widget, 0)

    @staticmethod
    def _populate_pressure_units(combo: NoWheelComboBox, default_unit: PressureUnit = PressureUnit.PSIA) -> None:
        """Populate a pressure-unit combo with the shared enum order."""
        for unit in PressureUnit:
            combo.addItem(unit.value, unit)
        index = combo.findData(default_unit)
        combo.setCurrentIndex(0 if index < 0 else index)

    @staticmethod
    def _populate_temperature_units(
        combo: NoWheelComboBox,
        default_unit: TemperatureUnit = TemperatureUnit.F,
    ) -> None:
        """Populate a temperature-unit combo with the shared enum order."""
        for unit in TemperatureUnit:
            combo.addItem(unit.value, unit)
        index = combo.findData(default_unit)
        combo.setCurrentIndex(0 if index < 0 else index)

    def _register_focus_tooltip(self, widget: QWidget, text: str) -> None:
        """Show full helper copy when a clipped sidebar field receives focus."""
        widget.setToolTip(text)
        widget.setWhatsThis(text)
        self._focus_tooltip_text_by_widget[widget] = text
        widget.installEventFilter(self)

    def eventFilter(self, watched, event):
        tooltip = self._focus_tooltip_text_by_widget.get(watched)
        if tooltip is not None and event is not None:
            if event.type() == QEvent.Type.FocusIn:
                QToolTip.showText(
                    watched.mapToGlobal(QPoint(0, watched.height())),
                    tooltip,
                    watched,
                )
            elif event.type() == QEvent.Type.MouseButtonPress:
                QToolTip.showText(
                    watched.mapToGlobal(QPoint(0, watched.height())),
                    tooltip,
                    watched,
                )
        return super().eventFilter(watched, event)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale sidebar-only geometry that is not controlled by QSS."""
        scaled_gap = scale_metric(2, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        scaled_row_gap = scale_metric(4, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        scaled_unit_width = scale_metric(96, ui_scale, reference_scale=DEFAULT_UI_SCALE)

        root_layout = self.layout()
        if root_layout is not None:
            root_layout.setSpacing(scaled_gap)

        for form_layout in self.findChildren(QFormLayout):
            form_layout.setHorizontalSpacing(scaled_gap)
            form_layout.setVerticalSpacing(scaled_row_gap)

        for row_layout in self.findChildren(QHBoxLayout):
            row_layout.setSpacing(scaled_row_gap)

        for unit_widget in self.findChildren(QWidget):
            if unit_widget.property("sidebar_unit_widget") and hasattr(unit_widget, "setMaximumWidth"):
                unit_widget.setMaximumWidth(scaled_unit_width)

    def _create_pt_flash_widget(self) -> QWidget:
        """Create PT flash configuration widget."""
        widget = QGroupBox("PT Flash Conditions")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        # Pressure input
        p_layout = QHBoxLayout()
        self.pressure_edit = ValidatedLineEdit()
        self.pressure_edit.setPlaceholderText("Enter pressure")

        self.pressure_unit = NoWheelComboBox()
        for unit in PressureUnit:
            self.pressure_unit.addItem(unit.value, unit)
        self.pressure_unit.setCurrentIndex(3)  # bar
        self._configure_unit_row(p_layout, self.pressure_edit, self.pressure_unit)

        layout.addRow("Pressure:", p_layout)

        # Temperature input
        t_layout = QHBoxLayout()
        self.temperature_edit = ValidatedLineEdit()
        self.temperature_edit.setPlaceholderText("Enter temperature")

        self.temperature_unit = NoWheelComboBox()
        for unit in TemperatureUnit:
            self.temperature_unit.addItem(unit.value, unit)
        self.temperature_unit.setCurrentIndex(2)  # F (US petroleum engineering default)
        self._configure_unit_row(t_layout, self.temperature_edit, self.temperature_unit)

        layout.addRow("Temperature:", t_layout)

        return widget

    def _create_phase_envelope_widget(self) -> QWidget:
        """Create phase envelope configuration widget."""
        widget = QGroupBox("Phase Envelope Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        # Temperature range (default units: F, US petroleum engineering convention).
        t_min_layout = QHBoxLayout()
        self.env_t_min = NoWheelDoubleSpinBox()
        self.env_t_min.setRange(-400, 1200)
        self.env_t_min.setValue(-190.0)  # ~150 K in F
        self.env_t_min.setDecimals(2)
        t_min_layout.addWidget(self.env_t_min)
        t_min_layout.addWidget(QLabel("F"))
        layout.addRow("Min Temperature:", t_min_layout)

        t_max_layout = QHBoxLayout()
        self.env_t_max = NoWheelDoubleSpinBox()
        self.env_t_max.setRange(-400, 1200)
        self.env_t_max.setValue(620.0)  # ~600 K in F
        self.env_t_max.setDecimals(2)
        t_max_layout.addWidget(self.env_t_max)
        t_max_layout.addWidget(QLabel("F"))
        layout.addRow("Max Temperature:", t_max_layout)

        # Number of points
        self.env_n_points = NoWheelSpinBox()
        self.env_n_points.setRange(10, 500)
        self.env_n_points.setValue(50)
        layout.addRow("Number of Points:", self.env_n_points)

        self.env_tracing_method = NoWheelComboBox()
        self.env_tracing_method.addItem(
            "Fixed grid (recommended — fast)",
            PhaseEnvelopeTracingMethod.FIXED_GRID,
        )
        self.env_tracing_method.addItem(
            "Continuation (multi-root / difficult fluids)",
            PhaseEnvelopeTracingMethod.CONTINUATION,
        )
        layout.addRow("Tracer:", self.env_tracing_method)

        return widget

    def _create_stability_analysis_widget(self) -> QWidget:
        """Create standalone Michelsen / TPD stability-analysis widget."""
        widget = QGroupBox("Stability Analysis Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        pressure_layout = QHBoxLayout()
        self.stability_pressure_edit = ValidatedLineEdit()
        self.stability_pressure_edit.setPlaceholderText("Enter pressure")
        self.stability_pressure_unit = NoWheelComboBox()
        self._populate_pressure_units(self.stability_pressure_unit, PressureUnit.PSIA)
        self._configure_unit_row(
            pressure_layout,
            self.stability_pressure_edit,
            self.stability_pressure_unit,
        )
        layout.addRow("Pressure:", pressure_layout)

        temperature_layout = QHBoxLayout()
        self.stability_temperature_edit = ValidatedLineEdit()
        self.stability_temperature_edit.setPlaceholderText("Enter temperature")
        self.stability_temperature_unit = NoWheelComboBox()
        self._populate_temperature_units(self.stability_temperature_unit, TemperatureUnit.F)
        self._configure_unit_row(
            temperature_layout,
            self.stability_temperature_edit,
            self.stability_temperature_unit,
        )
        layout.addRow("Temperature:", temperature_layout)

        self.stability_feed_phase_combo = NoWheelComboBox()
        self.stability_feed_phase_combo.addItem("Auto", StabilityFeedPhase.AUTO)
        self.stability_feed_phase_combo.addItem("Liquid", StabilityFeedPhase.LIQUID)
        self.stability_feed_phase_combo.addItem("Vapor", StabilityFeedPhase.VAPOR)
        layout.addRow("Feed Phase:", self.stability_feed_phase_combo)

        self.stability_use_gdem = QCheckBox("Enable GDEM acceleration")
        self.stability_use_gdem.setChecked(True)
        layout.addRow("Acceleration:", self.stability_use_gdem)

        self.stability_random_trials = NoWheelSpinBox()
        self.stability_random_trials.setRange(0, 12)
        self.stability_random_trials.setValue(0)
        layout.addRow("Random Trials:", self.stability_random_trials)

        self.stability_random_seed = NoWheelSpinBox()
        self.stability_random_seed.setRange(0, 2_147_483_647)
        self.stability_random_seed.setValue(0)
        layout.addRow("Random Seed:", self.stability_random_seed)

        self.stability_max_eos_failures = NoWheelSpinBox()
        self.stability_max_eos_failures.setRange(0, 50)
        self.stability_max_eos_failures.setValue(5)
        layout.addRow("Max EOS Failures:", self.stability_max_eos_failures)

        return widget

    def _create_tbp_widget(self) -> QWidget:
        """Create standalone TBP assay configuration widget."""
        widget = QGroupBox("TBP Settings")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        note = QLabel(
            "Standalone TBP assay. Enter ordered cuts such as C7, C7-C9, C10-C12. "
            "Gaps are allowed; EOS and feed composition are not used for this workflow. "
            "Optional Tb values are in Kelvin."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9ca3af;")
        layout.addWidget(note)

        form_layout = QFormLayout()
        self._configure_form_layout(form_layout)
        self.tbp_cut_start_spin = NoWheelSpinBox()
        self.tbp_cut_start_spin.setRange(1, 200)
        self.tbp_cut_start_spin.setValue(7)
        form_layout.addRow("Cut Start:", self.tbp_cut_start_spin)
        layout.addLayout(form_layout)

        self.tbp_cut_table = QTableWidget(0, 5)
        self.tbp_cut_table.setHorizontalHeaderLabels(["Cut", "z", "MW (g/mol)", "SG", "Tb (K)"])
        self.tbp_cut_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbp_cut_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tbp_cut_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tbp_cut_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tbp_cut_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tbp_cut_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tbp_cut_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tbp_cut_table)

        button_row = QHBoxLayout()
        self.add_tbp_cut_btn = QPushButton("Add Cut")
        self.remove_tbp_cut_btn = QPushButton("Remove Selected")
        button_row.addWidget(self.add_tbp_cut_btn)
        button_row.addWidget(self.remove_tbp_cut_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        return widget

    def _create_saturation_point_widget(
        self,
        *,
        title: str,
        temperature_attr: str,
        guess_enabled_attr: str,
        guess_spin_attr: str,
    ) -> QWidget:
        """Create a bubble/dew point configuration widget."""
        widget = QGroupBox(title)
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        t_layout = QHBoxLayout()
        temperature = ValidatedLineEdit()
        temperature.setPlaceholderText("Enter temperature")
        temperature.setText("100")
        setattr(self, temperature_attr, temperature)

        temperature_unit = NoWheelComboBox()
        for unit in TemperatureUnit:
            temperature_unit.addItem(unit.value, unit)
        temperature_unit.setCurrentIndex(2)  # F (US petroleum engineering default)
        setattr(self, f"{temperature_attr}_unit", temperature_unit)
        self._configure_unit_row(t_layout, temperature, temperature_unit)
        layout.addRow("Temperature:", t_layout)

        guess_enabled = QCheckBox("Use initial pressure guess")
        setattr(self, guess_enabled_attr, guess_enabled)
        guess_enabled.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        layout.addRow("Pressure Guess:", guess_enabled)

        guess_spin_layout = QHBoxLayout()
        guess_spin = ValidatedLineEdit()
        guess_spin.setPlaceholderText("Enter pressure guess")
        guess_spin.setText("100")
        guess_spin.setEnabled(False)
        setattr(self, guess_spin_attr, guess_spin)

        guess_unit = NoWheelComboBox()
        for unit in PressureUnit:
            guess_unit.addItem(unit.value, unit)
        guess_unit.setCurrentIndex(3)  # bar
        guess_unit.setEnabled(False)
        setattr(self, f"{guess_spin_attr}_unit", guess_unit)
        self._configure_unit_row(guess_spin_layout, guess_spin, guess_unit)
        layout.addRow("", guess_spin_layout)

        guess_enabled.toggled.connect(guess_spin.setEnabled)
        guess_enabled.toggled.connect(guess_unit.setEnabled)
        return widget

    def _create_bubble_point_widget(self) -> QWidget:
        """Create bubble-point configuration widget."""
        return self._create_saturation_point_widget(
            title="Bubble-Point Settings",
            temperature_attr="bubble_temperature",
            guess_enabled_attr="bubble_pressure_guess_enabled",
            guess_spin_attr="bubble_pressure_guess",
        )

    def _create_dew_point_widget(self) -> QWidget:
        """Create dew-point configuration widget."""
        return self._create_saturation_point_widget(
            title="Dew-Point Settings",
            temperature_attr="dew_temperature",
            guess_enabled_attr="dew_pressure_guess_enabled",
            guess_spin_attr="dew_pressure_guess",
        )

    def _create_cce_widget(self) -> QWidget:
        """Create CCE configuration widget."""
        widget = QGroupBox("CCE Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        # Temperature
        t_layout = QHBoxLayout()
        self.cce_temperature = NoWheelDoubleSpinBox()
        self.cce_temperature.setRange(-200, 500)
        self.cce_temperature.setValue(200)  # F default (previously 100 C)
        self.cce_temperature.setDecimals(2)
        self.cce_temperature_unit = NoWheelComboBox()
        self._populate_temperature_units(self.cce_temperature_unit, TemperatureUnit.F)
        self._configure_unit_row(t_layout, self.cce_temperature, self.cce_temperature_unit)
        layout.addRow("Temperature:", t_layout)

        # Start pressure
        p_start_layout = QHBoxLayout()
        self.cce_p_start = NoWheelDoubleSpinBox()
        self.cce_p_start.setRange(0.01, 10000)
        self.cce_p_start.setValue(500)
        self.cce_p_start.setDecimals(2)
        self.cce_pressure_unit = NoWheelComboBox()
        self._populate_pressure_units(self.cce_pressure_unit, PressureUnit.PSIA)
        self._configure_unit_row(p_start_layout, self.cce_p_start, self.cce_pressure_unit)
        layout.addRow("Start Pressure:", p_start_layout)

        # End pressure
        p_end_layout = QHBoxLayout()
        self.cce_p_end = NoWheelDoubleSpinBox()
        self.cce_p_end.setRange(0.01, 10000)
        self.cce_p_end.setValue(50)
        self.cce_p_end.setDecimals(2)
        self.cce_p_end_unit = QLabel(PressureUnit.PSIA.value)
        self._configure_unit_row(p_end_layout, self.cce_p_end, self.cce_p_end_unit)
        layout.addRow("End Pressure:", p_end_layout)

        # Number of steps
        self.cce_n_steps = NoWheelSpinBox()
        self.cce_n_steps.setRange(2, 200)
        self.cce_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.cce_n_steps)

        self.cce_pressure_points = QLineEdit()
        self._register_focus_tooltip(self.cce_pressure_points, "")
        layout.addRow("Exact Pressures:", self.cce_pressure_points)

        return widget

    def _create_dl_widget(self) -> QWidget:
        """Create Differential Liberation configuration widget."""
        widget = QGroupBox("Differential Liberation Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        t_layout = QHBoxLayout()
        self.dl_temperature = NoWheelDoubleSpinBox()
        self.dl_temperature.setRange(-200, 500)
        self.dl_temperature.setValue(200)  # F default (previously 100 C)
        self.dl_temperature.setDecimals(2)
        self.dl_temperature_unit = NoWheelComboBox()
        self._populate_temperature_units(self.dl_temperature_unit, TemperatureUnit.F)
        self._configure_unit_row(t_layout, self.dl_temperature, self.dl_temperature_unit)
        layout.addRow("Temperature:", t_layout)

        bubble_layout = QHBoxLayout()
        self.dl_bubble_pressure = NoWheelDoubleSpinBox()
        self.dl_bubble_pressure.setRange(0.0, 10000)
        self.dl_bubble_pressure.setValue(0.0)
        self.dl_bubble_pressure.setDecimals(2)
        self.dl_bubble_pressure.setSpecialValueText("Auto")
        self.dl_bubble_pressure.setReadOnly(True)
        self.dl_bubble_pressure.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._register_focus_tooltip(
            self.dl_bubble_pressure,
            "Auto-calculated from the active fluid composition and temperature when the configuration is built.",
        )
        self.dl_pressure_unit = NoWheelComboBox()
        self._populate_pressure_units(self.dl_pressure_unit, PressureUnit.PSIA)
        self._configure_unit_row(bubble_layout, self.dl_bubble_pressure, self.dl_pressure_unit)
        layout.addRow("Bubble Pressure:", bubble_layout)

        end_layout = QHBoxLayout()
        self.dl_p_end = NoWheelDoubleSpinBox()
        self.dl_p_end.setRange(0.01, 10000)
        self.dl_p_end.setValue(10)
        self.dl_p_end.setDecimals(2)
        self.dl_p_end_unit = QLabel(PressureUnit.PSIA.value)
        self._configure_unit_row(end_layout, self.dl_p_end, self.dl_p_end_unit)
        layout.addRow("End Pressure:", end_layout)

        self.dl_n_steps = NoWheelSpinBox()
        self.dl_n_steps.setRange(2, 200)
        self.dl_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.dl_n_steps)

        self.dl_pressure_points = QLineEdit()
        self._register_focus_tooltip(self.dl_pressure_points, "")
        layout.addRow("Exact Pressures:", self.dl_pressure_points)

        return widget

    def _create_cvd_widget(self) -> QWidget:
        """Create CVD configuration widget."""
        widget = QGroupBox("CVD Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        # Temperature
        t_layout = QHBoxLayout()
        self.cvd_temperature = NoWheelDoubleSpinBox()
        self.cvd_temperature.setRange(-200, 500)
        self.cvd_temperature.setValue(200)  # F default (previously 100 C)
        self.cvd_temperature.setDecimals(2)
        t_layout.addWidget(self.cvd_temperature)
        t_layout.addWidget(QLabel("C"))
        layout.addRow("Temperature:", t_layout)

        # Dew pressure
        p_dew_layout = QHBoxLayout()
        self.cvd_p_dew = NoWheelDoubleSpinBox()
        self.cvd_p_dew.setRange(0.01, 10000)
        self.cvd_p_dew.setValue(300)
        self.cvd_p_dew.setDecimals(2)
        p_dew_layout.addWidget(self.cvd_p_dew)
        p_dew_layout.addWidget(QLabel("bar"))
        layout.addRow("Dew Pressure:", p_dew_layout)

        # End pressure
        p_end_layout = QHBoxLayout()
        self.cvd_p_end = NoWheelDoubleSpinBox()
        self.cvd_p_end.setRange(0.01, 10000)
        self.cvd_p_end.setValue(50)
        self.cvd_p_end.setDecimals(2)
        p_end_layout.addWidget(self.cvd_p_end)
        p_end_layout.addWidget(QLabel("bar"))
        layout.addRow("End Pressure:", p_end_layout)

        # Number of steps
        self.cvd_n_steps = NoWheelSpinBox()
        self.cvd_n_steps.setRange(5, 200)
        self.cvd_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.cvd_n_steps)

        return widget

    def _create_separator_widget(self) -> QWidget:
        """Create separator-train configuration widget."""
        widget = QGroupBox("Separator Settings")
        layout = QVBoxLayout(widget)

        form_layout = QFormLayout()
        self._configure_form_layout(form_layout)

        reservoir_pressure_layout = QHBoxLayout()
        self.separator_reservoir_pressure = NoWheelDoubleSpinBox()
        self.separator_reservoir_pressure.setRange(0.01, 10000)
        self.separator_reservoir_pressure.setValue(300)
        self.separator_reservoir_pressure.setDecimals(2)
        reservoir_pressure_layout.addWidget(self.separator_reservoir_pressure)
        reservoir_pressure_layout.addWidget(QLabel("bar"))
        form_layout.addRow("Reservoir Pressure:", reservoir_pressure_layout)

        reservoir_temperature_layout = QHBoxLayout()
        self.separator_reservoir_temperature = NoWheelDoubleSpinBox()
        self.separator_reservoir_temperature.setRange(-200, 500)
        self.separator_reservoir_temperature.setValue(200)  # F default (previously 100 C)
        self.separator_reservoir_temperature.setDecimals(2)
        reservoir_temperature_layout.addWidget(self.separator_reservoir_temperature)
        reservoir_temperature_layout.addWidget(QLabel("C"))
        form_layout.addRow("Reservoir Temperature:", reservoir_temperature_layout)

        self.separator_include_stock_tank = QCheckBox("Include stock-tank stage")
        self.separator_include_stock_tank.setChecked(True)
        form_layout.addRow("Stock Tank:", self.separator_include_stock_tank)

        layout.addLayout(form_layout)

        stages_label = QLabel("Separator Stages")
        layout.addWidget(stages_label)

        self.separator_stage_table = QTableWidget(0, 3)
        self.separator_stage_table.setHorizontalHeaderLabels(["Name", "Pressure (bar)", "Temperature (C)"])
        self.separator_stage_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.separator_stage_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.separator_stage_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.separator_stage_table)

        button_row = QHBoxLayout()
        self.add_separator_stage_btn = QPushButton("Add Stage")
        self.remove_separator_stage_btn = QPushButton("Remove Selected")
        self.add_separator_stage_btn.clicked.connect(self._add_separator_stage_row)
        self.remove_separator_stage_btn.clicked.connect(self._remove_selected_separator_stage_rows)
        button_row.addWidget(self.add_separator_stage_btn)
        button_row.addWidget(self.remove_separator_stage_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._set_separator_stage_rows(
            [
                {"name": "HP", "pressure_bar": 30.0, "temperature_c": 46.85},
                {"name": "LP", "pressure_bar": 5.0, "temperature_c": 26.85},
            ]
        )
        return widget

    def _create_swelling_widget(self) -> QWidget:
        """Create bounded first-slice swelling-test configuration controls."""
        widget = QGroupBox("Swelling Test Settings")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        note = QLabel(
            "Oil feed comes from the main composition editor. Enter a fixed test "
            "temperature, enrichment schedule, and an explicit injection-gas feed "
            "with resolved component rows."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #9ca3af;")
        layout.addWidget(note)

        form_layout = QFormLayout()
        self._configure_form_layout(form_layout)

        t_layout = QHBoxLayout()
        self.swelling_temperature = NoWheelDoubleSpinBox()
        self.swelling_temperature.setRange(-200, 500)
        self.swelling_temperature.setValue(76.85)
        self.swelling_temperature.setDecimals(2)
        self.swelling_temperature_unit = NoWheelComboBox()
        self._populate_temperature_units(self.swelling_temperature_unit, TemperatureUnit.F)
        self._configure_unit_row(t_layout, self.swelling_temperature, self.swelling_temperature_unit)
        form_layout.addRow("Temperature:", t_layout)

        self.swelling_pressure_unit = NoWheelComboBox()
        self._populate_pressure_units(self.swelling_pressure_unit, PressureUnit.PSIA)
        form_layout.addRow("Pressure Unit:", self.swelling_pressure_unit)

        self.swelling_enrichment_steps = QLineEdit("0.05, 0.10, 0.20, 0.35")
        self._register_focus_tooltip(
            self.swelling_enrichment_steps,
            "Comma- or space-separated gas additions in mol gas per mol initial oil. "
            "The baseline 0.0 row is inserted automatically if omitted.",
        )
        form_layout.addRow("Enrichment Steps:", self.swelling_enrichment_steps)
        layout.addLayout(form_layout)

        gas_label = QLabel("Injection Gas Composition")
        layout.addWidget(gas_label)

        self.swelling_gas_table = QTableWidget(0, 2)
        self.swelling_gas_table.setHorizontalHeaderLabels(["Component ID", "Mole Fraction"])
        self.swelling_gas_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.swelling_gas_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.swelling_gas_table)

        button_row = QHBoxLayout()
        self.add_swelling_gas_row_btn = QPushButton("Add Gas Row")
        self.remove_swelling_gas_row_btn = QPushButton("Remove Selected")
        self.add_swelling_gas_row_btn.clicked.connect(self._add_swelling_gas_row)
        self.remove_swelling_gas_row_btn.clicked.connect(self._remove_selected_swelling_gas_rows)
        button_row.addWidget(self.add_swelling_gas_row_btn)
        button_row.addWidget(self.remove_swelling_gas_row_btn)
        button_row.addStretch()
        layout.addLayout(button_row)

        self._set_swelling_gas_rows(
            [
                {"component_id": "C1", "mole_fraction": 0.85},
                {"component_id": "CO2", "mole_fraction": 0.15},
            ]
        )
        return widget

    def _add_separator_stage_row(
        self,
        *,
        name: str = "",
        pressure_bar: float = 10.0,
        temperature_c: float = 25.0,
    ) -> None:
        """Append a separator-stage row."""
        row = self.separator_stage_table.rowCount()
        self.separator_stage_table.insertRow(row)
        self.separator_stage_table.setItem(row, 0, QTableWidgetItem(name))
        self.separator_stage_table.setItem(row, 1, QTableWidgetItem(f"{pressure_bar:.2f}"))
        self.separator_stage_table.setItem(row, 2, QTableWidgetItem(f"{temperature_c:.2f}"))

    def _remove_selected_separator_stage_rows(self) -> None:
        """Remove selected separator-stage rows."""
        rows = sorted({index.row() for index in self.separator_stage_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.separator_stage_table.removeRow(row)

    def _set_separator_stage_rows(self, stages: list[dict[str, float | str]]) -> None:
        """Replace the separator-stage table contents."""
        self.separator_stage_table.setRowCount(0)
        for stage in stages:
            self._add_separator_stage_row(
                name=str(stage.get("name", "")),
                pressure_bar=float(stage.get("pressure_bar", 10.0)),
                temperature_c=float(stage.get("temperature_c", 25.0)),
            )

    def _add_swelling_gas_row(
        self,
        *,
        component_id: str = "",
        mole_fraction: str = "",
    ) -> None:
        """Append one injection-gas composition row."""
        row = self.swelling_gas_table.rowCount()
        self.swelling_gas_table.insertRow(row)
        self.swelling_gas_table.setItem(row, 0, QTableWidgetItem(component_id))
        self.swelling_gas_table.setItem(row, 1, QTableWidgetItem(mole_fraction))

    def _remove_selected_swelling_gas_rows(self) -> None:
        """Remove selected injection-gas composition rows."""
        rows = sorted({index.row() for index in self.swelling_gas_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.swelling_gas_table.removeRow(row)
        self.conditions_changed.emit()

    def _set_swelling_gas_rows(self, rows: list[dict[str, float | str]]) -> None:
        """Replace the swelling injection-gas table contents."""
        self.swelling_gas_table.blockSignals(True)
        try:
            self.swelling_gas_table.setRowCount(0)
            for row in rows:
                self._add_swelling_gas_row(
                    component_id=str(row.get("component_id", "")),
                    mole_fraction=f"{float(row.get('mole_fraction', 0.0)):.6f}"
                    if "mole_fraction" in row
                    else "",
                )
        finally:
            self.swelling_gas_table.blockSignals(False)

    def _add_tbp_cut_row(
        self,
        *,
        name: str = "",
        z: str = "",
        mw: str = "",
        sg: str = "",
        tb_k: str = "",
    ) -> None:
        """Append a TBP cut row."""
        row = self.tbp_cut_table.rowCount()
        self.tbp_cut_table.insertRow(row)
        self.tbp_cut_table.setItem(row, 0, QTableWidgetItem(name))
        self.tbp_cut_table.setItem(row, 1, QTableWidgetItem(z))
        self.tbp_cut_table.setItem(row, 2, QTableWidgetItem(mw))
        self.tbp_cut_table.setItem(row, 3, QTableWidgetItem(sg))
        self.tbp_cut_table.setItem(row, 4, QTableWidgetItem(tb_k))

    def _remove_selected_tbp_cut_rows(self) -> None:
        """Remove selected TBP cut rows."""
        rows = sorted({index.row() for index in self.tbp_cut_table.selectedIndexes()}, reverse=True)
        for row in rows:
            self.tbp_cut_table.removeRow(row)
        self.conditions_changed.emit()

    def _set_tbp_cut_rows(self, cuts: list[dict[str, float | str]]) -> None:
        """Replace the TBP cut table contents."""
        self.tbp_cut_table.blockSignals(True)
        try:
            self.tbp_cut_table.setRowCount(0)
            for cut in cuts:
                sg_value = cut.get("sg")
                tb_k_value = cut.get("tb_k")
                self._add_tbp_cut_row(
                    name=str(cut.get("name", "")),
                    z=f"{float(cut.get('z', 0.0)):.6f}" if "z" in cut else "",
                    mw=f"{float(cut.get('mw', 0.0)):.6f}" if "mw" in cut else "",
                    sg="" if sg_value in {None, ""} else f"{float(sg_value):.6f}",
                    tb_k="" if tb_k_value in {None, ""} else f"{float(tb_k_value):.6f}",
                )
        finally:
            self.tbp_cut_table.blockSignals(False)

    @staticmethod
    def _coerce_tbp_cut_start_from_name(name: str) -> Optional[int]:
        match = re.fullmatch(r"[cC](\d+)(?:\s*-\s*[cC]?(\d+))?", name.strip())
        if match is None:
            return None
        return int(match.group(1))

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.calc_type_combo.currentIndexChanged.connect(self._on_calc_type_changed)
        self.eos_combo.currentIndexChanged.connect(self._on_eos_changed)
        self.pressure_edit.textChanged.connect(self._validate_pressure)
        self.temperature_edit.textChanged.connect(self._validate_temperature)
        self.stability_pressure_edit.textChanged.connect(self._validate_stability_pressure)
        self.stability_temperature_edit.textChanged.connect(self._validate_stability_temperature)
        self.tbp_cut_start_spin.valueChanged.connect(self._emit_conditions_changed)
        self.tbp_cut_table.itemChanged.connect(self._emit_conditions_changed)
        self.add_tbp_cut_btn.clicked.connect(self._add_tbp_cut_row)
        self.remove_tbp_cut_btn.clicked.connect(self._remove_selected_tbp_cut_rows)
        self.bubble_temperature.textChanged.connect(self._emit_conditions_changed)
        self.dew_temperature.textChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess.textChanged.connect(self._emit_conditions_changed)
        self.dew_pressure_guess.textChanged.connect(self._emit_conditions_changed)
        self.cce_temperature.valueChanged.connect(self._emit_conditions_changed)
        self.cce_p_start.valueChanged.connect(self._on_cce_schedule_inputs_changed)
        self.cce_p_end.valueChanged.connect(self._on_cce_schedule_inputs_changed)
        self.cce_n_steps.valueChanged.connect(self._on_cce_schedule_inputs_changed)
        self.dl_temperature.valueChanged.connect(self._on_dl_temperature_changed)
        self.dl_p_end.valueChanged.connect(self._emit_conditions_changed)
        self.dl_n_steps.valueChanged.connect(self._emit_conditions_changed)
        self.swelling_temperature.valueChanged.connect(self._emit_conditions_changed)
        self.cce_pressure_points.textChanged.connect(self._on_cce_pressure_points_changed)
        self.dl_pressure_points.textChanged.connect(self._emit_conditions_changed)
        self.swelling_enrichment_steps.textChanged.connect(self._emit_conditions_changed)
        self.swelling_gas_table.itemChanged.connect(self._emit_conditions_changed)
        self.bubble_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.dew_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.dew_pressure_guess_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.cce_temperature_unit.currentIndexChanged.connect(self._on_cce_temperature_unit_changed)
        self.cce_pressure_unit.currentIndexChanged.connect(self._on_cce_pressure_unit_changed)
        self.dl_temperature_unit.currentIndexChanged.connect(self._on_dl_temperature_unit_changed)
        self.dl_pressure_unit.currentIndexChanged.connect(self._on_dl_pressure_unit_changed)
        self.swelling_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.swelling_pressure_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess_enabled.toggled.connect(self._emit_conditions_changed)
        self.dew_pressure_guess_enabled.toggled.connect(self._emit_conditions_changed)
        self.stability_pressure_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.stability_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.stability_feed_phase_combo.currentIndexChanged.connect(self._emit_conditions_changed)
        self.stability_use_gdem.toggled.connect(self._emit_conditions_changed)
        self.stability_random_trials.valueChanged.connect(self._emit_conditions_changed)
        self.stability_random_seed.valueChanged.connect(self._emit_conditions_changed)
        self.stability_max_eos_failures.valueChanged.connect(self._emit_conditions_changed)

    def _emit_conditions_changed(self, *_args) -> None:
        """Re-emit input changes from Qt signals that may carry extra arguments."""
        self.conditions_changed.emit()

    def _on_calc_type_changed(self) -> None:
        """Update visible configuration based on calculation type."""
        calc_type = self.calc_type_combo.currentData()

        if calc_type == CalculationType.PT_FLASH:
            self.config_stack.setCurrentWidget(self.pt_flash_widget)
        elif calc_type == CalculationType.STABILITY_ANALYSIS:
            self.config_stack.setCurrentWidget(self.stability_widget)
        elif calc_type == CalculationType.BUBBLE_POINT:
            self.config_stack.setCurrentWidget(self.bubble_widget)
        elif calc_type == CalculationType.DEW_POINT:
            self.config_stack.setCurrentWidget(self.dew_widget)
        elif calc_type == CalculationType.PHASE_ENVELOPE:
            self.config_stack.setCurrentWidget(self.phase_env_widget)
        elif calc_type == CalculationType.TBP:
            self.config_stack.setCurrentWidget(self.tbp_widget)
        elif calc_type == CalculationType.CCE:
            self.config_stack.setCurrentWidget(self.cce_widget)
        elif calc_type == CalculationType.DL:
            self.config_stack.setCurrentWidget(self.dl_widget)
        elif calc_type == CalculationType.CVD:
            self.config_stack.setCurrentWidget(self.cvd_widget)
        elif calc_type == CalculationType.SWELLING_TEST:
            self.config_stack.setCurrentWidget(self.swelling_widget)
        elif calc_type == CalculationType.SEPARATOR:
            self.config_stack.setCurrentWidget(self.separator_widget)
        else:
            self.config_stack.setCurrentWidget(self.placeholder_widget)

        eos_enabled = calc_type != CalculationType.TBP
        self.eos_combo.setEnabled(eos_enabled)
        self.eos_combo.setToolTip(
            "" if eos_enabled else "EOS selection is not used for standalone TBP assay runs."
        )
        self._shrink_config_stack_to_current()
        self.config_stack.updateGeometry()
        self.updateGeometry()
        self.conditions_changed.emit()

    def _shrink_config_stack_to_current(self) -> None:
        """Clamp the config stack's max height to the active page's hint.

        QStackedWidget's default ``heightForWidth`` is the max over every
        child, which leaves a dead vertical band between this stack and
        the solver-settings group below whenever the active calc-specific
        panel is shorter than the tallest one (Separator, Swelling). Pin
        ``setMaximumHeight`` from the current page's ``sizeHint`` so the
        layout packs tightly underneath.
        """
        current = self.config_stack.currentWidget()
        if current is None:
            self.config_stack.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
            return
        current.adjustSize()
        hint = current.sizeHint().height()
        if hint <= 0:
            hint = current.minimumSizeHint().height()
        pad = scale_metric(4, DEFAULT_UI_SCALE, reference_scale=DEFAULT_UI_SCALE)
        self.config_stack.setMaximumHeight(max(hint + pad, 0))

    def _validate_pressure(self) -> bool:
        """Validate pressure input."""
        try:
            value = float(self.pressure_edit.text())
            unit = self._coerce_combo_enum(self.pressure_unit.currentData(), PressureUnit)
            pa = pressure_to_pa(value, unit)

            if pa < PRESSURE_MIN_PA or pa > PRESSURE_MAX_PA:
                self.pressure_edit.set_valid(False)
                return False

            self.pressure_edit.set_valid(True)
            return True
        except (ValueError, TypeError):
            self.pressure_edit.set_valid(False)
            return False

    def _validate_temperature(self) -> bool:
        """Validate temperature input."""
        try:
            value = float(self.temperature_edit.text())
            unit = self._coerce_combo_enum(self.temperature_unit.currentData(), TemperatureUnit)
            k = temperature_to_k(value, unit)

            if k < TEMPERATURE_MIN_K or k > TEMPERATURE_MAX_K:
                self.temperature_edit.set_valid(False)
                return False

            self.temperature_edit.set_valid(True)
            return True
        except (ValueError, TypeError):
            self.temperature_edit.set_valid(False)
            return False

    def _validate_stability_pressure(self) -> bool:
        """Validate standalone stability-analysis pressure input."""
        try:
            value = float(self.stability_pressure_edit.text())
            unit = self._coerce_combo_enum(self.stability_pressure_unit.currentData(), PressureUnit)
            pa = pressure_to_pa(value, unit)

            if pa < PRESSURE_MIN_PA or pa > PRESSURE_MAX_PA:
                self.stability_pressure_edit.set_valid(False)
                return False

            self.stability_pressure_edit.set_valid(True)
            return True
        except (ValueError, TypeError):
            self.stability_pressure_edit.set_valid(False)
            return False

    def _validate_stability_temperature(self) -> bool:
        """Validate standalone stability-analysis temperature input."""
        try:
            value = float(self.stability_temperature_edit.text())
            unit = self._coerce_combo_enum(self.stability_temperature_unit.currentData(), TemperatureUnit)
            k = temperature_to_k(value, unit)

            if k < TEMPERATURE_MIN_K or k > TEMPERATURE_MAX_K:
                self.stability_temperature_edit.set_valid(False)
                return False

            self.stability_temperature_edit.set_valid(True)
            return True
        except (ValueError, TypeError):
            self.stability_temperature_edit.set_valid(False)
            return False

    @staticmethod
    def _coerce_combo_enum(value, enum_type):
        """Normalize Qt combo-box data back into the expected enum type."""
        if isinstance(value, enum_type):
            return value
        return enum_type(value)

    @staticmethod
    def _parse_pressure_points(text: str, unit: PressureUnit) -> Optional[list[float]]:
        """Parse an optional comma/whitespace-delimited pressure list."""
        stripped = text.strip()
        if not stripped:
            return None
        tokens = [token for token in re.split(r"[,\s;]+", stripped) if token]
        return [pressure_to_pa(float(token), unit) for token in tokens]

    @staticmethod
    def _normalize_descending_pressure_points(values_pa: Optional[list[float]]) -> Optional[list[float]]:
        """Sort explicit pressure schedules into descending solver order."""
        if values_pa is None:
            return None
        return sorted(values_pa, reverse=True)

    @staticmethod
    def _format_pressure_points(values_pa: Optional[list[float]], unit: PressureUnit) -> str:
        """Format an optional pressure list in the selected pressure unit."""
        if not values_pa:
            return ""
        return ", ".join(f"{pressure_from_pa(value, unit):.12g}" for value in values_pa)

    def _generated_cce_pressure_points_pa(self) -> list[float]:
        """Return the derived CCE pressure schedule from start/end/steps."""
        unit = self._coerce_combo_enum(self.cce_pressure_unit.currentData(), PressureUnit)
        start_pa = pressure_to_pa(self.cce_p_start.value(), unit)
        end_pa = pressure_to_pa(self.cce_p_end.value(), unit)
        high_pa = max(start_pa, end_pa)
        low_pa = min(start_pa, end_pa)
        return np.linspace(high_pa, low_pa, self.cce_n_steps.value(), dtype=float).tolist()

    def _cce_schedule_is_valid(self) -> bool:
        """Return True when the entered CCE start/end schedule is physically descending."""
        unit = self._coerce_combo_enum(self.cce_pressure_unit.currentData(), PressureUnit)
        start_pa = pressure_to_pa(self.cce_p_start.value(), unit)
        end_pa = pressure_to_pa(self.cce_p_end.value(), unit)
        return start_pa > end_pa

    def _set_cce_pressure_points_text(self, text: str, *, auto_generated: bool) -> None:
        """Set the visible CCE exact-pressure list without marking it as manual."""
        self._updating_cce_pressure_points = True
        try:
            self.cce_pressure_points.setText(text)
        finally:
            self._updating_cce_pressure_points = False
        self._cce_pressure_points_is_auto = auto_generated

    def _sync_cce_generated_pressure_points(self, *, force: bool = False) -> None:
        """Keep the CCE exact-pressure preview aligned with start/end/steps."""
        if not force and not self._cce_pressure_points_is_auto:
            return
        if not self._cce_schedule_is_valid():
            if self._cce_pressure_points_is_auto and self.cce_pressure_points.text().strip():
                self._set_cce_pressure_points_text("", auto_generated=True)
            return
        unit = self._coerce_combo_enum(self.cce_pressure_unit.currentData(), PressureUnit)
        generated_text = self._format_pressure_points(
            self._generated_cce_pressure_points_pa(),
            unit,
        )
        if self.cce_pressure_points.text().strip() != generated_text:
            self._set_cce_pressure_points_text(generated_text, auto_generated=True)
        else:
            self._cce_pressure_points_is_auto = True

    @staticmethod
    def _convert_pressure_spinbox_unit(
        spinbox: NoWheelDoubleSpinBox,
        old_unit: PressureUnit,
        new_unit: PressureUnit,
    ) -> None:
        """Preserve the physical pressure value when the display unit changes."""
        pressure_pa = pressure_to_pa(spinbox.value(), old_unit)
        spinbox.setValue(pressure_from_pa(pressure_pa, new_unit))

    @staticmethod
    def _convert_temperature_spinbox_unit(
        spinbox: NoWheelDoubleSpinBox,
        old_unit: TemperatureUnit,
        new_unit: TemperatureUnit,
    ) -> None:
        """Preserve the physical temperature value when the display unit changes."""
        temperature_k = temperature_to_k(spinbox.value(), old_unit)
        spinbox.setValue(temperature_from_k(temperature_k, new_unit))

    def _convert_pressure_points_text(
        self,
        widget: QLineEdit,
        old_unit: PressureUnit,
        new_unit: PressureUnit,
    ) -> None:
        """Re-render an exact-pressure list when the selected pressure unit changes."""
        try:
            values_pa = self._parse_pressure_points(widget.text(), old_unit)
        except ValueError:
            return
        if values_pa is None:
            return
        widget.setText(self._format_pressure_points(values_pa, new_unit))

    def _set_focus_tooltip_text(self, widget: QWidget, text: str) -> None:
        """Refresh a registered focus tooltip without reinstalling the event filter."""
        widget.setToolTip(text)
        widget.setWhatsThis(text)
        self._focus_tooltip_text_by_widget[widget] = text

    def _sync_cce_pressure_affordances(self) -> None:
        """Keep the CCE pressure labels and helper copy aligned to the chosen unit."""
        unit = self._coerce_combo_enum(self.cce_pressure_unit.currentData(), PressureUnit)
        self.cce_p_end_unit.setText(unit.value)
        self.cce_pressure_points.setPlaceholderText(f"Optional exact pressures ({unit.value})")
        self._set_focus_tooltip_text(
            self.cce_pressure_points,
            (
                f"Optional exact pressures in {unit.value}. "
                "You can enter them in any order."
            ),
        )

    def _sync_dl_pressure_affordances(self) -> None:
        """Keep the DL pressure labels and helper copy aligned to the chosen unit."""
        unit = self._coerce_combo_enum(self.dl_pressure_unit.currentData(), PressureUnit)
        self.dl_p_end_unit.setText(unit.value)
        self.dl_pressure_points.setPlaceholderText(f"Optional exact pressures below bubble ({unit.value})")
        self._set_focus_tooltip_text(
            self.dl_pressure_points,
            (
                f"Optional exact pressures below bubble in {unit.value}. "
                "You can enter them in any order."
            ),
        )

    def _on_cce_temperature_unit_changed(self, *_args) -> None:
        """Convert the visible CCE temperature when the unit selector changes."""
        new_unit = self._coerce_combo_enum(self.cce_temperature_unit.currentData(), TemperatureUnit)
        old_unit = self._cce_temperature_unit_value
        if new_unit != old_unit:
            self._convert_temperature_spinbox_unit(self.cce_temperature, old_unit, new_unit)
            self._cce_temperature_unit_value = new_unit
        self.conditions_changed.emit()

    def _on_cce_pressure_unit_changed(self, *_args) -> None:
        """Convert visible CCE pressures when the unit selector changes."""
        new_unit = self._coerce_combo_enum(self.cce_pressure_unit.currentData(), PressureUnit)
        old_unit = self._cce_pressure_unit_value
        was_auto_generated = self._cce_pressure_points_is_auto
        if new_unit != old_unit:
            self._convert_pressure_spinbox_unit(self.cce_p_start, old_unit, new_unit)
            self._convert_pressure_spinbox_unit(self.cce_p_end, old_unit, new_unit)
            self._convert_pressure_points_text(self.cce_pressure_points, old_unit, new_unit)
            self._cce_pressure_unit_value = new_unit
            self._cce_pressure_points_is_auto = was_auto_generated
        self._sync_cce_pressure_affordances()
        self._sync_cce_generated_pressure_points()
        self.conditions_changed.emit()

    def _on_cce_schedule_inputs_changed(self, *_args) -> None:
        """Refresh the generated CCE exact-pressure preview when schedule inputs change."""
        self._sync_cce_generated_pressure_points()
        if self._cce_schedule_is_valid():
            self.status_hint.emit(self._cce_schedule_hint)
        else:
            self.status_warning.emit(
                "⚠ End pressure must be lower than start pressure for CCE."
            )
        self.conditions_changed.emit()

    def _on_cce_pressure_points_changed(self, *_args) -> None:
        """Track whether the CCE exact-pressure list is generated or user-authored."""
        if not self._updating_cce_pressure_points:
            self._cce_pressure_points_is_auto = not bool(self.cce_pressure_points.text().strip())
            if self._cce_pressure_points_is_auto:
                self._sync_cce_generated_pressure_points(force=True)
        self.conditions_changed.emit()

    def _on_dl_temperature_unit_changed(self, *_args) -> None:
        """Convert the visible DL temperature when the unit selector changes."""
        new_unit = self._coerce_combo_enum(self.dl_temperature_unit.currentData(), TemperatureUnit)
        old_unit = self._dl_temperature_unit_value
        if new_unit != old_unit:
            self._convert_temperature_spinbox_unit(self.dl_temperature, old_unit, new_unit)
            self._dl_temperature_unit_value = new_unit
        self.conditions_changed.emit()

    def _on_dl_temperature_changed(self, *_args) -> None:
        """Invalidate the cached DL bubble-pressure preview when temperature changes."""
        self.clear_dl_bubble_pressure()
        self.conditions_changed.emit()

    def _on_eos_changed(self, *_args) -> None:
        """Invalidate the cached DL bubble-pressure preview when the EOS changes.

        The preview is computed with the currently selected EOS; without this
        reset, switching EOS leaves a stale Pb in the DL panel.
        """
        self.clear_dl_bubble_pressure()
        self.conditions_changed.emit()

    def _on_dl_pressure_unit_changed(self, *_args) -> None:
        """Convert visible DL pressures when the unit selector changes."""
        new_unit = self._coerce_combo_enum(self.dl_pressure_unit.currentData(), PressureUnit)
        old_unit = self._dl_pressure_unit_value
        if new_unit != old_unit:
            self._convert_pressure_spinbox_unit(self.dl_bubble_pressure, old_unit, new_unit)
            self._convert_pressure_spinbox_unit(self.dl_p_end, old_unit, new_unit)
            self._convert_pressure_points_text(self.dl_pressure_points, old_unit, new_unit)
            self._dl_pressure_unit_value = new_unit
        self._sync_dl_pressure_affordances()
        self.conditions_changed.emit()

    def get_dl_temperature_k(self) -> float:
        """Return the current DL temperature in Kelvin."""
        temperature_unit = self._coerce_combo_enum(
            self.dl_temperature_unit.currentData(),
            TemperatureUnit,
        )
        return temperature_to_k(self.dl_temperature.value(), temperature_unit)

    def get_dl_bubble_pressure_pa(self) -> Optional[float]:
        """Return the cached DL bubble pressure in Pa when available."""
        pressure_unit = self._coerce_combo_enum(
            self.dl_pressure_unit.currentData(),
            PressureUnit,
        )
        bubble_value = float(self.dl_bubble_pressure.value())
        if bubble_value <= 0.0:
            return None
        return pressure_to_pa(bubble_value, pressure_unit)

    def set_dl_bubble_pressure_pa(self, pressure_pa: Optional[float]) -> None:
        """Update the display-only DL bubble-pressure preview."""
        pressure_unit = self._coerce_combo_enum(
            self.dl_pressure_unit.currentData(),
            PressureUnit,
        )
        display_value = 0.0 if pressure_pa is None else pressure_from_pa(pressure_pa, pressure_unit)
        self.dl_bubble_pressure.blockSignals(True)
        try:
            self.dl_bubble_pressure.setValue(display_value)
        finally:
            self.dl_bubble_pressure.blockSignals(False)

    def clear_dl_bubble_pressure(self) -> None:
        """Reset the display-only DL bubble-pressure preview to auto mode."""
        self.set_dl_bubble_pressure_pa(None)

    def get_calculation_type(self) -> CalculationType:
        """Get selected calculation type."""
        return self._coerce_combo_enum(self.calc_type_combo.currentData(), CalculationType)

    def get_eos_type(self) -> EOSType:
        """Get selected EOS."""
        return self._coerce_combo_enum(self.eos_combo.currentData(), EOSType)

    def set_calculation_type(self, calc_type: CalculationType) -> None:
        """Set selected calculation type."""
        calc_type = self._coerce_combo_enum(calc_type, CalculationType)
        if not is_gui_supported_calculation_type(calc_type):
            supported = ", ".join(calc.value for calc in GUI_SUPPORTED_CALCULATION_TYPES)
            raise ValueError(
                f"Calculation type '{calc_type.value}' is not currently exposed in the desktop GUI. "
                f"Supported GUI types: {supported}"
            )
        index = self.calc_type_combo.findData(calc_type)
        if index < 0:
            raise ValueError(f"Unsupported calculation type: {calc_type}")
        self.calc_type_combo.setCurrentIndex(index)

    def set_eos_type(self, eos_type: EOSType) -> None:
        """Set selected EOS type."""
        eos_type = self._coerce_combo_enum(eos_type, EOSType)
        if not is_gui_supported_eos_type(eos_type):
            supported = ", ".join(eos.value for eos in GUI_SUPPORTED_EOS_TYPES)
            raise ValueError(
                f"EOS '{eos_type.value}' is not currently exposed in the desktop GUI. "
                f"Supported GUI EOS types: {supported}"
            )
        index = self.eos_combo.findData(eos_type)
        if index < 0:
            raise ValueError(f"Unsupported EOS type: {eos_type}")
        self.eos_combo.setCurrentIndex(index)

    def set_solver_settings(self, solver_settings: SolverSettings) -> None:
        """Set solver settings controls from a model."""
        self.tolerance_edit.setText(f"{solver_settings.tolerance:.6g}")
        self.max_iters_spin.setValue(solver_settings.max_iterations)

    def set_pt_flash_config(self, config: PTFlashConfig) -> None:
        """Load PT flash config into widget controls."""
        pressure_unit = config.pressure_unit
        temperature_unit = config.temperature_unit

        p_index = self.pressure_unit.findData(pressure_unit)
        if p_index >= 0:
            self.pressure_unit.setCurrentIndex(p_index)
        t_index = self.temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.temperature_unit.setCurrentIndex(t_index)

        pressure_value = pressure_from_pa(config.pressure_pa, pressure_unit)
        temperature_value = temperature_from_k(config.temperature_k, temperature_unit)
        self.pressure_edit.setText(f"{pressure_value:.6g}")
        self.temperature_edit.setText(f"{temperature_value:.6g}")

    def set_stability_analysis_config(self, config: StabilityAnalysisConfig) -> None:
        """Load standalone stability-analysis config into widget controls."""
        pressure_unit = config.pressure_unit
        temperature_unit = config.temperature_unit

        p_index = self.stability_pressure_unit.findData(pressure_unit)
        if p_index >= 0:
            self.stability_pressure_unit.setCurrentIndex(p_index)
        t_index = self.stability_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.stability_temperature_unit.setCurrentIndex(t_index)
        phase_index = self.stability_feed_phase_combo.findData(config.feed_phase)
        if phase_index >= 0:
            self.stability_feed_phase_combo.setCurrentIndex(phase_index)

        self.stability_pressure_edit.setText(
            f"{pressure_from_pa(config.pressure_pa, pressure_unit):.6g}"
        )
        self.stability_temperature_edit.setText(
            f"{temperature_from_k(config.temperature_k, temperature_unit):.6g}"
        )
        self.stability_use_gdem.setChecked(config.use_gdem)
        self.stability_random_trials.setValue(config.n_random_trials)
        self.stability_random_seed.setValue(0 if config.random_seed is None else int(config.random_seed))
        self.stability_max_eos_failures.setValue(config.max_eos_failures_per_trial)

    def set_phase_envelope_config(self, config: PhaseEnvelopeConfig) -> None:
        """Load phase-envelope config into widget controls."""
        self.env_t_min.setValue(config.temperature_min_k - 273.15)
        self.env_t_max.setValue(config.temperature_max_k - 273.15)
        self.env_n_points.setValue(config.n_points)
        method_index = self.env_tracing_method.findData(config.tracing_method)
        if method_index >= 0:
            self.env_tracing_method.setCurrentIndex(method_index)

    def set_tbp_config(self, config: TBPConfig) -> None:
        """Load TBP config into widget controls."""
        cut_start = config.cut_start
        if cut_start is None and config.cuts:
            cut_start = self._coerce_tbp_cut_start_from_name(config.cuts[0].name) or 7
        self.tbp_cut_start_spin.setValue(7 if cut_start is None else cut_start)
        self._set_tbp_cut_rows(
            [cut.model_dump(mode="python", exclude_none=True) for cut in config.cuts]
        )

    def set_bubble_point_config(self, config: SaturationPointConfig) -> None:
        """Load bubble-point config into widget controls."""
        temperature_unit = config.temperature_unit
        pressure_unit = config.pressure_unit

        t_index = self.bubble_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.bubble_temperature_unit.setCurrentIndex(t_index)
        p_index = self.bubble_pressure_guess_unit.findData(pressure_unit)
        if p_index >= 0:
            self.bubble_pressure_guess_unit.setCurrentIndex(p_index)

        self.bubble_temperature.setText(
            f"{temperature_from_k(config.temperature_k, temperature_unit):.6g}"
        )
        has_guess = config.pressure_initial_pa is not None
        self.bubble_pressure_guess_enabled.setChecked(has_guess)
        if config.pressure_initial_pa is not None:
            self.bubble_pressure_guess.setText(
                f"{pressure_from_pa(config.pressure_initial_pa, pressure_unit):.6g}"
            )
        else:
            self.bubble_pressure_guess.setText("100")

    def set_dew_point_config(self, config: SaturationPointConfig) -> None:
        """Load dew-point config into widget controls."""
        temperature_unit = config.temperature_unit
        pressure_unit = config.pressure_unit

        t_index = self.dew_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.dew_temperature_unit.setCurrentIndex(t_index)
        p_index = self.dew_pressure_guess_unit.findData(pressure_unit)
        if p_index >= 0:
            self.dew_pressure_guess_unit.setCurrentIndex(p_index)

        self.dew_temperature.setText(
            f"{temperature_from_k(config.temperature_k, temperature_unit):.6g}"
        )
        has_guess = config.pressure_initial_pa is not None
        self.dew_pressure_guess_enabled.setChecked(has_guess)
        if config.pressure_initial_pa is not None:
            self.dew_pressure_guess.setText(
                f"{pressure_from_pa(config.pressure_initial_pa, pressure_unit):.6g}"
            )
        else:
            self.dew_pressure_guess.setText("100")

    def set_cce_config(self, config: CCEConfig) -> None:
        """Load CCE config into widget controls."""
        temperature_unit = config.temperature_unit
        pressure_unit = config.pressure_unit

        t_index = self.cce_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.cce_temperature_unit.setCurrentIndex(t_index)
        p_index = self.cce_pressure_unit.findData(pressure_unit)
        if p_index >= 0:
            self.cce_pressure_unit.setCurrentIndex(p_index)

        self.cce_temperature.setValue(temperature_from_k(config.temperature_k, temperature_unit))
        if config.pressure_start_pa is not None:
            self.cce_p_start.setValue(pressure_from_pa(config.pressure_start_pa, pressure_unit))
        if config.pressure_end_pa is not None:
            self.cce_p_end.setValue(pressure_from_pa(config.pressure_end_pa, pressure_unit))
        if config.n_steps is not None:
            self.cce_n_steps.setValue(config.n_steps)
        if config.pressure_points_pa:
            self._set_cce_pressure_points_text(
                self._format_pressure_points(config.pressure_points_pa, pressure_unit),
                auto_generated=True,
            )
        else:
            self._set_cce_pressure_points_text("", auto_generated=True)
            self._sync_cce_generated_pressure_points(force=True)
        self._sync_cce_pressure_affordances()

    def set_dl_config(self, config: DLConfig) -> None:
        """Load DL config into widget controls."""
        temperature_unit = config.temperature_unit
        pressure_unit = config.pressure_unit

        t_index = self.dl_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.dl_temperature_unit.setCurrentIndex(t_index)
        p_index = self.dl_pressure_unit.findData(pressure_unit)
        if p_index >= 0:
            self.dl_pressure_unit.setCurrentIndex(p_index)

        self.dl_temperature.setValue(temperature_from_k(config.temperature_k, temperature_unit))
        self.set_dl_bubble_pressure_pa(config.bubble_pressure_pa)
        if config.pressure_end_pa is not None:
            self.dl_p_end.setValue(pressure_from_pa(config.pressure_end_pa, pressure_unit))
        if config.n_steps is not None:
            self.dl_n_steps.setValue(config.n_steps)
        self.dl_pressure_points.setText(
            self._format_pressure_points(config.pressure_points_pa, pressure_unit)
        )
        self._sync_dl_pressure_affordances()

    def _get_dl_schedule_inputs(
        self,
    ) -> tuple[float, PressureUnit, TemperatureUnit, Optional[list[float]], Optional[float], int]:
        """Parse the current DL schedule inputs independent of bubble-pressure derivation."""
        temperature_unit = self._coerce_combo_enum(
            self.dl_temperature_unit.currentData(),
            TemperatureUnit,
        )
        pressure_unit = self._coerce_combo_enum(
            self.dl_pressure_unit.currentData(),
            PressureUnit,
        )
        t_k = temperature_to_k(self.dl_temperature.value(), temperature_unit)
        pressure_points_pa = self._parse_pressure_points(
            self.dl_pressure_points.text(),
            pressure_unit,
        )
        if pressure_points_pa is not None:
            normalized_text = self._format_pressure_points(pressure_points_pa, pressure_unit)
            if self.dl_pressure_points.text().strip() != normalized_text:
                self.dl_pressure_points.setText(normalized_text)
            return t_k, pressure_unit, temperature_unit, pressure_points_pa, None, len(pressure_points_pa) + 1

        p_end_pa = pressure_to_pa(self.dl_p_end.value(), pressure_unit)
        return t_k, pressure_unit, temperature_unit, None, p_end_pa, self.dl_n_steps.value()

    def set_cvd_config(self, config: CVDConfig) -> None:
        """Load CVD config into widget controls."""
        self.cvd_temperature.setValue(config.temperature_k - 273.15)
        self.cvd_p_dew.setValue(config.dew_pressure_pa / 1e5)
        self.cvd_p_end.setValue(config.pressure_end_pa / 1e5)
        self.cvd_n_steps.setValue(config.n_steps)

    def set_swelling_test_config(self, config: SwellingTestConfig) -> None:
        """Load swelling-test config into widget controls."""
        temperature_unit = config.temperature_unit
        pressure_unit = config.pressure_unit

        t_index = self.swelling_temperature_unit.findData(temperature_unit)
        if t_index >= 0:
            self.swelling_temperature_unit.setCurrentIndex(t_index)
        p_index = self.swelling_pressure_unit.findData(pressure_unit)
        if p_index >= 0:
            self.swelling_pressure_unit.setCurrentIndex(p_index)

        self.swelling_temperature.setValue(
            temperature_from_k(config.temperature_k, temperature_unit)
        )
        self.swelling_enrichment_steps.setText(
            ", ".join(f"{value:.12g}" for value in config.enrichment_steps_mol_per_mol_oil)
        )
        self._set_swelling_gas_rows(
            [
                {
                    "component_id": entry.component_id,
                    "mole_fraction": entry.mole_fraction,
                }
                for entry in config.injection_gas_composition.components
            ]
        )

    def set_separator_config(self, config: SeparatorConfig) -> None:
        """Load separator config into widget controls."""
        self.separator_reservoir_pressure.setValue(config.reservoir_pressure_pa / 1e5)
        self.separator_reservoir_temperature.setValue(config.reservoir_temperature_k - 273.15)
        self.separator_include_stock_tank.setChecked(config.include_stock_tank)
        self._set_separator_stage_rows(
            [
                {
                    "name": stage.name,
                    "pressure_bar": stage.pressure_pa / 1e5,
                    "temperature_c": stage.temperature_k - 273.15,
                }
                for stage in config.separator_stages
            ]
        )

    def load_from_run_config(self, config: RunConfig) -> None:
        """Load a validated RunConfig into widget controls."""
        self.set_calculation_type(config.calculation_type)
        self.set_eos_type(config.eos_type)
        self.set_solver_settings(config.solver_settings)

        if config.calculation_type == CalculationType.PT_FLASH:
            if config.pt_flash_config is None:
                raise ValueError("RunConfig missing pt_flash_config")
            self.set_pt_flash_config(config.pt_flash_config)
        elif config.calculation_type == CalculationType.STABILITY_ANALYSIS:
            if config.stability_analysis_config is None:
                raise ValueError("RunConfig missing stability_analysis_config")
            self.set_stability_analysis_config(config.stability_analysis_config)
        elif config.calculation_type == CalculationType.BUBBLE_POINT:
            if config.bubble_point_config is None:
                raise ValueError("RunConfig missing bubble_point_config")
            self.set_bubble_point_config(config.bubble_point_config)
        elif config.calculation_type == CalculationType.DEW_POINT:
            if config.dew_point_config is None:
                raise ValueError("RunConfig missing dew_point_config")
            self.set_dew_point_config(config.dew_point_config)
        elif config.calculation_type == CalculationType.PHASE_ENVELOPE:
            if config.phase_envelope_config is None:
                raise ValueError("RunConfig missing phase_envelope_config")
            self.set_phase_envelope_config(config.phase_envelope_config)
        elif config.calculation_type == CalculationType.TBP:
            if config.tbp_config is None:
                raise ValueError("RunConfig missing tbp_config")
            self.set_tbp_config(config.tbp_config)
        elif config.calculation_type == CalculationType.CCE:
            if config.cce_config is None:
                raise ValueError("RunConfig missing cce_config")
            self.set_cce_config(config.cce_config)
        elif config.calculation_type == CalculationType.DL:
            if config.dl_config is None:
                raise ValueError("RunConfig missing dl_config")
            self.set_dl_config(config.dl_config)
        elif config.calculation_type == CalculationType.CVD:
            if config.cvd_config is None:
                raise ValueError("RunConfig missing cvd_config")
            self.set_cvd_config(config.cvd_config)
        elif config.calculation_type == CalculationType.SWELLING_TEST:
            if config.swelling_test_config is None:
                raise ValueError("RunConfig missing swelling_test_config")
            self.set_swelling_test_config(config.swelling_test_config)
        elif config.calculation_type == CalculationType.SEPARATOR:
            if config.separator_config is None:
                raise ValueError("RunConfig missing separator_config")
            self.set_separator_config(config.separator_config)
        else:
            raise ValueError(
                f"Loading calculation type '{config.calculation_type.value}' is not implemented"
            )

    def get_solver_settings(self) -> SolverSettings:
        """Get solver settings."""
        try:
            tolerance = float(self.tolerance_edit.text())
        except ValueError:
            tolerance = 1e-10

        return SolverSettings(
            tolerance=tolerance,
            max_iterations=self.max_iters_spin.value(),
        )

    def get_pt_flash_config(self) -> Optional[PTFlashConfig]:
        """Get PT flash configuration if valid."""
        if not self._validate_pressure() or not self._validate_temperature():
            return None

        try:
            p_value = float(self.pressure_edit.text())
            t_value = float(self.temperature_edit.text())

            p_unit = self._coerce_combo_enum(self.pressure_unit.currentData(), PressureUnit)
            t_unit = self._coerce_combo_enum(self.temperature_unit.currentData(), TemperatureUnit)

            p_pa = pressure_to_pa(p_value, p_unit)
            t_k = temperature_to_k(t_value, t_unit)

            return PTFlashConfig(
                pressure_pa=p_pa,
                temperature_k=t_k,
                pressure_unit=p_unit,
                temperature_unit=t_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_phase_envelope_config(self) -> Optional[PhaseEnvelopeConfig]:
        """Get phase envelope configuration if valid."""
        try:
            t_min_c = self.env_t_min.value()
            t_max_c = self.env_t_max.value()

            t_min_k = t_min_c + 273.15
            t_max_k = t_max_c + 273.15

            if t_min_k >= t_max_k:
                self.validation_error.emit("Min temperature must be less than max")
                return None

            return PhaseEnvelopeConfig(
                temperature_min_k=t_min_k,
                temperature_max_k=t_max_k,
                n_points=self.env_n_points.value(),
                tracing_method=self._coerce_combo_enum(
                    self.env_tracing_method.currentData(),
                    PhaseEnvelopeTracingMethod,
                ),
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_stability_analysis_config(self) -> Optional[StabilityAnalysisConfig]:
        """Get standalone stability-analysis configuration if valid."""
        if not self._validate_stability_pressure() or not self._validate_stability_temperature():
            return None

        try:
            pressure_value = float(self.stability_pressure_edit.text())
            temperature_value = float(self.stability_temperature_edit.text())
            pressure_unit = self._coerce_combo_enum(
                self.stability_pressure_unit.currentData(),
                PressureUnit,
            )
            temperature_unit = self._coerce_combo_enum(
                self.stability_temperature_unit.currentData(),
                TemperatureUnit,
            )
            return StabilityAnalysisConfig(
                pressure_pa=pressure_to_pa(pressure_value, pressure_unit),
                temperature_k=temperature_to_k(temperature_value, temperature_unit),
                feed_phase=self._coerce_combo_enum(
                    self.stability_feed_phase_combo.currentData(),
                    StabilityFeedPhase,
                ),
                use_gdem=self.stability_use_gdem.isChecked(),
                n_random_trials=self.stability_random_trials.value(),
                random_seed=self.stability_random_seed.value(),
                max_eos_failures_per_trial=self.stability_max_eos_failures.value(),
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_tbp_config(self) -> Optional[TBPConfig]:
        """Get standalone TBP assay configuration if valid."""
        try:
            cuts: list[dict[str, float | str]] = []
            for row in range(self.tbp_cut_table.rowCount()):
                name_item = self.tbp_cut_table.item(row, 0)
                z_item = self.tbp_cut_table.item(row, 1)
                mw_item = self.tbp_cut_table.item(row, 2)
                sg_item = self.tbp_cut_table.item(row, 3)
                tb_k_item = self.tbp_cut_table.item(row, 4)

                name = "" if name_item is None else name_item.text().strip()
                z_text = "" if z_item is None else z_item.text().strip()
                mw_text = "" if mw_item is None else mw_item.text().strip()
                sg_text = "" if sg_item is None else sg_item.text().strip()
                tb_k_text = "" if tb_k_item is None else tb_k_item.text().strip()

                if not any((name, z_text, mw_text, sg_text, tb_k_text)):
                    continue
                if not name:
                    raise ValueError(f"TBP row {row + 1} cut name is required")
                if not z_text:
                    raise ValueError(f"TBP row {row + 1} z is required")
                if not mw_text:
                    raise ValueError(f"TBP row {row + 1} MW is required")

                cut_payload: dict[str, float | str] = {
                    "name": name,
                    "z": float(z_text),
                    "mw": float(mw_text),
                }
                if sg_text:
                    cut_payload["sg"] = float(sg_text)
                if tb_k_text:
                    cut_payload["tb_k"] = float(tb_k_text)
                cuts.append(cut_payload)

            config = TBPConfig(
                cuts=cuts,
                cut_start=self.tbp_cut_start_spin.value(),
            )

            from pvtcore.experiments.tbp import simulate_tbp

            simulate_tbp(
                [cut.model_dump(mode="python", exclude_none=True) for cut in config.cuts],
                cut_start=config.cut_start,
            )
            return config
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def _get_optional_pressure_guess(
        self,
        enabled_widget: QCheckBox,
        spin_widget: QLineEdit,
        unit_widget: QWidget,
    ) -> Optional[float]:
        """Return an optional initial pressure guess in Pa."""
        if not enabled_widget.isChecked():
            return None
        value = float(spin_widget.text())
        unit = self._coerce_combo_enum(unit_widget.currentData(), PressureUnit)
        return pressure_to_pa(value, unit)

    def _get_saturation_temperature_k(
        self,
        temperature_widget: QLineEdit,
        unit_widget: QWidget,
    ) -> float:
        """Return a saturation temperature in Kelvin."""
        value = float(temperature_widget.text())
        unit = self._coerce_combo_enum(unit_widget.currentData(), TemperatureUnit)
        return temperature_to_k(value, unit)

    def get_bubble_point_config(self) -> Optional[SaturationPointConfig]:
        """Get bubble-point configuration if valid."""
        try:
            pressure_unit = self._coerce_combo_enum(
                self.bubble_pressure_guess_unit.currentData(),
                PressureUnit,
            )
            temperature_unit = self._coerce_combo_enum(
                self.bubble_temperature_unit.currentData(),
                TemperatureUnit,
            )
            return SaturationPointConfig(
                temperature_k=self._get_saturation_temperature_k(
                    self.bubble_temperature,
                    self.bubble_temperature_unit,
                ),
                pressure_initial_pa=self._get_optional_pressure_guess(
                    self.bubble_pressure_guess_enabled,
                    self.bubble_pressure_guess,
                    self.bubble_pressure_guess_unit,
                ),
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_dew_point_config(self) -> Optional[SaturationPointConfig]:
        """Get dew-point configuration if valid."""
        try:
            pressure_unit = self._coerce_combo_enum(
                self.dew_pressure_guess_unit.currentData(),
                PressureUnit,
            )
            temperature_unit = self._coerce_combo_enum(
                self.dew_temperature_unit.currentData(),
                TemperatureUnit,
            )
            return SaturationPointConfig(
                temperature_k=self._get_saturation_temperature_k(
                    self.dew_temperature,
                    self.dew_temperature_unit,
                ),
                pressure_initial_pa=self._get_optional_pressure_guess(
                    self.dew_pressure_guess_enabled,
                    self.dew_pressure_guess,
                    self.dew_pressure_guess_unit,
                ),
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_cce_config(self) -> Optional[CCEConfig]:
        """Get CCE configuration if valid."""
        try:
            temperature_unit = self._coerce_combo_enum(
                self.cce_temperature_unit.currentData(),
                TemperatureUnit,
            )
            pressure_unit = self._coerce_combo_enum(
                self.cce_pressure_unit.currentData(),
                PressureUnit,
            )
            t_k = temperature_to_k(self.cce_temperature.value(), temperature_unit)
            pressure_points_pa = self._parse_pressure_points(
                self.cce_pressure_points.text()
                ,
                pressure_unit,
            )
            if pressure_points_pa is not None:
                original_pressure_points_pa = list(pressure_points_pa)
                pressure_points_pa = self._normalize_descending_pressure_points(pressure_points_pa)
                normalized_text = self._format_pressure_points(pressure_points_pa, pressure_unit)
                if self.cce_pressure_points.text().strip() != normalized_text:
                    self.cce_pressure_points.setText(normalized_text)
                if list(pressure_points_pa) != original_pressure_points_pa:
                    self.status_hint.emit(self._cce_schedule_hint)
                return CCEConfig(
                    temperature_k=t_k,
                    pressure_points_pa=pressure_points_pa,
                    pressure_unit=pressure_unit,
                    temperature_unit=temperature_unit,
                )

            p_start_pa = pressure_to_pa(self.cce_p_start.value(), pressure_unit)
            p_end_pa = pressure_to_pa(self.cce_p_end.value(), pressure_unit)

            if p_start_pa <= p_end_pa:
                self.validation_error.emit(
                    "Start pressure must be greater than end pressure for CCE"
                )
                return None

            return CCEConfig(
                temperature_k=t_k,
                pressure_start_pa=p_start_pa,
                pressure_end_pa=p_end_pa,
                n_steps=self.cce_n_steps.value(),
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_dl_config(self) -> Optional[DLConfig]:
        """Get DL configuration if valid."""
        try:
            t_k, pressure_unit, temperature_unit, pressure_points_pa, p_end_pa, n_steps = (
                self._get_dl_schedule_inputs()
            )
            bubble_pressure_pa = self.get_dl_bubble_pressure_pa()
            if bubble_pressure_pa is None:
                self.validation_error.emit(
                    "Bubble pressure is auto-calculated from the active fluid composition and DL temperature."
                )
                return None
            if pressure_points_pa is not None:
                return DLConfig(
                    temperature_k=t_k,
                    bubble_pressure_pa=bubble_pressure_pa,
                    pressure_points_pa=pressure_points_pa,
                    pressure_unit=pressure_unit,
                    temperature_unit=temperature_unit,
                )

            assert p_end_pa is not None
            if bubble_pressure_pa <= p_end_pa:
                self.validation_error.emit(
                    "Bubble pressure must be greater than end pressure for DL"
                )
                return None

            return DLConfig(
                temperature_k=t_k,
                bubble_pressure_pa=bubble_pressure_pa,
                pressure_end_pa=p_end_pa,
                n_steps=n_steps,
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_cvd_config(self) -> Optional[CVDConfig]:
        """Get CVD configuration if valid."""
        try:
            t_k = self.cvd_temperature.value() + 273.15
            p_dew_pa = self.cvd_p_dew.value() * 1e5  # bar to Pa
            p_end_pa = self.cvd_p_end.value() * 1e5

            if p_dew_pa <= p_end_pa:
                self.validation_error.emit(
                    "Dew pressure must be greater than end pressure for CVD"
                )
                return None

            return CVDConfig(
                temperature_k=t_k,
                dew_pressure_pa=p_dew_pa,
                pressure_end_pa=p_end_pa,
                n_steps=self.cvd_n_steps.value(),
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_swelling_test_config(self) -> Optional[SwellingTestConfig]:
        """Get swelling-test configuration if valid."""
        try:
            temperature_unit = self._coerce_combo_enum(
                self.swelling_temperature_unit.currentData(),
                TemperatureUnit,
            )
            pressure_unit = self._coerce_combo_enum(
                self.swelling_pressure_unit.currentData(),
                PressureUnit,
            )
            schedule_text = self.swelling_enrichment_steps.text().strip()
            if not schedule_text:
                raise ValueError("At least one enrichment step is required")
            schedule = [
                float(token)
                for token in re.split(r"[,\s;]+", schedule_text)
                if token
            ]

            components: list[ComponentEntry] = []
            seen_component_ids: set[str] = set()
            total_mole_fraction = 0.0

            for row in range(self.swelling_gas_table.rowCount()):
                component_item = self.swelling_gas_table.item(row, 0)
                mole_fraction_item = self.swelling_gas_table.item(row, 1)
                raw_component_id = "" if component_item is None else component_item.text().strip()
                raw_mole_fraction = "" if mole_fraction_item is None else mole_fraction_item.text().strip()

                if not raw_component_id and not raw_mole_fraction:
                    continue
                if not raw_component_id:
                    raise ValueError(f"Injection-gas row {row + 1} component ID is required")
                if not raw_mole_fraction:
                    raise ValueError(f"Injection-gas row {row + 1} mole fraction is required")

                canonical_id = resolve_component_id(raw_component_id, self._components_db)
                if canonical_id in seen_component_ids:
                    raise ValueError(
                        f"Injection gas contains duplicate component ID '{raw_component_id}' "
                        "after alias resolution"
                    )
                seen_component_ids.add(canonical_id)

                mole_fraction = float(raw_mole_fraction)
                total_mole_fraction += mole_fraction
                components.append(
                    ComponentEntry(
                        component_id=raw_component_id,
                        mole_fraction=mole_fraction,
                    )
                )

            if not components:
                raise ValueError("Injection gas must include at least one component row")
            if abs(total_mole_fraction - 1.0) > COMPOSITION_SUM_TOLERANCE:
                raise ValueError(
                    f"Injection gas mole fractions must sum to 1.0 within ±{COMPOSITION_SUM_TOLERANCE:.1e}; "
                    f"got {total_mole_fraction:.8f}"
                )

            return SwellingTestConfig(
                temperature_k=temperature_to_k(self.swelling_temperature.value(), temperature_unit),
                enrichment_steps_mol_per_mol_oil=schedule,
                injection_gas_composition=FluidComposition(components=components),
                pressure_unit=pressure_unit,
                temperature_unit=temperature_unit,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_separator_config(self) -> Optional[SeparatorConfig]:
        """Get separator configuration if valid."""
        try:
            stages = []
            for row in range(self.separator_stage_table.rowCount()):
                name_item = self.separator_stage_table.item(row, 0)
                pressure_item = self.separator_stage_table.item(row, 1)
                temperature_item = self.separator_stage_table.item(row, 2)
                if pressure_item is None or temperature_item is None:
                    raise ValueError(f"Separator stage row {row + 1} is incomplete")
                stage_name = "" if name_item is None else name_item.text().strip()
                pressure_pa = float(pressure_item.text()) * 1e5
                temperature_k = float(temperature_item.text()) + 273.15
                stages.append(
                    {
                        "name": stage_name,
                        "pressure_pa": pressure_pa,
                        "temperature_k": temperature_k,
                    }
                )

            return SeparatorConfig(
                reservoir_pressure_pa=self.separator_reservoir_pressure.value() * 1e5,
                reservoir_temperature_k=self.separator_reservoir_temperature.value() + 273.15,
                include_stock_tank=self.separator_include_stock_tank.isChecked(),
                separator_stages=stages,
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def validate(self) -> Tuple[bool, str]:
        """Validate current conditions.

        Returns:
            Tuple of (is_valid, error_message)
        """
        calc_type = self.get_calculation_type()

        if calc_type == CalculationType.PT_FLASH:
            config = self.get_pt_flash_config()
            if config is None:
                return False, "Invalid PT flash conditions"
        elif calc_type == CalculationType.STABILITY_ANALYSIS:
            config = self.get_stability_analysis_config()
            if config is None:
                return False, "Invalid stability-analysis conditions"
        elif calc_type == CalculationType.BUBBLE_POINT:
            config = self.get_bubble_point_config()
            if config is None:
                return False, "Invalid bubble-point conditions"
        elif calc_type == CalculationType.DEW_POINT:
            config = self.get_dew_point_config()
            if config is None:
                return False, "Invalid dew-point conditions"
        elif calc_type == CalculationType.PHASE_ENVELOPE:
            config = self.get_phase_envelope_config()
            if config is None:
                return False, "Invalid phase envelope conditions"
        elif calc_type == CalculationType.TBP:
            config = self.get_tbp_config()
            if config is None:
                return False, "Invalid TBP conditions"
        elif calc_type == CalculationType.CCE:
            config = self.get_cce_config()
            if config is None:
                return False, "Invalid CCE conditions"
        elif calc_type == CalculationType.DL:
            try:
                self._get_dl_schedule_inputs()
            except Exception:
                return False, "Invalid DL conditions"
            if self.get_dl_bubble_pressure_pa() is not None:
                config = self.get_dl_config()
                if config is None:
                    return False, "Invalid DL conditions"
        elif calc_type == CalculationType.CVD:
            config = self.get_cvd_config()
            if config is None:
                return False, "Invalid CVD conditions"
        elif calc_type == CalculationType.SWELLING_TEST:
            config = self.get_swelling_test_config()
            if config is None:
                return False, "Invalid swelling-test conditions"
        elif calc_type == CalculationType.SEPARATOR:
            config = self.get_separator_config()
            if config is None:
                return False, "Invalid separator conditions"
        else:
            return False, f"Calculation type '{calc_type.value}' is not currently exposed in the desktop GUI"

        return True, ""
