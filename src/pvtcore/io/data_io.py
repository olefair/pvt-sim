"""Data import/export utilities for PVT simulations.

This module provides functions to:
- Import fluid compositions from CSV/JSON
- Export results to various formats
- Save/load calculation states
- Handle unit conversions at I/O boundaries

Supported formats:
- CSV: Comma-separated values (compositions, experimental data)
- JSON: Structured data (full state, results)
- Excel: Spreadsheet format (via pandas if available)

Units Convention:
- Internal: SI (Pa, K, kg/m³, m³/mol)
- Import/Export: User-specified units with automatic conversion

References
----------
Standard file formats for petroleum engineering data exchange.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional, Dict, Any, Union
from pathlib import Path
import json
import csv
from datetime import datetime

import numpy as np
from numpy.typing import NDArray

from ..core.errors import ValidationError
from ..models.component import Component, get_component, load_components


# Unit conversion factors (multiply to convert TO SI)
PRESSURE_CONVERSIONS = {
    'Pa': 1.0,
    'kPa': 1e3,
    'MPa': 1e6,
    'bar': 1e5,
    'psi': 6894.76,
    'psia': 6894.76,
    'atm': 101325.0,
}

TEMPERATURE_CONVERSIONS = {
    'K': ('K', 0.0),  # (unit, offset)
    'C': ('K', 273.15),
    'F': ('R', 459.67),  # Convert to Rankine, then to K
    'R': ('K', 0.0),  # 1 R = 5/9 K
}

DENSITY_CONVERSIONS = {
    'kg/m3': 1.0,
    'g/cm3': 1000.0,
    'lb/ft3': 16.0185,
}


@dataclass
class CompositionData:
    """Imported composition data.

    Attributes:
        component_names: List of component names/identifiers
        mole_fractions: Mole fractions (normalized)
        molecular_weights: MW for each component (if provided)
        description: Optional description
        source_file: Original file path
        metadata: Additional metadata
    """
    component_names: List[str]
    mole_fractions: NDArray[np.float64]
    molecular_weights: Optional[NDArray[np.float64]] = None
    description: str = ""
    source_file: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'component_names': self.component_names,
            'mole_fractions': self.mole_fractions.tolist(),
            'molecular_weights': self.molecular_weights.tolist() if self.molecular_weights is not None else None,
            'description': self.description,
            'source_file': self.source_file,
            'metadata': self.metadata,
        }


@dataclass
class ExperimentalDataFile:
    """Imported experimental data.

    Attributes:
        data_type: Type of data (e.g., 'bubble_point', 'density')
        temperatures: Temperature values
        pressures: Pressure values (if applicable)
        values: Measured values
        temperature_unit: Original temperature unit
        pressure_unit: Original pressure unit
        value_unit: Original value unit
        composition: Associated composition (if provided)
        source_file: Original file path
    """
    data_type: str
    temperatures: NDArray[np.float64]
    pressures: Optional[NDArray[np.float64]]
    values: NDArray[np.float64]
    temperature_unit: str = 'K'
    pressure_unit: str = 'Pa'
    value_unit: str = ''
    composition: Optional[NDArray[np.float64]] = None
    source_file: str = ""


def convert_pressure(value: float, from_unit: str) -> float:
    """Convert pressure to SI (Pa).

    Parameters
    ----------
    value : float
        Pressure value in original units.
    from_unit : str
        Original unit.

    Returns
    -------
    float
        Pressure in Pa.
    """
    from_unit = from_unit.lower().replace(' ', '')
    if from_unit == 'pa':
        return value
    if from_unit == 'kpa':
        return value * 1e3
    if from_unit == 'mpa':
        return value * 1e6
    if from_unit == 'bar':
        return value * 1e5
    if from_unit in ('psi', 'psia'):
        return value * 6894.76
    if from_unit == 'atm':
        return value * 101325.0

    raise ValidationError(f"Unknown pressure unit: {from_unit}", parameter="from_unit")


def convert_temperature(value: float, from_unit: str) -> float:
    """Convert temperature to SI (K).

    Parameters
    ----------
    value : float
        Temperature value in original units.
    from_unit : str
        Original unit.

    Returns
    -------
    float
        Temperature in K.
    """
    from_unit = from_unit.upper()
    if from_unit == 'K':
        return value
    if from_unit in ('C', 'CELSIUS'):
        return value + 273.15
    if from_unit in ('F', 'FAHRENHEIT'):
        return (value + 459.67) * 5 / 9
    if from_unit in ('R', 'RANKINE'):
        return value * 5 / 9

    raise ValidationError(f"Unknown temperature unit: {from_unit}", parameter="from_unit")


def import_composition_csv(
    filepath: Union[str, Path],
    component_col: str = 'component',
    fraction_col: str = 'mole_fraction',
    mw_col: Optional[str] = 'MW',
    delimiter: str = ',',
) -> CompositionData:
    """Import fluid composition from CSV file.

    Expected CSV format:
    component,mole_fraction,MW
    C1,0.50,16.04
    C3,0.30,44.10
    C7,0.20,100.0

    Parameters
    ----------
    filepath : str or Path
        Path to CSV file.
    component_col : str
        Column name for component identifiers.
    fraction_col : str
        Column name for mole fractions.
    mw_col : str, optional
        Column name for molecular weights.
    delimiter : str
        CSV delimiter.

    Returns
    -------
    CompositionData
        Imported composition data.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise ValidationError(f"File not found: {filepath}", parameter="filepath")

    components = []
    fractions = []
    mws = []

    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            if component_col not in row:
                raise ValidationError(
                    f"Column '{component_col}' not found in CSV",
                    parameter="component_col"
                )
            if fraction_col not in row:
                raise ValidationError(
                    f"Column '{fraction_col}' not found in CSV",
                    parameter="fraction_col"
                )

            components.append(row[component_col].strip())
            fractions.append(float(row[fraction_col]))

            if mw_col and mw_col in row and row[mw_col]:
                mws.append(float(row[mw_col]))

    fractions_arr = np.array(fractions, dtype=np.float64)
    fractions_arr = fractions_arr / fractions_arr.sum()  # Normalize

    mws_arr = np.array(mws, dtype=np.float64) if len(mws) == len(components) else None

    return CompositionData(
        component_names=components,
        mole_fractions=fractions_arr,
        molecular_weights=mws_arr,
        source_file=str(filepath),
    )


def import_composition_json(filepath: Union[str, Path]) -> CompositionData:
    """Import fluid composition from JSON file.

    Expected JSON format:
    {
        "components": ["C1", "C3", "C7"],
        "mole_fractions": [0.5, 0.3, 0.2],
        "molecular_weights": [16.04, 44.1, 100.0],
        "description": "Sample gas condensate"
    }

    Parameters
    ----------
    filepath : str or Path
        Path to JSON file.

    Returns
    -------
    CompositionData
        Imported composition data.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise ValidationError(f"File not found: {filepath}", parameter="filepath")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    components = data.get('components', data.get('component_names', []))
    fractions = data.get('mole_fractions', [])
    mws = data.get('molecular_weights')

    if not components or not fractions:
        raise ValidationError("JSON must contain 'components' and 'mole_fractions'", parameter="filepath")

    fractions_arr = np.array(fractions, dtype=np.float64)
    fractions_arr = fractions_arr / fractions_arr.sum()

    mws_arr = np.array(mws, dtype=np.float64) if mws else None

    return CompositionData(
        component_names=components,
        mole_fractions=fractions_arr,
        molecular_weights=mws_arr,
        description=data.get('description', ''),
        source_file=str(filepath),
        metadata=data.get('metadata', {}),
    )


def export_composition_csv(
    composition: CompositionData,
    filepath: Union[str, Path],
    include_mw: bool = True,
) -> None:
    """Export composition to CSV file.

    Parameters
    ----------
    composition : CompositionData
        Composition data to export.
    filepath : str or Path
        Output file path.
    include_mw : bool
        Include molecular weights if available.
    """
    filepath = Path(filepath)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['component', 'mole_fraction']
        if include_mw and composition.molecular_weights is not None:
            fieldnames.append('MW')

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for i, name in enumerate(composition.component_names):
            row = {
                'component': name,
                'mole_fraction': composition.mole_fractions[i],
            }
            if include_mw and composition.molecular_weights is not None:
                row['MW'] = composition.molecular_weights[i]
            writer.writerow(row)


def export_composition_json(
    composition: CompositionData,
    filepath: Union[str, Path],
    indent: int = 2,
) -> None:
    """Export composition to JSON file.

    Parameters
    ----------
    composition : CompositionData
        Composition data to export.
    filepath : str or Path
        Output file path.
    indent : int
        JSON indentation.
    """
    filepath = Path(filepath)

    data = {
        'components': composition.component_names,
        'mole_fractions': composition.mole_fractions.tolist(),
        'description': composition.description,
        'exported_at': datetime.now().isoformat(),
    }

    if composition.molecular_weights is not None:
        data['molecular_weights'] = composition.molecular_weights.tolist()

    if composition.metadata:
        data['metadata'] = composition.metadata

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent)


def import_experimental_csv(
    filepath: Union[str, Path],
    data_type: str,
    temperature_col: str = 'temperature',
    pressure_col: Optional[str] = 'pressure',
    value_col: str = 'value',
    temperature_unit: str = 'K',
    pressure_unit: str = 'Pa',
    delimiter: str = ',',
) -> ExperimentalDataFile:
    """Import experimental data from CSV.

    Parameters
    ----------
    filepath : str or Path
        Path to CSV file.
    data_type : str
        Type of data (e.g., 'bubble_point', 'liquid_density').
    temperature_col : str
        Column name for temperature.
    pressure_col : str, optional
        Column name for pressure.
    value_col : str
        Column name for measured values.
    temperature_unit : str
        Temperature unit in file.
    pressure_unit : str
        Pressure unit in file.
    delimiter : str
        CSV delimiter.

    Returns
    -------
    ExperimentalDataFile
        Imported data.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise ValidationError(f"File not found: {filepath}", parameter="filepath")

    temperatures = []
    pressures = []
    values = []

    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)

        for row in reader:
            T = convert_temperature(float(row[temperature_col]), temperature_unit)
            temperatures.append(T)

            if pressure_col and pressure_col in row and row[pressure_col]:
                P = convert_pressure(float(row[pressure_col]), pressure_unit)
                pressures.append(P)

            values.append(float(row[value_col]))

    return ExperimentalDataFile(
        data_type=data_type,
        temperatures=np.array(temperatures),
        pressures=np.array(pressures) if pressures else None,
        values=np.array(values),
        temperature_unit=temperature_unit,
        pressure_unit=pressure_unit,
        source_file=str(filepath),
    )


def export_results_json(
    results: Dict[str, Any],
    filepath: Union[str, Path],
    indent: int = 2,
) -> None:
    """Export calculation results to JSON.

    Parameters
    ----------
    results : dict
        Results dictionary (will be serialized).
    filepath : str or Path
        Output file path.
    indent : int
        JSON indentation.
    """
    filepath = Path(filepath)

    def serialize(obj):
        """Custom serializer for numpy arrays and dataclasses."""
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, '__dataclass_fields__'):
            return asdict(obj)
        if isinstance(obj, (np.float64, np.float32)):
            return float(obj)
        if isinstance(obj, (np.int64, np.int32)):
            return int(obj)
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    output = {
        'results': results,
        'exported_at': datetime.now().isoformat(),
        'version': '1.0',
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=indent, default=serialize)


def load_results_json(filepath: Union[str, Path]) -> Dict[str, Any]:
    """Load calculation results from JSON.

    Parameters
    ----------
    filepath : str or Path
        Path to JSON file.

    Returns
    -------
    dict
        Loaded results.
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise ValidationError(f"File not found: {filepath}", parameter="filepath")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get('results', data)


def match_components(
    names: List[str],
    database: Optional[Dict[str, Component]] = None,
) -> List[Component]:
    """Match component names to database entries.

    Parameters
    ----------
    names : list of str
        Component names from import.
    database : dict, optional
        Component database. If None, loads default.

    Returns
    -------
    list of Component
        Matched components.

    Raises
    ------
    ValidationError
        If a component cannot be matched.
    """
    if database is None:
        database = load_components()

    matched = []
    for name in names:
        try:
            matched.append(get_component(name, database))
        except KeyError as exc:
            raise ValidationError(str(exc), parameter="names") from exc

    return matched
