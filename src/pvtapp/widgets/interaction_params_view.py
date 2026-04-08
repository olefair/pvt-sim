"""Interaction parameters (BIP) view."""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvtcore.characterization.bip import BIPMethod, build_bip_matrix
from pvtcore.models.component import Component


class InteractionParamsWidget(QWidget):
    """Display binary interaction parameters (kij) for selected components."""

    def __init__(
        self,
        components_db: Dict[str, Component],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = components_db
        self._component_ids: List[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._hint = QLabel("Binary interaction parameters (kᵢⱼ)")
        self._hint.setStyleSheet("color: #9ca3af;")
        header.addWidget(self._hint, 1)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Default", BIPMethod.DEFAULT_VALUES)
        self.method_combo.addItem("All zeros", BIPMethod.ZERO)
        self.method_combo.addItem("Chueh–Prausnitz", BIPMethod.CHUEH_PRAUSNITZ)
        self.method_combo.currentIndexChanged.connect(lambda _i: self._rebuild())
        header.addWidget(QLabel("Method:"))
        header.addWidget(self.method_combo)

        layout.addLayout(header)

        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectItems)
        layout.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self.status)

        self.update_components([])

    def update_components(self, component_ids: List[str]) -> None:
        # Preserve order; remove empties and duplicates.
        seen = set()
        cleaned: List[str] = []
        for cid in component_ids:
            cid = str(cid).strip()
            if not cid or cid in seen:
                continue
            cleaned.append(cid)
            seen.add(cid)

        self._component_ids = cleaned
        self._rebuild()

    def _rebuild(self) -> None:
        ids = self._component_ids
        n = len(ids)

        self.table.clear()
        self.table.setRowCount(n)
        self.table.setColumnCount(n)
        self.table.setHorizontalHeaderLabels(ids)
        self.table.setVerticalHeaderLabels(ids)

        if n == 0:
            self.status.setText("No components selected")
            return
        if n == 1:
            self.status.setText("Select 2+ components to view kᵢⱼ")
            self.table.setItem(0, 0, QTableWidgetItem("0"))
            return

        method = self.method_combo.currentData()
        if not isinstance(method, BIPMethod):
            method = BIPMethod.DEFAULT_VALUES

        # Tc vector
        Tc = []
        missing = []
        for cid in ids:
            comp = self._db.get(cid)
            if comp is None:
                missing.append(cid)
                Tc.append(np.nan)
            else:
                Tc.append(float(comp.Tc))

        if missing:
            self.status.setText(f"Missing components in DB: {', '.join(missing)}")
            Tc = [t if np.isfinite(t) else 300.0 for t in Tc]
        else:
            self.status.setText(f"{n} components")

        try:
            bip = build_bip_matrix(component_ids=ids, Tc=np.asarray(Tc, dtype=np.float64), method=method)
            kij = bip.kij
        except Exception as e:
            self.status.setText(f"Failed to build BIP matrix: {e}")
            kij = np.zeros((n, n), dtype=np.float64)

        for i in range(n):
            for j in range(n):
                val = float(kij[i, j])
                item = QTableWidgetItem(f"{val:.3f}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, j, item)

        self.table.resizeColumnsToContents()
