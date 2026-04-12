"""Run log / history view with preview.

This is intended to mirror the MI-PVT "Log" tab concept:
- A tree of prior runs
- Selecting a run previews its results (plot) for side-by-side comparisons
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvtapp.job_runner import list_runs, load_run_result
from pvtapp.schemas import RunResult
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.widgets.results_view import ResultsPlotWidget
from pvtapp.widgets.text_output_view import TextOutputWidget


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


class RunLogWidget(QWidget):
    """Show a run history tree and preview the selected run."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected_run_dir: Optional[Path] = None
        self._selected_result: Optional[RunResult] = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

        # Header row
        self._header = QHBoxLayout()
        self._header.setContentsMargins(0, 0, 0, 0)
        self._header.setSpacing(8)

        title = QLabel("Run log (local runs)")
        title.setStyleSheet("color: #9ca3af;")
        self._header.addWidget(title, 1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self._header.addWidget(self.refresh_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected)
        self._header.addWidget(self.delete_btn)

        self._layout.addLayout(self._header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)

        # Run tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Run", "Status", "When"])
        self.tree.setUniformRowHeights(True)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.tree)

        # Preview area (plot + text)
        preview = QWidget()
        self._preview_layout = QVBoxLayout(preview)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(10)

        self.preview_title = QLabel("Select a run to preview")
        self.preview_title.setWordWrap(True)
        self.preview_title.setStyleSheet("color: #9ca3af;")
        self._preview_layout.addWidget(self.preview_title)

        self.preview_plot = ResultsPlotWidget()
        self._preview_layout.addWidget(self.preview_plot, 2)

        self.preview_text = TextOutputWidget()
        self._preview_layout.addWidget(self.preview_text, 1)

        splitter.addWidget(preview)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        self._layout.addWidget(splitter, 1)

        self.refresh()

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Forward app zoom to preview widgets that expose sizing hooks."""
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._header.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._preview_layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        if hasattr(self.preview_text, "apply_ui_scale"):
            self.preview_text.apply_ui_scale(ui_scale)

    def refresh(self) -> None:
        """Reload the run tree from the runs directory."""
        self.tree.clear()

        runs = list_runs(limit=200)
        groups: dict[str, QTreeWidgetItem] = {}

        for run in runs:
            run_dir = Path(run.get("path", ""))
            result = load_run_result(run_dir)
            if result is None:
                continue

            calc_type = result.config.calculation_type.value.replace("_", " ").title()
            group_item = groups.get(calc_type)
            if group_item is None:
                group_item = QTreeWidgetItem([calc_type, "", ""])
                group_item.setFirstColumnSpanned(False)
                self.tree.addTopLevelItem(group_item)
                groups[calc_type] = group_item

            name = result.run_name or result.run_id
            status = result.status.value
            when = _fmt_dt(result.completed_at or result.started_at)

            item = QTreeWidgetItem([name, status, when])
            item.setData(0, Qt.ItemDataRole.UserRole, str(run_dir))
            group_item.addChild(item)

        self.tree.expandAll()

    def _on_selection_changed(self) -> None:
        items = self.tree.selectedItems()
        if not items:
            self._set_preview(None, None)
            return

        item = items[0]
        run_dir_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not run_dir_str:
            # Selected a group header
            self._set_preview(None, None)
            return

        run_dir = Path(str(run_dir_str))
        result = load_run_result(run_dir)
        self._set_preview(run_dir, result)

    def _set_preview(self, run_dir: Optional[Path], result: Optional[RunResult]) -> None:
        self._selected_run_dir = run_dir
        self._selected_result = result

        if run_dir is None or result is None:
            self.preview_title.setText("Select a run to preview")
            self.preview_plot.clear()
            self.preview_text.clear()
            return

        calc_type = result.config.calculation_type.value.replace("_", " ").title()
        self.preview_title.setText(
            f"{calc_type} — {result.run_name or result.run_id}  ({result.status.value})"
        )
        self.preview_plot.display_result(result)
        self.preview_text.display_result(result)

    def _delete_selected(self) -> None:
        if self._selected_run_dir is None:
            return

        run_dir = self._selected_run_dir
        reply = QMessageBox.question(
            self,
            "Delete run",
            f"Delete run folder?\n\n{run_dir}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            shutil.rmtree(run_dir)
        except Exception as e:
            QMessageBox.critical(self, "Delete failed", str(e))
            return

        self._set_preview(None, None)
        self.refresh()
