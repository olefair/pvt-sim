"""Workspace layout regressions for the fixed-inputs shell."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication, QLabel, QSplitter, QWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]
    QLabel = None  # type: ignore[assignment]
    QSplitter = None  # type: ignore[assignment]
    QWidget = None  # type: ignore[assignment]

try:
    from pvtapp.widgets.two_pane_workspace import TwoPaneWorkspace, ViewSpec
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    TwoPaneWorkspace = None  # type: ignore[assignment]
    ViewSpec = None  # type: ignore[assignment]

from pvtapp.style import DEFAULT_UI_SCALE


@pytest.fixture(scope="module")
def app() -> QApplication:
    if QApplication is None or TwoPaneWorkspace is None or QLabel is None or QWidget is None:
        pytest.skip("PySide6 is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def test_workspace_uses_resizable_inputs_sidebar_and_removes_inputs_dropdown(app: QApplication) -> None:
    fixed_inputs = QLabel("inputs")
    view_specs = [
        ViewSpec("critical_props", "Critical prop."),
        ViewSpec("results_table", "Results table"),
        ViewSpec("phase_envelope", "Phase Envelope"),
    ]
    view_widgets = {
        "critical_props": QWidget(),
        "results_table": QWidget(),
        "phase_envelope": QWidget(),
    }

    workspace = TwoPaneWorkspace(
        view_specs=view_specs,
        view_widgets=view_widgets,
        left_default="phase_envelope",
        right_default="results_table",
        fixed_widget=fixed_inputs,
        fixed_title="Feeds / Inputs",
        fixed_width=360,
    )

    assert workspace.fixed_pane is not None
    assert isinstance(workspace.outer_splitter, QSplitter)
    assert workspace.fixed_pane.minimumWidth() < 360
    assert workspace.fixed_pane.maximumWidth() > 360
    assert workspace.outer_splitter.count() == 2

    left_labels = [workspace.left_pane.combo.itemText(i) for i in range(workspace.left_pane.combo.count())]
    right_labels = [workspace.right_pane.combo.itemText(i) for i in range(workspace.right_pane.combo.count())]

    assert "Feeds / Inputs" not in left_labels
    assert "Feeds / Inputs" not in right_labels
    assert workspace.left_pane.current_view_id == "phase_envelope"
    assert workspace.right_pane.current_view_id == "results_table"


def test_workspace_scale_updates_fixed_sidebar_and_splitter_handles(app: QApplication) -> None:
    workspace = TwoPaneWorkspace(
        view_specs=[
            ViewSpec("critical_props", "Critical prop."),
            ViewSpec("results_table", "Results table"),
        ],
        view_widgets={
            "critical_props": QWidget(),
            "results_table": QWidget(),
        },
        left_default="critical_props",
        right_default="results_table",
        fixed_widget=QLabel("inputs"),
        fixed_title="Feeds / Inputs",
        fixed_width=360,
    )

    assert workspace.fixed_pane is not None
    initial_min_width = workspace.fixed_pane.minimumWidth()
    initial_handle_width = workspace.outer_splitter.handleWidth()

    workspace.apply_ui_scale(DEFAULT_UI_SCALE + 0.2, previous_scale=DEFAULT_UI_SCALE)

    assert workspace.fixed_pane.minimumWidth() > initial_min_width
    assert workspace.outer_splitter.handleWidth() > initial_handle_width
