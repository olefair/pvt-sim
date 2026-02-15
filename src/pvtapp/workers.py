"""QThread workers for non-blocking calculation execution.

These workers run calculations in background threads, emitting signals
for progress updates, completion, and errors. The GUI remains responsive
while calculations run.

Design principles:
- GUI never blocks: all calculations run in worker threads
- Cancellation support: workers can be cancelled cleanly
- Progress reporting: workers emit progress signals for UI updates
- Structured errors: failures include actionable error messages
"""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Signal

from pvtapp.schemas import RunConfig, RunResult, RunStatus
from pvtapp.job_runner import run_calculation, ProgressCallback


class CalculationWorker(QObject):
    """Worker for running PVT calculations in a background thread.

    Signals:
        started: Emitted when calculation starts (run_id, calculation_type)
        progress: Emitted during calculation (run_id, progress 0-100, message)
        finished: Emitted when calculation completes (RunResult)
        error: Emitted if calculation fails (run_id, error_message)

    Usage:
        thread = QThread()
        worker = CalculationWorker(config)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(handle_result)
        worker.error.connect(handle_error)

        thread.start()
    """

    # Signals
    started = Signal(str, str)  # run_id, calculation_type
    progress = Signal(str, int, str)  # run_id, progress (0-100), message
    finished = Signal(object)  # RunResult
    error = Signal(str, str)  # run_id, error_message

    def __init__(
        self,
        config: RunConfig,
        output_dir: Optional[Path] = None,
        write_artifacts: bool = True,
    ):
        """Initialize the calculation worker.

        Args:
            config: Validated run configuration
            output_dir: Directory for artifacts (default: auto-generated)
            write_artifacts: Whether to write artifact files
        """
        super().__init__()
        self.config = config
        self.output_dir = output_dir
        self.write_artifacts = write_artifacts
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the calculation.

        Note: The calculation may not stop immediately. Check the result
        status for CANCELLED status.
        """
        self._cancelled = True

    def run(self) -> None:
        """Execute the calculation.

        This method is called when the thread starts. It runs the calculation
        and emits signals for progress and completion.
        """
        run_id = self.config.run_id or "unknown"

        # Create a callback that emits Qt signals
        callback = _QtProgressCallback(
            worker=self,
            run_id=run_id,
        )

        try:
            result = run_calculation(
                config=self.config,
                output_dir=self.output_dir,
                callback=callback,
                write_artifacts=self.write_artifacts,
            )

            # Check if cancelled
            if self._cancelled:
                result = RunResult(
                    run_id=run_id,
                    run_name=self.config.run_name,
                    status=RunStatus.CANCELLED,
                    error_message="Calculation was cancelled by user",
                    started_at=result.started_at,
                    completed_at=result.completed_at,
                    duration_seconds=result.duration_seconds,
                    config=self.config,
                )

            self.finished.emit(result)

        except Exception as e:
            error_msg = str(e)
            self.error.emit(run_id, error_msg)


class _QtProgressCallback(ProgressCallback):
    """Progress callback that emits Qt signals."""

    def __init__(self, worker: CalculationWorker, run_id: str):
        self.worker = worker
        self.run_id = run_id

    def on_started(self, run_id: str, calculation_type: str) -> None:
        self.worker.started.emit(run_id, calculation_type)

    def on_progress(self, run_id: str, progress: float, message: str) -> None:
        # Convert 0-1 to 0-100 for Qt progress bars
        percent = int(progress * 100)
        self.worker.progress.emit(run_id, percent, message)

    def on_completed(self, run_id: str, result: RunResult) -> None:
        # Completion is handled by the worker
        pass

    def on_failed(self, run_id: str, error: str) -> None:
        # Failure is handled by the worker
        pass

    def on_cancelled(self, run_id: str) -> None:
        pass


class CalculationThread(QThread):
    """Convenience class combining QThread and CalculationWorker.

    This simplifies the common pattern of running a calculation in a
    background thread.

    Usage:
        thread = CalculationThread(config)
        thread.progress.connect(update_progress_bar)
        thread.finished.connect(handle_result)
        thread.error.connect(handle_error)
        thread.start()
    """

    # Signals (forwarded from worker)
    started = Signal(str, str)
    progress = Signal(str, int, str)
    finished = Signal(object)
    error = Signal(str, str)

    def __init__(
        self,
        config: RunConfig,
        output_dir: Optional[Path] = None,
        write_artifacts: bool = True,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.config = config
        self.output_dir = output_dir
        self.write_artifacts = write_artifacts
        self._worker: Optional[CalculationWorker] = None

    def run(self) -> None:
        """Thread entry point - creates and runs the worker."""
        self._worker = CalculationWorker(
            config=self.config,
            output_dir=self.output_dir,
            write_artifacts=self.write_artifacts,
        )

        # Connect worker signals to thread signals
        self._worker.started.connect(self.started.emit)
        self._worker.progress.connect(self.progress.emit)
        self._worker.finished.connect(self.finished.emit)
        self._worker.error.connect(self.error.emit)

        # Run the calculation
        self._worker.run()

    def cancel(self) -> None:
        """Request cancellation of the calculation."""
        if self._worker:
            self._worker.cancel()


class BatchCalculationWorker(QObject):
    """Worker for running multiple calculations sequentially.

    Useful for parameter sweeps or running a suite of calculations.

    Signals:
        batch_started: Emitted when batch starts (total_count)
        calculation_started: Emitted for each calculation (index, run_id)
        calculation_finished: Emitted for each calculation (index, RunResult)
        batch_progress: Emitted after each calculation (completed_count, total_count)
        batch_finished: Emitted when all calculations complete (list of RunResults)
        error: Emitted if a calculation fails (index, run_id, error_message)
    """

    batch_started = Signal(int)
    calculation_started = Signal(int, str)
    calculation_finished = Signal(int, object)
    batch_progress = Signal(int, int)
    batch_finished = Signal(list)
    error = Signal(int, str, str)

    def __init__(
        self,
        configs: list,  # List[RunConfig]
        output_dir: Optional[Path] = None,
        write_artifacts: bool = True,
        stop_on_error: bool = False,
    ):
        """Initialize batch calculation worker.

        Args:
            configs: List of RunConfig objects to execute
            output_dir: Directory for artifacts
            write_artifacts: Whether to write artifact files
            stop_on_error: If True, stop batch on first error
        """
        super().__init__()
        self.configs = configs
        self.output_dir = output_dir
        self.write_artifacts = write_artifacts
        self.stop_on_error = stop_on_error
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation of the batch."""
        self._cancelled = True

    def run(self) -> None:
        """Execute all calculations in sequence."""
        results = []
        total = len(self.configs)

        self.batch_started.emit(total)

        for i, config in enumerate(self.configs):
            if self._cancelled:
                break

            run_id = config.run_id or f"batch_{i}"
            self.calculation_started.emit(i, run_id)

            try:
                result = run_calculation(
                    config=config,
                    output_dir=self.output_dir,
                    write_artifacts=self.write_artifacts,
                )
                results.append(result)
                self.calculation_finished.emit(i, result)

            except Exception as e:
                error_msg = str(e)
                self.error.emit(i, run_id, error_msg)

                if self.stop_on_error:
                    break

                # Create a failed result
                from datetime import datetime
                failed_result = RunResult(
                    run_id=run_id,
                    status=RunStatus.FAILED,
                    error_message=error_msg,
                    started_at=datetime.now(),
                    config=config,
                )
                results.append(failed_result)

            self.batch_progress.emit(i + 1, total)

        self.batch_finished.emit(results)
