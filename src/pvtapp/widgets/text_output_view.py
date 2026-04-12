"""Text output view for the latest run result."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from pvtapp.plus_fraction_policy import describe_plus_fraction_policy
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.schemas import (
    PressureUnit,
    PTFlashConfig,
    RunResult,
    SaturationPointConfig,
    TemperatureUnit,
    pressure_from_pa,
    temperature_from_k,
)


def _fmt_dt(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    try:
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt)


def _pa_to_bar(p_pa: float) -> float:
    return float(p_pa) / 1e5


def _format_pressure(value_pa: float, unit: PressureUnit, *, precision: int = 5) -> str:
    return f"{pressure_from_pa(value_pa, unit):.{precision}f} {unit.value}"


def _format_temperature(value_k: float, unit: TemperatureUnit, *, precision: int = 3) -> str:
    return f"{temperature_from_k(value_k, unit):.{precision}f} {unit.value}"


def _pt_flash_units(config: Optional[PTFlashConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.BAR, TemperatureUnit.C
    return config.pressure_unit, config.temperature_unit


def _saturation_units(config: Optional[SaturationPointConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.BAR, TemperatureUnit.C
    return config.pressure_unit, config.temperature_unit


class TextOutputWidget(QWidget):
    """Render a plain-text report similar to the MI-PVT 'Text output' tab."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(10)

        self._hint = QLabel("Text output / run report")
        self._hint.setStyleSheet("color: #9ca3af;")
        self._layout.addWidget(self._hint)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.text.setFont(mono)
        self._layout.addWidget(self.text, 1)

        self.clear()

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale the monospace report view with the app zoom."""
        self._layout.setSpacing(scale_metric(10, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        font = self.text.font()
        font.setPointSizeF(scale_metric(11, ui_scale, reference_scale=DEFAULT_UI_SCALE))
        self.text.setFont(font)

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
        if cfg.composition.plus_fraction is not None:
            plus_fraction = cfg.composition.plus_fraction
            lines.append(f"{plus_fraction.label:<8s} {plus_fraction.z_plus:>12.6f}")
        lines.append("")
        if cfg.composition.plus_fraction is not None:
            plus_fraction = cfg.composition.plus_fraction
            lines.append("C7+ characterization")
            lines.append("-------------------")
            lines.append(describe_plus_fraction_policy(plus_fraction))
            lines.append(f"MW+ = {plus_fraction.mw_plus_g_per_mol:.6f} g/mol")
            if plus_fraction.sg_plus_60f is not None:
                lines.append(f"SG+ = {plus_fraction.sg_plus_60f:.6f}")
            lines.append("")

        # Calculation-specific
        if result.pt_flash_result is not None and cfg.pt_flash_config is not None:
            t = cfg.pt_flash_config.temperature_k
            p = cfg.pt_flash_config.pressure_pa
            pressure_unit, temperature_unit = _pt_flash_units(cfg.pt_flash_config)
            lines.append("PT-flash")
            lines.append("-------")
            lines.append(f"T = {_format_temperature(t, temperature_unit)}")
            lines.append(f"P = {_format_pressure(p, pressure_unit)}")
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

        elif result.bubble_point_result is not None:
            r = result.bubble_point_result
            pressure_unit, temperature_unit = _saturation_units(cfg.bubble_point_config)
            lines.append("Bubble point")
            lines.append("------------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"Pb = {_format_pressure(r.pressure_pa, pressure_unit)}")
            lines.append(f"Converged: {r.converged}")
            if r.diagnostics is not None:
                lines.append(f"Solver status: {r.diagnostics.status.value}")
            lines.append(f"Stable liquid: {r.stable_liquid}")
            lines.append(f"Iterations: {r.iterations}")
            lines.append(f"Residual: {r.residual:.5e}")
            if r.certificate is not None:
                lines.append(f"Invariant certificate: {'pass' if r.certificate.passed else 'fail'}")
            lines.append("")
            lines.append("Component       x            y            K")
            for cid in sorted(set(r.liquid_composition) | set(r.vapor_composition) | set(r.k_values)):
                lines.append(
                    f"{cid:<8s} "
                    f"{r.liquid_composition.get(cid, 0.0):>12.6f} "
                    f"{r.vapor_composition.get(cid, 0.0):>12.6f} "
                    f"{r.k_values.get(cid, 0.0):>12.6f}"
                )
            lines.append("")

        elif result.dew_point_result is not None:
            r = result.dew_point_result
            pressure_unit, temperature_unit = _saturation_units(cfg.dew_point_config)
            lines.append("Dew point")
            lines.append("---------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"Pd = {_format_pressure(r.pressure_pa, pressure_unit)}")
            lines.append(f"Converged: {r.converged}")
            if r.diagnostics is not None:
                lines.append(f"Solver status: {r.diagnostics.status.value}")
            lines.append(f"Stable vapor: {r.stable_vapor}")
            lines.append(f"Iterations: {r.iterations}")
            lines.append(f"Residual: {r.residual:.5e}")
            if r.certificate is not None:
                lines.append(f"Invariant certificate: {'pass' if r.certificate.passed else 'fail'}")
            lines.append("")
            lines.append("Component       x            y            K")
            for cid in sorted(set(r.liquid_composition) | set(r.vapor_composition) | set(r.k_values)):
                lines.append(
                    f"{cid:<8s} "
                    f"{r.liquid_composition.get(cid, 0.0):>12.6f} "
                    f"{r.vapor_composition.get(cid, 0.0):>12.6f} "
                    f"{r.k_values.get(cid, 0.0):>12.6f}"
                )
            lines.append("")

        elif result.phase_envelope_result is not None:
            r = result.phase_envelope_result
            lines.append("Phase envelope")
            lines.append("--------------")
            lines.append(f"Tracer:        {r.tracing_method.value}")
            lines.append(f"Bubble points: {len(r.bubble_curve)}")
            lines.append(f"Dew points:    {len(r.dew_curve)}")
            if r.continuation_switched is not None:
                lines.append(f"Switched:      {'yes' if r.continuation_switched else 'no'}")
            if r.critical_source is not None:
                lines.append(f"Critical src:  {r.critical_source}")

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

        elif result.dl_result is not None:
            r = result.dl_result
            lines.append("Differential liberation")
            lines.append("-----------------------")
            lines.append(f"T = {r.temperature_k:.3f} K")
            lines.append(f"Pb = {_pa_to_bar(r.bubble_pressure_pa):.5f} bar")
            lines.append(f"Rsi = {r.rsi:.5f}")
            lines.append(f"Boi = {r.boi:.5f}")
            lines.append(f"Converged: {r.converged}")
            lines.append("")
            lines.append("P (bar)         Rs         Bo         Bt     VaporFrac")
            for step in r.steps[:80]:
                lines.append(
                    f"{_pa_to_bar(step.pressure_pa):>10.5f} "
                    f"{step.rs:>10.5f} "
                    f"{step.bo:>10.5f} "
                    f"{step.bt:>10.5f} "
                    f"{step.vapor_fraction:>12.5f}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

        elif result.cvd_result is not None:
            r = result.cvd_result
            lines.append("CVD")
            lines.append("---")
            lines.append(f"T = {r.temperature_k:.3f} K")
            lines.append(f"Pd = {_pa_to_bar(r.dew_pressure_pa):.5f} bar")
            lines.append(f"Initial Z = {r.initial_z:.5f}")
            lines.append("")
            lines.append("P (bar)     Liquid Dropout   Cum. Gas     Z")
            for step in r.steps[:80]:
                z_two_phase = "" if step.z_two_phase is None else f"{step.z_two_phase:.5f}"
                lines.append(
                    f"{_pa_to_bar(step.pressure_pa):>10.5f} "
                    f"{step.liquid_dropout:>16.5f} "
                    f"{step.cumulative_gas_produced:>10.5f} "
                    f"{z_two_phase:>8s}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

        elif result.separator_result is not None:
            r = result.separator_result
            lines.append("Separator train")
            lines.append("---------------")
            lines.append(f"Converged = {r.converged}")
            lines.append(f"Bo = {r.bo:.5f}")
            lines.append(f"Rs = {r.rs:.5f}")
            lines.append(f"Rs (scf/STB) = {r.rs_scf_stb:.5f}")
            lines.append(f"Bg = {r.bg:.5f}")
            lines.append(f"API = {r.api_gravity:.3f}")
            lines.append(f"Stock-tank oil density = {r.stock_tank_oil_density:.5f}")
            lines.append("")
            lines.append("Stage         P (bar)      T (K)    VaporFrac   LiquidMol    VaporMol")
            for stage in r.stages[:80]:
                vapor_fraction = "" if stage.vapor_fraction is None else f"{stage.vapor_fraction:.5f}"
                liquid_moles = "" if stage.liquid_moles is None else f"{stage.liquid_moles:.5f}"
                vapor_moles = "" if stage.vapor_moles is None else f"{stage.vapor_moles:.5f}"
                lines.append(
                    f"{stage.stage_name[:12]:<12s} "
                    f"{_pa_to_bar(stage.pressure_pa):>10.5f} "
                    f"{stage.temperature_k:>10.3f} "
                    f"{vapor_fraction:>11s} "
                    f"{liquid_moles:>11s} "
                    f"{vapor_moles:>11s}"
                )
            if len(r.stages) > 80:
                lines.append(f"... ({len(r.stages) - 80} more)")
            lines.append("")

        else:
            lines.append("(No results payload)")

        if result.error_message:
            lines.append("")
            lines.append("Error")
            lines.append("-----")
            lines.append(result.error_message)

        return "\n".join(lines)
