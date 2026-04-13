"""Scrollable inputs panel (composition + conditions)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QScrollArea, QSizePolicy, QWidget, QVBoxLayout

from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.composition_input import CompositionInputWidget
from pvtapp.widgets.conditions_input import ConditionsInputWidget


class InputsPanel(QScrollArea):
    """A scrollable container for the primary input widgets."""

    def __init__(
        self,
        composition_widget: Optional[CompositionInputWidget] = None,
        conditions_widget: Optional[ConditionsInputWidget] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.composition_widget = composition_widget or CompositionInputWidget()
        self.conditions_widget = conditions_widget or ConditionsInputWidget()

        content = QWidget()
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(8)
        self._content_layout.addWidget(self.composition_widget)
        self._content_layout.addWidget(self.conditions_widget)
        self._content_layout.addStretch(1)

        self.setWidget(content)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Forward app zoom into child widgets that expose scaling hooks."""
        self._content_layout.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        for widget in (self.composition_widget, self.conditions_widget):
            if hasattr(widget, "apply_ui_scale"):
                widget.apply_ui_scale(ui_scale)
