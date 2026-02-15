"""Pure component thermodynamic properties.

This module defines the Component dataclass for storing pure component
thermodynamic properties, along with supporting types for component
classification and property provenance tracking.
"""

import json
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional


class ComponentFamily(Enum):
    """Chemical family classification for components.

    Used to categorize components for correlation selection and
    group contribution methods like PPR78.
    """

    ALKANE = auto()  # n-paraffins (C1, C2, C3, ...)
    ISOALKANE = auto()  # Branched paraffins (iC4, iC5, neoC5, ...)
    CYCLOALKANE = auto()  # Naphthenes (cyclohexane, methylcyclohexane, ...)
    AROMATIC = auto()  # Aromatics (benzene, toluene, xylenes, ...)
    DIATOMIC = auto()  # Diatomic gases (N2, O2, H2)
    INORGANIC = auto()  # Inorganic compounds (CO2, H2S, He, Ar, CO)
    SULFUR_ORGANIC = auto()  # Sulfur-containing organics (mercaptans, COS, CS2)
    UNDEFINED = auto()  # Pseudo-components or unknown family


class PseudoType(Enum):
    """Type classification for pseudo-components.

    Pseudo-components are not real molecules but represent petroleum
    fractions characterized by average properties.
    """

    SCN = auto()  # Single carbon number fraction (C7, C8, ...)
    LUMPED = auto()  # Lumped pseudo-component (C7-C12, C13-C19, ...)
    UNDEFINED_CUT = auto()  # Undefined petroleum cut


@dataclass(frozen=True)
class PropertyProvenance:
    """Provenance information for a property value.

    Tracks the source, method, and uncertainty of thermodynamic
    property values for data quality assessment.

    Attributes:
        source: Data source identifier (e.g., "NIST", "DIPPR", "correlation")
        reference: Citation or DOI for the data source
        method: How the value was obtained ("measured", "estimated", etc.)
        uncertainty: Relative uncertainty (e.g., 0.02 for 2%)
    """

    source: str
    reference: Optional[str] = None
    method: Optional[str] = None
    uncertainty: Optional[float] = None


@dataclass
class Component:
    """Pure component thermodynamic properties.

    This dataclass stores thermodynamic properties for pure components,
    with optional fields for structural information (SMILES), classification,
    PPR78 group decomposition, and property provenance tracking.

    Attributes:
        name: Component common name (e.g., "Methane")
        formula: Chemical formula (e.g., "CH4")
        Tc: Critical temperature (K)
        Pc: Critical pressure (Pa)
        Vc: Critical molar volume (m³/mol)
        omega: Acentric factor (dimensionless)
        MW: Molecular weight (g/mol)
        Tb: Normal boiling point temperature (K)
        note: Optional notes about the component

        id: Canonical component identifier (e.g., "C1", "BENZENE")
        aliases: Alternative names for the component
        cas: CAS registry number (e.g., "74-82-8" for methane)
        smiles: SMILES string for molecular structure
        family: Chemical family classification
        groups: PPR78 group decomposition (e.g., {"CH3": 2, "CH2": 4})
        provenance: Property data source and uncertainty information

        is_pseudo: True if this is a pseudo-component (not a real molecule)
        pseudo_type: Type of pseudo-component (SCN, LUMPED, etc.)
        parent_plus: Parent plus fraction ID (e.g., "C7+") if from splitting
        scn_index: Single carbon number index if SCN pseudo-component
    """

    # === Required thermodynamic properties ===
    name: str
    formula: str
    Tc: float  # Critical temperature (K)
    Pc: float  # Critical pressure (Pa)
    Vc: float  # Critical molar volume (m³/mol)
    omega: float  # Acentric factor
    MW: float  # Molecular weight (g/mol)
    Tb: float  # Normal boiling point (K)

    # === Optional basic fields ===
    note: Optional[str] = None

    # === Extended identification fields ===
    id: Optional[str] = None  # Canonical ID (e.g., "C1", "BENZENE")
    aliases: Optional[List[str]] = None  # Alternative names
    cas: Optional[str] = None  # CAS registry number
    smiles: Optional[str] = None  # SMILES string for structure
    inchi: Optional[str] = None  # InChI identifier for deterministic matching
    inchikey: Optional[str] = None  # InChIKey (hashed InChI for quick lookup)
    isomer_group: Optional[str] = None  # Isomer family (e.g., "xylene")

    # === Classification ===
    family: Optional[ComponentFamily] = None  # Chemical family

    # === PPR78 group contribution ===
    groups: Optional[Dict[str, int]] = None  # PPR78 groups {"CH3": 2, "CH2": 4}

    # === Provenance ===
    provenance: Optional[PropertyProvenance] = None

    # === Pseudo-component fields ===
    is_pseudo: bool = False
    pseudo_type: Optional[PseudoType] = None
    parent_plus: Optional[str] = None  # e.g., "C7+"
    scn_index: Optional[int] = None  # Carbon number for SCN

    @property
    def Pc_bar(self) -> float:
        """Critical pressure in bar."""
        return self.Pc / 1e5

    @property
    def Pc_MPa(self) -> float:
        """Critical pressure in MPa."""
        return self.Pc / 1e6

    @property
    def Vc_cm3_per_mol(self) -> float:
        """Critical volume in cm³/mol."""
        return self.Vc * 1e6

    @property
    def Vc_L_per_mol(self) -> float:
        """Critical volume in L/mol."""
        return self.Vc * 1e3

    def __repr__(self) -> str:
        """String representation of component."""
        return f"Component(name='{self.name}', formula='{self.formula}', MW={self.MW:.4f} g/mol)"

    def __str__(self) -> str:
        """Human-readable string representation."""
        return (
            f"{self.name} ({self.formula}):\n"
            f"  MW = {self.MW:.4f} g/mol\n"
            f"  Tc = {self.Tc:.2f} K, Pc = {self.Pc_MPa:.4f} MPa, Vc = {self.Vc_cm3_per_mol:.2f} cm³/mol\n"
            f"  Tb = {self.Tb:.2f} K, ω = {self.omega:.4f}"
        )


def _default_components_path() -> Path:
    """Resolve the default components.json location across source and packaged builds."""
    candidates: List[Path] = []

    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ""))
        if base:
            candidates.append(base / "data" / "pure_components" / "components.json")

    try:
        from importlib import resources

        resources_root = resources.files("pvtcore")
        resource_path = resources_root / "data" / "pure_components" / "components.json"
        with resources.as_file(resource_path) as resolved_path:
            candidates.append(resolved_path)
    except Exception:
        pass

    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    candidates.append(project_root / "data" / "pure_components" / "components.json")

    for candidate in candidates:
        if candidate and candidate.exists():
            return candidate

    return candidates[-1]


def load_components(json_path: Optional[Path] = None) -> Dict[str, Component]:
    """Load pure component data from JSON file.

    Args:
        json_path: Path to components JSON file. If None, uses default location
                  at data/pure_components/components.json relative to project root.

    Returns:
        Dictionary mapping component IDs (e.g., 'C1', 'N2') to Component objects.

    Raises:
        FileNotFoundError: If the JSON file is not found.
        json.JSONDecodeError: If the JSON file is malformed.
        KeyError: If required fields are missing from component data.

    Example:
        >>> components = load_components()
        >>> methane = components['C1']
        >>> print(methane.name)
        'Methane'
        >>> print(methane.MW)
        16.0425
    """
    if json_path is None:
        json_path = _default_components_path()

    json_path = Path(json_path)

    if not json_path.exists():
        raise FileNotFoundError(
            f"Component database not found at {json_path}. "
            "Please ensure the components.json file exists."
        )

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    components = {}
    for comp_id, comp_data in data['components'].items():
        # Parse optional family enum
        family = None
        family_str = comp_data.get('family')
        if family_str:
            try:
                family = ComponentFamily[family_str]
            except KeyError:
                pass  # Invalid family name, leave as None

        # Parse optional provenance
        provenance = None
        prov_data = comp_data.get('provenance')
        if prov_data:
            provenance = PropertyProvenance(
                source=prov_data.get('source', ''),
                reference=prov_data.get('reference'),
                method=prov_data.get('method'),
                uncertainty=prov_data.get('uncertainty'),
            )

        # Parse optional pseudo_type enum
        pseudo_type = None
        pseudo_type_str = comp_data.get('pseudo_type')
        if pseudo_type_str:
            try:
                pseudo_type = PseudoType[pseudo_type_str]
            except KeyError:
                pass

        components[comp_id] = Component(
            # Required fields
            name=comp_data['name'],
            formula=comp_data['formula'],
            Tc=comp_data['Tc'],
            Pc=comp_data['Pc'],
            Vc=comp_data['Vc'],
            omega=comp_data['omega'],
            MW=comp_data['MW'],
            Tb=comp_data['Tb'],
            # Optional fields with defaults
            note=comp_data.get('note'),
            id=comp_data.get('id', comp_id),
            aliases=comp_data.get('aliases'),
            cas=comp_data.get('cas'),
            smiles=comp_data.get('smiles'),
            inchi=comp_data.get('inchi'),
            inchikey=comp_data.get('inchikey'),
            isomer_group=comp_data.get('isomer_group'),
            family=family,
            groups=comp_data.get('groups'),
            provenance=provenance,
            is_pseudo=comp_data.get('is_pseudo', False),
            pseudo_type=pseudo_type,
            parent_plus=comp_data.get('parent_plus'),
            scn_index=comp_data.get('scn_index'),
        )

    return components


def get_component(component_id: str, components: Optional[Dict[str, Component]] = None) -> Component:
    """Get a component by its ID.

    Args:
        component_id: Component identifier (e.g., 'C1', 'N2', 'CO2')
        components: Pre-loaded components dictionary. If None, loads from default path.

    Returns:
        Component object for the specified ID.

    Raises:
        KeyError: If component_id is not found in the database.
        FileNotFoundError: If components dict is None and default file not found.

    Example:
        >>> methane = get_component('C1')
        >>> print(methane.Tc)
        190.6
    """
    if components is None:
        components = load_components()

    if component_id not in components:
        available = ', '.join(sorted(components.keys()))
        raise KeyError(
            f"Component '{component_id}' not found in database. "
            f"Available components: {available}"
        )

    return components[component_id]


# Module-level cache for lazy loading
_COMPONENTS_CACHE: Optional[Dict[str, Component]] = None


def get_components_cached() -> Dict[str, Component]:
    """Get cached components dictionary, loading if necessary.

    This function loads the components database once and caches it for
    subsequent calls, improving performance when accessing multiple components.

    Returns:
        Dictionary mapping component IDs to Component objects.

    Example:
        >>> components = get_components_cached()
        >>> methane = components['C1']
        >>> ethane = components['C2']
    """
    global _COMPONENTS_CACHE
    if _COMPONENTS_CACHE is None:
        _COMPONENTS_CACHE = load_components()
    return _COMPONENTS_CACHE
