"""Two-pane workspace with per-pane view selection.

Provides the layout requested for side-by-side comparisons:
- Two panes
- Each pane has a drop-down to select which panel/view to show
- The currently selected view in one pane is disabled in the other
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)


@dataclass(frozen=True)
class ViewSpec:
    view_id: str
    label: str


class _Pane(QFrame):
    """Single pane: header (dropdown) + content area."""

    view_changed = Signal(str)  # view_id

    def __init__(self, *, title: str, view_specs: List[ViewSpec], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PaneCard")
        self._current_view_id: Optional[str] = None
        self._current_widget: Optional[QWidget] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("PaneTitle")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header.addWidget(title_lbl)

        self.combo = QComboBox()
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for spec in view_specs:
            self.combo.addItem(spec.label, spec.view_id)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        header.addWidget(self.combo, 1)

        outer.addLayout(header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        outer.addWidget(self._content, 1)

    @property
    def current_view_id(self) -> Optional[str]:
        return self._current_view_id

    def set_current_view(self, view_id: str) -> None:
        idx = self.combo.findData(view_id)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def set_widget(self, widget: Optional[QWidget]) -> None:
        # Detach old
        if self._current_widget is not None:
            self._content_layout.removeWidget(self._current_widget)
            self._current_widget.setParent(None)
            self._current_widget = None

        self._current_widget = widget
        if widget is None:
            return

        widget.setParent(self._content)
        widget.show()
        self._content_layout.addWidget(widget)

    def set_item_enabled(self, view_id: str, enabled: bool) -> None:
        idx = self.combo.findData(view_id)
        if idx < 0:
            return
        model = self.combo.model()
        if hasattr(model, "item"):
            item = model.item(idx)
            if item is not None:
                item.setEnabled(enabled)

    def _on_combo_changed(self, _index: int) -> None:
        view_id = self.combo.currentData()
        if isinstance(view_id, str):
            self._current_view_id = view_id
            self.view_changed.emit(view_id)


class TwoPaneWorkspace(QWidget):
    """A workspace with two panes and mutual exclusion of selected views."""

    def __init__(
        self,
        *,
        view_specs: List[ViewSpec],
        view_widgets: Dict[str, QWidget],
        left_default: str,
        right_default: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._view_specs = list(view_specs)
        self._view_widgets = dict(view_widgets)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.left_pane = _Pane(title="Left", view_specs=self._view_specs)
        self.right_pane = _Pane(title="Right", view_specs=self._view_specs)

        self.left_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.left_pane, vid))
        self.right_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.right_pane, vid))

        splitter.addWidget(self.left_pane)
        splitter.addWidget(self.right_pane)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter, 1)

        # Initialize
        self.left_pane.set_current_view(left_default)
        self.right_pane.set_current_view(right_default)
        self._apply_view_to_pane(self.left_pane, left_default)
        self._apply_view_to_pane(self.right_pane, right_default)
        self._sync_disabled_items()

    def _on_pane_changed(self, pane: _Pane, view_id: str) -> None:
        self._apply_view_to_pane(pane, view_id)
        self._sync_disabled_items()

    def _apply_view_to_pane(self, pane: _Pane, view_id: str) -> None:
        widget = self._view_widgets.get(view_id)
        pane.set_widget(widget)

    def _sync_disabled_items(self) -> None:
        left = self.left_pane.current_view_id
        right = self.right_pane.current_view_id

        # Enable everything first
        for spec in self._view_specs:
            self.left_pane.set_item_enabled(spec.view_id, True)
            self.right_pane.set_item_enabled(spec.view_id, True)

        # Disable opposite selection
        if isinstance(right, str):
            self.left_pane.set_item_enabled(right, False)
        if isinstance(left, str):
            self.right_pane.set_item_enabled(left, False)
