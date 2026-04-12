"""Runtime contract tests for pvtapp calculation dispatch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pvtapp.job_runner import ProgressCallback, run_calculation, validate_runtime_config
from pvtapp.schemas import RunConfig, RunStatus


def _pt_flash_config(*, eos_type: str = "peng_robinson") -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": f"PT Flash - {eos_type}",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": eos_type,
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )


def test_validate_runtime_config_accepts_peng_robinson() -> None:
    config = _pt_flash_config()

    validate_runtime_config(config)


def test_validate_runtime_config_rejects_srk() -> None:
    config = _pt_flash_config(eos_type="srk")

    try:
        validate_runtime_config(config)
    except ValueError as exc:
        assert str(exc) == "EOS 'srk' is declared in the schema but is not implemented in pvtcore/eos"
    else:  # pragma: no cover - explicit contract failure
        raise AssertionError("validate_runtime_config() accepted unsupported EOS 'srk'")


def test_validate_runtime_config_rejects_pr78() -> None:
    config = _pt_flash_config(eos_type="pr78")

    try:
        validate_runtime_config(config)
    except ValueError as exc:
        assert str(exc) == (
            "EOS 'pr78' is not a standalone runtime EOS in the current codebase; "
            "predictive PPR78 BIP wiring is not implemented"
        )
    else:  # pragma: no cover - explicit contract failure
        raise AssertionError("validate_runtime_config() accepted unsupported EOS 'pr78'")


def test_run_calculation_fails_fast_for_unsupported_runtime_eos() -> None:
    config = _pt_flash_config(eos_type="srk")

    result = run_calculation(config=config, write_artifacts=False)

    assert result.status == RunStatus.FAILED
    assert result.error_message == (
        "EOS 'srk' is declared in the schema but is not implemented in pvtcore/eos"
    )


class _CancelAfterDispatchCallback(ProgressCallback):
    """Simulate a user cancelling once the runtime reaches the solve boundary."""

    def __init__(self) -> None:
        self._cancelled = False
        self.cancelled_run_id: str | None = None

    def on_progress(self, run_id: str, progress: float, message: str) -> None:
        if progress >= 0.3:
            self._cancelled = True

    def on_cancelled(self, run_id: str) -> None:
        self.cancelled_run_id = run_id

    def is_cancelled(self) -> bool:
        return self._cancelled


def test_run_calculation_writes_cancelled_manifest_when_callback_requests_stop(
    tmp_path: Path,
) -> None:
    config = _pt_flash_config()
    callback = _CancelAfterDispatchCallback()

    result = run_calculation(
        config=config,
        output_dir=tmp_path,
        callback=callback,
        write_artifacts=True,
    )

    assert result.status == RunStatus.CANCELLED
    assert result.error_message == "Calculation was cancelled by user"
    assert result.pt_flash_result is None
    assert callback.cancelled_run_id == result.run_id

    run_dirs = sorted(tmp_path.iterdir())
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    with (run_dir / "manifest.json").open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    with (run_dir / "results.json").open("r", encoding="utf-8") as handle:
        stored_result = json.load(handle)

    assert manifest["status"] == RunStatus.CANCELLED.value
    assert manifest["error_message"] == "Calculation was cancelled by user"
    assert stored_result["status"] == RunStatus.CANCELLED.value
    assert stored_result["error_message"] == "Calculation was cancelled by user"
    assert stored_result["pt_flash_result"] is None


def test_calculation_thread_preserves_cancel_request_before_worker_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("PySide6")
    from pvtapp.workers import CalculationThread, CalculationWorker

    observed: dict[str, bool] = {}

    def fake_run(self: CalculationWorker) -> None:
        observed["cancelled"] = self._cancelled

    monkeypatch.setattr(CalculationWorker, "run", fake_run)

    thread = CalculationThread(config=_pt_flash_config())
    thread.cancel()
    thread.run()

    assert observed["cancelled"] is True
