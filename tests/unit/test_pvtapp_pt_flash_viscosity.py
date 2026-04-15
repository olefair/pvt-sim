"""PT-flash viscosity runtime and GUI wiring tests."""

from __future__ import annotations

import os

import pytest

from pvtapp.job_runner import run_calculation
from pvtapp.schemas import RunConfig, RunStatus

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _pt_flash_config() -> RunConfig:
    return RunConfig.model_validate(
        {
            "run_name": "PT Flash - viscosity wiring",
            "composition": {
                "components": [
                    {"component_id": "C1", "mole_fraction": 0.5},
                    {"component_id": "C10", "mole_fraction": 0.5},
                ]
            },
            "calculation_type": "pt_flash",
            "eos_type": "peng_robinson",
            "pt_flash_config": {
                "pressure_pa": 5.0e6,
                "temperature_k": 350.0,
            },
        }
    )


def _run_pt_flash():
    result = run_calculation(_pt_flash_config(), write_artifacts=False)
    assert result.status == RunStatus.COMPLETED
    assert result.pt_flash_result is not None
    return result


def test_run_calculation_populates_pt_flash_density_viscosity_and_ift() -> None:
    result = _run_pt_flash()
    flash = result.pt_flash_result
    assert flash is not None

    assert flash.phase == "two-phase"
    assert flash.liquid_density_kg_per_m3 is not None
    assert flash.vapor_density_kg_per_m3 is not None
    assert flash.liquid_density_kg_per_m3 > flash.vapor_density_kg_per_m3 > 0.0

    assert flash.liquid_viscosity_pa_s is not None
    assert flash.vapor_viscosity_pa_s is not None
    assert flash.liquid_viscosity_pa_s > flash.vapor_viscosity_pa_s > 0.0

    assert flash.liquid_viscosity_cp is not None
    assert flash.vapor_viscosity_cp is not None
    assert flash.liquid_viscosity_cp == pytest.approx(flash.liquid_viscosity_pa_s * 1000.0)
    assert flash.vapor_viscosity_cp == pytest.approx(flash.vapor_viscosity_pa_s * 1000.0)

    assert flash.interfacial_tension_n_per_m is not None
    assert flash.interfacial_tension_n_per_m > 0.0
    assert flash.interfacial_tension_mn_per_m is not None
    assert flash.interfacial_tension_mn_per_m == pytest.approx(
        flash.interfacial_tension_n_per_m * 1000.0
    )


@pytest.fixture
def app():
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication

    existing = QApplication.instance()
    if existing is not None:
        return existing
    return QApplication([])


@pytest.mark.gui_contract
def test_pt_flash_widgets_display_density_viscosity_and_ift(app) -> None:
    from pvtapp.widgets.results_view import ResultsTableWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget

    result = _run_pt_flash()
    flash = result.pt_flash_result
    assert flash is not None

    table = ResultsTableWidget()
    table.display_result(result)
    summary = {
        table.summary_table.item(row, 0).text(): table.summary_table.item(row, 1).text()
        for row in range(table.summary_table.rowCount())
    }

    assert summary["Liquid Density"] == f"{flash.liquid_density_kg_per_m3:.2f} kg/m³"
    assert summary["Vapor Density"] == f"{flash.vapor_density_kg_per_m3:.2f} kg/m³"
    assert summary["Liquid Viscosity"] == f"{flash.liquid_viscosity_cp:.4f} cP"
    assert summary["Vapor Viscosity"] == f"{flash.vapor_viscosity_cp:.4f} cP"
    assert summary["Interfacial Tension"] == f"{flash.interfacial_tension_mn_per_m:.4f} mN/m"

    text = TextOutputWidget()
    text.display_result(result)
    report = text.text.toPlainText()

    assert f"Liquid density: {flash.liquid_density_kg_per_m3:.2f} kg/m³" in report
    assert f"Vapor density: {flash.vapor_density_kg_per_m3:.2f} kg/m³" in report
    assert f"Liquid viscosity: {flash.liquid_viscosity_cp:.4f} cP" in report
    assert f"Vapor viscosity: {flash.vapor_viscosity_cp:.4f} cP" in report
    assert f"Interfacial tension: {flash.interfacial_tension_mn_per_m:.4f} mN/m" in report
