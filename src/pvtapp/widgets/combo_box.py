"""Shared no-wheel selector helpers for the desktop UI."""

from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSpinBox, QTabWidget, QWidget


class NoWheelComboBox(QComboBox):
    """Combo box that ignores mouse-wheel selection changes.

    This keeps scroll-wheel navigation attached to the surrounding scroll area
    instead of silently mutating the hovered combo box.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()


class NoWheelSpinBox(QSpinBox):
    """Spin box that ignores mouse-wheel value changes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """Double spin box that ignores mouse-wheel value changes."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()


class NoWheelTabWidget(QTabWidget):
    """Tab widget that ignores mouse-wheel tab switching."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

    def wheelEvent(self, event) -> None:  # pragma: no cover - simple UI guard
        event.ignore()
