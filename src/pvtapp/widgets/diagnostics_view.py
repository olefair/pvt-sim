"""Diagnostics view widget for solver convergence analysis.

Displays iteration history, convergence status, and solver performance
metrics for debugging and analysis.
"""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QLabel,
    QGroupBox,
    QProgressBar,
    QTextEdit,
)

from pvtapp.schemas import (
    RunResult,
    RunStatus,
    SolverDiagnostics,
    SolverCertificate,
    ConvergenceStatusEnum,
    StabilityAnalysisResult,
)
from pvtapp.style import DEFAULT_UI_SCALE, scale_metric


class DiagnosticsWidget(QWidget):
    """Widget for displaying solver diagnostics and convergence info."""

    _DEFAULT_HISTORY_HEADERS = [
        "Iteration", "Residual", "Step Norm", "Damping", "Time (ms)"
    ]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._ui_scale = DEFAULT_UI_SCALE
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Create the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Convergence status group
        status_group = QGroupBox("Convergence Status")
        status_layout = QVBoxLayout(status_group)

        # Status indicator
        status_row = QHBoxLayout()
        status_row.addWidget(QLabel("Status:"))
        self.status_label = QLabel("No calculation")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_layout.addLayout(status_row)

        # Metrics grid
        metrics_layout = QHBoxLayout()

        # Iterations
        iter_box = QVBoxLayout()
        iter_box.addWidget(QLabel("Iterations"))
        self.iterations_label = QLabel("-")
        self.iterations_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.iterations_label.setStyleSheet("font-weight: bold;")
        iter_box.addWidget(self.iterations_label)
        metrics_layout.addLayout(iter_box)

        # Final residual
        res_box = QVBoxLayout()
        res_box.addWidget(QLabel("Final Residual"))
        self.residual_label = QLabel("-")
        self.residual_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.residual_label.setStyleSheet("font-weight: bold;")
        res_box.addWidget(self.residual_label)
        metrics_layout.addLayout(res_box)

        # Reduction ratio
        red_box = QVBoxLayout()
        red_box.addWidget(QLabel("Residual Reduction"))
        self.reduction_label = QLabel("-")
        self.reduction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reduction_label.setStyleSheet("font-weight: bold;")
        red_box.addWidget(self.reduction_label)
        metrics_layout.addLayout(red_box)

        status_layout.addLayout(metrics_layout)

        # Progress bar (for displaying relative convergence)
        self.convergence_bar = QProgressBar()
        self.convergence_bar.setMaximum(100)
        self.convergence_bar.setValue(0)
        self.convergence_bar.setFormat("Convergence Quality")
        status_layout.addWidget(self.convergence_bar)

        layout.addWidget(status_group)

        # Iteration history table
        history_group = QGroupBox("Iteration History")
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(self._DEFAULT_HISTORY_HEADERS)
        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.history_table.setAlternatingRowColors(True)
        history_layout.addWidget(self.history_table)

        layout.addWidget(history_group)

        # Convergence plot placeholder
        self.plot_group = QGroupBox("Convergence Plot")
        plot_layout = QVBoxLayout(self.plot_group)

        try:
            from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
            from matplotlib.figure import Figure

            self.figure = Figure(figsize=(6, 3), dpi=100)
            self.canvas = FigureCanvasQTAgg(self.figure)
            plot_layout.addWidget(self.canvas)
            self._matplotlib_available = True

        except ImportError:
            self._matplotlib_available = False
            placeholder = QLabel("Matplotlib not available for convergence plot")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            plot_layout.addWidget(placeholder)

        layout.addWidget(self.plot_group)

        # Error/warning log
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_group)

        self.apply_ui_scale(self._ui_scale)

    def apply_ui_scale(self, ui_scale: float) -> None:
        """Scale diagnostic widget elements that are not controlled by QSS."""
        self._ui_scale = ui_scale
        iterations_px = scale_metric(24, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        detail_px = scale_metric(19, ui_scale, reference_scale=DEFAULT_UI_SCALE)
        self.iterations_label.setStyleSheet(f"font-size: {iterations_px}px; font-weight: bold;")
        self.residual_label.setStyleSheet(f"font-size: {detail_px}px; font-weight: bold;")
        self.reduction_label.setStyleSheet(f"font-size: {detail_px}px; font-weight: bold;")
        self.log_text.setMaximumHeight(scale_metric(100, ui_scale, reference_scale=DEFAULT_UI_SCALE))

    def clear(self) -> None:
        """Clear all diagnostics displays."""
        self.status_label.setText("No calculation")
        self.status_label.setStyleSheet("font-weight: bold;")
        self.iterations_label.setText("-")
        self.residual_label.setText("-")
        self.reduction_label.setText("-")
        self.convergence_bar.setValue(0)
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(self._DEFAULT_HISTORY_HEADERS)
        self.history_table.setRowCount(0)
        self.log_text.clear()

        if self._matplotlib_available:
            self.figure.clear()
            self.canvas.draw()

    def display_result(self, result: RunResult) -> None:
        """Display diagnostics from a calculation result.

        Args:
            result: RunResult containing diagnostics
        """
        self.log_text.clear()

        # Handle error cases
        if result.status == RunStatus.FAILED:
            self._display_failure(result)
            return

        if result.status == RunStatus.CANCELLED:
            self._display_cancelled(result)
            return

        # Get diagnostics from the appropriate result type
        diagnostics = None
        certificate = None
        if result.pt_flash_result:
            diagnostics = result.pt_flash_result.diagnostics
            certificate = result.pt_flash_result.certificate
        elif result.stability_analysis_result:
            self._display_stability_analysis(result.stability_analysis_result)
            return
        elif result.bubble_point_result:
            diagnostics = result.bubble_point_result.diagnostics
            certificate = result.bubble_point_result.certificate
        elif result.dew_point_result:
            diagnostics = result.dew_point_result.diagnostics
            certificate = result.dew_point_result.certificate

        if diagnostics:
            self._display_diagnostics(diagnostics)
            self._append_certificate_summary(certificate)
        else:
            self.log_text.append("No solver diagnostics available")

    def _display_diagnostics(self, diag: SolverDiagnostics) -> None:
        """Display solver diagnostics."""
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(self._DEFAULT_HISTORY_HEADERS)
        # Status with color coding
        status = diag.status
        color_map = {
            ConvergenceStatusEnum.CONVERGED: ("green", "CONVERGED"),
            ConvergenceStatusEnum.MAX_ITERS: ("orange", "MAX ITERATIONS"),
            ConvergenceStatusEnum.DIVERGED: ("red", "DIVERGED"),
            ConvergenceStatusEnum.STAGNATED: ("orange", "STAGNATED"),
            ConvergenceStatusEnum.INVALID_INPUT: ("red", "INVALID INPUT"),
            ConvergenceStatusEnum.NUMERIC_ERROR: ("red", "NUMERIC ERROR"),
        }
        color, text = color_map.get(status, ("black", status.value.upper()))
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")

        # Metrics
        self.iterations_label.setText(str(diag.iterations))
        self.residual_label.setText(f"{diag.final_residual:.2e}")

        # Reduction ratio
        if diag.residual_reduction is not None:
            self.reduction_label.setText(f"{diag.residual_reduction:.2e}")
        else:
            self.reduction_label.setText("-")

        # Convergence quality bar (log scale mapping)
        if diag.final_residual > 0:
            import math
            # Map log10(residual) from [-15, 0] to [100, 0]
            log_res = math.log10(diag.final_residual)
            quality = max(0, min(100, int(-log_res * 100 / 15)))
            self.convergence_bar.setValue(quality)
        else:
            self.convergence_bar.setValue(100)

        # Iteration history table
        history = diag.iteration_history
        self.history_table.setRowCount(len(history))

        for row, record in enumerate(history):
            self.history_table.setItem(
                row, 0, QTableWidgetItem(str(record.iteration))
            )
            self.history_table.setItem(
                row, 1, QTableWidgetItem(f"{record.residual:.2e}")
            )
            self.history_table.setItem(
                row, 2, QTableWidgetItem(
                    f"{record.step_norm:.2e}" if record.step_norm else "-"
                )
            )
            self.history_table.setItem(
                row, 3, QTableWidgetItem(
                    f"{record.damping:.3f}" if record.damping else "-"
                )
            )
            self.history_table.setItem(
                row, 4, QTableWidgetItem(
                    f"{record.timing_ms:.2f}" if record.timing_ms else "-"
                )
            )

        # Convergence plot
        if self._matplotlib_available and history:
            self._plot_convergence(history)

        # Log summary
        self.log_text.append(
            f"Solver completed in {diag.iterations} iterations"
        )
        self.log_text.append(
            f"Function evaluations: {diag.n_func_evals}"
        )
        self.log_text.append(
            f"Jacobian evaluations: {diag.n_jac_evals}"
        )

    def _display_stability_analysis(self, result: StabilityAnalysisResult) -> None:
        """Display standalone stability-analysis branch diagnostics."""
        status_text = "STABLE" if result.stable else "UNSTABLE"
        status_color = "green" if result.stable else "orange"
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")

        trials = [
            ("Vapor-like", result.vapor_like_trial),
            ("Liquid-like", result.liquid_like_trial),
        ]
        present_trials = [(label, trial) for label, trial in trials if trial is not None]
        total_iterations = sum(trial.total_iterations for _label, trial in present_trials)
        total_eos_failures = sum(trial.n_eos_failures for _label, trial in present_trials)
        converged_trials = sum(1 for _label, trial in present_trials if trial.converged)

        self.iterations_label.setText(str(total_iterations))
        self.residual_label.setText(f"{result.tpd_min:.2e}")
        self.reduction_label.setText("-")

        if not present_trials:
            self.convergence_bar.setValue(0)
        else:
            self.convergence_bar.setValue(int(round(100.0 * converged_trials / len(present_trials))))

        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(
            ["Trial", "TPD", "Iterations", "Phi Calls", "EOS Failures"]
        )
        self.history_table.setRowCount(len(present_trials))
        for row, (label, trial) in enumerate(present_trials):
            self.history_table.setItem(row, 0, QTableWidgetItem(label))
            self.history_table.setItem(row, 1, QTableWidgetItem(f"{trial.tpd:.2e}"))
            self.history_table.setItem(row, 2, QTableWidgetItem(str(trial.total_iterations)))
            self.history_table.setItem(row, 3, QTableWidgetItem(str(trial.n_phi_calls)))
            self.history_table.setItem(row, 4, QTableWidgetItem(str(trial.n_eos_failures)))

        if self._matplotlib_available:
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            labels = [label for label, _trial in present_trials]
            values = [trial.tpd for _label, trial in present_trials]
            colors = ["#22c55e" if value >= 0.0 else "#ef4444" for value in values]
            ax.bar(labels, values, color=colors, alpha=0.85)
            ax.axhline(0.0, color="#94a3b8", linestyle="--", linewidth=1.2)
            ax.set_title("TPD Trial Summary")
            ax.set_ylabel("TPD")
            self.figure.tight_layout()
            self.canvas.draw()

        self.log_text.append(f"Minimum TPD: {result.tpd_min:.6e}")
        self.log_text.append(f"Phase regime: {result.phase_regime}")
        self.log_text.append(f"Physical state hint: {result.physical_state_hint}")
        self.log_text.append(f"Hint basis: {result.physical_state_hint_basis}")
        self.log_text.append(f"Hint confidence: {result.physical_state_hint_confidence}")
        self.log_text.append(f"Requested feed phase: {result.requested_feed_phase.value}")
        self.log_text.append(f"Resolved feed phase: {result.resolved_feed_phase}")
        self.log_text.append(f"Reference root used: {result.reference_root_used}")
        if result.best_unstable_trial_kind is not None:
            self.log_text.append(f"Best unstable trial: {result.best_unstable_trial_kind}")
        self.log_text.append(f"Total EOS failures: {total_eos_failures}")
        if result.liquid_root_z is not None:
            self.log_text.append(f"Liquid root Z: {result.liquid_root_z:.6f}")
        if result.vapor_root_z is not None:
            self.log_text.append(f"Vapor root Z: {result.vapor_root_z:.6f}")
        if result.root_gap is not None:
            self.log_text.append(f"Root gap: {result.root_gap:.6e}")
        if result.gibbs_gap is not None:
            self.log_text.append(f"Gibbs gap: {result.gibbs_gap:.6e}")
        if result.average_reduced_pressure is not None:
            self.log_text.append(f"Average reduced pressure: {result.average_reduced_pressure:.6f}")
        if result.bubble_pressure_hint_pa is not None:
            self.log_text.append(f"Bubble pressure hint: {result.bubble_pressure_hint_pa:.6e} Pa")
        if result.dew_pressure_hint_pa is not None:
            self.log_text.append(f"Dew pressure hint: {result.dew_pressure_hint_pa:.6e} Pa")
        if result.bubble_boundary_reason is not None:
            self.log_text.append(f"Bubble boundary reason: {result.bubble_boundary_reason}")
        if result.dew_boundary_reason is not None:
            self.log_text.append(f"Dew boundary reason: {result.dew_boundary_reason}")

        for label, trial in present_trials:
            self.log_text.append("")
            self.log_text.append(f"{label} branch: TPD={trial.tpd:.6e}, converged={trial.converged}")
            self.log_text.append(
                f"Seed attempts: {trial.seed_attempts}/{trial.candidate_seed_count}; "
                f"best seed={trial.best_seed.seed_label}"
            )
            if trial.diagnostic_messages:
                for message in trial.diagnostic_messages:
                    if message:
                        self.log_text.append(f"- {message}")
            for seed in trial.seed_results:
                self.log_text.append(
                    "  "
                    f"{seed.seed_label}: tpd={seed.tpd:.6e}, converged={seed.converged}, "
                    f"iters={seed.iterations}, phi={seed.n_phi_calls}, eos_failures={seed.n_eos_failures}"
                )

    def _append_certificate_summary(self, certificate: Optional[SolverCertificate]) -> None:
        """Append invariant-certificate status to the diagnostics log when available."""
        if certificate is None:
            return

        self.log_text.append("")
        self.log_text.append(
            f"Invariant certificate: {'PASS' if certificate.passed else 'FAIL'}"
        )
        self.log_text.append(
            f"Certificate status: {certificate.status.value.replace('_', ' ').title()}"
        )

        failed_checks = [
            check.name
            for check in certificate.checks
            if check.applicable and not check.passed
        ]
        if failed_checks:
            self.log_text.append(f"Failed checks: {', '.join(failed_checks)}")

    def _plot_convergence(self, history) -> None:
        """Plot convergence history."""
        from matplotlib.ticker import MaxNLocator

        self.figure.clear()
        ax = self.figure.add_subplot(111)

        iterations = [r.iteration for r in history]
        residuals = [r.residual for r in history]

        ax.semilogy(iterations, residuals, 'b-o', linewidth=1.5, markersize=4)
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Residual')
        ax.set_title('Convergence History')
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.grid(True, alpha=0.3)

        self.figure.tight_layout()
        self.canvas.draw()

    def _display_failure(self, result: RunResult) -> None:
        """Display failure information."""
        self.status_label.setText("FAILED")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        self.iterations_label.setText("-")
        self.residual_label.setText("-")
        self.reduction_label.setText("-")
        self.convergence_bar.setValue(0)
        self.history_table.setRowCount(0)

        if result.error_message:
            self.log_text.append(f"Error: {result.error_message}")
        else:
            self.log_text.append("Calculation failed with unknown error")

    def _display_cancelled(self, result: RunResult) -> None:
        """Display cancelled information."""
        self.status_label.setText("CANCELLED")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")

        self.iterations_label.setText("-")
        self.residual_label.setText("-")
        self.reduction_label.setText("-")
        self.convergence_bar.setValue(0)
        self.history_table.setRowCount(0)

        self.log_text.append("Calculation was cancelled by user")
