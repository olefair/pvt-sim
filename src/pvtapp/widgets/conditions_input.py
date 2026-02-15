"""Conditions input widget with units-aware validated fields.

Provides input fields for pressure, temperature, and calculation type
with explicit unit handling and strict validation.
"""

from typing import Optional, Tuple

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QLabel,
    QGroupBox,
    QStackedWidget,
    QSpinBox,
    QDoubleSpinBox,
)

from pvtapp.schemas import (
    CalculationType,
    EOSType,
    PressureUnit,
    TemperatureUnit,
    PTFlashConfig,
    PhaseEnvelopeConfig,
    CCEConfig,
    SolverSettings,
    pressure_to_pa,
    temperature_to_k,
    PRESSURE_MIN_PA,
    PRESSURE_MAX_PA,
    TEMPERATURE_MIN_K,
    TEMPERATURE_MAX_K,
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

        self.calc_type_combo = QComboBox()
        for calc_type in CalculationType:
            # Display friendly names
            display_name = calc_type.value.replace("_", " ").title()
            self.calc_type_combo.addItem(display_name, calc_type)
        calc_layout.addRow("Type:", self.calc_type_combo)

        self.eos_combo = QComboBox()
        for eos in EOSType:
            display_name = eos.value.replace("_", "-").upper()
            self.eos_combo.addItem(display_name, eos)
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

        # CCE config
        self.cce_widget = self._create_cce_widget()
        self.config_stack.addWidget(self.cce_widget)

        # Placeholder for other calculation types
        self.placeholder_widget = QLabel("Configuration for this calculation type\ncoming soon...")
        self.placeholder_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.config_stack.addWidget(self.placeholder_widget)

        layout.addWidget(self.config_stack)

        # Solver settings (collapsed by default)
        solver_group = QGroupBox("Solver Settings (Advanced)")
        solver_group.setCheckable(True)
        solver_group.setChecked(False)
        solver_layout = QFormLayout(solver_group)

        self.tolerance_edit = QLineEdit("1e-10")
        self.tolerance_edit.setValidator(QDoubleValidator(1e-15, 1e-1, 15))
        solver_layout.addRow("Tolerance:", self.tolerance_edit)

        self.max_iters_spin = QSpinBox()
        self.max_iters_spin.setRange(1, 10000)
        self.max_iters_spin.setValue(100)
        solver_layout.addRow("Max Iterations:", self.max_iters_spin)

        layout.addWidget(solver_group)

        layout.addStretch()

    def _create_pt_flash_widget(self) -> QWidget:
        """Create PT flash configuration widget."""
        widget = QGroupBox("PT Flash Conditions")
        layout = QFormLayout(widget)

        # Pressure input
        p_layout = QHBoxLayout()
        self.pressure_edit = ValidatedLineEdit()
        self.pressure_edit.setPlaceholderText("Enter pressure")
        p_layout.addWidget(self.pressure_edit)

        self.pressure_unit = QComboBox()
        for unit in PressureUnit:
            self.pressure_unit.addItem(unit.value, unit)
        self.pressure_unit.setCurrentIndex(3)  # bar
        p_layout.addWidget(self.pressure_unit)

        layout.addRow("Pressure:", p_layout)

        # Temperature input
        t_layout = QHBoxLayout()
        self.temperature_edit = ValidatedLineEdit()
        self.temperature_edit.setPlaceholderText("Enter temperature")
        t_layout.addWidget(self.temperature_edit)

        self.temperature_unit = QComboBox()
        for unit in TemperatureUnit:
            self.temperature_unit.addItem(unit.value, unit)
        self.temperature_unit.setCurrentIndex(1)  # C
        t_layout.addWidget(self.temperature_unit)

        layout.addRow("Temperature:", t_layout)

        return widget

    def _create_phase_envelope_widget(self) -> QWidget:
        """Create phase envelope configuration widget."""
        widget = QGroupBox("Phase Envelope Settings")
        layout = QFormLayout(widget)

        # Temperature range
        t_min_layout = QHBoxLayout()
        self.env_t_min = QDoubleSpinBox()
        self.env_t_min.setRange(-200, 500)
        self.env_t_min.setValue(-123.15)  # 150 K in C
        self.env_t_min.setDecimals(2)
        t_min_layout.addWidget(self.env_t_min)
        t_min_layout.addWidget(QLabel("C"))
        layout.addRow("Min Temperature:", t_min_layout)

        t_max_layout = QHBoxLayout()
        self.env_t_max = QDoubleSpinBox()
        self.env_t_max.setRange(-200, 600)
        self.env_t_max.setValue(326.85)  # 600 K in C
        self.env_t_max.setDecimals(2)
        t_max_layout.addWidget(self.env_t_max)
        t_max_layout.addWidget(QLabel("C"))
        layout.addRow("Max Temperature:", t_max_layout)

        # Number of points
        self.env_n_points = QSpinBox()
        self.env_n_points.setRange(10, 500)
        self.env_n_points.setValue(50)
        layout.addRow("Number of Points:", self.env_n_points)

        return widget

    def _create_cce_widget(self) -> QWidget:
        """Create CCE configuration widget."""
        widget = QGroupBox("CCE Settings")
        layout = QFormLayout(widget)

        # Temperature
        t_layout = QHBoxLayout()
        self.cce_temperature = QDoubleSpinBox()
        self.cce_temperature.setRange(-200, 500)
        self.cce_temperature.setValue(100)
        self.cce_temperature.setDecimals(2)
        t_layout.addWidget(self.cce_temperature)
        t_layout.addWidget(QLabel("C"))
        layout.addRow("Temperature:", t_layout)

        # Start pressure
        p_start_layout = QHBoxLayout()
        self.cce_p_start = QDoubleSpinBox()
        self.cce_p_start.setRange(0.01, 10000)
        self.cce_p_start.setValue(500)
        self.cce_p_start.setDecimals(2)
        p_start_layout.addWidget(self.cce_p_start)
        p_start_layout.addWidget(QLabel("bar"))
        layout.addRow("Start Pressure:", p_start_layout)

        # End pressure
        p_end_layout = QHBoxLayout()
        self.cce_p_end = QDoubleSpinBox()
        self.cce_p_end.setRange(0.01, 10000)
        self.cce_p_end.setValue(50)
        self.cce_p_end.setDecimals(2)
        p_end_layout.addWidget(self.cce_p_end)
        p_end_layout.addWidget(QLabel("bar"))
        layout.addRow("End Pressure:", p_end_layout)

        # Number of steps
        self.cce_n_steps = QSpinBox()
        self.cce_n_steps.setRange(5, 200)
        self.cce_n_steps.setValue(20)
        layout.addRow("Number of Steps:", self.cce_n_steps)

        return widget

    def _connect_signals(self) -> None:
        """Connect widget signals."""
        self.calc_type_combo.currentIndexChanged.connect(self._on_calc_type_changed)
        self.pressure_edit.textChanged.connect(self._validate_pressure)
        self.temperature_edit.textChanged.connect(self._validate_temperature)

    def _on_calc_type_changed(self) -> None:
        """Update visible configuration based on calculation type."""
        calc_type = self.calc_type_combo.currentData()

        if calc_type == CalculationType.PT_FLASH:
            self.config_stack.setCurrentWidget(self.pt_flash_widget)
        elif calc_type == CalculationType.PHASE_ENVELOPE:
            self.config_stack.setCurrentWidget(self.phase_env_widget)
        elif calc_type == CalculationType.CCE:
            self.config_stack.setCurrentWidget(self.cce_widget)
        else:
            self.config_stack.setCurrentWidget(self.placeholder_widget)

        self.conditions_changed.emit()

    def _validate_pressure(self) -> bool:
        """Validate pressure input."""
        try:
            value = float(self.pressure_edit.text())
            unit = self.pressure_unit.currentData()
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
            unit = self.temperature_unit.currentData()
            k = temperature_to_k(value, unit)

            if k < TEMPERATURE_MIN_K or k > TEMPERATURE_MAX_K:
                self.temperature_edit.set_valid(False)
                return False

            self.temperature_edit.set_valid(True)
            return True
        except (ValueError, TypeError):
            self.temperature_edit.set_valid(False)
            return False

    def get_calculation_type(self) -> CalculationType:
        """Get selected calculation type."""
        return self.calc_type_combo.currentData()

    def get_eos_type(self) -> EOSType:
        """Get selected EOS."""
        return self.eos_combo.currentData()

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

            p_unit = self.pressure_unit.currentData()
            t_unit = self.temperature_unit.currentData()

            p_pa = pressure_to_pa(p_value, p_unit)
            t_k = temperature_to_k(t_value, t_unit)

            return PTFlashConfig(pressure_pa=p_pa, temperature_k=t_k)
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
            )
        except Exception as e:
            self.validation_error.emit(str(e))
            return None

    def get_cce_config(self) -> Optional[CCEConfig]:
        """Get CCE configuration if valid."""
        try:
            t_k = self.cce_temperature.value() + 273.15
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
        elif calc_type == CalculationType.PHASE_ENVELOPE:
            config = self.get_phase_envelope_config()
            if config is None:
                return False, "Invalid phase envelope conditions"
        elif calc_type == CalculationType.CCE:
            config = self.get_cce_config()
            if config is None:
                return False, "Invalid CCE conditions"
        else:
            return False, f"Calculation type '{calc_type.value}' not yet implemented"

        return True, ""
