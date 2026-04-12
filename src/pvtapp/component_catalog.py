"""Shared component picker data for the application layer.

This module is intentionally GUI-free so audits and contract tests can import
the picker surface without pulling in PySide6.
"""

STANDARD_COMPONENTS = [
    "N2", "CO2", "H2S", "C1", "C2", "C3", "iC4", "nC4",
    "iC5", "nC5", "C6", "C7",
]


DEFAULT_COMPONENT_ROWS = [
    ("C1", 0.50),
    ("C2", 0.10),
    ("C3", 0.10),
    ("nC4", 0.10),
    ("nC5", 0.10),
    ("C6", 0.10),
]
