"""Scrollable inputs panel (composition + conditions)."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QScrollArea, QWidget, QVBoxLayout

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

        self.composition_widget = composition_widget or CompositionInputWidget()
        self.conditions_widget = conditions_widget or ConditionsInputWidget()

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.composition_widget)
        layout.addWidget(self.conditions_widget)
        layout.addStretch(1)

        self.setWidget(content)
