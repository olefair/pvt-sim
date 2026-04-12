"""Conditions input widget with units-aware validated fields.

Provides input fields for pressure, temperature, and calculation type
with explicit unit handling and strict validation.
"""

import re
from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
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
)

from pvtapp.schemas import (
    CalculationType,
    EOSType,
    PhaseEnvelopeTracingMethod,
    PressureUnit,
    TemperatureUnit,
    RunConfig,
    PTFlashConfig,
    PhaseEnvelopeConfig,
    CCEConfig,
    SaturationPointConfig,
    DLConfig,
    CVDConfig,
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


class ConditionsInputWidget(QWidget):
    """Widget for entering calculation conditions with unit selection.

    Signals:
        conditions_changed: Emitted when valid conditions are entered
        validation_error: Emitted with error message when validation fails
    """

    conditions_changed = Signal()
    validation_error = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
        self._on_calc_type_changed()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

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
        self.config_stack = QStackedWidget()

        # PT Flash config
        self.pt_flash_widget = self._create_pt_flash_widget()
        self.config_stack.addWidget(self.pt_flash_widget)

        # Phase Envelope config
        self.phase_env_widget = self._create_phase_envelope_widget()
        self.config_stack.addWidget(self.phase_env_widget)

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
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

    @staticmethod
    def _configure_unit_row(layout: QHBoxLayout, field: QWidget, unit_widget: QWidget) -> None:
        """Give input/unit rows predictable proportions inside narrow forms."""
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        unit_widget.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        unit_widget.setProperty("sidebar_unit_widget", True)
        if hasattr(unit_widget, "setMaximumWidth"):
            unit_widget.setMaximumWidth(96)
        layout.addWidget(field, 1)
        layout.addWidget(unit_widget, 0)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale sidebar-only geometry that is not controlled by QSS."""
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
        self.temperature_unit.setCurrentIndex(1)  # C
        self._configure_unit_row(t_layout, self.temperature_edit, self.temperature_unit)

        layout.addRow("Temperature:", t_layout)

        return widget

    def _create_phase_envelope_widget(self) -> QWidget:
        """Create phase envelope configuration widget."""
        widget = QGroupBox("Phase Envelope Settings")
        layout = QFormLayout(widget)
        self._configure_form_layout(layout)

        # Temperature range
        t_min_layout = QHBoxLayout()
        self.env_t_min = NoWheelDoubleSpinBox()
        self.env_t_min.setRange(-200, 500)
        self.env_t_min.setValue(-123.15)  # 150 K in C
        self.env_t_min.setDecimals(2)
        t_min_layout.addWidget(self.env_t_min)
        t_min_layout.addWidget(QLabel("C"))
        layout.addRow("Min Temperature:", t_min_layout)

        t_max_layout = QHBoxLayout()
        self.env_t_max = NoWheelDoubleSpinBox()
        self.env_t_max.setRange(-200, 600)
        self.env_t_max.setValue(326.85)  # 600 K in C
        self.env_t_max.setDecimals(2)
        t_max_layout.addWidget(self.env_t_max)
        t_max_layout.addWidget(QLabel("C"))
        layout.addRow("Max Temperature:", t_max_layout)

        # Number of points
        self.env_n_points = NoWheelSpinBox()
        self.env_n_points.setRange(10, 500)
        self.env_n_points.setValue(50)
        layout.addRow("Number of Points:", self.env_n_points)

        self.env_tracing_method = NoWheelComboBox()
        self.env_tracing_method.addItem(
            "Continuation (Default)",
            PhaseEnvelopeTracingMethod.CONTINUATION,
        )
        self.env_tracing_method.addItem(
            "Legacy (Fixed Grid)",
            PhaseEnvelopeTracingMethod.FIXED_GRID,
        )
        layout.addRow("Tracer:", self.env_tracing_method)

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
        temperature_unit.setCurrentIndex(1)  # C
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
        self.cce_temperature.setValue(100)
        self.cce_temperature.setDecimals(2)
        t_layout.addWidget(self.cce_temperature)
        t_layout.addWidget(QLabel("C"))
        layout.addRow("Temperature:", t_layout)

        # Start pressure
        p_start_layout = QHBoxLayout()
        self.cce_p_start = NoWheelDoubleSpinBox()
        self.cce_p_start.setRange(0.01, 10000)
        self.cce_p_start.setValue(500)
        self.cce_p_start.setDecimals(2)
        p_start_layout.addWidget(self.cce_p_start)
        p_start_layout.addWidget(QLabel("bar"))
        layout.addRow("Start Pressure:", p_start_layout)

        # End pressure
        p_end_layout = QHBoxLayout()
        self.cce_p_end = NoWheelDoubleSpinBox()
        self.cce_p_end.setRange(0.01, 10000)
        self.cce_p_end.setValue(50)
        self.cce_p_end.setDecimals(2)
        p_end_layout.addWidget(self.cce_p_end)
        p_end_layout.addWidget(QLabel("bar"))
        layout.addRow("End Pressure:", p_end_layout)

        # Number of steps
        self.cce_n_steps = NoWheelSpinBox()
        self.cce_n_steps.setRange(2, 200)
        self.cce_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.cce_n_steps)

        self.cce_pressure_points = QLineEdit()
        self.cce_pressure_points.setPlaceholderText(
            "Optional exact pressures in bar, e.g. 200, 150, 100"
        )
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
        self.dl_temperature.setValue(100)
        self.dl_temperature.setDecimals(2)
        t_layout.addWidget(self.dl_temperature)
        t_layout.addWidget(QLabel("C"))
        layout.addRow("Temperature:", t_layout)

        bubble_layout = QHBoxLayout()
        self.dl_bubble_pressure = NoWheelDoubleSpinBox()
        self.dl_bubble_pressure.setRange(0.01, 10000)
        self.dl_bubble_pressure.setValue(150)
        self.dl_bubble_pressure.setDecimals(2)
        bubble_layout.addWidget(self.dl_bubble_pressure)
        bubble_layout.addWidget(QLabel("bar"))
        layout.addRow("Bubble Pressure:", bubble_layout)

        end_layout = QHBoxLayout()
        self.dl_p_end = NoWheelDoubleSpinBox()
        self.dl_p_end.setRange(0.01, 10000)
        self.dl_p_end.setValue(10)
        self.dl_p_end.setDecimals(2)
        end_layout.addWidget(self.dl_p_end)
        end_layout.addWidget(QLabel("bar"))
        layout.addRow("End Pressure:", end_layout)

        self.dl_n_steps = NoWheelSpinBox()
        self.dl_n_steps.setRange(2, 200)
        self.dl_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.dl_n_steps)

        self.dl_pressure_points = QLineEdit()
        self.dl_pressure_points.setPlaceholderText(
            "Optional exact pressures below bubble in bar, e.g. 60, 40, 20"
        )
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
        self.cvd_temperature.setValue(100)
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
        self.separator_reservoir_temperature.setValue(100)
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

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.calc_type_combo.currentIndexChanged.connect(self._on_calc_type_changed)
        self.pressure_edit.textChanged.connect(self._validate_pressure)
        self.temperature_edit.textChanged.connect(self._validate_temperature)
        self.bubble_temperature.textChanged.connect(self._emit_conditions_changed)
        self.dew_temperature.textChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess.textChanged.connect(self._emit_conditions_changed)
        self.dew_pressure_guess.textChanged.connect(self._emit_conditions_changed)
        self.cce_pressure_points.textChanged.connect(self._emit_conditions_changed)
        self.dl_pressure_points.textChanged.connect(self._emit_conditions_changed)
        self.bubble_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.dew_temperature_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.dew_pressure_guess_unit.currentIndexChanged.connect(self._emit_conditions_changed)
        self.bubble_pressure_guess_enabled.toggled.connect(self._emit_conditions_changed)
        self.dew_pressure_guess_enabled.toggled.connect(self._emit_conditions_changed)

    def _emit_conditions_changed(self, *_args) -> None:
        """Re-emit input changes from Qt signals that may carry extra arguments."""
        self.conditions_changed.emit()

    def _on_calc_type_changed(self) -> None:
        """Update visible configuration based on calculation type."""
        calc_type = self.calc_type_combo.currentData()

        if calc_type == CalculationType.PT_FLASH:
            self.config_stack.setCurrentWidget(self.pt_flash_widget)
        elif calc_type == CalculationType.BUBBLE_POINT:
            self.config_stack.setCurrentWidget(self.bubble_widget)
        elif calc_type == CalculationType.DEW_POINT:
            self.config_stack.setCurrentWidget(self.dew_widget)
        elif calc_type == CalculationType.PHASE_ENVELOPE:
            self.config_stack.setCurrentWidget(self.phase_env_widget)
        elif calc_type == CalculationType.CCE:
            self.config_stack.setCurrentWidget(self.cce_widget)
        elif calc_type == CalculationType.DL:
            self.config_stack.setCurrentWidget(self.dl_widget)
        elif calc_type == CalculationType.CVD:
            self.config_stack.setCurrentWidget(self.cvd_widget)
        elif calc_type == CalculationType.SEPARATOR:
            self.config_stack.setCurrentWidget(self.separator_widget)
        else:
            self.config_stack.setCurrentWidget(self.placeholder_widget)

        self.conditions_changed.emit()

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

    @staticmethod
    def _coerce_combo_enum(value, enum_type):
        """Normalize Qt combo-box data back into the expected enum type."""
        if isinstance(value, enum_type):
            return value
        return enum_type(value)

    @staticmethod
    def _parse_pressure_points_bar(text: str) -> Optional[list[float]]:
        """Parse an optional comma/whitespace-delimited pressure list in bar."""
        stripped = text.strip()
        if not stripped:
            return None
        tokens = [token for token in re.split(r"[,\s;]+", stripped) if token]
        return [float(token) * 1e5 for token in tokens]

    @staticmethod
    def _format_pressure_points_bar(values_pa: Optional[list[float]]) -> str:
        """Format an optional pressure list in bar for the widget."""
        if not values_pa:
            return ""
        return ", ".join(f"{value / 1e5:.12g}" for value in values_pa)

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

    def set_phase_envelope_config(self, config: PhaseEnvelopeConfig) -> None:
        """Load phase-envelope config into widget controls."""
        self.env_t_min.setValue(config.temperature_min_k - 273.15)
        self.env_t_max.setValue(config.temperature_max_k - 273.15)
        self.env_n_points.setValue(config.n_points)
        method_index = self.env_tracing_method.findData(config.tracing_method)
        if method_index >= 0:
            self.env_tracing_method.setCurrentIndex(method_index)

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
        self.cce_temperature.setValue(config.temperature_k - 273.15)
        self.cce_p_start.setValue(config.pressure_start_pa / 1e5)
        self.cce_p_end.setValue(config.pressure_end_pa / 1e5)
        self.cce_n_steps.setValue(config.n_steps)
        self.cce_pressure_points.setText(
            self._format_pressure_points_bar(config.pressure_points_pa)
        )

    def set_dl_config(self, config: DLConfig) -> None:
        """Load DL config into widget controls."""
        self.dl_temperature.setValue(config.temperature_k - 273.15)
        self.dl_bubble_pressure.setValue(config.bubble_pressure_pa / 1e5)
        self.dl_p_end.setValue(config.pressure_end_pa / 1e5)
        self.dl_n_steps.setValue(config.n_steps)
        self.dl_pressure_points.setText(
            self._format_pressure_points_bar(config.pressure_points_pa)
        )

    def set_cvd_config(self, config: CVDConfig) -> None:
        """Load CVD config into widget controls."""
        self.cvd_temperature.setValue(config.temperature_k - 273.15)
        self.cvd_p_dew.setValue(config.dew_pressure_pa / 1e5)
        self.cvd_p_end.setValue(config.pressure_end_pa / 1e5)
        self.cvd_n_steps.setValue(config.n_steps)

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
            t_k = self.cce_temperature.value() + 273.15
            pressure_points_pa = self._parse_pressure_points_bar(
                self.cce_pressure_points.text()
            )
            if pressure_points_pa is not None:
                return CCEConfig(
                    temperature_k=t_k,
                    pressure_points_pa=pressure_points_pa,
                )

            p_start_pa = self.cce_p_start.value() * 1e5  # bar to Pa
            p_end_pa = self.cce_p_end.value() * 1e5

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
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_dl_config(self) -> Optional[DLConfig]:
        """Get DL configuration if valid."""
        try:
            t_k = self.dl_temperature.value() + 273.15
            bubble_pressure_pa = self.dl_bubble_pressure.value() * 1e5
            pressure_points_pa = self._parse_pressure_points_bar(
                self.dl_pressure_points.text()
            )
            if pressure_points_pa is not None:
                return DLConfig(
                    temperature_k=t_k,
                    bubble_pressure_pa=bubble_pressure_pa,
                    pressure_points_pa=pressure_points_pa,
                )

            p_end_pa = self.dl_p_end.value() * 1e5

            if bubble_pressure_pa <= p_end_pa:
                self.validation_error.emit(
                    "Bubble pressure must be greater than end pressure for DL"
                )
                return None

            return DLConfig(
                temperature_k=t_k,
                bubble_pressure_pa=bubble_pressure_pa,
                pressure_end_pa=p_end_pa,
                n_steps=self.dl_n_steps.value(),
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
        elif calc_type == CalculationType.CCE:
            config = self.get_cce_config()
            if config is None:
                return False, "Invalid CCE conditions"
        elif calc_type == CalculationType.DL:
            config = self.get_dl_config()
            if config is None:
                return False, "Invalid DL conditions"
        elif calc_type == CalculationType.CVD:
            config = self.get_cvd_config()
            if config is None:
                return False, "Invalid CVD conditions"
        elif calc_type == CalculationType.SEPARATOR:
            config = self.get_separator_config()
            if config is None:
                return False, "Invalid separator conditions"
        else:
            return False, f"Calculation type '{calc_type.value}' is not currently exposed in the desktop GUI"

        return True, ""
