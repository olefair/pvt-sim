"""Unit tests for pure component database.

Tests validate component property values against NIST Chemistry WebBook
reference data to ensure database accuracy.
"""

import pytest
from pathlib import Path
from pvtcore.models.component import (
    build_component_alias_index,
    Component,
    get_component,
    get_components_cached,
    load_components,
    resolve_component_id,
)


class TestComponentDataValidation:
    """Test suite for validating component database against NIST reference values."""

    @pytest.fixture
    def components(self):
        """Load component database for testing."""
        return load_components()

    def test_load_components(self, components):
        """Test that component database loads successfully."""
        assert components is not None
        assert isinstance(components, dict)

        # Dataset has expanded beyond the legacy "16 component" set; require at least the legacy core.
        assert len(components) >= 16


    def test_all_components_present(self, components):
        """Test that all expected components are in the database."""
        expected_components = [
            'N2', 'CO2', 'H2S',
            'C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10',
            'iC4', 'iC5', 'neoC5'
        ]
        for comp_id in expected_components:
            assert comp_id in components, f"Component {comp_id} not found in database"

    def test_component_dataclass_structure(self, components):
        """Test that components have correct dataclass structure."""
        methane = components['C1']
        assert isinstance(methane, Component)
        assert hasattr(methane, 'name')
        assert hasattr(methane, 'formula')
        assert hasattr(methane, 'Tc')
        assert hasattr(methane, 'Pc')
        assert hasattr(methane, 'Vc')
        assert hasattr(methane, 'omega')
        assert hasattr(methane, 'MW')
        assert hasattr(methane, 'Tb')

    # ========================================================================
    # NITROGEN (N2) - NIST Reference Validation
    # ========================================================================

    def test_nitrogen_critical_temperature(self, components):
        """Validate N2 critical temperature against NIST (126.19 K)."""
        n2 = components['N2']
        assert n2.Tc == pytest.approx(126.19, rel=0.001)

    def test_nitrogen_critical_pressure(self, components):
        """Validate N2 critical pressure against NIST (3.3978 MPa)."""
        n2 = components['N2']
        assert n2.Pc_MPa == pytest.approx(3.3978, rel=0.001)

    def test_nitrogen_molecular_weight(self, components):
        """Validate N2 molecular weight (28.0134 g/mol)."""
        n2 = components['N2']
        assert n2.MW == pytest.approx(28.0134, rel=0.0001)

    def test_nitrogen_boiling_point(self, components):
        """Validate N2 normal boiling point (77.34 K)."""
        n2 = components['N2']
        assert n2.Tb == pytest.approx(77.34, rel=0.001)

    def test_nitrogen_acentric_factor(self, components):
        """Validate N2 acentric factor (0.039)."""
        n2 = components['N2']
        assert n2.omega == pytest.approx(0.039, abs=0.002)

    # ========================================================================
    # CARBON DIOXIDE (CO2) - NIST Reference Validation
    # ========================================================================

    def test_co2_critical_temperature(self, components):
        """Validate CO2 critical temperature against NIST (304.18 K)."""
        co2 = components['CO2']
        assert co2.Tc == pytest.approx(304.18, rel=0.001)

    def test_co2_critical_pressure(self, components):
        """Validate CO2 critical pressure against NIST (7.38 MPa)."""
        co2 = components['CO2']
        assert co2.Pc_MPa == pytest.approx(7.38, rel=0.01)

    def test_co2_critical_volume(self, components):
        """Validate CO2 critical volume against NIST (91.9 cm³/mol)."""
        co2 = components['CO2']
        assert co2.Vc_cm3_per_mol == pytest.approx(91.9, rel=0.01)

    def test_co2_molecular_weight(self, components):
        """Validate CO2 molecular weight (44.0095 g/mol)."""
        co2 = components['CO2']
        assert co2.MW == pytest.approx(44.0095, rel=0.0001)

    def test_co2_acentric_factor(self, components):
        """Validate CO2 acentric factor (0.239)."""
        co2 = components['CO2']
        assert co2.omega == pytest.approx(0.239, abs=0.005)

    # ========================================================================
    # HYDROGEN SULFIDE (H2S) - NIST Reference Validation
    # ========================================================================

    def test_h2s_critical_temperature(self, components):
        """Validate H2S critical temperature against NIST (373.3 K)."""
        h2s = components['H2S']
        assert h2s.Tc == pytest.approx(373.3, rel=0.001)

    def test_h2s_critical_pressure(self, components):
        """Validate H2S critical pressure against NIST (8.96 MPa)."""
        h2s = components['H2S']
        assert h2s.Pc_MPa == pytest.approx(8.96, rel=0.01)

    def test_h2s_molecular_weight(self, components):
        """Validate H2S molecular weight (34.081 g/mol)."""
        h2s = components['H2S']
        assert h2s.MW == pytest.approx(34.081, rel=0.0001)

    def test_h2s_boiling_point(self, components):
        """Validate H2S normal boiling point (212.87 K)."""
        h2s = components['H2S']
        assert h2s.Tb == pytest.approx(212.87, rel=0.001)

    def test_h2s_acentric_factor(self, components):
        """Validate H2S acentric factor (0.081)."""
        h2s = components['H2S']
        assert h2s.omega == pytest.approx(0.081, abs=0.005)

    # ========================================================================
    # METHANE (C1) - NIST Reference Validation
    # ========================================================================

    def test_methane_critical_temperature(self, components):
        """Validate methane critical temperature against NIST (190.6 K)."""
        methane = components['C1']
        assert methane.Tc == pytest.approx(190.6, rel=0.002)

    def test_methane_critical_pressure(self, components):
        """Validate methane critical pressure against NIST (4.61 MPa)."""
        methane = components['C1']
        assert methane.Pc_MPa == pytest.approx(4.61, rel=0.01)

    def test_methane_critical_volume(self, components):
        """Validate methane critical volume against NIST (98.52 cm³/mol)."""
        methane = components['C1']
        assert methane.Vc_cm3_per_mol == pytest.approx(98.52, rel=0.01)

    def test_methane_molecular_weight(self, components):
        """Validate methane molecular weight (16.0425 g/mol)."""
        methane = components['C1']
        assert methane.MW == pytest.approx(16.0425, rel=0.0001)

    def test_methane_boiling_point(self, components):
        """Validate methane normal boiling point (111 K)."""
        methane = components['C1']
        assert methane.Tb == pytest.approx(111.0, rel=0.02)

    def test_methane_acentric_factor(self, components):
        """Validate methane acentric factor (0.011)."""
        methane = components['C1']
        assert methane.omega == pytest.approx(0.011, abs=0.002)

    # ========================================================================
    # ETHANE (C2) - NIST Reference Validation
    # ========================================================================

    def test_ethane_critical_temperature(self, components):
        """Validate ethane critical temperature against NIST (305.3 K)."""
        ethane = components['C2']
        assert ethane.Tc == pytest.approx(305.3, rel=0.001)

    def test_ethane_critical_pressure(self, components):
        """Validate ethane critical pressure against NIST (4.9 MPa)."""
        ethane = components['C2']
        assert ethane.Pc_MPa == pytest.approx(4.9, rel=0.02)

    def test_ethane_critical_volume(self, components):
        """Validate ethane critical volume against NIST (147 cm³/mol)."""
        ethane = components['C2']
        assert ethane.Vc_cm3_per_mol == pytest.approx(147, rel=0.01)

    def test_ethane_molecular_weight(self, components):
        """Validate ethane molecular weight (30.069 g/mol)."""
        ethane = components['C2']
        assert ethane.MW == pytest.approx(30.069, rel=0.0001)

    def test_ethane_acentric_factor(self, components):
        """Validate ethane acentric factor (0.099)."""
        ethane = components['C2']
        assert ethane.omega == pytest.approx(0.099, abs=0.002)

    # ========================================================================
    # PROPANE (C3) - NIST Reference Validation
    # ========================================================================

    def test_propane_critical_temperature(self, components):
        """Validate propane critical temperature against NIST (369.9 K)."""
        propane = components['C3']
        assert propane.Tc == pytest.approx(369.9, rel=0.001)

    def test_propane_critical_pressure(self, components):
        """Validate propane critical pressure against NIST (4.25 MPa)."""
        propane = components['C3']
        assert propane.Pc_MPa == pytest.approx(4.25, rel=0.01)

    def test_propane_molecular_weight(self, components):
        """Validate propane molecular weight (44.0956 g/mol)."""
        propane = components['C3']
        assert propane.MW == pytest.approx(44.0956, rel=0.0001)

    def test_propane_acentric_factor(self, components):
        """Validate propane acentric factor (0.153)."""
        propane = components['C3']
        assert propane.omega == pytest.approx(0.153, abs=0.002)

    # ========================================================================
    # N-BUTANE (C4) - NIST Reference Validation
    # ========================================================================

    def test_butane_critical_temperature(self, components):
        """Validate n-butane critical temperature against NIST (425 K)."""
        butane = components['C4']
        assert butane.Tc == pytest.approx(425.0, rel=0.003)

    def test_butane_critical_pressure(self, components):
        """Validate n-butane critical pressure against NIST (3.8 MPa)."""
        butane = components['C4']
        assert butane.Pc_MPa == pytest.approx(3.8, rel=0.01)

    def test_butane_molecular_weight(self, components):
        """Validate n-butane molecular weight (58.1222 g/mol)."""
        butane = components['C4']
        assert butane.MW == pytest.approx(58.1222, rel=0.0001)

    def test_butane_acentric_factor(self, components):
        """Validate n-butane acentric factor (0.199)."""
        butane = components['C4']
        assert butane.omega == pytest.approx(0.199, abs=0.002)

    # ========================================================================
    # ISOBUTANE (iC4) - NIST Reference Validation
    # ========================================================================

    def test_isobutane_critical_temperature(self, components):
        """Validate isobutane critical temperature against NIST (407.7 K)."""
        isobutane = components['iC4']
        assert isobutane.Tc == pytest.approx(407.7, rel=0.002)

    def test_isobutane_critical_pressure(self, components):
        """Validate isobutane critical pressure against NIST (3.65 MPa)."""
        isobutane = components['iC4']
        assert isobutane.Pc_MPa == pytest.approx(3.65, rel=0.015)

    def test_isobutane_acentric_factor(self, components):
        """Validate isobutane acentric factor (0.183)."""
        isobutane = components['iC4']
        assert isobutane.omega == pytest.approx(0.183, abs=0.002)

    # ========================================================================
    # N-DECANE (C10) - NIST Reference Validation
    # ========================================================================

    def test_decane_critical_temperature(self, components):
        """Validate n-decane critical temperature against NIST (617.8 K)."""
        decane = components['C10']
        assert decane.Tc == pytest.approx(617.8, rel=0.002)

    def test_decane_critical_pressure(self, components):
        """Validate n-decane critical pressure against NIST (2.11 MPa)."""
        decane = components['C10']
        assert decane.Pc_MPa == pytest.approx(2.11, rel=0.04)

    def test_decane_molecular_weight(self, components):
        """Validate n-decane molecular weight (142.2817 g/mol)."""
        decane = components['C10']
        assert decane.MW == pytest.approx(142.2817, rel=0.0001)

    def test_decane_boiling_point(self, components):
        """Validate n-decane normal boiling point (447.2 K)."""
        decane = components['C10']
        assert decane.Tb == pytest.approx(447.2, rel=0.001)

    def test_decane_acentric_factor(self, components):
        """Validate n-decane acentric factor (0.4884)."""
        decane = components['C10']
        assert decane.omega == pytest.approx(0.4884, abs=0.005)

    # ========================================================================
    # PROPERTY RANGE VALIDATION
    # ========================================================================

    def test_all_critical_temperatures_positive(self, components):
        """Test that all critical temperatures are positive."""
        for comp_id, comp in components.items():
            assert comp.Tc > 0, f"{comp_id} has non-positive Tc"

    def test_all_critical_pressures_positive(self, components):
        """Test that all critical pressures are positive."""
        for comp_id, comp in components.items():
            assert comp.Pc > 0, f"{comp_id} has non-positive Pc"

    def test_all_critical_volumes_positive(self, components):
        """Test that all critical volumes are positive."""
        for comp_id, comp in components.items():
            assert comp.Vc > 0, f"{comp_id} has non-positive Vc"

    def test_all_molecular_weights_positive(self, components):
        """Test that all molecular weights are positive."""
        for comp_id, comp in components.items():
            assert comp.MW > 0, f"{comp_id} has non-positive MW"

    def test_all_boiling_points_positive(self, components):
        """Test that all boiling points are positive."""
        for comp_id, comp in components.items():
            assert comp.Tb > 0, f"{comp_id} has non-positive Tb"

    def test_acentric_factor_reasonable_range(self, components):
        """Test that acentric factors are in reasonable range (-0.5 to 2.0)."""
        for comp_id, comp in components.items():
            assert -0.5 <= comp.omega <= 2.0, \
                f"{comp_id} acentric factor {comp.omega} outside reasonable range"

    def test_boiling_point_less_than_critical_temperature(self, components):
        """Test that Tb < Tc for all components."""
        for comp_id, comp in components.items():
            assert comp.Tb < comp.Tc, \
                f"{comp_id}: Tb ({comp.Tb} K) should be less than Tc ({comp.Tc} K)"

    # ========================================================================
    # UNIT CONVERSION TESTS
    # ========================================================================

    def test_pressure_unit_conversions(self, components):
        """Test pressure unit conversion properties."""
        methane = components['C1']
        # Test Pa to bar conversion
        assert methane.Pc_bar == pytest.approx(methane.Pc / 1e5, rel=1e-10)
        # Test Pa to MPa conversion
        assert methane.Pc_MPa == pytest.approx(methane.Pc / 1e6, rel=1e-10)

    def test_volume_unit_conversions(self, components):
        """Test volume unit conversion properties."""
        methane = components['C1']
        # Test m³/mol to cm³/mol conversion
        assert methane.Vc_cm3_per_mol == pytest.approx(methane.Vc * 1e6, rel=1e-10)
        # Test m³/mol to L/mol conversion
        assert methane.Vc_L_per_mol == pytest.approx(methane.Vc * 1e3, rel=1e-10)

    # ========================================================================
    # FUNCTION TESTS
    # ========================================================================

    def test_get_component_function(self):
        """Test get_component() function."""
        methane = get_component('C1')
        assert methane.name == 'Methane'
        assert methane.formula == 'CH4'

    def test_get_component_accepts_alias(self):
        """Test that aliases resolve to the canonical component."""
        n_butane = get_component('nC4')
        assert n_butane.id == 'C4'
        assert n_butane.name == 'n-Butane'

    def test_get_component_invalid_id(self):
        """Test that get_component() raises KeyError for invalid ID."""
        with pytest.raises(KeyError):
            get_component('INVALID')

    def test_resolve_component_id_accepts_aliases_names_and_formulas(self):
        """Test the canonical component resolver."""
        components = load_components()
        assert resolve_component_id('nC4', components) == 'C4'
        assert resolve_component_id('n-pentane', components) == 'C5'
        assert resolve_component_id('methane', components) == 'C1'
        assert resolve_component_id('CH4', components) == 'C1'

    def test_component_alias_index_contains_expected_aliases(self):
        """Test the alias index generated from the component database."""
        alias_index = build_component_alias_index()
        assert alias_index['nc4'] == 'C4'
        assert alias_index['n-pentane'] == 'C5'
        assert alias_index['methane'] == 'C1'

    def test_get_components_cached(self):
        """Test cached component loading."""
        components1 = get_components_cached()
        components2 = get_components_cached()
        # Should return the same cached object
        assert components1 is components2

    def test_component_repr(self, components):
        """Test Component __repr__ method."""
        methane = components['C1']
        repr_str = repr(methane)
        assert 'Methane' in repr_str
        assert 'CH4' in repr_str
        assert '16.0425' in repr_str

    def test_component_str(self, components):
        """Test Component __str__ method."""
        methane = components['C1']
        str_repr = str(methane)
        assert 'Methane' in str_repr
        assert 'CH4' in str_repr
        assert '190.60 K' in str_repr
        assert '4.6100 MPa' in str_repr

    # ========================================================================
    # ALKANE SERIES TRENDS
    # ========================================================================

    def test_alkane_tc_increases_with_carbon_number(self, components):
        """Test that critical temperature increases with carbon number for n-alkanes."""
        alkanes = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10']
        for i in range(len(alkanes) - 1):
            tc_i = components[alkanes[i]].Tc
            tc_next = components[alkanes[i + 1]].Tc
            assert tc_next > tc_i, \
                f"Tc should increase from {alkanes[i]} to {alkanes[i+1]}"

    def test_alkane_mw_increases_with_carbon_number(self, components):
        """Test that molecular weight increases with carbon number for n-alkanes."""
        alkanes = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10']
        for i in range(len(alkanes) - 1):
            mw_i = components[alkanes[i]].MW
            mw_next = components[alkanes[i + 1]].MW
            assert mw_next > mw_i, \
                f"MW should increase from {alkanes[i]} to {alkanes[i+1]}"

    def test_alkane_omega_increases_with_carbon_number(self, components):
        """Test that acentric factor increases with carbon number for n-alkanes."""
        alkanes = ['C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7', 'C8', 'C9', 'C10']
        for i in range(len(alkanes) - 1):
            omega_i = components[alkanes[i]].omega
            omega_next = components[alkanes[i + 1]].omega
            assert omega_next > omega_i, \
                f"omega should increase from {alkanes[i]} to {alkanes[i+1]}"

    # ========================================================================
    # ISOMER COMPARISONS
    # ========================================================================

    def test_butane_isomers_same_mw(self, components):
        """Test that n-butane and isobutane have the same molecular weight."""
        n_butane = components['C4']
        isobutane = components['iC4']
        assert n_butane.MW == pytest.approx(isobutane.MW, rel=1e-10)

    def test_pentane_isomers_same_mw(self, components):
        """Test that pentane isomers have the same molecular weight."""
        n_pentane = components['C5']
        isopentane = components['iC5']
        neopentane = components['neoC5']
        assert n_pentane.MW == pytest.approx(isopentane.MW, rel=1e-10)
        assert n_pentane.MW == pytest.approx(neopentane.MW, rel=1e-10)

    def test_branching_lowers_tc(self, components):
        """Test that branching generally lowers critical temperature."""
        # For butanes: n-butane should have higher Tc than isobutane
        assert components['C4'].Tc > components['iC4'].Tc
        # For pentanes: n-pentane > isopentane > neopentane
        assert components['C5'].Tc > components['iC5'].Tc
        assert components['iC5'].Tc > components['neoC5'].Tc


class TestComponentDatabaseIntegrity:
    """Test suite for database file integrity and structure."""

    def test_json_file_exists(self):
        """Test that the components JSON file exists."""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        json_path = project_root / "data" / "pure_components" / "components.json"
        assert json_path.exists(), "Component database JSON file not found"

    def test_load_from_custom_path(self):
        """Test loading components from a custom path."""
        current_file = Path(__file__)
        project_root = current_file.parent.parent.parent
        json_path = project_root / "data" / "pure_components" / "components.json"
        components = load_components(json_path)

        # Dataset has expanded beyond the legacy "16 component" set; require at least the legacy core.
        assert len(components) >= 16


    def test_invalid_path_raises_error(self):
        """Test that loading from invalid path raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_components(Path("/nonexistent/path/components.json"))
