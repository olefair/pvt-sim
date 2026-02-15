"""PVT Simulator Desktop Application.

This package provides a Windows-native desktop GUI for the PVT simulator
using PySide6 (Qt). It implements the "thin GUI, thick engine" pattern
where all calculations are performed by pvtcore with strict validation.

Architecture:
    - schemas.py: Pydantic config/results schemas (API contract)
    - job_runner.py: Job execution, artifact writing, run history
    - workers.py: QThread workers for non-blocking execution
    - main.py: Application entry point and main window
    - widgets/: Custom Qt widgets for input/output
"""

__version__ = "0.1.0"
__app_name__ = "PVT Simulator"
