"""Application-wide styling for the PVT Simulator GUI.

This module keeps QSS (Qt stylesheet) centralized so the main window can
apply a consistent, Cato-like dark theme and scalable spacing.
"""

from __future__ import annotations

MIN_UI_SCALE = 0.8
MAX_UI_SCALE = 1.6
DEFAULT_UI_SCALE = 1.10
UI_SCALE_STEP = 0.10


def clamp_ui_scale(scale: float) -> float:
    """Clamp UI scale into the supported desktop range."""
    return max(MIN_UI_SCALE, min(MAX_UI_SCALE, float(scale)))


def scale_metric(value: float, scale: float, *, reference_scale: float = 1.0) -> int:
    """Scale a pixel metric against a reference scale."""
    clamped = clamp_ui_scale(scale)
    return max(1, int(round(value * clamped / reference_scale)))


def build_cato_dark_stylesheet(*, scale: float = DEFAULT_UI_SCALE) -> str:
    """Return a dark QSS theme roughly aligned with the Pete/Cato window.

    Args:
        scale: UI scale factor applied to padding/radii/font sizes.
    """

    def px(value: float) -> int:
        return scale_metric(value, scale)

    return f"""
/* Base */
QMainWindow {{
  background: #0b1220;
}}

QWidget {{
  background: #0b1220;
  color: #e5e7eb;
  font-size: {px(12)}px;
}}

QToolTip {{
  background: #0f1a2b;
  color: #e5e7eb;
  border: 1px solid #223044;
  padding: {px(6)}px;
}}

/* Menu */
QMenuBar {{
  background: #0f1a2b;
  color: #e5e7eb;
}}
QMenuBar::item {{
  padding: {px(6)}px {px(10)}px;
  background: transparent;
}}
QMenuBar::item:selected {{
  background: #162844;
  border-radius: {px(8)}px;
}}

QMenu {{
  background: #0f1a2b;
  border: 1px solid #223044;
  padding: {px(6)}px;
}}
QMenu::item {{
  padding: {px(6)}px {px(10)}px;
  border-radius: {px(8)}px;
}}
QMenu::item:selected {{
  background: #162844;
}}
QMenu::separator {{
  height: 1px;
  margin: {px(6)}px {px(2)}px;
  background: #223044;
}}

/* Toolbars / status */
QToolBar {{
  background: #0f1a2b;
  border-bottom: 1px solid #1f2a3a;
  spacing: {px(8)}px;
  padding: {px(6)}px;
}}

QStatusBar {{
  background: #0f1a2b;
  border-top: 1px solid #1f2a3a;
  color: #9ca3af;
}}

/* Cards */
QFrame#PaneCard {{
  background: #0f1a2b;
  border: 1px solid #1f2a3a;
  border-radius: {px(14)}px;
}}

QLabel#PaneTitle {{
  background: transparent;
  color: #9ca3af;
  font-size: {px(11)}px;
}}

/* Inputs */
QLineEdit, QTextEdit, QTextBrowser {{
  background: #0f1a2b;
  border: 1px solid #223044;
  border-radius: {px(10)}px;
  padding: {px(8)}px;
  selection-background-color: #2b6cb0;
}}

QComboBox {{
  background: #121f34;
  border: 1px solid #223044;
  border-radius: {px(10)}px;
  padding: {px(6)}px {px(10)}px;
}}
QComboBox:hover {{
  background: #162844;
}}
QComboBox:disabled {{
  color: #64748b;
  background: #0c1524;
}}
QComboBox QAbstractItemView {{
  background: #0f1a2b;
  border: 1px solid #223044;
  selection-background-color: #162844;
  color: #e5e7eb;
}}

/* Buttons */
QPushButton, QToolButton {{
  background: #121f34;
  border: 1px solid #223044;
  border-radius: {px(12)}px;
  padding: {px(8)}px {px(12)}px;
}}
QPushButton:hover, QToolButton:hover {{
  background: #162844;
}}
QPushButton:pressed, QToolButton:pressed {{
  background: #1b3356;
}}
QPushButton:disabled, QToolButton:disabled {{
  color: #64748b;
  background: #0c1524;
}}

QPushButton#RunButton {{
  background: #1f6f3a;
  border: 1px solid #2d8a4a;
}}
QPushButton#RunButton:hover {{
  background: #248244;
}}

QPushButton#CancelButton {{
  background: #7a1f1f;
  border: 1px solid #a02a2a;
}}
QPushButton#CancelButton:hover {{
  background: #8d2424;
}}

/* Group boxes */
QGroupBox {{
  background: #0f1a2b;
  border: 1px solid #1f2a3a;
  border-radius: {px(12)}px;
  margin-top: {px(14)}px;
  padding: {px(10)}px;
}}
QGroupBox::title {{
  subcontrol-origin: margin;
  left: {px(12)}px;
  padding: 0 {px(6)}px;
}}

/* Tables */
QTableWidget {{
  background: #0f1a2b;
  alternate-background-color: #0c1524;
  gridline-color: #223044;
  border: 1px solid #223044;
  border-radius: {px(10)}px;
}}
QHeaderView::section {{
  background: #121f34;
  color: #e5e7eb;
  padding: {px(6)}px;
  border: 1px solid #223044;
}}

/* Tabs */
QTabWidget::pane {{
  border: 1px solid #223044;
  border-radius: {px(10)}px;
}}
QTabBar::tab {{
  background: #121f34;
  padding: {px(8)}px {px(12)}px;
  border-top-left-radius: {px(10)}px;
  border-top-right-radius: {px(10)}px;
  margin-right: {px(4)}px;
}}
QTabBar::tab:selected {{
  background: #162844;
}}

/* Splitters */
QSplitter::handle {{
  background: #1f2a3a;
}}
"""
