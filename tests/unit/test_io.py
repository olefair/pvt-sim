"""Consolidated unit tests for the I/O module.

Covers:
- Import/export round-trips (CSV, JSON) — parametrized by format
- Unit conversions (pressure, temperature) — parametrized
- Fluid-definition parser (valid/invalid JSON, schema variants)
- Report generation (text, markdown, HTML)
- Edge-case / invalid-input validation
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from pvtcore.characterization import KatzSplitResult, LohrenzSplitResult
from pvtcore.core.errors import ConfigurationError, ValidationError
from pvtcore.io import (
    CompositionData,
    ExperimentalDataFile,
    characterize_from_schema,
    convert_pressure,
    convert_temperature,
    export_composition_csv,
    export_composition_json,
    export_results_json,
    import_composition_csv,
    import_composition_json,
    import_experimental_csv,
    load_fluid_definition,
    load_results_json,
    match_components,
    PVTReport,
    ReportSection,
)


# ---------------------------------------------------------------------------
# Helpers — reusable schema docs
# ---------------------------------------------------------------------------

def _example_doc() -> dict:
    return {
        "fluid": {
            "name": "Example Fluid",
            "basis": "mole",
            "components": [
                {"id": "CO2", "z": 0.02},
                {"id": "C1", "z": 0.70},
                {"id": "C2", "z": 0.08},
                {"id": "C3", "z": 0.05},
                {"id": "C4", "z": 0.05},
                {"id": "C5", "z": 0.03},
                {"id": "C6", "z": 0.02},
            ],
            "plus_fraction": {
                "label": "C7+",
                "z_plus": 0.05,
                "cut_start": 7,
                "mw_plus_g_per_mol": 215.0,
                "sg_plus_60F": 0.85,
                "splitting": {
                    "method": "pedersen",
                    "max_carbon_number": 45,
                    "pedersen": {"mw_model": "MWn = 14n - 4"},
                },
                "lumping": {"enabled": True, "n_groups": 4},
            },
            "correlations": {"critical_props": "riazi_daubert_1987"},
            "eos": {
                "model": "PR",
                "mixing_rule": "vdW1",
                "kij": {"overrides": [{"pair": ["CO2", "C7+"], "kij": 0.12}]},
            },
        }
    }


def _tbp_example_doc() -> dict:
    return {
        "fluid": {
            "name": "TBP-backed Example Fluid",
            "basis": "mole",
            "components": [
                {"id": "CO2", "z": 0.02},
                {"id": "C1", "z": 0.70},
                {"id": "C2", "z": 0.08},
                {"id": "C3", "z": 0.05},
                {"id": "C4", "z": 0.05},
                {"id": "C5", "z": 0.03},
                {"id": "C6", "z": 0.02},
            ],
            "plus_fraction": {
                "label": "C7+",
                "cut_start": 7,
                "sg_plus_60F": 0.85,
                "tbp_data": {
                    "cuts": [
                        {"name": "C7", "z": 0.020, "mw": 96.0},
                        {"name": "C8", "z": 0.015, "mw": 110.0},
                        {"name": "C9", "z": 0.015, "mw": 124.0},
                    ]
                },
                "splitting": {
                    "method": "pedersen",
                    "max_carbon_number": 12,
                    "pedersen": {
                        "mw_model": "MWn = 14n - 4",
                        "solve_AB_from": "balances",
                    },
                },
                "lumping": {"enabled": False},
            },
            "correlations": {"critical_props": "riazi_daubert_1987"},
        }
    }


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# ---------------------------------------------------------------------------
# Import / export round-trips (parametrized by format)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", ["csv", "json"], ids=["CSV", "JSON"])
def test_import_export_roundtrip(temp_dir, fmt):
    """Import → export → re-import preserves data for both CSV and JSON."""
    if fmt == "csv":
        path = temp_dir / "comp.csv"
        with open(path, "w") as f:
            f.write("component,mole_fraction,MW\n")
            f.write("C1,0.50,16.04\nC3,0.30,44.10\nC7,0.20,100.0\n")

        data = import_composition_csv(path)
        assert data.component_names == ["C1", "C3", "C7"]
        assert abs(data.mole_fractions[0] - 0.50) < 1e-10
        assert data.molecular_weights is not None
        assert abs(data.molecular_weights[0] - 16.04) < 0.01

        out_path = temp_dir / "exported.csv"
        export_composition_csv(data, out_path)
        data2 = import_composition_csv(out_path)
        assert data2.component_names == data.component_names
        np.testing.assert_array_almost_equal(data2.mole_fractions, data.mole_fractions)

        # normalization
        un_path = temp_dir / "unnorm.csv"
        with open(un_path, "w") as f:
            f.write("component,mole_fraction\nC1,1.0\nC3,1.0\n")
        un_data = import_composition_csv(un_path)
        assert abs(un_data.mole_fractions.sum() - 1.0) < 1e-10

    else:
        path = temp_dir / "comp.json"
        with open(path, "w") as f:
            json.dump(
                {"components": ["C1", "C3", "C7"], "mole_fractions": [0.5, 0.3, 0.2], "description": "Test"},
                f,
            )

        data = import_composition_json(path)
        assert data.description == "Test"

        out_path = temp_dir / "exported.json"
        export_composition_json(data, out_path)
        with open(out_path) as f:
            exported = json.load(f)
        assert exported["components"] == ["C1", "C3", "C7"]

    # --- CompositionData helpers ---
    cd = CompositionData(component_names=["C1", "C3"], mole_fractions=np.array([0.6, 0.4]), description="mix")
    d = cd.to_dict()
    assert d["component_names"] == ["C1", "C3"]
    assert d["description"] == "mix"

    # --- experimental data import ---
    exp_path = temp_dir / "exp.csv"
    with open(exp_path, "w") as f:
        f.write("temperature,pressure,value\n300,5,100.0\n320,10,150.0\n")
    exp_data = import_experimental_csv(exp_path, data_type="bubble_point", temperature_unit="K", pressure_unit="MPa")
    assert exp_data.data_type == "bubble_point"
    assert exp_data.temperatures[0] == 300.0
    assert exp_data.pressures[0] == 5e6

    # --- results JSON ---
    res = {"pressure": 5e6, "temperature": 300.0, "vapor_fraction": 0.45, "array_data": np.array([1.0, 2.0, 3.0])}
    rpath = temp_dir / "results.json"
    export_results_json(res, rpath)
    loaded = load_results_json(rpath)
    assert loaded["pressure"] == 5e6
    assert loaded["array_data"] == [1.0, 2.0, 3.0]


# ---------------------------------------------------------------------------
# Unit conversions (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "quantity, value, unit, expected",
    [
        pytest.param("pressure", 1e6, "Pa", 1e6, id="Pa-identity"),
        pytest.param("pressure", 1.0, "MPa", 1e6, id="MPa"),
        pytest.param("pressure", 1.0, "bar", 1e5, id="bar"),
        pytest.param("pressure", 14.696, "psi", 101325.0, id="psi"),
        pytest.param("pressure", 1.0, "atm", 101325.0, id="atm"),
        pytest.param("temperature", 300.0, "K", 300.0, id="K-identity"),
        pytest.param("temperature", 0.0, "C", 273.15, id="C-to-K"),
        pytest.param("temperature", 100.0, "C", 373.15, id="C100-to-K"),
        pytest.param("temperature", 32.0, "F", 273.15, id="F-to-K"),
        pytest.param("temperature", 491.67, "R", 273.15, id="R-to-K"),
    ],
)
def test_unit_conversions(quantity, value, unit, expected):
    """Pressure and temperature conversions to SI base units."""
    if quantity == "pressure":
        result = convert_pressure(value, unit)
    else:
        result = convert_temperature(value, unit)
    assert abs(result - expected) < 100  # psi tolerance


# ---------------------------------------------------------------------------
# Fluid-definition parser (parametrized valid / invalid)
# ---------------------------------------------------------------------------

def test_fluid_definition_parser(tmp_path):
    """Schema-driven characterization: valid configs, split methods, TBP, kij overrides."""
    # --- basic + kij override ---
    doc = _example_doc()
    res = characterize_from_schema(doc)
    assert np.isclose(float(res.composition.sum()), 1.0)
    assert res.lumping is not None
    assert len(res.component_ids) == 7 + 4

    idx_co2 = res.component_ids.index("CO2")
    for j in range(7, len(res.component_ids)):
        assert res.binary_interaction[idx_co2, j] == pytest.approx(0.12, abs=0.0)
        assert res.binary_interaction[j, idx_co2] == pytest.approx(0.12, abs=0.0)

    # --- load from file ---
    path = tmp_path / "fluid.json"
    path.write_text(json.dumps(_example_doc()), encoding="utf-8")
    loaded = load_fluid_definition(path)
    assert np.isclose(float(characterize_from_schema(loaded).composition.sum()), 1.0)

    # --- split methods ---
    for method, expected_type in [("katz", KatzSplitResult), ("lohrenz", LohrenzSplitResult), ("lohrens", LohrenzSplitResult)]:
        d = _example_doc()
        d["fluid"]["plus_fraction"]["splitting"]["method"] = method
        r = characterize_from_schema(d)
        assert r.plus_fraction is not None
        assert np.isclose(float(r.composition.sum()), 1.0)
        assert isinstance(r.split_result, expected_type)

    # --- unsupported legacy contiguous lumping ---
    d = _example_doc()
    d["fluid"]["plus_fraction"]["lumping"]["method"] = "contiguous"
    with pytest.raises(ConfigurationError):
        characterize_from_schema(d)

    # --- TBP-derived inputs ---
    tbp_res = characterize_from_schema(_tbp_example_doc())
    assert tbp_res.plus_fraction is not None
    assert tbp_res.plus_fraction.z_plus == pytest.approx(0.05)
    assert tbp_res.plus_fraction.mw_plus == pytest.approx(108.6)

    # --- TBP with matching explicit aggregate values ---
    d = _tbp_example_doc()
    d["fluid"]["plus_fraction"]["z_plus"] = 0.05
    d["fluid"]["plus_fraction"]["mw_plus_g_per_mol"] = 108.6
    assert characterize_from_schema(d).plus_fraction is not None

    # --- TBP with gapped cuts ---
    d = _tbp_example_doc()
    d["fluid"]["plus_fraction"]["tbp_data"]["cuts"] = [
        {"name": "C7", "z": 0.02, "mw": 96.0},
        {"name": "C9-C10", "z": 0.03, "mw": 130.0, "tb_k": 430.0},
    ]
    r = characterize_from_schema(d)
    assert r.plus_fraction.z_plus == pytest.approx(0.05)
    assert r.plus_fraction.mw_plus == pytest.approx((0.02 * 96.0 + 0.03 * 130.0) / 0.05)

    # --- TBP fit-to-tbp mode ---
    d = _tbp_example_doc()
    d["fluid"]["plus_fraction"]["splitting"]["pedersen"]["solve_AB_from"] = "fit_to_tbp"
    r = characterize_from_schema(d)
    assert r.split_result.solve_ab_from == "fit_to_tbp"
    assert r.split_result.tbp_cut_rms_relative_error is not None
    assert np.isclose(float(r.composition.sum()), 1.0)

    # --- repo example file ---
    repo_root = Path(__file__).resolve().parents[2]
    example_path = repo_root / "examples" / "tbp_fluid_definition.json"
    loaded_ex = load_fluid_definition(example_path)
    ex_res = characterize_from_schema(loaded_ex)
    assert ex_res.plus_fraction is not None
    assert np.isclose(float(ex_res.composition.sum()), 1.0)

    # --- rejection cases ---
    for mutate, exc, match in [
        (lambda d: d["fluid"].__setitem__("basis", "mass"), ConfigurationError, None),
        (lambda d: d["fluid"]["plus_fraction"]["lumping"].__setitem__("method", "lee"), ConfigurationError, None),
        (lambda d: d["fluid"]["correlations"].__setitem__("critical_props", "kesler_lee_1976"), ConfigurationError, None),
    ]:
        d = _example_doc()
        mutate(d)
        with pytest.raises(exc):
            characterize_from_schema(d)

    # --- TBP mismatch rejections ---
    d = _tbp_example_doc()
    d["fluid"]["plus_fraction"]["z_plus"] = 0.051
    with pytest.raises(ValidationError, match="fluid.plus_fraction.z_plus"):
        characterize_from_schema(d)

    d = _tbp_example_doc()
    d["fluid"]["plus_fraction"]["mw_plus_g_per_mol"] = 120.0
    with pytest.raises(ValidationError, match="fluid.plus_fraction.mw_plus_g_per_mol"):
        characterize_from_schema(d)

    # --- invalid TBP cut names ---
    for cut_name, match_text in [("heavy", "must look like 'C7' or 'C7-C9'"), ("C6", "must not start below")]:
        d = _tbp_example_doc()
        d["fluid"]["plus_fraction"]["tbp_data"]["cuts"][0]["name"] = cut_name
        with pytest.raises(ValidationError, match=match_text):
            characterize_from_schema(d)


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def test_report_generation(temp_dir):
    """PVTReport: sections, tables, format outputs, auto-save."""
    report = PVTReport("Test Report", "A test description")
    assert report.title == "Test Report"

    report.add_section("Section 1", "Content 1")
    report.add_section("Section 2", "Content 2", level=3)
    assert len(report.sections) == 2

    report.add_table("Data Table", ["Col1", "Col2"], [[1, 2], [3, 4]])
    assert len(report.tables) == 1

    # text
    text = report.to_text()
    assert "Test Report" in text
    assert "Section 1" in text

    # markdown
    md = report.to_markdown()
    assert "# Test Report" in md
    assert "## Section 1" in md
    assert "| Col1 | Col2 |" in md

    # html
    html = report.to_html()
    assert "<h1>Test Report</h1>" in html

    # save auto-format
    md_path = temp_dir / "report.md"
    report.save(md_path)
    with open(md_path) as f:
        assert "# Test" in f.read()
    html_path = temp_dir / "report.html"
    report.save(html_path)
    with open(html_path) as f:
        assert "<h1>" in f.read()

    # formatted table
    r2 = PVTReport("T2")
    r2.add_table("Fmt", ["Value", "Sci"], [[1234.5678, 0.000123]], formats=[".2f", ".2e"])
    t2 = r2.to_text()
    assert "1234.57" in t2
    assert "1.23e-04" in t2

    # empty table
    r3 = PVTReport("T3")
    r3.add_table("Empty", ["A"], [])
    assert "no data" in r3.to_text().lower()


# ---------------------------------------------------------------------------
# IO edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "kind",
    [
        pytest.param("csv_not_found", id="csv-file-not-found"),
        pytest.param("pressure_invalid_unit", id="pressure-invalid-unit"),
        pytest.param("temperature_invalid_unit", id="temperature-invalid-unit"),
        pytest.param("unknown_component", id="unknown-component"),
    ],
)
def test_io_edge_cases(components, kind):
    """Invalid IO inputs must raise ValidationError."""
    if kind == "csv_not_found":
        with pytest.raises(ValidationError):
            import_composition_csv("nonexistent.csv")
    elif kind == "pressure_invalid_unit":
        with pytest.raises(ValidationError):
            convert_pressure(1.0, "invalid_unit")
    elif kind == "temperature_invalid_unit":
        with pytest.raises(ValidationError):
            convert_temperature(300.0, "invalid")
    elif kind == "unknown_component":
        with pytest.raises(ValidationError):
            match_components(["C1", "UnknownComponent"], components)


# ---------------------------------------------------------------------------
# Component matching (uses session components fixture)
# ---------------------------------------------------------------------------

def test_component_matching(components):
    """Component matching: exact, common names, case insensitive, aliases."""
    matched = match_components(["C1", "C3"], components)
    assert len(matched) == 2
    assert matched[0].name == "Methane"

    matched2 = match_components(["methane", "propane"], components)
    assert matched2[0].name == "Methane"
    assert matched2[1].name == "Propane"

    matched3 = match_components(["METHANE", "PROPANE"], components)
    assert len(matched3) == 2

    matched4 = match_components(["nC4", "n-pentane"], components)
    assert matched4[0].id == "C4"
    assert matched4[1].id == "C5"


# ---------------------------------------------------------------------------
# Full IO workflow
# ---------------------------------------------------------------------------

def test_io_full_workflow(temp_dir, components):
    """Import → match → export → report → verify files."""
    csv_path = temp_dir / "input.csv"
    with open(csv_path, "w") as f:
        f.write("component,mole_fraction\nC1,0.5\nC3,0.3\nC7,0.2\n")

    comp_data = import_composition_csv(csv_path)
    matched = match_components(comp_data.component_names, components)
    assert len(matched) == 3

    results = {"composition": comp_data.mole_fractions.tolist(), "components": comp_data.component_names, "calculated_value": 42.0}
    results_path = temp_dir / "results.json"
    export_results_json(results, results_path)

    report = PVTReport("Analysis Results")
    report.add_section("Input", f"Components: {comp_data.component_names}")
    report.add_table("Composition", ["Component", "Mole Fraction"], [[n, z] for n, z in zip(comp_data.component_names, comp_data.mole_fractions)])
    report_path = temp_dir / "report.md"
    report.save(report_path)

    assert results_path.exists()
    assert report_path.exists()
