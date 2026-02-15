"""Custom Qt widgets for PVT Simulator GUI."""

from pvtapp.widgets.composition_input import CompositionInputWidget
from pvtapp.widgets.conditions_input import ConditionsInputWidget
from pvtapp.widgets.results_view import ResultsTableWidget, ResultsPlotWidget
from pvtapp.widgets.diagnostics_view import DiagnosticsWidget

__all__ = [
    'CompositionInputWidget',
    'ConditionsInputWidget',
    'ResultsTableWidget',
    'ResultsPlotWidget',
    'DiagnosticsWidget',
]
