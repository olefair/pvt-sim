"""Custom Qt widgets for PVT Simulator GUI."""

from pvtapp.widgets.composition_input import CompositionInputWidget
from pvtapp.widgets.conditions_input import ConditionsInputWidget
from pvtapp.widgets.results_view import ResultsTableWidget, ResultsPlotWidget, ResultsSidebarWidget, UnitConverterWidget
from pvtapp.widgets.diagnostics_view import DiagnosticsWidget
from pvtapp.widgets.inputs_panel import InputsPanel
from pvtapp.widgets.critical_props_view import CriticalPropsWidget
from pvtapp.widgets.interaction_params_view import InteractionParamsWidget
from pvtapp.widgets.text_output_view import TextOutputWidget
from pvtapp.widgets.run_log_view import RunLogWidget
from pvtapp.widgets.two_pane_workspace import TwoPaneWorkspace, ViewSpec

__all__ = [
    'CompositionInputWidget',
    'ConditionsInputWidget',
    'ResultsTableWidget',
    'ResultsPlotWidget',
    'ResultsSidebarWidget',
    'UnitConverterWidget',
    'DiagnosticsWidget',
    'InputsPanel',
    'CriticalPropsWidget',
    'InteractionParamsWidget',
    'TextOutputWidget',
    'RunLogWidget',
    'TwoPaneWorkspace',
    'ViewSpec',
]
