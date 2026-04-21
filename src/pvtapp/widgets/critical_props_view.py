"""Critical properties view (component table)."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pvtcore.core.constants import R
from pvtcore.models.component import Component
from pvtcore.models import resolve_component_id


class CriticalPropsWidget(QWidget):
    """Display component critical properties for the current component set."""

    def __init__(
        self,
        components_db: Dict[str, Component],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._db = components_db

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._hint = QLabel("Components → critical properties (Tc, Pc, ω, MW, Zc)")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._hint)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "ID",
            "Name",
            "Tc (K)",
            "Pc (bar)",
            "ω",
            "MW (g/mol)",
            "Zc",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(False)
        layout.addWidget(self.table, 1)

        self.update_components([])

    def update_components(self, component_ids: List[str]) -> None:
        component_ids = [cid for cid in component_ids if cid]

        self.table.setRowCount(len(component_ids))

        for row, cid in enumerate(component_ids):
            # The GUI picker uses n-alkane aliases like 'nC4' / 'nC5' that
            # the component database stores as canonical 'C4' / 'C5'.
            # Route the lookup through resolve_component_id so aliases
            # find their canonical entry instead of falling through to
            # '(unknown)'.
            comp = self._db.get(cid)
            if comp is None:
                try:
                    canonical = resolve_component_id(cid, self._db)
                except KeyError:
                    canonical = None
                if canonical is not None:
                    comp = self._db.get(canonical)

            name = comp.name if comp else "(unknown)"
            Tc = comp.Tc if comp else None
            Pc_bar = comp.Pc_bar if comp else None
            omega = comp.omega if comp else None
            mw = comp.MW if comp else None

            Zc = None
            if comp and comp.Tc and comp.Pc and comp.Vc and comp.Tc > 0:
                # Zc = Pc*Vc/(R*Tc)
                Zc = (comp.Pc * comp.Vc) / (R.Pa_m3_per_mol_K * comp.Tc)

            values = [
                cid,
                name,
                f"{Tc:.3f}" if Tc is not None else "",
                f"{Pc_bar:.3f}" if Pc_bar is not None else "",
                f"{omega:.5f}" if omega is not None else "",
                f"{mw:.4f}" if mw is not None else "",
                f"{Zc:.5f}" if Zc is not None else "",
            ]

            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

        self.table.resizeColumnsToContents()
