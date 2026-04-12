"""Workspace layout regressions for the fixed-inputs shell."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QSplitter, QWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    Qt = None  # type: ignore[assignment]
    QApplication = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QSplitter = None  # type: ignore[assignment]
    QWidget = None  # type: ignore[assignment]

try:
    from pvtapp.widgets.two_pane_workspace import TwoPaneWorkspace, ViewSpec
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    TwoPaneWorkspace = None  # type: ignore[assignment]
    ViewSpec = None  # type: ignore[assignment]

from pvtapp.style import DEFAULT_UI_SCALE, scale_metric


@pytest.fixture(scope="module")
def app() -> QApplication:
    if QApplication is None or TwoPaneWorkspace is None or QLabel is None or QWidget is None:
        pytest.skip("PySide6 is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_workspace_uses_fixed_sidebars_and_defaults_to_single_center_pane(app: QApplication) -> None:
    fixed_inputs = QLabel("inputs")
    fixed_results = QLabel("results")
    view_specs = [
        ViewSpec("critical_props", "Critical prop."),
        ViewSpec("phase_envelope", "Phase Envelope"),
        ViewSpec("text_output", "Text output"),
    ]
    view_widgets = {
        "critical_props": QWidget(),
        "phase_envelope": QWidget(),
        "text_output": QWidget(),
    }

    workspace = TwoPaneWorkspace(
        view_specs=view_specs,
        view_widgets=view_widgets,
        left_default="text_output",
        right_default="phase_envelope",
        fixed_widget=fixed_inputs,
        fixed_title="Feeds / Inputs",
        fixed_width=360,
        fixed_right_widget=fixed_results,
        fixed_right_title="Results table",
        fixed_right_width=340,
        default_pane_mode="single",
    )

    assert workspace.fixed_pane is not None
    assert workspace.results_pane is not None
    assert isinstance(workspace.outer_splitter, QSplitter)
    assert workspace.fixed_pane.minimumWidth() == 360
    assert workspace.fixed_pane.maximumWidth() == 360
    assert workspace.results_pane.minimumWidth() == 340
    assert workspace.results_pane.maximumWidth() == 340
    assert workspace.outer_splitter.count() == 3
    assert workspace.outer_splitter.handleWidth() == 0
    for handle_index in range(1, workspace.outer_splitter.count()):
        assert workspace.outer_splitter.handle(handle_index).cursor().shape() == Qt.CursorShape.ArrowCursor

    left_labels = [workspace.left_pane.combo.itemText(i) for i in range(workspace.left_pane.combo.count())]
    right_labels = [workspace.right_pane.combo.itemText(i) for i in range(workspace.right_pane.combo.count())]

    assert "Feeds / Inputs" not in left_labels
    assert "Feeds / Inputs" not in right_labels
    assert workspace.left_pane.current_view_id == "text_output"
    assert workspace.right_pane.current_view_id == "phase_envelope"
    assert workspace.pane_mode == "single"
    assert workspace.right_pane.isHidden()

def test_workspace_scale_resizes_fixed_sidebars_and_updates_handles(app: QApplication) -> None:
    workspace = TwoPaneWorkspace(
        view_specs=[
            ViewSpec("critical_props", "Critical prop."),
            ViewSpec("phase_envelope", "Phase Envelope"),
        ],
        view_widgets={
            "critical_props": QWidget(),
            "phase_envelope": QWidget(),
        },
        left_default="critical_props",
        right_default="phase_envelope",
        fixed_widget=QLabel("inputs"),
        fixed_title="Feeds / Inputs",
        fixed_width=360,
        fixed_right_widget=QLabel("results"),
        fixed_right_title="Results table",
        fixed_right_width=340,
    )

    assert workspace.fixed_pane is not None
    initial_min_width = workspace.fixed_pane.minimumWidth()
    initial_results_width = workspace.results_pane.minimumWidth() if workspace.results_pane is not None else 0
    scaled_ui = DEFAULT_UI_SCALE + 0.2

    workspace.apply_ui_scale(scaled_ui, previous_scale=DEFAULT_UI_SCALE)

    assert workspace.fixed_pane.minimumWidth() == scale_metric(
        initial_min_width,
        scaled_ui,
        reference_scale=DEFAULT_UI_SCALE,
    )
    assert workspace.results_pane is not None
    assert workspace.results_pane.minimumWidth() == scale_metric(
        initial_results_width,
        scaled_ui,
        reference_scale=DEFAULT_UI_SCALE,
    )
    assert workspace.outer_splitter.handleWidth() == 0
    for handle_index in range(1, workspace.outer_splitter.count()):
        assert workspace.outer_splitter.handle(handle_index).cursor().shape() == Qt.CursorShape.ArrowCursor


def test_workspace_can_toggle_between_single_and_double_center_panes(app: QApplication) -> None:
    workspace = TwoPaneWorkspace(
        view_specs=[
            ViewSpec("critical_props", "Critical prop."),
            ViewSpec("phase_envelope", "Phase Envelope"),
            ViewSpec("text_output", "Text output"),
        ],
        view_widgets={
            "critical_props": QWidget(),
            "phase_envelope": QWidget(),
            "text_output": QWidget(),
        },
        left_default="text_output",
        right_default="phase_envelope",
        fixed_widget=QLabel("inputs"),
        fixed_right_widget=QLabel("results"),
        default_pane_mode="single",
    )

    workspace.set_pane_mode("double")

    assert workspace.pane_mode == "double"
    assert not workspace.right_pane.isHidden()
    assert workspace.panes_splitter.handleWidth() > 0
