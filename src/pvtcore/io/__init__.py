"""Input/Output module for PVT simulations.

This module provides data import/export and report generation:
- Import compositions from CSV/JSON
- Export results to various formats
- Generate formatted reports (text, markdown, HTML)
- Handle unit conversions at I/O boundaries

Units Convention:
- Internal: SI (Pa, K, kg/m³, m³/mol)
- Import/Export: User-specified units with automatic conversion

References
----------
Standard file formats for petroleum engineering data exchange.
"""

# Data import/export
from .data_io import (
    # Data classes
    CompositionData,
    ExperimentalDataFile,
    # Unit conversions
    convert_pressure,
    convert_temperature,
    # Import functions
    import_composition_csv,
    import_composition_json,
    import_experimental_csv,
    # Export functions
    export_composition_csv,
    export_composition_json,
    export_results_json,
    load_results_json,
    # Utilities
    match_components,
)

# Report generation
from .reports import (
    ReportSection,
    PVTReport,
    generate_flash_report,
    generate_cce_report,
    generate_separator_report,
)

# Schema-driven fluid definition parsing (optional)
from .fluid_definition import (
    load_fluid_definition,
    characterize_from_schema,
)

__all__ = [
    # Data classes
    "CompositionData",
    "ExperimentalDataFile",
    # Unit conversions
    "convert_pressure",
    "convert_temperature",
    # Import functions
    "import_composition_csv",
    "import_composition_json",
    "import_experimental_csv",
    # Export functions
    "export_composition_csv",
    "export_composition_json",
    "export_results_json",
    "load_results_json",
    # Utilities
    "match_components",
    # Report classes
    "ReportSection",
    "PVTReport",
    # Report generators
    "generate_flash_report",
    "generate_cce_report",
    "generate_separator_report",

    # Schema parsing
    "load_fluid_definition",
    "characterize_from_schema",
]
