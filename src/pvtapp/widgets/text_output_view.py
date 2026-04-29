"""Text output view for the latest run result."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QLabel, QTextEdit, QVBoxLayout, QWidget

from pvtapp.capabilities import GUI_EOS_TYPE_LABELS
from pvtapp.plus_fraction_policy import describe_plus_fraction_policy
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric
from pvtapp.schemas import (
    EOSType,
    PressureUnit,
    PTFlashConfig,
    RunResult,
    SaturationPointConfig,
    CCEConfig,
    DLConfig,
    WhitsonTorpConfig,
    SwellingTestConfig,
    StabilityAnalysisConfig,
    TemperatureUnit,
    describe_pt_flash_reported_surface_status,
    describe_reported_component_basis,
    describe_runtime_component_basis,
    pressure_from_pa,
    temperature_from_k,
)


_COMPONENT_DISPLAY_OVERRIDES = {
    "PSEUDO_PLUS": "PSEUDO+",
}

# Lines in the `_format` output that start with this sentinel are pre-formatted
# HTML fragments and are passed through to `setHtml` unescaped; all other lines
# are HTML-escaped before being wrapped in the outer <pre> block. Using a byte
# that will never appear in real report text keeps the plumbing trivial.
_HTML_LINE_MARK = "\x01"

# Colours used for the feed-composition normalization diff (and, going forward,
# any other inline-colored text in this report). Chosen to match the dark-mode
# palette used elsewhere in the app (Tailwind 500-series greens/reds).
_DIFF_GREEN = "#22c55e"
_DIFF_RED = "#ef4444"


def _display_component_id(comp_id: str) -> str:
    """Map a runtime component id to the user-facing token for text reports."""
    return _COMPONENT_DISPLAY_OVERRIDES.get(comp_id.strip(), comp_id.strip())


def _render_feed_composition_lines(composition) -> list[str]:
    """Render the ``Feed composition (z)`` section.

    If the user-entered mole fractions already sum to 1.0 (within a tight
    tolerance), the classic single-column format is returned unchanged. If
    they do not, the values are silently normalized for the simulator run —
    so the echo is rendered with a parenthesised delta column showing how
    each row was adjusted, plus a trailing "Total: 1.000000 (Normalized
    from <input-sum>)" line. Negative deltas are coloured red, positive
    deltas green, and the "(Normalized from …)" footer is green. The
    per-row delta lines and the footer are emitted as HTML fragments
    (prefixed with ``_HTML_LINE_MARK``); all other lines are plain text.
    """
    lines: list[str] = ["Feed composition (z)", "------------------"]

    entries: list[tuple[str, float]] = [
        (_display_component_id(entry.component_id), float(entry.mole_fraction))
        for entry in composition.components
    ]
    if composition.plus_fraction is not None:
        pf = composition.plus_fraction
        entries.append((_display_component_id(pf.label), float(pf.z_plus)))

    input_sum = sum(v for _, v in entries)
    needs_norm = abs(input_sum - 1.0) > 1e-9 and input_sum > 0.0

    if not needs_norm:
        for cid, v in entries:
            lines.append(f"{cid:<8s} {v:>12.6f}")
        return lines

    # Column layout:  "<cid:8s> <value:12.6f>   (<signed delta:9>)"
    # The separator underline and the trailing footer both sit under the
    # parenthesised delta column, so the "(Normalized from …)" text aligns
    # naturally with each row's "(+/-X.XXXXXX)".
    prefix_width = 8 + 1 + 12 + 3  # cid + space + value + 3 spaces
    sep_width = 11                 # matches "(+X.XXXXXX)" / "(-X.XXXXXX)"

    for cid, v in entries:
        v_norm = v / input_sum
        delta = v_norm - v
        delta_str = f"({delta:+.6f})"
        color = _DIFF_GREEN if delta > 0 else (_DIFF_RED if delta < 0 else None)
        escaped_prefix = html.escape(f"{cid:<8s} {v_norm:>12.6f}   ")
        if color is None:
            lines.append(_HTML_LINE_MARK + escaped_prefix + html.escape(delta_str))
        else:
            lines.append(
                _HTML_LINE_MARK
                + escaped_prefix
                + f'<span style="color:{color};">{html.escape(delta_str)}</span>'
            )

    lines.append(" " * prefix_width + "─" * sep_width)

    total_prefix = html.escape(f"{'Total:':<8s} {1.0:>12.6f}   ")
    footer_text = f"(Normalized from {input_sum:.6f})"
    lines.append(
        _HTML_LINE_MARK
        + total_prefix
        + f'<span style="color:{_DIFF_GREEN};">{html.escape(footer_text)}</span>'
    )

    return lines


def _lines_to_html(lines: list[str]) -> str:
    """Wrap ``_format`` output for ``QTextEdit.setHtml``.

    Plain-text lines are HTML-escaped so that any stray ``<`` / ``>`` / ``&``
    (e.g. future formula echoes) render as literal characters. Lines that
    begin with ``_HTML_LINE_MARK`` are already HTML fragments — we strip the
    sentinel and pass them through unchanged. The final body is wrapped in
    a ``<pre>`` block pinned to Consolas so monospace column alignment is
    preserved across the entire report.
    """
    rendered: list[str] = []
    for line in lines:
        if line.startswith(_HTML_LINE_MARK):
            rendered.append(line[len(_HTML_LINE_MARK):])
        else:
            rendered.append(html.escape(line))
    body = "\n".join(rendered)
    return (
        "<pre style=\"font-family:Consolas,'Courier New',monospace; margin:0;\">"
        f"{body}"
        "</pre>"
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


def _format_temperature_unit(unit: TemperatureUnit) -> str:
    """Render compact temperature units with a visible degree marker."""
    return f"\N{DEGREE SIGN}{unit.value}"


def _format_pressure(value_pa: float, unit: PressureUnit, *, precision: int = 5) -> str:
    return f"{pressure_from_pa(value_pa, unit):.{precision}f} {unit.value}"


def _format_temperature(value_k: float, unit: TemperatureUnit, *, precision: int = 3) -> str:
    return f"{temperature_from_k(value_k, unit):.{precision}f} {_format_temperature_unit(unit)}"


def _format_optional_measurement(value: Optional[float], *, precision: int, unit: str) -> str:
    if value is None:
        return "-"
    return f"{value:.{precision}f} {unit}"


def _pt_flash_units(config: Optional[PTFlashConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _saturation_units(config: Optional[SaturationPointConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _cce_units(config: Optional[CCEConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _dl_units(config: Optional[DLConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _whitson_torp_units(config: Optional[WhitsonTorpConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _cvd_units() -> tuple[PressureUnit, TemperatureUnit]:
    """Return CVD display units.

    CVDConfig does not carry pressure / temperature preference fields, so
    the text output renders in the repo-wide US-petroleum defaults (psia /
    °F) — same units the CVD results-panel and Excel export use.
    """
    return PressureUnit.PSIA, TemperatureUnit.F


def _stability_units(config: Optional[StabilityAnalysisConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _swelling_units(config: Optional[SwellingTestConfig]) -> tuple[PressureUnit, TemperatureUnit]:
    if config is None:
        return PressureUnit.PSIA, TemperatureUnit.F
    return config.pressure_unit, config.temperature_unit


def _classify_omitted_step(step, field: str) -> str:
    """Return ``"single-phase"`` or ``"missing"`` for a step with no composition.

    For a liquid-composition pass, a step without a liquid phase (no liquid
    density) is single-phase vapor rather than missing data, and vice versa
    for vapor-composition passes.
    """
    if field == "liquid_composition":
        density = getattr(step, "liquid_density_kg_per_m3", None)
        fraction = getattr(step, "liquid_fraction", None)
    elif field == "vapor_composition":
        density = getattr(step, "vapor_density_kg_per_m3", None)
        fraction = getattr(step, "vapor_fraction", None)
    elif field == "gas_composition":
        density = getattr(step, "gas_density_kg_per_m3", None) or getattr(
            step, "gas_density_kg_per_sm3", None
        )
        fraction = None
    else:
        density = None
        fraction = None
    if density is None or (isinstance(density, (int, float)) and density <= 0):
        return "single-phase"
    if fraction is not None and isinstance(fraction, (int, float)) and fraction <= 0:
        return "single-phase"
    return "missing"


def _format_per_step_composition_table(
    *,
    title: str,
    steps,
    pressure_unit: PressureUnit,
    field: str,
    max_steps: int = 40,
) -> list[str]:
    """Render a per-step composition sub-table for CCE/DL text output.

    Rows are pressure steps; columns are components. Rows with missing or all-zero
    compositions (e.g. the absent phase of a single-phase step) are omitted.
    Returns [] when no step has any data in the requested field.
    """
    rows: list[tuple[float, dict[str, float]]] = []
    omitted_reasons: dict[str, int] = {"single-phase": 0, "missing": 0}
    component_ids: list[str] = []
    for step in steps[:max_steps]:
        comp = getattr(step, field, None)
        if not comp:
            reason = _classify_omitted_step(step, field)
            omitted_reasons[reason] = omitted_reasons.get(reason, 0) + 1
            continue
        if not component_ids:
            component_ids = list(comp.keys())
        rows.append((step.pressure_pa, comp))
    if not rows:
        return []

    col_width = 12
    pressure_col_width = 10
    header = (
        f"{f'P ({pressure_unit.value})':>{pressure_col_width}s}"
        + "".join(
            f"{_display_component_id(cid):>{col_width}s}" for cid in component_ids
        )
    )
    out = [title, header]
    for p_pa, comp in rows:
        pressure = pressure_from_pa(p_pa, pressure_unit)
        row_cells = "".join(
            f"{comp.get(cid, 0.0):>{col_width}.6f}" for cid in component_ids
        )
        out.append(f"{pressure:>{pressure_col_width}.3f}{row_cells}")
    omitted_bits: list[str] = []
    if omitted_reasons["single-phase"]:
        omitted_bits.append(f"{omitted_reasons['single-phase']} single-phase")
    if omitted_reasons["missing"]:
        omitted_bits.append(f"{omitted_reasons['missing']} missing data")
    if omitted_bits:
        out.append(f"... ({', '.join(omitted_bits)})")
    out.append("")
    return out


def format_eos_label(eos_type: EOSType) -> str:
    """Return the GUI-facing EOS label for reports and compact summaries."""
    return GUI_EOS_TYPE_LABELS.get(eos_type, eos_type.value.replace("_", " ").title())


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
        # Disable word wrap so report columns (CCE/DL/CVD/stability tables)
        # stay aligned at any window width. Qt will add a horizontal scroll
        # bar automatically when the monospaced grid is wider than the
        # viewport; the user scrolls horizontally instead of having column
        # headers drift out of sync with their value rows.
        self.text.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.text.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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
        self.text.setHtml(self._format(result))

    def _format(self, result: RunResult) -> str:
        cfg = result.config
        lines: list[str] = []

        title = "TBP" if cfg.calculation_type.value == "tbp" else cfg.calculation_type.value.replace("_", " ").title()
        lines.append(title)
        lines.append(_fmt_dt(result.completed_at or result.started_at))
        lines.append("")

        lines.append(f"Run: {result.run_name or result.run_id}")
        lines.append(f"Status: {result.status.value}")
        if cfg.calculation_type.value != "tbp":
            lines.append(f"EOS: {format_eos_label(cfg.eos_type)}")
        if result.duration_seconds is not None:
            lines.append(f"Duration: {result.duration_seconds:.3f} s")
        lines.append("")

        # Composition echo. Renders a parenthesised diff column + "(Normalized
        # from <sum>)" footer when the user-entered mole fractions do not sum
        # to exactly 1.0 — otherwise falls through to the classic single-column
        # format. Colouring on the diff/footer is applied via the sentinel-tagged
        # HTML lines handled by `_lines_to_html` at the end of this function.
        if cfg.composition is not None:
            lines.extend(_render_feed_composition_lines(cfg.composition))
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
                if result.runtime_characterization is not None:
                    runtime = result.runtime_characterization
                    lines.append("Runtime characterization")
                    lines.append("----------------------")
                    basis_label = describe_runtime_component_basis(runtime.runtime_component_basis)
                    lines.append(f"Basis = {basis_label or runtime.runtime_component_basis}")
                    lines.append(f"Split = {runtime.split_method}")
                    if runtime.lumping_method is not None:
                        lines.append(f"Lumping = {runtime.lumping_method}")
                    lines.append(f"Runtime components = {len(runtime.runtime_component_ids)}")
                    lines.append(f"SCNs = {len(runtime.scn_distribution)}")
                    if runtime.lump_distribution:
                        lines.append(f"Lumps = {len(runtime.lump_distribution)}")
                    if runtime.delumping_basis is not None:
                        lines.append(f"Delumping = {runtime.delumping_basis}")
                    if runtime.pedersen_fit is not None:
                        lines.append(
                            f"Pedersen A/B = {runtime.pedersen_fit.A:.6f}, {runtime.pedersen_fit.B:.6f}"
                        )
                        if runtime.pedersen_fit.tbp_cut_rms_relative_error is not None:
                            lines.append(
                                f"Cut Fit RMS = {runtime.pedersen_fit.tbp_cut_rms_relative_error:.6f}"
                            )
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
            lines.append(
                f"Liquid density: {_format_optional_measurement(r.liquid_density_kg_per_m3, precision=2, unit='kg/m³')}"
            )
            lines.append(
                f"Vapor density: {_format_optional_measurement(r.vapor_density_kg_per_m3, precision=2, unit='kg/m³')}"
            )
            lines.append(
                f"Liquid viscosity: {_format_optional_measurement(r.liquid_viscosity_cp, precision=4, unit='cP')}"
            )
            lines.append(
                f"Vapor viscosity: {_format_optional_measurement(r.vapor_viscosity_cp, precision=4, unit='cP')}"
            )
            lines.append(
                f"Interfacial tension: {_format_optional_measurement(r.interfacial_tension_mn_per_m, precision=4, unit='mN/m')}"
            )
            reported_surface_label = describe_pt_flash_reported_surface_status(
                r.reported_surface_status
            )
            reported_basis_label = describe_reported_component_basis(r.reported_component_basis)
            if reported_surface_label is not None:
                lines.append(f"Reported surface: {reported_surface_label}")
                if r.reported_surface_reason:
                    lines.append(f"Reported surface note: {r.reported_surface_reason}")
            if reported_basis_label is not None:
                lines.append(f"Reported basis: {reported_basis_label}")
                lines.append(
                    "Rendered basis: "
                    + (
                        reported_basis_label
                        if r.has_reported_thermodynamic_surface
                        else "Runtime thermodynamic basis"
                    )
                )
            elif reported_surface_label is not None:
                lines.append("Rendered basis: Runtime thermodynamic basis")
            lines.append("")

            lines.append("Liquid composition (x)")
            for cid, x in sorted(r.display_liquid_composition.items()):
                lines.append(f"{cid:<8s} {x:>12.6f}")
            lines.append("")

            lines.append("Vapor composition (y)")
            for cid, y in sorted(r.display_vapor_composition.items()):
                lines.append(f"{cid:<8s} {y:>12.6f}")
            lines.append("")

        elif result.stability_analysis_result is not None:
            r = result.stability_analysis_result
            pressure_unit, temperature_unit = _stability_units(cfg.stability_analysis_config)
            lines.append("Stability analysis")
            lines.append("------------------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"P = {_format_pressure(r.pressure_pa, pressure_unit)}")
            lines.append(f"Stable = {r.stable}")
            lines.append(f"Minimum TPD = {r.tpd_min:.6e}")
            lines.append(f"Phase regime = {r.phase_regime}")
            lines.append(f"Physical state hint = {r.physical_state_hint}")
            lines.append(f"Hint basis = {r.physical_state_hint_basis}")
            lines.append(f"Hint confidence = {r.physical_state_hint_confidence}")
            lines.append(f"Requested feed phase = {r.requested_feed_phase.value}")
            lines.append(f"Resolved feed phase = {r.resolved_feed_phase}")
            lines.append(f"Reference root used = {r.reference_root_used}")
            if r.best_unstable_trial_kind is not None:
                lines.append(f"Best unstable trial = {r.best_unstable_trial_kind}")
            lines.append("")

            lines.append("Interpretation provenance")
            lines.append("------------------------")
            if r.liquid_root_z is not None:
                lines.append(f"Liquid root Z = {r.liquid_root_z:.6f}")
            if r.vapor_root_z is not None:
                lines.append(f"Vapor root Z = {r.vapor_root_z:.6f}")
            if r.root_gap is not None:
                lines.append(f"Root gap = {r.root_gap:.6e}")
            if r.gibbs_gap is not None:
                lines.append(f"Gibbs gap = {r.gibbs_gap:.6e}")
            if r.average_reduced_pressure is not None:
                lines.append(f"Average reduced pressure = {r.average_reduced_pressure:.6f}")
            if r.bubble_pressure_hint_pa is not None:
                lines.append(f"Bubble pressure hint = {_format_pressure(r.bubble_pressure_hint_pa, pressure_unit)}")
            if r.dew_pressure_hint_pa is not None:
                lines.append(f"Dew pressure hint = {_format_pressure(r.dew_pressure_hint_pa, pressure_unit)}")
            if r.bubble_boundary_reason is not None:
                lines.append(f"Bubble boundary reason = {r.bubble_boundary_reason}")
            if r.dew_boundary_reason is not None:
                lines.append(f"Dew boundary reason = {r.dew_boundary_reason}")
            lines.append("")

            vapor_comp = {} if r.vapor_like_trial is None else r.vapor_like_trial.composition
            liquid_comp = {} if r.liquid_like_trial is None else r.liquid_like_trial.composition
            components = sorted(set(r.feed_composition) | set(vapor_comp) | set(liquid_comp))
            lines.append("Feed / trial compositions")
            lines.append("------------------------")
            lines.append("Component        Feed(z)    Vapor-like   Liquid-like")
            for cid in components:
                vapor_value = "-" if cid not in vapor_comp else f"{vapor_comp.get(cid, 0.0):.6f}"
                liquid_value = "-" if cid not in liquid_comp else f"{liquid_comp.get(cid, 0.0):.6f}"
                lines.append(
                    f"{cid:<12s} "
                    f"{r.feed_composition.get(cid, 0.0):>10.6f} "
                    f"{vapor_value:>12s} "
                    f"{liquid_value:>12s}"
                )
            lines.append("")

            for trial_label, trial in (
                ("Vapor-like trial", r.vapor_like_trial),
                ("Liquid-like trial", r.liquid_like_trial),
            ):
                if trial is None:
                    continue
                lines.append(trial_label)
                lines.append("-" * len(trial_label))
                lines.append(f"Trial phase = {trial.trial_phase}")
                lines.append(f"TPD = {trial.tpd:.6e}")
                lines.append(f"Converged = {trial.converged}")
                lines.append(f"Early exit unstable = {trial.early_exit_unstable}")
                lines.append(f"Iterations = {trial.iterations}")
                lines.append(f"Total iterations = {trial.total_iterations}")
                lines.append(f"Phi calls = {trial.n_phi_calls}")
                lines.append(f"EOS failures = {trial.n_eos_failures}")
                lines.append(
                    f"Best seed = {trial.best_seed.seed_label} (index {trial.best_seed_index})"
                )
                lines.append(
                    f"Seed attempts = {trial.seed_attempts}/{trial.candidate_seed_count}"
                )
                if trial.message:
                    lines.append(f"Message = {trial.message}")
                if trial.diagnostic_messages:
                    lines.append("Diagnostics:")
                    for message in trial.diagnostic_messages:
                        if message:
                            lines.append(f"  - {message}")
                if trial.seed_results:
                    lines.append("")
                    lines.append(
                        "Seed              TPD        Conv  Early  Iter   Phi  EOSFail  Message"
                    )
                    for seed in trial.seed_results:
                        message = "-" if not seed.message else seed.message
                        lines.append(
                            f"{seed.seed_label:<16s} "
                            f"{seed.tpd:>10.3e} "
                            f"{('Y' if seed.converged else 'N'):>5s} "
                            f"{('Y' if seed.early_exit_unstable else 'N'):>5s} "
                            f"{seed.iterations:>5d} "
                            f"{seed.n_phi_calls:>5d} "
                            f"{seed.n_eos_failures:>8d} "
                            f"{message}"
                        )
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
            reported_basis_label = describe_reported_component_basis(r.reported_component_basis)
            if reported_basis_label is not None:
                lines.append(f"Reported basis: {reported_basis_label}")
                lines.append(
                    "Rendered basis: "
                    + (
                        reported_basis_label
                        if r.has_reported_surface
                        else "Runtime thermodynamic basis"
                    )
                )
            if r.certificate is not None:
                lines.append(f"Invariant certificate: {'pass' if r.certificate.passed else 'fail'}")
            lines.append("")
            lines.append(
                f"{'Component':<10s} "
                f"{'x':>12s} "
                f"{'y':>12s} "
                f"{'K':>12s}"
            )
            for cid in sorted(
                set(r.display_liquid_composition)
                | set(r.display_vapor_composition)
                | set(r.display_k_values)
            ):
                lines.append(
                    f"{_display_component_id(cid):<10s} "
                    f"{r.display_liquid_composition.get(cid, 0.0):>12.6f} "
                    f"{r.display_vapor_composition.get(cid, 0.0):>12.6f} "
                    f"{r.display_k_values.get(cid, 0.0):>12.6f}"
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
            reported_basis_label = describe_reported_component_basis(r.reported_component_basis)
            if reported_basis_label is not None:
                lines.append(f"Reported basis: {reported_basis_label}")
                lines.append(
                    "Rendered basis: "
                    + (
                        reported_basis_label
                        if r.has_reported_surface
                        else "Runtime thermodynamic basis"
                    )
                )
            if r.certificate is not None:
                lines.append(f"Invariant certificate: {'pass' if r.certificate.passed else 'fail'}")
            lines.append("")
            lines.append(
                f"{'Component':<10s} "
                f"{'x':>12s} "
                f"{'y':>12s} "
                f"{'K':>12s}"
            )
            for cid in sorted(
                set(r.display_liquid_composition)
                | set(r.display_vapor_composition)
                | set(r.display_k_values)
            ):
                lines.append(
                    f"{_display_component_id(cid):<10s} "
                    f"{r.display_liquid_composition.get(cid, 0.0):>12.6f} "
                    f"{r.display_vapor_composition.get(cid, 0.0):>12.6f} "
                    f"{r.display_k_values.get(cid, 0.0):>12.6f}"
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
            if r.bubble_termination_reason is not None:
                bubble_stop = r.bubble_termination_reason
                if r.bubble_termination_temperature_k is not None:
                    bubble_stop = f"{bubble_stop} @ {r.bubble_termination_temperature_k:.3f} K"
                lines.append(f"Bubble stop:   {bubble_stop}")
            if r.dew_termination_reason is not None:
                dew_stop = r.dew_termination_reason
                if r.dew_termination_temperature_k is not None:
                    dew_stop = f"{dew_stop} @ {r.dew_termination_temperature_k:.3f} K"
                lines.append(f"Dew stop:      {dew_stop}")

            env_p = PressureUnit.PSIA
            env_t = TemperatureUnit.F
            if r.critical_point is not None:
                cp = r.critical_point
                lines.append(
                    f"Critical: T={_format_temperature(cp.temperature_k, env_t)}, "
                    f"P={_format_pressure(cp.pressure_pa, env_p)}"
                )
            if r.cricondenbar is not None:
                cb = r.cricondenbar
                lines.append(
                    f"Cricondenbar: T={_format_temperature(cb.temperature_k, env_t)}, "
                    f"P={_format_pressure(cb.pressure_pa, env_p)}"
                )
            if r.cricondentherm is not None:
                ct = r.cricondentherm
                lines.append(
                    f"Cricondentherm: T={_format_temperature(ct.temperature_k, env_t)}, "
                    f"P={_format_pressure(ct.pressure_pa, env_p)}"
                )
            lines.append("")

            lines.append("Bubble curve (sample)")
            lines.append(f"T ({_format_temperature_unit(env_t)})          P ({env_p.value})")
            for pt in r.bubble_curve[:60]:
                lines.append(
                    f"{temperature_from_k(pt.temperature_k, env_t):>10.4f} "
                    f"{pressure_from_pa(pt.pressure_pa, env_p):>14.4f}"
                )
            if len(r.bubble_curve) > 60:
                lines.append(f"... ({len(r.bubble_curve) - 60} more)")
            lines.append("")

            lines.append("Dew curve (sample)")
            lines.append(f"T ({_format_temperature_unit(env_t)})          P ({env_p.value})")
            for pt in r.dew_curve[:60]:
                lines.append(
                    f"{temperature_from_k(pt.temperature_k, env_t):>10.4f} "
                    f"{pressure_from_pa(pt.pressure_pa, env_p):>14.4f}"
                )
            if len(r.dew_curve) > 60:
                lines.append(f"... ({len(r.dew_curve) - 60} more)")
            lines.append("")

        elif result.tbp_result is not None:
            r = result.tbp_result
            lines.append("TBP assay")
            lines.append("---------")
            lines.append(f"Cut start = C{r.cut_start}")
            lines.append(f"Cut end   = C{r.cut_end}")
            lines.append(f"z+        = {r.z_plus:.6f}")
            lines.append(f"MW+       = {r.mw_plus_g_per_mol:.6f} g/mol")
            lines.append("")
            lines.append(
                "Cut         Range        z       Norm z    Cum Mole %      MW      Tb(K)   Cum Mass %"
            )
            for cut in r.cuts[:80]:
                carbon_range = (
                    f"{cut.carbon_number}"
                    if cut.carbon_number_end == cut.carbon_number
                    else f"{cut.carbon_number}-{cut.carbon_number_end}"
                )
                lines.append(
                    f"{cut.name:<8s} "
                    f"{carbon_range:<10s} "
                    f"{cut.mole_fraction:>8.5f} "
                    f"{cut.normalized_mole_fraction:>10.5f} "
                    f"{cut.cumulative_mole_fraction * 100.0:>11.2f} "
                    f"{cut.molecular_weight_g_per_mol:>9.3f} "
                    f"{('-' if cut.boiling_point_k is None else f'{cut.boiling_point_k:.2f}'):>9s} "
                    f"{cut.cumulative_mass_fraction * 100.0:>11.2f}"
                )
            if len(r.cuts) > 80:
                lines.append(f"... ({len(r.cuts) - 80} more)")
            lines.append("")

            if r.characterization_context is not None:
                ctx = r.characterization_context
                lines.append("Runtime bridge")
                lines.append("--------------")
                lines.append("Source = TBP assay")
                status_label = (
                    "Characterized SCN"
                    if ctx.bridge_status == "characterized_scn"
                    else "Aggregate only"
                )
                lines.append(f"Status = {status_label}")
                lines.append(f"Label  = {ctx.plus_fraction_label}")
                lines.append(f"z+     = {ctx.z_plus:.6f}")
                lines.append(f"MW+    = {ctx.mw_plus_g_per_mol:.6f} g/mol")
                lines.append(f"SG+    = {'-' if ctx.sg_plus_60f is None else f'{ctx.sg_plus_60f:.6f}'}")
                if ctx.characterization_method is not None:
                    lines.append(f"Method = {ctx.characterization_method}")
                if ctx.runtime_component_basis is not None:
                    lines.append(f"Basis  = {ctx.runtime_component_basis}")
                if ctx.pedersen_fit is not None:
                    lines.append(
                        f"Pedersen A/B = {ctx.pedersen_fit.A:.6f}, {ctx.pedersen_fit.B:.6f}"
                    )
                    if ctx.pedersen_fit.tbp_cut_rms_relative_error is not None:
                        lines.append(
                            f"Cut Fit RMS = {ctx.pedersen_fit.tbp_cut_rms_relative_error:.6f}"
                        )
                if ctx.cut_mappings:
                    lines.append("")
                    lines.append("Cut mapping")
                    lines.append("-----------")
                    lines.append("Cut         Range      Obs z    Char z    Rel Err    SCNs")
                    for mapping in ctx.cut_mappings[:20]:
                        carbon_range = (
                            f"{mapping.carbon_number}"
                            if mapping.carbon_number_end == mapping.carbon_number
                            else f"{mapping.carbon_number}-{mapping.carbon_number_end}"
                        )
                        rel_error = (
                            "-"
                            if mapping.normalized_relative_error is None
                            else f"{mapping.normalized_relative_error:.4f}"
                        )
                        scn_members = ",".join(str(member) for member in mapping.scn_members)
                        lines.append(
                            f"{mapping.cut_name:<8s} "
                            f"{carbon_range:<10s} "
                            f"{mapping.observed_normalized_mole_fraction:>7.4f} "
                            f"{mapping.characterized_normalized_mole_fraction:>9.4f} "
                            f"{rel_error:>10s} "
                            f"{scn_members}"
                        )
                    if len(ctx.cut_mappings) > 20:
                        lines.append(f"... ({len(ctx.cut_mappings) - 20} more)")
                if ctx.scn_distribution:
                    lines.append("")
                    lines.append("Derived SCN characterization (sample)")
                    lines.append("-----------------------------------")
                    lines.append("SCN        Assay z   Norm z      MW      SG    Tb(K)   omega")
                    for entry in ctx.scn_distribution[:20]:
                        lines.append(
                            f"{entry.component_id:<8s} "
                            f"{entry.assay_mole_fraction:>8.5f} "
                            f"{entry.normalized_mole_fraction:>8.5f} "
                            f"{entry.molecular_weight_g_per_mol:>8.3f} "
                            f"{entry.specific_gravity_60f:>7.4f} "
                            f"{entry.boiling_point_k:>8.2f} "
                            f"{entry.omega:>8.4f}"
                        )
                    if len(ctx.scn_distribution) > 20:
                        lines.append(f"... ({len(ctx.scn_distribution) - 20} more)")
                for note in ctx.notes:
                    lines.append(f"Note: {note}")
                lines.append("")

        elif result.cce_result is not None:
            r = result.cce_result
            pressure_unit, temperature_unit = _cce_units(cfg.cce_config)
            lines.append("CCE")
            lines.append("---")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            if r.saturation_pressure_pa is not None:
                lines.append(f"Psat = {_format_pressure(r.saturation_pressure_pa, pressure_unit)}")
            lines.append("")
            # Uniform 12-char columns (matches the per-step composition
            # table style) so every header is right-edge-aligned with its
            # values. Use plain ASCII L / V suffixes instead of Unicode
            # subscript glyphs (ρₗ, ρᵥ, ...) because Consolas renders the
            # subscripts at a narrower visual width than ASCII digits, which
            # drifts the right-edge of every header column leftward and
            # accumulates across the row. With ρL / ρV / μL / μV every glyph
            # is exactly one monospace cell so character-count alignment
            # equals visual alignment.
            cce_col = 12
            # Two-row header: variable name on top, units in square
            # brackets underneath. The unit row absorbs everything that
            # used to crowd the variable name (psia, V/Vsat, kg/m³, cP)
            # which lets the variable names stay short and uniform across
            # all columns — "Rel. Vol." matches the results-panel
            # Expansion table, and densities / viscosities now carry
            # their (previously missing) kg/m³ and cP labels.
            lines.append(
                f"{'P':>{cce_col}s}"
                f"{'Rel. Vol.':>{cce_col}s}"
                f"{'\u03c1L':>{cce_col}s}"
                f"{'\u03c1V':>{cce_col}s}"
                f"{'\u03bcL':>{cce_col}s}"
                f"{'\u03bcV':>{cce_col}s}"
                f"{'Z\u2011factor':>{cce_col}s}"
            )
            lines.append(
                f"{f'[{pressure_unit.value}]':>{cce_col}s}"
                f"{'[V/Vsat]':>{cce_col}s}"
                f"{'[kg/m\u00b3]':>{cce_col}s}"
                f"{'[kg/m\u00b3]':>{cce_col}s}"
                f"{'[cP]':>{cce_col}s}"
                f"{'[cP]':>{cce_col}s}"
                f"{'[\u2013]':>{cce_col}s}"
            )
            for step in r.steps[:80]:
                z = step.z_factor
                z_txt = f"{z:.5f}" if z is not None else "-"
                liquid_density = step.liquid_density_kg_per_m3
                vapor_density = step.vapor_density_kg_per_m3
                liquid_viscosity = step.liquid_viscosity_cp
                vapor_viscosity = step.vapor_viscosity_cp
                liquid_txt = (
                    f"{liquid_density:.2f}"
                    if liquid_density is not None and liquid_density > 0
                    else "-"
                )
                vapor_txt = (
                    f"{vapor_density:.2f}"
                    if vapor_density is not None and vapor_density > 0
                    else "-"
                )
                liquid_viscosity_txt = (
                    f"{liquid_viscosity:.4f}"
                    if liquid_viscosity is not None and liquid_viscosity > 0
                    else "-"
                )
                vapor_viscosity_txt = (
                    f"{vapor_viscosity:.4f}"
                    if vapor_viscosity is not None and vapor_viscosity > 0
                    else "-"
                )
                lines.append(
                    f"{pressure_from_pa(step.pressure_pa, pressure_unit):>{cce_col}.5f}"
                    f"{step.relative_volume:>{cce_col}.5f}"
                    f"{liquid_txt:>{cce_col}s}"
                    f"{vapor_txt:>{cce_col}s}"
                    f"{liquid_viscosity_txt:>{cce_col}s}"
                    f"{vapor_viscosity_txt:>{cce_col}s}"
                    f"{z_txt:>{cce_col}s}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

            lines.extend(
                _format_per_step_composition_table(
                    title="Per-step liquid composition (x)",
                    steps=r.steps,
                    pressure_unit=pressure_unit,
                    field="liquid_composition",
                )
            )
            lines.extend(
                _format_per_step_composition_table(
                    title="Per-step vapor composition (y)",
                    steps=r.steps,
                    pressure_unit=pressure_unit,
                    field="vapor_composition",
                )
            )

        elif result.dl_result is not None:
            r = result.dl_result
            pressure_unit, temperature_unit = _dl_units(cfg.dl_config)
            lines.append("Differential liberation")
            lines.append("-----------------------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"Pb = {_format_pressure(r.bubble_pressure_pa, pressure_unit)}")
            lines.append(f"RsDb = {r.rsi_scf_stb:.5f} scf/STB")
            lines.append(f"Boi = {r.boi:.5f}")
            lines.append(
                "Residual oil density = "
                f"{_format_optional_measurement(r.residual_oil_density_kg_per_m3, precision=2, unit='kg/m³')}"
            )
            lines.append(f"Converged: {r.converged}")
            lines.append("")
            # DL text output split into five narrow stacked tables so no
            # horizontal scrolling is needed — same logical grouping as
            # the results-panel split (see ResultsTableWidget._display_dl):
            #   1. GOR                      (P, RsD, RsDb)              3 cols
            #   2. Formation Volume Factors (P, Bo, Bg, BtD)             4 cols
            #   3. Oil Phase                (Step, ρO, μO, n_L)          4 cols
            #   4. Gas Phase                (Step, γg, Zg, μG)           4 cols
            #   5. Vapor Frac. & Production (Step, β, Cum. Gas)          3 cols
            # Uniform 12-char columns, two-row header (variable + unit).
            dl_col = 12
            step_rows = list(enumerate(r.steps[:80], start=1))

            def _fmt_opt(value: Optional[float], precision: int) -> str:
                if value is None or value <= 0:
                    return "-"
                return f"{value:.{precision}f}"

            p_unit_label = f"[{pressure_unit.value}]"

            # ── Table 1: GOR ─────────────────────────────────────────
            lines.append("GOR")
            lines.append(
                f"{'P':>{dl_col}s}"
                f"{'RsD':>{dl_col}s}"
                f"{'RsDb':>{dl_col}s}"
            )
            lines.append(
                f"{p_unit_label:>{dl_col}s}"
                f"{'[scf/STB]':>{dl_col}s}"
                f"{'[scf/STB]':>{dl_col}s}"
            )
            for _, step in step_rows:
                lines.append(
                    f"{pressure_from_pa(step.pressure_pa, pressure_unit):>{dl_col}.5f}"
                    f"{step.rs_scf_stb:>{dl_col}.5f}"
                    f"{r.rsi_scf_stb:>{dl_col}.5f}"
                )
            lines.append("")

            # ── Table 2: Formation Volume Factors ────────────────────
            lines.append("Formation volume factors")
            lines.append(
                f"{'P':>{dl_col}s}"
                f"{'Bo':>{dl_col}s}"
                f"{'Bg':>{dl_col}s}"
                f"{'BtD':>{dl_col}s}"
            )
            lines.append(
                f"{p_unit_label:>{dl_col}s}"
                f"{'[rb/STB]':>{dl_col}s}"
                f"{'[rb/scf]':>{dl_col}s}"
                f"{'[rb/STB]':>{dl_col}s}"
            )
            for _, step in step_rows:
                bg_txt = "-" if step.bg_rb_per_scf is None else f"{step.bg_rb_per_scf:.5f}"
                lines.append(
                    f"{pressure_from_pa(step.pressure_pa, pressure_unit):>{dl_col}.5f}"
                    f"{step.bo:>{dl_col}.5f}"
                    f"{bg_txt:>{dl_col}s}"
                    f"{step.bt:>{dl_col}.5f}"
                )
            lines.append("")

            # ── Table 3: Oil Phase ───────────────────────────────────
            lines.append("Oil phase")
            lines.append(
                f"{'Step':>{dl_col}s}"
                f"{'\u03c1O':>{dl_col}s}"
                f"{'\u03bcO':>{dl_col}s}"
                f"{'n_L':>{dl_col}s}"
            )
            lines.append(
                f"{'[#]':>{dl_col}s}"
                f"{'[kg/m\u00b3]':>{dl_col}s}"
                f"{'[cP]':>{dl_col}s}"
                f"{'[mol]':>{dl_col}s}"
            )
            for idx, step in step_rows:
                oil_density = _fmt_opt(step.oil_density_kg_per_m3, 2)
                oil_viscosity = _fmt_opt(step.oil_viscosity_cp, 4)
                liquid_moles = (
                    "-" if step.liquid_moles_remaining is None
                    else f"{step.liquid_moles_remaining:.6f}"
                )
                lines.append(
                    f"{idx:>{dl_col}d}"
                    f"{oil_density:>{dl_col}s}"
                    f"{oil_viscosity:>{dl_col}s}"
                    f"{liquid_moles:>{dl_col}s}"
                )
            lines.append("")

            # ── Table 4: Gas Phase ───────────────────────────────────
            lines.append("Gas phase")
            lines.append(
                f"{'Step':>{dl_col}s}"
                f"{'\u03b3g':>{dl_col}s}"
                f"{'Zg':>{dl_col}s}"
                f"{'\u03bcG':>{dl_col}s}"
            )
            lines.append(
                f"{'[#]':>{dl_col}s}"
                f"{'[\u2013]':>{dl_col}s}"
                f"{'[\u2013]':>{dl_col}s}"
                f"{'[cP]':>{dl_col}s}"
            )
            for idx, step in step_rows:
                gas_gravity = "-" if step.gas_gravity is None else f"{step.gas_gravity:.4f}"
                gas_z = "-" if step.gas_z_factor is None else f"{step.gas_z_factor:.4f}"
                gas_viscosity = _fmt_opt(step.gas_viscosity_cp, 4)
                lines.append(
                    f"{idx:>{dl_col}d}"
                    f"{gas_gravity:>{dl_col}s}"
                    f"{gas_z:>{dl_col}s}"
                    f"{gas_viscosity:>{dl_col}s}"
                )
            lines.append("")

            # ── Table 5: Vapor Frac. & Production ────────────────────
            lines.append("Vapor frac. & production")
            lines.append(
                f"{'Step':>{dl_col}s}"
                f"{'\u03b2':>{dl_col}s}"
                f"{'Cum. Gas':>{dl_col}s}"
            )
            lines.append(
                f"{'[#]':>{dl_col}s}"
                f"{'[frac]':>{dl_col}s}"
                f"{'[scf/STB]':>{dl_col}s}"
            )
            for idx, step in step_rows:
                cumulative_gas = (
                    "-" if step.cumulative_gas_produced_scf_stb is None
                    else f"{step.cumulative_gas_produced_scf_stb:.5f}"
                )
                lines.append(
                    f"{idx:>{dl_col}d}"
                    f"{step.vapor_fraction:>{dl_col}.5f}"
                    f"{cumulative_gas:>{dl_col}s}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

            lines.extend(
                _format_per_step_composition_table(
                    title="Per-step residual-oil composition (x)",
                    steps=r.steps,
                    pressure_unit=pressure_unit,
                    field="liquid_composition",
                )
            )
            lines.extend(
                _format_per_step_composition_table(
                    title="Per-step liberated-gas composition (y)",
                    steps=r.steps,
                    pressure_unit=pressure_unit,
                    field="gas_composition",
                )
            )

        elif result.whitson_torp_result is not None:
            r = result.whitson_torp_result
            pressure_unit, temperature_unit = _whitson_torp_units(cfg.whitson_torp_config)
            lines.append("Whitson-Torp")
            lines.append("-------------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"Pk = {_format_pressure(r.convergence_pressure_pa, pressure_unit)}")
            lines.append(f"Pb = {_format_pressure(r.bubble_pressure_pa, pressure_unit)}")
            lines.append(f"Converged = {r.converged}")
            lines.append("")

            lines.append("Incipient vapor at bubble point (y)")
            for cid, value in sorted(r.bubble_vapor_composition.items()):
                lines.append(f"{cid:<8s} {value:>12.6f}")
            lines.append("")

            wt_col = 12
            lines.append("DL flash steps")
            lines.append(
                f"{'Step':>{wt_col}s}"
                f"{'P':>{wt_col}s}"
                f"{'nL':>{wt_col}s}"
                f"{'nL actual':>{wt_col}s}"
                f"{'Bg':>{wt_col}s}"
                f"{'Zg':>{wt_col}s}"
            )
            lines.append(
                f"{'[#]':>{wt_col}s}"
                f"{f'[{pressure_unit.value}]':>{wt_col}s}"
                f"{'[frac]':>{wt_col}s}"
                f"{'[mol]':>{wt_col}s}"
                f"{'[bbl/scf]':>{wt_col}s}"
                f"{'[-]':>{wt_col}s}"
            )
            for step in r.steps[:80]:
                bg_txt = "-" if step.bg_bbl_per_scf is None else f"{step.bg_bbl_per_scf:.6f}"
                z_txt = "-" if step.gas_z_factor is None else f"{step.gas_z_factor:.5f}"
                lines.append(
                    f"{step.step_index:>{wt_col}d}"
                    f"{pressure_from_pa(step.pressure_pa, pressure_unit):>{wt_col}.3f}"
                    f"{step.liquid_fraction:>{wt_col}.6f}"
                    f"{step.liquid_moles_actual:>{wt_col}.6f}"
                    f"{bg_txt:>{wt_col}s}"
                    f"{z_txt:>{wt_col}s}"
                )
            lines.append("")

            for step in r.steps[:12]:
                lines.append(
                    f"Step {step.step_index} liquid composition (x), "
                    f"P = {_format_pressure(step.pressure_pa, pressure_unit, precision=3)}"
                )
                for cid, value in sorted(step.liquid_composition.items()):
                    lines.append(f"{cid:<8s} {value:>12.6f}")
                lines.append("")
                lines.append(f"Step {step.step_index} vapor composition (y)")
                for cid, value in sorted(step.vapor_composition.items()):
                    lines.append(f"{cid:<8s} {value:>12.6f}")
                lines.append("")

            sep = r.separator
            lines.append("Stock-tank separator")
            lines.append("--------------------")
            lines.append(f"P = {_format_pressure(sep.pressure_pa, pressure_unit)}")
            lines.append(f"T = {_format_temperature(sep.temperature_k, temperature_unit)}")
            lines.append(f"GOR = {sep.gor_scf_stb:.5f} scf/STB")
            lines.append(f"Oil MW = {sep.stock_tank_oil_mw_g_per_mol:.5f} g/mol")
            lines.append(f"Oil API = {sep.stock_tank_oil_api:.5f}")
            lines.append(f"Oil SG = {sep.stock_tank_oil_specific_gravity:.5f}")
            lines.append("")
            lines.append("Stock-tank gas composition")
            for cid, value in sorted(sep.stock_tank_gas_composition.items()):
                lines.append(f"{cid:<8s} {value:>12.6f}")
            lines.append("")
            lines.append("Stock-tank oil composition")
            for cid, value in sorted(sep.stock_tank_oil_composition.items()):
                lines.append(f"{cid:<8s} {value:>12.6f}")
            lines.append("")

        elif result.cvd_result is not None:
            r = result.cvd_result
            pressure_unit, temperature_unit = _cvd_units()
            lines.append("CVD")
            lines.append("---")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(f"Pd = {_format_pressure(r.dew_pressure_pa, pressure_unit)}")
            lines.append(f"Initial Z = {r.initial_z:.5f}")
            lines.append("")
            # 9 CVD columns on one row forced horizontal scrolling.
            # Split into two stacked tables — depletion summary +
            # phase densities/viscosities — both indexed by Step so the
            # reader can cross-reference by row without scrolling.
            # Uniform 12-char columns, two-row header (variable + unit).
            cvd_col = 12
            step_rows = list(enumerate(r.steps[:80], start=1))

            # ── Table 1: Depletion summary ───────────────────────────
            lines.append("Depletion summary")
            lines.append(
                f"{'Step':>{cvd_col}s}"
                f"{'P':>{cvd_col}s}"
                f"{'Liq. Dropout':>{cvd_col}s}"
                f"{'Gas Prod.':>{cvd_col}s}"
                f"{'Cum. Gas':>{cvd_col}s}"
                f"{'Z':>{cvd_col}s}"
            )
            lines.append(
                f"{'[#]':>{cvd_col}s}"
                f"{f'[{pressure_unit.value}]':>{cvd_col}s}"
                f"{'[frac]':>{cvd_col}s}"
                f"{'[frac]':>{cvd_col}s}"
                f"{'[frac]':>{cvd_col}s}"
                f"{'[\u2013]':>{cvd_col}s}"
            )
            for idx, step in step_rows:
                z_two_phase = "-" if step.z_two_phase is None else f"{step.z_two_phase:.5f}"
                gas_produced = "-" if step.gas_produced is None else f"{step.gas_produced:.5f}"
                lines.append(
                    f"{idx:>{cvd_col}d}"
                    f"{pressure_from_pa(step.pressure_pa, pressure_unit):>{cvd_col}.5f}"
                    f"{step.liquid_dropout:>{cvd_col}.5f}"
                    f"{gas_produced:>{cvd_col}s}"
                    f"{step.cumulative_gas_produced:>{cvd_col}.5f}"
                    f"{z_two_phase:>{cvd_col}s}"
                )
            lines.append("")

            # ── Table 2: Phase densities & viscosities ───────────────
            lines.append("Phase densities & viscosities")
            lines.append(
                f"{'Step':>{cvd_col}s}"
                f"{'\u03c1L':>{cvd_col}s}"
                f"{'\u03c1V':>{cvd_col}s}"
                f"{'\u03bcL':>{cvd_col}s}"
                f"{'\u03bcV':>{cvd_col}s}"
            )
            lines.append(
                f"{'[#]':>{cvd_col}s}"
                f"{'[kg/m\u00b3]':>{cvd_col}s}"
                f"{'[kg/m\u00b3]':>{cvd_col}s}"
                f"{'[cP]':>{cvd_col}s}"
                f"{'[cP]':>{cvd_col}s}"
            )
            for idx, step in step_rows:
                liquid_density = (
                    "-"
                    if step.liquid_density_kg_per_m3 is None or step.liquid_density_kg_per_m3 <= 0
                    else f"{step.liquid_density_kg_per_m3:.2f}"
                )
                vapor_density = (
                    "-"
                    if step.vapor_density_kg_per_m3 is None or step.vapor_density_kg_per_m3 <= 0
                    else f"{step.vapor_density_kg_per_m3:.2f}"
                )
                liquid_viscosity = (
                    "-"
                    if step.liquid_viscosity_cp is None or step.liquid_viscosity_cp <= 0
                    else f"{step.liquid_viscosity_cp:.4f}"
                )
                vapor_viscosity = (
                    "-"
                    if step.vapor_viscosity_cp is None or step.vapor_viscosity_cp <= 0
                    else f"{step.vapor_viscosity_cp:.4f}"
                )
                lines.append(
                    f"{idx:>{cvd_col}d}"
                    f"{liquid_density:>{cvd_col}s}"
                    f"{vapor_density:>{cvd_col}s}"
                    f"{liquid_viscosity:>{cvd_col}s}"
                    f"{vapor_viscosity:>{cvd_col}s}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

        elif result.swelling_test_result is not None:
            r = result.swelling_test_result
            pressure_unit, temperature_unit = _swelling_units(cfg.swelling_test_config)
            certified_steps = sum(step.status == "certified" for step in r.steps)
            lines.append("Swelling test")
            lines.append("-------------")
            lines.append(f"T = {_format_temperature(r.temperature_k, temperature_unit)}")
            lines.append(
                "Baseline Pb = "
                + (
                    "-"
                    if r.baseline_bubble_pressure_pa is None
                    else _format_pressure(r.baseline_bubble_pressure_pa, pressure_unit)
                )
            )
            lines.append(
                "Baseline sat. Vm = "
                + (
                    "-"
                    if r.baseline_saturated_liquid_molar_volume_m3_per_mol is None
                    else f"{r.baseline_saturated_liquid_molar_volume_m3_per_mol:.6e} m³/mol"
                )
            )
            lines.append(f"Certified steps = {certified_steps}/{len(r.steps)}")
            lines.append(f"Overall status = {r.overall_status}")
            lines.append(f"Fully certified = {r.fully_certified}")
            lines.append("")
            lines.append(
                f"{'Step':>4s} {'AddedGas':>10s} {'BubbleP':>14s} {'SwellFact':>10s} "
                f"{'\u03c1L':>10s} {'Status':>24s}  Message"
            )
            for step in r.steps[:80]:
                bubble_pressure = (
                    "-"
                    if step.bubble_pressure_pa is None
                    else f"{pressure_from_pa(step.bubble_pressure_pa, pressure_unit):.5f}"
                )
                swelling_factor = "-" if step.swelling_factor is None else f"{step.swelling_factor:.6f}"
                liquid_density = (
                    "-"
                    if step.saturated_liquid_density_kg_per_m3 is None
                    else f"{step.saturated_liquid_density_kg_per_m3:.2f}"
                )
                lines.append(
                    f"{step.step_index:>4d} "
                    f"{step.added_gas_moles_per_mole_oil:>10.5f} "
                    f"{bubble_pressure:>14s} "
                    f"{swelling_factor:>10s} "
                    f"{liquid_density:>10s} "
                    f"{step.status:>24s}  "
                    f"{step.message or ''}"
                )
            if len(r.steps) > 80:
                lines.append(f"... ({len(r.steps) - 80} more)")
            lines.append("")

        elif result.separator_result is not None:
            r = result.separator_result
            sep_p = PressureUnit.PSIA
            sep_t = TemperatureUnit.F
            lines.append("Separator train")
            lines.append("---------------")
            lines.append(f"Converged = {r.converged}")
            lines.append(f"Bo (rb/STB) = {r.bo:.5f}")
            lines.append(f"Rs (scf/STB) = {r.rs_scf_stb:.5f}")
            lines.append(f"Bg (rb/scf) = {(r.bg / 5.615):.5f}")
            lines.append(f"API = {r.api_gravity:.3f}")
            lines.append(f"Stock-tank oil density = {r.stock_tank_oil_density:.3f} kg/m³")
            if r.stock_tank_oil_mw_g_per_mol is not None:
                lines.append(f"Stock-tank MW = {r.stock_tank_oil_mw_g_per_mol:.4f} g/mol")
            if r.stock_tank_oil_specific_gravity is not None:
                lines.append(f"Stock-tank SG = {r.stock_tank_oil_specific_gravity:.5f}")
            if r.total_gas_moles is not None:
                lines.append(f"Total gas moles = {r.total_gas_moles:.6f}")
            if r.shrinkage is not None:
                lines.append(f"Shrinkage = {r.shrinkage:.5f}")
            lines.append("")
            lines.append(
                f"{'Stage':<12s} "
                f"{f'P ({sep_p.value})':>10s} "
                f"{f'T ({_format_temperature_unit(sep_t)})':>10s} "
                f"{'VaporFrac':>11s} "
                f"{'LiquidMol':>11s} "
                f"{'VaporMol':>11s} "
                f"{'\u03c1L':>9s} "
                f"{'\u03c1V':>9s} "
                f"{'ZL':>8s} "
                f"{'ZV':>8s}"
            )
            for stage in r.stages[:80]:
                vapor_fraction = "" if stage.vapor_fraction is None else f"{stage.vapor_fraction:.5f}"
                liquid_moles = "" if stage.liquid_moles is None else f"{stage.liquid_moles:.5f}"
                vapor_moles = "" if stage.vapor_moles is None else f"{stage.vapor_moles:.5f}"
                liquid_density = (
                    ""
                    if stage.liquid_density_kg_per_m3 is None or stage.liquid_density_kg_per_m3 <= 0
                    else f"{stage.liquid_density_kg_per_m3:.2f}"
                )
                vapor_density = (
                    ""
                    if stage.vapor_density_kg_per_m3 is None or stage.vapor_density_kg_per_m3 <= 0
                    else f"{stage.vapor_density_kg_per_m3:.2f}"
                )
                liquid_z = "" if stage.liquid_z_factor is None else f"{stage.liquid_z_factor:.5f}"
                vapor_z = "" if stage.vapor_z_factor is None else f"{stage.vapor_z_factor:.5f}"
                lines.append(
                    f"{stage.stage_name[:12]:<12s} "
                    f"{pressure_from_pa(stage.pressure_pa, sep_p):>10.2f} "
                    f"{temperature_from_k(stage.temperature_k, sep_t):>10.2f} "
                    f"{vapor_fraction:>11s} "
                    f"{liquid_moles:>11s} "
                    f"{vapor_moles:>11s} "
                    f"{liquid_density:>9s} "
                    f"{vapor_density:>9s} "
                    f"{liquid_z:>8s} "
                    f"{vapor_z:>8s}"
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

        return _lines_to_html(lines)
