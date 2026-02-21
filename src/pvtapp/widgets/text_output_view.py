"""Text output view for the latest run result."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from pvtapp.schemas import RunResult


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


def _pa_to_bar(p_pa: float) -> float:
    return float(p_pa) / 1e5


class TextOutputWidget(QWidget):
    """Render a plain-text report similar to the MI-PVT 'Text output' tab."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._hint = QLabel("Text output / run report")
        self._hint.setStyleSheet("color: #9ca3af;")
        layout.addWidget(self._hint)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        layout.addWidget(self.text, 1)

        self.clear()

    def clear(self) -> None:
        self.text.setPlainText("(no results yet)")

    def display_result(self, result: RunResult) -> None:
        self.text.setPlainText(self._format(result))

    def _format(self, result: RunResult) -> str:
        cfg = result.config
        lines: list[str] = []

        title = cfg.calculation_type.value.replace("_", " ").title()
        lines.append(title)
        lines.append(_fmt_dt(result.completed_at or result.started_at))
        lines.append("")

        lines.append(f"Run: {result.run_name or result.run_id}")
        lines.append(f"Status: {result.status.value}")
        lines.append(f"EOS: {cfg.eos_type.value}")
        if result.duration_seconds is not None:
            lines.append(f"Duration: {result.duration_seconds:.3f} s")
        lines.append("")

        # Composition echo
        lines.append("Feed composition (z)")
        lines.append("------------------")
        for entry in cfg.composition.components:
            lines.append(f"{entry.component_id:<8s} {entry.mole_fraction:>12.6f}")
        lines.append("")

        # Calculation-specific
        if result.pt_flash_result is not None and cfg.pt_flash_config is not None:
            t = cfg.pt_flash_config.temperature_k
            p = cfg.pt_flash_config.pressure_pa
            lines.append("PT-flash")
            lines.append("-------")
            lines.append(f"T = {t:.3f} K")
            lines.append(f"P = {_pa_to_bar(p):.5f} bar")
            lines.append("")

            r = result.pt_flash_result
            lines.append(f"Phase: {r.phase}")
            lines.append(f"Vapor fraction: {r.vapor_fraction:.6f}")
            lines.append("")

            lines.append("Liquid composition (x)")
            for cid, x in sorted(r.liquid_composition.items()):
                lines.append(f"{cid:<8s} {x:>12.6f}")
            lines.append("")

            lines.append("Vapor composition (y)")
            for cid, y in sorted(r.vapor_composition.items()):
                lines.append(f"{cid:<8s} {y:>12.6f}")
            lines.append("")

        elif result.phase_envelope_result is not None:
            r = result.phase_envelope_result
            lines.append("Phase envelope")
            lines.append("--------------")
            lines.append(f"Bubble points: {len(r.bubble_curve)}")
            lines.append(f"Dew points:    {len(r.dew_curve)}")

            if r.critical_point is not None:
                cp = r.critical_point
                lines.append(f"Critical: T={cp.temperature_k:.3f} K, P={_pa_to_bar(cp.pressure_pa):.5f} bar")
            if r.cricondenbar is not None:
                cb = r.cricondenbar
                lines.append(f"Cricondenbar: T={cb.temperature_k:.3f} K, P={_pa_to_bar(cb.pressure_pa):.5f} bar")
            if r.cricondentherm is not None:
                ct = r.cricondentherm
                lines.append(f"Cricondentherm: T={ct.temperature_k:.3f} K, P={_pa_to_bar(ct.pressure_pa):.5f} bar")
            lines.append("")

            lines.append("Bubble curve (sample)")
            lines.append("T (K)          P (bar)")
            for pt in r.bubble_curve[:60]:
                lines.append(f"{pt.temperature_k:>10.4f} { _pa_to_bar(pt.pressure_pa):>14.6f}")
            if len(r.bubble_curve) > 60:
                lines.append(f"... ({len(r.bubble_curve) - 60} more)")
            lines.append("")

            lines.append("Dew curve (sample)")
            lines.append("T (K)          P (bar)")
            for pt in r.dew_curve[:60]:
                lines.append(f"{pt.temperature_k:>10.4f} { _pa_to_bar(pt.pressure_pa):>14.6f}")
            if len(r.dew_curve) > 60:
                lines.append(f"... ({len(r.dew_curve) - 60} more)")
            lines.append("")

        elif result.cce_result is not None:
            r = result.cce_result
            lines.append("CCE")
            lines.append("---")
            lines.append(f"T = {r.temperature_k:.3f} K")
            if r.saturation_pressure_pa is not None:
                lines.append(f"Psat = {_pa_to_bar(r.saturation_pressure_pa):.5f} bar")
            lines.append("")
            lines.append("P (bar)        RelVol     z")
            for step in r.steps[:80]:
                z = step.z_factor
                z_txt = f"{z:.5f}" if z is not None else ""
                lines.append(f"{_pa_to_bar(step.pressure_pa):>10.5f} {step.relative_volume:>10.5f} {z_txt:>8s}")
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

        else:
            lines.append("(No results payload)")

        if result.error_message:
            lines.append("")
            lines.append("Error")
            lines.append("-----")
            lines.append(result.error_message)

        return "\n".join(lines)
