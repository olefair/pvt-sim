"""Workspace with a fixed inputs sidebar plus two selectable panes.

Provides the MI-PVT-like layout requested for side-by-side comparisons:
- a permanently docked inputs sidebar on the left
- two right-side panes with drop-down view selection
- mutual exclusion so the same view cannot be selected in both panes
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

from pvtapp.style import DEFAULT_UI_SCALE, scale_metric


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

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(12, 12, 12, 12)
        self._outer.setSpacing(10)

        self._header = QHBoxLayout()
        self._header.setContentsMargins(0, 0, 0, 0)
        self._header.setSpacing(8)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("PaneTitle")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._header.addWidget(title_lbl)

        self.combo = QComboBox()
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        for spec in view_specs:
            self.combo.addItem(spec.label, spec.view_id)
        self.combo.currentIndexChanged.connect(self._on_combo_changed)
        self._header.addWidget(self.combo, 1)

        self._outer.addLayout(self._header)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._outer.addWidget(self._content, 1)

    def apply_ui_scale(self, scale: float) -> None:
        """Scale pane chrome that is not governed by QSS."""
        self._outer.setContentsMargins(*([scale_metric(12, scale, reference_scale=DEFAULT_UI_SCALE)] * 4))
        self._outer.setSpacing(scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE))
        self._header.setSpacing(scale_metric(8, scale, reference_scale=DEFAULT_UI_SCALE))

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


class _StaticPane(QFrame):
    """Fixed pane: header label + permanently hosted widget."""

    def __init__(self, *, title: str, widget: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("PaneCard")

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(12, 12, 12, 12)
        self._outer.setSpacing(10)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("PaneTitle")
        title_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._outer.addWidget(title_lbl)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._outer.addWidget(self._content, 1)

        widget.setParent(self._content)
        widget.show()
        self._content_layout.addWidget(widget)

    def apply_ui_scale(self, scale: float) -> None:
        """Scale pane chrome that is not governed by QSS."""
        self._outer.setContentsMargins(*([scale_metric(12, scale, reference_scale=DEFAULT_UI_SCALE)] * 4))
        self._outer.setSpacing(scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE))


class TwoPaneWorkspace(QWidget):
    """A workspace with a fixed left sidebar and two selectable panes."""

    def __init__(
        self,
        *,
        view_specs: List[ViewSpec],
        view_widgets: Dict[str, QWidget],
        left_default: str,
        right_default: str,
        fixed_widget: Optional[QWidget] = None,
        fixed_title: str = "Feeds / Inputs",
        fixed_width: int = 360,
        fixed_min_width: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._view_specs = list(view_specs)
        self._view_widgets = dict(view_widgets)
        self.fixed_pane: Optional[_StaticPane] = None
        self._fixed_width = fixed_width
        self._fixed_min_width = fixed_min_width if fixed_min_width is not None else max(300, fixed_width - 60)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(0)

        self.outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.outer_splitter.setChildrenCollapsible(False)
        self.outer_splitter.setHandleWidth(8)

        if fixed_widget is not None:
            self.fixed_pane = _StaticPane(title=fixed_title, widget=fixed_widget)
            self.fixed_pane.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self.fixed_pane.setMinimumWidth(self._fixed_min_width)
            self.outer_splitter.addWidget(self.fixed_pane)

        self.panes_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.panes_splitter.setChildrenCollapsible(False)
        self.panes_splitter.setHandleWidth(8)

        self.left_pane = _Pane(title="Left", view_specs=self._view_specs)
        self.right_pane = _Pane(title="Right", view_specs=self._view_specs)

        self.left_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.left_pane, vid))
        self.right_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.right_pane, vid))

        self.panes_splitter.addWidget(self.left_pane)
        self.panes_splitter.addWidget(self.right_pane)
        self.panes_splitter.setStretchFactor(0, 1)
        self.panes_splitter.setStretchFactor(1, 1)
        self.panes_splitter.setSizes([640, 480])

        self.outer_splitter.addWidget(self.panes_splitter)
        self.outer_splitter.setStretchFactor(0, 0)
        self.outer_splitter.setStretchFactor(1, 1)
        if self.fixed_pane is not None:
            self.outer_splitter.setSizes([fixed_width, 1120])
        else:
            self.outer_splitter.setSizes([1120])

        self._layout.addWidget(self.outer_splitter, 1)

        # Initialize
        self.left_pane.set_current_view(left_default)
        self.right_pane.set_current_view(right_default)
        self._apply_view_to_pane(self.left_pane, left_default)
        self._apply_view_to_pane(self.right_pane, right_default)
        self._sync_disabled_items()

    def apply_ui_scale(self, scale: float, *, previous_scale: float = DEFAULT_UI_SCALE) -> None:
        """Scale workspace chrome and fixed pane geometry."""
        scaled_margin = scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE)
        self._layout.setContentsMargins(scaled_margin, scaled_margin, scaled_margin, scaled_margin)
        self.outer_splitter.setHandleWidth(scale_metric(8, scale, reference_scale=DEFAULT_UI_SCALE))
        self.panes_splitter.setHandleWidth(scale_metric(8, scale, reference_scale=DEFAULT_UI_SCALE))
        self.left_pane.apply_ui_scale(scale)
        self.right_pane.apply_ui_scale(scale)

        if self.fixed_pane is not None:
            self.fixed_pane.apply_ui_scale(scale)
            self.fixed_pane.setMinimumWidth(
                scale_metric(self._fixed_min_width, scale, reference_scale=DEFAULT_UI_SCALE)
            )
            sizes = self.outer_splitter.sizes()
            if len(sizes) == 2:
                ratio = scale / max(previous_scale, 1e-6)
                fixed_width = max(self.fixed_pane.minimumWidth(), int(round(sizes[0] * ratio)))
                other_width = max(scale_metric(320, scale, reference_scale=DEFAULT_UI_SCALE), int(round(sizes[1] * ratio)))
                self.outer_splitter.setSizes([fixed_width, other_width])

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
