"""Unit tests for the I/O module (data import/export and reports)."""

import numpy as np
import pytest
import tempfile
import json
from pathlib import Path

from pvtcore.io import (
    # Data classes
    CompositionData,
    ExperimentalDataFile,
    # Unit conversions
    convert_pressure,
    convert_temperature,
    # Import/export functions
    import_composition_csv,
    import_composition_json,
    import_experimental_csv,
    export_composition_csv,
    export_composition_json,
    export_results_json,
    load_results_json,
    # Utilities
    match_components,
    # Report classes
    ReportSection,
    PVTReport,
)
from pvtcore.models.component import load_components
from pvtcore.core.errors import ValidationError


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def components():
    """Load component database."""
    return load_components()


# =============================================================================
# Unit Conversion Tests
# =============================================================================

class TestPressureConversion:
    """Tests for pressure unit conversion."""

    def test_pa_identity(self):
        """Test Pa to Pa (identity)."""
        assert convert_pressure(1e6, 'Pa') == 1e6

    def test_mpa_to_pa(self):
        """Test MPa to Pa."""
        assert convert_pressure(1.0, 'MPa') == 1e6

    def test_bar_to_pa(self):
        """Test bar to Pa."""
        assert convert_pressure(1.0, 'bar') == 1e5

    def test_psi_to_pa(self):
        """Test psi to Pa."""
        result = convert_pressure(14.696, 'psi')
        # 14.696 psi ≈ 1 atm ≈ 101325 Pa
        assert abs(result - 101325) < 100

    def test_atm_to_pa(self):
        """Test atm to Pa."""
        assert convert_pressure(1.0, 'atm') == 101325.0

    def test_invalid_unit(self):
        """Test invalid pressure unit raises error."""
        with pytest.raises(ValidationError):
            convert_pressure(1.0, 'invalid_unit')


class TestTemperatureConversion:
    """Tests for temperature unit conversion."""

    def test_kelvin_identity(self):
        """Test K to K (identity)."""
        assert convert_temperature(300.0, 'K') == 300.0

    def test_celsius_to_kelvin(self):
        """Test Celsius to Kelvin."""
        assert convert_temperature(0.0, 'C') == 273.15
        assert convert_temperature(100.0, 'C') == 373.15

    def test_fahrenheit_to_kelvin(self):
        """Test Fahrenheit to Kelvin."""
        result = convert_temperature(32.0, 'F')
        # 32 F = 0 C = 273.15 K
        assert abs(result - 273.15) < 0.1

    def test_rankine_to_kelvin(self):
        """Test Rankine to Kelvin."""
        result = convert_temperature(491.67, 'R')
        # 491.67 R = 273.15 K
        assert abs(result - 273.15) < 0.1

    def test_invalid_unit(self):
        """Test invalid temperature unit raises error."""
        with pytest.raises(ValidationError):
            convert_temperature(300.0, 'invalid')


# =============================================================================
# CompositionData Tests
# =============================================================================

class TestCompositionData:
    """Tests for CompositionData class."""

    def test_create_composition_data(self):
        """Test creating composition data."""
        data = CompositionData(
            component_names=['C1', 'C3', 'C7'],
            mole_fractions=np.array([0.5, 0.3, 0.2]),
        )
        assert len(data.component_names) == 3
        assert abs(data.mole_fractions.sum() - 1.0) < 1e-10

    def test_to_dict(self):
        """Test converting to dictionary."""
        data = CompositionData(
            component_names=['C1', 'C3'],
            mole_fractions=np.array([0.6, 0.4]),
            description="Test mixture",
        )
        d = data.to_dict()

        assert d['component_names'] == ['C1', 'C3']
        assert d['description'] == "Test mixture"


# =============================================================================
# Import/Export Tests
# =============================================================================

class TestCompositionCSV:
    """Tests for CSV composition import/export."""

    def test_import_export_roundtrip(self, temp_dir):
        """Test that import/export preserves data."""
        # Create test CSV
        csv_path = temp_dir / "test_comp.csv"
        with open(csv_path, 'w') as f:
            f.write("component,mole_fraction,MW\n")
            f.write("C1,0.50,16.04\n")
            f.write("C3,0.30,44.10\n")
            f.write("C7,0.20,100.0\n")

        # Import
        data = import_composition_csv(csv_path)

        assert data.component_names == ['C1', 'C3', 'C7']
        assert abs(data.mole_fractions[0] - 0.50) < 1e-10
        assert data.molecular_weights is not None
        assert abs(data.molecular_weights[0] - 16.04) < 0.01

        # Export
        export_path = temp_dir / "exported.csv"
        export_composition_csv(data, export_path)

        # Re-import
        data2 = import_composition_csv(export_path)
        assert data2.component_names == data.component_names
        np.testing.assert_array_almost_equal(data2.mole_fractions, data.mole_fractions)

    def test_import_normalizes_fractions(self, temp_dir):
        """Test that imported fractions are normalized."""
        csv_path = temp_dir / "unnormalized.csv"
        with open(csv_path, 'w') as f:
            f.write("component,mole_fraction\n")
            f.write("C1,1.0\n")
            f.write("C3,1.0\n")

        data = import_composition_csv(csv_path)
        assert abs(data.mole_fractions.sum() - 1.0) < 1e-10

    def test_import_file_not_found(self):
        """Test error on missing file."""
        with pytest.raises(ValidationError):
            import_composition_csv("nonexistent.csv")


class TestCompositionJSON:
    """Tests for JSON composition import/export."""

    def test_import_export_roundtrip(self, temp_dir):
        """Test JSON roundtrip."""
        json_path = temp_dir / "test_comp.json"
        with open(json_path, 'w') as f:
            json.dump({
                'components': ['C1', 'C3', 'C7'],
                'mole_fractions': [0.5, 0.3, 0.2],
                'description': 'Test mixture',
            }, f)

        # Import
        data = import_composition_json(json_path)
        assert data.description == 'Test mixture'

        # Export
        export_path = temp_dir / "exported.json"
        export_composition_json(data, export_path)

        # Verify export
        with open(export_path, 'r') as f:
            exported = json.load(f)
        assert exported['components'] == ['C1', 'C3', 'C7']


class TestExperimentalDataImport:
    """Tests for experimental data import."""

    def test_import_with_unit_conversion(self, temp_dir):
        """Test importing data with unit conversion."""
        csv_path = temp_dir / "exp_data.csv"
        with open(csv_path, 'w') as f:
            f.write("temperature,pressure,value\n")
            f.write("300,5,100.0\n")
            f.write("320,10,150.0\n")

        data = import_experimental_csv(
            csv_path,
            data_type='bubble_point',
            temperature_unit='K',
            pressure_unit='MPa',
        )

        assert data.data_type == 'bubble_point'
        assert data.temperatures[0] == 300.0
        assert data.pressures[0] == 5e6  # Converted to Pa


class TestResultsJSON:
    """Tests for results JSON import/export."""

    def test_export_and_load(self, temp_dir):
        """Test exporting and loading results."""
        results = {
            'pressure': 5e6,
            'temperature': 300.0,
            'vapor_fraction': 0.45,
            'array_data': np.array([1.0, 2.0, 3.0]),
        }

        json_path = temp_dir / "results.json"
        export_results_json(results, json_path)

        loaded = load_results_json(json_path)

        assert loaded['pressure'] == 5e6
        assert loaded['vapor_fraction'] == 0.45
        assert loaded['array_data'] == [1.0, 2.0, 3.0]


# =============================================================================
# Component Matching Tests
# =============================================================================

class TestMatchComponents:
    """Tests for component name matching."""

    def test_exact_match(self, components):
        """Test exact name matching."""
        matched = match_components(['C1', 'C3'], components)
        assert len(matched) == 2
        assert matched[0].name == 'Methane'  # C1 maps to Methane

    def test_common_names(self, components):
        """Test common name mapping."""
        matched = match_components(['methane', 'propane'], components)
        assert len(matched) == 2
        assert matched[0].name == 'Methane'
        assert matched[1].name == 'Propane'

    def test_case_insensitive(self, components):
        """Test case insensitive matching."""
        matched = match_components(['METHANE', 'PROPANE'], components)
        assert len(matched) == 2

    def test_alias_ids_and_common_aliases(self, components):
        """Test alias-aware matching from the component database."""
        matched = match_components(['nC4', 'n-pentane'], components)
        assert len(matched) == 2
        assert matched[0].id == 'C4'
        assert matched[1].id == 'C5'

    def test_unknown_component(self, components):
        """Test error on unknown component."""
        with pytest.raises(ValidationError):
            match_components(['C1', 'UnknownComponent'], components)


# =============================================================================
# Report Tests
# =============================================================================

class TestPVTReport:
    """Tests for PVT report generation."""

    def test_create_report(self):
        """Test creating a basic report."""
        report = PVTReport("Test Report", "A test description")
        assert report.title == "Test Report"
        assert report.description == "A test description"

    def test_add_section(self):
        """Test adding sections."""
        report = PVTReport("Test")
        report.add_section("Section 1", "Content 1")
        report.add_section("Section 2", "Content 2", level=3)

        assert len(report.sections) == 2
        assert report.sections[0].title == "Section 1"
        assert report.sections[1].level == 3

    def test_add_table(self):
        """Test adding tables."""
        report = PVTReport("Test")
        report.add_table(
            "Data Table",
            ['Col1', 'Col2'],
            [[1, 2], [3, 4]],
        )

        assert len(report.tables) == 1
        assert report.tables[0]['title'] == "Data Table"

    def test_to_text(self):
        """Test text output."""
        report = PVTReport("Test Report")
        report.add_section("Section", "Some content")
        report.add_table("Table", ['A', 'B'], [[1, 2]])

        text = report.to_text()

        assert "Test Report" in text
        assert "Section" in text
        assert "Some content" in text

    def test_to_markdown(self):
        """Test markdown output."""
        report = PVTReport("Test Report")
        report.add_section("Section", "Content")
        report.add_table("Table", ['A', 'B'], [[1, 2]])

        md = report.to_markdown()

        assert "# Test Report" in md
        assert "## Section" in md
        assert "| A | B |" in md

    def test_to_html(self):
        """Test HTML output."""
        report = PVTReport("Test Report")
        report.add_section("Section", "Content")

        html = report.to_html()

        assert "<h1>Test Report</h1>" in html
        assert "<h3>Section</h3>" in html

    def test_save_auto_format(self, temp_dir):
        """Test saving with automatic format detection."""
        report = PVTReport("Test")
        report.add_section("Test", "Content")

        # Save as markdown
        md_path = temp_dir / "report.md"
        report.save(md_path)
        with open(md_path, 'r') as f:
            content = f.read()
        assert "# Test" in content

        # Save as HTML
        html_path = temp_dir / "report.html"
        report.save(html_path)
        with open(html_path, 'r') as f:
            content = f.read()
        assert "<h1>Test</h1>" in content


class TestReportFormatting:
    """Tests for table formatting."""

    def test_table_with_formats(self):
        """Test table with format strings."""
        report = PVTReport("Test")
        report.add_table(
            "Formatted Data",
            ['Value', 'Scientific'],
            [[1234.5678, 0.000123]],
            formats=['.2f', '.2e'],
        )

        text = report.to_text()
        assert '1234.57' in text
        assert '1.23e-04' in text

    def test_empty_table(self):
        """Test empty table handling."""
        report = PVTReport("Test")
        report.add_table("Empty", ['A'], [])

        text = report.to_text()
        assert "no data" in text.lower()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIOIntegration:
    """Integration tests for the I/O module."""

    def test_full_workflow(self, temp_dir, components):
        """Test complete import-process-export-report workflow."""
        # Create input file
        csv_path = temp_dir / "input.csv"
        with open(csv_path, 'w') as f:
            f.write("component,mole_fraction\n")
            f.write("C1,0.5\n")
            f.write("C3,0.3\n")
            f.write("C7,0.2\n")

        # Import
        comp_data = import_composition_csv(csv_path)

        # Match components
        matched = match_components(comp_data.component_names, components)
        assert len(matched) == 3

        # Create results
        results = {
            'composition': comp_data.mole_fractions.tolist(),
            'components': comp_data.component_names,
            'calculated_value': 42.0,
        }

        # Export results
        results_path = temp_dir / "results.json"
        export_results_json(results, results_path)

        # Create report
        report = PVTReport("Analysis Results")
        report.add_section("Input", f"Components: {comp_data.component_names}")
        report.add_table(
            "Composition",
            ['Component', 'Mole Fraction'],
            [[n, z] for n, z in zip(comp_data.component_names, comp_data.mole_fractions)],
        )

        # Save report
        report_path = temp_dir / "report.md"
        report.save(report_path)

        # Verify all files exist
        assert results_path.exists()
        assert report_path.exists()
