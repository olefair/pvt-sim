"""Run log / history view with a plot preview.

This keeps the middle pane focused on:
- a sortable list of saved runs
- a plot preview for the selected run
"""

from __future__ import annotations

import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
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
from pvtapp.widgets.combo_box import NoWheelComboBox
from pvtapp.widgets.results_view import ResultsPlotWidget
from pvtapp.widgets.text_output_view import format_eos_label


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


class RunLogWidget(QWidget):
    """Show a run history tree and preview the selected run."""

    load_inputs_requested = Signal(str)
    result_selected = Signal(object)
    result_activated = Signal(object)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._selected_run_dir: Optional[Path] = None
        self._selected_result: Optional[RunResult] = None
        self._replay_actions_enabled = True
        self._preview_split_fraction = 0.58
        self._sort_column = 2
        self._sort_order = Qt.SortOrder.DescendingOrder
        self._group_by = "none"
        self._entries: list[dict[str, object]] = []

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

        self.group_by_label = QLabel("Group by")
        self._header.addWidget(self.group_by_label)

        self.group_by_combo = NoWheelComboBox()
        self.group_by_combo.addItem("None", "none")
        self.group_by_combo.addItem("Test Type", "calc_type")
        self.group_by_combo.addItem("Status", "status")
        self.group_by_combo.currentIndexChanged.connect(self._on_group_by_changed)
        self._header.addWidget(self.group_by_combo)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        self._header.addWidget(self.refresh_btn)

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_runs)
        self._header.addWidget(self.select_all_btn)

        self.load_inputs_btn = QPushButton("Load Inputs")
        self.load_inputs_btn.clicked.connect(self._emit_load_inputs_requested)
        self._header.addWidget(self.load_inputs_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.clicked.connect(self._export_selected)
        self._header.addWidget(self.export_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_selected)
        self._header.addWidget(self.delete_btn)

        self._layout.addLayout(self._header)

        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setChildrenCollapsible(False)

        # Run tree
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Run", "Status", "When", "EOS"])
        self.tree.setUniformRowHeights(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setSortingEnabled(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setToolTip("Shift-click or Ctrl-click to select multiple runs.")
        self.tree.header().setSortIndicatorShown(True)
        self.tree.header().setSortIndicator(self._sort_column, self._sort_order)
        self.tree.header().sectionClicked.connect(self._on_header_clicked)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self._splitter.addWidget(self.tree)

        # Preview area (plot only)
        self._preview_panel = QWidget()
        self._preview_layout = QVBoxLayout(self._preview_panel)
        self._preview_layout.setContentsMargins(0, 0, 0, 0)
        self._preview_layout.setSpacing(10)

        self.preview_title = QLabel("Select a run to preview")
        self.preview_title.setWordWrap(True)
        self.preview_title.setStyleSheet("color: #9ca3af;")
        self._preview_layout.addWidget(self.preview_title)

        self.preview_plot = ResultsPlotWidget()
        self._preview_layout.addWidget(self.preview_plot, 2)

        self._splitter.addWidget(self._preview_panel)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 2)

        self._layout.addWidget(self._splitter, 1)

        self._set_preview(None, None)
        self._sync_action_state()
        self.refresh()

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Forward app zoom to preview widgets that expose sizing hooks."""
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._header.setSpacing(scale_metric(8, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self._preview_layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))

    def refresh(self) -> None:
        """Reload the run tree from the runs directory."""
        selected_run_path = str(self._selected_run_dir) if self._selected_run_dir is not None else None
        runs = list_runs(limit=200)
        entries: list[dict[str, object]] = []

        for run in runs:
            run_dir = Path(run.get("path", ""))
            result = load_run_result(run_dir)
            if result is None:
                continue

            entries.append(
                {
                    "path": run_dir,
                    "result": result,
                    "name": result.run_name or result.run_id,
                    "status": result.status.value,
                    "when": _fmt_dt(result.completed_at or result.started_at),
                    "when_dt": result.completed_at or result.started_at,
                    "calc_type": result.config.calculation_type.value.replace("_", " ").title(),
                    "eos": format_eos_label(result.config.eos_type),
                }
            )

        self._entries = entries
        selected_item = self._rebuild_tree(selected_run_path)

        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
            self._load_item_preview(selected_item)
        elif self._selected_run_dir is not None or self._selected_result is not None:
            self._set_preview(None, None)
        self._sync_action_state()

    def set_replay_actions_enabled(self, enabled: bool) -> None:
        """Enable or disable actions that reuse saved run artifacts."""
        self._replay_actions_enabled = enabled
        self._sync_action_state()

    def _on_selection_changed(self) -> None:
        items = self._selected_run_items()
        if not items:
            self._set_preview(None, None)
            return

        current_item = self.tree.currentItem()
        if current_item in items:
            target_item = current_item
        elif self._selected_run_dir is not None:
            target_item = next(
                (
                    item
                    for item in items
                    if str(item.data(0, Qt.ItemDataRole.UserRole)) == str(self._selected_run_dir)
                ),
                items[0],
            )
        else:
            target_item = items[0]

        if str(target_item.data(0, Qt.ItemDataRole.UserRole)) != str(self._selected_run_dir):
            self._load_item_preview(target_item)
            return
        self._sync_action_state()

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        """Handle explicit user clicks even if the clicked row was already selected."""
        if not item.data(0, Qt.ItemDataRole.UserRole):
            item.setExpanded(not item.isExpanded())
            return
        self._load_item_preview(item)
        self.result_activated.emit(self._selected_result)

    def _on_group_by_changed(self, _index: int) -> None:
        """Regroup the run list without changing the current sort column/order."""
        self._group_by = str(self.group_by_combo.currentData() or "none")
        selected_run_path = str(self._selected_run_dir) if self._selected_run_dir is not None else None
        selected_item = self._rebuild_tree(selected_run_path)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)
        elif self._selected_run_dir is not None or self._selected_result is not None:
            self._set_preview(None, None)

    def _on_header_clicked(self, section: int) -> None:
        """Toggle manual sorting so grouped and flat views behave consistently."""
        if self._sort_column == section:
            self._sort_order = (
                Qt.SortOrder.AscendingOrder
                if self._sort_order == Qt.SortOrder.DescendingOrder
                else Qt.SortOrder.DescendingOrder
            )
        else:
            self._sort_column = section
            self._sort_order = (
                Qt.SortOrder.DescendingOrder
                if section == 2
                else Qt.SortOrder.AscendingOrder
            )
        self.tree.header().setSortIndicator(self._sort_column, self._sort_order)
        selected_run_path = str(self._selected_run_dir) if self._selected_run_dir is not None else None
        selected_item = self._rebuild_tree(selected_run_path)
        if selected_item is not None:
            self.tree.setCurrentItem(selected_item)

    def _entry_sort_key(self, entry: dict[str, object]) -> object:
        """Return the active Python sort key for a run entry."""
        if self._sort_column == 0:
            return str(entry["name"]).casefold()
        if self._sort_column == 1:
            return str(entry["status"]).casefold()
        if self._sort_column == 3:
            return str(entry["eos"]).casefold()
        when_dt = entry["when_dt"]
        return when_dt or datetime.min

    def _sorted_entries(self) -> list[dict[str, object]]:
        """Return entries sorted by the active header sort selection."""
        reverse = self._sort_order == Qt.SortOrder.DescendingOrder
        return sorted(self._entries, key=self._entry_sort_key, reverse=reverse)

    def _group_label(self, entry: dict[str, object]) -> str:
        """Return the visible group label for a run entry."""
        if self._group_by == "calc_type":
            return str(entry["calc_type"])
        if self._group_by == "status":
            return str(entry["status"]).replace("_", " ").title()
        return ""

    def _build_run_item(self, entry: dict[str, object]) -> QTreeWidgetItem:
        """Create a concrete selectable run row."""
        item = QTreeWidgetItem(
            [
                str(entry["name"]),
                str(entry["status"]),
                str(entry["when"]),
                str(entry["eos"]),
            ]
        )
        item.setData(0, Qt.ItemDataRole.UserRole, str(entry["path"]))
        item.setToolTip(0, str(entry["calc_type"]))
        return item

    def _rebuild_tree(self, selected_run_path: Optional[str]) -> Optional[QTreeWidgetItem]:
        """Rebuild the tree using the current grouping and sorting rules."""
        self.tree.clear()
        self.tree.setRootIsDecorated(self._group_by != "none")
        selected_item: Optional[QTreeWidgetItem] = None
        entries = self._sorted_entries()

        if self._group_by == "none":
            for entry in entries:
                item = self._build_run_item(entry)
                self.tree.addTopLevelItem(item)
                if selected_run_path is not None and str(entry["path"]) == selected_run_path:
                    selected_item = item
            return selected_item

        groups: dict[str, list[dict[str, object]]] = {}
        for entry in entries:
            group = self._group_label(entry)
            groups.setdefault(group, []).append(entry)

        for group_name in sorted(groups.keys(), key=str.casefold):
            group_item = QTreeWidgetItem([group_name, "", ""])
            group_item.setFirstColumnSpanned(True)
            group_item.setFlags(group_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            group_item.setExpanded(True)
            self.tree.addTopLevelItem(group_item)

            for entry in groups[group_name]:
                item = self._build_run_item(entry)
                group_item.addChild(item)
                if selected_run_path is not None and str(entry["path"]) == selected_run_path:
                    selected_item = item

        return selected_item

    def _load_item_preview(self, item: QTreeWidgetItem) -> None:
        """Load the saved result for a concrete tree item."""
        run_dir_str = item.data(0, Qt.ItemDataRole.UserRole)
        if not run_dir_str:
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
            self._preview_panel.setVisible(False)
            self._splitter.setSizes([1, 0])
            self._sync_action_state()
            self.result_selected.emit(None)
            return

        preview_was_hidden = not self._preview_panel.isVisible()
        self._preview_panel.setVisible(True)
        calc_type = result.config.calculation_type.value.replace("_", " ").title()
        self.preview_title.setText(
            f"{calc_type} — {result.run_name or result.run_id} ({result.status.value}) | "
            f"EOS: {format_eos_label(result.config.eos_type)}"
        )
        self.preview_plot.display_result(result)
        if preview_was_hidden:
            total_height = max(self._splitter.height(), self.height(), 1)
            preview_height = max(1, int(total_height * self._preview_split_fraction))
            tree_height = max(1, total_height - preview_height)
            self._splitter.setSizes([tree_height, preview_height])
        self._sync_action_state()
        self.result_selected.emit(result)

    def _sync_action_state(self) -> None:
        selected_count = len(self._selected_run_items())
        has_selected_run = self._selected_run_dir is not None and self._selected_result is not None
        self.select_all_btn.setEnabled(bool(self._entries))
        self.load_inputs_btn.setEnabled(
            has_selected_run and selected_count <= 1 and self._replay_actions_enabled
        )
        self.export_btn.setEnabled(selected_count > 0)
        self.delete_btn.setEnabled(selected_count > 0)

    def _selected_run_items(self) -> list[QTreeWidgetItem]:
        """Return the currently selected concrete run rows."""
        return [
            item
            for item in self.tree.selectedItems()
            if item.data(0, Qt.ItemDataRole.UserRole)
        ]

    def _selected_run_dirs(self) -> list[Path]:
        """Return selected run directories in tree order without duplicates."""
        selected: list[Path] = []
        seen: set[str] = set()
        for item in self._selected_run_items():
            run_dir_str = str(item.data(0, Qt.ItemDataRole.UserRole))
            if not run_dir_str or run_dir_str in seen:
                continue
            seen.add(run_dir_str)
            selected.append(Path(run_dir_str))
        return selected

    def _emit_load_inputs_requested(self) -> None:
        if self._selected_run_dir is None or not self._replay_actions_enabled:
            return
        self.load_inputs_requested.emit(str(self._selected_run_dir))

    def _select_all_runs(self) -> None:
        if not self._entries:
            return
        self.tree.selectAll()

    def _export_selected(self) -> None:
        run_dirs = self._selected_run_dirs()
        if not run_dirs:
            return

        default_name = (
            "pvt-sim-runs.zip"
            if len(run_dirs) > 1
            else f"{run_dirs[0].name}.zip"
        )
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Selected Runs",
            default_name,
            "ZIP Files (*.zip)",
        )
        if not filename:
            return

        archive_path = Path(filename)
        if archive_path.suffix.lower() != ".zip":
            archive_path = archive_path.with_suffix(".zip")

        try:
            self._write_selected_runs_archive(run_dirs, archive_path)
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def _write_selected_runs_archive(self, run_dirs: list[Path], archive_path: Path) -> None:
        """Bundle selected run artifact directories into a single zip archive."""
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for run_dir in run_dirs:
                for path in sorted(run_dir.rglob("*")):
                    if not path.is_file():
                        continue
                    archive.write(path, arcname=Path(run_dir.name) / path.relative_to(run_dir))

    def _delete_selected(self) -> None:
        run_dirs = self._selected_run_dirs()
        if not run_dirs:
            return

        if len(run_dirs) == 1:
            title = "Delete run"
            body = f"Delete run folder?\n\n{run_dirs[0]}"
        else:
            preview = "\n".join(str(path) for path in run_dirs[:5])
            suffix = "" if len(run_dirs) <= 5 else f"\n... and {len(run_dirs) - 5} more"
            title = "Delete runs"
            body = f"Delete {len(run_dirs)} run folders?\n\n{preview}{suffix}"

        reply = QMessageBox.question(
            self,
            title,
            body,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        failures: list[str] = []
        for run_dir in run_dirs:
            try:
                shutil.rmtree(run_dir)
            except Exception as exc:
                failures.append(f"{run_dir}: {exc}")
        if failures:
            QMessageBox.critical(self, "Delete failed", "\n".join(failures))
            return

        self._set_preview(None, None)
        self.refresh()
