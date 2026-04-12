"""Workspace shell with fixed sidebars and configurable center panes.

Provides a simulator-oriented layout with:
- a stable inputs sidebar on the left
- a stable results sidebar on the right
- one or two configurable center panes for plots, text output, diagnostics, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from pvtapp.style import DEFAULT_THEME, DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.combo_box import NoWheelComboBox

PANE_MODE_SINGLE = "single"
PANE_MODE_DOUBLE = "double"
DEFAULT_OUTER_HANDLE_WIDTH = 0
DEFAULT_DYNAMIC_HANDLE_WIDTH = 8


@dataclass(frozen=True)
class ViewSpec:
    view_id: str
    label: str


class _Pane(QFrame):
    """Single dynamic pane: header (dropdown) + content area."""

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

        self._title_label = QLabel(title)
        self._title_label.setObjectName("PaneTitle")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._header.addWidget(self._title_label)

        self.combo = NoWheelComboBox()
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
        self._outer.setContentsMargins(*([scale_metric(12, scale, reference_scale=DEFAULT_UI_SCALE)] * 4))
        self._outer.setSpacing(scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE))
        self._header.setSpacing(scale_metric(8, scale, reference_scale=DEFAULT_UI_SCALE))
        if self._current_widget is not None and hasattr(self._current_widget, "apply_ui_scale"):
            self._current_widget.apply_ui_scale(scale)

    @property
    def current_view_id(self) -> Optional[str]:
        return self._current_view_id

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_current_view(self, view_id: str) -> None:
        idx = self.combo.findData(view_id)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def set_widget(self, widget: Optional[QWidget]) -> None:
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
        self._hosted_widget = widget

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(12, 12, 12, 12)
        self._outer.setSpacing(10)

        self._title_label = QLabel(title)
        self._title_label.setObjectName("PaneTitle")
        self._title_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._outer.addWidget(self._title_label)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._outer.addWidget(self._content, 1)

        widget.setParent(self._content)
        widget.show()
        self._content_layout.addWidget(widget)

    def apply_ui_scale(self, scale: float) -> None:
        self._outer.setContentsMargins(*([scale_metric(12, scale, reference_scale=DEFAULT_UI_SCALE)] * 4))
        self._outer.setSpacing(scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE))
        if hasattr(self._hosted_widget, "apply_ui_scale"):
            self._hosted_widget.apply_ui_scale(scale)


class TwoPaneWorkspace(QWidget):
    """Workspace shell with fixed sidebars and configurable center panes."""

    pane_mode_changed = Signal(str)
    theme_mode_changed = Signal(str)

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
        fixed_right_widget: Optional[QWidget] = None,
        fixed_right_title: str = "Results",
        fixed_right_width: int = 440,
        default_pane_mode: str = PANE_MODE_SINGLE,
        default_theme_mode: str = DEFAULT_THEME,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._view_specs = list(view_specs)
        self._view_widgets = dict(view_widgets)
        self.fixed_pane: Optional[_StaticPane] = None
        self.results_pane: Optional[_StaticPane] = None
        self._base_fixed_width = fixed_width
        self._base_fixed_right_width = fixed_right_width
        self._fixed_width = fixed_width
        self._fixed_right_width = fixed_right_width
        self._pane_mode = PANE_MODE_DOUBLE
        self._theme_mode = default_theme_mode
        self._dynamic_handle_width = DEFAULT_DYNAMIC_HANDLE_WIDTH
        self._double_splitter_sizes: List[int] = [640, 480]

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setSpacing(0)

        self.outer_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.outer_splitter.setChildrenCollapsible(False)
        self.outer_splitter.setHandleWidth(DEFAULT_OUTER_HANDLE_WIDTH)

        if fixed_widget is not None:
            self.fixed_pane = _StaticPane(title=fixed_title, widget=fixed_widget)
            self.fixed_pane.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.fixed_pane.setMinimumWidth(self._fixed_width)
            self.fixed_pane.setMaximumWidth(self._fixed_width)
            self.outer_splitter.addWidget(self.fixed_pane)

        self.center_shell = QWidget()
        self.center_layout = QVBoxLayout(self.center_shell)
        self.center_layout.setContentsMargins(10, 0, 10, 0)
        self.center_layout.setSpacing(10)

        self._build_controls_row()

        self.panes_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.panes_splitter.setChildrenCollapsible(False)
        self.panes_splitter.setHandleWidth(self._dynamic_handle_width)

        self.left_pane = _Pane(title="Primary", view_specs=self._view_specs)
        self.right_pane = _Pane(title="Secondary", view_specs=self._view_specs)
        self.left_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.left_pane, vid))
        self.right_pane.view_changed.connect(lambda vid: self._on_pane_changed(self.right_pane, vid))

        self.panes_splitter.addWidget(self.left_pane)
        self.panes_splitter.addWidget(self.right_pane)
        self.panes_splitter.setStretchFactor(0, 1)
        self.panes_splitter.setStretchFactor(1, 1)
        self.panes_splitter.setSizes(self._double_splitter_sizes)
        self.center_layout.addWidget(self.panes_splitter, 1)

        self.outer_splitter.addWidget(self.center_shell)
        self.outer_splitter.setStretchFactor(0, 0)
        self.outer_splitter.setStretchFactor(1, 1)

        if fixed_right_widget is not None:
            self.results_pane = _StaticPane(title=fixed_right_title, widget=fixed_right_widget)
            self.results_pane.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
            self.results_pane.setMinimumWidth(self._fixed_right_width)
            self.results_pane.setMaximumWidth(self._fixed_right_width)
            self.outer_splitter.addWidget(self.results_pane)
            self.outer_splitter.setStretchFactor(2, 0)

        self._layout.addWidget(self.outer_splitter, 1)

        self.left_pane.set_current_view(left_default)
        self.right_pane.set_current_view(right_default)
        self._apply_view_to_pane(self.left_pane, left_default)
        self._apply_view_to_pane(self.right_pane, right_default)
        self._sync_disabled_items()

        self._sync_outer_splitter_sizes()
        self._sync_outer_handle_affordance()
        self.set_pane_mode(default_pane_mode, emit_signal=False)
        self.set_theme_mode(default_theme_mode, emit_signal=False)

    @property
    def pane_mode(self) -> str:
        return self._pane_mode

    @property
    def theme_mode(self) -> str:
        return self._theme_mode

    def _build_controls_row(self) -> None:
        self.controls_row = QHBoxLayout()
        self.controls_row.setContentsMargins(0, 0, 0, 0)
        self.controls_row.setSpacing(8)

        outputs_label = QLabel("Outputs")
        outputs_label.setObjectName("PaneTitle")
        self.controls_row.addWidget(outputs_label)

        self.single_mode_btn = self._build_toggle_button("Single")
        self.double_mode_btn = self._build_toggle_button("Double")
        self._pane_mode_group = QButtonGroup(self)
        self._pane_mode_group.setExclusive(True)
        self._pane_mode_group.addButton(self.single_mode_btn)
        self._pane_mode_group.addButton(self.double_mode_btn)
        self.single_mode_btn.clicked.connect(lambda: self.set_pane_mode(PANE_MODE_SINGLE))
        self.double_mode_btn.clicked.connect(lambda: self.set_pane_mode(PANE_MODE_DOUBLE))
        self.controls_row.addWidget(self.single_mode_btn)
        self.controls_row.addWidget(self.double_mode_btn)

        self.controls_row.addSpacing(12)

        theme_label = QLabel("Palette")
        theme_label.setObjectName("PaneTitle")
        self.controls_row.addWidget(theme_label)

        self.dark_theme_btn = self._build_toggle_button("Dark")
        self.slate_theme_btn = self._build_toggle_button("Slate")
        self._theme_mode_group = QButtonGroup(self)
        self._theme_mode_group.setExclusive(True)
        self._theme_mode_group.addButton(self.dark_theme_btn)
        self._theme_mode_group.addButton(self.slate_theme_btn)
        self.dark_theme_btn.clicked.connect(lambda: self.set_theme_mode("dark"))
        self.slate_theme_btn.clicked.connect(lambda: self.set_theme_mode("slate"))
        self.controls_row.addWidget(self.dark_theme_btn)
        self.controls_row.addWidget(self.slate_theme_btn)
        self.controls_row.addStretch(1)

        self.center_layout.addLayout(self.controls_row)

    @staticmethod
    def _build_toggle_button(label: str) -> QToolButton:
        button = QToolButton()
        button.setText(label)
        button.setCheckable(True)
        button.setAutoRaise(False)
        return button

    def apply_ui_scale(self, scale: float, *, previous_scale: float = DEFAULT_UI_SCALE) -> None:
        del previous_scale
        self._fixed_width = scale_metric(
            self._base_fixed_width,
            scale,
            reference_scale=DEFAULT_UI_SCALE,
        )
        self._fixed_right_width = scale_metric(
            self._base_fixed_right_width,
            scale,
            reference_scale=DEFAULT_UI_SCALE,
        )
        scaled_margin = scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE)
        self._layout.setContentsMargins(scaled_margin, scaled_margin, scaled_margin, scaled_margin)
        self.center_layout.setContentsMargins(scaled_margin, 0, scaled_margin, 0)
        self.center_layout.setSpacing(scale_metric(10, scale, reference_scale=DEFAULT_UI_SCALE))
        self.controls_row.setSpacing(scale_metric(8, scale, reference_scale=DEFAULT_UI_SCALE))
        self.outer_splitter.setHandleWidth(DEFAULT_OUTER_HANDLE_WIDTH)
        self._dynamic_handle_width = scale_metric(
            DEFAULT_DYNAMIC_HANDLE_WIDTH,
            scale,
            reference_scale=DEFAULT_UI_SCALE,
        )
        self.panes_splitter.setHandleWidth(
            self._dynamic_handle_width if self._pane_mode == PANE_MODE_DOUBLE else 0
        )
        self.left_pane.apply_ui_scale(scale)
        self.right_pane.apply_ui_scale(scale)

        if self.fixed_pane is not None:
            self.fixed_pane.apply_ui_scale(scale)
            self.fixed_pane.setMinimumWidth(self._fixed_width)
            self.fixed_pane.setMaximumWidth(self._fixed_width)
        if self.results_pane is not None:
            self.results_pane.apply_ui_scale(scale)
            self.results_pane.setMinimumWidth(self._fixed_right_width)
            self.results_pane.setMaximumWidth(self._fixed_right_width)
        self._sync_outer_splitter_sizes()
        self._sync_outer_handle_affordance()

    def set_pane_mode(self, mode: str, *, emit_signal: bool = True) -> None:
        if mode not in {PANE_MODE_SINGLE, PANE_MODE_DOUBLE}:
            raise ValueError(f"Unsupported pane mode: {mode}")

        if mode == PANE_MODE_DOUBLE and self.left_pane.current_view_id == self.right_pane.current_view_id:
            for spec in self._view_specs:
                if spec.view_id != self.left_pane.current_view_id:
                    self.right_pane.set_current_view(spec.view_id)
                    self._apply_view_to_pane(self.right_pane, spec.view_id)
                    break

        if self._pane_mode == PANE_MODE_DOUBLE:
            sizes = self.panes_splitter.sizes()
            if len(sizes) == 2 and any(size > 0 for size in sizes):
                self._double_splitter_sizes = sizes

        self._pane_mode = mode
        self.single_mode_btn.setChecked(mode == PANE_MODE_SINGLE)
        self.double_mode_btn.setChecked(mode == PANE_MODE_DOUBLE)
        self.right_pane.setVisible(mode == PANE_MODE_DOUBLE)
        self.panes_splitter.setHandleWidth(self._dynamic_handle_width if mode == PANE_MODE_DOUBLE else 0)

        if mode == PANE_MODE_SINGLE:
            self.left_pane.set_title("Output")
            self.panes_splitter.setSizes([1, 0])
        else:
            self.left_pane.set_title("Primary")
            self.panes_splitter.setSizes(self._double_splitter_sizes)

        self._sync_disabled_items()
        if emit_signal:
            self.pane_mode_changed.emit(mode)

    def set_theme_mode(self, theme: str, *, emit_signal: bool = True) -> None:
        self._theme_mode = theme
        self.dark_theme_btn.setChecked(theme == "dark")
        self.slate_theme_btn.setChecked(theme == "slate")
        if emit_signal:
            self.theme_mode_changed.emit(theme)

    def _sync_outer_splitter_sizes(self) -> None:
        sizes: list[int] = []
        if self.fixed_pane is not None:
            sizes.append(self._fixed_width)
        sizes.append(1200)
        if self.results_pane is not None:
            sizes.append(self._fixed_right_width)
        self.outer_splitter.setSizes(sizes)

    def _sync_outer_handle_affordance(self) -> None:
        """Keep fixed-sidebar splitter handles visually passive."""
        for index in range(1, self.outer_splitter.count()):
            handle = self.outer_splitter.handle(index)
            if handle is not None:
                handle.setCursor(Qt.CursorShape.ArrowCursor)

    def _on_pane_changed(self, pane: _Pane, view_id: str) -> None:
        self._apply_view_to_pane(pane, view_id)
        self._sync_disabled_items()

    def _apply_view_to_pane(self, pane: _Pane, view_id: str) -> None:
        pane.set_widget(self._view_widgets.get(view_id))

    def _sync_disabled_items(self) -> None:
        left = self.left_pane.current_view_id
        right = self.right_pane.current_view_id

        for spec in self._view_specs:
            self.left_pane.set_item_enabled(spec.view_id, True)
            self.right_pane.set_item_enabled(spec.view_id, True)

        if self._pane_mode != PANE_MODE_DOUBLE:
            return

        if isinstance(right, str):
            self.left_pane.set_item_enabled(right, False)
        if isinstance(left, str):
            self.right_pane.set_item_enabled(left, False)
