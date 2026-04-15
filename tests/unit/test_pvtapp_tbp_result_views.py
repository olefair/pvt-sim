"""Regression tests for TBP result presentation widgets."""

from __future__ import annotations

import os
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    QApplication = None  # type: ignore[assignment]

from pvtapp.schemas import (
    CalculationType,
    RunConfig,
    RunResult,
    RunStatus,
    SolverSettings,
    TBPCharacterizationContext,
    TBPCharacterizationCutMapping,
    TBPCharacterizationPedersenFit,
    TBPCharacterizationSCNEntry,
    TBPExperimentCutResult,
    TBPExperimentResult,
)

try:
    from pvtapp.widgets.results_view import ResultsPlotWidget, ResultsTableWidget
    from pvtapp.widgets.text_output_view import TextOutputWidget
except ModuleNotFoundError:  # pragma: no cover - environment dependent
    ResultsPlotWidget = None  # type: ignore[assignment]
    ResultsTableWidget = None  # type: ignore[assignment]
    TextOutputWidget = None  # type: ignore[assignment]


@pytest.fixture(scope="module")
def app() -> QApplication:
    if (
        QApplication is None
        or ResultsPlotWidget is None
        or ResultsTableWidget is None
        or TextOutputWidget is None
    ):
        pytest.skip("PySide6/matplotlib is not installed in this test environment")
    instance = QApplication.instance()
    if instance is not None:
        return instance
    return QApplication([])


def _build_tbp_run_result() -> RunResult:
    return RunResult(
        run_id="tbp-view-test",
        run_name="tbp-view-test",
        status=RunStatus.COMPLETED,
        started_at=datetime(2026, 4, 14, 11, 0, 0),
        completed_at=datetime(2026, 4, 14, 11, 0, 2),
        duration_seconds=2.0,
        config=RunConfig(
            calculation_type=CalculationType.TBP,
            solver_settings=SolverSettings(),
            tbp_config={
                "cuts": [
                    {"name": "C7-C9", "z": 0.020, "mw": 103.0, "sg": 0.74, "tb_k": 385.0},
                    {"name": "C12", "z": 0.015, "mw": 170.0, "sg": 0.77},
                    {"name": "C15-C18", "z": 0.015, "mw": 235.0, "sg": 0.80},
                ]
            },
        ),
        tbp_result=TBPExperimentResult(
            cut_start=7,
            cut_end=18,
            z_plus=0.05,
            mw_plus_g_per_mol=164.8,
            cuts=[
                TBPExperimentCutResult(
                    name="C7-C9",
                    carbon_number=7,
                    carbon_number_end=9,
                    mole_fraction=0.020,
                    normalized_mole_fraction=0.4,
                    cumulative_mole_fraction=0.4,
                    molecular_weight_g_per_mol=103.0,
                    normalized_mass_fraction=0.25,
                    cumulative_mass_fraction=0.25,
                    specific_gravity=0.74,
                    boiling_point_k=385.0,
                    boiling_point_source="input",
                ),
                TBPExperimentCutResult(
                    name="C12",
                    carbon_number=12,
                    carbon_number_end=12,
                    mole_fraction=0.015,
                    normalized_mole_fraction=0.3,
                    cumulative_mole_fraction=0.7,
                    molecular_weight_g_per_mol=170.0,
                    normalized_mass_fraction=0.3098305084745763,
                    cumulative_mass_fraction=0.5598305084745763,
                    specific_gravity=0.77,
                    boiling_point_k=500.0,
                    boiling_point_source="estimated_soreide",
                ),
                TBPExperimentCutResult(
                    name="C15-C18",
                    carbon_number=15,
                    carbon_number_end=18,
                    mole_fraction=0.015,
                    normalized_mole_fraction=0.3,
                    cumulative_mole_fraction=1.0,
                    molecular_weight_g_per_mol=235.0,
                    normalized_mass_fraction=0.4401694915254237,
                    cumulative_mass_fraction=1.0,
                    specific_gravity=0.80,
                    boiling_point_k=620.0,
                    boiling_point_source="estimated_soreide",
                ),
            ],
            characterization_context=TBPCharacterizationContext(
                bridge_status="characterized_scn",
                plus_fraction_label="C7+",
                cut_start=7,
                cut_end=18,
                cut_count=3,
                z_plus=0.05,
                mw_plus_g_per_mol=164.8,
                characterization_method="pedersen_fit_to_tbp",
                split_mw_model="table",
                pseudo_property_correlation="riazi_daubert",
                runtime_component_basis="scn_unlumped",
                pedersen_fit=TBPCharacterizationPedersenFit(
                    solve_ab_from="fit_to_tbp",
                    A=-3.2571,
                    B=0.0124,
                    tbp_cut_rms_relative_error=0.0182,
                ),
                cut_mappings=[
                    TBPCharacterizationCutMapping(
                        cut_name="C7-C9",
                        carbon_number=7,
                        carbon_number_end=9,
                        observed_mole_fraction=0.020,
                        observed_normalized_mole_fraction=0.4,
                        characterized_mole_fraction=0.0202,
                        characterized_normalized_mole_fraction=0.404,
                        characterized_average_molecular_weight_g_per_mol=104.0,
                        normalized_relative_error=0.01,
                        scn_members=[7, 8, 9],
                    ),
                    TBPCharacterizationCutMapping(
                        cut_name="C12",
                        carbon_number=12,
                        carbon_number_end=12,
                        observed_mole_fraction=0.015,
                        observed_normalized_mole_fraction=0.3,
                        characterized_mole_fraction=0.0148,
                        characterized_normalized_mole_fraction=0.296,
                        characterized_average_molecular_weight_g_per_mol=170.0,
                        normalized_relative_error=-0.0133,
                        scn_members=[12],
                    ),
                ],
                scn_distribution=[
                    TBPCharacterizationSCNEntry(
                        component_id="SCN7",
                        carbon_number=7,
                        assay_mole_fraction=0.0067,
                        normalized_mole_fraction=0.134,
                        normalized_mass_fraction=0.079,
                        molecular_weight_g_per_mol=96.0,
                        specific_gravity_60f=0.731,
                        boiling_point_k=371.6,
                        critical_temperature_k=540.2,
                        critical_pressure_pa=2740000.0,
                        critical_volume_m3_per_mol=0.00043,
                        omega=0.351,
                    ),
                    TBPCharacterizationSCNEntry(
                        component_id="SCN12",
                        carbon_number=12,
                        assay_mole_fraction=0.0148,
                        normalized_mole_fraction=0.296,
                        normalized_mass_fraction=0.305,
                        molecular_weight_g_per_mol=170.0,
                        specific_gravity_60f=0.781,
                        boiling_point_k=489.2,
                        critical_temperature_k=665.4,
                        critical_pressure_pa=1820000.0,
                        critical_volume_m3_per_mol=0.00071,
                        omega=0.615,
                    ),
                    TBPCharacterizationSCNEntry(
                        component_id="SCN15",
                        carbon_number=15,
                        assay_mole_fraction=0.0096,
                        normalized_mole_fraction=0.192,
                        normalized_mass_fraction=0.287,
                        molecular_weight_g_per_mol=212.0,
                        specific_gravity_60f=0.812,
                        boiling_point_k=572.8,
                        critical_temperature_k=742.1,
                        critical_pressure_pa=1460000.0,
                        critical_volume_m3_per_mol=0.00092,
                        omega=0.792,
                    ),
                ],
                notes=[
                    "Standalone TBP assay artifacts now preserve a bounded SCN characterization bridge.",
                ],
            ),
        ),
    )


def _summary_rows(widget: ResultsTableWidget) -> dict[str, str]:
    return {
        widget.summary_table.item(row, 0).text(): widget.summary_table.item(row, 1).text()
        for row in range(widget.summary_table.rowCount())
    }


def test_tbp_results_table_displays_cut_sections(app: QApplication) -> None:
    widget = ResultsTableWidget()
    widget.display_result(_build_tbp_run_result())

    summary = _summary_rows(widget)
    assert summary["Cut Start"] == "7"
    assert summary["MW+"] == "164.800 g/mol"
    assert summary["Tb Curve"] == "Available"
    assert summary["Bridge Source"] == "TBP assay"
    assert summary["Bridge Status"] == "Characterized SCN"
    assert summary["Bridge Label"] == "C7+"
    assert summary["SCNs"] == "3"
    assert widget.composition_section.title() == "Cuts"
    assert widget.details_section.title() == "Curves"
    assert widget.composition_table.rowCount() == 3
    assert widget.composition_table.horizontalHeaderItem(0).text() == "Cut"
    assert widget.composition_table.item(0, 1).text() == "7-9"
    assert widget.composition_table.item(0, 6).text() == "385.00"
    assert widget.details_table.item(2, 3).text() == "100.00"


def test_tbp_plot_widget_renders_a_plot(app: QApplication) -> None:
    widget = ResultsPlotWidget()
    if not getattr(widget, "_matplotlib_available", False):
        pytest.skip("matplotlib Qt backend unavailable")

    widget.display_result(_build_tbp_run_result())

    assert len(widget.figure.axes) >= 1
    assert "TBP" in widget.figure.axes[0].get_title()
    assert len(widget.figure.axes) >= 2


def test_tbp_text_output_reports_cumulative_curves(app: QApplication) -> None:
    widget = TextOutputWidget()
    widget.display_result(_build_tbp_run_result())

    text = widget.text.toPlainText()
    assert "TBP assay" in text
    assert "Runtime bridge" in text
    assert "Characterized SCN" in text
    assert "Label  = C7+" in text
    assert "Method = pedersen_fit_to_tbp" in text
    assert "Derived SCN characterization" in text
    assert "Range" in text
    assert "385.00" in text
    assert "Cum Mole %" in text
    assert "Cum Mass %" in text
